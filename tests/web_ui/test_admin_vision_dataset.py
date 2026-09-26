"""Freeze actual capture assets; hardware is replaced only at acquisition."""

import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from katrain.vision.classes import CLASS_NAMES
from katrain.vision.geometry_lock import GeometryLock
from katrain.web.admin.vision_capture_txn import VisionCaptureCoordinator
from katrain.web.admin.vision_sgf import prepare_vision_sgf


class Camera:
    def __init__(self, visible_led=False):
        self.seq = 1
        self.visible_led = visible_led

    def is_connected(self):
        return True

    def grab_fresh(self, after_ts=None, settle_ms=0):
        image = np.full((210, 210, 3), 100, np.uint8)
        if self.visible_led:
            image[18:23, 18:23] = (0, 0, 255)
            image[28:33, 28:33] = (0, 255, 0)
        if after_ts == 0:
            return image, self.seq, time.monotonic() - 1
        self.seq += 1
        return image, self.seq, max(time.monotonic(), after_ts + settle_ms / 1000 + 0.01)


class Led:
    def is_connected(self):
        return True

    def set_points(self, points, strict=False):
        return {"ok": True, "shown_at": time.monotonic()}

    def clear(self, strict=False):
        return {"ok": True, "shown_at": time.monotonic()}


@pytest.fixture
def session(tmp_path):
    xs = np.arange(10, 200, 10, dtype=np.float32)
    geometry = GeometryLock(
        corners=np.array([[0, 0], [209, 0], [209, 209], [0, 209]], np.float32),
        points=np.stack(np.meshgrid(xs, xs), axis=-1),
        xs=xs,
        ys=xs,
        M=np.eye(3),
        Minv=np.eye(3),
        out_size=210,
        baseline=np.zeros((19, 19, 3), np.float32),
        confidence=0.99,
        source_width=210,
        source_height=210,
    )
    coordinator = VisionCaptureCoordinator(tmp_path / "captures")
    sgf = prepare_vision_sgf("(;SZ[19];B[bb];W[];W[cc])")
    kwargs = dict(
        sgf=sgf,
        game_id=sgf.game_id,
        geometry=geometry,
        geometry_revision="geo-1",
        geometry_source="opencv_empty_board",
        mode="stones2",
        camera=Camera(),
        operator_confirmed=True,
        settle_ms=0,
    )
    return coordinator, kwargs, tmp_path / "datasets"


def populate(session, *, mode="stones2", visible_led=False, count=3):
    coordinator, kwargs, _ = session
    kwargs.update(mode=mode, camera=Camera(visible_led), led=Led() if mode == "led4" else None)
    for index in (-1, 0, 2)[:count]:
        coordinator.capture(**kwargs, move_index=index)
    return coordinator.load_session(kwargs["game_id"])


def builder(session):
    from katrain.web.admin.vision_dataset import VisionDatasetBuilder

    return VisionDatasetBuilder(session[0], output_root=session[2])


