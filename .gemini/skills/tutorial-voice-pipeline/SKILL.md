---
name: tutorial-voice-pipeline
description: >
  Tutorial voice narration pipeline for Go textbook digitization. Use when generating
  narration text and TTS audio for tutorial figures: managing narration rewriting 
  via Gemini (Agent-led), configuring TTS backends (edge-tts / CosyVoice), 
  debugging audio output, or editing narration in the web UI.
  Triggers on: voice generation, narration, TTS, audio, 语音讲解, 旁白, edge-tts,
  CosyVoice, generate_voice.
---

# Tutorial Voice Pipeline

Convert Go textbook prose into tutorial narration text and synthesized speech audio.
The pipeline rewrites `book_text` into natural tutorial narration (via Gemini Agent), 
then generates MP3 audio via edge-tts (or CosyVoice), saving both to the database. 
Supports parallel processing.

## Architecture

```
Book Import (import_book.py)
  └─ book_text (OCR from textbook)
       │
       ├─ [Step 1] Narration Rewriting:
       │     Gemini Agent: Agent rewrites directly and updates DB.
       │     Prompt: rephrase for tutorial tone, keep all Go concepts
       │
       ├─ [Step 2] TTS synthesis → MP3 audio file (via generate_voice.py)
       │     Backend: edge-tts (default) or CosyVoice (optional)
       │     Voice: zh-CN-XiaoxiaoNeural (default)
       │
       └─ [Step 3] Save to DB → narration + audio_asset columns
             API: PUT /figures/{id}/narration
```

## Pipeline Execution Order

This skill is part of a 3-skill tutorial digitization pipeline. **Check prerequisites before running.**

| Order | Skill | Script | Prerequisite Check |
|-------|-------|--------|--------------------|
| 0 (first) | `tutorial-book-import` | `import_book.py` | book.json + pages exist in book-dir |
| 1 (after 0) | `tutorial-recognition-pipeline` | `recognize_boards_v2.py` | Figures exist in DB with `page_image_path` and `bbox` |
| 2 (after 0) | **`tutorial-voice-pipeline`** | `generate_voice.py` | Figures exist in DB with `book_text` |

Steps 1 and 2 are independent — can run in any order or in parallel. Both require step 0.

**Before running this skill, verify:**
- Section has figures in the database with `book_text` populated.
- If prerequisites are not met, inform the user to run `tutorial-book-import` (`scripts/import_book.py`) first.

## Key Files

| Component | Path |
|-----------|------|
| Pipeline script | `scripts/generate_voice.py` |
| DB models | `katrain/web/core/models_db.py` (TutorialFigure) |
| DB queries | `katrain/web/tutorials/db_queries.py` (`update_figure_narration`) |
| API schemas | `katrain/web/tutorials/models.py` (`NarrationUpdate`) |
| API endpoints | `katrain/web/api/v1/endpoints/tutorials.py` |
| Audio player UI | `katrain/web/ui/src/galaxy/components/tutorials/AudioPlayer.tsx` |
| Figure page UI | `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx` |
| Audio output dir | `data/tutorial_assets/{book_slug}/audio/` |

## Running the Pipeline

### Option A: Gemini Agent-Led (Recommended)

1. **Agent Rewrites**: Ask the Gemini CLI agent to generate narrations for a specific section.
2. **Agent Updates DB**: The agent writes the narrations directly to the database.
3. **Run TTS**:
   ```bash
   python scripts/generate_voice.py --section-id <ID>
   ```
   (The script will detect existing narrations and only generate audio).

## Narration Rewriting

### Gemini Agent

- **Workflow**: Agent reads `book_text`, rewrites it using internal logic, and uses `run_shell_command` to update the DB.
- **Prompt**: Warm, conversational, technical integrity.

### Prompt

```
You are helping create Go (围棋) tutorial narration for learners.

Rewrite the following Chinese Go book text. Requirements:
- Keep ALL concepts, technical terms, and strategic content intact
- Rephrase sentence structure and word choice so it doesn't feel like a direct copy
- Maintain the same level of detail and meaning
- Write in natural, clear Mandarin Chinese suitable for a digital tutorial
- Use a warm, conversational tone as if explaining to a student
- Output ONLY the rewritten Chinese text — no translation, no explanation, no quotes

Original text:
{text}
```

## TTS Backends

### edge-tts (Default)

Free Microsoft Edge TTS service. No API key required.

- **Package**: `edge-tts`
- **Default voice**: `zh-CN-XiaoxiaoNeural` (female Mandarin Chinese)

### CosyVoice (Optional)

Self-hosted TTS via CosyVoice HTTP API.

- **API**: `POST {base_url}/tts`
- **Default URL**: `http://localhost:50000`

## Data Model

### TutorialFigure Columns (voice-related)

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `book_text` | `Text` | `import_book.py` | Original OCR text from book (input) |
| `narration` | `Text` | AI Agent | Rewritten narration text (output) |
| `audio_asset` | `String(512)` | `generate_voice.py` | Relative path to MP3 file (output) |

## Finding Section IDs

```python
from katrain.web.core.db import SessionLocal
from katrain.web.core.models_db import TutorialSection, TutorialFigure

db = SessionLocal()
for s in db.query(TutorialSection).all():
    figs = db.query(TutorialFigure).filter_by(section_id=s.id).all()
    print(f"Section {s.id}: {s.title} — {len(figs)} figs")
```
