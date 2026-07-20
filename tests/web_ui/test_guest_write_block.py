"""Guest write-block tests (Task 2 of the box-SSO guest-mode plan, R2-F1/R2-F8).

Covers:
  - `require_writable_user` 403s the guest on every enumerated per-user write
    route, while a real user still gets 2xx WITH that route's real
    prerequisites (owned game/task, live match, comment target, platform
    adapter) -- not one generic parametrization.
  - The four optional-auth tutorial-authoring writers guest-only reject
    (anonymous stays allowed).
  - `/ws/lobby` rejects the guest before `add_user`.
  - The new `_require_multiplayer_participant` guard on `/api/resign` and
    `/api/timeout`, for both local-multiplayer AND platform-backed games.
  - Zero persisted rows / zero sync-queue entries / zero remote-adapter calls
    after every guest write attempt.

Runs on the shared NON-STRICT `app()` fixture (tests/web_ui/conftest.py).
"""

import threading
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocketDisconnect

from katrain.web.api.v1.endpoints.auth import _get_or_create_shadow_user
from katrain.web.core import models_db
from katrain.web.core.auth import create_access_token
from katrain.web.core.box_sso import GUEST_USERNAME
from katrain.web.core.config import settings
from katrain.web.core.db import get_db
from katrain.web.platforms.gateway import PlatformCommandGateway
from katrain.web.platforms.golaxy.engine_client import AreaResult
from katrain.web.session import LobbyManager, Matchmaker

from tests.web_ui._helpers import _create_user_and_login


@asynccontextmanager
async def _no_lifespan(app):
    """Skip the real (heavy) server lifespan for the sync TestClient websocket test."""
    yield


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def full_app(app, monkeypatch):
    """The shared non-strict `app()` fixture, further wired with every domain
    touched by the guest-write-block route surface:

      - `Depends(get_db)` (tsumego/board/billing/tutorials) overridden to the
        SAME SQLite engine already backing user_repo/game_repo/user_game_repo,
        so real-user writes are actually observable in assertions.
      - `katrain.web.core.db.SessionLocal` monkeypatched to that same session
        factory -- live.py's comment endpoints and the live translator import
        `SessionLocal` directly (not via `Depends`), so this is the only way
        to make THEIR writes observable too.
      - live_service / platform_manager / platform_gateway / lobby_manager /
        matchmaker: not wired by `create_app()` itself (those come from the
        real lifespan, which we don't run) -- every route this task governs
        that touches one of these needs it present so a guest 403 is what
        actually fires, not an unrelated 503/500 from a missing attribute.
      - KATRAIN_MODE forced to "server" so billing.redeem doesn't 503 before
        ever reaching the guest guard.

    Real-user tests further customize the platform adapter mock per route;
    guest-403 checks never reach any of this (the auth dependency raises
    before the handler body runs), so this generic wiring is safe for both.
    """
    TestSessionLocal = app.state.user_repo.session_factory

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr("katrain.web.core.db.SessionLocal", TestSessionLocal)

    from katrain.web.live import translator as translator_module

    translator_module.reset_translator()

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")

    app.state.lobby_manager = LobbyManager()
    app.state.matchmaker = Matchmaker()

    live_service = MagicMock()
    live_service.cache.get_match = AsyncMock(
        return_value=SimpleNamespace(status=SimpleNamespace(value="live"))
    )
    app.state.live_service = live_service

    platform_manager = MagicMock()
    platform_manager.is_platform_game = MagicMock(return_value=False)
    platform_manager._credential_store = MagicMock()
    platform_manager._credential_store.load_credentials = MagicMock(return_value=None)
    app.state.platform_manager = platform_manager
    app.state.platform_gateway = PlatformCommandGateway(platform_manager, app.state.session_manager)

    app.router.lifespan_context = _no_lifespan

    return app


@pytest.fixture
def guest_headers(full_app):
    """Seed the guest User row (R3-F4: without this, sub="guest" 401s -- no
    user -- rather than the intended 403) and mint its JWT."""
    _get_or_create_shadow_user(full_app.state.user_repo, GUEST_USERNAME)
    token = create_access_token(data={"sub": GUEST_USERNAME})
    return {"Authorization": f"Bearer {token}"}


def _db(app):
    return app.state.user_repo.session_factory


