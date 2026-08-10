"""HTTP contract and trusted settlement tests for ranked AI ladder games."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
import logging
import threading
from pathlib import Path
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.ai_ladder_ranked import AiLadderRankedRepository
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core.db import Base
from katrain.web.core.engine_recovery import EngineRecoveryConfig, EngineRecoveryTracker
from katrain.web.core.ranked_session_guard import RankedAnalysisActivity
from katrain.web.core.user_game_repo import UserGameAnalysisRepository, UserGameRepository
from katrain.web import server
from katrain.web.server import create_app


class FixtureRecipe:
    def __init__(self, rung: int):
        self.rung = rung
        self.net = "fixture-net"
        self.mechanism = "net_search"
        self.max_visits = rung
        self.selection = "search"

    def to_dict(self):
        return {
            "rung": self.rung,
            "golaxy_level_name": None,
            "golaxy_api_level": None,
            "display_elo": None,
            "ref_rank": "",
            "rank_name": f"fixture-{self.rung}",
            "net": self.net,
            "mechanism": self.mechanism,
            "human_sl_profile": None,
            "max_visits": self.max_visits,
            "human_sl_params": {},
            "backend_hint": "server",
            "root_policy_temperature": 1.0,
            "human_policy_temperature": None,
            "selection": self.selection,
        }


def fixture_catalog(*, unavailable_rung: int | None = None, provisional_rung: int | None = None):
    return tuple(
        SimpleNamespace(
            rung=rung,
            rank_name=f"fixture-{rung}",
            certification_status="provisional" if rung == provisional_rung else "certified",
            availability="unavailable" if rung == unavailable_rung else "available",
            route="server",
            recipe=FixtureRecipe(rung),
        )
        for rung in range(1, 42)
    )


class FakeKaTrain:
    def __init__(self, username: str):
        self.calls = []
        self.config_updates = []
        self.game_type = "free"
        self.ladder_rung = None
        self.game = SimpleNamespace(
            end_result=None,
            current_node=SimpleNamespace(end_state=None, player="B", score=3.5),
        )
        self.players_info = {
            "B": SimpleNamespace(
                name=username,
                human=True,
                ai=False,
                calculated_rank=None,
                sgf_rank=None,
                player_subtype="player:human",
            ),
            "W": SimpleNamespace(
                name="",
                human=False,
                ai=True,
                calculated_rank=None,
                sgf_rank=None,
                player_subtype="ai:ladder",
            ),
        }
        self._state = {
            "board_size": [19, 19],
            "komi": 7.5,
            "ruleset": "chinese",
            "history": [{"move": [3, 3]}],
            "end_result": None,
            "player_to_move": "B",
        }

    def __call__(self, action, *args, **kwargs):
        self.calls.append((action, kwargs))
        if action == "update_player":
            info = self.players_info[kwargs["bw"]]
            subtype = kwargs["player_subtype"]
            info.player_subtype = subtype
            info.human = subtype == "player:human"
            info.ai = subtype != "player:human"
            if kwargs.get("name") is not None:
                info.name = kwargs["name"]
        elif action == "new_game":
            self.ladder_rung = {"rung": kwargs.get("ladder_rung")} if kwargs.get("ladder_rung") else None
            self.frozen_ladder_recipe = kwargs.get("frozen_ladder_recipe")
            self.game_type = kwargs.get("game_type", "free")
            self._state.update(
                board_size=[kwargs.get("size", 19), kwargs.get("size", 19)],
                komi=kwargs.get("komi", 7.5),
                ruleset=kwargs.get("rules", "chinese"),
            )
        elif action == "resign":
            self.game.end_result = "W+R"
            self.game.current_node.end_state = "W+R"
            self._state["end_result"] = "W+R"
        elif action == "timeout":
            self.game.end_result = "W+T"
            self.game.current_node.end_state = "W+T"
            self._state["end_result"] = "W+T"
        elif action == "play":
            self._state["history"].append({"move": args[0]})
            self._state["player_to_move"] = "W"

    def update_config(self, setting, value):
        self.config_updates.append((setting, value))

    def update_state(self):
        return None

    def shutdown(self):
        return None

    def config(self, setting, default=None):
        if setting == "game/count_min_moves":
            return 0
        return default

    def get_state(self):
        return dict(self._state)

    def get_sgf(self):
        result = self._state.get("end_result") or "Void"
        return (
            f"(;FF[4]GM[1]SZ[19]RU[chinese]KM[7.5]PB[{self.players_info['B'].name}]"
            f"PW[{self.players_info['W'].name}]RE[{result}];B[pd])"
        )


@pytest.fixture
def api_app(tmp_path, monkeypatch):
    from katrain.core import ladder

    monkeypatch.setattr(ladder, "LADDER_LEVELS", fixture_catalog())
    db_path = tmp_path / "ai-ladder-api.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    app = create_app(enable_engine=False)
    app.state.user_repo = SQLAlchemyUserRepository(sessions)
    app.state.user_game_repo = UserGameRepository(sessions)
    app.state.user_game_analysis_repo = UserGameAnalysisRepository(sessions)
    app.state.ai_ladder_repo = AiLadderRankedRepository(sessions)
    app.state.ai_ladder_authoritative = True
    app.state.report_session_factory = sessions

    with sessions() as db:
        user = models_db.User(username="ladder-user", hashed_password="x", rank="20k")
        db.add(user)
        db.commit()
        user_id = user.id
        user_uuid = user.uuid

    created_sessions = []

    def create_session(katago_uuid=None, **kwargs):
        app.state._test_last_create_kwargs = {"katago_uuid": katago_uuid, **kwargs}
        session_id = f"session-{len(created_sessions) + 1}"
        session = SimpleNamespace(
            session_id=session_id,
            user_id=kwargs.get("user_id"),
            player_b_id=None,
            player_w_id=None,
            mode="play",
            lock=threading.Lock(),
            sockets=set(),
            pending_count_request=None,
            pending_count_timestamp=None,
            katrain=FakeKaTrain("ladder-user"),
            last_state=None,
            last_access=0.0,
        )
        session.touch = lambda: None
        app.state.session_manager._sessions[session_id] = session
        created_sessions.append(session)
        return session

    monkeypatch.setattr(app.state.session_manager, "create_session", create_session)
    token = create_access_token({"sub": "ladder-user"})
    app.state._test_session_factory = sessions
    app.state._test_created_sessions = created_sessions
    app.state._test_user_id = user_id
    app.state._test_user_uuid = user_uuid
    app.state._test_headers = {"Authorization": f"Bearer {token}"}
    return app


@pytest.fixture
def client(api_app):
    return AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/ai-ladder/catalog"),
        ("get", "/api/v1/ai-ladder/status"),
        ("post", "/api/v1/ai-ladder/start"),
    ],
)
async def test_ai_ladder_endpoints_require_authentication(client, method, path):
    async with client as ac:
        response = await ac.post(path, json={}) if method == "post" else await ac.get(path)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_catalog_and_legacy_endpoint_use_the_same_product_projection(api_app, client):
    async with client as ac:
        catalog = await ac.get("/api/v1/ai-ladder/catalog", headers=api_app.state._test_headers)
        legacy = await ac.get("/api/ladder-rungs")

    assert catalog.status_code == 200
    assert catalog.json() == legacy.json()
    assert len(catalog.json()["rungs"]) == 41
    assert set(catalog.json()["rungs"][0]) == {
        "rung",
        "rank_name",
        "certification_status",
        "availability",
        "route",
    }


@pytest.mark.asyncio
async def test_status_projects_uncreated_profile_and_server_selected_midpoint(api_app, client):
    async with client as ac:
        response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert response.status_code == 200
    assert response.json() == {
        "view_state": "ready",
        "placement_state": {"phase": "placement", "completed_games": 0, "total_games": 5},
        "current_opponent": {
            "rung": 16,
            "rank_name": "fixture-16",
            "certification_status": "certified",
            "availability": "available",
            "route": "server",
            "counting_eligibility": "eligible",
        },
        "recent_ranked_results": [],
        "net_score": 0,
        "pending_settlement": False,
        "blocking_game": None,
        "provisional_play_allowed": False,
    }


@pytest.mark.asyncio
async def test_status_exposes_public_counting_eligibility_for_the_current_opponent(api_app, client):
    async with client as ac:
        response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert response.status_code == 200
    assert response.json()["current_opponent"] == {
        "rung": 16,
        "rank_name": "fixture-16",
        "certification_status": "certified",
        "availability": "available",
        "route": "server",
        "counting_eligibility": "eligible",
    }


@pytest.mark.asyncio
async def test_status_explains_when_the_current_opponent_will_not_count(api_app, client, monkeypatch):
    from katrain.core import ladder

    monkeypatch.setattr(ladder, "LADDER_LEVELS", fixture_catalog(provisional_rung=16))
    async with client as ac:
        response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    opponent = response.json()["current_opponent"]
    assert opponent["counting_eligibility"] == "ineligible"
    assert opponent["counting_reason"] == "opponent_not_eligible"


@pytest.mark.asyncio
async def test_game_scoped_settlement_receipt_moves_from_pending_to_settled(api_app, client):
    headers = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "receipt-device"}
    async with client as ac:
        reserved = await ac.post("/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload())
        game_id = reserved.json()["game_id"]

        pending = await ac.get(f"/api/v1/ai-ladder/settlements/{game_id}", headers=headers)
        settled_post = await ac.post(
            f"/api/v1/ai-ladder/games/{game_id}/end",
            headers=headers,
            json={"reason": "user_resigned"},
        )
        settled = await ac.get(f"/api/v1/ai-ladder/settlements/{game_id}", headers=headers)
        missing = await ac.get("/api/v1/ai-ladder/settlements/not-this-users-game", headers=api_app.state._test_headers)

    assert pending.status_code == 200
    assert pending.json() == {"state": "pending"}
    assert settled_post.status_code == 200
    assert settled.status_code == 200
    assert settled.json() == {
        "state": "settled",
        "game_id": game_id,
        "counted": True,
        "reason": None,
    }
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_settled_receipt_is_hidden_from_other_accounts(api_app, client):
    with api_app.state._test_session_factory() as db:
        db.add(models_db.User(username="receipt-attacker", hashed_password="x", rank="20k"))
        db.commit()
    owner = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "owner-board"}
    attacker = {"Authorization": f"Bearer {create_access_token({'sub': 'receipt-attacker'})}"}
    async with client as ac:
        reserved = await ac.post("/api/v1/ai-ladder/games/reserve", headers=owner, json=reservation_payload())
        game_id = reserved.json()["game_id"]
        await ac.post(
            f"/api/v1/ai-ladder/games/{game_id}/end",
            headers=owner,
            json={"reason": "user_resigned"},
        )
        response = await ac.get(f"/api/v1/ai-ladder/settlements/{game_id}", headers=attacker)

    assert response.status_code == 404
    assert response.json() == {"detail": "Ranked game not found"}


@pytest.mark.asyncio
async def test_status_projects_placed_profile_net_score_and_only_five_counted_results(api_app, client):
    from katrain.web.core.ai_ladder_catalog import build_opponent_snapshot

    with api_app.state._test_session_factory() as db:
        db.add(
            models_db.AiLadderProfile(
                user_id=api_app.state._test_user_id,
                ai_ladder_rung=20,
                placement_lo=20,
                placement_hi=20,
                placement_completed=5,
                net_score=0,
                version=0,
            )
        )
        db.commit()

    opponent, _ = build_opponent_snapshot(20)
    for index, result in enumerate(("win", "loss", "win", "win", "loss", "loss")):
        api_app.state.ai_ladder_repo.settle_game(
            user_id=api_app.state._test_user_id,
            game_id=f"status-{index}",
            user_color="B",
            result=result,
            game_type="ai_ladder_ranked",
            opponent=opponent,
        )

    async with client as ac:
        response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    payload = response.json()
    assert payload["placement_state"] == {
        "phase": "placed",
        "rung": {
            "rung": 20,
            "rank_name": "fixture-20",
            "certification_status": "certified",
            "availability": "available",
            "route": "server",
        },
    }
    assert payload["current_opponent"]["rung"] == 20
    assert payload["net_score"] == 0
    assert payload["recent_ranked_results"] == ["loss", "loss", "win", "win", "loss"]


async def start_ranked(api_app, client, **body):
    # Board size, ruleset, komi and handicap are server-owned (the conditions every
    # rung was calibrated under) and the request model forbids extras, so the client
    # sends seat + clock only.
    payload = {
        "color": "black",
        "time_enabled": False,
        **body,
    }
    return await client.post("/api/v1/ai-ladder/start", headers=api_app.state._test_headers, json=payload)


@pytest.mark.asyncio
async def test_start_issues_server_game_id_and_frozen_ranked_session_snapshot(api_app, client):
    async with client as ac:
        response = await start_ranked(api_app, ac)

    assert response.status_code == 201
    payload = response.json()
    assert len(payload["game_id"]) == 32
    assert int(payload["game_id"], 16) >= 0
    assert payload["opponent"]["rung"] == 16

    session = api_app.state._test_created_sessions[0]
    snapshot = session.ai_ladder_snapshot
    assert snapshot.game_id == payload["game_id"]
    assert snapshot.session_id == session.session_id
    assert snapshot.user_id == api_app.state._test_user_id
    assert snapshot.user_color == "B"
    assert snapshot.game_type == "ai_ladder_ranked"
    assert snapshot.opponent.rung == 16
    assert snapshot.opponent.rank_name == "fixture-16"
    assert snapshot.opponent.certification_status == "certified"
    assert snapshot.opponent.availability == "available"
    assert snapshot.opponent.route == "server"
    assert snapshot.opponent.config_snapshot["config_digest"]
    assert snapshot.opponent.config_snapshot["config_version"]
    assert snapshot.opponent.config_snapshot["recipe_identity"]
    assert snapshot.ai_subtype == "ai:ladder"
    assert session.game_type == "ai_ladder_ranked"
    assert session.katrain.game_type == "ai_ladder_ranked"
    assert session.katrain.ladder_rung == {"rung": 16}
    assert session.katrain.frozen_ladder_recipe.rung == 16
    assert session.katrain.frozen_ladder_recipe.max_visits == 16
    assert api_app.state._test_last_create_kwargs == {
        "katago_uuid": api_app.state._test_user_uuid,
        "user_id": api_app.state._test_user_id,
        "initial_game_type": "ai_ladder_ranked",
        "skip_initial_analysis": True,
    }
    ranked_new_game = next(kwargs for action, kwargs in session.katrain.calls if action == "new_game")
    assert ranked_new_game["skip_initial_analysis"] is True

    with api_app.state._test_session_factory() as db:
        assert "ai_ladder_pending_games" in inspect(db.get_bind()).get_table_names()
        pending = (
            db.execute(
                text(
                    "SELECT game_id, user_id, session_id, user_color, opponent_rung, opponent_rank_name, "
                    "opponent_config_snapshot, execution_identity, game_saved, saved_result "
                    "FROM ai_ladder_pending_games"
                )
            )
            .mappings()
            .one()
        )
        assert pending["game_id"] == payload["game_id"]
        assert pending["user_id"] == api_app.state._test_user_id
        assert pending["session_id"] == session.session_id
        assert pending["user_color"] == "B"
        assert pending["opponent_rung"] == 16
        assert pending["opponent_rank_name"] == "fixture-16"
        assert pending["execution_identity"] == snapshot.execution_identity
        assert pending["game_saved"] in (False, 0)
        assert pending["saved_result"] is None


RANKED_FORBIDDEN_SESSION_ACTIONS = (
    ("delete", "/api/session/{session_id}", {}),
    ("post", "/api/player", {"bw": "W", "player_type": "player:human", "player_subtype": "player:human"}),
    ("post", "/api/player/swap", {}),
    ("post", "/api/nav", {"node_id": 0}),
    ("post", "/api/nav/mistake", {"fn": "redo"}),
    ("post", "/api/nav/branch", {"direction": 1}),
    ("post", "/api/new-game", {"size": 13, "komi": 6.5, "rules": "japanese"}),
    ("post", "/api/game/setup", {"mode": "newgame", "settings": {"size": 13}}),
    ("post", "/api/edit-game", {"size": 13}),
    ("post", "/api/sgf/load", {"sgf": "(;FF[4]SZ[9])"}),
    ("post", "/api/config", {"setting": "timer/main_time", "value": 999}),
    ("post", "/api/config/bulk", {"updates": {"timer/main_time": 999}}),
    ("post", "/api/mode", {"mode": "analyze"}),
    ("post", "/api/mode/insert", {"mode": "toggle"}),
    ("post", "/api/ai-move", {"n_times": 1}),
    ("post", "/api/undo", {"n_times": 1}),
    ("post", "/api/redo", {"n_times": 1}),
    ("post", "/api/node/delete", {"node_id": 0}),
    ("post", "/api/node/prune", {"node_id": 0}),
    ("post", "/api/node/make-main", {"node_id": 0}),
    ("post", "/api/node/toggle-collapse", {"node_id": 0}),
    ("post", "/api/ui/toggle", {"setting": "ownership"}),
    ("post", "/api/analysis/continuous", {}),
    ("post", "/api/analysis/current", {}),
    ("post", "/api/analysis/extra", {"mode": "ownership"}),
    ("post", "/api/analysis/show-pv", {"pv": "D4 Q16"}),
    ("post", "/api/analysis/clear-pv", {}),
    ("post", "/api/analysis/tsumego", {"ko": False}),
    ("post", "/api/analysis/selfplay", {"until_move": 10}),
    ("post", "/api/analysis/region", {"coords": [0, 0, 3, 3]}),
    ("post", "/api/analysis/game", {"visits": 50}),
    ("post", "/api/analysis/scan", {"visits": 50}),
    ("get", "/api/analysis/progress", {}),
    ("post", "/api/analysis/report", {}),
    ("post", "/api/timer/pause", {}),
    ("post", "/api/v1/analysis/analyze", {"payload": {"maxVisits": 50}}),
    ("post", "/api/v1/hint", {"top_n": 3}),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,payload", RANKED_FORBIDDEN_SESSION_ACTIONS)
async def test_ranked_session_rejects_canonical_mutation_and_analysis_endpoints(api_app, client, method, path, payload):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session_id = started.json()["session_id"]
        session = api_app.state._test_created_sessions[0]
        resolved_path = path.format(session_id=session_id)
        if method == "get":
            response = await ac.get(
                resolved_path, headers=api_app.state._test_headers, params={"session_id": session_id, **payload}
            )
        elif method == "delete":
            response = await ac.delete(resolved_path, headers=api_app.state._test_headers)
        else:
            response = await ac.post(
                resolved_path, headers=api_app.state._test_headers, json={"session_id": session_id, **payload}
            )

    assert response.status_code == 403, (path, response.text)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,payload",
    (
        ("/api/ui/toggle", {"setting": "coords"}),
        ("/api/ui/toggle", {"setting": "numbers"}),
        ("/api/ui/toggle", {"setting": "zen_mode"}),
        ("/api/language", {"lang": "en"}),
        ("/api/theme", {"theme": "dark"}),
    ),
)
async def test_ranked_session_keeps_cosmetic_controls_available(api_app, client, path, payload):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        response = await ac.post(
            path,
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"], **payload},
        )

    assert response.status_code == 200, (path, response.text)


@pytest.mark.asyncio
async def test_free_session_canonical_mutations_remain_available(api_app, client):
    session = api_app.state.session_manager.create_session(user_id=api_app.state._test_user_id)
    session.game_type = "free"
    session.katrain.game_type = "free"
    async with client as ac:
        responses = (
            await ac.post(
                "/api/player",
                json={
                    "session_id": session.session_id,
                    "bw": "W",
                    "player_type": "player:human",
                    "player_subtype": "player:human",
                },
            ),
            await ac.post(
                "/api/config",
                json={"session_id": session.session_id, "setting": "timer/main_time", "value": 10},
            ),
            await ac.post(
                "/api/nav", headers=api_app.state._test_headers, json={"session_id": session.session_id, "node_id": 0}
            ),
            await ac.post(
                "/api/analysis/current",
                headers=api_app.state._test_headers,
                json={"session_id": session.session_id},
            ),
            await ac.post(
                "/api/new-game",
                headers=api_app.state._test_headers,
                json={"session_id": session.session_id, "size": 19, "komi": 7.5, "rules": "chinese"},
            ),
        )

    assert [response.status_code for response in responses] == [200, 200, 200, 200, 200]


@pytest.mark.asyncio
async def test_ranked_session_cannot_be_used_to_extract_saved_analysis(api_app, client):
    game_id = "free-analysis-source"
    api_app.state.user_game_repo.create(
        user_id=api_app.state._test_user_id,
        game_id=game_id,
        sgf_content="(;FF[4]SZ[19])",
        source="import",
        game_type="free",
    )
    async with client as ac:
        started = await start_ranked(api_app, ac)
        response = await ac.post(
            f"/api/v1/user-games/{game_id}/analysis/save",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"], "game_id": game_id},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,payload",
    (
        ("/api/analysis/current", {}),
        ("/api/analysis/extra", {"mode": "ownership"}),
        ("/api/analysis/show-pv", {"pv": "D4 Q16"}),
        ("/api/analysis/region", {"coords": [0, 0, 3, 3]}),
        ("/api/analysis/game", {"visits": 50}),
        ("/api/nav/mistake", {"fn": "redo"}),
        ("/api/nav", {"node_id": 0}),
        ("/api/mode", {"mode": "analyze"}),
        ("/api/ui/toggle", {"setting": "ownership"}),
        ("/api/v1/analysis/analyze", {"payload": {"maxVisits": 50}}),
        ("/api/v1/hint", {"top_n": 3}),
    ),
)
async def test_pending_ranked_user_cannot_analyze_a_second_free_session(api_app, client, path, payload):
    async with client as ac:
        await start_ranked(api_app, ac)
        free = api_app.state.session_manager.create_session()
        free.user_id = api_app.state._test_user_id
        response = await ac.post(
            path,
            headers=api_app.state._test_headers,
            json={"session_id": free.session_id, **payload},
        )

    assert response.status_code == 403, (path, response.text)


@pytest.mark.asyncio
async def test_pending_ranked_user_cannot_read_second_free_session_state(api_app, client):
    free = api_app.state.session_manager.create_session(user_id=api_app.state._test_user_id)
    async with client as ac:
        anonymous = await ac.get("/api/state", params={"session_id": free.session_id})
        await start_ranked(api_app, ac)
        pending = await ac.get(
            "/api/state", headers=api_app.state._test_headers, params={"session_id": free.session_id}
        )

    assert anonymous.status_code == 401
    assert pending.status_code == 403


@pytest.mark.asyncio
async def test_ranked_owner_can_read_analysis_free_ranked_state(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        response = await ac.get(
            "/api/state",
            headers=api_app.state._test_headers,
            params={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 200
    assert response.json()["session_id"] == started.json()["session_id"]


@pytest.mark.asyncio
async def test_other_user_cannot_read_free_session_state(api_app, client):
    with api_app.state._test_session_factory() as db:
        db.add(models_db.User(username="state-other", hashed_password="x", rank="20k"))
        db.commit()
    other_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'state-other'})}"}
    free = api_app.state.session_manager.create_session(user_id=api_app.state._test_user_id)

    async with client as ac:
        response = await ac.get("/api/state", headers=other_headers, params={"session_id": free.session_id})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_free_session_creation_registers_auto_analysis_before_ranked_start(api_app, client):
    async with client as ac:
        created = await ac.post("/api/session", headers=api_app.state._test_headers)
        started = await start_ranked(api_app, ac)

    assert created.status_code == 200
    assert started.status_code == 409
    assert api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,payload",
    (
        ("/api/new-game", {"size": 19, "komi": 7.5, "rules": "chinese"}),
        ("/api/move", {"coords": [3, 3]}),
    ),
)
async def test_free_auto_eval_lifecycle_blocks_ranked_start(api_app, client, path, payload):
    free = api_app.state.session_manager.create_session(user_id=api_app.state._test_user_id)
    async with client as ac:
        mutation = await ac.post(
            path,
            headers=api_app.state._test_headers,
            json={"session_id": free.session_id, **payload},
        )
        started = await start_ranked(api_app, ac)

    assert mutation.status_code == 200
    assert started.status_code == 409


def test_activity_end_session_clears_all_users_for_reset_session():
    activity = RankedAnalysisActivity()
    activity.begin_background(1, "shared", "current")
    activity.begin_background(2, "shared", "scan")

    activity.end_session("shared")

    assert activity.reserve_ranked_start(1)
    assert activity.reserve_ranked_start(2)


@pytest.mark.asyncio
async def test_legacy_analysis_requires_auth_but_other_user_free_session_remains_available(api_app, client):
    with api_app.state._test_session_factory() as db:
        db.add(models_db.User(username="analysis-other", hashed_password="x", rank="20k"))
        db.commit()
    other_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'analysis-other'})}"}
    free = api_app.state.session_manager.create_session()
    async with client as ac:
        anonymous = await ac.post("/api/analysis/current", json={"session_id": free.session_id})
        await start_ranked(api_app, ac)
        other = await ac.post("/api/analysis/current", headers=other_headers, json={"session_id": free.session_id})

    assert anonymous.status_code == 401
    assert other.status_code == 200


@pytest.mark.asyncio
async def test_v1_session_analysis_in_flight_does_not_return_after_ranked_game_starts(api_app, client):
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingRouter:
        async def route(self, payload):
            entered.set()
            await release.wait()
            return {"engine": "fixture", "moveInfos": [{"move": "D4"}]}

    api_app.state.router = BlockingRouter()
    free = api_app.state.session_manager.create_session()
    free.user_id = api_app.state._test_user_id
    async with client as ac:
        analysis_task = asyncio.create_task(
            ac.post(
                "/api/v1/analysis/analyze",
                headers=api_app.state._test_headers,
                json={"session_id": free.session_id, "payload": {"maxVisits": 50}},
            )
        )
        await entered.wait()
        started = await start_ranked(api_app, ac)
        release.set()
        analysis = await analysis_task

    assert started.status_code == 409
    assert analysis.status_code == 200
    assert analysis.json()["moveInfos"][0]["move"] == "D4"
    assert free.katrain.last_engine == "fixture"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "analysis_path,payload",
    (
        ("/api/analysis/current", {}),
        ("/api/analysis/continuous", {}),
        ("/api/analysis/scan", {"visits": 50}),
        ("/api/analysis/game", {"visits": 50}),
        ("/api/analysis/selfplay", {"until_move": 10}),
        ("/api/nav", {"node_id": 0}),
    ),
)
async def test_ranked_start_rejects_preexisting_background_analysis(api_app, client, analysis_path, payload):
    free = api_app.state.session_manager.create_session()
    free.user_id = api_app.state._test_user_id
    free.katrain.pondering = False
    free.katrain.update_state = lambda: None
    async with client as ac:
        analysis = await ac.post(
            analysis_path,
            headers=api_app.state._test_headers,
            json={"session_id": free.session_id, **payload},
        )
        started = await start_ranked(api_app, ac)

    assert analysis.status_code == 200
    assert started.status_code == 409
    assert api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id) is None


@pytest.mark.asyncio
async def test_pending_ranked_user_navigation_does_not_trigger_free_session_analysis(api_app, client):
    async with client as ac:
        await start_ranked(api_app, ac)
        free = api_app.state.session_manager.create_session()
        calls_before = list(free.katrain.calls)
        response = await ac.post(
            "/api/nav",
            headers=api_app.state._test_headers,
            json={"session_id": free.session_id, "node_id": 0},
        )

    assert response.status_code == 403
    assert free.katrain.calls == calls_before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,payload",
    (
        ("/api/sgf/load", {"sgf": "(;FF[4]SZ[19])", "skip_analysis": False}),
        ("/api/game/setup", {"mode": "newgame", "settings": {"size": 19}}),
        ("/api/edit-game", {"size": 13}),
        ("/api/undo", {}),
        ("/api/redo", {}),
        ("/api/ai-move", {}),
    ),
)
async def test_pending_ranked_user_cannot_trigger_legacy_auto_analysis_mutations(api_app, client, path, payload):
    async with client as ac:
        await start_ranked(api_app, ac)
        free = api_app.state.session_manager.create_session(user_id=api_app.state._test_user_id)
        calls_before = list(free.katrain.calls)
        response = await ac.post(
            path,
            headers=api_app.state._test_headers,
            json={"session_id": free.session_id, **payload},
        )

    assert response.status_code == 403
    assert free.katrain.calls == calls_before


@pytest.mark.asyncio
async def test_stopping_continuous_analysis_releases_ranked_start(api_app, client):
    free = api_app.state.session_manager.create_session()
    free.user_id = api_app.state._test_user_id
    free.katrain.pondering = False
    free.katrain.update_state = lambda: None
    async with client as ac:
        first = await ac.post(
            "/api/analysis/continuous",
            headers=api_app.state._test_headers,
            json={"session_id": free.session_id},
        )
        stopped = await ac.post(
            "/api/analysis/continuous",
            headers=api_app.state._test_headers,
            json={"session_id": free.session_id},
        )
        started = await start_ranked(api_app, ac)

    assert first.status_code == 200 and first.json()["pondering"] is True
    assert stopped.status_code == 200 and stopped.json()["pondering"] is False
    assert started.status_code == 201


@pytest.mark.asyncio
async def test_quick_analysis_requires_auth_and_is_blocked_while_ranked_game_pending(api_app, client):
    api_app.state.router = SimpleNamespace(route=lambda payload: None)
    async with client as ac:
        unauthenticated = await ac.post("/api/v1/analysis/quick-analyze", json={"moves": []})
        await start_ranked(api_app, ac)
        ranked = await ac.post(
            "/api/v1/analysis/quick-analyze",
            headers=api_app.state._test_headers,
            json={"moves": []},
        )

    assert unauthenticated.status_code == 401
    assert ranked.status_code == 403


@pytest.mark.asyncio
async def test_quick_analysis_in_flight_does_not_return_after_ranked_game_starts(api_app, client):
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingRouter:
        async def route(self, payload):
            entered.set()
            await release.wait()
            return {"moveInfos": [{"move": "D4"}]}

    api_app.state.router = BlockingRouter()
    async with client as ac:
        analysis_task = asyncio.create_task(
            ac.post("/api/v1/analysis/quick-analyze", headers=api_app.state._test_headers, json={"moves": []})
        )
        await entered.wait()
        started = await start_ranked(api_app, ac)
        release.set()
        analysis = await analysis_task

    assert started.status_code == 409
    assert analysis.status_code == 200
    assert analysis.json()["moveInfos"][0]["move"] == "D4"


@pytest.mark.asyncio
async def test_concurrent_quick_analysis_leases_are_reference_counted(api_app, client):
    entered = asyncio.Queue()
    releases = [asyncio.Event(), asyncio.Event()]

    class TwiceBlockingRouter:
        def __init__(self):
            self.next_index = 0

        async def route(self, payload):
            index = self.next_index
            self.next_index += 1
            await entered.put(index)
            await releases[index].wait()
            return {"moveInfos": [{"move": "D4"}]}

    api_app.state.router = TwiceBlockingRouter()
    async with client as ac:
        tasks = [
            asyncio.create_task(
                ac.post("/api/v1/analysis/quick-analyze", headers=api_app.state._test_headers, json={"moves": []})
            )
            for _ in range(2)
        ]
        await entered.get()
        await entered.get()
        releases[0].set()
        assert (await tasks[0]).status_code == 200
        while_first_finished = await start_ranked(api_app, ac)
        releases[1].set()
        assert (await tasks[1]).status_code == 200
        after_both_finished = await start_ranked(api_app, ac)

    assert while_first_finished.status_code == 409
    assert after_both_finished.status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", ["invalid-reset", "delete"])
async def test_session_reset_or_delete_cannot_clear_inflight_temporary_analysis_lease(api_app, client, interrupt):
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingRouter:
        async def route(self, payload):
            entered.set()
            await release.wait()
            return {"engine": "fixture", "moveInfos": [{"move": "D4"}]}

    api_app.state.router = BlockingRouter()
    free = api_app.state.session_manager.create_session(user_id=api_app.state._test_user_id)
    async with client as ac:
        analysis_task = asyncio.create_task(
            ac.post(
                "/api/v1/analysis/analyze",
                headers=api_app.state._test_headers,
                json={"session_id": free.session_id, "payload": {"maxVisits": 50}},
            )
        )
        await entered.wait()
        if interrupt == "invalid-reset":
            interrupted = await ac.post(
                "/api/new-game",
                headers=api_app.state._test_headers,
                json={"session_id": free.session_id, "ladder_rung": 999},
            )
            assert interrupted.status_code == 422
        else:
            interrupted = await ac.delete(f"/api/session/{free.session_id}", headers=api_app.state._test_headers)
            assert interrupted.status_code == 200

        while_analysis_runs = await start_ranked(api_app, ac)
        release.set()
        assert (await analysis_task).status_code == 200
        after_analysis = await start_ranked(api_app, ac)

    assert while_analysis_runs.status_code == 409
    assert after_analysis.status_code == 201


@pytest.mark.asyncio
async def test_active_ranked_sgf_export_is_blocked(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        response = await ac.get(
            "/api/sgf/save",
            headers=api_app.state._test_headers,
            params={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_settled_ranked_sgf_export_uses_shared_game_history_instead_of_live_session(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session_id = started.json()["session_id"]
        resigned = await ac.post("/api/resign", headers=api_app.state._test_headers, json={"session_id": session_id})
        response = await ac.get("/api/sgf/save", headers=api_app.state._test_headers, params={"session_id": session_id})

    assert resigned.status_code == 200
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_settled_ranked_game_rejects_public_and_vision_moves_without_changing_sgf(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session_id = started.json()["session_id"]
        session = api_app.state._test_created_sessions[0]
        assert (
            await ac.post("/api/resign", headers=api_app.state._test_headers, json={"session_id": session_id})
        ).status_code == 200
        sgf_before = session.katrain.get_sgf()
        snapshot = session.ai_ladder_snapshot
        vision = SimpleNamespace(bound_session_id=session_id, set_expected_from_stones=lambda stones: None)
        api_app.state.ranked_vision_binding = SimpleNamespace(
            session_id=session_id,
            user_id=snapshot.user_id,
            user_color=snapshot.user_color,
            game_id=snapshot.game_id,
        )
        public_move = await ac.post(
            "/api/move",
            headers=api_app.state._test_headers,
            json={"session_id": session_id, "coords": [4, 4]},
        )
        delay = await __import__("katrain.web.server", fromlist=["_handle_confirmed_move"])._handle_confirmed_move(
            api_app, vision, session_id, SimpleNamespace(col=4, row=4, color=1), logging.getLogger("vision")
        )
        sgf_after = session.katrain.get_sgf()

    assert public_move.status_code == 403
    assert delay == 0.5
    assert sgf_after == sgf_before


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"coords": [3, 3]}, {"pass_move": True}])
async def test_ranked_session_still_allows_human_move_and_pass(api_app, client, payload):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session_id = started.json()["session_id"]
        response = await ac.post(
            "/api/move",
            headers=api_app.state._test_headers,
            json={"session_id": session_id, **payload},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_ranked_human_moves_recheck_turn_inside_session_lock(api_app, client, monkeypatch):
    import katrain.web.server as server_module

    observed_lock_states = []
    original_guard = server_module.guard_ai_ladder_ranked_human_action

    def observing_guard(session, current_user, action):
        observed_lock_states.append(session.lock.locked())
        return original_guard(session, current_user, action)

    monkeypatch.setattr(server_module, "guard_ai_ladder_ranked_human_action", observing_guard)
    async with client as ac:
        started = await start_ranked(api_app, ac)
        body = {"session_id": started.json()["session_id"], "coords": [3, 3]}
        first, second = await asyncio.gather(
            ac.post("/api/move", headers=api_app.state._test_headers, json=body),
            ac.post("/api/move", headers=api_app.state._test_headers, json=body),
        )

    assert sorted((first.status_code, second.status_code)) == [200, 403]
    assert True in observed_lock_states
    session = api_app.state._test_created_sessions[0]
    assert len(session.katrain._state["history"]) == 2


@pytest.mark.asyncio
async def test_ranked_vision_bind_requires_owner_and_freezes_identity(api_app, client):
    vision = SimpleNamespace(bound_session_id=None)

    def bind_session(session_id):
        vision.bound_session_id = session_id

    vision.bind_session = bind_session
    vision.set_expected_from_stones = lambda stones: None
    api_app.state.vision = vision
    async with client as ac:
        started = await start_ranked(api_app, ac)
        response = await ac.post(
            "/api/v1/vision/bind",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 200
    assert vision.bound_session_id == started.json()["session_id"]
    binding = api_app.state.ranked_vision_binding
    assert binding.user_id == api_app.state._test_user_id
    assert binding.user_color == "B"
    assert binding.game_id == started.json()["game_id"]


@pytest.mark.asyncio
async def test_ranked_vision_bind_rejects_unauthenticated_and_non_owner(api_app, client):
    vision = SimpleNamespace(bound_session_id=None, bind_session=lambda session_id: None)
    api_app.state.vision = vision
    with api_app.state._test_session_factory() as db:
        other = models_db.User(username="vision-other", hashed_password="x", rank="20k")
        db.add(other)
        db.commit()
    other_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'vision-other'})}"}
    async with client as ac:
        started = await start_ranked(api_app, ac)
        body = {"session_id": started.json()["session_id"]}
        unauthenticated = await ac.post("/api/v1/vision/bind", json=body)
        non_owner = await ac.post("/api/v1/vision/bind", headers=other_headers, json=body)

    assert unauthenticated.status_code == 403
    assert non_owner.status_code == 403
    assert vision.bound_session_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("board_size", 9), ("rules", "japanese"), ("komi", 6.5), ("handicap", 4)])
async def test_start_refuses_to_take_board_conditions_from_the_client(api_app, client, field, value):
    """A rung's rank name describes its strength at 19x19 / Chinese / 7.5 / no handicap
    and nothing else. A client that could pick the board would be seating an opponent
    whose measured strength no longer describes the game -- and then banking it. The
    request model forbids extras, so this is a 422 rather than a silently dropped field.

    Both shipping clients used to send komi 6.5 here (galaxy also sent Japanese rules),
    which is how a mismatch this size stayed invisible: the tests sent 7.5.
    """
    async with client as ac:
        response = await start_ranked(api_app, ac, **{field: value})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_started_ranked_game_is_always_on_the_calibrated_board(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
    assert started.status_code == 201
    katrain = api_app.state._test_created_sessions[0].katrain
    new_game = next(kwargs for action, kwargs in katrain.calls if action == "new_game")
    assert new_game["size"] == 19
    assert new_game["rules"] == "chinese"
    assert new_game["komi"] == 7.5
    assert new_game["handicap"] == 0


@pytest.mark.asyncio
async def test_vision_bind_rejects_unsupported_physical_board_size(api_app, client):
    """The physical board is 19x19. Ranked games can no longer be anything else (above),
    so this guard is now exercised through an ordinary session."""
    vision = SimpleNamespace(bound_session_id=None)
    vision.bind_session = lambda session_id: setattr(vision, "bound_session_id", session_id)
    api_app.state.vision = vision
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session_id = started.json()["session_id"]
        api_app.state._test_created_sessions[0].katrain._state["board_size"] = [9, 9]
        response = await ac.post(
            "/api/v1/vision/bind",
            headers=api_app.state._test_headers,
            json={"session_id": session_id},
        )

    assert response.status_code == 409
    assert vision.bound_session_id is None


@pytest.mark.asyncio
async def test_confirmed_ranked_vision_move_plays_exactly_once_on_human_turn(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
    session_id = started.json()["session_id"]
    snapshot = api_app.state._test_created_sessions[0].ai_ladder_snapshot
    api_app.state.ranked_vision_binding = SimpleNamespace(
        session_id=session_id, user_id=snapshot.user_id, user_color=snapshot.user_color, game_id=snapshot.game_id
    )
    vision = SimpleNamespace(bound_session_id=session_id, set_expected_from_stones=lambda stones: None)

    handler = __import__("katrain.web.server", fromlist=["_handle_confirmed_move"])._handle_confirmed_move
    first, duplicate = await asyncio.gather(
        handler(api_app, vision, session_id, SimpleNamespace(col=3, row=3, color=1), logging.getLogger("vision")),
        handler(api_app, vision, session_id, SimpleNamespace(col=3, row=3, color=1), logging.getLogger("vision")),
    )

    assert sorted((first, duplicate)) == [0.0, 0.5]
    assert len(api_app.state._test_created_sessions[0].katrain._state["history"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", ["ai_turn", "seat"])
async def test_confirmed_ranked_vision_move_rejects_ai_turn_and_seat_tamper(api_app, client, tamper):
    async with client as ac:
        started = await start_ranked(api_app, ac)
    session = api_app.state._test_created_sessions[0]
    snapshot = session.ai_ladder_snapshot
    api_app.state.ranked_vision_binding = SimpleNamespace(
        session_id=session.session_id,
        user_id=snapshot.user_id,
        user_color=snapshot.user_color,
        game_id=snapshot.game_id,
    )
    if tamper == "ai_turn":
        session.katrain._state["player_to_move"] = "W"
    else:
        session.katrain.players_info["W"].player_subtype = "ai:default"
    before = list(session.katrain._state["history"])
    vision = SimpleNamespace(bound_session_id=session.session_id, set_expected_from_stones=lambda stones: None)

    delay = await __import__("katrain.web.server", fromlist=["_handle_confirmed_move"])._handle_confirmed_move(
        api_app, vision, session.session_id, SimpleNamespace(col=3, row=3, color=1), logging.getLogger("vision")
    )

    assert delay == 0.5
    assert session.katrain._state["history"] == before


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["retry", "cancel"])
async def test_ranked_vision_recovery_requires_bound_owner_and_never_injects_human_move(api_app, client, action):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        snapshot = session.ai_ladder_snapshot
        api_app.state.vision = SimpleNamespace(bound_session_id=session.session_id)
        api_app.state.ranked_vision_binding = SimpleNamespace(
            session_id=session.session_id,
            user_id=snapshot.user_id,
            user_color=snapshot.user_color,
            game_id=snapshot.game_id,
        )
        api_app.state.engine_recovery = EngineRecoveryTracker(EngineRecoveryConfig())
        episode = api_app.state.engine_recovery.trip_now(
            game_id=snapshot.game_id, coords=(3, 3), detail="fixture failure"
        )
        body = {"session_id": session.session_id, "recovery_token": episode.recovery_token}
        unauthenticated = await ac.post(f"/api/v1/vision/engine-move/{action}", json=body)
        assert unauthenticated.status_code == 403
        assert api_app.state.engine_recovery.active_episode.recovery_token == episode.recovery_token
        history_before = list(session.katrain._state["history"])
        owner = await ac.post(f"/api/v1/vision/engine-move/{action}", headers=api_app.state._test_headers, json=body)

    assert owner.status_code == 200
    assert session.katrain._state["history"] == history_before
    if action == "retry":
        assert owner.json()["ok"] is False
        assert owner.json()["recovery_token"] != episode.recovery_token
    else:
        assert owner.json() == {"ok": True, "awaiting_removal": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/resign", "/api/count/request", "/api/timeout"])
async def test_ranked_session_allows_human_turn_terminal_actions(api_app, client, path):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        response = await ac.post(
            path,
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 200, (path, response.text)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/timeout"])
async def test_ranked_session_rejects_public_terminal_action_during_ai_turn(api_app, client, path):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        session.katrain._state["player_to_move"] = "W"
        response = await ac.post(
            path,
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 403
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderPendingGame).count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("player_to_move", ["B", "W"])
async def test_ranked_owner_resign_always_records_user_loss(api_app, client, player_to_move):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        session.katrain._state["player_to_move"] = player_to_move
        response = await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 200
    assert session.katrain.game.current_node.end_state == "W+R"
    assert session.katrain.get_state()["end_result"] == "W+R"
    with api_app.state._test_session_factory() as db:
        ledger = db.query(models_db.AiLadderGameLedger).one()
        assert ledger.result == "loss"
        assert db.query(models_db.AiLadderPendingGame).count() == 0


@pytest.mark.asyncio
async def test_ranked_resign_supports_real_game_read_only_end_result(api_app, client):
    class ReadOnlyEndResultGame:
        def __init__(self):
            self.current_node = SimpleNamespace(end_state=None, player="B", score=3.5)

        @property
        def end_result(self):
            return self.current_node.end_state

    async with client as ac:
        started = await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        session.katrain.game = ReadOnlyEndResultGame()
        response = await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 200
    assert session.katrain.game.end_result == "W+R"
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).one().result == "loss"


@pytest.mark.asyncio
async def test_repeated_ranked_resign_is_rejected_without_changing_authoritative_result(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session_id = started.json()["session_id"]
        first = await ac.post("/api/resign", headers=api_app.state._test_headers, json={"session_id": session_id})
        session = api_app.state._test_created_sessions[0]
        sgf_before = session.katrain.get_sgf()
        second = await ac.post("/api/resign", headers=api_app.state._test_headers, json={"session_id": session_id})
        sgf_after = session.katrain.get_sgf()

    assert first.status_code == 200
    assert second.status_code == 409
    assert sgf_after == sgf_before
    assert session.katrain.game.current_node.end_state == "W+R"
    with api_app.state._test_session_factory() as db:
        ledger = db.query(models_db.AiLadderGameLedger).all()
        assert len(ledger) == 1
        assert ledger[0].result == "loss"


@pytest.mark.asyncio
async def test_ranked_non_owner_cannot_resign(api_app, client):
    with api_app.state._test_session_factory() as db:
        db.add(models_db.User(username="resign-other", hashed_password="x", rank="20k"))
        db.commit()
    other_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'resign-other'})}"}
    async with client as ac:
        started = await start_ranked(api_app, ac)
        response = await ac.post(
            "/api/resign", headers=other_headers, json={"session_id": started.json()["session_id"]}
        )

    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("forbidden", ["rung", "result", "config", "certification_status", "availability"])
async def test_start_rejects_client_authored_strength_or_result(api_app, client, forbidden):
    async with client as ac:
        response = await start_ranked(api_app, ac, **{forbidden: "forged"})
    assert response.status_code == 422
    assert api_app.state._test_created_sessions == []


@pytest.mark.asyncio
@pytest.mark.parametrize("catalog", [fixture_catalog(unavailable_rung=16), fixture_catalog(provisional_rung=16)])
async def test_start_fails_closed_when_exact_server_selected_level_is_ineligible(api_app, client, monkeypatch, catalog):
    from katrain.core import ladder

    monkeypatch.setattr(ladder, "LADDER_LEVELS", catalog)
    async with client as ac:
        response = await start_ranked(api_app, ac)
    assert response.status_code == 409
    assert api_app.state._test_created_sessions == []


@pytest.mark.asyncio
@pytest.mark.parametrize("catalog", [fixture_catalog(unavailable_rung=16), fixture_catalog(provisional_rung=16)])
async def test_provisional_switch_seats_an_uncertified_rung_without_relabelling_it(
    api_app, client, monkeypatch, catalog
):
    """The switch changes what the SERVER will do, never what the rung IS.

    Without it the same catalog is a 409 (the test above). With it the game starts, and
    the frozen opponent record still says provisional/unavailable -- so the ledger row
    for this game names an unmeasured rung instead of quietly claiming a certified one.
    """
    from katrain.core import ladder

    monkeypatch.setattr(ladder, "LADDER_LEVELS", catalog)
    monkeypatch.setenv(ladder.LADDER_ALLOW_PROVISIONAL_ENV, "1")
    async with client as ac:
        status = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
        response = await start_ranked(api_app, ac)

    assert response.status_code == 201
    assert status.json()["provisional_play_allowed"] is True
    # The API keeps reporting the rung's real state next to the started game.
    opponent = response.json()["opponent"]
    assert (opponent["certification_status"], opponent["availability"]) == (
        catalog[15].certification_status,
        catalog[15].availability,
    )
    with api_app.state._test_session_factory() as db:
        pending = db.query(models_db.AiLadderPendingGame).one()
    assert pending.opponent_certification_status == catalog[15].certification_status
    assert pending.opponent_availability == catalog[15].availability


@pytest.mark.asyncio
async def test_status_says_this_node_will_not_seat_uncertified_rungs_by_default(api_app, client):
    async with client as ac:
        response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
    assert response.json()["provisional_play_allowed"] is False


@pytest.mark.asyncio
async def test_a_rung_with_no_recipe_is_refused_even_with_the_provisional_switch_on(api_app, client, monkeypatch):
    """The switch forgives "not measured yet"; it cannot forgive "no recipe exists"."""
    from katrain.core import ladder

    catalog = list(fixture_catalog(provisional_rung=16))
    catalog[15] = SimpleNamespace(**{**catalog[15].__dict__, "recipe": None})
    monkeypatch.setattr(ladder, "LADDER_LEVELS", tuple(catalog))
    monkeypatch.setenv(ladder.LADDER_ALLOW_PROVISIONAL_ENV, "1")
    async with client as ac:
        response = await start_ranked(api_app, ac)
    assert response.status_code == 409
    assert api_app.state._test_created_sessions == []


@pytest.mark.asyncio
async def test_generic_user_games_endpoint_rejects_ranked_ai_forgery(api_app, client):
    async with client as ac:
        response = await ac.post(
            "/api/v1/user-games/",
            headers=api_app.state._test_headers,
            json={
                "id": "forged-ranked",
                "sgf_content": "(;FF[4]SZ[19])",
                "source": "play_ai",
                "game_type": "ai_ladder_ranked",
                "result": "B+R",
            },
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_generic_user_games_cannot_claim_pending_server_game_id(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        game_id = started.json()["game_id"]
        response = await ac.post(
            "/api/v1/user-games/",
            headers=api_app.state._test_headers,
            json={
                "id": game_id,
                "sgf_content": "(;FF[4]SZ[19])",
                "source": "import",
                "game_type": "free",
                "result": "B+R",
            },
        )

    assert response.status_code == 409
    with pytest.raises(ValueError, match="reserved"):
        api_app.state.user_game_repo.create(
            user_id=api_app.state._test_user_id,
            game_id=game_id,
            sgf_content="(;FF[4]SZ[19])",
            source="import",
            game_type="free",
            result="B+R",
        )
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_field", ["game_type", "source", "owner", "sgf_hash"])
async def test_recovery_rejects_non_authoritative_user_game_using_pending_id(api_app, client, caplog, invalid_field):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        game_id = started.json()["game_id"]
        with api_app.state._test_session_factory() as db:
            owner_id = api_app.state._test_user_id
            if invalid_field == "owner":
                other = models_db.User(username="recovery-attacker", hashed_password="x", rank="20k")
                db.add(other)
                db.flush()
                owner_id = other.id
            db.add(
                models_db.UserGame(
                    id=game_id,
                    user_id=owner_id,
                    sgf_content="(;FF[4]SZ[19])",
                    sgf_hash=(
                        "forged"
                        if invalid_field == "sgf_hash"
                        else hashlib.sha256("(;FF[4]SZ[19])".encode()).hexdigest()
                    ),
                    source="import" if invalid_field == "source" else "play_ai",
                    result="B+R",
                    board_size=19,
                    rules="chinese",
                    komi=7.5,
                    move_count=0,
                    category="game",
                    game_type="free" if invalid_field == "game_type" else "ai_ladder_ranked",
                )
            )
            db.commit()
        api_app.state.session_manager._sessions.clear()
        status_response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    # The cloud reservation is authoritative across restarts. Status must not
    # inspect an unrelated/incomplete local row and clear or settle that occupancy.
    assert status_response.json()["pending_settlement"] is False
    assert status_response.json()["blocking_game"]["game_id"] == game_id
    assert status_response.json()["blocking_game"]["state"] == "active"
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0
        assert db.query(models_db.AiLadderPendingGame).count() == 1


@pytest.mark.asyncio
async def test_ranked_user_game_cannot_be_updated_or_deleted_through_generic_crud(api_app, client):
    game_id = "protected-ranked-game"
    original_sgf = "(;FF[4]SZ[19];B[pd])"
    api_app.state.user_game_repo.create_ai_ladder_ranked(
        user_id=api_app.state._test_user_id,
        game_id=game_id,
        sgf_content=original_sgf,
        source="play_ai",
        result="B+R",
    )

    async with client as ac:
        updated = await ac.put(
            f"/api/v1/user-games/{game_id}",
            headers=api_app.state._test_headers,
            json={"sgf_content": "(;FF[4]SZ[19];W[dd])", "result": "W+R"},
        )
        deleted = await ac.delete(f"/api/v1/user-games/{game_id}", headers=api_app.state._test_headers)

    assert updated.status_code == 403
    assert deleted.status_code == 403
    with pytest.raises(ValueError, match="protected"):
        api_app.state.user_game_repo.update(game_id, api_app.state._test_user_id, result="W+R")
    with pytest.raises(ValueError, match="protected"):
        api_app.state.user_game_repo.delete(game_id, api_app.state._test_user_id)
    saved = api_app.state.user_game_repo.get(game_id, api_app.state._test_user_id)
    assert saved["sgf_content"] == original_sgf
    assert saved["result"] == "B+R"


def test_authoritative_ranked_save_uses_game_id_not_sgf_hash_and_checks_owner(api_app):
    repo = api_app.state.user_game_repo
    common = {
        "sgf_content": "(;FF[4]SZ[19];B[pd])",
        "source": "play_ai",
        "result": "B+R",
    }
    repo.create_ai_ladder_ranked(user_id=api_app.state._test_user_id, game_id="ranked-save-1", **common)
    repo.create_ai_ladder_ranked(user_id=api_app.state._test_user_id, game_id="ranked-save-2", **common)

    with api_app.state._test_session_factory() as db:
        other = models_db.User(username="other-owner", hashed_password="x", rank="20k")
        db.add(other)
        db.commit()
        other_id = other.id
        assert db.query(models_db.UserGame).count() == 2

    with pytest.raises(ValueError, match="another user"):
        repo.create_ai_ladder_ranked(user_id=other_id, game_id="ranked-save-1", **common)

    for changed in (
        {"sgf_content": "(;FF[4]SZ[19];W[dd])"},
        {"result": "W+R"},
        {"board_size": 13},
        {"rules": "japanese"},
        {"komi": 6.5},
        {"move_count": 99},
        {"player_black": "forged"},
    ):
        with pytest.raises(ValueError, match="immutable"):
            repo.create_ai_ladder_ranked(
                user_id=api_app.state._test_user_id,
                game_id="ranked-save-1",
                **{**common, **changed},
            )


@pytest.mark.asyncio
async def test_ranked_natural_result_saves_once_then_settles_once(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        response = await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": session.session_id},
        )
        assert response.status_code == 200
        await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": session.session_id},
        )

    game_id = started.json()["game_id"]
    with api_app.state._test_session_factory() as db:
        games = db.query(models_db.UserGame).all()
        ledger = db.query(models_db.AiLadderGameLedger).all()
        profile = db.get(models_db.AiLadderProfile, api_app.state._test_user_id)
        assert len(games) == 1
        assert games[0].id == game_id
        assert games[0].source == "play_ai"
        assert games[0].game_type == "ai_ladder_ranked"
        assert len(ledger) == 1
        assert ledger[0].game_id == game_id
        assert ledger[0].counted is True
        assert profile.placement_completed == 1
    assert session._recorded is True
    assert session.ai_ladder_settlement_pending is False


@pytest.mark.asyncio
async def test_concurrent_ranked_terminal_callbacks_are_serialized(api_app, client):
    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"
        record = __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN
        user = SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user")
        await asyncio.gather(record(session, api_app, user, "B+R"), record(session, api_app, user, "B+R"))

    assert isinstance(session.record_game_lock, asyncio.Lock)
    assert session._recorded is True
    assert session.ai_ladder_settlement_pending is False
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 1
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        assert db.query(models_db.AiLadderPendingGame).count() == 0


@pytest.mark.asyncio
async def test_snapshot_runtime_identity_tampering_is_rejected_without_saving(api_app, client):
    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        session.ai_ladder_runtime_identity = "forged"
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"
        await __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN(
            session, api_app, SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user"), "B+R"
        )

    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
    assert session.ai_ladder_settlement_pending is True
    assert session._recorded is False


@pytest.mark.asyncio
async def test_ranked_settlement_rejects_player_seat_tampering(api_app, client):
    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        session.katrain.players_info["W"].player_subtype = "ai:default"
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"
        await __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN(
            session, api_app, SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user"), "B+R"
        )

    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderPendingGame).count() == 1
    assert session.ai_ladder_settlement_pending is True
    assert session._recorded is False


@pytest.mark.asyncio
async def test_frozen_execution_recipe_tampering_is_rejected_without_saving(api_app, client):
    from dataclasses import replace

    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        session.katrain.frozen_ladder_recipe = replace(session.katrain.frozen_ladder_recipe, max_visits=999)
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"
        await __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN(
            session, api_app, SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user"), "B+R"
        )

    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
    assert session.ai_ladder_settlement_pending is True


@pytest.mark.asyncio
async def test_catalog_change_does_not_change_frozen_runtime_or_block_settlement(api_app, client):
    from katrain.core import ladder

    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        ladder.LADDER_LEVELS[15].recipe.max_visits = 999
        assert session.katrain.frozen_ladder_recipe.max_visits == 16
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"
        await __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN(
            session, api_app, SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user"), "B+R"
        )

    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 1
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        assert db.get(models_db.AiLadderProfile, api_app.state._test_user_id).placement_completed == 1
    assert session.ai_ladder_settlement_pending is False
    assert session._recorded is True


@pytest.mark.asyncio
async def test_ordinary_ai_and_pvp_sessions_never_enter_ranked_ledger(api_app):
    record = __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN
    user = SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user")
    for game_type in ("free", "rated", "pvp_local"):
        session = api_app.state.session_manager.create_session()
        session.user_id = user.id
        session.game_type = game_type
        session.katrain.game_type = game_type
        await record(session, api_app, user, "B+R")

    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0


@pytest.mark.asyncio
async def test_atomic_settlement_failure_keeps_reservation_and_retries_same_session(api_app, client, monkeypatch):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        record = __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN
        user = SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user")
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"

        original_settle = api_app.state.ai_ladder_repo.finalize_reserved_game

        def fail_once(**kwargs):
            raise RuntimeError("fixture settlement failure")

        monkeypatch.setattr(api_app.state.ai_ladder_repo, "finalize_reserved_game", fail_once)
        await record(session, api_app, user, "B+R")

        pending = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
        assert pending.json()["pending_settlement"] is False
        assert pending.json()["blocking_game"]["state"] == "active"
        assert session._recorded is False
        blocked_start = await start_ranked(api_app, ac)
        assert blocked_start.status_code == 409
        assert len(api_app.state._test_created_sessions) == 1

        # The failed atomic transaction saved nothing. The same live session retries
        # its complete record after the transient failure clears.
        monkeypatch.setattr(api_app.state.ai_ladder_repo, "finalize_reserved_game", original_settle)
        await record(session, api_app, user, "B+R")
        recovered = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
        assert recovered.json()["pending_settlement"] is False
        assert recovered.json()["blocking_game"] is None

    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 1
        assert db.query(models_db.UserGame).one().id == started.json()["game_id"]
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        assert db.get(models_db.AiLadderProfile, user.id).placement_completed == 1
        assert db.execute(text("SELECT COUNT(*) FROM ai_ladder_pending_games")).scalar_one() == 0


@pytest.mark.asyncio
async def test_active_cloud_reservation_is_not_abandoned_after_restart(api_app, client):
    async with client as ac:
        await start_ranked(api_app, ac)
        api_app.state.session_manager._sessions.clear()
        status_response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
        restarted = await start_ranked(api_app, ac)

    assert status_response.json()["pending_settlement"] is False
    assert status_response.json()["blocking_game"]["state"] == "active"
    assert restarted.status_code == 409
    with api_app.state._test_session_factory() as db:
        assert db.execute(text("SELECT COUNT(*) FROM ai_ladder_pending_games")).scalar_one() == 1


@pytest.mark.asyncio
async def test_pending_is_not_abandoned_while_its_session_is_still_being_configured(api_app, client):
    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        session.user_id = None
        status_response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert status_response.json()["pending_settlement"] is False
    assert status_response.json()["blocking_game"]["state"] == "active"
    with api_app.state._test_session_factory() as db:
        assert db.execute(text("SELECT COUNT(*) FROM ai_ladder_pending_games")).scalar_one() == 1


@pytest.mark.asyncio
async def test_conflicting_retry_after_atomic_failure_leaves_no_partial_result(api_app, client, monkeypatch):
    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        record = __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN
        user = SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user")
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"
        original_settle = api_app.state.ai_ladder_repo.finalize_reserved_game
        monkeypatch.setattr(
            api_app.state.ai_ladder_repo,
            "finalize_reserved_game",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("first settle fails")),
        )
        await record(session, api_app, user, "B+R")

        session.katrain.game.end_result = "W+R"
        session.katrain._state["end_result"] = "W+R"
        session.katrain.get_sgf = lambda: "(;FF[4]SZ[19];W[dd])"
        monkeypatch.setattr(api_app.state.ai_ladder_repo, "finalize_reserved_game", original_settle)
        await record(session, api_app, user, "W+R")

    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0
        pending = db.execute(text("SELECT game_saved, saved_result FROM ai_ladder_pending_games")).one()
        assert pending[0] in (False, 0)
        assert pending[1] is None
        assert db.query(models_db.AiLadderActiveGame).count() == 1


@pytest.mark.asyncio
async def test_board_or_remote_dispatch_mode_refuses_local_authoritative_start(api_app, client):
    api_app.state.ai_ladder_authoritative = False
    api_app.state.repository_dispatcher = object()
    async with client as ac:
        status = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
        started = await start_ranked(api_app, ac)
    assert status.status_code == 503
    assert started.status_code == 503
    assert api_app.state._test_created_sessions == []


def settlement_payload(**overrides):
    return {
        "game_id": "board-game-1",
        "user_color": "B",
        "result": "loss",
        "game_type": "ai_ladder_ranked",
        "opponent": {
            "rung": 16,
            "rank_name": "fixture-16",
            "config_snapshot": {"config_digest": "d" * 16, "config_version": "v1"},
            "certification_status": "certified",
            "availability": "available",
            "route": "server",
        },
        "engine_stalled": False,
        "device_id": "rk3562-p04-001",
        **overrides,
    }


@pytest.mark.asyncio
async def test_a_board_settlement_moves_the_cloud_profile(api_app, client):
    """The board played the game; the cloud is where the account's rank lives."""
    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/settlements",
            headers=api_app.state._test_headers,
            json=settlement_payload(),
        )

    assert response.status_code == 200
    body = response.json()
    assert (body["counted"], body["replayed"], body["reason"]) == (True, False, None)
    assert body["profile"]["placement_completed"] == 1
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).one().game_id == "board-game-1"


