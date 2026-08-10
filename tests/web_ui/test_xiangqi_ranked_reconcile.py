from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.core import models_db
from tests.web_ui.test_xiangqi_ranked_api import NOW, api_app, auth, get_preview


def seed_terminal_events(app, *, count: int, device_id: str = "box-01", start_seq: int = 1) -> None:
    owner_uuid = app.state._ranked_owner["uuid"]
    with app.state._ranked_sessions.begin() as session:
        profile = session.get(models_db.XiangqiRatingProfile, owner_uuid)
        if profile is None:
            profile = models_db.XiangqiRatingProfile(
                user_uuid=owner_uuid,
                rating=1000.0,
                rated_games=0,
                profile_version=0,
                active_algo_version=4,
                settlement_seq=0,
                updated_at=NOW,
            )
            session.add(profile)
            session.flush()
        for local_seq in range(start_seq, start_seq + count):
            settlement_seq = profile.settlement_seq + 1
            game_id = f"{local_seq:08x}-0000-4000-8000-{local_seq:012d}"
            reservation_id = f"{local_seq:08x}-0000-4001-8000-{local_seq:012d}"
            status = ("settled", "resigned", "system_aborted")[(local_seq - 1) % 3]
            counted = status != "system_aborted"
            payload_hash = hashlib.sha256(f"payload-{device_id}-{local_seq}".encode()).hexdigest()
            rating_before = float(profile.rating)
            rating_after = rating_before + 1.0 if counted else None
            version_before = profile.profile_version
            version_after = version_before + int(counted)
            receipt = {
                "receipt_id": f"{local_seq:08x}-0000-4002-8000-{local_seq:012d}",
                "game_id": game_id,
                "reservation_id": reservation_id,
                "payload_hash": payload_hash,
                "status": status,
                "counted": counted,
                "reason": None if counted else "engine_unavailable",
                "rating_before_hex": rating_before.hex(),
                "rating_after_hex": None if rating_after is None else rating_after.hex(),
                "delta": 1 if counted else None,
                "tier_before": "学棋",
                "tier_after": "学棋" if counted else None,
                "profile_version_after": version_after,
                "settlement_seq": settlement_seq,
            }
            session.add(
                models_db.XiangqiRankedReservation(
                    reservation_id=reservation_id,
                    game_id=game_id,
                    user_uuid=owner_uuid,
                    device_id=device_id,
                    status=status,
                    expected_profile_version=version_before,
                    projection_fingerprint="1" * 64,
                    frozen_snapshot={"schema": "test"},
                    last_heartbeat_at=NOW,
                    created_at=NOW + timedelta(seconds=local_seq),
                    materialized_at=NOW,
                    terminal_at=NOW + timedelta(seconds=local_seq),
                )
            )
            session.add(
                models_db.XiangqiRankedLedger(
                    game_id=game_id,
                    receipt_id=receipt["receipt_id"],
                    reservation_id=reservation_id,
                    user_uuid=owner_uuid,
                    device_id=device_id,
                    local_seq=local_seq,
                    terminal_status=status,
                    payload_hash=payload_hash,
                    canonical_payload={"event_kind": "system_abort" if not counted else "settle"},
                    frozen_snapshot={"schema": "test"},
                    result=None if not counted else ("loss" if status == "resigned" else "win"),
                    counted=counted,
                    reason=None if counted else "engine_unavailable",
                    rating_before=rating_before,
                    rating_after=rating_after,
                    rating_delta=1 if counted else None,
                    tier_before="学棋",
                    tier_after="学棋" if counted else None,
                    profile_version_before=version_before,
                    profile_version_after=version_after,
                    settlement_seq=settlement_seq,
                    received_at=NOW + timedelta(seconds=local_seq),
                    settled_at=NOW + timedelta(seconds=local_seq),
                    receipt=receipt,
                )
            )
            if counted:
                profile.rating = rating_after
                profile.rated_games += 1
                profile.profile_version = version_after
            profile.settlement_seq = settlement_seq
            profile.updated_at = NOW + timedelta(seconds=local_seq)


