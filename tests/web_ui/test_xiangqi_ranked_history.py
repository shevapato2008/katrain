from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from tests.web_ui.test_xiangqi_ranked_api import api_app, auth
from tests.web_ui.test_xiangqi_ranked_reconcile import seed_terminal_events


@pytest.mark.asyncio
async def test_history_uses_an_independent_snapshot_cursor_for_more_than_100_summaries(api_app):
    seed_terminal_events(api_app, count=101)
    headers = auth(api_app.state._ranked_owner)
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        first = await client.get(
            "/api/v1/xiangqi-ranked/settlements",
            headers=headers,
            params={"after_seq": 0},
        )
        assert first.status_code == 200
        page = first.json()
        seed_terminal_events(api_app, count=1, start_seq=102)
        second = await client.get(
            "/api/v1/xiangqi-ranked/settlements",
            headers=headers,
            params={
                "after_seq": 0,
                "snapshot_seq": page["snapshot_seq"],
                "summary_cursor": page["next_summary_cursor"],
            },
        )

    assert page["snapshot_seq"] == 101
    assert page["has_more"] is True
    assert len(page["summaries"]) == 100
    assert second.status_code == 200
    assert [item["settlement_seq"] for item in second.json()["summaries"]] == [101]
    assert second.json()["has_more"] is False
    assert second.json()["profile"]["settlement_seq"] == 102


@pytest.mark.asyncio
async def test_history_cursor_is_bound_to_owner_snapshot_and_initial_after_seq(api_app):
    seed_terminal_events(api_app, count=101)
    headers = auth(api_app.state._ranked_owner)
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        first = await client.get("/api/v1/xiangqi-ranked/settlements", headers=headers, params={"after_seq": 0})
        page = first.json()
        cases = [
            {"after_seq": 1, "snapshot_seq": page["snapshot_seq"], "summary_cursor": page["next_summary_cursor"]},
            {"after_seq": 0, "snapshot_seq": page["snapshot_seq"] + 1, "summary_cursor": page["next_summary_cursor"]},
            {
                "after_seq": 0,
                "snapshot_seq": page["snapshot_seq"],
                "summary_cursor": page["next_summary_cursor"].rsplit(".", 1)[0]
                + ".x"
                + page["next_summary_cursor"].rsplit(".", 1)[1][1:],
            },
        ]
        rejected = [
            await client.get("/api/v1/xiangqi-ranked/settlements", headers=headers, params=params) for params in cases
        ]
        foreign = await client.get(
            "/api/v1/xiangqi-ranked/settlements",
            headers=auth(api_app.state._ranked_other),
            params={
                "after_seq": 0,
                "snapshot_seq": page["snapshot_seq"],
                "summary_cursor": page["next_summary_cursor"],
            },
        )

    assert all(response.status_code == 409 for response in rejected)
    assert foreign.status_code == 409


@pytest.mark.asyncio
async def test_history_requires_login_and_has_no_device_event_fields(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        unauthenticated = await client.get("/api/v1/xiangqi-ranked/settlements", params={"after_seq": 0})
        response = await client.get(
            "/api/v1/xiangqi-ranked/settlements",
            headers=auth(api_app.state._ranked_owner),
            params={"after_seq": 0},
        )
    assert unauthenticated.status_code == 401
    assert response.status_code == 200
    assert "event_statuses" not in response.json()
    assert "next_device_cursor" not in response.json()
