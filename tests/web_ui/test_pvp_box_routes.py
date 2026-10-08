"""A strict physical box reaches the central lobby through its own origin."""

from contextlib import asynccontextmanager
import asyncio
import json
import logging
import socket
import subprocess
import sys
import time
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core.config import settings
from katrain.web.core.physical_play import PhysicalPlayConfig
from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator
from katrain.web.core.pvp_box_bridge import PvpBoxBridge, PvpBoxRooms
from katrain.web.core.remote_client import RemoteAPIClient
from katrain.web.core import pvp_box_bridge as bridge_module
from katrain.web.server import create_app, _handle_confirmed_move
from katrain.web.session import LobbyManager, Matchmaker, WebSession
from katrain.vision.ipc import ConfirmedMove


@asynccontextmanager
async def no_lifespan(app):
    yield


class Central:
    bound_user_id = "4"
    is_authenticated = True
    base_url = "https://central.example"
    _access_token = "cloud-secret"

    def __init__(self):
        self.offline = False
        self.calls = []

    async def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if self.offline:
            raise httpx.ConnectError("offline")
        if path in ("/api/state", "/api/move", "/api/resign", "/api/count/request", "/api/timeout"):
            return httpx.Response(
                200,
                json={
                    "session_id": "central-room",
                    "state": {
                        "game_type": "free",
                        "board_size": [19, 19],
                        "stones": [["B", [3, 3], None, 1]],
                        "player_to_move": "W",
                    },
                },
                request=httpx.Request(method, f"https://central.example{path}"),
            )
        data = {
            "/api/v1/auth/me": {"id": 811, "username": "alice"},
            "/api/v1/users/online": [
                {"id": 811, "username": "alice", "ladder_rung": 4, "rank_label": "1d", "presence": "playing"},
                {"id": 990, "username": "bob", "ladder_rung": 4, "rank_label": "1d", "presence": "playing"},
            ],
            "/api/v1/games/active/multiplayer": [
                {
                    "session_id": "central-room",
                    "player_b": "alice",
                    "player_w": "bob",
                    "player_b_id": 811,
                    "player_w_id": 990,
                    "spectator_count": 0,
                    "move_count": 0,
                    "game_type": "free",
                },
            ],
        }[path]
        return httpx.Response(200, json=data, request=httpx.Request(method, f"https://central.example{path}"))


