"""Generate tsumego physical-board voice prompts via edge-tts (dev-time tool).

Usage: uv run --no-sync python scripts/generate_tsumego_voice.py
Output: katrain/sounds/voice/<name>.mp3 (committed to the repo)

The two committed lighting_* clips use macOS Tingting Mandarin (2026-10-12),
as an offline fallback after Microsoft synthesis repeatedly returned HTTP 403.
This generator keeps Xiaoxiao as its default voice.
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
    "board_mismatch": "盘面与对局不一致，请查看屏幕圈出的位置。",
    "judge_undecided": "星阵数子还有归属未定的位置，请查看棋盘并继续收官。",
    "local_confirm_physical": "请双方每次只下一手。落子并拿除提子后，移开双手，点击本方确认。听到落子音效、对方区域亮起后，对方再下下一手。",
    "local_confirm_screen": "请点击棋盘选择落子位置，可以再次点击调整。选好后，点击本方确认。听到落子音效、对方区域亮起后，对方再下下一手。",
    "lighting_overexposed": "画面过亮，无法可靠识别棋盘。请移开遮挡。如果提示仍未消失，请换到光线均匀、合适的地方下棋。",
    "lighting_underexposed": "画面过暗，无法可靠识别棋盘。请移开遮挡。如果提示仍未消失，请换到光线均匀、合适的地方下棋。",
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
