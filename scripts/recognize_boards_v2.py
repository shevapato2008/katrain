#!/usr/bin/env python3
"""Hybrid VLLM+CV Go board recognition from book page images.

Pipeline:
  Step 0: VLLM detects bounding boxes for each diagram on the page
  Step 1: VLLM identifies which part of the 19x19 board is shown
  Step 2: OpenCV detects grid lines precisely (no counting errors)
  Step 3: OpenCV detects stones at grid intersections (black/white)
  Step 4: VLLM reads move numbers on stones
  Step 5: Combine into board_payload and write to DB

Usage:
    # Test CV pipeline on a single page (no DB write)
    python scripts/recognize_boards_v2.py --test-cv PAGE_IMAGE

    # Process a full section
    python scripts/recognize_boards_v2.py --section-id 1 [--dry-run]
"""

import argparse
import json
import logging
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
from PIL import Image

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.tutorials import db_queries

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

ASSET_BASE = Path("data")


# ── Step 2: OpenCV grid detection ─────────────────────────────────────────────

def _find_peaks(arr, min_val, min_dist):
    """Simple 1D peak finder without scipy dependency."""
    peaks = []
    for i in range(1, len(arr) - 1):
        if arr[i] >= min_val and arr[i] >= arr[i - 1] and arr[i] >= arr[i + 1]:
            if not peaks or i - peaks[-1] >= min_dist:
                peaks.append(i)
    return np.array(peaks)


def cv_detect_grid(gray):
    """Detect grid line positions from a grayscale board image.

    Returns (h_positions, v_positions, spacing) where positions are pixel
    coordinates of each horizontal/vertical grid line.
    """
    h_img, w_img = gray.shape

    _, binary = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)

    # Morphological isolation of horizontal and vertical lines
    min_line_len = min(h_img, w_img) // 8
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_len, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_line_len))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

    # Project to 1D
    h_proj = np.sum(h_lines, axis=1) // 255
    v_proj = np.sum(v_lines, axis=0) // 255

    h_thresh = max(10, int(np.max(h_proj) * 0.3))
    v_thresh = max(10, int(np.max(v_proj) * 0.3))

    # Estimate minimum distance between lines (~60% of expected spacing)
    # For a 19-line board in 700px image, spacing ≈ 700/18 ≈ 39px
    est_spacing = min(h_img, w_img) / 20
    min_dist = max(10, int(est_spacing * 0.6))

    h_positions = _find_peaks(h_proj, h_thresh, min_dist)
    v_positions = _find_peaks(v_proj, v_thresh, min_dist)

    if len(h_positions) < 2 or len(v_positions) < 2:
        return h_positions, v_positions, 0.0

    h_spacing = float(np.median(np.diff(h_positions)))
    v_spacing = float(np.median(np.diff(v_positions)))
    spacing = (h_spacing + v_spacing) / 2

    # Fill gaps where stones occlude grid lines (gap ≈ 2× spacing → missing line)
    def _fill_gaps(positions, sp):
        if len(positions) < 2:
            return positions
        result = [positions[0]]
        for i in range(1, len(positions)):
            gap = positions[i] - positions[i - 1]
            if gap > sp * 1.6:
                n_missing = round(gap / sp) - 1
                for j in range(1, n_missing + 1):
                    result.append(int(positions[i - 1] + j * gap / (n_missing + 1)))
            result.append(positions[i])
        return np.array(result)

    h_positions = _fill_gaps(h_positions, h_spacing)
    v_positions = _fill_gaps(v_positions, v_spacing)

    return h_positions, v_positions, spacing


# ── Step 3a: OpenCV occupied intersection detection ──────────────────────────