def _seed_tutorial_figure(app) -> int:
    SessionLocal = _db(app)
    with SessionLocal() as db:
        book = models_db.TutorialBook(
            category="入门",
            title="Test Book",
            slug=f"book-{uuid.uuid4().hex[:8]}",
            asset_dir="test",
        )
        db.add(book)
        db.flush()
        chapter = models_db.TutorialChapter(book_id=book.id, chapter_number="1", title="Ch1", order=1)
        db.add(chapter)
        db.flush()
        section = models_db.TutorialSection(chapter_id=chapter.id, section_number="1", title="Sec1", order=1)
        db.add(section)
        db.flush()
        figure = models_db.TutorialFigure(section_id=section.id, page=1, figure_label="图1", order=1)
        db.add(figure)
        db.commit()
        return figure.id


def _mock_multiplayer_session(player_b_id, player_w_id, sgf="(;FF[4]SZ[19];B[pd])"):
    session = MagicMock()
    session.session_id = uuid.uuid4().hex
    session.user_id = None
    session.player_b_id = player_b_id
    session.player_w_id = player_w_id
    session.mode = "play"
    session.game_type = "free"
    session.lock = threading.Lock()
    session.sockets = set()
    session.pending_count_request = None
    session.pending_count_timestamp = None
    session._recorded = False
    katrain = MagicMock()
    katrain.get_sgf.return_value = sgf
    katrain.get_state.return_value = {"end_result": None}
    session.katrain = katrain
    return session


def _mock_platform_adapter(full_app, **attrs):
    """Replace app.state.platform_manager with a fresh MagicMock configured
    with the given adapter attributes, wired to a fresh gateway."""
    pm = MagicMock()
    pm.is_platform_game = MagicMock(return_value=False)
    pm._credential_store = MagicMock()
    pm._credential_store.load_credentials = MagicMock(return_value=None)
    adapter = MagicMock()
    for k, v in attrs.items():
        setattr(adapter, k, v)
    pm.get_adapter = MagicMock(return_value=adapter)
    full_app.state.platform_manager = pm
    full_app.state.platform_gateway = PlatformCommandGateway(pm, full_app.state.session_manager)
    return pm, adapter


async def _req(ac, method, url, headers=None, body=None):
    kwargs = {"headers": headers} if headers else {}
    if body is not None:
        kwargs["json"] = body
    return await ac.request(method, url, **kwargs)


# ---------------------------------------------------------------------------
# The full write-route surface (Step 3 + billing/board/platforms/live).
# Guest never reaches the handler body for any of these (the dependency
# raises first), so no real prerequisites are required for the 403 checks --
# only a body shape valid enough that pydantic validation doesn't race the
# auth dependency.
# ---------------------------------------------------------------------------

WRITE_ROUTES = [
    ("POST", "/api/v1/tsumego/progress/no-such-problem", {"completed": True, "attempts": 1}),
    ("POST", "/api/v1/users/follow/no-such-user", None),
    ("DELETE", "/api/v1/users/follow/no-such-user", None),
    ("POST", "/api/v1/live/matches/no-such-match/comments", {"content": "hi"}),
    ("DELETE", "/api/v1/live/comments/999999", None),
    ("POST", "/api/v1/user-games/", {"sgf_content": "(;)", "source": "import"}),
    ("PUT", "/api/v1/user-games/no-such-game", {"title": "x"}),
    ("DELETE", "/api/v1/user-games/no-such-game", None),
    ("POST", "/api/v1/user-games/no-such-game/analysis/save", {"session_id": "s", "game_id": "no-such-game"}),
    ("POST", "/api/v1/reports/", {"user_game_id": "no-such-game", "report_type": "normal"}),
    ("POST", "/api/v1/reports/999999/retry", None),
    ("POST", "/api/v1/billing/redeem", {"code": "NOPE"}),
    ("POST", "/api/v1/board/heartbeat", {"device_id": "dev-guest"}),
    ("GET", "/api/v1/board/devices", None),
    ("POST", "/api/v1/live/translations/learn", {"name": "X", "name_type": "player", "translations": {"en": "X"}}),
    ("POST", "/api/v1/platforms/ogs/login", {"username": "u", "password": "p"}),
    ("DELETE", "/api/v1/platforms/ogs/logout", None),
    ("POST", "/api/v1/platforms/ogs/sms/request", {"phone": "123"}),
    ("POST", "/api/v1/platforms/ogs/engine/start", {"level": 1, "human_color": "B", "handicap": 0}),
    ("POST", "/api/v1/platforms/ogs/engine/analysis", {"session_id": "s", "kind": "area"}),
    ("POST", "/api/v1/platforms/ogs/challenge", {"user_id": "u1"}),
    ("POST", "/api/v1/platforms/ogs/challenge/accept", {"challenge_id": "c1"}),
    ("POST", "/api/v1/platforms/ogs/challenge/decline", {"challenge_id": "c1"}),
    ("POST", "/api/v1/platforms/ogs/automatch/start", {}),
    ("POST", "/api/v1/platforms/ogs/automatch/cancel", None),
]

