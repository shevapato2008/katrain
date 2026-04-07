#!/usr/bin/env python3
"""Refine Go board bounding boxes using Gemini vision model.

The initial bboxes from the digitization pipeline are often too wide (spanning
nearly the full page width), capturing text and annotations alongside the board
diagram.  This script sends the cropped region to Gemini and asks it to return
a tight bbox around just the Go board grid area (lines + stones), excluding
figure labels, move descriptions, and margins.

Usage:
    # Dry run — print before/after without writing to DB
    python scripts/refine_bbox_gemini.py --section-id 194 --dry-run

    # Apply refinements to DB
    python scripts/refine_bbox_gemini.py --section-id 194

    # Process multiple sections
    python scripts/refine_bbox_gemini.py --section-id 194 195 197
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types

from katrain.web.core.config import settings
from katrain.web.core.db import SessionLocal
from katrain.web.core.models_db import TutorialFigure, TutorialSection

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

ASSET_BASE = Path("data")

GEMINI_MODEL = "gemini-3-flash-preview"

PROMPT = """\
You are looking at a cropped region from a Go (Baduk/Weiqi) textbook page.
The image contains a Go board diagram — a grid with black and white stones.
There may also be surrounding text, figure labels (like "图1"), move
descriptions, and page margins visible in the crop.

Your task: return the **tight bounding box** of JUST the Go board grid area.
Include the grid lines, stones on the grid, and the thin border/edge marks of
the board, but EXCLUDE:
- Figure labels (e.g. "图1", "图2")
- Text annotations or move descriptions
- Page margins or whitespace outside the board
- Any text below or beside the board

Return the bounding box as four normalized coordinates (0.0 to 1.0) relative
to this cropped image, in this exact format on a single line:

x_min=0.XX y_min=0.XX x_max=0.XX y_max=0.XX

Return ONLY that single line, nothing else."""


def parse_bbox_response(text: str) -> dict | None:
    """Parse Gemini's bbox response into a dict of floats."""
    text = text.strip()
    # Match pattern: x_min=0.XX y_min=0.XX x_max=0.XX y_max=0.XX
    pattern = r"x_min\s*=\s*([\d.]+)\s+y_min\s*=\s*([\d.]+)\s+x_max\s*=\s*([\d.]+)\s+y_max\s*=\s*([\d.]+)"
    match = re.search(pattern, text)
    if not match:
        return None
    vals = {
        "x_min": float(match.group(1)),
        "y_min": float(match.group(2)),
        "x_max": float(match.group(3)),
        "y_max": float(match.group(4)),
    }
    # Validate ranges
    for k, v in vals.items():
        if not (0.0 <= v <= 1.0):
            log.warning("Out-of-range value %s=%.4f, clamping", k, v)
            vals[k] = max(0.0, min(1.0, v))
    if vals["x_min"] >= vals["x_max"] or vals["y_min"] >= vals["y_max"]:
        log.warning("Invalid bbox (min >= max): %s", vals)
        return None
    return vals


def crop_relative_to_page(old_bbox: dict, gemini_bbox: dict) -> dict:
    """Convert Gemini's crop-relative bbox back to page-relative coordinates.

    old_bbox: the current page-relative bbox used to crop
    gemini_bbox: Gemini's response relative to the cropped image
    Returns: new page-relative bbox
    """
    ox, oy = old_bbox["x_min"], old_bbox["y_min"]
    ow = old_bbox["x_max"] - old_bbox["x_min"]
    oh = old_bbox["y_max"] - old_bbox["y_min"]

    new_bbox = {
        "x_min": round(ox + gemini_bbox["x_min"] * ow, 4),
        "y_min": round(oy + gemini_bbox["y_min"] * oh, 4),
        "x_max": round(ox + gemini_bbox["x_max"] * ow, 4),
        "y_max": round(oy + gemini_bbox["y_max"] * oh, 4),
    }
    return new_bbox


def crop_image_bytes(image_path: Path, bbox: dict) -> bytes:
    """Load a page image, crop it to the bbox, and return PNG bytes."""
    from PIL import Image
    import io

    img = Image.open(image_path)
    w, h = img.size
    left = int(bbox["x_min"] * w)
    top = int(bbox["y_min"] * h)
    right = int(bbox["x_max"] * w)
    bottom = int(bbox["y_max"] * h)
    cropped = img.crop((left, top, right, bottom))

    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()


def call_gemini(client: genai.Client, image_data: bytes) -> str | None:
    """Send cropped image to Gemini and return raw response text."""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_data, mime_type="image/png"),
                        types.Part.from_text(text=PROMPT),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
            ),
        )
        return response.text
    except Exception as e:
        log.error("Gemini API error: %s", e)
        return None


