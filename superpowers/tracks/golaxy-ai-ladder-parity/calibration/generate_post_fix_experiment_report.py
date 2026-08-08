#!/usr/bin/env python3
"""Generate the self-contained post-fix Golaxy and self-play evidence report."""

from __future__ import annotations

import argparse
import html
from pathlib import Path


TRACK = "superpowers/tracks/golaxy-ai-ladder-parity"
DEFAULT_OUTPUT = Path(TRACK) / "reports" / "post-fix-experiment-report.html"


def _experiment(
    *,
    family: str,
    player_a: str,
    player_b: str,
    wins: int,
    losses: int,
    source: str,
    planned: int | None = None,
    inconclusive: int = 0,
    complete_pairs: int | None = None,
    inconclusive_pairs: int = 0,
    completion: str = "completed",
    evidence: str = "formal",
    notes: str = "",
    level: str = "",
    level_order: int = 0,
    candidate: str = "",
) -> dict:
    eligible = wins + losses
    target = planned if planned is not None else eligible
    return {
        "family": family,
        "player_a": player_a,
        "player_b": player_b,
        "wins": wins,
        "losses": losses,
        "planned_games": target,
        "eligible_games": eligible,
        "missing_games": max(0, target - eligible),
        "inconclusive_games": inconclusive,
        "complete_pairs": complete_pairs,
        "inconclusive_pairs": inconclusive_pairs,
        "completion_status": completion,
        "evidence_class": evidence,
        "notes": notes,
        "source": source,
        "level": level,
        "level_order": level_order,
        "candidate": candidate,
    }


