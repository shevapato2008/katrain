#!/usr/bin/env python3
"""Repair reviewed legacy Golaxy provenance without changing game content or timestamps.

Default: scoped, read-only manifest. Names are review hints, never automatic proof.
Use a fresh dedicated session; apply/rollback own its commit or rollback. PostgreSQL
rows are locked for the entire comparison/backup/update transaction.
"""

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import DateTime, String, cast, inspect, or_, select, text, update


class RepairError(ValueError):
    """The reviewed scope or database snapshot no longer permits this repair."""


def _table():
    # Keep runtime database configuration/session creation out of module imports.
    from katrain.web.core.models_db import UserGame

    return UserGame.__table__


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _serial(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _identity(session):
    connection = session.connection()
    engine = connection.engine
    if engine.dialect.name == "postgresql":
        database = list(
            connection.execute(
                text("SELECT current_database(), current_schema(), inet_server_addr()::text, inet_server_port()")
            ).one()
        )
        # URL host/port distinguish proxies and Unix sockets; credentials are excluded.
        database.extend([engine.url.host, engine.url.port])
    elif engine.dialect.name == "sqlite":
        database = list(connection.execute(text("PRAGMA database_list")).all()[0])
        if not database[2]:
            database.append(str(id(engine)))  # In-memory DBs cannot be reused across engines/processes.
        else:
            database[2] = str(Path(database[2]).resolve())
    else:
        raise RepairError("Unsupported database dialect")
    schema = [
        [c["name"], str(c["type"]), c["nullable"], bool(c.get("primary_key"))]
        for c in inspect(connection).get_columns("user_games")
    ]
    return _sha(_json([engine.dialect.name, database, schema]))


def _evidence(row):
    from katrain.core.sgf_parser import SGF

    root = None
    try:
        root = SGF.parse_sgf(row["sgf_content"] or "")
        if root.get_list_property("KTP", []) == ["golaxy"]:
            return "ktp_golaxy"
    except Exception:
        # Malformed/missing SGF cannot provide trusted KTP evidence.
        pass
    names = [row["player_black"], row["player_white"]]
    if root is not None:
        names.extend([root.get_property("PB", ""), root.get_property("PW", "")])
    return "name_hint" if any("[golaxy]" in (name or "").lower() for name in names) else "none"


def _snapshot(row):
    # Hash remaining metadata as well, so rollback refuses even edits that preserved updated_at.
    metadata = {key: _serial(value) for key, value in row.items() if key not in ("platform", "sgf_content")}
    return {
        **{
            key: _serial(row[key])
            for key in ("id", "user_id", "source", "game_type", "platform", "sgf_hash", "updated_at")
        },
        "sgf_content_sha256": _sha(row["sgf_content"] or ""),
        "sgf_content_is_null": row["sgf_content"] is None,
        "metadata_sha256": _sha(_json(metadata)),
        "evidence": _evidence(row),
    }


def dry_run(session, *, user_id=None, game_ids=()):
    """Return all scoped played/platform-NULL rows, including explicitly unknown evidence."""
    game_ids = list(game_ids or ())
    if user_id is None and not game_ids:
        raise RepairError("A user-id or concrete game-id scope is required")
    if any(not isinstance(value, str) or not value.strip() for value in game_ids):
        raise RepairError("Game-id scope must contain concrete IDs")
    table = _table()
    query = select(table).where(table.c.source.in_(("play_ai", "play_human")), table.c.platform.is_(None))
    if user_id is not None:
        query = query.where(table.c.user_id == user_id)
    if game_ids:
        query = query.where(table.c.id.in_(game_ids))
    return {
        "format": "user-game-platform-review-v1",
        "database_identity_sha256": _identity(session),
        "scope": {"user_id": user_id, "game_ids": sorted(set(game_ids))},
        "rows": [_snapshot(row) for row in session.execute(query.order_by(table.c.id)).mappings()],
    }


def _check_document(session, document, kind):
    if document.get("format") != kind:
        raise RepairError("Unrecognized manifest format")
    if document.get("database_identity_sha256") != _identity(session):
        raise RepairError("Database/schema identity differs from the reviewed manifest")
    rows = document.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not row.get("id") for row in rows):
        raise RepairError("Invalid manifest rows")
    if len({row["id"] for row in rows}) != len(rows):
        raise RepairError("Duplicate manifest IDs")
    return rows


def _locked_row(session, game_id):
    table = _table()
    row = session.execute(select(table).where(table.c.id == game_id).with_for_update()).mappings().one_or_none()
    if row is None:
        raise RepairError(f"Game missing: {game_id}")
    return row


def _matches(row, expected, platform):
    actual = _snapshot(row)
    return actual == {**expected, "platform": platform}


