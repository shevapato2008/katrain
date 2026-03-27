---
name: tutorial-recognition-pipeline
description: >
  Go board recognition pipeline for tutorial book digitization. Use when processing
  tutorial book pages into structured board data: running the 5-step CV+VLLM pipeline
  (recognize_boards_v2.py), managing the figure editing/verification UI, exporting
  training samples, or debugging recognition results. Triggers on: board recognition,
  棋谱识别, tutorial processing, figure verification, patch classification, training data export.
---

# Tutorial Board Recognition Pipeline

Digitize Go textbook diagrams into structured `BoardPayload` JSON via a hybrid CV + VLLM pipeline.

## Architecture

```
Book PDF → Page Images → [S0] BBox Detection → [S1] Region Calibration
→ [S2] Grid Detection → [S3] Occupied Detection → [S4] VLLM Classification
→ BoardPayload → Human Verification → Training Samples Export
```

## Key Files

| Component | Path |
|-----------|------|
| Pipeline script | `scripts/recognize_boards_v2.py` |
| Training export | `katrain/web/tutorials/training_export.py` |
| Verify endpoint | `katrain/web/api/v1/endpoints/tutorials.py` |
| DB models | `katrain/web/core/models_db.py` (TutorialFigure, TrainingSample) |
| Editor UI | `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx` |
| Few-shot examples | `data/training_patches/examples/` (6 reference patches) |
| Debug output | `data/tutorial_assets/{book_slug}/debug/{figure_label}/` |

## Running the Pipeline

```bash
# Full pipeline for a section (CV + VLLM + DB write)
python scripts/recognize_boards_v2.py --section-id <ID>

# Dry run (print results without DB write)
python scripts/recognize_boards_v2.py --section-id <ID> --dry-run

# Force re-process (overwrite existing board_payload)
python scripts/recognize_boards_v2.py --section-id <ID> --force

# CV-only test on a single page image
python scripts/recognize_boards_v2.py --test-cv data/tutorial_assets/.../pages/page_016.png
```

## VLLM Authentication

The pipeline uses Claude Max OAuth for VLLM calls (vision API). The `vllm_call()` function:
- Clears `ANTHROPIC_API_KEY` from subprocess env (that key has no credits)
- Calls `claude -p` which falls back to Max OAuth from macOS keychain
- Images are base64-encoded inline in the prompt text
- Model: `claude-sonnet-4-20250514`

If auth fails: run `claude /login` to refresh OAuth credentials.

## Pipeline Steps

See [references/pipeline-steps.md](references/pipeline-steps.md) for detailed step descriptions.

**Summary:**
- **S0**: Detect diagram bounding boxes on page (VLLM fallback to CV)
- **S1**: Determine which portion of 19x19 board is shown (CV hint + VLLM)
- **S2**: OpenCV morphological grid line detection (precise h/v positions)
- **S3**: Multi-feature anomaly detection for occupied intersections + letter annotations
- **S4**: VLLM few-shot classification (sends fewshot_sheet + annotated_crop)

## Data Model

See [references/data-model.md](references/data-model.md) for complete schemas.

**BoardPayload** (stored in `tutorial_figures.board_payload`):
```json
{
  "size": 19,
  "stones": {"B": [[col,row],...], "W": [[col,row],...]},
  "labels": {"col,row": "1"},    // move numbers
  "letters": {"col,row": "A"},   // annotations
  "shapes": {"col,row": "triangle"},
  "viewport": {"col": 0, "row": 0, "cols": 12, "rows": 19}
}
```

## Human Verification Flow

1. Open tutorial figure page in web UI (`/galaxy/tutorials/section/{id}`)
2. Edit board with toolbar (stone/letter/shape/eraser tools)
3. Click "保存" to save board_payload
4. Click "确认审核" to mark as verified
5. Verify endpoint auto-exports training samples to `training_samples` table

## Training Data Export

Auto-triggered on verify. Can also run manually:

```bash
# Export all verified figures
python scripts/export_training_data.py --all

# Export specific section
python scripts/export_training_data.py --section-id <ID>

# Preview without DB write
python scripts/export_training_data.py --all --dry-run
```

**Training patch structure:** Each patch is ~40x40px grayscale, centered on an intersection using precise OpenCV grid positions. Labels are derived from the human-verified `board_payload`.

## Debug Output

Each processed figure generates debug images in `data/tutorial_assets/{book}/debug/{figure}/`:
- `crop.png` — cropped diagram from page
- `grid_debug.png` — detected grid lines overlay
- `annotated_crop.png` — crop with labeled occupied positions (sent to VLLM)
- `bbox_debug.png` — bounding box detection
- `patches/` — individual intersection patches (`{label}_{col}_{row}.png`)

## Finding Section IDs

```python
from katrain.web.core.db import SessionLocal
from katrain.web.core.models_db import TutorialSection, TutorialFigure
db = SessionLocal()
sections = db.query(TutorialSection).all()
for s in sections:
    figs = db.query(TutorialFigure).filter_by(section_id=s.id).all()
    unprocessed = [f for f in figs if not (f.recognition_debug or {}).get('classification')]
    print(f"Section {s.id}: {s.title} — {len(figs)} figs ({len(unprocessed)} unprocessed)")
```
