#!/usr/bin/env python3
"""Hybrid CV+VLLM Go board recognition from book page images.

Pipeline:
  Step 0: CV detects diagram bounding boxes on the page (VLLM fallback)
  Step 1: VLLM identifies which part of the 19x19 board is shown (col_start/row_start)
  Step 2: CV detects grid lines precisely (no counting errors)
  Step 3: CV detects occupied intersections + pre-classifies obvious B/W
  Step 4: VLLM classifies ambiguous patches via contact sheet
  Step 5: Merge CV+VLLM → board_payload → DB + training data

Division of labor:
  CV  handles WHERE: grid lines, intersection positions, patch cropping
  VLLM handles WHAT: stone color, move numbers, annotations, board region

Usage:
    # Generate contact sheets (CV only, fast)
    python scripts/recognize_boards_v2.py --section-id 1 --save-sheets /tmp/sheets/

    # Apply subagent classifications to DB
    python scripts/recognize_boards_v2.py --section-id 1 --apply-classifications FILE.json --force

    # Full auto pipeline (requires working VLLM)
    python scripts/recognize_boards_v2.py --section-id 1 --force [--dry-run]

    # Test CV pipeline only
    python scripts/recognize_boards_v2.py --test-cv PAGE_IMAGE
"""

import argparse
import json
import logging
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
from PIL import Image

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.tutorials import db_queries
from katrain.web.tutorials.vision.region_calibrator import calibrate_region

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

ASSET_BASE = Path("data")


# ── Structured classification schema ─────────────────────────────────────────

@dataclass
class PatchClassification:
    """Classification result for a single intersection patch."""
    label: str                            # contact sheet label: "A", "B", ...
    local_col: int                        # grid index in cropped diagram
    local_row: int
    base_type: str                        # "black" | "white" | "empty" | "unknown"
    text: Optional[str] = None            # move number "1"-"99+" or letter "A"-"Z" or None
    shape: Optional[str] = None           # "triangle" | "square" | "circle" | None
    confidence: float = 1.0               # 0.0-1.0; <0.8 → needs_review
    source: str = "cv"                    # "cv" | "vllm" | "model" | "human"


@dataclass
class FigureResult:
    """Per-figure processing result for batch status tracking."""
    label: str
    figure_id: int
    status: str  # "success" | "needs_review" | "failed_cv" | "failed_semantic" | "skipped"
    detail: str = ""
    stone_count: int = 0
    label_count: int = 0
    calibration_confidence: float = 0.0


def print_summary_report(results):
    """Print a summary report of figure processing results."""
    log.info("\n═══ Processing Summary ═══")
    status_counts = defaultdict(int)
    for r in results:
        status_counts[r.status] += 1
        icon = {"success": "✓", "needs_review": "?", "skipped": "—"}.get(r.status, "✗")
        log.info("  %s %s (id=%d): %s %s",
                 icon, r.label, r.figure_id, r.status, r.detail)

    log.info("──────────────────────────")
    for status, count in sorted(status_counts.items()):
        log.info("  %s: %d", status, count)
    log.info("  total: %d", len(results))


VLLM_CLASSIFY_PROMPT = """This is a Go (围棋) board diagram from a textbook.
Magenta letters (A, B, C...) mark positions where stones or markings were detected.
For each labeled position, classify what is at that position on the board.

How to distinguish black vs white stones:
- BLACK stone: solid filled dark circle (completely dark, may have a white number printed on it)
- WHITE stone: outlined circle with a hollow/light center (thin dark circular border, may have a dark number)
- If the circle is mostly dark/filled → it is BLACK
- If the circle has a light/empty center with just an outline → it is WHITE

Categories:
- "black": solid black stone, no number
- "white": outlined white stone, no number
- "black+N": black stone with move number N (white number on dark stone)
- "white+N": white stone with move number N (dark number on light stone)
- "triangle_black" / "triangle_white": stone marked with △
- "square_black" / "square_white": stone marked with □
- "circle_black" / "circle_white": stone marked with ○
- "letter_X": letter X (A, B, C...) annotation on an empty intersection (not a stone)
- "empty": no stone at this position (false detection)

Return JSON only, no explanation:
{"A": "black+1", "B": "white+8", "C": "black", "D": "letter_A", ...}
"""


