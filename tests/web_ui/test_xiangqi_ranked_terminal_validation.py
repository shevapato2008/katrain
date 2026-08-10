from __future__ import annotations

from copy import deepcopy

import pytest
from httpx import ASGITransport, AsyncClient

from smartbox_xiangqi_ranked.canonical import hash_event

from katrain.web.core import models_db
from tests.web_ui.test_xiangqi_ranked_api import api_app
from tests.web_ui.test_xiangqi_ranked_settlement import MATE_MOVES, reserve, terminal_payload


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", ["result", "missing_move", "illegal_move", "clock_revision", "engine_fault"])
async def test_terminal_replay_rejects_forged_or_discontinuous_evidence(api_app, tamper):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        _, reserved = await reserve(client, api_app)
        if tamper == "engine_fault":
            frozen = reserved["frozen_preview"]
            payload = {
                "payload_schema": "xiangqi-ranked-event-v2",
                "event_kind": "system_abort",
                "user_uuid": api_app.state._ranked_owner["uuid"],
                "device_id": "box-01",
                "game_id": reserved["game_id"],
                "local_seq": 1,
                "opponent_profile_hash": frozen["opponent_profile_hash"],
                "projection_fingerprint": frozen["projection_fingerprint"],
                "reservation_id": reserved["reservation_id"],
                "scoring_contract_version": frozen["scoring_contract_version"],
                "catalog_version": frozen["catalog_version"],
                "time_control": frozen["time_control"],
                "fault_evidence": {
                    "fault_kind": "engine_unavailable",
                    "retry_count": 0,
                    "last_complete_revision": 0,
                    "engine_exit_summary": "ordinary process restart",
                    "health_summary": "client says the engine failed",
                },
            }
        else:
            payload = terminal_payload(api_app, reserved)
            if tamper == "result":
                payload["result"] = "loss"
            elif tamper == "missing_move":
                payload["moves"] = MATE_MOVES[:-1]
                payload["clock_revision"] -= 1
            elif tamper == "illegal_move":
                payload["moves"] = ["b0b1", *MATE_MOVES[1:]]
            elif tamper == "clock_revision":
                payload["clock_revision"] += 1
        request = {
            "event_payload": deepcopy(payload),
            "payload_hash": hash_event(payload),
            "terminal_capability": reserved["terminal_capability"],
        }
        response = await client.post("/api/v1/xiangqi-ranked/settlements", json=request)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_terminal_evidence"
    with api_app.state._ranked_sessions() as session:
        profile = session.get(models_db.XiangqiRatingProfile, api_app.state._ranked_owner["uuid"])
        assert (profile.rating, profile.rated_games, profile.profile_version) == (1000.0, 0, 0)
        assert session.query(models_db.XiangqiRankedLedger).count() == 0


@pytest.mark.asyncio
async def test_terminal_rejects_capability_binding_and_frozen_snapshot_mismatches(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        _, reserved = await reserve(client, api_app)
        payload = terminal_payload(api_app, reserved, projection_fingerprint="f" * 64)
        response = await client.post(
            "/api/v1/xiangqi-ranked/settlements",
            json={
                "event_payload": payload,
                "payload_hash": hash_event(payload),
                "terminal_capability": reserved["terminal_capability"],
            },
        )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_snapshot"
