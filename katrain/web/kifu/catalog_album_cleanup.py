"""Exact-preimage cleanup of album rows whose original SGF lacks a player name.

The caller must save the returned plan as a durable backup before ``run(...,
apply=True)``. No table outside the named album dependencies is modified.
"""

import hashlib
import json
from datetime import date, datetime

from sqlalchemy import bindparam, inspect, text

from katrain.core.sgf_parser import SGF


FORMAT = "kifu-album-cleanup-v1"
PLACEHOLDERS = {"", "unknown", "black", "white", "?", "???", "初段", "b", "w"}
PATCH_COLUMNS = {"player_black", "player_white", "black_rank", "white_rank", "black_player_id", "white_player_id"}
CHILD_TABLES = {
    "kifu_album_sources": ("album_id",),
    "kifu_dedup_changes": ("album_id", "duplicate_of_id_before", "duplicate_of_id_after"),
    "kifu_album_event_selections": ("album_id",),
    "kifu_analysis_jobs": ("album_id",),
    "kifu_analysis_moves": ("job_id",),
}


def _json(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


def _digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _rows(conn, table, where, ids):
    if not ids:
        return []
    order = "album_id" if table == "kifu_album_event_selections" else "id"
    statement = text(f"SELECT * FROM {table} WHERE {where} ORDER BY {order}").bindparams(bindparam("ids", expanding=True))
    return [_json(dict(row)) for row in conn.execute(statement, {"ids": sorted(ids)}).mappings()]


def _snapshot(conn, delete_ids, patch_ids):
    tables = set(inspect(conn).get_table_names())
    target_ids = sorted(set(delete_ids) | set(patch_ids))
    absent = set(CHILD_TABLES) - tables
    if absent:
        raise ValueError(f"required dependency tables absent: {sorted(absent)}")
    albums = _rows(conn, "kifu_albums", "id IN :ids", target_ids)
    if {row["id"] for row in albums} != set(target_ids):
        raise ValueError("target album missing")
    deleted = set(delete_ids)
    dependencies = {}
    for table, columns in CHILD_TABLES.items():
        if table == "kifu_analysis_moves":
            continue
        where = " OR ".join(f"{column} IN :ids" for column in columns)
        dependencies[table] = _rows(conn, table, where, deleted)
    job_ids = {row["id"] for row in dependencies["kifu_analysis_jobs"]}
    dependencies["kifu_analysis_moves"] = _rows(conn, "kifu_analysis_moves", "job_id IN :ids", job_ids)
    referring_albums = _rows(conn, "kifu_albums", "duplicate_of_id IN :ids", deleted)
    survivors = [row for row in referring_albums if row["id"] not in deleted]
    if survivors:
        raise ValueError(f"surviving albums point to deleted albums: {[row['id'] for row in survivors]}")

    # A new FK-bearing table is a changed deletion contract. Require a deliberate
    # implementation update before deleting anything from it.
    allowed = {("kifu_albums", ("duplicate_of_id",))}
    allowed.update((table, columns) for table, columns in CHILD_TABLES.items() if table != "kifu_analysis_moves")
    for table in sorted(tables):
        for fk in inspect(conn).get_foreign_keys(table):
            if fk.get("referred_table") != "kifu_albums":
                continue
            pair = (table, tuple(fk["constrained_columns"]))
            if not any(pair[0] == known[0] and set(pair[1]) <= set(known[1]) for known in allowed):
                raise ValueError(f"unexpected album foreign key: {table}.{pair[1]}")
    return {"albums": albums, "dependencies": dependencies}


def _raw_names(row):
    try:
        root = SGF.parse_sgf(row["sgf_content"])
        return root.get_property("PB"), root.get_property("PW")
    except Exception as exc:
        raise ValueError(f"album {row['id']} SGF cannot be parsed") from exc


def _check_delete_names(row):
    # These observed broken tags can cause a parser to report an absent name.
    # Keep the record for manual repair instead of treating it as nameless.
    if "PB]" in row["sgf_content"] or "PW]" in row["sgf_content"]:
        raise ValueError(f"album {row['id']} has malformed source player brackets")
    black, white = _raw_names(row)
    names = (black, white)
    if any(name is not None and ("[" in name or "]" in name) for name in names):
        raise ValueError(f"album {row['id']} has malformed source player brackets")
    if not any(name is None or name.strip().casefold() in PLACEHOLDERS for name in names):
        raise ValueError(f"album {row['id']} original SGF has two real player names")


def _normalize_patches(patches):
    result = {}
    for patch in patches:
        if not isinstance(patch, dict) or type(patch.get("id")) is not int or patch["id"] <= 0:
            raise ValueError("patch requires a positive integer album id")
        album_id = patch["id"]
        if album_id in result:
            raise ValueError("duplicate patch id")
        supplied = set(patch) - {"id", "black_player_name", "white_player_name"}
        if not supplied or not supplied <= PATCH_COLUMNS:
            raise ValueError(f"unsupported or empty album patch: {album_id}")
        for side in ("black", "white"):
            key = f"{side}_player_id"
            if key in patch and patch[key] is not None and (type(patch[key]) is not int or patch[key] <= 0):
                raise ValueError(f"invalid {key}")
            if f"{side}_player_name" in patch and key not in patch:
                raise ValueError(f"{side}_player_name requires {key}")
        result[album_id] = dict(patch)
    return result


def _check_patches(conn, albums, patches):
    for row in albums:
        patch = patches.get(row["id"])
        if patch is None:
            continue
        black = patch.get("black_player_id", row["black_player_id"])
        white = patch.get("white_player_id", row["white_player_id"])
        if black is not None and black == white:
            raise ValueError(f"album {row['id']} has identical black/white player IDs")
        for side, player_id in (("black", black), ("white", white)):
            if player_id is None:
                continue
            player = conn.execute(text("SELECT canonical_name FROM kifu_players WHERE id=:id"), {"id": player_id}).scalar_one_or_none()
            if player is None:
                raise ValueError(f"album {row['id']} {side} player ID does not exist")
            expected = patch.get(f"{side}_player_name")
            if expected is not None and player != expected:
                raise ValueError(f"album {row['id']} {side} canonical name changed")


def capture(engine, delete_ids, patches=()):
    """Capture full album and dependent row preimages for external gzip backup."""
    ids = sorted(delete_ids)
    if not ids or any(type(value) is not int or value <= 0 for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("delete_ids must be distinct positive integer IDs")
    patch_map = _normalize_patches(patches)
    if set(ids) & set(patch_map):
        raise ValueError("cannot patch and delete the same album")
    with engine.connect() as conn:
        snapshot = _snapshot(conn, ids, patch_map)
        for row in snapshot["albums"]:
            if row["id"] in ids:
                _check_delete_names(row)
        _check_patches(conn, snapshot["albums"], patch_map)
        plan = {"format": FORMAT, "delete_ids": ids, "patches": [patch_map[id_] for id_ in sorted(patch_map)], "snapshot": snapshot}
        plan["sha256"] = _digest(plan)
        return plan


def _lock(conn):
    if conn.dialect.name == "postgresql":
        tables = ["kifu_albums", "kifu_players", *CHILD_TABLES]
        conn.execute(text("LOCK TABLE " + ", ".join(tables) + " IN SHARE ROW EXCLUSIVE MODE"))


def run(engine, plan, *, apply=False):
    """CAS the complete preimage; atomically patch and delete, or roll back a dry run."""
    if plan.get("format") != FORMAT or _digest({key: value for key, value in plan.items() if key != "sha256"}) != plan.get("sha256"):
        raise ValueError("cleanup backup identity or SHA mismatch")
    ids = plan["delete_ids"]
    patches = _normalize_patches(plan["patches"])
    if set(ids) & set(patches):
        raise ValueError("overlapping patch/delete IDs")
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            _lock(conn)
            current = _snapshot(conn, ids, patches)
            if current != plan["snapshot"]:
                raise ValueError("live album/dependency preimage drift")
            for row in current["albums"]:
                if row["id"] in ids:
                    _check_delete_names(row)
            _check_patches(conn, current["albums"], patches)
            rank_changes = 0
            for row in current["albums"]:
                patch = patches.get(row["id"])
                if patch is None:
                    continue
                values = {key: patch[key] for key in PATCH_COLUMNS & patch.keys()}
                rank_changes += sum(key in values and values[key] != row[key] for key in ("black_rank", "white_rank"))
                updated = dict(row, **values)
                values["search_text"] = " ".join(str(updated.get(key) or "") for key in (
                    "player_black", "player_white", "black_rank", "white_rank", "event", "result", "round_name", "date_played", "place", "source"
                )).strip().lower()
                assignments = ", ".join(f"{key}=:{key}" for key in values)
                conn.execute(text(f"UPDATE kifu_albums SET {assignments} WHERE id=:id"), dict(values, id=row["id"]))
            dependencies = current["dependencies"]
            for table in ("kifu_analysis_moves", "kifu_analysis_jobs", "kifu_album_event_selections", "kifu_dedup_changes", "kifu_album_sources"):
                rows = dependencies[table]
                if rows:
                    pk = "album_id" if table == "kifu_album_event_selections" else "id"
                    statement = text(f"DELETE FROM {table} WHERE {pk} IN :ids").bindparams(bindparam("ids", expanding=True))
                    conn.execute(statement, {"ids": [row[pk] for row in rows]})
            statement = text("DELETE FROM kifu_albums WHERE id IN :ids").bindparams(bindparam("ids", expanding=True))
            conn.execute(statement, {"ids": ids})
            result = {"committed": bool(apply), "deleted": len(ids), "updated": len(patches), "rank_changes": rank_changes,
                      "dependencies": {table: len(rows) for table, rows in dependencies.items()}}
            if apply:
                transaction.commit()
            else:
                transaction.rollback()
            return result
        except Exception:
            transaction.rollback()
            raise
