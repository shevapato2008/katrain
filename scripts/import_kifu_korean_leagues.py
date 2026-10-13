"""Dry-run reviewed Korean men's, women's, and senior league EV aliases."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from scripts.import_kifu_chinese_event_types import build_plan as build_chinese_plan
from scripts.import_kifu_event_types import run


GROUPS = {
    "men": ("韩国围棋联赛", frozenset({
        "韩国围棋联赛", "韩国围甲", "韩国围甲联赛", "韩国职业围棋联赛",
    })),
    "women": ("韩国女子围棋联赛", frozenset({"韩国女子联赛", "韩国女子围棋联赛"})),
    "seniors": ("韩国元老围棋联赛", frozenset({
        "韩国元老联赛", "韩国平江杯元老联赛", "韩国扁钢杯元老联赛",
    })),
}


def edition_status(group: str, edition: list | None, date: str) -> tuple[str, int | None]:
    if edition is None:
        return "type_only", None
    year = int(date[:4]) if isinstance(date, str) and date[:4].isdecimal() else None
    kind, value = edition
    if group == "men":
        number = value if kind == "edition_number" else value - 2003 if kind == "year" and 2004 <= value <= 2018 else None
        valid = (number is not None and year is not None and (
            1 <= number <= 15 and year in (2003 + number, 2004 + number)
            or number == 19 and year in (2022, 2023)
            or number == 20 and year in (2023, 2024)
        ))
    elif group == "women":
        number = value if kind == "edition_number" else value - 2014 if kind == "year" else None
        valid = number is not None and 1 <= number <= 11 and year in (2014 + number, 2015 + number)
    else:
        number = value if kind == "edition_number" else None
        valid = number is not None and 1 <= number <= 10 and year in (2015 + number, 2016 + number)
    return ("edition", number) if valid else ("type_only", None)


def build_plan(inventory: dict, inventory_sha: str, catalog: dict, selection: str) -> tuple[dict, dict]:
    if selection not in GROUPS:
        raise ValueError(f"unknown Korean league selection: {selection}")
    canonical, source_names = GROUPS[selection]
    broad, _ = build_chinese_plan(inventory, inventory_sha, catalog=catalog)
    selected = [row for row in broad["albums"] if row[2] in source_names]
    missing = source_names - {row[2] for row in selected}
    if missing:
        raise ValueError(f"Korean league source names are missing: {sorted(missing)}")
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    dates = {row[columns["id"]]: row[columns["date_played"]] for row in inventory["album_associations"]}
    albums = []
    held = Counter()
    for album_id, raw, _, edition, frozen_date in selected:
        status, number = edition_status(selection, edition, dates[album_id])
        if status == "type_only":
            held["type_only_no_verifiable_edition"] += 1
        albums.append([album_id, raw, canonical, ["edition_number", number] if number else None, frozen_date])
    albums.sort(key=lambda row: row[0])
    plan = {"version": 1, "inventory_sha256": inventory_sha, "total_albums": inventory["counts"]["all"],
            "selected_series": [canonical], "series_names": {canonical: canonical},
            "series_aliases": {canonical: sorted(source_names - {canonical})},
            "albums": albums, "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))}
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    return plan, {"selection": selection, "selected_albums": len(albums),
                  "source_type_count": len(source_names), "held": dict(sorted(held.items())),
                  "plan_sha256": plan["sha256"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--selection", choices=tuple(GROUPS), required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    raw = args.inventory.read_bytes()
    inventory = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    plan, report = build_plan(inventory, hashlib.sha256(raw).hexdigest(), catalog, args.selection)
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
