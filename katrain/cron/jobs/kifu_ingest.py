"""Disabled-by-default incremental Kifu orchestration.

Frozen manifests are resumed before new source discovery. All network and
publishing work runs outside long database transactions.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import inspect
import json
import logging
import os
from pathlib import Path
import time
from uuid import uuid4

import httpx
from sqlalchemy import select, text
from sqlalchemy.exc import NoResultFound

from katrain.cron import config
from katrain.cron.db import engine
from katrain.cron.jobs.base import BaseJob
from katrain.kifu_ingest.catalog import (
    lookup_qualified_identities,
    publish_manifest,
    qualified_raw_event_templates,
)
from katrain.kifu_ingest.exclusions import historical_excluded_ids, known_source_ids
from katrain.kifu_ingest.orchestration import (
    _validated,
    derive_staged_record,
    isolate_unportable_identities,
    prepare_staged_games,
)
from katrain.kifu_ingest.names import NameRejected, NameServiceError, NeedsCredentials, QwenNameService
from katrain.kifu_ingest.source_19x19 import Source19x19
from katrain.kifu_ingest.staging import Stage, discover_and_download
from katrain.kifu_ingest.state import StateStore, batches, items
from katrain.kifu_ingest.sync import check_production_identities, send_verified_manifest, verify_album_api
from katrain.web.kifu.name_candidates import canonical_sha256


logger = logging.getLogger("katrain_cron.kifu_ingest")
LOCK_KEY = 0x4B494655494E4731
_BATCH_RECEIPTS = {
    "test_published": "test_receipt",
    "test_verified": "test_verification",
    "prod_published": "prod_receipt",
    "prod_synced": "prod_verification",
}


class DailyTokenLedger:
    """Durable per-day charge upper bounds shared by hourly job instances."""

    def __init__(self, path, budget, atomic_write):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(".lock")
        self.budget = budget
        self.atomic_write = atomic_write

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            entries = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
            if not isinstance(entries, list):
                raise ValueError("Qwen usage audit is invalid")
            yield entries
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _write(self, entries):
        self.atomic_write(self.path, json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8"))

    @staticmethod
    def _spent(entries):
        reservations = {}
        settlements = {}
        legacy = 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Qwen usage audit is invalid")
            kind = entry.get("kind")
            if kind == "reservation":
                reservations[entry["reservation_id"]] = entry["reserved_tokens"]
            elif kind == "settlement":
                settlements[entry["reservation_id"]] = entry["actual_tokens"]
            elif kind is None and isinstance(entry.get("usage"), dict):
                legacy += entry["usage"].get("total_tokens", 0)
        if settlements.keys() - reservations.keys():
            raise ValueError("Qwen usage settlement lacks reservation")
        return legacy + sum(settlements.get(key, upper) for key, upper in reservations.items())

    def spent(self):
        with self._locked() as entries:
            return self._spent(entries)

    def reserve(self, upper_bound):
        if not isinstance(upper_bound, int) or upper_bound <= 0:
            raise ValueError("invalid Qwen token reservation")
        with self._locked() as entries:
            if self._spent(entries) + upper_bound > self.budget:
                raise NameServiceError("Qwen token budget exhausted")
            reservation_id = str(uuid4())
            entries.append({"kind": "reservation", "reservation_id": reservation_id, "reserved_tokens": upper_bound})
            self._write(entries)
            return reservation_id

    def settle(self, reservation_id, actual_tokens):
        if not isinstance(actual_tokens, int) or actual_tokens < 0:
            raise ValueError("invalid actual Qwen usage")
        with self._locked() as entries:
            reservations = {e["reservation_id"] for e in entries if e.get("kind") == "reservation"}
            if reservation_id not in reservations:
                raise ValueError("Qwen reservation missing")
            if not any(e.get("kind") == "settlement" and e.get("reservation_id") == reservation_id for e in entries):
                entries.append({"kind": "settlement", "reservation_id": reservation_id, "actual_tokens": actual_tokens})
                self._write(entries)
            return self._spent(entries)

    def record_call(self, entry):
        with self._locked() as entries:
            entries.append({"kind": "call", **entry})
            self._write(entries)


class DailyTokenBudget:
    """Choose the UTC ledger at each request; settle against its reservation day."""

    def __init__(self, root, budget, atomic_write, *, clock=None):
        self.root = Path(root)
        self.budget = budget
        self.atomic_write = atomic_write
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _ledger(self, day):
        return DailyTokenLedger(self.root / f"qwen-usage-{day}.json", self.budget, self.atomic_write)

    def _today(self):
        return self.clock().astimezone(timezone.utc).strftime("%Y%m%d")

    def spent(self):
        return self._ledger(self._today()).spent()

    def reserve(self, upper_bound):
        day = self._today()
        return day, self._ledger(day).reserve(upper_bound)

    def settle(self, reservation, actual_tokens):
        day, reservation_id = reservation
        self._ledger(day).settle(reservation_id, actual_tokens)
        return self.spent()

    def record_call(self, entry):
        self._ledger(self._today()).record_call(entry)


@contextmanager
def _session_lock(database):
    """Hold a dedicated PostgreSQL session lock across one run, without a transaction."""
    if database.dialect.name != "postgresql":
        raise RuntimeError("kifu ingest requires PostgreSQL for its session lock")
    connection = database.connect().execution_options(isolation_level="AUTOCOMMIT")
    acquired = False
    try:
        acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}))
        yield acquired
    finally:
        if acquired:
            connection.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
        connection.close()


def _batch_row(store, key):
    if hasattr(store, "get_batch"):
        return store.get_batch(key)
    with store.engine.connect() as connection:
        row = connection.execute(select(batches).where(batches.c.publication_key == key)).mappings().one()
        return dict(row)


def _item_row(store, source, source_id):
    if hasattr(store, "get_item"):
        return store.get_item(source, source_id)
    with store.engine.connect() as connection:
        row = (
            connection.execute(select(items).where(items.c.source_key == source, items.c.external_id == source_id))
            .mappings()
            .one()
        )
        return dict(row)


async def _call(fn, *args):
    if inspect.iscoroutinefunction(fn):
        return await fn(*args)
    return await asyncio.to_thread(fn, *args)


async def process_package_queue(store, manifests, process, *, now=None, timeout_seconds=None):
    """Continue independent frozen packages; persist each failure at its phase."""
    now = now or datetime.now(timezone.utc)
    failures = 0
    for manifest in manifests:
        key = manifest["publication_key"]
        try:
            try:
                row = await asyncio.to_thread(_batch_row, store, key)
            except NoResultFound:
                row = {"status": "unregistered"}
            if row["status"] == "retry_wait":
                retry_at = row.get("next_retry_at")
                if retry_at is not None and retry_at > now:
                    continue
                phase = row["resume_phase"]
                kwargs = {"expected_status": "retry_wait"}
                receipt_column = _BATCH_RECEIPTS.get(phase)
                if receipt_column:
                    receipt = row.get(receipt_column)
                    if not isinstance(receipt, dict):
                        raise ValueError(f"durable {receipt_column} missing for retry")
                    kwargs["receipt"] = receipt
                await asyncio.to_thread(store.advance_batch, key, phase, **kwargs)
            task = _call(process, manifest)
            if timeout_seconds is not None:
                await asyncio.wait_for(task, timeout=timeout_seconds)
            else:
                await task
        except Exception as exc:
            try:
                row = await asyncio.to_thread(_batch_row, store, key)
            except NoResultFound:
                row = {"status": "unregistered"}
            if row["status"] == "retry_wait" and isinstance(exc, ValueError) and "durable " in str(exc):
                await asyncio.to_thread(
                    store.advance_batch, key, "quarantined", expected_status="retry_wait", error=str(exc)[:512]
                )
            if row["status"] not in ("unregistered", "retry_wait", "quarantined", "prod_synced"):
                await asyncio.to_thread(
                    store.advance_batch,
                    key,
                    "retry_wait",
                    expected_status=row["status"],
                    error=(str(exc) or f"package phase exceeded {timeout_seconds}s")[:512],
                    next_retry_at=now + timedelta(minutes=5),
                )
            failures += 1
            logger.exception("kifu package %s failed at %s", key, row["status"])
    return failures


def group_staged_items(items, *, review_enabled):
    if not review_enabled:
        return [[item] for item in items]
    return [items[start : start + 100] for start in range(0, len(items), 100)]


def select_review_items(records, resolved, *, reusable_events, max_new_names, isolated=None):
    """Choose a finite batch before any paid request; leave overflow staged."""
    chosen, deferred, names = [], [], set()
    isolated = isolated if isolated is not None else []
    for item, game in records:
        required = set()
        ambiguity = None
        for slot in ("black", "white", "event"):
            kind = "event" if slot == "event" else "player"
            raw = game["metadata"]["event" if slot == "event" else f"player_{slot}"]
            match = resolved[kind].get(raw, {"status": "unresolved"})
            if match["status"] == "ambiguous":
                ambiguity = f"ambiguous {kind} identity requires review"
                break
            if match["status"] == "qualified":
                continue
            if match["status"] == "missing_qualified_five_languages":
                required.add((kind, match["canonical_name"]))
            elif not (kind == "event" and raw in reusable_events):
                required.add((f"raw_{kind}", raw))
        if ambiguity:
            isolated.append((item["external_id"], ambiguity))
        elif len(names | required) > max_new_names:
            deferred.append(item)
        else:
            chosen.append(item)
            names.update(required)
    return chosen, deferred


async def select_portable_review_items(
    records, resolved, *, check_identities, reusable_events, max_new_names, isolated=None
):
    isolated = isolated if isolated is not None else []
    excluded = await isolate_unportable_identities([game for _, game in records], resolved, check_identities, isolated)
    return select_review_items(
        [(item, game) for item, game in records if game["source_item_id"] not in excluded],
        resolved,
        reusable_events=reusable_events,
        max_new_names=max_new_names,
        isolated=isolated,
    )


def register_frozen_batch(store, key, digest):
    """A schema-validated, reviewed package may enter the publication queue."""
    row = store.register_batch(key, digest)
    pending = ("discovered", "downloaded", "parsed", "names_ready")
    if row["status"] not in pending:
        return row
    for status in pending[pending.index(row["status"]) + 1 :]:
        row = store.advance_batch(key, status, expected_status=row["status"])
    return row


def register_frozen_items(store, manifest):
    phases = ("discovered", "downloaded", "parsed", "names_ready")
    for game in manifest["games"]:
        source, source_id = game["source_key"], game["source_item_id"]
        row = store.remember_item(source, source_id, raw_sha256=game["raw_sha256"], sgf_sha256=game["sgf_sha256"])
        if row["status"] not in phases:
            continue
        for status in phases[phases.index(row["status"]) + 1 :]:
            changes = (
                {"raw_sha256": game["raw_sha256"]}
                if status == "downloaded"
                else (
                    {"sgf_sha256": game["sgf_sha256"]}
                    if status == "parsed"
                    else {"publication_key": manifest["publication_key"]} if status == "names_ready" else {}
                )
            )
            row = store.advance_item(source, source_id, status, expected_status=row["status"], **changes)


def reconcile_items(store, manifest, batch_row):
    """Catch item journal up to a durable batch receipt after a crash."""
    phases = ("names_ready", "test_published", "test_verified", "prod_published", "prod_synced")
    target = batch_row["status"]
    if target not in phases:
        return
    receipts = {
        "test_published": "test_receipt",
        "test_verified": "test_verification",
        "prod_published": "prod_receipt",
        "prod_synced": "prod_verification",
    }
    for game in manifest["games"]:
        source, source_id = game["source_key"], game["source_item_id"]
        row = _item_row(store, source, source_id)
        if row["status"] not in phases:
            raise ValueError("item journal is not ready for publication")
        for status in phases[phases.index(row["status"]) + 1 : phases.index(target) + 1]:
            receipt = batch_row[receipts[status]]
            if not isinstance(receipt, dict):
                raise ValueError("durable batch receipt missing")
            kwargs = {"expected_status": row["status"], "receipt": receipt}
            if status in ("test_published", "prod_published"):
                matches = [
                    entry
                    for entry in receipt["games"]
                    if (entry["source_key"], entry["source_item_id"]) == (source, source_id)
                ]
                if len(matches) != 1:
                    raise ValueError("batch receipt source mapping missing")
                kwargs["test_album_id" if status == "test_published" else "prod_album_id"] = matches[0]["album_id"]
            row = store.advance_item(source, source_id, status, **kwargs)


def record_staged_item(store, item):
    row = store.remember_item(
        "19x19",
        item["external_id"],
        raw_sha256=item.get("raw_sha256"),
        staging_path=item.get("raw_sgf_path"),
        source_metadata=item.get("metadata"),
    )
    if item["status"] == "downloaded" and row["status"] == "discovered":
        row = store.advance_item(
            "19x19",
            item["external_id"],
            "downloaded",
            expected_status="discovered",
            raw_sha256=item["raw_sha256"],
            staging_path=item["raw_sgf_path"],
            source_metadata=item.get("metadata"),
        )
    return row


def mark_needs_credentials(store, source_id):
    row = _item_row(store, "19x19", source_id)
    if row["status"] == "downloaded":
        return store.advance_item(
            "19x19", source_id, "retry_wait", expected_status="downloaded", error="needs_credentials"
        )
    return row


def resume_credential_item(store, source_id):
    row = _item_row(store, "19x19", source_id)
    if row["status"] == "retry_wait" and row.get("error") == "needs_credentials":
        return store.advance_item("19x19", source_id, "downloaded", expected_status="retry_wait")
    return row


def quarantine_staged_item(stage, store, source_id, reason):
    class PermanentPreparationError(ValueError):
        retryable = False

    stage.fail(source_id, PermanentPreparationError(reason))
    store.advance_item(
        "19x19",
        source_id,
        "quarantined",
        expected_status="downloaded",
        error=reason,
    )


async def resume_batch(store, manifest, digest, *, test_verify, sync, prod_verify, test_publish=None):
    """Recover at durable boundaries; an API timeout never repeats publication."""
    key = manifest["publication_key"]
    row = _batch_row(store, key)
    status = row["status"]
    if status == "names_ready":
        if test_publish is None:
            raise ValueError("test publisher is required")
        receipt = await _call(test_publish, manifest, digest)
        row = await asyncio.to_thread(
            store.advance_batch, key, "test_published", expected_status="names_ready", receipt=receipt
        )
        status = row["status"]
    if status == "test_published":
        result = await _call(test_verify, manifest, row["test_receipt"])
        result = {**result, "manifest_sha256": digest}
        row = await asyncio.to_thread(
            store.advance_batch, key, "test_verified", expected_status="test_published", receipt=result
        )
        status = row["status"]
    if status == "test_verified":
        response = await _call(sync, manifest, digest, row["test_verification"])
        receipt = response["receipt"]
        row = await asyncio.to_thread(
            store.advance_batch, key, "prod_published", expected_status="test_verified", receipt=receipt
        )
        status = row["status"]
    if status == "prod_published":
        result = await _call(prod_verify, manifest, row["prod_receipt"])
        result = {**result, "manifest_sha256": digest}
        row = await asyncio.to_thread(
            store.advance_batch, key, "prod_synced", expected_status="prod_published", receipt=result
        )
    return row


def _receiver_timeout(deadline):
    return max(1, deadline - time.monotonic())


class KifuIngestJob(BaseJob):
    name = "kifu_ingest"
    interval_seconds = 3600

    async def run(self):
        await asyncio.to_thread(self._run_lock)

    def _run_lock(self):
        # An async loop and its DB/network calls execute in this worker thread;
        # the main cron event loop remains free for analysis and other jobs.
        with _session_lock(engine) as acquired:
            if not acquired:
                logger.info("kifu ingest skipped: another run holds the session lock")
                return
            asyncio.run(self._run_locked())

    async def _run_locked(self):
        stage_root = Path(config.KIFU_INGEST_STAGING_DIR)
        stage = Stage(stage_root)
        store = StateStore(engine)
        deadline = time.monotonic() + config.KIFU_INGEST_TOTAL_SECONDS

        async with httpx.AsyncClient() as client:
            test_base = config.KIFU_INGEST_TEST_API_URL
            prod_base = config.KIFU_INGEST_PROD_API_URL

            async def test_verify(manifest, receipt):
                return await verify_album_api(client, test_base, manifest, receipt)

            async def prod_verify(manifest, receipt):
                return await verify_album_api(client, prod_base, manifest, receipt)

            def publish(manifest, digest):
                return publish_manifest(engine, manifest, expected_manifest_sha256=digest)

            def sync(manifest, digest, verification):
                return send_verified_manifest(
                    manifest,
                    digest,
                    verification,
                    host=config.KIFU_INGEST_SSH_HOST,
                    key_path=config.KIFU_INGEST_SSH_KEY,
                    known_hosts=config.KIFU_INGEST_KNOWN_HOSTS,
                    timeout=_receiver_timeout(deadline),
                )

            def check_identities(request):
                return check_production_identities(
                    request,
                    host=config.KIFU_INGEST_SSH_HOST,
                    key_path=config.KIFU_INGEST_SSH_KEY,
                    known_hosts=config.KIFU_INGEST_KNOWN_HOSTS,
                    timeout=_receiver_timeout(deadline),
                )

            package_dir = stage_root / "packages"
            if package_dir.is_symlink():
                raise ValueError("package directory symlink is unsafe")
            package_dir.mkdir(exist_ok=True)
            packaged_ids = set()

            async def process_manifest(manifest):
                digest = _validated(manifest)
                row = await asyncio.to_thread(register_frozen_batch, store, manifest["publication_key"], digest)
                for game in manifest["games"]:
                    await asyncio.to_thread(resume_credential_item, store, game["source_item_id"])
                await asyncio.to_thread(register_frozen_items, store, manifest)
                if row["manifest_sha256"] != digest:
                    raise ValueError("frozen package hash differs from durable batch")
                await asyncio.to_thread(reconcile_items, store, manifest, row)
                if row["status"] != "prod_synced":
                    row = await resume_batch(
                        store,
                        manifest,
                        digest,
                        test_verify=test_verify,
                        sync=sync,
                        prod_verify=prod_verify,
                        test_publish=publish,
                    )
                    await asyncio.to_thread(reconcile_items, store, manifest, row)

            failed_packages = 0
            for path in sorted(package_dir.glob("*.json")):
                if time.monotonic() + 350 >= deadline:
                    if failed_packages:
                        raise RuntimeError(f"kifu round failed: {failed_packages} package(s)")
                    return
                try:
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                    packaged_ids.update(game["source_item_id"] for game in manifest["games"])
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    failed_packages += 1
                    logger.error("kifu package %s could not be read: %s", path.name, exc)
                    continue
                failed_packages += await process_package_queue(
                    store, [manifest], process_manifest, timeout_seconds=max(1, deadline - time.monotonic())
                )

            if time.monotonic() >= deadline:
                if failed_packages:
                    raise RuntimeError(f"kifu round failed: {failed_packages} package(s)")
                return
            with engine.connect() as connection:
                known = set(connection.scalars(select(items.c.external_id)))
            known.update(await asyncio.to_thread(known_source_ids, engine))
            known.update(historical_excluded_ids())
            source = Source19x19(client, deadline=min(deadline, time.monotonic() + config.KIFU_INGEST_SOURCE_SECONDS))
            discovery = await discover_and_download(
                source,
                stage,
                known,
                max_downloads=config.KIFU_INGEST_MAX_GAMES,
                deadline=min(deadline, time.monotonic() + config.KIFU_INGEST_SOURCE_SECONDS),
            )
            for item in discovery["items"]:
                await asyncio.to_thread(record_staged_item, store, item)
            ledger = DailyTokenBudget(stage_root, config.KIFU_INGEST_MAX_TOKENS, stage._atomic)

            async def audit_call(entry):
                await asyncio.to_thread(ledger.record_call, entry)

            async def reserve_call(upper_bound):
                return await asyncio.to_thread(ledger.reserve, upper_bound)

            async def settle_call(reservation_id, actual_tokens):
                return await asyncio.to_thread(ledger.settle, reservation_id, actual_tokens)

            names = QwenNameService(
                client,
                key=(
                    config.DASHSCOPE_API_KEY
                    if config.KIFU_INGEST_LLM_ENABLED
                    and config.KIFU_INGEST_MAX_TOKENS > 0
                    and config.KIFU_INGEST_MAX_NEW_NAMES > 0
                    else None
                ),
                max_items=max(1, config.KIFU_INGEST_MAX_NEW_NAMES),
                max_total_tokens=config.KIFU_INGEST_MAX_TOKENS if config.KIFU_INGEST_LLM_ENABLED else 0,
                audit_call=audit_call,
                reserve_call=reserve_call,
                settle_call=settle_call,
                initial_tokens_used=await asyncio.to_thread(ledger.spent),
            )
            needs_credentials = 0
            prepared = 0
            records = []
            for item in discovery["items"]:
                if (
                    time.monotonic() + 350 >= deadline
                    or len(records) >= config.KIFU_INGEST_MAX_GAMES
                    or item["status"] != "downloaded"
                    or item["external_id"] in packaged_ids
                ):
                    continue
                if names.key:
                    await asyncio.to_thread(resume_credential_item, store, item["external_id"])
                try:
                    game = await derive_staged_record(item)
                except ValueError as exc:
                    await asyncio.to_thread(quarantine_staged_item, stage, store, item["external_id"], str(exc))
                    logger.error("kifu preparation quarantined source %s", item["external_id"])
                    continue
                records.append((item, game))

            if names.key and records:
                players = {game["metadata"][f"player_{slot}"] for _, game in records for slot in ("black", "white")}
                events = {game["metadata"]["event"] for _, game in records}
                resolved = await asyncio.to_thread(
                    lookup_qualified_identities, engine, player_values=players, event_values=events
                )
                event_templates = await asyncio.to_thread(qualified_raw_event_templates, engine, raw_values=events)
                ambiguous_items = []
                candidates, deferred = await select_portable_review_items(
                    records,
                    resolved,
                    check_identities=check_identities,
                    reusable_events=set(event_templates["templates"]),
                    max_new_names=config.KIFU_INGEST_MAX_NEW_NAMES,
                    isolated=ambiguous_items,
                )
                for source_id, reason in ambiguous_items:
                    await asyncio.to_thread(quarantine_staged_item, stage, store, source_id, reason)
                if deferred:
                    logger.info("kifu deferred %d staged games beyond the new-name budget", len(deferred))
            else:
                candidates = [item for item, _ in records]

            for group in group_staged_items(candidates, review_enabled=bool(names.key)):
                if time.monotonic() + 350 >= deadline:
                    break
                isolated = []
                try:
                    manifest = await asyncio.wait_for(
                        prepare_staged_games(
                            group,
                            engine=engine,
                            client=client,
                            names=names,
                            isolated=isolated,
                            check_identities=check_identities,
                        ),
                        timeout=max(1, deadline - time.monotonic() - 350),
                    )
                except NeedsCredentials:
                    isolated_ids = {source_id for source_id, _ in isolated}
                    needs_credentials += len(group) - len(isolated_ids)
                    for item in group:
                        if item["external_id"] not in isolated_ids:
                            await asyncio.to_thread(mark_needs_credentials, store, item["external_id"])
                    continue
                except NameRejected as exc:
                    logger.error("kifu name review rejected %d staged games: %s", len(group), exc)
                    continue
                except NameServiceError as exc:
                    logger.error("kifu name service deferred: %s", exc)
                    break
                except ValueError as exc:
                    logger.error("kifu batch preparation deferred %d games: %s", len(group), exc)
                    continue
                finally:
                    for source_id, reason in isolated:
                        await asyncio.to_thread(quarantine_staged_item, stage, store, source_id, reason)
                digest = canonical_sha256(manifest)
                package = package_dir / f"{manifest['games'][0]['source_item_id']}-{digest[:16]}.json"
                payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
                if package.exists() and package.read_bytes() != payload:
                    raise ValueError("frozen package content changed")
                if not package.exists():
                    stage._atomic(package, payload)
                packaged_ids.update(game["source_item_id"] for game in manifest["games"])
                prepared += len(manifest["games"])
                failed_packages += await process_package_queue(
                    store, [manifest], process_manifest, timeout_seconds=max(1, deadline - time.monotonic())
                )
            unprepared = [
                item["external_id"]
                for item in discovery["items"]
                if item["status"] == "downloaded" and item["external_id"] not in packaged_ids
            ]
            if unprepared:
                logger.error(
                    "kifu pending: %d downloaded SGFs lack a reviewed package; needs_credentials=%d",
                    len(unprepared),
                    needs_credentials,
                )
            logger.info(
                "kifu discovery %s: downloaded=%s, pending=%s, deferred_until=%s",
                discovery["status"],
                discovery["downloaded"],
                sum(item["status"] != "downloaded" for item in discovery["items"]),
                discovery["deferred_until"],
            )
            if discovery["status"] == "partial":
                logger.error("kifu discovery partial; deferred_until=%s", discovery["deferred_until"])
            if discovery["errors"] or failed_packages:
                raise RuntimeError(
                    f"kifu round failed: {len(discovery['errors'])} source request(s), "
                    f"{failed_packages} package(s); downloaded items were retained and processed"
                )