def _golaxy_rows() -> list[dict]:
    g = []
    add = lambda **kw: g.append(_experiment(**kw))
    alignment = f"{TRACK}/calibration/results/golaxy_alignment_campaign_20260730/campaign_v2.jsonl"
    sampling = f"{TRACK}/calibration/results/golaxy_sampling_campaign_20260730/campaign_v1.jsonl"
    rank_sampling = f"{TRACK}/calibration/results/golaxy_rank1_6_sampling_final_continuation_20260802/campaign_v4.jsonl"

    # Same-rank native HumanSL sampling evidence, including two frozen carry matchups.
    native = [
        ("星阵准1段", 1, "rank_1d@1", 10, 0, rank_sampling, "过强"),
        ("星阵1段", 2, "rank_1d@1", 10, 0, rank_sampling, "过强"),
        ("星阵准2段", 3, "rank_2d@1", 9, 1, rank_sampling, "过强"),
        ("星阵2段", 4, "rank_2d@1", 10, 0, rank_sampling, "过强"),
        ("星阵准3段", 5, "rank_3d@1", 9, 1, rank_sampling, "过强"),
        ("星阵3段", 6, "rank_3d@1", 9, 1, rank_sampling, "过强"),
        ("星阵准4段", 7, "rank_4d@1", 9, 1, rank_sampling, "过强"),
        ("星阵4段", 8, "rank_4d@1", 8, 2, rank_sampling, "偏强"),
        ("星阵准5段", 9, "rank_5d@1", 9, 1, sampling, "过强"),
        ("星阵5段", 10, "rank_5d@1", 8, 2, rank_sampling, "偏强"),
        ("星阵准6段", 11, "rank_6d@1", 9, 1, sampling, "过强"),
        ("星阵6段", 12, "rank_6d@1", 6, 3, rank_sampling, "未满10盘"),
    ]
    for level, order, player, wins, losses, source, candidate in native:
        partial = level == "星阵6段"
        add(
            family="HumanSL 原生加权采样",
            player_a=player,
            player_b=level,
            wins=wins,
            losses=losses,
            planned=10,
            completion="partial" if partial else "completed",
            source=source,
            level=level,
            level_order=order,
            candidate=candidate,
            notes="扩充链最后一盘因星阵 7002 停止。" if partial else "同 rank 原生 policy 正权重抽样。",
        )

    # Quasi-dan and 5D–9D HumanSL alignment paths.
    alignment_rows = [
        ("星阵准5段", 9, "rank_4d@8", 3, 1, "screening", "强侧筛选"),
        ("星阵准5段", 9, "rank_4d@1s", 9, 1, "formal", "网格下界仍过强"),
        ("星阵准6段", 11, "rank_5d@8", 4, 0, "screening", "强侧筛选"),
        ("星阵准6段", 11, "rank_5d@1s", 10, 0, "formal", "网格下界仍过强"),
        ("星阵准7段", 13, "rank_6d@8", 4, 0, "screening", "强侧筛选"),
        ("星阵准7段", 13, "rank_6d@1s", 9, 1, "formal", "网格下界仍过强"),
        ("星阵准8段", 15, "rank_7d@8", 4, 0, "screening", "强侧筛选"),
        ("星阵准8段", 15, "rank_7d@4", 10, 0, "formal", "过强"),
        ("星阵准8段", 15, "rank_7d@1s", 7, 3, "formal", "当前最接近"),
        ("星阵准9段", 17, "rank_8d@8", 4, 0, "screening", "强侧筛选"),
        ("星阵准9段", 17, "rank_8d@4", 9, 1, "formal", "过强"),
        ("星阵准9段", 17, "rank_8d@1s", 6, 4, "formal", "当前最接近"),
        ("星阵5段", 10, "rank_5d@1s", 10, 0, "formal", "明显过强"),
        ("星阵6段", 12, "rank_6d@1s", 9, 1, "formal", "明显过强"),
        ("星阵7段", 14, "rank_7d@1s", 5, 5, "formal", "实测对齐"),
        ("星阵7段", 14, "rank_7d@4", 10, 0, "formal", "过强"),
        ("星阵8段", 16, "rank_8d@1s", 6, 4, "formal", "实测对齐"),
        ("星阵8段", 16, "rank_8d@4", 5, 0, "screening", "方向性过强"),
        ("星阵9段", 18, "rank_9d@4", 5, 5, "formal", "实测对齐"),
        ("星阵9段", 18, "rank_9d@5", 5, 0, "screening", "小样本偏强"),
        ("星阵9段", 18, "rank_9d@6", 4, 1, "screening", "小样本偏强"),
        ("星阵9段", 18, "rank_9d@8", 10, 0, "formal", "安全档但明显过强"),
    ]
    for level, order, player, wins, losses, evidence, candidate in alignment_rows:
        add(
            family="HumanSL 星阵对标",
            player_a=player,
            player_b=level,
            wins=wins,
            losses=losses,
            source=alignment,
            evidence=evidence,
            level=level,
            level_order=order,
            candidate=candidate,
            notes="PIKL 搜索" if "@1s" not in player else "humanPolicy argmax",
        )

    stars = f"{TRACK}/calibration/results/golaxy_b18_binary_stars_20260726/binary_search_v5.jsonl"
    three_star = f"{TRACK}/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v6.jsonl"
    pure_b18 = [
        ("星阵1星（职业水平）", 19, "b18@1", 6, 4, 10, "completed", alignment, "实测对齐"),
        ("星阵1星（职业水平）", 19, "b18@2", 7, 3, 10, "completed", stars, "最低强侧"),
        ("星阵1星（职业水平）", 19, "b18@4", 3, 1, 4, "completed", stars, "强侧筛选"),
        ("星阵1星（职业水平）", 19, "b18@8", 3, 1, 4, "completed", stars, "强侧筛选"),
        ("星阵2星（职业顶尖）", 20, "b18@8", 1, 3, 4, "completed", stars, "弱侧筛选"),
        ("星阵2星（职业顶尖）", 20, "b18@16", 8, 2, 10, "completed", stars, "最低强侧"),
        ("星阵3星（超越人类）", 21, "b18@8", 0, 4, 4, "completed", stars, "弱侧筛选"),
        ("星阵3星（超越人类）", 21, "b18@16", 2, 2, 4, "completed", stars, "弱侧筛选"),
        ("星阵3星（超越人类）", 21, "b18@32", 7, 7, 20, "stopped", three_star, "尚无结论"),
        ("星阵3星（超越人类）", 21, "b18@64", 7, 3, 20, "stopped", three_star, "方向偏强但未补满"),
    ]
    for level, order, player, wins, losses, planned, completion, source, candidate in pure_b18:
        add(
            family="纯 b18 星级对标",
            player_a=player,
            player_b=level,
            wins=wins,
            losses=losses,
            planned=planned,
            completion=completion,
            evidence="formal" if planned == wins + losses else "descriptive",
            source=source,
            level=level,
            level_order=order,
            candidate=candidate,
            notes="扩充在 7002 illegal query 后零重试停止。" if completion == "stopped" else "纯 b18 搜索，无 HumanSL/PIKL。",
        )

    human3 = f"{TRACK}/calibration/results/golaxy_3star_rank_9d_conditional_20260725/fixed_screen.jsonl"
    for visits in (8, 16, 32, 64):
        add(
            family="HumanSL 对最高星级筛选",
            player_a=f"rank_9d@{visits}",
            player_b="星阵3星（超越人类）",
            wins=0,
            losses=5,
            source=human3,
            evidence="screening",
            level="星阵3星（超越人类）",
            level_order=21,
            candidate="明显过弱",
            notes="b18 + humanv0 + canonical PIKL。",
        )
    return sorted(g, key=lambda row: (row["level_order"], row["player_a"]))


