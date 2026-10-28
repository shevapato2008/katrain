"""Kifu HTTP timing includes queue, serialization, and the awaited final body send."""

import asyncio
from contextlib import nullcontext
import json
import logging
import re
from threading import Event
import time

import anyio.to_thread
import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from katrain.web.api.v1.endpoints import kifu


LOGGER = "katrain_web.kifu_http_timing"
REQUEST_ID = "0123456789abcdef0123456789abcdef"


def _metrics(caplog):
    return [json.loads(record.getMessage()) for record in caplog.records if record.name == LOGGER]


def _scope(path="/api/v1/kifu/albums", headers=(), **extra):
    return {
        "type": "http",
        "path": path,
        "headers": list(headers),
        "query_string": b"q=PRIVATE_QUERY",
        **extra,
    }


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


@pytest.mark.asyncio
async def test_logs_once_after_awaited_final_body_with_exact_status_bytes_and_scope_clock(caplog, monkeypatch):
    from katrain.web.core import kifu_http_timing as timing

    caplog.set_level(logging.INFO, logger=LOGGER)
    clock = [10.0]
    monkeypatch.setattr(timing, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(timing, "time", lambda: 1234.5)
    sent = []

    async def send(message):
        assert _metrics(caplog) == [], "logging must wait until final send returns"
        sent.append(message)
        clock[0] += 0.1

    async def app(scope, receive, send):
        clock[0] += 0.2
        await send({"type": "http.response.start", "status": 503, "headers": [(b"server-timing", b"part;dur=2")]})
        await send({"type": "http.response.body", "body": b"PRIVATE_SGF", "more_body": True})
        await send({"type": "http.response.body", "body": b"{}"})
        assert len(_metrics(caplog)) == 1
        clock[0] += 5  # Background work is beyond the final response body.

    await timing.KifuHTTPTimingMiddleware(app)(
        _scope(headers=[(b"x-kifu-request-id", REQUEST_ID.encode()), (b"authorization", b"SECRET_TOKEN")]),
        _receive,
        send,
    )
    (metric,) = _metrics(caplog)
    assert metric == {
        "event": "kifu_http_timing",
        "request_id": REQUEST_ID,
        "ingress_unix_s": 1234.5,
        "asgi_total_ms": pytest.approx(500),
        "status": 503,
        "bytes": len(b"PRIVATE_SGF{}"),
    }
    assert dict(sent[0]["headers"])[b"x-kifu-request-id"] == REQUEST_ID.encode()
    assert dict(sent[0]["headers"])[b"server-timing"] == b"part;dur=2"
    assert not any(secret in caplog.text for secret in ("PRIVATE_QUERY", "PRIVATE_SGF", "SECRET_TOKEN"))


@pytest.mark.asyncio
@pytest.mark.parametrize("incoming", [None, b"short", b"A" * 32, b"a" * 32 + b"\n", b"\xff" * 32])
async def test_missing_or_invalid_request_id_is_replaced_with_lowercase_uuid(caplog, incoming):
    from katrain.web.core.kifu_http_timing import KifuHTTPTimingMiddleware

    caplog.set_level(logging.INFO, logger=LOGGER)
    sent = []

    async def send(message):
        sent.append(message)

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [(b"x-kifu-request-id", b"stale")]})
        await send({"type": "http.response.body", "body": b""})

    headers = [] if incoming is None else [(b"x-kifu-request-id", incoming)]
    await KifuHTTPTimingMiddleware(app)(_scope(headers=headers), _receive, send)
    (metric,) = _metrics(caplog)
    assert re.fullmatch("[0-9a-f]{32}", metric["request_id"])
    assert [value for key, value in sent[0]["headers"] if key == b"x-kifu-request-id"] == [
        metric["request_id"].encode()
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "scope_type", "timed"),
    [
        ("/api/v1/kifu/albums", "http", True),
        ("/api/v1/kifu/albums/", "http", True),
        ("/api/v1/kifu/albums/17", "http", True),
        ("/api/v1/kifu/albums/17/analysis", "http", True),
        ("/health", "http", False),
        ("/api/v1/health", "http", False),
        ("/api/v1/kifu/albums-extra", "http", False),
        ("/api/v1/kifus/albums", "http", False),
        ("/api/v1/kifu/albums/17/unrelated", "http", False),
        ("/api/v1/kifu/albums", "websocket", False),
    ],
)
async def test_only_exact_kifu_http_routes_are_timed(caplog, path, scope_type, timed):
    from katrain.web.core.kifu_http_timing import KifuHTTPTimingMiddleware

    caplog.set_level(logging.INFO, logger=LOGGER)
    seen = []
    scope = _scope(path=path, type=scope_type)

    async def send(message):
        seen.append(message)

    async def app(inner_scope, receive, send):
        assert inner_scope is scope
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    await KifuHTTPTimingMiddleware(app)(scope, _receive, send)
    assert len(_metrics(caplog)) == int(timed)
    assert (b"x-kifu-request-id" in dict(seen[0]["headers"])) is timed


