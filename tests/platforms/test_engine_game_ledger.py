"""星阵人机局终局端点契约测试。"""

import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

import katrain.web.server as server
from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.models import User
from katrain.web.platforms.gateway import PlatformMoveRejectedError
from katrain.web.server import create_app
from katrain.web.session import WebSession

HUMAN = User(id=7, username="小明")


def _engine_session(end_result=None, human_color="B", engine=True):
    """构造星阵人机会话；engine=False 时构造同座位形状的 OGS 真人局。"""
    katrain = MagicMock()
    katrain.game_type = "free"
    katrain.analysis_allowed = True
    katrain.get_state.return_value = {"end_result": end_result, "player_to_move": human_color, "history": []}
    katrain.game.end_result = end_result
    if engine:
        katrain.platform_engine_color = "W" if human_color == "B" else "B"
    session = WebSession(session_id="eng-1", katrain=katrain, lock=threading.Lock())
    session.user_id = HUMAN.id
    session.player_b_id = HUMAN.id if human_color == "B" else -1
    session.player_w_id = HUMAN.id if human_color == "W" else -1
    return session


def _gateway(is_engine=True):
    gw = MagicMock()
    gw.is_platform_game.return_value = True
    gw.is_engine_game.return_value = is_engine
    gw.play_move = AsyncMock()
    gw.pass_move = AsyncMock()
    gw.resign = AsyncMock(return_value={"status": "ok"})
    return gw


def _app(session, gateway):
    app = create_app(enable_engine=False)
    app.state.session_manager._sessions[session.session_id] = session
    app.state.session_manager._schedule_broadcast = MagicMock()
    app.state.platform_gateway = gateway
    app.state.game_repo = MagicMock()
    app.dependency_overrides[get_current_user_optional] = lambda: HUMAN
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestMoveWhenTheEngineEndsTheGame:
    async def test_game_ended_returns_the_ended_state_not_409(self):
        session = _engine_session(end_result="Void")
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("AI returned non-move coord 361", reason="game_ended")
        app = _app(session, gw)

        async with _client(app) as ac:
            response = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert response.status_code == 200, response.text
        assert response.json()["state"]["end_result"] == "Void"
        assert session.last_state["end_result"] == "Void"

    async def test_other_rejections_are_still_409(self):
        session = _engine_session()
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("tunnel down", reason="engine_error")
        app = _app(session, gw)

        async with _client(app) as ac:
            response = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert response.status_code == 409
        assert response.json()["detail"] == "tunnel down"

    async def test_consecutive_pass_terminal_returns_the_ended_state(self):
        session = _engine_session(end_result="终局")
        gw = _gateway()
        gw.pass_move.side_effect = PlatformMoveRejectedError("Engine game ended", reason="game_ended")
        app = _app(session, gw)

        async with _client(app) as ac:
            response = await ac.post("/api/move", json={"session_id": session.session_id, "pass_move": True})

        assert response.status_code == 200, response.text
        gw.pass_move.assert_awaited_once()
        assert response.json()["state"]["end_result"] == "终局"


class TestAfterTheEngineGameEnded:
    async def test_a_move_still_goes_to_the_gateway_and_gets_the_ended_state(self):
        session = _engine_session(end_result="W+R")
        gw = _gateway()
        gw.is_platform_game.return_value = False
        gw.play_move.side_effect = PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
        app = _app(session, gw)

        async with _client(app) as ac:
            response = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert response.status_code == 200, response.text
        gw.play_move.assert_awaited_once()
        assert [call.args[0] for call in session.katrain.call_args_list] == []

    async def test_resigning_again_changes_nothing_and_records_nothing(self):
        session = _engine_session(end_result="W+R")
        gw = _gateway()
        gw.is_platform_game.return_value = False
        gw.resign.side_effect = PlatformMoveRejectedError("This engine game has already ended", reason="game_ended")
        app = _app(session, gw)

        async with _client(app) as ac:
            response = await ac.post("/api/resign", json={"session_id": session.session_id})

        assert response.status_code == 200, response.text
        assert response.json()["state"]["end_result"] == "W+R"
        gw.resign.assert_awaited_once()
        assert [call.args[0] for call in session.katrain.call_args_list] == []
        app.state.game_repo.record_multiplayer_game.assert_not_called()
        assert app.state.session_manager._schedule_broadcast.call_args_list == []


class TestMoveLedger:
    async def test_ai_terminal_move_is_recorded_for_the_requesting_user(self, monkeypatch):
        session = _engine_session(end_result="Void")
        gw = _gateway()
        gw.play_move.side_effect = PlatformMoveRejectedError("AI returned non-move coord 361", reason="game_ended")
        app = _app(session, gw)
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        async with _client(app) as ac:
            response = await ac.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

        assert response.status_code == 200, response.text
        recorder.assert_awaited_once()
        assert recorder.await_args.args[0] is session
        assert recorder.await_args.args[2].id == HUMAN.id


