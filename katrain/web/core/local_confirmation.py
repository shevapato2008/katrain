"""Local two-player confirmation; vision owns all image recognition, the game owns legality."""

from __future__ import annotations

import asyncio
import copy
import logging
import time
import uuid
from collections import OrderedDict

import numpy as np

from katrain.core.game import IllegalMoveException
from katrain.core.sgf_parser import Move
from katrain.vision.sync import game_state_stones_to_board
from katrain.web.core.game_end_rules import is_awaiting_count

logger = logging.getLogger("katrain_web.local_confirmation")


class LocalConfirmationConflict(Exception):
    pass


def trial_board(game, coords, color):
    """Use the real rules on copied board/chains without creating a live SGF node."""
    x, y = coords
    width, height = game.board_size
    if not (0 <= x < width and 0 <= y < height):
        raise IllegalMoveException("Outside board")
    trial = copy.copy(game)
    trial.board = [row[:] for row in game.board]
    trial.chains = [chain[:] for chain in game.chains]
    trial.prisoners = game.prisoners[:]
    trial.last_capture = game.last_capture[:]
    trial._validate_move_and_update_chains(Move((x, y), player=color), ignore_ko=False)
    return game_state_stones_to_board([[stone.player, list(stone.coords)] for stone in trial.stones], width)


