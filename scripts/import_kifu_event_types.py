"""Link exact, conservative Japanese series cores to type and edition IDs.

Dry-run computes a snapshot-bound plan. Apply requires that plan's SHA-256 and
rechecks live album raw EV, date_played, and existing event links in one transaction. This
does not alter SGF EV strings, display translations, rounds, or legacy IDs.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuEvent, KifuEventAlias, KifuEventEdition
from katrain.web.kifu.catalog_preprocess_events import prepare_event_raw_values


SERIES = {
    "Oteai": "大手合", "Honinbo": "日本本因坊战", "Judan": "日本十段战",
    "Oza": "日本王座战", "Tengen": "日本天元战", "Meijin": "日本名人战",
    "Kisei": "日本棋圣战", "Gosei": "日本碁圣战",
    "Pro Best Ten": "日本职业十杰战", "ProBestTen": "日本职业十杰战",
}
# Exact album holds from the 2026-10-04 independent source/date review.
# Keep these here so a rebuilt historical plan cannot recreate a cleared link.
# See docs/resource/kifu-event-exact-link-corrections-2026-10-04.md.
_TYPE_HOLD_IDS = frozenset({
    33426, 33427, 33428, 48851, 65756, 125013, 125014,
    63983, 82318, 101422,
})
_EDITION_HOLD_IDS = frozenset({
    31009, 32664, 32665, 33874, 33875, 54391, 54392, 54534, 58575,
    63983, 66460, 82318, 101422, 124320, 124341, 124342, 124343,
    128390, 130126, 130127, 131890, 140418, 140419, 140420, 140421,
    141416, 142448, 142778, 143135, 145039,
})
_ORDINAL = re.compile(r"([1-9]\d{0,2})(?:st|nd|rd|th)\Z", re.I)
_YEAR = re.compile(r"[12]\d{3}\Z")


def edition_key(core: str, components: list[dict]) -> tuple[str, int] | None:
    if not components:
        return None
    if len(components) != 1:
        raise ValueError(f"ambiguous components for {core}")
    item = components[0]
    if core == "Oteai" and item["kind"] == "year" and _YEAR.fullmatch(item["value"]):
        return "year", int(item["value"])
    if core != "Oteai" and item["kind"] == "edition":
        match = _ORDINAL.fullmatch(item["value"])
        if match:
            return "edition_number", int(match.group(1))
    raise ValueError(f"ambiguous edition/year for {core}: {item!r}")


def build_plan(inventory: dict, inventory_sha: str, *, selected: set[str]) -> dict:
    if not selected or selected - SERIES.keys():
        raise ValueError("invalid selected series")
    raw_targets = {}
    for row in prepare_event_raw_values(inventory):
        data = row["parsed_data"]
        core = data["series_core"]
        if core not in selected:
            continue
        structure = data["structure"]
        if structure["grammar"] not in {
            "unparsed", "oteai_year", "english_ordinal_edition", "english_ordinal_joined", "english_ordinal_suffix"
        }:
            raise ValueError(f"unexpected grammar for {core}: {structure['grammar']}")
        if structure["exceptions"]:
            raise ValueError(f"structure exception for {core}: {structure['exceptions']}")
        raw_targets[data["original_raw_value"]] = (core, edition_key(core, structure["components"]))
    cols = {name: i for i, name in enumerate(inventory["association_columns"])}
    album_rows = []
    for association in inventory["album_associations"]:
        album_id, raw = association[cols["id"]], association[cols["event"]]
        if raw in raw_targets:
            core, edition = raw_targets[raw]
            album_rows.append([album_id, raw, core, list(edition) if edition else None,
                               association[cols["date_played"]]])
    album_rows.sort(key=lambda row: row[0])
    if sum(row["parsed_data"]["occurrences"] for row in prepare_event_raw_values(inventory)
           if row["parsed_data"]["original_raw_value"] in raw_targets) != len(album_rows):
        raise ValueError("target raw counts do not reconcile with album associations")
    plan = {"version": 1, "inventory_sha256": inventory_sha,
            "selected_series": sorted(selected), "albums": album_rows,
            "total_albums": inventory["counts"]["all"],
            "raw_counts": dict(sorted(Counter(row[1] for row in album_rows).items()))}
    plan["sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
    return plan


def _check_live(db: Session, plan: dict) -> dict:
    rows = plan["albums"]
    if any(len(row) != 5 or not isinstance(row[4], (str, type(None))) for row in rows):
        raise ValueError("plan lacks frozen album dates")
    if db.scalar(select(func.count()).select_from(KifuAlbum)) != plan["total_albums"]:
        raise ValueError("live album count differs from frozen inventory")
    live_raw_counts = Counter()
    raw_values = list(plan["raw_counts"])
    for start in range(0, len(raw_values), 500):
        live_raw_counts.update({raw: count for raw, count in db.execute(
            select(KifuAlbum.event, func.count()).where(KifuAlbum.event.in_(raw_values[start:start + 500]))
            .group_by(KifuAlbum.event)).all()})
    if dict(live_raw_counts) != plan["raw_counts"]:
        raise ValueError("live selected raw EV counts differ from frozen inventory")
    actual = {}
    for start in range(0, len(rows), 500):
        ids = [row[0] for row in rows[start:start + 500]]
        actual.update({row.id: row for row in db.execute(
            select(KifuAlbum.id, KifuAlbum.event, KifuAlbum.date_played,
                   KifuAlbum.event_id, KifuAlbum.event_edition_id)
            .where(KifuAlbum.id.in_(ids))).all()})
    if len(actual) != len(rows):
        raise ValueError("target album IDs differ from frozen inventory")
    linked = Counter()
    for album_id, raw, core, edition, date_played in rows:
        live = actual[album_id]
        if live.event != raw:
            raise ValueError(f"raw EV changed for album {album_id}")
        if live.date_played != date_played:
            raise ValueError(f"date_played changed for album {album_id}")
        if live.event_edition_id is not None and live.event_id is None:
            raise ValueError(f"orphan edition for album {album_id}")
        if live.event_id is not None:
            linked[core] += 1
    return {"counts": dict(linked), "rows": actual}


def run(engine, plan: dict, *, apply: bool, approved_sha256: str | None = None) -> dict:
    digest = hashlib.sha256(json.dumps({key: value for key, value in plan.items() if key != "sha256"},
                                       ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    if plan.get("sha256") != digest:
        raise ValueError("plan SHA-256 does not match content")
    if apply and approved_sha256 != plan["sha256"]:
        raise ValueError("approved plan SHA-256 differs from exact plan")
    for album_id, _raw, _core, edition, _date in plan["albums"]:
        if album_id in _TYPE_HOLD_IDS:
            raise ValueError(f"reviewed event type hold for album {album_id}")
        if album_id in _EDITION_HOLD_IDS and edition is not None:
            raise ValueError(f"reviewed event edition hold for album {album_id}")
    series_names = plan.get("series_names", SERIES)
    if set(plan["selected_series"]) - set(series_names):
        raise ValueError("plan has series without canonical names")
    require_existing_types = set(plan.get("require_existing_types", []))
    series_aliases = plan.get("series_aliases", {})
    with Session(engine) as db:
        with db.begin():
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums IN SHARE ROW EXCLUSIVE MODE"))
                db.execute(text("LOCK TABLE kifu_events, kifu_event_editions IN SHARE ROW EXCLUSIVE MODE"))
            live_state = _check_live(db, plan)
            existing = defaultdict(list)
            for item in db.execute(select(KifuEvent.id, KifuEvent.canonical_name)).all():
                existing[item.canonical_name].append(item.id)
            aliases = defaultdict(set)
            normalized_aliases = defaultdict(set)
            for item in db.execute(select(KifuEventAlias.event_id, KifuEventAlias.alias,
                                          KifuEventAlias.normalized_alias)).all():
                aliases[item.alias].add(item.event_id)
                normalized_aliases[item.normalized_alias].add(item.event_id)
            event_ids = {}
            to_create = []
            cores_by_name = defaultdict(list)
            for core in plan["selected_series"]:
                cores_by_name[series_names[core]].append(core)
            for name, cores in cores_by_name.items():
                matches = set(existing[name]) | aliases[name]
                for core in cores:
                    matches |= aliases[core]
                if len(matches) == 1:
                    event_ids.update({core: next(iter(matches)) for core in cores})
                elif matches:
                    raise ValueError(f"multiple existing event IDs or aliases for {name}")
                elif any(core in require_existing_types for core in cores):
                    raise ValueError(f"required existing event ID is absent for {core}")
                elif "Oteai" in cores:
                    raise ValueError("Oteai requires an existing confirmed event ID")
                else:
                    to_create.append(name)
            for album_id, raw, core, edition, date_played in plan["albums"]:
                current_event_id = live_state["rows"][album_id].event_id
                if current_event_id is not None and current_event_id != event_ids.get(core):
                    raise ValueError(f"existing album {album_id} has a different event type")
            existing_editions = defaultdict(list)
            edition_by_id = {}
            if event_ids:
                for item in db.execute(select(KifuEventEdition.id, KifuEventEdition.event_id,
                                              KifuEventEdition.edition_number, KifuEventEdition.year)
                                       .where(KifuEventEdition.event_id.in_(event_ids.values()))).all():
                    key = (item.event_id, "edition_number", item.edition_number) if item.edition_number else (
                        item.event_id, "year", item.year)
                    existing_editions[key].append(item.id)
                    edition_by_id[item.id] = key
            for album_id, raw, core, pair, date_played in plan["albums"]:
                current = live_state["rows"][album_id]
                if current.event_edition_id is not None:
                    expected = (event_ids[core], pair[0], pair[1]) if pair else None
                    if edition_by_id.get(current.event_edition_id) != expected:
                        raise ValueError(f"existing edition conflict on album {album_id}")
            needed_editions = {(series_names[core], tuple(edition))
                               for _, _, core, edition, _ in plan["albums"] if edition}
            report = {"plan_sha256": plan["sha256"], "selected_series": plan["selected_series"],
                      "album_count": len(plan["albums"]), "existing_links": live_state["counts"],
                      "new_type_count": len(to_create), "distinct_edition_keys": len(needed_editions),
                      "database_mode": "apply" if apply else "dry_run"}
            new_aliases = []
            for core, spellings in series_aliases.items():
                if core not in event_ids and series_names[core] not in to_create:
                    raise ValueError(f"aliases refer to absent series: {core}")
                for spelling in spellings:
                    if not isinstance(spelling, str) or not spelling.strip():
                        raise ValueError("empty event alias")
                    current_ids = aliases[spelling]
                    if current_ids and current_ids != {event_ids.get(core)}:
                        raise ValueError(f"event alias conflicts with another type: {spelling}")
                    normalized = unicodedata.normalize("NFKC", spelling).casefold().strip()
                    normalized_ids = normalized_aliases[normalized]
                    if normalized_ids and normalized_ids != {event_ids.get(core)}:
                        raise ValueError(f"normalized event alias conflicts with another type: {spelling}")
                    if not normalized_ids:
                        new_aliases.append((core, spelling))
                        normalized_aliases[normalized] = {event_ids.get(core)}
            report["new_alias_count"] = len(new_aliases)
            if not apply:
                return report
            for name in to_create:
                event = KifuEvent(canonical_name=name)
                db.add(event)
                db.flush()
                event_ids.update({core: event.id for core in cores_by_name[name]})
            for core, spelling in new_aliases:
                normalized = unicodedata.normalize("NFKC", spelling).casefold().strip()
                db.add(KifuEventAlias(event_id=event_ids[core], alias=spelling, normalized_alias=normalized))
            db.flush()
            edition_ids = {}
            for name, pair in sorted(needed_editions):
                field, number = pair
                event_id = event_ids[cores_by_name[name][0]]
                ids = existing_editions[(event_id, field, number)]
                if len(ids) > 1:
                    raise ValueError(f"duplicate existing edition for {name}: {pair}")
                if ids:
                    edition_ids[(name, pair)] = ids[0]
                else:
                    edition = KifuEventEdition(event_id=event_id, **{field: number})
                    db.add(edition)
                    db.flush()
                    edition_ids[(name, pair)] = edition.id
            updates = 0
            for album_id, raw, core, pair, date_played in plan["albums"]:
                current_event_id = live_state["rows"][album_id].event_id
                values = {"event_id": event_ids[core]}
                if pair:
                    values["event_edition_id"] = edition_ids[(series_names[core], tuple(pair))]
                if current_event_id is not None:
                    # Keep an already linked album's edition intact unless it
                    # was explicitly absent and this exact key is available.
                    live = db.get(KifuAlbum, album_id)
                    if live.event_edition_id is not None:
                        if pair and live.event_edition_id != values["event_edition_id"]:
                            raise ValueError(f"existing edition conflict on album {album_id}")
                        continue
                result = db.execute(update(KifuAlbum).where(KifuAlbum.id == album_id,
                                                             KifuAlbum.event == raw,
                                                             KifuAlbum.date_played == date_played,
                                                             KifuAlbum.event_id == current_event_id).values(**values))
                if result.rowcount != 1:
                    raise ValueError(f"album {album_id} changed during apply")
                updates += 1
            report["updated_albums"] = updates
            report["event_ids"] = event_ids
            return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--series", nargs="+", choices=sorted(SERIES), default=sorted(SERIES))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    raw = args.inventory.read_bytes()
    payload = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    plan = build_plan(json.loads(payload), hashlib.sha256(raw).hexdigest(), selected=set(args.series))
    engine = create_engine(args.database_url)
    try:
        result = run(engine, plan, apply=args.apply, approved_sha256=args.approved_plan_sha256)
    finally:
        engine.dispose()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
