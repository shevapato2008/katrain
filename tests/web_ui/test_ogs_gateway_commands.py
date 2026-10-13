"""OGS commands commit only after the platform confirms the exact action."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.core.game import IllegalMoveException
from katrain.web.platforms.gateway import PlatformCommandGateway, PlatformMoveRejectedError
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import GamePhase, PlatformGameContext, PlatformGameSnapshot, PlatformMove
from katrain.web.api.v1.endpoints.auth import get_current_user, get_current_user_optional, require_writable_user
from katrain.web.models import User
from katrain.web.server import create_app
from katrain.web.session import WebSession


class Game:
    board_size = (9, 9)

    def __init__(self):
        self.board = {}
        self.chains = {}
        self.last_capture = []
        self.prisoners = []
        self.current_node = SimpleNamespace(next_player="B")
        self.end_result = None

    def _validate_move_and_update_chains(self, move, ignore_ko=False):
        if move.coords is not None and move.coords in self.board:
            raise IllegalMoveException("occupied")
        if move.coords is not None:
            self.board[move.coords] = move.player


class Kat:
    def __init__(self):
        self.game = Game()
        self.calls = []

    def __call__(self, action, **kwargs):
        self.calls.append((action, kwargs))
        if action == "play":
            coords = kwargs["coords"]
            if coords is not None:
                self.game.board[coords] = self.game.current_node.next_player
            self.game.current_node = SimpleNamespace(
                next_player="W" if self.game.current_node.next_player == "B" else "B"
            )


class Sessions:
    def __init__(self):
        self.session = SimpleNamespace(session_id="local", user_id=7, katrain=Kat(), lock=__import__("threading").RLock())
        self.broadcasts = []

    def get_session(self, session_id):
        assert session_id == "local"
        return self.session

    def broadcast_to_session(self, session_id, message):
        self.broadcasts.append((session_id, message))


class Adapter:
    platform_name = "ogs"
    supports_scoring = True
    is_connected = True

    def __init__(self):
        self.snapshot = PlatformGameSnapshot("42", 9, (), (), GamePhase.PLAYING)
        self.sent = []
        self.on_submit = None
        self.on_fetch = None
        self.pending_id = None

    def pending_direct_challenge_id(self):
        return self.pending_id

    async def submit_move(self, game_id, col, row):
        self.sent.append(("move", game_id, col, row))
        if self.on_submit:
            await self.on_submit()
        return True

    async def submit_pass(self, game_id):
        self.sent.append(("pass", game_id))
        if self.on_submit:
            await self.on_submit()
        return True

    async def resign(self, game_id):
        self.sent.append(("resign", game_id))

    def get_game_snapshot(self, game_id):
        assert game_id == "42"
        return self.snapshot

    async def fetch_game_snapshot(self, game_id):
        self.sent.append(("snapshot", game_id))
        if self.on_fetch:
            await self.on_fetch()

    async def submit_scoring_action(self, game_id, action):
        self.sent.append(("score", game_id, action))
        return True


def bridge():
    sessions = Sessions()
    pm = PlatformManager(sessions)
    adapter = Adapter()
    pm.register_adapter(adapter)
    ctx = PlatformGameContext(session_id="local", platform="ogs", remote_game_id="42", my_color="B")
    pm._active_games["42"] = ctx
    pm._session_to_game["local"] = "42"
    return PlatformCommandGateway(pm, sessions), pm, adapter, ctx, sessions


@pytest.mark.asyncio
async def test_send_does_not_commit_until_exact_own_echo():
    gateway, pm, adapter, ctx, sessions = bridge()
    task = asyncio.create_task(gateway.play_move("local", 2, 3, 7))
    await asyncio.sleep(0)
    assert adapter.sent == [("move", "42", 2, 3)]
    assert sessions.session.katrain.calls == []
    assert ctx.is_pending

    move = PlatformMove(2, 3, "B", 1, "42")
    adapter.snapshot = PlatformGameSnapshot("42", 9, (), (move,), GamePhase.PLAYING)
    await pm._on_opponent_move(move)
    assert await task == {"status": "ok"}
    assert sessions.session.katrain.calls == [("play", {"coords": (2, 3)})]
    assert not ctx.is_pending


@pytest.mark.asyncio
async def test_ogs_can_resume_after_two_pass_scoring_rejected():
    gateway, pm, adapter, ctx, sessions = bridge()
    # KaTrain derives a local end_result from two passes. OGS can still
    # reject scoring and return the same remote game to play.
    sessions.session.katrain.game.end_result = "board-game-end"
    ctx.game_phase = GamePhase.PLAYING
    task = asyncio.create_task(gateway.play_move("local", 2, 3, 7))
    await asyncio.sleep(0)
    assert adapter.sent == [("move", "42", 2, 3)]
    move = PlatformMove(2, 3, "B", 1, "42")
    adapter.snapshot = PlatformGameSnapshot("42", 9, (), (move,), GamePhase.PLAYING)
    await pm._on_opponent_move(move)
    assert await task == {"status": "ok"}


@pytest.mark.asyncio
async def test_missing_echo_reconciles_exact_move_from_snapshot(monkeypatch):
    monkeypatch.setattr("katrain.web.platforms.gateway.PLATFORM_ACK_TIMEOUT", 0.01)
    gateway, pm, adapter, ctx, sessions = bridge()

    async def fetch():
        move = PlatformMove(2, 3, "B", 1, "42")
        adapter.snapshot = PlatformGameSnapshot("42", 9, (), (move,), GamePhase.PLAYING)
        sessions.session.katrain("play", coords=(2, 3))
        ctx.last_confirmed_move = 1
        ctx.clear_pending()

    adapter.on_fetch = fetch
    assert await gateway.play_move("local", 2, 3, 7) == {"status": "ok"}
    assert adapter.sent == [("move", "42", 2, 3), ("snapshot", "42")]
    assert len(sessions.session.katrain.calls) == 1


@pytest.mark.asyncio
async def test_mismatched_snapshot_never_confirms_or_replays_locally(monkeypatch):
    monkeypatch.setattr("katrain.web.platforms.gateway.PLATFORM_ACK_TIMEOUT", 0.01)
    gateway, pm, adapter, ctx, sessions = bridge()

    async def fetch():
        adapter.snapshot = PlatformGameSnapshot("42", 9, (), (PlatformMove(4, 4, "B", 1, "42"),), GamePhase.PLAYING)
        ctx.last_confirmed_move = 1
        ctx.clear_pending()

    adapter.on_fetch = fetch
    with pytest.raises(PlatformMoveRejectedError):
        await gateway.play_move("local", 2, 3, 7)
    assert sessions.session.katrain.calls == []
    assert adapter.sent == [("move", "42", 2, 3), ("snapshot", "42")]


@pytest.mark.asyncio
async def test_unresolved_send_stays_pending_without_blind_retry(monkeypatch):
    monkeypatch.setattr("katrain.web.platforms.gateway.PLATFORM_ACK_TIMEOUT", 0.01)
    gateway, pm, adapter, ctx, sessions = bridge()
    with pytest.raises(PlatformMoveRejectedError):
        await gateway.play_move("local", 2, 3, 7)
    assert ctx.is_pending
    with pytest.raises(PlatformMoveRejectedError) as err:
        await gateway.play_move("local", 2, 3, 7)
    assert err.value.reason == "pending"
    assert adapter.sent == [("move", "42", 2, 3), ("snapshot", "42")]
    assert sessions.session.katrain.calls == []


@pytest.mark.asyncio
async def test_late_matching_echo_clears_timeout_resync_guard(monkeypatch):
    monkeypatch.setattr("katrain.web.platforms.gateway.PLATFORM_ACK_TIMEOUT", 0.01)
    gateway, pm, adapter, ctx, sessions = bridge()
    with pytest.raises(PlatformMoveRejectedError):
        await gateway.play_move("local", 2, 3, 7)
    assert ctx.needs_resync and ctx.is_pending

    move = PlatformMove(2, 3, "B", 1, "42")
    adapter.snapshot = PlatformGameSnapshot("42", 9, (), (move,), GamePhase.PLAYING)
    await pm._on_opponent_move(move)

    assert not ctx.needs_resync
    assert not ctx.is_pending
    assert sessions.session.katrain.calls == [("play", {"coords": (2, 3)})]


@pytest.mark.asyncio
async def test_out_of_turn_and_illegal_moves_are_not_sent():
    gateway, pm, adapter, ctx, sessions = bridge()
    sessions.session.katrain.game.current_node.next_player = "W"
    with pytest.raises(PlatformMoveRejectedError):
        await gateway.play_move("local", 2, 3, 7)
    sessions.session.katrain.game.current_node.next_player = "B"
    sessions.session.katrain.game.board[(2, 3)] = "W"
    with pytest.raises(PlatformMoveRejectedError) as err:
        await gateway.play_move("local", 2, 3, 7)
    assert err.value.reason == "illegal_move"
    assert adapter.sent == []


@pytest.mark.asyncio
async def test_resign_uses_remote_authority_and_keeps_local_game_open():
    gateway, pm, adapter, ctx, sessions = bridge()
    result = await gateway.resign("local", 7)
    assert result == {"status": "pending"}
    assert adapter.sent == [("resign", "42")]
    assert sessions.session.katrain.calls == []
    assert sessions.session.katrain.game.end_result is None


@pytest.mark.asyncio
async def test_pass_also_waits_for_ogs_echo():
    gateway, pm, adapter, ctx, sessions = bridge()
    task = asyncio.create_task(gateway.pass_move("local", 7))
    await asyncio.sleep(0)
    assert sessions.session.katrain.calls == []
    move = PlatformMove(-1, -1, "B", 1, "42")
    adapter.snapshot = PlatformGameSnapshot("42", 9, (), (move,), GamePhase.PLAYING)
    await pm._on_opponent_move(move)
    assert await task == {"status": "ok"}
    assert sessions.session.katrain.calls == [("play", {"coords": None})]


@pytest.mark.asyncio
async def test_scoring_requires_remote_scoring_phase():
    gateway, pm, adapter, ctx, sessions = bridge()
    with pytest.raises(PlatformMoveRejectedError):
        await gateway.scoring_action("local", 7, "accept", "")
    ctx.game_phase = GamePhase.SCORING
    assert await gateway.scoring_action("local", 7, "reject", "") == {"status": "pending"}
    assert adapter.sent == [("score", "42", {"action": "reject"})]


@pytest.mark.asyncio
async def test_scoring_action_blocks_contradictory_second_send_until_phase_changes():
    gateway, pm, adapter, ctx, sessions = bridge()
    ctx.game_phase = GamePhase.SCORING
    assert await gateway.scoring_action("local", 7, "accept", "") == {"status": "pending"}
    with pytest.raises(PlatformMoveRejectedError) as err:
        await gateway.scoring_action("local", 7, "reject", "")
    assert err.value.reason == "pending"
    assert adapter.sent == [("score", "42", {"action": "accept", "stones": ""})]
    await pm._on_game_phase_changed("42", GamePhase.PLAYING)
    assert not ctx.is_pending


def http_bridge():
    app = create_app(enable_engine=False)
    pm = PlatformManager(app.state.session_manager)
    adapter = Adapter()
    pm.register_adapter(adapter)
    pm._platform_user_ids["ogs"] = 7
    app.state.platform_manager = pm
    app.state.platform_gateway = PlatformCommandGateway(pm, app.state.session_manager)
    katrain = MagicMock()
    katrain.game_type = "pvp_online"
    katrain.game.end_result = None
    katrain.get_state.return_value = {"end_result": None}
    session = WebSession(session_id="local", katrain=katrain, user_id=7, player_b_id=7, player_w_id=-1)
    session.game_type = "pvp_online"
    app.state.session_manager._sessions["local"] = session
    ctx = PlatformGameContext(session_id="local", platform="ogs", remote_game_id="42", my_color="B")
    pm._active_games["42"] = ctx
    pm._session_to_game["local"] = "42"
    app.dependency_overrides[get_current_user] = lambda: User(id=7, username="owner")
    app.dependency_overrides[get_current_user_optional] = lambda: User(id=7, username="owner")
    app.dependency_overrides[require_writable_user] = lambda: User(id=7, username="owner")
    return app, pm, adapter, session, ctx


@pytest.mark.asyncio
async def test_online_resign_http_returns_pending_without_local_result_or_record():
    app, pm, adapter, session, ctx = http_bridge()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/resign", json={"session_id": "local"})
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert adapter.sent == [("resign", "42")]
    session.katrain.assert_not_called()
    assert session.katrain.game.end_result is None


@pytest.mark.asyncio
async def test_active_game_endpoint_is_owner_scoped():
    app, pm, adapter, session, ctx = http_bridge()
    adapter.pending_id = "challenge-4"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/platforms/ogs/active-game")
        assert response.status_code == 200
        assert response.json() == {"session_id": "local", "pending_challenge_id": "challenge-4"}
        pm._platform_user_ids["ogs"] = 8
        denied = await client.get("/api/v1/platforms/ogs/active-game")
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_disconnected_active_game_is_error_not_false_empty():
    app, pm, adapter, session, ctx = http_bridge()
    adapter.is_connected = False
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/platforms/ogs/active-game")
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_scoring_endpoint_rejects_non_scoring_then_relays_decision():
    app, pm, adapter, session, ctx = http_bridge()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        blocked = await client.post("/api/v1/platforms/ogs/scoring", json={"session_id": "local", "action": "reject"})
        assert blocked.status_code == 409
        ctx.game_phase = GamePhase.SCORING
        accepted = await client.post("/api/v1/platforms/ogs/scoring", json={"session_id": "local", "action": "reject"})
        assert accepted.status_code == 200
        assert accepted.json() == {"status": "pending"}
    assert adapter.sent == [("score", "42", {"action": "reject"})]