VLLM_REGION_PROMPT = """This is a cropped Go (围棋) board diagram from a textbook.
The full board is 19×19. This diagram shows only part of the board.
OpenCV detected {num_v} vertical lines and {num_h} horizontal lines.

Determine which portion of the full 19×19 board is shown:
- col_start: column index (0-based) of the leftmost visible line
- row_start: row index (0-based) of the topmost visible line

Rules:
- If the LEFT edge has a thick border line → col_start = 0
- If the RIGHT edge has a thick border line → col_start = 19 - {num_v}
- If the TOP edge has a thick border line → row_start = 0
- If the BOTTOM edge has a thick border line → row_start = 19 - {num_h}
- Star points (hoshi) on a 19×19 board are at lines 3, 9, 15 (0-indexed) on each axis
- Most textbook diagrams show a corner (col_start=0 or row_start=0)

Return JSON only:
{{"col_start": 0, "row_start": 0}}
"""


def parse_classification(label, cls_str, local_col, local_row, source="vllm"):
    """Parse a VLLM classification string into a PatchClassification."""
    base_type = "unknown"
    text = None
    shape = None

    if cls_str == "empty":
        return PatchClassification(label, local_col, local_row, "empty", source=source)

    if cls_str.startswith("black"):
        base_type = "black"
        if "+" in cls_str:
            text = cls_str.split("+", 1)[1]
    elif cls_str.startswith("white"):
        base_type = "white"
        if "+" in cls_str:
            text = cls_str.split("+", 1)[1]
    elif cls_str.startswith(("triangle_", "square_", "circle_")):
        parts = cls_str.split("_", 1)
        shape = parts[0]
        base_type = parts[1] if len(parts) > 1 else "unknown"
    elif cls_str.startswith("letter_"):
        base_type = "empty"
        text = cls_str.split("_", 1)[1]

    return PatchClassification(label, local_col, local_row, base_type,
                               text=text, shape=shape, source=source)


def classification_to_payload(classifications, label_map, col_start=0, row_start=0):
    """Convert classification results to board_payload format.

    Args:
        classifications: dict like {"A": "black+1", "B": "white+8", ...}
            OR list of PatchClassification objects
        label_map: dict like {"A": (col_idx, row_idx), ...}
        col_start: offset to map local col to full 19×19 col
        row_start: offset to map local row to full 19×19 row
    """
    black, white = [], []
    labels, letters, shapes = {}, {}, {}

    # Normalize to PatchClassification objects
    if isinstance(classifications, dict):
        parsed = []
        for lbl, cls_str in classifications.items():
            if lbl in label_map:
                ci, ri = label_map[lbl]
                parsed.append(parse_classification(lbl, cls_str, ci, ri))
        items = parsed
    else:
        items = classifications

    for pc in items:
        if pc.base_type == "empty" and pc.text and pc.text.isalpha():
            # Letter annotation on empty intersection
            ci, ri = pc.local_col, pc.local_row
            col = col_start + ci
            row = row_start + ri
            key = f"{col},{row}"
            letters[key] = pc.text
            continue

        if pc.base_type in ("empty", "unknown"):
            continue

        ci, ri = pc.local_col, pc.local_row
        col = col_start + ci
        row = row_start + ri
        key = f"{col},{row}"

        if pc.base_type == "black":
            black.append([col, row])
        elif pc.base_type == "white":
            white.append([col, row])

        if pc.text and pc.text.isdigit():
            labels[key] = pc.text

        if pc.shape:
            shapes[key] = pc.shape

    return {
        "size": 19,
        "stones": {"B": black, "W": white},
        "labels": labels,
        "letters": letters,
        "shapes": shapes,
        "highlights": [],
    }


# ── Debug image generation ────────────────────────────────────────────────────

