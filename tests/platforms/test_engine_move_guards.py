"""Server-level guards for the engine-move commit protocol (Task 4, B2/D5).

While a Golaxy 人机对弈 (engine-play) move is pending inside the ~180s genmove
tunnel, tree-mutating endpoints must not be allowed to race it (review B2) — the
eventual AI reply would land on whatever node happens to be current when it
returns, not the one it was actually computed against. Task 4's gateway also
carries a defensive position-token assert for this (see test_engine_gateway.py),
but these guards are the first line of defense: an immediate, correct 409/403
instead of a move silently discarded up to 3 minutes later.

Scope (fable5 裁决 2026-07-11, plan.md 基线记录):
  - 409 while pending: /api/undo, /api/redo, /api/nav, /api/nav/mistake, /api/nav/branch
  - 403 unconditionally (pending or not): /api/ai-move — it bypasses the tunnel
    and triggers local KataGo directly, never valid for an engine game.
  - Everything else (sgf/load, new-game, edit-game, node/*, player/swap, ...) is
    NOT guarded this iteration — out of scope, not this file's concern.

NOTE on test wiring: this deliberately does NOT use FastAPI's lifespan (no
`with TestClient(app) as c:`) — running the real startup path off-thread (as
TestClient's sync wrapper does) pulls in katrain.web.interface -> real Kivy/
KivyMD, which segfaults here when initialized off the main thread (macOS). So,
like tests/platforms/test_engine_endpoints.py, this builds the app with
`create_app()` (module wiring only, no lifespan) and attaches a real
PlatformManager/PlatformCommandGateway + a MagicMock-based session by hand
(same pattern as tests/web_ui/test_ranked_rules.py's `_make_mock_session`) —
exercising the REAL guard code in server.py without ever touching real Kivy.
"""

import threading
import time
import uuid
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.platforms.gateway import PlatformCommandGateway
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import PlatformGameContext
from katrain.web.server import create_app


def _make_mock_session(session_id=None):
    session = MagicMock()
    session.session_id = session_id or uuid.uuid4().hex
    session.mode = "play"
    session.lock = threading.Lock()
    session.last_access = time.time()
    session.pending_count_request = None
    session.pending_count_timestamp = None
    katrain = MagicMock()
    katrain.game_type = "free"
    katrain.get_state.return_value = {"game_type": "free"}
    session.katrain = katrain
    return session


def _build_app():
    app = create_app(enable_engine=False)
    pm = PlatformManager(app.state.session_manager)
    app.state.platform_manager = pm
    app.state.platform_gateway = PlatformCommandGateway(pm, app.state.session_manager)
    return app, pm


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _register_engine_ctx(pm, session_id: str, pending: bool) -> PlatformGameContext:
    ctx = PlatformGameContext(
        session_id=session_id,
        platform="golaxy",
        remote_game_id="g",
        my_color="B",
        is_engine=True,
    )
    if pending:
        ctx.set_pending("move")
    pm._active_games["g"] = ctx
    pm._session_to_game[session_id] = "g"
    return ctx


def _register_platform_ctx_non_engine(pm, session_id: str) -> PlatformGameContext:
    """A human-vs-human platform game (OGS/Fox-style) — not engine, must be unaffected."""
    ctx = PlatformGameContext(session_id=session_id, platform="ogs", remote_game_id="g2", my_color="B")
    pm._active_games["g2"] = ctx
    pm._session_to_game[session_id] = "g2"
    return ctx


# (endpoint, extra JSON body fields) for the pending-gated guard family.
GUARDED_ENDPOINTS = [
    ("/api/undo", {"n_times": 1}),
    ("/api/redo", {"n_times": 1}),
    ("/api/nav", {"node_id": None}),
    ("/api/nav/mistake", {"fn": "redo"}),
    ("/api/nav/branch", {"direction": 1}),
]


class TestPendingGuards409:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint,extra", GUARDED_ENDPOINTS)
    async def test_409_while_engine_move_pending(self, endpoint, extra):
        app, pm = _build_app()
        session = _make_mock_session()
        app.state.session_manager._sessions[session.session_id] = session
        _register_engine_ctx(pm, session.session_id, pending=True)

        async with _client(app) as ac:
            r = await ac.post(endpoint, json={"session_id": session.session_id, **extra})

        assert r.status_code == 409
        assert r.json()["detail"] == "engine move pending"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint,extra", GUARDED_ENDPOINTS)
    async def test_ok_after_pending_cleared(self, endpoint, extra):
        app, pm = _build_app()
        session = _make_mock_session()
        app.state.session_manager._sessions[session.session_id] = session
        ctx = _register_engine_ctx(pm, session.session_id, pending=True)
        ctx.clear_pending()

        async with _client(app) as ac:
            r = await ac.post(endpoint, json={"session_id": session.session_id, **extra})

        assert r.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint,extra", GUARDED_ENDPOINTS)
    async def test_non_engine_platform_session_unaffected(self, endpoint, extra):
        """A human-vs-human platform game is not 'engine' — the pending guard must
        not fire for it even though it IS a platform-backed session."""
        app, pm = _build_app()
        session = _make_mock_session()
        app.state.session_manager._sessions[session.session_id] = session
        _register_platform_ctx_non_engine(pm, session.session_id)

        async with _client(app) as ac:
            r = await ac.post(endpoint, json={"session_id": session.session_id, **extra})

        assert r.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint,extra", GUARDED_ENDPOINTS)
    async def test_plain_local_session_unaffected(self, endpoint, extra):
        """No platform context at all (ordinary local kiosk game) — never blocked."""
        app, pm = _build_app()
        session = _make_mock_session()
        app.state.session_manager._sessions[session.session_id] = session

        async with _client(app) as ac:
            r = await ac.post(endpoint, json={"session_id": session.session_id, **extra})

        assert r.status_code == 200


class TestAiMoveGuard403:
    @pytest.mark.asyncio
    async def test_403_for_engine_game_while_pending(self):
        app, pm = _build_app()
        session = _make_mock_session()
        app.state.session_manager._sessions[session.session_id] = session
        _register_engine_ctx(pm, session.session_id, pending=True)

        async with _client(app) as ac:
            r = await ac.post("/api/ai-move", json={"session_id": session.session_id})

        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_403_for_engine_game_even_when_not_pending(self):
        """Unconditional: /api/ai-move bypasses the tunnel entirely, so it's never
        valid for an engine game regardless of pending state."""
        app, pm = _build_app()
        session = _make_mock_session()
        app.state.session_manager._sessions[session.session_id] = session
        _register_engine_ctx(pm, session.session_id, pending=False)

        async with _client(app) as ac:
            r = await ac.post("/api/ai-move", json={"session_id": session.session_id})

        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_non_engine_platform_session_unaffected(self):
        app, pm = _build_app()
        session = _make_mock_session()
        app.state.session_manager._sessions[session.session_id] = session
        _register_platform_ctx_non_engine(pm, session.session_id)

        async with _client(app) as ac:
            r = await ac.post("/api/ai-move", json={"session_id": session.session_id})

        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_plain_local_session_unaffected(self):
        app, pm = _build_app()
        session = _make_mock_session()
        app.state.session_manager._sessions[session.session_id] = session

        async with _client(app) as ac:
            r = await ac.post("/api/ai-move", json={"session_id": session.session_id})

        assert r.status_code == 200