@pytest.fixture
def box_app(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    app = create_app(enable_engine=False)
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    app.router.lifespan_context = no_lifespan
    engine = create_engine(f"sqlite:///{tmp_path / 'box.db'}", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    repo = SQLAlchemyUserRepository(sessionmaker(bind=engine))
    # The first three IDs are deliberately *not* the cloud user's ID.
    for i in range(3):
        repo.create_user(f"padding{i}", "hash")
    shadow = repo.create_user("alice", "hash")
    app.state.user_repo = repo
    app.state.lobby_manager = LobbyManager()
    app.state.matchmaker = Matchmaker()
    app.state.box_sso.active_generation = 12
    app.state.box_sso.active_user_id = shadow["id"]
    central = Central()
    central.bound_user_id = str(shadow["id"])
    app.state.pvp_box_bridge = PvpBoxBridge(central, app.state.box_sso, PvpBoxRooms(), lambda *_: "local-room")
    yield app, central, create_access_token(data={"sub": "alice"}, box_generation=12)
    engine.dispose()


def test_box_origin_identity_roster_and_own_game_use_central_ids_and_local_room(box_app):
    app, central, token = box_app
    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        assert client.get("/api/pvp/identity").json() == {"user_id": 811}
        users = client.get("/api/v1/users/online")
        games = client.get("/api/v1/games/active/multiplayer")

    assert users.status_code == 200
    assert [u["id"] for u in users.json()] == [811, 990]
    assert games.status_code == 200
    assert games.json()[0]["session_id"] == "local-room"
    assert games.json()[0]["central_session_id"] == "central-room"
    assert all("Authorization" not in str(call) for call in central.calls)


def test_box_lobby_requires_current_cookie_and_reports_cloud_outage(box_app):
    app, central, token = box_app
    with TestClient(app) as client:
        assert client.get("/api/pvp/identity").status_code == 401
        client.cookies.set("sb_go_token", token)
        central.offline = True
        assert client.get("/api/pvp/identity").status_code == 503
        assert client.get("/api/v1/users/online").status_code == 503


class Upstream:
    def __init__(self, first):
        self.inbox = asyncio.Queue()
        self.inbox.put_nowait(first)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def recv(self):
        return json.dumps(await self.inbox.get())

    async def send(self, raw):
        self.sent.append(json.loads(raw))
        if self.sent[-1]["type"] == "start_matchmaking":
            await self.inbox.put(
                {"type": "match_found", "session_id": "central-room", "game_type": "free", "my_color": "W"}
            )


def test_box_lobby_websocket_forwards_to_central_and_rewrites_match(box_app, monkeypatch):
    app, _, token = box_app
    upstream = Upstream({"type": "lobby_update", "online_count": 2})
    monkeypatch.setattr(bridge_module, "ws_connect", lambda *_args, **_kwargs: upstream)

    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        with client.websocket_connect("/ws/lobby", headers={"Origin": "http://testserver"}) as ws:
            assert ws.receive_json() == {"type": "lobby_update", "online_count": 2}
            ws.send_json({"type": "start_matchmaking"})
            match = ws.receive_json()

    assert match["session_id"] == "local-room"
    assert match["central_session_id"] == "central-room"
    assert upstream.sent == [{"type": "start_matchmaking"}]
    assert app.state.pvp_box_bridge.rooms.for_local(12, "local-room") is not None


def test_room_websocket_projects_central_update_and_keeps_mapping_for_reconnect(box_app, monkeypatch):
    app, _, token = box_app
    bridge = app.state.pvp_box_bridge
    bridge.rewrite_match(12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "W"})
    katrain = MagicMock()
    katrain.get_state.return_value = {"game_type": "pvp_lobby", "stones": []}
    katrain.start_clock.return_value = False
    mirror = WebSession(session_id="local-room", katrain=katrain, user_id=4, player_w_id=4)
    app.state.session_manager._sessions["local-room"] = mirror
    central_state = {
        "game_type": "free",
        "board_size": [19, 19],
        "stones": [["B", [3, 3], None, 1]],
        "player_to_move": "W",
    }
    monkeypatch.setattr(
        bridge_module,
        "ws_connect",
        lambda *_args, **_kwargs: Upstream({"type": "game_update", "state": central_state}),
    )

    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        for _ in range(2):
            with client.websocket_connect("/ws/local-room", headers={"Origin": "http://testserver"}) as ws:
                update = ws.receive_json()
                assert update["state"]["game_type"] == "pvp_lobby"
                assert update["state"]["platform_my_color"] == "W"

    assert mirror.last_state["stones"] == central_state["stones"]
    assert bridge.rooms.for_local(12, "local-room") is not None


def test_room_outage_reports_disconnected_closes_1013_and_pauses_vision(box_app):
    app, central, token = box_app
    bridge = app.state.pvp_box_bridge
    bridge.rewrite_match(12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "W"})
    katrain = MagicMock()
    katrain.get_state.return_value = {"game_type": "pvp_lobby", "stones": []}
    mirror = WebSession(session_id="local-room", katrain=katrain, user_id=4, player_w_id=4)
    mirror.game_type = "pvp_lobby"
    app.state.session_manager._sessions["local-room"] = mirror
    vision = MagicMock()
    vision.bound_session_id = "local-room"
    app.state.vision = vision
    orchestrator = MagicMock()
    app.state.physical_play = orchestrator
    central.offline = True

    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        assert client.get("/api/state", params={"session_id": "local-room"}).status_code == 503
        with client.websocket_connect("/ws/local-room", headers={"Origin": "http://testserver"}) as ws:
            error = ws.receive_json()
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_json()

    assert error == {"type": "error", "code": "CENTRAL_DISCONNECTED", "message": "Central lobby disconnected"}
    assert closed.value.code == 1013
    assert orchestrator.enter_remote_disconnected.call_count >= 1


def test_box_state_and_touchscreen_move_forward_to_central_without_local_commit(box_app):
    app, central, token = box_app
    app.state.pvp_box_bridge.rewrite_match(
        12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "B"}
    )
    katrain = MagicMock()
    katrain.get_state.return_value = {"game_type": "pvp_lobby", "stones": []}
    mirror = WebSession(session_id="local-room", katrain=katrain, user_id=4, player_b_id=4)
    mirror.game_type = "pvp_lobby"
    app.state.session_manager._sessions["local-room"] = mirror

    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        state = client.get("/api/state", params={"session_id": "local-room"})
        move = client.post("/api/move", json={"session_id": "local-room", "coords": [3, 3], "pass_move": False})

    assert state.status_code == 200
    assert state.json()["state"]["game_type"] == "pvp_lobby"
    assert move.status_code == 200
    assert move.json()["session_id"] == "local-room"
    assert (
        "POST",
        "/api/move",
        {"json": {"session_id": "central-room", "coords": [3, 3], "pass_move": False}},
    ) in central.calls
    assert mirror.last_state["stones"] == [["B", [3, 3], None, 1]]
    katrain.assert_not_called()