def generate_bbox_debug_image(page_img, bboxes, figure_labels):
    """Draw bounding boxes on page image. Returns annotated image."""
    debug = page_img.copy()
    colors = [(0, 200, 0), (200, 0, 0), (0, 0, 200), (200, 200, 0)]
    for i, (label, bbox) in enumerate(zip(figure_labels, bboxes)):
        if bbox is None:
            continue
        x1, y1, x2, y2 = [int(c) for c in bbox]
        color = colors[i % len(colors)]
        cv2.rectangle(debug, (x1, y1), (x2, y2), color, 3)
        cv2.putText(debug, label, (x1 + 5, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
    return debug


def generate_grid_debug_image(crop, h_pos, v_pos, spacing, occupied, confident, ambiguous):
    """Draw grid lines and occupied patches on crop. Returns annotated image."""
    debug = crop.copy()
    if len(debug.shape) == 2:
        debug = cv2.cvtColor(debug, cv2.COLOR_GRAY2BGR)

    # Draw grid lines
    for y in h_pos:
        cv2.line(debug, (0, int(y)), (debug.shape[1], int(y)), (0, 0, 200), 1)
    for x in v_pos:
        cv2.line(debug, (int(x), 0), (int(x), debug.shape[0]), (200, 0, 0), 1)

    r = int(spacing * 0.4) if spacing > 0 else 8

    # Draw occupied intersections
    confident_set = {(ci, ri) for ci, ri, _, _ in confident}
    for ci, ri, _ in occupied:
        vx, hy = int(v_pos[ci]), int(h_pos[ri])
        if (ci, ri) in confident_set:
            cv2.circle(debug, (vx, hy), r, (0, 220, 0), 2)  # green = confident
        else:
            cv2.circle(debug, (vx, hy), r, (0, 220, 220), 2)  # yellow = ambiguous

    # Label indices
    for ci, ri, _ in occupied:
        vx, hy = int(v_pos[ci]), int(h_pos[ri])
        cv2.putText(debug, f"{ci},{ri}", (vx + r + 2, hy + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

    return debug


def save_debug_images(page_img, crop, h_pos, v_pos, spacing, occupied, confident, ambiguous,
                      bboxes_dict, figure_labels, label, book_slug):
    """Save all debug images and return their relative paths."""
    debug_dir = ASSET_BASE / "tutorial_assets" / book_slug / "debug" / label
    debug_dir.mkdir(parents=True, exist_ok=True)

    paths = {}

    # 1. Bbox debug image (page with rectangles)
    bbox_list = [bboxes_dict.get(l) for l in figure_labels]
    bbox_debug = generate_bbox_debug_image(page_img, bbox_list, figure_labels)
    bbox_path = debug_dir / "bbox_debug.png"
    cv2.imwrite(str(bbox_path), bbox_debug)
    paths["bbox_debug"] = str(bbox_path.relative_to(ASSET_BASE))

    # 2. Grid + occupied debug image
    grid_debug = generate_grid_debug_image(crop, h_pos, v_pos, spacing, occupied, confident, ambiguous)
    grid_path = debug_dir / "grid_debug.png"
    cv2.imwrite(str(grid_path), grid_debug)
    paths["grid_debug"] = str(grid_path.relative_to(ASSET_BASE))

    # 3. Contact sheet (save a copy)
    # (built and saved separately in the caller, path added later)

    # 4. Crop image
    crop_path = debug_dir / "crop.png"
    cv2.imwrite(str(crop_path), crop)
    paths["crop"] = str(crop_path.relative_to(ASSET_BASE))

    return paths


# ── Training data collection ──────────────────────────────────────────────────

TRAINING_DIR = Path("data/training_patches")


def save_training_patch(patch, classification, book_slug, page, figure_label,
                        local_col, local_row, global_col, global_row, source):
    """Save a single classified patch with full provenance to manifest.jsonl."""
    patch_id = f"{book_slug}_{figure_label}_{local_col}_{local_row}"

    # Save image (organized by base_type for browsing)
    base_type = classification.base_type  # "black", "white", "empty", "unknown"
    class_dir = TRAINING_DIR / "images" / base_type
    class_dir.mkdir(parents=True, exist_ok=True)
    img_path = class_dir / f"{patch_id}.png"
    cv2.imwrite(str(img_path), patch)

    # Append to manifest.jsonl
    record = {
        "patch_id": patch_id,
        "image_path": str(img_path.relative_to(TRAINING_DIR)),
        "book": book_slug,
        "page": page,
        "figure": figure_label,
        "local_col": local_col,
        "local_row": local_row,
        "global_col": global_col,
        "global_row": global_row,
        "base_type": base_type,
        "text": classification.text,
        "shape": classification.shape,
        "confidence": classification.confidence,
        "source": source,
        "review_status": "raw_auto",  # raw_auto → reviewed → gold
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = TRAINING_DIR / "manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return patch_id


def save_all_training_patches(occupied_patches, classifications, label_map,
                              col_start, row_start, book_slug, page, figure_label):
    """Save all patches (including empty) for a figure with full provenance."""
    saved = 0
    patch_lookup = {(ci, ri): patch for ci, ri, patch in occupied_patches}

    for lbl, (ci, ri) in label_map.items():
        patch = patch_lookup.get((ci, ri))
        if patch is None:
            continue

        # Get classification for this label
        if isinstance(classifications, dict):
            cls_str = classifications.get(lbl, "empty")
            pc = parse_classification(lbl, cls_str, ci, ri, source="vllm")
        elif isinstance(classifications, list):
            pc = next((c for c in classifications if c.label == lbl), None)
            if pc is None:
                pc = PatchClassification(lbl, ci, ri, "empty", source="cv")
        else:
            continue

        save_training_patch(
            patch, pc, book_slug, page, figure_label,
            ci, ri, col_start + ci, row_start + ri, pc.source
        )
        saved += 1

    log.info("  Saved %d training patches for %s", saved, figure_label)
    return saved


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


# ── Contact sheet generation ──────────────────────────────────────────────────

def build_contact_sheet(occupied_patches, spacing, cols_per_row=8):
    """Arrange occupied intersection patches into a labeled contact sheet image.

    Args:
        occupied_patches: list of (col_idx, row_idx, patch_image)
        spacing: grid spacing in pixels (determines patch size)
        cols_per_row: number of patches per row in the sheet

    Returns:
        (sheet_image, label_map) where label_map is {"A": (col_idx, row_idx), ...}
    """
    if not occupied_patches:
        return None, {}

    patch_size = int(spacing * 1.0)
    margin = 4
    label_h = 16  # height for text label below each patch
    cell_w = patch_size + margin * 2
    cell_h = patch_size + margin * 2 + label_h

    n = len(occupied_patches)
    rows = ceil(n / cols_per_row)
    sheet_w = cols_per_row * cell_w
    sheet_h = rows * cell_h

    sheet = np.ones((sheet_h, sheet_w), dtype=np.uint8) * 240  # light gray background
    label_map = {}

    for idx, (ci, ri, patch) in enumerate(occupied_patches):
        row_i = idx // cols_per_row
        col_i = idx % cols_per_row
        x_off = col_i * cell_w + margin
        y_off = row_i * cell_h + margin

        # Resize patch to standard size
        resized = cv2.resize(patch, (patch_size, patch_size), interpolation=cv2.INTER_AREA)

        # Place patch
        sheet[y_off:y_off + patch_size, x_off:x_off + patch_size] = resized

        # Draw border
        cv2.rectangle(sheet, (x_off - 1, y_off - 1),
                      (x_off + patch_size, y_off + patch_size), 0, 1)

        # Label: A, B, C, ... AA, AB, ...
        if idx < 26:
            label = chr(65 + idx)
        else:
            label = chr(65 + idx // 26 - 1) + chr(65 + idx % 26)

        label_map[label] = (ci, ri)

        # Draw label text
        cv2.putText(sheet, f"{label}:({ci},{ri})", (x_off, y_off + patch_size + label_h - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, 0, 1)

    return sheet, label_map


# ── Annotated crop for VLLM classification ───────────────────────────────────

def build_annotated_crop(crop, h_positions, v_positions, occupied_patches, spacing):
    """Draw letter labels at occupied intersections on the full crop image.

    Unlike build_contact_sheet (isolated patches), this gives VLLM full context:
    complete stone shapes, surrounding board lines, and neighboring stones.

    Returns (annotated_image, label_map) where label_map is {"A": (col_idx, row_idx), ...}
    """
    annotated = crop.copy()
    if len(annotated.shape) == 2:
        annotated = cv2.cvtColor(annotated, cv2.COLOR_GRAY2BGR)

    label_map = {}
    r = max(8, int(spacing * 0.25))  # label circle radius

    for idx, (ci, ri, _) in enumerate(occupied_patches):
        if idx < 26:
            label = chr(65 + idx)
        else:
            label = chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
        label_map[label] = (ci, ri)

        vx = int(v_positions[ci])
        hy = int(h_positions[ri])

        # Draw a white circle background with magenta border for the label
        cv2.circle(annotated, (vx, hy), r, (255, 255, 255), -1)  # white fill
        cv2.circle(annotated, (vx, hy), r, (200, 0, 200), 2)     # magenta border

        # Draw the letter label centered
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.4 if len(label) == 1 else 0.3
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, 1)
        cv2.putText(annotated, label, (vx - tw // 2, hy + th // 2),
                    font, font_scale, (200, 0, 200), 1, cv2.LINE_AA)

    return annotated, label_map


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

def process_page(page_image_path, figure_ids, dry_run=False, db=None, force=False):
    """Process all diagrams on a single page.

    figure_ids: list of (figure_label, figure_db_id) e.g. [("图1", 1), ("图2", 2)]
    Returns list of FigureResult for per-figure status tracking.
    """
    results = []
    page_img = cv2.imread(str(page_image_path))
    if page_img is None:
        log.error("Cannot read image: %s", page_image_path)
        for label, fig_id in figure_ids:
            results.append(FigureResult(label, fig_id, "failed_cv", "cannot read page image"))
        return results
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
            results.append(FigureResult(label, fig_id, "failed_cv", "no bbox detected"))
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
            results.append(FigureResult(label, fig_id, "failed_cv", f"too few grid lines ({len(h_pos)}×{len(v_pos)})"))
            continue

        # Step 3: CV occupied intersection detection
        occupied = cv_detect_occupied(crop_gray, h_pos, v_pos, spacing)
        confident, ambiguous = cv_preclass_confident(occupied, spacing)
        log.info("  Step 3: %d occupied (%d confident, %d ambiguous)",
                 len(occupied), len(confident), len(ambiguous))

        # Step 1: Region calibration — CV hint, VLLM determines final value
        occupied_set = {(ci, ri) for ci, ri, _ in occupied}
        col_start, row_start, cal_conf, cal_evidence = calibrate_region(
            crop_gray, h_pos, v_pos, spacing, occupied_set
        )
        log.info("  Step 1 (CV hint): col_start=%d, row_start=%d, confidence=%.2f, evidence=%s",
                 col_start, row_start, cal_conf, cal_evidence)

        # VLLM region identification (always, CV is unreliable for this)
        try:
            region_prompt = VLLM_REGION_PROMPT.format(
                num_v=len(v_pos), num_h=len(h_pos))
            region = vllm_call(crop_path, region_prompt)
            col_start = region.get("col_start", col_start)
            row_start = region.get("row_start", row_start)
            log.info("  Step 1 (VLLM): col_start=%d, row_start=%d", col_start, row_start)
        except Exception as e:
            log.warning("  VLLM region failed (%s), using CV hint", e)

        # Step 4: VLLM classification via annotated crop (full context)
        # Build annotated crop with letter labels at ALL occupied positions
        annotated, full_label_map = build_annotated_crop(
            crop, h_pos, v_pos, occupied, spacing
        )
        log.info("  Step 4: built annotated crop with %d labeled positions", len(full_label_map))

        # Start with CV-confident as fallback
        confident_set = {(ci, ri): bt for ci, ri, _, bt in confident}
        merged_classifications = {}
        for lbl, (ci, ri) in full_label_map.items():
            if (ci, ri) in confident_set:
                merged_classifications[lbl] = confident_set[(ci, ri)]

        # VLLM classifies ALL positions using the full annotated crop
        annotated_path = Path(tempfile.mktemp(suffix=".png", prefix=f"annotated_{label}_"))
        cv2.imwrite(str(annotated_path), annotated)
        try:
            vllm_result = vllm_call(annotated_path, VLLM_CLASSIFY_PROMPT)
            log.info("  Step 4 (VLLM): classified %d positions", len(vllm_result))
            # VLLM results override CV pre-classifications (VLLM sees full context)
            for lbl, cls_str in vllm_result.items():
                if lbl in full_label_map:
                    merged_classifications[lbl] = cls_str
        except Exception as e:
            log.warning("  VLLM classification failed (%s), using CV-confident only", e)
        finally:
            annotated_path.unlink(missing_ok=True)

        log.info("  Classifications: %d total", len(merged_classifications))

        # Step 5: Build payload via classification_to_payload
        payload = classification_to_payload(merged_classifications, full_label_map, col_start, row_start)
        log.info("  Payload: B=%d W=%d labels=%d letters=%d",
                 len(payload["stones"]["B"]), len(payload["stones"]["W"]),
                 len(payload["labels"]), len(payload["letters"]))

        # Save training data
        # Extract page number from image path for training data provenance
        page_num_str = page_image_path.stem.replace("page_", "")
        book_slug = page_image_path.parent.parent.name  # e.g. "曹薰铉布局技巧-上册-曹薰铉-1997"
        save_all_training_patches(
            occupied, merged_classifications, full_label_map,
            col_start, row_start, book_slug, page_num_str, label
        )

        stone_count = len(payload["stones"]["B"]) + len(payload["stones"]["W"])
        label_count_total = len(payload.get("labels", {}))

        # Determine per-figure status
        if stone_count == 0:
            status = "failed_cv"
            detail = "no stones detected"
        elif cal_conf < 0.3:
            status = "needs_review"
            detail = f"low calibration confidence ({cal_conf:.2f})"
        else:
            status = "success"
            detail = f"{stone_count} stones, {label_count_total} labels"

        if dry_run:
            print(f"\n=== {label} (id={fig_id}) [{status}] ===")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif db is not None:
            figure = db_queries.get_figure(db, fig_id)
            if figure:
                if figure.board_payload and not force:
                    log.info("  Skipping %s (already has payload, use --force to overwrite)", label)
                    status = "skipped"
                    detail = "already has payload"
                else:
                    db_queries.update_figure_board(db, figure, payload)
                    log.info("  ✓ Saved to DB")
            else:
                log.error("  Figure id=%d not found in DB", fig_id)
                status = "failed_semantic"
                detail = "figure not found in DB"

        results.append(FigureResult(
            label, fig_id, status, detail,
            stone_count=stone_count, label_count=label_count_total,
            calibration_confidence=cal_conf,
        ))

        # Cleanup temp file
        crop_path.unlink(missing_ok=True)

    return results


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

def apply_classifications_from_file(db, section_id, json_path, force=False):
    """Apply VLLM classification results from a JSON file to DB.

    JSON format (col_start/row_start determined by VLLM/subagent, NOT CV):
    {
      "图1": {"classifications": {"A": "black+1", ...}, "col_start": 0, "row_start": 0},
      "图2": {...},
      ...
    }

    If patches directory exists alongside the JSON file (from --save-sheets),
    training data is automatically saved.
    """
    from katrain.web.tutorials.viewport import compute_viewport

    with open(json_path) as f:
        data = json.load(f)

    section = db_queries.get_section(db, section_id)
    if section is None:
        log.error("Section %d not found", section_id)
        return

    # Build figure lookup
    fig_by_label = {fig.figure_label: fig for fig in section.figures}

    results = []  # (label, status, detail)

    for label, entry in data.items():
        figure = fig_by_label.get(label)
        if figure is None:
            log.warning("  %s: not found in section — skipping", label)
            results.append((label, "failed_semantic", "figure not found in section"))
            continue

        if figure.board_payload and figure.board_payload.get("stones", {}).get("B") and not force:
            log.info("  %s: already has board_payload — skipping (use --force to overwrite)", label)
            results.append((label, "skipped", "already has payload"))
            continue

        classifications = entry.get("classifications", {})
        col_start = entry.get("col_start", 0)
        row_start = entry.get("row_start", 0)

        # Load label_map from the contact sheet metadata if available
        label_map = entry.get("label_map", {})
        if not label_map:
            log.warning("  %s: no label_map in JSON — skipping", label)
            results.append((label, "failed_semantic", "missing label_map"))
            continue

        # Convert label_map values from lists to tuples
        label_map = {k: tuple(v) for k, v in label_map.items()}

        try:
            payload = classification_to_payload(classifications, label_map, col_start, row_start)

            # Compute viewport before DB write (Codex fix)
            viewport = compute_viewport(payload)
            payload["viewport"] = viewport

            db_queries.update_figure_board(db, figure, payload)
            stone_count = len(payload["stones"]["B"]) + len(payload["stones"]["W"])
            log.info("  %s: applied (%d stones, %d labels) ✓",
                     label, stone_count, len(payload.get("labels", {})))

            # Update recognition_debug with classification results + final region
            # Deep copy to avoid SQLAlchemy in-place mutation detection issue
            existing_debug = json.loads(json.dumps(figure.recognition_debug or {}))
            existing_debug.setdefault("classification", {})["classifications"] = classifications
            existing_debug.setdefault("region", {})["col_start"] = col_start
            existing_debug["region"]["row_start"] = row_start
            existing_debug["region"]["method"] = "vllm"
            db_queries.update_figure_recognition_debug(db, figure, existing_debug)

            # Save training data if patches directory exists
            json_dir = Path(json_path).parent
            patches_dir = json_dir / "patches" / label
            if patches_dir.exists():
                occupied_patches = []
                for lbl, (ci, ri) in label_map.items():
                    patch_path = patches_dir / f"{lbl}_{ci}_{ri}.png"
                    if patch_path.exists():
                        patch = cv2.imread(str(patch_path), cv2.IMREAD_GRAYSCALE)
                        if patch is not None:
                            occupied_patches.append((ci, ri, patch))
                if occupied_patches:
                    book_slug = entry.get("book_slug", "unknown")
                    page = entry.get("page", 0)
                    save_all_training_patches(
                        occupied_patches, classifications, label_map,
                        col_start, row_start, book_slug, page, label
                    )

            results.append((label, "success", f"{stone_count} stones"))
        except Exception as e:
            log.error("  %s: failed — %s", label, e)
            results.append((label, "failed_semantic", str(e)))

    # Summary
    success = sum(1 for _, s, _ in results if s == "success")
    failed = sum(1 for _, s, _ in results if s.startswith("failed"))
    skipped = sum(1 for _, s, _ in results if s == "skipped")
    log.info("\nSummary: %d success, %d failed, %d skipped (total %d)",
             success, failed, skipped, len(results))


def save_sheets_for_section(db, section_id, output_dir):
    """Generate and save contact sheets for all figures in a section.

    Runs CV pipeline only (Steps 0-3), builds contact sheets, saves to output_dir.
    No VLLM calls, no DB writes.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    section = db_queries.get_section(db, section_id)
    if section is None:
        log.error("Section %d not found", section_id)
        return

    log.info("Section %d: %s (%d figures)", section.id, section.title, len(section.figures))

    pages = defaultdict(list)
    for fig in section.figures:
        pages[fig.page].append((fig.figure_label, fig.id))

    for page_num in sorted(pages.keys()):
        figure_ids = pages[page_num]
        fig0 = next(f for f in section.figures if f.page == page_num)
        if not fig0.page_image_path:
            log.warning("Page %d: no image path — skipping", page_num)
            continue
        image_path = ASSET_BASE / fig0.page_image_path
        if not image_path.exists():
            log.warning("Page %d: image not found at %s — skipping", page_num, image_path)
            continue

        page_img = cv2.imread(str(image_path))
        if page_img is None:
            log.error("Cannot read image: %s", image_path)
            continue
        page_gray = cv2.cvtColor(page_img, cv2.COLOR_BGR2GRAY)

        # Step 0: detect diagram bboxes (CV only — no VLLM)
        cv_regions = cv_detect_diagram_bboxes(page_gray)
        log.info("Page %d: CV detected %d diagram regions for %d figures",
                 page_num, len(cv_regions), len(figure_ids))

        bboxes = {}
        for i, (label, _) in enumerate(figure_ids):
            if i < len(cv_regions):
                y1, y2 = cv_regions[i]
                strip = page_gray[y1:y2, :]
                col_dark = np.sum(strip < 100, axis=0)
                dark_cols = np.where(col_dark > 5)[0]
                if len(dark_cols) > 0:
                    x1, x2 = int(dark_cols[0]) - 10, int(dark_cols[-1]) + 10
                    bboxes[label] = [x1, y1 - 10, x2, y2 + 10]

        for label, fig_id in figure_ids:
            bbox = bboxes.get(label)
            if bbox is None:
                log.warning("  %s: no bbox — skipping", label)
                continue

            x1, y1, x2, y2 = [max(0, int(c)) for c in bbox]
            x2 = min(page_img.shape[1], x2)
            y2 = min(page_img.shape[0], y2)
            crop = page_img[y1:y2, x1:x2]
            crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

            # Step 2: grid detection
            h_pos, v_pos, spacing = cv_detect_grid(crop_gray)
            if len(h_pos) < 3 or len(v_pos) < 3:
                log.warning("  %s: too few grid lines — skipping", label)
                continue

            # Step 3: occupied detection
            occupied = cv_detect_occupied(crop_gray, h_pos, v_pos, spacing)
            confident, ambiguous = cv_preclass_confident(occupied, spacing)
            log.info("  %s: %d×%d grid, %d occupied (%d confident, %d ambiguous)",
                     label, len(v_pos), len(h_pos), len(occupied),
                     len(confident), len(ambiguous))

            if not occupied:
                log.warning("  %s: no occupied intersections — skipping", label)
                continue

            # Region calibration
            occupied_set = {(ci, ri) for ci, ri, _ in occupied}
            col_start, row_start, cal_conf, cal_evidence = calibrate_region(
                crop_gray, h_pos, v_pos, spacing, occupied_set
            )
            log.info("  %s: region col_start=%d, row_start=%d (conf=%.2f)",
                     label, col_start, row_start, cal_conf)

            # Build annotated crop (primary VLLM input) + contact sheet (for display)
            annotated, label_map = build_annotated_crop(
                crop, h_pos, v_pos, occupied, spacing
            )
            sheet, _ = build_contact_sheet(occupied, spacing)

            # Save both
            annotated_path = output_dir / f"{label}_annotated.png"
            cv2.imwrite(str(annotated_path), annotated)
            sheet_path = output_dir / f"{label}.png"
            if sheet is not None:
                cv2.imwrite(str(sheet_path), sheet)

            # Build confident map
            confident_set = {(ci, ri): bt for ci, ri, _, bt in confident}
            conf_map = {}
            for lbl, (ci, ri) in label_map.items():
                if (ci, ri) in confident_set:
                    conf_map[lbl] = confident_set[(ci, ri)]

            region_needs_vllm = cal_conf < 0.5

            # Generate and save debug images to data/ dir
            book_slug = image_path.parent.parent.name
            figure_labels = [l for l, _ in figure_ids]
            debug_paths = save_debug_images(
                page_img, crop, h_pos, v_pos, spacing,
                occupied, confident, ambiguous,
                bboxes, figure_labels, label, book_slug
            )

            # Save annotated crop + contact sheet to debug dir
            debug_dir = ASSET_BASE / "tutorial_assets" / book_slug / "debug" / label
            debug_annotated_path = debug_dir / "annotated_crop.png"
            cv2.imwrite(str(debug_annotated_path), annotated)
            debug_paths["annotated_crop"] = str(debug_annotated_path.relative_to(ASSET_BASE))
            if sheet is not None:
                debug_sheet_path = debug_dir / "contact_sheet.png"
                cv2.imwrite(str(debug_sheet_path), sheet)
                debug_paths["contact_sheet"] = str(debug_sheet_path.relative_to(ASSET_BASE))

            # Build recognition_debug metadata for DB
            recognition_debug = {
                "bbox": {
                    "method": "cv",
                    "bbox": bboxes.get(label),
                    "debug_image": debug_paths.get("bbox_debug"),
                },
                "region": {
                    "method": "cv_hint",
                    "col_start": col_start,
                    "row_start": row_start,
                    "confidence": cal_conf,
                    "evidence": cal_evidence,
                    "grid_rows": len(h_pos),
                    "grid_cols": len(v_pos),
                    "needs_vllm": region_needs_vllm,
                },
                "cv_detection": {
                    "debug_image": debug_paths.get("grid_debug"),
                    "spacing": spacing,
                    "total_occupied": len(occupied),
                    "confident_count": len(confident),
                    "ambiguous_count": len(ambiguous),
                },
                "classification": {
                    "annotated_crop": debug_paths.get("annotated_crop"),
                    "contact_sheet": debug_paths.get("contact_sheet"),
                    "label_map": {k: list(v) for k, v in label_map.items()},
                    "confident_cv": conf_map,
                    "classifications": None,  # filled after VLLM step
                },
                "crop_image": debug_paths.get("crop"),
            }

            # Save recognition_debug to DB
            figure = db_queries.get_figure(db, fig_id)
            if figure:
                db_queries.update_figure_recognition_debug(db, figure, recognition_debug)

            # Save metadata to output dir (for --apply-classifications)
            meta = {
                "figure_label": label,
                "figure_id": fig_id,
                "grid_rows": len(h_pos),
                "grid_cols": len(v_pos),
                "spacing": spacing,
                "col_start": col_start,
                "row_start": row_start,
                "region_needs_vllm": region_needs_vllm,
                "calibration_confidence": cal_conf,
                "calibration_evidence": cal_evidence,
                "total_occupied": len(occupied),
                "confident_count": len(confident),
                "ambiguous_count": len(ambiguous),
                "label_map": {k: list(v) for k, v in label_map.items()},
                "confident": conf_map,
            }
            meta_path = output_dir / f"{label}.json"
            with open(meta_path, "w") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            # Save individual patches
            patches_dir = output_dir / "patches" / label
            patches_dir.mkdir(parents=True, exist_ok=True)
            patch_lookup = {(ci, ri): patch for ci, ri, patch in occupied}
            for lbl, (ci, ri) in label_map.items():
                patch = patch_lookup.get((ci, ri))
                if patch is not None:
                    patch_path = patches_dir / f"{lbl}_{ci}_{ri}.png"
                    cv2.imwrite(str(patch_path), patch)

            crop_path = output_dir / f"{label}_crop.png"
            cv2.imwrite(str(crop_path), crop)

            log.info("  %s: saved sheet + debug images → %s", label, debug_dir)

    log.info("Contact sheets saved to %s", output_dir)


def main():
    parser = argparse.ArgumentParser(description="Hybrid VLLM+CV board recognition")
    parser.add_argument("--section-id", type=int, help="Process all figures in this section")
    parser.add_argument("--test-cv", type=str, help="Test CV pipeline on a page image")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without DB write")
    parser.add_argument("--force", action="store_true", help="Overwrite existing board_payload")
    parser.add_argument("--save-sheets", type=str,
                        help="Save contact sheets to this directory (no DB write)")
    parser.add_argument("--apply-classifications", type=str,
                        help="Apply VLLM classification results from JSON file to DB")
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
        # Mode: save contact sheets (CV only, no VLLM, no DB write)
        if args.save_sheets:
            save_sheets_for_section(db, args.section_id, args.save_sheets)
            return

        # Mode: apply VLLM classifications from JSON file
        if args.apply_classifications:
            apply_classifications_from_file(db, args.section_id, args.apply_classifications, force=args.force)
            return

        # Default mode: full pipeline
        section = db_queries.get_section(db, args.section_id)
        if section is None:
            log.error("Section %d not found", args.section_id)
            return

        log.info("Section %d: %s (%d figures)", section.id, section.title, len(section.figures))

        # Group figures by page
        pages = defaultdict(list)
        for fig in section.figures:
            pages[fig.page].append((fig.figure_label, fig.id))

        all_results = []
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
            page_results = process_page(image_path, figure_ids, dry_run=args.dry_run, db=db, force=args.force)
            if page_results:
                all_results.extend(page_results)

        # Print summary report
        if all_results:
            print_summary_report(all_results)

    finally:
        db.close()


if __name__ == "__main__":
    main()
