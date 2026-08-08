from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from smartbox_xiangqi_ranked.canonical import hash_event

from tests.web_ui.test_xiangqi_ranked_api import GAME_ID, api_app, auth
from tests.web_ui.test_xiangqi_ranked_settlement import reserve, terminal_payload


@pytest.mark.asyncio
async def test_lost_settlement_response_is_recovered_by_owner_or_game_capability_receipt_query(api_app, monkeypatch):
    service = api_app.state.xiangqi_ranked_service
    original_settle = service.settle

    def accept_after_committing(**kwargs):
        confirmed = original_settle(**kwargs)
        return {
            "code": "accepted",
            "receipt_id": confirmed["receipt"]["receipt_id"],
            "game_id": confirmed["receipt"]["game_id"],
            "payload_hash": confirmed["receipt"]["payload_hash"],
        }

    monkeypatch.setattr(service, "settle", accept_after_committing)
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        _, reserved = await reserve(client, api_app)
        payload = terminal_payload(api_app, reserved)
        posted = await client.post(
            "/api/v1/xiangqi-ranked/settlements",
            json={
                "event_payload": payload,
                "payload_hash": hash_event(payload),
                "terminal_capability": reserved["terminal_capability"],
            },
        )
        assert posted.status_code == 202  # Treat the accepted body as lost after the server committed it.
        owner = await client.get(
            f"/api/v1/xiangqi-ranked/settlements/{GAME_ID}",
            headers=auth(api_app.state._ranked_owner),
        )
        capability = await client.get(
            f"/api/v1/xiangqi-ranked/settlements/{GAME_ID}",
            headers={"Authorization": f"Bearer {reserved['terminal_capability']}"},
        )
        foreign = await client.get(
            f"/api/v1/xiangqi-ranked/settlements/{GAME_ID}",
            headers=auth(api_app.state._ranked_other),
        )

    assert owner.status_code == capability.status_code == 200
    assert owner.json() == capability.json()
    assert owner.json()["code"] == "confirmed"
    assert owner.json()["receipt"]["payload_hash"] == hash_event(payload)
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "not_found"
    assert reserved["terminal_capability"] not in owner.text + capability.text + foreign.text


@pytest.mark.asyncio
async def test_receipt_query_reports_missing_and_conflict_with_original_hash(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        _, reserved = await reserve(client, api_app)
        missing = await client.get(
            f"/api/v1/xiangqi-ranked/settlements/{GAME_ID}",
            headers=auth(api_app.state._ranked_owner),
        )
        payload = terminal_payload(api_app, reserved, kind="resign", terminal_kind="resign", result="loss")
        original_hash = hash_event(payload)
        await client.post(
            "/api/v1/xiangqi-ranked/settlements",
            json={
                "event_payload": payload,
                "payload_hash": original_hash,
                "terminal_capability": reserved["terminal_capability"],
            },
        )
        conflict = await client.get(
            f"/api/v1/xiangqi-ranked/settlements/{GAME_ID}",
            headers=auth(api_app.state._ranked_owner),
            params={"payload_hash": "f" * 64},
        )

    assert missing.status_code == 200 and missing.json()["code"] == "missing"
    assert conflict.status_code == 200 and conflict.json()["code"] == "conflict"
    assert conflict.json()["payload_hash"] == original_hash
    assert conflict.json()["receipt"]["status"] == "resigned"


def test_task9_openapi_has_owner_derived_requests_and_separate_cursor_contracts(api_app):
    schema = api_app.openapi()
    paths = schema["paths"]
    receipt = paths["/api/v1/xiangqi-ranked/settlements/{game_id}"]["get"]
    reconcile = paths["/api/v1/xiangqi-ranked/reconcile"]["post"]
    history = paths["/api/v1/xiangqi-ranked/settlements"]["get"]
    reconcile_schema = schema["components"]["schemas"]["ReconcileRequest"]

    assert "user_uuid" not in reconcile_schema.get("properties", {})
    assert "terminal_capability" not in str(receipt.get("responses", {}))
    assert "event_snapshot_token" in reconcile_schema["properties"]
    assert any(parameter["name"] == "summary_cursor" for parameter in history["parameters"])
    assert all(parameter["name"] != "device_cursor" for parameter in history["parameters"])