def cv_detect_occupied(gray, h_positions, v_positions, spacing):
    """Detect all non-empty intersections using multi-feature anomaly detection.

    Returns list of (col_idx, row_idx, patch) where patch is the cropped grayscale image.
    Does NOT classify color — that's VLLM's job.
    """
    h_img, w_img = gray.shape
    r = int(spacing * 0.5)  # slightly larger for better patch quality
    if r < 3:
        return []

    # Compute features for every intersection
    features = []
    for ci, vx in enumerate(v_positions):
        for ri, hy in enumerate(h_positions):
            y1, y2 = max(0, int(hy) - r), min(h_img, int(hy) + r)
            x1, x2 = max(0, int(vx) - r), min(w_img, int(vx) + r)
            roi = gray[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            # Multi-dimensional features
            dark_ratio = float(np.sum(roi < 100) / roi.size)
            edges = cv2.Canny(roi, 50, 150)
            edge_ratio = float(np.sum(edges > 0) / edges.size)
            std_val = float(np.std(roi.astype(float)))

            # Circular contrast (white stone signature)
            mask = np.zeros_like(roi, dtype=np.uint8)
            cr = roi.shape[0] // 2
            cv2.circle(mask, (cr, cr), max(1, cr - 2), 255, -1)
            inside = roi[mask > 0]
            outside = roi[mask == 0]
            circ_contrast = float(np.mean(outside) - np.mean(inside)) if inside.size > 0 and outside.size > 0 else 0.0

            features.append((ci, ri, int(vx), int(hy), dark_ratio, edge_ratio, std_val, circ_contrast, roi.copy()))

    if not features:
        return []

    # Compute background statistics (median ± std for each feature)
    darks = np.array([f[4] for f in features])
    edges_arr = np.array([f[5] for f in features])
    stds = np.array([f[6] for f in features])

    dark_med, dark_std = float(np.median(darks)), float(np.std(darks))
    edge_med, edge_std = float(np.median(edges_arr)), float(np.std(edges_arr))
    std_med, std_std = float(np.median(stds)), float(np.std(stds))

    # Mark as occupied if ANY feature is anomalous (wide net, minimal false negatives)
    occupied = []
    for ci, ri, vx, hy, dark, edge, std_v, circ, roi in features:
        is_occupied = (
            dark > dark_med + 2.0 * dark_std
            or edge > edge_med + 2.0 * edge_std
            or std_v > std_med + 2.0 * std_std
            or circ < -15  # white stone signature (light center)
            or dark > 0.28  # absolute threshold for numbered stones
        )
        if is_occupied:
            occupied.append((ci, ri, roi))

    return occupied


def cv_preclass_confident(occupied_patches, spacing):
    """Pre-classify high-confidence patches using simple CV heuristics.

    Returns (confident, ambiguous) where:
      confident: list of (col_idx, row_idx, patch, base_type) for obvious B/W
      ambiguous: list of (col_idx, row_idx, patch) needing VLLM classification
    """
    confident = []
    ambiguous = []

    for ci, ri, patch in occupied_patches:
        dark_ratio = float(np.sum(patch < 100) / patch.size)
        mean_val = float(np.mean(patch))

        # Very dark → almost certainly black stone
        if dark_ratio > 0.55 and mean_val < 80:
            confident.append((ci, ri, patch, "black"))
        # Very light center → almost certainly white stone (no number)
        elif mean_val > 180 and dark_ratio < 0.05:
            confident.append((ci, ri, patch, "white"))
        else:
            ambiguous.append((ci, ri, patch))

    return confident, ambiguous


# ── Step 3b: OpenCV stone detection (legacy) ─────────────────────────────────

def cv_detect_stones_legacy(gray, h_positions, v_positions, spacing):
    """Detect stones at grid intersections using dark-ratio + edge analysis.

    Legacy version that classifies B/W. Kept for --test-cv comparison.
    Returns list of (col_idx, row_idx, color) where color is 'B' or 'W'.
    """
    h_img, w_img = gray.shape
    r = int(spacing * 0.45)
    if r < 3:
        return []

    # Compute features for every intersection
    features = []
    for ci, vx in enumerate(v_positions):
        for ri, hy in enumerate(h_positions):
            y1, y2 = max(0, hy - r), min(h_img, hy + r)
            x1, x2 = max(0, vx - r), min(w_img, vx + r)
            roi = gray[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            edges = cv2.Canny(roi, 50, 150)
            dark_ratio = float(np.sum(roi < 100) / roi.size)
            edge_ratio = float(np.sum(edges > 0) / edges.size)
            features.append((ci, ri, int(vx), int(hy), dark_ratio, edge_ratio))

    if not features:
        return []

    # Fixed thresholds derived from empirical analysis of Go book scans:
    #   Black stone:  dark_ratio > 0.45 (solid filled circle)
    #   White+number: dark_ratio > 0.28 AND std > 105 (circle outline + number text)
    #   White plain:  circ_contrast < -15 (light center, dark outline ring)
    BLACK_DARK = 0.45
    WHITE_NUMBERED_DARK = 0.28
    WHITE_NUMBERED_STD = 105
    WHITE_PLAIN_CONTRAST = -15

    stones = []
    for ci, ri, vx, hy, dark, edge in features:
        if dark > BLACK_DARK:
            stones.append((ci, ri, "B"))
            continue

        # White stone with number: moderate dark + high std (number adds texture)
        y1, y2 = max(0, hy - r), min(h_img, hy + r)
        x1, x2 = max(0, vx - r), min(w_img, vx + r)
        roi = gray[y1:y2, x1:x2]
        std_val = float(np.std(roi.astype(float)))

        if dark > WHITE_NUMBERED_DARK and std_val > WHITE_NUMBERED_STD:
            stones.append((ci, ri, "W"))
            continue

        # White stone without number: circle outline makes edges darker than center
        if roi.size > 0:
            mask = np.zeros_like(roi, dtype=np.uint8)
            cr = roi.shape[0] // 2
            cv2.circle(mask, (cr, cr), max(1, cr - 2), 255, -1)
            inside = roi[mask > 0]
            outside = roi[mask == 0]
            if inside.size > 0 and outside.size > 0:
                circ_contrast = float(np.mean(outside)) - float(np.mean(inside))
                if circ_contrast < WHITE_PLAIN_CONTRAST:
                    stones.append((ci, ri, "W"))

    return stones


# ── Step 0: VLLM bbox detection (via claude CLI) ─────────────────────────────

def vllm_call(image_path, prompt):
    """Call Claude via the claude CLI (uses Max membership, no API key needed)."""
    result = subprocess.run(
        ["claude", "-p", prompt, "--image", str(image_path)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr[:300]}")
    text = result.stdout.strip()
    # Extract JSON from response
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        # Try array
        start = text.find("[")
        end = text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON in VLLM response: {text[:300]}")
    return json.loads(text[start:end])


def vllm_detect_bboxes(page_image_path):
    """Step 0: Detect bounding boxes for each board diagram on the page.

    Returns dict mapping figure_label → (x1, y1, x2, y2) in pixels.
    """
    prompt = """This is a page from a Go (围棋) textbook. Identify each board diagram (棋盘图) on the page.
For each diagram, return its bounding box in pixel coordinates.
The figure label is the text like "图1", "图2" shown below or near each diagram.

Return JSON only, no explanation:
{"figures": {"图1": [x1, y1, x2, y2], "图2": [x1, y1, x2, y2]}}

Where x1,y1 is the top-left corner and x2,y2 is the bottom-right corner of the board grid area (not including the "图N" label text)."""

    result = vllm_call(page_image_path, prompt)
    return result.get("figures", {})


# ── Step 1: VLLM board region identification ──────────────────────────────────

def vllm_identify_region(crop_image_path, num_h_lines, num_v_lines):
    """Step 1: Identify which part of the 19x19 board this diagram shows.

    Uses the number of detected grid lines from CV to constrain the answer.
    Returns dict with 'col_start' and 'row_start'.
    """
    prompt = f"""This is a cropped Go (围棋) board diagram from a textbook.
OpenCV detected {num_v_lines} vertical lines and {num_h_lines} horizontal lines.

The full board is 19×19. This diagram shows only part of the board.

Coordinate system: col=0 is leftmost, row=0 is topmost on the full 19×19 board.
Star points (hoshi) are at positions: (3,3), (9,3), (15,3), (3,9), (9,9), (15,9), (3,15), (9,15), (15,15).

Determine which portion of the full board is shown:
- col_start: the column index of the leftmost visible line (0 if left edge is the board edge)
- row_start: the row index of the topmost visible line (0 if top edge is the board edge)

The board has {num_v_lines} columns visible (col_start to col_start+{num_v_lines - 1}) and {num_h_lines} rows visible (row_start to row_start+{num_h_lines - 1}).

Look for star points (small dots on intersections) to calibrate your answer.
If the left edge and top edge are thick board borders, col_start=0 and row_start=0.

Return JSON only:
{{"col_start": 0, "row_start": 0}}"""

    return vllm_call(crop_image_path, prompt)


# ── Step 4: VLLM number recognition ──────────────────────────────────────────

def vllm_read_numbers(crop_image_path, stones):
    """Step 4: Read move numbers on detected stones.

    Returns dict mapping "col_idx,row_idx" → number (int) for stones that have labels.
    """
    if not stones:
        return {}

    stone_desc = ", ".join(
        f"{color} stone at grid position ({ci},{ri})"
        for ci, ri, color in stones
    )
    prompt = f"""This is a cropped Go board diagram from a textbook.
The following stones were detected: {stone_desc}

For each stone, check if it has a move number printed on it (like ①②③ or 1,2,3...).
Also check for any letter annotations (like A, B, C) on empty intersections.

Return JSON only:
{{"labels": {{"col_idx,row_idx": number_or_null, ...}}, "letters": {{"col_idx,row_idx": "A", ...}}}}

For stones without numbers, set the value to null. Only include entries that have actual labels."""

    return vllm_call(crop_image_path, prompt)


# ── Step 5: Build board_payload ───────────────────────────────────────────────

def build_payload(stones, labels_data, col_start, row_start):
    """Combine CV stone detection + VLLM label recognition into board_payload."""
    black, white = [], []
    labels = {}
    letters = {}

    for ci, ri, color in stones:
        full_col = col_start + ci
        full_row = row_start + ri
        if color == "B":
            black.append([full_col, full_row])
        else:
            white.append([full_col, full_row])

    # Add labels from VLLM
    if labels_data:
        for key, val in labels_data.get("labels", {}).items():
            if val is None:
                continue
            ci, ri = map(int, key.split(","))
            full_col = col_start + ci
            full_row = row_start + ri
            labels[f"{full_col},{full_row}"] = str(int(val))

        for key, val in labels_data.get("letters", {}).items():
            if not val:
                continue
            ci, ri = map(int, key.split(","))
            full_col = col_start + ci
            full_row = row_start + ri
            letters[f"{full_col},{full_row}"] = str(val)

    return {
        "size": 19,
        "stones": {"B": black, "W": white},
        "labels": labels,
        "letters": letters,
        "shapes": {},
        "highlights": [],
    }


# ── Page-level crop detection (CV fallback for VLLM bbox) ────────────────────

def cv_detect_diagram_bboxes(page_gray):
    """Fallback: detect board diagram regions using CV projection analysis.

    Returns list of (y_start, y_end) for each diagram on the page (left portion).
    """
    h_img, w_img = page_gray.shape

    # Board diagrams are in the left ~50% of the page
    left_half = page_gray[:, : w_img // 2]
    row_dark = np.sum(left_half < 100, axis=1)

    # Find rows with significant dark content (board lines)
    threshold = np.max(row_dark) * 0.15
    board_rows = np.where(row_dark > threshold)[0]

    if len(board_rows) == 0:
        return []

    # Split into groups (diagrams) by large gaps
    groups = []
    current_start = board_rows[0]
    prev = board_rows[0]
    for r in board_rows[1:]:
        if r - prev > 50:
            groups.append((int(current_start), int(prev)))
            current_start = r
        prev = r
    groups.append((int(current_start), int(prev)))

    # Filter: only keep groups with reasonable height (at least 100px)
    # Add generous padding to avoid clipping board edge lines
    pad = 40
    return [(max(0, y1 - pad), min(h_img, y2 + pad)) for y1, y2 in groups if y2 - y1 > 100]


def crop_diagram(page_img, page_gray, y_start, y_end, padding=15):
    """Crop a single board diagram from the page, finding its horizontal extent."""
    h_img, w_img = page_gray.shape

    y1 = max(0, y_start - padding)
    y2 = min(h_img, y_end + padding)

    # Find horizontal extent within this row range
    strip = page_gray[y1:y2, :]
    col_dark = np.sum(strip < 100, axis=0)
    dark_cols = np.where(col_dark > 5)[0]

    if len(dark_cols) == 0:
        return None

    x1 = max(0, int(dark_cols[0]) - padding)
    x2 = min(w_img, int(dark_cols[-1]) + padding)

    return page_img[y1:y2, x1:x2]


# ── Full pipeline ─────────────────────────────────────────────────────────────

def process_page(page_image_path, figure_ids, dry_run=False, db=None):
    """Process all diagrams on a single page.

    figure_ids: list of (figure_label, figure_db_id) e.g. [("图1", 1), ("图2", 2)]
    """
    page_img = cv2.imread(str(page_image_path))
    if page_img is None:
        log.error("Cannot read image: %s", page_image_path)
        return
    page_gray = cv2.cvtColor(page_img, cv2.COLOR_BGR2GRAY)

    # Step 0: detect diagram bounding boxes
    log.info("Step 0: detecting diagram bboxes on %s", page_image_path.name)

    # Try VLLM first, fall back to CV
    try:
        bboxes = vllm_detect_bboxes(page_image_path)
        log.info("  VLLM bboxes: %s", bboxes)
    except Exception as e:
        log.warning("  VLLM bbox failed (%s), using CV fallback", e)
        bboxes = {}

    # CV fallback: detect diagram vertical ranges
    if not bboxes or len(bboxes) < len(figure_ids):
        cv_regions = cv_detect_diagram_bboxes(page_gray)
        log.info("  CV detected %d diagram regions", len(cv_regions))

        # Map CV regions to figure labels (by order)
        for i, (label, _) in enumerate(figure_ids):
            if label not in bboxes and i < len(cv_regions):
                y1, y2 = cv_regions[i]
                # Find horizontal extent
                strip = page_gray[y1:y2, :]
                col_dark = np.sum(strip < 100, axis=0)
                dark_cols = np.where(col_dark > 5)[0]
                if len(dark_cols) > 0:
                    x1, x2 = int(dark_cols[0]) - 10, int(dark_cols[-1]) + 10
                    bboxes[label] = [x1, y1 - 10, x2, y2 + 10]

    # Process each figure
    for label, fig_id in figure_ids:
        log.info("Processing %s (id=%d)", label, fig_id)

        bbox = bboxes.get(label)
        if bbox is None:
            log.warning("  No bbox found — skipping")
            continue

        # Crop diagram
        x1, y1, x2, y2 = [int(c) for c in bbox]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(page_img.shape[1], x2)
        y2 = min(page_img.shape[0], y2)
        crop = page_img[y1:y2, x1:x2]
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        # Save crop for VLLM steps
        crop_path = Path(tempfile.mktemp(suffix=".png", prefix=f"board_{label}_"))
        cv2.imwrite(str(crop_path), crop)
        log.info("  Cropped: %dx%d → %s", crop.shape[1], crop.shape[0], crop_path.name)

        # Step 2: CV grid detection
        h_pos, v_pos, spacing = cv_detect_grid(crop_gray)
        log.info("  Step 2: %d rows × %d cols, spacing=%.1fpx", len(h_pos), len(v_pos), spacing)

        if len(h_pos) < 3 or len(v_pos) < 3:
            log.warning("  Too few grid lines — skipping")
            crop_path.unlink(missing_ok=True)
            continue

        # Step 3: CV occupied intersection detection
        occupied = cv_detect_occupied(crop_gray, h_pos, v_pos, spacing)
        confident, ambiguous = cv_preclass_confident(occupied, spacing)
        log.info("  Step 3: %d occupied (%d confident, %d ambiguous)",
                 len(occupied), len(confident), len(ambiguous))

        # Legacy stone detection for payload (until VLLM classification is wired up)
        stones = cv_detect_stones_legacy(crop_gray, h_pos, v_pos, spacing)
        b_count = sum(1 for _, _, c in stones if c == "B")
        w_count = sum(1 for _, _, c in stones if c == "W")
        log.info("  Step 3 (legacy): %d stones (B=%d, W=%d)", len(stones), b_count, w_count)

        # Step 1: VLLM board region
        try:
            region = vllm_identify_region(crop_path, len(h_pos), len(v_pos))
            col_start = region.get("col_start", 0)
            row_start = region.get("row_start", 0)
            log.info("  Step 1: col_start=%d, row_start=%d", col_start, row_start)
        except Exception as e:
            log.warning("  VLLM region failed (%s), assuming col_start=0, row_start=0", e)
            col_start, row_start = 0, 0

        # Step 4: VLLM number recognition
        try:
            labels_data = vllm_read_numbers(crop_path, stones)
            label_count = sum(1 for v in labels_data.get("labels", {}).values() if v is not None)
            letter_count = len(labels_data.get("letters", {}))
            log.info("  Step 4: %d labels, %d letters", label_count, letter_count)
        except Exception as e:
            log.warning("  VLLM number recognition failed (%s)", e)
            labels_data = {}

        # Step 5: Build payload
        payload = build_payload(stones, labels_data, col_start, row_start)
        log.info("  Payload: B=%d W=%d labels=%d letters=%d",
                 len(payload["stones"]["B"]), len(payload["stones"]["W"]),
                 len(payload["labels"]), len(payload["letters"]))

        if dry_run:
            print(f"\n=== {label} (id={fig_id}) ===")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif db is not None:
            figure = db_queries.get_figure(db, fig_id)
            if figure:
                db_queries.update_figure_board(db, figure, payload)
                log.info("  ✓ Saved to DB")
            else:
                log.error("  Figure id=%d not found in DB", fig_id)

        # Cleanup temp file
        crop_path.unlink(missing_ok=True)


# ── Test CV pipeline ──────────────────────────────────────────────────────────

def test_cv(page_image_path):
    """Test the CV pipeline (Steps 2-3 only) on a page image."""
    page_img = cv2.imread(str(page_image_path))
    page_gray = cv2.cvtColor(page_img, cv2.COLOR_BGR2GRAY)

    regions = cv_detect_diagram_bboxes(page_gray)
    log.info("Found %d diagram regions", len(regions))

    for i, (y_start, y_end) in enumerate(regions):
        crop = crop_diagram(page_img, page_gray, y_start, y_end)
        if crop is None:
            continue
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        h_pos, v_pos, spacing = cv_detect_grid(crop_gray)

        # New: occupied detection (no color classification)
        occupied = cv_detect_occupied(crop_gray, h_pos, v_pos, spacing)
        confident, ambiguous = cv_preclass_confident(occupied, spacing)
        log.info("Diagram %d: %d×%d grid, spacing=%.1fpx, %d occupied (%d confident, %d ambiguous)",
                 i + 1, len(v_pos), len(h_pos), spacing, len(occupied),
                 len(confident), len(ambiguous))
        for ci, ri, _, base_type in confident:
            log.info("  CV-confident: %s at local(%d,%d)", base_type, ci, ri)
        for ci, ri, _ in ambiguous:
            log.info("  Ambiguous: local(%d,%d)", ci, ri)

        # Legacy comparison
        stones = cv_detect_stones_legacy(crop_gray, h_pos, v_pos, spacing)
        log.info("  Legacy: %d stones (B=%d, W=%d)", len(stones),
                 sum(1 for _, _, c in stones if c == "B"),
                 sum(1 for _, _, c in stones if c == "W"))

        # Save debug image
        r = int(spacing * 0.45) if spacing > 0 else 10
        debug = crop.copy()
        for y in h_pos:
            cv2.line(debug, (0, y), (crop.shape[1], y), (0, 0, 255), 1)
        for x in v_pos:
            cv2.line(debug, (x, 0), (x, crop.shape[0]), (255, 0, 0), 1)
        for ci, ri, patch in occupied:
            vx, hy = int(v_pos[ci]), int(h_pos[ri])
            cv2.circle(debug, (vx, hy), r, (0, 255, 255), 2)
            cv2.putText(debug, f"({ci},{ri})", (vx + r + 2, hy + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
        # Mark confident patches in green (black) / orange (white)
        for ci, ri, _, base_type in confident:
            vx, hy = int(v_pos[ci]), int(h_pos[ri])
            c = (0, 255, 0) if base_type == "black" else (255, 128, 0)
            cv2.circle(debug, (vx, hy), r + 3, c, 2)
        out = Path(f"/tmp/cv_debug_diagram_{i + 1}.png")
        cv2.imwrite(str(out), debug)
        log.info("  Debug image: %s", out)

        # Save crop for contact sheet testing
        crop_out = Path(f"/tmp/cv_crop_diagram_{i + 1}.png")
        cv2.imwrite(str(crop_out), crop)
        log.info("  Crop: %s", crop_out)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hybrid VLLM+CV board recognition")
    parser.add_argument("--section-id", type=int, help="Process all figures in this section")
    parser.add_argument("--test-cv", type=str, help="Test CV pipeline on a page image")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without DB write")
    args = parser.parse_args()

    if args.test_cv:
        test_cv(Path(args.test_cv))
        return

    if not args.section_id:
        parser.error("--section-id or --test-cv required")

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        section = db_queries.get_section(db, args.section_id)
        if section is None:
            log.error("Section %d not found", args.section_id)
            return

        log.info("Section %d: %s (%d figures)", section.id, section.title, len(section.figures))

        # Group figures by page
        pages = defaultdict(list)
        for fig in section.figures:
            pages[fig.page].append((fig.figure_label, fig.id))

        for page_num in sorted(pages.keys()):
            figure_ids = pages[page_num]
            # Find page image path from the first figure
            fig0 = next(f for f in section.figures if f.page == page_num)
            if not fig0.page_image_path:
                log.warning("Page %d: no image path — skipping", page_num)
                continue
            image_path = ASSET_BASE / fig0.page_image_path

            if not image_path.exists():
                log.warning("Page %d: image not found at %s — skipping", page_num, image_path)
                continue

            log.info("\n── Page %d (%s) ── %d figure(s)", page_num, image_path.name, len(figure_ids))
            process_page(image_path, figure_ids, dry_run=args.dry_run, db=db)

    finally:
        db.close()

    if not args.dry_run:
        log.info("\nDone. Reload browser to see results.")


if __name__ == "__main__":
    main()
