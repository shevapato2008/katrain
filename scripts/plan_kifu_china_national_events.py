"""Freeze exact, offline event plans for China's national individual/team Go events.

This planner only reads a post7 inventory and writes a gzip plan. It never
connects to the database. The shared event importer may validate a reviewed
plan later, after concurrent album writers have stopped.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re


SERIES = {
    "individual": {
        "canonical": "中国全国围棋个人赛",
        "tokens": ("中国围棋全国个人赛", "中国全国围棋个人赛", "中国全国个人赛"),
        "aliases": ("中国围棋全国个人赛", "中国全国个人赛"),
        "raw_count": 87,
        "album_count": 670,
    },
    "team": {
        "canonical": "中国全国围棋团体赛",
        "tokens": ("中国围棋团体赛", "ChineseNationalTeamTournament", "ChineseNationalTeamChampionships"),
        "aliases": ("中国围棋团体赛", "ChineseNationalTeamTournament", "ChineseNationalTeamChampionships"),
        "raw_count": 21,
        "album_count": 419,
    },
}
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_DESCRIPTION = ("比赛说明", "竞赛规程", "赛事介绍", "比赛介绍")
_TEAM_RAW_HOLDS = {"2000年中国围棋团体赛"}
_TEAM_ALBUM_HOLDS = {75789: ("中国围棋团体赛", "1993-09-12")}


def select_group(raw: str) -> str | None:
    matches = [name for name, config in SERIES.items() if any(token in raw for token in config["tokens"])]
    if len(matches) > 1:
        raise ValueError(f"individual/team identity collision: {raw}")
    return matches[0] if matches else None


def edition_for(raw: str, date: str | None, group: str) -> list | None:
    years = {int(match.group()) for match in _YEAR.finditer(raw)}
    if len(years) != 1 or not date or date.startswith("1900-"):
        return None
    year = next(iter(years))
    # The 2022 individual championship was postponed until September 2023.
    # Its type is secure; keep the year edition unlinked in this batch.
    if group == "individual" and year == 2022:
        return None
    return ["year", year] if date[:4] == str(year) else None


def build_plan(inventory: dict, inventory_sha: str, group: str) -> tuple[dict, dict]:
    if group not in SERIES:
        raise ValueError(f"unknown national event group: {group}")
    config = SERIES[group]
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    if len(inventory["album_associations"]) != inventory["counts"]["all"]:
        raise ValueError("frozen inventory album count differs")
    albums = []
    selected_raw_counts = Counter()
    held = Counter()
    for item in inventory["album_associations"]:
        raw = item[columns["event"]]
        if not raw or select_group(raw) != group:
            continue
        if any(word in raw for word in _DESCRIPTION):
            held[raw] += 1
            continue
        date = item[columns["date_played"]]
        if group == "team" and raw in _TEAM_RAW_HOLDS:
            continue
        selected_raw_counts[raw] += 1
        album_id = item[columns["id"]]
        if group == "team" and album_id in _TEAM_ALBUM_HOLDS:
            if (raw, date) != _TEAM_ALBUM_HOLDS[album_id]:
                raise ValueError(f"team exact album hold changed: {album_id}")
            continue
        edition = edition_for(raw, date, group)
        if edition is None:
            held["type_only"] += 1
        albums.append([item[columns["id"]], raw, config["canonical"], edition, date])
    albums.sort(key=lambda row: row[0])
    # Live validation counts every database row for each selected raw, including
    # the exact album hold within the otherwise approved aggregate raw.
    raw_counts = dict(sorted(selected_raw_counts.items()))
    if len(raw_counts) != config["raw_count"] or len(albums) != config["album_count"]:
        raise ValueError(f"exact {group} scope differs from reviewed post7 inventory")
    plan = {
        "version": 1,
        "inventory_sha256": inventory_sha,
        "total_albums": inventory["counts"]["all"],
        "selected_series": [config["canonical"]],
        "series_names": {config["canonical"]: config["canonical"]},
        "series_aliases": {config["canonical"]: list(config["aliases"])},
        "albums": albums,
        "raw_counts": raw_counts,
    }
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":")).encode()).hexdigest()
    report = {"group": group, "raw_values": len(raw_counts), "albums": len(albums),
              "year_editions": sum(row[3] is not None for row in albums),
              "type_only": held["type_only"],
              "description_holds": {raw: count for raw, count in held.items() if raw != "type_only"},
              "plan_sha256": plan["sha256"]}
    return plan, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--group", choices=tuple(SERIES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    raw = args.inventory.read_bytes()
    inventory = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    plan, report = build_plan(inventory, hashlib.sha256(raw).hexdigest(), args.group)
    args.output.write_bytes(gzip.compress(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode(), mtime=0))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
