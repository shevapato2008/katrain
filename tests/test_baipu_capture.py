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


# --- P11: every-move fiducial recalibration -------------------------------- #

import cv2  # noqa: E402


def _ident_geometry():
    """Identity geometry (camera == canonical): points[r][c] = (xs[c], ys[r])."""
    xs = np.linspace(0, 949, 19).astype(np.float32)
    ys = xs.copy()
    pts = np.zeros((19, 19, 2), np.float32)
    for r in range(19):
        for c in range(19):
            pts[r][c] = (xs[c], ys[r])
    return GeometryLock(
        corners=np.zeros((4, 2), np.float32),
        points=pts,
        xs=xs,
        ys=ys,
        M=np.eye(3),
        Minv=np.eye(3),
        out_size=950,
        baseline=np.zeros((19, 19, 3), np.float32),
    )


class FiducialLed:
    def __init__(self):
        self.calls = []

    def clear(self, *, strict=False):
        self.calls.append(("clear", None))
        return {"ok": True, "connected": True, "shown_at": None, "errors": []}

    def set_rgb_points(self, points, *, strict=False):
        self.calls.append(("rgb", [(p["row"], p["col"]) for p in points]))
        return {"ok": True, "connected": True, "shown_at": 100.0, "errors": []}

    def set_points(self, points, *, strict=False):
        self.calls.append(("guide", [(p["row"], p["col"]) for p in points]))
        return {"ok": True, "connected": True, "shown_at": 111.0, "errors": []}


class FiducialCapture:
    """grab_fresh alternates dark/lit (lit has green blobs at canonical corners+star);
    capture_to writes a real black training frame so warp artifacts can be read back."""

    def __init__(self, geometry):
        self.points = geometry.points
        self.out = int(geometry.out_size)
        self.n = 0

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        self.n += 1
        img = np.zeros((self.out, self.out, 3), np.uint8)
        if self.n % 2 == 0:  # even call = lit frame
            for r in (0, 18):
                for c in (0, 18):
                    cv2.circle(img, (int(self.points[r][c][0]), int(self.points[r][c][1])), 6, (0, 200, 0), -1)
            for r in (3, 9, 15):
                for c in (3, 9, 15):
                    cv2.circle(img, (int(self.points[r][c][0]), int(self.points[r][c][1])), 6, (0, 200, 0), -1)
        return img, self.n, float(self.n)

    def capture_to(self, path, after_ts=None, settle_ms=150.0):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(path, np.zeros((self.out, self.out, 3), np.uint8))
        return path, 99, 223.0


def _capture_fid(tmp_path, steps, bs, k, led, cap, geom, **kw):
    return run_capture(
        led=led,
        capture=cap,
        geometry=geom,
        steps=steps,
        board_size=bs,
        out_dir=str(tmp_path),
        game_id=kw.pop("game_id", "gf"),
        move_index=k,
        sgf="(;SZ[19];B[pd];W[dp])",
        fiducial_mode=kw.pop("fiducial_mode", "every-move"),
        **kw,
    )


