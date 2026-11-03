"""Hourly orchestration with a real temporary journal/Stage and no network."""

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.pool import StaticPool

from katrain.cron.jobs import kifu_ingest as job
from katrain.kifu_ingest.orchestration import derive_staged_record
from katrain.kifu_ingest.staging import Stage
from katrain.kifu_ingest.state import StateStore, batches, items, metadata
from katrain.web.kifu.name_candidates import canonical_sha256


def source_metadata(source_id, *, old=False, black="Black"):
    now = datetime.now(timezone(timedelta(hours=8))).replace(hour=12, minute=0, second=0, microsecond=0)
    played = now - timedelta(days=1000 if old else 1)
    return {
        "id": int(source_id),
        "pb": black,
        "pw": "White",
        "gamename": "Event",
        "playTime": {
            "date": {"year": played.year, "month": played.month, "day": played.day},
            "time": {"hour": played.hour, "minute": played.minute, "second": played.second},
        },
    }


SGF = "(;GM[1]SZ[19]PB[Black]PW[White]EV[Event];B[aa])"


@pytest.fixture
def hourly(tmp_path, monkeypatch):
    database = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    metadata.create_all(database)
    monkeypatch.setattr(job, "engine", database)
    monkeypatch.setattr(job.config, "KIFU_INGEST_STAGING_DIR", str(tmp_path))
    for key, value in {
        "TOTAL_SECONDS": 3300,
        "SOURCE_SECONDS": 600,
        "MAX_GAMES": 100,
        "MAX_NEW_NAMES": 20,
        "MAX_TOKENS": 0,
        "LLM_ENABLED": False,
        "WINDOW_DAYS": 7,
        "HEAD_PAGES": 5,
        "MAX_REQUESTS": 160,
        "MAX_RECHECKS": 20,
        "RECOVERY_SECONDS": 300,
    }.items():
        monkeypatch.setattr(job.config, "KIFU_INGEST_" + key, value, raising=False)
    monkeypatch.setattr(job.config, "KIFU_INGEST_TEST_API_URL", "https://test.invalid")
    monkeypatch.setattr(job.config, "KIFU_INGEST_PROD_API_URL", "https://prod.invalid")
    monkeypatch.setattr(job, "historical_excluded_ids", lambda: {"999"})
    monkeypatch.setattr(job, "_validated", canonical_sha256)
    state = SimpleNamespace(
        database=database,
        store=StateStore(database),
        root=tmp_path,
        pages=[],
        events=[],
        published=set(),
        lookups=[],
        failures=set(),
        ticks=None,
        sgf_errors={},
        sgfs={},
    )

    async def forbidden(*args, **kwargs):
        pytest.fail("real HTTP is forbidden in orchestration tests")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)

    class Source:
        def __init__(self, client, *, deadline):
            self.deadline, self.requests, self.max_requests = deadline, 0, 240

        async def fetch_page(self, page):
            self.requests += 1
            state.events.append(("page", page))
            return state.pages if page == 0 else []

        async def fetch_sgf(self, source_id):
            self.requests += 1
            state.events.append(("sgf", source_id))
            if source_id in state.sgf_errors:
                raise state.sgf_errors[source_id]
            return state.sgfs.get(source_id, SGF)

    monkeypatch.setattr(job, "Source19x19", Source)

    def published(database, *, candidate_ids=None):
        assert candidate_ids is not None, "hourly lookup must not enumerate the full catalog"
        state.lookups.append(set(candidate_ids))
        return state.published & set(candidate_ids)

    monkeypatch.setattr(job, "known_source_ids", published)

    async def prepare(group, **kwargs):
        state.events.append(("prepare", tuple(i["external_id"] for i in group)))
        games = [await derive_staged_record(i) for i in group]
        return {"publication_key": "new-" + games[0]["source_item_id"], "games": games, "decisions": []}

    monkeypatch.setattr(job, "prepare_staged_games", prepare)

    def receipt(manifest):
        return {
            "games": [
                {
                    "source_key": "19x19",
                    "source_item_id": game["source_item_id"],
                    "album_id": int(game["source_item_id"]),
                }
                for game in manifest["games"]
            ]
        }

    state.receipt = receipt

    def report(manifest, receipt):
        return {
            "status": "verified",
            "manifest_sha256": canonical_sha256(manifest),
            "games": len(manifest["games"]),
            "checks": [
                {"album_id": game["album_id"], "lang": lang}
                for game in receipt["games"]
                for lang in ("cn", "tw", "jp", "ko", "en")
            ],
        }

    state.report = report

    def publish(database, manifest, **kwargs):
        state.events.append(("publish", manifest["publication_key"]))
        state.published.update(g["source_item_id"] for g in manifest["games"])
        state.cache_ids = getattr(state, "cache_ids", []) + [id(kwargs.get("sgf_cache"))]
        return receipt(manifest)

    monkeypatch.setattr(job, "publish_manifest", publish)

    def sync(manifest, *args, **kwargs):
        state.events.append(("sync", manifest["publication_key"]))
        return {"receipt": receipt(manifest)}

    monkeypatch.setattr(job, "send_verified_manifest", sync)

    async def verify(client, base, manifest, receipt, **kwargs):
        state.events.append(("verify", manifest["publication_key"], base, kwargs))
        if state.ticks is not None:
            state.ticks[0] += 80
        if manifest["publication_key"] in state.failures:
            raise httpx.ReadTimeout("")
        return report(manifest, receipt)

    monkeypatch.setattr(job, "verify_album_api", verify)
    yield state
    database.dispose()


