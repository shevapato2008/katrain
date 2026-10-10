"""The physical box keeps a room mapping after its lobby socket goes away."""

import pytest
import httpx
from concurrent.futures import ThreadPoolExecutor
import time
from katrain.web.core import pvp_box_bridge as bridge_module
from katrain.web.core.box_sso import BoxSSOState

from katrain.web.core.pvp_box_bridge import PvpBoxRooms, PvpBoxBridge, PvpBoxAuthError, PvpBoxRemoteError


def test_room_survives_lobby_disconnect_and_reconnects_by_central_id():
    rooms = PvpBoxRooms()
    room = rooms.attach(
        generation=12,
        central_user_id=811,
        central_session_id="central-a",
        local_session_id="local-b",
        local_user_id=4,
        my_color="W",
    )
    rooms.lobby_disconnected(12)

    assert rooms.for_central(12, "central-a") is room
    assert rooms.for_local(12, "local-b") is room
    assert room.central_user_id != room.local_user_id
    assert room.my_color == "W"


def test_generation_replacement_revokes_old_rooms_without_touching_new_rooms():
    rooms = PvpBoxRooms()
    rooms.attach(1, 811, "old", "old-local", 4, "B")
    rooms.attach(2, 912, "new", "new-local", 5, "W")

    revoked = rooms.revoke_generation(1)

    assert [room.central_session_id for room in revoked] == ["old"]
    assert rooms.for_central(1, "old") is None
    assert rooms.for_local(1, "old-local") is None
    assert rooms.for_central(2, "new") is not None


def test_local_room_id_cannot_be_rebound_to_a_different_central_room():
    rooms = PvpBoxRooms()
    rooms.attach(1, 811, "central-a", "local-b", 4, "B")

    with pytest.raises(ValueError, match="local room"):
        rooms.attach(1, 811, "central-c", "local-b", 4, "B")


def test_same_central_room_reconnect_preserves_mapping():
    rooms = PvpBoxRooms()
    first = rooms.attach(1, 811, "central-a", "local-b", 4, "B")
    second = rooms.attach(1, 811, "central-a", "local-b", 4, "B")

    assert second is first
    assert rooms.end_room(1, "central-a") is first
    assert rooms.for_local(1, "local-b") is None


def test_removed_local_mirror_clears_room_mapping():
    rooms = PvpBoxRooms()
    rooms.attach(1, 811, "central-a", "local-b", 4, "B")

    rooms.discard_local("local-b")

    assert rooms.for_local(1, "local-b") is None
    assert rooms.for_central(1, "central-a") is None


@pytest.mark.parametrize("color", ["", "black", None, 1])
def test_room_rejects_invalid_color(color):
    with pytest.raises(ValueError, match="color"):
        PvpBoxRooms().attach(1, 811, "central-a", "local-b", 4, color)


class FakeRemote:
    def __init__(self):
        self.bound_user_id = "4"
        self.is_authenticated = True
        self.base_url = "https://central.example"
        self.calls = []
        self.responses = {
            "/api/v1/auth/me": {"id": 811, "username": "box-user"},
            "/api/v1/users/online": [{"id": 811, "username": "box-user"}],
        }

    async def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        answer = self.responses[path]
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(200, json=answer, request=httpx.Request(method, f"https://central.example{path}"))


class FakeSSO:
    active_generation = 12
    active_user_id = 4

    def validates(self, generation):
        return generation == self.active_generation


def test_concurrent_room_discovery_creates_only_one_mirror():
    created = []

    def make_mirror(*_):
        created.append("local-room")
        time.sleep(0.02)
        return "local-room"

    bridge = PvpBoxBridge(FakeRemote(), FakeSSO(), PvpBoxRooms(), make_mirror)
    message = {"type": "match_found", "session_id": "central-room", "my_color": "B"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: bridge.rewrite_match(12, 4, 811, message), range(2)))

    assert [row["session_id"] for row in results] == ["local-room", "local-room"]
    assert created == ["local-room"]


def test_generation_replaced_during_mirror_creation_removes_orphan():
    sso = FakeSSO()
    removed = []

    def make_mirror(*_):
        sso.active_generation = 13
        return "orphan-room"

    bridge = PvpBoxBridge(FakeRemote(), sso, PvpBoxRooms(), make_mirror, removed.append)
    with pytest.raises(PvpBoxAuthError):
        bridge.rewrite_match(12, 4, 811, {"session_id": "central-room", "my_color": "B"})

    assert removed == ["orphan-room"]
    assert bridge.rooms.for_central(12, "central-room") is None