class TestFiducialEveryMove:
    def test_corrected_status_isolated_artifacts_clean_training_frame(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        geom = _ident_geometry()
        led, cap = FiducialLed(), FiducialCapture(geom)
        res = _capture_fid(tmp_path, steps, bs, -1, led, cap, geom)

        assert res["geometry_correction"]["status"] == "corrected"
        gd = tmp_path / "gf"
        man = json.loads((gd / "manifest.json").read_text())
        fr = man["frames"][-1]
        assert fr["geometry_correction"]["source"] == "fiducial"
        assert fr["geometry_correction"]["inlier_count"] >= 6
        assert (gd / fr["artifacts"]["fiducial"]).is_file()
        assert (gd / fr["artifacts"]["warped"]).is_file()
        assert (gd / fr["artifacts"]["grid_overlay"]).is_file()
        # set_rgb_points was issued, guidance point (3,15) excluded from fiducials
        rgb_calls = [c[1] for c in led.calls if c[0] == "rgb"]
        assert rgb_calls and (3, 15) not in rgb_calls[0]
        # training frame is the clean black capture_to image (no fiducial green)
        train = cv2.imread(str(gd / fr["file"]))
        assert int(train[..., 1].max()) < 20

    def test_off_mode_is_p10_no_artifacts(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        geom = _ident_geometry()
        led, cap = FiducialLed(), FiducialCapture(geom)
        res = _capture_fid(tmp_path, steps, bs, -1, led, cap, geom, game_id="goff", fiducial_mode="off")
        gd = tmp_path / "goff"
        man = json.loads((gd / "manifest.json").read_text())
        assert "geometry_correction" not in man["frames"][-1]
        assert "geometry_correction" not in res
        assert not (gd / "fiducial").exists() and not (gd / "warped").exists()

    def test_stale_falls_back_to_last_good_not_M0(self, tmp_path):
        # First move corrects; then make detection fail -> must reuse last_good (stale), not frozen.
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp];B[pp])")
        steps, bs = data["steps"], data["board_size"]
        geom = _ident_geometry()
        led, cap = FiducialLed(), FiducialCapture(geom)
        _capture_fid(tmp_path, steps, bs, -1, led, cap, geom, game_id="gs")

        class DarkOnly(FiducialCapture):
            def grab_fresh(self, after_ts=None, settle_ms=150.0):
                return np.zeros((self.out, self.out, 3), np.uint8), 1, 1.0  # never lit -> no detections

        res = _capture_fid(tmp_path, steps, bs, 0, led, DarkOnly(geom), geom, game_id="gs")
        assert res["geometry_correction"]["status"] == "stale"
        assert res["geometry_correction"]["source"] == "last_good"

    def test_overwrite_cleans_artifacts_no_orphans(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp];B[pp])")
        steps, bs = data["steps"], data["board_size"]
        geom = _ident_geometry()
        led, cap = FiducialLed(), FiducialCapture(geom)
        _capture_fid(tmp_path, steps, bs, -1, led, cap, geom, game_id="gov")
        _capture_fid(tmp_path, steps, bs, 0, led, cap, geom, game_id="gov")  # 2 frames + artifacts
        gd = tmp_path / "gov"
        assert (gd / "fiducial" / "frame_001.jpg").is_file()

        _capture_fid(tmp_path, steps, bs, -1, led, cap, geom, game_id="gov", overwrite_existing=True)
        man = json.loads((gd / "manifest.json").read_text())
        # tail (frame_001) pruned, including its artifacts:
        assert [f["file"] for f in man["frames"]] == ["frame_000.jpg"]
        assert not (gd / "fiducial" / "frame_001.jpg").exists()
        assert not (gd / "warped" / "frame_001.jpg").exists()
        assert not (gd / "grid_overlay" / "frame_001.jpg").exists()
        # every referenced artifact still exists; no orphan files beyond referenced:
        referenced = {p for fr in man["frames"] for p in fr.get("artifacts", {}).values()}
        for fr in man["frames"]:
            for p in fr.get("artifacts", {}).values():
                assert (gd / p).is_file()
        for sub in ("fiducial", "warped", "grid_overlay"):
            for f in (gd / sub).glob("*.jpg"):
                assert str(f.relative_to(gd)) in referenced


def test_resolve_fiducial_mode_precedence():
    from katrain.web.core.baipu_capture import resolve_fiducial_mode

    assert resolve_fiducial_mode("every-move", "off") == "every-move"  # CLI wins
    assert resolve_fiducial_mode(None, "every-move") == "every-move"  # env
    assert resolve_fiducial_mode(None, None) == "auto"  # default
    assert resolve_fiducial_mode("bogus", None) == "auto"  # invalid ignored
    assert resolve_fiducial_mode(None, "off") == "off"


def test_resolve_baipu_collect_defaults_off():
    from katrain.web.core.baipu_capture import resolve_baipu_collect

    assert resolve_baipu_collect() is False  # 上线版默认不拍照
    assert resolve_baipu_collect(None, "") is False
    assert resolve_baipu_collect(None, "0") is False
    assert resolve_baipu_collect(True, None) is True  # --baipu-collect
    assert resolve_baipu_collect(None, "1") is True  # KATRAIN_BAIPU_COLLECT=1
    assert resolve_baipu_collect(None, " TRUE ") is True


