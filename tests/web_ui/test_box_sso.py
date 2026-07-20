from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

from katrain.web.api.v1.endpoints.auth import SHADOW_USER_NO_LOCAL_AUTH
from katrain.web.core import models_db
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token
from katrain.web.core.box_sso import BoxSSOState, GUEST_USERNAME, is_guest_user
from katrain.web.core.config import settings
from katrain.web.server import create_app
from katrain.web.session import LobbyManager, Matchmaker, SessionManager


BRIDGE_HEADER = {"X-SmartBox-Bridge-Key": "bridge-test-secret"}


@asynccontextmanager
async def no_lifespan(app):
    yield


@pytest.fixture
def strict_app(tmp_path, monkeypatch):
    key_path = tmp_path / "bridge.key"
    key_path.write_text("bridge-test-secret\n", encoding="utf-8")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO_BRIDGE_KEY_PATH", str(key_path))

    # The headless WebKaTrain test double must expose a JSON-compatible state
    # for the game WebSocket's initial update.
    from katrain.web import session as session_module

    session_module.WebKaTrain.return_value.get_state.return_value = {
        "player_to_move": "B"
    }

    # The repository does not track the built static-kiosk-2d bundle. Construct
    # the API app against the tracked server bundle, then enable strict board
    # runtime semantics before any request is made.
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    app = create_app(enable_engine=False)
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    app.router.lifespan_context = no_lifespan
    engine = create_engine(
        f"sqlite:///{tmp_path / 'box_sso.db'}", connect_args={"check_same_thread": False}
    )
    models_db.Base.metadata.create_all(bind=engine)
    app.state.user_repo = SQLAlchemyUserRepository(sessionmaker(bind=engine))
    app.state.remote_client = MagicMock()
    app.state.remote_client.set_tokens = MagicMock()
    app.state.remote_client.clear_tokens = MagicMock()
    app.state.lobby_manager = LobbyManager()
    app.state.matchmaker = Matchmaker()
    app.state.session_manager = SessionManager(enable_engine=False)
    app.state.game_repo = None
    yield app
    engine.dispose()


async def bootstrap(client, *, generation=1, username="alice", headers=None):
    return await client.post(
        "/api/v1/auth/box-sso/bootstrap",
        headers=headers or BRIDGE_HEADER,
        json={
            "username": username,
            "generation": generation,
            "remote_access_token": "remote-access",
            "remote_refresh_token": "remote-refresh",
        },
    )


@pytest.mark.asyncio
async def test_strict_bridge_bootstrap_returns_generation_bound_local_token(strict_app):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await bootstrap(client, generation=7)

    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    token = response.json()["access_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "alice"
    assert payload["box_generation"] == 7
    strict_app.state.remote_client.set_tokens.assert_called_once_with(
        "remote-access", "remote-refresh"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("username", ["guest", " GUEST "])
async def test_strict_bridge_bootstrap_rejects_reserved_guest_username(strict_app, username):
    """CRO-1: a cloud account literally named "guest" (or a normalized variant)
    must not collapse into the box's reserved zero-persistence guest identity.
    """
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await bootstrap(client, generation=1, username=username)

    assert response.status_code == 400
    assert strict_app.state.user_repo.get_user_by_username(GUEST_USERNAME) is None
    strict_app.state.remote_client.set_tokens.assert_not_called()


@pytest.mark.asyncio
async def test_strict_mode_rejects_bad_bridge_secret_and_non_loopback(strict_app):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        bad_secret = await bootstrap(
            client, headers={"X-SmartBox-Bridge-Key": "wrong"}
        )
    async with AsyncClient(
        transport=ASGITransport(app=strict_app, client=("198.51.100.10", 4242)),
        base_url="http://board.example",
    ) as client:
        remote_host = await bootstrap(client)

    assert bad_secret.status_code == 403
    assert remote_host.status_code == 403
    strict_app.state.remote_client.set_tokens.assert_not_called()


@pytest.mark.asyncio
async def test_strict_browser_accepts_only_go_cookie_and_current_generation(strict_app):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        first = await bootstrap(client, generation=3)
        old_token = first.json()["access_token"]
        direct_bearer = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}
        )
        retired_cookie = await client.get(
            "/api/v1/auth/me", cookies={"sb_token": old_token}
        )
        current_cookie = await client.get(
            "/api/v1/auth/me", cookies={"sb_go_token": old_token}
        )
        await bootstrap(client, generation=4)
        stale_cookie = await client.get(
            "/api/v1/auth/me", cookies={"sb_go_token": old_token}
        )

    assert direct_bearer.status_code == 401
    assert retired_cookie.status_code == 401
    assert current_cookie.status_code == 200
    assert stale_cookie.status_code == 401


