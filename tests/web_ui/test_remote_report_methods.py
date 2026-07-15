"""RemoteAPIClient Report and delete methods use the server API contract."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from katrain.web.core.remote_client import RemoteAPIClient


def _client_with_capture():
    client = RemoteAPIClient(base_url="http://up", device_id="test-dev")
    calls = []

    async def fake_request(method, path, *, json=None, params=None, auth=True):
        calls.append({"method": method, "path": path, "json": json, "params": params, "auth": auth})
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value={"ok": True})
        return response

    client._request = AsyncMock(side_effect=fake_request)
    return client, calls


@pytest.mark.asyncio
async def test_report_and_delete_methods_forward_paths_payloads_and_auth():
    client, calls = _client_with_capture()
    payload = {"user_game_id": "g1", "report_type": "deep", "force": True}

    assert await client.list_reports() == {"ok": True}
    assert await client.get_report_summary() == {"ok": True}
    assert await client.get_report(7) == {"ok": True}
    assert await client.create_report(payload) == {"ok": True}
    assert await client.retry_report(7) == {"ok": True}
    assert await client.get_report_moves(7) == {"ok": True}
    assert await client.delete_user_game("g1") == {"ok": True}

    assert calls == [
        {"method": "GET", "path": "/api/v1/reports/", "json": None, "params": None, "auth": True},
        {"method": "GET", "path": "/api/v1/reports/summary", "json": None, "params": None, "auth": True},
        {"method": "GET", "path": "/api/v1/reports/7", "json": None, "params": None, "auth": True},
        {"method": "POST", "path": "/api/v1/reports/", "json": payload, "params": None, "auth": True},
        {"method": "POST", "path": "/api/v1/reports/7/retry", "json": None, "params": None, "auth": True},
        {"method": "GET", "path": "/api/v1/reports/7/moves", "json": None, "params": None, "auth": True},
        {"method": "DELETE", "path": "/api/v1/user-games/g1", "json": None, "params": None, "auth": True},
    ]

    await client.close()
