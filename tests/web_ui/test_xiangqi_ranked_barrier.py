from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from smartbox_xiangqi_ranked.canonical import hash_event

from katrain.web.core import models_db
from katrain.web.core.xiangqi_ranked_service import FORCE_RESIGN_THRESHOLD
from tests.web_ui.test_xiangqi_ranked_api import api_app, auth
from tests.web_ui.test_xiangqi_ranked_settlement import reserve, terminal_payload


@pytest.mark.asyncio
async def test_takeover_requires_owner_confirmation_and_stale_cloud_heartbeat_then_wins_once(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        _, reserved = await reserve(client, api_app)
        path = f"/api/v1/xiangqi-ranked/reservations/{reserved['reservation_id']}/force-resign"
        early = await client.post(path, headers=auth(api_app.state._ranked_owner), json={"confirm": True})
        api_app.state._ranked_clock["now"] += FORCE_RESIGN_THRESHOLD
        takeover = await client.post(path, headers=auth(api_app.state._ranked_owner), json={"confirm": True})
        payload = terminal_payload(api_app, reserved)
        late_settle = await client.post(
            "/api/v1/xiangqi-ranked/settlements",
            json={
                "event_payload": payload,
                "payload_hash": hash_event(payload),
                "terminal_capability": reserved["terminal_capability"],
            },
        )
        health = await client.get("/api/v1/health")

    assert early.status_code == 409
    assert takeover.status_code == 200 and takeover.json()["receipt"]["counted"] is True
    assert takeover.json()["receipt"]["rating_after_hex"] == reserved["frozen_preview"]["outcome_loss_hex"]
    assert late_settle.status_code == 409 and late_settle.json()["code"] == "reservation_terminal_conflict"
    metrics = health.json()["xiangqi_ranked"]
    assert set(metrics) == {
        "active_reservation_count",
        "oldest_reservation_age_seconds",
        "oldest_heartbeat_age_seconds",
        "terminal_conflict_counts",
    }
    assert metrics["terminal_conflict_counts"]["reservation_terminal_conflict"] >= 1
    assert api_app.state._ranked_owner["uuid"] not in health.text
    assert "box-01" not in health.text
    with api_app.state._ranked_sessions() as session:
        assert session.query(models_db.XiangqiRankedLedger).count() == 1
        assert session.query(models_db.XiangqiRankedReservation).filter_by(status="reserved").count() == 0
