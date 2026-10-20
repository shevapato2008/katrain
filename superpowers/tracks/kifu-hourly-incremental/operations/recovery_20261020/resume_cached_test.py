"""Explicit paused-job recovery of corrected72, using original resume_batch.

Run beside native_cached_prod.py inside TEST cron. --prod-relay requires root's
single-use private Mac stdin/stdout bridge; no SSH credentials are used here.
"""

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import re
import sys
import traceback
from uuid import uuid4

logging.disable(logging.CRITICAL)
sys.path.insert(0, "/app")

import httpx
from sqlalchemy import func, select
from katrain.cron import config
from katrain.cron.db import engine
from katrain.cron.jobs.kifu_ingest import _session_lock, _batch_row, resume_batch, reconcile_items
from katrain.cron.models import CronJobCommandDB, CronJobControlDB, CronJobRunDB
from katrain.kifu_ingest.catalog import publish_manifest
from katrain.kifu_ingest.state import StateStore, batches, items
from katrain.kifu_ingest.sync import validate_test_verification, verify_album_api
from katrain.web.core.models_db import KifuNameBatch
from native_cached_prod import (
    checked_manifest,
    checked_receipt,
    load_cache,
    native_receipt,
    read_file,
    require,
)

OLD_KEY = "19x19-recovery-a5425ac6c5b3d96d9bc23d3b"
OLD_SHA = "ae8fd9d9f9f4a0bde3ea72e20b74c64b0b3e041848dbb5f50d73a3b7d935e019"
PHASES = ("names_ready", "test_published", "test_verified", "prod_published", "prod_synced")
REQUEST_PREFIX = "KIFU_CACHE_RECOVERY_REQUEST "
SUMMARY_PREFIX = "KIFU_CACHE_RECOVERY_SUMMARY "


def paused():
    with engine.connect() as conn:
        require(
            conn.scalar(select(CronJobControlDB.paused).where(CronJobControlDB.job_name == "kifu_ingest")) is True,
            "B must remain paused",
        )
        require(
            conn.scalar(
                select(func.count())
                .select_from(CronJobRunDB)
                .where(CronJobRunDB.job_name == "kifu_ingest", CronJobRunDB.status == "running")
            )
            == 0,
            "scheduled B run is still active",
        )
        require(
            conn.scalar(
                select(func.count())
                .select_from(CronJobCommandDB)
                .where(CronJobCommandDB.job_name == "kifu_ingest", CronJobCommandDB.state == "pending")
            )
            == 0,
            "pending B command must be resolved by root",
        )


def preflight(store, manifest, digest):
    paused()
    key = manifest["publication_key"]
    row = _batch_row(store, key)
    require(
        row["manifest_sha256"] == digest and row["status"] in PHASES,
        "corrected queue is not at a supported durable phase",
    )
    if row["status"] == "names_ready":
        require(
            row["resume_phase"] is None
            and all(row[f] is None for f in ("test_receipt", "test_verification", "prod_receipt", "prod_verification")),
            "initial corrected queue already contains publication fields",
        )
    with engine.connect() as conn:
        old = conn.execute(select(batches).where(batches.c.publication_key == OLD_KEY)).mappings().one()
        marker = (old["stats"] or {}).get("semantic_recovery", {})
        require(
            old["manifest_sha256"] == OLD_SHA
            and old["status"] == "quarantined"
            and marker.get("new_key") == key
            and marker.get("new_sha256") == digest,
            "old ae8 quarantine/recovery marker differs",
        )
        undone = conn.execute(
            select(KifuNameBatch.id, KifuNameBatch.status, KifuNameBatch.bundle_sha256).where(
                KifuNameBatch.id.in_([880, 881, 882])
            )
        ).all()
        require(
            len(undone) == 3
            and all(r.status == "undone" for r in undone)
            and next(r.bundle_sha256 for r in undone if r.id == 880) == OLD_SHA,
            "native TEST880 and children are not undone",
        )
        rows = conn.execute(select(items).where(items.c.publication_key == key)).mappings().all()
        games = {g["source_item_id"]: g for g in manifest["games"]}
        require(len(rows) == 72 and {r["external_id"] for r in rows} == set(games), "journal source72 differs")
        require(
            all(
                r["source_key"] == "19x19"
                and r["status"] in PHASES
                and r["raw_sha256"] == games[r["external_id"]]["raw_sha256"]
                and r["sgf_sha256"] == games[r["external_id"]]["sgf_sha256"]
                for r in rows
            ),
            "source72 journal phase/hashes differ",
        )
    return row


