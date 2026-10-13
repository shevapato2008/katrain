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
        "game_id": None,
        "last_move": {"color": "W", "coordinate": "Q4"},
        "history": [
            {"black_stones": [], "white_stones": [], "move_number": 0, "last_move": None},
            {
                "black_stones": ["Q16"],
                "white_stones": [],
                "move_number": 1,
                "last_move": {"color": "B", "coordinate": "Q16"},
            },
            {
                "black_stones": ["Q16"],
                "white_stones": ["Q4"],
                "move_number": 2,
                "last_move": {"color": "W", "coordinate": "Q4"},
            },
        ],
        "clocks": None,
        "members": None,
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
    history = response.json()["history"]
    assert [position["move_number"] for position in history] == list(range(9))
    assert history[7]["black_stones"] == history[6]["black_stones"]
    assert history[7]["white_stones"] == history[6]["white_stones"]
    assert history[7]["last_move"] == {"color": "B", "coordinate": None}
    assert history[8]["last_move"] == {"color": "W", "coordinate": "B3"}
    assert "B2" in history[6]["black_stones"]
    assert "B2" not in history[8]["black_stones"]
    assert response.json()["last_move"] == history[8]["last_move"]


def test_matching_game_ids_change_when_a_room_is_reused():
    def room_for_game(game_id):
        return {
            **ROOM,
            "wsGameId": game_id,
            "gameMetaDto": {
                **ROOM["gameMetaDto"],
                "wsGameId": game_id,
                "gameroomId": ROOM["id"],
                "gameState": {**ROOM["gameMetaDto"]["gameState"], "wsGameId": game_id},
            },
        }

    first = _read(room_for_game(441))
    reused = _read(room_for_game(442))

    assert first.status_code == reused.status_code == 200
    assert first.json()["room_id"] == reused.json()["room_id"]
    assert first.json()["game_id"] == "441"
    assert reused.json()["game_id"] == "442"


@pytest.mark.parametrize(
    "game_ids",
    [
        (None, 441, 441),
        (441, None, 441),
        (441, 441, None),
        (441, 442, 441),
        (441, 441, 442),
        (True, 441, 441),
        (0, 0, 0),
        ("441", "441", "441"),
    ],
)
def test_missing_or_mismatched_game_id_is_unknown(game_ids):
    room_id, meta_id, state_id = game_ids
    room = {
        **ROOM,
        "wsGameId": room_id,
        "gameMetaDto": {
            **ROOM["gameMetaDto"],
            "wsGameId": meta_id,
            "gameroomId": ROOM["id"],
            "gameState": {**ROOM["gameMetaDto"]["gameState"], "wsGameId": state_id},
        },
    }
    response = _read(room)
    assert response.status_code == 200
    assert response.json()["game_id"] is None


def test_clock_shaped_fields_and_room_user_count_do_not_imply_timers_or_roster():
    state = {
        **ROOM["gameMetaDto"]["gameState"],
        "blackRemainTime": 10000,
        "whiteRemainTime": 20000,
        "blackCountdownTimestamp": 1700000000000,
        "whiteCountdownTimestamp": 1700000000000,
    }
    room = {
        **ROOM,
        "gameroomStateDto": {"onlineUserCount": 9},
        "gameMetaDto": {**ROOM["gameMetaDto"], "mainTime": 2400000, "gameState": state},
    }
    response = _read(room)
    assert response.status_code == 200
    assert response.json()["clocks"] is None
    assert response.json()["members"] is None


def test_empty_game_and_latest_pass_have_honest_last_move():
    meta = ROOM["gameMetaDto"]
    empty = _read({**ROOM, "gameMetaDto": {**meta, "moveNum": 0, "gameState": {"situation": "", "moveNum": 0}}})
    passed = _read({**ROOM, "gameMetaDto": {**meta, "gameState": {"situation": "72,-1", "moveNum": 2}}})

    assert empty.status_code == passed.status_code == 200
    assert empty.json()["history"] == [{"black_stones": [], "white_stones": [], "move_number": 0, "last_move": None}]
    assert empty.json()["last_move"] is None
    assert passed.json()["history"][-1]["black_stones"] == ["Q16"]
    assert passed.json()["last_move"] == {"color": "W", "coordinate": None}


@pytest.mark.parametrize("meta_room_id", [True, 10078688, "10078687"])
def test_game_identity_is_unknown_when_meta_room_binding_is_invalid(meta_room_id):
    room = {
        **ROOM,
        "wsGameId": 441,
        "gameMetaDto": {
            **ROOM["gameMetaDto"],
            "gameroomId": meta_room_id,
            "wsGameId": 441,
            "gameState": {**ROOM["gameMetaDto"]["gameState"], "wsGameId": 441},
        },
    }
    response = _read(room)
    assert response.status_code == 200
    assert response.json()["game_id"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("boardSize", 13),
        ("handicap", 2),
        ("startMoveNum", 1),
        ("gameType", "80"),
        ("gameType", "99"),
        ("rule", "japanese"),
    ],
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
