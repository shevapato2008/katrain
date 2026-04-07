#!/usr/bin/env python3
"""Compare CV vs Gemini vs DB bounding box detection on Go textbook pages.

Generates an HTML comparison page showing:
  - Green: Original DB bboxes (current values in tutorial_figures.bbox)
  - Blue:  CV S0 morphological line detection (same as recognize_boards_v2.py)
  - Red:   Gemini vision model detection (full-page, all boards at once)

Usage:
    export GEMINI_API_KEY=...
    python scripts/compare_bboxes.py --section-id 194 195 196 197
"""

import argparse
import logging
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from katrain.web.core.db import SessionLocal
from katrain.web.core.models_db import TutorialFigure, TutorialSection

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

ASSET_BASE = Path("data")
GEMINI_MODEL = "gemini-3-flash-preview"

# ── CV S0 detection (replicated from recognize_boards_v2.py) ────────────────

def cv_detect_bboxes(page_image_path, binary_threshold=160):
    """Detect board bboxes using morphological line detection (S0 step).

    Returns list of (x1, y1, x2, y2) pixel-coordinate tuples.
    """
    gray = cv2.imread(str(page_image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        log.error("Could not read image: %s", page_image_path)
        return []
    h, w = gray.shape

    _, binary = cv2.threshold(gray, binary_threshold, 255, cv2.THRESH_BINARY_INV)

    min_line_len = min(h, w) // 10
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_len, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_line_len))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

    combined = cv2.bitwise_or(h_lines, v_lines)
    dilate_k = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 30))
    dilated = cv2.dilate(combined, dilate_k, iterations=3)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = (min(h, w) // 8) ** 2
    boxes = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw * bh > min_area:
            boxes.append((x, y, x + bw, y + bh))

    boxes.sort(key=lambda b: (b[1] // 200, b[0]))
    return boxes


def cv_bboxes_to_normalized(boxes, img_w, img_h):
    """Convert pixel bboxes to normalized [0,1] dicts."""
    result = []
    for x1, y1, x2, y2 in boxes:
        result.append({
            "x_min": x1 / img_w,
            "y_min": y1 / img_h,
            "x_max": x2 / img_w,
            "y_max": y2 / img_h,
        })
    return result


# ── Gemini full-page detection ──────────────────────────────────────────────

GEMINI_PAGE_PROMPT = """\
You are looking at a full page from a Go (Baduk/Weiqi) textbook.
The page may contain one or more Go board diagrams — grids with black and white stones.
There may also be text, figure labels (like "图1"), move descriptions, and page margins.

Your task: find ALL Go board diagrams on this page and return a tight bounding box
for each one. Include the grid lines, stones on the grid, and the thin border/edge
marks of the board, but EXCLUDE:
- Figure labels (e.g. "图1", "图2")
- Text annotations or move descriptions
- Page margins or whitespace outside the board

Return each bounding box as four normalized coordinates (0.0 to 1.0) relative to
the full page image, one per line, in this exact format:

board1: x_min=0.XX y_min=0.XX x_max=0.XX y_max=0.XX
board2: x_min=0.XX y_min=0.XX x_max=0.XX y_max=0.XX

If there is only one board, return just one line starting with "board1:".
Return ONLY these lines, nothing else. Order boards top-to-bottom, left-to-right."""


def parse_gemini_page_response(text):
    """Parse Gemini's multi-board page response into a list of bbox dicts."""
    bboxes = []
    pattern = r"x_min\s*=\s*([\d.]+)\s+y_min\s*=\s*([\d.]+)\s+x_max\s*=\s*([\d.]+)\s+y_max\s*=\s*([\d.]+)"
    for match in re.finditer(pattern, text):
        vals = {
            "x_min": float(match.group(1)),
            "y_min": float(match.group(2)),
            "x_max": float(match.group(3)),
            "y_max": float(match.group(4)),
        }
        # Clamp to [0, 1]
        for k in vals:
            vals[k] = max(0.0, min(1.0, vals[k]))
        if vals["x_min"] < vals["x_max"] and vals["y_min"] < vals["y_max"]:
            bboxes.append(vals)
    return bboxes


def call_gemini_page(client, image_path):
    """Send full page image to Gemini and get all board bboxes."""
    from google.genai import types

    with open(image_path, "rb") as f:
        image_data = f.read()

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_data, mime_type="image/png"),
                        types.Part.from_text(text=GEMINI_PAGE_PROMPT),
                    ],
                )
            ],
            config=types.GenerateContentConfig(temperature=0.1),
        )
        raw = response.text
        log.info("  Gemini raw response: %s", raw.strip().replace("\n", " | "))
        return parse_gemini_page_response(raw)
    except Exception as e:
        log.error("  Gemini API error: %s", e)
        return []


