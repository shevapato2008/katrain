"""Hourly orchestration with a real temporary journal/Stage and no network."""

import asyncio
from contextlib import contextmanager
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
    )

    async def forbidden(*args, **kwargs):
        pytest.fail("real HTTP is forbidden in orchestration tests")

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)

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
            return SGF

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
        return {"status": "verified", "games": len(manifest["games"])}

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
        row = h.store.advance_batch(
            manifest["publication_key"], target, expected_status=row["status"], receipt=h.receipt(manifest)
        )
        job.reconcile_items(h.store, manifest, row)
        if target == phase:
            break
    return manifest


def batch(h, key):
    return job._batch_row(h.store, key)


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
@pytest.mark.parametrize("reason", ["source_changed", "unchecked", "different_raw_baseline"])
async def test_unverified_source_version_never_publishes_frozen_test_package(hourly, monkeypatch, reason):
    h = hourly
    manifest = freeze(h, "4", original=reason != "different_raw_baseline")
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
