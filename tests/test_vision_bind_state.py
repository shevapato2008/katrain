"""Bind a session to vision and assert the expected board is seeded from katrain state."""

import asyncio

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import vision


class FakeVision:
    def __init__(self):
        self.bound = None
        self.expected_stones = None
        self.expected_node_id = None

    def bind_session(self, sid):
        self.bound = sid

    def unbind_session(self):
        self.bound = None

    def set_expected_from_stones(self, stones, board_size=19, *, expected_node_id=None):
        self.expected_stones = stones
        self.expected_node_id = expected_node_id


class FakeKatrain:
    def __init__(self):
        self.clock_started = False

    def get_state(self):
        return {"stones": [["B", [3, 15], None, 1]], "board_size": [19, 19], "current_node_id": 4242}

    def start_clock(self):
        # 实体盘绑定就是「棋盘可用」那一刻,钟从这里起步(KaTrainWeb.start_clock 同语义:幂等)。
        if self.clock_started:
            return False
        self.clock_started = True
        return True


class FakeSession:
    def __init__(self):
        self.katrain = FakeKatrain()


class FakeManager:
    def get_session(self, sid):
        return FakeSession()


def _client(vision_obj, manager):
    app = FastAPI()
    app.include_router(vision.router, prefix="/vision")
    app.state.vision = vision_obj
    app.state.session_manager = manager
    return TestClient(app, raise_server_exceptions=False)


class TestVisionBind:
    def test_bind_seeds_expected_board_from_katrain_state(self):
        fake = FakeVision()
        c = _client(fake, FakeManager())
        r = c.post("/vision/bind", json={"session_id": "s1"})
        assert r.status_code == 200
        assert fake.bound == "s1"
        assert fake.expected_stones == [["B", [3, 15], None, 1]]
        assert fake.expected_node_id == 4242


class FakeOrchestrator:
    def __init__(self):
        self.bound = None
        self.unbound = False

    def on_bind(self, session_id, session):
        self.bound = session_id

    def on_unbind(self):
        self.unbound = True


class TestOrchestratorHooks:
    def test_bind_and_unbind_notify_orchestrator(self):
        fake_vision, orch = FakeVision(), FakeOrchestrator()
        c = _client(fake_vision, FakeManager())
        c.app.state.physical_play = orch
        assert c.post("/vision/bind", json={"session_id": "s1"}).status_code == 200
        assert orch.bound == "s1"
        assert c.post("/vision/unbind").status_code == 200
        assert orch.unbound is True


class TestVisionMoveQueueHygiene:
    """Review M1: /vision/bind and /vision/unbind both drain app.state.vision_move_queue
    (the queue route_vision_event feeds) if present, so a stale ConfirmedMove queued
    for a previous session can't cross into whatever session binds next."""

    def _client_with_queue(self):
        fake = FakeVision()
        c = _client(fake, FakeManager())
        c.app.state.vision_move_queue = asyncio.Queue()
        c.app.state.vision_move_queue.put_nowait({"stale": "move-for-old-session"})
        return c

    def test_bind_drains_stale_move_queue(self):
        c = self._client_with_queue()
        assert c.post("/vision/bind", json={"session_id": "s1"}).status_code == 200
        assert c.app.state.vision_move_queue.empty()

    def test_unbind_drains_stale_move_queue(self):
        c = self._client_with_queue()
        c.post("/vision/bind", json={"session_id": "s1"})
        c.app.state.vision_move_queue.put_nowait({"stale": "move-after-bind"})
        assert c.post("/vision/unbind").status_code == 200
        assert c.app.state.vision_move_queue.empty()

    def test_bind_without_queue_attribute_does_not_raise(self):
        fake = FakeVision()
        c = _client(fake, FakeManager())
        r = c.post("/vision/bind", json={"session_id": "s1"})
        assert r.status_code == 200


class _FakeRecoveryTracker:
    def __init__(self):
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1


class TestUnbindClearsEngineRecovery:
    """Task 7: an active engine_recovery episode belongs to the game being unbound
    from -- it must not survive into whatever session binds next."""

    def test_unbind_clears_engine_recovery_tracker(self):
        fake = FakeVision()
        c = _client(fake, FakeManager())
        tracker = _FakeRecoveryTracker()
        c.app.state.engine_recovery = tracker
        c.post("/vision/bind", json={"session_id": "s1"})
        assert c.post("/vision/unbind").status_code == 200
        assert tracker.clear_calls == 1

    def test_unbind_without_engine_recovery_attribute_does_not_raise(self):
        fake = FakeVision()
        c = _client(fake, FakeManager())
        assert c.post("/vision/unbind").status_code == 200


