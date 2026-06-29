from pathlib import Path
import os
import numpy as np
import pytest
import cv2

from katrain.vision.tools import baipu_autolabel as bal

GAME = Path(os.path.expanduser("~/.katrain/baipu_captures/kifu_24171"))
# Decorate ONLY the SGF-parse / real-data tests with this — NOT a module-level pytestmark,
# so the synthetic pure-CV tests below always run in CI.
requires_capture = pytest.mark.skipif(
    not GAME.exists(), reason="baipu capture fixture not present (real-data integration)"
)

# Synthetic grid — faithful to kifu_24171 (out_size 950, spacing ~52.72).
SYNTH_XS = np.linspace(0.0, 949.0, 19)
SYNTH_YS = np.linspace(0.0, 949.0, 19)


# ---------- pure-CV unit tests (CI: no fixture, no .mo) ----------


def test_grid_point_corner_and_topright():
    x0, y0 = bal.grid_point(0, 0, SYNTH_XS, SYNTH_YS)
    assert (round(x0), round(y0)) == (0, 0)
    x, y = bal.grid_point(0, 18, SYNTH_XS, SYNTH_YS)
    assert round(x) == 949 and round(y) == 0  # row=0 top, col=18 right


def test_mean_grid_spacing():
    assert abs(bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS) - 52.72) < 0.5


# ---------- real-data integration tests (skip without fixture; need .mo) ----------


@requires_capture
def test_load_capture_shapes():
    cap = bal.load_capture(GAME)
    assert cap.out_size == 950
    assert cap.xs.shape == (19,) and cap.ys.shape == (19,)
    assert cap.M.shape == (3, 3)
    assert cap.manifest["board_size"] == 19
    assert len(cap.steps) >= cap.manifest["total_moves"]


@requires_capture
def test_reconstruct_board_matches_move_index_minus_captures():
    cap = bal.load_capture(GAME)
    # frame_040: applied_move_index=39 -> 40 placements minus captures.
    board = bal.reconstruct_board(cap.steps, 39)
    n_black = sum(c == "B" for row in board for c in row)
    n_white = sum(c == "W" for row in board for c in row)
    assert (n_black, n_white) == (20, 20)  # 40 moves, no captures yet at move 40


@requires_capture
def test_reconstruct_board_handles_captures_by_final_move():
    cap = bal.load_capture(GAME)
    board = bal.reconstruct_board(cap.steps, 210)  # final position of a 211-move game
    total = sum(c is not None for row in board for c in row)
    assert total == 205  # 211 placements - 6 captured (verified)


# ---------- pure-CV unit tests (CI: no fixture, no .mo) ----------


def test_detect_led_centroid_finds_green_blob():
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    img = np.zeros((950, 950, 3), dtype=np.uint8)
    gx, gy = bal.grid_point(9, 9, SYNTH_XS, SYNTH_YS)
    cv2.circle(img, (int(gx) + 4, int(gy) - 3), 6, (0, 255, 0), -1)  # green (BGR) blob
    c = bal.detect_led_centroid(img, gx, gy, int(0.7 * spacing), "white")  # white move -> green LED
    assert c is not None
    assert abs(c[0] - (gx + 4)) < 3 and abs(c[1] - (gy - 3)) < 3


def test_estimate_global_shift_recovers_known_translation():
    # LED-only anchor: deterministic (HSV centroid), no Hough flakiness.
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    img = np.zeros((950, 950, 3), dtype=np.uint8)
    led = {"row": 9, "col": 9, "color": "white"}  # green LED
    gx, gy = bal.grid_point(9, 9, SYNTH_XS, SYNTH_YS)
    tx, ty = 8.0, -5.0
    cv2.circle(img, (int(gx + tx), int(gy + ty)), 6, (0, 255, 0), -1)
    empty = [[None] * 19 for _ in range(19)]
    rep = bal.estimate_global_shift(img, empty, led, SYNTH_XS, SYNTH_YS, spacing)
    assert abs(rep.dx - tx) < 0.1 * spacing and abs(rep.dy - ty) < 0.1 * spacing
    assert rep.led_found and rep.anchor_count >= 1 and not rep.fallback_used


def test_estimate_global_shift_carry_forward_on_no_anchor():
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    blank = np.zeros((950, 950, 3), dtype=np.uint8)
    empty = [[None] * 19 for _ in range(19)]
    rep = bal.estimate_global_shift(blank, empty, None, SYNTH_XS, SYNTH_YS, spacing, prev_shift=(5.0, -3.0))
    assert (rep.dx, rep.dy) == (5.0, -3.0) and rep.fallback_used and rep.anchor_count == 0
    rep0 = bal.estimate_global_shift(blank, empty, None, SYNTH_XS, SYNTH_YS, spacing)
    assert (rep0.dx, rep0.dy) == (0.0, 0.0)  # first frame: default prev_shift


