"""着手评价（move grade）。

阈值与档位的唯一真源是同目录的 ``move_grade.yaml``；本模块只负责读它、
按它判级、以及把档位表生成给前端。

设计要点（依据见 docs/move-grading/design.md）：

* ``pointsLost`` 取自**同一次搜索**（第 N-1 手的 moveInfos），不是两次搜索之差。
  实测两次搜索之差在「人类恰好走了引擎首选」的手上仍有 p95=1.34 目的抖动，
  1.5 目这样的档位会落在噪声里。
* 「妙手」不建在目数轴上，而建在**难度**轴上：走出引擎首选，且该首选的
  policy 先验很低。目数轴是单边的（落子前的评估已假定最优应手），
  在它上面永远造不出与失误对等的好手档。

本模块不 import 引擎、不 import kivy，可以安全地被 katrain/cron 使用
（注意 Dockerfile.cron 必须显式 COPY 本文件与 yaml）。
"""

from __future__ import annotations

import functools
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "move_grade.yaml")

# 未评级（visits 不够、缺少上一手分析、停一手等）。不进任何列表与直方图。
UNRATED = "unrated"


@functools.lru_cache(maxsize=1)
def load_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    _validate(cfg)
    return cfg


def _validate(cfg: Dict[str, Any]) -> None:
    tier_ids = [t["id"] for t in cfg["tiers"]]
    expected = ["brilliant", "best", "very_good", "playable", "inaccuracy", "mistake", "blunder"]
    if tier_ids != expected:
        raise ValueError(f"move_grade.yaml tiers must be exactly {expected} in order, got {tier_ids}")
    ladder = cfg["ladder_points"]
    values = [ladder["very_good"], ladder["playable"], ladder["inaccuracy"], ladder["mistake"]]
    if values != sorted(values):
        # 这个仓在 katrain/config.json 上正好栽过一次方向反了的跟头，所以这里显式挡住。
        raise ValueError(f"ladder_points must be ascending, got {values}")
    levels = cfg["brilliant"]["levels_prior"]
    if levels != sorted(levels, reverse=True):
        raise ValueError(f"brilliant.levels_prior must be descending, got {levels}")


def tiers() -> List[Dict[str, Any]]:
    return load_config()["tiers"]


def tier_ids() -> List[str]:
    return [t["id"] for t in tiers()]


def phase_of(move_number: int, cfg: Optional[Dict[str, Any]] = None) -> str:
    """手数 → 布局/中盘/官子。move_number 是这手棋的序号（1 起）。"""
    cfg = cfg or load_config()
    for name, (lo, hi) in cfg["display"]["phases"].items():
        if move_number >= lo and (hi is None or move_number <= hi):
            return name
    return "endgame"


def _player_sign(player: str) -> int:
    return 1 if player == "B" else -1


def points_lost_in_search(
    prev_top_moves: Sequence[Dict[str, Any]],
    actual_move: str,
    actual_player: str,
    actual_score_lead_fallback: Optional[float],
) -> Tuple[Optional[float], str]:
    """同一次搜索内的目数损失（对落子方而言，>=0 表示亏）。

    所有 scoreLead 都是黑方视角（``reportAnalysisWinratesAs: BLACK``）。

    返回 ``(points_lost, source)``，source 取值：
      ``in_search``  实战手也在候选里，两个数完全同源，最干净；
      ``two_search`` 实战手不在候选里，只能用下一行的根评估，混了两次搜索；
      ``none``       算不出来。
    """
    if not prev_top_moves:
        return None, "none"
    sign = _player_sign(actual_player)
    leads = [m.get("score_lead") for m in prev_top_moves if m.get("score_lead") is not None]
    if not leads:
        return None, "none"
    # 对落子方最好的那个候选。注意不能直接取 top_moves[0]：order 是按
    # playSelectionValue 排的，实测有 17.7%~34.4% 的局面里 order-0 不是 scoreLead 最优的。
    best = max(leads) if sign > 0 else min(leads)

    for m in prev_top_moves:
        if m.get("move") == actual_move and m.get("score_lead") is not None:
            return max(0.0, sign * (best - m["score_lead"])), "in_search"

    if actual_score_lead_fallback is None:
        return None, "none"
    return max(0.0, sign * (best - actual_score_lead_fallback)), "two_search"


def brilliance_level(prior: float, cfg: Optional[Dict[str, Any]] = None) -> int:
    """policy 先验 → 玄妙指数 1..5（越低越玄妙）。

    levels_prior 是降序断点 [0.05, 0.03, 0.02, 0.01, 0.0]，
    级数 = 1 + 越过的断点数：>=0.05 → 1，<0.05 → 2，<0.03 → 3，<0.02 → 4，<0.01 → 5。
    """
    cfg = cfg or load_config()
    bounds = cfg["brilliant"]["levels_prior"]
    crossed = sum(1 for b in bounds if prior < b)
    return min(1 + crossed, len(bounds))


