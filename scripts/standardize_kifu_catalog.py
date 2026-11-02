#!/usr/bin/env python3
"""Prepare a reviewed catalog repair (default), or apply/undo its frozen hash.

No SGF files are read. Before apply, retain the exact exported manifest and SHA:
it contains immutable evidence and every affected beforeimage. Production apply
requires a fresh deployed-writer/read-model compatibility preflight. This command
does not deploy compatible code and must not be used to bypass that ordering.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from katrain.web.kifu.catalog_standardization import (
    prepare_dedup_manifest,
    validate_dedup_manifest,
    dedup_manifest_sha256,
    apply_dedup_manifest,
    undo_dedup_manifest,
    _lock,
)
from katrain.web.kifu.source_rank_repair import (
    prepare_rank_manifest,
    validate_rank_manifest,
    rank_manifest_sha256,
    apply_rank_manifest,
    undo_rank_manifest,
)

FORMAT = "kifu-catalog-standardization-v1"
CONTRACTS = (
    "reviewed_same_game_native_original_receipt",
    "reviewed_same_game_legacy_import",
    "reviewed_same_game_http_replay",
    "source_rank_snapshot_v2_reader",
)


def manifest_sha256(manifest):
    return sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def database_identity(conn):
    return {
        "dialect": conn.dialect.name,
        "database": (
            conn.scalar(text("SELECT current_database()"))
            if conn.dialect.name == "postgresql"
            else conn.engine.url.database
        ),
    }


def prepare_manifest(conn):
    return {
        "format": FORMAT,
        "database_identity": database_identity(conn),
        "dedup": prepare_dedup_manifest(conn),
        "ranks": prepare_rank_manifest(conn),
    }


def _validate(manifest, expected_sha256):
    if manifest.get("format") != FORMAT or manifest_sha256(manifest) != expected_sha256:
        raise ValueError("frozen catalog manifest hash or format mismatch")
    validate_dedup_manifest(manifest["dedup"])
    validate_rank_manifest(manifest["ranks"])


def export_manifest(manifest, output):
    """Exclusive durable writes prevent silently replacing a reviewed artifact."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if output.exists():
        if manifest_sha256(json.loads(output.read_text())) != manifest_sha256(manifest) or output.with_suffix(
            output.suffix + ".sha256"
        ).read_text().strip() != manifest_sha256(manifest):
            raise ValueError("existing durable manifest or hash differs; overwrite refused")
        return
    with output.open("x", encoding="utf-8") as file:
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())
    with output.with_suffix(output.suffix + ".sha256").open("x", encoding="ascii") as file:
        file.write(manifest_sha256(manifest) + "\n")
        file.flush()
        os.fsync(file.fileno())
    # Verify exported bytes can reconstruct precisely the reviewed input.
    if manifest_sha256(json.loads(output.read_text())) != manifest_sha256(manifest):
        raise ValueError("durable manifest verification failed")


def apply_manifest(conn, manifest, *, expected_sha256):
    _validate(manifest, expected_sha256)
    if database_identity(conn) != manifest["database_identity"]:
        raise ValueError("catalog manifest database identity mismatch")
    with conn.begin_nested():
        _lock(conn, [member["album"]["id"] for group in manifest["dedup"]["groups"] for member in group["members"]])
        # Ranks pin original source links. Dedup then aggregates display provenance.
        ranks = apply_rank_manifest(conn, manifest["ranks"], expected_sha256=rank_manifest_sha256(manifest["ranks"]))
        dedup = apply_dedup_manifest(conn, manifest["dedup"], expected_sha256=dedup_manifest_sha256(manifest["dedup"]))
        return {
            "ranks": ranks,
            "dedup": dedup,
            "search": {"status": "caller_managed", "album_ids": _affected_album_ids(manifest)},
        }


def undo_manifest(conn, manifest, *, expected_sha256):
    _validate(manifest, expected_sha256)
    if database_identity(conn) != manifest["database_identity"]:
        raise ValueError("catalog manifest database identity mismatch")
    with conn.begin_nested():
        _lock(conn, [member["album"]["id"] for group in manifest["dedup"]["groups"] for member in group["members"]])
        dedup = undo_dedup_manifest(conn, manifest["dedup"], expected_sha256=dedup_manifest_sha256(manifest["dedup"]))
        ranks = undo_rank_manifest(conn, manifest["ranks"], expected_sha256=rank_manifest_sha256(manifest["ranks"]))
        return {
            "ranks": ranks,
            "dedup": dedup,
            "search": {"status": "caller_managed", "album_ids": _affected_album_ids(manifest)},
        }