def _selfplay_rows() -> list[dict]:
    s = []
    add = lambda **kw: s.append(_experiment(**kw))
    base = f"{TRACK}/calibration/results"

    same_scores = [(1, 2, 18, 1), (2, 5, 15, 1), (3, 3, 17, 2), (4, 0, 20, 2), (5, 2, 18, 0), (6, 2, 18, 0), (7, 0, 20, 0), (8, 1, 19, 0), (9, 0, 20, 0)]
    for rank, wins, losses, ipairs in same_scores:
        add(
            family="同等级 sampling vs argmax",
            player_a=f"rank_{rank}d@1",
            player_b=f"rank_{rank}d@1s",
            wins=wins,
            losses=losses,
            complete_pairs=10,
            inconclusive_pairs=ipairs,
            source=f"{base}/selfplay_v2_same_rank_sampling_vs_argmax_20260729/selfplay_summary.json",
            notes="同一 humanPolicy；A 正权重抽样，B 取 argmax。",
        )

    adjacent_scores = [(1, 7, 13), (2, 7, 13), (3, 4, 16), (4, 9, 11), (5, 6, 14), (6, 9, 11), (7, 6, 14), (8, 7, 13)]
    for low, wins, losses in adjacent_scores:
        source_dir = "selfplay_v2_policy_argmax_gap_low_ranks_20260802" if low <= 4 else "selfplay_v2_policy_argmax_gap_recovery/exploratory_adjacent_rank_1s"
        add(
            family="相邻段位 argmax",
            player_a=f"rank_{low}d@1s",
            player_b=f"rank_{low + 1}d@1s",
            wins=wins,
            losses=losses,
            complete_pairs=10,
            evidence="exploratory",
            source=f"{base}/{source_dir}/" + ("selfplay_summary.json" if low <= 4 else "summary.json"),
            notes="点估计八组均指向高一段；仅作排序方向证据。",
        )

    avs_scores = [(1, 16, 4, 2), (2, 14, 6, 1), (3, 18, 2, 0), (4, 18, 2, 0), (5, 14, 6, 0), (6, 17, 3, 2), (7, 17, 3, 1), (8, 16, 4, 0)]
    for low, wins, losses, ipairs in avs_scores:
        add(
            family="低一段 argmax vs 高一段 sampling",
            player_a=f"rank_{low}d@1s",
            player_b=f"rank_{low + 1}d@1",
            wins=wins,
            losses=losses,
            complete_pairs=10,
            inconclusive_pairs=ipairs,
            source=f"{base}/selfplay_v2_adjacent_argmax_vs_sampling_20260729/selfplay_summary.json",
            notes="选点规则差异大于一个 profile 段位差。",
        )

    # PIKL 80-vs-40 fixed confirmation and screens.
    pikl = f"{base}/selfplay_v2_pikl"
    for rank, wins, losses, ipairs in [(5, 22, 18, 7), (7, 21, 19, 4), (9, 21, 19, 4)]:
        add(
            family="PIKL @80 vs @40 confirmation",
            player_a=f"rank_{rank}d@80",
            player_b=f"rank_{rank}d@40",
            wins=wins,
            losses=losses,
            complete_pairs=20,
            inconclusive_pairs=ipairs,
            source=f"{pikl}/selfplay_summary_confirm_exp12.json",
            notes="固定确认样本；方向一致但 Wilson 95% 区间均跨 50%。",
        )
    for rank, wins, losses, ipairs in [(5, 14, 6, 2), (7, 13, 7, 2), (9, 11, 9, 6)]:
        add(
            family="PIKL @80 vs @40 screening",
            player_a=f"rank_{rank}d@80",
            player_b=f"rank_{rank}d@40",
            wins=wins,
            losses=losses,
            complete_pairs=10,
            inconclusive_pairs=ipairs,
            evidence="screening",
            source=f"{pikl}/selfplay_summary_screen_batch1.json",
            notes="仅用于选择确认候选。",
        )

    # PIKL versus b28 search grid.
    for visits, wins, losses in [(40, 2, 18), (80, 4, 16), (160, 5, 15), (320, 11, 9)]:
        add(
            family="PIKL vs b28@20 screening",
            player_a=f"rank_9d@{visits}",
            player_b="b28@20",
            wins=wins,
            losses=losses,
            complete_pairs=10,
            evidence="screening",
            source=f"{pikl}/selfplay_summary_screen_batch" + ("1.json" if visits == 40 else f"{ {80: '2_exp4_80', 160: '3_exp4_160', 320: '4_exp4_320'}[visits]}.json"),
            notes="@320 只是 confirmation 候选；40-pair confirmation 尚未运行。",
        )

    # Adjacent-rank PIKL boundary: @40 evidence, formal @20, descriptive @10/@5/@2.
    for low, wins, losses, ipairs in [(5, 19, 1, 0), (6, 19, 1, 2), (7, 17, 3, 3), (8, 16, 4, 7)]:
        add(
            family="相邻段位 PIKL@40 筛选",
            player_a=f"rank_{low}d@40",
            player_b=f"rank_{low + 1}d@1s",
            wins=wins,
            losses=losses,
            complete_pairs=10,
            inconclusive_pairs=ipairs,
            evidence="screening",
            source=f"{pikl}/selfplay_summary_screen_exp3_40.json",
            notes="只用于冻结后续 confirmation 候选，不并入确认样本。",
        )
    for low, wins, losses, completion in [(5, 36, 4, "completed"), (6, 36, 4, "completed"), (7, 19, 3, "stopped")]:
        add(
            family="低一段 PIKL@40 vs 高一段 argmax",
            player_a=f"rank_{low}d@40",
            player_b=f"rank_{low + 1}d@1s",
            wins=wins,
            losses=losses,
            planned=40,
            complete_pairs=20 if completion == "completed" else 11,
            completion=completion,
            evidence="formal" if completion == "completed" else "descriptive",
            source=f"{pikl}/artifacts/confirm_exp3_40_halted/halted_confirmations_manifest.json",
            notes="第三组为中断样本，不作为固定确认结论。" if completion == "stopped" else "固定 confirmation 完成。",
        )

    formal20 = [(5, 17, 3, 0), (6, 14, 6, 1), (7, 15, 5, 3), (8, 16, 4, 2)]
    for low, wins, losses, ipairs in formal20:
        add(
            family="相邻段位 PIKL@20 正式筛选",
            player_a=f"rank_{low}d@20",
            player_b=f"rank_{low + 1}d@1s",
            wins=wins,
            losses=losses,
            complete_pairs=10,
            inconclusive_pairs=ipairs,
            source=f"{base}/selfplay_v2_pikl_boundary_recovery/formal_screen_20/manifest.json",
            notes="exp3-boundary-v1 正式、预声明样本。",
        )
    descriptive = {
        5: [(2, 15, 5, 1), (5, 18, 2, 0), (10, 20, 0, 0)],
        6: [(2, 13, 7, 0), (5, 20, 0, 0), (10, 20, 0, 3)],
        7: [(2, 12, 8, 0), (5, 16, 4, 0), (10, 19, 1, 0)],
        8: [(2, 12, 8, 0), (5, 15, 5, 0), (10, 14, 6, 0)],
    }
    for low, points in descriptive.items():
        for visits, wins, losses, ipairs in points:
            add(
                family="相邻段位 PIKL 回溯筛选",
                player_a=f"rank_{low}d@{visits}",
                player_b=f"rank_{low + 1}d@1s",
                wins=wins,
                losses=losses,
                complete_pairs=10,
                inconclusive_pairs=ipairs,
                evidence="descriptive",
                source=f"{base}/selfplay_v2_pikl_boundary_recovery/retrospective_manual_continuation/manifest.json",
                notes="缺少预声明历史门禁，只能描述，不支持正式边界 ≤2。",
            )
    return s


