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