@pytest.mark.asyncio
async def test_resubmitting_the_same_game_replays_instead_of_counting_it_twice(api_app, client):
    """A board that retries an uncertain POST must not double-move the rank."""
    async with client as ac:
        first = await ac.post(
            "/api/v1/ai-ladder/settlements", headers=api_app.state._test_headers, json=settlement_payload()
        )
        second = await ac.post(
            "/api/v1/ai-ladder/settlements", headers=api_app.state._test_headers, json=settlement_payload()
        )

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json()["replayed"] is True
    assert first.json()["profile"] == second.json()["profile"]
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        assert db.query(models_db.AiLadderProfile).one().placement_completed == 1


@pytest.mark.asyncio
async def test_a_settlement_submission_is_refused_by_a_node_that_keeps_no_scores(api_app, client):
    api_app.state.ai_ladder_authoritative = False
    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/settlements", headers=api_app.state._test_headers, json=settlement_payload()
        )
    assert response.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"user_color": "X"},
        {"result": "draw"},
        {"game_id": ""},
        {
            "opponent": {
                "rung": 99,
                "rank_name": "x",
                "config_snapshot": {},
                "certification_status": "certified",
                "availability": "available",
                "route": "server",
            }
        },
        {"extra_field": "nope"},
    ],
)
async def test_a_settlement_submission_is_validated_not_trusted(api_app, client, overrides):
    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/settlements",
            headers=api_app.state._test_headers,
            json=settlement_payload(**overrides),
        )
    assert response.status_code == 422
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 0