def _affected_album_ids(manifest):
    ids = {member["album"]["id"] for group in manifest["dedup"]["groups"] for member in group["members"]}
    ids.update(change["album_id"] for change in manifest["ranks"]["changes"])
    if any(type(album_id) is not int or album_id <= 0 for album_id in ids):
        raise ValueError("finite positive album IDs required for catalog search sync")
    return sorted(ids)


def write_manifest(engine, manifest, *, mode, expected_sha256):
    """Own the real SQL commit and existing ES pending/refresh/ready protocol.

    The connection helpers above deliberately leave transaction and search
    coordination to their caller. Production CLI writes use this coordinator;
    a post-commit ES failure retains the existing repairable finite-ID gate.
    """
    from katrain.web.kifu import name_batch, search_sync

    _validate(manifest, expected_sha256)
    if mode not in {"apply", "undo"}:
        raise ValueError("catalog write mode must be apply or undo")
    ids = _affected_album_ids(manifest)
    with name_batch._locked_write(engine, search_operation=("sync_ids", {"album_ids": ids})) as conn:
        result = (apply_manifest if mode == "apply" else undo_manifest)(conn, manifest, expected_sha256=expected_sha256)
    result["search"] = {"status": "synced" if search_sync.sync_mode() == "enabled" else "disabled", "album_ids": ids}
    return result


def validate_writer_preflight(preflight, manifest):
    """Require the recorded deployed compatibility audit, never a local candidate."""
    if (
        not isinstance(preflight, dict)
        or preflight.get("format") != "kifu-deployed-writer-preflight-v1"
        or preflight.get("database_identity") != manifest["database_identity"]
        or preflight.get("manifest_sha256") != manifest_sha256(manifest)
        or preflight.get("status") != "compatible"
        or set(preflight.get("verified_contracts", [])) != set(CONTRACTS)
        or not isinstance(preflight.get("deployed_build_sha"), str)
        or not __import__("re").fullmatch(r"[0-9a-f]{40}", preflight["deployed_build_sha"])
    ):
        raise ValueError("compatible deployed-writer preflight is required before apply")
    try:
        observed = datetime.fromisoformat(preflight["checked_at"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - observed).total_seconds()
    except (ValueError, KeyError, TypeError):
        raise ValueError("deployed-writer preflight timestamp is invalid")
    if not 0 <= age <= 86400:
        raise ValueError("deployed-writer preflight is stale")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dry-run", "apply", "undo"), nargs="?", default="dry-run")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--output", type=Path, help="new durable manifest path (dry-run)")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--sha256", help="exact reviewed manifest SHA-256")
    parser.add_argument("--audit-dir", type=Path, help="new local durable beforeimage copy, required for writes")
    parser.add_argument("--writer-preflight", type=Path, help="fresh audit of the deployed compatible runtime (apply)")
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    engine = create_engine(args.database_url)
    if args.mode == "dry-run":
        if args.output is None:
            parser.error("--output is required for the full dry-run artifact")
        with engine.connect() as conn, conn.begin():
            if conn.dialect.name == "postgresql":
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            manifest = prepare_manifest(conn)
        export_manifest(manifest, args.output)
        print(
            json.dumps(
                {
                    "status": "dry-run",
                    "manifest_sha256": manifest_sha256(manifest),
                    "artifact": str(args.output.resolve()),
                    "dedup": manifest["dedup"]["summary"],
                    "ranks": manifest["ranks"].get("census"),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if not args.manifest or not args.sha256 or not args.audit_dir:
        parser.error("writes require --manifest, --sha256 and --audit-dir")
    manifest = json.loads(args.manifest.read_text())
    _validate(manifest, args.sha256)
    if args.mode == "apply":
        if not args.writer_preflight:
            parser.error("apply requires --writer-preflight from the deployed compatible runtime")
        validate_writer_preflight(json.loads(args.writer_preflight.read_text()), manifest)
    export_manifest(manifest, args.audit_dir / (args.mode + "-" + args.sha256 + ".json"))
    result = write_manifest(engine, manifest, mode=args.mode, expected_sha256=args.sha256)
    print(json.dumps({"status": args.mode, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