def build_report_data() -> dict:
    inventory_paths = [
        f"{TRACK}/EXPERIMENTS.md",
        f"{TRACK}/calibration/results/golaxy_alignment_campaign_20260730/campaign_v2.jsonl",
        f"{TRACK}/calibration/results/golaxy_sampling_campaign_20260730/campaign_v1.jsonl",
        f"{TRACK}/calibration/results/golaxy_rank1_6_sampling_campaign_20260802/campaign_v1.jsonl",
        f"{TRACK}/calibration/results/golaxy_rank1_6_sampling_extension_20260802/campaign_v2.jsonl",
        f"{TRACK}/calibration/results/golaxy_rank1_6_sampling_continuation_20260802/campaign_v3.jsonl",
        f"{TRACK}/calibration/results/golaxy_rank1_6_sampling_final_continuation_20260802/campaign_v4.jsonl",
        f"{TRACK}/calibration/results/golaxy_b18_binary_stars_20260726/binary_search_v5.jsonl",
        f"{TRACK}/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v6.jsonl",
        f"{TRACK}/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v7.jsonl",
        f"{TRACK}/calibration/results/golaxy_3star_rank_9d_conditional_20260725/fixed_screen.jsonl",
        f"{TRACK}/calibration/results/selfplay_v2_same_rank_sampling_vs_argmax_20260729/selfplay_summary.json",
        f"{TRACK}/calibration/results/selfplay_v2_adjacent_argmax_vs_sampling_20260729/selfplay_summary.json",
        f"{TRACK}/calibration/results/selfplay_v2_policy_argmax_gap_low_ranks_20260802/selfplay_summary.json",
        f"{TRACK}/calibration/results/selfplay_v2_policy_argmax_gap_recovery/exploratory_adjacent_rank_1s/manifest.json",
        f"{TRACK}/calibration/results/selfplay_v2_pikl_boundary_recovery/formal_screen_20/manifest.json",
        f"{TRACK}/calibration/results/selfplay_v2_pikl_boundary_recovery/retrospective_manual_continuation/manifest.json",
    ]
    audit = [
        {"kind": "修复前排除", "path": f"{TRACK}/calibration/results/selfplay", "reason": "早于 e45531b3；旧 humansl_search 实际路由到 b28。"},
        {"kind": "非对局", "path": f"{TRACK}/calibration/results/semantic_probe", "reason": "用于证明 PIKL 语义与模型路由，不是胜负对局。"},
        {"kind": "superseded", "path": f"{TRACK}/calibration/results/golaxy_b18_binary_stars_20260725/binary_search_v2.jsonl", "reason": "错误起点的早期二分，由 v3/v4/v5 明确取代。"},
        {"kind": "续跑停止", "path": f"{TRACK}/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v7.jsonl", "reason": "7002 后停止，未新增有效盘；保留停止点。"},
        {"kind": "部分完成", "path": f"{TRACK}/calibration/results/golaxy_rank1_6_sampling_final_continuation_20260802/campaign_v4.jsonl", "reason": "扩充 59/60；累计 99/100，最后一盘未完成。"},
        {"kind": "描述性证据", "path": f"{TRACK}/calibration/results/selfplay_v2_pikl_boundary_recovery/retrospective_manual_continuation/manifest.json", "reason": "缺少历史选择门禁，不升级为正式边界结论。"},
    ]
    return {
        "data_as_of": "2026-08-02 18:00 +08:00",
        "baseline": "KaTrain e45531b3；KataGo wrapper e1b68dd0 + d11d80ea",
        "models": {
            "b28": "798da8fe…d3f0",
            "b18": "9d7a6afe…1f1d",
            "humanv0": "637746e4…ab5",
        },
        "golaxy": _golaxy_rows(),
        "selfplay": _selfplay_rows(),
        "source_inventory": [{"path": path, "disposition": "included"} for path in inventory_paths],
        "audit": audit,
    }


