"""Plan conservative Chinese EV type/edition links; dry-run before review/apply.

The selection rule keeps sponsor spellings distinct. Orthographic similarities
and title-sponsor changes are review leads, not automatic alias merges. Only
complete clean groups above a frequency floor enter the plan. Legacy catalog
raw EV IDs remain outside this importer's scope.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from katrain.web.kifu.catalog_preprocess_events import prepare_event_raw_values
from scripts.import_kifu_event_types import run
from scripts.prepare_kifu_events_full import split_type_candidate


_HAN = re.compile(r"[\u3400-\u9fff]")
_UNSAFE_TYPE = re.compile(r"[A-Za-z0-9\[\]，,;:/\\~？?－\-()（）“”‘’]")
_TYPE_END = re.compile(r"(?:杯|赛|战|围甲|围乙|联赛|大手合)$")
_STAGE_IN_TYPE = re.compile(r"预选|预赛|循环圈|本战|本赛|本选|资格赛|初赛|复赛|季后赛|选拔赛|败者复活|决胜|淘汰|小组|分组|首届|\d+[届期轮回局场]|[0-9一二三四五六七八九十百]+强")
_AMBIGUOUS = {"团体赛", "友情杯", "名人战", "王座战", "本因坊战", "碁圣战", "十段战", "棋圣战", "升段赛", "韩国联赛", "围棋甲级联赛", "全国围棋甲级联赛"}
_EDITION = re.compile(r"(?:第)?([0-9]{1,3}|[一二三四五六七八九十百]+|首)(?:期|届)\Z")
_ENGLISH_ORDINAL = re.compile(r"([1-9]\d{0,2})(?:st|nd|rd|th)\Z", re.I)
_YEAR = re.compile(r"[12]\d{3}\Z")
EXISTING_CANONICAL_TYPES = frozenset({
    "日本本因坊战", "日本十段战", "日本王座战", "日本天元战",
    "日本名人战", "日本棋圣战", "日本碁圣战",
})
# These names are distinct titled cups in the current strict candidate set.
# Their possible historical sponsor changes remain review leads, not aliases.
UNIQUE_SPONSOR_CANDIDATES = frozenset({
    "台湾海峰杯职业围棋赛", "韩国物价信息杯", "日本广岛铝制杯若鲤战",
})
JAPAN_DISTINCT_CANDIDATES = frozenset({
    "日本龙星战", "日本新人王战", "日本女子本因坊战", "日本女子名人战",
    "日本女子棋圣战", "日本阿含桐山杯", "日本王冠战",
})
JAPAN_DISTINCT_HOLD_RAW = frozenset({
    "第30期日本女子名人战循环圈赛", "第30期日本女子名人战第1轮",
    "第31期日本新人王战本赛", "日本第15期新人王战",
    "第27期日本阿含桐山杯16强赛",
    "第22期日本龙星战本战E组第5局", "第22期日本龙星战本战F组第5局",
    "第22期日本龙星战本战E组第11局",
})
SAMSUNG_CUP_SOURCE_TYPES = frozenset({
    "三星杯", "三星火灾杯", "三星保险杯", "三星财产杯",
    "三星车险杯", "三星车险杯世界大师赛",
})
SAMSUNG_CUP_CANONICAL = "三星杯世界围棋大师赛"
SAMSUNG_CUP_EDITION_HOLD_RAW = "第5届三星杯预选"
CHINA_A_LEAGUE_CANONICAL = "中国围棋甲级联赛"
CHINA_A_LEAGUE_SOURCE_TYPES = frozenset({
    "中国围棋甲级联赛", "中国全国围棋甲级联赛", "中国围甲", "中国围甲联赛",
    "好猫杯围棋甲级联赛", "澳特来围甲联赛", "中国和围甲联赛",
    "金立手机杯围甲联赛", "金立智能手机杯围甲", "金立智能手机杯围甲联赛",
    "金立智能手机杯中国围甲", "金立智能手机中国围甲", "金立杯中国围甲",
    "金立杯围甲联赛", "华为手机杯中国围甲联赛", "华为手机杯中国围棋甲级联赛",
    "华为手机围甲", "三国赤壁古战场杯围甲", "三国赤壁古战场围甲",
})
CHINA_WOMENS_LEAGUE_CANONICAL = "中国女子围棋甲级联赛"
CHINA_WOMENS_LEAGUE_SOURCE_TYPES = frozenset({
    "中信置业杯中国女子围甲联赛", "中信置业中国女子围甲", "中信和业女子围甲",
    "中信置业杯女子围甲", "中信杯女子围甲", "中信置业杯中国女子围甲",
    "中信置业女子围甲", "中信杯中国女子围甲联赛", "中信和业杯中国女子围甲联赛",
})
OLD_MEIJIN_CANONICAL = "日本旧名人战"
OLD_MEIJIN_CHINESE_RAW = frozenset({
    "第1届日本名人战", "第3届日本名人战", "第4届日本名人战", "第5届日本名人战",
})
EXACT_HOLD_RAW = frozenset({
    "第39期日本本因坊战挑战赛5番棋第4局",
    "第44期日本名人战预选赛第1轮",
    "58期日本名人战循环圈",
})
EXACT_EDITION_HOLD_RAW = frozenset({
    "第2届台湾海峰杯职业围棋赛32强战",
    "第2届台湾海峰杯职业围棋赛16强战",
    "第2届台湾海峰杯职业围棋赛8强战",
    "第2届台湾海峰杯职业围棋赛半决赛",
    "第2届台湾海峰杯职业围棋赛决赛3番棋第1局",
    "第2届台湾海峰杯职业围棋赛决赛3番棋第2局",
})


def clean_type(name: str) -> bool:
    return bool(_HAN.search(name) and _TYPE_END.search(name)
                and not _UNSAFE_TYPE.search(name) and not _STAGE_IN_TYPE.search(name)
                and name not in _AMBIGUOUS
                and not (name.endswith(("快棋", "主将")) and ("围甲" in name or "联赛" in name)))


def chinese_number(value: str) -> int | None:
    if value == "首":
        return 1
    if value.isascii() and value.isdecimal():
        return int(value)
    digits = {char: i for i, char in enumerate("零一二三四五六七八九")}
    if all(char in digits for char in value):
        number = 0
        for char in value:
            number = number * 10 + digits[char]
        return number or None
    if value.count("百") == 1:
        head, tail = value.split("百")
        hundreds = 1 if not head else chinese_number(head)
        rest = chinese_number(tail) if tail else 0
        return hundreds * 100 + rest if hundreds and rest is not None else None
    if value.count("十") == 1:
        head, tail = value.split("十")
        tens = 1 if not head else chinese_number(head)
        units = chinese_number(tail) if tail else 0
        return tens * 10 + units if tens and units is not None else None
    return None


def edition_for_row(data: dict, split: dict) -> tuple[tuple[str, int] | None, int | None]:
    numbers, years = set(), set()
    for value in [split["edition"], *(item["value"] for item in data["structure"]["components"]
                                      if item["kind"] == "edition")]:
        if value is None:
            continue
        match = _EDITION.fullmatch(value)
        english = _ENGLISH_ORDINAL.fullmatch(value)
        number = chinese_number(match.group(1)) if match else int(english.group(1)) if english else None
        if not number or number > 999:
            raise ValueError(f"invalid edition: {value!r}")
        numbers.add(number)
    for value in [split["year"], *(item["value"] for item in data["structure"]["components"]
                                   if item["kind"] == "year")]:
        if value is None:
            continue
        if not _YEAR.fullmatch(value):
            raise ValueError(f"invalid year: {value!r}")
        years.add(int(value))
    if len(numbers) > 1 or len(years) > 1:
        raise ValueError("conflicting edition or year components")
    number = next(iter(numbers), None)
    year = next(iter(years), None)
    return (("edition_number", number) if number else ("year", year) if year else None), year


def build_plan(inventory: dict, inventory_sha: str, *, catalog: dict, min_games: int = 50) -> tuple[dict, dict]:
    if min_games < 1:
        raise ValueError("min_games must be positive")
    legacy_raw = {row["canonical_name"] for row in catalog["kifu_events"] if row["id"] != 1}
    staged = prepare_event_raw_values(inventory)
    groups = defaultdict(list)
    exclusion_reasons = Counter()
    for row in staged:
        data = row["parsed_data"]
        core = data["series_core"]
        if core is None:
            continue
        split = split_type_candidate(core)
        name = split["type_candidate"]
        if name:
            groups[name].append((row, split))
    selected = {}
    raw_targets = {}
    year_hints = defaultdict(set)
    for name, members in groups.items():
        games = sum(row["parsed_data"]["occurrences"] for row, _ in members)
        if games < min_games:
            exclusion_reasons["below_frequency_floor"] += games
            continue
        if not clean_type(name):
            exclusion_reasons["type_boundary_or_script_unclear"] += games
            continue
        pending = []
        reason = None
        for row, split in members:
            data = row["parsed_data"]
            raw = data["original_raw_value"]
            if raw in EXACT_HOLD_RAW:
                exclusion_reasons["exact_raw_anomaly"] += data["occurrences"]
                continue
            if raw in OLD_MEIJIN_CHINESE_RAW:
                exclusion_reasons["old_meijin_exact_raw"] += data["occurrences"]
                continue
            if raw in legacy_raw:
                exclusion_reasons["legacy_raw_event_id"] += data["occurrences"]
                continue
            if set(data["parse_exceptions"] + data["structure"]["exceptions"]) - {
                "classification_review", "identity_unverified"
            }:
                reason = "parse_exception"
                break
            try:
                edition, year = edition_for_row(data, split)
            except ValueError:
                reason = "ambiguous_edition_or_year"
                break
            if raw in EXACT_EDITION_HOLD_RAW:
                exclusion_reasons["edition_link_held_raw_games"] += data["occurrences"]
                edition = None
            if any(item["kind"] not in {"edition", "year", "round", "game"}
                   for item in data["structure"]["components"]):
                reason = "unexpected_component"
                break
            pending.append((raw, edition, year, data["occurrences"]))
        if reason:
            exclusion_reasons[reason] += games
            continue
        if not pending:
            continue
        hints = defaultdict(set)
        for _, edition, year, _ in pending:
            if edition and edition[0] == "edition_number" and year:
                hints[edition[1]].add(year)
        if any(len(years) > 1 for years in hints.values()):
            exclusion_reasons["edition_year_conflict"] += games
            continue
        selected[name] = sum(count for _, _, _, count in pending)
        for raw, edition, year, _ in pending:
            raw_targets[raw] = (name, list(edition) if edition else None)
            if edition and year:
                year_hints[(name, edition[1])].add(year)

    cols = {name: i for i, name in enumerate(inventory["association_columns"])}
    albums = []
    for association in inventory["album_associations"]:
        raw = association[cols["event"]]
        if raw in raw_targets:
            name, edition = raw_targets[raw]
            albums.append([association[cols["id"]], raw, name, edition, association[cols["date_played"]]])
    albums.sort(key=lambda row: row[0])
    if len(albums) != sum(selected.values()):
        raise ValueError("selected event counts do not reconcile with albums")
    plan = {"version": 1, "inventory_sha256": inventory_sha,
            "series_names": {name: name for name in sorted(selected)},
            "selected_series": sorted(selected), "albums": albums,
            "total_albums": inventory["counts"]["all"],
            "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))}
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
    report = {"selected_types": len(selected), "selected_albums": len(albums),
              "selected_games_by_type": dict(sorted(selected.items(), key=lambda item: -item[1])),
              "excluded_games_by_reason": dict(sorted(exclusion_reasons.items())),
              "year_hint_count": len(year_hints), "plan_sha256": plan["sha256"],
              "minimum_games_per_type": min_games,
              "selection_status": "structural_candidates_pending_review"}
    return plan, report


def build_old_meijin_plan(inventory: dict, inventory_sha: str) -> tuple[dict, dict]:
    targets = {}
    chinese_seen = set()
    for row in prepare_event_raw_values(inventory):
        data = row["parsed_data"]
        raw = data["original_raw_value"]
        core = data["series_core"]
        if core != "Old Meijin" and raw not in OLD_MEIJIN_CHINESE_RAW:
            continue
        components = data["structure"]["components"]
        if len(components) != 1 or components[0]["kind"] != "edition":
            raise ValueError(f"Old Meijin edition is not explicit: {raw}")
        edition, _ = edition_for_row(data, {"year": None, "edition": None})
        if edition is None or edition[0] != "edition_number" or not 1 <= edition[1] <= 14:
            raise ValueError(f"Old Meijin edition is out of range: {raw}")
        targets[raw] = ["edition_number", edition[1]]
        if raw in OLD_MEIJIN_CHINESE_RAW:
            chinese_seen.add(raw)
    if chinese_seen != OLD_MEIJIN_CHINESE_RAW:
        raise ValueError("Old Meijin Chinese raw allowlist differs from frozen inventory")
    cols = {name: i for i, name in enumerate(inventory["association_columns"])}
    albums = []
    for association in inventory["album_associations"]:
        raw = association[cols["event"]]
        if raw not in targets:
            continue
        date = association[cols["date_played"]]
        if not isinstance(date, str) or not re.match(r"^(?:196\d|197[0-5])", date):
            raise ValueError(f"Old Meijin date is outside 1960–1975: album {association[cols['id']]}")
        albums.append([association[cols["id"]], raw, OLD_MEIJIN_CANONICAL, targets[raw], date])
    albums.sort(key=lambda row: row[0])
    if len(albums) != 1216:
        raise ValueError(f"Old Meijin album count changed: {len(albums)}")
    plan = {"version": 1, "inventory_sha256": inventory_sha,
            "series_names": {OLD_MEIJIN_CANONICAL: OLD_MEIJIN_CANONICAL},
            "selected_series": [OLD_MEIJIN_CANONICAL],
            "series_aliases": {OLD_MEIJIN_CANONICAL: ["Old Meijin", "旧名人戦"]},
            "albums": albums, "total_albums": inventory["counts"]["all"],
            "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))}
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
    return plan, {"selection": "old-meijin", "selected_types": 1, "selected_albums": len(albums),
                  "source_raw_values": len(targets), "chinese_raw_values": len(chinese_seen),
                  "selection_status": "primary_source_bounded_candidate", "plan_sha256": plan["sha256"]}


def build_china_a_league_plan(broad_plan: dict, inventory: dict) -> tuple[dict, dict]:
    """Merge reviewed men's A League spellings; require an explicit matching season."""
    missing = CHINA_A_LEAGUE_SOURCE_TYPES - set(broad_plan["selected_series"])
    if missing:
        raise ValueError(f"China A League source types are missing: {sorted(missing)}")
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    dates = {row[columns["id"]]: row[columns["date_played"]] for row in inventory["album_associations"]}
    albums = []
    held = Counter()
    for album_id, raw, source, edition, frozen_date in broad_plan["albums"]:
        if source not in CHINA_A_LEAGUE_SOURCE_TYPES:
            continue
        season = (edition[1] if edition and edition[0] == "year" else
                  1998 + edition[1] if edition and edition[0] == "edition_number" else None)
        date_year = str(dates[album_id])[:4]
        if season is None or not 1999 <= season <= 2026 or not date_year.isdecimal() or int(date_year) not in (season, season + 1):
            held[source] += 1
            continue
        albums.append([album_id, raw, CHINA_A_LEAGUE_CANONICAL, ["edition_number", season - 1998], frozen_date])
    albums.sort(key=lambda row: row[0])
    plan = {key: value for key, value in broad_plan.items() if key not in {
        "sha256", "albums", "selected_series", "series_names", "raw_counts", "require_existing_types"
    }}
    plan.update({"selected_series": [CHINA_A_LEAGUE_CANONICAL],
                 "series_names": {CHINA_A_LEAGUE_CANONICAL: CHINA_A_LEAGUE_CANONICAL},
                 "series_aliases": {CHINA_A_LEAGUE_CANONICAL: sorted(CHINA_A_LEAGUE_SOURCE_TYPES - {CHINA_A_LEAGUE_CANONICAL})},
                 "albums": albums, "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))})
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    return plan, {"selection": "china-a-league", "selected_types": 1,
                  "source_type_count": len(CHINA_A_LEAGUE_SOURCE_TYPES),
                  "selected_albums": len(albums), "held_without_matching_season": dict(sorted(held.items())),
                  "selection_status": "reviewed_sponsor_alias_candidate", "plan_sha256": plan["sha256"]}


def build_china_womens_league_plan(broad_plan: dict, inventory: dict) -> tuple[dict, dict]:
    missing = CHINA_WOMENS_LEAGUE_SOURCE_TYPES - set(broad_plan["selected_series"])
    if missing:
        raise ValueError(f"China women's league source types are missing: {sorted(missing)}")
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    dates = {row[columns["id"]]: row[columns["date_played"]] for row in inventory["album_associations"]}
    seasons = {**{edition: {edition + 2012} for edition in range(1, 8)},
               8: {2020, 2021}, 9: {2021, 2022}, 10: {2023}, 11: {2024}, 12: {2025}}
    albums = []
    held = Counter()
    for album_id, raw, source, edition, frozen_date in broad_plan["albums"]:
        if source not in CHINA_WOMENS_LEAGUE_SOURCE_TYPES:
            continue
        number = (edition[1] if edition and edition[0] == "edition_number" else
                  edition[1] - 2012 if edition and edition[0] == "year" and edition[1] in (2013, 2016) else None)
        date_year = str(dates[album_id])[:4]
        if number not in seasons or not date_year.isdecimal() or int(date_year) not in seasons[number]:
            held[source] += 1
            continue
        albums.append([album_id, raw, CHINA_WOMENS_LEAGUE_CANONICAL, ["edition_number", number], frozen_date])
    albums.sort(key=lambda row: row[0])
    plan = {key: value for key, value in broad_plan.items() if key not in {
        "sha256", "albums", "selected_series", "series_names", "raw_counts", "require_existing_types"
    }}
    plan.update({"selected_series": [CHINA_WOMENS_LEAGUE_CANONICAL],
                 "series_names": {CHINA_WOMENS_LEAGUE_CANONICAL: CHINA_WOMENS_LEAGUE_CANONICAL},
                 "series_aliases": {CHINA_WOMENS_LEAGUE_CANONICAL: sorted(CHINA_WOMENS_LEAGUE_SOURCE_TYPES)},
                 "albums": albums, "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))})
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    return plan, {"selection": "china-womens-league", "selected_types": 1,
                  "source_type_count": len(CHINA_WOMENS_LEAGUE_SOURCE_TYPES),
                  "selected_albums": len(albums), "held_without_matching_edition": dict(sorted(held.items())),
                  "selection_status": "reviewed_sponsor_alias_candidate", "plan_sha256": plan["sha256"]}


def build_samsung_cup_plan(broad_plan: dict, broad_report: dict, inventory: dict) -> tuple[dict, dict]:
    plan, report = select_plan(broad_plan, broad_report, "samsung-cup")
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    dates = {row[columns["id"]]: row[columns["date_played"]] for row in inventory["album_associations"]}
    held = 0
    for row in plan["albums"]:
        album_id, raw, _, edition, frozen_date = row
        date_year = str(dates[album_id])[:4]
        if not date_year.isdecimal():
            raise ValueError(f"Samsung Cup game date is missing: {album_id}")
        if raw == SAMSUNG_CUP_EDITION_HOLD_RAW:
            if album_id != 30426 or edition != ["edition_number", 5] or int(date_year) != 2003:
                raise ValueError("Samsung Cup exact edition hold no longer matches frozen inventory")
            row[3] = None
            held += 1
            continue
        number = edition[1] if edition and edition[0] == "edition_number" else (
            edition[1] - 1995 if edition and edition[0] == "year" else None
        )
        if number is None or not 1 <= number <= 30 or int(date_year) not in (1995 + number, 1996 + number):
            raise ValueError(f"Samsung Cup edition/date mismatch: album {album_id}, {raw!r}")
        if edition[0] == "year":
            row[3] = ["edition_number", number]
    if held != 1:
        raise ValueError("Samsung Cup exact edition hold count changed")
    plan["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in plan.items() if k != "sha256"},
                                             ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    report.update({"edition_link_held_games": held, "plan_sha256": plan["sha256"]})
    return plan, report


def select_plan(plan: dict, report: dict, selection: str) -> tuple[dict, dict]:
    choices = {
        "existing-only": EXISTING_CANONICAL_TYPES,
        "unique-sponsor": UNIQUE_SPONSOR_CANDIDATES,
        "japan-distinct": JAPAN_DISTINCT_CANDIDATES,
        "samsung-cup": SAMSUNG_CUP_SOURCE_TYPES,
        "all-candidates": set(plan["selected_series"]),
    }
    if selection not in choices:
        raise ValueError(f"unknown selection: {selection}")
    selected = set(plan["selected_series"]) & choices[selection]
    if selected != choices[selection] and selection != "all-candidates":
        raise ValueError(f"requested types are absent from structural candidates: {sorted(choices[selection]-selected)}")
    source_albums = [row for row in plan["albums"] if row[2] in selected
                     and not (selection == "japan-distinct" and row[1] in JAPAN_DISTINCT_HOLD_RAW)]
    albums = ([row[:2] + [SAMSUNG_CUP_CANONICAL, row[3], row[4]] for row in source_albums]
              if selection == "samsung-cup" else source_albums)
    output_names = {SAMSUNG_CUP_CANONICAL} if selection == "samsung-cup" else selected
    narrowed = {key: value for key, value in plan.items() if key not in {
        "sha256", "albums", "selected_series", "series_names", "raw_counts", "require_existing_types"
    }}
    narrowed.update({"selected_series": sorted(output_names),
                     "series_names": {name: name for name in sorted(output_names)},
                     "require_existing_types": sorted(selected & EXISTING_CANONICAL_TYPES),
                     "albums": albums, "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))})
    if selection == "samsung-cup":
        narrowed["series_aliases"] = {SAMSUNG_CUP_CANONICAL: sorted(selected)}
    narrowed["sha256"] = hashlib.sha256(json.dumps(narrowed, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":")).encode()).hexdigest()
    subset_report = {**report, "selection": selection, "selected_types": len(output_names),
                     "source_type_count": len(selected),
                     "selected_albums": len(albums),
                     "selected_games_by_type": {name: report["selected_games_by_type"][name] for name in sorted(selected)},
                     "plan_sha256": narrowed["sha256"]}
    if selection == "japan-distinct":
        subset_report["held_exact_raw_games"] = sum(
            row[2] in selected and row[1] in JAPAN_DISTINCT_HOLD_RAW for row in plan["albums"]
        )
        subset_report["selected_games_by_type"] = dict(sorted(Counter(row[2] for row in source_albums).items()))
    return narrowed, subset_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--min-games", type=int, default=50)
    parser.add_argument("--selection", choices=("existing-only", "unique-sponsor", "japan-distinct", "samsung-cup", "china-a-league",
                                                "china-womens-league",
                                                "old-meijin", "all-candidates"),
                        default="existing-only")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    raw = args.inventory.read_bytes()
    payload = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    inventory = json.loads(payload)
    inventory_sha = hashlib.sha256(raw).hexdigest()
    if args.selection == "old-meijin":
        plan, selection = build_old_meijin_plan(inventory, inventory_sha)
    else:
        broad_plan, broad_report = build_plan(inventory, inventory_sha,
                                              catalog=catalog, min_games=args.min_games)
        if args.selection == "china-a-league":
            plan, selection = build_china_a_league_plan(broad_plan, inventory)
        elif args.selection == "china-womens-league":
            plan, selection = build_china_womens_league_plan(broad_plan, inventory)
        elif args.selection == "samsung-cup":
            plan, selection = build_samsung_cup_plan(broad_plan, broad_report, inventory)
        else:
            plan, selection = select_plan(broad_plan, broad_report, args.selection)
    engine = create_engine(args.database_url)
    try:
        result = run(engine, plan, apply=args.apply, approved_sha256=args.approved_plan_sha256)
    finally:
        engine.dispose()
    result["selection"] = selection
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief = {key: value for key, value in result.items() if key not in {"selection", "selected_series"}}
    brief["selected_type_count"] = len(result["selected_series"])
    print(json.dumps(brief, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