@pytest.mark.asyncio
async def test_strict_mode_disables_direct_login_register_and_refresh(strict_app):
    refresh_token = create_access_token({"sub": "legacy"})
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "alice", "password": "pw"}
        )
        register = await client.post(
            "/api/v1/auth/register", json={"username": "alice", "password": "pw"}
        )
        refresh = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        boot = await bootstrap(client, generation=5)
        logout = await client.post(
            "/api/v1/auth/logout",
            cookies={"sb_go_token": boot.json()["access_token"]},
        )

    assert login.status_code == 403
    assert register.status_code == 403
    assert refresh.status_code == 403
    assert logout.status_code == 403
    strict_app.state.remote_client.clear_tokens.assert_not_called()


@pytest.mark.asyncio
async def test_bridge_clear_invalidates_generation_and_closes_registered_sockets(strict_app):
    socket = MagicMock()
    socket.close = AsyncMock()
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        boot = await bootstrap(client, generation=9)
        token = boot.json()["access_token"]
        strict_app.state.box_sso.register_socket(socket)
        cleared = await client.post(
            "/api/v1/auth/box-sso/clear",
            headers=BRIDGE_HEADER,
            json={"generation": 9},
        )
        me = await client.get(
            "/api/v1/auth/me", cookies={"sb_go_token": token}
        )

    assert cleared.status_code == 200
    assert me.status_code == 401
    strict_app.state.remote_client.clear_tokens.assert_called_once_with()
    socket.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_generation_closes_sockets_from_prior_generation(strict_app):
    socket = MagicMock()
    socket.close = AsyncMock()
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        await bootstrap(client, generation=20)
        strict_app.state.box_sso.register_socket(socket)
        response = await bootstrap(client, generation=21)

    assert response.status_code == 200
    socket.close.assert_awaited_once()


def test_strict_lobby_rejects_query_token_but_accepts_same_origin_go_cookie(strict_app):
    with TestClient(strict_app, client=("127.0.0.1", 50000)) as client:
        boot = client.post(
            "/api/v1/auth/box-sso/bootstrap",
            headers=BRIDGE_HEADER,
            json={
                "username": "socket-user",
                "generation": 11,
                "remote_access_token": "remote-access",
                "remote_refresh_token": "remote-refresh",
            },
        )
        token = boot.json()["access_token"]
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/lobby?token={token}") as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 1008

        client.cookies.set("sb_go_token", token)
        with client.websocket_connect(
            "/ws/lobby", headers={"Origin": "http://testserver"}
        ) as websocket:
            assert websocket.receive_json()["type"] == "lobby_update"


def test_strict_game_socket_rejects_query_token_and_accepts_go_cookie(strict_app):
    with TestClient(strict_app, client=("127.0.0.1", 50000)) as client:
        boot = client.post(
            "/api/v1/auth/box-sso/bootstrap",
            headers=BRIDGE_HEADER,
            json={
                "username": "game-user",
                "generation": 12,
                "remote_access_token": "remote-access",
                "remote_refresh_token": "remote-refresh",
            },
        )
        token = boot.json()["access_token"]
        client.cookies.set("sb_go_token", token)
        session_response = client.post("/api/session")
        assert session_response.status_code == 200
        session_id = session_response.json()["session_id"]

        client.cookies.delete("sb_go_token")
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                f"/ws/{session_id}?token={token}"
            ) as websocket:
                websocket.receive_json()
        assert exc_info.value.code == 1008

        client.cookies.set("sb_go_token", token)
        with client.websocket_connect(
            f"/ws/{session_id}", headers={"Origin": "http://testserver"}
        ) as websocket:
            assert websocket.receive_json()["type"] == "game_update"


