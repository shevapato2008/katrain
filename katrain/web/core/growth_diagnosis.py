"""跨局能力诊断的分桶:按布局 / 中盘 / 官子三段数「评过级的手」和「其中的问题手」。

**没有新阈值。** 档位与阶段边界的唯一真源都是 `katrain/core/move_grade.yaml`
(`tiers[].bad` 那三档 = 小亏 · 失误 · 恶手,`display.phases` = 复盘屏那三段)——
仓里为「妙手 / 失误」散过五份阈值,那条路不能再走。

**`grade` 为空 / `unrated` 的手不进分母。** 它们是「不知道」(上一手没分析、搜索量不够),
不是「没问题」;算进分母只会把失误率稀释成一个看着很好的假数。
"""

from typing import Any, Iterable, Mapping, Optional

from katrain.core import move_grade

PHASES = ("opening", "midgame", "endgame")


def bucket(moves: Iterable[Mapping[str, Any]], cfg: Optional[dict] = None) -> dict:
    """`moves` 每项要有 `move_number` 与 `grade` → `{"graded": n, "phases": {phase: {"graded", "bad"}}}`。"""
    cfg = cfg or move_grade.load_config()
    bad_ids = {t["id"] for t in cfg["tiers"] if t.get("bad")}
    out = {"graded": 0, "phases": {p: {"graded": 0, "bad": 0} for p in PHASES}}
    for move in moves:
        grade = move.get("grade")
        if not grade or grade == move_grade.UNRATED:
            continue
        slot = out["phases"][move_grade.phase_of(int(move["move_number"]), cfg)]
        slot["graded"] += 1
        if grade in bad_ids:
            slot["bad"] += 1
        out["graded"] += 1
    return out
