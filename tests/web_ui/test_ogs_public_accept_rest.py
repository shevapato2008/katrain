"""OGS public seeks use the same accept request as its current web client."""

import httpx
import pytest

from katrain.web.platforms.ogs.rest_client import OGSRestClient


@pytest.mark.asyncio
async def test_public_seek_accept_uses_public_path_and_session_csrf():
    seen = []

    def handle(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={})

    rest = OGSRestClient()
    rest._client = httpx.AsyncClient(
        base_url="https://online-go.com", transport=httpx.MockTransport(handle)
    )
    rest._client.cookies.set("csrftoken", "csrf-test", domain="online-go.com")
    try:
        await rest.accept_open_challenge(42)
    finally:
        await rest.close()

    assert len(seen) == 1
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/api/v1/challenges/42/accept"
    assert seen[0].headers["X-CSRFToken"] == "csrf-test"
    assert seen[0].headers["Referer"] == "https://online-go.com/"
    assert seen[0].content == b"{}"


@pytest.mark.asyncio
async def test_public_seek_accept_requires_session_csrf_before_post():
    seen = []
    rest = OGSRestClient()
    rest._client = httpx.AsyncClient(
        base_url="https://online-go.com",
        transport=httpx.MockTransport(lambda request: seen.append(request) or httpx.Response(200)),
    )
    try:
        with pytest.raises(RuntimeError, match="CSRF"):
            await rest.accept_open_challenge(42)
    finally:
        await rest.close()

    assert seen == []


@pytest.mark.asyncio
async def test_direct_player_challenge_uses_valid_time_control_and_csrf():
    seen = []

    def handle(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={"challenge": 4, "game": 42})

    rest = OGSRestClient()
    rest._client = httpx.AsyncClient(base_url="https://online-go.com", transport=httpx.MockTransport(handle))
    rest._client.cookies.set("csrftoken", "csrf-test", domain="online-go.com")
    try:
        assert await rest.challenge_player(8, {"board_size": 19, "time_control": {}}) == (4, 42)
    finally:
        await rest.close()

    assert seen[0].url.path == "/api/v1/players/8/challenge/"
    assert seen[0].headers["X-CSRFToken"] == "csrf-test"
    payload = __import__("json").loads(seen[0].content)
    game = payload["game"]
    assert payload["challenger_color"] == "automatic"
    assert game["time_control"] == "byoyomi"
    assert game["time_control_parameters"]["system"] == "byoyomi"
    assert game["time_control_parameters"]["time_control"] == "byoyomi"
    assert game["time_control_parameters"]["speed"] == "live"
    assert "komi" not in game
    assert game["private"] is False
    assert game["rengo"] is False


@pytest.mark.asyncio
async def test_direct_challenge_cancel_uses_owned_rest_route_and_csrf():
    seen = []
    rest = OGSRestClient()
    rest._client = httpx.AsyncClient(
        base_url="https://online-go.com",
        transport=httpx.MockTransport(lambda request: seen.append(request) or httpx.Response(204)),
    )
    rest._client.cookies.set("csrftoken", "csrf-test", domain="online-go.com")
    try:
        await rest.decline_challenge(42)
    finally:
        await rest.close()
    assert seen[0].method == "DELETE"
    assert seen[0].url.path == "/api/v1/me/challenges/42"
    assert seen[0].headers["X-CSRFToken"] == "csrf-test"
