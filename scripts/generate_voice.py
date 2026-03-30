#!/usr/bin/env python3
"""Generate narration text + TTS audio for tutorial figures.

For each figure in a section:
  1. Rewrite book_text → narration via Claude API
  2. Generate TTS audio via edge-tts (or CosyVoice if configured)
  3. Save narration + audio_asset path to database

Usage:
    python scripts/generate_voice.py --section-id <ID>
    python scripts/generate_voice.py --section-id <ID> --force      # Re-generate all
    python scripts/generate_voice.py --section-id <ID> --dry-run    # Preview only
    python scripts/generate_voice.py --section-id <ID> --tts cosyvoice --cosyvoice-url http://localhost:50000
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from katrain.web.core.db import SessionLocal
from katrain.web.core.models_db import TutorialFigure, TutorialSection, TutorialBook, TutorialChapter


def get_book_slug(db, section_id: int) -> str:
    """Resolve book slug from section_id."""
    section = db.query(TutorialSection).filter_by(id=section_id).first()
    if not section:
        raise ValueError(f"Section {section_id} not found")
    chapter = db.query(TutorialChapter).filter_by(id=section.chapter_id).first()
    book = db.query(TutorialBook).filter_by(id=chapter.book_id).first()
    return book.slug


def rewrite_narration(book_text: str) -> str:
    """Rewrite book text via Claude API into tutorial narration."""
    import anthropic

    prompt = """You are helping create Go (围棋) tutorial narration for learners.

Rewrite the following Chinese Go book text. Requirements:
- Keep ALL concepts, technical terms, and strategic content intact
- Rephrase sentence structure and word choice so it doesn't feel like a direct copy
- Maintain the same level of detail and meaning
- Write in natural, clear Mandarin Chinese suitable for a digital tutorial
- Use a warm, conversational tone as if explaining to a student
- Output ONLY the rewritten Chinese text — no translation, no explanation, no quotes

Original text:
{text}
"""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt.format(text=book_text)}],
    )
    return message.content[0].text.strip()


def generate_audio_edge_tts(text: str, path: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bool:
    """Generate TTS audio via edge-tts."""
    import asyncio
    import edge_tts

    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        async def _gen():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(path)
        asyncio.run(_gen())
        return True
    except Exception as e:
        print(f"  [TTS] Warning: edge-tts failed: {e}")
        return False


def generate_audio_cosyvoice(text: str, path: str, base_url: str = "http://localhost:50000") -> bool:
    """Generate TTS audio via CosyVoice HTTP API."""
    import requests

    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        resp = requests.post(
            f"{base_url}/tts",
            json={"text": text, "speaker": "中文女"},
            timeout=60,
        )
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
        return True
    except Exception as e:
        print(f"  [TTS] Warning: CosyVoice failed: {e}")
        return False


def process_section(
    section_id: int,
    force: bool = False,
    dry_run: bool = False,
    tts_backend: str = "edge-tts",
    cosyvoice_url: str = "http://localhost:50000",
    voice: str = "zh-CN-XiaoxiaoNeural",
):
    db = SessionLocal()
    try:
        section = db.query(TutorialSection).filter_by(id=section_id).first()
        if not section:
            print(f"Error: Section {section_id} not found")
            return

        book_slug = get_book_slug(db, section_id)
        audio_dir = REPO_ROOT / "data" / "tutorial_assets" / book_slug / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        figures = (
            db.query(TutorialFigure)
            .filter_by(section_id=section_id)
            .order_by(TutorialFigure.order)
            .all()
        )

        print(f"Section {section_id}: {section.title} — {len(figures)} figures")
        print(f"TTS backend: {tts_backend}")
        print(f"Audio dir: {audio_dir}")
        print()

        for fig in figures:
            print(f"  [{fig.figure_label}] page {fig.page}")

            if not fig.book_text:
                print(f"    ⏭ No book_text, skipping")
                continue

            if fig.narration and fig.audio_asset and not force:
                print(f"    ✓ Already has narration + audio, skipping (use --force to redo)")
                continue

            # Step 1: Rewrite narration
            if fig.narration and not force:
                narration = fig.narration
                print(f"    ✓ Using existing narration")
            else:
                print(f"    Rewriting narration...")
                if dry_run:
                    narration = f"[DRY RUN] Would rewrite: {fig.book_text[:50]}..."
                    print(f"    → {narration}")
                else:
                    try:
                        narration = rewrite_narration(fig.book_text)
                        print(f"    → {narration[:60]}...")
                    except Exception as e:
                        print(f"    ✗ Narration failed: {e}")
                        narration = fig.book_text  # fallback

            # Step 2: Generate TTS audio
            audio_filename = f"fig_{fig.id}.mp3"
            audio_path = audio_dir / audio_filename
            audio_asset_relative = f"tutorial_assets/{book_slug}/audio/{audio_filename}"

            if audio_path.exists() and not force:
                print(f"    ✓ Audio file exists: {audio_filename}")
            else:
                print(f"    Generating TTS → {audio_filename}")
                if not dry_run:
                    if tts_backend == "cosyvoice":
                        ok = generate_audio_cosyvoice(narration, str(audio_path), cosyvoice_url)
                    else:
                        ok = generate_audio_edge_tts(narration, str(audio_path), voice)
                    if ok:
                        print(f"    ✓ Audio saved")
                    else:
                        print(f"    ✗ Audio generation failed")
                        audio_asset_relative = None

            # Step 3: Save to DB
            if not dry_run:
                fig.narration = narration
                if audio_asset_relative:
                    fig.audio_asset = audio_asset_relative
                db.commit()
                print(f"    ✓ Saved to DB")
            else:
                print(f"    [DRY RUN] Would save narration + audio_asset={audio_asset_relative}")

            print()

        print("Done!")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Generate voice narration for tutorial figures")
    parser.add_argument("--section-id", type=int, required=True, help="Section ID to process")
    parser.add_argument("--force", action="store_true", help="Re-generate even if narration/audio exists")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--tts", choices=["edge-tts", "cosyvoice"], default="edge-tts", help="TTS backend")
    parser.add_argument("--cosyvoice-url", default="http://localhost:50000", help="CosyVoice API URL")
    parser.add_argument("--voice", default="zh-CN-XiaoxiaoNeural", help="edge-tts voice name")
    args = parser.parse_args()

    process_section(
        section_id=args.section_id,
        force=args.force,
        dry_run=args.dry_run,
        tts_backend=args.tts,
        cosyvoice_url=args.cosyvoice_url,
        voice=args.voice,
    )


if __name__ == "__main__":
    main()
