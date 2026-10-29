"""The list-only spawn pool owns its PostgreSQL connections and complete JSON."""

import asyncio
import importlib
import json
import logging
import os
from time import monotonic

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import text, update
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from katrain.web.api.v1.endpoints import kifu
from katrain.web.kifu import prepared_models as prepared
from tests.web_ui.test_kifu_prepare_search import prepare_pg_engine  # noqa: F401
from tests.web_ui.test_kifu_prepared_read import _prepare, reader_pg_engine  # noqa: F401


@pytest.mark.asyncio
async def test_spawn_readers_own_connections_preserve_json_and_fail_closed(reader_pg_engine, monkeypatch):
    module = importlib.import_module("katrain.web.core.kifu_read_executor")
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine = reader_pg_engine
    _prepare(engine)
    with engine.connect() as db:
        schema = db.scalar(text("SELECT current_schema()"))
        assert not db.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user"))
    application_name = "kifu_reader_" + schema
    url = engine.url.update_query_dict(
        {"options": f"-csearch_path={schema},public", "application_name": application_name}
    )
    executor = module.KifuReadExecutor(url.render_as_string(hide_password=False))
    await executor.start()
    app = FastAPI()
    app.state.kifu_read_executor = executor
    app.include_router(kifu.router, prefix="/kifu")
    try:
        assert len(executor.worker_pids) == 4
        assert os.getpid() not in executor.worker_pids
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for params in ({}, {"q": "吴清源"}, {"player_id": 17, "lang": "jp"}, {"page": 2}):
                with Session(engine) as db:
                    expected = JSONResponse(
                        kifu.read_album_page(db, **params).model_dump(mode="json", by_alias=True)
                    ).body
                result = await client.get("/kifu/albums", params=params)
                assert result.status_code == 200
                assert result.content == expected
                assert "kifu_serialization;dur=" in result.headers["server-timing"]
            result = await executor.read({"page": 1})
            assert result["reader_pool"]["worker_pid"] in executor.worker_pids
            assert result["reader_pool"]["after_read"] == {"size": 1, "checkedout": 0, "overflow": 0}
            assert isinstance(result["body"], bytes) and json.loads(result["body"])["total"] == 1
            with engine.begin() as db:
                db.execute(update(prepared.state).values(ready=False))
            for _ in range(2):
                response = await client.get("/kifu/albums")
                assert response.status_code == 503
                assert response.json()["detail"]["code"] == "kifu_search_not_ready"
        # Keep real child jobs blocked in PostgreSQL while their HTTP waiters
        # are cancelled. Admission belongs to the underlying process jobs.
        lock = engine.connect()
        transaction = lock.begin()
        tasks, closing = [], None
        try:
            lock.exec_driver_sql("LOCK TABLE kifu_search_prepared_state IN ACCESS EXCLUSIVE MODE")
            tasks = [asyncio.create_task(executor.read({})) for _ in range(32)]
            deadline = monotonic() + 5
            while True:
                await asyncio.sleep(0.02)
                with engine.connect() as db:
                    blocked = db.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE application_name=:name AND wait_event_type='Lock'"
                        ),
                        {"name": application_name},
                    )
                if blocked == 4:
                    break
                assert monotonic() < deadline, "four child readers did not reach the test lock"
            tasks[0].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[0]
            with pytest.raises(HTTPException) as busy:
                await asyncio.wait_for(executor.read({}), timeout=0.25)
            assert busy.value.status_code == 503 and busy.value.detail["code"] == "kifu_reader_busy"
            closing = asyncio.create_task(executor.close())
            await asyncio.sleep(0.02)
            assert not closing.done(), "shutdown must wait for underlying read-only jobs"
        finally:
            transaction.rollback()
            lock.close()
            await asyncio.gather(*tasks, return_exceptions=True)
            if closing is not None:
                await closing
        assert executor._slots._value == 32
    finally:
        await executor.close()
    with pytest.raises(HTTPException) as closed:
        await executor.read({})
    assert closed.value.status_code == 503
    with engine.connect() as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:name"), {"name": application_name}
            )
            == 0
        )


