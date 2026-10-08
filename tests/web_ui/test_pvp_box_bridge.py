"""The physical box keeps a room mapping after its lobby socket goes away."""

import pytest
import httpx

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