def freeze(h, source_id, *, phase="test_published", old=False, original=True):
    stage = Stage(h.root)
    meta = source_metadata(source_id, old=old)
    item = stage.remember(meta)
    if original:
        stage.save_sgf(source_id, SGF)
    game = {
        "source_key": "19x19",
        "source_item_id": source_id,
        "raw_sha256": sha256(SGF.encode()).hexdigest(),
        "sgf_sha256": sha256(SGF.encode()).hexdigest(),
        "metadata": {"player_black": "Black", "player_white": "White", "event": "Event"},
    }
    manifest = {"publication_key": "frozen-" + source_id, "games": [game]}
    (h.root / "packages").mkdir(exist_ok=True)
    (h.root / "packages" / (source_id + ".json")).write_text(json.dumps(manifest))
    row = job.register_frozen_batch(h.store, manifest["publication_key"], canonical_sha256(manifest))
    job.register_frozen_items(h.store, manifest)
    for target in ("test_published", "test_verified", "prod_published", "prod_synced"):
        receipt = h.receipt(manifest)
        row = h.store.advance_batch(
            manifest["publication_key"],
            target,
            expected_status=row["status"],
            receipt=h.report(manifest, receipt) if target in {"test_verified", "prod_synced"} else receipt,
        )
        job.reconcile_items(h.store, manifest, row)
        if target == phase:
            break
    return manifest


def batch(h, key):
    return job._batch_row(h.store, key)


@pytest.mark.asyncio
async def test_current_rank_supplement_cannot_fill_original_test_authorization(hourly, monkeypatch):
    h = hourly
    manifest = freeze(h, "31")
    before = deepcopy(batch(h, manifest["publication_key"]))

    async def current_report(*args):
        return {"status": "current_rank_verified", "algorithm": "kifu-current-rank-verification-v1"}

    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "disabled")
    with pytest.raises(ValueError, match="verification"):
        await job.resume_batch(
            h.store,
            manifest,
            canonical_sha256(manifest),
            test_verify=current_report,
            sync=lambda *a: pytest.fail("current supplement authorized production"),
            prod_verify=lambda *a: pytest.fail("unpublished PROD was verified"),
        )
    assert batch(h, manifest["publication_key"]) == before
    assert before["test_verification"] is None


@pytest.mark.asyncio
async def test_rank_test_report_receipt_hash_is_pinned_before_durable_advance(hourly, monkeypatch):
    from tests.test_kifu_api_verification import rank_api

    h, api = hourly, rank_api()
    async with api.client() as client:
        from katrain.kifu_ingest.sync import verify_album_api

        report = await verify_album_api(client, "https://test.invalid", api.manifest, api.receipt)
    manifest, digest = api.manifest, canonical_sha256(api.manifest)
    row = job.register_frozen_batch(h.store, manifest["publication_key"], digest)
    actual_receipt = {**api.receipt, "batch_id": 123}
    h.store.advance_batch(
        manifest["publication_key"], "test_published", expected_status=row["status"], receipt=actual_receipt
    )
    before = deepcopy(batch(h, manifest["publication_key"]))
    monkeypatch.setenv("KIFU_SEARCH_SYNC_MODE", "disabled")
    with pytest.raises(ValueError, match="receipt"):
        await job.resume_batch(
            h.store,
            manifest,
            digest,
            test_verify=lambda *a: report,
            sync=lambda *a: pytest.fail("wrong receipt report authorized production"),
            prod_verify=lambda *a: pytest.fail("unpublished PROD was verified"),
        )
    assert batch(h, manifest["publication_key"]) == before