@pytest.mark.asyncio
async def test_broken_process_pool_returns_503_without_thread_fallback():
    from katrain.web.core.kifu_read_executor import KifuReadExecutor
    from tests.web_ui.test_kifu_prepared_invalidation_pg import isolated_test_url

    executor = KifuReadExecutor(isolated_test_url())
    await executor.start()
    try:
        # These are test-owned children; initialization opens no DB connection.
        next(iter(executor._pool._processes.values())).terminate()
        with pytest.raises(HTTPException) as unavailable:
            await executor.read({})
        assert unavailable.value.status_code == 503
        assert unavailable.value.detail["code"] == "kifu_reader_unavailable"
    finally:
        await executor.close()


@pytest.mark.asyncio
async def test_injected_factory_ignores_server_process_executor(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from tests.web_ui.test_kifu_library_worker import _app

    class NeverRead:
        async def read(self, params):
            pytest.fail("an injected Session factory must stay on its original worker")

    engine = create_engine(f"sqlite:///{tmp_path / 'injected.db'}")
    app = _app(sessionmaker(bind=engine))
    app.state.kifu_read_executor = NeverRead()
    monkeypatch.setattr(
        kifu,
        "read_album_page",
        lambda db, **params: kifu.KifuAlbumListResponse(items=[], total=0, page=1, page_size=20),
    )
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/kifu/albums")).status_code == 200
    finally:
        engine.dispose()


def test_gc_observer_logs_only_slow_collections_for_each_generation(caplog, monkeypatch):
    from katrain.web.core import kifu_read_executor as module

    caplog.set_level(logging.INFO, logger="katrain_web.kifu_gc_pause")
    clock = [10.0]
    monkeypatch.setattr(module, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(module, "time", lambda: 1000 + clock[0])
    monkeypatch.setattr(module, "get_ident", lambda: 123)
    observe = module._gc_pause_observer()
    for generation in range(3):
        for duration in (0.019, 0.025):
            info = {"generation": generation, "collected": 7, "uncollectable": 2}
            started = clock[0]
            observe("start", info)
            clock[0] += duration
            observe("stop", info)
            if duration < 0.02:
                assert len(caplog.records) == generation
            else:
                assert json.loads(caplog.records[-1].getMessage()) == {
                    "event": "kifu_gc_pause",
                    "pid": os.getpid(),
                    "thread_ident": 123,
                    "generation": generation,
                    "start_unix_s": 1000 + started,
                    "duration_ms": pytest.approx(25),
                    "collected": 7,
                    "uncollectable": 2,
                }
    assert len(caplog.records) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_gc_observer_lives_only_in_parent_executor_lifecycle(monkeypatch, failure):
    import gc
    from concurrent.futures import Future
    from katrain.web.core import kifu_read_executor as module

    original = tuple(gc.callbacks)

    class Pool:
        count = 0

        def __init__(self, **kwargs):
            pass

        def submit(self, operation):
            if failure:
                raise RuntimeError("test startup failure")
            self.count += 1
            future = Future()
            future.set_result(self.count)
            return future

        def shutdown(self, *, wait):
            assert wait
            assert gc.callbacks.count(executor._gc_observer) == 1

    monkeypatch.setattr(module, "ProcessPoolExecutor", Pool)
    executor = module.KifuReadExecutor("postgresql://unused")
    assert tuple(gc.callbacks) == original
    if failure:
        with pytest.raises(RuntimeError, match="Kifu reader startup failed"):
            await executor.start()
    else:
        try:
            await executor.start()
            await executor.start()
            assert gc.callbacks.count(executor._gc_observer) == 1
        finally:
            await executor.close()
    assert tuple(gc.callbacks) == original