# ---------- real-data integration test (skip without fixture; need .mo) ----------


@requires_capture
def test_estimate_global_shift_is_small_and_clamped():
    cap = bal.load_capture(GAME)
    spacing = bal.mean_grid_spacing(cap.xs, cap.ys)
    fr = next(f for f in cap.manifest["frames"] if f["file"] == "frame_040.jpg")
    img = cv2.imread(str(GAME / fr["file"]))
    warped = bal.warp_frame(img, cap.M, cap.out_size)
    board = bal.reconstruct_board(cap.steps, fr["applied_move_index"])
    rep = bal.estimate_global_shift(warped, board, fr["led_point"], cap.xs, cap.ys, spacing)
    assert abs(rep.dx) <= 0.6 * spacing and abs(rep.dy) <= 0.6 * spacing
    assert rep.anchor_count >= 1  # frame_040 has the guide LED + isolated stones


# ---------- pure-CV unit tests (CI: no fixture, no .mo) ----------

from katrain.vision.classes import NAME_TO_ID


def test_frame_boxes_stone_and_led_sizes():
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    board = [[None] * 19 for _ in range(19)]
    board[9][9] = "W"
    led = {"row": 3, "col": 3, "color": "black"}  # -> led_red
    boxes = bal.frame_boxes(board, led, SYNTH_XS, SYNTH_YS, (0.0, 0.0), spacing)
    stone = next(b for b in boxes if b.class_id in (0, 1))
    led_box = next(b for b in boxes if b.class_id in (2, 3))
    assert 40 <= stone.w <= 70 and stone.class_id == NAME_TO_ID["white"]
    assert led_box.class_id == NAME_TO_ID["led_red"]
    assert led_box.w <= 36 and led_box.w < stone.w  # LED box is tight, smaller than a stone


def test_corner_box_is_clipped_into_image():
    spacing = bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS)
    board = [[None] * 19 for _ in range(19)]
    board[0][0] = "B"  # grid (0,0) -> pixel (0,0); an unclipped box would hang off-frame
    boxes = bal.frame_boxes(board, None, SYNTH_XS, SYNTH_YS, (0.0, 0.0), spacing)
    b = boxes[0]
    assert b.cx - b.w / 2 >= -0.01 and b.cy - b.h / 2 >= -0.01  # fully inside image
    stone_side = min(max(1.05 * spacing, 40.0), 70.0)
    assert abs(b.w - stone_side / 2) < 1.0  # exactly the off-image half was clipped


def test_boxes_to_yolo_lines_format_and_range():
    boxes = [bal.Box(class_id=3, cx=475.0, cy=475.0, w=90.0, h=90.0)]
    lines = bal.boxes_to_yolo_lines(boxes, 950, 950)
    assert lines == ["3 0.500000 0.500000 0.094737 0.094737"]


# ---------- real-data integration tests (skip without fixture; need .mo) ----------


@requires_capture
def test_frame_boxes_counts_and_led_class():
    cap = bal.load_capture(GAME)
    spacing = bal.mean_grid_spacing(cap.xs, cap.ys)
    fr = next(f for f in cap.manifest["frames"] if f["file"] == "frame_040.jpg")
    board = bal.reconstruct_board(cap.steps, fr["applied_move_index"])
    boxes = bal.frame_boxes(board, fr["led_point"], cap.xs, cap.ys, (0.0, 0.0), spacing)
    stones = [b for b in boxes if b.class_id in (0, 1)]
    leds = [b for b in boxes if b.class_id in (2, 3)]
    assert len(stones) == 40
    # frame_040 led_point.color == "black" -> led_red (2)
    assert len(leds) == 1 and leds[0].class_id == NAME_TO_ID["led_red"]


@requires_capture
def test_final_frame_has_no_led_box():
    cap = bal.load_capture(GAME)
    spacing = bal.mean_grid_spacing(cap.xs, cap.ys)
    fr = next(f for f in cap.manifest["frames"] if f["file"] == "frame_211.jpg")
    board = bal.reconstruct_board(cap.steps, fr["applied_move_index"])
    boxes = bal.frame_boxes(board, fr["led_point"], cap.xs, cap.ys, (0.0, 0.0), spacing)
    assert all(b.class_id in (0, 1) for b in boxes)  # final_no_led frame


# ---------- P11: per-frame M_f consumption + quality gate (synthetic, CI-safe) ----------