def _status_label(value: str) -> str:
    return {"completed": "完成", "partial": "部分完成", "stopped": "已停止"}.get(value, value)


def _evidence_label(value: str) -> str:
    return {"formal": "正式", "screening": "筛选", "descriptive": "描述性", "exploratory": "探索性"}.get(value, value)


def _table(rows: list[dict], *, kind: str, caption: str) -> str:
    body = []
    for row in rows:
        progress = f'{row["eligible_games"]} / {row["planned_games"]}'
        pairs = "—" if row["complete_pairs"] is None else str(row["complete_pairs"])
        level = row["level"] or "内部"
        body.append(
            "<tr class='data-row' "
            f"data-kind='{html.escape(kind)}' data-evidence='{html.escape(row['evidence_class'])}' "
            f"data-status='{html.escape(row['completion_status'])}'>"
            f"<td class='level'>{html.escape(level)}</td>"
            f"<td><code>{html.escape(row['player_a'])}</code></td>"
            f"<td><code>{html.escape(row['player_b'])}</code></td>"
            f"<td class='score'>{row['wins']}–{row['losses']}</td>"
            f"<td>{progress}</td><td>{pairs}</td><td>{row['inconclusive_pairs'] or row['inconclusive_games']}</td>"
            f"<td><span class='badge evidence-{html.escape(row['evidence_class'])}'>{_evidence_label(row['evidence_class'])}</span></td>"
            f"<td><span class='badge status-{html.escape(row['completion_status'])}'>{_status_label(row['completion_status'])}</span></td>"
            f"<td>{html.escape(row['candidate'] or row['notes'])}</td>"
            f"<td class='source'><code>{html.escape(row['source'])}</code></td></tr>"
        )
    return f"""
    <div class="table-wrap">
      <table>
        <caption>{html.escape(caption)}</caption>
        <thead><tr><th>等级/类别</th><th>A 方</th><th>B 方</th><th>A 方比分</th><th>有效/目标</th><th>完整颜色对</th><th>未定对/盘</th><th>证据</th><th>状态</th><th>结论边界</th><th>来源</th></tr></thead>
        <tbody>{''.join(body)}</tbody>
      </table>
    </div>"""


