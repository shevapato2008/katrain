"""Build an offline, read-only report from a frozen kifu inventory and catalog snapshot.

The parser produces review hints. It does not merge identities, approve Chinese
names, or change any database row.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from katrain.web.kifu.name_parse import parse_event, parse_player  # noqa: E402
from katrain.web.kifu.name_structure import RULE_VERSION, structure_event  # noqa: E402


DEFAULT_INVENTORY = Path("/tmp/kifu-five-prod-inventory-post7.json.gz")
DEFAULT_CATALOG = Path("/tmp/kifu-prod-catalog-post-cn-20261004.json")
DEFAULT_CANDIDATES = ROOT / "docs/resource/kifu-duplicate-candidates-2026-10-04.json"
DEFAULT_OUTPUT = ROOT / "docs/resource/kifu-preprocess-report-2026-10-04.html"
NON_SERIES = {"empty", "generic_event_description", "game_description", "program_source_label", "corrupt_data"}


def read_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    payload = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value, hashlib.sha256(raw).hexdigest()


def sort_text(value: str) -> bytes:
    return value.encode("utf-8")


def has_han(value: str) -> bool:
    return any("CJK UNIFIED IDEOGRAPH" in unicodedata.name(char, "") for char in value)


def fold(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def build_data(inventory: dict, catalog: dict, candidates: dict, inventory_sha: str, catalog_sha: str,
               candidate_sha: str) -> dict:
    if inventory.get("inventory_format") not in (2, 3, 4):
        raise ValueError("unsupported inventory format")
    total_games = inventory["counts"]["all"]
    player_values = inventory["scopes"]["all"]["values"]["player"]
    event_values = inventory["scopes"]["all"]["values"]["event"]
    if len(player_values) != inventory["distinct_values"]["all"]["player"]:
        raise ValueError("player distinct count does not match summary")
    if len(event_values) != inventory["distinct_values"]["all"]["event"]:
        raise ValueError("event distinct count does not match summary")
    if sum(row["occurrences"] for row in player_values) != total_games * 2:
        raise ValueError("player slot total does not match album count")
    if sum(row["occurrences"] for row in event_values) != total_games:
        raise ValueError("event slot total does not match album count")
    if len({row["value"] for row in player_values}) != len(player_values):
        raise ValueError("duplicate player raw value")
    if len({row["value"] for row in event_values}) != len(event_values):
        raise ValueError("duplicate event raw value")

    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    associations = inventory["album_associations"]
    if len(associations) != total_games:
        raise ValueError("album association total does not match inventory")
    player_fk_slots = sum(
        row[columns[key]] is not None for row in associations for key in ("black_player_id", "white_player_id")
    )
    both_player_fk_games = sum(
        row[columns["black_player_id"]] is not None and row[columns["white_player_id"]] is not None
        for row in associations
    )
    event_fk_slots = sum(row[columns["event_id"]] is not None for row in associations)

    player_groups = defaultdict(list)
    player_categories = Counter()
    player_exceptions = Counter()
    embedded_ranks = 0
    for item in player_values:
        raw = item["value"]
        if raw is None:
            raise ValueError("unexpected null player spelling; report needs a separate null entry")
        parsed = parse_player(raw, None)
        player_categories[parsed.category] += 1
        player_exceptions.update(parsed.exceptions)
        embedded_ranks += parsed.embedded_rank is not None
        player_groups[(parsed.category, parsed.name)].append(
            [raw, item["occurrences"], parsed.embedded_rank, list(parsed.exceptions)]
        )
    players = []
    for (category, base), members in player_groups.items():
        members.sort(key=lambda member: (-member[1], sort_text(member[0])))
        players.append([base, category, sum(member[1] for member in members), members])
    players.sort(key=lambda group: (-group[2], sort_text(group[0]), group[1]))

    event_groups = defaultdict(list)
    event_categories = Counter()
    event_exceptions = Counter()
    component_counts = Counter()
    grammar_counts = Counter()
    for item in event_values:
        raw = item["value"]
        parsed = parse_event(raw, None)
        structure = structure_event(raw or "")
        if "".join(part["text"] for part in structure["parts"]) != (raw or ""):
            raise ValueError(f"event parser lost original characters: {raw!r}")
        event_categories[parsed.category] += 1
        event_exceptions.update(parsed.exceptions)
        grammar_counts[structure["grammar"]] += 1
        component_counts.update({part["kind"] for part in structure["components"]})
        series_core = structure["core"] if parsed.category not in NON_SERIES else None
        kind = "core" if series_core else "exception"
        # Exceptional EV values remain individually visible; they are not all
        # merged into an artificial empty tournament group.
        key = (kind, series_core if series_core else raw)
        event_groups[key].append(
            [raw, item["occurrences"], parsed.category,
             [[part["kind"], part["text"]] for part in structure["parts"]],
             structure["grammar"], list(dict.fromkeys([*parsed.exceptions, *structure["exceptions"]]))]
        )
    events = []
    for (kind, core), members in event_groups.items():
        members.sort(key=lambda member: (-member[1], sort_text(member[0] or "")))
        events.append([core, kind, sum(member[1] for member in members), members])
    events.sort(key=lambda group: (-group[2], sort_text(group[0] or ""), group[1]))

    folded = defaultdict(list)
    for core, kind, _, _ in events:
        if kind == "core":
            folded[fold(core)].append(core)
    possible_variants = [sorted(values, key=sort_text) for values in folded.values() if len(values) > 1]
    possible_variants.sort(key=lambda values: sort_text(values[0]))

    catalog_players = sorted(
        [[row["id"], row["canonical_name"], has_han(row["canonical_name"])] for row in catalog["kifu_players"]],
        key=lambda row: row[0],
    )
    catalog_events = sorted(
        [[row["id"], row["canonical_name"], has_han(row["canonical_name"])] for row in catalog["kifu_events"]],
        key=lambda row: row[0],
    )
    if len({row[0] for row in catalog_players}) != len(catalog_players):
        raise ValueError("duplicate catalog player ID")
    if len({row[0] for row in catalog_events}) != len(catalog_events):
        raise ValueError("duplicate catalog event ID")
    candidate_counts = candidates["counts"]
    if (candidates.get("inventory_sha256") != inventory.get("sha256")
            or candidate_counts["albums"] != total_games
            or candidate_counts["raw_player_values"] != len(player_values)
            or candidate_counts["raw_event_values"] != len(event_values)
            or candidate_counts["catalog_players"] != len(catalog_players)
            or candidate_counts["catalog_events"] != len(catalog_events)):
        raise ValueError("duplicate-candidate report does not match the inventory and catalog")
    top_candidates = [
        [row["priority_rank"], row["entity"],
         row.get("candidate_chinese_name") or row.get("candidate_event_series") or row.get("candidate_name"),
         row["raw_spelling_count"], row["occurrences"], row["catalog_status"], row.get("catalog_ids", [])]
        for row in candidates["top_100_candidate_groups"]
    ]

    return {
        "meta": {
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "snapshot": inventory.get("snapshot_time", "unknown"),
            "inventory_path": str(DEFAULT_INVENTORY),
            "inventory_sha": inventory_sha,
            "inventory_internal_sha": inventory.get("sha256"),
            "catalog_path": str(DEFAULT_CATALOG),
            "catalog_sha": catalog_sha,
            "candidate_path": str(DEFAULT_CANDIDATES),
            "candidate_sha": candidate_sha,
            "parser_version": RULE_VERSION,
        },
        "stats": {
            "games": total_games,
            "player_slots": total_games * 2,
            "player_raw": len(player_values),
            "player_groups": len(players),
            "player_multi": sum(len(group[3]) > 1 for group in players),
            "player_ranked": embedded_ranks,
            "player_categories": dict(player_categories),
            "player_exceptions": dict(player_exceptions),
            "player_fk_slots": player_fk_slots,
            "both_player_fk_games": both_player_fk_games,
            "event_raw": len(event_values),
            "event_groups": sum(group[1] == "core" for group in events),
            "event_multi": sum(group[1] == "core" and len(group[3]) > 1 for group in events),
            "event_nonseries": sum(group[1] == "exception" for group in events),
            "event_categories": dict(event_categories),
            "event_exceptions": dict(event_exceptions),
            "event_components": dict(component_counts),
            "event_grammars": dict(grammar_counts),
            "event_fk_slots": event_fk_slots,
            "possible_variant_sets": len(possible_variants),
            "possible_variant_cores": sum(map(len, possible_variants)),
            "catalog_players": len(catalog_players),
            "catalog_players_han": sum(row[2] for row in catalog_players),
            "catalog_events": len(catalog_events),
            "catalog_events_han": sum(row[2] for row in catalog_events),
        },
        "players": players,
        "events": events,
        "possible_variants": possible_variants,
        "candidate_counts": {
            "players": candidate_counts["all_player_candidates"],
            "events": candidate_counts["all_event_candidates"],
        },
        "top_candidates": top_candidates,
        "catalog_players": catalog_players,
        "catalog_events": catalog_events,
    }


HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>棋谱姓名与赛事原值预处理报告 · 2026-10-04</title>
<style>
:root{--blue:#1e40af;--blue-dark:#1e3a8a;--ink:#17253b;--muted:#526176;--line:#d7e1ee;--bg:#f8fafc;--card:#fff;--amber:#92400e;--amber-bg:#fff4d6;--red:#991b1b;--red-bg:#fef2f2;--green:#166534;--green-bg:#e8f7ed}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}button,input{font:inherit}button{cursor:pointer}button:disabled{cursor:default;opacity:.5}a{color:var(--blue)}a:hover{text-decoration-thickness:2px}:focus-visible{outline:3px solid var(--blue);outline-offset:2px}.wrap{max-width:1400px;margin:auto;padding:0 22px}.eyebrow{font-size:12px;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:#bcd1ff}.top{background:linear-gradient(123deg,#102f84,#1e40af 66%,#315ac4);color:#fff;padding:29px 0 25px}.top h1{font-size:clamp(25px,3vw,39px);line-height:1.25;letter-spacing:-.025em;margin:7px 0 8px}.top p{max-width:930px;color:#e2eafe;margin:0}.topline{display:flex;align-items:center;gap:16px;justify-content:space-between;flex-wrap:wrap}.stamp{border:1px solid #a9befa;background:#ffffff1d;border-radius:100px;padding:5px 11px;font-size:12px;font-weight:700}.nav{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:3}.nav .wrap{display:flex;gap:22px;overflow:auto;white-space:nowrap}.nav a{display:block;padding:12px 0;text-decoration:none;font-weight:700;font-size:13px}.nav a:hover{box-shadow:inset 0 -3px var(--blue)}main{padding:24px 0 48px}.notice{border:1px solid #e7b755;border-left:5px solid #b45309;border-radius:11px;background:#fffaf0;padding:15px 18px;color:#713f12;margin-bottom:20px}.notice strong{display:block;color:#78350f;font-size:16px}.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px}.kpi,.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:0 3px 14px #1837630a}.kpi{padding:15px 17px}.kpi .n{font:700 clamp(23px,2.6vw,32px)/1.1 ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--blue-dark);font-variant-numeric:tabular-nums}.kpi .label{font-weight:700;margin-top:7px}.kpi .hint{font-size:12px;color:var(--muted);margin-top:3px}.section{margin-top:27px;scroll-margin-top:65px}.section-head{display:flex;align-items:end;gap:15px;justify-content:space-between;margin-bottom:11px;flex-wrap:wrap}.section h2{margin:0;font-size:22px;line-height:1.3}.section-head p{margin:4px 0 0;color:var(--muted);max-width:860px}.panel{padding:17px}.mini-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.mini-grid h3{font-size:15px;margin:0 0 11px}.metricline{display:flex;justify-content:space-between;gap:14px;border-top:1px solid #edf1f7;padding:6px 0;font-size:13px}.metricline:first-of-type{border-top:0}.metricline b{font-variant-numeric:tabular-nums}.controls{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.search{flex:1 1 300px;min-width:210px;min-height:43px;border:1px solid #a8b8cd;background:#fff;border-radius:8px;padding:8px 12px;color:var(--ink)}.search::placeholder{color:#65758b}.select{min-height:43px;border:1px solid #a8b8cd;border-radius:8px;background:#fff;padding:6px 11px;color:var(--ink)}.count{font-size:13px;color:var(--muted);margin:2px 0 10px}.group{border:1px solid var(--line);border-radius:9px;background:#fff;margin-bottom:8px;overflow:hidden}.group summary{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;list-style:none;padding:11px 14px;cursor:pointer}.group summary::-webkit-details-marker{display:none}.group summary:hover{background:#f4f7fd}.group summary::after{content:"展开原值";font-size:12px;font-weight:700;color:var(--blue);grid-column:2}.group[open] summary::after{content:"收起原值"}.group .name{font-weight:750;overflow-wrap:anywhere}.group .sub{font-size:12px;color:var(--muted);margin-top:2px}.group .stats{font-size:12px;font-weight:700;white-space:nowrap;color:#344562;text-align:right}.group .variants{border-top:1px solid var(--line);background:#fbfcff;padding:5px 14px 10px}.variant{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;border-bottom:1px solid #e9eff7;padding:8px 1px;align-items:start;font-size:13px}.variant:last-child{border-bottom:0}.raw{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Noto Sans Mono CJK SC",monospace;font-size:12px;overflow-wrap:anywhere;white-space:pre-wrap}.vmeta{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}.parts{display:flex;gap:4px;flex-wrap:wrap;margin-top:5px}.part{border:1px solid #dce4ef;border-radius:5px;background:#fff;padding:1px 5px;font-size:11px;color:#40516c;overflow-wrap:anywhere}.part b{color:var(--blue-dark);margin-right:4px}.badge{display:inline-block;border-radius:4px;padding:1px 6px;font-size:11px;font-weight:800;vertical-align:1px;white-space:nowrap}.b-blue{background:#e8efff;color:#1e40af}.b-amber{background:var(--amber-bg);color:var(--amber)}.b-red{background:var(--red-bg);color:var(--red)}.b-green{background:var(--green-bg);color:var(--green)}.pager{display:flex;gap:9px;align-items:center;justify-content:flex-end;padding:8px 0 2px}.pager button{border:1px solid #a8b8cd;background:#fff;color:var(--blue-dark);border-radius:7px;min-width:72px;min-height:40px;font-weight:700}.pager span{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}.catalog-grid{display:grid;grid-template-columns:2fr 1fr;gap:14px}.table-wrap{overflow:auto;max-height:440px;border:1px solid var(--line);border-radius:8px;background:#fff}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid #e9eef5}th{position:sticky;top:0;background:#eaf0fa;color:#253a5a;z-index:1}td.code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-variant-numeric:tabular-nums}td.long{overflow-wrap:anywhere}.method{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}.method h3{font-size:15px;margin:0 0 6px}.method p{margin:0;color:#46566b;font-size:13px}.source-list{margin:0;padding-left:19px;font-size:12px;color:#45546a;overflow-wrap:anywhere}.source-list li{margin:6px 0}.source-list code{font:11px ui-monospace,SFMono-Regular,Consolas,monospace}footer{margin-top:30px;border-top:1px solid var(--line);padding:20px 0;color:var(--muted);font-size:12px}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.group summary{grid-template-columns:minmax(0,1fr) auto auto}.group summary::after{grid-column:3;grid-row:1}.group .stats{grid-column:2;grid-row:1}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.catalog-grid{grid-template-columns:1fr}}@media(max-width:600px){.wrap{padding:0 14px}.top{padding:23px 0}.kpis,.mini-grid,.method{grid-template-columns:1fr}.kpi{padding:13px}.panel{padding:13px}.group summary{padding:10px}.variant{grid-template-columns:1fr}.vmeta{white-space:normal}.nav .wrap{gap:16px}.section{margin-top:24px}}
</style>
</head>
<body>
<header class="top"><div class="wrap"><div class="topline"><div class="eyebrow">KIFU / RAW NAME INVENTORY</div><span class="stamp">TEST / PROD 原值 staging 已应用 · 身份待审</span></div><h1>棋谱姓名与赛事原值预处理报告</h1><p>从冻结的 173,025 盘棋谱清单提取原始姓名与 EV 字段，展示可逆的解析分组、已有目录 ID 和仍需处理的例外。页面离线可用，搜索与分页仅在本机运行。</p></div></header>
<nav class="nav" aria-label="报告导航"><div class="wrap"><a href="#overview">总览</a><a href="#players">棋手原值</a><a href="#events">赛事原值</a><a href="#variants">重复候选</a><a href="#catalog">已建实体目录</a><a href="#method">口径与来源</a></div></nav>
<main class="wrap">
<div class="notice" role="note"><strong>当前阶段：原值 staging 已在 TEST 与 PROD 应用；身份归并与全量中文规范名审核仍待完成</strong>“解析名分组”不是不同棋手数，“候选系列核心”不是不同赛事数。现有 ID 与原值分组没有自动对应；含汉字的 canonical 只是字形观察，不代表已审定中文名。拉丁、占位符与破损原值继续待核。</div>
<section id="overview" class="section"><div class="section-head"><div><h2>总览</h2><p>棋手按黑白两个槽位统计；赛事按每盘一条 EV 槽位统计。分组不会覆盖原始字段。</p></div></div><div class="kpis" id="kpis"></div><div class="mini-grid" style="margin-top:14px"><div class="panel"><h3>棋手处理状态</h3><div id="playerStats"></div></div><div class="panel"><h3>赛事处理状态</h3><div id="eventStats"></div></div></div></section>
<section id="players" class="section"><div class="section-head"><div><h2>棋手 · 原始写法分组</h2><p>覆盖全部 7,251 种原值，包括单写法组；按保守解析得到的 base name 分组，段位单列。展开可查看该组全部原串、槽位次数及解析例外。</p></div><span class="badge b-amber">分组待审 ≠ 已确认人物</span></div><div class="panel"><div class="controls"><label class="sr-only" for="playerSearch">搜索棋手分组或原值</label><input id="playerSearch" class="search" type="search" placeholder="搜索解析名或任一原始写法…" autocomplete="off"><label class="sr-only" for="playerFilter">棋手类别</label><select id="playerFilter" class="select"><option value="all">全部类别</option><option value="readable_unlinked">可读待关联</option><option value="placeholder">占位符</option><option value="corrupt_pending">破损待核</option></select></div><div id="playerCount" class="count" aria-live="polite"></div><div id="playerList"></div><div id="playerPager" class="pager"></div></div></section>
<section id="events" class="section"><div class="section-head"><div><h2>赛事 · 候选系列核心</h2><p>覆盖全部 50,223 种 EV 原值，包括单写法组和 NULL；仅拆出明确的年份、届期、轮次、局次或季节。非系列描述和异常值也在此清单中。</p></div><span class="badge b-amber">核心待审 ≠ 已确认赛事</span></div><div class="panel"><div class="controls"><label class="sr-only" for="eventSearch">搜索赛事核心或原值</label><input id="eventSearch" class="search" type="search" placeholder="搜索核心或任一原始 EV…" autocomplete="off"><label class="sr-only" for="eventFilter">赛事类别</label><select id="eventFilter" class="select"><option value="all">全部类别</option><option value="core">候选核心</option><option value="exception">非系列／异常</option></select></div><div id="eventCount" class="count" aria-live="polite"></div><div id="eventList"></div><div id="eventPager" class="pager"></div></div></section>
<section id="variants" class="section"><div class="section-head"><div><h2>跨写法重复候选 · 全部待审</h2><p>独立候选审计使用 NFKC、繁简折叠及已知别名连接；目录精确字符串锚点也不能证明同名棋谱已归属某人或赛事。下方先列全量候选统计和优先审核前 100 组，再列本页机械折叠发现的核心标签变体。</p></div></div><div class="mini-grid" id="candidateStats" style="margin-bottom:14px"></div><div class="panel" style="margin-bottom:14px"><h3>优先审核前 100 组 <span class="badge b-amber">候选 · 未归并</span></h3><label class="sr-only" for="candidateSearch">搜索优先审核候选</label><input id="candidateSearch" class="search" type="search" placeholder="搜索候选名或目录 ID…" style="width:100%;margin-bottom:9px"><div id="candidateCount" class="count"></div><div class="table-wrap"><table><thead><tr><th scope="col">优先级</th><th scope="col">类型 / 候选名</th><th scope="col">原值种类 / 槽位</th><th scope="col">目录锚点</th></tr></thead><tbody id="candidateRows"></tbody></table></div></div><div class="panel"><h3>额外的机械字形折叠提示</h3><p class="count">仅当两个不同核心在 Unicode NFKC、大小写及空白折叠后相同时列出；不构成赛事合并决定。</p><div id="variantIntro" class="count"></div><div id="variantList"></div><div id="variantPager" class="pager"></div></div></section>
<section id="catalog" class="section"><div class="section-head"><div><h2>已建实体目录</h2><p>直接列出 PROD 目录快照中的全部棋手与赛事 ID、当前 canonical。中文默认状态按是否含汉字作待核提示；是否为已确认的中文规范名无法从本快照推断。</p></div></div><div class="catalog-grid"><div class="panel"><h3>棋手 ID</h3><label class="sr-only" for="catalogPlayerSearch">搜索棋手目录</label><input id="catalogPlayerSearch" class="search" type="search" placeholder="搜索棋手 ID 或 canonical…" style="width:100%;margin-bottom:9px"><div id="catalogPlayerCount" class="count"></div><div class="table-wrap"><table><thead><tr><th scope="col">ID</th><th scope="col">当前 canonical</th><th scope="col">中文默认状态</th></tr></thead><tbody id="catalogPlayerRows"></tbody></table></div><div id="catalogPlayerPager" class="pager"></div></div><div class="panel"><h3>赛事类型 ID</h3><label class="sr-only" for="catalogEventSearch">搜索赛事目录</label><input id="catalogEventSearch" class="search" type="search" placeholder="搜索赛事 ID 或 canonical…" style="width:100%;margin-bottom:9px"><div id="catalogEventCount" class="count"></div><div class="table-wrap"><table><thead><tr><th scope="col">ID</th><th scope="col">当前 canonical</th><th scope="col">中文默认状态</th></tr></thead><tbody id="catalogEventRows"></tbody></table></div></div></div></section>
<section id="method" class="section"><div class="section-head"><div><h2>口径与来源</h2><p>原值数字取自冻结清单，目录 ID 取自之后导出的 PROD 快照；页面生成后不会连接生产库，也不会自行刷新。</p></div></div><div class="method"><div class="panel"><h3>分组方法</h3><p>棋手原串仅去除明确嵌入的“X段”后缀，保留原串和次数；占位、SGF 属性污染单列。赛事结构解析只剥离有明确边界的年份、届期、轮次、局次和季节；每条原串与各片段仍可拼回原文。解析结果统一为待审，未创建身份、别名或赛事关联。</p></div><div class="panel"><h3>统计边界</h3><p>原值种类按完全相同的字符串去重；次数按棋谱槽位累计。已有目录 ID 是另一种对象，不能从原值个数推导。FK 槽位仅表示清单捕获当时已有链接。含汉字检测不检验语种、字形正确性或人物身份；疑似重复只用机械字形折叠。</p></div></div><div class="panel" style="margin-top:13px"><h3>快照与可复现性</h3><ul id="sources" class="source-list"></ul></div></section>
<footer>静态数据报告 · 仅供预处理与人工审核。原始棋谱字段未在本报告中修改。</footer>
</main>
<script id="report-data" type="application/json">__DATA__</script>
<script>
"use strict";
const D=JSON.parse(document.getElementById("report-data").textContent), S=D.stats;
const fmt=n=>Number(n).toLocaleString("zh-CN");
const esc=s=>String(s===null?"∅ NULL":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const $=id=>document.getElementById(id);
const line=(label,value)=>`<div class="metricline"><span>${esc(label)}</span><b>${esc(value)}</b></div>`;
const card=(n,label,hint)=>`<div class="kpi"><div class="n">${fmt(n)}</div><div class="label">${label}</div><div class="hint">${hint}</div></div>`;
$("kpis").innerHTML=card(S.player_raw,"棋手原值种类","黑白槽位合计 "+fmt(S.player_slots))+card(S.player_groups,"解析名分组","不代表不同人物")+card(S.event_raw,"赛事 EV 原值种类","覆盖 "+fmt(S.games)+" 盘")+card(S.event_groups,"候选系列核心分组","不代表不同赛事");
$("playerStats").innerHTML=line("可读原值种类",fmt(S.player_categories.readable_unlinked||0))+line("含明确段位后缀",fmt(S.player_ranked))+line("占位符原值",fmt(S.player_categories.placeholder||0))+line("破损待核原值",fmt(S.player_categories.corrupt_pending||0))+line("一个解析名对应多原串的组",fmt(S.player_multi))+line("已有棋手 FK 槽位",fmt(S.player_fk_slots)+" / "+fmt(S.player_slots)+"（"+(100*S.player_fk_slots/S.player_slots).toFixed(2)+"%）")+line("黑白两位均有 ID 的棋谱",fmt(S.both_player_fk_games));
$("eventStats").innerHTML=line("候选核心分组",fmt(S.event_groups))+line("一个核心对应多原串的组",fmt(S.event_multi))+line("非系列／异常 EV 原值",fmt(S.event_nonseries))+line("年份 / 届期 / 轮次原值",[S.event_components.year||0,S.event_components.edition||0,S.event_components.round||0].map(fmt).join(" / "))+line("局次 / 季节原值",[S.event_components.game||0,S.event_components.season||0].map(fmt).join(" / "))+line("已有赛事 FK 槽位",fmt(S.event_fk_slots)+" / "+fmt(S.games)+"（"+(100*S.event_fk_slots/S.games).toFixed(2)+"%）");
const pLabels={readable_unlinked:"可读待关联",placeholder:"占位符",corrupt_pending:"破损待核"};
const eLabels={empty:"空值",generic_event_description:"泛化赛事描述",game_description:"对局描述",program_source_label:"程序来源标记",corrupt_data:"污染原值",formal_event_candidate:"形式候选",unclassified_pending:"待分类"};
const partLabels={year:"年份",edition:"届期",round:"轮次",game:"局次",season:"季节",core:"核心"};
function pager(id,page,pages,move){$(id).innerHTML=`<button type="button" data-step="-1" ${page<=0?"disabled":""}>上一页</button><span>第 ${fmt(page+1)} / ${fmt(Math.max(1,pages))} 页</span><button type="button" data-step="1" ${page>=pages-1?"disabled":""}>下一页</button>`;$(id).querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>move(Number(b.dataset.step))));}
function setupGroups(kind,rows){const isEvent=kind==="event",search=$(kind+"Search"),filter=$(kind+"Filter"),list=$(kind+"List"),count=$(kind+"Count"),pageBox=$(kind+"Pager");let page=0,found=rows;const size=32;const searchable=value=>value===null?"NULL ∅":value||"";const indexed=rows.map(row=>[row,([searchable(row[0]),...row[3].map(x=>searchable(x[0]))].join("\u0001")).toLocaleLowerCase()]);
function render(){const pages=Math.ceil(found.length/size);page=Math.max(0,Math.min(page,Math.max(0,pages-1)));count.textContent=`显示 ${fmt(found.length)} 个分组 · 全部 ${fmt(rows.length)} 个分组 · 每页 ${size} 组`;list.innerHTML=found.slice(page*size,(page+1)*size).map((g,i)=>{const label=g[0]===null?"∅ NULL":g[0]||"（空解析名）",badge=isEvent?(g[1]==="core"?'<span class="badge b-amber">核心待审</span>':'<span class="badge b-red">非系列／异常</span>'):`<span class="badge ${g[1]==="readable_unlinked"?"b-blue":"b-red"}">${esc(pLabels[g[1]]||g[1])}</span>`;return `<details class="group" data-offset="${page*size+i}" data-kind="${kind}"><summary><div><div class="name">${esc(label)} ${badge}</div><div class="sub">${isEvent?"原始 EV":"原始写法"} ${fmt(g[3].length)} 种 · ${isEvent?"棋谱":"槽位"} ${fmt(g[2])} 次</div></div><div class="stats">#${fmt(page*size+i+1)}</div></summary><div class="variants"></div></details>`;}).join("")||'<p class="count">没有匹配结果。</p>';
list.querySelectorAll("details").forEach(el=>el.addEventListener("toggle",()=>{if(el.open&&!el.dataset.loaded){const g=found[Number(el.dataset.offset)];el.querySelector(".variants").innerHTML=g[3].map(m=>{if(!isEvent)return `<div class="variant"><div><div class="raw">${esc(m[0])}</div>${m[2]?`<div class="parts"><span class="part"><b>段位</b>${esc(m[2])}</span></div>`:""}${m[3].length?`<div class="sub">例外：${esc(m[3].join("、"))}</div>`:""}</div><div class="vmeta">${fmt(m[1])} 槽位</div></div>`;const parts=m[3].filter(part=>part[0]!=="core").map(part=>`<span class="part"><b>${esc(partLabels[part[0]]||part[0])}</b>${esc(part[1])}</span>`).join("");return `<div class="variant"><div><div class="raw">${esc(m[0])}</div><div class="parts">${parts||'<span class="part">未拆分</span>'}</div><div class="sub">${esc(eLabels[m[2]]||m[2])} · ${esc(m[4])}${m[5].length?" · 例外："+esc(m[5].join("、")):""}</div></div><div class="vmeta">${fmt(m[1])} 盘</div></div>`;}).join("");el.dataset.loaded="1";}}));pager(kind+"Pager",page,pages,step=>{page+=step;render();list.scrollIntoView({block:"start",behavior:"smooth"});});}
let timer;function update(){clearTimeout(timer);timer=setTimeout(()=>{const q=search.value.trim().toLocaleLowerCase(),f=filter.value;found=indexed.filter(([row,index])=>(f==="all"||row[1]===f)&&(!q||index.includes(q))).map(item=>item[0]);page=0;render();},120);}search.addEventListener("input",update);filter.addEventListener("change",update);render();}
setupGroups("player",D.players);setupGroups("event",D.events);
const C=D.candidate_counts;$("candidateStats").innerHTML=`<div class="panel"><h3>棋手跨写法候选</h3>${line("待审候选组",fmt(C.players.candidate_group_count))}${line("覆盖原始写法",fmt(C.players.candidate_raw_spelling_count))}${line("涉及黑白槽位",fmt(C.players.candidate_occurrences))}</div><div class="panel"><h3>赛事跨写法候选</h3>${line("待审候选组",fmt(C.events.candidate_group_count))}${line("覆盖原始 EV",fmt(C.events.candidate_raw_spelling_count))}${line("涉及棋谱",fmt(C.events.candidate_occurrences))}</div>`;
function renderCandidates(){const q=$("candidateSearch").value.trim().toLocaleLowerCase(),matches=D.top_candidates.filter(r=>[r[2],...r[6]].join(" ").toLocaleLowerCase().includes(q));$("candidateCount").textContent=`${fmt(matches.length)} / ${fmt(D.top_candidates.length)} 组 · 全部状态为待审候选`;$("candidateRows").innerHTML=matches.map(r=>`<tr><td class="code">#${fmt(r[0])}</td><td class="long"><span class="badge b-blue">${r[1]==="player"?"棋手":"赛事"}</span> ${esc(r[2])}</td><td class="code">${fmt(r[3])} / ${fmt(r[4])}</td><td>${r[6].length?"ID "+r[6].map(fmt).join(", "):"无"}<div class="sub">${esc(r[5])} · 待审</div></td></tr>`).join("")||'<tr><td colspan="4">没有匹配结果。</td></tr>';}$("candidateSearch").addEventListener("input",renderCandidates);renderCandidates();
$("variantIntro").textContent=`${fmt(S.possible_variant_sets)} 组折叠后相同的核心，涉及 ${fmt(S.possible_variant_cores)} 个不同核心标签。`;let variantPage=0;function renderVariants(){const size=24,pages=Math.ceil(D.possible_variants.length/size);$("variantList").innerHTML=D.possible_variants.slice(variantPage*size,(variantPage+1)*size).map((set,i)=>`<div class="group" style="padding:10px 14px"><div class="name">#${fmt(variantPage*size+i+1)} <span class="badge b-amber">待审候选</span></div><div class="raw" style="margin-top:4px">${set.map(esc).join("<br>")}</div></div>`).join("");pager("variantPager",variantPage,pages,step=>{variantPage+=step;renderVariants();});}renderVariants();
function catalogRow(r){return `<tr><td class="code">${fmt(r[0])}</td><td class="long">${esc(r[1])}</td><td><span class="badge ${r[2]?"b-green":"b-amber"}">${r[2]?"含汉字 · 待核":"非汉字 · 待转写"}</span></td></tr>`;}
function setupCatalog(){const all=D.catalog_players,box=$("catalogPlayerRows"),input=$("catalogPlayerSearch");let rows=all,page=0;const size=45;function render(){const pages=Math.ceil(rows.length/size);$("catalogPlayerCount").textContent=`${fmt(rows.length)} / ${fmt(all.length)} 个 ID；${fmt(S.catalog_players_han)} 个 canonical 含汉字（未作确认）`;box.innerHTML=rows.slice(page*size,(page+1)*size).map(catalogRow).join("")||'<tr><td colspan="3">没有匹配结果。</td></tr>';pager("catalogPlayerPager",page,pages,step=>{page+=step;render();});}input.addEventListener("input",()=>{const q=input.value.trim().toLocaleLowerCase();rows=all.filter(r=>String(r[0]).includes(q)||r[1].toLocaleLowerCase().includes(q));page=0;render();});render();const eventAll=D.catalog_events,eventInput=$("catalogEventSearch");function renderEvents(){const q=eventInput.value.trim().toLocaleLowerCase(),matches=eventAll.filter(r=>String(r[0]).includes(q)||r[1].toLocaleLowerCase().includes(q));$("catalogEventCount").textContent=`${fmt(matches.length)} / ${fmt(S.catalog_events)} 个 ID；${fmt(S.catalog_events_han)} 个 canonical 含汉字（未作确认）`;$("catalogEventRows").innerHTML=matches.map(catalogRow).join("")||'<tr><td colspan="3">没有匹配结果。</td></tr>';}eventInput.addEventListener("input",renderEvents);renderEvents();}setupCatalog();
const M=D.meta;$("sources").innerHTML=`<li>棋谱清单快照时间：<code>${esc(M.snapshot)}</code>；报告生成时间：<code>${esc(M.generated)}</code>（UTC）。原值 staging 已在 TEST / PROD 应用并核验；该状态来自本次处理流程，非本页面实时查询。</li><li>清单输入：<code>${esc(M.inventory_path)}</code>；文件 SHA-256：<code>${esc(M.inventory_sha)}</code>；清单内部 SHA-256：<code>${esc(M.inventory_internal_sha)}</code>。</li><li>后续 PROD 目录输入：<code>${esc(M.catalog_path)}</code>；文件 SHA-256：<code>${esc(M.catalog_sha)}</code>。</li><li>独立重复候选审计：<code>${esc(M.candidate_path)}</code>；文件 SHA-256：<code>${esc(M.candidate_sha)}</code>。</li><li>结构解析规则：<code>${esc(M.parser_version)}</code>。棋手、赛事原值均从清单的 <code>all</code> 范围读取；页面内不调用网络或数据库。</li>`;
</script>
</body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    inventory, inventory_sha = read_json(args.inventory)
    catalog, catalog_sha = read_json(args.catalog)
    candidates, candidate_sha = read_json(args.candidates)
    data = build_data(inventory, catalog, candidates, inventory_sha, catalog_sha, candidate_sha)
    data["meta"]["inventory_path"] = str(args.inventory)
    data["meta"]["catalog_path"] = str(args.catalog)
    data["meta"]["candidate_path"] = str(args.candidates)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(HTML.replace("__DATA__", payload), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size, "stats": data["stats"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
