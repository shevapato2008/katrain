"""Capture one fresh reviewed fixed-pair preimage and assemble an unsigned proposal."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import JSON, Column, Integer, String, create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from katrain.web.core.models_db import KifuAlbum, KifuPlayer
from katrain.web.kifu import name_inventory  # freeze the native format-4 inventory column list before mapping

NEW_KEYS = frozenset({"li_jie", "park_ji", "park_jin", "cho_huilian", "cho_huilian_variant"})


def native_duplicate_columns(engine, *, require_read_only=True):
    """Map three existing physical columns missing from the older r8 importer ORM."""
    with engine.connect() as conn:
        if conn.dialect.name != "postgresql" or (require_read_only
                and conn.scalar(text("SHOW transaction_read_only")) != "on"):
            raise RuntimeError("native duplicate capture requires PostgreSQL READ ONLY")
        physical = {column["name"]: column for column in inspect(conn).get_columns("kifu_albums")}
        player_physical = {column["name"]: column for column in inspect(conn).get_columns("kifu_players")}
    if "event_edition_id" not in physical or "list_hidden_reason" not in physical:
        raise RuntimeError("required physical album columns missing")
    hidden = physical["list_hidden_reason"]["type"]
    if not isinstance(hidden, String) or hidden.length != 64:
        raise RuntimeError("physical hidden reason type changed")
    if "event_edition_id" not in KifuAlbum.__table__.c:
        KifuAlbum.event_edition_id = Column(Integer, nullable=True)
    if "list_hidden_reason" not in KifuAlbum.__table__.c:
        KifuAlbum.list_hidden_reason = Column(String(64), nullable=True)
    if str(player_physical.get("authoritative_pages", {}).get("type", "")).lower() not in {"json", "jsonb"}:
        raise RuntimeError("physical owner authoritative pages column changed")
    if "authoritative_pages" not in KifuPlayer.__table__.c:
        KifuPlayer.authoritative_pages = Column(JSON, nullable=False)


def build_proposal(merge, preimage, key, *, producer_id, producer_model, identity_review_sha, preimage_path,
                   preimage_bytes_sha):
    if key not in NEW_KEYS:
        raise ValueError("only five reviewed directions are supported")
    pair = merge.PAIRS[key]
    environment = preimage["environment"]
    survivor, retired = pair["ids"][environment]
    players = {row["id"]: row for row in preimage["full_rows"]["kifu_players"]}
    albums = preimage["full_rows"]["kifu_albums"]
    moving, protected = [], []
    for album in albums:
        for side in ("black", "white"):
            owner = album[side + "_player_id"]
            if owner in (survivor, retired):
                (moving if owner == retired else protected).append(merge._slot(album, side, survivor))
    raws = {row["id"]: row for row in preimage["full_rows"]["kifu_raw_player_values"]}
    raw_updates = []
    for raw_id in pair["raw_ids"]:
        raw = raws[raw_id]
        raw_updates.append({
            "raw_id": raw_id, "raw_value": raw["raw_value"], "before_full_row": raw,
            "before_review_metadata": raw["review_metadata"],
            "after_review_metadata": {**raw["review_metadata"], "player_id": survivor},
            "columns_allowed_to_change": ["review_metadata"], "preserve_review_status": raw["review_status"],
        })
    alias = pair["names"][1]
    plan = {
        "format": merge.FORMAT, "status": "pending_independent_review", "environment": environment,
        "database": merge.DATABASES[environment], "captured_at": preimage["captured_at"],
        "producer_id": producer_id, "producer_model": producer_model,
        "identity_review_canonical_sha256": identity_review_sha,
        "full_preimage_canonical_sha256": merge.canonical_sha256(preimage),
        "full_preimage_artifact": {"path": str(preimage_path), "sha256": preimage_bytes_sha},
        "survivor_player": players[survivor], "retire_player": players[retired],
        "operations": {
            "album_fk_updates": moving, "raw_metadata_updates": raw_updates,
            "insert_alias_if_exact_preimage_still_absent": {
                "player_id": survivor, "alias": alias, "normalized_alias": merge.normalize_alias(alias),
            },
            "delete_empty_unreviewed_player_after_repoints": players[retired],
        },
        "protected_existing_slots": protected, "declared_fk_inventory": preimage["declared_player_fks"],
        "protected_table_full_row_hashes": {
            table: merge.canonical_sha256(preimage["full_rows"][table]) for table in merge._PROTECTED
        },
        "counts": merge.expected_counts(key),
    }
    merge._validate(plan, preimage, merge.canonical_sha256(plan))
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("TEST", "PROD"), required=True)
    parser.add_argument("--key", choices=sorted(NEW_KEYS), required=True)
    parser.add_argument("--database-url", default=os.getenv("KATRAIN_DATABASE_URL"), required=False)
    parser.add_argument("--producer-id", required=True)
    parser.add_argument("--producer-model", required=True)
    parser.add_argument("--identity-review-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.database_url or len(args.identity_review_sha256) != 64:
        parser.error("database URL and exact identity review SHA-256 are required")
    engine = create_engine(args.database_url, connect_args={"options": "-c default_transaction_read_only=on"})
    try:
        native_duplicate_columns(engine)
        from katrain.web.kifu import player_duplicate as merge
        with merge._readonly(engine) as conn, conn.begin():
            preimage = merge.capture(conn, args.environment, args.key)
        raw = json.dumps(preimage, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        compressed = gzip.compress(raw, mtime=0)
        target = args.output_dir / "current.json.gz"
        plan = build_proposal(
            merge, preimage, args.key, producer_id=args.producer_id, producer_model=args.producer_model,
            identity_review_sha=args.identity_review_sha256, preimage_path=target,
            preimage_bytes_sha=hashlib.sha256(compressed).hexdigest())
        args.output_dir.mkdir(parents=True, exist_ok=False)
        target.write_bytes(compressed)
        (args.output_dir / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "pending_independent_review", "key": args.key,
                          "environment": args.environment, "plan_sha256": merge.canonical_sha256(plan),
                          "preimage_bytes_sha256": hashlib.sha256(compressed).hexdigest(),
                          "counts": plan["counts"]}, ensure_ascii=False, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