# ---------------------------------------------------------------------------
# Guest mode: box-sso/guest-bootstrap bridge endpoint + reserved-name guard
# (see superpowers/tracks/box-sso-2026-07-13 guest-mode spec, task 1).
# ---------------------------------------------------------------------------


def test_is_guest_user_helper_matches_reserved_username_only():
    from types import SimpleNamespace

    assert is_guest_user(None) is False
    assert is_guest_user(SimpleNamespace(username=GUEST_USERNAME)) is True
    assert is_guest_user(SimpleNamespace(username="alice")) is False
    assert is_guest_user(SimpleNamespace()) is False


async def guest_bootstrap(client, *, generation=1, headers=None):
    return await client.post(
        "/api/v1/auth/box-sso/guest-bootstrap",
        headers=headers if headers is not None else BRIDGE_HEADER,
        json={"generation": generation},
    )


@pytest.mark.asyncio
async def test_guest_bootstrap_mints_local_jwt(strict_app):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=1)

    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "guest"
    assert payload["box_generation"] == 1


@pytest.mark.asyncio
async def test_guest_bootstrap_requires_bridge_key(strict_app):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, headers={})

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_guest_bootstrap_clears_remote_tokens(strict_app):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=1)

    assert response.status_code == 200
    strict_app.state.remote_client.clear_tokens.assert_called_once_with()


# Regression: Pydantic v2 coerces a JSON `true`/`false` to plain int 1/0 for an
# `int`-typed field *before* any endpoint code runs, which made a post-coercion
# `isinstance(generation, bool)` guard dead code -- `{"generation": true}` used to
# mint a 200 token instead of the required 400. `GuestBootstrapRequest.generation`
# is now `Any`, validated explicitly by `_validate_guest_bootstrap_generation`.
@pytest.mark.asyncio
@pytest.mark.parametrize("generation", [True, False])
async def test_guest_bootstrap_rejects_boolean_generation(strict_app, generation):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=generation)

    assert response.status_code == 400
    assert "access_token" not in response.json()
    strict_app.state.remote_client.clear_tokens.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("generation", ["1", 1.5])
async def test_guest_bootstrap_rejects_non_int_generation(strict_app, generation):
    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=generation)

    assert response.status_code == 400
    assert "access_token" not in response.json()


@pytest.mark.asyncio
async def test_guest_bootstrap_mints_token_without_remote_client(strict_app):
    """The `remote_client is not None` guard must not be load-bearing for success."""
    strict_app.state.remote_client = None

    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=1)

    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "guest"


@pytest.mark.asyncio
async def test_guest_bootstrap_409_on_non_pristine_guest_row(strict_app):
    repo = strict_app.state.user_repo
    guest = repo.create_user(username=GUEST_USERNAME, hashed_password=SHADOW_USER_NO_LOCAL_AUTH)
    session = repo.session_factory()
    try:
        session.add(models_db.UserGame(user_id=guest["id"], source="play_ai"))
        session.commit()
    finally:
        session.close()

    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=1)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_guest_bootstrap_adopts_pristine_existing_guest_row(strict_app):
    repo = strict_app.state.user_repo
    repo.create_user(username=GUEST_USERNAME, hashed_password=SHADOW_USER_NO_LOCAL_AUTH)

    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=1)

    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == GUEST_USERNAME


@pytest.mark.asyncio
async def test_guest_bootstrap_409_when_existing_guest_has_real_password(strict_app):
    from katrain.web.core.auth import get_password_hash

    repo = strict_app.state.user_repo
    repo.create_user(username=GUEST_USERNAME, hashed_password=get_password_hash("realpassword"))

    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=1)

    assert response.status_code == 409


