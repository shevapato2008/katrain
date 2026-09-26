"""Capture transactions with real JPEG/geometry persistence and fake hardware."""

import hashlib
import json
import threading
import time
from dataclasses import replace

import cv2
import numpy as np
import pytest

from katrain.vision.geometry_lock import GeometryLock
from katrain.web.admin.vision_sgf import prepare_vision_sgf


class Camera:
    def __init__(self):
        self.seq = 10
        self.calls = []
        self.stale = False
        self.same_seq = False
        self.connected = True

    def is_connected(self):
        return self.connected

    def grab_fresh(self, after_ts=None, settle_ms=0):
        self.calls.append((after_ts, settle_ms))
        if after_ts == 0:
            return np.zeros((32, 48, 3), np.uint8), self.seq, time.monotonic() - 1
        if not self.same_seq:
            self.seq += 1
        ts = after_ts - 1 if self.stale else max(time.monotonic(), after_ts + settle_ms / 1000 + 0.01)
        return np.full((32, 48, 3), self.seq, np.uint8), self.seq, ts


class Led:
    def __init__(self):
        self.calls = []

    def is_connected(self):
        return True

    def set_points(self, points, strict=False):
        self.calls.append(points)
        return {"ok": True, "shown_at": time.monotonic()}

    def clear(self, strict=False):
        self.calls.append([])
        return {"ok": True, "shown_at": time.monotonic()}


@pytest.fixture
def context(tmp_path):
    from katrain.web.admin.vision_capture_txn import VisionCaptureCoordinator

    xs = np.linspace(0, 47, 19).astype(np.float32)
    ys = np.linspace(0, 31, 19).astype(np.float32)
    geometry = GeometryLock(
        corners=np.array([[0, 0], [47, 0], [47, 31], [0, 31]], np.float32),
        points=np.stack(np.meshgrid(xs, ys), axis=-1),
        xs=xs,
        ys=ys,
        M=np.eye(3),
        Minv=np.eye(3),
        out_size=48,
        baseline=np.zeros((19, 19, 3), np.float32),
        confidence=0.99,
        source_width=48,
        source_height=32,
    )
    sgf = prepare_vision_sgf("(;SZ[19];B[aa];W[];W[bb];B[cc])")
    coordinator = VisionCaptureCoordinator(tmp_path)
    kwargs = dict(
        sgf=sgf,
        game_id=sgf.game_id,
        mode="stones2",
        geometry=geometry,
        geometry_revision="geo-1",
        geometry_source="opencv_empty_board",
        camera=Camera(),
        operator_confirmed=True,
        settle_ms=0,
    )
    return coordinator, kwargs, tmp_path / sgf.game_id


def capture(context, index=-1, **changes):
    coordinator, kwargs, _ = context
    return coordinator.capture(**{**kwargs, "move_index": index, **changes})


def snapshot(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


def test_initial_empty_publishes_hashes_and_legacy_fields(context):
    result = capture(context)
    coordinator, kwargs, directory = context
    manifest = coordinator.load_session(kwargs["game_id"])
    assert manifest["schema_version"] == 1
    assert manifest["mode"] == "stones2"
    assert manifest["class_names"] == ["black", "white"]
    assert manifest["next_step"] == 0
    assert manifest["sgf_sha256"] == kwargs["sgf"].sgf_sha256
    for path_key, hash_key in [
        ("sgf_path", "sgf_sha256"),
        ("geometry_path", "geometry_sha256"),
        ("geometry_sidecar_path", "geometry_sidecar_sha256"),
    ]:
        assert hashlib.sha256((directory / manifest[path_key]).read_bytes()).hexdigest() == manifest[hash_key]
    frame = manifest["frames"][0]
    assert frame["frame_kind"] == "initial_empty"
    assert frame["led_point"] is None
    assert frame["board_hash"] == hashlib.sha1(b"[]").hexdigest()[:16]
    assert frame["applied_move_index"] == -1
    assert frame["next_guided_move_index"] == 0
    assert frame["captured_at_source"] == "runtime_observed_at"
    assert frame["camera_seq"] > 10
    assert frame["camera_monotonic_ts"] > frame["confirmation_monotonic_ts"]
    assert frame["qa_status"] == "operator_confirmed"
    assert frame["mode"] == "stones2"
    image = directory / frame["file"]
    assert cv2.imread(str(image)) is not None
    assert result["sha256"] == hashlib.sha256(image.read_bytes()).hexdigest()
    assert result["frame_id"] == frame["frame_id"]


def test_strict_order_skips_pass_and_recovers_after_restart(context):
    from katrain.web.admin.vision_capture_txn import VisionCaptureCoordinator, VisionCaptureError

    with pytest.raises(VisionCaptureError) as error:
        capture(context, 0)
    assert error.value.status_code == 409
    assert context[1]["camera"].calls == []
    capture(context)
    capture(context, 0)
    with pytest.raises(VisionCaptureError):
        capture(context, 1)
    capture(context, 2)
    coordinator = VisionCaptureCoordinator(context[2].parent)
    assert coordinator.load_session(context[1]["game_id"])["next_step"] == 3
    result = coordinator.capture(**context[1], move_index=3)
    assert result["idempotent"] is False
    assert coordinator.load_session(context[1]["game_id"])["next_step"] is None


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"operator_confirmed": False}, 409),
        ({"mode": "bad"}, 422),
        ({"game_id": "../escape"}, 422),
        ({"move_index": True}, 422),
        ({"geometry_revision": ""}, 409),
        ({"geometry": None}, 409),
        ({"mode": "led4"}, 409),
    ],
)
def test_preflight_refuses_before_camera_or_disk(context, changes, status):
    from katrain.web.admin.vision_capture_txn import VisionCaptureError

    with pytest.raises(VisionCaptureError) as error:
        capture(context, **changes)
    assert error.value.status_code == status
    assert not context[1]["camera"].calls
    assert not context[2].exists()