import json  # noqa: E402


def _make_game(tmp_path, gid, frames, sgf="(;SZ[19];B[pd];W[dp];B[pp])"):
    """Tiny self-contained capture dir (manifest + identity geometry.npz + sgf + blank frames)."""
    from katrain.vision.geometry_lock import GeometryLock, save_geometry_lock

    gd = tmp_path / gid
    gd.mkdir(parents=True, exist_ok=True)
    (gd / "game.sgf").write_text(sgf)
    xs = np.linspace(0, 949, 19).astype(np.float32)
    pts = np.zeros((19, 19, 2), np.float32)
    for r in range(19):
        for c in range(19):
            pts[r][c] = (xs[c], xs[r])
    lock = GeometryLock(
        corners=np.zeros((4, 2), np.float32), points=pts, xs=xs, ys=xs,
        M=np.eye(3), Minv=np.eye(3), out_size=950, baseline=np.zeros((19, 19, 3), np.float32),
    )
    save_geometry_lock(lock, gd / "geometry.npz")
    for fr in frames:
        cv2.imwrite(str(gd / fr["file"]), np.zeros((950, 950, 3), np.uint8))
    manifest = {
        "game_id": gid, "board_size": 19, "sgf_path": "game.sgf", "geometry_path": "geometry.npz",
        "total_moves": 2, "frames": frames,
    }
    (gd / "manifest.json").write_text(json.dumps(manifest))
    return gd


def _corrected(median_cells=0.02, over=False):
    return {"status": "corrected", "source": "fiducial", "M": np.eye(3).tolist(),
            "drift": {"median_cells": median_cells, "over_threshold": over}}


def test_corrected_uses_Mf_and_skips_estimate(tmp_path, monkeypatch):
    monkeypatch.setattr(
        bal, "estimate_global_shift",
        lambda *a, **k: pytest.fail("estimate_global_shift must not run for corrected frames"),
    )
    gd = _make_game(tmp_path, "gc", [
        {"file": "frame_000.jpg", "applied_move_index": 0,
         "led_point": {"row": 3, "col": 3, "color": "black"}, "geometry_correction": _corrected()},
    ])
    stats = bal.process_game(gd, tmp_path / "img", tmp_path / "lbl", verify_dir=tmp_path / "v")
    assert stats["written"] == 1
    assert (tmp_path / "lbl" / "gc_frame_000.txt").exists()
    csv = (tmp_path / "v" / "shifts.csv").read_text()
    assert "label_quality" in csv.splitlines()[0]
    assert "corrected" in csv


def test_frozen_with_drift_isolated_unless_flag(tmp_path):
    frames = [
        {"file": "frame_000.jpg", "applied_move_index": 0, "led_point": None,
         "geometry_correction": _corrected(median_cells=0.5, over=True)},   # game drifted
        {"file": "frame_001.jpg", "applied_move_index": 1, "led_point": None,
         "geometry_correction": {"status": "frozen", "source": "frozen", "M": np.eye(3).tolist(),
                                 "drift": {"median_cells": 0.0, "over_threshold": False}}},
    ]
    gd = _make_game(tmp_path, "gd", frames)
    stats = bal.process_game(gd, tmp_path / "i1", tmp_path / "l1")
    assert stats["skipped_drift"] >= 1
    assert not (tmp_path / "l1" / "gd_frame_001.txt").exists()
    assert (tmp_path / "l1" / "gd_frame_000.txt").exists()  # corrected frame still exported

    stats2 = bal.process_game(gd, tmp_path / "i2", tmp_path / "l2", allow_legacy_drift=True)
    assert (tmp_path / "l2" / "gd_frame_001.txt").exists()
    assert stats2["skipped_drift"] == 0


def test_legacy_no_field_falls_back_with_quality_flag(tmp_path):
    frames = [{"file": "frame_000.jpg", "applied_move_index": 0, "led_point": None}]  # no geometry_correction
    gd = _make_game(tmp_path, "gl", frames)
    bal.process_game(gd, tmp_path / "i", tmp_path / "l", verify_dir=tmp_path / "v")
    assert (tmp_path / "l" / "gl_frame_000.txt").exists()
    assert "legacy_estimate" in (tmp_path / "v" / "shifts.csv").read_text()


def test_latest_game_dir_picks_newest(tmp_path):
    import os as _os

    from katrain.vision.tools.baipu_autolabel import _latest_game_dir

    root = tmp_path / "caps"
    for gid, mtime in (("g1", 1000), ("g2", 2000)):
        (root / gid).mkdir(parents=True)
        man = root / gid / "manifest.json"
        man.write_text("{}")
        _os.utime(man, (mtime, mtime))
    assert _latest_game_dir(root).name == "g2"
    assert _latest_game_dir(tmp_path / "nonexistent") is None
    assert _latest_game_dir(tmp_path / "caps_empty") is None  # missing root -> None