TUTORIAL_WRITE_ROUTES = [
    ("PUT", "board", {"board_payload": {"size": 19, "stones": {"B": [[3, 3]], "W": []}}}),
    ("PUT", "narration", {"narration": "hello"}),
    ("PUT", "verify", None),
    ("POST", "generate-audio", {"narration": "hello"}),
]


# ---------------------------------------------------------------------------
# Step 1 RED-turned-GREEN: guest 403 sweep + sanity body check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guest_403_sanity_body(full_app, guest_headers):
    """One representative route returns 403 with the exact detail body --
    proving the request reaches `require_writable_user`, not a 401
    short-circuit (which would mean the guest row wasn't seeded / resolved)."""
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/user-games/",
            headers=guest_headers,
            json={"sgf_content": "(;)", "source": "import"},
        )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Guest is read-only"}


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url,body", WRITE_ROUTES, ids=[f"{m}:{u}" for m, u, _ in WRITE_ROUTES])
async def test_guest_403_on_all_write_routes(full_app, guest_headers, method, url, body):
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await _req(ac, method, url, headers=guest_headers, body=body)
    assert resp.status_code == 403, f"{method} {url} -> {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("method,action,body", TUTORIAL_WRITE_ROUTES, ids=[r[1] for r in TUTORIAL_WRITE_ROUTES])
async def test_tutorial_writer_guest_403(full_app, guest_headers, method, action, body):
    figure_id = _seed_tutorial_figure(full_app)
    url = f"/api/v1/tutorials/figures/{figure_id}/{action}"
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await _req(ac, method, url, headers=guest_headers, body=body)
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Guest is read-only"}


@pytest.mark.asyncio
@pytest.mark.parametrize("method,action,body", TUTORIAL_WRITE_ROUTES, ids=[r[1] for r in TUTORIAL_WRITE_ROUTES])
async def test_tutorial_writer_anonymous_still_2xx(full_app, method, action, body, monkeypatch):
    """Guest-only reject (R3-F1): anonymous (no token at all) must stay allowed."""
    if action == "generate-audio":
        # Don't exercise the real TTS pipeline in a unit test -- out of scope
        # for the guest-mode auth boundary this task governs.
        async def _fake_generate_figure_audio(db, figure, narration):
            figure.narration = narration
            figure.audio_asset = "fake-audio.mp3"
            return figure

        monkeypatch.setattr(
            "katrain.web.api.v1.endpoints.tutorials.generate_figure_audio",
            _fake_generate_figure_audio,
        )

    figure_id = _seed_tutorial_figure(full_app)
    url = f"/api/v1/tutorials/figures/{figure_id}/{action}"
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await _req(ac, method, url, body=body)
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Real user -> 2xx WITH each route's real prerequisites (no regression).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_user_can_update_tsumego_progress(full_app):
    headers, user_id, _ = await _create_user_and_login(full_app, "tsumego-user")
    SessionLocal = _db(full_app)
    with SessionLocal() as db:
        db.add(models_db.TsumegoProblem(id="p-real-1", level="3d", category="life-death", hint="黑先"))
        db.commit()

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/tsumego/progress/p-real-1",
            headers=headers,
            json={"completed": True, "attempts": 1, "lastDuration": 42},
        )
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    with SessionLocal() as db:
        row = (
            db.query(models_db.UserTsumegoProgress)
            .filter_by(user_id=user_id, problem_id="p-real-1")
            .first()
        )
        assert row is not None
        assert row.completed is True


@pytest.mark.asyncio
async def test_real_user_can_follow_and_unfollow(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "follower")
    _, _, target_username = await _create_user_and_login(full_app, "target")

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        follow = await ac.post(f"/api/v1/users/follow/{target_username}", headers=headers)
        assert follow.status_code == 200
        unfollow = await ac.delete(f"/api/v1/users/follow/{target_username}", headers=headers)
        assert unfollow.status_code == 200


