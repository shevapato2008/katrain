"""Private, read-only ownership estimates for ordinary human lobby games."""

import asyncio
import copy
import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from katrain.core.base_katrain import Player
from katrain.core.game_node import GameNode
from katrain.core.sgf_parser import Move
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core.config import settings
from katrain.web.server import create_app
from katrain.web.session import WebSession


@asynccontextmanager
async def no_lifespan(app):
    yield


class Engine:
    def __init__(self):
        self.calls = []
        self.during_analysis = None
        self.result = {
            "ownership": [1, -1, 0.5, -0.5, 0, 0.75],
            "rootInfo": {"winrate": 0.8},
            "moveInfos": [{"pv": ["A1"]}],
        }

    async def analyze(self, payload):
        self.calls.append(copy.deepcopy(payload))
        if self.during_analysis:
            await self.during_analysis()
        return self.result


@pytest.fixture
def lobby(monkeypatch):
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    app = create_app(enable_engine=False)
    app.router.lifespan_context = no_lifespan
    node = GameNode(properties={"SZ": ["3:2"], "KM": ["0.5"], "RU": ["chinese"]})
    runtime = SimpleNamespace(
        game_type="free",
        pvp_lobby_human_session=True,
        suppress_auto_eval=False,
        players_info={"B": Player("B"), "W": Player("W")},
        game=SimpleNamespace(game_id="game-1", current_node=node, terminal=None),
        continuous_analysis=False,
        pvp_lobby_awaiting_count=False,
    )
    session = WebSession(session_id="room", katrain=runtime, player_b_id=11, player_w_id=22)
    session.game_type = "free"
    app.state.session_manager._sessions[session.session_id] = session
    engine = Engine()
    app.state.router = SimpleNamespace(local_client=engine)
    identity = SimpleNamespace(user=SimpleNamespace(id=11))

    def current_user():
        if identity.user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return identity.user

    app.dependency_overrides[get_current_user] = current_user
    return app, session, engine, identity


async def request(app, **body):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/pvp/territory", json={"session_id": "room", **body})


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id", [11, 22])
async def test_both_participants_receive_only_private_territory(lobby, user_id):
    app, session, engine, identity = lobby
    identity.user.id = user_id
    node = session.katrain.game.current_node
    analysis_before = copy.deepcopy(node.analysis)
    response = await request(app)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "session_id": "room",
        "game_id": "game-1",
        "current_node_id": id(node),
        "move_count": 0,
        "board_size": [3, 2],
        "ownership": [1, -1, 0.5, -0.5, 0, 0.75],
        "black_area": 2,
        "white_area": 1,
        "stale": False,
    }
    assert node.analysis == analysis_before
    assert node.end_state is None
    assert session.katrain.game.terminal is None
    assert session.game_ended is False
    assert session.pending_count_request is None
    assert session.last_state is None
    assert session.katrain.continuous_analysis is False
    assert len(engine.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id,expected", [(None, 401), (33, 403)])
async def test_requires_actual_authenticated_participant(lobby, user_id, expected):
    app, _, engine, identity = lobby
    identity.user = SimpleNamespace(id=user_id) if user_id else None
    response = await request(app)
    assert response.status_code == expected
    assert not engine.calls


@pytest.mark.asyncio
async def test_snapshot_uses_server_node_path_setup_pass_rules_and_initial_player(lobby):
    app, session, engine, _ = lobby
    root = GameNode(
        properties={
            "SZ": ["3:2"],
            "KM": ["0.5"],
            "RU": ['{"koRule":"SIMPLE"}'],
            "PL": ["W"],
            "AB": ["aa"],
            "AW": ["cb"],
        }
    )
    node = root.play(Move(None, "W")).play(Move((1, 0), "B"))
    session.katrain.game.current_node = node
    response = await request(app)
    assert response.status_code == 200, response.text
    assert engine.calls == [
        {
            "rules": {"koRule": "SIMPLE"},
            "komi": 0.5,
            "boardXSize": 3,
            "boardYSize": 2,
            "initialStones": [["B", "A2"], ["W", "C1"]],
            "initialPlayer": "W",
            "moves": [["W", "pass"], ["B", "B1"]],
            "analyzeTurns": [2],
            "maxVisits": 200,
            "includeOwnership": True,
            "includePolicy": False,
        }
    ]
    assert response.json()["move_count"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        lambda s: setattr(s, "game_type", "ranked"),
        lambda s: setattr(s.katrain, "game_type", "rated"),
        lambda s: setattr(s.katrain, "pvp_lobby_human_session", False),
        lambda s: setattr(s, "bot_game", True),
        lambda s: setattr(s, "player_w_id", -1),
        lambda s: setattr(s, "player_w_id", True),
        lambda s: setattr(s, "player_w_id", None),
        lambda s: setattr(s.katrain.players_info["W"], "player_type", "ai"),
        lambda s: setattr(s.katrain, "platform_engine_color", "B"),
        lambda s: setattr(s, "mode", "research"),
    ],
)
async def test_rejects_every_non_ordinary_human_lobby(lobby, change):
    app, session, engine, _ = lobby
    change(session)
    response = await request(app)
    assert response.status_code == 403
    assert not engine.calls