@pytest.mark.asyncio
async def test_a_settlement_submission_needs_authentication(client):
    async with client as ac:
        response = await ac.post("/api/v1/ai-ladder/settlements", json=settlement_payload())
    assert response.status_code == 401


def reservation_payload(**overrides):
    return {
        "game_id": "0123456789abcdef0123456789abcdef",
        "reservation_key": "fixture-reservation-key",
        "color": "black",
        "time_enabled": False,
        "main_time": 0,
        "byo_length": 30,
        "byo_periods": 3,
        **overrides,
    }


@pytest.mark.asyncio
async def test_cloud_reservation_is_account_unique_and_status_hides_origin_secrets(api_app, client):
    origin = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "  board-a  "}
    other = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "board-b"}
    async with client as ac:
        reserved = await ac.post("/api/v1/ai-ladder/games/reserve", headers=origin, json=reservation_payload())
        replay = await ac.post("/api/v1/ai-ladder/games/reserve", headers=origin, json=reservation_payload())
        blocked = await ac.post(
            "/api/v1/ai-ladder/games/reserve",
            headers=other,
            json=reservation_payload(game_id="fedcba9876543210fedcba9876543210"),
        )
        owner_status = await ac.get("/api/v1/ai-ladder/status", headers=origin)
        other_status = await ac.get("/api/v1/ai-ladder/status", headers=other)

    assert reserved.status_code == 201
    assert set(reserved.json()) == {"game_id", "reservation_key", "blocking_game", "opponent", "execution_identity"}
    assert reserved.json()["reservation_key"]
    assert reserved.json()["opponent"]["rank_name"] == "fixture-16"
    assert reserved.json()["execution_identity"] == reserved.json()["opponent"]["config_snapshot"]["recipe_identity"]
    assert replay.status_code == 201
    assert replay.json()["reservation_key"] == reservation_payload()["reservation_key"]
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["blocking_game"]["ownership"] == "other_device"
    assert owner_status.json()["blocking_game"] == {
        "game_id": reservation_payload()["game_id"],
        "state": "active",
        "ownership": "current_device",
        "user_color": "B",
        "opponent_rank_name": "fixture-16",
    }
    assert other_status.json()["blocking_game"]["ownership"] == "other_device"
    assert "session_id" not in other_status.json()["blocking_game"]
    assert "reservation_key" not in str(other_status.json())
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).one().origin_device_id == "board-a"


