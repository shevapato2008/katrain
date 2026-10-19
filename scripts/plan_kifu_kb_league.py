"""Freeze a read-only, exact-album plan for additional Korean KB league EV values.

The live JSONL input is a read-only capture of [id, event, date_played,
event_id, event_edition_id]. This command never connects to or writes a DB.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re


CANONICAL = "韩国围棋联赛"
EXCLUDED_WORDS = ("女子", "围乙", "新秀", "future", "퓨처", "挑战", "选拔", "선발", "预选", "资格", "比赛说明",
                  "全明星赛", "赛季前超快棋探索赛")
TYPE_HOLDS = frozenset({"韩国联赛"})
_SEASON = re.compile(r"(20\d{2})\s*[-~～]\s*(20\d{2})")
_EDITION = re.compile(r"(?:第)?(\d{1,2})届")
_YEAR = re.compile(r"20\d{2}")


def candidate(raw: str) -> bool:
    text = raw.lower()
    return (
        "韩国围甲" in raw
        or "韩国围棋联赛" in raw
        or "韩国联赛" in raw
        or (("kb" in text or "国民银行杯" in raw) and ("围甲" in raw or "韩国联赛" in raw))
    )


def excluded(raw: str) -> bool:
    return raw in TYPE_HOLDS or any(word in raw.casefold() for word in EXCLUDED_WORDS)


def edition_key(raw: str, date: str | None) -> list | None:
    """Only reuse independently identifiable edition numbers; never infer a late season ordinal."""
    if not date or date.startswith("1900-"):
        return None
    actual_year = int(date[:4])
    season = _SEASON.search(raw)
    if season and int(season.group(2)) != int(season.group(1)) + 1:
        return None
    if season and (int(season.group(1)), int(season.group(2))) == (2021, 2022):
        # The SGF labels this season "19th"; the league archive calls it 18th.
        # Preserve the tournament type while the edition discrepancy is held.
        return None
    explicit = _EDITION.search(raw)
    if explicit:
        number = int(explicit.group(1))
        if 1 <= number <= 15 and actual_year in (2003 + number, 2004 + number):
            return ["edition_number", number]
        if number == 19 and actual_year in (2022, 2023):
            return ["edition_number", number]
        if number == 20 and actual_year in (2023, 2024):
            return ["edition_number", number]
        return None
    if season:
        return None
    year_match = _YEAR.search(raw)
    if year_match:
        year = int(year_match.group())
        if 2004 <= year <= 2018 and actual_year in (year, year + 1):
            return ["edition_number", year - 2003]
    return None


def build_plan(inventory: dict, inventory_sha: str, live_rows: list[list]) -> tuple[dict, dict]:
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    frozen = {row[columns["id"]]: row for row in inventory["album_associations"]}
    if len(frozen) != inventory["counts"]["all"]:
        raise ValueError("inventory album count mismatch")
    live_by_id = {row[0]: row for row in live_rows}
    if len(live_by_id) != len(live_rows):
        raise ValueError("duplicate live album ID")
    raw_status = defaultdict(set)
    for album_id, raw, date, event_id, edition_id in live_rows:
        if album_id not in frozen or frozen[album_id][columns["event"]] != raw or frozen[album_id][columns["date_played"]] != date:
            raise ValueError(f"live raw/date diverges from frozen inventory: {album_id}")
        if edition_id is not None and event_id is None:
            raise ValueError(f"orphan live edition: {album_id}")
        raw_status[raw].add(event_id)
    selected_raw = {raw for raw, ids in raw_status.items() if candidate(raw) and not excluded(raw) and None in ids}
    for raw in selected_raw:
        if raw_status[raw] - {None, 50}:
            raise ValueError(f"different event type already linked to selected raw: {raw}")
    rows = []
    for album_id, raw, date, event_id, edition_id in live_rows:
        if raw in selected_raw:
            if edition_id is not None:
                raise ValueError(f"selected raw has an existing edition; review exact album {album_id}")
            rows.append([album_id, raw, CANONICAL, edition_key(raw, date), date])
    rows.sort(key=lambda row: row[0])
    raw_counts = Counter(row[1] for row in rows)
    plan = {
        "version": 1,
        "inventory_sha256": inventory_sha,
        "total_albums": inventory["counts"]["all"],
        "selected_series": [CANONICAL],
        "series_names": {CANONICAL: CANONICAL},
        "require_existing_types": [CANONICAL],
        "albums": rows,
        "raw_counts": dict(sorted(raw_counts.items())),
    }
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    report = {
        "raw_values": len(selected_raw),
        "albums": len(rows),
        "type_only": sum(row[3] is None for row in rows),
        "edition_keys": sorted({tuple(row[3]) for row in rows if row[3]}),
        "already_linked": sum(live_by_id[row[0]][3] is not None for row in rows),
        "held_raw": {raw: sum(row[1] == raw and row[3] is None for row in live_rows) for raw in raw_status if candidate(raw) and excluded(raw) and None in raw_status[raw]},
        "plan_sha256": plan["sha256"],
    }
    return plan, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--live-jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    raw = args.inventory.read_bytes()
    inventory = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    live_rows = [json.loads(line) for line in args.live_jsonl.read_text(encoding="utf-8").splitlines()]
    plan, report = build_plan(inventory, hashlib.sha256(raw).hexdigest(), live_rows)
    args.output.write_bytes(gzip.compress(json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(), mtime=0))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
