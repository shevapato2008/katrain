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
def client(tmp_path):
    # `with TestClient(app)` 会跑 lifespan ⇒ 会**真连数据库**。仓里默认的
    # DATABASE_URL 指向 docker 里的 PostgreSQL，本机没起时这四条就 error。
    # 2026-09-10 之前它们「绿」的真实原因是 tests/web_ui/test_lobby_api.py 换库之后
    # 从不还原（按文件名排序它跑在前面），把 core.db 的 engine 留成了 sqlite ——
    # 也就是说这四条一直靠另一个文件的副作用活着，单独跑一直是 error。
    # 那份泄漏一修就露馅，所以这里自带一个 SQLite。实测：任意可用的库都能让它们全绿。
    from conftest import isolated_core_db

    with isolated_core_db(f"sqlite:///{tmp_path / 'ranked.db'}"):
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

    def test_anonymous_free_undo_requires_auth(self, client):
        app = client.app
        session = _make_mock_session("free")
        app.state.session_manager._sessions[session.session_id] = session

        r = client.post("/api/undo", json={"session_id": session.session_id, "n_times": 1})
        assert r.status_code == 401

    @pytest.mark.parametrize("endpoint", ["undo", "redo"])
    def test_ai_ladder_ranked_tree_mutation_403(self, client, endpoint):
        app = client.app
        session = _make_mock_session("ai_ladder_ranked")
        app.state.session_manager._sessions[session.session_id] = session

        r = client.post(f"/api/{endpoint}", json={"session_id": session.session_id, "n_times": 1})
        assert r.status_code == 403