@pytest.mark.asyncio
async def test_origin_can_activate_mark_pending_and_cancel_only_unactivated(api_app, client):
    headers = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "board-a"}
    async with client as ac:
        reserved = await ac.post("/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload())
        key = reserved.json()["reservation_key"]
        activated = await ac.post(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/activate",
            headers={**api_app.state._test_headers, "X-StellaBox-Device-ID": "board-replaced"},
            json={"reservation_key": key, "session_id": "local-session"},
        )
        pending = await ac.post(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/pending-settlement",
            headers=api_app.state._test_headers,
            json={"reservation_key": key},
        )
        cancel = await ac.request(
            "DELETE",
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/reservation",
            headers=headers,
            json={"reservation_key": key},
        )
        game_status = await ac.get(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/status", headers=headers
        )

    assert activated.status_code == 200
    assert activated.json() == {"state": "active", "game_id": reservation_payload()["game_id"]}
    assert pending.json() == {"state": "pending_settlement", "game_id": reservation_payload()["game_id"]}
    assert cancel.status_code == 409
    assert game_status.json() == {"state": "pending_settlement", "game_id": reservation_payload()["game_id"]}


@pytest.mark.asyncio
async def test_any_account_device_can_end_immediately_and_replay_same_receipt(api_app, client):
    origin = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "board-a"}
    other = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "board-b"}
    async with client as ac:
        await ac.post("/api/v1/ai-ladder/games/reserve", headers=origin, json=reservation_payload())
        first = await ac.post(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/end",
            headers=other,
            json={"reason": "user_resigned"},
        )
        second = await ac.post(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/end",
            headers=origin,
            json={"reason": "user_resigned"},
        )
        status_response = await ac.get(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/status", headers=other
        )

    expected = {
        "state": "settled",
        "game_id": reservation_payload()["game_id"],
        "receipt": {"counted": True, "reason": None},
    }
    assert first.status_code == 200
    assert first.json() == expected
    assert second.json() == expected
    assert status_response.json() == expected
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 1
        game = db.query(models_db.UserGame).one()
        ledger = db.query(models_db.AiLadderGameLedger).one()
        assert (game.source, game.game_type, game.origin_device_id) == ("play_ai", "ai_ladder_ranked", "board-a")
        assert (ledger.origin_device_id, ledger.deciding_device_id, ledger.terminal_source) == (
            "board-a",
            "board-b",
            "remote_resign",
        )
        assert db.query(models_db.AiLadderProfile).one().placement_completed == 1