class FakeLed:
    def is_board_connected(self):
        return True


class TestStatusLed:
    def test_status_reports_led_connected(self):
        c = _client(FakeVision(), FakeManager())
        c.app.state.led = FakeLed()
        # FakeVision 缺 status 属性时按 vision=None 分支断言：
        c.app.state.vision = None
        r = c.get("/vision/status")
        assert r.status_code == 200
        assert r.json()["led_connected"] is True


def test_remote_bind_fetch_cannot_replace_a_newer_binding_or_auth_generation():
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.service import VisionService
    from katrain.web.core.pvp_box_bridge import PvpBoxBridge

    async def run(change_auth):
        svc = VisionService(VisionServiceConfig())
        svc._worker = MagicMock()
        a, b = FakeSession(), FakeSession()
        a.game_type = "pvp_lobby"
        a.last_state = {"game_id": "a", "board_size": [19, 19], "stones": [], "current_node_id": 1}
        sessions = {"a": a, "b": b}
        entered, returned = asyncio.Event(), asyncio.Event()
        room = SimpleNamespace(local_user_id=1)

        async def fetch(*_):
            entered.set()
            await returned.wait()
            return {"state": {**a.last_state, "current_node_id": 2}}

        bridge = SimpleNamespace(
            rooms=SimpleNamespace(for_local=lambda *_: room),
            fetch_state=fetch,
            newer_state=PvpBoxBridge.newer_state,
        )
        app = SimpleNamespace(
            state=SimpleNamespace(
                vision=svc,
                session_manager=SimpleNamespace(get_session=lambda sid: sessions[sid]),
                pvp_box_bridge=bridge,
                box_sso=SimpleNamespace(active_generation=1),
            )
        )
        request = SimpleNamespace(app=app)
        task = asyncio.create_task(
            vision.bind_session(request, vision.BindRequest(session_id="a"), SimpleNamespace(id=1))
        )
        await entered.wait()
        if change_auth:
            app.state.box_sso.active_generation = 2
        else:
            await vision.bind_session(request, vision.BindRequest(session_id="b"), None)
        epoch, revision = svc.binding_epoch, svc.expected_revision
        returned.set()
        with pytest.raises(HTTPException) as error:
            await task
        assert error.value.status_code == 409
        assert svc.binding_epoch == epoch and svc.expected_revision == revision
        assert svc.bound_session_id == (None if change_auth else "b")
        assert a.last_state["current_node_id"] == 1

    asyncio.run(run(False))
    asyncio.run(run(True))


def test_manual_expected_target_is_rejected_for_bound_authority():
    from types import SimpleNamespace
    from fastapi import HTTPException
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.service import VisionService

    svc = VisionService(VisionServiceConfig())
    svc.bind_session("bound", session=FakeSession())
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(vision=svc)))
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            vision.set_expected_board(request, vision.ExpectedBoardRequest(board=[[0] * 19 for _ in range(19)]))
        )
    assert error.value.status_code == 409


def test_central_receive_source_is_fixed_before_await_and_renewed_only_for_next_receive():
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.service import VisionService
    from katrain.web.core.physical_play import PhysicalPlayConfig
    from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator
    from katrain.web.core.pvp_box_bridge import PvpBoxBridge
    from katrain.web.server import _apply_pvp_box_state, _receive_box_pvp_message

    async def run():
        svc = VisionService(VisionServiceConfig())
        svc._worker = MagicMock()
        session = FakeSession()
        session.katrain.update_state_callback = None
        session.game_type = "pvp_lobby"
        session.last_state = {**session.katrain.get_state(), "game_id": "room-game", "current_node_index": 0}
        manager = SimpleNamespace(get_session=lambda _: session)
        orch = PhysicalPlayOrchestrator(config=PhysicalPlayConfig(), led=None, vision=svc, session_manager=manager)
        entered, returned = asyncio.Event(), asyncio.Event()
        incoming = {
            **session.last_state,
            "current_node_id": 2,
            "current_node_index": 1,
            "stones": [["B", [4, 15], None, 1]],
        }

        async def recv():
            entered.set()
            await returned.wait()
            return json.dumps(incoming)

        room = object()
        app = SimpleNamespace(
            state=SimpleNamespace(
                session_manager=manager,
                vision=svc,
                physical_play=orch,
                box_sso=SimpleNamespace(active_generation=1),
                pvp_box_bridge=SimpleNamespace(
                    newer_state=PvpBoxBridge.newer_state, rooms=SimpleNamespace(for_local=lambda *_: room)
                ),
            )
        )

        def capture():
            return (svc.capture_binding_source("s", session), session, ("room", "room-game", None), 1, room)

        def transform(payload, source):
            return _apply_pvp_box_state(app, "s", payload, source=source, catch_up_current_binding=True)

        kwargs = dict(capture_source=capture, check_user=lambda: None, transform=transform)
        task = asyncio.create_task(_receive_box_pvp_message(SimpleNamespace(recv=recv), **kwargs))
        await entered.wait()
        svc.bind_session("s", session=session)
        orch.on_bind("s", session)
        revision = svc.expected_revision
        returned.set()
        await task
        # A single valid update must catch up the currently bound SAME room without waiting
        # for a second message (the opponent may now wait indefinitely for our move).
        assert svc.expected_revision == revision + 1
        await _receive_box_pvp_message(SimpleNamespace(recv=recv), **kwargs)
        assert svc.expected_revision == revision + 1
        stale = {**incoming, "current_node_id": 1, "current_node_index": 0, "stones": []}
        _apply_pvp_box_state(app, "s", stale, source=capture(), catch_up_current_binding=True)
        assert svc.expected_revision == revision + 1
        assert session.last_state["current_node_id"] == 2
        assert svc._worker.send_command.call_args.args[0].data["board"][3][4] == 1
        await orch.shutdown()

    asyncio.run(run())


