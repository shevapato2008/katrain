"""HTTP contract and trusted settlement tests for ranked AI ladder games."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.ai_ladder_ranked import AiLadderRankedRepository
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core.db import Base
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

    def config(self, setting, default=None):
        if setting == "game/count_min_moves":
            return 0
        return default

    def get_state(self):
        return dict(self._state)

    def get_sgf(self):
        return "(;FF[4]SZ[19];B[pd])"


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

    def create_session(katago_uuid=None):
        session_id = f"session-{len(created_sessions) + 1}"
        session = SimpleNamespace(
            session_id=session_id,
            user_id=None,
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
        },
        "recent_ranked_results": [],
        "net_score": 0,
        "pending_settlement": False,
    }


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
    payload = {
        "board_size": 19,
        "rules": "chinese",
        "komi": 7.5,
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
    session = api_app.state.session_manager.create_session()
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
            await ac.post("/api/nav", json={"session_id": session.session_id, "node_id": 0}),
            await ac.post("/api/analysis/current", json={"session_id": session.session_id}),
            await ac.post(
                "/api/new-game",
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
async def test_vision_cannot_bind_ranked_session(api_app, client):
    vision = SimpleNamespace(bound_session_id=None)

    def bind_session(session_id):
        vision.bound_session_id = session_id

    vision.bind_session = bind_session
    api_app.state.vision = vision
    async with client as ac:
        started = await start_ranked(api_app, ac)
        response = await ac.post(
            "/api/v1/vision/bind",
            json={"session_id": started.json()["session_id"]},
        )

    assert response.status_code == 403
    assert vision.bound_session_id is None


@pytest.mark.asyncio
async def test_confirmed_vision_move_is_ignored_and_unbound_for_ranked_session(api_app, client):
    async with client as ac:
        started = await start_ranked(api_app, ac)
    session_id = started.json()["session_id"]
    vision = SimpleNamespace(bound_session_id=session_id)
    vision.unbind_session = lambda: setattr(vision, "bound_session_id", None)
    history_before = list(api_app.state._test_created_sessions[0].katrain._state["history"])

    delay = await __import__("katrain.web.server", fromlist=["_handle_confirmed_move"])._handle_confirmed_move(
        api_app,
        vision,
        session_id,
        SimpleNamespace(col=3, row=3, color=1),
        logging.getLogger("test-ranked-vision"),
    )

    assert delay == 0.0
    assert vision.bound_session_id is None
    assert api_app.state._test_created_sessions[0].katrain._state["history"] == history_before


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
@pytest.mark.parametrize("path", ["/api/resign", "/api/timeout"])
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

    assert status_response.json()["pending_settlement"] is True
    assert "authoritative ranked AI" in caplog.text
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
        assert [(game.id, game.game_type) for game in games] == [(game_id, "ai_ladder_ranked")]
        assert [(row.game_id, row.counted) for row in ledger] == [(game_id, True)]
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
async def test_settlement_failure_remains_pending_and_retries_same_saved_game(api_app, client, monkeypatch):
    async with client as ac:
        started = await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        record = __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN
        user = SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user")
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"

        original_settle = api_app.state.ai_ladder_repo.settle_game

        def fail_once(**kwargs):
            raise RuntimeError("fixture settlement failure")

        monkeypatch.setattr(api_app.state.ai_ladder_repo, "settle_game", fail_once)
        await record(session, api_app, user, "B+R")

        pending = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
        assert pending.json()["pending_settlement"] is True
        assert session._recorded is False
        blocked_start = await start_ranked(api_app, ac)
        assert blocked_start.status_code == 409
        assert len(api_app.state._test_created_sessions) == 1

        # Simulate a restart: discard the only session and restore the real repository
        # method. Recovery must use only the database snapshot + saved UserGame.
        api_app.state.session_manager._sessions.clear()
        monkeypatch.setattr(api_app.state.ai_ladder_repo, "settle_game", original_settle)
        recovered = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
        assert recovered.json()["pending_settlement"] is False

    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 1
        assert db.query(models_db.UserGame).one().id == started.json()["game_id"]
        assert db.query(models_db.AiLadderGameLedger).count() == 1
        assert db.get(models_db.AiLadderProfile, user.id).placement_completed == 1
        assert db.execute(text("SELECT COUNT(*) FROM ai_ladder_pending_games")).scalar_one() == 0


@pytest.mark.asyncio
async def test_orphan_pending_without_saved_game_is_abandoned_after_restart(api_app, client):
    async with client as ac:
        await start_ranked(api_app, ac)
        api_app.state.session_manager._sessions.clear()
        status_response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)
        restarted = await start_ranked(api_app, ac)

    assert status_response.json()["pending_settlement"] is False
    assert restarted.status_code == 201
    with api_app.state._test_session_factory() as db:
        assert db.execute(text("SELECT COUNT(*) FROM ai_ladder_pending_games")).scalar_one() == 1


@pytest.mark.asyncio
async def test_pending_is_not_abandoned_while_its_session_is_still_being_configured(api_app, client):
    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        session.user_id = None
        status_response = await ac.get("/api/v1/ai-ladder/status", headers=api_app.state._test_headers)

    assert status_response.json()["pending_settlement"] is True
    with api_app.state._test_session_factory() as db:
        assert db.execute(text("SELECT COUNT(*) FROM ai_ladder_pending_games")).scalar_one() == 1


@pytest.mark.asyncio
async def test_conflicting_retry_after_saved_result_is_rejected_without_settlement(api_app, client, monkeypatch):
    async with client as ac:
        await start_ranked(api_app, ac)
        session = api_app.state._test_created_sessions[0]
        record = __import__("katrain.web.server", fromlist=["_RECORD_FN"])._RECORD_FN
        user = SimpleNamespace(id=api_app.state._test_user_id, username="ladder-user")
        session.katrain.game.end_result = "B+R"
        session.katrain._state["end_result"] = "B+R"
        original_settle = api_app.state.ai_ladder_repo.settle_game
        monkeypatch.setattr(
            api_app.state.ai_ladder_repo,
            "settle_game",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("first settle fails")),
        )
        await record(session, api_app, user, "B+R")

        session.katrain.game.end_result = "W+R"
        session.katrain._state["end_result"] = "W+R"
        session.katrain.get_sgf = lambda: "(;FF[4]SZ[19];W[dd])"
        monkeypatch.setattr(api_app.state.ai_ladder_repo, "settle_game", original_settle)
        await record(session, api_app, user, "W+R")

    with api_app.state._test_session_factory() as db:
        assert db.query(models_db.UserGame).count() == 1
        assert db.query(models_db.UserGame).one().result == "B+R"
        assert db.query(models_db.AiLadderGameLedger).count() == 0
        assert db.query(models_db.AiLadderProfile).count() == 0
        pending = db.execute(text("SELECT game_saved, saved_result FROM ai_ladder_pending_games")).one()
        assert pending[0] in (True, 1)
        assert pending[1] == "B+R"


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