@pytest.mark.asyncio
async def test_bridge_uses_remote_identity_and_never_shadow_id_for_roster():
    remote = FakeRemote()
    bridge = PvpBoxBridge(remote, FakeSSO(), PvpBoxRooms(), lambda *_: "mirror-a")

    assert await bridge.identity(12, 4) == {"user_id": 811}
    assert await bridge.get_json(12, 4, "/api/v1/users/online") == [{"id": 811, "username": "box-user"}]
    assert all(call[2] == {} for call in remote.calls)


@pytest.mark.asyncio
async def test_bridge_rejects_replaced_generation_and_wrong_shadow_binding():
    remote, sso = FakeRemote(), FakeSSO()
    bridge = PvpBoxBridge(remote, sso, PvpBoxRooms(), lambda *_: "mirror-a")

    with pytest.raises(PvpBoxAuthError):
        await bridge.identity(11, 4)
    with pytest.raises(PvpBoxAuthError):
        await bridge.identity(12, 5)
    remote.bound_user_id = "5"
    with pytest.raises(PvpBoxAuthError):
        await bridge.identity(12, 4)
    assert remote.calls == []


@pytest.mark.asyncio
async def test_bridge_rechecks_generation_after_remote_response():
    remote, sso = FakeRemote(), FakeSSO()
    original = remote._request

    async def switch_generation(*args, **kwargs):
        response = await original(*args, **kwargs)
        sso.active_generation = 13
        return response

    remote._request = switch_generation
    bridge = PvpBoxBridge(remote, sso, PvpBoxRooms(), lambda *_: "mirror-a")
    with pytest.raises(PvpBoxAuthError):
        await bridge.identity(12, 4)


@pytest.mark.asyncio
async def test_bridge_preserves_remote_outage_as_error():
    remote = FakeRemote()
    remote.responses["/api/v1/auth/me"] = httpx.ConnectError("offline")
    bridge = PvpBoxBridge(remote, FakeSSO(), PvpBoxRooms(), lambda *_: "mirror-a")

    with pytest.raises(PvpBoxRemoteError):
        await bridge.identity(12, 4)


def test_match_rewrites_only_box_room_id_and_remembers_central_room():
    created = []

    def make_mirror(local_user_id, color, central_session_id):
        created.append((local_user_id, color, central_session_id))
        return "local-room"

    bridge = PvpBoxBridge(FakeRemote(), FakeSSO(), PvpBoxRooms(), make_mirror)
    central = {"type": "match_found", "session_id": "central-room", "game_type": "free", "my_color": "W"}

    rewritten = bridge.rewrite_match(12, 4, 811, central)
    assert rewritten == {**central, "session_id": "local-room", "central_session_id": "central-room"}
    assert bridge.rooms.for_local(12, "local-room").central_user_id == 811
    assert bridge.rewrite_match(12, 4, 811, central) == rewritten
    assert created == [(4, "W", "central-room")]


def test_active_game_rewrites_only_own_row_with_distinct_central_id():
    bridge = PvpBoxBridge(FakeRemote(), FakeSSO(), PvpBoxRooms(), lambda *_: "local-room")
    games = [
        {"session_id": "central-room", "player_b_id": 99, "player_w_id": 811, "game_type": "free"},
        {"session_id": "strangers", "player_b_id": 5, "player_w_id": 6, "game_type": "free"},
    ]

    rows = bridge.rewrite_active_games(12, 4, 811, games)
    assert rows[0] == {**games[0], "session_id": "local-room", "central_session_id": "central-room"}
    assert rows[1] == games[1]
    assert bridge.rooms.for_local(12, "local-room").my_color == "W"


@pytest.mark.asyncio
async def test_fetch_state_uses_central_room_id_and_projects_mirror_state():
    remote = FakeRemote()
    remote.responses["/api/state"] = {"session_id": "central-room", "state": {"game_type": "free", "stones": []}}
    bridge = PvpBoxBridge(remote, FakeSSO(), PvpBoxRooms(), lambda *_: "local-room")
    bridge.rewrite_match(12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "W"})

    state = await bridge.fetch_state(12, "local-room")

    assert remote.calls[-1] == ("GET", "/api/state", {"params": {"session_id": "central-room"}})
    assert state == {
        "session_id": "local-room",
        "state": {"game_type": "pvp_lobby", "stones": [], "platform_my_color": "W", "my_color": "W"},
    }


@pytest.mark.asyncio
async def test_upstream_websocket_uses_server_side_bearer_and_central_origin(monkeypatch):
    remote = FakeRemote()
    remote._access_token = "cloud-secret"
    seen = {}
    monkeypatch.setattr(bridge_module, "ws_connect", lambda url, **kw: seen.update(url=url, **kw) or "connection")
    bridge = PvpBoxBridge(remote, FakeSSO(), PvpBoxRooms(), lambda *_: "local-room")

    assert await bridge.upstream_websocket(12, 4, "/ws/lobby") == "connection"
    assert seen == {
        "url": "wss://central.example/ws/lobby",
        "origin": "https://central.example",
        "additional_headers": {"Authorization": "Bearer cloud-secret"},
        "open_timeout": 10,
    }


