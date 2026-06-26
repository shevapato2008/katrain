from pathlib import Path
from sqlalchemy.orm import Session
from katrain.web.core.models_db import TutorialFigure, TutorialSection, TutorialChapter, TutorialBook

REPO_ROOT = Path(__file__).parent.parent.parent.parent


def _get_book_slug(db: Session, figure: TutorialFigure) -> str:
    section = db.get(TutorialSection, figure.section_id)
    if section is None:
        raise ValueError(f"Missing section for figure {figure.id}")
    chapter = db.get(TutorialChapter, section.chapter_id)
    if chapter is None:
        raise ValueError(f"Missing chapter for figure {figure.id}")
    book = db.get(TutorialBook, chapter.book_id)
    if book is None:
        raise ValueError(f"Missing book for figure {figure.id}")
    return book.slug


async def generate_figure_audio(db: Session, figure: TutorialFigure, text: str = None) -> TutorialFigure:
    """Generate TTS audio for a figure and update the database.

    If text is provided, it updates the narration first.
    Uses edge-tts by default.
    """
    import edge_tts

    if text is not None:
        figure.narration = text
        db.add(figure)
        db.commit()
        db.refresh(figure)

    if not figure.narration:
        return figure

    book_slug = _get_book_slug(db, figure)
    rel_path = f"{book_slug}/audio/fig_{figure.id}.mp3"
    abs_path = REPO_ROOT / "data" / "tutorial_assets" / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate audio
    voice = "zh-CN-XiaoxiaoNeural"
    communicate = edge_tts.Communicate(figure.narration, voice)
    await communicate.save(str(abs_path))

    # Update audio_asset in DB
    figure.audio_asset = f"tutorial_assets/{rel_path}"
    db.add(figure)
    db.commit()
    db.refresh(figure)

    # Write-through to object store (no-op for local backend). D8: local copy stays.
    from katrain.web.core.storage import upload_file

    upload_file(figure.audio_asset, abs_path)

    return figure