def test_hash_and_geometry_changes_refused_before_acquisition(context):
    from katrain.web.admin.vision_capture_txn import VisionCaptureError

    capture(context)
    before = snapshot(context[2])
    context[1]["camera"].calls.clear()
    invalid = replace(context[1]["sgf"], original_sgf="(;SZ[19];B[dd])")
    for changes in [
        {"sgf": invalid},
        {"mode": "led4", "led": Led()},
        {"geometry_revision": "geo-2"},
        {"geometry": replace(context[1]["geometry"], M=np.eye(3) * 2)},
    ]:
        with pytest.raises(VisionCaptureError):
            capture(context, 0, **changes)
    assert context[1]["camera"].calls == []
    assert snapshot(context[2]) == before


@pytest.mark.parametrize("attribute", ["stale", "same_seq"])
def test_timeout_non_null_or_unadvanced_sequence_never_publishes(context, attribute):
    from katrain.web.admin.vision_capture_txn import VisionCaptureError

    capture(context)
    before = snapshot(context[2])
    setattr(context[1]["camera"], attribute, True)
    with pytest.raises(VisionCaptureError) as error:
        capture(context, 0)
    assert error.value.status_code == 503
    assert snapshot(context[2]) == before


def test_idempotence_needs_no_camera_and_explicit_retake_preserves_later_frames(context):
    capture(context)
    capture(context, 0)
    capture(context, 2)
    coordinator, kwargs, directory = context
    before = coordinator.load_session(kwargs["game_id"])
    bytes_before = snapshot(directory)
    kwargs["camera"].calls.clear()
    result = capture(context, 0)
    assert result["idempotent"] is True
    assert not kwargs["camera"].calls
    assert snapshot(directory) == bytes_before
    capture(context, 0, overwrite_existing=True)
    after = coordinator.load_session(kwargs["game_id"])
    assert after["frames"][0] == before["frames"][0]
    assert after["frames"][2] == before["frames"][2]
    assert after["frames"][1]["file"] != before["frames"][1]["file"]
    assert (directory / before["frames"][1]["file"]).read_bytes() == bytes_before[before["frames"][1]["file"]]
    assert after["next_step"] == 3


@pytest.mark.parametrize("failure", ["image", "manifest"])
def test_failed_retake_leaves_manifest_and_referenced_files_byte_identical(context, monkeypatch, failure):
    from katrain.web.admin import vision_capture_txn as txn

    capture(context)
    capture(context, 0)
    capture(context, 2)
    before = snapshot(context[2])
    if failure == "image":
        monkeypatch.setattr(cv2, "imwrite", lambda *args, **kwargs: False)
    else:
        original = txn.os.replace

        def fail_manifest(src, dst):
            if str(dst).endswith("manifest.json"):
                raise OSError("disk failure")
            return original(src, dst)

        monkeypatch.setattr(txn.os, "replace", fail_manifest)
    with pytest.raises(txn.VisionCaptureError) as error:
        capture(context, 0, overwrite_existing=True)
    assert error.value.status_code == 507
    after = snapshot(context[2])
    assert after == before


@pytest.mark.parametrize("corruption", ["json", "schema", "image", "sidecar", "order"])
def test_existing_corrupt_manifest_is_503_and_never_bootstrapped(context, corruption):
    from katrain.web.admin.vision_capture_txn import VisionCaptureError

    capture(context)
    manifest_path = context[2] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if corruption == "json":
        manifest_path.write_text("{broken")
    elif corruption == "image":
        (context[2] / manifest["frames"][0]["file"]).write_bytes(b"corrupt")
    elif corruption == "sidecar":
        (context[2] / manifest["geometry_sidecar_path"]).write_text("{}")
    else:
        if corruption == "schema":
            manifest["schema_version"] = 999
        else:
            manifest["frames"][0]["applied_move_index"] = 0
        manifest_path.write_text(json.dumps(manifest))
    before = snapshot(context[2])
    context[1]["camera"].calls.clear()
    with pytest.raises(VisionCaptureError) as error:
        capture(context)
    assert error.value.status_code == 503
    assert not context[1]["camera"].calls
    assert snapshot(context[2]) == before