@pytest.mark.asyncio
async def test_game_lifecycle_is_private_and_requests_are_strict(api_app, client):
    with api_app.state._test_session_factory() as db:
        other_user = models_db.User(username="other-lifecycle-user", hashed_password="x", rank="20k")
        db.add(other_user)
        db.commit()
    other_auth = {
        "Authorization": f"Bearer {create_access_token({'sub': 'other-lifecycle-user'})}",
        "X-StellaBox-Device-ID": "x",
    }
    headers = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "board-a"}
    async with client as ac:
        unauthenticated = await ac.post("/api/v1/ai-ladder/games/reserve", json=reservation_payload())
        no_header_game_id = "11111111111111111111111111111111"
        missing_device = await ac.post(
            "/api/v1/ai-ladder/games/reserve",
            headers=api_app.state._test_headers,
            json=reservation_payload(game_id=no_header_game_id),
        )
        await ac.post(
            f"/api/v1/ai-ladder/games/{no_header_game_id}/end",
            headers=api_app.state._test_headers,
            json={"reason": "user_resigned"},
        )
        extra = await ac.post("/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload(extra=True))
        reserved = await ac.post("/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload())
        private = await ac.get(f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/status", headers=other_auth)
        bad_end = await ac.post(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/end",
            headers=headers,
            json={"reason": "abandon", "extra": True},
        )

    assert unauthenticated.status_code == 401
    assert missing_device.status_code == 201
    assert extra.status_code == 422
    assert reserved.status_code == 201
    assert private.status_code == 404
    assert bad_end.status_code == 422


def lifecycle_game_record(*, result="B+R"):
    return {
        "sgf_content": f"(;GM[1]FF[4]SZ[19]RU[chinese]KM[7.5]PB[ladder-user]PW[fixture-16]RE[{result}])",
        "result": result,
        "board_size": 19,
        "rules": "chinese",
        "komi": 7.5,
        "move_count": 0,
        "player_black": "ladder-user",
        "player_white": "fixture-16",
        "source": "play_ai",
        "category": "game",
        "game_type": "ai_ladder_ranked",
    }


@pytest.mark.asyncio
async def test_origin_settlement_finalizes_reserved_game_and_end_replays_first_terminal_decision(api_app, client):
    headers = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "board-a"}
    async with client as ac:
        reserved = await ac.post("/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload())
        key = reserved.json()["reservation_key"]
        await ac.post(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/activate",
            headers=headers,
            json={"reservation_key": key, "session_id": "board-session"},
        )
        settled = await ac.post(
            "/api/v1/ai-ladder/settlements",
            headers={**api_app.state._test_headers, "X-StellaBox-Device-ID": "replacement-board"},
            json=settlement_payload(
                game_id=reservation_payload()["game_id"],
                result="win",
                reservation_key=key,
                game_record=lifecycle_game_record(),
            ),
        )
        ended = await ac.post(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/end",
            headers={**api_app.state._test_headers, "X-StellaBox-Device-ID": "board-b"},
            json={"reason": "user_resigned"},
        )

    assert settled.status_code == 200
    assert settled.json()["lifecycle"] == {
        "state": "settled",
        "game_id": reservation_payload()["game_id"],
        "receipt": {"counted": True, "reason": None},
    }
    assert ended.json() == settled.json()["lifecycle"]
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 1
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        ledger = db.query(models_db.AiLadderGameLedger).one()
        assert (ledger.result, ledger.terminal_source, ledger.deciding_device_id) == (
            "win",
            "played_result",
            "replacement-board",
        )
        assert db.query(models_db.AiLadderProfile).one().placement_completed == 1


@pytest.mark.asyncio
async def test_direct_authoritative_start_reserves_and_activates_before_returning(api_app, client):
    headers = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "galaxy-a"}
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=headers,
            json={"color": "black", "time_enabled": False},
        )
        status_response = await ac.get("/api/v1/ai-ladder/status", headers=headers)

    assert started.status_code == 201
    assert status_response.json()["blocking_game"] == {
        "game_id": started.json()["game_id"],
        "state": "active",
        "ownership": "current_device",
        "session_id": started.json()["session_id"],
        "user_color": "B",
        "opponent_rank_name": "fixture-16",
    }
    with api_app.state._test_session_factory() as db:
        active = db.query(models_db.AiLadderActiveGame).one()
        assert (active.state, active.origin_device_id, active.origin_session_id) == (
            "active",
            "galaxy-a",
            started.json()["session_id"],
        )


@pytest.mark.asyncio
async def test_other_account_cannot_legacy_settle_an_active_global_game_id(api_app, client):
    with api_app.state._test_session_factory() as db:
        db.add(models_db.User(username="game-id-attacker", hashed_password="x", rank="20k"))
        db.commit()
    attacker = {
        "Authorization": f"Bearer {create_access_token({'sub': 'game-id-attacker'})}",
        "X-StellaBox-Device-ID": "attacker-board",
    }
    owner = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "owner-board"}
    async with client as ac:
        await ac.post("/api/v1/ai-ladder/games/reserve", headers=owner, json=reservation_payload())
        response = await ac.post(
            "/api/v1/ai-ladder/settlements",
            headers=attacker,
            json=settlement_payload(game_id=reservation_payload()["game_id"]),
        )

    assert response.status_code == 404
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).count() == 1
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0


@pytest.mark.asyncio
async def test_remote_end_first_makes_late_direct_record_a_noop(api_app, client):
    headers = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "galaxy-a"}
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start", headers=headers, json={"color": "black", "time_enabled": False}
        )
        ended = await ac.post(
            f"/api/v1/ai-ladder/games/{started.json()['game_id']}/end",
            headers={**api_app.state._test_headers, "X-StellaBox-Device-ID": "galaxy-b"},
            json={"reason": "user_resigned"},
        )
        session = api_app.state._test_created_sessions[0]
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"
        await __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN(
            session, api_app, SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user"), "B+R"
        )

    assert ended.status_code == 200
    assert session._recorded is True
    assert session.ai_ladder_settlement_pending is False
    with api_app.state._test_session_factory() as db:
        game = db.query(models_db.UserGame).one()
        ledger = db.query(models_db.AiLadderGameLedger).one()
        assert game.result == "W+R"
        assert (ledger.result, ledger.terminal_source) == ("loss", "remote_resign")
        assert db.query(models_db.AiLadderPendingGame).count() == 0


@pytest.mark.asyncio
async def test_cross_device_ranked_journey_has_one_receipt_and_one_auditable_write(api_app, client):
    origin = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "galaxy-a"}
    other = {**api_app.state._test_headers, "X-StellaBox-Device-ID": "galaxy-b"}
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=origin,
            json={"color": "black", "time_enabled": False},
        )
        game_id = started.json()["game_id"]
        session = api_app.state._test_created_sessions[0]
        history_before = list(session.katrain._state["history"])
        other_status = await ac.get("/api/v1/ai-ladder/status", headers=other)
        ended = await ac.post(
            f"/api/v1/ai-ladder/games/{game_id}/end",
            headers=other,
            json={"reason": "user_resigned"},
        )
        origin_lifecycle = await ac.get(f"/api/v1/ai-ladder/games/{game_id}/status", headers=origin)
        other_lifecycle = await ac.get(f"/api/v1/ai-ladder/games/{game_id}/status", headers=other)
        moved = await ac.post(
            "/api/move",
            headers=origin,
            json={"session_id": session.session_id, "coords": [3, 3]},
        )

    assert started.status_code == 201
    assert other_status.json()["blocking_game"] == {
        "game_id": game_id,
        "state": "active",
        "ownership": "other_device",
        "user_color": "B",
        "opponent_rank_name": "fixture-16",
        # The origin here never sends a heartbeat, so this is the compatibility branch: the
        # second device may end the game immediately and there is no deadline to count down to.
        # `ended` below is that call succeeding, which is what makes this the regression guard
        # for "the takeover gate must not take the existing escape hatch away".
        "can_force_resign": True,
        "takeover_eligible_at": None,
        "takeover_threshold_seconds": 300,
        "takeover_threshold_version": 1,
        # The game is `active`, so the other exit is closed and says so with a deadline of None:
        # no amount of waiting turns a game in progress into an undelivered result. The screen
        # has to be able to tell the two apart -- one banks a loss, the other banks nothing.
        "can_release_abandoned_settlement": False,
        "abandoned_settlement_eligible_at": None,
        "abandoned_settlement_threshold_seconds": 1800,
        "abandoned_settlement_threshold_version": 1,
    }
    receipt = ended.json()
    assert ended.status_code == 200
    assert receipt == {
        "state": "settled",
        "game_id": game_id,
        "receipt": {"counted": True, "reason": None},
    }
    assert origin_lifecycle.json() == receipt
    assert other_lifecycle.json() == receipt
    assert moved.status_code == 409
    assert session.katrain._state["history"] == history_before
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 1
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        game = db.query(models_db.UserGame).one()
        ledger = db.query(models_db.AiLadderGameLedger).one()
        assert (game.source, game.game_type, game.origin_device_id) == ("play_ai", "ai_ladder_ranked", "galaxy-a")
        assert (ledger.origin_device_id, ledger.deciding_device_id, ledger.terminal_source) == (
            "galaxy-a",
            "galaxy-b",
            "remote_resign",
        )