def test_local_mirror_state_has_seat_and_never_claims_central_free_game():
    bridge = PvpBoxBridge(FakeRemote(), FakeSSO(), PvpBoxRooms(), lambda *_: "local-room")
    bridge.rewrite_match(12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "B"})
    central = {"game_type": "free", "stones": [], "player_to_move": "B"}

    assert bridge.rewrite_state(12, "local-room", central) == {
        **central,
        "game_type": "pvp_lobby",
        "platform_my_color": "B",
        "my_color": "B",
    }
    assert central["game_type"] == "free"


def test_delayed_move_response_cannot_replace_newer_opponent_websocket_state():
    current = {"game_id": "g", "current_node_index": 2, "stones": [["W", [4, 4], None, 2]]}
    delayed = {"game_id": "g", "current_node_index": 1, "stones": [["B", [3, 3], None, 1]]}
    assert PvpBoxBridge.newer_state(current, delayed) is current
    assert PvpBoxBridge.newer_state(delayed, current) is current


def test_terminal_result_cannot_be_erased_by_same_node_update():
    terminal = {"game_id": "g", "current_node_index": 2, "end_result": "B+F", "awaiting_count": False}
    stale = {"game_id": "g", "current_node_index": 2, "end_result": None}
    assert PvpBoxBridge.newer_state(terminal, stale) is terminal
    pending_count = {"game_id": "g", "current_node_index": 2, "end_result": "终局", "awaiting_count": True}
    assert PvpBoxBridge.newer_state(terminal, pending_count) is terminal


@pytest.mark.asyncio
async def test_physical_move_uses_central_room_and_returns_authoritative_state():
    remote = FakeRemote()
    remote.responses["/api/move"] = {
        "session_id": "central-room",
        "state": {"game_type": "free", "player_to_move": "W", "stones": [["B", [3, 3], None, 1]]},
    }
    bridge = PvpBoxBridge(remote, FakeSSO(), PvpBoxRooms(), lambda *_: "local-room")
    bridge.rewrite_match(12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "B"})

    response = await bridge.forward_move(12, "local-room", coords=[3, 3])

    assert remote.calls[-1] == (
        "POST",
        "/api/move",
        {"json": {"session_id": "central-room", "coords": [3, 3], "pass_move": False}},
    )
    assert response["session_id"] == "local-room"
    assert response["state"]["stones"] == [["B", [3, 3], None, 1]]
    assert response["state"]["game_type"] == "pvp_lobby"


@pytest.mark.asyncio
async def test_remote_failure_does_not_invent_a_local_move():
    remote = FakeRemote()
    remote.responses["/api/move"] = httpx.ConnectError("offline")
    bridge = PvpBoxBridge(remote, FakeSSO(), PvpBoxRooms(), lambda *_: "local-room")
    bridge.rewrite_match(12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "B"})

    with pytest.raises(PvpBoxRemoteError):
        await bridge.forward_move(12, "local-room", coords=[3, 3])


@pytest.mark.asyncio
async def test_control_action_rewrites_room_id_and_keeps_central_result_authoritative():
    remote = FakeRemote()
    remote.responses["/api/resign"] = {
        "session_id": "central-room",
        "state": {"game_type": "free", "end_result": "W+R"},
    }
    bridge = PvpBoxBridge(remote, FakeSSO(), PvpBoxRooms(), lambda *_: "local-room")
    bridge.rewrite_match(12, 4, 811, {"type": "match_found", "session_id": "central-room", "my_color": "B"})

    result = await bridge.forward_action(12, "local-room", "POST", "/api/resign", {"color": None})

    assert remote.calls[-1] == ("POST", "/api/resign", {"json": {"color": None, "session_id": "central-room"}})
    assert result == {
        "session_id": "local-room",
        "state": {"game_type": "pvp_lobby", "end_result": "W+R", "platform_my_color": "B", "my_color": "B"},
    }


@pytest.mark.asyncio
async def test_sso_generation_replacement_and_clear_revoke_room_mappings(tmp_path):
    state = BoxSSOState(str(tmp_path / "key"))
    rooms = PvpBoxRooms()
    revoked = []

    async def on_revoke(generation):
        revoked.extend(rooms.revoke_generation(generation))

    state.on_revoke_generation = on_revoke
    await state.activate(12, user_id=4)
    rooms.attach(12, 811, "central-room", "local-room", 4, "B")
    await state.activate(13, user_id=5)
    assert rooms.for_local(12, "local-room") is None
    rooms.attach(13, 912, "new-central", "new-local", 5, "W")
    await state.clear(13)
    assert rooms.for_local(13, "new-local") is None
    assert [room.central_session_id for room in revoked] == ["central-room", "new-central"]
