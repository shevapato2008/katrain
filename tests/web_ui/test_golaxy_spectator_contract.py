"""Read-only Golaxy room snapshots use the authenticated room detail response."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.platforms.golaxy.adapter import GolaxyAdapter
from katrain.web.platforms.manager import PlatformManager
from katrain.web.server import create_app


ROOM = {
    "id": 10078687,
    "gameroomCode": "8687",
    "gameroomStatus": 30,
    "gameMetaDto": {
        "boardSize": 19,
        "handicap": 0,
        "startMoveNum": 0,
        "moveNum": 2,
        "gameType": "82",
        "rule": "chinese",
        "blackNickname": "Black",
        "whiteNickname": "White",
        "blackLevel": 25,
        "whiteLevel": 29,
        "gameState": {"situation": "72,300", "moveNum": 2, "gameStatus": 10},
    },
}


def _app(handler, owner=7):
    adapter = GolaxyAdapter()
    adapter._rest._client = httpx.AsyncClient(base_url="https://api.19x19.com", transport=httpx.MockTransport(handler))
    adapter._rest.set_tokens("old-token", "refresh-token")
    adapter._connected = True
    app = create_app(enable_engine=False)
    manager = PlatformManager(SimpleNamespace())
    manager.register_adapter(adapter)
    manager._platform_user_ids[adapter.platform_name] = owner
    app.state.platform_manager = manager
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    return app


def _read(room=ROOM):
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/api/social/gameroom/info/10078687"
        assert request.headers["Authorization"] == "Bearer old-token"
        return httpx.Response(200, json={"code": "0", "data": room})

    return TestClient(_app(handler)).get("/api/v1/platforms/golaxy/rooms/10078687/snapshot")


def test_snapshot_uses_meta_board_fields_and_bottom_up_go_coordinates():
    response = _read()
    assert response.status_code == 200
    assert response.json() == {
        "room_id": "10078687",
        "room_number": "8687",
        "room_type": None,
        "handicap": 0,
        "board_size": 19,
        "black": {"username": "Black", "rank": None},
        "white": {"username": "White", "rank": None},
        "black_stones": ["Q16"],
        "white_stones": ["Q4"],
        "move_number": 2,
        "phase": "进行中",
        "result": None,
    }


def test_snapshot_replays_capture_and_pass_without_leaving_captured_stone():
    # Black B2 is surrounded by White; Black's pass still consumes a turn.
    moves = "324,323,72,343,300,325,-1,305"
    room = {
        **ROOM,
        "gameMetaDto": {
            **ROOM["gameMetaDto"],
            "moveNum": 8,
            "gameState": {"situation": moves, "moveNum": 8, "gameStatus": 10},
        },
    }
    response = _read(room)
    assert response.status_code == 200
    assert set(response.json()["black_stones"]) == {"Q16", "Q4"}
    assert set(response.json()["white_stones"]) == {"A2", "B1", "C2", "B3"}
    assert response.json()["move_number"] == 8


@pytest.mark.parametrize(
    "field,value", [("boardSize", 13), ("handicap", 2), ("startMoveNum", 1), ("gameType", "99"), ("rule", "japanese")]
)
def test_unverified_game_setups_are_rejected(field, value):
    room = {**ROOM, "gameMetaDto": {**ROOM["gameMetaDto"], field: value}}
    response = _read(room)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "situation,move_number",
    [
        ("72", 2),
        ("72,", 2),
        ("72,x", 2),
        ("72,999", 2),
        ("72,72", 2),
        ("-3,72", 2),
    ],
)
def test_incomplete_or_illegal_history_is_upstream_failure(situation, move_number):
    room = {
        **ROOM,
        "gameMetaDto": {
            **ROOM["gameMetaDto"],
            "gameState": {"situation": situation, "moveNum": move_number, "gameStatus": 10},
        },
    }
    assert _read(room).status_code == 502


def test_suicide_history_is_upstream_failure():
    room = {
        **ROOM,
        "gameMetaDto": {
            **ROOM["gameMetaDto"],
            "moveNum": 5,
            "gameState": {"situation": "72,323,300,343,342", "moveNum": 5, "gameStatus": 10},
        },
    }
    assert _read(room).status_code == 502


def test_boolean_metadata_move_count_is_not_accepted_as_one_move():
    room = {
        **ROOM,
        "gameMetaDto": {
            **ROOM["gameMetaDto"],
            "moveNum": True,
            "gameState": {"situation": "72", "moveNum": 1, "gameStatus": 10},
        },
    }
    assert _read(room).status_code == 502


def test_reported_finished_room_has_no_inferred_result():
    response = _read({**ROOM, "gameroomStatus": 40})
    assert response.status_code == 200
    assert response.json()["phase"] == "已结束"
    assert response.json()["result"] is None


def test_foreign_owner_cannot_fetch_snapshot():
    def handler(request):
        raise AssertionError("upstream must not be called")

    response = TestClient(_app(handler, owner=8)).get("/api/v1/platforms/golaxy/rooms/10078687/snapshot")
    assert response.status_code == 403


@pytest.mark.parametrize("room_id", ["abc", "1%2F2", "-1"])
def test_non_numeric_room_id_never_reaches_upstream(room_id):
    def handler(request):
        raise AssertionError("upstream must not be called")

    response = TestClient(_app(handler)).get(f"/api/v1/platforms/golaxy/rooms/{room_id}/snapshot")
    assert response.status_code in (400, 404, 422)


@pytest.mark.parametrize(
    "upstream,expected",
    [
        (httpx.Response(401), 401),
        (httpx.Response(403), 401),
        (httpx.Response(200, json={"code": "6003", "data": "expired"}), 401),
        (httpx.Response(500), 502),
        (httpx.Response(200, json={"code": "5001", "data": ROOM}), 502),
        (httpx.Response(200, json={"code": "0", "data": {}}), 502),
    ],
)
def test_upstream_auth_and_other_failures_are_distinct(upstream, expected):
    response = TestClient(_app(lambda request: upstream)).get("/api/v1/platforms/golaxy/rooms/10078687/snapshot")
    assert response.status_code == expected


def test_upstream_timeout_is_502():
    def handler(request):
        raise httpx.ReadTimeout("timeout")

    response = TestClient(_app(handler)).get("/api/v1/platforms/golaxy/rooms/10078687/snapshot")
    assert response.status_code == 502
