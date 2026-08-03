"""Ranked games must reject undo server-side (PRD R5.3/R6.1).

NOTE: tests/web_ui/conftest.py replaces the whole `katrain.web.interface` module
with a MagicMock (to avoid pulling in Kivy). That means a real HTTP round-trip
through /api/session + /api/game/setup never actually executes
WebKaTrain._do_new_game, so `session.katrain.game_type` would never be set to a
real string that way. Following the established pattern in
tests/web_ui/test_ai_game_autosave.py, we build a mock WebSession by hand (with a
concrete `game_type` on the mocked `katrain`) and inject it directly into the
session manager, so the ban condition in /api/undo is exercised against a
realistic value instead of an unconfigured Mock attribute.
"""

import threading
import time
import uuid

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from katrain.web.server import create_app


@pytest.fixture
def client():
    app = create_app(enable_engine=False)
    with TestClient(app) as c:
        yield c


def _make_mock_session(game_type):
    session = MagicMock()
    session.session_id = uuid.uuid4().hex
    session.mode = "play"
    session.lock = threading.Lock()
    session.last_access = time.time()  # real float: app shutdown's cleanup_expired() compares this
    session.pending_count_request = None  # real None: cleanup_expired() checks "is not None"
    session.pending_count_timestamp = None
    katrain = MagicMock()
    katrain.game_type = game_type
    katrain.get_state.return_value = {"game_type": game_type}
    session.katrain = katrain
    return session


class TestRankedUndo:
    def test_ranked_undo_403(self, client):
        app = client.app
        session = _make_mock_session("ranked")
        app.state.session_manager._sessions[session.session_id] = session

        r = client.post("/api/undo", json={"session_id": session.session_id, "n_times": 1})
        assert r.status_code == 403

    def test_free_undo_ok(self, client):
        app = client.app
        session = _make_mock_session("free")
        app.state.session_manager._sessions[session.session_id] = session

        r = client.post("/api/undo", json={"session_id": session.session_id, "n_times": 1})
        assert r.status_code == 200

    @pytest.mark.parametrize("endpoint", ["undo", "redo"])
    def test_ai_ladder_ranked_tree_mutation_403(self, client, endpoint):
        app = client.app
        session = _make_mock_session("ai_ladder_ranked")
        app.state.session_manager._sessions[session.session_id] = session

        r = client.post(f"/api/{endpoint}", json={"session_id": session.session_id, "n_times": 1})
        assert r.status_code == 403
