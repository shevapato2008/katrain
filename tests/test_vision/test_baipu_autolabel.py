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
