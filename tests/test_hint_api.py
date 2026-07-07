"""Hint gating matrix (PRD D3) + endpoint behaviour with fake router/orchestrator."""

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import hint
from katrain.web.core.hint_gate import DefaultHintGate
from katrain.web.core.physical_play import PhysicalPlayConfig


class TestDefaultHintGate:
    def test_free_allowed_with_engine(self):
        d = DefaultHintGate("cloud").check(game_type="free", user_id=None)
        assert d.allowed and d.engine == "cloud"

    def test_ranked_denied(self):
        d = DefaultHintGate("local").check(game_type="ranked", user_id=1)
        assert not d.allowed and d.reason == "ranked_forbidden"

    def test_engine_off_denied(self):
        d = DefaultHintGate("off").check(game_type="free", user_id=1)
        assert not d.allowed and d.reason == "disabled"


class FakeRouter:
    def __init__(self):
        self.payloads = []

    async def route(self, payload):
        self.payloads.append(payload)
        return {
            "engine": "local",
            "moveInfos": [
                {"move": "Q16", "order": 0, "winrate": 0.61, "scoreLead": 2.3, "visits": 100},
                {"move": "D4", "order": 1, "winrate": 0.58, "scoreLead": 1.9, "visits": 80},
                {"move": "pass", "order": 2, "winrate": 0.5, "scoreLead": 0.0, "visits": 10},
                {"move": "C3", "order": 3, "winrate": 0.55, "scoreLead": 1.0, "visits": 60},
            ],
        }


class FakeOrch:
    def __init__(self):
        self.shown = None
        self.dismissed = False

    def show_hint(self, points):
        self.shown = points

    def dismiss_hint(self):
        self.dismissed = True


class FakeMove:
    def __init__(self, player, gtp):
        self.player, self._gtp = player, gtp

    def gtp(self):
        return self._gtp


class FakeNode:
    def __init__(self):
        self.moves = []
        self.placements = []
        self.clear_placements = []
        self.ruleset = "chinese"
        self.initial_player = "B"
        self.nodes_from_root = [self]


class FakeGame:
    board_size = (19, 19)
    komi = 7.5

    def __init__(self):
        self.current_node = FakeNode()


class FakeKatrain:
    def __init__(self, game_type="free"):
        self.game_type = game_type
        self.analysis_allowed = game_type not in ("rated", "ranked")
        self.game = FakeGame()


class FakeSession:
    def __init__(self, game_type="free"):
        self.katrain = FakeKatrain(game_type)
        self.user_id = 1


class FakeManager:
    def __init__(self, session):
        self._s = session

    def get_session(self, sid):
        return self._s


def _client(session, engine="local"):
    app = FastAPI()
    app.include_router(hint.router, prefix="/hint")
    app.state.session_manager = FakeManager(session)
    app.state.router = FakeRouter()
    app.state.physical_play = FakeOrch()
    app.state.physical_play_config = PhysicalPlayConfig(hint_engine=engine, hint_top_n=3)
    app.state.hint_gate = DefaultHintGate(engine)
    return TestClient(app)


class TestHintEndpoint:
    def test_free_game_returns_topn_skipping_pass_and_blinks(self):
        c = _client(FakeSession("free"))
        r = c.post("/hint", json={"session_id": "s1"})
        assert r.status_code == 200
        body = r.json()
        assert [m["gtp"] for m in body["moves"]] == ["Q16", "D4", "C3"]  # pass 被跳过，补足 top3
        assert body["moves"][0]["vision_rc"] == [3, 15]  # Q16: x=15,y=15 -> row 3, col 15
        assert c.app.state.physical_play.shown == [(3, 15), (15, 3), (16, 2)]
        assert body["timeout_s"] == 30.0

    def test_ranked_rejected_server_side(self):
        c = _client(FakeSession("ranked"))
        r = c.post("/hint", json={"session_id": "s1"})
        assert r.status_code == 403

    def test_engine_off_rejected(self):
        c = _client(FakeSession("free"), engine="off")
        assert c.post("/hint", json={"session_id": "s1"}).status_code == 403

    def test_dismiss(self):
        c = _client(FakeSession("free"))
        assert c.post("/hint/dismiss").status_code == 200
        assert c.app.state.physical_play.dismissed is True

    def test_handicap_payload_includes_initial_stones_and_player(self):
        # 评审 Codex I2：payload 须镜像 engine.py 语义（placements + initialPlayer）
        c = _client(FakeSession("free"))
        node = c.app.state.session_manager._s.katrain.game.current_node
        node.placements = [FakeMove("B", "D4"), FakeMove("B", "Q16")]
        node.initial_player = "W"
        assert c.post("/hint", json={"session_id": "s1"}).status_code == 200
        payload = c.app.state.router.payloads[0]
        assert payload["initialStones"] == [["B", "D4"], ["B", "Q16"]]
        assert payload["initialPlayer"] == "W"

    def test_clear_placements_rejected(self):
        # AE（清除摆子）KaTrain 自己的查询构造器也拒绝（engine.py:127 "TODO: support these"）
        c = _client(FakeSession("free"))
        node = c.app.state.session_manager._s.katrain.game.current_node
        node.clear_placements = [FakeMove("B", "D4")]
        assert c.post("/hint", json={"session_id": "s1"}).status_code == 400