class TestFiducialAuto:
    """P12 'auto' mode: no-LED outer-corner per-move geometry. Guidance LED unchanged."""

    def test_auto_mode_lights_no_geometry_led(self, tmp_path):
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        geom = _ident_geometry()
        led, cap = FiducialLed(), FiducialCapture(geom)
        res = _capture_fid(tmp_path, steps, bs, -1, led, cap, geom, game_id="gauto", fiducial_mode="auto")
        # geometry path NEVER lights an LED (no set_rgb_points); guidance LED still used.
        assert not any(c[0] == "rgb" for c in led.calls)
        assert any(c[0] == "guide" for c in led.calls)
        gc = res["geometry_correction"]
        assert gc["source"] in ("outer_corner", "frozen")  # blank synth → OuterCorner fails → frozen
        man = json.loads((tmp_path / "gauto" / "manifest.json").read_text())
        assert man["frames"][-1]["geometry_correction"]["source"] == gc["source"]

    def test_auto_corrected_path_writes_outer_corner_source(self, tmp_path, monkeypatch):
        import katrain.vision.calibration_registry as reg
        from katrain.vision.calibration_strategy import CalibrationOutcome

        M = np.eye(3)

        class _OkSel:
            def calibrate(self, scenario, ctx):
                return CalibrationOutcome(ok=True, M=M, Minv=M, confidence=0.9, strategy="outer_corner")

        monkeypatch.setattr(reg, "build_default_selector", lambda: _OkSel())
        data = build_steps_from_sgf("(;SZ[19];B[pd];W[dp])")
        steps, bs = data["steps"], data["board_size"]
        geom = _ident_geometry()
        led, cap = FiducialLed(), FiducialCapture(geom)
        res = _capture_fid(tmp_path, steps, bs, -1, led, cap, geom, game_id="gac", fiducial_mode="auto")
        gc = res["geometry_correction"]
        assert gc["status"] == "corrected" and gc["source"] == "outer_corner"
        assert not any(c[0] == "rgb" for c in led.calls)
        gd = tmp_path / "gac"
        fr = json.loads((gd / "manifest.json").read_text())["frames"][-1]
        assert (gd / fr["artifacts"]["warped"]).is_file()
        assert "fiducial" not in fr["artifacts"]  # no fiducial image in auto mode


class TestVersionedArchiveAndGuidance:
    @staticmethod
    def capture(tmp_path, sgf, k, *, overwrite=False, game_id="archive", led=None, cap=None):
        data = build_steps_from_sgf(sgf)
        return run_capture(
            led=led or FakeLed(),
            capture=cap or FakeCapture(tmp_path),
            geometry=_geometry(),
            steps=data["steps"],
            board_size=data["board_size"],
            out_dir=str(tmp_path),
            game_id=game_id,
            move_index=k,
            sgf=sgf,
            overwrite_existing=overwrite,
        )

    @staticmethod
    def snapshot(path):
        return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}

    @pytest.mark.parametrize(
        "sgf,k",
        [
            ("(;SZ[19];B[aa];W[aa];B[dd])", 0),  # replacement
            ("(;SZ[19];B[aa];AE[aa];B[dd])", 0),  # clear
            ("(;SZ[19];W[aa];B[ba];B[ab];W[dd])", 1),  # upcoming capture
        ],
    )
    def test_removal_operation_blocks_later_guidance_and_is_not_final(self, tmp_path, sgf, k):
        led, cap = FakeLed(), FakeCapture(tmp_path)
        result = self.capture(tmp_path, sgf, k, led=led, cap=cap)
        manifest = json.loads((tmp_path / "archive" / "manifest.json").read_text())
        frame = manifest["frames"][-1]
        assert result["next_guided_move_index"] is None
        assert frame["led_point"] is None and frame["frame_kind"] == "after_move_no_led"
        assert led.shown == [] and led.cleared == 1
        assert cap.capture_calls[-1]["after_ts"] is None

    def test_repeat_and_pass_without_removals_can_be_skipped_for_guidance(self, tmp_path):
        result = self.capture(tmp_path, "(;SZ[19];B[aa];B[aa];W[];B[dd])", 0)
        assert result["next_guided_move_index"] == 3

    def test_new_manifest_pins_exact_sgf_and_replay_version(self, tmp_path):
        from katrain.core.baipu_identity import sgf_sha256

        sgf = "(;SZ[19]\r\n;B[aa])"
        self.capture(tmp_path, sgf, -1)
        self.capture(tmp_path, sgf, 0)
        manifest = json.loads((tmp_path / "archive" / "manifest.json").read_text())
        assert manifest["replay_version"] == 2
        assert manifest["sgf_sha256"] == sgf_sha256(sgf)
        assert manifest["total_steps"] == 1
        assert (tmp_path / "archive" / "game.sgf").read_bytes() == sgf.encode()

    @pytest.mark.parametrize("overwrite,k", [(False, -1), (True, -1), (False, 1)])
    @pytest.mark.parametrize(
        "corruption", ["sgf", "hash", "missing_hash", "version", "size", "index", "through", "pin"]
    )
    def test_incompatible_archive_rejected_before_reuse_overwrite_or_append(self, tmp_path, overwrite, k, corruption):
        sgf = "(;SZ[19];B[aa];W[dd])"
        self.capture(tmp_path, sgf, -1)
        self.capture(tmp_path, sgf, 0)
        gd = tmp_path / "archive"
        manifest = json.loads((gd / "manifest.json").read_text())
        if corruption == "sgf":
            (gd / "game.sgf").write_text(sgf + "\n")
        elif corruption == "hash":
            manifest["frames"][1]["board_hash"] = "incompatible"
        elif corruption == "missing_hash":
            manifest["frames"][1].pop("board_hash")
        elif corruption == "version":
            manifest["replay_version"] = 999
        elif corruption == "size":
            manifest["board_size"] = 9
        elif corruption == "index":
            manifest["frames"][1]["applied_move_index"] = 99
        elif corruption == "through":
            manifest["frames"][1]["board_through_index"] = 1
        elif corruption == "pin":
            manifest["sgf_sha256"] = "bad"
        (gd / "manifest.json").write_text(json.dumps(manifest))
        before = self.snapshot(gd)
        led, cap = FakeLed(), FakeCapture(tmp_path)
        with pytest.raises(ValueError, match="archive"):
            self.capture(tmp_path, sgf, k, overwrite=overwrite, led=led, cap=cap)
        assert self.snapshot(gd) == before
        assert led.shown == [] and led.cleared == 0 and cap.capture_calls == []

    def test_compatible_legacy_archive_proven_by_real_frame_hash_continues(self, tmp_path):
        sgf = "(;SZ[19];B[aa];W[dd])"
        self.capture(tmp_path, sgf, -1)
        self.capture(tmp_path, sgf, 0)
        path = tmp_path / "archive" / "manifest.json"
        manifest = json.loads(path.read_text())
        for field in ("replay_version", "sgf_sha256", "total_steps"):
            manifest.pop(field, None)
        manifest["frames"][0]["board_hash"] = None  # historical initial empty frame
        path.write_text(json.dumps(manifest))
        assert self.capture(tmp_path, sgf, 0)["idempotent"] is True
        assert self.capture(tmp_path, sgf, 1)["frame_kind"] == "final_no_led"

    def test_legacy_setup_capture_semantic_change_is_rejected_and_preserved(self, tmp_path):
        import hashlib

        sgf = "(;SZ[19]AB[aa];AW[ba][ab])"
        self.capture(tmp_path, sgf, 2)
        gd = tmp_path / "archive"
        manifest = json.loads((gd / "manifest.json").read_text())
        manifest.pop("replay_version", None)
        manifest.pop("sgf_sha256", None)
        # v1 incorrectly captured AB[aa] while applying the final AW setup.
        manifest["frames"][0]["board_hash"] = hashlib.sha1(repr([(0, 17, "W"), (1, 18, "W")]).encode()).hexdigest()[:16]
        (gd / "manifest.json").write_text(json.dumps(manifest))
        before = self.snapshot(gd)
        with pytest.raises(ValueError, match="archive"):
            self.capture(tmp_path, sgf, 2, overwrite=True)
        assert self.snapshot(gd) == before

    def test_malformed_manifest_is_never_silently_replaced(self, tmp_path):
        sgf = "(;SZ[19];B[aa])"
        self.capture(tmp_path, sgf, -1)
        gd = tmp_path / "archive"
        (gd / "manifest.json").write_text("{broken")
        before = self.snapshot(gd)
        with pytest.raises(ValueError, match="archive"):
            self.capture(tmp_path, sgf, -1, overwrite=True)
        assert self.snapshot(gd) == before


