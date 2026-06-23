"""Tests for 带灯拍 capture orchestration + endpoint (mock led/camera/geometry).

Real capture (camera and LED on a physical board) is verified on hardware day.
Here we lock the operator-trusted orchestration: no classifier gate, the sync
barrier (capture grabbed after the LED's shown_at), the rich manifest (schema,
frame_kind sequence, pass skipping), per-SGF isolation, atomic/idempotent writes,
slug/containment, and first-frame freeze.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from katrain.core.baipu import build_steps_from_sgf
from katrain.vision.geometry_lock import GeometryLock
from katrain.web.core.baipu_capture import run_capture


def _geometry():
    return GeometryLock(
        corners=np.zeros((4, 2), np.float32),
        points=np.zeros((19, 19, 2), np.float32),
        xs=np.linspace(0, 949, 19).astype(np.float32),
        ys=np.linspace(0, 949, 19).astype(np.float32),
        M=np.eye(3),
        Minv=np.eye(3),
        out_size=950,
        baseline=np.zeros((19, 19, 3), np.float32),
        confidence=0.9,
    )


class FakeLed:
    def __init__(self):
        self.cleared = 0
        self.shown = []

    def clear(self, *, strict=False):
        self.cleared += 1
        return {"ok": True, "connected": True, "shown_at": None, "errors": []}

    def set_points(self, points, *, strict=False):
        self.shown.append(points)
        return {"ok": True, "connected": True, "shown_at": 111.0, "errors": []}


class FakeCapture:
    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)
        self.capture_calls = []

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        return np.zeros((4, 4, 3), np.uint8), 1, 222.0

    def capture_to(self, path, after_ts=None, settle_ms=150.0):
        self.capture_calls.append({"path": path, "after_ts": after_ts})
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"jpgdata")
        return path, 42, 223.0


class VersionedCapture(FakeCapture):
    def __init__(self, out_dir):
        super().__init__(out_dir)
        self.version = 0

    def capture_to(self, path, after_ts=None, settle_ms=150.0):
        self.version += 1
        self.capture_calls.append({"path": path, "after_ts": after_ts})
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(f"jpg-{self.version}".encode("ascii"))
        return path, self.version, 223.0


def _capture(out_dir, steps, board_size, k, led, cap, **kw):
    return run_capture(
        led=led,
        capture=cap,
        geometry=_geometry(),
        steps=steps,
        board_size=board_size,
        out_dir=out_dir,
        game_id=kw.pop("game_id", "g1"),
        move_index=k,
        sgf="(;SZ[19];B[pd];W[dp])",
        **kw,
    )


class TestCaptureSequence:
    def test_full_sequence_manifest(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        led, cap = FakeLed(), FakeCapture(tmp_path)

        # initial_led (k=-1): board empty
        r0 = _capture(str(tmp_path), steps, bs, -1, led, cap)
        # after_move 0
        r1 = _capture(str(tmp_path), steps, bs, 0, led, cap)
        # final (k=1): no next
        r2 = _capture(str(tmp_path), steps, bs, 1, led, cap)

        assert r0["frame_kind"] == "initial_led" and r0["next_guided_move_index"] == 0
        assert r1["frame_kind"] == "after_move" and r1["next_guided_move_index"] == 1
        assert r2["frame_kind"] == "final_no_led" and r2["next_guided_move_index"] is None

        manifest = json.loads((tmp_path / "g1" / "manifest.json").read_text())
        assert manifest["total_moves"] == 2
        assert [f["file"] for f in manifest["frames"]] == ["frame_000.jpg", "frame_001.jpg", "frame_002.jpg"]
        assert manifest["frames"][0]["applied_move_index"] == -1
        assert manifest["frames"][0]["led_point"] == {"row": 3, "col": 15, "color": "black"}
        assert manifest["frames"][2]["led_point"] is None
        assert {frame["qa_status"] for frame in manifest["frames"]} == {"operator_confirmed"}
        # all frames + first-frame freeze written
        assert (tmp_path / "g1" / "frame_002.jpg").exists()
        assert (tmp_path / "g1" / "geometry.npz").exists()
        assert (tmp_path / "g1" / "game.sgf").exists()

    def test_sync_barrier_uses_shown_at(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        led, cap = FakeLed(), FakeCapture(tmp_path)
        _capture(str(tmp_path), steps, bs, -1, led, cap)
        # the lit-frame capture must wait for the LED's shown_at (111.0), not None
        assert cap.capture_calls[-1]["after_ts"] == 111.0

    def test_pass_skipped_in_next(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[];B[pp])")
        steps, bs = data["steps"], data["board_size"]
        led, cap = FakeLed(), FakeCapture(tmp_path)
        r = run_capture(
            led=led,
            capture=cap,
            geometry=_geometry(),
            steps=steps,
            board_size=bs,
            out_dir=str(tmp_path),
            game_id="g2",
            move_index=0,
            sgf="x",
        )
        assert r["next_guided_move_index"] == 2  # skipped the pass at index 1


class TestOperatorTrustedCapture:
    def test_operator_confirmation_skips_classifier(self, tmp_path, monkeypatch):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        led, cap = FakeLed(), FakeCapture(tmp_path)
        monkeypatch.setattr(
            "katrain.vision.board_qa.classify_canonical",
            lambda *_args, **_kwargs: pytest.fail("classifier must not run during collection"),
        )

        result = _capture(str(tmp_path), steps, bs, 0, led, cap)

        assert result["qa_status"] == "operator_confirmed"


class TestRobustness:
    def test_idempotent_on_duplicate_move(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        led, cap = FakeLed(), FakeCapture(tmp_path)
        _capture(str(tmp_path), steps, bs, -1, led, cap)
        n_calls = len(cap.capture_calls)
        r2 = _capture(str(tmp_path), steps, bs, -1, led, cap)  # same move_index again
        assert r2["idempotent"] is True
        assert len(cap.capture_calls) == n_calls  # no new capture

    def test_missing_frame_is_recaptured_in_place(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        led, cap = FakeLed(), FakeCapture(tmp_path)
        _capture(str(tmp_path), steps, bs, -1, led, cap)
        first = _capture(str(tmp_path), steps, bs, 0, led, cap)
        missing_path = Path(first["path"])
        missing_path.unlink()
        n_calls = len(cap.capture_calls)

        repaired = _capture(str(tmp_path), steps, bs, 0, led, cap)

        assert repaired["idempotent"] is False
        assert repaired["repaired"] is True
        assert Path(repaired["path"]) == missing_path
        assert missing_path.read_bytes() == b"jpgdata"
        assert len(cap.capture_calls) == n_calls + 1
        manifest = json.loads((tmp_path / "g1" / "manifest.json").read_text())
        assert len(manifest["frames"]) == 2
        assert manifest["frames"][1]["file"] == "frame_001.jpg"
        assert manifest["frames"][1]["applied_move_index"] == 0

    def test_overwrite_existing_restarts_same_directory_and_prunes_stale_tail(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp];B[pp])")
        steps, bs = data["steps"], data["board_size"]
        led, cap = FakeLed(), VersionedCapture(tmp_path)
        _capture(str(tmp_path), steps, bs, -1, led, cap)
        _capture(str(tmp_path), steps, bs, 0, led, cap)
        _capture(str(tmp_path), steps, bs, 1, led, cap)

        restarted = _capture(str(tmp_path), steps, bs, -1, led, cap, overwrite_existing=True)

        assert restarted["idempotent"] is False
        assert restarted["overwritten"] is True
        assert (tmp_path / "g1" / "frame_000.jpg").read_bytes() == b"jpg-4"
        assert not (tmp_path / "g1" / "frame_001.jpg").exists()
        assert not (tmp_path / "g1" / "frame_002.jpg").exists()
        manifest = json.loads((tmp_path / "g1" / "manifest.json").read_text())
        assert [f["file"] for f in manifest["frames"]] == ["frame_000.jpg"]

    def test_game_ids_use_independent_directories(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]

        for game_id in ("kifu_24171", "kifu_24172"):
            _capture(str(tmp_path), steps, bs, -1, FakeLed(), FakeCapture(tmp_path), game_id=game_id)

        for game_id in ("kifu_24171", "kifu_24172"):
            game_dir = tmp_path / game_id
            assert (game_dir / "frame_000.jpg").exists()
            manifest = json.loads((game_dir / "manifest.json").read_text())
            assert manifest["game_id"] == game_id
            assert [frame["file"] for frame in manifest["frames"]] == ["frame_000.jpg"]

    def test_invalid_game_id_rejected(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        with pytest.raises(ValueError):
            _capture(str(tmp_path), steps, bs, -1, FakeLed(), FakeCapture(tmp_path), game_id="../escape")