@pytest.mark.asyncio
async def test_real_user_can_create_and_delete_comment(full_app):
    headers, user_id, _ = await _create_user_and_login(full_app, "commenter")
    SessionLocal = _db(full_app)
    with SessionLocal() as db:
        db.add(
            models_db.LiveMatchDB(
                match_id="m-real-1",
                source="xingzhen",
                source_id="s-1",
                tournament="Test Cup",
                player_black="B",
                player_white="W",
            )
        )
        db.commit()

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        created = await ac.post(
            "/api/v1/live/matches/m-real-1/comments", headers=headers, json={"content": "nice move"}
        )
        assert created.status_code == 200
        comment_id = created.json()["id"]
        deleted = await ac.delete(f"/api/v1/live/comments/{comment_id}", headers=headers)
        assert deleted.status_code == 200

    with SessionLocal() as db:
        row = db.query(models_db.LiveCommentDB).filter_by(id=comment_id).first()
        assert row is not None
        assert row.user_id == user_id
        assert row.is_deleted is True  # soft delete


@pytest.mark.asyncio
async def test_real_user_can_learn_translation(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "translator-user")
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/live/translations/learn",
            headers=headers,
            json={"name": "王立诚", "name_type": "player", "translations": {"en": "Wang Licheng"}},
        )
    assert resp.status_code == 200, resp.text
    SessionLocal = _db(full_app)
    with SessionLocal() as db:
        row = db.query(models_db.PlayerTranslationDB).filter_by(canonical_name="王立诚").first()
        assert row is not None
        assert row.en == "Wang Licheng"


