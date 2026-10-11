"""Link reviewed Fujitsu and Ing world championship games to event IDs."""

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

from katrain.web.kifu.catalog_preprocess_events import prepare_event_raw_values
from scripts.import_kifu_chinese_event_types import edition_for_row
from scripts.import_kifu_event_types import run
from scripts.prepare_kifu_events_full import split_type_candidate


GROUPS = {
    "fujitsu": ("富士通杯世界围棋锦标赛", {"富士通杯", "富士通杯世界围棋锦标赛", "FujitsuCup"}),
    "ing": ("应氏杯世界职业围棋锦标赛", {"应氏杯", "应氏杯世界职业围棋锦标赛", "应氏杯世界围棋锦标赛"}),
}
ING_YEAR = {1: 1988, 2: 1992, 3: 1996, 4: 2000, 5: 2004,
            6: 2008, 7: 2012, 8: 2016, 9: 2020, 10: 2024}


def classify_core(core: str, group: str) -> bool:
    if group == "fujitsu":
        return (core.startswith(("富士通杯", "FujitsuCup"))
                and not any(word in core for word in ("U15", "少年", "中日友谊", "纪念对局", "讲解")))
    return (core.startswith(("应氏杯", "“应氏杯”"))
            and not any(word in core for word in ("大学生", "青少年", "纪念对局")))


def reviewed_edition(group: str, edition: tuple[str, int] | None, date: str, core: str) -> list | None:
    if edition is None or edition[0] != "edition_number" or not isinstance(date, str) or not date[:4].isdecimal():
        return None
    number, year = edition[1], int(date[:4])
    qualifying = any(word in core for word in ("预选", "予選", "选拔", "資格", "资格", "国内最终", "代表"))
    if group == "fujitsu":
        expected = 1987 + number
        valid = 1 <= number <= 24 and year in ({expected - 1, expected} if qualifying else {expected})
    else:
        expected = ING_YEAR.get(number)
        valid = expected is not None and year in (
            {expected - 1, expected, expected + 1} if qualifying else {expected, expected + 1}
        )
        # The ninth final was played in person in 2023 after the 2020 online rounds.
        valid = valid or number == 9 and year == 2023 and "决赛" in core
    return list(edition) if valid else None


def build_plan(inventory: dict, inventory_sha: str, selection: str) -> tuple[dict, dict]:
    canonical, aliases = GROUPS[selection]
    staged = {}
    for item in prepare_event_raw_values(inventory):
        data = item["parsed_data"]
        core = data["series_core"] or ""
        if not classify_core(core, selection):
            continue
        try:
            edition, _ = edition_for_row(data, split_type_candidate(core))
        except ValueError:
            edition = None
        staged[data["original_raw_value"]] = (core, edition)
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    albums = []
    held = Counter()
    for association in inventory["album_associations"]:
        album_id, raw = association[columns["id"]], association[columns["event"]]
        if raw not in staged:
            continue
        core, edition = staged[raw]
        reviewed = reviewed_edition(selection, edition, association[columns["date_played"]], core)
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
