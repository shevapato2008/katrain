"""Cloud ranked territory quota and private result contract."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.api.v1.endpoints.ai_ladder import analyze_ranked_territory, router
from katrain.web.core import models_db
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core.ai_ladder_ranked import (
    AiLadderRankedRepository,
    AiLadderLifecycleConflict,
    AiLadderLifecycleNotFound,
    InvalidReservationKey,
)

SGF = "(;GM[1]SZ[19]RU[chinese]KM[7.5];B[pd])"


@pytest.fixture
def territory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'territory.db'}", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    repo = AiLadderRankedRepository(sessions)
    with sessions() as db:
        user = models_db.User(username="territory", hashed_password="x")
        db.add(user)
        db.flush()
        db.add(
            models_db.AiLadderActiveGame(
                game_id="game",
                user_id=user.id,
                origin_device_id="device",
                state="active",
                version=1,
                reservation_key_hash=repo._hash_reservation_key("key"),
                user_color="B",
                game_type="ai_ladder_ranked",
                opponent_rung=1,
                opponent_rank_name="20k",
                opponent_config_snapshot={},
                opponent_certification_status="certified",
                opponent_availability="available",
                opponent_route="server",
                ai_subtype="test",
                execution_identity="test",
                rules_snapshot={"board_size": 19, "rules": "chinese", "komi": 7.5, "handicap": 0},
                time_control_snapshot={},
            )
        )
        db.commit()
        user_id = user.id
    return repo, sessions, user_id


def test_territory_claim_is_single_flight_and_reclaims_stale(territory):
    repo, sessions, user_id = territory
    first = repo.claim_territory(
        user_id=user_id, game_id="game", reservation_key="key", request_id="a", sgf_content=SGF
    )
    assert first["state"] == "claimed"
    assert repo.get_territory_status(user_id=user_id, game_id="game") == {"remaining": 3, "in_flight": True}
    with pytest.raises(AiLadderLifecycleConflict):
        repo.claim_territory(user_id=user_id, game_id="game", reservation_key="key", request_id="b", sgf_content=SGF)
    with sessions() as db:
        row = db.query(models_db.AiLadderTerritoryRequest).one()
        row.started_at = datetime.now(timezone.utc) - timedelta(seconds=91)
        db.commit()
    second = repo.claim_territory(
        user_id=user_id, game_id="game", reservation_key="key", request_id="b", sgf_content=SGF
    )
    assert second["state"] == "claimed"
    assert not repo.complete_territory(
        user_id=user_id, game_id="game", request_id="a", claim_token=first["claim_token"], result={}
    )


def test_territory_success_quota_and_idempotency(territory):
    repo, _, user_id = territory
    for n in range(3):
        request_id = str(n)
        claim = repo.claim_territory(
            user_id=user_id, game_id="game", reservation_key="key", request_id=request_id, sgf_content=SGF
        )
        assert repo.complete_territory(
            user_id=user_id,
            game_id="game",
            request_id=request_id,
            claim_token=claim["claim_token"],
            result={"ownership": [0.0] * 361, "black_area": 0, "white_area": 0, "move_count": 1},
        )
        replay = repo.claim_territory(
            user_id=user_id, game_id="game", reservation_key="key", request_id=request_id, sgf_content=SGF
        )
        assert replay["state"] == "replay" and replay["remaining"] == 2 - n
        with pytest.raises(AiLadderLifecycleConflict):
            repo.claim_territory(
                user_id=user_id, game_id="game", reservation_key="key", request_id=request_id, sgf_content=SGF + " "
            )
    assert repo.get_territory_status(user_id=user_id, game_id="game") == {"remaining": 0, "in_flight": False}
    with pytest.raises(AiLadderLifecycleConflict):
        repo.claim_territory(user_id=user_id, game_id="game", reservation_key="key", request_id="four", sgf_content=SGF)


def test_territory_requires_current_account_key_and_frozen_rules(territory):
    repo, sessions, user_id = territory
    with pytest.raises(AiLadderLifecycleNotFound):
        repo.get_territory_status(user_id=user_id + 1, game_id="game")
    with pytest.raises(InvalidReservationKey):
        repo.claim_territory(
            user_id=user_id, game_id="game", reservation_key="wrong", request_id="one", sgf_content=SGF
        )
    with sessions() as db:
        row = db.get(models_db.AiLadderActiveGame, "game")
        row.rules_snapshot = {"board_size": 19, "rules": "japanese", "komi": 6.5, "handicap": 0}
        db.commit()
    with pytest.raises(AiLadderLifecycleConflict):
        repo.claim_territory(user_id=user_id, game_id="game", reservation_key="key", request_id="one", sgf_content=SGF)
    with pytest.raises(AiLadderLifecycleConflict):
        repo.get_territory_status(user_id=user_id, game_id="game")


@pytest.mark.asyncio
async def test_territory_rejects_invalid_sgf_without_claim(territory):
    repo, _, user_id = territory
    app = SimpleNamespace(state=SimpleNamespace(ai_ladder_repo=repo))
    with pytest.raises(HTTPException) as exc:
        await analyze_ranked_territory(
            app,
            user_id=user_id,
            game_id="game",
            reservation_key="key",
            sgf_content="(;SZ[9]RU[chinese]KM[7.5];B[aa])",
            request_id="bad",
        )
    assert exc.value.status_code == 422
    assert repo.get_territory_status(user_id=user_id, game_id="game") == {"remaining": 3, "in_flight": False}


@pytest.mark.asyncio
async def test_territory_failure_does_not_charge_and_response_is_private(territory):
    repo, _, user_id = territory
    calls = []

    async def analyze(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise RuntimeError("engine down")
        return {"rootInfo": {"ownership": [0.2] * 361, "winrate": 0.9, "scoreLead": 9}, "moveInfos": [{"move": "D4"}]}

    app = SimpleNamespace(
        state=SimpleNamespace(
            ai_ladder_repo=repo, router=SimpleNamespace(local_client=SimpleNamespace(analyze=analyze))
        )
    )
    with pytest.raises(HTTPException) as exc:
        await analyze_ranked_territory(
            app, user_id=user_id, game_id="game", reservation_key="key", sgf_content=SGF, request_id="one"
        )
    assert exc.value.status_code == 503
    assert repo.get_territory_status(user_id=user_id, game_id="game") == {"remaining": 3, "in_flight": False}
    result = await analyze_ranked_territory(
        app, user_id=user_id, game_id="game", reservation_key="key", sgf_content=SGF, request_id="one"
    )
    assert result == {"remaining": 2, "move_count": 1, "ownership": [0.2] * 361, "black_area": 0, "white_area": 0}
    assert calls[-1]["includeOwnership"] is True and calls[-1]["includePolicy"] is False
    assert len(calls) == 2
    assert (
        await analyze_ranked_territory(
            app, user_id=user_id, game_id="game", reservation_key="key", sgf_content=SGF, request_id="one"
        )
        == result
    )
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_territory_routes_require_current_account_and_return_only_territory(territory):
    repo, sessions, user_id = territory
    with sessions() as db:
        other = models_db.User(username="other-territory", hashed_password="x")
        db.add(other)
        db.commit()

    async def analyze(payload):
        return {"ownership": [0.9] * 361, "rootInfo": {"winrate": 0.9, "scoreLead": 9}, "moveInfos": [{"move": "D4"}]}

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/ai-ladder")
    app.state.user_repo = SQLAlchemyUserRepository(sessions)
    app.state.ai_ladder_repo = repo
    app.state.ai_ladder_authoritative = True
    app.state.router = SimpleNamespace(local_client=SimpleNamespace(analyze=analyze))
    path = "/api/v1/ai-ladder/games/game/territory"
    owner = {"Authorization": f"Bearer {create_access_token({'sub': 'territory'})}"}
    other = {"Authorization": f"Bearer {create_access_token({'sub': 'other-territory'})}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(path)).status_code == 401
        assert (await client.get(path, headers=other)).status_code == 404
        assert (await client.get(path, headers=owner)).json() == {"remaining": 3, "in_flight": False}
        body = {"reservation_key": "key", "sgf_content": SGF, "request_id": "route"}
        assert (await client.post(path, headers=other, json=body)).status_code == 404
        response = await client.post(path, headers=owner, json=body)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"remaining", "move_count", "ownership", "black_area", "white_area"}
    assert response.json()["remaining"] == 2
