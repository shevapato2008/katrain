"""Read-only coverage audit of the names users would see on every kifu album."""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from typing import Callable

from sqlalchemy import func, text
from sqlalchemy.orm import Session, defer

from katrain.web.core.models_db import KifuAlbum, KifuAlbumEventSelection
from katrain.web.kifu.identity import (
    LANGUAGES,
    live_event_selections,
    obscured_program_event_ids,
    resolve_strict_display,
    strict_display_maps,
    strict_slot_approvals,
)


_FIELDS = (
    "id", "duplicate_of_id", "player_black", "player_white", "event", "round_name",
    "black_rank", "white_rank", "date_played", "black_player_id", "white_player_id", "event_id",
)
_SLOTS = ("black", "white", "event")


def _era(date: str | None) -> str:
    if not date or len(date) < 4 or not date[:4].isdigit():
        return "unknown"
    year = int(date[:4])
    if year < 1900:
        return "pre1900"
    if year < 1950:
        return "1900-1949"
    if year < 2000:
        return "1950-1999"
    return "2000+"


def _row_matches(album: KifuAlbum, expected: dict, sources: list[str]) -> bool:
    return all(getattr(album, field) == expected[field] for field in _FIELDS) and sources == sorted(
        {source[2] for source in expected["sources"]}
    )


