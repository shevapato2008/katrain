import asyncio
import json

import httpx
import pytest

from katrain.kifu_ingest.source_19x19 import Source19x19, SourceError, SourceRateLimited


def run(coro):
    return asyncio.run(coro)


def response(code="0", data=None, status=200, headers=None):
    return httpx.Response(status, json={"code": code, "data": data}, headers=headers)


def test_list_request_and_original_metadata():
    seen = []
    meta = {"id": 12, "gamename": "原名", "playTime": {"date": {"year": 2026}}}

    def handle(req):
        seen.append(req)
        return response(data={"gameMetaList": [meta]})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(client, sleep=lambda _: asyncio.sleep(0), list_interval=(0, 0), sgf_interval=(0, 0))
            assert await source.fetch_page(3) == [meta]

    run(check())
    assert dict(seen[0].url.params) == {"page": "3", "size": "20", "game_type": "2", "username": "0086-golaxy_public"}
    assert seen[0].headers["referer"] == "https://www.19x19.com/"


def test_sgf_post_and_utf8_content():
    seen = []

    def handle(req):
        seen.append(req)
        return response(data={"sgf": "(;GM[1]C[中文])"})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(client, sleep=lambda _: asyncio.sleep(0), list_interval=(0, 0), sgf_interval=(0, 0))
            assert await source.fetch_sgf("12") == "(;GM[1]C[中文])"

    run(check())
    assert seen[0].method == "POST"
    assert json.loads(seen[0].content) == {"id": 12}


@pytest.mark.parametrize(
    "payload", [response(code="1", data={"gameMetaList": []}), response(data={}), response(data={"gameMetaList": None})]
)
def test_bad_business_or_shape_is_error_not_empty(payload):
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: payload)) as client:
            source = Source19x19(client, sleep=lambda _: asyncio.sleep(0), list_interval=(0, 0), sgf_interval=(0, 0))
            with pytest.raises(SourceError):
                await source.fetch_page(0)

    run(check())


def test_404_does_not_retry():
    calls = []

    def handle(req):
        calls.append(req)
        return response(status=404)

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(client, sleep=lambda _: asyncio.sleep(0), list_interval=(0, 0), sgf_interval=(0, 0))
            with pytest.raises(SourceError) as exc:
                await source.fetch_sgf("12")
            assert exc.value.retryable is False

    run(check())
    assert len(calls) == 1


def test_transient_error_retries_at_most_three_times():
    calls = []

    def handle(req):
        calls.append(req)
        return response(status=503)

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(client, sleep=lambda _: asyncio.sleep(0), list_interval=(0, 0), sgf_interval=(0, 0))
            with pytest.raises(SourceError):
                await source.fetch_page(0)

    run(check())
    assert len(calls) == 4


def test_transient_protocol_error_is_bounded_and_wrapped():
    calls = []

    def handle(req):
        calls.append(req)
        raise httpx.RemoteProtocolError("server disconnected")

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(client, sleep=lambda _: asyncio.sleep(0), list_interval=(0, 0), sgf_interval=(0, 0))
            with pytest.raises(SourceError):
                await source.fetch_page(0)

    run(check())
    assert len(calls) == 4


def test_429_retry_after_respects_deadline():
    calls = []
    now = [0.0]

    async def sleep(seconds):
        now[0] += seconds

    def handle(req):
        calls.append(req)
        return response(status=429, headers={"Retry-After": "100"})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(
                client, sleep=sleep, clock=lambda: now[0], deadline=30, list_interval=(0, 0), sgf_interval=(0, 0)
            )
            with pytest.raises(SourceRateLimited) as exc:
                await source.fetch_page(0)
            assert exc.value.retry_after == 100

    run(check())
    assert len(calls) == 1
    assert now[0] == 0


def test_429_longer_than_wait_cap_is_deferred_without_early_retry():
    calls = []
    slept = []

    async def sleep(seconds):
        slept.append(seconds)

    def handle(req):
        calls.append(req)
        return response(status=429, headers={"Retry-After": "120"})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(client, sleep=sleep, list_interval=(0, 0), sgf_interval=(0, 0), retry_after_cap=60)
            with pytest.raises(SourceRateLimited) as exc:
                await source.fetch_page(0)
            assert exc.value.retry_after == 120

    run(check())
    assert len(calls) == 1
    assert slept == []


@pytest.mark.parametrize("path,terminal", [("sgf", True), ("list", False)])
def test_only_shared_7004_is_terminal_and_retains_bounded_evidence(path, terminal):
    async def check():
        payload = httpx.Response(200, json={"code": 7004, "msg": "gone" * 300})
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: payload)) as client:
            source = Source19x19(client, list_interval=(0, 0), sgf_interval=(0, 0))
            with pytest.raises(SourceError) as exc:
                await (source.fetch_sgf("12") if path == "sgf" else source.fetch_page(0))
            assert exc.value.retryable is not terminal
            assert exc.value.code == 7004
            assert exc.value.source_message == ("gone" * 300)[:512]

    run(check())


def test_short_429_also_defers_without_internal_retry():
    calls = []

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: calls.append(req) or response(status=429, headers={"Retry-After": "1"})
            )
        ) as client:
            source = Source19x19(client, list_interval=(0, 0), sgf_interval=(0, 0))
            with pytest.raises(SourceRateLimited):
                await source.fetch_sgf("12")

    run(check())
    assert len(calls) == 1


def test_absolute_deadline_cancels_transport_and_clamps_httpx_timeout():
    import time

    seen = []

    async def handle(req):
        seen.append(req.extensions["timeout"])
        await asyncio.sleep(1)
        return response(data={"gameMetaList": []})

    async def check():
        from katrain.kifu_ingest.source_19x19 import SourceBudgetExceeded

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(client, deadline=time.monotonic() + 0.03, list_interval=(0, 0))
            with pytest.raises(SourceBudgetExceeded):
                await source.fetch_page(0)

    run(check())
    assert 0 < seen[0]["read"] <= 0.03


def test_global_spacing_applies_between_list_and_sgf():
    now = [0.0]
    requests_at = []

    async def sleep(seconds):
        now[0] += seconds

    def handle(req):
        requests_at.append(now[0])
        return response(data={"gameMetaList": []} if req.method == "GET" else {"sgf": "(;GM[1])"})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            source = Source19x19(client, sleep=sleep, clock=lambda: now[0], list_interval=(5, 5), sgf_interval=(2, 2))
            await source.fetch_page(0)
            await source.fetch_sgf("12")
            await source.fetch_page(1)

    run(check())
    assert requests_at == [0, 2, 7]


def test_list_response_cannot_exceed_requested_twenty_rows():
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: response(data={"gameMetaList": [{"id": i} for i in range(21)]}))
        ) as client:
            source = Source19x19(client, list_interval=(0, 0))
            with pytest.raises(SourceError, match="20"):
                await source.fetch_page(0)

    run(check())