@pytest.mark.asyncio
async def test_rejects_platform_gateway_and_owner_who_is_not_a_seat(lobby):
    app, session, engine, identity = lobby
    session.owner_user_id = 33
    identity.user.id = 33
    assert (await request(app)).status_code == 403
    identity.user.id = 11
    app.state.platform_gateway = SimpleNamespace(is_platform_game=lambda sid: sid == "room")
    assert (await request(app)).status_code == 403
    assert not engine.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        lambda s: setattr(s, "game_ended", True),
        lambda s: setattr(s.katrain.game, "terminal", SimpleNamespace(result="B+R")),
        lambda s: setattr(s.katrain.game.current_node, "end_state", "B+R"),
        lambda s: setattr(s.katrain, "pvp_lobby_awaiting_count", True),
    ],
)
async def test_rejects_terminal_or_awaiting_count(lobby, change):
    app, session, engine, _ = lobby
    change(session)
    response = await request(app)
    assert response.status_code == 409
    assert not engine.calls


@pytest.mark.asyncio
async def test_rejects_two_pass_awaiting_count_and_unsupported_clear_placements(lobby):
    app, session, engine, _ = lobby
    root = session.katrain.game.current_node
    session.katrain.suppress_auto_eval = True
    session.katrain.game.current_node = root.play(Move(None, "B")).play(Move(None, "W"))
    assert (await request(app)).status_code == 409
    session.katrain.game.current_node = GameNode(properties={"SZ": ["3:2"], "AE": ["aa"]})
    assert (await request(app)).status_code == 409
    assert not engine.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        None,
        {},
        {"ownership": [0]},
        {"ownership": [True] * 6},
        {"ownership": [float("nan")] * 6},
        {"ownership": [1.1] * 6},
    ],
)
async def test_invalid_engine_result_is_unavailable_and_releases_lease(lobby, result):
    app, _, engine, _ = lobby
    engine.result = result
    response = await request(app)
    assert response.status_code == 503
    assert not app.state.ranked_analysis_activity._temporary
    engine.result = {"rootInfo": {"ownership": [0] * 6}}
    assert (await request(app)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("engine offline"), asyncio.TimeoutError()])
async def test_engine_failure_is_unavailable_and_can_retry(lobby, failure):
    app, _, engine, _ = lobby

    async def fail():
        raise failure

    engine.during_analysis = fail
    assert (await request(app)).status_code == 503
    assert not app.state.ranked_analysis_activity._temporary
    engine.during_analysis = None
    assert (await request(app)).status_code == 200


@pytest.mark.asyncio
async def test_unavailable_engine_does_not_hold_lease(lobby):
    app, _, _, _ = lobby
    app.state.router.local_client = None
    assert (await request(app)).status_code == 503
    assert not app.state.ranked_analysis_activity._temporary


