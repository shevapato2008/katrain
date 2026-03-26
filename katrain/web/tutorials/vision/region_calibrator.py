"""Multi-evidence region calibration for Go board diagrams.

Infers col_start/row_start (which part of the 19×19 board is shown)
using multiple evidence sources: border lines, star points, line count,
and layout bias. Replaces fragile star-point-only calibration.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

log = logging.getLogger(__name__)

KNOWN_STARS_19 = {(3, 3), (9, 3), (15, 3), (3, 9), (9, 9), (15, 9), (3, 15), (9, 15), (15, 15)}


def _is_border_line(gray, position, axis, thickness_threshold=3):
    """Check if a grid line at the given position is a thick border line.

    Border lines (board edges) are typically 2-3x thicker than interior lines.
    """
    h_img, w_img = gray.shape

    if axis == "h":
        # Horizontal line: sample a narrow horizontal strip
        y = int(position)
        y1 = max(0, y - 6)
        y2 = min(h_img, y + 7)
        strip = gray[y1:y2, :]
        # Count dark pixels in each row of the strip
        dark_per_row = np.sum(strip < 120, axis=1)
        # A border line has more consecutive dark rows
        consecutive_dark = np.sum(dark_per_row > w_img * 0.3)
        return consecutive_dark >= thickness_threshold
    else:
        # Vertical line
        x = int(position)
        x1 = max(0, x - 6)
        x2 = min(w_img, x + 7)
        strip = gray[:, x1:x2]
        dark_per_col = np.sum(strip < 120, axis=0)
        consecutive_dark = np.sum(dark_per_col > h_img * 0.3)
        return consecutive_dark >= thickness_threshold


def _count_star_matches(gray, h_positions, v_positions, spacing, occupied_set,
                        col_off, row_off, known_stars):
    """Count how many unoccupied intersections match expected star point positions.

    Star points appear as small dots (~3-5px) at specific intersections.
    Only checks unoccupied intersections (stones cover star points).
    """
    matches = 0
    r = max(3, int(spacing * 0.15))  # small radius for star point detection

    for ci, vx in enumerate(v_positions):
        for ri, hy in enumerate(h_positions):
            global_pos = (col_off + ci, row_off + ri)
            if global_pos not in known_stars:
                continue
            if (ci, ri) in occupied_set:
                continue  # stone covers star point

            # Check for a small dark dot at this intersection
            h_img, w_img = gray.shape
            y1 = max(0, int(hy) - r)
            y2 = min(h_img, int(hy) + r)
            x1 = max(0, int(vx) - r)
            x2 = min(w_img, int(vx) + r)
            roi = gray[y1:y2, x1:x2]

            if roi.size == 0:
                continue

            # Star points are small dark clusters at the center of the ROI
            dark_ratio = float(np.sum(roi < 120) / roi.size)
            if dark_ratio > 0.15:  # has a visible mark
                matches += 1

    return matches


def calibrate_region(gray, h_positions, v_positions, spacing, occupied=None):
    """Multi-evidence inference of col_start/row_start.

    Evidence sources:
    1. Border detection: thick lines at edges → board boundary → col/row = 0 or 18
    2. Star point matching: small dots at unoccupied intersections → known 19×19 positions
    3. Line count constraint: num_visible_cols + col_start <= 19
    4. Typical layout bias: most book diagrams start from corner

    Args:
        gray: grayscale image of the cropped diagram
        h_positions: detected horizontal line positions (pixel coords)
        v_positions: detected vertical line positions (pixel coords)
        spacing: average grid spacing in pixels
        occupied: set of (col_idx, row_idx) occupied intersections (optional)

    Returns:
        (col_start, row_start, confidence, evidence_details)
    """
    num_cols = len(v_positions)
    num_rows = len(h_positions)
    occupied_set = occupied or set()

    candidates = []
    for col_off in range(max(0, 19 - num_cols) + 1):
        for row_off in range(max(0, 19 - num_rows) + 1):
            score = 0.0
            evidence = []

            # Evidence 1: border lines (thick first/last lines → board edge)
            if len(v_positions) > 0:
                if _is_border_line(gray, v_positions[0], axis="v"):
                    if col_off == 0:
                        score += 2.0
                        evidence.append("left_border")
                    else:
                        score -= 1.0  # penalty: border detected but not at edge
                if _is_border_line(gray, v_positions[-1], axis="v"):
                    if col_off + num_cols == 19:
                        score += 2.0
                        evidence.append("right_border")
                    else:
                        score -= 1.0

            if len(h_positions) > 0:
                if _is_border_line(gray, h_positions[0], axis="h"):
                    if row_off == 0:
                        score += 2.0
                        evidence.append("top_border")
                    else:
                        score -= 1.0
                if _is_border_line(gray, h_positions[-1], axis="h"):
                    if row_off + num_rows == 19:
                        score += 2.0
                        evidence.append("bottom_border")
                    else:
                        score -= 1.0

            # Evidence 2: star point matching
            star_matches = _count_star_matches(
                gray, h_positions, v_positions, spacing,
                occupied_set, col_off, row_off, KNOWN_STARS_19
            )
            score += star_matches * 1.5
            if star_matches > 0:
                evidence.append(f"stars={star_matches}")

            # Evidence 3: typical layout bias (most book diagrams start from col=0, row=0)
            if col_off == 0:
                score += 0.5
            if row_off == 0:
                score += 0.5

            # Evidence 4: line count sanity check
            if col_off + num_cols > 19 or row_off + num_rows > 19:
                score -= 100  # impossible
                evidence.append("out_of_bounds")

            candidates.append((col_off, row_off, score, evidence))

    if not candidates:
        return 0, 0, 0.0, ["no_candidates"]

    best = max(candidates, key=lambda x: x[2])
    max_score = best[2]

    # Confidence: how much better is the best vs second-best
    sorted_candidates = sorted(candidates, key=lambda x: x[2], reverse=True)
    if len(sorted_candidates) > 1 and max_score > 0:
        second_score = sorted_candidates[1][2]
        confidence = min(1.0, (max_score - second_score) / (max_score + 1e-6))
    else:
        confidence = 1.0

    log.info("Region calibration: col_start=%d, row_start=%d, confidence=%.2f, evidence=%s",
             best[0], best[1], confidence, best[3])

    return best[0], best[1], confidence, best[3]