def test_old_room_stream_updates_only_its_own_mirror_after_another_room_binds():
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.service import VisionService, binding_game_identity
    from katrain.web.core.physical_play import PhysicalPlayConfig
    from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator
    from katrain.web.core.pvp_box_bridge import PvpBoxBridge
    from katrain.web.server import _apply_pvp_box_state

    async def run():
        svc = VisionService(VisionServiceConfig())
        svc._worker = MagicMock()
        a, b = FakeSession(), FakeSession()
        sessions = {"a": a, "b": b}
        for sid, session in sessions.items():
            session.session_id = sid
            session.game_type = "pvp_lobby"
            session.katrain.update_state_callback = None
            session.last_state = {**session.katrain.get_state(), "game_id": sid, "current_node_index": 0}
        manager = SimpleNamespace(get_session=lambda sid: sessions[sid])
        rooms = {"a": object(), "b": object()}
        orch = PhysicalPlayOrchestrator(config=PhysicalPlayConfig(), led=None, vision=svc, session_manager=manager)
        app = SimpleNamespace(
            state=SimpleNamespace(
                session_manager=manager,
                vision=svc,
                physical_play=orch,
                box_sso=SimpleNamespace(active_generation=1),
                pvp_box_bridge=SimpleNamespace(
                    newer_state=PvpBoxBridge.newer_state, rooms=SimpleNamespace(for_local=lambda _, sid: rooms[sid])
                ),
            )
        )
        svc.bind_session("a", session=a)
        orch.on_bind("a", a)
        source_a = (svc.capture_binding_source("a", a), a, binding_game_identity(a), 1, rooms["a"])
        svc.bind_session("b", session=b)
        orch.on_bind("b", b)
        revision, calls = svc.expected_revision, svc._worker.send_command.call_count
        _apply_pvp_box_state(
            app,
            "a",
            {**a.last_state, "current_node_id": 2, "current_node_index": 1, "stones": [], "end_result": "W+R"},
            source=source_a,
            catch_up_current_binding=True,
        )
        assert a.last_state["current_node_id"] == 2
        assert svc.expected_revision == revision
        assert svc._worker.send_command.call_count == calls
        assert orch._session is b and not orch._pause_reasons
        assert orch._latest_state["game_id"] == "b"
        await orch.shutdown()

    asyncio.run(run())


