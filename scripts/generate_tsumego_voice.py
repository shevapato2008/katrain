"""Generate tsumego physical-board voice prompts via edge-tts (dev-time tool).

Usage: uv run --no-sync python scripts/generate_tsumego_voice.py
Output: katrain/sounds/voice/<name>.mp3 (committed to the repo)
"""

import asyncio
from pathlib import Path

import edge_tts

VOICE = "zh-CN-XiaoxiaoNeural"

LINES = {
    "clear_board": "请清空棋盘",
    "place_black": "请摆放黑棋",
    "place_white": "请摆放白棋",
    "setup_done": "摆放完成，请开始解题",
    "correct": "答对了",
    "wrong_remove": "答错了，请取回棋子",
    "capture_remove": "请提走被吃的棋子",
}


async def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "katrain" / "sounds" / "voice"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in LINES.items():
        path = out_dir / f"{name}.mp3"
        await edge_tts.Communicate(text, VOICE).save(str(path))
        print(f"wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
