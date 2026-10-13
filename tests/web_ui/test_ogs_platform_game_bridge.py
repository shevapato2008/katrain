"""Verified local session foundation for an OGS game (no guessed live protocol)."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user, get_current_user_optional
from katrain.web.models import User
from katrain.web.platforms.gateway import PlatformCommandGateway
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import OnlineUser, PlatformGameContext, PlatformGameSession, TimeControl
from katrain.web.platforms.ogs.adapter import OGSAdapter
from katrain.web.server import create_app
from katrain.web.session import SessionManager, WebSession


def _game(**overrides):
    fields = dict(
        platform="ogs",
        game_id="ogs-42",
        board_size=13,
        my_color="W",
        opponent=OnlineUser(platform="ogs", user_id="88", username="opponent", rank="4k", rank_numeric=-4),
        time_control=TimeControl(system="fischer", main_time=600),
        rules="japanese",
        ranked=False,
        handicap=2,
        komi=6.5,
    )
    fields.update(overrides)
    return PlatformGameSession(**fields)


def _ogs_data(**overrides):
    data = dict(
        width=19,
        height=19,
        players={
            "black": {"id": 7, "username": "owner", "ranking": 30},
            "white": {"id": 8, "username": "opponent", "ranking": 20},
        },
        time_control={"system": "fischer", "main_time": 600},
        rules="japanese",
        handicap=0,
        komi=6.5,
        phase="play",
        moves=[],
        initial_state={"black": "", "white": ""},
    )
    data.update(overrides)
    return data


class FakeKatrain:
    def __init__(self):
        self.calls = []

    def __call__(self, action, **kwargs):
        self.calls.append((action, kwargs))


class FakeSessions:
    def __init__(self):
        self._sessions = {}
        self.create_calls = []

    def create_multiplayer_session(self, **kwargs):
        self.create_calls.append(kwargs)
        session = SimpleNamespace(
            session_id=f"local-{len(self.create_calls)}",
            user_id=next(i for i in (kwargs["player_b_id"], kwargs["player_w_id"]) if i >= 0),
            player_b_id=kwargs["player_b_id"],
            player_w_id=kwargs["player_w_id"],
            katrain=FakeKatrain(),
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id):
        return self._sessions[session_id]

    def remove_session(self, session_id):
        self._sessions.pop(session_id, None)


@pytest.mark.parametrize("initial_type", ["free", "pvp_online"])
def test_multiplayer_session_initial_type_is_optional_and_forwarded(monkeypatch, initial_type):
    manager = SessionManager(enable_engine=False)
    seen = []

    class FakeKatrain:
        deliver_analysis = False

        def __call__(self, *args, **kwargs):
            pass

    def fake_create_session(**kwargs):
        seen.append(kwargs)
        from katrain.web.session import WebSession

        return WebSession(session_id="local", katrain=FakeKatrain(), user_id=kwargs["user_id"])

    monkeypatch.setattr(manager, "create_session", fake_create_session)
    kwargs = {"initial_game_type": initial_type} if initial_type != "free" else {}
    session = manager.create_multiplayer_session(7, -1, **kwargs)

    assert session.user_id == 7
    assert session.game_type == initial_type
    assert seen[0]["initial_game_type"] == initial_type


def test_multiplayer_online_session_does_not_reenable_analysis(monkeypatch):
    manager = SessionManager(enable_engine=False)
    katrain = SimpleNamespace(deliver_analysis=False)

    def fake_create_session(**kwargs):
        return WebSession(session_id="local", katrain=katrain, user_id=kwargs["user_id"])

    monkeypatch.setattr(manager, "create_session", fake_create_session)
    manager.create_multiplayer_session(7, -1, initial_game_type="pvp_online")

    assert katrain.deliver_analysis is False


def test_online_session_suppresses_analysis_before_game_start(monkeypatch):
    observed = []

    class FakeWebKaTrain:
        def __init__(self, **kwargs):
            self.deliver_analysis = None

        def start(self, **kwargs):
            observed.append((self.deliver_analysis, kwargs))

        def get_state(self):
            return {}

        def __call__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("katrain.web.session.WebKaTrain", FakeWebKaTrain)
    manager = SessionManager(enable_engine=False)
    manager.create_multiplayer_session(7, -1, initial_game_type="pvp_online", skip_initial_analysis=True)

    assert observed == [(False, {"game_type": "pvp_online", "skip_initial_analysis": True})]


def test_real_webkatrain_disallows_online_pvp_analysis():
    # tests/web_ui/conftest.py deliberately stubs katrain.web.interface, so
    # load its source under a separate name to test the real class contract.
    source = Path(__file__).resolve().parents[2] / "katrain/web/interface.py"
    spec = importlib.util.spec_from_file_location("_ogs_real_interface", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    katrain = object.__new__(module.WebKaTrain)
    katrain.game_type = "pvp_online"

    assert "pvp_online" in module.WebKaTrain.GAME_TYPES
    assert katrain.analysis_allowed is False


@pytest.mark.asyncio
@pytest.mark.parametrize("my_color", ["B", "W"])
async def test_ogs_game_connection_requires_logged_in_player_in_exactly_one_seat(my_color):
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(user_id=7, get_game=AsyncMock(return_value=_ogs_data()))
    adapter._rt = SimpleNamespace(game_connect=AsyncMock())
    adapter._register_game_events = MagicMock()
    if my_color == "W":
        adapter._rest.get_game.return_value = _ogs_data(
            players={
                "black": {"id": 8, "username": "opponent", "ranking": 20},
                "white": {"id": 7, "username": "owner", "ranking": 30},
            }
        )

    session = await adapter._connect_to_game(42)

    assert session.my_color == my_color
    assert session.board_size == 19
    assert session.opponent.user_id == "8"


@pytest.mark.asyncio
async def test_ogs_game_subscribes_before_fetching_snapshot_to_avoid_event_gap():
    adapter = OGSAdapter()
    order = []

    async def game_connect(game_id):
        order.append("subscribed")

    async def get_game(game_id):
        order.append("snapshot")
        return _ogs_data()

    adapter._rest = SimpleNamespace(user_id=7, get_game=get_game)
    adapter._rt = SimpleNamespace(game_connect=game_connect)
    adapter._register_game_events = MagicMock()

    await adapter._connect_to_game(42)

    assert order == ["subscribed", "snapshot"]


@pytest.mark.asyncio
async def test_ogs_game_connection_preserves_early_realtime_data_for_later_reconciliation():
    adapter = OGSAdapter()

    async def game_connect(game_id):
        adapter._game_data[game_id] = {
            "moves": [[3, 3]],
            "phase": "play",
            "players": {"black": {"id": 9}, "white": {"id": 10}},
            "handicap": 9,
        }

    adapter._rest = SimpleNamespace(user_id=7, get_game=AsyncMock(return_value=_ogs_data()))
    adapter._rt = SimpleNamespace(game_connect=game_connect)
    adapter._register_game_events = MagicMock()

    await adapter._connect_to_game(42)

    assert adapter._game_data[42]["moves"] == [[3, 3]]
    assert adapter._game_data[42]["players"]["black"]["id"] == 7
    assert adapter._game_data[42]["handicap"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data,user_id",
    [
        (_ogs_data(width=19, height=13), 7),
        (_ogs_data(width=11, height=11), 7),
        (_ogs_data(height=None), 7),
        (_ogs_data(), None),
        (_ogs_data(), 9),
        (_ogs_data(players={"black": {"id": 7}, "white": {}}), 7),
        (_ogs_data(players={"black": {"id": 7}, "white": {"id": 7}}), 7),
    ],
)
async def test_ogs_game_connection_rejects_unsupported_board_or_unverified_seat(data, user_id):
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(user_id=user_id, get_game=AsyncMock(return_value=data))
    adapter._rt = SimpleNamespace(game_connect=AsyncMock())
    adapter._register_game_events = MagicMock()

    with pytest.raises(ValueError):
        await adapter._connect_to_game(42)

    assert adapter._active_game_id is None
    assert adapter._game_data == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["undo", "redo", "edit-game", "new-game"])
async def test_generic_mutation_endpoints_reject_real_platform_session(endpoint):
    app = create_app(enable_engine=False)
    app.state.platform_manager = PlatformManager(app.state.session_manager)
    app.state.platform_gateway = PlatformCommandGateway(app.state.platform_manager, app.state.session_manager)
    katrain = MagicMock()
    katrain.game_type = "pvp_online"
    katrain.get_state.return_value = {"end_result": None, "history": []}
    session = WebSession(session_id="ogs-session", katrain=katrain, user_id=7, player_b_id=7, player_w_id=-1)
    app.state.session_manager._sessions[session.session_id] = session
    app.state.platform_manager._active_games["ogs-42"] = PlatformGameContext(
        session_id=session.session_id, platform="ogs", remote_game_id="ogs-42"
    )
    app.state.platform_manager._session_to_game[session.session_id] = "ogs-42"
    user = User(id=7, username="owner")
    app.dependency_overrides[get_current_user_optional] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/{endpoint}", json={"session_id": session.session_id})

    assert response.status_code == 409
    katrain.assert_not_called()


@pytest.mark.asyncio
async def test_undo_for_unmapped_free_session_retains_existing_behavior():
    app = create_app(enable_engine=False)
    katrain = MagicMock()
    katrain.game_type = "free"
    katrain.get_state.return_value = {"end_result": None, "history": []}
    session = WebSession(session_id="free-session", katrain=katrain, user_id=7)
    app.state.session_manager._sessions[session.session_id] = session
    user = User(id=7, username="owner")
    app.dependency_overrides[get_current_user_optional] = lambda: user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/undo", json={"session_id": session.session_id})

    assert response.status_code == 200
    katrain.assert_called_once_with("undo", 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("color,expected_seats", [("B", (7, -1)), ("W", (-1, 7))])
async def test_platform_game_uses_remote_settings_online_type_and_owner(color, expected_seats):
    sessions = FakeSessions()
    manager = PlatformManager(sessions)

    session_id = await manager.start_platform_game("ogs", _game(my_color=color), user_id=7)

    session = sessions.get_session(session_id)
    assert session.user_id == 7
    assert (session.player_b_id, session.player_w_id) == expected_seats
    assert sessions.create_calls[0]["initial_game_type"] == "pvp_online"
    assert sessions.create_calls[0]["skip_initial_analysis"] is True
    assert session.katrain.calls == [
        ("edit_game", {"size": 13, "rules": "japanese", "handicap": 2, "komi": 6.5})
    ]
    assert manager.get_game_context(session_id).remote_game_id == "ogs-42"


@pytest.mark.asyncio
async def test_repeated_remote_game_start_reuses_one_local_session():
    sessions = FakeSessions()
    manager = PlatformManager(sessions)

    first, second = await asyncio.gather(
        manager.start_platform_game("ogs", _game(), user_id=7),
        manager.start_platform_game("ogs", _game(), user_id=7),
    )

    assert first == second
    assert len(sessions._sessions) == 1
    assert len(manager._session_to_game) == 1


@pytest.mark.asyncio
async def test_existing_remote_game_cannot_be_claimed_by_another_owner():
    manager = PlatformManager(FakeSessions())
    await manager.start_platform_game("ogs", _game(), user_id=7)

    with pytest.raises(ValueError, match="different local user"):
        await manager.start_platform_game("ogs", _game(), user_id=8)


@pytest.mark.asyncio
async def test_missing_existing_local_session_does_not_create_blank_replacement():
    sessions = FakeSessions()
    manager = PlatformManager(sessions)
    session_id = await manager.start_platform_game("ogs", _game(), user_id=7)
    sessions.remove_session(session_id)

    with pytest.raises(RuntimeError, match="snapshot recovery"):
        await manager.start_platform_game("ogs", _game(), user_id=7)

    assert len(sessions.create_calls) == 1


@pytest.mark.asyncio
async def test_failed_local_configuration_cleans_up_session_and_mapping():
    sessions = FakeSessions()
    manager = PlatformManager(sessions)
    original_create = sessions.create_multiplayer_session

    def create_that_fails_on_edit(**kwargs):
        session = original_create(**kwargs)

        def failed_edit(action, **settings):
            raise RuntimeError("cannot configure local board")

        session.katrain = failed_edit
        return session

    sessions.create_multiplayer_session = create_that_fails_on_edit

    with pytest.raises(RuntimeError, match="cannot configure"):
        await manager.start_platform_game("ogs", _game(), user_id=7)

    assert sessions._sessions == {}
    assert manager._active_games == {}
    assert manager._session_to_game == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"board_size": 11},
        {"board_size": True},
        {"my_color": "?"},
        {"rules": "unknown"},
        {"handicap": -1},
        {"handicap": 10},
        {"komi": float("nan")},
        {"komi": None},
        {"game_id": ""},
        {"platform": "golaxy"},
    ],
)
async def test_invalid_remote_parameters_do_not_create_local_session(overrides):
    sessions = FakeSessions()
    manager = PlatformManager(sessions)

    with pytest.raises(ValueError):
        await manager.start_platform_game("ogs", _game(**overrides), user_id=7)

    assert sessions._sessions == {}
