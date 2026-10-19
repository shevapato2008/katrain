"""Operator-only recovery of four known prompt failures; default is read-only.

Run in the TEST cron after A finishes, while B scheduling and LLM remain disabled.
This only returns raw SGFs to downloaded; the normal job must requalify/review them.
"""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from sqlalchemy import select

from katrain.core.sgf_parser import SGF
from katrain.cron.db import engine
from katrain.kifu_ingest.staging import Stage
from katrain.kifu_ingest.state import StateStore, items

EXPECTED = {
    "91358273": (
        "e3fa2301a51413980606ab4180e9213b2a7ab9085ffcfb14703b83f406cd0029",
        "event year or round number lost",
    ),
    "91315699": (
        "10af6affdf07cccede7483bdca24cdc70b396c25ab902fdeb7a2f90aff7fb938",
        "Chinese original was changed without orthographic explanation",
    ),
    "91317146": (
        "1ca9035a3fd4a206cf11f6d43296136aa4275d0aefbe0d184277bbc337fb42fe",
        "candidate requires five nonempty displays",
    ),
    "91346493": (
        "06409bed838175e3bf15cb5db70f46f1a41723e8d5cfec1fd06d73c0f067a119",
        "candidate requires five nonempty displays",
    ),
}


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="restore only these four raw items to downloaded")
    args = parser.parse_args()
    require(os.getenv("CRON_KIFU_INGEST_ENABLED", "false").lower() == "false", "Stop: B scheduling must be disabled")
    require(os.getenv("CRON_KIFU_INGEST_LLM_ENABLED", "false").lower() == "false", "Stop: B LLM must be disabled")
    require(os.getenv("CRON_KIFU_INGEST_MAX_TOKENS", "0") == "0", "Stop: B token cap must be zero during recovery")
    root = Path(os.getenv("CRON_KIFU_INGEST_STAGING_DIR", "/app/data/kifu_ingest"))
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), "Invalid existing staging root")
    for name in ("sgf", "metadata"):
        require((root / name).is_dir() and not (root / name).is_symlink(), f"Invalid existing staging directory: {name}")
    manifest_path = root / "manifest.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink(), "Invalid existing stage manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with engine.connect() as connection:
        rows = {
            row["external_id"]: dict(row)
            for row in connection.execute(
                select(items).where(items.c.source_key == "19x19", items.c.external_id.in_(EXPECTED))
            ).mappings()
        }
    require(set(rows) == set(EXPECTED), "Expected exactly four existing journal items")
    prepared = []
    for source_id, (digest, reason) in EXPECTED.items():
        row = rows[source_id]
        staged = manifest["items"][source_id]
        path = root / "sgf" / f"{source_id}.sgf"
        require(path.is_file() and not path.is_symlink(), f"{source_id}: invalid raw SGF path")
        raw = path.read_bytes()
        require(sha256(raw).hexdigest() == digest == row["raw_sha256"] == staged["raw_sha256"], f"{source_id}: raw hash mismatch")
        require(row["staging_path"] == str(path) == staged["raw_sgf_path"], f"{source_id}: staging path mismatch")
        require(row["status"] == "quarantined" and row["resume_phase"] == "downloaded", f"{source_id}: expected saved quarantined/downloaded phase")
        require(row["error"] == reason and staged["status"] == "failed" and staged["last_error"] == reason, f"{source_id}: unexpected isolation reason/state")
        require(all(row[field] is None for field in ("publication_key", "test_album_id", "prod_album_id", "test_receipt", "test_verification", "prod_receipt", "prod_verification")), f"{source_id}: publication state already exists; stop for reconciliation")
        text = raw.decode("utf-8")
        SGF.parse_sgf(text)
        prepared.append((source_id, text))
    # All four hashes, saved phases and reasons pass before either store is changed.
    if args.apply:
        stage = Stage(root)
        store = StateStore(engine)
        for source_id, text in prepared:
            stage.save_sgf(source_id, text)
            store.advance_item("19x19", source_id, "downloaded", expected_status="quarantined")
    print(json.dumps({"mode": "restored_downloaded" if args.apply else "read_only_validated", "source_ids": list(EXPECTED), "publication_performed": False, "paid_requests": 0}))


if __name__ == "__main__":
    main()
