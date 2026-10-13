"""Read-only plans for Korean Futures League, Chinese Tianyuan, and Changqi Cup."""

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
    "futures": ("韩国围乙联赛", frozenset({"韩国围乙联赛", "韩国围乙"})),
    "china-tianyuan": ("中国围棋天元战", frozenset({"中国围棋天元战", "同里杯中国天元战"})),
    "changqi": ("中国倡棋杯", frozenset({"中国倡棋杯", "倡棋杯"})),
}


def reviewed_edition(group: str, edition: list | None, date: str) -> list | None:
    if edition is None or not isinstance(date, str) or not date[:4].isdecimal():
        return None
    year = int(date[:4])
    kind, value = edition
    if group == "futures":
        if kind == "year" and value == year and value in {2013, 2014, 2016, 2025}:
            return edition
        if kind == "year" and value == year and value in {2023, 2024}:
            return ["edition_number", {2023: 19, 2024: 20}[value]]
        if kind == "edition_number" and (
            value == 14 and year in {2017, 2018}
            or value == 15 and year == 2018
            or value == 19 and year == 2023
            or value == 20 and year == 2024
        ):
            return edition
        return None
    if kind != "edition_number":
        return None
    if group == "china-tianyuan":
        return edition if 1 <= value <= 40 and year in {1986 + value, 1987 + value} else None
    if group == "changqi":
        valid = (1 <= value <= 16 and year in {2003 + value, 2004 + value}
                 or value == 17 and year == 2021
                 or value == 18 and year in {2022, 2023}
                 or value == 19 and year == 2025)
        return edition if valid else None
    raise ValueError(group)


def build_plan(inventory: dict, inventory_sha: str, catalog: dict, selection: str) -> tuple[dict, dict]:
    canonical, source_names = GROUPS[selection]
    broad, _ = build_chinese_plan(inventory, inventory_sha, catalog=catalog)
    selected = [row for row in broad["albums"] if row[2] in source_names]
    missing = source_names - {row[2] for row in selected}
    if missing:
        raise ValueError(f"source names absent from structural candidates: {sorted(missing)}")
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    dates = {row[columns["id"]]: row[columns["date_played"]] for row in inventory["album_associations"]}
    albums = []
    held = Counter()
    for album_id, raw, _, edition, frozen_date in selected:
        verified = reviewed_edition(selection, edition, dates[album_id])
        if verified is None:
            held["type_only_unverified_edition"] += 1
        albums.append([album_id, raw, canonical, verified, frozen_date])
    albums.sort(key=lambda row: row[0])
    plan = {"version": 1, "inventory_sha256": inventory_sha, "total_albums": inventory["counts"]["all"],
            "selected_series": [canonical], "series_names": {canonical: canonical},
            "series_aliases": {canonical: sorted(source_names - {canonical})},
            "albums": albums, "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))}
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    return plan, {"selection": selection, "selected_albums": len(albums),
                  "held": dict(sorted(held.items())), "plan_sha256": plan["sha256"]}


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
