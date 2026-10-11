"""Link reviewed LG Cup and Chunlan Cup world championship games."""

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
    "lg-world": ("LG杯世界棋王赛", {"LG杯世界棋王赛", "LG杯世界棋王战", "朝鲜日报LG杯世界棋王战", "LGCup"}),
    "chunlan": ("春兰杯世界职业围棋锦标赛", {"春兰杯世界职业围棋锦标赛", "春兰杯", "春兰杯世界锦标赛"}),
}
CHUNLAN_START = {1: 1998, 2: 1999, 3: 2000, 4: 2002, 5: 2003, 6: 2006,
                 7: 2008, 8: 2010, 9: 2012, 10: 2014, 11: 2016, 12: 2018,
                 13: 2020, 14: 2022, 15: 2024, 16: 2026}
_CHINESE_EDITION = re.compile(r"(?<![0-9])(?:第)?([0-9]{1,3}|[一二三四五六七八九十百]+)(?:期|届)")


def classify_core(core: str, selection: str) -> bool:
    if selection == "lg-world":
        return ((core.startswith(("LG杯", "朝鲜日报LG杯", "LGCup")) or "世界第22届LG杯" in core)
                and not any(word in core for word in ("周年", "精油", "RefinedOils", "特别对局", "特別対局")))
    return core.startswith("春兰杯") and "纪念" not in core


def parsed_edition(data: dict) -> tuple[str, int] | None:
    match = _CHINESE_EDITION.search(data["original_raw_value"] or "")
    if match:
        number = chinese_number(match.group(1))
        return ("edition_number", number) if number else None
    try:
        parsed, _ = edition_for_row(data, split_type_candidate(data["series_core"] or ""))
    except ValueError:
        return None
    return parsed


def reviewed_edition(selection: str, edition: tuple[str, int] | None, date: str, core: str) -> list | None:
    if edition is None or edition[0] != "edition_number" or not isinstance(date, str) or not date[:4].isdecimal():
        return None
    number, year = edition[1], int(date[:4])
    if selection == "lg-world":
        valid = 1 <= number <= 31 and year in {1995 + number, 1996 + number}
    else:
        start = CHUNLAN_START.get(number)
        qualifying = any(word in core for word in ("预选", "选拔", "资格"))
        valid = start is not None and year in (
            {start - 1, start, start + 1, start + 2} if qualifying else {start, start + 1, start + 2}
        )
    return list(edition) if valid else None


def build_plan(inventory: dict, inventory_sha: str, selection: str) -> tuple[dict, dict]:
    canonical, aliases = GROUPS[selection]
    staged = {}
    for item in prepare_event_raw_values(inventory):
        data = item["parsed_data"]
        core = data["series_core"] or ""
        if classify_core(core, selection):
            staged[data["original_raw_value"]] = (core, parsed_edition(data))
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    albums, held = [], Counter()
    for association in inventory["album_associations"]:
        album_id, raw = association[columns["id"]], association[columns["event"]]
        if raw not in staged:
            continue
        core, edition = staged[raw]
        verified = reviewed_edition(selection, edition, association[columns["date_played"]], core)
        if verified is None:
            held["type_only_unverified_edition"] += 1
        albums.append([album_id, raw, canonical, verified, association[columns["date_played"]]])
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