@pytest.mark.asyncio
async def test_total_includes_worker_queue_and_pydantic_json_delay_while_queue_leaves_loop_responsive(
    caplog, monkeypatch
):
    from katrain.web.core.kifu_http_timing import KifuHTTPTimingMiddleware

    caplog.set_level(logging.INFO, logger=LOGGER)

    class SlowJSONResponse(JSONResponse):
        def render(self, content):
            time.sleep(0.04)
            return super().render(content)

    app = FastAPI(default_response_class=SlowJSONResponse)
    app.include_router(kifu.router, prefix="/api/v1/kifu")
    app.add_middleware(KifuHTTPTimingMiddleware)

    async def session_factory():
        return lambda: nullcontext(object())

    app.dependency_overrides[kifu.get_kifu_session_factory] = session_factory
    monkeypatch.setattr(
        kifu,
        "read_album_page",
        lambda db, **params: kifu.KifuAlbumListResponse(items=[], total=0, page=1, page_size=20),
    )
    route = next(route for route in app.routes if isinstance(route, APIRoute) and route.path == "/api/v1/kifu/albums")
    serialize = route.response_field.serialize

    def delayed_serialize(*args, **kwargs):
        time.sleep(0.04)
        return serialize(*args, **kwargs)

    monkeypatch.setattr(route.response_field, "serialize", delayed_serialize)

    @app.get("/ping", response_class=JSONResponse)
    async def ping():
        return {"ok": True}

    limiter = anyio.to_thread.current_default_thread_limiter()
    previous_tokens = limiter.total_tokens
    limiter.total_tokens = 1
    occupied, release = Event(), Event()

    def occupy_worker():
        occupied.set()
        assert release.wait(3), "test did not release occupied worker"

    blocker = asyncio.create_task(run_in_threadpool(occupy_worker))
    listing = None
    try:
        assert await asyncio.to_thread(occupied.wait, 1)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            listing = asyncio.create_task(client.get("/api/v1/kifu/albums", headers={"x-kifu-request-id": REQUEST_ID}))
            await asyncio.sleep(0.04)
            assert not listing.done()
            assert (await asyncio.wait_for(client.get("/ping"), 0.5)).json() == {"ok": True}
            assert _metrics(caplog) == []
            release.set()
            response = await listing
        assert response.status_code == 200
        parts = dict(re.findall(r"(kifu_\w+);dur=([\d.]+)", response.headers["server-timing"]))
        assert float(parts["kifu_queue"]) >= 25
        (metric,) = _metrics(caplog)
        assert metric["asgi_total_ms"] >= float(parts["kifu_handler"]) + 70
        assert metric["bytes"] == len(response.content)
    finally:
        release.set()
        await blocker
        if listing is not None:
            await listing
        limiter.total_tokens = previous_tokens


@pytest.mark.asyncio
async def test_server_installs_timing_around_kifu_validation_response_without_timing_other_routes(caplog):
    from katrain.web.core.db import engine
    from katrain.web.core.kifu_http_timing import KifuHTTPTimingMiddleware
    from katrain.web.server import create_app

    caplog.set_level(logging.INFO, logger=LOGGER)
    app = create_app(enable_engine=False)
    timing = next(middleware for middleware in app.user_middleware if middleware.cls is KifuHTTPTimingMiddleware)
    assert timing.kwargs["pool"] is engine.pool
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.get("/api/v1/kifu/albums?player_id=0", headers={"x-kifu-request-id": REQUEST_ID})
        other = await client.get("/unrelated")
    assert result.status_code == 422
    assert result.headers["x-kifu-request-id"] == REQUEST_ID
    assert "x-kifu-request-id" not in other.headers
    (metric,) = _metrics(caplog)
    assert metric["status"] == 422
    assert metric["bytes"] == len(result.content)


@pytest.mark.asyncio
async def test_injected_pool_is_observed_at_scope_and_after_final_send_but_never_on_other_routes(caplog):
    from katrain.web.core.kifu_http_timing import KifuHTTPTimingMiddleware

    caplog.set_level(logging.INFO, logger=LOGGER)
    calls = []

    class FakePool:
        values = {"size": 20, "checkedout": 1, "overflow": -19}

        def size(self):
            calls.append("size")
            return self.values["size"]

        def checkedout(self):
            calls.append("checkedout")
            return self.values["checkedout"]

        def overflow(self):
            calls.append("overflow")
            return self.values["overflow"]

    pool = FakePool()
    sent = []

    async def send(message):
        sent.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            # Only the observation after this awaited send may see these values.
            pool.values = {"size": 20, "checkedout": 4, "overflow": -16}

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"first", "more_body": True})
        await send({"type": "http.response.body", "body": b"last"})

    middleware = KifuHTTPTimingMiddleware(app, pool=pool)
    await middleware(_scope(), _receive, send)
    (metric,) = _metrics(caplog)
    assert metric["db_pool_at_scope_entry"] == {"size": 20, "checkedout": 1, "overflow": -19}
    assert metric["db_pool_after_final_body"] == {"size": 20, "checkedout": 4, "overflow": -16}
    assert calls == ["size", "checkedout", "overflow"] * 2
    assert metric["bytes"] == len(b"firstlast")
    caplog.clear()
    await middleware(_scope(path="/health"), _receive, send)
    assert calls == ["size", "checkedout", "overflow"] * 2
    assert _metrics(caplog) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown", [False, True])
async def test_unknown_or_failing_pool_observation_does_not_affect_response(caplog, unknown):
    from katrain.web.core.kifu_http_timing import KifuHTTPTimingMiddleware

    caplog.set_level(logging.INFO, logger=LOGGER)

    class BrokenPool:
        def size(self):
            raise RuntimeError("observation failed")

    sent = []

    async def send(message):
        sent.append(message)

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    await KifuHTTPTimingMiddleware(app, pool=object() if unknown else BrokenPool())(_scope(), _receive, send)
    (metric,) = _metrics(caplog)
    assert metric["db_pool_at_scope_entry"] is None
    assert metric["db_pool_after_final_body"] is None
    assert sent[-1]["body"] == b"ok"
    assert metric["status"] == 200 and metric["bytes"] == 2
