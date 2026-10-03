"""Read-only current eleven-language progress; run after each approved DB update.

Entity totals count canonical catalog identities, including currently unused ones.
Album totals include every stored album (including duplicate_of_id rows), matching
name_coverage. Empty event slots follow identity's explicit hidden approval.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, defer

from katrain.web.core.models_db import KifuAlbum, KifuEvent, KifuEventName, KifuNameBatch, KifuPlayer, KifuPlayerName
from katrain.web.kifu.identity import (
    LANGUAGES,
    _approved_names,
    _approved_raw_event_names,
    _approved_raw_player_names,
    _qualified_name_rows,
    live_event_selections,
    obscured_program_event_ids,
    strict_slot_approvals,
)


def progress_report(engine, *, environment="local", batch_id=None, batch_size=500):
    """Use production approval resolution in one consistent, read-only snapshot."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    languages = sorted(LANGUAGES)
    report = {
        "format": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "database_identity": f"{engine.url.host or ''}:{engine.url.port or ''}/{engine.url.database or ''}",
        "languages": languages,
        "batch_id": batch_id,
    }
    connection = engine.connect().execution_options(
        isolation_level="REPEATABLE READ" if engine.dialect.name == "postgresql" else "SERIALIZABLE"
    )
    try:
        with connection.begin():
            if engine.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            with Session(bind=connection) as db:
                if batch_id is not None:
                    batch = db.get(KifuNameBatch, batch_id)
                    if batch is None or batch.status != "applied":
                        raise ValueError(f"name batch {batch_id} is not applied in this database")
                    report["bundle_sha256"] = batch.bundle_sha256
                for key, entity, name_model, owner in (
                    ("players", KifuPlayer, KifuPlayerName, "player_id"),
                    ("events", KifuEvent, KifuEventName, "event_id"),
                ):
                    ids = set(db.scalars(db.query(entity.id).statement))
                    approved = {entity_id: set() for entity_id in ids}
                    rows = _qualified_name_rows(
                        db, _approved_names(db, name_model, owner), name_model, owner
                    )
                    for name, _ in rows:
                        if name.lang in LANGUAGES:
                            approved[getattr(name, owner)].add(name.lang)
                    report[key] = {
                        "total": len(ids),
                        "complete_11": sum(langs == LANGUAGES for langs in approved.values()),
                        "by_language": {lang: sum(lang in langs for langs in approved.values()) for lang in languages},
                    }
                slots = ("black", "white", "event")
                album_stats = {
                    "total": 0, "complete_11": 0,
                    "by_slot_complete_11": dict.fromkeys(slots, 0),
                    "both_players_complete_11": 0,
                    "by_language": {lang: {"all_slots": 0, **dict.fromkeys(slots, 0)} for lang in languages},
                }
                raw_slots = {"players": {}, "events": {}}
                last_id = 0
                while True:
                    albums = (
                        db.query(KifuAlbum).options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
                        .filter(KifuAlbum.id > last_id).order_by(KifuAlbum.id).limit(batch_size).all()
                    )
                    if not albums:
                        break
                    selected = live_event_selections(db, albums)
                    obscured = obscured_program_event_ids(db, albums, selected_events=selected)
                    counts = {album.id: [0, 0, 0] for album in albums}
                    for lang in languages:
                        approvals = strict_slot_approvals(
                            db, albums, lang, selected_events=selected, obscured_event_ids=obscured
                        )
                        for album in albums:
                            present = [approval is not None for approval in approvals[album.id]]
                            album_stats["by_language"][lang]["all_slots"] += all(present)
                            for index, slot in enumerate(slots):
                                album_stats["by_language"][lang][slot] += present[index]
                                counts[album.id][index] += present[index]
                    for album in albums:
                        event_raw, event_id = selected.get(album.id, (album.event, album.event_id))
                        for kind, raw, owner_id, index in (
                            ("players", album.player_black, album.black_player_id, 0),
                            ("players", album.player_white, album.white_player_id, 1),
                            ("events", event_raw, event_id, 2),
                        ):
                            if not owner_id and raw and raw.strip():
                                complete = counts[album.id][index] == len(languages)
                                raw_slots[kind][raw] = raw_slots[kind].get(raw, True) and complete
                    for count in counts.values():
                        complete = [value == len(languages) for value in count]
                        album_stats["complete_11"] += all(complete)
                        album_stats["both_players_complete_11"] += all(complete[:2])
                        for slot, value in zip(slots, complete):
                            album_stats["by_slot_complete_11"][slot] += value
                    album_stats["total"] += len(albums)
                    last_id = albums[-1].id
                report["albums"] = album_stats
                report["unlinked_raw_values"] = {}
                for key, values in raw_slots.items():
                    approved_languages = defaultdict(set)
                    resolver = _approved_raw_player_names if key == "players" else _approved_raw_event_names
                    raw_values = sorted(values)
                    for start in range(0, len(raw_values), batch_size):
                        for name, raw, _ in resolver(db, values=set(raw_values[start:start + batch_size])):
                            approved_languages[raw].add(name.lang)
                    report["unlinked_raw_values"][key] = {
                        "total": len(values),
                        "complete_11": sum(approved_languages[raw] == LANGUAGES for raw in values),
                        "complete_11_all_occurrences": sum(values.values()),
                    }
    finally:
        connection.close()
    for key in ("players", "events", "albums"):
        values = report[key]
        values["complete_11_ratio"] = values["complete_11"] / values["total"] if values["total"] else None
    for values in report["unlinked_raw_values"].values():
        values["complete_11_ratio"] = values["complete_11"] / values["total"] if values["total"] else None
    return report


def progress_delta(current, previous):
    """Show numeric changes since a prior run; negative changes remain visible."""
    for key in ("format", "languages", "environment", "database_identity"):
        if previous.get(key) != current[key]:
            raise ValueError(f"previous report {key} differs")

    def subtract(new, old):
        return {key: subtract(value, old[key]) if isinstance(value, dict) else value - old[key]
                for key, value in new.items() if key != "complete_11_ratio"}

    return {
        key: subtract(current[key], previous[key])
        for key in ("players", "events", "albums", "unlinked_raw_values")
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--environment", choices=("test", "prod"), required=True)
    parser.add_argument("--batch-id", type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--batch-size", default=500, type=int)
    args = parser.parse_args(argv)
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else None
    engine = create_engine(args.database_url)
    try:
        report = progress_report(engine, environment=args.environment, batch_id=args.batch_id,
                                 batch_size=args.batch_size)
    finally:
        engine.dispose()
    if previous is not None:
        report["delta"] = progress_delta(report, previous)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {key: report[key] for key in ("players", "events", "albums", "unlinked_raw_values")}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