class RecordingDispatcher:
    """Stand-in for board mode's online/offline repository dispatcher."""

    def __init__(self):
        self.calls = []

    async def user_games_create(self, user_id, data):
        self.calls.append((user_id, data))
        return {"id": data.get("id"), **data}


def _board_remote(api_app):
    from katrain.web.core.ai_ladder_catalog import build_opponent_snapshot

    opponent, identity = build_opponent_snapshot(16)
    remote = SimpleNamespace(
        bound_user_id=str(api_app.state._test_user_id),
        get_ai_ladder_status=AsyncMock(
            return_value={"view_state": "ready", "pending_settlement": False, "blocking_game": None}
        ),
        reserve_ai_ladder_game=AsyncMock(),
        activate_ai_ladder_game=AsyncMock(return_value={"state": "active"}),
        cancel_ai_ladder_reservation=AsyncMock(return_value={"state": "cancelled"}),
        get_ai_ladder_game_status=AsyncMock(),
        end_ai_ladder_game=AsyncMock(),
    )
    reservation = {
        "game_id": "0123456789abcdef0123456789abcdef",
        "reservation_key": "raw-reservation-key",
        "opponent": {
            "rung": opponent.rung,
            "rank_name": opponent.rank_name,
            "config_snapshot": dict(opponent.config_snapshot),
            "certification_status": opponent.certification_status,
            "availability": opponent.availability,
            "route": opponent.route,
        },
        "execution_identity": identity,
    }

    def reserve(data):
        return {**reservation, "game_id": data.get("game_id", reservation["game_id"])}

    remote.reserve_ai_ladder_game.side_effect = reserve
    api_app.state.remote_client = remote
    api_app.state.repository_dispatcher = RecordingDispatcher()
    api_app.state.ai_ladder_authoritative = True
    return remote


@pytest.mark.asyncio
async def test_board_status_uses_cloud_authority_and_only_enriches_its_live_local_session(api_app, client):
    remote = _board_remote(api_app)
    game_id = "0123456789abcdef0123456789abcdef"
    remote.get_ai_ladder_status.return_value = {
        "view_state": "ready",
        "pending_settlement": False,
        "blocking_game": {
            "game_id": game_id,
            "state": "active",
            "ownership": "current_device",
            "user_color": "B",
            "opponent_rank_name": "fixture-16",
        },
    }
    # A local mirror with a live session proves that this board may reveal only its
    # own local session id. The cloud never sends a session id/key back to the UI.
    started = await remote.reserve_ai_ladder_game({})
    from katrain.web.core.ai_ladder_ranked import AiLadderOpponentSnapshot

    opponent = AiLadderOpponentSnapshot(**started["opponent"])
    snapshot = __import__(
        "katrain.web.core.ai_ladder_catalog", fromlist=["AiLadderSessionSnapshot"]
    ).AiLadderSessionSnapshot(
        game_id=game_id,
        session_id="local-live-session",
        user_id=api_app.state._test_user_id,
        user_color="B",
        game_type="ai_ladder_ranked",
        opponent=opponent,
        ai_subtype="ai:ladder",
        execution_identity=started["execution_identity"],
    )
    api_app.state.ai_ladder_repo.create_pending_game(snapshot, reservation_key="never-relay")
    api_app.state.session_manager._sessions["local-live-session"] = SimpleNamespace(
        user_id=api_app.state._test_user_id,
        game_type="ai_ladder_ranked",
        ai_ladder_snapshot=snapshot,
    )

    async with client as ac:
        response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert response.status_code == 200
    assert response.json()["blocking_game"]["session_id"] == "local-live-session"
    assert "reservation_key" not in str(response.json())
    remote.get_ai_ladder_status.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_session", ["wrong_owner", "replaced_snapshot", "reset_game"])
async def test_board_status_rejects_stale_or_mismatched_local_sessions(api_app, client, bad_session):
    remote = _board_remote(api_app)
    game_id = "0123456789abcdef0123456789abcdef"
    remote.get_ai_ladder_status.return_value = {
        "view_state": "ready",
        "blocking_game": {
            "game_id": game_id,
            "state": "active",
            "ownership": "current_device",
            "user_color": "B",
            "opponent_rank_name": "fixture-16",
        },
    }
    reserved = await remote.reserve_ai_ladder_game({})
    from katrain.web.core.ai_ladder_ranked import AiLadderOpponentSnapshot

    opponent = AiLadderOpponentSnapshot(**reserved["opponent"])
    snapshot = __import__(
        "katrain.web.core.ai_ladder_catalog", fromlist=["AiLadderSessionSnapshot"]
    ).AiLadderSessionSnapshot(
        game_id=game_id,
        session_id="local-live-session",
        user_id=api_app.state._test_user_id,
        user_color="B",
        game_type="ai_ladder_ranked",
        opponent=opponent,
        ai_subtype="ai:ladder",
        execution_identity=reserved["execution_identity"],
    )
    api_app.state.ai_ladder_repo.create_pending_game(snapshot, reservation_key="secret")
    session = SimpleNamespace(
        user_id=api_app.state._test_user_id,
        game_type="ai_ladder_ranked",
        ai_ladder_snapshot=snapshot,
    )
    if bad_session == "wrong_owner":
        session.user_id += 1
    elif bad_session == "replaced_snapshot":
        session.ai_ladder_snapshot = SimpleNamespace(
            game_id="fedcba9876543210fedcba9876543210",
            user_id=api_app.state._test_user_id,
            session_id="local-live-session",
        )
    else:
        session.game_type = "free"
    api_app.state.session_manager._sessions["local-live-session"] = session

    async with client as ac:
        response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert response.status_code == 200
    assert "session_id" not in response.json()["blocking_game"]


@pytest.mark.asyncio
async def test_board_status_never_relays_cloud_session_or_reservation_secrets(api_app, client):
    remote = _board_remote(api_app)
    remote.get_ai_ladder_status.return_value = {
        "view_state": "ready",
        "blocking_game": {
            "game_id": "0123456789abcdef0123456789abcdef",
            "state": "active",
            "ownership": "other_device",
            "session_id": "cloud-internal-session",
            "reservation_key": "cloud-secret",
            "user_color": "B",
            "opponent_rank_name": "fixture-16",
        },
    }

    async with client as ac:
        response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert response.status_code == 200
    assert "session_id" not in response.json()["blocking_game"]
    assert "reservation_key" not in response.json()["blocking_game"]


@pytest.mark.asyncio
async def test_board_proxy_rejects_local_jwt_when_cloud_is_bound_to_another_user(api_app, client):
    remote = _board_remote(api_app)
    remote.bound_user_id = str(api_app.state._test_user_id + 1)

    async with client as ac:
        status_response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
        start_response = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        game_response = await ac.get(
            "/api/v1/ai-ladder/games/0123456789abcdef0123456789abcdef/status",
            headers=api_app.state._test_headers,
        )

    assert (status_response.status_code, start_response.status_code, game_response.status_code) == (401, 401, 401)
    remote.get_ai_ladder_status.assert_not_awaited()
    remote.reserve_ai_ladder_game.assert_not_awaited()


@pytest.mark.asyncio
async def test_board_start_reserves_cloud_before_creating_and_activates_after_local_setup(api_app, client):
    remote = _board_remote(api_app)

    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )

    assert response.status_code == 201
    session = api_app.state._test_created_sessions[0]
    reservation_key = remote.reserve_ai_ladder_game.await_args.args[0]["reservation_key"]
    remote.reserve_ai_ladder_game.assert_awaited_once()
    remote.activate_ai_ladder_game.assert_awaited_once_with(
        response.json()["game_id"], reservation_key, session.session_id
    )
    pending = api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id)
    assert pending["reservation_key"] == reservation_key
    assert pending["game_id"] == response.json()["game_id"]


@pytest.mark.asyncio
async def test_board_reserve_timeout_retries_the_same_game_and_client_key(api_app, client):
    import httpx

    remote = _board_remote(api_app)
    original = remote.reserve_ai_ladder_game.side_effect
    attempts = 0

    def reserve_with_timeout(data):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("ambiguous", request=httpx.Request("POST", "https://cloud.invalid"))
        return original(data)

    remote.reserve_ai_ladder_game.side_effect = reserve_with_timeout
    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )

    assert response.status_code == 201
    assert remote.reserve_ai_ladder_game.await_count == 2
    assert (
        remote.reserve_ai_ladder_game.await_args_list[0].args[0]
        == remote.reserve_ai_ladder_game.await_args_list[1].args[0]
    )


@pytest.mark.asyncio
async def test_board_reserve_gateway_502_retries_the_same_game_and_client_key(api_app, client):
    import httpx

    remote = _board_remote(api_app)
    original = remote.reserve_ai_ladder_game.side_effect
    attempts = 0

    def reserve_with_gateway_error(data):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            request = httpx.Request("POST", "https://cloud.invalid/api/v1/ai-ladder/games/reserve")
            response = httpx.Response(502, request=request, text="bad gateway")
            raise httpx.HTTPStatusError("502", request=request, response=response)
        return original(data)

    remote.reserve_ai_ladder_game.side_effect = reserve_with_gateway_error
    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )

    assert response.status_code == 201
    assert remote.reserve_ai_ladder_game.await_count == 2
    assert (
        remote.reserve_ai_ladder_game.await_args_list[0].args[0]
        == remote.reserve_ai_ladder_game.await_args_list[1].args[0]
    )


@pytest.mark.asyncio
async def test_board_activation_two_gateway_failures_preserve_live_session_for_status_reconcile(api_app, client):
    import httpx

    remote = _board_remote(api_app)
    request = httpx.Request("POST", "https://cloud.invalid/api/v1/ai-ladder/games/g/activate")
    gateway = httpx.HTTPStatusError(
        "504", request=request, response=httpx.Response(504, request=request, text="gateway timeout")
    )
    remote.activate_ai_ladder_game.side_effect = [gateway, gateway, {"state": "active"}]
    remote.get_ai_ladder_game_status.side_effect = [gateway]

    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )

        assert started.status_code == 503
        session = api_app.state._test_created_sessions[0]
        pending = api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id)
        assert pending["session_id"] == session.session_id
        assert session.session_id in api_app.state.session_manager._sessions

        remote.get_ai_ladder_status.return_value = {
            "view_state": "ready",
            "blocking_game": {
                "game_id": pending["game_id"],
                "state": "active",
                "ownership": "current_device",
                "user_color": "B",
                "opponent_rank_name": "fixture-16",
            },
        }
        reconciled = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert reconciled.status_code == 200
    assert reconciled.json()["blocking_game"]["session_id"] == session.session_id
    assert remote.activate_ai_ladder_game.await_count == 3


@pytest.mark.asyncio
async def test_board_start_compensates_cloud_reservation_when_local_session_creation_fails(
    api_app, client, monkeypatch
):
    remote = _board_remote(api_app)
    monkeypatch.setattr(
        api_app.state.session_manager,
        "create_session",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no engine")),
    )

    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )

    assert response.status_code == 503
    reserved_game_id = remote.reserve_ai_ladder_game.await_args.args[0]["game_id"]
    reservation_key = remote.reserve_ai_ladder_game.await_args.args[0]["reservation_key"]
    remote.cancel_ai_ladder_reservation.assert_awaited_once_with(reserved_game_id, reservation_key)
    assert api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id) is None


@pytest.mark.asyncio
async def test_board_start_keeps_client_key_when_local_setup_and_cloud_cancel_both_fail(api_app, client, monkeypatch):
    remote = _board_remote(api_app)
    remote.cancel_ai_ladder_reservation.side_effect = RuntimeError("cloud unavailable")
    monkeypatch.setattr(
        api_app.state.session_manager,
        "create_session",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no engine")),
    )

    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )

    assert response.status_code == 503
    pending = api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id)
    assert pending["reservation_key"] == remote.reserve_ai_ladder_game.await_args.args[0]["reservation_key"]
    assert pending["session_id"].startswith("unconfigured-")


@pytest.mark.asyncio
async def test_offline_board_cannot_start_an_official_ranked_game(api_app, client):
    import httpx

    remote = _board_remote(api_app)
    upstream = httpx.Request("POST", "https://cloud.invalid/api/v1/ai-ladder/games/reserve")
    remote.reserve_ai_ladder_game.side_effect = httpx.ConnectError("offline", request=upstream)

    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )

    assert response.status_code == 503
    assert api_app.state._test_created_sessions == []


@pytest.mark.asyncio
async def test_board_end_and_game_status_are_cloud_proxies(api_app, client):
    remote = _board_remote(api_app)
    game_id = "0123456789abcdef0123456789abcdef"
    remote.get_ai_ladder_game_status.return_value = {"state": "pending_settlement", "game_id": game_id}
    remote.end_ai_ladder_game.return_value = {
        "state": "settled",
        "game_id": game_id,
        "receipt": {"counted": True, "reason": None},
    }

    async with client as ac:
        lifecycle = await ac.get(f"/api/v1/ai-ladder/games/{game_id}/status", headers=api_app.state._test_headers)
        ended = await ac.post(
            f"/api/v1/ai-ladder/games/{game_id}/end",
            headers=api_app.state._test_headers,
            json={"reason": "user_resigned"},
        )

    assert lifecycle.json() == remote.get_ai_ladder_game_status.return_value
    assert ended.json() == remote.end_ai_ladder_game.return_value


@pytest.mark.asyncio
async def test_board_game_status_proxy_stops_the_matching_local_session_after_remote_end(api_app, client):
    remote = _board_remote(api_app)
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        game_id = started.json()["game_id"]
        session = api_app.state._test_created_sessions[0]
        session.katrain.engine = SimpleNamespace(stop_pondering=MagicMock(), terminate_queries=MagicMock())
        session.katrain.pondering = True
        remote.get_ai_ladder_game_status.return_value = {
            "state": "pending_settlement",
            "game_id": game_id,
        }
        response = await ac.get(
            f"/api/v1/ai-ladder/games/{game_id}/status",
            headers=api_app.state._test_headers,
        )

    assert response.status_code == 200
    assert session.ai_ladder_remote_ended is True
    assert session.katrain.ai_ladder_remote_ended is True
    session.katrain.engine.stop_pondering.assert_called_once()
    session.katrain.engine.terminate_queries.assert_called_once_with(only_for_node=session.katrain.game.current_node)
    assert session.katrain.pondering is False


