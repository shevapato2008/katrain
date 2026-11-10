"""One-off trusted operator. Stdout is PRIVATE: retain its actual JSON error.

Default is receipt-only SELECT. --publish is an explicit single write attempt.
No transport, retry, model, scheduler, cache persistence or parser replacement.
"""

import argparse
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import re
import sys

logging.disable(logging.CRITICAL)
sys.path.insert(0, "/app")

from sqlalchemy import Text, cast, create_engine, select, text
from katrain.kifu_ingest.catalog import (
    FORMAT,
    _check_source_receipts,
    _validate_manifest,
    publish_manifest,
)
from katrain.kifu_ingest.sync import validate_test_verification
from katrain.web.core.models_db import KifuNameBatch
from katrain.web.kifu.name_candidates import canonical_sha256

CACHE_SHA = "b3d4ae68d0994c3c6b9032e72ea19f8ea1770d0817446da57a3b3fb1cb049a8a"
CACHE_HOST_SOURCE = "/home/ubuntu/kifu-hourly-incremental-20261019/pre-web-final-runtime/kifu-backfill/sgf-cache.json"
SOURCE72_SHA = "0404084ef2ed16ae305bf67cd29896d2851944d96a0ac4fb1079219fb56702ef"
PROD_PREFIX = "KIFU_CACHE_RECOVERY_PROD "


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_file(path):
    path = Path(path)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "unsafe operator input file")
    return path.read_bytes()


def checked_manifest(manifest, digest, key):
    require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "expected manifest SHA invalid")
    require(
        key.startswith("19x19-event-recovery-") and manifest.get("publication_key") == key,
        "expected corrected publication key differs",
    )
    _validate_manifest(manifest, digest)
    games = manifest["games"]
    require(len(games) == 72 and len(manifest["decisions"]) == 18, "expected corrected72/18 only")
    require(all(g["source_key"] == "19x19" for g in games), "unexpected source")
    members = sorted((g["source_item_id"], g["raw_sha256"], g["sgf_sha256"]) for g in games)
    require(canonical_sha256(members) == SOURCE72_SHA, "original72 source hashes differ")
    return manifest


def load_cache(path):
    raw = read_file(path)
    require(sha256(raw).hexdigest() == CACHE_SHA, "trusted cache file SHA differs")
    cache = json.loads(raw)
    require(isinstance(cache, dict) and len(cache) == 176539, "trusted cache membership differs")
    require(
        all(
            isinstance(k, str)
            and re.fullmatch(r"[0-9a-f]{64}", k)
            and isinstance(v, str)
            and re.fullmatch(r"[0-9a-f]{64}", v)
            for k, v in cache.items()
        ),
        "trusted cache has invalid or null entries",
    )
    return cache


def checked_receipt(receipt, manifest, digest):
    require(
        isinstance(receipt, dict) and receipt.get("status") == "applied" and receipt.get("manifest_sha256") == digest,
        "actual receipt identity differs",
    )
    rows = receipt.get("games")
    expected = {(g["source_key"], g["source_item_id"]) for g in manifest["games"]}
    require(
        isinstance(rows, list)
        and len(rows) == 72
        and {(r["source_key"], r["source_item_id"]) for r in rows} == expected
        and all(type(r.get("album_id")) is int and r["album_id"] > 0 for r in rows),
        "actual receipt source72 differs",
    )
    return receipt


def native_receipt(engine, manifest, digest):
    """Read the actual applied outer receipt, including current SGF/source links."""
    key = manifest["publication_key"]
    with engine.connect() as conn, conn.begin():
        conn.execute(text("SET TRANSACTION READ ONLY"))
        rows = (
            conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.bundle_sha256 == digest)).mappings().all()
        )
        if not rows:
            # Only parse candidates found by the established text predicate;
            # JSON path extraction across giant historical artifacts is slow.
            candidates = conn.scalars(
                select(KifuNameBatch.reviewed_artifact).where(cast(KifuNameBatch.reviewed_artifact, Text).contains(key))
            )
            require(
                not any(isinstance(value, dict) and value.get("publication_key") == key for value in candidates),
                "publication key names another native packet",
            )
            return None
        require(len(rows) == 1, "native publication identity is ambiguous")
        row = rows[0]
        artifact = row["reviewed_artifact"]
        require(
            row["status"] == "applied"
            and row["bundle_sha256"] == digest
            and artifact.get("publication_format") == FORMAT
            and artifact.get("publication_key") == key
            and artifact.get("manifest_sha256") == digest,
            "native publication is not the expected applied packet",
        )
        logical = {**manifest, "games": [{k: v for k, v in g.items() if k != "sgf_content"} for g in manifest["games"]]}
        require(artifact.get("logical_manifest") == logical, "native logical manifest differs")
        receipt = checked_receipt(artifact.get("receipt"), manifest, digest)
        _check_source_receipts(conn, artifact["sources"])
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--publication-key", required=True)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
        require(len(raw) <= 16 * 1024 * 1024, "relay payload too large")
        request = json.loads(raw)
        require(request.get("operation") == "prod_publish", "unexpected relay operation")
        require(request.get("manifest_sha256") == args.manifest_sha256, "relay digest differs")
        manifest = checked_manifest(request["manifest"], args.manifest_sha256, args.publication_key)
        validate_test_verification(manifest, args.manifest_sha256, request.get("test_verification"))
        engine = create_engine(os.environ["KATRAIN_DATABASE_URL"], pool_pre_ping=True)
        require(engine.dialect.name == "postgresql", "expected PROD PostgreSQL")
        try:
            receipt = native_receipt(engine, manifest, args.manifest_sha256)
            if receipt is None and args.publish:
                require(args.cache is not None, "explicit trusted cache path required for publish")
                receipt = publish_manifest(
                    engine, manifest, expected_manifest_sha256=args.manifest_sha256, sgf_cache=load_cache(args.cache)
                )
            result = (
                {"status": "absent", "manifest_sha256": args.manifest_sha256}
                if receipt is None
                else {
                    "status": "applied",
                    "manifest_sha256": args.manifest_sha256,
                    "receipt": checked_receipt(receipt, manifest, args.manifest_sha256),
                }
            )
        finally:
            engine.dispose()
        print(PROD_PREFIX + json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        # The Mac bridge retains this entire stream in a private0600 file and
        # sends TEST only {"error": <safe type>}; never forward this text publicly.
        print(
            PROD_PREFIX
            + json.dumps({"status": "error", "error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