@pytest.mark.asyncio
async def test_hourly_rank_context_loaders_use_local_test_and_fixed_production_roles(hourly, monkeypatch):
    from katrain.kifu_ingest import catalog, sync as transport

    h = hourly
    freeze(h, "32")
    h.pages = [source_metadata("32")]
    monkeypatch.setattr(job.config, "KIFU_INGEST_SSH_HOST", "role-host")
    monkeypatch.setattr(job.config, "KIFU_INGEST_SSH_KEY", "/role/key")
    monkeypatch.setattr(job.config, "KIFU_INGEST_KNOWN_HOSTS", "/role/known_hosts")
    calls = []

    def local(db, manifest_sha256, receipt_sha256, *, deadline):
        assert db is h.database
        assert 0 < deadline - job.time.monotonic() <= 12
        calls.append(("local", manifest_sha256, receipt_sha256))
        return {"local": True}

    def remote(**kwargs):
        assert kwargs == {
            "host": "role-host",
            "key_path": "/role/key",
            "known_hosts": "/role/known_hosts",
            "manifest_sha256": "a" * 64,
            "receipt_sha256": "b" * 64,
            "timeout": 12,
        }
        calls.append(("remote", kwargs["manifest_sha256"], kwargs["receipt_sha256"]))
        return {"remote": True}

    monkeypatch.setattr(catalog, "resolve_rank_publication_context", local, raising=False)
    monkeypatch.setattr(transport, "read_rank_publication_context", remote, raising=False)

    async def verify(client, base, manifest, receipt, **kwargs):
        loader = kwargs["rank_context_loader"]
        context = loader("a" * 64, "b" * 64, timeout=12)
        assert context == ({"local": True} if base == "https://test.invalid" else {"remote": True})
        return h.report(manifest, receipt)

    monkeypatch.setattr(job, "verify_album_api", verify)
    await job.KifuIngestJob()._run_locked()
    assert calls == [("local", "a" * 64, "b" * 64), ("remote", "a" * 64, "b" * 64)]
    assert batch(h, "frozen-32")["status"] == "prod_synced"


