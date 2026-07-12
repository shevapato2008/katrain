import os

# Warm up the real kivy/kivymd Window singleton on the MAIN thread before any
# TestClient request runs. Starlette's TestClient bridges sync<->async via a
# background "portal" thread, and WebKaTrain.__init__ does `from kivymd.app
# import MDApp` on first use — importing kivymd for the first time from that
# background thread triggers real SDL2/Cocoa window creation off the main
# thread, which aborts the process on macOS (NSInternalInconsistencyException:
# "setting the main menu on a non-main thread"). Importing here, before the
# portal thread exists, makes the (cached) module import a no-op later.
import kivymd.app  # noqa: F401

import pytest
from fastapi.testclient import TestClient
from katrain.web.server import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _new_session(client):
    r = client.post("/api/session", json={})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def test_pvp_local_sets_both_players_human(client):
    sid = _new_session(client)
    r = client.post(
        "/api/game/setup",
        json={
            "session_id": sid,
            "mode": "pvp_local",
            "settings": {
                "board_size": 19,
                "rules": "chinese",
                "handicap": 0,
                "komi": 7.5,
                "black_name": "小明",
                "white_name": "小红",
                "time_enabled": False,
            },
        },
    )
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["players_info"]["B"]["player_type"] == "player:human"
    assert state["players_info"]["W"]["player_type"] == "player:human"
    assert state["players_info"]["B"]["name"] == "小明"
    assert state["players_info"]["W"]["name"] == "小红"
    # pvp_local behaves like free for analysis, but is distinguishable
    assert state["game_type"] == "pvp_local"
    assert state.get("analysis_allowed") is not False