def test_process_game_idempotent_rerun(tmp_path):
    # --watch re-runs process_game each tick; it must be idempotent (no dups, no errors) so
    # labels can be regenerated incrementally as 摆谱 adds frames.
    frames = [
        {"file": f"frame_00{i}.jpg", "applied_move_index": i, "led_point": None, "geometry_correction": _corrected()}
        for i in range(2)
    ]
    gd = _make_game(tmp_path, "gi", frames)
    s1 = bal.process_game(gd, tmp_path / "img", tmp_path / "lbl")
    s2 = bal.process_game(gd, tmp_path / "img", tmp_path / "lbl")  # one watch tick later
    assert s1 == s2
    assert sorted(p.name for p in (tmp_path / "lbl").glob("*.txt")) == ["gi_frame_000.txt", "gi_frame_001.txt"]


def test_outer_corner_source_uses_M_and_flags_quality(tmp_path, monkeypatch):
    # P12 Task 7: source="outer_corner" (no-LED auto mode) consumes its per-frame M directly
    # (no estimate_global_shift) and is tagged distinctly to reflect coarser precision.
    monkeypatch.setattr(
        bal, "estimate_global_shift",
        lambda *a, **k: pytest.fail("estimate_global_shift must not run for corrected outer_corner"),
    )
    gc = {
        "status": "corrected", "source": "outer_corner", "M": np.eye(3).tolist(),
        "drift": {"median_cells": 0.05, "over_threshold": False},
    }
    gd = _make_game(tmp_path, "goc", [
        {"file": "frame_000.jpg", "applied_move_index": 0,
         "led_point": {"row": 3, "col": 3, "color": "black"}, "geometry_correction": gc},
    ])
    bal.process_game(gd, tmp_path / "img", tmp_path / "lbl", verify_dir=tmp_path / "v")
    assert (tmp_path / "lbl" / "goc_frame_000.txt").exists()
    assert "corrected_outer_corner" in (tmp_path / "v" / "shifts.csv").read_text()


def test_mixed_legacy_and_outer_corner_manifest_does_not_break(tmp_path):
    # Backward-compat: a manifest mixing legacy (no gc) + new outer_corner frames processes cleanly.
    frames = [
        {"file": "frame_000.jpg", "applied_move_index": 0, "led_point": None},  # legacy, no gc
        {"file": "frame_001.jpg", "applied_move_index": 1, "led_point": None,
         "geometry_correction": {"status": "corrected", "source": "outer_corner", "M": np.eye(3).tolist(),
                                 "drift": {"median_cells": 0.04, "over_threshold": False}}},
    ]
    gd = _make_game(tmp_path, "gm", frames)
    bal.process_game(gd, tmp_path / "i", tmp_path / "l", verify_dir=tmp_path / "v")
    csv = (tmp_path / "v" / "shifts.csv").read_text()
    assert "legacy_estimate" in csv and "corrected_outer_corner" in csv


@requires_capture
def test_process_game_writes_matching_labels(tmp_path):
    imgs = tmp_path / "images"
    lbls = tmp_path / "labels"
    verify = tmp_path / "verify"
    stats = bal.process_game(GAME, imgs, lbls, verify_dir=verify, dedup_per_move=True)
    assert stats["written"] == 212  # all frames distinct applied_move_index -> dedup is a no-op here
    # every image has a label file
    img_stems = {p.stem for p in imgs.glob("*.jpg")}
    lbl_stems = {p.stem for p in lbls.glob("*.txt")}
    assert img_stems == lbl_stems
    # 211 frames carry a guide LED, but frame_143's LED is on row 0 and the board drifted ~25px
    # off the top edge, so that LED is genuinely outside the rectified image and is correctly
    # dropped (labeling an off-frame point would be a phantom). 210-211 tolerates the sub-pixel boundary.
    assert 210 <= stats["led_red"] + stats["led_green"] <= 211
    assert (verify / "shifts.csv").exists()  # per-frame drift diagnostics for the QA gate
    # every label line is well-formed with class in 0..3
    for txt in lbls.glob("*.txt"):
        for line in txt.read_text().splitlines():
            parts = line.split()
            assert len(parts) == 5 and 0 <= int(parts[0]) <= 3
            assert all(0.0 <= float(x) <= 1.0 for x in parts[1:])
