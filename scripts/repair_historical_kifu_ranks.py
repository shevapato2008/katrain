"""Prepare a private historical rank audit; explicit apply/undo uses finite parts.

DSN comes from KATRAIN_DATABASE_URL or the normal in-memory settings loader.
Examples (no database URL in argv):
  python scripts/repair_historical_kifu_ranks.py --matched-at ISO --output private.json
  python scripts/repair_historical_kifu_ranks.py --apply --manifest private.json --expected-sha256 SHA --part 1

Each part commits independently. On failure the audit identifies every completed
part and the failed part; no automatic compensation or full-corpus atomicity is
claimed. Original SGF files and ingestion stage/state are never opened.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from katrain.web.kifu import historical_rank_repair as repair
from katrain.web.kifu.source_rank_normalization import require

MAX_EXPORT_BYTES = 128 * 1024 * 1024


def _path(path):
    value = Path(path).absolute()
    for candidate in (value, value.resolve()):
        require(
            not any(candidate.parts[i : i + 2] == ("data", "kifu-album") for i in range(len(candidate.parts) - 1)),
            "album filesystem access is forbidden",
        )
    require(not value.is_symlink(), "private artifact symlink is unsafe")
    return value


def _read(path):
    fd = os.open(_path(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_EXPORT_BYTES, "private manifest size invalid")
        raw = handle.read(info.st_size + 1)
        require(
            len(raw) == info.st_size and os.fstat(handle.fileno()).st_size == info.st_size,
            "private manifest changed while reading",
        )
    return json.loads(raw)


def _open_private(path):
    return os.fdopen(os.open(_path(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w")


def _write_handle(handle, value):
    handle.seek(0)
    json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    handle.write("\n")
    handle.truncate()
    handle.flush()
    os.fsync(handle.fileno())


def _engine():
    from katrain.web.core.config import settings

    # Avoid importing core.db (which constructs a global engine and logs URLs).
    return create_engine(settings.DATABASE_URL, echo=False, hide_parameters=True)


def main(argv=None, *, engine=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true")
    action.add_argument("--undo", action="store_true")
    parser.add_argument("--matched-at", help="shared ISO freeze timestamp for TEST/PROD comparison")
    parser.add_argument(
        "--album-id", action="append", type=int, help="limit write candidates; census still covers every album"
    )
    parser.add_argument("--output", help="new private 0600 manifest export (prepare only)")
    parser.add_argument("--manifest", help="previously reviewed private manifest")
    parser.add_argument("--expected-sha256", help="exact full reviewed manifest SHA")
    parser.add_argument(
        "--part", action="append", type=int, help="1-based reviewed part; repeat for selected finite parts"
    )
    parser.add_argument(
        "--audit-output", help="new private result journal; default is manifest.ACTION.TIMESTAMP.audit.json"
    )
    args = parser.parse_args(argv)
    owned_engine = engine is None
    completed = []
    failed_part = None
    pending_outcome = None
    audit = None
    result = None
    try:
        if args.apply or args.undo:
            require(
                args.manifest
                and args.expected_sha256
                and not args.output
                and not args.album_id
                and not args.matched_at,
                "apply/undo requires --manifest and --expected-sha256 only, with optional --part/--audit-output",
            )
            manifest = repair.validate_manifest(_read(args.manifest))
            require(repair.manifest_sha256(manifest) == args.expected_sha256, "historical rank manifest SHA mismatch")
            indexes = sorted(set(args.part or range(1, len(manifest["parts"]) + 1)), reverse=args.undo)
            require(all(1 <= number <= len(manifest["parts"]) for number in indexes), "reviewed part selection invalid")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            audit_path = args.audit_output or f"{args.manifest}.{'undo' if args.undo else 'apply'}.{stamp}.audit.json"
            audit = _open_private(audit_path)
            result = {
                "status": "running",
                "action": "undo" if args.undo else "apply",
                "manifest_sha256": args.expected_sha256,
                "selected_parts": indexes,
                "completed_parts": completed,
                "atomicity": "per_part",
            }
            _write_handle(audit, result)
            engine = engine or _engine()
            for number in indexes:
                failed_part = number
                pending_outcome = None
                part = manifest["parts"][number - 1]
                with engine.connect() as conn:
                    if engine.dialect.name == "postgresql":
                        conn = conn.execution_options(isolation_level="READ COMMITTED")
                    with conn.begin():
                        pending_outcome = (repair.undo_in_transaction if args.undo else repair.apply_in_transaction)(
                            conn,
                            part,
                            expected_sha256=manifest["part_sha256"][number - 1],
                        )
                completed.append({"part": number, **pending_outcome})
                failed_part = None
                pending_outcome = None
                _write_handle(audit, result)
            result["status"] = "undone" if args.undo else "applied"
            _write_handle(audit, result)
        else:
            require(
                not args.manifest and not args.expected_sha256 and not args.part and not args.audit_output,
                "prepare does not accept apply/undo options",
            )
            engine = engine or _engine()
            with engine.connect() as conn:
                if engine.dialect.name == "postgresql":
                    conn = conn.execution_options(isolation_level="REPEATABLE READ")
                with conn.begin():
                    if engine.dialect.name == "postgresql":
                        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                    manifest = repair.prepare_manifest(
                        conn,
                        matched_at=args.matched_at or datetime.now(timezone.utc).isoformat(),
                        album_ids=args.album_id,
                    )
            if args.output:
                with _open_private(args.output) as handle:
                    _write_handle(handle, manifest)
            result = {
                "status": "prepared",
                "manifest_sha256": repair.manifest_sha256(manifest),
                "census": manifest["census"],
                "source_albums": manifest["source_albums"],
                "systems": manifest["systems"],
                "refusals": manifest["refusals"],
                "parts": [
                    {"part": n, "sha256": value, "changes": len(manifest["parts"][n - 1]["changes"])}
                    for n, value in enumerate(manifest["part_sha256"], 1)
                ],
            }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, SQLAlchemyError) as exc:
        # SQLAlchemy exceptions may embed a DSN, SQL parameters or raw data.
        error = "database operation failed" if isinstance(exc, SQLAlchemyError) else str(exc)
        result = {
            **(result or {}),
            "status": "error",
            "error": error,
            "failed_part": failed_part,
            "completed_parts": completed,
            "atomicity": "per_part",
            # A failed COMMIT response cannot establish rollback. Retrying the
            # same frozen part resolves its durable CAS journal without upgrade.
            "commit_outcome_unknown_part": failed_part if pending_outcome is not None else None,
        }
        if audit:
            try:
                _write_handle(audit, result)
            except OSError:
                result["audit_error"] = "private audit could not be updated"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2
    finally:
        if audit:
            audit.close()
        if owned_engine and engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
