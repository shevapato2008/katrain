"""Link reviewed Japanese and Chinese title games to event IDs."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from katrain.web.kifu.catalog_preprocess_events import prepare_event_raw_values
from scripts.import_kifu_chinese_event_types import chinese_number, edition_for_row
from scripts.import_kifu_event_types import run
from scripts.prepare_kifu_events_full import split_type_candidate


GROUPS = {
    "prime-minister": ("日本首相杯争夺战", {"日本首相杯争夺战", "日本首相杯"}),
    "kansai-first": ("日本关西棋院第一位决定战", {"日本关西棋院第一位决定战", "日本关西棋院第一位战", "关西棋院第一位决定战", "Kansai Ki-in 1st Place"}),
    "china-ryusei": ("中国龙星战", {"中国龙星战", "钻石杯中国龙星战", "钻石杯龙星战"}),
    "china-meijin": ("中国围棋名人战", {"中国围棋名人战", "中国名人战", "永城杯中国名人战", "春茧杯中国名人战", "嫘祖杯中国名人战"}),
}
RYUSEI_YEAR = {1: 2008, 2: 2009, 3: 2011, 4: 2012, 5: 2013, 6: 2014,
               7: 2015, 8: 2016, 9: 2018, 10: 2019, 11: 2020, 12: 2021, 13: 2023}
_CHINESE_EDITION = re.compile(r"(?<![0-9])(?:第)?([0-9]{1,3}|[一二三四五六七八九十百]+)(?:期|届)")


def classify_core(core: str, selection: str) -> bool:
    if selection == "prime-minister":
        return ((core.startswith(("日本首相杯", "首相杯", "Prime Minister's Cup")))
                and not any(word in core for word in ("Winner vs", "优胜者", "纪念", "記念", "业余")))
    if selection == "kansai-first":
        return (("关西棋院第一位" in core or core.startswith("Kansai Ki-in 1st Place"))
                and not any(word in core for word in ("纪念", "記念", "特别对局", "特別対局")))
    if selection == "china-ryusei":
        return ("中国龙星战" in core or core.startswith("钻石杯龙星战")) and "冠军对抗赛" not in core
    if selection == "china-meijin":
        return ("中国名人战" in core or "中国围棋名人战" in core or core.startswith(("Mingren", "MingrenLeague", "MingrenFinal")))
    raise ValueError(selection)


def parsed_edition(data: dict) -> tuple[str, int] | None:
    raw = data["original_raw_value"] or ""
    match = _CHINESE_EDITION.search(raw)
    if match:
        number = chinese_number(match.group(1))
        return ("edition_number", number) if number else None
    try:
        parsed, _ = edition_for_row(data, split_type_candidate(data["series_core"] or ""))
    except ValueError:
        return None
    return parsed


def reviewed_edition(selection: str, edition: tuple[str, int] | None, date: str) -> list | None:
    if edition is None or edition[0] != "edition_number" or not isinstance(date, str) or not date[:4].isdecimal():
        return None
    number, year = edition[1], int(date[:4])
    if selection == "prime-minister":
        valid = 1 <= number <= 25 and year in {1955 + number, 1956 + number, 1957 + number}
    elif selection == "kansai-first":
        valid = 1 <= number <= 70 and year in {1955 + number, 1956 + number, 1957 + number}
    elif selection == "china-ryusei":
        expected = RYUSEI_YEAR.get(number)
        valid = expected is not None and year in {expected - 1, expected, expected + 1}
    else:
        expected = 1987 + number if 1 <= number <= 32 else {33: 2023, 34: 2024, 35: 2026}.get(number)
        valid = expected is not None and year in {expected - 1, expected, expected + 1}
    return list(edition) if valid else None


def build_plan(inventory: dict, inventory_sha: str, selection: str) -> tuple[dict, dict]:
    canonical, aliases = GROUPS[selection]
    staged = {}
    for item in prepare_event_raw_values(inventory):
        data = item["parsed_data"]
        core = data["series_core"] or ""
        if classify_core(core, selection) and not (selection == "prime-minister" and data["original_raw_value"] == "Prime Minister's Cup"):
            staged[data["original_raw_value"]] = parsed_edition(data)
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    albums, held = [], Counter()
    for association in inventory["album_associations"]:
        album_id, raw = association[columns["id"]], association[columns["event"]]
        if raw not in staged:
            continue
        reviewed = reviewed_edition(selection, staged[raw], association[columns["date_played"]])
        if reviewed is None:
            held["type_only_unverified_edition"] += 1
        albums.append([album_id, raw, canonical, reviewed, association[columns["date_played"]]])
    albums.sort(key=lambda row: row[0])
    plan = {"version": 1, "inventory_sha256": inventory_sha, "total_albums": inventory["counts"]["all"],
            "selected_series": [canonical], "series_names": {canonical: canonical},
            "series_aliases": {canonical: sorted(aliases - {canonical})},
            "albums": albums, "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))}
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    return plan, {"selection": selection, "selected_albums": len(albums),
                  "held": dict(sorted(held.items())), "plan_sha256": plan["sha256"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--selection", choices=tuple(GROUPS), required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    raw = args.inventory.read_bytes()
    inventory = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    plan, report = build_plan(inventory, hashlib.sha256(raw).hexdigest(), args.selection)
    engine = create_engine(args.database_url)
    try:
        result = run(engine, plan, apply=args.apply, approved_sha256=args.approved_plan_sha256)
    finally:
        engine.dispose()
    result["selection"] = report
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
