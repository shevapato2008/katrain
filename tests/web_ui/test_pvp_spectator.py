"""The hall spectator is a read-only projection, including on strict SSO boxes."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core.config import settings
from katrain.web.core.db import Base
from katrain.web.core.models_db import AiLadderProfile
from katrain.web.core.pvp_box_bridge import PvpBoxBridge, PvpBoxRooms
from katrain.web.core.pvp_lobby_bots import bot_id, playable_rungs
from katrain.web.server import create_app
from katrain.web.session import WebSession


@asynccontextmanager
async def no_lifespan(app):
    app.state.session_manager.attach_loop(asyncio.get_running_loop())
    yield


@pytest.fixture
def spectator_app(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    app = create_app(enable_engine=False)
    app.router.lifespan_context = no_lifespan
    engine = create_engine(f"sqlite:///{tmp_path / 'spectator.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    app.state.session_factory = sessionmaker(bind=engine)
    app.state.user_repo = SQLAlchemyUserRepository(app.state.session_factory)
    viewer = app.state.user_repo.create_user("viewer", "hash")
    player = app.state.user_repo.create_user("black", "hash")
    app.state.pvp_lobby_bots = MagicMock()
    app.state.pvp_lobby_bots.public_online_rows.return_value = []
    yield app, viewer, player
    engine.dispose()


def headers(user):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': user['username']})}"}


def hall(app, player, *, game_type="pvp_lobby", white=991, ended=False):
    state = {
        "board_size": [19, 19],
        "stones": [["B", [3, 3], None, 1]],
        "last_move": [3, 3],
        "current_node_index": 1,
        "player_to_move": "W",
        "history": [],
        "end_result": "B+R" if ended else None,
    }
    katrain = MagicMock()
    katrain.get_state.return_value = state
    session = WebSession("central-room", katrain, player_b_id=player["id"], player_w_id=white)
    session.game_type = game_type
    session.game_ended = ended
    session.last_state = state if ended else {"stones": []}
    app.state.session_manager._sessions[session.session_id] = session
    return session, state


@pytest.mark.parametrize("game_type", ["free", "pvp_lobby"])
def test_authenticated_hall_spectator_reads_live_state_and_authoritative_players(spectator_app, game_type):
    app, viewer, player = spectator_app
    rung = playable_rungs()[0]
    bot = bot_id(rung.rung, 1)
    session, state = hall(app, player, game_type=game_type, white=bot)
    db = app.state.session_factory()
    db.add(
        AiLadderProfile(
            user_id=player["id"], ai_ladder_rung=rung.rung, placement_lo=1, placement_hi=41, placement_completed=5
        )
    )
    db.commit()
    db.close()
    app.state.pvp_lobby_bots.public_online_rows.return_value = [
        {"id": bot, "username": "棋友", "ladder_rung": rung.rung}
    ]
    with TestClient(app) as client:
        response = client.get("/api/pvp/spectate/central-room", headers=headers(viewer))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["session_id"] == "central-room" and data["public_lobby"] is True
    assert data["state"]["stones"] == state["stones"]  # Refreshed via the existing read closure, not the old cache.
    assert data["spectator_count"] == data["state"]["spectator_count"] == 1
    assert data["player_b"] == "black" and data["player_w"] == "棋友"
    assert data["player_b_id"] == player["id"] and data["player_w_id"] == bot
    assert data["player_b_rank_label"] == data["player_w_rank_label"] == rung.rank_label
    assert not {"uuid", "credits", "token", "hashed_password"}.intersection(data)
    session.katrain.get_state.assert_called_once()
    assert session.sockets == set()
    session.katrain.start.assert_not_called()


def test_anonymous_cannot_read_hall(spectator_app):
    app, _, player = spectator_app
    session, _ = hall(app, player)
    with TestClient(app) as client:
        assert client.get("/api/pvp/spectate/central-room").status_code == 401
    assert session.spectator_presence.count((player["id"], 991), set()) == 0


@pytest.mark.parametrize(
    "game_type,white", [("free", None), ("ai_ladder_ranked", 88), ("pvp_online", -1), ("pvp_lobby", True)]
)
def test_private_sessions_are_not_exposed_even_to_their_owner(spectator_app, game_type, white):
    app, _, player = spectator_app
    session, _ = hall(app, player, game_type=game_type, white=white)
    session.user_id = player["id"]
    with TestClient(app) as client:
        assert client.get("/api/pvp/spectate/central-room", headers=headers(player)).status_code == 404
    session.katrain.get_state.assert_not_called()
    assert session.spectator_presence.count((session.player_b_id, session.player_w_id), set()) == 0


def test_failed_authoritative_read_does_not_register_observer(spectator_app):
    app, viewer, player = spectator_app
    session, _ = hall(app, player)
    session.katrain.get_state.side_effect = RuntimeError("state unavailable")
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/pvp/spectate/central-room", headers=headers(viewer)).status_code == 500
    assert session.spectator_presence.count((player["id"], 991), set()) == 0


def test_owner_snapshot_does_not_count_and_hall_reports_unique_http_viewer(spectator_app):
    app, viewer, player = spectator_app
    hall(app, player)
    with TestClient(app) as client:
        owner = client.get("/api/pvp/spectate/central-room", headers=headers(player)).json()
        assert owner["spectator_count"] == owner["state"]["spectator_count"] == 0
        client.get("/api/pvp/spectate/central-room", headers=headers(viewer))
        client.get("/api/pvp/spectate/central-room", headers=headers(viewer))
        rooms = client.get("/api/v1/games/active/multiplayer", headers=headers(viewer)).json()
    assert rooms[0]["spectator_count"] == 1


def test_http_observer_join_pushes_already_connected_player_websocket(spectator_app):
    app, viewer, player = spectator_app
    hall(app, player)
    token = create_access_token(data={"sub": player["username"]})
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/central-room?token={token}") as ws:
            initial = ws.receive_json()
            assert initial["state"]["sockets_count"] == 1
            assert initial["state"]["spectator_count"] == 0
            assert ws.receive_json() == {"type": "spectator_count", "count": 1, "spectator_count": 0}
            response = client.get("/api/pvp/spectate/central-room", headers=headers(viewer))
            assert response.json()["spectator_count"] == 1
            assert ws.receive_json() == {"type": "spectator_count", "count": 1, "spectator_count": 1}


def test_duplicate_viewer_websockets_keep_raw_count_and_leave_after_last_tab(spectator_app):
    app, viewer, player = spectator_app
    session, _ = hall(app, player)
    token = create_access_token(data={"sub": viewer["username"]})
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/central-room?token={token}") as first:
            assert first.receive_json()["state"]["spectator_count"] == 1
            assert first.receive_json() == {"type": "spectator_count", "count": 1, "spectator_count": 1}
            with client.websocket_connect(f"/ws/central-room?token={token}") as second:
                assert second.receive_json()["state"]["spectator_count"] == 1
                assert second.receive_json() == {"type": "spectator_count", "count": 2, "spectator_count": 1}
                assert first.receive_json() == {"type": "spectator_count", "count": 2, "spectator_count": 1}
            assert first.receive_json() == {"type": "spectator_count", "count": 1, "spectator_count": 1}
    assert session.spectator_presence.count((player["id"], 991), session.sockets) == 0


def test_accepted_socket_is_removed_when_initial_clock_start_fails(spectator_app):
    app, _, player = spectator_app
    session, _ = hall(app, player)
    session.katrain.start_clock.side_effect = RuntimeError("clock unavailable")
    token = create_access_token(data={"sub": player["username"]})
    with TestClient(app) as client:
        try:
            with client.websocket_connect(f"/ws/central-room?token={token}"):
                pass
        except RuntimeError:
            pass
    assert not session.sockets
    assert session.spectator_presence.count((player["id"], 991), session.sockets) == 0


def test_missing_and_unsafe_session_ids_are_not_read(spectator_app):
    app, viewer, _ = spectator_app
    app.state.session_manager.get_session = MagicMock(side_effect=KeyError("missing"))
    with TestClient(app) as client:
        assert client.get("/api/pvp/spectate/missing", headers=headers(viewer)).status_code == 404
        assert client.get("/api/pvp/spectate/bad%3Fid", headers=headers(viewer)).status_code == 404
    app.state.session_manager.get_session.assert_called_once_with("missing")


def test_terminal_hall_snapshot_stays_available(spectator_app):
    app, viewer, player = spectator_app
    session, _ = hall(app, player, ended=True)
    with TestClient(app) as client:
        response = client.get("/api/pvp/spectate/central-room", headers=headers(viewer))
    assert response.status_code == 200
    assert response.json()["state"]["end_result"] == "B+R"
    assert response.json()["game_ended"] is True
    session.katrain.get_state.assert_not_called()


class Central:
    is_authenticated = True

    def __init__(self, local_id):
        self.bound_user_id = str(local_id)
        self.calls = []
        self.status = 200
        self.data = {
            "session_id": "cloud-room",
            "public_lobby": True,
            "spectator_count": 3,
            "state": {"stones": [], "spectator_count": 3},
            "player_b": "中央黑",
            "player_w": "中央白",
            "player_b_id": 811,
            "player_w_id": 990,
            "player_b_rank_label": None,
            "player_w_rank_label": "业余 2 段",
            "game_ended": False,
        }
        self.after_request = None

    async def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if self.after_request:
            self.after_request()
        return httpx.Response(
            self.status, json=self.data, request=httpx.Request(method, f"https://central.example{path}")
        )


@pytest.fixture
def spectator_box(spectator_app, monkeypatch):
    app, viewer, _ = spectator_app
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    app.state.box_sso.active_generation = 12
    app.state.box_sso.active_user_id = viewer["id"]
    central = Central(viewer["id"])
    make_mirror = MagicMock(side_effect=AssertionError("spectating must not create a mirror"))
    app.state.pvp_box_bridge = PvpBoxBridge(central, app.state.box_sso, PvpBoxRooms(), make_mirror)
    app.state.session_manager.get_session = MagicMock(side_effect=AssertionError("cloud IDs are not local IDs"))
    app.state.session_manager.create_session = MagicMock()
    token = create_access_token(data={"sub": viewer["username"]}, box_generation=12)
    yield app, central, token, make_mirror


def test_box_reads_same_central_endpoint_without_local_lookup_or_actions(spectator_box):
    app, central, token, make_mirror = spectator_box
    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        response = client.get("/api/pvp/spectate/cloud-room")
        assert client.post("/api/pvp/spectate/cloud-room").status_code == 405
    assert response.status_code == 200, response.text
    assert response.json() == central.data
    assert central.calls == [("GET", "/api/pvp/spectate/cloud-room", {})]
    app.state.session_manager.get_session.assert_not_called()
    app.state.session_manager.create_session.assert_not_called()
    make_mirror.assert_not_called()
    assert not app.state.pvp_box_bridge.rooms._by_local


@pytest.mark.parametrize("path", ["/api/pvp/spectate/cloud-room", "/api/v1/games/active/multiplayer"])
def test_box_without_central_bridge_cannot_fall_back_to_local_counts(spectator_box, path):
    app, _, token, _ = spectator_box
    app.state.pvp_box_bridge = None
    app.state.session_manager.list_active_multiplayer_sessions = MagicMock(return_value=[])
    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        assert client.get(path).status_code == 503
    app.state.session_manager.list_active_multiplayer_sessions.assert_not_called()


@pytest.mark.parametrize("status,expected", [(401, 401), (404, 404), (503, 503)])
def test_box_preserves_auth_missing_and_outage_errors(spectator_box, status, expected):
    app, central, token, _ = spectator_box
    central.status = status
    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        assert client.get("/api/pvp/spectate/cloud-room").status_code == expected


@pytest.mark.parametrize("changed", [{"session_id": "another-room"}, {"public_lobby": False}])
def test_box_rejects_wrong_room_or_nonpublic_response(spectator_box, changed):
    _, central, token, _ = spectator_box
    central.data.update(changed)
    with TestClient(spectator_box[0]) as client:
        client.cookies.set("sb_go_token", token)
        assert client.get("/api/pvp/spectate/cloud-room").status_code == 503


@pytest.mark.parametrize("change", ["generation", "user"])
def test_box_rejects_account_change_during_read(spectator_box, change):
    app, central, token, _ = spectator_box
    central.after_request = lambda: setattr(
        app.state.box_sso, "active_generation" if change == "generation" else "active_user_id", 99
    )
    with TestClient(app) as client:
        client.cookies.set("sb_go_token", token)
        assert client.get("/api/pvp/spectate/cloud-room").status_code == 401
