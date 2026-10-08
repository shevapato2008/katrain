"""The physical box keeps a room mapping after its lobby socket goes away."""

import pytest

from katrain.web.core.pvp_box_bridge import PvpBoxRooms


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
