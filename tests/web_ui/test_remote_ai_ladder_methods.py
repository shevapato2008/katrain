from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from katrain.web.core.remote_client import RemoteAPIClient


@pytest.mark.asyncio
async def test_authenticated_requests_carry_the_board_device_id():
    seen = {}

    async def handler(request: httpx.Request):
        seen["authorization"] = request.headers.get("Authorization")
        seen["device_id"] = request.headers.get("X-StellaBox-Device-ID")
        return httpx.Response(200, json={"ok": True})

    client = RemoteAPIClient("https://cloud.invalid", "box-17")
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://cloud.invalid", transport=httpx.MockTransport(handler)
    )
    client.set_tokens("secret-token")
    try:
        await client.get_ai_ladder_status()
    finally:
        await client.close()

    assert seen == {"authorization": "Bearer secret-token", "device_id": "box-17"}


@pytest.mark.asyncio
async def test_ranked_lifecycle_methods_use_strict_paths_and_bodies():
    client = RemoteAPIClient("https://cloud.invalid", "box-17")
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"state": "ok"}
    client._request = AsyncMock(return_value=response)

    assert await client.reserve_ai_ladder_game({"game_id": "g", "color": "black"}) == {"state": "ok"}
    assert await client.activate_ai_ladder_game("g", "key", "session") == {"state": "ok"}
    assert await client.mark_ai_ladder_game_pending("g", "key") == {"state": "ok"}
    assert await client.cancel_ai_ladder_reservation("g", "key") == {"state": "ok"}
    assert await client.get_ai_ladder_game_status("g") == {"state": "ok"}
    assert await client.end_ai_ladder_game("g") == {"state": "ok"}

    assert client._request.await_args_list == [
        (("POST", "/api/v1/ai-ladder/games/reserve"), {"json": {"game_id": "g", "color": "black"}}),
        (("POST", "/api/v1/ai-ladder/games/g/activate"), {"json": {"reservation_key": "key", "session_id": "session"}}),
        (("POST", "/api/v1/ai-ladder/games/g/pending-settlement"), {"json": {"reservation_key": "key"}}),
        (("DELETE", "/api/v1/ai-ladder/games/g/reservation"), {"json": {"reservation_key": "key"}}),
        (("GET", "/api/v1/ai-ladder/games/g/status"), {}),
        (("POST", "/api/v1/ai-ladder/games/g/end"), {"json": {"reason": "user_resigned"}}),
    ]
    assert response.raise_for_status.call_count == 6
