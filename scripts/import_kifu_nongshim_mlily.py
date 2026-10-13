"""Link reviewed Nongshim team cup and MLILY world open games."""

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
    "nongshim": ("农心辛拉面杯世界围棋团体赛", {"农心辛拉面杯世界围棋团体赛", "农心杯三国擂台赛", "农心杯世界团体赛"}),
    "mlily": ("梦百合杯世界围棋公开赛", {"梦百合杯世界围棋公开赛", "Mlily梦百合世界公开赛"}),
}
MLILY_START = {1: 2013, 2: 2015, 3: 2017, 4: 2019, 5: 2023, 6: 2026}
_EDITION = re.compile(r"(?<![0-9])(?:第)?([0-9]{1,3}|[一二三四五六七八九十百]+)(?:期|届)")


def classify_core(core: str, selection: str) -> bool:
    if selection == "nongshim":
        if any(word in core for word in ("白山水", "元老", "高校", "经典", "传奇", "超级对抗", "特邀")):
            return False
        return "农心" in core
    if any(word in core for word in ("围甲", "熬鹰", "十番棋", "业余", "表演赛")):
        return False
    return "杯" in core and ("梦百合" in core or "Mlily" in core or "MLILY" in core or "MLILI" in core)


def parsed_edition(data: dict) -> tuple[str, int] | None:
    match = _EDITION.search(data["original_raw_value"] or "")
    if match:
        number = chinese_number(match.group(1))
        return ("edition_number", number) if number else None
    try:
        parsed, _ = edition_for_row(data, split_type_candidate(data["series_core"] or ""))
    except ValueError:
        return None
    return parsed


def reviewed_edition(selection: str, edition: tuple[str, int] | None, date: str) -> list | None:
    if edition is None or not isinstance(date, str) or not date[:4].isdecimal():
        return None
    year = int(date[:4])
    kind, value = edition
    if selection == "nongshim":
        number = value if kind == "edition_number" else value - 1998 if kind == "year" and value == year else None
        valid = number is not None and 1 <= number <= 28 and year in {1998 + number, 1999 + number}
    else:
        number = value if kind == "edition_number" else None
        start = MLILY_START.get(number)
        valid = start is not None and year in range(start, start + (3 if number == 4 else 2))
    return ["edition_number", number] if valid else None


def build_plan(inventory: dict, inventory_sha: str, selection: str) -> tuple[dict, dict]:
    canonical, aliases = GROUPS[selection]
    staged = {}
    for item in prepare_event_raw_values(inventory):
        data = item["parsed_data"]
        if classify_core(data["series_core"] or "", selection):
            staged[data["original_raw_value"]] = parsed_edition(data)
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    albums, held = [], Counter()
    for association in inventory["album_associations"]:
        album_id, raw = association[columns["id"]], association[columns["event"]]
        if raw not in staged:
            continue
        verified = reviewed_edition(selection, staged[raw], association[columns["date_played"]])
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