class LocalConfirmationController:
    WINDOW_SECONDS = 8.0
    ERROR_STABLE_OBSERVATIONS = 3

    def __init__(self, session):
        self.session = session
        self.ready_game_id = None
        self.input = None
        self._active = None  # (request_id, signature, task)
        self._results = OrderedDict()
        self._closed = False
        self._window = None

    def close(self):
        self._closed = True
        if self._window is not None:
            vision, token = self._window
            try:
                vision.cancel_local_window(token)
            except Exception:
                logger.exception("Failed to close local vision window")
        # The bounded waiter sees _closed on its next tick and returns a normal
        # rejected result; cancelling its task would also cancel the HTTP response.

    def ready(self, game_id, input_mode, vision=None):
        katrain = self.session.katrain
        with self.session.lock, katrain.ai_ladder_commit_lock:
            if self._closed or katrain.game_type != "pvp_local" or katrain.game.game_id != game_id:
                raise LocalConfirmationConflict("Game is no longer current")
            if self._active is not None or katrain.local_confirmation_in_progress:
                if self.input != input_mode:
                    raise LocalConfirmationConflict("Confirmation is in progress")
                return
            if input_mode == "physical" and not (
                vision is not None
                and vision.bound_session_id == self.session.session_id
                and vision.supports_local_confirmation
                and vision.local_confirmation_ready
            ):
                raise LocalConfirmationConflict("Physical recognition is not ready")
            self.ready_game_id, self.input = game_id, input_mode
            katrain.start_clock()
            katrain.update_state()

    def _current(self, request):
        katrain = self.session.katrain
        node = katrain.game.current_node
        return (
            not self._closed
            and katrain.game_type == "pvp_local"
            and katrain.game.game_id == request.expected_game_id
            and id(node) == request.expected_node_id
            and node.next_player == request.color
            and not katrain.game.terminal
            and not is_awaiting_count(katrain)
        )

    async def confirm(self, request, vision, commit):
        signature = (
            request.expected_game_id,
            request.expected_node_id,
            request.color,
            request.input,
            request.action,
            tuple(request.coords) if request.coords is not None else None,
        )
        cached = self._results.get(request.request_id)
        if cached is not None:
            if cached[0] != signature:
                raise LocalConfirmationConflict("request_id was already used for another action")
            return cached[1]
        if self._active is not None:
            rid, sig, task = self._active
            if rid != request.request_id or sig != signature:
                raise LocalConfirmationConflict("Confirmation is in progress")
            return await asyncio.shield(task)
        katrain = self.session.katrain
        with self.session.lock, katrain.ai_ladder_commit_lock:
            if not self._current(request):
                raise LocalConfirmationConflict("Game, node or turn is no longer current")
            if (self.ready_game_id, self.input) != (request.expected_game_id, request.input):
                raise LocalConfirmationConflict("Input is not ready")
            if request.action == "pass" and request.coords is not None:
                raise LocalConfirmationConflict("Pass cannot have coordinates")
            if request.action == "move" and ((request.input == "screen") != (request.coords is not None)):
                raise LocalConfirmationConflict("Invalid coordinates for this input")
            if katrain.clock_exhausted():
                katrain(
                    "timeout",
                    expected_game_id=request.expected_game_id,
                    expected_node_id=request.expected_node_id,
                    color=request.color,
                )
                self._results[request.request_id] = (signature, False)
                return False
            katrain.update_timer()
            katrain.local_confirmation_in_progress = True
            katrain.local_confirmation_state = {"status": "recognizing", "reason": None, "points": []}
        task = asyncio.create_task(self._run(request, vision, commit, signature))
        self._active = (request.request_id, signature, task)
        # Disconnecting HTTP must not leave a paused clock or cancel a committed turn.
        return await asyncio.shield(task)

    async def _run(self, request, vision, commit, signature):
        katrain = self.session.katrain
        token = uuid.uuid4().hex
        accepted, reason, points = False, "unavailable", []
        opened = False
        try:
            katrain.update_state()
            coords = None if request.action == "pass" else request.coords
            if request.action == "move" and request.input == "physical":
                if not (
                    vision is not None
                    and vision.bound_session_id == self.session.session_id
                    and vision.supports_local_confirmation
                    and vision.local_confirmation_ready
                ):
                    return False
                expected = game_state_stones_to_board(
                    [[stone.player, list(stone.coords)] for stone in katrain.game.stones], katrain.game.board_size[0]
                )
                opened_at = time.monotonic()
                deadline = opened_at + self.WINDOW_SECONDS
                opened = vision.open_local_window(
                    token,
                    expected,
                    expected_node_id=request.expected_node_id,
                    expected_color=1 if request.color == "B" else 2,
                    deadline_monotonic=deadline,
                )
                if not opened:
                    return False
                self._window = (vision, token)
                reason = "timeout"
                last_seq = -1
                last_camera_seq = -1
                error_key, error_count = None, 0
                while time.monotonic() < deadline:
                    if (
                        not self._current(request)
                        or vision.bound_session_id != self.session.session_id
                        or not vision.local_confirmation_ready
                    ):
                        reason = "unavailable"
                        return False
                    obs = vision.get_local_window_observation(token)
                    if (
                        obs is None
                        or obs.token != token
                        or obs.observation_seq <= last_seq
                        or (
                            obs.camera_ts is None
                            or obs.camera_ts <= opened_at
                            or obs.camera_seq is None
                            or obs.camera_seq <= last_camera_seq
                        )
                    ):
                        await asyncio.sleep(0.05)
                        continue
                    last_seq = obs.observation_seq
                    last_camera_seq = obs.camera_seq
                    board = np.asarray(obs.board, dtype=int)
                    if board.shape != expected.shape:
                        continue
                    added = np.argwhere((expected == 0) & (board != 0))
                    points = [{"row": int(r), "col": int(c)} for r, c in added]
                    if len(added) > 1:
                        reason = "multiple_stones"
                    elif not len(added):
                        if np.array_equal(board, expected):
                            reason = "timeout" if getattr(obs, "pending", False) else "no_stone"
                        else:
                            reason = "illegal_move"
                    else:
                        row, col = map(int, added[0])
                        coords = [col, expected.shape[0] - 1 - row]
                        try:
                            if int(board[row, col]) != (1 if request.color == "B" else 2):
                                raise IllegalMoveException("Wrong colour")
                            after = trial_board(katrain.game, coords, request.color)
                            remaining = np.argwhere((expected != 0) & (after == 0) & (board != 0))
                            remainder_free = board.copy()
                            for r, c in remaining:
                                remainder_free[r, c] = 0
                            if len(remaining) and np.array_equal(remainder_free, after):
                                reason = "capture_remaining"
                                points = [{"row": int(r), "col": int(c)} for r, c in remaining]
                            elif not np.array_equal(board, after):
                                reason = "illegal_move"
                                points = [{"row": int(r), "col": int(c)} for r, c in np.argwhere(board != after)]
                            else:
                                candidate = obs.candidate
                                if candidate is not None and (candidate.row, candidate.col, candidate.color) == (
                                    row,
                                    col,
                                    1 if request.color == "B" else 2,
                                ):
                                    break
                                reason = "timeout"
                        except IllegalMoveException:
                            reason = "illegal_move"
                    key = (reason, board.tobytes())
                    error_count = error_count + 1 if key == error_key else 1
                    error_key = key
                    required = getattr(vision, "local_confirmation_frames", self.ERROR_STABLE_OBSERVATIONS)
                    if (
                        reason in ("no_stone", "multiple_stones", "capture_remaining", "illegal_move")
                        and error_count >= required
                    ):
                        return False
                    await asyncio.sleep(0.05)
                else:
                    return False
            with self.session.lock, katrain.ai_ladder_commit_lock:
                if not self._current(request):
                    reason = "unavailable"
                    return False
                if coords is not None:
                    try:
                        trial_board(katrain.game, coords, request.color)
                    except IllegalMoveException:
                        reason = "illegal_move"
                        return False
                commit(None if coords is None else tuple(coords), request.color)
                accepted = id(katrain.game.current_node) != request.expected_node_id
                reason = None if accepted else "illegal_move"
                if accepted and opened:
                    after = game_state_stones_to_board(
                        [[stone.player, list(stone.coords)] for stone in katrain.game.stones],
                        katrain.game.board_size[0],
                    )
                    vision.complete_local_window(token, after, expected_node_id=id(katrain.game.current_node))
                    opened = False
            return accepted
        except Exception:
            logger.exception("Local confirmation failed")
            reason = None if accepted else "unavailable"
            return accepted
        finally:
            try:
                if opened:
                    try:
                        vision.cancel_local_window(token)
                    except Exception:
                        logger.exception("Failed to close local vision window")
                self._window = None
                with self.session.lock, katrain.ai_ladder_commit_lock:
                    # A late window may not change a freshly-created game's clock/status.
                    if katrain.game.game_id == request.expected_game_id:
                        try:
                            katrain.update_timer()  # discard the pending recognition interval
                        finally:
                            katrain.local_confirmation_in_progress = False
                            katrain.local_confirmation_state = {
                                "status": "idle",
                                "reason": reason,
                                "points": [] if accepted else points,
                            }
                        try:
                            katrain.update_state()
                        except Exception:
                            logger.exception("Failed to publish local confirmation result")
            finally:
                self._results[request.request_id] = (signature, accepted)
                while len(self._results) > 64:
                    self._results.popitem(last=False)
                self._active = None


def local_confirmation_for(session):
    controller = getattr(session, "local_confirmation_controller", None)
    if controller is None:
        controller = session.local_confirmation_controller = LocalConfirmationController(session)
    return controller