def generate_bbox_debug_image(page_image_path: Path, new_bbox: dict, fig_id: int, label: str, book_slug: str) -> str:
    """Draw the Gemini bbox on the page image and save as debug image.

    Returns the relative path for storing in recognition_debug.
    """
    page_img = cv2.imread(str(page_image_path))
    h, w = page_img.shape[:2]

    x1 = int(new_bbox["x_min"] * w)
    y1 = int(new_bbox["y_min"] * h)
    x2 = int(new_bbox["x_max"] * w)
    y2 = int(new_bbox["y_max"] * h)

    cv2.rectangle(page_img, (x1, y1), (x2, y2), (0, 0, 255), 3)
    cv2.putText(page_img, f"{label} (Gemini)", (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    debug_dir = ASSET_BASE / "tutorial_assets" / book_slug / "debug" / f"{fig_id}_{label}"
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_path = debug_dir / "bbox_debug.png"
    cv2.imwrite(str(debug_path), page_img)

    return f"tutorial_assets/{book_slug}/debug/{fig_id}_{label}/bbox_debug.png"


def process_section(section_id: int, client: genai.Client, dry_run: bool = True):
    """Process all figures in a section, refining their bboxes."""
    db = SessionLocal()
    try:
        section = db.query(TutorialSection).filter(TutorialSection.id == section_id).first()
        if not section:
            log.error("Section %d not found", section_id)
            return

        figures = (
            db.query(TutorialFigure)
            .filter(TutorialFigure.section_id == section_id)
            .order_by(TutorialFigure.order)
            .all()
        )

        if not figures:
            log.warning("Section %d has no figures", section_id)
            return

        log.info("=" * 70)
        log.info("Section %d: %s — %d figures", section_id, section.title, len(figures))
        log.info("=" * 70)

        success_count = 0
        fail_count = 0

        for fig in figures:
            if not fig.bbox or not fig.page_image_path:
                log.warning("  Figure %d (%s): missing bbox or image path — skipping", fig.id, fig.figure_label)
                fail_count += 1
                continue

            image_path = ASSET_BASE / fig.page_image_path
            if not image_path.exists():
                log.warning("  Figure %d (%s): image not found at %s — skipping", fig.id, fig.figure_label, image_path)
                fail_count += 1
                continue

            old_bbox = fig.bbox
            log.info("  Figure %d (%s) page %d:", fig.id, fig.figure_label, fig.page)
            log.info("    OLD bbox: x=[%.4f, %.4f] y=[%.4f, %.4f]  width=%.4f height=%.4f",
                     old_bbox["x_min"], old_bbox["x_max"],
                     old_bbox["y_min"], old_bbox["y_max"],
                     old_bbox["x_max"] - old_bbox["x_min"],
                     old_bbox["y_max"] - old_bbox["y_min"])

            # Crop and send to Gemini
            try:
                cropped_data = crop_image_bytes(image_path, old_bbox)
            except Exception as e:
                log.error("    Failed to crop image: %s", e)
                fail_count += 1
                continue

            raw_response = call_gemini(client, cropped_data)
            if not raw_response:
                log.error("    Gemini returned no response — skipping")
                fail_count += 1
                continue

            log.info("    Gemini raw: %s", raw_response.strip())

            gemini_bbox = parse_bbox_response(raw_response)
            if not gemini_bbox:
                log.error("    Failed to parse Gemini response — skipping")
                fail_count += 1
                continue

            new_bbox = crop_relative_to_page(old_bbox, gemini_bbox)
            log.info("    NEW bbox: x=[%.4f, %.4f] y=[%.4f, %.4f]  width=%.4f height=%.4f",
                     new_bbox["x_min"], new_bbox["x_max"],
                     new_bbox["y_min"], new_bbox["y_max"],
                     new_bbox["x_max"] - new_bbox["x_min"],
                     new_bbox["y_max"] - new_bbox["y_min"])

            old_area = (old_bbox["x_max"] - old_bbox["x_min"]) * (old_bbox["y_max"] - old_bbox["y_min"])
            new_area = (new_bbox["x_max"] - new_bbox["x_min"]) * (new_bbox["y_max"] - new_bbox["y_min"])
            reduction = (1 - new_area / old_area) * 100 if old_area > 0 else 0
            log.info("    Area reduction: %.1f%%", reduction)

            if not dry_run:
                # Generate debug image
                book_slug = Path(fig.page_image_path).parts[1]  # e.g. "李昌镐官子技巧-第1卷-李昌镐-1998"
                debug_image_rel = generate_bbox_debug_image(
                    image_path, new_bbox, fig.id, fig.figure_label, book_slug
                )

                # Convert new_bbox to pixel coords for recognition_debug
                from PIL import Image as PILImage
                pimg = PILImage.open(image_path)
                pw, ph = pimg.size
                pixel_bbox = [
                    int(new_bbox["x_min"] * pw),
                    int(new_bbox["y_min"] * ph),
                    int(new_bbox["x_max"] * pw),
                    int(new_bbox["y_max"] * ph),
                ]

                # Update bbox
                fig.bbox = new_bbox

                # Update recognition_debug.bbox
                rd = dict(fig.recognition_debug) if fig.recognition_debug else {}
                rd["bbox"] = {
                    "method": "gemini",
                    "bbox": pixel_bbox,
                    "debug_image": debug_image_rel,
                }
                fig.recognition_debug = rd

                db.commit()
                log.info("    -> Updated bbox + recognition_debug in DB")
            else:
                log.info("    -> DRY RUN, not saved")

            success_count += 1

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        log.info("-" * 70)
        log.info("Section %d summary: %d/%d refined, %d failed",
                 section_id, success_count, len(figures), fail_count)

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Refine Go board bboxes using Gemini vision")
    parser.add_argument("--section-id", type=int, nargs="+", required=True,
                        help="Section ID(s) to process")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print results without writing to DB")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY environment variable is required")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    for sid in args.section_id:
        process_section(sid, client, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