def test_box_resign_uses_central_terminal_action_without_local_settlement(box_app):
    app, central, token = box_app
    app.state.pvp_box_bridge.rewrite_match(
        12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "B"}
    )
    katrain = MagicMock()
    katrain.get_state.return_value = {"game_type": "pvp_lobby", "stones": []}
    mirror = WebSession(session_id="local-room", katrain=katrain, user_id=4, player_b_id=4)
    mirror.game_type = "pvp_lobby"
    app.state.session_manager._sessions["local-room"] = mirror

    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        response = client.post("/api/resign", json={"session_id": "local-room"})

    assert response.status_code == 200
    assert response.json()["session_id"] == "local-room"
    assert ("POST", "/api/resign", {"json": {"session_id": "central-room", "color": None}}) in central.calls
    katrain.assert_not_called()


def test_vision_bind_uses_authoritative_central_board_for_local_mirror(box_app):
    app, _, token = box_app
    app.state.pvp_box_bridge.rewrite_match(
        12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "W"}
    )
    katrain = MagicMock()
    katrain.get_state.return_value = {"game_type": "pvp_lobby", "board_size": [19, 19], "stones": []}
    mirror = WebSession(session_id="local-room", katrain=katrain, user_id=4, player_w_id=4)
    mirror.game_type = "pvp_lobby"
    app.state.session_manager._sessions["local-room"] = mirror
    vision = MagicMock()
    vision.enabled = True
    app.state.vision = vision
    orchestrator = MagicMock()
    app.state.physical_play = orchestrator

    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        response = client.post("/api/v1/vision/bind", json={"session_id": "local-room"})

    assert response.status_code == 200
    vision.bind_session.assert_called_once_with("local-room")
    expected = orchestrator.on_game_state.call_args.args[0]
    assert expected["stones"] == [["B", [3, 3], None, 1]]
    assert expected["platform_my_color"] == "W"
    katrain.start_clock.assert_not_called()


@pytest.mark.asyncio
async def test_confirmed_physical_move_goes_upstream_and_updates_local_mirror(box_app):
    app, central, _ = box_app
    app.state.pvp_box_bridge.rewrite_match(
        12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "B"}
    )
    katrain = MagicMock()
    katrain.get_state.return_value = {"game_type": "pvp_lobby", "stones": []}
    mirror = WebSession(session_id="local-room", katrain=katrain, user_id=4, player_b_id=4)
    mirror.game_type = "pvp_lobby"
    mirror.last_state = {"game_type": "pvp_lobby", "stones": [], "player_to_move": "B"}
    app.state.session_manager._sessions["local-room"] = mirror
    vision = MagicMock()
    vision.bound_session_id = "local-room"
    vision.get_board_observation.return_value = (None, 0)
    app.state.physical_play = MagicMock()

    delay = await _handle_confirmed_move(
        app, vision, "local-room", ConfirmedMove(col=3, row=15, color=1), logging.getLogger("test")
    )

    assert delay == 0
    assert (
        "POST",
        "/api/move",
        {"json": {"session_id": "central-room", "coords": [3, 3], "pass_move": False}},
    ) in central.calls
    assert mirror.last_state["stones"] == [["B", [3, 3], None, 1]]
    katrain.assert_not_called()


class SmokeVision:
    enabled = True

    def __init__(self):
        self.bound_session_id = None
        self.expected = []
        self.detected = [[0] * 19 for _ in range(19)]
        self.paused = False

    def bind_session(self, session_id):
        self.bound_session_id = session_id

    def set_expected_from_stones(self, stones, *_, **__):
        self.expected = stones

    def get_board_observation(self):
        return None, 0

    def get_detected_board(self):
        return self.detected

    def set_lit_points(self, _points):
        pass

    def pause_detection(self):
        self.paused = True

    def resume_detection(self):
        self.paused = False


class SmokeLed:
    def __init__(self):
        self.points = []

    def set_points(self, points, **_):
        self.points = points

    def clear(self, **_):
        self.points = []