def write_private_json(path, document):
    """Create a durable owner-only file, refusing to overwrite any existing path."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _write_platform(session, row, platform):
    table = _table()
    # SQLite ignores FOR UPDATE. Compare every actual original column atomically
    # so edits committed after our snapshot cannot be overwritten on either DB.
    unchanged = []
    for column in table.columns:
        value = row[column.name]
        matches = column == value
        if session.get_bind().dialect.name == "sqlite" and isinstance(column.type, DateTime) and value is not None:
            # SQLite CURRENT_TIMESTAMP omits .000000, unlike bound datetimes.
            # Accept that exact zero-microsecond spelling without rounding times.
            if value.microsecond == 0:
                matches = or_(matches, cast(column, String) == value.strftime("%Y-%m-%d %H:%M:%S"))
        unchanged.append(matches)
    # Explicit updated_at suppresses SQLAlchemy's onupdate=func.now().
    result = session.execute(update(table).where(*unchanged).values(platform=platform, updated_at=row["updated_at"]))
    if result.rowcount != 1:
        raise RepairError(f"Concurrent/missing game: {row['id']}")


def apply_manifest(session, manifest, *, confirmed_game_ids, backup_path):
    """Apply explicit KTP proof and individually confirmed name hints, atomically."""
    try:
        rows = _check_document(session, manifest, "user-game-platform-review-v1")
        scope = manifest.get("scope", {})
        if scope.get("user_id") is None and not scope.get("game_ids"):
            raise RepairError("Manifest has no concrete scope")
        confirmed = set(confirmed_game_ids or ())
        if confirmed - {row["id"] for row in rows}:
            raise RepairError("Confirmed IDs are outside the reviewed manifest")
        selected = [row for row in rows if row.get("evidence") == "ktp_golaxy" or row["id"] in confirmed]
        if not selected:
            raise RepairError("No explicit KTP proof or confirmed game IDs")
        pending = []
        for expected in sorted(selected, key=lambda row: row["id"]):
            if expected.get("source") not in ("play_ai", "play_human") or expected.get("platform") is not None:
                raise RepairError("Only played platform-NULL originals may be repaired")
            if expected.get("evidence") not in ("ktp_golaxy", "name_hint"):
                raise RepairError("No Golaxy evidence for confirmed game")
            if scope.get("user_id") is not None and expected.get("user_id") != scope["user_id"]:
                raise RepairError("Manifest owner is outside scope")
            if scope.get("game_ids") and expected["id"] not in scope["game_ids"]:
                raise RepairError("Manifest game is outside scope")
            current = _locked_row(session, expected["id"])
            if _matches(current, expected, "golaxy"):
                continue  # Already applied, with no intervening edits.
            if not _matches(current, expected, None):
                raise RepairError(f"Game snapshot changed: {expected['id']}")
            pending.append((current, expected))
        if pending:
            backup = {
                "format": "user-game-platform-backup-v1",
                "batch_id": uuid.uuid4().hex,
                "database_identity_sha256": manifest["database_identity_sha256"],
                "post_platform": "golaxy",
                "rows": [expected for _, expected in pending],
            }
            write_private_json(backup_path, backup)  # Before the first mutation, while locks are held.
            for current, _ in pending:
                _write_platform(session, current, "golaxy")
        session.commit()
        return {"updated_ids": [expected["id"] for _, expected in pending]}
    except Exception:
        session.rollback()
        raise


def rollback_batch(session, backup):
    """Restore only this batch's platform values; reject all later row edits."""
    try:
        rows = _check_document(session, backup, "user-game-platform-backup-v1")
        if not backup.get("batch_id") or backup.get("post_platform") != "golaxy":
            raise RepairError("Invalid repair batch")
        pending = []
        for expected in sorted(rows, key=lambda row: row["id"]):
            if expected.get("source") not in ("play_ai", "play_human") or expected.get("platform") is not None:
                raise RepairError("Invalid original row in repair batch")
            current = _locked_row(session, expected["id"])
            if _matches(current, expected, None):
                continue
            if not _matches(current, expected, "golaxy"):
                raise RepairError(f"Later edits prevent rollback: {expected['id']}")
            pending.append(current)
        for current in pending:
            _write_platform(session, current, None)
        session.commit()
        return {"restored_ids": [row["id"] for row in pending]}
    except Exception:
        session.rollback()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Default: read-only candidate manifest")
    mode.add_argument("--apply", metavar="MANIFEST")
    mode.add_argument("--rollback", metavar="BACKUP")
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--game-id", action="append", default=[])
    parser.add_argument("--confirmed-game-id", action="append", default=[])
    parser.add_argument("--output", help="New 0600 manifest/result file; never overwritten")
    parser.add_argument("--backup", help="Required new 0600 original metadata backup for apply")
    args = parser.parse_args(argv)
    if args.apply and not args.backup:
        parser.error("--apply requires --backup")
    if not args.apply and not args.rollback and args.user_id is None and not args.game_id:
        parser.error("dry-run requires --user-id or concrete --game-id scope")
    if (args.apply or args.rollback) and (args.user_id is not None or args.game_id):
        parser.error("apply/rollback scope comes from the reviewed manifest")
    if not args.apply and (args.backup or args.confirmed_game_id):
        parser.error("--backup and --confirmed-game-id are apply-only")
    if args.output and Path(args.output).exists():
        parser.error("--output already exists")
    # Direct execution from scripts/ must resolve this checkout, not a sibling installation.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from katrain.web.core.db import SessionLocal

    try:
        with SessionLocal() as session:
            if args.apply:
                result = apply_manifest(
                    session,
                    json.loads(Path(args.apply).read_text()),
                    confirmed_game_ids=args.confirmed_game_id,
                    backup_path=args.backup,
                )
            elif args.rollback:
                result = rollback_batch(session, json.loads(Path(args.rollback).read_text()))
            else:
                result = dry_run(session, user_id=args.user_id, game_ids=args.game_id)
        if args.output:
            write_private_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (RepairError, OSError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Repair refused: {exc}\n")


if __name__ == "__main__":
    main()
