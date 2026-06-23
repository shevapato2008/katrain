"""Auto-label baipu capture frames for 4-class YOLO training.

Unlike auto_label.py (HSV-guess on warped images, 2 classes), this uses the
SGF GROUND TRUTH + frozen board geometry to place exact 4-class boxes
(black, white, led_red, led_green) in the rectified 950x950 board space that
worker.py feeds the detector. See superpowers/tracks/yolo-train/plan.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from katrain.vision.classes import ID_TO_NAME, LED_COLOR_TO_CLASS, NAME_TO_ID
from katrain.vision.config import LedAnchorConfig

# NOTE: katrain.core.baipu is imported LAZILY inside load_capture / reconstruct_board.
# Importing it at module top would pull in katrain.core.game -> katrain.core.lang, which
# instantiates gettext at import and raises FileNotFoundError when the i18n .mo files are
# absent — breaking the pure-CV unit tests that never parse an SGF. Keep it lazy.


@dataclass
class Capture:
    game_dir: Path
    manifest: dict
    steps: list[dict]
    M: np.ndarray
    out_size: int
    xs: np.ndarray
    ys: np.ndarray


def load_capture(game_dir: Path) -> Capture:
    from katrain.core.baipu import build_steps_from_sgf  # lazy: avoids i18n import at module load

    game_dir = Path(game_dir)
    manifest = json.loads((game_dir / "manifest.json").read_text())
    sgf = (game_dir / (manifest.get("sgf_path") or "game.sgf")).read_text()
    steps = build_steps_from_sgf(sgf)["steps"]
    geo = np.load(game_dir / (manifest.get("geometry_path") or "geometry.npz"), allow_pickle=True)
    return Capture(
        game_dir=game_dir,
        manifest=manifest,
        steps=steps,
        M=np.asarray(geo["M"], dtype=np.float64),
        out_size=int(geo["out_size"]),
        xs=np.asarray(geo["xs"], dtype=np.float64),
        ys=np.asarray(geo["ys"], dtype=np.float64),
    )


def warp_frame(frame_bgr: np.ndarray, M: np.ndarray, out_size: int) -> np.ndarray:
    """Rectify a raw camera frame to the out_size square board (deployment space)."""
    return cv2.warpPerspective(frame_bgr, M, (out_size, out_size))


def grid_point(row: int, col: int, xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    """Warped-image (x, y) of canonical intersection (row, col). Direct, no flip."""
    return float(xs[col]), float(ys[row])


def reconstruct_board(steps: list[dict], applied_move_index: int) -> list[list[str | None]]:
    """19x19 of 'B'/'W'/None after applying steps[0..applied_move_index] (capture-aware)."""
    from katrain.core.baipu import expected_board_from_steps  # lazy: avoids i18n import at module load

    return expected_board_from_steps(steps, applied_move_index, 19)


def mean_grid_spacing(xs: np.ndarray, ys: np.ndarray) -> float:
    return float(np.mean([np.mean(np.diff(xs)), np.mean(np.diff(ys))]))


def detect_led_centroid(warped_bgr, gx, gy, search_px, color, cfg: LedAnchorConfig | None = None):
    """Brightest saturated red/green blob within search_px of (gx,gy). None if not found.

    Thresholds come from cfg (parameterized so a new light/camera is a config edit).
    """
    cfg = cfg or LedAnchorConfig()
    h, w = warped_bgr.shape[:2]
    x0, y0 = max(0, int(gx - search_px)), max(0, int(gy - search_px))
    x1, y1 = min(w, int(gx + search_px)), min(h, int(gy + search_px))
    roi = warped_bgr[y0:y1, x0:x1]
    if roi.size == 0:
        return None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    hue = hsv[:, :, 0]
    bright = (s > cfg.s_min) & (v > cfg.v_min)
    if color == "black":  # red LED: hue wraps around 0/180
        mask = bright & ((hue < cfg.red_hue_hi) | (hue > cfg.red_hue_lo))
    else:  # white move -> green LED
        mask = bright & (hue > cfg.green_hue_lo) & (hue < cfg.green_hue_hi)
    if mask.sum() < 4:
        return None
    ys_, xs_ = np.nonzero(mask)
    weights = v[ys_, xs_].astype(np.float64)
    cx = float(np.average(xs_, weights=weights)) + x0
    cy = float(np.average(ys_, weights=weights)) + y0
    return cx, cy


def _has_occupied_neighbor(board, r, c):
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, cc = r + dr, c + dc
        if 0 <= rr < 19 and 0 <= cc < 19 and board[rr][cc] is not None:
            return True
    return False


def detect_isolated_stone_centroids(warped_bgr, board, xs, ys, spacing):
    """Hough-circle centroid for stones with no occupied 4-neighbor (avoids cluster drag)."""
    gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
    r = max(6, int(0.45 * spacing))
    out = []
    half = int(0.7 * spacing)
    for rr in range(19):
        for cc in range(19):
            if board[rr][cc] is None or _has_occupied_neighbor(board, rr, cc):
                continue
            gx, gy = grid_point(rr, cc, xs, ys)
            x0, y0 = max(0, int(gx - half)), max(0, int(gy - half))
            x1, y1 = min(gray.shape[1], int(gx + half)), min(gray.shape[0], int(gy + half))
            patch = gray[y0:y1, x0:x1]
            if patch.size == 0:
                continue
            circles = cv2.HoughCircles(
                patch,
                cv2.HOUGH_GRADIENT,
                dp=1.2,
                minDist=2 * r,
                param1=120,
                param2=18,
                minRadius=int(0.6 * r),
                maxRadius=int(1.4 * r),
            )
            if circles is None:
                continue
            c0 = circles[0][0]
            out.append(((gx, gy), (float(c0[0]) + x0, float(c0[1]) + y0)))
    return out


@dataclass
class ShiftReport:
    dx: float
    dy: float
    anchor_count: int
    led_found: bool
    residual_px: float  # MAD of anchor deltas about the median (anchor agreement)
    fallback_used: bool  # True when no anchors -> prev_shift was carried forward


def estimate_global_shift(warped_bgr, board, led_point, xs, ys, spacing, prev_shift=(0.0, 0.0), cfg=None):
    """Robust per-frame drift = median(detected_centroid - grid_point) over anchors.

    On zero anchors, carry forward prev_shift (NOT (0,0)) so a single anchor-less frame
    mid-game (e.g. the full-board final frame) inherits the correct ~16px offset instead
    of snapping back to the un-drifted grid. Returns a ShiftReport.
    """
    deltas = []
    led_found = False
    if led_point is not None:
        gx, gy = grid_point(led_point["row"], led_point["col"], xs, ys)
        led = detect_led_centroid(warped_bgr, gx, gy, int(0.7 * spacing), led_point["color"], cfg)
        if led is not None:
            deltas.append((led[0] - gx, led[1] - gy))
            led_found = True
    for (gx, gy), (cx, cy) in detect_isolated_stone_centroids(warped_bgr, board, xs, ys, spacing):
        deltas.append((cx - gx, cy - gy))
    if not deltas:
        return ShiftReport(float(prev_shift[0]), float(prev_shift[1]), 0, led_found, 0.0, True)
    arr = np.asarray(deltas, dtype=np.float64)
    dx, dy = float(np.median(arr[:, 0])), float(np.median(arr[:, 1]))
    residual = float(np.median(np.abs(arr - np.array([dx, dy]))))  # MAD
    lim = 0.6 * spacing
    dx, dy = float(np.clip(dx, -lim, lim)), float(np.clip(dy, -lim, lim))
    return ShiftReport(dx, dy, len(deltas), led_found, residual, False)


_DRAW = {0: (0, 0, 255), 1: (0, 255, 0), 2: (0, 140, 255), 3: (255, 200, 0)}


@dataclass
class Box:
    class_id: int
    cx: float
    cy: float
    w: float
    h: float


def _clip_box(cx, cy, w, h, img_w, img_h):
    """Clip a center box to [0,img_w]x[0,img_h] and return the re-centered (cx,cy,w,h)."""
    x1, y1 = max(0.0, cx - w / 2), max(0.0, cy - h / 2)
    x2, y2 = min(float(img_w), cx + w / 2), min(float(img_h), cy + h / 2)
    return (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1


def frame_boxes(
    board,
    led_point,
    xs,
    ys,
    shift,
    spacing,
    stone_frac: float = 1.05,
    led_frac: float = 0.45,
    img_w: int = 950,
    img_h: int = 950,
):
    # Stones ~object-tight (deploy snaps on center; box extent is training-localization only).
    # LEDs tight: a background-dominated box destroys small-target recall (the success metric).
    stone_side = float(np.clip(stone_frac * spacing, 40.0, 70.0))
    led_side = float(np.clip(led_frac * spacing, 16.0, 36.0))
    dx, dy = shift
    boxes: list[Box] = []
    for r in range(19):
        for c in range(19):
            v = board[r][c]
            if v is None:
                continue
            gx, gy = grid_point(r, c, xs, ys)
            cid = NAME_TO_ID["black"] if v == "B" else NAME_TO_ID["white"]
            cx, cy, w, h = _clip_box(gx + dx, gy + dy, stone_side, stone_side, img_w, img_h)
            boxes.append(Box(cid, cx, cy, w, h))
    if led_point is not None:
        gx, gy = grid_point(led_point["row"], led_point["col"], xs, ys)
        cx, cy, w, h = _clip_box(gx + dx, gy + dy, led_side, led_side, img_w, img_h)
        boxes.append(Box(LED_COLOR_TO_CLASS[led_point["color"]], cx, cy, w, h))
    return boxes


def boxes_to_yolo_lines(boxes, img_w, img_h):
    lines = []
    for b in boxes:
        lines.append(f"{b.class_id} {b.cx / img_w:.6f} {b.cy / img_h:.6f} {b.w / img_w:.6f} {b.h / img_h:.6f}")
    return lines


def draw_overlay(warped_bgr, boxes):
    vis = warped_bgr.copy()
    for b in boxes:
        x1, y1 = int(b.cx - b.w / 2), int(b.cy - b.h / 2)
        x2, y2 = int(b.cx + b.w / 2), int(b.cy + b.h / 2)
        cv2.rectangle(vis, (x1, y1), (x2, y2), _DRAW[b.class_id], 2)
    return vis
