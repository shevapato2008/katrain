"""Authoritative local confirmation: one move, retry, clocks and full-board capture checks."""

import kivymd.app  # noqa: F401 -- macOS Window must initialise on the main thread

from types import SimpleNamespace
import time
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from katrain.vision.ipc import ConfirmedMove
from katrain.vision.sync import game_state_stones_to_board
from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.server import create_app


@pytest.fixture
def client(isolated_session_factory):
    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory
    with TestClient(app) as c:
        app.state.user_game_repo = MagicMock()
        app.state.repository_dispatcher = None
        app.dependency_overrides[get_current_user_optional] = lambda: None
        yield c
        for session in list(app.state.session_manager._sessions.values()):
            app.state.session_manager.remove_session(session.session_id)


def start(client, monkeypatch, *, timed=False):
    session = client.app.state.session_manager.create_session()
    monkeypatch.setattr(session.katrain, "save_config", lambda *a, **k: None)
    r = client.post(
        "/api/game/setup",
        json={
            "session_id": session.session_id,
            "mode": "pvp_local",
            "settings": {
                "board_size": 9,
                "handicap": 0,
                "time_enabled": timed,
                "main_time": 10,
                "byo_length": 30,
                "byo_periods": 3,
            },
        },
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/local/ready",
        json={"session_id": session.session_id, "expected_game_id": session.katrain.game.game_id, "input": "screen"},
    )
    assert r.status_code == 200, r.text
    return session


def request_for(session, **changes):
    state = session.katrain.get_state()
    return {
        "session_id": session.session_id,
        "expected_game_id": state["game_id"],
        "expected_node_id": state["current_node_id"],
        "color": state["player_to_move"],
        "request_id": "one-request",
        "input": "screen",
        "action": "move",
        "coords": [3, 3],
        **changes,
    }


def test_screen_confirm_commits_once_and_returns_capability(client, monkeypatch):
    session = start(client, monkeypatch)
    body = request_for(session)
    messages = []
    monkeypatch.setattr(session.katrain, "message_callback", lambda kind, data: messages.append((kind, data)))
    assert session.katrain.get_state()["local_confirmation"]["enabled"] is True
    assert client.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]}).status_code == 409
    first = client.post("/api/local/confirm", json=body)
    assert first.status_code == 200, first.text
    assert first.json()["accepted"] is True
    assert first.json()["state"]["current_node_index"] == 1
    second = client.post("/api/local/confirm", json=body)
    assert second.status_code == 200, second.text
    assert second.json()["accepted"] is True
    assert second.json()["state"]["current_node_index"] == 1
    assert len([m for m in messages if m[0] == "sound"]) == 1


def test_rejects_stale_node_color_and_id_reuse(client, monkeypatch):
    session = start(client, monkeypatch)
    body = request_for(session)
    assert client.post("/api/local/confirm", json={**body, "color": "W"}).status_code == 409
    assert client.post("/api/local/confirm", json=body).json()["accepted"] is True
    assert client.post("/api/local/confirm", json={**body, "request_id": "old-node"}).status_code == 409
    assert client.post("/api/local/confirm", json={**body, "coords": [4, 4]}).status_code == 409
    assert session.katrain.game.current_node.depth == 1


def test_illegal_move_keeps_turn_and_has_no_sound(client, monkeypatch):
    session = start(client, monkeypatch)
    assert client.post("/api/local/confirm", json=request_for(session)).json()["accepted"] is True
    messages = []
    monkeypatch.setattr(session.katrain, "message_callback", lambda kind, data: messages.append((kind, data)))
    r = client.post("/api/local/confirm", json=request_for(session, request_id="occupied"))
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is False
    assert r.json()["state"]["local_confirmation"]["reason"] == "illegal_move"
    assert r.json()["state"]["player_to_move"] == "W"
    assert not [m for m in messages if m[0] == "sound"]