@pytest.mark.asyncio
async def test_board_game_status_proxy_rejects_mismatched_remote_game_without_marking_session(api_app, client):
    remote = _board_remote(api_app)
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        session = api_app.state._test_created_sessions[0]
        session.katrain.engine = SimpleNamespace(stop_pondering=MagicMock())
        remote.get_ai_ladder_game_status.return_value = {
            "state": "settled",
            "game_id": "different-game",
            "receipt": {"counted": True, "reason": None},
        }
        response = await ac.get(
            f"/api/v1/ai-ladder/games/{started.json()['game_id']}/status",
            headers=api_app.state._test_headers,
        )

    assert response.status_code == 502
    assert not getattr(session, "ai_ladder_remote_ended", False)
    session.katrain.engine.stop_pondering.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/api/resign", "/api/count/request", "/api/timeout"],
)
async def test_board_remote_terminal_blocks_ranked_terminal_actions_before_mutation(api_app, client, path):
    remote = _board_remote(api_app)
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        game_id = started.json()["game_id"]
        session = api_app.state._test_created_sessions[0]
        state_before = dict(session.katrain._state)
        end_before = session.katrain.game.current_node.end_state
        remote.get_ai_ladder_game_status.return_value = {
            "state": "pending_settlement",
            "game_id": game_id,
        }
        response = await ac.post(
            path,
            headers=api_app.state._test_headers,
            json={"session_id": session.session_id},
        )

    assert response.status_code == 409
    assert session.katrain._state == state_before
    assert session.katrain.game.current_node.end_state == end_before


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["pending_settlement", "settled"])
async def test_board_remote_terminal_blocks_move_and_save_before_local_mutation(api_app, client, state):
    remote = _board_remote(api_app)
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        game_id = started.json()["game_id"]
        lifecycle = {"state": state, "game_id": game_id}
        if state == "settled":
            lifecycle["receipt"] = {"counted": True, "reason": None}
        remote.get_ai_ladder_game_status.return_value = lifecycle
        session = api_app.state._test_created_sessions[0]
        session.katrain.stop_pondering = MagicMock()
        history_before = list(session.katrain._state["history"])
        moved = await ac.post(
            "/api/move",
            headers=api_app.state._test_headers,
            json={"session_id": session.session_id, "coords": [3, 3]},
        )
        session._recorded = True
        session.ai_ladder_settlement_pending = False
        saved = await ac.get(
            "/api/sgf/save",
            headers=api_app.state._test_headers,
            params={"session_id": session.session_id},
        )

    assert (moved.status_code, saved.status_code) == (409, 409)
    assert session.katrain._state["history"] == history_before
    assert session.ai_ladder_remote_ended is True
    session.katrain.stop_pondering.assert_called()


@pytest.mark.asyncio
async def test_board_remote_settled_blocks_direct_save_even_when_local_game_already_ended(api_app, client):
    remote = _board_remote(api_app)
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        game_id = started.json()["game_id"]
        session = api_app.state._test_created_sessions[0]
        session.katrain.stop_pondering = MagicMock()
        session.katrain._state["end_result"] = "W+R"
        session._recorded = True
        session.ai_ladder_settlement_pending = False
        remote.get_ai_ladder_game_status.return_value = {
            "state": "settled",
            "game_id": game_id,
            "receipt": {"counted": True, "reason": None},
        }

        saved = await ac.get(
            "/api/sgf/save",
            headers=api_app.state._test_headers,
            params={"session_id": session.session_id},
        )

    assert saved.status_code == 409
    remote.get_ai_ladder_game_status.assert_awaited_once_with(game_id)
    session.katrain.stop_pondering.assert_called_once()


@pytest.mark.asyncio
async def test_board_remote_error_blocks_direct_ranked_save_with_503(api_app, client):
    remote = _board_remote(api_app)
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        session = api_app.state._test_created_sessions[0]
        session.katrain._state["end_result"] = "W+R"
        session._recorded = True
        session.ai_ladder_settlement_pending = False
        remote.get_ai_ladder_game_status.side_effect = RuntimeError("cloud offline")

        saved = await ac.get(
            "/api/sgf/save",
            headers=api_app.state._test_headers,
            params={"session_id": session.session_id},
        )

    assert saved.status_code == 503


@pytest.mark.asyncio
async def test_board_remote_active_allows_move_and_save(api_app, client):
    remote = _board_remote(api_app)
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        game_id = started.json()["game_id"]
        remote.get_ai_ladder_game_status.return_value = {"state": "active", "game_id": game_id}
        session = api_app.state._test_created_sessions[0]
        history_before = len(session.katrain._state["history"])
        moved = await ac.post(
            "/api/move",
            headers=api_app.state._test_headers,
            json={"session_id": session.session_id, "coords": [3, 3]},
        )
        session._recorded = True
        session.ai_ladder_settlement_pending = False
        saved = await ac.get(
            "/api/sgf/save",
            headers=api_app.state._test_headers,
            params={"session_id": session.session_id},
        )

    assert (moved.status_code, saved.status_code) == (200, 200)
    assert len(session.katrain._state["history"]) == history_before + 1


@pytest.mark.asyncio
async def test_board_remote_lifecycle_error_returns_503_without_mutating_move(api_app, client):
    remote = _board_remote(api_app)
    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        session = api_app.state._test_created_sessions[0]
        history_before = list(session.katrain._state["history"])
        remote.get_ai_ladder_game_status.side_effect = RuntimeError("cloud offline")
        moved = await ac.post(
            "/api/move",
            headers=api_app.state._test_headers,
            json={"session_id": session.session_id, "coords": [3, 3]},
        )

    assert moved.status_code == 503
    assert session.katrain._state["history"] == history_before


@pytest.mark.asyncio
async def test_board_terminal_queues_the_full_record_with_reservation_and_device(api_app, client, monkeypatch):
    from katrain.web import server as server_module

    remote = _board_remote(api_app)
    remote.mark_ai_ladder_game_pending = AsyncMock()
    enqueue = MagicMock(return_value=True)
    api_app.state.sync_enqueue_fn = enqueue
    monkeypatch.setattr(server_module.settings, "DEVICE_ID", "box-17")

    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        remote.get_ai_ladder_game_status.return_value = {"state": "active", "game_id": started.json()["game_id"]}
        response = await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 200
    reservation_key = remote.reserve_ai_ladder_game.await_args.args[0]["reservation_key"]
    remote.mark_ai_ladder_game_pending.assert_awaited_once_with(started.json()["game_id"], reservation_key)
    payload = enqueue.call_args.kwargs["payload"]
    assert payload["reservation_key"] == reservation_key
    assert payload["device_id"] == "box-17"
    assert payload["game_record"]["sgf_content"].startswith("(;FF[4]")
    assert payload["game_record"]["game_type"] == "ai_ladder_ranked"
    assert payload["game_id"] == started.json()["game_id"]


@pytest.mark.asyncio
async def test_board_terminal_retains_pending_credential_until_outbox_is_durable(api_app, client, monkeypatch):
    from katrain.web import server as server_module

    remote = _board_remote(api_app)
    remote.mark_ai_ladder_game_pending = AsyncMock()
    enqueue = MagicMock(side_effect=[False, True])
    api_app.state.sync_enqueue_fn = enqueue
    monkeypatch.setattr(server_module.settings, "DEVICE_ID", "box-17")

    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        remote.get_ai_ladder_game_status.return_value = {"state": "active", "game_id": started.json()["game_id"]}
        await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    session = api_app.state._test_created_sessions[0]
    pending = api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id)
    assert pending["reservation_key"] == remote.reserve_ai_ladder_game.await_args.args[0]["reservation_key"]
    assert session.ai_ladder_settlement_pending is True
    assert session._recorded is False

    await server_module._RECORD_FN(
        session,
        api_app,
        SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user"),
        "W+R",
    )

    assert enqueue.call_count == 2
    assert api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id) is None
    assert session.ai_ladder_settlement_pending is False
    assert session._recorded is True


@pytest.mark.asyncio
async def test_board_status_rebuilds_missing_settlement_outbox_after_restart(api_app, client, monkeypatch):
    from katrain.web import server as server_module

    remote = _board_remote(api_app)
    remote.mark_ai_ladder_game_pending = AsyncMock()
    enqueue = MagicMock(side_effect=[False, False, True])
    api_app.state.sync_enqueue_fn = enqueue
    monkeypatch.setattr(server_module.settings, "DEVICE_ID", "box-17")

    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        remote.get_ai_ladder_game_status.return_value = {"state": "active", "game_id": started.json()["game_id"]}
        await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )
        api_app.state.session_manager._sessions.pop(started.json()["session_id"])
        failed_recovery = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

        pending = api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id)
        assert failed_recovery.status_code == 200
        assert pending["reservation_key"]

        recovered = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert recovered.status_code == 200
    assert enqueue.call_count == 3
    recovered_payload = enqueue.call_args.kwargs["payload"]
    assert recovered_payload["game_id"] == started.json()["game_id"]
    assert recovered_payload["game_record"]["sgf_content"].startswith("(;FF[4]")
    assert api_app.state.ai_ladder_repo.get_pending_game(api_app.state._test_user_id) is None


@pytest.mark.asyncio
async def test_board_recovery_preserves_engine_unavailable_as_non_counting(api_app, client, monkeypatch):
    from katrain.web import server as server_module

    remote = _board_remote(api_app)
    remote.mark_ai_ladder_game_pending = AsyncMock()
    enqueue = MagicMock(side_effect=[False, True])
    api_app.state.sync_enqueue_fn = enqueue
    monkeypatch.setattr(server_module.settings, "DEVICE_ID", "box-17")

    async with client as ac:
        started = await ac.post(
            "/api/v1/ai-ladder/start",
            headers=api_app.state._test_headers,
            json={"color": "black", "time_enabled": False},
        )
        remote.get_ai_ladder_game_status.return_value = {"state": "active", "game_id": started.json()["game_id"]}
        await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )
        with api_app.state._test_session_factory() as db:
            ledger = db.query(models_db.AiLadderGameLedger).filter_by(game_id=started.json()["game_id"]).one()
            ledger.reason = "engine_unavailable"
            ledger.counted = False
            db.commit()
        api_app.state.session_manager._sessions.pop(started.json()["session_id"])

        recovered = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert recovered.status_code == 200
    assert enqueue.call_args.kwargs["payload"]["engine_stalled"] is True


@pytest.mark.asyncio
async def test_a_node_with_a_sync_dispatcher_still_settles_its_own_ranked_game(api_app, client):
    """A board is the authority for the games its own engine played.

    Settlement re-reads the row it just wrote before moving the rank, so the ranked row
    has to go to this node's authoritative store — never through the dispatcher, which
    would have sent it to the cloud (online) or queued it (offline), leaving nothing to
    read back. Free games keep using the dispatcher.
    """
    dispatcher = RecordingDispatcher()
    api_app.state.repository_dispatcher = dispatcher
    async with client as ac:
        started = await start_ranked(api_app, ac)
        response = await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 200
    assert dispatcher.calls == []
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).one().result == "loss"
        assert db.query(models_db.UserGame).one().game_type == "ai_ladder_ranked"
        assert db.query(models_db.AiLadderPendingGame).count() == 0


@pytest.mark.asyncio
async def test_a_node_that_is_not_the_ladder_authority_refuses_to_settle(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        api_app.state.ai_ladder_authoritative = False  # e.g. a node demoted mid-game
        response = await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 200  # the game still ends; only the ledger abstains
    session = api_app.state._test_created_sessions[0]
    assert session.ai_ladder_settlement_pending is True
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.AiLadderPendingGame).count() == 1


@pytest.mark.asyncio
async def test_finishing_a_free_game_records_it_without_erroring(api_app, client, caplog):
    """A free game's record path must complete, not just leave a row behind.

    `_record_ai_game_locked` swallows every exception into one log line, so a broken
    call after the row is written looks exactly like success from the outside: the game
    is in the database, the request is 200, and only the log says the function blew up.
    """
    async with client as ac:
        created = await ac.post("/api/session", headers=api_app.state._test_headers)
        session_id = created.json()["session_id"]
        session = api_app.state.session_manager._sessions[session_id]
        session.user_id = api_app.state._test_user_id
        session.game_type = "free"
        session.katrain.players_info["W"].player_subtype = "ai:policy"

        with caplog.at_level(logging.ERROR, logger="katrain_web"):
            response = await ac.post(
                "/api/resign",
                headers=api_app.state._test_headers,
                json={"session_id": session_id},
            )

    assert response.status_code == 200
    assert [r.message for r in caplog.records if "Failed to record game" in r.message] == []
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 1
        assert db.query(models_db.AiLadderGameLedger).count() == 0


# --- 心跳:盒端定时器 ---------------------------------------------------------
#
# 三层各自有守卫(契约 ⑧):枚举(会话 → 目标)、扫描(目标 → 权威)、循环(永不静默停摆)。
# 判据不是「跑没跑绿」,是把任一层的实现单独删掉,有没有东西红。


def _active_row(api_app, game_id: str):
    with api_app.state._test_session_factory() as db:
        return db.query(models_db.AiLadderActiveGame).filter(models_db.AiLadderActiveGame.game_id == game_id).one()


@pytest.mark.asyncio
async def test_heartbeat_sweep_reports_liveness_for_a_game_started_through_the_api(api_app, client):
    """整条链路:/start 建的会话,扫描器能从它身上取到密钥并把生存证据写进权威。

    走真 HTTP 起局而不是手工塞一个会话 —— 这条要证的恰恰是「/start 把密钥和设备标记
    留在了扫描器找得到的地方」,自己造会话就把要证的东西假设掉了。
    """

    async with client as ac:
        response = await start_ranked(api_app, ac)
    assert response.status_code == 201
    game_id = response.json()["game_id"]

    before = _active_row(api_app, game_id)
    assert before.state == "active"
    assert before.heartbeat_generation == 0
    assert before.last_heartbeat_at is None

    await server._send_ai_ladder_heartbeats(api_app)

    after = _active_row(api_app, game_id)
    assert after.heartbeat_generation == 1
    assert after.last_heartbeat_at is not None


@pytest.mark.asyncio
async def test_heartbeat_sweep_leaves_out_a_game_that_has_already_ended_here(api_app, client):
    """局在本地下完了就不再报生存 —— 心跳声称有人在棋盘前,下完之后那句话就是假的。"""

    async with client as ac:
        response = await start_ranked(api_app, ac)
    game_id = response.json()["game_id"]
    api_app.state._test_created_sessions[0].game_ended = True

    assert api_app.state.session_manager.ai_ladder_liveness_targets() == []


@pytest.mark.asyncio
async def test_heartbeat_sweep_counts_one_game_once_even_with_two_sessions_on_it(api_app, client):
    """同一局两个会话只报一次。

    云端数的是「这个客户端在不在跑定时器」,重复上报会让一个盒子以两倍速度越过那道门槛,
    把「证明过自己会报」变成「报得比别人快」。
    """

    async with client as ac:
        response = await start_ranked(api_app, ac)
    game_id = response.json()["game_id"]
    original = api_app.state._test_created_sessions[0]
    twin = SimpleNamespace(
        session_id="twin",
        user_id=original.user_id,
        game_type="ai_ladder_ranked",
        ai_ladder_snapshot=original.ai_ladder_snapshot,
        ai_ladder_reservation_key=original.ai_ladder_reservation_key,
        ai_ladder_settlement_pending=False,
    )
    api_app.state.session_manager._sessions["twin"] = twin

    targets = api_app.state.session_manager.ai_ladder_liveness_targets()
    assert [t[1] for t in targets] == [game_id]

    await server._send_ai_ladder_heartbeats(api_app)
    assert _active_row(api_app, game_id).heartbeat_generation == 1


@pytest.mark.asyncio
async def test_heartbeat_sweep_routes_to_the_cloud_when_this_process_is_a_board(api_app, monkeypatch):
    """盒端不写自己的库,它把生存证据转给权威 —— 判决在云端做,盒子只是被判决的对象。"""

    remote = AsyncMock()
    monkeypatch.setattr(api_app.state, "remote_client", remote, raising=False)
    monkeypatch.setattr(api_app.state, "repository_dispatcher", MagicMock(), raising=False)
    monkeypatch.setattr(
        api_app.state.session_manager,
        "ai_ladder_liveness_targets",
        lambda: [(7, "game-7", "key-7", "box-7")],
    )
    local_write = MagicMock()
    monkeypatch.setattr(api_app.state.ai_ladder_repo, "record_heartbeat", local_write)

    await server._send_ai_ladder_heartbeats(api_app)

    remote.send_ai_ladder_heartbeat.assert_awaited_once_with("game-7", "key-7")
    local_write.assert_not_called()


