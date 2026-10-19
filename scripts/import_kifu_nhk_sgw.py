"""Read-only, date-checked event plans for Japan's NHK Cup and SGW Chuyosen."""

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

from scripts.import_kifu_event_types import run


GROUPS = {
    "nhk": ("日本NHK杯电视围棋锦标赛", ["日本NHK杯快棋赛", "日本NHK杯", "NHK Cup", "NHKCup"]),
    "sgw": ("日本SGW杯中庸战", ["日本SGW中庸战", "SGW杯中庸战"]),
}
_CHINESE_NUMBER = re.compile(r"第?([1-9][0-9]{0,2})(?:期|届|回)")
_ENGLISH_NUMBER = re.compile(r"(?<![0-9])([1-9][0-9]{0,2})(?:st|nd|rd|th)", re.I)
_NHK_SPECIAL_ROUNDS = ("new year special", "goodwill match")
_NHK_UNCERTAIN_EDITION_IDS = frozenset({136144})


def classify_raw(raw: str, selection: str) -> bool:
    folded = raw.casefold()
    if selection == "sgw":
        return "sgw" in folded and "中庸" in raw and ("杯" in raw or "日本" in raw)
    if any(word in folded for word in ("women", "new year", "newyear", "special", "exhibition", "radio", "sgf")):
        return False
    if any(word in raw for word in ("新春", "お好み", "講座", "围棋讲座", "号", "戞")):
        return False
    if "nhk" not in folded:
        return False
    return "杯" in raw or "nhkcup" in folded or "nhk cup" in folded


def edition_number(raw: str) -> int | None:
    match = _CHINESE_NUMBER.search(raw) or _ENGLISH_NUMBER.search(raw)
    return int(match.group(1)) if match else None


def reviewed_edition(selection: str, number: int | None, date: str | None) -> list | None:
    if number is None or not isinstance(date, str) or not date[:4].isdecimal():
        return None
    year = int(date[:4])
    if selection == "sgw":
        valid = 1 <= number <= 9 and year == 2017 + number
    else:
        valid = 1 <= number <= 74 and year in {1952 + number, 1953 + number}
    return ["edition_number", number] if valid else None


def build_plan(inventory: dict, inventory_sha: str, selection: str) -> tuple[dict, dict]:
    canonical, aliases = GROUPS[selection]
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    candidates = defaultdict(list)
    for row in inventory["album_associations"]:
        raw = row[columns["event"]]
        if isinstance(raw, str) and classify_raw(raw, selection):
            candidates[raw].append(row)
    # The raw count gate in the shared importer requires every occurrence of a
    # selected EV. Hold a raw in full if any occurrence falls outside this title's era.
    safe = {}
    excluded = Counter()
    first_year = 2018 if selection == "sgw" else 1953
    for raw, rows in candidates.items():
        if selection == "nhk" and any(
            (isinstance(row[columns["round_name"]], str)
             and any(marker in row[columns["round_name"]].casefold() for marker in _NHK_SPECIAL_ROUNDS))
            or any("/NHK/Misc/" in source[3] for source in row[columns["sources"]]
                   if len(source) > 3 and isinstance(source[3], str))
            for row in rows
        ):
            # The shared importer's raw-count gate requires whole raw groups.
            # This also holds the undated duplicate of a New Year special.
            excluded["special_game_raw_group"] += len(rows)
            continue
        if any(not isinstance(row[columns["date_played"]], str)
               or not row[columns["date_played"]][:4].isdecimal()
               or not first_year <= int(row[columns["date_played"]][:4]) <= 2026 for row in rows):
            excluded["outside_title_era_or_missing_date"] += len(rows)
            continue
        safe[raw] = rows
    albums = []
    held = Counter()
    for raw, rows in safe.items():
        number = edition_number(raw)
        for row in rows:
            date = row[columns["date_played"]]
            verified = None if selection == "nhk" and row[columns["id"]] in _NHK_UNCERTAIN_EDITION_IDS else reviewed_edition(selection, number, date)
            if verified is None:
                held["type_only_unverified_edition"] += 1
            albums.append([row[columns["id"]], raw, canonical, verified, date])
    albums.sort(key=lambda row: row[0])
    plan = {"version": 1, "inventory_sha256": inventory_sha, "total_albums": inventory["counts"]["all"],
            "selected_series": [canonical], "series_names": {canonical: canonical},
            "series_aliases": {canonical: aliases}, "albums": albums,
            "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))}
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    return plan, {"selection": selection, "selected_albums": len(albums),
                  "held": dict(sorted(held.items())), "excluded": dict(sorted(excluded.items())),
                  "plan_sha256": plan["sha256"]}


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