def test_led_legacy_runs_only_in_staging_and_stale_adapter_rejects(context, monkeypatch):
    from katrain.web.core import baipu_capture
    from katrain.web.admin.vision_capture_txn import VisionCaptureError

    original = baipu_capture.run_capture
    staging = []

    def inspect(**kwargs):
        staging.append(kwargs["out_dir"])
        assert kwargs["fiducial_mode"] == "off"
        assert kwargs["out_dir"] != str(context[2].parent)
        return original(**kwargs)

    monkeypatch.setattr(baipu_capture, "run_capture", inspect)
    led = Led()
    capture(context, mode="led4", led=led)
    manifest = context[0].load_session(context[1]["game_id"])
    assert manifest["class_names"] == ["black", "white", "led_red", "led_green"]
    assert manifest["frames"][0]["led_point"] == {"row": 0, "col": 0, "color": "black"}
    assert manifest["frames"][0]["board_hash"] == hashlib.sha1(b"[]").hexdigest()[:16]
    before = snapshot(context[2])
    context[1]["camera"].stale = True
    with pytest.raises(VisionCaptureError) as error:
        capture(context, 0, mode="led4", led=led)
    assert error.value.status_code == 503
    assert snapshot(context[2]) == before
    from pathlib import Path

    assert all(not Path(path).exists() for path in staging)


def test_shared_lock_serializes_capture_against_disconnect(context):
    from katrain.web.admin.vision_capture_txn import VisionCaptureCoordinator

    lock = threading.RLock()
    coordinator = VisionCaptureCoordinator(context[2].parent, lock=lock)
    started, release, disconnected = threading.Event(), threading.Event(), threading.Event()
    camera = context[1]["camera"]
    original = camera.grab_fresh

    def blocking(after_ts=None, settle_ms=0):
        if after_ts != 0:
            started.set()
            assert release.wait(3)
        return original(after_ts, settle_ms)

    camera.grab_fresh = blocking
    results = []
    worker = threading.Thread(target=lambda: results.append(coordinator.capture(**context[1], move_index=-1)))

    def disconnect():
        with lock:
            camera.connected = False
            disconnected.set()

    worker.start()
    assert started.wait(3)
    peer = threading.Thread(target=disconnect)
    peer.start()
    assert not disconnected.wait(0.05)
    release.set()
    worker.join(3)
    peer.join(3)
    assert len(results) == 1 and disconnected.is_set()


def test_led_final_frame_is_after_blackout_completion(context):
    led = Led()
    capture(context, mode="led4", led=led)
    capture(context, 0, mode="led4", led=led)
    capture(context, 2, mode="led4", led=led)
    completed = []

    def clear(strict=False):
        completed.append(time.monotonic())
        return {"ok": True, "shown_at": None}

    led.clear = clear
    result = capture(context, 3, mode="led4", led=led)
    assert result["frame_kind"] == "final_no_led"
    assert result["led_point"] is None
    assert result["acquisition_barrier_monotonic_ts"] >= completed[0]


def test_first_asset_failure_publishes_no_partial_session(context, monkeypatch):
    from katrain.web.admin import vision_capture_txn as txn

    original = txn._write_bytes

    def fail_sidecar(path, data):
        if path.name == "geometry.json":
            raise OSError("disk failure")
        return original(path, data)

    monkeypatch.setattr(txn, "_write_bytes", fail_sidecar)
    with pytest.raises(txn.VisionCaptureError) as error:
        capture(context)
    assert error.value.status_code == 507
    assert not context[2].exists()
    assert snapshot(context[2].parent) == {}


def test_non_finite_saved_confirmation_barrier_is_corrupt(context):
    from katrain.web.admin.vision_capture_txn import VisionCaptureError

    capture(context)
    path = context[2] / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["frames"][0]["confirmation_monotonic_ts"] = float("nan")
    path.write_text(json.dumps(manifest))
    with pytest.raises(VisionCaptureError) as error:
        context[0].load_session(context[1]["game_id"])
    assert error.value.status_code == 503


def test_even_a_frame_id_collision_cannot_overwrite_referenced_image(context, monkeypatch):
    from katrain.web.admin import vision_capture_txn as txn

    first = capture(context)
    before = snapshot(context[2])
    monkeypatch.setattr(txn, "uuid4", lambda: first["frame_id"])
    with pytest.raises(txn.VisionCaptureError) as error:
        capture(context, overwrite_existing=True)
    assert error.value.status_code == 507
    assert snapshot(context[2]) == before