def coverage_report(
    engine,
    inventory: dict,
    *,
    languages: tuple[str, ...] = tuple(sorted(LANGUAGES)),
    batch_size: int = 500,
    missing_sink: Callable[[dict], None] | None = None,
    max_examples: int = 50,
) -> dict:
    """Audit one pinned inventory against one read-only DB snapshot.

    Missing decisions stay missing even when the strict API renders a localized
    placeholder. The caller can stream every missing slot to a controlled file.
    """

    if inventory.get("inventory_format") not in {2, 3} or len(str(inventory.get("sha256", ""))) != 64:
        raise ValueError("inventory format 2 or 3 with SHA-256 required")
    pinned_selection = inventory.get("event_selection") if inventory["inventory_format"] == 3 else None
    if inventory["inventory_format"] == 3 and not (
        isinstance(pinned_selection, dict)
        and pinned_selection.get("selection_format") == 1
        and isinstance(pinned_selection.get("columns"), list)
        and isinstance(pinned_selection.get("rows"), list)
    ):
        raise ValueError("inventory event selection supplement is incomplete")
    columns = inventory.get("association_columns")
    rows = inventory.get("album_associations")
    if not isinstance(columns, list) or not isinstance(rows, list) or not set((*_FIELDS, "sources")) <= set(columns):
        raise ValueError("inventory associations are incomplete")
    if not languages or len(languages) != len(set(languages)) or not set(languages) <= LANGUAGES:
        raise ValueError("languages must be distinct product languages")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    stats = {
        lang: {"slots": 0, "approved": 0, "missing": 0, "by_decision": Counter(),
               "by_source": defaultdict(Counter), "by_era": defaultdict(Counter)}
        for lang in languages
    }
    examples: list[dict] = []
    missing_hashes = {lang: sha256() for lang in languages}
    observed = 0
    selection_drift = 0
    selection_snapshot_sha256 = None
    selection_sgf_sha256 = sha256()

    # PostgreSQL holds the full report in one REPEATABLE READ, READ ONLY view.
    connection = engine.connect().execution_options(
        isolation_level="REPEATABLE READ" if engine.dialect.name == "postgresql" else "SERIALIZABLE"
    )
    try:
        with connection.begin():
            if engine.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            db = Session(bind=connection)
            try:
                from katrain.web.kifu.name_inventory import _selection_supplement

                current_selection = _selection_supplement(connection)
                pinned_columns = pinned_selection["columns"] if pinned_selection else []
                pinned_rows = {
                    dict(zip(pinned_columns, row))["album_id"]: row for row in pinned_selection["rows"]
                } if pinned_selection else {}
                live_columns = current_selection["columns"] if current_selection else []
                live_rows = {
                    dict(zip(live_columns, row))["album_id"]: row for row in current_selection["rows"]
                } if current_selection else {}
                all_selection_ids = set(db.scalars(db.query(KifuAlbumEventSelection.album_id).statement))
                selection_drift = sum(
                    pinned_rows.get(album_id) != live_rows.get(album_id) or album_id not in live_rows
                    for album_id in set(pinned_rows) | set(live_rows) | all_selection_ids
                )
                selection_snapshot_sha256 = current_selection["sha256"] if current_selection else None
                for album_id, raw, pinned_hash, content in (
                    db.query(
                        KifuAlbumEventSelection.album_id, KifuAlbumEventSelection.selected_raw,
                        KifuAlbumEventSelection.sgf_sha256, KifuAlbum.sgf_content,
                    )
                    .join(KifuAlbum, KifuAlbum.id == KifuAlbumEventSelection.album_id)
                    .order_by(KifuAlbumEventSelection.album_id)
                ):
                    selection_sgf_sha256.update(
                        (json.dumps(
                            [album_id, raw, pinned_hash, sha256(content.encode("utf-8")).hexdigest()],
                            ensure_ascii=False, separators=(",", ":"),
                        ) + "\n").encode("utf-8")
                    )
                if db.query(func.count(KifuAlbum.id)).scalar() != len(rows):
                    raise RuntimeError("snapshot drift: album count differs from inventory")
                for start in range(0, len(rows), batch_size):
                    expected = [dict(zip(columns, row)) for row in rows[start:start + batch_size]]
                    albums = (
                        db.query(KifuAlbum)
                        .options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
                        .filter(KifuAlbum.id.in_([item["id"] for item in expected]))
                        .order_by(KifuAlbum.id)
                        .all()
                    )
                    if len(albums) != len(expected):
                        raise RuntimeError("snapshot drift: inventory album ID is absent")
                    selected_events = live_event_selections(db, albums)
                    obscured_event_ids = obscured_program_event_ids(db, albums, selected_events=selected_events)
                    for lang in languages:
                        maps = strict_display_maps(db, albums, lang, selected_events=selected_events)
                        approvals = strict_slot_approvals(
                            db, albums, lang, obscured_event_ids=obscured_event_ids, selected_events=selected_events
                        )
                        sources = maps[3]
                        for album, item in zip(albums, expected):
                            if not _row_matches(album, item, sources.get(album.id, [])):
                                raise RuntimeError(f"snapshot drift: album {item['id']} metadata or sources changed")
                            displayed = resolve_strict_display(
                                album, lang, maps[0], maps[1], maps[2], maps[4], maps[5],
                                obscured_event_ids=obscured_event_ids, selected_events=selected_events,
                            )
                            for slot, approval, value in zip(_SLOTS, approvals[album.id], displayed):
                                aggregate = stats[lang]
                                aggregate["slots"] += 1
                                era = _era(album.date_played)
                                keys = sources.get(album.id, []) or ["unattributed"]
                                if approval is None:
                                    aggregate["missing"] += 1
                                    aggregate["by_era"][era]["missing"] += 1
                                    for source in keys:
                                        aggregate["by_source"][source]["missing"] += 1
                                    gap = {"album_id": album.id, "lang": lang, "slot": slot, "display": value}
                                    missing_hashes[lang].update(
                                        (
                                            json.dumps(gap, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                                            + "\n"
                                        ).encode("utf-8")
                                    )
                                    if len(examples) < max_examples:
                                        examples.append(gap)
                                    if missing_sink:
                                        missing_sink(gap)
                                else:
                                    aggregate["approved"] += 1
                                    aggregate["by_decision"][approval[0]] += 1
                                    aggregate["by_era"][era]["approved"] += 1
                                    for source in keys:
                                        aggregate["by_source"][source]["approved"] += 1
                    observed += len(albums)
            finally:
                db.close()
    finally:
        connection.close()

    def plain(values):
        result = {}
        for key, value in values.items():
            if isinstance(value, int):
                result[key] = value
            elif isinstance(value, Counter):
                result[key] = dict(value)
            else:
                result[key] = {item: dict(counts) for item, counts in value.items()}
        return result

    return {
        "inventory_sha256": inventory["sha256"],
        "albums": observed,
        "languages": {lang: plain(values) for lang, values in stats.items()},
        "missing_sha256": sha256(
            "".join(lang + ":" + missing_hashes[lang].hexdigest() + "\n" for lang in sorted(languages)).encode("utf-8")
        ).hexdigest(),
        "missing_examples": examples,
        "event_selection_drift": selection_drift,
        "event_selection_scope_sha256": selection_snapshot_sha256,
        "event_selection_sha256": selection_sgf_sha256.hexdigest(),
        "complete": (set(languages) == LANGUAGES and selection_drift == 0
                     and all(stats[lang]["missing"] == 0 for lang in languages)),
    }