def render_report(data: dict) -> str:
    golaxy = data["golaxy"]
    selfplay = data["selfplay"]
    complete = sum(row["eligible_games"] for row in golaxy + selfplay)
    partial = sum(row["completion_status"] != "completed" for row in golaxy + selfplay)
    families = sorted({row["family"] for row in golaxy + selfplay})

    same = [r for r in selfplay if r["family"] == "同等级 sampling vs argmax"]
    adjacent = [r for r in selfplay if r["family"] == "相邻段位 argmax"]
    arg_sampling = [r for r in selfplay if r["family"] == "低一段 argmax vs 高一段 sampling"]
    pikl = [r for r in selfplay if r not in same + adjacent + arg_sampling]

    candidates = [
        ("星阵准1段–准4段", "同 rank HumanSL@1", "目前均 9–1 或 10–0，明显过强；低档仍需产品 HumanSL 级位补齐"),
        ("星阵5段", "rank_5d@1（8–2）", "方向偏强"),
        ("星阵6段", "rank_6d@1（6–3）", "最接近，但少1盘"),
        ("星阵7段", "rank_7d@1s（5–5）", "直接五五开证据"),
        ("星阵8段", "rank_8d@1s（6–4）", "当前最接近"),
        ("星阵9段", "rank_9d@4（5–5）", "直接五五开证据"),
        ("星阵1星（职业水平）", "b18@1（6–4）", "当前产品对齐"),
        ("星阵2星（职业顶尖）", "b18@16（8–2）", "最低强侧，仍偏强"),
        ("星阵3星（超越人类）", "尚未闭环", "b18@32 为7–7/14；b18@64 为7–3/10，均未满20盘"),
    ]
    candidate_rows = "".join(f"<tr><td>{html.escape(a)}</td><td><code>{html.escape(b)}</code></td><td>{html.escape(c)}</td></tr>" for a, b, c in candidates)
    audit_rows = "".join(
        f"<tr><td>{html.escape(item['kind'])}</td><td><code>{html.escape(item['path'])}</code></td><td>{html.escape(item['reason'])}</td></tr>"
        for item in data["audit"]
    )
    source_rows = "".join(
        f"<tr><td>{index}</td><td><code>{html.escape(item['path'])}</code></td><td>{html.escape(item['disposition'])}</td></tr>"
        for index, item in enumerate(data["source_inventory"], 1)
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>修复后星阵与内部对局实验报告</title>
<style>
:root{{--paper:#f4f0e7;--surface:#fffdf8;--ink:#202b2b;--muted:#66716e;--line:#d7d1c5;--accent:#245f5a;--accent-soft:#dce9e5;--warn:#a85c22;--warn-soft:#f7e5d5;--shadow:0 18px 50px rgba(43,52,48,.09)}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.58 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif}}
a{{color:var(--accent)}} code{{font:500 .88em/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}} .shell{{max-width:1540px;margin:auto;padding:28px}}
.hero{{background:linear-gradient(125deg,#163d3a,#2a625c 62%,#9b632f);color:white;border-radius:24px;padding:42px;box-shadow:var(--shadow)}}
.eyebrow{{letter-spacing:.12em;text-transform:uppercase;font-size:.78rem;opacity:.78}} h1{{font-size:clamp(2rem,4vw,4.4rem);line-height:1.03;max-width:920px;margin:.35em 0}} h2{{font-size:1.72rem;margin:0 0 12px}} h3{{margin:0 0 10px}} .lede{{max-width:940px;font-size:1.08rem;opacity:.9}}
.meta,.metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:24px}} .meta div,.metric{{padding:14px 16px;border-radius:14px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.16)}} .metric strong{{display:block;font-size:1.65rem}}
.toolbar{{position:sticky;top:0;z-index:20;margin:18px 0;background:rgba(244,240,231,.94);backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:16px;padding:12px;display:grid;grid-template-columns:2fr repeat(3,1fr);gap:10px}}
input,select{{width:100%;min-height:44px;border:1px solid #bdb8ae;border-radius:10px;background:var(--surface);padding:9px 12px;color:var(--ink);font:inherit}} input:focus,select:focus{{outline:3px solid rgba(36,95,90,.22);border-color:var(--accent)}}
.section{{background:var(--surface);border:1px solid var(--line);border-radius:20px;padding:26px;margin:18px 0;box-shadow:0 8px 28px rgba(44,51,48,.04)}} .section-head{{display:flex;justify-content:space-between;gap:18px;align-items:end;margin-bottom:16px}} .section-head p{{max-width:820px;color:var(--muted);margin:0}}
.callout{{border-left:5px solid var(--warn);background:var(--warn-soft);padding:15px 18px;border-radius:10px;margin:16px 0}} .insights{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}} .insight{{border:1px solid var(--line);border-radius:14px;padding:16px;background:#faf8f2}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:14px;margin-top:14px;max-height:72vh}} table{{border-collapse:separate;border-spacing:0;width:100%;min-width:1120px;background:white}} caption{{text-align:left;font-weight:700;padding:13px 14px;background:#ede9df}} th,td{{padding:11px 12px;text-align:left;border-bottom:1px solid #e6e1d8;vertical-align:top}} th{{position:sticky;top:0;background:#e8efec;color:#294744;z-index:2;font-size:.82rem;letter-spacing:.025em}} tbody tr:hover{{background:#faf5ea}} td.level{{font-weight:700;white-space:nowrap}} td.score{{font-size:1.08rem;font-weight:800;white-space:nowrap}} td.source{{min-width:330px;color:var(--muted)}}
.badge{{display:inline-block;white-space:nowrap;padding:3px 8px;border-radius:999px;font-size:.76rem;font-weight:700;border:1px solid currentColor}} .evidence-formal{{color:#226151;background:#e4f1eb}} .evidence-screening,.evidence-descriptive{{color:#87501e;background:#fff0de}} .evidence-exploratory{{color:#6b587c;background:#f0e9f5}} .status-completed{{color:#226151}} .status-partial,.status-stopped{{color:#9a4f1c;background:#fff0de}}
.legend{{display:flex;gap:8px;flex-wrap:wrap}} .hidden{{display:none!important}} .count{{color:var(--muted);font-variant-numeric:tabular-nums}} details{{border-top:1px solid var(--line);padding:13px 0}} summary{{cursor:pointer;font-weight:700}} footer{{padding:30px;color:var(--muted);text-align:center}}
@media(max-width:900px){{.shell{{padding:14px}}.hero{{padding:26px;border-radius:18px}}.meta,.metrics,.insights{{grid-template-columns:1fr 1fr}}.toolbar{{grid-template-columns:1fr 1fr}}.section{{padding:18px}}}}
@media(max-width:560px){{.meta,.metrics,.insights,.toolbar{{grid-template-columns:1fr}}h1{{font-size:2.2rem}}.section-head{{display:block}}}}
@media print{{body{{background:white;font-size:10pt}}.shell{{max-width:none;padding:0}}.hero{{box-shadow:none;border-radius:0;background:white;color:black;border-bottom:2px solid #333}}.toolbar{{display:none}}.section{{box-shadow:none;border:0;padding:10px 0;break-inside:auto}}.table-wrap{{max-height:none;overflow:visible;border:0}}table{{min-width:0;font-size:8pt}}th{{position:static}}tr{{break-inside:avoid}}.source{{display:none}}}}
</style>
</head>
<body>
<main class="shell">
<header class="hero" id="top">
  <div class="eyebrow">Golaxy AI Ladder · Post-fix evidence archive</div>
  <h1>修复后星阵与内部对局实验报告</h1>
  <p class="lede">只纳入 HumanSL 搜索路由与实时模型身份校验修复后的真实对局。比分均以前列 A 方为视角；正文去重展示有效证据，停机、续跑、排除与描述性边界留在审计区。</p>
  <div class="meta"><div><small>数据截止</small><br><strong>{html.escape(data['data_as_of'])}</strong></div><div><small>修复基线</small><br>{html.escape(data['baseline'])}</div><div><small>模型身份</small><br>b18 {data['models']['b18']}<br>humanv0 {data['models']['humanv0']}</div><div><small>报告形态</small><br>单文件 · 离线 · 可搜索 · 可打印</div></div>
  <div class="metrics"><div class="metric"><strong>{len(golaxy)}</strong>星阵配置记录</div><div class="metric"><strong>{len(selfplay)}</strong>内部配置记录</div><div class="metric"><strong>{complete}</strong>有效胜负盘</div><div class="metric"><strong>{partial}</strong>未闭环记录</div></div>
</header>

<nav class="toolbar" aria-label="实验筛选">
  <input id="search" type="search" placeholder="搜索等级、模型、比分、来源或备注…" aria-label="全文筛选">
  <select id="kind"><option value="">全部类别</option><option value="golaxy">星阵</option><option value="selfplay">内部</option></select>
  <select id="evidence"><option value="">全部证据等级</option><option value="formal">正式</option><option value="screening">筛选</option><option value="descriptive">描述性</option><option value="exploratory">探索性</option></select>
  <select id="status"><option value="">全部状态</option><option value="completed">完成</option><option value="partial">部分完成</option><option value="stopped">已停止</option></select>
</nav>

<section class="section" id="summary"><div class="section-head"><div><div class="eyebrow">01 · Executive summary</div><h2>执行摘要</h2></div><p>共 {len(families)} 个实验族。搜索和筛选只改变下方数据行；摘要不会随筛选重算。</p></div>
  <div class="callout"><strong>两项未闭环必须优先看到：</strong>rank_1d..rank_6d 对星阵的本轮扩充为 <strong>59 / 60</strong>，与父账本合并后为 <strong>99 / 100</strong>；星阵3星 b18 扩充实际停在 @32 7–7/14 与 @64 7–3/10，并未各满20盘。</div>
  <div class="insights"><article class="insight"><h3>Sampling 与 argmax</h3><p>同 rank 下，@1s 在180盘有效样本中165–15；加权采样造成的棋力损失显著大于 profile 标签本身。</p></article><article class="insight"><h3>相邻 rank 方向</h3><p>八组 @1s 相邻段位均由高一段取得更多胜局，但6d–7d仅9–11，仍是探索性排序证据。</p></article><article class="insight"><h3>搜索深度</h3><p>PIKL @80 对 @40 的三个固定 confirmation 都略偏向 @80，但95%区间跨50%，不能宣称已证明单调增强。</p></article></div>
  <div class="table-wrap"><table><caption>当前星阵等级候选摘要</caption><thead><tr><th>星阵等级</th><th>当前候选</th><th>证据边界</th></tr></thead><tbody>{candidate_rows}</tbody></table></div>
</section>

<section class="section" id="golaxy"><div class="section-head"><div><div class="eyebrow">02 · External calibration</div><h2>星阵对局总表</h2></div><p>等级从准1段向上排列，列出修复后尝试过的全部主要配置。最高三级使用产品名称，同时保留原始星阵级别。</p></div>{_table(golaxy, kind='golaxy', caption='星阵等级 × KataGo / HumanSL 配置')}</section>

<section class="section" id="selfplay"><div class="section-head"><div><div class="eyebrow">03 · Internal evidence</div><h2>内部对局总表</h2></div><p>内部自对弈按完整颜色对计分；任一盘不可判定时整对剔除并重新补一对。</p></div>
  {_table(same, kind='selfplay', caption='同等级 @1 加权采样 vs @1s argmax')}
  {_table(adjacent, kind='selfplay', caption='相邻等级 rank_{n-1}d@1s vs rank_nd@1s')}
  {_table(arg_sampling, kind='selfplay', caption='低一段 argmax vs 高一段加权采样')}
  {_table(pikl, kind='selfplay', caption='PIKL 搜索、访问数边界与 b28 对照')}
</section>

<section class="section" id="method"><div class="section-head"><div><div class="eyebrow">04 · Method</div><h2>方法与术语</h2></div><p>这里解释选择语义，避免把 @N 错读为 policy top-N。</p></div>
  <div class="table-wrap"><table><caption>选点与模型语义</caption><thead><tr><th>标记</th><th>真实含义</th><th>是否搜索</th></tr></thead><tbody>
  <tr><td><code>rank_nd@1</code></td><td>从 humanv0 对应 rank 的 humanPolicy 正权重抽样</td><td>否</td></tr>
  <tr><td><code>rank_nd@1s</code></td><td>同一 humanPolicy 的确定性 argmax</td><td>否</td></tr>
  <tr><td><code>rank_nd@N</code></td><td>b18 主模型 + humanv0 + canonical PIKL，取搜索首选手；不是 policy top-N</td><td>是，最多 N visits</td></tr>
  <tr><td><code>b18@N / b28@N</code></td><td>对应强化学习主模型的纯搜索访问数</td><td>是</td></tr>
  </tbody></table></div>
  <details open><summary>PIKL 是什么</summary><p>PIKL 不是另一棵独立的蒙特卡洛树。KataGo 仍执行主模型驱动的树搜索，但把 HumanSL policy 作为偏好项加入候选着法的选择效用；主模型负责价值判断，humanv0 提供“该段位人类更可能怎样下”的先验偏好，最终仍选择搜索后的首选结果。</p></details>
  <details><summary>胜负与未定盘口径</summary><p>Golaxy 按明确单盘结论计分；内部自对弈按完整的黑白互换 pair 计分。inconclusive 不进入胜负分母。screening、exploratory 和 descriptive 都保留真实比分，但不会被包装成确认性结论。</p></details>
</section>

<section class="section" id="audit"><div class="section-head"><div><div class="eyebrow">05 · Audit trail</div><h2>审计附录</h2></div><p>正文排除项、重复表示和停止点仍保留路径与理由。</p></div>
  <div class="table-wrap"><table><caption>排除、替代与停止事项</caption><thead><tr><th>类别</th><th>路径</th><th>理由</th></tr></thead><tbody>{audit_rows}</tbody></table></div>
  <div class="table-wrap"><table><caption>正文权威来源清单</caption><thead><tr><th>#</th><th>仓库相对路径</th><th>处置</th></tr></thead><tbody>{source_rows}</tbody></table></div>
</section>
<footer>KaTrain × Golaxy AI Ladder · evidence as of {html.escape(data['data_as_of'])} · <a href="#top">返回顶部</a></footer>
</main>
<script>
(() => {{
  const controls = ['search','kind','evidence','status'].map(id => document.getElementById(id));
  const rows = [...document.querySelectorAll('.data-row')];
  const apply = () => {{
    const [q, kind, evidence, status] = controls.map(el => el.value.trim().toLowerCase());
    rows.forEach(row => {{
      const visible = (!q || row.textContent.toLowerCase().includes(q)) && (!kind || row.dataset.kind === kind) && (!evidence || row.dataset.evidence === evidence) && (!status || row.dataset.status === status);
      row.classList.toggle('hidden', !visible);
    }});
  }};
  controls.forEach(el => el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', apply));
}})();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = render_report(build_report_data())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"wrote {args.out} ({len(report):,} bytes)")


if __name__ == "__main__":
    main()