@pytest.mark.parametrize("k", [0, 1])
def test_no_led_frame_requires_confirmed_blackout_and_barrier(tmp_path, k):
    from katrain.web.core.baipu_capture import LedUnavailable

    sgf = "(;SZ[19];B[aa];AE[aa])"
    data = build_steps_from_sgf(sgf)

    class BlackoutLed(FakeLed):
        ok = False

        def clear(self, *, strict=False):
            assert strict is True
            return {"ok": self.ok, "shown_at": 456.0, "errors": ["unavailable"] if not self.ok else []}

    led, cap = BlackoutLed(), FakeCapture(tmp_path)
    kwargs = dict(
        led=led,
        capture=cap,
        geometry=_geometry(),
        steps=data["steps"],
        board_size=19,
        out_dir=str(tmp_path),
        game_id="blackout",
        move_index=k,
        sgf=sgf,
    )
    with pytest.raises(LedUnavailable):
        run_capture(**kwargs)
    assert cap.capture_calls == [] and not (tmp_path / "blackout").exists()
    led.ok = True
    run_capture(**kwargs)
    assert cap.capture_calls[-1]["after_ts"] == 456.0


def test_trailing_pass_is_nonfinal_dark_frame_until_pass_completed(tmp_path):
    first = TestVersionedArchiveAndGuidance.capture(tmp_path, "(;SZ[19];B[aa];W[])", 0)
    assert first["frame_kind"] == "after_move_no_led"
    last = TestVersionedArchiveAndGuidance.capture(tmp_path, "(;SZ[19];B[aa];W[])", 1)
    assert last["frame_kind"] == "final_no_led"