def test_two_process_box_match_room_vision_move_and_opponent_led(box_app):
    """Real HTTP/WS transport to a second process, with 4 != 811 and no browser cloud token."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.web_ui.pvp_box_fake_central:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    remote = None
    try:
        for _ in range(100):
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.05)
        else:
            pytest.fail("fake central process did not start")

        app, _, token = box_app
        remote = RemoteAPIClient(f"http://127.0.0.1:{port}", device_id="smoke")
        remote.set_tokens("cloud-secret", user_id=4)
        bridge = app.state.pvp_box_bridge
        bridge.remote = remote
        katrain = MagicMock()
        katrain.get_state.return_value = {"game_type": "pvp_lobby", "board_size": [19, 19], "stones": []}
        katrain.start_clock.return_value = False
        mirror = WebSession(session_id="local-room", katrain=katrain, user_id=4, player_b_id=4)
        mirror.game_type = "pvp_lobby"
        app.state.session_manager._sessions["local-room"] = mirror
        vision, led = SmokeVision(), SmokeLed()
        app.state.vision = vision
        physical = PhysicalPlayOrchestrator(
            config=PhysicalPlayConfig(tick_interval_s=0.02),
            led=led,
            vision=vision,
            session_manager=app.state.session_manager,
        )
        app.state.physical_play = physical

        with TestClient(app) as client:
            client.cookies.set("sb_go_token", token)
            assert client.get("/api/pvp/identity").json() == {"user_id": 811}
            assert client.get("/api/v1/users/online").json()[0]["id"] == 811
            with client.websocket_connect("/ws/lobby", headers={"Origin": "http://testserver"}) as lobby:
                assert lobby.receive_json()["type"] == "lobby_update"
                lobby.send_json({"type": "start_matchmaking"})
                match = lobby.receive_json()
                assert match["session_id"] == "local-room"
                assert match["central_session_id"] == "central-room"
            assert client.get("/api/v1/games/active/multiplayer").json()[0]["session_id"] == "local-room"
            with client.websocket_connect("/ws/local-room", headers={"Origin": "http://testserver"}) as room:
                assert room.receive_json()["state"]["platform_my_color"] == "B"
                assert client.post("/api/v1/vision/bind", json={"session_id": "local-room"}).status_code == 200
                assert (
                    client.portal.call(
                        _handle_confirmed_move,
                        app,
                        vision,
                        "local-room",
                        ConfirmedMove(col=3, row=15, color=1),
                        logging.getLogger("smoke"),
                    )
                    == 0
                )
                assert room.receive_json()["state"]["stones"] == [["B", [3, 3], None, 1]]
                opponent = room.receive_json()
                assert opponent["state"]["stones"][-1][:2] == ["W", [4, 4]]
                client.portal.call(physical._tick_once)
                assert {"row": 14, "col": 4, "color": "white"} in led.points, (
                    physical._latest_state["stones"],
                    physical._guided_colors_from_state(physical._latest_state),
                    physical._last_points,
                    physical._planner._observed_once,
                    vision.detected[14][4],
                )
                vision.detected[14][4] = 2
                physical._tick_once()
                assert led.points == []
            with client.websocket_connect("/ws/local-room", headers={"Origin": "http://testserver"}) as room:
                assert room.receive_json()["state"]["stones"][-1][:2] == ["W", [4, 4]]
            process.terminate()
            process.wait(timeout=5)
            assert client.get("/api/state", params={"session_id": "local-room"}).status_code == 503
            assert vision.paused is True
            with client.websocket_connect("/ws/local-room", headers={"Origin": "http://testserver"}) as room:
                assert room.receive_json()["code"] == "CENTRAL_DISCONNECTED"
                with pytest.raises(WebSocketDisconnect) as closed:
                    room.receive_json()
                assert closed.value.code == 1013

            async def revoke(generation):
                for mapped in bridge.rooms.revoke_generation(generation):
                    app.state.session_manager.remove_session(mapped.local_session_id)

            app.state.box_sso.on_revoke_generation = revoke
            client.portal.call(app.state.box_sso.activate, 13, 5)
            assert bridge.rooms.for_local(12, "local-room") is None
            assert client.get("/api/pvp/identity").status_code == 401
            client.portal.call(physical.shutdown)
            client.portal.call(remote.close)
            remote = None
    finally:
        if remote is not None:
            try:
                asyncio.run(remote.close())
            except RuntimeError:
                pass  # The TestClient portal may already have closed after an assertion failure.
        process.terminate()
        process.wait(timeout=5)
