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
    "stone_offcenter": "棋子没放正，请摆正后继续。",
    "suspected_move": "检测到疑似落子，请在屏幕上确认。",
    "calibration_move_hand": "请移开手，保持棋盘上方无遮挡。",
    "calibration_running": "正在标定，请不要遮挡棋盘。",
    "calibration_obstructed": "检测到遮挡，请移开手。",
    "calibration_too_bright": "光线太亮，请拉上窗帘，避开直射光。",
    "calibration_too_dark": "光线太暗，请打开室内灯。",
    "calibration_done": "棋盘标定完成。",
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