@pytest.mark.asyncio
async def test_heartbeat_sweep_keeps_reporting_after_one_game_fails(api_app, monkeypatch):
    """一局报不上去不影响别的局 —— 否则一条坏记录能让同一台机器上所有对局一起变成可接管。"""

    monkeypatch.setattr(
        api_app.state.session_manager,
        "ai_ladder_liveness_targets",
        lambda: [(1, "bad", "k1", "d"), (2, "good", "k2", "d")],
    )
    seen = []

    def record(*, user_id, game_id, reservation_key, origin_device_id):
        seen.append(game_id)
        if game_id == "bad":
            raise RuntimeError("row vanished")

    monkeypatch.setattr(api_app.state.ai_ladder_repo, "record_heartbeat", record)

    await server._send_ai_ladder_heartbeats(api_app)

    assert seen == ["bad", "good"]


@pytest.mark.asyncio
async def test_heartbeat_loop_does_not_stop_when_a_sweep_raises(monkeypatch):
    """循环吞掉一切异常并继续。

    这条守的是**静默停摆**:循环一死没有任何人报错,它托着的对局五分钟后变成可接管,
    另一台设备替一局还在下的棋记一笔败。所以「失败后仍然继续」本身就是被断言的性质,
    不是实现细节。
    """

    sweeps = []

    async def always_fails(app):
        sweeps.append(1)
        raise RuntimeError("authority unreachable")

    monkeypatch.setattr(server, "_send_ai_ladder_heartbeats", always_fails)
    monkeypatch.setattr(server, "AI_LADDER_HEARTBEAT_INTERVAL_SECONDS", 0)

    task = asyncio.create_task(server._ai_ladder_heartbeat_loop(SimpleNamespace()))
    for _ in range(50):
        await asyncio.sleep(0)
        if len(sweeps) >= 3:
            break
    task.cancel()

    assert len(sweeps) >= 3, "第一次失败就停了 —— 那正是要防的静默停摆"


@pytest.mark.asyncio
async def test_heartbeat_targets_carry_the_device_that_actually_reserved_the_game(api_app, client):
    """设备标记取自起局那一刻,不是回落成 "cloud-local"。

    `_verify_origin` 只认预约密钥、根本不看设备标记,所以这行赋值在鉴权上不产生任何后果 ——
    正因如此它才需要一条专门的断言:没有它,这行就是「写了但没人到得了」的那一类,
    删掉整套测试照样全绿。这里让起局带一个真设备头,回落值就与真值可区分了。
    """

    async with client as ac:
        response = await ac.post(
            "/api/v1/ai-ladder/start",
            headers={**api_app.state._test_headers, "X-StellaBox-Device-ID": "box-42"},
            json={"color": "black", "time_enabled": False},
        )
    assert response.status_code == 201

    targets = api_app.state.session_manager.ai_ladder_liveness_targets()
    assert [t[3] for t in targets] == ["box-42"]


# --- 结算被拒之后,账号不得被永久卡死 -------------------------------------------
#
# 这一组是**造状态真跑**,不是读代码。此前「围棋有出路」这个结论只到「我读了心跳枚举
# 会跳过结算在飞的会话」为止 —— 而今天四家反复证明的一条是:读起来到得了不算数。


@pytest.mark.asyncio
async def test_a_rejected_settlement_stops_the_heartbeat(api_app, client):
    """结算被拒之后,心跳必须**真的**停。

    这是整条出路的地基:接管判据读的是 `now - last_heartbeat_at`,心跳只要还在发,
    另一台设备就永远等不到可接管的那一刻 —— 那正是国象和象棋的死局形状。

    这里断言的是「代际不再增长」,不是「枚举返回空」:枚举是实现,代际是云端真正读到的东西。
    """

    async with client as ac:
        response = await start_ranked(api_app, ac)
    game_id = response.json()["game_id"]

    await server._send_ai_ladder_heartbeats(api_app)
    assert _active_row(api_app, game_id).heartbeat_generation == 1

    # 局下完了。云端拒不拒、什么时候拒,与这里无关 —— 这正是修好之后的性质:
    # 心跳停在「局结束」这一刻,而不是等某个结算标记被谁置上。
    api_app.state._test_created_sessions[0].game_ended = True

    await server._send_ai_ladder_heartbeats(api_app)
    await server._send_ai_ladder_heartbeats(api_app)

    assert _active_row(api_app, game_id).heartbeat_generation == 1, (
        "被拒之后心跳还在发 —— 那台盒子上已经没有人在下棋了,继续报生存就是在报假信息,"
        "而接管判据永不满足,账号被永久卡死"
    )


@pytest.mark.asyncio
async def test_a_rejected_settlement_leaves_an_exit_for_another_device(api_app, client):
    """被拒之后过了失联阈值,另一台设备能把账号解套。

    构造的是「标记没落上」那一档 —— 行停在 `active`,走接管;这是围棋最坏的一档,
    因为 `mark_ai_ladder_game_pending` 是 best-effort 的,它没落上时不会有任何人告诉你。
    """

    async with client as ac:
        response = await start_ranked(api_app, ac)
        game_id = response.json()["game_id"]

        # 心跳代际爬过门槛,让判据走真分支而不是「从未心跳」的兼容分支。
        await server._send_ai_ladder_heartbeats(api_app)
        await server._send_ai_ladder_heartbeats(api_app)
        api_app.state._test_created_sessions[0].game_ended = True

        with api_app.state._test_session_factory() as db:
            row = db.query(models_db.AiLadderActiveGame).filter_by(game_id=game_id).one()
            assert row.state == "active" and row.heartbeat_generation >= 2
            row.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=6)
            db.commit()

        # 拨旧之后**再扫一轮**,这一步是这条测试的要害。
        # 少了它,这条测的只是「接管机制会不会开门」,而不是「因为心跳停了门才开」——
        # 手工拨旧的时间戳等于把因果里的前一半直接假设掉(契约 ⑦c:断言的是副作用,不是性质)。
        # 加上它,心跳但凡还在发,这一轮就会把时间戳刷新回来、门重新关上,测试当场红。
        await server._send_ai_ladder_heartbeats(api_app)

        ended = await ac.post(
            f"/api/v1/ai-ladder/games/{game_id}/end",
            headers={**api_app.state._test_headers, "X-StellaBox-Device-ID": "other-device"},
            json={"reason": "user_resigned"},
        )

    assert ended.status_code == 200, ended.text
    assert ended.json()["state"] == "settled"
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).filter_by(game_id=game_id).one_or_none() is None


@pytest.mark.asyncio
async def test_the_exit_stays_shut_while_the_box_is_still_reporting_in(api_app, client):
    """反向:心跳还在的时候那扇门必须是关的。

    没有这条,上面那条证明不了任何事 —— 一扇永远开着的门当然「有出路」,
    而那等于把段位并发规则整个作废。
    """

    async with client as ac:
        response = await start_ranked(api_app, ac)
        game_id = response.json()["game_id"]
        await server._send_ai_ladder_heartbeats(api_app)
        await server._send_ai_ladder_heartbeats(api_app)

        ended = await ac.post(
            f"/api/v1/ai-ladder/games/{game_id}/end",
            headers={**api_app.state._test_headers, "X-StellaBox-Device-ID": "other-device"},
            json={"reason": "user_resigned"},
        )

    assert ended.status_code == 409
    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.AiLadderActiveGame).filter_by(game_id=game_id).one().state == "active"


@pytest.mark.asyncio
async def test_heartbeat_stops_when_the_local_game_ends_not_when_settlement_is_flagged(api_app, client):
    """心跳绑「本地这局还在下」,不绑「结算失败标记」。

    这条是审计推翻我先前结论之后补的。原来的枚举只跳过 `ai_ladder_settlement_pending`,
    而**云端拒绝发生在异步 sync worker 里**:worker 收到 4xx 只把队列行标成 `failed`
    (`sync_worker.py:172-173`),**从不回头碰会话**。于是盒端标记停在 False、心跳照发、
    云端行停在 `active` —— 接管判据永不满足,账号被永久卡死。

    先前那两条测试没抓到它,是因为它们**手工**把 `settlement_pending` 置了真 ——
    断言的是我摆好的状态,不是系统真会走到的状态(契约 ⑦c)。

    所以这里构造的是真路径:局下完了(`game_ended`)、盒端认为已入队落袋
    (`settlement_pending=False`、`_recorded=True`),云端稍后才拒。
    """

    async with client as ac:
        response = await start_ranked(api_app, ac)
    game_id = response.json()["game_id"]
    await server._send_ai_ladder_heartbeats(api_app)
    assert _active_row(api_app, game_id).heartbeat_generation == 1

    session = api_app.state._test_created_sessions[0]
    session.game_ended = True  # 引擎报了 end_result
    session.ai_ladder_settlement_pending = False  # 盒端认为已经交出去了
    session._recorded = True

    await server._send_ai_ladder_heartbeats(api_app)
    await server._send_ai_ladder_heartbeats(api_app)

    assert _active_row(api_app, game_id).heartbeat_generation == 1, (
        "局已经下完了还在报生存 —— 那台机器上没有人在下棋,继续发心跳就是在报假信息。"
        "而云端异步拒绝之后行仍是 active,接管判据永不满足 ⇒ 账号永久卡死"
    )


@pytest.mark.asyncio
async def test_the_heartbeat_sweep_does_not_keep_its_own_session_alive(api_app, client):
    """巡检不得给被巡检的对象续命。

    围棋唯一的兜底上限是会话超时:用户中途走开、局永远不终局,心跳会一直发下去,
    直到 `cleanup_expired` 把这个闲置会话整个删掉(默认 1 小时)—— 那之后心跳自然停,
    再 5 分钟另一台设备就能接管。

    这条上限成立的前提是**枚举不碰 `last_access`**。`ai_ladder_liveness_targets` 因此
    直接读 `_sessions.values()`,不走 `get_session()`(它会 `touch()`)。改成走
    `get_session()` 看起来更规矩,后果却是每 30 秒把会话续一次命 ⇒ 永不过期 ⇒
    心跳永不停 ⇒ 那个账号在所有设备上永远开不了新局。

    **一个把被巡检对象保活的巡检器,会让所有基于超时的回收永不触发**,而且没有任何
    现象指向巡检器 —— 看起来只是「这个会话怎么一直不过期」。
    """

    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        # fixture 里的假会话把 `touch` 打成了空 lambda。不换掉它,这条断言就是空转的:
        # 把枚举改成走 `get_session()`(真会续命的那个写法)照样绿 —— 我第一版正是这样,
        # 变异红在了另一条测试上,而那条红的是别的原因。**红了不等于红在你要证的地方。**
        session.touch = lambda s=session: setattr(s, "last_access", time.time())
        session.last_access = 0.0

        # 造的是**盒子真实的行为**,不是巡检器自己的行为:局还在下的时候,盒子除了发心跳
        # 还会不断被前端问状态。走满一整轮阈值的量级、期间反复轮询,才逼近真实压力。
        # (象棋钉这条时用的就是这个形状:只连扫两轮,量的是一个不存在的安静系统。)
        for _ in range(10):
            await server._send_ai_ladder_heartbeats(api_app)
            await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert session.last_access == 0.0, "心跳扫描把会话续命了 —— 超时回收这条兜底就永远不会触发"


@pytest.mark.asyncio
async def test_a_real_resign_stops_the_heartbeat_without_anyone_setting_the_flag(api_app, client):
    """真认输之后心跳必须停 —— 而且**不许由测试代替系统去置那个标记**。

    这条是对抗性审计挖出来的,它推翻的正是我自己前面那几条心跳测试:它们全部手工写
    `session.game_ended = True`,于是证明的只是「标记置上以后心跳会停」,
    **而不是「真实终局会把标记置上」**。两句话之间隔着整个缺陷。

    段位认输分支(`server.py:1725-1735`)直接改
    `game.game_result` / `current_node.end_state` / `katrain._state["end_result"]`,
    然后自己给 `session.last_state` 赋值,**全程不调 `session.katrain(...)`** ——
    而 `game_ended` 唯一的自动写点是 `SessionManager._on_state`,它挂在
    `update_state` 回调链上。链不触发,标记就永远是 False,心跳永远发下去,
    另一台设备看到的是一个**永远往后跑的倒计时**。

    对照:`/api/timeout` 走 `session.katrain("timeout")`(会触发回调),
    数子路径显式赋值(`server.py:1796`)—— 唯独认输两条都没有。
    """

    async with client as ac:
        response = await start_ranked(api_app, ac)
        game_id = response.json()["game_id"]
        session_id = api_app.state._test_created_sessions[0].session_id

        await server._send_ai_ladder_heartbeats(api_app)
        assert _active_row(api_app, game_id).heartbeat_generation == 1

        # 让结算失败,好让云端那一行**活下来** —— 结算成功时行会被删掉,死局无从谈起。
        # 这正是被拒场景的形状:局下完了,而占位还在。
        def refuse(*args, **kwargs):
            raise RuntimeError("cloud refused this settlement")

        api_app.state.ai_ladder_repo.finalize_reserved_game = refuse
        api_app.state.ai_ladder_repo.settle_game = refuse

        resigned = await ac.post("/api/resign", headers=api_app.state._test_headers, json={"session_id": session_id})
        assert resigned.status_code == 200, resigned.text

    await server._send_ai_ladder_heartbeats(api_app)
    await server._send_ai_ladder_heartbeats(api_app)

    assert (
        _active_row(api_app, game_id).heartbeat_generation == 1
    ), "认输之后还在报生存 —— 心跳唯一的停止条件在最常用的终局路径上没被置位"


def test_every_place_that_writes_a_terminal_result_by_hand_also_ends_the_game():
    """绊线:凡是绕过 `session.katrain(...)` 直接把终局写到树上的地方,都必须自己置 `game_ended`。

    `game_ended` 的自动写点只有一个 —— `SessionManager._on_state`,挂在 `update_state`
    回调链上。**绕过引擎直接改树,那条链就不触发**,而 `game_ended` 是段位心跳唯一的
    停止条件:漏一处,那条终局路径上的对局就永远在报「有人在棋盘前」,云端预约永远
    不可接管,账号在它名下每台设备上都开不了新局。

    认输那处就是这么漏的,而且它是最常用的终局路径。数子那处一直是对的 ——
    **两处并存正说明这不是「想不到」,是「没有东西提醒」。**

    扫源码而不是跑用例,因为要防的是**将来新加的第三处**:它今天还不存在,
    写不出针对它的用例;而这条断言在它出现的当天就会红。
    """

    source = (Path(server.__file__)).read_text(encoding="utf-8")
    lines = source.splitlines()
    offenders = []
    for index, line in enumerate(lines):
        if "current_node.end_state = " not in line:
            continue
        # 直写终局之后 12 行内必须出现 game_ended 置真(两处现存写法都在 4 行以内)。
        window = "\n".join(lines[index : index + 12])
        if "session.game_ended = True" not in window:
            offenders.append(f"server.py:{index + 1}: {line.strip()}")

    assert (
        not offenders
    ), "这些地方直接写了终局却没有置 `session.game_ended` —— 段位心跳会永远发下去:\n  " + "\n  ".join(offenders)


def test_the_tripwire_can_actually_see_a_missing_flag():
    """正对照:证明上面那条不是恒真。

    扫源码的断言最容易变成「扫不到任何东西所以 0 违规」,长得和守得很好一模一样。
    这里直接喂一段缺 `game_ended` 的假源码,确认扫描逻辑抓得到。
    """

    fake = (
        "                    session.katrain.game.current_node.end_state = result\n" * 1 + "                    pass\n"
    )
    lines = fake.splitlines()
    hits = [
        i
        for i, line in enumerate(lines)
        if "current_node.end_state = " in line and "session.game_ended = True" not in "\n".join(lines[i : i + 12])
    ]
    assert hits, "扫描逻辑抓不到缺失的置位 —— 上面那条断言说明不了任何事情"