class WindowVision:
    supports_local_confirmation = True
    local_confirmation_ready = True
    local_confirmation_frames = 3

    def stop(self):
        pass

    def poll_events(self):
        return []

    def get_confirmed_move(self):
        return None

    def __init__(self, session, boards, candidate=None):
        self.bound_session_id = session.session_id
        self.session = session
        self.boards = boards
        self.candidate = candidate
        self.closed = []
        self.opened = []

    def open_local_window(self, token, expected_board, **kwargs):
        self.opened.append(token)
        self.token = token
        self.seq = 0
        return True

    def get_local_window_observation(self, token=None):
        if not self.boards:
            return None
        self.seq += 1
        # Artificial processing time must be excluded from both clocks.
        self.session.katrain.last_timer_update -= 5
        self.session.katrain.get_state()
        return SimpleNamespace(
            token=self.token,
            observation_seq=self.seq,
            board=self.boards.pop(0).tolist(),
            candidate=self.candidate,
            camera_seq=self.seq,
            camera_ts=time.monotonic(),
        )

    def complete_local_window(self, token, board, **kwargs):
        self.closed.append((token, "accepted"))
        return True

    def cancel_local_window(self, token):
        self.closed.append((token, "cancelled"))
        return True


def test_physical_full_board_and_clock_pause(client, monkeypatch):
    session = start(client, monkeypatch, timed=True)
    session.katrain.start_clock()
    before = session.katrain.main_time_used_by_player["B"]
    board = np.zeros((9, 9), dtype=int)
    board[5, 3] = 1  # game (3,3), camera rows top to bottom
    vision = WindowVision(session, [board], ConfirmedMove(col=3, row=5, color=1))
    client.app.state.vision = vision
    assert (
        client.post(
            "/api/local/ready",
            json={
                "session_id": session.session_id,
                "expected_game_id": session.katrain.game.game_id,
                "input": "physical",
            },
        ).status_code
        == 200
    )
    r = client.post("/api/local/confirm", json=request_for(session, input="physical", coords=None))
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is True
    assert r.json()["state"]["player_to_move"] == "W"
    assert session.katrain.main_time_used_by_player["B"] - before < 1
    assert r.json()["state"]["timer"]["paused"] is False
    assert vision.closed[-1][1] == "accepted"


def test_multiple_stones_fail_without_commit(client, monkeypatch):
    session = start(client, monkeypatch)
    board = np.zeros((9, 9), dtype=int)
    board[5, 3] = board[4, 4] = 1
    vision = WindowVision(session, [board.copy(), board.copy(), board.copy()], ConfirmedMove(col=3, row=5, color=1))
    client.app.state.vision = vision
    assert (
        client.post(
            "/api/local/ready",
            json={
                "session_id": session.session_id,
                "expected_game_id": session.katrain.game.game_id,
                "input": "physical",
            },
        ).status_code
        == 200
    )
    r = client.post("/api/local/confirm", json=request_for(session, input="physical", coords=None))
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is False
    assert r.json()["state"]["local_confirmation"]["reason"] == "multiple_stones"
    assert len(r.json()["state"]["local_confirmation"]["points"]) == 2
    assert session.katrain.game.current_node.is_root
    assert vision.closed[-1][1] == "cancelled"


def test_pass_never_opens_camera_and_second_pass_keeps_count_flow(client, monkeypatch):
    session = start(client, monkeypatch)
    session.katrain.suppress_auto_eval = True  # same board-mode count policy as existing tests
    vision = WindowVision(session, [])
    client.app.state.vision = vision
    assert (
        client.post(
            "/api/local/ready",
            json={
                "session_id": session.session_id,
                "expected_game_id": session.katrain.game.game_id,
                "input": "physical",
            },
        ).status_code
        == 200
    )
    for n in range(2):
        r = client.post(
            "/api/local/confirm",
            json=request_for(session, request_id=f"pass-{n}", input="physical", action="pass", coords=None),
        )
        assert r.status_code == 200, r.text
        assert r.json()["accepted"] is True
    assert vision.opened == []
    assert r.json()["state"]["awaiting_count"] is True


@pytest.mark.parametrize("removed", [False, True])
def test_capture_must_be_removed_and_other_stones_preserved(client, monkeypatch, removed):
    session = start(client, monkeypatch)
    for n, coords in enumerate(([0, 1], [0, 0])):
        assert client.post(
            "/api/local/confirm", json=request_for(session, request_id=f"setup-{n}", coords=coords)
        ).json()["accepted"]
    before = game_state_stones_to_board(session.katrain.get_state()["stones"], 9)
    board = before.copy()
    board[8, 1] = 1  # B(1,0) captures W(0,0)
    if removed:
        board[8, 0] = 0
    vision = WindowVision(session, [board.copy() for _ in range(3)], ConfirmedMove(col=1, row=8, color=1))
    client.app.state.vision = vision
    assert (
        client.post(
            "/api/local/ready",
            json={
                "session_id": session.session_id,
                "expected_game_id": session.katrain.game.game_id,
                "input": "physical",
            },
        ).status_code
        == 200
    )
    r = client.post(
        "/api/local/confirm", json=request_for(session, request_id="capture", input="physical", coords=None)
    )
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is removed
    if not removed:
        assert r.json()["state"]["local_confirmation"]["reason"] == "capture_remaining"
        assert r.json()["state"]["local_confirmation"]["points"] == [{"row": 8, "col": 0}]
        assert r.json()["state"]["current_node_index"] == 2
    else:
        assert r.json()["state"]["current_node_index"] == 3
        assert len(r.json()["state"]["stones"]) == 2


