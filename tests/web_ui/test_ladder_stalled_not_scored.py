"""A 升降级对弈 game the engine could not actually play must never reach the ledger.

Found on an RK3562 kiosk (2026-08-05): its HTTP engine does not advertise certified
ladder capabilities, so `ai:ladder` fails closed and plays nothing
(interface._surface_ladder_unavailable sets `last_ladder_error`). The game is then
stuck — and however it ends, it is an artefact of our engine, not a result:

  - the player gives up on a board that will never answer -> a *loss* would be banked
  - the AI's own clock expires -> galaxy auto-forfeits it -> a *win* would be banked,
    handing out promotion credit for a game nobody played

Both are silent: the rank moves and nothing on screen says why. Hence a test rather
than a comment.
"""

import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient

pytest.importorskip("fastapi")

# The shared web_ui conftest mocks `katrain.web.interface` as a MagicMock so unrelated
# tests don't drag in the kivy import chain. This suite plays a real game to the point
# of recording it, so it needs the real WebKaTrain (same pattern as
# test_ladder_injection.py). Blast radius is limited to this module.
sys.modules.pop("katrain.web.interface", None)

from katrain.core.ladder import LADDER_ALLOW_PROVISIONAL_ENV  # noqa: E402
from katrain.web.core.config import settings  # noqa: E402
from katrain.web.core.db import Base  # noqa: E402
from katrain.web.core.models_db import AiLadderLedger  # noqa: E402
from katrain.web.server import create_app  # noqa: E402

DB_FILE = "./test_ladder_stalled.db"


@pytest.fixture
def app(monkeypatch):
    # No rung is certified yet (ladder._CERTIFIED_RUNGS is empty by design), so the
    # ladder refuses to seat anyone unless the provisional switch is on. The switch
    # only decides whether a game may START; it has no bearing on what this test
    # asserts, which is what happens to a started game that stalled.
    monkeypatch.setenv(LADDER_ALLOW_PROVISIONAL_ENV, "1")
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{DB_FILE}")
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    application = create_app(enable_engine=False)

    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.user_game_repo import UserGameAnalysisRepository, UserGameRepository

    application.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)
    application.state.user_game_repo = UserGameRepository(TestSessionLocal)
    application.state.user_game_analysis_repo = UserGameAnalysisRepository(TestSessionLocal)
    application.state.test_session_factory = TestSessionLocal

    yield application

    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)


async def _start_ladder_game(ac, app):
    from passlib.context import CryptContext

    app.state.user_repo.create_user("stalled", CryptContext(schemes=["bcrypt"], deprecated="auto").hash("pw"))
    login = await ac.post("/api/v1/auth/login", json={"username": "stalled", "password": "pw"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Authenticated session creation: resign only records (and therefore only settles)
    # when the session is owned by a user — see server.py resign().
    session_id = (await ac.post("/api/session", json={}, headers=headers)).json()["session_id"]
    started = await ac.post(
        "/api/ladder/start-game",
        json={"session_id": session_id, "color": "B"},
        headers=headers,
    )
    assert started.status_code == 200, started.text
    return session_id, headers


@pytest.mark.asyncio
async def test_stalled_ladder_game_is_not_scored(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        session_id, headers = await _start_ladder_game(ac, app)

        # Exactly what the board does when the engine cannot serve the seated rung.
        session = app.state.session_manager.get_session(session_id)
        session.katrain.last_ladder_error = True

        resigned = await ac.post("/api/resign", json={"session_id": session_id}, headers=headers)
        assert resigned.status_code == 200, resigned.text

        result = (await ac.get(f"/api/ladder/session-result/{session_id}", headers=headers)).json()
        assert result["settled"] is False
        # The reason is what the endgame card reads to explain itself; a generic
        # failure reason here would tell the player to report a bug that isn't one.
        assert result["reason"] == "engine_unavailable"

        db = app.state.test_session_factory()
        try:
            assert db.query(AiLadderLedger).count() == 0
        finally:
            db.close()


@pytest.mark.asyncio
async def test_recovered_ladder_game_is_still_scored(app):
    """The flag is per-turn, not per-game: an engine that hiccuped and then played on
    must not cost the player the whole game's result."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        session_id, headers = await _start_ladder_game(ac, app)

        session = app.state.session_manager.get_session(session_id)
        session.katrain.last_ladder_error = True
        session.katrain.last_ladder_error = False  # a later AI move succeeded

        await ac.post("/api/resign", json={"session_id": session_id}, headers=headers)

        result = (await ac.get(f"/api/ladder/session-result/{session_id}", headers=headers)).json()
        assert result["settled"] is True
        assert result["won"] is False  # resigned as Black