@pytest.mark.asyncio
async def test_real_user_can_create_update_delete_user_game_and_save_analysis(full_app):
    headers, user_id, _ = await _create_user_and_login(full_app, "gamer")
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        created = await ac.post(
            "/api/v1/user-games/",
            headers=headers,
            json={"sgf_content": "(;FF[4]SZ[19];B[pd];W[dp])", "source": "import", "move_count": 2},
        )
        assert created.status_code == 200
        game_id = created.json()["id"]

        updated = await ac.put(
            f"/api/v1/user-games/{game_id}", headers=headers, json={"title": "Updated title"}
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Updated title"

        # save_analysis needs a live session with an extractable analysis.
        mock_session = MagicMock()
        mock_session.session_id = uuid.uuid4().hex
        mock_session.lock = threading.Lock()
        mock_session.katrain._do_extract_analysis.return_value = [
            {"move_number": 1, "status": "complete", "winrate": 0.55, "score_lead": 1.0, "visits": 500}
        ]
        full_app.state.session_manager._sessions[mock_session.session_id] = mock_session

        saved = await ac.post(
            f"/api/v1/user-games/{game_id}/analysis/save",
            headers=headers,
            json={"session_id": mock_session.session_id, "game_id": game_id},
        )
        assert saved.status_code == 200
        assert saved.json()["saved_moves"] == 1

        deleted = await ac.delete(f"/api/v1/user-games/{game_id}", headers=headers)
        assert deleted.status_code == 200

        missing = await ac.get(f"/api/v1/user-games/{game_id}", headers=headers)
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_real_user_can_create_and_retry_report_task(full_app):
    headers, user_id, _ = await _create_user_and_login(full_app, "reporter")
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        game_resp = await ac.post(
            "/api/v1/user-games/",
            headers=headers,
            json={"sgf_content": "(;FF[4]SZ[19];B[pd];W[dp])", "source": "import", "move_count": 2},
        )
        assert game_resp.status_code == 200
        game_id = game_resp.json()["id"]

        created = await ac.post(
            "/api/v1/reports/", headers=headers, json={"user_game_id": game_id, "report_type": "normal"}
        )
        assert created.status_code == 200
        task_id = created.json()["id"]

    SessionLocal = _db(full_app)
    with SessionLocal() as db:
        task = db.query(models_db.ReportTask).filter_by(id=task_id).one()
        task.status = "failed"
        db.commit()

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        retried = await ac.post(f"/api/v1/reports/{task_id}/retry", headers=headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_real_user_can_redeem_code(full_app):
    headers, user_id, _ = await _create_user_and_login(full_app, "redeemer")
    SessionLocal = _db(full_app)
    with SessionLocal() as db:
        db.add(models_db.RedeemCode(code="REALCODE1", credits=300))
        db.commit()

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/billing/redeem", headers=headers, json={"code": "REALCODE1"})
    assert resp.status_code == 200
    assert resp.json()["credits"] >= 300

    with SessionLocal() as db:
        code = db.query(models_db.RedeemCode).filter_by(code="REALCODE1").one()
        assert code.used_by == user_id


@pytest.mark.asyncio
async def test_real_user_can_heartbeat_and_list_devices(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "device-user")
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        beat = await ac.post(
            "/api/v1/board/heartbeat", headers=headers, json={"device_id": "dev-real-1", "queue_depth": 0}
        )
        assert beat.status_code == 200
        assert beat.json()["status"] == "ok"

        listed = await ac.get("/api/v1/board/devices", headers=headers)
        assert listed.status_code == 200
        assert any(d["device_id"] == "dev-real-1" for d in listed.json())


# --- Platform mutations (10 routes) ---


@pytest.mark.asyncio
async def test_real_user_can_platform_login(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "plat-login")
    pm, adapter = _mock_platform_adapter(full_app)
    pm.connect_platform = AsyncMock(return_value=True)

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/platforms/ogs/login", headers=headers, json={"username": "u", "password": "p"}
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"


@pytest.mark.asyncio
async def test_real_user_can_platform_logout(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "plat-logout")
    pm, adapter = _mock_platform_adapter(full_app)
    pm.disconnect_platform = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.delete("/api/v1/platforms/ogs/logout", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"
    pm._credential_store.delete_credentials.assert_called_once()


@pytest.mark.asyncio
async def test_real_user_can_request_sms(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "plat-sms")
    pm, adapter = _mock_platform_adapter(full_app)
    adapter.request_sms_code = AsyncMock(return_value=True)

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/platforms/golaxy/sms/request", headers=headers, json={"phone": "13800000000"}
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_real_user_can_start_engine_game(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "plat-engine-start")
    pm, adapter = _mock_platform_adapter(full_app, is_connected=True, supports_engine_play=True)
    adapter.get_engine_levels = MagicMock(return_value=[{"elo_score": 1, "name": "beginner"}])
    pm.start_engine_game = AsyncMock(return_value="engine-session-1")

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/platforms/golaxy/engine/start",
            headers=headers,
            json={"level": 1, "human_color": "B", "handicap": 0},
        )
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "engine-session-1"


@pytest.mark.asyncio
async def test_real_user_can_run_engine_analysis(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "plat-engine-analysis")
    pm, adapter = _mock_platform_adapter(full_app, is_connected=True, supports_engine_play=True)
    pm.engine_analysis = AsyncMock(return_value=AreaResult(area=[0.1, 0.2], winrate=0.55, delta=1.0))

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            headers=headers,
            json={"session_id": "engine-session-1", "kind": "area"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["winrate"] == 0.55


@pytest.mark.asyncio
async def test_real_user_can_send_challenge(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "plat-challenge")
    pm, adapter = _mock_platform_adapter(full_app, is_connected=True)
    adapter.send_challenge = AsyncMock(return_value="challenge-1")

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/platforms/ogs/challenge", headers=headers, json={"user_id": "u1"}
        )
    assert resp.status_code == 200
    assert resp.json()["challenge_id"] == "challenge-1"


@pytest.mark.asyncio
async def test_real_user_can_accept_challenge(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "plat-accept")
    pm, adapter = _mock_platform_adapter(full_app, is_connected=True)
    game_session = SimpleNamespace(my_color="B", opponent=SimpleNamespace(username="foe"), game_id="g-1")
    adapter.accept_challenge = AsyncMock(return_value=game_session)
    pm.start_platform_game = AsyncMock(return_value="platform-session-1")

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/platforms/ogs/challenge/accept", headers=headers, json={"challenge_id": "c-1"}
        )
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "platform-session-1"


@pytest.mark.asyncio
async def test_real_user_can_decline_challenge(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "plat-decline")
    pm, adapter = _mock_platform_adapter(full_app, is_connected=True)
    adapter.decline_challenge = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/platforms/ogs/challenge/decline", headers=headers, json={"challenge_id": "c-1"}
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"


@pytest.mark.asyncio
async def test_real_user_can_start_and_cancel_automatch(full_app):
    headers, _, _ = await _create_user_and_login(full_app, "plat-automatch")
    pm, adapter = _mock_platform_adapter(full_app, is_connected=True, supports_automatch=True)
    adapter.start_automatch = AsyncMock(return_value=None)
    adapter.cancel_automatch = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        started = await ac.post("/api/v1/platforms/ogs/automatch/start", headers=headers, json={})
        assert started.status_code == 200
        assert started.json()["status"] == "searching"

        cancelled = await ac.post("/api/v1/platforms/ogs/automatch/cancel", headers=headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Board-mode representative proof: guest is blocked BEFORE the handler body
# ever reaches `repository_dispatcher.*` (so the online-vs-offline dispatch
# split -- remote write vs local write + sync_queue enqueue, see
# tests/web_ui/test_tsumego_offline.py -- never even gets a chance to run).
# tsumego.update_progress is the representative route; the SAME
# "dependency raises before the handler body runs" guarantee holds for every
# other route (already proven exhaustively by test_guest_403_on_all_write_routes),
# so this is intentionally not duplicated per-route.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guest_blocked_before_reaching_board_mode_dispatcher(full_app, guest_headers):
    dispatcher = MagicMock()
    dispatcher.tsumego_update_progress = AsyncMock(return_value={"success": True})
    full_app.state.repository_dispatcher = dispatcher

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/tsumego/progress/anything",
            headers=guest_headers,
            json={"completed": True, "attempts": 1},
        )
    assert resp.status_code == 403
    dispatcher.tsumego_update_progress.assert_not_called()


# ---------------------------------------------------------------------------
# Zero persistence, exhaustively, after attempting every guest write.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guest_writes_leave_zero_rows_and_zero_sync(full_app, guest_headers):
    figure_id = _seed_tutorial_figure(full_app)

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        for method, url, body in WRITE_ROUTES:
            resp = await _req(ac, method, url, headers=guest_headers, body=body)
            assert resp.status_code == 403, f"{method} {url} unexpectedly not blocked: {resp.status_code}"
        for method, action, body in TUTORIAL_WRITE_ROUTES:
            resp = await _req(
                ac, method, f"/api/v1/tutorials/figures/{figure_id}/{action}", headers=guest_headers, body=body
            )
            assert resp.status_code == 403

    SessionLocal = _db(full_app)
    with SessionLocal() as db:
        assert db.query(models_db.UserGame).count() == 0
        assert db.query(models_db.UserGameAnalysis).count() == 0
        assert db.query(models_db.UserTsumegoProgress).count() == 0
        assert db.query(models_db.UserTutorialProgress).count() == 0
        assert db.query(models_db.Relationship).count() == 0
        assert db.query(models_db.LiveCommentDB).count() == 0
        assert db.query(models_db.ReportTask).count() == 0
        assert db.query(models_db.ReportTaskMove).count() == 0
        assert db.query(models_db.DeviceHeartbeatDB).count() == 0
        assert db.query(models_db.RatingHistory).count() == 0
        assert db.query(models_db.PlatformGameDB).count() == 0
        assert db.query(models_db.CreditTransaction).count() == 0
        assert db.query(models_db.RedeemCode).filter(models_db.RedeemCode.used_by.isnot(None)).count() == 0
        assert db.query(models_db.SyncQueueEntry).count() == 0
        assert db.query(models_db.PlayerTranslationDB).count() == 0
        assert db.query(models_db.TournamentTranslationDB).count() == 0
        assert (
            db.query(models_db.BoardPayloadHistory)
            .filter(models_db.BoardPayloadHistory.changed_by == GUEST_USERNAME)
            .count()
            == 0
        )


# ---------------------------------------------------------------------------
# Lobby WebSocket reject (severs multiplayer at the entry point).
# ---------------------------------------------------------------------------


def test_guest_rejected_from_lobby_ws(full_app):
    guest = _get_or_create_shadow_user(full_app.state.user_repo, GUEST_USERNAME)
    token = create_access_token(data={"sub": GUEST_USERNAME})

    with TestClient(full_app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/lobby?token={token}") as websocket:
                websocket.receive_json()

    assert exc_info.value.code == 1008
    assert guest["id"] not in full_app.state.lobby_manager.get_online_user_ids()


# ---------------------------------------------------------------------------
# Multiplayer-termination participant guard on resign/timeout (Step 5b).
# CRITICAL: the guard must fire BEFORE the platform-gateway branch, else
# gateway.resign(...) (which mutates the remote game AND runs a local
# resign) runs on a caller who was never a participant.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resign_local_multiplayer_rejects_nonparticipants_but_allows_participant(full_app, guest_headers):
    headers1, user1_id, _ = await _create_user_and_login(full_app, "resign-p1")
    headers2, _, _ = await _create_user_and_login(full_app, "resign-outsider")

    mock_session = _mock_multiplayer_session(player_b_id=user1_id, player_w_id=-1)
    full_app.state.session_manager._sessions[mock_session.session_id] = mock_session

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        anon_resp = await ac.post("/api/resign", json={"session_id": mock_session.session_id})
        guest_resp = await ac.post(
            "/api/resign", headers=guest_headers, json={"session_id": mock_session.session_id}
        )
        outsider_resp = await ac.post(
            "/api/resign", headers=headers2, json={"session_id": mock_session.session_id}
        )

    assert anon_resp.status_code == 403
    assert guest_resp.status_code == 403
    assert outsider_resp.status_code == 403
    for r in (anon_resp, guest_resp, outsider_resp):
        assert r.json() == {"detail": "Not a participant"}

    # State untouched: the direct local-resign path was never reached.
    mock_session.katrain.assert_not_called()
    with _db(full_app)() as db:
        assert db.query(models_db.UserGame).count() == 0

    # Legit participant succeeds.
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        ok_resp = await ac.post("/api/resign", headers=headers1, json={"session_id": mock_session.session_id})
    assert ok_resp.status_code == 200
    mock_session.katrain.assert_any_call("resign")
    with _db(full_app)() as db:
        assert db.query(models_db.UserGame).filter_by(user_id=user1_id).count() == 1


@pytest.mark.asyncio
async def test_resign_platform_backed_rejects_nonparticipants_and_skips_gateway(full_app, guest_headers):
    headers1, user1_id, _ = await _create_user_and_login(full_app, "plat-resign-p1")
    headers2, _, _ = await _create_user_and_login(full_app, "plat-resign-outsider")

    mock_session = _mock_multiplayer_session(player_b_id=user1_id, player_w_id=-1)
    full_app.state.session_manager._sessions[mock_session.session_id] = mock_session

    full_app.state.platform_manager.is_platform_game = MagicMock(return_value=True)
    full_app.state.platform_gateway.resign = AsyncMock(return_value={"status": "ok"})

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        guest_resp = await ac.post(
            "/api/resign", headers=guest_headers, json={"session_id": mock_session.session_id}
        )
        outsider_resp = await ac.post(
            "/api/resign", headers=headers2, json={"session_id": mock_session.session_id}
        )

    assert guest_resp.status_code == 403
    assert outsider_resp.status_code == 403
    full_app.state.platform_gateway.resign.assert_not_called()
    mock_session.katrain.assert_not_called()

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        ok_resp = await ac.post("/api/resign", headers=headers1, json={"session_id": mock_session.session_id})
    assert ok_resp.status_code == 200
    full_app.state.platform_gateway.resign.assert_awaited_once()


@pytest.mark.asyncio
async def test_timeout_local_multiplayer_rejects_nonparticipants_but_allows_participant(full_app, guest_headers):
    headers1, user1_id, _ = await _create_user_and_login(full_app, "timeout-p1")
    headers2, _, _ = await _create_user_and_login(full_app, "timeout-outsider")

    mock_session = _mock_multiplayer_session(player_b_id=user1_id, player_w_id=-1)
    full_app.state.session_manager._sessions[mock_session.session_id] = mock_session

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        anon_resp = await ac.post("/api/timeout", json={"session_id": mock_session.session_id})
        guest_resp = await ac.post(
            "/api/timeout", headers=guest_headers, json={"session_id": mock_session.session_id}
        )
        outsider_resp = await ac.post(
            "/api/timeout", headers=headers2, json={"session_id": mock_session.session_id}
        )

    assert anon_resp.status_code == 403
    assert guest_resp.status_code == 403
    assert outsider_resp.status_code == 403
    mock_session.katrain.assert_not_called()
    with _db(full_app)() as db:
        assert db.query(models_db.UserGame).count() == 0

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        ok_resp = await ac.post("/api/timeout", headers=headers1, json={"session_id": mock_session.session_id})
    assert ok_resp.status_code == 200
    mock_session.katrain.assert_any_call("timeout")



# ---------------------------------------------------------------------------
# `_is_guest_participant` True branch (TES-1, final-review defense-in-depth
# follow-up): guest genuinely SEATED as a participant. This is the only way
# to reach the belt-and-suspenders recording guard's True branch at all --
# the participant-guard tests above seat guest as a NON-participant (e.g.
# player_w_id=-1), so control never gets past `_require_multiplayer_participant`
# to exercise this guard. In real deployments guest can never actually be
# seated (rejected at `/ws/lobby`, so it never enters matchmaking), but this
# proves the second, independent line of defense also holds on its own: IF a
# guest ever ends up seated (compound failure), recording is still skipped and
# zero rows -- for either player -- are ever written.
# ---------------------------------------------------------------------------


def _seat_guest_headers_and_id(full_app):
    guest_row = _get_or_create_shadow_user(full_app.state.user_repo, GUEST_USERNAME)
    token = create_access_token(data={"sub": GUEST_USERNAME})
    return {"Authorization": f"Bearer {token}"}, guest_row["id"]


@pytest.mark.asyncio
async def test_resign_by_seated_guest_participant_skips_recording_and_writes_zero_rows(full_app):
    seated_guest_headers, guest_id = _seat_guest_headers_and_id(full_app)
    _, opponent_id, _ = await _create_user_and_login(full_app, "resign-vs-guest")

    mock_session = _mock_multiplayer_session(player_b_id=guest_id, player_w_id=opponent_id)
    full_app.state.session_manager._sessions[mock_session.session_id] = mock_session

    record_spy = MagicMock(wraps=full_app.state.game_repo.record_multiplayer_game)
    full_app.state.game_repo.record_multiplayer_game = record_spy

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/resign", headers=seated_guest_headers, json={"session_id": mock_session.session_id}
        )

    assert resp.status_code == 200  # participant check passed -- guest WAS seated
    mock_session.katrain.assert_any_call("resign")  # the resign mutation itself still runs
    record_spy.assert_not_called()
    with _db(full_app)() as db:
        assert db.query(models_db.UserGame).filter_by(user_id=guest_id).count() == 0
        assert db.query(models_db.UserGame).filter_by(user_id=opponent_id).count() == 0


@pytest.mark.asyncio
async def test_timeout_by_seated_guest_participant_skips_recording_and_writes_zero_rows(full_app):
    seated_guest_headers, guest_id = _seat_guest_headers_and_id(full_app)
    _, opponent_id, _ = await _create_user_and_login(full_app, "timeout-vs-guest")

    mock_session = _mock_multiplayer_session(player_b_id=opponent_id, player_w_id=guest_id)
    full_app.state.session_manager._sessions[mock_session.session_id] = mock_session

    record_spy = MagicMock(wraps=full_app.state.game_repo.record_multiplayer_game)
    full_app.state.game_repo.record_multiplayer_game = record_spy

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/timeout", headers=seated_guest_headers, json={"session_id": mock_session.session_id}
        )

    assert resp.status_code == 200
    mock_session.katrain.assert_any_call("timeout")
    record_spy.assert_not_called()
    with _db(full_app)() as db:
        assert db.query(models_db.UserGame).filter_by(user_id=guest_id).count() == 0
        assert db.query(models_db.UserGame).filter_by(user_id=opponent_id).count() == 0


@pytest.mark.asyncio
async def test_resign_and_timeout_still_open_for_single_player_session(full_app):
    """Non-multiplayer sessions (both player ids None) are unaffected by the
    new guard -- single-player/local resign stays open, including for an
    anonymous caller (unauthenticated local practice)."""
    resign_session = _mock_multiplayer_session(player_b_id=None, player_w_id=None)
    timeout_session = _mock_multiplayer_session(player_b_id=None, player_w_id=None)
    full_app.state.session_manager._sessions[resign_session.session_id] = resign_session
    full_app.state.session_manager._sessions[timeout_session.session_id] = timeout_session

    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resign_resp = await ac.post("/api/resign", json={"session_id": resign_session.session_id})
        timeout_resp = await ac.post("/api/timeout", json={"session_id": timeout_session.session_id})

    assert resign_resp.status_code == 200
    assert timeout_resp.status_code == 200
