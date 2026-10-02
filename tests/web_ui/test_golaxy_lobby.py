"""Read-only Golaxy lobby contract, with all upstream HTTP traffic mocked."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.platforms.golaxy.adapter import GolaxyAdapter
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import OnlineUser, PlatformCredentials
from katrain.web.server import create_app


ROOM = {
    "id": 10078687,
    "gameroomCode": "8687",
    "gameroomStatus": 30,
    "wsGameId": 441,
    "gameroomType": 20,
    "gameMetaDto": {
        "gameType": "82",
        "handicap": 0,
        "komi": 7.5,
        "blackNickname": "Black",
        "whiteNickname": "White",
        "blackUserCode": "b1",
        "whiteUserCode": "w1",
        "blackLevel": 2500,
        "whiteLevel": 2600,
        "gameState": {"situation": "1,2,3", "moveNum": 3, "gameStatus": 20},
    },
    "gameroomStateDto": {"onlineUserCount": 8},
}


def _adapter(handler):
    adapter = GolaxyAdapter()
    adapter._rest._client = httpx.AsyncClient(base_url="https://api.19x19.com", transport=httpx.MockTransport(handler))
    adapter._rest.set_tokens("old-token", "refresh-token")
    adapter._connected = True
    return adapter


def _app(adapter, owner=7):
    app = create_app(enable_engine=False)
    manager = PlatformManager(SimpleNamespace())
    manager.register_adapter(adapter)
    manager._platform_user_ids[adapter.platform_name] = owner
    app.state.platform_manager = manager
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    return app


def test_room_endpoint_maps_captured_fields_without_inventing_spectators():
    def handler(request):
        assert request.url.path == "/api/social/gameroom/list"
        assert dict(request.url.params) == {"page": "0", "size": "15"}
        assert request.headers["Authorization"] == "Bearer old-token"
        return httpx.Response(200, json={"code": "0", "data": [ROOM]})

    adapter = _adapter(handler)
    response = TestClient(_app(adapter)).get("/api/v1/platforms/golaxy/rooms")
    assert response.status_code == 200
    assert response.json() == {
        "rooms": [
            {
                "room_id": "10078687",
                "room_number": "8687",
                "room_type": "升降战",
                "handicap": 0,
                "black": {"user_id": "b1", "username": "Black", "rank": "7段"},
                "white": {"user_id": "w1", "username": "White", "rank": "准8段"},
                "phase": "3手",
                "move_number": 3,
                "room_user_count": 8,
                "spectator_count": None,
            }
        ]
    }


def test_user_endpoint_fetches_golaxy_list_and_projects_only_verified_fields():
    def handler(request):
        assert request.url.path == "/api/social/gamezone/user/list"
        assert dict(request.url.params) == {"page": "0", "size": "15", "level": "-1"}
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    {
                        "userCode": "u1",
                        "nickname": "Player",
                        "level": "2500",
                        "userStatus": 20,
                        "connectionStatus": 1,
                        "winNum": 5,
                        "loseNum": 2,
                        "inviteAble": True,
                        "photoFile": "https://assets.19x19.com/user_photo/player.png",
                        "webConnectionStatus": 1,
                        "webUserStatusDetail": "WSGAME_WATCH",
                    },
                    {"userCode": "u2", "nickname": "Other", "followAlias": "Friend"},
                ],
            },
        )

    response = TestClient(_app(_adapter(handler))).get("/api/v1/platforms/golaxy/users")
    assert response.status_code == 200
    assert response.json() == {
        "users": [
            {
                "user_id": "u1",
                "username": "Player",
                "rank": "7段",
                "status": "观战",
                "wins": 5,
                "losses": 2,
                "invite_able": True,
                "avatar_url": "https://assets.19x19.com/user_photo/player.png",
            },
            {
                "user_id": "u2",
                "username": "Friend",
                "rank": None,
                "status": None,
                "wins": None,
                "losses": None,
                "invite_able": None,
                "avatar_url": None,
            },
        ]
    }


def test_golaxy_user_query_filters_current_page_by_username_prefix():
    def handler(request):
        assert request.url.path == "/api/social/gamezone/user/list"
        assert dict(request.url.params) == {"page": "0", "size": "15", "level": "-1"}
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    {"userCode": "u1", "nickname": "Player"},
                    {"userCode": "u2", "nickname": "Other"},
                ],
            },
        )

    response = TestClient(_app(_adapter(handler))).get("/api/v1/platforms/golaxy/users?q=pl")
    assert response.status_code == 200
    assert response.json() == {
        "users": [
            {
                "user_id": "u1",
                "username": "Player",
                "rank": None,
                "status": None,
                "wins": None,
                "losses": None,
                "invite_able": None,
                "avatar_url": None,
            },
        ]
    }


@pytest.mark.parametrize(
    "game_type,label",
    [
        (80, "自由战"),
        ("80", "自由战"),
        (82, "升降战"),
        ("82", "升降战"),
        (10, None),
        (20, None),
        (True, None),
        ([], None),
    ],
)
async def test_room_category_uses_game_type_and_never_room_source_enum(game_type, label):
    room = {**ROOM, "gameMetaDto": {**ROOM["gameMetaDto"], "gameType": game_type}}
    rooms = await _adapter(lambda request: httpx.Response(200, json={"code": "0", "data": [room]})).get_rooms()
    assert rooms[0]["room_type"] == label
    assert rooms[0]["spectator_count"] is None


@pytest.mark.parametrize(
    "level,rank",
    [
        (2500, "7段"),
        ("2600", "准8段"),
        (25, None),
        (29, None),
        (2550, None),
        (True, None),
        (2500.0, None),
        ("2500.0", None),
        ({}, None),
    ],
)
async def test_rank_is_an_exact_verified_elo_lookup(level, rank):
    room = {**ROOM, "gameMetaDto": {**ROOM["gameMetaDto"], "blackLevel": level}}
    user = {"userCode": "u1", "nickname": "Player", "level": level}
    adapter = _adapter(
        lambda request: httpx.Response(
            200, json={"code": "0", "data": [room if request.url.path.endswith("/gameroom/list") else user]}
        )
    )
    assert (await adapter.get_rooms())[0]["black"]["rank"] == rank
    assert (await adapter.get_online_users())[0]["rank"] == rank


@pytest.mark.parametrize("value", [None, -1, True, 2.5, "8", [], {}])
async def test_room_optional_counts_reject_malformed_values(value):
    room = {
        **ROOM,
        "gameroomStateDto": {"onlineUserCount": value},
        "gameMetaDto": {**ROOM["gameMetaDto"], "gameState": {"moveNum": value}},
    }
    result = (await _adapter(lambda request: httpx.Response(200, json={"code": "0", "data": [room]})).get_rooms())[0]
    assert result["room_user_count"] is None
    assert result["move_number"] is None
    assert result["phase"] is None
    assert result["spectator_count"] is None


async def test_room_missing_or_malformed_optional_objects_stay_unknown():
    rows = [
        {"id": "1", "gameroomType": 10},
        {"id": "2", "gameroomType": 20, "gameMetaDto": [], "gameroomStateDto": "invalid"},
    ]
    results = await _adapter(lambda request: httpx.Response(200, json={"code": "0", "data": rows})).get_rooms()
    for result in results:
        assert result["room_type"] is None
        assert result["room_user_count"] is None
        assert result["black"] is None and result["white"] is None
        assert result["spectator_count"] is None


@pytest.mark.parametrize("value", [None, -1, True, 2.5, "5", [], {}])
async def test_user_optional_counts_and_invitation_flag_are_strict(value):
    user = {"userCode": "u1", "nickname": "Player", "winNum": value, "loseNum": value, "inviteAble": value}
    result = (
        await _adapter(lambda request: httpx.Response(200, json={"code": "0", "data": [user]})).get_online_users()
    )[0]
    assert result["wins"] is None and result["losses"] is None
    assert result["invite_able"] is (True if value is True else None)
    assert result["status"] is None


@pytest.mark.parametrize(
    "fields,status",
    [
        ({"userStatus": 20}, None),
        ({"connectionStatus": 0}, "离线"),
        ({"connectionStatus": "1", "userStatus": "20", "inviteAble": True}, "空闲"),
        ({"connectionStatus": 1, "userStatus": 40, "inviteAble": False}, "拒绝"),
        ({"connectionStatus": 1, "userStatus": 90}, "退出"),
        ({"connectionStatus": True, "userStatus": 20}, None),
        ({"connectionStatus": 1, "userStatus": 999}, None),
        ({"connectionStatus": 1, "userStatus": {}, "webUserStatusDetail": []}, None),
        (
            {
                "connectionStatus": 1,
                "userStatus": 40,
                "webConnectionStatus": 1,
                "webUserStatusDetail": "AI_ANALYSIS",
                "appConnectionStatus": 1,
                "appUserStatusDetail": "AI_GAME",
            },
            "研究中",
        ),
        (
            {
                "connectionStatus": 1,
                "userStatus": 20,
                "webConnectionStatus": 0,
                "webUserStatusDetail": "WSGAME_WATCH",
                "appConnectionStatus": 1,
                "appUserStatusDetail": "AI_LIFE_DEATH",
            },
            "AI解题中",
        ),
        ({"connectionStatus": 1, "userStatus": 30, "webConnectionStatus": 1, "webUserStatusDetail": "UNKNOWN"}, "忙碌"),
    ],
)
async def test_user_presence_uses_verified_connection_and_detail_precedence(fields, status):
    user = {"userCode": "u1", "nickname": "Player", **fields}
    result = (
        await _adapter(lambda request: httpx.Response(200, json={"code": "0", "data": [user]})).get_online_users()
    )[0]
    assert result["status"] == status


@pytest.mark.parametrize(
    "photo",
    [
        "player.png",
        "http://assets.19x19.com/user_photo/a.png",
        "https://example.com/a.png",
        "javascript:alert(1)",
        "https://assets.19x19.com.evil.example/a.png",
        "https://user:password@assets.19x19.com/a.png",
        [],
        {},
    ],
)
async def test_user_avatar_does_not_forward_untrusted_urls(photo):
    user = {"userCode": "u1", "nickname": "Player", "photoFile": photo}
    result = (
        await _adapter(lambda request: httpx.Response(200, json={"code": "0", "data": [user]})).get_online_users()
    )[0]
    assert result["avatar_url"] is None


async def test_user_zero_counts_false_flag_and_photo_fallback_are_preserved():
    user = {
        "userCode": "u1",
        "nickname": "Player",
        "winNum": 0,
        "loseNum": 0,
        "inviteAble": False,
        "photoFile": "",
        "photo": "https://assets.19x19.com/user_photo/player.png",
    }
    result = (
        await _adapter(lambda request: httpx.Response(200, json={"code": "0", "data": [user]})).get_online_users()
    )[0]
    assert result["wins"] == 0 and result["losses"] == 0
    assert result["invite_able"] is False
    assert result["avatar_url"] == user["photo"]


@pytest.mark.parametrize(
    "body",
    [
        {"code": "5001", "data": []},
        {"code": "0", "data": {}},
        {"data": []},
        {"code": "0", "data": [{"id": None}]},
    ],
)
def test_room_business_or_schema_failure_is_502(body):
    adapter = _adapter(lambda request: httpx.Response(200, json=body))
    response = TestClient(_app(adapter)).get("/api/v1/platforms/golaxy/rooms")
    assert response.status_code == 502


def test_room_timeout_is_502():
    def handler(request):
        raise httpx.ReadTimeout("timeout")

    response = TestClient(_app(_adapter(handler))).get("/api/v1/platforms/golaxy/rooms")
    assert response.status_code == 502


def test_user_invalid_token_is_401_without_runtime_refresh():
    refresh_calls = 0

    def handler(request):
        nonlocal refresh_calls
        if request.url.path == "/api/auth/oauth/token":
            refresh_calls += 1
            return httpx.Response(200, json={"access_token": "new-token", "refresh_token": "new-refresh"})
        return httpx.Response(200, json={"code": "6003", "data": "invalid token"})

    response = TestClient(_app(_adapter(handler))).get("/api/v1/platforms/golaxy/users")
    assert response.status_code == 401
    assert refresh_calls == 0


def test_foreign_owner_cannot_read_lobby():
    adapter = _adapter(lambda request: (_ for _ in ()).throw(AssertionError("upstream called")))
    assert TestClient(_app(adapter, owner=8)).get("/api/v1/platforms/golaxy/rooms").status_code == 403
    assert TestClient(_app(adapter, owner=8)).get("/api/v1/platforms/golaxy/users").status_code == 403


@pytest.mark.parametrize("path", ["rooms", "users"])
async def test_owner_switch_while_list_is_loading_cannot_expose_new_owners_data(path):
    upstream_started = asyncio.Event()
    release_upstream = asyncio.Event()

    async def handler(request):
        upstream_started.set()
        await release_upstream.wait()
        if path == "rooms":
            room = {**ROOM, "gameMetaDto": {**ROOM["gameMetaDto"], "blackNickname": "B-secret"}}
            return httpx.Response(200, json={"code": "0", "data": [room]})
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    {"userCode": "b-user", "nickname": "B", "followAlias": "B-secret"},
                ],
            },
        )

    app = _app(_adapter(handler), owner=7)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        pending = asyncio.create_task(client.get(f"/api/v1/platforms/golaxy/{path}"))
        await asyncio.wait_for(upstream_started.wait(), timeout=2)
        app.state.platform_manager._platform_user_ids["golaxy"] = 8
        release_upstream.set()
        response = await pending

    assert response.status_code == 403
    assert "B-secret" not in response.text


def test_ogs_users_still_come_from_challenges():
    class OGSAdapter:
        platform_name = "ogs"
        is_connected = True

        async def get_online_users(self, room=None):
            raise AssertionError("default OGS listing should use challenges")

        async def get_open_challenges(self):
            return [
                SimpleNamespace(
                    from_user=OnlineUser(
                        platform="ogs",
                        user_id="42",
                        username="seeker",
                        rank="3d",
                        rank_numeric=3,
                    )
                )
            ]

    response = TestClient(_app(OGSAdapter())).get("/api/v1/platforms/ogs/users")
    assert response.status_code == 200
    assert response.json()["users"] == [{"user_id": "42", "username": "seeker", "rank": "3d", "status": "seeking"}]


async def test_reconnect_verifies_stored_token_with_authenticated_user_list_and_refreshes_once():
    calls = []

    def handler(request):
        calls.append((request.url.path, request.headers.get("Authorization")))
        if request.url.path == "/api/auth/oauth/token":
            return httpx.Response(200, json={"access_token": "new-token", "refresh_token": "new-refresh"})
        if request.headers.get("Authorization") == "Bearer old-token":
            return httpx.Response(200, json={"code": "6003", "data": "invalid token"})
        return httpx.Response(200, json={"code": "0", "data": []})

    adapter = _adapter(handler)
    events = []

    async def refreshed(data):
        events.append(data)

    adapter.on_token_refreshed(refreshed)
    assert await adapter.connect(
        PlatformCredentials(
            "golaxy",
            "",
            {
                "access_token": "old-token",
                "refresh_token": "refresh-token",
            },
        )
    )
    assert calls[0][0] == "/api/social/gamezone/user/list"
    assert not any(path == "/api/engine/golives/all" for path, _ in calls)
    assert sum(path == "/api/auth/oauth/token" for path, _ in calls) == 1
    assert events[0]["access_token"] == "new-token"


async def test_parallel_runtime_lists_surface_auth_errors_without_refresh():
    refresh_calls = 0

    async def handler(request):
        nonlocal refresh_calls
        if request.url.path == "/api/auth/oauth/token":
            refresh_calls += 1
            return httpx.Response(200, json={"access_token": "new-token", "refresh_token": "new-refresh"})
        if request.url.path.endswith("/gameroom/list"):
            return httpx.Response(401)
        return httpx.Response(200, json={"code": "6003", "data": "invalid token"})

    adapter = _adapter(handler)
    results = await asyncio.gather(adapter.get_rooms(), adapter.get_online_users(), return_exceptions=True)
    assert all(type(result).__name__ == "GolaxyLobbyAuthError" for result in results)
    assert refresh_calls == 0


def test_room_expired_token_is_401_without_runtime_refresh():
    refresh_calls = 0

    def handler(request):
        nonlocal refresh_calls
        if request.url.path == "/api/auth/oauth/token":
            refresh_calls += 1
            return httpx.Response(200, json={"access_token": "new-token", "refresh_token": "new-refresh"})
        return httpx.Response(401)

    response = TestClient(_app(_adapter(handler))).get("/api/v1/platforms/golaxy/rooms")
    assert response.status_code == 401
    assert refresh_calls == 0
