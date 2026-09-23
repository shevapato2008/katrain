"""Ending a game the server has already forgotten answers honestly instead of 404-ing.

On RK3562 2026-09-20 a cross-platform game's session was reclaimed underneath an open
kiosk page; resign then 404'd and the user could not leave the screen.

Two things this must NOT do:
- claim the game ended. Eviction does not call the platform adapter (gateway.py:399-420),
  so the remote game may well still be live.
- weaken guard_session_terminator (server.py:921). A session that does not exist has no
  owner to impersonate and no ledger row to write - see the spec's E6.
"""

# kivymd's first import from Starlette's portal thread opens a real SDL2/Cocoa window
# off the main thread and aborts on macOS. Same preamble as test_local_play_game_end.py.
import kivymd.app  # noqa: F401

import types
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.server import create_app

OWNER = types.SimpleNamespace(id=7, username="owner", uuid="u-7")


@pytest.fixture
def client(isolated_session_factory):
    """Same shape as tests/test_local_play_game_end.py's fixture - one app factory only."""
    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory  # must precede TestClient: lifespan uses it
    with TestClient(app) as c:
        c.app.state.user_game_repo = MagicMock()
        c.app.state.repository_dispatcher = None
        c.app.dependency_overrides[get_current_user_optional] = lambda: OWNER
        yield c
        c.app.dependency_overrides.clear()
        for session in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager.remove_session(session.session_id)


def test_resign_unknown_session_reports_session_gone(client):
    response = client.post("/api/resign", json={"session_id": "no-such-session"})
    assert response.status_code == 200
    assert response.json() == {"session_id": "no-such-session", "status": "session_gone"}


def test_timeout_unknown_session_reports_session_gone(client):
    response = client.post("/api/timeout", json={"session_id": "no-such-session"})
    assert response.status_code == 200
    assert response.json()["status"] == "session_gone"


def test_the_reply_never_claims_the_game_ended(client):
    """Eviction says nothing about the remote game. Claiming a result here would make
    the kiosk tell the user they resigned a game that is still running."""
    body = client.post("/api/resign", json={"session_id": "no-such-session"}).json()
    assert "ended" not in body
    assert "state" not in body
    assert "result" not in body


def test_the_reply_writes_nothing_to_the_ledger(client):
    client.post("/api/resign", json={"session_id": "no-such-session"})
    client.post("/api/timeout", json={"session_id": "no-such-session"})
    assert client.app.state.user_game_repo.create.call_count == 0


def test_other_endpoints_still_404_on_an_unknown_session(client):
    """Only the two END-GAME endpoints change. Silently succeeding on /api/state would
    be lying about a game that does not exist."""
    assert client.get("/api/state", params={"session_id": "no-such-session"}).status_code == 404
