"""Read-only snapshot of raw kifu names and their dataset provenance.

The hash covers selected album columns and source-link columns in fixed order.
Each row is a UTF-8 JSON array with explicit JSON nulls, prefixed by its row
type. SGF content is read only for albums with reviewed event selections;
files at source_path are never read.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata

from sqlalchemy import select

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuAlbumSource, KifuEventSelectionBatch, KifuSource,
)


NAME_FIELDS = ("player_black", "player_white", "event", "round_name", "black_rank", "white_rank")
IDENTITY_FIELDS = ("black_player_id", "white_player_id", "event_id")
ALBUM_COLUMNS = (
    KifuAlbum.id,
    KifuAlbum.duplicate_of_id,
    KifuAlbum.player_black,
    KifuAlbum.player_white,
    KifuAlbum.event,
    KifuAlbum.round_name,
    KifuAlbum.black_rank,
    KifuAlbum.white_rank,
    KifuAlbum.black_player_id,
    KifuAlbum.white_player_id,
    KifuAlbum.event_id,
    KifuAlbum.date_played,
    KifuAlbum.source_path,
    KifuAlbum.source,
)
ALBUM_KEYS = tuple(column.key for column in ALBUM_COLUMNS)
SOURCE_COLUMNS = (
    KifuAlbumSource.id,
    KifuAlbumSource.album_id,
    KifuAlbumSource.source_id,
    KifuSource.source_key,
    KifuAlbumSource.origin_path,
    KifuAlbumSource.match_method,
)
ASSOCIATION_COLUMNS = (
    "id",
    "duplicate_of_id",
    "player_black",
    "player_white",
    "event",
    "round_name",
    "black_rank",
    "white_rank",
    "date_played",
    "black_player_id",
    "white_player_id",
    "event_id",
    "sources",
)
SOURCE_LINK_COLUMNS = ("id", "source_id", "source_key", "origin_path", "match_method")
SELECTION_COLUMNS = (
    "album_id", "selected_raw", "sgf_sha256", "reviewer_id", "reviewed_at", "batch_id", "bundle_sha256",
)


def _new_scope():
    return {
        "album_ids": [],
        "values": {field: defaultdict(lambda: [0, 0]) for field in (*NAME_FIELDS, "player")},
        "identity_ids": {field: Counter() for field in IDENTITY_FIELDS},
        "era": Counter(),
        "script": {field: Counter() for field in NAME_FIELDS},
        "sgf_source": Counter(),
    }


def _script_type(value):
    if not value:
        return "empty"
    scripts = set()
    for char in value:
        code = ord(char)
        character_name = unicodedata.name(char, "")
        if character_name.startswith(("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH")):
            scripts.add("han")
        elif 0x3040 <= code <= 0x30FF:
            scripts.add("kana")
        elif 0xAC00 <= code <= 0xD7AF or 0x1100 <= code <= 0x11FF:
            scripts.add("hangul")
        elif 0x0400 <= code <= 0x052F:
            scripts.add("cyrillic")
        elif "LATIN" in character_name and char.isalpha():
            scripts.add("latin")
        elif char.isalpha():
            scripts.add("other")
    if not scripts:
        return "other"
    return next(iter(scripts)) if len(scripts) == 1 else "mixed"


def _era(value):
    match = re.match(r"^(\d{4})", value or "")
    if not match:
        return "unknown"
    year = int(match.group(1))
    return f"{year // 10 * 10}s" if year else "unknown"


def _record(scope, album):
    album_id = album["id"]
    scope["album_ids"].append(album_id)
    for field in NAME_FIELDS:
        value = album[field]
        entry = scope["values"][field][value]
        entry[0] += 1
        entry[1] += 1
        scope["script"][field][_script_type(value)] += 1
    for field in ("player_black", "player_white"):
        entry = scope["values"]["player"][album[field]]
        entry[0] += 1
    for value in {album["player_black"], album["player_white"]}:
        scope["values"]["player"][value][1] += 1
    for field in IDENTITY_FIELDS:
        scope["identity_ids"][field]["null" if album[field] is None else str(album[field])] += 1
    scope["era"][_era(album["date_played"])] += 1
    scope["sgf_source"][album["source"]] += 1


def _value_rows(entries):
    return [
        {"value": value, "occurrences": count, "affected_games": games}
        for value, (count, games) in sorted(
            entries.items(), key=lambda item: (item[0] is not None, (item[0] or "").encode("utf-8"))
        )
    ]


def _finish_scope(scope):
    return {
        "album_ids": scope["album_ids"],
        "values": {field: _value_rows(entries) for field, entries in scope["values"].items()},
        "identity_ids": {field: dict(sorted(counts.items())) for field, counts in scope["identity_ids"].items()},
    }


def _hash_row(hasher, prefix, values):
    hasher.update(prefix)
    hasher.update(json.dumps(list(values), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    hasher.update(b"\n")


def _selection_supplement(conn):
    """Return the approved live-SGF subset, retaining an empty v3 scope on drift."""
    from katrain.core.sgf_parser import SGF, ParseError
    from katrain.web.kifu.event_selection import (
        audited_selection_images, selected_second_gn, selection_matches_audit,
    )
    from katrain.web.kifu.provenance import classify_source_path

    table = KifuAlbumEventSelection.__table__
    columns = tuple(table.c)
    query = (
        select(*columns, KifuAlbum.sgf_content, KifuAlbum.event, KifuAlbum.source_path)
        .join(KifuAlbum, KifuAlbumEventSelection.album_id == KifuAlbum.id)
        .order_by(KifuAlbumEventSelection.album_id)
    )
    rows = []
    seen = False
    audited_batches = {}
    for result in conn.execute(query):
        seen = True
        selection = dict(zip((column.key for column in columns), result[:len(columns)]))
        sgf_content, old_event, source_path = result[len(columns):]
        batch_id = selection["batch_id"]
        if batch_id not in audited_batches:
            batch = conn.execute(select(KifuEventSelectionBatch.__table__).where(
                KifuEventSelectionBatch.id == batch_id)).mappings().one_or_none()
            audited_batches[batch_id] = (batch, audited_selection_images(batch) if batch is not None else None)
        batch, images = audited_batches[batch_id]
        if not (
            selection_matches_audit(selection, images) and old_event == "GNUGo3.8"
            and isinstance(sgf_content, str)
            and hashlib.sha256(sgf_content.encode("utf-8")).hexdigest() == selection["sgf_sha256"]
        ):
            continue
        try:
            selected = selected_second_gn(SGF.parse_sgf(sgf_content), classify_source_path(source_path))
        except (ParseError, ValueError, TypeError, AttributeError, IndexError):
            continue
        if selected != selection["selected_raw"]:
            continue
        rows.append([selection["album_id"], selected, selection["sgf_sha256"], selection["reviewer_id"],
                     selection["reviewed_at"].isoformat(), batch_id, batch["bundle_sha256"]])
    if not seen:
        return None
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (1, SELECTION_COLUMNS))
    for row in rows:
        _hash_row(digest, b"E", row)
    return {"selection_format": 1, "columns": list(SELECTION_COLUMNS), "rows": rows, "sha256": digest.hexdigest()}


def build_inventory(engine, *, batch_size=1000):
    """Scan one consistent database snapshot in ID order without writing data."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    scopes = {name: _new_scope() for name in ("all", "visible", "sample")}
    source_stats = {name: defaultdict(lambda: [0, set()]) for name in scopes}
    linked_ids = {name: set() for name in scopes}
    album_associations = {}
    hasher = hashlib.sha256()
    selection = None
    with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            conn = conn.execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True)
            conn.begin()
        elif engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA query_only=ON")
            conn.exec_driver_sql("BEGIN")
        else:
            raise ValueError("Only PostgreSQL and SQLite are supported")
        snapshot_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            if engine.dialect.name == "postgresql":
                isolation = conn.exec_driver_sql("SHOW transaction_isolation").scalar_one()
                read_only = conn.exec_driver_sql("SHOW transaction_read_only").scalar_one()
                if isolation.lower() != "repeatable read" or read_only.lower() != "on":
                    raise RuntimeError(f"Inventory requires REPEATABLE READ READ ONLY, got {isolation} / {read_only}")
            last_id = -1
            while True:
                rows = conn.execute(
                    select(*ALBUM_COLUMNS).where(KifuAlbum.id > last_id).order_by(KifuAlbum.id).limit(batch_size)
                ).all()
                if not rows:
                    break
                for row in rows:
                    album = dict(zip(ALBUM_KEYS, row))
                    _hash_row(hasher, b"A", row)
                    album_associations[album["id"]] = [
                        *(album[field] for field in ASSOCIATION_COLUMNS[:-1]),
                        [],
                    ]
                    _record(scopes["all"], album)
                    if album["duplicate_of_id"] is None:
                        _record(scopes["visible"], album)
                    if album["id"] % 20 == 0:
                        _record(scopes["sample"], album)
                last_id = rows[-1][0]

            scope_ids = {name: set(scope["album_ids"]) for name, scope in scopes.items()}
            last_id = -1
            while True:
                rows = conn.execute(
                    select(*SOURCE_COLUMNS)
                    .join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
                    .where(KifuAlbumSource.id > last_id)
                    .order_by(KifuAlbumSource.id)
                    .limit(batch_size)
                ).all()
                if not rows:
                    break
                for source_id, album_id, dataset_id, key, path, method in rows:
                    _hash_row(hasher, b"S", (source_id, album_id, dataset_id, key, path, method))
                    album_associations[album_id][-1].append([source_id, dataset_id, key, path, method])
                    for name in scopes:
                        if album_id in scope_ids[name]:
                            entry = source_stats[name][key]
                            entry[0] += 1
                            entry[1].add(album_id)
                            linked_ids[name].add(album_id)
                last_id = rows[-1][0]
            selection = _selection_supplement(conn)
            if selection is not None:
                _hash_row(hasher, b"E", (selection["selection_format"], selection["sha256"]))
        finally:
            conn.rollback()
            if engine.dialect.name == "sqlite":
                conn.exec_driver_sql("PRAGMA query_only=OFF")
                conn.rollback()

    return {
        "inventory_format": 3 if selection is not None else 2,
        **({"event_selection": selection} if selection is not None else {}),
        "database_identifier": engine.url.render_as_string(hide_password=True),
        "snapshot_time": snapshot_time,
        "counts": {name: len(scope["album_ids"]) for name, scope in scopes.items()},
        "detail_ids": scopes["all"]["album_ids"],
        "association_columns": list(ASSOCIATION_COLUMNS),
        "source_link_columns": list(SOURCE_LINK_COLUMNS),
        "album_associations": list(album_associations.values()),
        "scopes": {name: _finish_scope(scope) for name, scope in scopes.items()},
        "distinct_values": {
            name: {field: len(entries) for field, entries in scope["values"].items()} for name, scope in scopes.items()
        },
        "source_stats": {
            name: {key: {"links": count, "affected_games": len(ids)} for key, (count, ids) in sorted(entries.items())}
            for name, entries in source_stats.items()
        },
        "unlinked_source_counts": {name: len(scope_ids[name] - linked_ids[name]) for name in scopes},
        "sgf_source_stats": {
            name: [
                {"value": value, "occurrences": count}
                for value, count in sorted(
                    scope["sgf_source"].items(), key=lambda item: (item[0] is not None, (item[0] or "").encode("utf-8"))
                )
            ]
            for name, scope in scopes.items()
        },
        "era_stats": {name: dict(sorted(scope["era"].items())) for name, scope in scopes.items()},
        "script_stats": {
            name: {field: dict(sorted(counts.items())) for field, counts in scope["script"].items()}
            for name, scope in scopes.items()
        },
        "sha256": hasher.hexdigest(),
    }