def event(local_seq: int, *, device_id: str = "box-01") -> dict:
    return {
        "game_id": f"{local_seq:08x}-0000-4000-8000-{local_seq:012d}",
        "event_kind": ("settle", "resign", "system_abort")[(local_seq - 1) % 3],
        "payload_hash": hashlib.sha256(f"payload-{device_id}-{local_seq}".encode()).hexdigest(),
        "local_seq": local_seq,
    }


@pytest.mark.asyncio
async def test_device_reconcile_freezes_upper_bound_and_pages_more_than_100_without_history(api_app):
    seed_terminal_events(api_app, count=151)
    headers = auth(api_app.state._ranked_owner)
    body = {
        "device_id": "box-01",
        "known_profile_version": 0,
        "known_settlement_seq": 0,
        "through_local_seq": 150,
        "device_cursor": None,
        "event_snapshot_token": None,
        "events": [event(seq) for seq in range(1, 101)],
    }
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        first = await client.post("/api/v1/xiangqi-ranked/reconcile", headers=headers, json=body)
        assert first.status_code == 200
        page = first.json()
        second = await client.post(
            "/api/v1/xiangqi-ranked/reconcile",
            headers=headers,
            json={
                **body,
                "device_cursor": page["next_device_cursor"],
                "event_snapshot_token": page["event_snapshot_token"],
                "events": [event(seq) for seq in range(101, 151)],
            },
        )

    assert page["has_more"] is True
    assert len(page["event_statuses"]) == 100
    assert "remote_summaries" not in page
    assert second.status_code == 200
    assert second.json()["has_more"] is False
    assert [item["local_seq"] for item in second.json()["event_statuses"]] == list(range(101, 151))
    assert all(item["local_seq"] <= 150 for item in page["event_statuses"] + second.json()["event_statuses"])
    assert second.json()["profile"]["settlement_seq"] == 151


@pytest.mark.asyncio
async def test_reconcile_rejects_skips_repeats_tampering_and_cross_owner_cursor(api_app):
    seed_terminal_events(api_app, count=101)
    headers = auth(api_app.state._ranked_owner)
    base = {
        "device_id": "box-01",
        "known_profile_version": 0,
        "known_settlement_seq": 0,
        "through_local_seq": 101,
        "device_cursor": None,
        "event_snapshot_token": None,
        "events": [event(seq) for seq in range(1, 101)],
    }
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        first = await client.post("/api/v1/xiangqi-ranked/reconcile", headers=headers, json=base)
        page = first.json()
        requests = [
            {**base, "events": [event(1), event(1)]},
            {
                **base,
                "device_cursor": page["next_device_cursor"] + 1,
                "event_snapshot_token": page["event_snapshot_token"],
                "events": [event(101)],
            },
            {
                **base,
                "device_cursor": page["next_device_cursor"],
                "event_snapshot_token": page["event_snapshot_token"].rsplit(".", 1)[0]
                + ".x"
                + page["event_snapshot_token"].rsplit(".", 1)[1][1:],
                "events": [event(101)],
            },
        ]
        rejected = [
            await client.post("/api/v1/xiangqi-ranked/reconcile", headers=headers, json=value) for value in requests
        ]
        foreign = await client.post(
            "/api/v1/xiangqi-ranked/reconcile",
            headers=auth(api_app.state._ranked_other),
            json={
                **base,
                "device_cursor": page["next_device_cursor"],
                "event_snapshot_token": page["event_snapshot_token"],
                "events": [event(101)],
            },
        )

    assert first.status_code == 200
    assert all(response.status_code in {409, 422} for response in rejected)
    assert foreign.status_code == 409


@pytest.mark.asyncio
async def test_reconcile_requires_owner_and_forbids_request_user_uuid(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        unauthenticated = await client.post("/api/v1/xiangqi-ranked/reconcile", json={})
        forged = await client.post(
            "/api/v1/xiangqi-ranked/reconcile",
            headers=auth(api_app.state._ranked_owner),
            json={
                "user_uuid": api_app.state._ranked_other["uuid"],
                "device_id": "box-01",
                "known_profile_version": 0,
                "known_settlement_seq": 0,
                "through_local_seq": 0,
                "device_cursor": None,
                "event_snapshot_token": None,
                "events": [],
            },
        )
    assert unauthenticated.status_code == 401
    assert forged.status_code == 422