class TestResignLedger:
    async def test_engine_resign_goes_through_the_ai_game_ledger(self, monkeypatch):
        session = _engine_session(end_result="W+R")
        gw = _gateway(is_engine=True)

        async def _resign_drops_context(*_args, **_kwargs):
            gw.is_engine_game.return_value = False
            gw.is_platform_game.return_value = False
            return {"status": "ok"}

        gw.resign.side_effect = _resign_drops_context
        app = _app(session, gw)
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        async with _client(app) as ac:
            response = await ac.post("/api/resign", json={"session_id": session.session_id})

        assert response.status_code == 200, response.text
        recorder.assert_awaited_once()
        assert recorder.await_args.args[0] is session
        assert recorder.await_args.args[2].id == HUMAN.id
        app.state.game_repo.record_multiplayer_game.assert_not_called()
        sent = [call.args[1] for call in app.state.session_manager._schedule_broadcast.call_args_list]
        assert any(message.get("type") == "game_end" for message in sent)

    async def test_non_engine_platform_resign_still_uses_the_multiplayer_repo(self, monkeypatch):
        session = _engine_session(end_result="W+R", engine=False)
        app = _app(session, _gateway(is_engine=False))
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        async with _client(app) as ac:
            response = await ac.post("/api/resign", json={"session_id": session.session_id})

        assert response.status_code == 200, response.text
        recorder.assert_not_awaited()
        app.state.game_repo.record_multiplayer_game.assert_called_once()


class TestRecordPlatformEngineGame:
    @staticmethod
    def _session(end_result, human_color="B", engine=True):
        session = _engine_session(end_result=end_result, human_color=human_color, engine=engine)
        me = SimpleNamespace(name="Me", human=False, ai=False, calculated_rank=None, sgf_rank=None)
        bot = SimpleNamespace(name="[golaxy] 星铠虾", human=False, ai=False, calculated_rank="2段", sgf_rank=None)
        session.katrain.players_info = {"B": me, "W": bot} if human_color == "B" else {"B": bot, "W": me}
        return session

    async def test_human_seat_gets_the_account_name_and_source_is_play_ai(self, monkeypatch):
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)
        session, app = self._session("W+R"), MagicMock()

        await server._record_platform_engine_game(session, app, HUMAN)

        record.assert_awaited_once()
        assert record.await_args.args == (session, app, HUMAN, "W+R")
        assert record.await_args.kwargs["data_overrides"] == {
            "source": "play_ai",
            "player_black": "小明",
            "player_white": "[golaxy] 星铠虾",
        }

    async def test_human_on_white_gets_the_name_on_white(self, monkeypatch):
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)

        await server._record_platform_engine_game(self._session("B+R", human_color="W"), MagicMock(), HUMAN)

        overrides = record.await_args.kwargs["data_overrides"]
        assert (overrides["player_black"], overrides["player_white"]) == ("[golaxy] 星铠虾", "小明")

    async def test_nothing_is_written_without_a_result_or_a_user(self, monkeypatch):
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)

        await server._record_platform_engine_game(self._session(None), MagicMock(), HUMAN)
        await server._record_platform_engine_game(self._session("W+R"), MagicMock(), None)

        record.assert_not_awaited()

    async def test_a_non_engine_platform_session_is_not_written(self, monkeypatch):
        record = AsyncMock()
        monkeypatch.setattr(server, "_RECORD_FN", record, raising=False)

        await server._record_platform_engine_game(self._session("W+R", engine=False), MagicMock(), HUMAN)

        record.assert_not_awaited()

    async def test_the_real_record_fn_writes_the_overrides_into_the_row(self):
        create_app(enable_engine=False)
        session = self._session("Void")
        session.katrain.get_sgf.return_value = "(;GM[1])"
        session.katrain.get_state.return_value = {
            "board_size": [19, 19],
            "history": [1, 2],
            "komi": 7.5,
            "ruleset": "chinese",
        }
        app = MagicMock()
        app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})

        await server._record_platform_engine_game(session, app, HUMAN)

        app.state.repository_dispatcher.user_games_create.assert_awaited_once()
        kwargs = app.state.repository_dispatcher.user_games_create.await_args.kwargs
        assert kwargs["user_id"] == HUMAN.id
        data = kwargs["data"]
        assert data["source"] == "play_ai"
        assert (data["player_black"], data["player_white"]) == ("小明", "[golaxy] 星铠虾")
        assert data["result"] == "Void"


class TestRecordOffRequest:
    async def test_records_for_the_session_owner(self, monkeypatch):
        session, app = _engine_session(end_result="Void"), MagicMock()
        app.state.user_repo = SimpleNamespace(
            get_user_by_id=lambda uid: {"id": uid, "username": "小明"} if uid == HUMAN.id else None
        )
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        await server._record_platform_engine_game_off_request(session, app)

        recorder.assert_awaited_once()
        recorded_session, recorded_app, owner = recorder.await_args.args
        assert recorded_session is session and recorded_app is app
        assert (owner.id, owner.username) == (HUMAN.id, "小明")

    async def test_an_unknown_owner_is_passed_as_none(self, monkeypatch):
        session, app = _engine_session(end_result="Void"), MagicMock()
        app.state.user_repo = SimpleNamespace(get_user_by_id=lambda uid: None)
        recorder = AsyncMock()
        monkeypatch.setattr(server, "_record_platform_engine_game", recorder)

        await server._record_platform_engine_game_off_request(session, app)

        assert recorder.await_args.args[2] is None
