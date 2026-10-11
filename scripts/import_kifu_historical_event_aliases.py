"""Review and dry-run five historical tournament name groups from frozen EV inventory."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from katrain.web.kifu.catalog_preprocess_events import prepare_event_raw_values
from scripts.import_kifu_chinese_event_types import build_plan as build_chinese_plan, edition_for_row
from scripts.import_kifu_event_types import run
from scripts.prepare_kifu_events_full import split_type_candidate


GROUPS = {
    "japan-championship": ("日本棋院选手权战", {"Nihon Ki-in Championship", "NihonKi-inChampionship",
        "NihonKi-inChampionshipFinal", "Nihon Ki-in Championship Title", "日本棋院选手权战"}),
    "all-japan-first": ("全日本第一位战", {"All Japan #1", "All Japan #1 Title", "全日本第一位战"}),
    "korean-kuksu": ("韩国国手战", {"Kuksu", "KuksuFinal", "KuksuLeague", "韩国国手战"}),
    "korean-wangwi": ("韩国王位战", {"Wangwi", "WangwiFinal", "WangwiLeague", "韩国王位战"}),
    "korean-myeongin": ("韩国名人战", {"Myeongin", "MyeonginFinal", "MyeonginLeague", "韩国名人战"}),
}


def _myeongin_year(number: int) -> int | None:
    if number == 1:
        return 1968
    if number == 2:
        return 1970
    if 3 <= number <= 8:
        return number + 1968
    if 9 <= number <= 33:
        return number + 1969
    if number == 34:
        return 2004
    if 35 <= number <= 43:
        return number + 1972
    if 44 <= number <= 48:
        return number + 1977
    return None


def _edition_status(group: str, number: int | None, date: str) -> str:
    if number is None:
        return "type_only"
    year = int(date[:4]) if isinstance(date, str) and date[:4].isdecimal() else None
    if year is None:
        return "type_only"
    if group == "japan-championship":
        expected = 1953 + number if 1 <= number <= 22 else None
        allowed = {-2, -1, 0, 1}
    elif group == "all-japan-first":
        expected = 1969 + number if 1 <= number <= 5 else None
        allowed = {-2, -1, 0, 1}
    elif group == "korean-kuksu":
        expected = 1955 + number if 1 <= number <= 59 else None
        allowed = {0, 1, 2}
    elif group == "korean-wangwi":
        expected = 1965 + number if 1 <= number <= 43 else None
        allowed = {0, 1}
    else:
        expected = _myeongin_year(number)
        allowed = {-2, -1, 0, 1}
    if expected is None:
        return "hold"
    return "edition" if year - expected in allowed else "hold"


def build_plan(inventory: dict, inventory_sha: str, catalog: dict, selection: str) -> tuple[dict, dict]:
    if selection not in GROUPS:
        raise ValueError(f"unknown historical group: {selection}")
    canonical, source_names = GROUPS[selection]
    broad, _ = build_chinese_plan(inventory, inventory_sha, catalog=catalog)
    chinese = {row[1]: row[3] for row in broad["albums"] if row[2] == canonical}
    staged = {row["parsed_data"]["original_raw_value"]: row["parsed_data"]
              for row in prepare_event_raw_values(inventory)}
    targets = {}
    for raw, data in staged.items():
        core = data["series_core"]
        if raw not in chinese and core not in source_names and not (
            selection == "all-japan-first" and core and split_type_candidate(core)["type_candidate"] == canonical
        ):
            continue
        if raw in chinese:
            edition = chinese[raw]
        elif core == canonical and selection != "all-japan-first":
            continue  # Chinese structural planner rejected this raw.
        else:
            try:
                parsed, _ = edition_for_row(data, {"year": None, "edition": None})
            except ValueError:
                continue
            edition = list(parsed) if parsed else None
        if edition and edition[0] != "edition_number":
            continue
        targets[raw] = edition
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    proposed = []
    held = Counter()
    conflicting_raw = set()
    for row in inventory["album_associations"]:
        raw = row[columns["event"]]
        if raw not in targets:
            continue
        album_id = row[columns["id"]]
        edition = targets[raw]
        status = _edition_status(selection, edition[1] if edition else None, row[columns["date_played"]])
        if status == "hold":
            held["date_or_edition_conflict"] += 1
            conflicting_raw.add(raw)
            continue
        if status == "type_only":
            held["type_only_no_verifiable_edition"] += 1
        proposed.append([album_id, raw, canonical, edition if status == "edition" else None,
                         row[columns["date_played"]]])
    albums = [row for row in proposed if row[1] not in conflicting_raw]
    held["same_raw_held_with_conflict"] = len(proposed) - len(albums)
    albums.sort(key=lambda row: row[0])
    plan = {"version": 1, "inventory_sha256": inventory_sha, "total_albums": inventory["counts"]["all"],
            "selected_series": [canonical], "series_names": {canonical: canonical},
            "series_aliases": {canonical: sorted(name for name in source_names - {canonical}
                                                 if not name.endswith(("Final", "League", "Title")))},
            "albums": albums, "raw_counts": dict(sorted(Counter(row[1] for row in albums).items()))}
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    report = {"selection": selection, "selected_albums": len(albums), "source_raw_values": len(targets),
              "held": dict(sorted(held.items())), "plan_sha256": plan["sha256"]}
    return plan, report


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