# ── Drawing ─────────────────────────────────────────────────────────────────

def draw_bboxes_on_image(image, bboxes, color, label, thickness=3):
    """Draw bboxes on an image. bboxes are normalized dicts."""
    h, w = image.shape[:2]
    for i, bbox in enumerate(bboxes):
        x1 = int(bbox["x_min"] * w)
        y1 = int(bbox["y_min"] * h)
        x2 = int(bbox["x_max"] * w)
        y2 = int(bbox["y_max"] * h)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
        # Label text with background
        tag = f"{label}" if len(bboxes) == 1 else f"{label}-{i+1}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        text_thickness = 2
        (tw, th), _ = cv2.getTextSize(tag, font, font_scale, text_thickness)
        # Draw text background
        cv2.rectangle(image, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
        cv2.putText(image, tag, (x1 + 3, y1 - 5), font, font_scale,
                    (255, 255, 255), text_thickness)
    return image


# ── HTML generation ─────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>BBox Comparison: CV vs Gemini vs DB</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
    background: #f5f5f5;
}}
h1 {{ color: #333; border-bottom: 2px solid #666; padding-bottom: 10px; }}
h2 {{ color: #555; margin-top: 40px; }}
.legend {{
    display: flex;
    gap: 30px;
    padding: 15px 20px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    margin-bottom: 30px;
    font-size: 14px;
}}
.legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
}}
.legend-swatch {{
    width: 24px;
    height: 16px;
    border-radius: 3px;
    border: 2px solid;
}}
.swatch-green {{ background: rgba(0,255,0,0.3); border-color: #00ff00; }}
.swatch-blue {{ background: rgba(255,100,0,0.3); border-color: #ff6400; }}
.swatch-red {{ background: rgba(0,0,255,0.3); border-color: #0000ff; }}
.page-card {{
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    margin-bottom: 20px;
    overflow: hidden;
}}
.page-card h3 {{
    margin: 0;
    padding: 12px 20px;
    background: #eee;
    font-size: 14px;
    color: #444;
}}
.page-card img {{
    width: 100%;
    display: block;
}}
.summary {{
    padding: 10px 20px;
    font-size: 13px;
    color: #666;
    border-top: 1px solid #eee;
}}
</style>
</head>
<body>
<h1>BBox Comparison: CV vs Gemini vs DB</h1>
<div class="legend">
    <div class="legend-item">
        <div class="legend-swatch swatch-green"></div>
        <span><strong>Green</strong> = DB original (current tutorial_figures.bbox)</span>
    </div>
    <div class="legend-item">
        <div class="legend-swatch swatch-blue"></div>
        <span><strong>Orange</strong> = CV S0 morphological detection</span>
    </div>
    <div class="legend-item">
        <div class="legend-swatch swatch-red"></div>
        <span><strong>Blue</strong> = Gemini vision detection</span>
    </div>
</div>
{sections_html}
</body>
</html>
"""


def generate_html(sections_data, output_dir):
    """Generate the comparison HTML file."""
    sections_html = ""
    for section_id, section_title, pages in sections_data:
        sections_html += f'<h2>Section {section_id}: {section_title}</h2>\n'
        for page_num, image_filename, db_count, cv_count, gemini_count in pages:
            sections_html += f"""<div class="page-card">
    <h3>Page {page_num} &mdash; {image_filename}</h3>
    <img src="{image_filename}" alt="Page {page_num}">
    <div class="summary">
        DB bboxes: {db_count} &nbsp;|&nbsp; CV S0 bboxes: {cv_count} &nbsp;|&nbsp; Gemini bboxes: {gemini_count}
    </div>
</div>
"""
    html = HTML_TEMPLATE.format(sections_html=sections_html)
    html_path = output_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")
    log.info("HTML written to %s", html_path)
    return html_path


# ── Main processing ─────────────────────────────────────────────────────────

def process_sections(section_ids, gemini_client):
    """Process all sections and generate comparison output."""
    db = SessionLocal()
    book_slug = "李昌镐官子技巧-第1卷-李昌镐-1998"
    output_dir = ASSET_BASE / f"tutorial_assets/{book_slug}/debug/bbox_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)

    sections_data = []

    try:
        for section_id in section_ids:
            section = db.query(TutorialSection).filter(TutorialSection.id == section_id).first()
            if not section:
                log.error("Section %d not found", section_id)
                continue

            figures = (
                db.query(TutorialFigure)
                .filter(TutorialFigure.section_id == section_id)
                .order_by(TutorialFigure.order)
                .all()
            )
            if not figures:
                log.warning("Section %d has no figures", section_id)
                continue

            log.info("=" * 70)
            log.info("Section %d: %s (%d figures)", section_id, section.title, len(figures))
            log.info("=" * 70)

            # Group figures by page image
            page_groups = defaultdict(list)
            for fig in figures:
                if fig.page_image_path and fig.bbox:
                    page_groups[fig.page_image_path].append(fig)

            page_results = []

            for page_image_rel, page_figures in sorted(page_groups.items(),
                                                        key=lambda x: x[1][0].page):
                page_num = page_figures[0].page
                page_image_path = ASSET_BASE / page_image_rel
                if not page_image_path.exists():
                    log.warning("  Page image not found: %s", page_image_path)
                    continue

                log.info("  Page %d: %s (%d DB figures)",
                         page_num, page_image_path.name, len(page_figures))

                # Load image
                img = cv2.imread(str(page_image_path))
                if img is None:
                    log.error("  Could not read image")
                    continue
                img_h, img_w = img.shape[:2]

                # 1. DB bboxes (green)
                db_bboxes = [fig.bbox for fig in page_figures]
                log.info("    DB bboxes: %d", len(db_bboxes))

                # 2. CV S0 bboxes (orange/blue in BGR)
                cv_pixel_boxes = cv_detect_bboxes(page_image_path)
                cv_bboxes = cv_bboxes_to_normalized(cv_pixel_boxes, img_w, img_h)
                log.info("    CV bboxes: %d", len(cv_bboxes))

                # 3. Gemini bboxes (red)
                if gemini_client:
                    gemini_bboxes = call_gemini_page(gemini_client, page_image_path)
                    log.info("    Gemini bboxes: %d", len(gemini_bboxes))
                    time.sleep(1.0)  # rate limit
                else:
                    gemini_bboxes = []
                    log.info("    Gemini: skipped (no API key)")

                # Draw on image (BGR colors)
                annotated = img.copy()
                # Green = DB (BGR: 0, 255, 0)
                draw_bboxes_on_image(annotated, db_bboxes, (0, 255, 0), "DB", thickness=3)
                # Orange = CV (BGR: 0, 100, 255)
                draw_bboxes_on_image(annotated, cv_bboxes, (0, 100, 255), "CV", thickness=3)
                # Blue = Gemini (BGR: 255, 0, 0)
                draw_bboxes_on_image(annotated, gemini_bboxes, (255, 0, 0), "Gemini", thickness=3)

                # Save annotated image
                out_filename = f"s{section_id}_page_{page_num:03d}.png"
                out_path = output_dir / out_filename
                cv2.imwrite(str(out_path), annotated)
                log.info("    Saved: %s", out_path)

                page_results.append((
                    page_num, out_filename,
                    len(db_bboxes), len(cv_bboxes), len(gemini_bboxes)
                ))

            sections_data.append((section_id, section.title, page_results))

    finally:
        db.close()

    # Generate HTML
    html_path = generate_html(sections_data, output_dir)
    return html_path


def main():
    parser = argparse.ArgumentParser(
        description="Compare CV vs Gemini vs DB bounding box detection"
    )
    parser.add_argument("--section-id", type=int, nargs="+", required=True,
                        help="Section ID(s) to process")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    gemini_client = None
    if api_key:
        from google import genai
        gemini_client = genai.Client(api_key=api_key)
        log.info("Gemini client initialized (model: %s)", GEMINI_MODEL)
    else:
        log.warning("GEMINI_API_KEY not set — Gemini detection will be skipped")

    html_path = process_sections(args.section_id, gemini_client)
    log.info("Done! Open in browser: %s", html_path)


if __name__ == "__main__":
    main()