def snapshot(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


def test_stones2_freeze_temporal_order_labels_hashes_and_readonly_idempotency(session):
    source = populate(session)
    # Retake an early frame: chronological capture time and UUID filenames are not SGF order.
    session[0].capture(**session[1], move_index=-1, overwrite_existing=True)
    source = session[0].load_session(session[1]["game_id"])
    draft_before = snapshot(session[0].root)
    result = builder(session).freeze(session[1]["game_id"], val_fraction=0.34)
    directory = Path(result["path"])
    manifest = json.loads((directory / "manifest.json").read_bytes())
    assert manifest["class_names"] == ["black", "white"]
    assert manifest["mode"] == "stones2"
    assert [sample["applied_move_index"] for sample in manifest["samples"]] == [-1, 0, 2]
    assert [sample["split"] for sample in manifest["samples"]] == ["train", "train", "val"]
    assert manifest["parameters"]["split_strategy"] == "sgf_temporal"
    assert manifest["source"]["geometry_source"] == "opencv_empty_board"
    assert manifest["source"]["sgf_sha256"] == source["sgf_sha256"]
    assert manifest["generator"]["code_sha256"]
    config = yaml.safe_load((directory / "data.yaml").read_bytes())
    assert config["names"] == ["black", "white"] and config["nc"] == 2
    assert Path(config["path"]) == directory
    assert (directory / manifest["samples"][0]["label"]).read_bytes() == b""
    assert [line.split()[0] for line in (directory / manifest["samples"][2]["label"]).read_text().splitlines()] == [
        "0",
        "1",
    ]
    for sample in manifest["samples"]:
        assert cv2.imread(str(directory / sample["image"])) is not None
        assert (directory / sample["label"]).is_file()
    files = snapshot(directory)
    assert set(manifest["assets"]) == set(files) - {"manifest.json"}
    for name, digest in manifest["assets"].items():
        assert hashlib.sha256(files[name]).hexdigest() == digest
        assert (directory / name).stat().st_mode & 0o222 == 0
    assert result["manifest_sha256"] == hashlib.sha256(files["manifest.json"]).hexdigest()
    assert snapshot(session[0].root) == draft_before
    second = builder(session).freeze(session[1]["game_id"], val_fraction=0.34)
    assert second["id"] == result["id"] and second["idempotent"] is True
    assert snapshot(directory) == files
    assert list(session[2].iterdir()) == [directory]


def test_led4_uses_existing_class_order_and_pixel_evidence(session):
    populate(session, mode="led4", visible_led=True)
    result = builder(session).freeze(session[1]["game_id"])
    directory = Path(result["path"])
    manifest = json.loads((directory / "manifest.json").read_bytes())
    config = yaml.safe_load((directory / "data.yaml").read_bytes())
    assert manifest["class_names"] == config["names"] == CLASS_NAMES
    assert config["nc"] == 4
    assert manifest["samples"][0]["led_evidence"]["centroid"]
    assert (directory / manifest["samples"][0]["label"]).read_text().split()[0] == "2"
    assert (directory / manifest["samples"][1]["label"]).read_text().splitlines()[-1].split()[0] == "3"


def test_led_metadata_without_visible_led_is_rejected(session):
    from katrain.web.admin.vision_dataset import VisionDatasetError

    populate(session, mode="led4", visible_led=False)
    before = snapshot(session[0].root)
    with pytest.raises(VisionDatasetError, match="LED"):
        builder(session).freeze(session[1]["game_id"])
    assert snapshot(session[0].root) == before
    assert not session[2].exists() or not list(session[2].iterdir())


@pytest.mark.parametrize(
    "asset", ["sgf_path", "geometry_path", "geometry_sidecar_path", "image", "missing", "unreadable"]
)
def test_invalid_source_assets_never_publish(session, asset):
    from katrain.web.admin.vision_dataset import VisionDatasetError

    manifest = populate(session)
    source = session[0].root / manifest["game_id"]
    path = source / (manifest["frames"][1]["file"] if asset in ("image", "missing", "unreadable") else manifest[asset])
    if asset == "missing":
        path.unlink()
    else:
        path.write_bytes(b"broken")
    if asset == "unreadable":
        manifest["frames"][1]["sha256"] = hashlib.sha256(b"broken").hexdigest()
        (source / "manifest.json").write_text(json.dumps(manifest))
    before = snapshot(session[0].root)
    with pytest.raises(VisionDatasetError):
        builder(session).freeze(manifest["game_id"])
    assert snapshot(session[0].root) == before
    assert not session[2].exists() or not list(session[2].iterdir())


@pytest.mark.parametrize("fraction", [0, 1, float("nan"), True])
def test_invalid_split_parameters_rejected(session, fraction):
    from katrain.web.admin.vision_dataset import VisionDatasetError

    populate(session)
    with pytest.raises(VisionDatasetError):
        builder(session).freeze(session[1]["game_id"], val_fraction=fraction)
    assert not session[2].exists()


def test_negative_margin_rejected_but_zero_margin_is_supported(session):
    from katrain.web.admin.vision_dataset import VisionDatasetError

    populate(session)
    with pytest.raises(VisionDatasetError):
        builder(session).freeze(session[1]["game_id"], margin_cells=-0.5)
    result = builder(session).freeze(session[1]["game_id"], margin_cells=0)
    image = cv2.imread(str(Path(result["path"]) / result["samples"][0]["image"]))
    assert image.shape[:2] == (210, 210)


def test_one_frame_cannot_make_two_nonempty_splits(session):
    from katrain.web.admin.vision_dataset import VisionDatasetError

    populate(session, count=1)
    with pytest.raises(VisionDatasetError, match="split"):
        builder(session).freeze(session[1]["game_id"])
    assert not session[2].exists()


@pytest.mark.parametrize(
    "bad_box", [(2, 20, 20, 10, 10), (0, float("nan"), 20, 10, 10), (0, 400, 20, 10, 10), (0, 20, 20, -1, 10)]
)
def test_invalid_generated_labels_never_publish(session, monkeypatch, bad_box):
    from katrain.vision.tools import baipu_autolabel
    from katrain.web.admin.vision_dataset import VisionDatasetError

    populate(session)
    monkeypatch.setattr(baipu_autolabel, "frame_boxes", lambda *args, **kwargs: [baipu_autolabel.Box(*bad_box)])
    with pytest.raises(VisionDatasetError, match="label"):
        builder(session).freeze(session[1]["game_id"])
    assert not session[2].exists() or not list(session[2].iterdir())


def test_publication_failure_keeps_previous_version_and_source(session, monkeypatch):
    from katrain.web.admin import vision_dataset

    populate(session)
    first = builder(session).freeze(session[1]["game_id"])
    previous = snapshot(session[2])
    source = snapshot(session[0].root)

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(vision_dataset.os, "rename", fail)
    with pytest.raises(vision_dataset.VisionDatasetError):
        builder(session).freeze(session[1]["game_id"], stone_frac=1.1)
    assert snapshot(session[2]) == previous
    assert snapshot(session[0].root) == source
    assert [p.name for p in session[2].iterdir()] == [first["id"]]


def test_review_sample_returns_actual_overlay_and_provenance(session):
    populate(session)
    frame = session[0].load_session(session[1]["game_id"])["frames"][1]
    sample = builder(session).review_sample(session[1]["game_id"], frame["frame_id"])
    image = cv2.imdecode(np.frombuffer(sample["overlay_png"], np.uint8), cv2.IMREAD_COLOR)
    assert image is not None and image.shape[:2] == (234, 234)
    assert sample["frame_id"] == frame["frame_id"]
    assert sample["source_sha256"] == frame["sha256"]
    assert sample["geometry_revision"] == "geo-1"
    assert sample["class_names"] == ["black", "white"]
    assert sample["boxes"][0]["class_id"] == 0


def test_initial_frame_can_be_reviewed_before_freezing_is_possible(session):
    source = populate(session, count=1)
    sample = builder(session).review_sample(session[1]["game_id"], source["frames"][0]["frame_id"])
    assert sample["boxes"] == []
    assert not session[2].exists()


def test_published_directory_is_already_readonly_at_atomic_rename(session, monkeypatch):
    from katrain.web.admin import vision_dataset

    populate(session)
    rename = vision_dataset.os.rename

    def assert_readonly(source, destination):
        assert source.stat().st_mode & 0o222 == 0
        assert all(path.stat().st_mode & 0o222 == 0 for path in source.rglob("*"))
        rename(source, destination)

    monkeypatch.setattr(vision_dataset.os, "rename", assert_readonly)
    builder(session).freeze(session[1]["game_id"])


def test_corrupt_previous_version_is_not_silently_reused_or_replaced(session):
    from katrain.web.admin.vision_dataset import VisionDatasetError

    populate(session)
    result = builder(session).freeze(session[1]["game_id"])
    label = Path(result["path"]) / result["samples"][0]["label"]
    label.chmod(0o644)
    label.write_bytes(b"broken")
    before = snapshot(session[2])
    with pytest.raises(VisionDatasetError):
        builder(session).freeze(session[1]["game_id"])
    assert snapshot(session[2]) == before


def test_cancel_during_build_cleans_stage_and_preserves_source(session, monkeypatch):
    import threading
    from katrain.web.admin import vision_dataset

    populate(session)
    before = snapshot(session[0].root)
    cancelled = threading.Event()
    encode = vision_dataset.cv2.imencode

    def cancel_after_encoding(*args, **kwargs):
        result = encode(*args, **kwargs)
        cancelled.set()
        return result

    monkeypatch.setattr(vision_dataset.cv2, "imencode", cancel_after_encoding)
    with pytest.raises(vision_dataset.VisionDatasetError, match="cancel"):
        builder(session).freeze(session[1]["game_id"], cancel_event=cancelled)
    assert snapshot(session[0].root) == before
    assert not list(session[2].iterdir())