@pytest.fixture
def superseded_hourly(hourly, monkeypatch):
    """Actual native/repair rows, hourly journal/Stage and actual API serializers."""
    from sqlalchemy.orm import Session
    from katrain.kifu_ingest import catalog, sync as transport
    from katrain.web.api.v1.endpoints import kifu
    from tests.web_ui.test_kifu_historical_rank_native import (
        authority_state,
        make_engine,
        repaired_legacy_publication,
    )

    h = hourly
    test_db, prod_db = make_engine(h.root / "test.db"), make_engine(h.root / "prod.db")
    metadata.create_all(test_db)
    h.database, h.store = test_db, StateStore(test_db)
    monkeypatch.setattr(job, "engine", test_db)
    monkeypatch.setattr(kifu.settings, "KIFU_SEARCH_BACKEND", "legacy")
    client_type = httpx.AsyncClient

    async def handle(request):
        db = test_db if request.url.host == "test.invalid" else prod_db
        with Session(db) as session:
            if request.url.path.endswith("/albums"):
                value = kifu.read_album_page(
                    session,
                    q=request.url.params.get("q"),
                    lang=request.url.params.get("lang", "cn"),
                    page=int(request.url.params.get("page", 1)),
                    page_size=int(request.url.params.get("page_size", 100)),
                )
            else:
                value = kifu.read_album_detail(
                    session, int(request.url.path.rsplit("/", 1)[1]), lang=request.url.params.get("lang", "cn")
                )
            return httpx.Response(200, json=value.model_dump(mode="json"))

    def client_factory(*args, **kwargs):
        return client_type(*args, transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(job, "verify_album_api", transport.verify_album_api)
    pins = SimpleNamespace(test_db=test_db, prod_db=prod_db, syncs=[], replays=[])
    meta = source_metadata("99600", black="Black Alias")
    meta.update(pw="White Alias", gamename="Summer Cup")
    pins.source_metadata = meta

    def before_repair(manifest, receipt):
        async def capture():
            async with client_factory() as client:
                result = await transport.verify_album_api(client, "https://test.invalid", manifest, receipt)
            result["manifest_sha256"] = canonical_sha256(manifest)
            transport.validate_test_verification(manifest, canonical_sha256(manifest), result)
            pins.original_report = result

        asyncio.run(capture())

    def prepare():
        return repaired_legacy_publication(test_db, games=5, source_metadata=meta, before_repair=before_repair)

    pins.prepare = prepare

    def publish(db, manifest, **kwargs):
        assert db is test_db
        result = catalog.publish_manifest(test_db, manifest, expected_manifest_sha256=canonical_sha256(manifest))
        pins.replays.append(deepcopy(result))
        return result

    def sync(manifest, digest, verification, **kwargs):
        transport.validate_test_verification(manifest, digest, verification)
        pins.syncs.append(deepcopy((manifest, digest, verification)))
        return {"receipt": catalog.publish_manifest(prod_db, manifest, expected_manifest_sha256=digest)}

    def remote(**kwargs):
        assert kwargs["host"] == job.config.KIFU_INGEST_SSH_HOST
        assert kwargs["key_path"] == job.config.KIFU_INGEST_SSH_KEY
        assert kwargs["known_hosts"] == job.config.KIFU_INGEST_KNOWN_HOSTS
        return catalog.resolve_rank_publication_context(
            prod_db,
            kwargs["manifest_sha256"],
            kwargs["receipt_sha256"],
            deadline=job.time.monotonic() + kwargs["timeout"],
        )

    monkeypatch.setattr(job, "publish_manifest", publish)
    monkeypatch.setattr(job, "send_verified_manifest", sync)
    monkeypatch.setattr(transport, "read_rank_publication_context", remote, raising=False)
    h.pins = pins
    h.authority_state = authority_state
    yield h
    test_db.dispose()
    prod_db.dispose()


def journal_superseded_package(h, manifest, receipt, *, saved_original=True):
    stage = Stage(h.root)
    for game in manifest["games"]:
        source_id = game["source_item_id"]
        meta = {**game["source_metadata"], "id": int(source_id)}
        stage.remember(meta)
        stage.save_sgf(source_id, game["sgf_content"])
        h.sgfs[source_id] = game["sgf_content"]
        h.pages.append(meta)
    (h.root / "packages").mkdir(exist_ok=True)
    (h.root / "packages" / "superseded.json").write_text(json.dumps(manifest))
    row = job.register_frozen_batch(h.store, manifest["publication_key"], canonical_sha256(manifest))
    job.register_frozen_items(h.store, manifest)
    row = h.store.advance_batch(
        manifest["publication_key"], "test_published", expected_status=row["status"], receipt=receipt
    )
    if saved_original:
        row = h.store.advance_batch(
            manifest["publication_key"], "test_verified", expected_status=row["status"], receipt=h.pins.original_report
        )
    job.reconcile_items(h.store, manifest, row)


@pytest.mark.asyncio
@pytest.mark.parametrize("expired", [False, True])
async def test_supersession_hourly_uses_real_window_scope_and_preserves_original_report(
    superseded_hourly, monkeypatch, expired
):
    from katrain.web.kifu import search_sync
    from katrain.web.core import models_db as models
    from tests.web_ui.test_kifu_historical_rank_native import seed_professional_black_identity

    h = superseded_hourly
    if expired:
        played = job.match_time(h.pins.source_metadata) - timedelta(days=8)
        h.pins.source_metadata["playTime"] = {
            "date": {"year": played.year, "month": played.month, "day": played.day},
            "time": {"hour": played.hour, "minute": played.minute, "second": played.second},
        }
    manifest, receipt, part, _ = await asyncio.to_thread(h.pins.prepare)
    assert len(manifest["games"]) == 5 and len(part["changes"]) == 10
    assert {game["rank_snapshots"]["black"]["rank_system"] for game in manifest["games"]} == {"professional_dan"}
    assert {change["snapshot_after"]["rank_system"] for change in part["changes"]} == {"dan_unspecified"}
    if not expired:
        # PROD independently approves the same identity capture before its first native publication.
        seed_professional_black_identity(h.pins.prod_db)
    journal_superseded_package(h, manifest, receipt)
    original = deepcopy((manifest, receipt, h.pins.original_report))
    before_test = h.authority_state(h.database)
    scopes = []
    real_scope = job._frozen_scope

    def scope(package, row, stage, discovery):
        result = real_scope(package, row, stage, discovery)
        scopes.append(result)
        if not expired:
            assert set(discovery["checked_ids"]) == {g["source_item_id"] for g in package["games"]}
            for game in package["games"]:
                observed = stage.manifest["items"][game["source_item_id"]]
                assert observed["recent"]["raw_sha256"] == observed["raw_sha256"] == game["raw_sha256"]
        return result

    monkeypatch.setattr(job, "_frozen_scope", scope)
    # Exercise resume's existing TEST search-repair replay without an external ES service.
    monkeypatch.setattr(search_sync, "sync_mode", lambda: "enabled")
    search_calls = []
    monkeypatch.setattr(
        search_sync, "begin_sync", lambda conn, operation, reference: search_calls.append(("begin", operation))
    )
    monkeypatch.setattr(search_sync, "finish_sync", lambda *a: search_calls.append(("finish",)))
    await job.KifuIngestJob()._run_locked()
    row = batch(h, manifest["publication_key"])
    assert scopes == ["test_verify" if expired else "recent"]
    assert row["test_verification"] == original[2]
    assert row["test_receipt"] == receipt and row["manifest_sha256"] == canonical_sha256(manifest)
    assert h.authority_state(h.database) == before_test
    if expired:
        assert row["status"] == "test_verified" and row["prod_receipt"] is None
        assert not h.pins.syncs
        assert search_calls == [("begin", "catalog_publish"), ("finish",)]
    else:
        assert row["status"] == "prod_synced"
        assert h.pins.replays == [receipt]
        assert h.pins.syncs == [(manifest, canonical_sha256(manifest), original[2])]
        assert search_calls == [("begin", "catalog_publish"), ("finish",)] * 2
        with h.pins.prod_db.connect() as conn:
            snapshots = conn.execute(select(models.KifuAlbumRankSnapshot.snapshot)).scalars().all()
        assert len(snapshots) == 10 and {s["version"] for s in snapshots} == {"kifu-rank-snapshot-v1"}
        before_prod = h.authority_state(h.pins.prod_db)
        await job.KifuIngestJob()._run_locked()
        assert len(h.pins.syncs) == 1
        assert h.authority_state(h.pins.prod_db) == before_prod
    assert (manifest, receipt, h.pins.original_report) == original


@pytest.mark.asyncio
async def test_supersession_valid_current_api_without_original_report_cannot_advance(superseded_hourly, monkeypatch):
    from katrain.kifu_ingest import catalog, sync as transport
    from katrain.web.kifu import search_sync

    h = superseded_hourly
    manifest, receipt, _, _ = await asyncio.to_thread(h.pins.prepare)
    journal_superseded_package(h, manifest, receipt, saved_original=False)
    before = deepcopy(batch(h, manifest["publication_key"]))
    context = catalog.resolve_rank_publication_context(
        h.database, canonical_sha256(manifest), canonical_sha256(receipt)
    )
    async with httpx.AsyncClient() as client:
        report = await transport.verify_album_api(
            client,
            "https://test.invalid",
            manifest,
            receipt,
            rank_context_loader=lambda *a, **kw: context,
        )
    transport.validate_current_rank_verification(manifest, receipt, report, context, "https://test.invalid")
    assert report["status"] == "current_rank_verified"
    monkeypatch.setattr(search_sync, "sync_mode", lambda: "disabled")
    with pytest.raises(ValueError, match="verification"):
        await job.resume_batch(
            h.store,
            manifest,
            canonical_sha256(manifest),
            test_verify=lambda *a: report,
            sync=lambda *a: pytest.fail("current supplement authorized PROD"),
            prod_verify=lambda *a: None,
        )
    assert batch(h, manifest["publication_key"]) == before
    assert before["status"] == "test_published" and before["test_verification"] is None
    assert not h.pins.syncs


@pytest.mark.asyncio
async def test_supersession_prod_published_saves_current_supplement_and_keeps_original_test_authorization(
    superseded_hourly, monkeypatch
):
    from katrain.web.kifu import search_sync
    from tests.web_ui.test_kifu_historical_rank_native import repaired_legacy_publication

    h = superseded_hourly
    manifest, receipt, _, _ = await asyncio.to_thread(h.pins.prepare)
    prod_manifest, prod_receipt, _, _ = await asyncio.to_thread(
        repaired_legacy_publication, h.pins.prod_db, games=5, source_metadata=h.pins.source_metadata
    )
    assert prod_manifest == manifest
    journal_superseded_package(h, manifest, receipt)
    row = h.store.advance_batch(
        manifest["publication_key"], "prod_published", expected_status="test_verified", receipt=prod_receipt
    )
    job.reconcile_items(h.store, manifest, row)
    original_report = deepcopy(row["test_verification"])
    before_prod = h.authority_state(h.pins.prod_db)
    monkeypatch.setattr(search_sync, "sync_mode", lambda: "enabled")
    monkeypatch.setattr(search_sync, "begin_sync", lambda *a: None)
    monkeypatch.setattr(search_sync, "finish_sync", lambda *a: None)
    await job.KifuIngestJob()._run_locked()
    row = batch(h, manifest["publication_key"])
    assert row["status"] == "prod_synced"
    assert row["prod_receipt"] == prod_receipt and row["test_receipt"] == receipt
    assert row["test_verification"] == original_report
    assert row["prod_verification"]["status"] == "current_rank_verified"
    assert h.pins.syncs == [(manifest, canonical_sha256(manifest), original_report)]
    assert h.authority_state(h.pins.prod_db) == before_prod
    with pytest.raises(ValueError, match="verification"):
        job.validate_test_verification(manifest, canonical_sha256(manifest), row["prod_verification"])
    await job.KifuIngestJob()._run_locked()
    assert len(h.pins.syncs) == 1 and h.authority_state(h.pins.prod_db) == before_prod


@pytest.mark.asyncio
async def test_rank_context_failure_has_no_publication_fallback(hourly, monkeypatch):
    from katrain.kifu_ingest import catalog
    from katrain.web.kifu import search_sync

    h = hourly
    manifest = freeze(h, "33")
    h.pages = [source_metadata("33")]
    monkeypatch.setattr(search_sync, "sync_mode", lambda: "disabled")

    def unavailable(*args, **kwargs):
        raise ValueError("rank publication context unavailable")

    monkeypatch.setattr(catalog, "resolve_rank_publication_context", unavailable)

    async def verify(client, base, manifest, receipt, **kwargs):
        return kwargs["rank_context_loader"]("a" * 64, "b" * 64, timeout=1)

    monkeypatch.setattr(job, "verify_album_api", verify)
    with pytest.raises(RuntimeError, match="package"):
        await job.KifuIngestJob()._run_locked()
    row = batch(h, manifest["publication_key"])
    assert row["status"] == "retry_wait" and row["resume_phase"] == "test_published"
    assert row["test_verification"] is None and row["test_receipt"] == h.receipt(manifest)
    assert not [e for e in h.events if e[0] in {"prepare", "publish", "sync"}]


@pytest.mark.asyncio
async def test_recent_pipeline_precedes_failed_old_verification_and_does_not_repeat(hourly, caplog):
    h = hourly
    old = freeze(h, "78", phase="prod_published", old=True)
    Stage(h.root).remember(source_metadata("2021", old=True))
    h.failures.add(old["publication_key"])
    h.pages = [
        source_metadata("1", black="WrongBlack"),
        source_metadata("2"),
        source_metadata("6"),
        source_metadata("999"),
    ]
    with caplog.at_level("INFO", logger=job.logger.name), pytest.raises(RuntimeError, match="package"):
        await job.KifuIngestJob()._run_locked()
    assert "actionable_window_pending=0" in caplog.text
    assert "terminal=1" in caplog.text
    assert h.events[0] == ("page", 0)
    assert batch(h, "new-2")["status"] == "prod_synced"
    assert job._item_row(h.store, "19x19", "1")["status"] == "quarantined"
    assert "ReadTimeout" in batch(h, "frozen-78")["error"]
    assert batch(h, "frozen-78")["resume_phase"] == "prod_published"
    assert not any(e[0] == "prepare" and "1" in e[1] for e in h.events)
    assert h.events.index(("sync", "new-2")) < next(
        i for i, e in enumerate(h.events) if e[:2] == ("verify", "frozen-78")
    )
    assert h.lookups == [{"1", "2", "6"}]
    assert len(h.cache_ids) == 2 and len(set(h.cache_ids)) == 1
    assert not h.database.connect().scalar(select(items.c.id).where(items.c.external_id == "2021"))
    calls = [e for e in h.events if e[0] in {"prepare", "publish", "sync"}]
    await job.KifuIngestJob()._run_locked()
    assert [e for e in h.events if e[0] in {"prepare", "publish", "sync"}] == calls
    assert job._item_row(h.store, "19x19", "1")["status"] == "quarantined"


@pytest.mark.asyncio
async def test_recent_frozen_test_receipt_continues_to_prod_without_prepare(hourly):
    h = hourly
    freeze(h, "3")
    h.pages = [source_metadata("3")]
    await job.KifuIngestJob()._run_locked()
    assert batch(h, "frozen-3")["status"] == "prod_synced"
    assert ("sync", "frozen-3") in h.events
    assert not [e for e in h.events if e[0] in {"prepare", "publish"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason", ["source_changed", "unchecked", "different_raw_baseline", "missing_original_baseline"]
)
async def test_unverified_source_version_never_publishes_frozen_test_package(hourly, monkeypatch, reason):
    h = hourly
    manifest = freeze(h, "4", original=reason not in {"different_raw_baseline", "missing_original_baseline"})
    h.pages = [source_metadata("4", black="Changed" if reason == "source_changed" else "Black")]
    if reason == "unchecked":
        monkeypatch.setattr(job.config, "KIFU_INGEST_MAX_GAMES", 0)
    if reason == "different_raw_baseline":
        manifest["games"][0]["raw_sha256"] = "b" * 64
        (h.root / "packages" / "4.json").write_text(json.dumps(manifest))
        with h.database.begin() as c:
            c.execute(
                update(batches)
                .where(batches.c.publication_key == "frozen-4")
                .values(manifest_sha256=canonical_sha256(manifest))
            )
    await job.KifuIngestJob()._run_locked()
    assert not [e for e in h.events if e[0] in {"publish", "sync"}]
    assert batch(h, "frozen-4")["status"] != "prod_synced"
    if reason == "missing_original_baseline":
        row = batch(h, "frozen-4")
        assert row["status"] == "quarantined" and row["error"] == "source_version_mismatch"
        assert row["test_receipt"] == h.receipt(manifest)
        observed = Stage(h.root).manifest["items"]["4"]
        assert observed["raw_sha256"] is None and observed["raw_sgf_path"] is None
        assert observed["recent"]["raw_sha256"] == manifest["games"][0]["raw_sha256"]


@pytest.mark.asyncio
async def test_historical_test_receipt_verifies_only_and_shared_tail_deadline(hourly, monkeypatch):
    h = hourly
    freeze(h, "10", old=True)
    freeze(h, "11", phase="prod_published", old=True)
    freeze(h, "12", phase="prod_published", old=True)
    h.ticks = [1000.0]
    monkeypatch.setattr(job.time, "monotonic", lambda: h.ticks[0])
    await job.KifuIngestJob()._run_locked()
    verifications = [e for e in h.events if e[0] == "verify"]
    assert len(verifications) == 3
    assert {e[3]["deadline"] for e in verifications} == {1300.0}
    assert all(e[3]["checkpoint_dir"] == h.root / "api-verification" for e in verifications)
    assert batch(h, "frozen-10")["status"] == "test_verified"
    assert not [e for e in h.events if e[0] in {"prepare", "publish", "sync"}]


@pytest.mark.asyncio
async def test_publication_overrun_finishes_writer_and_stops_next_package(hourly, monkeypatch):
    h = hourly
    h.pages = [source_metadata("20"), source_metadata("21")]
    ticks = [1000.0]
    monkeypatch.setattr(job.time, "monotonic", lambda: ticks[0])
    writers = []

    def slow_publish(database, manifest, **kwargs):
        writers.append(manifest["publication_key"])
        ticks[0] = 5000.0
        # Leave the writer thread active while the event loop sees the expired
        # budget. Cancelling its await must never discard its native receipt.
        import time

        time.sleep(0.02)
        return h.receipt(manifest)

    monkeypatch.setattr(job, "publish_manifest", slow_publish)
    await job.KifuIngestJob()._run_locked()
    assert writers == ["new-20"]
    assert batch(h, "new-20")["status"] == "test_published"
    assert not [e for e in h.events if e[0] == "sync"]


@pytest.mark.asyncio
async def test_remote_publication_keeps_writer_until_native_receipt_after_budget(hourly, monkeypatch):
    h = hourly
    h.pages = [source_metadata("20"), source_metadata("21")]
    ticks = [1000.0]
    monkeypatch.setattr(job.time, "monotonic", lambda: ticks[0])
    calls = []

    def slow_remote(manifest, *args, **kwargs):
        calls.append(manifest["publication_key"])
        assert kwargs["timeout"] is None, "SSH timeout cannot cancel a remote Docker writer"
        ticks[0] = 5000.0
        return {"receipt": h.receipt(manifest)}

    monkeypatch.setattr(job, "send_verified_manifest", slow_remote)
    await job.KifuIngestJob()._run_locked()
    assert calls == ["new-20"]
    assert batch(h, "new-20")["status"] == "prod_published"
    assert batch(h, "new-20")["prod_receipt"] == h.receipt({"games": [{"source_item_id": "20"}]})


def test_config_clamps_existing_oversized_source_and_new_budgets(monkeypatch):
    import importlib
    from katrain.cron import config

    with monkeypatch.context() as environment:
        for key in ("SOURCE_SECONDS", "RECOVERY_SECONDS", "WINDOW_DAYS", "HEAD_PAGES", "MAX_REQUESTS", "MAX_RECHECKS"):
            environment.setenv("CRON_KIFU_INGEST_" + key, "1800")
        environment.setenv("CRON_KIFU_INGEST_MAX_GAMES", "-2")
        importlib.reload(config)
        assert config.KIFU_INGEST_SOURCE_SECONDS == 600
        assert config.KIFU_INGEST_RECOVERY_SECONDS == 300
        assert config.KIFU_INGEST_WINDOW_DAYS == 14
        assert config.KIFU_INGEST_HEAD_PAGES == 10
        assert config.KIFU_INGEST_MAX_REQUESTS == 240
        assert config.KIFU_INGEST_MAX_RECHECKS == 20
        assert config.KIFU_INGEST_MAX_GAMES == 0
    importlib.reload(config)


def test_cron_holds_shared_staging_lock_for_entire_worker(hourly, monkeypatch):
    from katrain.kifu_ingest.staging import staging_writer_lock

    h = hourly

    @contextmanager
    def pg_lock(database):
        yield True

    monkeypatch.setattr(job, "_session_lock", pg_lock)
    entered = []

    async def worker(self):
        with pytest.raises(BlockingIOError):
            with staging_writer_lock(h.root):
                pytest.fail("worker ran without exclusive stage lock")
        Stage(h.root)._atomic(h.root / "checkpoint.json", b"{}")
        entered.append(True)

    monkeypatch.setattr(job.KifuIngestJob, "_run_locked", worker)
    job.KifuIngestJob()._run_lock()
    assert entered == [True]
    with staging_writer_lock(h.root):
        job.KifuIngestJob()._run_lock()
    assert entered == [True]
    with staging_writer_lock(h.root):
        pass


@pytest.mark.asyncio
async def test_published_observation_does_not_create_discovered_journal(hourly, caplog):
    h = hourly
    h.published.add("50")
    h.pages = [source_metadata("50")]
    with caplog.at_level("INFO", logger=job.logger.name):
        await job.KifuIngestJob()._run_locked()
    with h.database.connect() as connection:
        assert connection.scalar(select(items.c.id).where(items.c.external_id == "50")) is None
    assert Stage(h.root).manifest["items"]["50"]["recent"]["raw_sha256"]
    assert "actionable_window_pending=0" in caplog.text
    assert not [e for e in h.events if e[0] in {"prepare", "publish", "sync"}]


@pytest.mark.asyncio
async def test_terminal_source_error_is_quarantined_but_prod_success_is_preserved(hourly):
    from katrain.kifu_ingest.source_19x19 import SourceError

    h = hourly
    freeze(h, "60", phase="prod_synced")
    h.pages = [source_metadata("60"), source_metadata("61"), source_metadata("62")]
    for source_id in ("60", "61"):
        h.sgf_errors[source_id] = SourceError("source business error: 7004", retryable=False, code=7004)
    with pytest.raises(RuntimeError, match="source request"):
        await job.KifuIngestJob()._run_locked()
    assert batch(h, "frozen-60")["status"] == "prod_synced"
    assert job._item_row(h.store, "19x19", "60")["status"] == "prod_synced"
    rejected = job._item_row(h.store, "19x19", "61")
    assert rejected["status"] == "quarantined" and "7004" in rejected["error"]
    assert batch(h, "new-62")["status"] == "prod_synced"
    assert not [e for e in h.events if e[:2] == ("verify", "frozen-60")]


def test_candidate_catalog_lookup_keeps_hidden_and_provenance_rows_bounded(tmp_path):
    from sqlalchemy import event
    from katrain.kifu_ingest.exclusions import known_source_ids
    from katrain.web.core.models_db import KifuAlbum, KifuAlbumSource, KifuSource

    database = create_engine("sqlite://")
    for table in (KifuSource.__table__, KifuAlbum.__table__, KifuAlbumSource.__table__):
        table.create(database)
    with database.begin() as connection:
        connection.execute(KifuSource.__table__.insert().values(id=1, source_key="19x19"))
        for album_id, path in (
            (1, "data/kifu-album/19x19/1.sgf"),
            (2, "other/2.sgf"),
            (3, "data/kifu-album/19x19/9999.sgf"),
        ):
            connection.execute(
                KifuAlbum.__table__.insert().values(
                    id=album_id,
                    player_black="Black",
                    player_white="White",
                    sgf_content=SGF,
                    source_path=path,
                    list_hidden_reason="review",
                )
            )
        connection.execute(
            KifuAlbumSource.__table__.insert().values(
                album_id=2,
                source_id=1,
                origin_path="data/kifu-album/19x19/2.sgf",
                match_method="exact",
            )
        )
    queries = []

    @event.listens_for(database, "before_cursor_execute")
    def capture(conn, cursor, statement, parameters, context, executemany):
        queries.append((statement, parameters))

    try:
        assert known_source_ids(database, candidate_ids={"1", "2", "3"}) == {"1", "2"}
        assert len(queries) == 2 and all(" IN (" in statement for statement, _ in queries)
        assert all("9999" not in str(parameters) for _, parameters in queries)
        queries.clear()
        assert known_source_ids(database, candidate_ids=set()) == set()
        assert not queries
    finally:
        database.dispose()
