"""Opt-in real PostgreSQL checks, isolated from application databases."""

import multiprocessing
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from katrain.web.core.models_db import Base, KifuAlbum, KifuPlayer, KifuPlayerAlias, KifuRawEventValue
from katrain.web.kifu import name_batch
from katrain.web.kifu.name_parse import parse_event
from tests.web_ui.test_kifu_incremental_catalog import (
    _seed_names,
    assert_qualified,
    manifest,
    publish,
    publisher,
    state,
)


@pytest.fixture
def pg_engine():
    dsn = os.getenv("KIFU_INGEST_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("set KIFU_INGEST_TEST_DATABASE_URL to an isolated local PostgreSQL database")
    url = make_url(dsn)
    assert url.host in {"127.0.0.1", "localhost"} and url.database.startswith("kifu_ingest_validation")
    admin = create_engine(dsn)
    schema = "ingest_" + uuid4().hex
    with admin.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(dsn, connect_args={"options": f"-c search_path={schema},public"})
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            for owner_id, name in ((17, "Black"), (18, "White")):
                conn.execute(KifuPlayer.__table__.insert().values(id=owner_id, canonical_name=name))
                conn.execute(
                    KifuPlayerAlias.__table__.insert().values(
                        player_id=owner_id, alias=name + " Alias", normalized_alias=(name + " Alias").lower()
                    )
                )
            conn.execute(
                KifuRawEventValue.__table__.insert().values(
                    id=7,
                    raw_value="Summer Cup",
                    category=parse_event("Summer Cup", None).category,
                    review_status="pending",
                )
            )
            conn.execute(
                KifuAlbum.__table__.insert().values(
                    id=11,
                    black_player_id=17,
                    white_player_id=18,
                    player_black="Black",
                    player_white="White",
                    event="Summer Cup",
                    date_played="2026-01-30",
                    source_path="legacy-11.sgf",
                    sgf_content="(;PB[Black]PW[White]EV[Summer Cup];B[aa])",
                )
            )
        _seed_names(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def test_pg_publication_survives_connection_loss_and_replay(pg_engine):
    value = manifest()
    original = state(pg_engine)
    receipt = publish(pg_engine, value)
    album_id = receipt["games"][0]["album_id"]
    assert_qualified(pg_engine, [11, album_id])
    after = state(pg_engine)
    pg_engine.dispose()
    assert publish(pg_engine, value) == receipt
    assert state(pg_engine) == after
    with pg_engine.connect() as conn:
        old = conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == 11)).first()
    assert tuple(old) == original[KifuAlbum.__table__][0]


def test_pg_failure_rolls_back_rows_names_and_receipt(pg_engine, monkeypatch):
    api = publisher()
    before = state(pg_engine)
    actual = api.strict_slot_approvals

    def reject_new(db, albums, lang, **kwargs):
        approvals = actual(db, albums, lang, **kwargs)
        return {key: slots if key == 11 else (None, *slots[1:]) for key, slots in approvals.items()}

    monkeypatch.setattr(api, "strict_slot_approvals", reject_new)
    with pytest.raises(api.PublicationError, match="coverage"):
        publish(pg_engine, manifest())
    assert state(pg_engine) == before


def test_pg_conditional_compensation_restores_old_qualification(pg_engine):
    receipt = publish(pg_engine, manifest())
    result = publisher().undo_publication(pg_engine, receipt["batch_id"])
    assert result["status"] == "undone"
    assert publisher().undo_publication(pg_engine, receipt["batch_id"]) == result
    with pg_engine.connect() as conn:
        assert list(conn.scalars(select(KifuAlbum.id))) == [11]
    assert_qualified(pg_engine, [11])


def _hold_lock(dsn, ready, release):
    engine = create_engine(dsn)
    with engine.begin() as conn:
        conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (name_batch._ADVISORY_LOCK_KEY,))
        ready.set()
        release.wait(20)
    engine.dispose()


def test_pg_second_process_cannot_publish_through_lock(pg_engine):
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    holder = context.Process(
        target=_hold_lock, args=(pg_engine.url.render_as_string(hide_password=False), ready, release)
    )
    holder.start()
    before = state(pg_engine)
    try:
        assert ready.wait(10), "lock holder failed to start"
        with pytest.raises(DBAPIError, match="lock timeout"):
            with name_batch._locked_write(pg_engine, lock_timeout_ms=100):
                pytest.fail("concurrent publisher acquired an already-held advisory lock")
        assert state(pg_engine) == before
    finally:
        release.set()
        holder.join(10)
        if holder.is_alive():
            holder.terminate()
            holder.join()
    assert holder.exitcode == 0
    publish(pg_engine, manifest())


def test_pg_journal_migration_is_repeatable(pg_engine):
    migration = Path(__file__).resolve().parents[2] / "katrain/cron/migrations/003_kifu_incremental.sql"
    with pg_engine.begin() as conn:
        conn.exec_driver_sql(migration.read_text())
        conn.exec_driver_sql(migration.read_text())
        assert conn.exec_driver_sql("SELECT count(*) FROM kifu_ingest_batches").scalar_one() == 0
        assert conn.exec_driver_sql("SELECT count(*) FROM kifu_ingest_items").scalar_one() == 0
