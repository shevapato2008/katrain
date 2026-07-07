import os
import asyncio
from pathlib import Path
import edge_tts
from sqlalchemy.orm import Session
from katrain.web.core.models_db import TutorialFigure


async def _generate_audio_async(text: str, output_path: str, voice: str = "zh-CN-YunxiNeural"):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def generate_figure_audio(db: Session, figure: TutorialFigure, text: str) -> str:
    """Generates audio for the given text and updates the figure's audio_asset."""
    # Define paths
    assets_dir = Path("data/tutorial_assets")
    assets_dir.mkdir(parents=True, exist_ok=True)

    filename = f"figure_{figure.id}_audio.mp3"
    filepath = assets_dir / filename

    # Generate audio
    asyncio.run(_generate_audio_async(text, str(filepath)))

    # Update figure
    asset_path = f"tutorial_assets/{filename}"
    figure.audio_asset = asset_path
    figure.narration = text
    db.commit()
    db.refresh(figure)

    return asset_path
