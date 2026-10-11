"""Dry-run four reviewed Taiwanese tournament 赛/战 spellings as separate types."""

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
    "qiwang": ("台湾棋王赛", frozenset({"台湾棋王赛", "台湾棋王战"}), 2007),
    "guoshou": ("台湾国手赛", frozenset({"台湾国手赛", "台湾国手战"}), 2004),
    "tianyuan": ("台湾天元赛", frozenset({"台湾天元赛", "台湾天元战"}), 2001),
    "zhonghuan-gosei": ("台湾中环碁圣赛", frozenset({"台湾中环碁圣赛", "台湾中环碁圣战"}), 2012),
}


def edition_status(group: str, edition: list | None, date: str) -> list | None:
    if edition is None or edition[0] != "edition_number":
        return None
    number = edition[1]
    year = int(date[:4]) if isinstance(date, str) and date[:4].isdecimal() else None
    if year is None or not 1 <= number <= 26:
        return None
    expected = GROUPS[group][2] + number
    if group == "qiwang":
        return edition if year in (expected - 1, expected, expected + 1) else None
    return edition if year == expected else None


def build_plan(inventory: dict, inventory_sha: str, catalog: dict, selection: str) -> tuple[dict, dict]:
    if selection not in GROUPS:
        raise ValueError(f"unknown Taiwanese tournament: {selection}")
    canonical, source_names, _ = GROUPS[selection]
    broad, _ = build_chinese_plan(inventory, inventory_sha, catalog=catalog)
    selected = [row for row in broad["albums"] if row[2] in source_names]
    missing = source_names - {row[2] for row in selected}
    if missing:
        raise ValueError(f"Taiwanese source names are missing: {sorted(missing)}")
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    dates = {row[columns["id"]]: row[columns["date_played"]] for row in inventory["album_associations"]}
    albums = []
    held = Counter()
    for album_id, raw, _, edition, frozen_date in selected:
        verified = edition_status(selection, edition, dates[album_id])
        if verified is None:
            held["type_only_edition_date_conflict"] += 1
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
