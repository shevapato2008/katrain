"""AUTO-GENERATED from katrain/core/move_grade.yaml + move_grade_core.py -- DO NOT EDIT.

    python -m katrain.core.move_grade --emit

katrain/cron 不能 import katrain.core（Dockerfile.cron 只 COPY katrain/cron/），
也没有 PyYAML，所以阈值在这里是一份**字面量**，判级逻辑是 move_grade_core.py 的
逐字节副本。要改阈值请改 katrain/core/move_grade.yaml 再重新生成 ——
tests/test_move_grade.py::test_generated_cron_module_is_in_sync 会守住不同步。
"""

CONFIG = {   'version': 1,
    'metric': {'source': 'in_search', 'fallback': 'two_search', 'min_visits': 100},
    'ladder_points': {'very_good': 0.5, 'playable': 1.5, 'inaccuracy': 3.0, 'mistake': 6.0},
    'brilliant': {   'require_top_move': True,
                     'max_prior': 0.1,
                     'require_undecided': {   'max_abs_score_lead': 20.0,
                                              'winrate_band': [0.05, 0.95]},
                     'levels_prior': [0.05, 0.03, 0.02, 0.01, 0.0],
                     'min_visits': 400,
                     'phase_prior_scale': {'opening': 1.0, 'midgame': 1.0, 'endgame': 0.6}},
    'tiers': [   {   'id': 'brilliant',
                     'i18n': 'grade:brilliant',
                     'zh': '妙手',
                     'color': '#3FA2E8',
                     'bad': False},
                 {'id': 'best', 'i18n': 'grade:best', 'zh': '最佳', 'color': '#2E8B57', 'bad': False},
                 {   'id': 'very_good',
                     'i18n': 'grade:very_good',
                     'zh': '很好',
                     'color': '#4DBE46',
                     'bad': False},
                 {   'id': 'playable',
                     'i18n': 'grade:playable',
                     'zh': '尚可',
                     'color': '#A4B436',
                     'bad': False},
                 {   'id': 'inaccuracy',
                     'i18n': 'grade:inaccuracy',
                     'zh': '小亏',
                     'color': '#D6A318',
                     'bad': True},
                 {   'id': 'mistake',
                     'i18n': 'grade:mistake',
                     'zh': '失误',
                     'color': '#CF6B09',
                     'bad': True},
                 {   'id': 'blunder',
                     'i18n': 'grade:blunder',
                     'zh': '恶手',
                     'color': '#BB2121',
                     'bad': True}],
    'display': {   'per_side_limit': 5,
                   'phases': {'opening': [0, 59], 'midgame': [60, 149], 'endgame': [150, None]},
                   'show_truncated_total': True}}


# 未评级（visits 不够、缺少上一手分析、停一手等）。不进任何列表与直方图。
UNRATED = "unrated"

TIER_ORDER = ["brilliant", "best", "very_good", "playable", "inaccuracy", "mistake", "blunder"]


def validate(cfg):
    tier_ids = [t["id"] for t in cfg["tiers"]]
    if tier_ids != TIER_ORDER:
        raise ValueError(f"tiers must be exactly {TIER_ORDER} in order, got {tier_ids}")
    ladder = cfg["ladder_points"]
    values = [ladder["very_good"], ladder["playable"], ladder["inaccuracy"], ladder["mistake"]]
    if values != sorted(values):
        # 这个仓在 katrain/config.json 上正好栽过一次方向反了的跟头，所以这里显式挡住。
        raise ValueError(f"ladder_points must be ascending, got {values}")
    levels = cfg["brilliant"]["levels_prior"]
    if levels != sorted(levels, reverse=True):
        raise ValueError(f"brilliant.levels_prior must be descending, got {levels}")


def phase_of(move_number, cfg):
    """手数 → 布局/中盘/官子。move_number 是这手棋的序号。"""
    for name, bounds in cfg["display"]["phases"].items():
        lo, hi = bounds[0], bounds[1]
        if move_number >= lo and (hi is None or move_number <= hi):
            return name
    return "endgame"


def _player_sign(player):
    return 1 if player == "B" else -1


def points_lost_in_search(prev_top_moves, actual_move, actual_player, actual_score_lead_fallback):
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


def brilliance_level(prior, cfg):
    """policy 先验 → 妙度 1..5（越低越难想到）。

    levels_prior 是降序断点 [0.05, 0.03, 0.02, 0.01, 0.0]，
    级数 = 1 + 越过的断点数：>=0.05 → 1，<0.05 → 2，<0.03 → 3，<0.02 → 4，<0.01 → 5。
    """
    bounds = cfg["brilliant"]["levels_prior"]
    crossed = sum(1 for b in bounds if prior < b)
    return min(1 + crossed, len(bounds))


def grade_move(
    prev_top_moves,
    prev_visits,
    actual_move,
    actual_player,
    actual_score_lead,
    actual_winrate,
    move_number,
    cfg,
):
    """给一手棋评级。

    入参全部取自 ``report_task_moves``：``prev_*`` 来自第 N-1 行（落子前的局面），
    ``actual_*`` 来自第 N 行（落子后的局面）。
    """
    out = {
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


def _brilliant(out, score_lead, winrate, prev_visits, cfg):
    """走了首选的前提下，判断够不够妙手；够则返回妙度 1..5。"""
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


# ── 绑定 CONFIG 的薄封装，签名与 katrain.core.move_grade 一致 ──


def grade(
    *,
    prev_top_moves,
    prev_visits,
    actual_move,
    actual_player,
    actual_score_lead,
    actual_winrate,
    move_number,
):
    return grade_move(
        prev_top_moves,
        prev_visits,
        actual_move,
        actual_player,
        actual_score_lead,
        actual_winrate,
        move_number,
        CONFIG,
    )


def ladder():
    return CONFIG["ladder_points"]