async def operate(args, out):
    manifest = checked_manifest(json.loads(read_file(args.manifest)), args.manifest_sha256, args.publication_key)
    stage = Path(config.KIFU_INGEST_STAGING_DIR).resolve()
    require(args.manifest.resolve().parent == stage / "packages", "manifest must be the exposed queue packet")
    require(not out.is_relative_to(stage), "operator outputs must be outside application Stage")
    store = StateStore(engine)

    def save(name, value):
        target = out / name
        temporary = out / (name + "." + str(uuid4()))
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)

    with _session_lock(engine) as acquired:
        require(acquired, "another B operation holds the session lock")
        row = preflight(store, manifest, args.manifest_sha256)
        cache = load_cache(args.cache)
        save(
            "preflight.json",
            {
                "publication_key": args.publication_key,
                "manifest_sha256": args.manifest_sha256,
                "phase": row["status"],
                "cache_entries": len(cache),
            },
        )

        def test_publish(packet, digest):
            paused()
            receipt = native_receipt(engine, packet, digest)
            if receipt is None:
                receipt = publish_manifest(engine, packet, expected_manifest_sha256=digest, sgf_cache=cache)
            save("test-receipt.json", receipt)
            return checked_receipt(receipt, packet, digest)

        async def sync(packet, digest, verification):
            paused()
            validate_test_verification(packet, digest, verification)
            request = {
                "operation": "prod_publish",
                "manifest": packet,
                "manifest_sha256": digest,
                "test_verification": verification,
            }
            save("prod-request.json", request)
            print(REQUEST_PREFIX + json.dumps(request, ensure_ascii=False, separators=(",", ":")), flush=True)
            line = await asyncio.to_thread(sys.stdin.readline, 1024 * 1024 + 1)
            require(
                bool(line) and len(line) <= 1024 * 1024, "PROD relay closed or response too large; read receipt first"
            )
            response = json.loads(line)
            require(isinstance(response, dict), "PROD relay response must be an object")
            if set(response) == {"error"}:
                kind = response["error"]
                require(
                    isinstance(kind, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", kind),
                    "PROD relay error must be a safe type",
                )
                raise RuntimeError("PROD relay stopped: " + kind + "; root must read receipt before another write")
            require(set(response) == {"receipt"}, "PROD relay must return only the actual native receipt")
            receipt = checked_receipt(response["receipt"], packet, digest)
            save("prod-receipt.json", receipt)
            return {"receipt": receipt}

        async with httpx.AsyncClient() as client:

            async def verify(base, packet, receipt, name):
                paused()
                result = await verify_album_api(
                    client, base, packet, checked_receipt(receipt, packet, args.manifest_sha256), timeout=60
                )
                result = {**result, "manifest_sha256": args.manifest_sha256}
                validate_test_verification(packet, args.manifest_sha256, result)
                save(name + ".json", result)
                return result

            async def test_verify(packet, receipt):
                return await verify(config.KIFU_INGEST_TEST_API_URL, packet, receipt, "test-verification")

            async def prod_verify(packet, receipt):
                return await verify(config.KIFU_INGEST_PROD_API_URL, packet, receipt, "prod-verification")

            reconcile_items(store, manifest, row)
            try:
                row = await resume_batch(
                    store,
                    manifest,
                    args.manifest_sha256,
                    test_publish=test_publish,
                    test_verify=test_verify,
                    sync=sync,
                    prod_verify=prod_verify,
                )
            finally:
                row = _batch_row(store, args.publication_key)
                reconcile_items(store, manifest, row)
                save("durable-checkpoint.json", row)
        paused()
        require(row["status"] == "prod_synced", "recovery did not reach prod_synced")
        summary = {
            "status": row["status"],
            "publication_key": args.publication_key,
            "manifest_sha256": args.manifest_sha256,
            "games": 72,
            "checks_per_environment": 360,
        }
        save("complete.json", summary)
        print(SUMMARY_PREFIX + json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--publication-key", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prod-relay", action="store_true")
    args = parser.parse_args()
    require(args.prod_relay, "explicit --prod-relay is required; no default execution")
    os.umask(0o077)
    out = args.out.resolve()
    require(args.out.is_absolute() and not args.out.is_symlink(), "unsafe private operator directory")
    require(
        not out.is_relative_to(Path(config.KIFU_INGEST_STAGING_DIR).resolve()),
        "operator outputs must be outside application Stage",
    )
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(out.stat().st_mode & 0o077 == 0, "operator directory must be private0700")
    try:
        asyncio.run(operate(args, out))
        return 0
    except Exception as exc:
        # Complete local exception stays private; the bridge/public report gets
        # only its type. A lost relay reply never initiates a second write here.
        (out / "failure.private.json").write_text(
            json.dumps(
                {"error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()},
                ensure_ascii=False,
            )
        )
        os.chmod(out / "failure.private.json", 0o600)
        print(
            SUMMARY_PREFIX
            + json.dumps(
                {"status": "stopped", "error_type": type(exc).__name__, "read_prod_receipt_before_any_retry": True}
            ),
            flush=True,
        )
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