# Named profile fields, compared to their EXACT real defaults (models_db.py:55-63).
# credits defaults to 10000 (not 0) -- a fresh shadow user already holds 10000, so
# treating 0 as "pristine" would 409 every guest bootstrap and break the feature.
NON_PRISTINE_FIELD_MUTATIONS = {
    "rank": ("rank", "5d"),
    "net_wins": ("net_wins", 3),
    "elo_points": ("elo_points", 150),
    "credits": ("credits", 9000),
    "is_admin": ("is_admin", True),
    "avatar_url": ("avatar_url", "https://example.com/a.png"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("field_name", sorted(NON_PRISTINE_FIELD_MUTATIONS))
async def test_guest_bootstrap_409_on_non_pristine_profile_field(strict_app, field_name):
    repo = strict_app.state.user_repo
    guest = repo.create_user(username=GUEST_USERNAME, hashed_password=SHADOW_USER_NO_LOCAL_AUTH)
    attr, value = NON_PRISTINE_FIELD_MUTATIONS[field_name]
    session = repo.session_factory()
    try:
        user = session.query(models_db.User).filter(models_db.User.id == guest["id"]).first()
        setattr(user, attr, value)
        session.commit()
    finally:
        session.close()

    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=1)

    assert response.status_code == 409


def _seed_user_game_analysis(session, uid):
    game = models_db.UserGame(user_id=uid, source="play_ai")
    session.add(game)
    session.flush()
    session.add(models_db.UserGameAnalysis(game_id=game.id, move_number=1))


def _seed_user_tsumego_progress(session, uid):
    problem = models_db.TsumegoProblem(id="test-problem-1", level="3d", category="life-death", hint="黑先")
    session.add(problem)
    session.flush()
    session.add(models_db.UserTsumegoProgress(user_id=uid, problem_id="test-problem-1"))


def _seed_user_tutorial_progress(session, uid):
    session.add(models_db.UserTutorialProgress(user_id=uid, example_id="ex-1", topic_id="topic-1"))


def _seed_rating_history(session, uid):
    session.add(models_db.RatingHistory(user_id=uid, old_rank="20k", new_rank="19k"))


def _seed_follower_relationship(session, uid):
    """Guest FOLLOWS someone else (Relationship.follower_id == uid)."""
    other = models_db.User(username="other-followee", hashed_password="x")
    session.add(other)
    session.flush()
    session.add(models_db.Relationship(follower_id=uid, following_id=other.id))


def _seed_following_relationship(session, uid):
    """Someone else follows guest (Relationship.following_id == uid)."""
    other = models_db.User(username="other-follower", hashed_password="x")
    session.add(other)
    session.flush()
    session.add(models_db.Relationship(follower_id=other.id, following_id=uid))


def _seed_live_comment(session, uid):
    match = models_db.LiveMatchDB(
        match_id="m-test-1",
        source="xingzhen",
        source_id="s-1",
        tournament="Test Cup",
        player_black="B",
        player_white="W",
    )
    session.add(match)
    session.flush()
    session.add(models_db.LiveCommentDB(match_id="m-test-1", user_id=uid, content="hello"))


def _seed_report_task_with_move(session, uid):
    game = models_db.UserGame(user_id=uid, source="play_ai")
    session.add(game)
    session.flush()
    task = models_db.ReportTask(user_id=uid, user_game_id=game.id)
    session.add(task)
    session.flush()
    session.add(models_db.ReportTaskMove(task_id=task.id, move_number=1))


def _seed_platform_game(session, uid):
    session.add(models_db.PlatformGameDB(id="pg-1", user_id=uid, platform="ogs", platform_game_id="og-1"))


def _seed_credit_transaction(session, uid):
    session.add(
        models_db.CreditTransaction(
            user_id=uid, delta=100, reason="admin_grant", ref_id="ref-1", balance_after=10100
        )
    )


def _seed_recharge_order_owner(session, uid):
    session.add(
        models_db.RechargeOrder(
            out_trade_no="order-1",
            user_id=uid,
            package_id="pkg-1",
            amount_fen=100,
            credits=100,
            provider="manual",
        )
    )


def _seed_recharge_order_confirmed_by(session, uid):
    """RechargeOrder.user_id belongs to someone ELSE -- only confirmed_by is guest."""
    other = models_db.User(username="order-owner", hashed_password="x")
    session.add(other)
    session.flush()
    session.add(
        models_db.RechargeOrder(
            out_trade_no="order-2",
            user_id=other.id,
            package_id="pkg-1",
            amount_fen=100,
            credits=100,
            provider="manual",
            confirmed_by=uid,
        )
    )


def _seed_redeem_code(session, uid):
    session.add(models_db.RedeemCode(code="redeemcode1", credits=100, used_by=uid))


def _seed_sync_queue_entry(session, uid):
    """SyncQueueEntry.user_id is a String(64), NOT a FK -- still guest-attributable."""
    session.add(
        models_db.SyncQueueEntry(
            idempotency_key="idem-1",
            operation="create_user_game",
            endpoint="/api/v1/user-games",
            method="POST",
            payload={},
            user_id=str(uid),
        )
    )


OWNED_DATA_SEEDERS = {
    "user_game_analysis": _seed_user_game_analysis,
    "user_tsumego_progress": _seed_user_tsumego_progress,
    "user_tutorial_progress": _seed_user_tutorial_progress,
    "rating_history": _seed_rating_history,
    "relationship_follower": _seed_follower_relationship,
    "relationship_following": _seed_following_relationship,
    "live_comments": _seed_live_comment,
    "report_task_with_move": _seed_report_task_with_move,
    "platform_games": _seed_platform_game,
    "credit_transactions": _seed_credit_transaction,
    "recharge_order_user_id": _seed_recharge_order_owner,
    "recharge_order_confirmed_by": _seed_recharge_order_confirmed_by,
    "redeem_code_used_by": _seed_redeem_code,
    "sync_queue_user_id": _seed_sync_queue_entry,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("table_label", sorted(OWNED_DATA_SEEDERS))
async def test_guest_bootstrap_409_on_owned_data(strict_app, table_label):
    repo = strict_app.state.user_repo
    guest = repo.create_user(username=GUEST_USERNAME, hashed_password=SHADOW_USER_NO_LOCAL_AUTH)
    session = repo.session_factory()
    try:
        OWNED_DATA_SEEDERS[table_label](session, guest["id"])
        session.commit()
    finally:
        session.close()

    async with AsyncClient(
        transport=ASGITransport(app=strict_app), base_url="http://127.0.0.1:8081"
    ) as client:
        response = await guest_bootstrap(client, generation=1)

    assert response.status_code == 409


@pytest.fixture
def server_mode_app(tmp_path, monkeypatch):
    """A non-strict (server-mode, remote_client=None) app for reserved-name tests."""
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    app = create_app(enable_engine=False)
    engine = create_engine(
        f"sqlite:///{tmp_path / 'server_mode.db'}", connect_args={"check_same_thread": False}
    )
    models_db.Base.metadata.create_all(bind=engine)
    app.state.user_repo = SQLAlchemyUserRepository(sessionmaker(bind=engine))
    yield app
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("username", ["guest", "GUEST", " guest ", "Guest"])
async def test_register_and_login_reject_reserved_guest_username(server_mode_app, username):
    assert getattr(server_mode_app.state, "remote_client", None) is None

    async with AsyncClient(
        transport=ASGITransport(app=server_mode_app), base_url="http://test"
    ) as client:
        register_response = await client.post(
            "/api/v1/auth/register", json={"username": username, "password": "pw123456"}
        )
        login_response = await client.post(
            "/api/v1/auth/login", json={"username": username, "password": "pw123456"}
        )

    assert register_response.status_code == 400
    assert login_response.status_code == 400