@pytest.mark.asyncio
async def test_move_during_analysis_returns_snapshot_marked_stale_without_holding_lock(lobby):
    app, session, engine, _ = lobby
    node = session.katrain.game.current_node

    async def move():
        assert session.lock.acquire(blocking=False)
        try:
            session.katrain.game.current_node = node.play(Move((1, 0), "B"))
        finally:
            session.lock.release()
        assert not app.state.ranked_analysis_activity.reserve_ranked_start(11)

    engine.during_analysis = move
    response = await request(app)
    assert response.status_code == 200
    assert response.json()["stale"] is True
    assert response.json()["current_node_id"] == id(node)
    assert response.json()["move_count"] == 0
    assert not app.state.ranked_analysis_activity._temporary


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change,expected",
    [
        (lambda app, s: setattr(s.katrain.game, "terminal", SimpleNamespace(result="W+R")), 409),
        (lambda app, s: setattr(s.katrain, "pvp_lobby_awaiting_count", True), 409),
        (lambda app, s: setattr(s, "player_b_id", 44), 403),
        (lambda app, s: app.state.session_manager._sessions.pop(s.session_id), 404),
        (lambda app, s: setattr(app.state, "ai_ladder_repo", SimpleNamespace(get_pending_game=lambda uid: {})), 403),
    ],
)
async def test_reauthorizes_after_analysis_and_does_not_expose_old_result(lobby, change, expected):
    app, session, engine, _ = lobby

    async def changed():
        change(app, session)

    engine.during_analysis = changed
    response = await request(app)
    assert response.status_code == expected
    assert "ownership" not in response.json()
    assert not app.state.ranked_analysis_activity._temporary


@pytest.mark.asyncio
async def test_pending_ranked_game_denies_before_engine(lobby):
    app, _, engine, _ = lobby
    app.state.ai_ladder_repo = SimpleNamespace(get_pending_game=lambda uid: {})
    assert (await request(app)).status_code == 403
    assert not engine.calls


@pytest.mark.asyncio
async def test_singleflight_and_cancellation_release_all_request_activity(lobby):
    app, _, engine, _ = lobby
    started, finish = asyncio.Event(), asyncio.Event()

    async def block():
        started.set()
        await finish.wait()

    engine.during_analysis = block
    first = asyncio.create_task(request(app))
    await asyncio.wait_for(started.wait(), timeout=2)
    try:
        assert (await request(app)).status_code == 409
        assert len(engine.calls) == 1
    finally:
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
    assert not app.state.ranked_analysis_activity._temporary
    engine.during_analysis = None
    assert (await request(app)).status_code == 200


@pytest.mark.asyncio
async def test_real_multiplayer_runtime_is_authorized_and_state_stays_unchanged(lobby, monkeypatch):
    from katrain.web import session as session_module

    app, _, engine, _ = lobby
    # The shared conftest stubs interface.py; load its real runtime under a private name.
    name = "katrain.web._pvp_territory_test_interface"
    spec = importlib.util.spec_from_file_location(name, Path(session_module.__file__).with_name("interface.py"))
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)

    def runtime(**kwargs):
        instance = module.WebKaTrain(force_package_config=True, enable_engine=False)
        instance.save_config = lambda *_args, **_kwargs: None
        return instance

    monkeypatch.setattr(session_module, "WebKaTrain", runtime)
    session = app.state.session_manager.create_multiplayer_session(
        11,
        22,
        b_name="Black",
        w_name="White",
        skip_initial_analysis=True,
    )
    engine.result = {"ownership": [0] * 361}
    before = session.katrain.get_state()
    response = await request(app, session_id=session.session_id)
    assert response.status_code == 200, response.text
    assert response.json()["game_id"] == before["game_id"]
    assert response.json()["current_node_id"] == before["current_node_id"]
    after = session.katrain.get_state()
    assert {key: after[key] for key in ("analysis", "terminal_result", "awaiting_count", "timer")} == {
        key: before[key] for key in ("analysis", "terminal_result", "awaiting_count", "timer")
    }
    assert session.last_state["analysis"] == before["analysis"]
