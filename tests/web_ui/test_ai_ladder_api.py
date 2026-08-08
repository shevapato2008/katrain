"""HTTP contract and trusted settlement tests for ranked AI ladder games."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
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
        reserved = await ac.post(
            "/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload()
        )
        game_id = reserved.json()["game_id"]

        pending = await ac.get(
            f"/api/v1/ai-ladder/settlements/{game_id}", headers=headers
        )
        settled_post = await ac.post(
            f"/api/v1/ai-ladder/games/{game_id}/end",
            headers=headers,
            json={"reason": "user_resigned"},
        )
        settled = await ac.get(
            f"/api/v1/ai-ladder/settlements/{game_id}", headers=headers
        )
        missing = await ac.get(
            "/api/v1/ai-ladder/settlements/not-this-users-game", headers=api_app.state._test_headers
        )

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
        reserved = await ac.post(
            "/api/v1/ai-ladder/games/reserve", headers=owner, json=reservation_payload()
        )
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
async def test_settled_ranked_sgf_export_is_available_to_owner(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session_id = started.json()["session_id"]
        resigned = await ac.post("/api/resign", headers=api_app.state._test_headers, json={"session_id": session_id})
        response = await ac.get("/api/sgf/save", headers=api_app.state._test_headers, params={"session_id": session_id})

    assert resigned.status_code == 200
    assert response.status_code == 200
    assert response.json()["sgf"].startswith("(;FF[4]")


@pytest.mark.asyncio
async def test_settled_ranked_game_rejects_public_and_vision_moves_without_changing_sgf(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session_id = started.json()["session_id"]
        session = api_app.state._test_created_sessions[0]
        assert (
            await ac.post("/api/resign", headers=api_app.state._test_headers, json={"session_id": session_id})
        ).status_code == 200
        exported_before = await ac.get(
            "/api/sgf/save", headers=api_app.state._test_headers, params={"session_id": session_id}
        )
        assert exported_before.status_code == 200, (
            exported_before.text,
            session._recorded,
            session.ai_ladder_settlement_pending,
        )
        sgf_before = exported_before.json()["sgf"]
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
        sgf_after = (
            await ac.get("/api/sgf/save", headers=api_app.state._test_headers, params={"session_id": session_id})
        ).json()["sgf"]

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
        sgf_before = (
            await ac.get("/api/sgf/save", headers=api_app.state._test_headers, params={"session_id": session_id})
        ).json()["sgf"]
        second = await ac.post("/api/resign", headers=api_app.state._test_headers, json={"session_id": session_id})
        sgf_after = (
            await ac.get("/api/sgf/save", headers=api_app.state._test_headers, params={"session_id": session_id})
        ).json()["sgf"]

    assert first.status_code == 200
    assert second.status_code == 403
    assert sgf_after == sgf_before
    session = api_app.state._test_created_sessions[0]
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
        reserved = await ac.post(
            "/api/v1/ai-ladder/games/reserve", headers=origin, json=reservation_payload()
        )
        replay = await ac.post(
            "/api/v1/ai-ladder/games/reserve", headers=origin, json=reservation_payload()
        )
        blocked = await ac.post(
            "/api/v1/ai-ladder/games/reserve",
            headers=other,
            json=reservation_payload(game_id="fedcba9876543210fedcba9876543210"),
        )
        owner_status = await ac.get("/api/v1/ai-ladder/status", headers=origin)
        other_status = await ac.get("/api/v1/ai-ladder/status", headers=other)

    assert reserved.status_code == 201
    assert set(reserved.json()) == {
        "game_id", "reservation_key", "blocking_game", "opponent", "execution_identity"
    }
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
        reserved = await ac.post(
            "/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload()
        )
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
            "board-a", "board-b", "remote_resign"
        )
        assert db.query(models_db.AiLadderProfile).one().placement_completed == 1


@pytest.mark.asyncio
async def test_game_lifecycle_is_private_and_requests_are_strict(api_app, client):
    with api_app.state._test_session_factory() as db:
        other_user = models_db.User(username="other-lifecycle-user", hashed_password="x", rank="20k")
        db.add(other_user)
        db.commit()
    other_auth = {"Authorization": f"Bearer {create_access_token({'sub': 'other-lifecycle-user'})}", "X-StellaBox-Device-ID": "x"}
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
        extra = await ac.post(
            "/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload(extra=True)
        )
        reserved = await ac.post(
            "/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload()
        )
        private = await ac.get(
            f"/api/v1/ai-ladder/games/{reservation_payload()['game_id']}/status", headers=other_auth
        )
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
        reserved = await ac.post(
            "/api/v1/ai-ladder/games/reserve", headers=headers, json=reservation_payload()
        )
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
            "win", "played_result", "replacement-board"
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
            "active", "galaxy-a", started.json()["session_id"]
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
        "state": "settled", "game_id": game_id, "receipt": {"counted": True, "reason": None}
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
        response = await ac.post(
            "/api/resign",
            headers=api_app.state._test_headers,
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 200
    reservation_key = remote.reserve_ai_ladder_game.await_args.args[0]["reservation_key"]
    remote.mark_ai_ladder_game_pending.assert_awaited_once_with(
        started.json()["game_id"], reservation_key
    )
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
