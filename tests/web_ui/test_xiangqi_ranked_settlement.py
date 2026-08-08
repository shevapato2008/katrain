from __future__ import annotations

import hashlib

import pytest
from httpx import ASGITransport, AsyncClient

from smartbox_xiangqi_ranked.canonical import hash_event

from katrain.web.core import models_db
from tests.web_ui.test_xiangqi_ranked_api import GAME_ID, api_app, auth, get_preview, reservation_body


MATE_MOVES = "h2e2 b9c7 h0g2 g6g5 i0h0 a9a8 c3c4 a8f8 b2c2 f8f3 c4c5 f3f7 c5c6 c7e8 e2e6 f7e7 c2c9".split()
MATE_FEN = "2Cakabnr/4n4/1c2r2c1/p1P1C3p/6p2/9/P3P1P1P/6N2/9/RNBAKABR1 b - - 0 9"
START_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


def position_hash(fen: str) -> str:
    identity = " ".join(fen.split()[:2])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def terminal_payload(app, reserved, *, kind="settle", terminal_kind="rules", result="win", **updates):
    frozen = reserved["frozen_preview"]
    moves = MATE_MOVES if terminal_kind == "rules" else []
    final_fen = MATE_FEN if terminal_kind == "rules" else START_FEN
    payload = {
        "payload_schema": "xiangqi-ranked-event-v2",
        "event_kind": kind,
        "user_uuid": app.state._ranked_owner["uuid"],
        "device_id": "box-01",
        "game_id": GAME_ID,
        "local_seq": 1,
        "opponent_profile_hash": frozen["opponent_profile_hash"],
        "projection_fingerprint": frozen["projection_fingerprint"],
        "reservation_id": reserved["reservation_id"],
        "scoring_contract_version": frozen["scoring_contract_version"],
        "catalog_version": frozen["catalog_version"],
        "time_control": frozen["time_control"],
        "clock_revision": len(moves),
        "final_fen": final_fen,
        "final_position_hash": position_hash(final_fen),
        "moves": moves,
        "pgn_sha256": "0" * 64,
        "player_clock_ms": 420_000,
        "player_color": frozen["player_color"],
        "result": result,
        "terminal_kind": terminal_kind,
    }
    payload.update(updates)
    return payload


async def reserve(client, app):
    ready = (await get_preview(client, app)).json()
    response = await client.post(
        "/api/v1/xiangqi-ranked/reservations",
        headers=auth(app.state._ranked_owner),
        json=reservation_body(ready),
    )
    assert response.status_code == 201
    return ready, response.json()


@pytest.mark.asyncio
async def test_rules_settlement_replays_moves_uses_frozen_score_and_is_hash_idempotent(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        ready, reserved = await reserve(client, api_app)
        payload = terminal_payload(api_app, reserved)
        request = {
            "event_payload": payload,
            "payload_hash": hash_event(payload),
            "terminal_capability": reserved["terminal_capability"],
        }
        first = await client.post("/api/v1/xiangqi-ranked/settlements", json=request)
        replay = await client.post("/api/v1/xiangqi-ranked/settlements", json=request)
        conflict = await client.post(
            "/api/v1/xiangqi-ranked/settlements",
            json={**request, "payload_hash": "f" * 64},
        )

    assert first.status_code == replay.status_code == 200
    assert first.json()["receipt"] == replay.json()["receipt"]
    assert first.json()["receipt"]["rating_after_hex"] == ready["preview"]["outcomes"]["win"]["rating_hex"]
    assert conflict.status_code == 409 and conflict.json()["code"] == "payload_conflict"
    with api_app.state._ranked_sessions() as session:
        assert session.query(models_db.XiangqiRankedLedger).count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("terminal_kind", "clock_ms"), [("resign", 420_000), ("timeout", 0)])
async def test_resign_leave_and_timeout_are_frozen_player_losses(api_app, terminal_kind, clock_ms):
    kind = "resign" if terminal_kind == "resign" else "settle"
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        ready, reserved = await reserve(client, api_app)
        payload = terminal_payload(
            api_app,
            reserved,
            kind=kind,
            terminal_kind=terminal_kind,
            result="loss",
            player_clock_ms=clock_ms,
        )
        response = await client.post(
            "/api/v1/xiangqi-ranked/settlements",
            json={
                "event_payload": payload,
                "payload_hash": hash_event(payload),
                "terminal_capability": reserved["terminal_capability"],
            },
        )
    assert response.status_code == 200
    assert response.json()["receipt"]["status"] == ("resigned" if kind == "resign" else "settled")
    assert response.json()["receipt"]["rating_after_hex"] == ready["preview"]["outcomes"]["loss"]["rating_hex"]


@pytest.mark.asyncio
async def test_rules_result_maps_terminal_side_to_black_player_loss(api_app):
    api_app.state.xiangqi_ranked_service.color_chooser = lambda _colors: "black"
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        ready, reserved = await reserve(client, api_app)
        payload = terminal_payload(api_app, reserved, result="loss")
        response = await client.post(
            "/api/v1/xiangqi-ranked/settlements",
            json={
                "event_payload": payload,
                "payload_hash": hash_event(payload),
                "terminal_capability": reserved["terminal_capability"],
            },
        )
    assert response.status_code == 200
    assert response.json()["receipt"]["rating_after_hex"] == ready["preview"]["outcomes"]["loss"]["rating_hex"]


@pytest.mark.asyncio
async def test_server_validated_engine_abort_is_uncounted(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        _, reserved = await reserve(client, api_app)
        frozen = reserved["frozen_preview"]
        payload = {
            "payload_schema": "xiangqi-ranked-event-v2",
            "event_kind": "system_abort",
            "user_uuid": api_app.state._ranked_owner["uuid"],
            "device_id": "box-01",
            "game_id": GAME_ID,
            "local_seq": 1,
            "opponent_profile_hash": frozen["opponent_profile_hash"],
            "projection_fingerprint": frozen["projection_fingerprint"],
            "reservation_id": reserved["reservation_id"],
            "scoring_contract_version": frozen["scoring_contract_version"],
            "catalog_version": frozen["catalog_version"],
            "time_control": frozen["time_control"],
            "fault_evidence": {
                "fault_kind": "engine_unavailable",
                "retry_count": 3,
                "last_complete_revision": 7,
                "engine_exit_summary": "exit_code=1 after frozen-position retries",
                "health_summary": "three failed engine health probes",
            },
        }
        response = await client.post(
            "/api/v1/xiangqi-ranked/settlements",
            json={
                "event_payload": payload,
                "payload_hash": hash_event(payload),
                "terminal_capability": reserved["terminal_capability"],
            },
        )
    assert response.status_code == 200
    receipt = response.json()["receipt"]
    assert receipt["status"] == "system_aborted" and receipt["counted"] is False
    assert receipt["rating_after_hex"] is None