def grade_move(
    *,
    prev_top_moves: Optional[Sequence[Dict[str, Any]]],
    prev_visits: Optional[int],
    actual_move: Optional[str],
    actual_player: Optional[str],
    actual_score_lead: Optional[float],
    actual_winrate: Optional[float],
    move_number: int,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """给一手棋评级。

    入参全部取自 ``report_task_moves``：``prev_*`` 来自第 N-1 行（落子前的局面），
    ``actual_*`` 来自第 N 行（落子后的局面）。
    """
    cfg = cfg or load_config()
    out: Dict[str, Any] = {
        "grade": UNRATED,
        "points_lost": None,
        "points_lost_source": "none",
        "is_top_move": None,
        "top_prior": None,
        "brilliance": None,
        "phase": phase_of(move_number, cfg),
    }
    if not actual_move or not actual_player or not prev_top_moves:
        return out
    if prev_visits is not None and prev_visits < cfg["metric"]["min_visits"]:
        return out

    top = prev_top_moves[0]
    out["is_top_move"] = top.get("move") == actual_move
    out["top_prior"] = top.get("prior")

    pl, source = points_lost_in_search(prev_top_moves, actual_move, actual_player, actual_score_lead)
    out["points_lost"], out["points_lost_source"] = pl, source
    if pl is None:
        return out

    if out["is_top_move"]:
        out["grade"] = "best"
        b = _brilliant(out, actual_score_lead, actual_winrate, prev_visits, cfg)
        if b is not None:
            out["grade"] = "brilliant"
            out["brilliance"] = b
        return out

    ladder = cfg["ladder_points"]
    if pl < ladder["very_good"]:
        out["grade"] = "very_good"
    elif pl < ladder["playable"]:
        out["grade"] = "playable"
    elif pl < ladder["inaccuracy"]:
        out["grade"] = "inaccuracy"
    elif pl < ladder["mistake"]:
        out["grade"] = "mistake"
    else:
        out["grade"] = "blunder"
    return out


def _brilliant(
    out: Dict[str, Any],
    score_lead: Optional[float],
    winrate: Optional[float],
    prev_visits: Optional[int],
    cfg: Dict[str, Any],
) -> Optional[int]:
    """走了首选的前提下，判断够不够妙手；够则返回玄妙指数 1..5。"""
    bc = cfg["brilliant"]
    if bc["require_top_move"] and not out["is_top_move"]:
        return None
    prior = out["top_prior"]
    if prior is None:
        return None
    # 首选本身在重复搜索间会翻，visits 太低时不判妙手。
    if prev_visits is not None and prev_visits < bc["min_visits"]:
        return None

    # 局面已经完全决定时不给妙手（借自 Chess.com Brilliant 的成文条件）。
    und = bc["require_undecided"]
    if score_lead is not None and abs(score_lead) > und["max_abs_score_lead"]:
        return None
    if winrate is not None and not (und["winrate_band"][0] <= winrate <= und["winrate_band"][1]):
        return None

    # 官子段 policy 天然更平，按阶段缩放阈值，否则会在官子超额触发。
    scale = bc["phase_prior_scale"].get(out["phase"], 1.0)
    if prior >= bc["max_prior"] * scale:
        return None
    return brilliance_level(prior, cfg)


# ---------------------------------------------------------------------------
# 生成前端常量
# ---------------------------------------------------------------------------

TS_HEADER = """// AUTO-GENERATED from katrain/core/move_grade.yaml -- DO NOT EDIT BY HAND.
// Regenerate:  python -m katrain.core.move_grade --emit-ts
// A test (tests/test_move_grade.py::test_generated_ts_is_in_sync) fails if this
// file drifts from the yaml.
"""


def emit_ts() -> str:
    cfg = load_config()
    rows = []
    for t in cfg["tiers"]:
        rows.append(
            "  { id: %s, i18nKey: %s, zh: %s, color: %s, bad: %s },"
            % (json.dumps(t["id"]), json.dumps(t["i18n"]), json.dumps(t["zh"], ensure_ascii=False),
               json.dumps(t["color"]), "true" if t["bad"] else "false")
        )
    phases = cfg["display"]["phases"]
    phase_rows = [
        "  { id: %s, from: %d, to: %s }," % (json.dumps(k), v[0], "null" if v[1] is None else v[1])
        for k, v in phases.items()
    ]
    return (
        TS_HEADER
        + "\nexport type GradeId =\n"
        + "".join("  | %s\n" % json.dumps(t["id"]) for t in cfg["tiers"])
        + "  | \"unrated\";\n\n"
        + "export interface GradeTier {\n"
        + "  id: GradeId;\n  i18nKey: string;\n  zh: string;\n  color: string;\n  bad: boolean;\n}\n\n"
        + "export const GRADE_TIERS: readonly GradeTier[] = [\n"
        + "\n".join(rows)
        + "\n] as const;\n\n"
        + "export const GRADE_BY_ID: Readonly<Record<string, GradeTier>> = Object.fromEntries(\n"
        + "  GRADE_TIERS.map((t) => [t.id, t]),\n);\n\n"
        + "export const BAD_GRADES: readonly GradeId[] = GRADE_TIERS.filter((t) => t.bad).map((t) => t.id);\n\n"
        + "export const GRADE_LADDER_POINTS = {\n"
        + "".join("  %s: %s,\n" % (k, cfg["ladder_points"][k])
                 for k in ("very_good", "playable", "inaccuracy", "mistake"))
        + "} as const;\n\n"
        + "export const PER_SIDE_LIMIT = %d;\n\n" % cfg["display"]["per_side_limit"]
        + "export const SHOW_TRUNCATED_TOTAL = %s;\n\n" % ("true" if cfg["display"]["show_truncated_total"] else "false")
        + "export interface GradePhase {\n  id: string;\n  from: number;\n  to: number | null;\n}\n\n"
        + "export const GRADE_PHASES: readonly GradePhase[] = [\n"
        + "\n".join(phase_rows)
        + "\n] as const;\n"
    )


TS_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "web", "ui", "src", "features", "analysis", "gradeTiers.generated.ts",
    )
)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="move grade config tool")
    ap.add_argument("--emit-ts", action="store_true", help="write the generated TS constants file")
    args = ap.parse_args()
    if args.emit_ts:
        os.makedirs(os.path.dirname(TS_PATH), exist_ok=True)
        with open(TS_PATH, "w", encoding="utf-8") as f:
            f.write(emit_ts())
        print("wrote", TS_PATH)
    else:
        print(json.dumps(load_config(), ensure_ascii=False, indent=2))