@pytest.mark.parametrize("rebind_before_cleanup", [False, True])
def test_game_replacement_invalidates_binding_and_allows_normal_rebind(rebind_before_cleanup):
    import threading
    from katrain.core.game import BaseGame
    from katrain.web.server import _vision_game_replacement
    from tests.platforms.test_gateway import bound_vision_gateway

    async def run():
        app, session, svc, orch, pm, adapter, ctx = bound_vision_gateway()
        app.state.vision = svc
        original_callback = orch._orig_callback
        source = orch.binding_source
        epoch = svc.binding_epoch
        old_wrapper = session.katrain.update_state_callback
        orch.enter_engine_error((3, 3), "old-recovery")

        def replace():
            with session.lock, _vision_game_replacement(app, session):
                session.katrain.game = BaseGame(
                    session.katrain, game_properties={"SZ": 19, "RU": "japanese"}, bypass_config=True
                )
                session.last_state = session.katrain.get_state()
                old_wrapper(session.last_state)

        thread = threading.Thread(target=replace)
        thread.start()
        thread.join()
        assert svc.bound_session_id is None  # metadata invalidates before queued loop cleanup
        assert svc.binding_epoch > epoch
        assert not svc.source_is_current(source)
        if rebind_before_cleanup:
            svc.bind_session("s", session=session)
            orch.on_bind("s", session)
            revision = svc.expected_revision
        applied = asyncio.Event()
        asyncio.get_running_loop().call_soon(applied.set)
        await applied.wait()
        if rebind_before_cleanup:
            assert svc.bound_session_id == "s"
            assert svc.expected_revision == revision
            assert orch._session is session
        else:
            assert orch._session is None
            assert session.katrain.update_state_callback is original_callback
            svc.bind_session("s", session=session)
            orch.on_bind("s", session)
            assert svc.bound_session_id == "s" and svc.expected_revision == 1
        assert not orch._pause_reasons and orch._engine_error_context is None
        node = svc.expected_revision
        session.katrain("play", coords=(4, 15))
        assert svc.expected_revision == node + 1  # the NEW wrapper updates normally
        old_wrapper({"end_result": "W+R"})
        assert not orch._pause_reasons
        await orch.shutdown()

    asyncio.run(run())


def test_actual_new_game_holds_commit_lock_across_game_replacement():
    import threading
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch
    from katrain.web.interface import WebKaTrain

    runtime = MagicMock()
    runtime.ai_lock = threading.Lock()
    runtime.ai_ladder_commit_lock = threading.RLock()
    runtime.engine = None
    runtime.players_info = {}
    runtime.config.return_value = {"paused": False}
    held = []

    def game(*args, **kwargs):
        held.append(runtime.ai_ladder_commit_lock._is_owned())
        return SimpleNamespace()

    with patch("katrain.web.interface.WebGame", side_effect=game):
        WebKaTrain._do_new_game(runtime, skip_initial_analysis=True)
    assert held == [True]


@pytest.mark.parametrize("changed", [False, True])
def test_replacement_boundary_without_orchestrator_only_invalidates_actual_game_changes(changed):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.service import VisionService
    from katrain.web.server import _vision_game_replacement

    svc = VisionService(VisionServiceConfig())
    svc._worker = MagicMock()
    session = SimpleNamespace(session_id="s", katrain=SimpleNamespace(game=object()))
    app = SimpleNamespace(
        state=SimpleNamespace(
            vision=svc, session_manager=SimpleNamespace(), engine_recovery=MagicMock(), ranked_vision_binding=object()
        )
    )
    svc.bind_session("s", session=session)
    with _vision_game_replacement(app, session):
        if changed:
            session.katrain.game = object()
    assert svc.bound_session_id == (None if changed else "s")
    assert app.state.engine_recovery.clear.call_count == (1 if changed else 0)


def test_local_bind_republishes_authority_after_mode_enable_before_bootstrap_ready(monkeypatch):
    from types import SimpleNamespace
    from threading import RLock
    from katrain.web.core import local_confirmation

    calls = []
    game = SimpleNamespace(game_id="g", current_node=object())
    state = {
        "game_id": "g",
        "game_type": "pvp_local",
        "board_size": [19, 19],
        "current_node_id": id(game.current_node),
        "stones": [],
    }
    katrain = SimpleNamespace(
        game=game,
        get_state=lambda: state,
        set_local_geometry_paused=lambda *args, **kwargs: True,
        start_clock=lambda: None,
        local_geometry_pause_epoch=0,
    )
    session = SimpleNamespace(katrain=katrain, lock=RLock())

    class LocalVision(FakeVision):
        supports_local_confirmation = True
        local_confirmation_bootstrap_state = "bootstrap"

        def set_expected_from_stones(self, stones, *, expected_node_id=None):
            calls.append("expected")

        def set_local_confirmation_mode(self, enabled, **kwargs):
            calls.append("mode")
            return True

        @property
        def bound_session_id(self):
            return self.bound

        @property
        def local_confirmation_ready(self):
            assert calls[-2:] == ["mode", "expected"], "bootstrap checked before source-scoped republish"
            return True

    fake = LocalVision()
    monkeypatch.setattr(
        local_confirmation,
        "local_confirmation_for",
        lambda session: SimpleNamespace(ready=lambda *args, **kwargs: None),
    )
    c = _client(fake, SimpleNamespace(get_session=lambda sid: session))
    response = TestClient(c.app).post("/vision/bind", json={"session_id": "s"})
    assert response.status_code == 200, response.text
    assert calls == ["expected", "mode", "expected"]