def test_empty_window_and_timeout_resume_clock(client, monkeypatch):
    from katrain.web.core.local_confirmation import LocalConfirmationController

    session = start(client, monkeypatch, timed=True)
    board = np.zeros((9, 9), dtype=int)
    vision = WindowVision(session, [board.copy() for _ in range(3)])
    client.app.state.vision = vision
    assert (
        client.post(
            "/api/local/ready",
            json={
                "session_id": session.session_id,
                "expected_game_id": session.katrain.game.game_id,
                "input": "physical",
            },
        ).status_code
        == 200
    )
    r = client.post("/api/local/confirm", json=request_for(session, input="physical", coords=None))
    assert r.json()["state"]["local_confirmation"]["reason"] == "no_stone"
    assert r.json()["state"]["timer"]["paused"] is False
    monkeypatch.setattr(LocalConfirmationController, "WINDOW_SECONDS", 0.1)
    r = client.post(
        "/api/local/confirm", json=request_for(session, request_id="timeout", input="physical", coords=None)
    )
    assert r.json()["state"]["local_confirmation"]["reason"] == "timeout"
    assert r.json()["state"]["timer"]["paused"] is False
    assert session.katrain.game.current_node.is_root


def test_concurrent_retry_joins_one_window_and_conflicting_actions_fail(client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from katrain.web.core.local_confirmation import LocalConfirmationController

    session = start(client, monkeypatch, timed=True)
    vision = WindowVision(session, [])
    client.app.state.vision = vision
    client.post(
        "/api/local/ready",
        json={"session_id": session.session_id, "expected_game_id": session.katrain.game.game_id, "input": "physical"},
    )
    monkeypatch.setattr(LocalConfirmationController, "WINDOW_SECONDS", 0.4)
    body = request_for(session, input="physical", coords=None)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(client.post, "/api/local/confirm", json=body)
        deadline = time.monotonic() + 2
        while not vision.opened and time.monotonic() < deadline:
            time.sleep(0.01)
        assert vision.opened
        duplicate = pool.submit(client.post, "/api/local/confirm", json=body)
        assert client.post("/api/local/confirm", json={**body, "request_id": "other"}).status_code == 409
        assert client.post("/api/resign", json={"session_id": session.session_id, "color": "W"}).status_code == 409
        assert client.post("/api/count/request", json={"session_id": session.session_id}).status_code == 409
        assert first.result(timeout=3).json()["accepted"] is False
        assert duplicate.result(timeout=3).json()["accepted"] is False
    assert len(vision.opened) == 1
    assert not session.katrain.local_confirmation_in_progress


def test_vision_consumer_and_cleanup_errors_cannot_leave_clock_paused(client, monkeypatch):
    session = start(client, monkeypatch, timed=True)
    vision = WindowVision(session, [])
    client.app.state.vision = vision
    client.post(
        "/api/local/ready",
        json={"session_id": session.session_id, "expected_game_id": session.katrain.game.game_id, "input": "physical"},
    )
    monkeypatch.setattr(vision, "get_local_window_observation", MagicMock(side_effect=RuntimeError("lost worker")))
    monkeypatch.setattr(vision, "cancel_local_window", MagicMock(side_effect=RuntimeError("lost command queue")))
    r = client.post("/api/local/confirm", json=request_for(session, input="physical", coords=None))
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is False
    assert r.json()["state"]["timer"]["paused"] is False
    assert session.local_confirmation_controller._active is None


@pytest.mark.parametrize("value,reason", [(255, "frame_overexposed"), (10, "frame_underexposed")])
def test_real_worker_lighting_from_first_severe_frame_rejects_without_sgf_sound_or_clock_switch(
    client, monkeypatch, value, reason
):
    from tests.test_vision.test_local_confirmation_window import worker, run
    from katrain.vision.board_state import BoardStateExtractor
    from katrain.vision.config import BoardConfig, DEFAULT_MARGIN_CELLS
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.service import VisionService

    session = start(client, monkeypatch, timed=True)
    result, camera = worker()
    result._active_extractor = lambda: BoardStateExtractor(BoardConfig(grid_size=9, margin_cells=DEFAULT_MARGIN_CELLS))
    result._ref_hold = np.zeros((9, 9), dtype=int)
    result._ref_released = np.zeros((9, 9), dtype=bool)
    vision = VisionService(VisionServiceConfig(enabled=True))
    vision._worker = result
    vision.bind_session(session.session_id)
    vision.set_expected_from_stones([], board_size=9, expected_node_id=id(session.katrain.game.current_node))
    vision.set_local_confirmation_mode(True, session_id=session.session_id, game_id=session.katrain.game.game_id)
    result._drain_commands()
    run(result, camera)
    assert vision.local_confirmation_ready
    client.app.state.vision = vision
    messages = []
    monkeypatch.setattr(session.katrain, "message_callback", lambda kind, data: messages.append((kind, data)))
    body = {"session_id": session.session_id, "expected_game_id": session.katrain.game.game_id, "input": "physical"}
    assert client.post("/api/local/ready", json=body).status_code == 200
    get_observation = vision.get_local_window_observation
    camera_reads = []

    def observe(token):
        result._drain_commands()
        window = result._local_window
        assert window is not None
        index = len(camera_reads)
        ts = window.opened_monotonic + (0.01, 0.2, 0.4, 1.02)[index]
        run(result, camera, identities=[(101 + index, ts, np.full((240, 240, 3), value, dtype=np.uint8))])
        camera_reads.append(ts)
        return get_observation(token)

    monkeypatch.setattr(vision, "get_local_window_observation", observe)
    response = client.post("/api/local/confirm", json=request_for(session, input="physical", coords=None))
    assert response.status_code == 200, response.text
    state = response.json()["state"]
    assert response.json()["accepted"] is False
    assert state["local_confirmation"]["reason"] == reason
    assert state["local_confirmation"]["points"] == []
    assert len(camera_reads) == 4  # Three quick severe frames must not return no_stone.
    assert state["current_node_index"] == 0 and state["player_to_move"] == "B"
    assert state["timer"]["paused"] is False
    assert not [m for m in messages if m[0] == "sound"]
    result._drain_commands()
    assert result._local_window is None


@pytest.mark.parametrize("ready", [True, False])
def test_physical_ready_clears_only_stale_unavailable_after_authoritative_success(client, monkeypatch, ready):
    session = start(client, monkeypatch)
    vision = WindowVision(session, [])
    vision.local_confirmation_ready = ready
    client.app.state.vision = vision
    session.katrain.local_confirmation_state = {
        "status": "idle",
        "reason": "unavailable",
        "points": [{"row": 1, "col": 2}],
    }
    response = client.post(
        "/api/local/ready",
        json={"session_id": session.session_id, "expected_game_id": session.katrain.game.game_id, "input": "physical"},
    )
    assert response.status_code == (200 if ready else 409)
    assert session.katrain.local_confirmation_state["reason"] == (None if ready else "unavailable")
    assert session.katrain.local_confirmation_state["points"] == ([] if ready else [{"row": 1, "col": 2}])
    assert session.katrain.game.current_node.is_root


def test_geometry_pause_rejects_physical_pass_without_touching_node(client, monkeypatch):
    session = start(client, monkeypatch, timed=True)
    vision = WindowVision(session, [])
    client.app.state.vision = vision
    ready = client.post(
        "/api/local/ready",
        json={"session_id": session.session_id, "expected_game_id": session.katrain.game.game_id, "input": "physical"},
    )
    assert ready.status_code == 200
    session.katrain.set_local_geometry_paused(True, expected_game_id=session.katrain.game.game_id)
    node = session.katrain.game.current_node
    result = client.post(
        "/api/local/confirm",
        json=request_for(session, input="physical", action="pass", coords=None),
    )
    assert result.status_code == 409
    assert session.katrain.game.current_node is node
    assert session.katrain.local_confirmation_in_progress is False


def test_real_bind_ready_clears_geometry_pause_for_same_game(client, monkeypatch):
    session = start(client, monkeypatch, timed=True)
    vision = WindowVision(session, [])
    vision.bind_session = lambda session_id: setattr(vision, "bound_session_id", session_id)
    vision.set_expected_from_stones = lambda *args, **kwargs: None
    vision.set_local_confirmation_mode = lambda *args, **kwargs: True
    vision.local_confirmation_bootstrap_state = "ready"
    client.app.state.vision = vision
    session.katrain.set_local_geometry_paused(True, expected_game_id=session.katrain.game.game_id)
    result = client.post("/api/v1/vision/bind", json={"session_id": session.session_id})
    assert result.status_code == 200, result.text
    assert session.katrain.local_geometry_paused is False


@pytest.mark.parametrize("status,reason", [("idle", "frame_overexposed"), ("recognizing", "unavailable")])
def test_ready_preserves_other_result_or_recognizing_state(client, monkeypatch, status, reason):
    session = start(client, monkeypatch)
    vision = WindowVision(session, [])
    client.app.state.vision = vision
    original = {"status": status, "reason": reason, "points": [{"row": 1, "col": 2}]}
    session.katrain.local_confirmation_state = original.copy()
    response = client.post(
        "/api/local/ready",
        json={"session_id": session.session_id, "expected_game_id": session.katrain.game.game_id, "input": "physical"},
    )
    assert response.status_code == 200
    assert session.katrain.local_confirmation_state == original


@pytest.mark.parametrize("single_severe", [False, True])
def test_real_bind_first_physical_confirmation_commits_one_stone_and_stops_inference(
    client, monkeypatch, single_severe
):
    from tests.test_vision.test_local_confirmation_window import worker, run, frame
    from katrain.vision.board_state import BoardStateExtractor
    from katrain.vision.config import BoardConfig, DEFAULT_MARGIN_CELLS
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.service import VisionService
    from katrain.vision.stone_detector import Detection

    session = start(client, monkeypatch)
    result, camera = worker(pose_locked=False)
    config = BoardConfig(grid_size=9, margin_cells=DEFAULT_MARGIN_CELLS)
    result._active_extractor = lambda: BoardStateExtractor(config)
    result._ref_hold = np.zeros((9, 9), dtype=int)
    result._ref_released = np.zeros((9, 9), dtype=bool)
    vision = VisionService(VisionServiceConfig(enabled=True))
    vision._worker = result
    vision.bind_session(session.session_id)
    vision.set_expected_from_stones([], board_size=9, expected_node_id=id(session.katrain.game.current_node))
    vision.set_local_confirmation_mode(True, session_id=session.session_id, game_id=session.katrain.game.game_id)
    result._drain_commands()
    assert result._sync.state.value == "calibrating"
    run(result, camera, n=4)
    assert vision.local_confirmation_ready and result.get_status().pose_lock_status == "locked"
    assert result.get_status().sync_state == "synced" and session.katrain.game.current_node.is_root
    assert result._detector.detect.call_count == 1
    client.app.state.vision = vision
    assert (
        client.post(
            "/api/local/ready",
            json={
                "session_id": session.session_id,
                "expected_game_id": session.katrain.game.game_id,
                "input": "physical",
            },
        ).status_code
        == 200
    )
    x = int((config.border_width_mm + 3 * config.grid_spacing_w) / config.total_width * 240)
    y = int((config.border_length_mm + 5 * config.grid_spacing_l) / config.total_length * 240)
    result._detector.detect.return_value = [Detection(x, y, 0, 0.9, (x - 5, y - 5, x + 5, y + 5))]
    changed = frame().copy()
    changed[y - 15 : y + 15, x - 15 : x + 15] = 15
    get_observation = vision.get_local_window_observation
    images = [np.full_like(changed, 255)] if single_severe else []

    def observe(token):
        result._drain_commands()
        run(result, camera, image=images.pop(0) if images else changed)
        return get_observation(token)

    monkeypatch.setattr(vision, "get_local_window_observation", observe)
    messages = []
    monkeypatch.setattr(session.katrain, "message_callback", lambda kind, data: messages.append((kind, data)))
    response = client.post("/api/local/confirm", json=request_for(session, input="physical", coords=None))
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] is True
    assert response.json()["state"]["current_node_index"] == 1
    assert response.json()["state"]["player_to_move"] == "W"
    assert len([m for m in messages if m[0] == "sound"]) == 1
    result._drain_commands()
    assert result._local_window is None
    inferences = result._detector.detect.call_count
    run(result, camera, n=3, image=changed)
    assert result._detector.detect.call_count == inferences
    assert vision.get_confirmed_move() is None and vision.poll_events() == []
