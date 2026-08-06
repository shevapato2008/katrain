from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from smartbox_xiangqi_ranked import SUPPORTED_CATALOGS, pick_level
from smartbox_xiangqi_ranked.canonical import hash_preview

from katrain.web.core import migrations, models_db
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core.config import settings
from katrain.web.core.xiangqi_ranked_capabilities import TerminalCapabilityCodec, TerminalCapabilityStore
from katrain.web.core.xiangqi_ranked_repo import XiangqiRankedRepository
from katrain.web.core.xiangqi_ranked_service import FORCE_RESIGN_THRESHOLD, XiangqiRankedService
from katrain.web.server import create_app


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
GAME_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def api_app(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ranked-api.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    models_db.Base.metadata.create_all(engine)
    migrations.install_xiangqi_ranked_immutability(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    user_repo = SQLAlchemyUserRepository(sessions)
    owner = user_repo.create_user("ranked-owner", "x")
    other = user_repo.create_user("other-owner", "x")

    clock = {"now": NOW}
    ids = iter(
        (
            "660e8400-e29b-41d4-a716-446655440000",
            "770e8400-e29b-41d4-a716-446655440000",
            "880e8400-e29b-41d4-a716-446655440000",
            "990e8400-e29b-41d4-a716-446655440000",
            "aa0e8400-e29b-41d4-a716-446655440000",
            "bb0e8400-e29b-41d4-a716-446655440000",
        )
    )
    codec = TerminalCapabilityCodec(
        secret=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
        now=lambda: clock["now"],
        jti_factory=lambda: f"jti-{next(ids)}",
    )
    capabilities = TerminalCapabilityStore(sessions, codec)
    service = XiangqiRankedService(
        XiangqiRankedRepository(sessions),
        capabilities,
        now=lambda: clock["now"],
        id_factory=lambda: next(ids),
        color_chooser=lambda _colors: "red",
    )
    app = create_app(enable_engine=False)
    app.state.user_repo = user_repo
    app.state.xiangqi_ranked_service = service
    bridge_key = tmp_path / "bridge.key"
    bridge_key.write_text("local-service-secret", encoding="utf-8")
    app.state.box_sso.bridge_key_path = Path(bridge_key)
    app.state._ranked_sessions = sessions
    app.state._ranked_owner = owner
    app.state._ranked_other = other
    app.state._ranked_clock = clock
    return app


def auth(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': user['username']})}"}


def preview_body(**updates):
    body = {
        "device_id": "box-01",
        "catalog_version": "pikafish-r1",
        "supported_contract_versions": [4],
    }
    body.update(updates)
    return body


def reservation_body(preview, **updates):
    body = {
        "game_id": GAME_ID,
        "device_id": "box-01",
        "expected_profile_version": preview["profile"]["profile_version"],
        "projection_fingerprint": preview["preview"]["projection_fingerprint"],
        "scoring_contract_version": preview["preview"]["scoring_contract_version"],
        "catalog_version": preview["preview"]["catalog_version"],
        "opponent_profile_hash": preview["preview"]["opponent"]["profile_hash"],
        "time_control": "standard10",
    }
    body.update(updates)
    return body


async def get_preview(client, app, **updates):
    return await client.post(
        "/api/v1/xiangqi-ranked/previews",
        headers=auth(app.state._ranked_owner),
        json=preview_body(**updates),
    )


@pytest.mark.asyncio
async def test_preview_requires_bearer_identity_and_forbids_forged_owner_fields(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        unauthenticated = await client.post("/api/v1/xiangqi-ranked/previews", json=preview_body())
        forged = await client.post(
            "/api/v1/xiangqi-ranked/previews",
            headers=auth(api_app.state._ranked_owner),
            json=preview_body(user_uuid=api_app.state._ranked_other["uuid"]),
        )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "ranked_login_required"
    assert forged.status_code == 422
    assert forged.json()["code"] == "invalid_request"
    with api_app.state._ranked_sessions() as session:
        assert session.query(models_db.XiangqiRatingProfile).count() == 0


@pytest.mark.asyncio
async def test_preview_creates_1000_profile_and_uses_cloud_canonical_fingerprint(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        response = await get_preview(client, api_app)
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "ready"
    assert payload["profile"] == {
        "rating_hex": (1000.0).hex(),
        "rating_display": 1000,
        "rated_games": 0,
        "profile_version": 0,
        "settlement_seq": 0,
    }
    preview = payload["preview"]
    assert "canonical" not in preview
    canonical = {
        "schema": "xiangqi-ranked-preview-v1",
        "user_uuid": api_app.state._ranked_owner["uuid"],
        "profile_version": payload["profile"]["profile_version"],
        "rating_hex": payload["profile"]["rating_hex"],
        "rated_games": payload["profile"]["rated_games"],
        "scoring_contract_version": preview["scoring_contract_version"],
        "catalog_version": preview["catalog_version"],
        "opponent_profile_hash": preview["opponent"]["profile_hash"],
    }
    for outcome in ("win", "draw", "loss"):
        canonical[f"outcome_{outcome}_hex"] = preview["outcomes"][outcome]["rating_hex"]
        canonical[f"delta_{outcome}"] = preview["outcomes"][outcome]["delta"]
        canonical[f"tier_{outcome}"] = preview["outcomes"][outcome]["tier"]
    assert preview["projection_fingerprint"] == hash_preview(canonical)
    assert preview["opponent"]["level"] == pick_level(1000.0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"supported_contract_versions": [1, 2, 3]}, "unsupported_contract_version"),
        ({"catalog_version": "future-device-catalog"}, "unsupported_catalog_version"),
    ],
)
async def test_preview_rejects_contract_or_catalog_the_device_cannot_execute(api_app, updates, code):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        response = await get_preview(client, api_app, **updates)
    assert response.status_code == 422
    assert response.json()["code"] == code


def test_service_reaches_all_nine_shared_catalog_levels(api_app):
    service = api_app.state.xiangqi_ranked_service
    sessions = api_app.state._ranked_sessions
    owner = api_app.state._ranked_owner
    for expected, profile in enumerate(SUPPORTED_CATALOGS["pikafish-r1"].profiles, start=1):
        with sessions.begin() as session:
            rating = session.get(models_db.XiangqiRatingProfile, owner["uuid"])
            if rating is None:
                service.preview(
                    user_uuid=owner["uuid"],
                    device_id="box-01",
                    catalog_version="pikafish-r1",
                    supported_contract_versions=[4],
                )
                rating = session.get(models_db.XiangqiRatingProfile, owner["uuid"])
            rating.rating = float(profile.anchor)
        result = service.preview(
            user_uuid=owner["uuid"],
            device_id="box-01",
            catalog_version="pikafish-r1",
            supported_contract_versions=[4],
        )
        assert result["preview"]["opponent"]["level"] == expected


@pytest.mark.asyncio
async def test_reservation_freezes_exact_preview_server_color_and_terminal_capability(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        ready = (await get_preview(client, api_app)).json()
        response = await client.post(
            "/api/v1/xiangqi-ranked/reservations",
            headers=auth(api_app.state._ranked_owner),
            json=reservation_body(ready),
        )
        current = await client.get(
            "/api/v1/xiangqi-ranked/reservations/current", headers=auth(api_app.state._ranked_owner)
        )
    assert response.status_code == 201
    reserved = response.json()
    assert reserved["code"] == "reserved"
    assert reserved["player_color"] == "red"
    assert reserved["frozen_preview"]["time_control"] == "standard10"
    assert reserved["frozen_preview"]["profile_version"] == ready["profile"]["profile_version"]
    assert reserved["frozen_preview"]["projection_fingerprint"] == ready["preview"]["projection_fingerprint"]
    for outcome in ("win", "draw", "loss"):
        assert (
            reserved["frozen_preview"][f"outcome_{outcome}_hex"] == ready["preview"]["outcomes"][outcome]["rating_hex"]
        )
        assert reserved["frozen_preview"][f"delta_{outcome}"] == ready["preview"]["outcomes"][outcome]["delta"]
        assert reserved["frozen_preview"][f"tier_{outcome}"] == ready["preview"]["outcomes"][outcome]["tier"]
    assert reserved["frozen_preview"]["opponent_profile_hash"] == ready["preview"]["opponent"]["profile_hash"]
    assert reserved["terminal_capability"].count(".") == 2
    assert current.status_code == 200
    assert "terminal_capability" not in current.text
    assert current.json()["reservation"]["game_id"] == GAME_ID


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expected_profile_version", 99),
        ("projection_fingerprint", "f" * 64),
        ("opponent_profile_hash", "e" * 64),
        ("catalog_version", "pikafish-r0"),
    ],
)
async def test_reservation_recomputes_preview_and_rejects_any_stale_projection(api_app, field, value):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        ready = (await get_preview(client, api_app)).json()
        response = await client.post(
            "/api/v1/xiangqi-ranked/reservations",
            headers=auth(api_app.state._ranked_owner),
            json=reservation_body(ready, **{field: value}),
        )
    assert response.status_code == 409
    assert response.json()["code"] == "stale_projection"
    assert len(response.json()["preview"]["projection_fingerprint"]) == 64
    if field != "catalog_version":
        assert response.json()["preview"]["projection_fingerprint"] == ready["preview"]["projection_fingerprint"]
    with api_app.state._ranked_sessions() as session:
        assert session.query(models_db.XiangqiRankedReservation).count() == 0


@pytest.mark.asyncio
async def test_profile_change_after_preview_is_stale_and_existing_barrier_is_deterministic(api_app):
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        ready = (await get_preview(client, api_app)).json()
        with api_app.state._ranked_sessions.begin() as session:
            profile = session.get(models_db.XiangqiRatingProfile, api_app.state._ranked_owner["uuid"])
            profile.rating = 1040.0
            profile.rated_games = 1
            profile.profile_version = 1
        stale = await client.post(
            "/api/v1/xiangqi-ranked/reservations",
            headers=auth(api_app.state._ranked_owner),
            json=reservation_body(ready),
        )
        with api_app.state._ranked_sessions() as session:
            assert session.query(models_db.XiangqiRankedReservation).count() == 0
            assert session.query(models_db.XiangqiRankedCapabilityJti).count() == 0
        fresh = (await get_preview(client, api_app)).json()
        created = await client.post(
            "/api/v1/xiangqi-ranked/reservations",
            headers=auth(api_app.state._ranked_owner),
            json=reservation_body(fresh),
        )
        barrier = await get_preview(client, api_app)
    assert stale.status_code == 409 and stale.json()["profile"]["profile_version"] == 1
    with api_app.state._ranked_sessions() as session:
        assert session.query(models_db.XiangqiRankedCapabilityJti).count() == 1
    assert created.status_code == 201
    assert barrier.status_code == 409
    assert barrier.json()["code"] == "ranked_reserved_elsewhere"
    assert barrier.json()["reservation"]["device_id"] == "box-01"


@pytest.mark.asyncio
async def test_locked_reserve_recomputes_if_authority_changes_in_the_old_two_phase_seam(api_app, monkeypatch):
    from katrain.web.core import xiangqi_ranked_service as service_module

    headers = auth(api_app.state._ranked_owner)
    original_project_three = service_module.project_three

    def changed_project_three(*args, **kwargs):
        outcomes = original_project_three(*args, **kwargs)
        win = outcomes["win"]
        changed_after = replace(win.after, rating=win.after.rating + 1.0)
        outcomes["win"] = replace(
            win,
            after=changed_after,
            display_after=round(changed_after.rating),
            display_delta=round(changed_after.rating) - win.display_before,
        )
        return outcomes

    original_locked_reserve = api_app.state.xiangqi_ranked_service.repository.create_reservation_locked

    def reserve_after_authority_change(**kwargs):
        monkeypatch.setattr(service_module, "project_three", changed_project_three)
        return original_locked_reserve(**kwargs)

    monkeypatch.setattr(
        api_app.state.xiangqi_ranked_service.repository,
        "create_reservation_locked",
        reserve_after_authority_change,
    )
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        old = (await get_preview(client, api_app)).json()
        response = await client.post(
            "/api/v1/xiangqi-ranked/reservations",
            headers=headers,
            json=reservation_body(old),
        )
    assert response.status_code == 409
    assert response.json()["code"] == "stale_projection"
    assert response.json()["preview"]["outcomes"]["win"] != old["preview"]["outcomes"]["win"]
    with api_app.state._ranked_sessions() as session:
        assert session.query(models_db.XiangqiRankedReservation).count() == 0
        assert session.query(models_db.XiangqiRankedCapabilityJti).count() == 0


@pytest.mark.asyncio
async def test_concurrent_reservation_requests_create_only_one_account_barrier(api_app):
    headers = auth(api_app.state._ranked_owner)
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        ready = (await get_preview(client, api_app)).json()

        async def reserve(game_id, device_id):
            return await client.post(
                "/api/v1/xiangqi-ranked/reservations",
                headers=headers,
                json=reservation_body(ready, game_id=game_id, device_id=device_id),
            )

        responses = await asyncio.gather(
            reserve(GAME_ID, "box-01"),
            reserve("990e8400-e29b-41d4-a716-446655440000", "box-02"),
        )
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert next(response for response in responses if response.status_code == 409).json()["code"] == (
        "ranked_reserved_elsewhere"
    )
    with api_app.state._ranked_sessions() as session:
        assert session.query(models_db.XiangqiRankedReservation).filter_by(status="reserved").count() == 1


@pytest.mark.asyncio
async def test_owner_rotates_capability_old_jti_is_revoked_and_original_device_heartbeats(api_app):
    owner_headers = auth(api_app.state._ranked_owner)
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        ready = (await get_preview(client, api_app)).json()
        reserved = (
            await client.post(
                "/api/v1/xiangqi-ranked/reservations", headers=owner_headers, json=reservation_body(ready)
            )
        ).json()
        old = reserved["terminal_capability"]
        foreign_current = await client.get(
            "/api/v1/xiangqi-ranked/reservations/current", headers=auth(api_app.state._ranked_other)
        )
        foreign_rotate = await client.post(
            f"/api/v1/xiangqi-ranked/reservations/{reserved['reservation_id']}/capabilities/rotate",
            headers=auth(api_app.state._ranked_other),
            json={"game_id": GAME_ID},
        )
        rotated = await client.post(
            f"/api/v1/xiangqi-ranked/reservations/{reserved['reservation_id']}/capabilities/rotate",
            headers=owner_headers,
            json={"game_id": GAME_ID},
        )
        api_app.state._ranked_clock["now"] += timedelta(seconds=5)
        old_heartbeat = await client.post(
            f"/api/v1/xiangqi-ranked/reservations/{reserved['reservation_id']}/heartbeat",
            headers={"Authorization": f"Bearer {old}"},
            json={},
        )
        new_heartbeat = await client.post(
            f"/api/v1/xiangqi-ranked/reservations/{reserved['reservation_id']}/heartbeat",
            headers={"Authorization": f"Bearer {rotated.json()['terminal_capability']}"},
            json={},
        )
    assert foreign_current.json()["reservation"] is None
    assert foreign_rotate.status_code == 409
    assert rotated.status_code == 200
    assert old_heartbeat.status_code == 401
    assert old not in old_heartbeat.text
    assert new_heartbeat.status_code == 200
    assert new_heartbeat.json()["code"] == "heartbeat_recorded"


@pytest.mark.asyncio
async def test_force_resign_requires_owner_confirm_and_cloud_threshold_and_always_records_loss(api_app):
    owner_headers = auth(api_app.state._ranked_owner)
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        ready = (await get_preview(client, api_app)).json()
        reserved = (
            await client.post(
                "/api/v1/xiangqi-ranked/reservations", headers=owner_headers, json=reservation_body(ready)
            )
        ).json()
        path = f"/api/v1/xiangqi-ranked/reservations/{reserved['reservation_id']}/force-resign"
        forged = await client.post(path, headers=owner_headers, json={"confirm": True, "result": "win"})
        early = await client.post(path, headers=owner_headers, json={"confirm": True})
        api_app.state._ranked_clock["now"] += FORCE_RESIGN_THRESHOLD
        resigned = await client.post(path, headers=owner_headers, json={"confirm": True})
    assert forged.status_code == 422
    assert early.status_code == 409 and early.json()["code"] == "heartbeat_threshold_not_reached"
    assert resigned.status_code == 200
    assert resigned.json()["receipt"]["status"] == "resigned"
    assert resigned.json()["receipt"]["counted"] is True
    assert resigned.json()["receipt"]["delta"] == ready["preview"]["outcomes"]["loss"]["delta"]


@pytest.mark.asyncio
async def test_void_unmaterialized_rejects_browser_bearer_and_accepts_loopback_bridge(api_app):
    owner_headers = auth(api_app.state._ranked_owner)
    async with AsyncClient(
        transport=ASGITransport(app=api_app, client=("127.0.0.1", 123)), base_url="http://test"
    ) as client:
        ready = (await get_preview(client, api_app)).json()
        reserved = (
            await client.post(
                "/api/v1/xiangqi-ranked/reservations", headers=owner_headers, json=reservation_body(ready)
            )
        ).json()
        path = f"/api/v1/xiangqi-ranked/reservations/{reserved['reservation_id']}/void-unmaterialized"
        browser = await client.post(
            path,
            headers=owner_headers,
            json={"game_id": GAME_ID, "user_uuid": api_app.state._ranked_owner["uuid"]},
        )
        internal = await client.post(
            path,
            headers={"X-SmartBox-Bridge-Key": "local-service-secret"},
            json={"game_id": GAME_ID, "user_uuid": api_app.state._ranked_owner["uuid"]},
        )
    assert browser.status_code == 403
    assert internal.status_code == 200
    assert internal.json() == {"code": "voided", "voided": True}
