"""Reference-frame check (2026-09-23): per-cell ZNCC against the last frame whose board matched the
game record, as bounded evidence against daylight false negatives/positives.
Design: superpowers/tracks/vision-optimizations/reference-frame/design.md
"""

import numpy as np
import pytest

from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.reference_frame import ReferenceFrame, build_sampler, to_gray

BLACK, WHITE = 1, 2
SIZE = 1056
CONFIG = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
ZNCC = 0.90


def _sampler(parallax=None):
    return build_sampler(SIZE, SIZE, CONFIG, parallax)


def _cell_centre(row, col):
    x_mm = CONFIG.border_width_mm + col * CONFIG.grid_spacing_w
    y_mm = CONFIG.border_length_mm + row * CONFIG.grid_spacing_l
    return int(round(x_mm / CONFIG.total_width * SIZE)), int(round(y_mm / CONFIG.total_length * SIZE))


def _board_frame(stones=(), seed=0):
    """A textured board (wood grain + grid lines) with discs on the given intersections."""
    rng = np.random.default_rng(seed)
    frame = np.full((SIZE, SIZE, 3), 150, np.uint8)
    frame[..., 0] = 120
    frame = np.clip(frame.astype(np.int16) + rng.integers(0, 25, frame.shape), 0, 255).astype(np.uint8)
    for i in range(19):
        x, y = _cell_centre(i, i)
        frame[max(0, y - 1) : y + 1, :] = 90
        frame[:, max(0, x - 1) : x + 1] = 90
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    for row, col, colour, *offset in stones:
        x, y = _cell_centre(row, col)
        dx, dy = (offset + [0, 0])[:2] if offset else (0, 0)
        frame[(xx - x - dx) ** 2 + (yy - y - dy) ** 2 <= 24**2] = 235 if colour == WHITE else 25
    return frame


def _empty_board():
    return np.zeros((19, 19), dtype=int)


def test_the_patch_of_every_cell_is_centred_on_its_intersection_and_inside_the_frame():
    sampler = _sampler()
    assert sampler.flat_index.min() >= 0 and sampler.flat_index.max() < SIZE * SIZE
    for row, col in ((0, 0), (0, 18), (18, 0), (18, 18), (0, 9), (9, 0), (18, 9), (9, 18), (2, 2), (9, 9)):
        ys, xs = np.divmod(sampler.flat_index[row * 19 + col], SIZE)
        x, y = _cell_centre(row, col)
        # < 1, not <= 2: the first draft sampled arange(0, patch, 2) and sat exactly 1 px up-left
        assert abs((xs.min() + xs.max()) / 2 - x) < 1 and abs((ys.min() + ys.max()) / 2 - y) < 1


def test_the_patch_follows_the_mount_parallax_outward():
    """A stone is imaged away from the nadir, so with parallax the patch shifts outward, not inward."""
    parallax = type("P", (), {"nadir": (19.612, 9.0), "k": 0.989689})()
    shifted = build_sampler(SIZE, SIZE, CONFIG, parallax)
    plain = _sampler()
    ys_p, xs_p = np.divmod(plain.flat_index[0 * 19 + 0], SIZE)
    ys_s, xs_s = np.divmod(shifted.flat_index[0 * 19 + 0], SIZE)
    assert xs_s.mean() < xs_p.mean()  # (0,0) is on the far side of the nadir: imaged further out


def test_the_same_scene_is_unchanged_everywhere():
    frame = _board_frame([(4, 4, BLACK)])
    board = _empty_board()
    board[4][4] = BLACK
    reference = ReferenceFrame(_sampler(), to_gray(frame), board)
    mask, sim = reference.unchanged(to_gray(frame), ZNCC)
    assert mask.all() and np.nanmin(sim) > 0.99


def test_a_brightness_change_is_still_unchanged_where_a_pixel_diff_would_scream():
    frame = _board_frame([(4, 4, BLACK)])
    brighter = np.clip(frame.astype(np.float32) * 1.3 + 40, 0, 250).astype(np.uint8)
    reference = ReferenceFrame(_sampler(), to_gray(frame), _empty_board())
    mask, _ = reference.unchanged(to_gray(brighter), ZNCC)
    assert mask.all()
    assert np.abs(to_gray(brighter).astype(int) - to_gray(frame).astype(int)).mean() > 40


@pytest.mark.parametrize(
    "before,after,cell",
    [
        ((), ((9, 9, WHITE),), (9, 9)),  # a stone placed
        (((9, 9, WHITE),), (), (9, 9)),  # a stone taken off (capture)
        (((9, 9, BLACK),), ((9, 9, WHITE),), (9, 9)),  # colour replaced
        (((9, 9, WHITE),), ((9, 9, WHITE, 26, 0),), (9, 9)),  # nudged half a cell
    ],
)
def test_every_real_board_change_breaks_the_correlation(before, after, cell):
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame(before)), _empty_board())
    mask, sim = reference.unchanged(to_gray(_board_frame(after)), ZNCC)
    assert not mask[cell[0]][cell[1]], f"zncc={sim[cell[0]][cell[1]]}"


def test_a_stone_at_one_eighth_weight_still_reads_as_unchanged():
    """Why the comparison must never be fed the frame averager's output: at 1/8 weight -- the first
    frame of a new stone inside an 8-frame average -- the cell still correlates about 0.93, above any
    usable threshold, so a veto there would erase a move while it is appearing. The production path
    avoids this by comparing the pre-average frame (see to_gray, and the loop test in Task 2)."""
    empty = _board_frame().astype(np.float32)
    stone = _board_frame([(9, 9, BLACK)]).astype(np.float32)
    blended = (empty * 7 / 8 + stone / 8).astype(np.uint8)
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame()), _empty_board())
    _, sim = reference.unchanged(to_gray(blended), ZNCC)
    assert sim[9][9] > ZNCC  # the hazard, recorded on purpose
    _, raw_sim = reference.unchanged(to_gray(_board_frame([(9, 9, BLACK)])), ZNCC)
    assert raw_sim[9][9] < ZNCC  # the frame production actually compares


def test_a_blown_out_cell_cannot_be_compared():
    before = _board_frame([(2, 2, WHITE)])
    after = before.copy()
    x, y = _cell_centre(2, 2)
    after[y - 30 : y + 30, x - 30 : x + 30] = 255
    reference = ReferenceFrame(_sampler(), to_gray(before), _empty_board())
    mask, sim = reference.unchanged(to_gray(after), ZNCC)
    assert np.isnan(sim[2][2]) and not mask[2][2]


def test_a_mostly_clipped_cell_with_one_grid_line_left_is_also_cannot_tell():
    """std alone passes here (the surviving line carries variance) -- the clipped-fraction test is
    what catches it."""
    before = _board_frame([(2, 2, WHITE)])
    after = before.copy()
    x, y = _cell_centre(2, 2)
    after[y - 30 : y + 30, x - 30 : x + 30] = 255
    after[y - 30 : y + 30, x - 2 : x + 2] = 60  # one dark grid line survives the glare
    reference = ReferenceFrame(_sampler(), to_gray(before), _empty_board())
    mask, sim = reference.unchanged(to_gray(after), ZNCC)
    assert np.isnan(sim[2][2]) and not mask[2][2]


def test_a_mostly_crushed_cell_with_one_grid_line_left_is_also_cannot_tell():
    """The mirror of the glare case: a corner lost in deep window shadow."""
    before = _board_frame([(2, 2, BLACK)])
    after = before.copy()
    x, y = _cell_centre(2, 2)
    after[y - 30 : y + 30, x - 30 : x + 30] = 2
    after[y - 30 : y + 30, x - 2 : x + 2] = 60  # one grid line keeps the std up
    reference = ReferenceFrame(_sampler(), to_gray(before), _empty_board())
    mask, sim = reference.unchanged(to_gray(after), ZNCC)
    assert np.isnan(sim[2][2]) and not mask[2][2]


def _shaded(frame, gain):
    """The same scene under a light that has moved: a left-to-right brightness ramp scaled by `gain`."""
    ramp = np.linspace(1.0 - gain, 1.0 + gain, SIZE, dtype=np.float32)[None, :, None]
    return np.clip(frame.astype(np.float32) * ramp, 0, 255).astype(np.uint8)


def test_a_refresh_absorbs_drift_but_never_a_new_stone_nobody_recognised():
    """Fan 2026-09-23: refresh while the player thinks. A stone that landed unrecognised in that minute
    must keep the old sample, or it would later be vetoed as 'the reference says empty here'."""
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame()), _empty_board())
    later = to_gray(_shaded(_board_frame([(4, 4, BLACK)]), 0.05))
    refreshed, kept = reference.refreshed(later, ZNCC, REFERENCE_ANCHOR_ZNCC)
    assert kept[4][4] and kept.sum() == 1
    sim = refreshed.similarity(later)
    assert sim[4][4] < ZNCC  # the unrecognised stone still reads as a change
    assert np.nanmin(np.delete(sim.reshape(-1), 4 * 19 + 4)) > 0.999  # everything else is this frame now
    assert (refreshed.board == reference.board).all() and refreshed is not reference


def test_a_refresh_step_is_bounded_by_the_current_sample_too():
    """With the anchor gate wide open, the minute-to-minute gate alone still keeps the new stone out."""
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame()), _empty_board())
    _, kept = reference.refreshed(to_gray(_board_frame([(4, 4, BLACK)])), ZNCC, -1.0)
    assert kept[4][4] and kept.sum() == 1


def _shadow_edge(frame, x0, width=30, depth=0.6):
    """A soft shadow edge (a window frame) at x = x0, shadow on its left."""
    xs = np.arange(SIZE, dtype=np.float32)
    mask = 1.0 - (1.0 - depth) * np.clip((x0 - xs) / width + 0.5, 0.0, 1.0)
    return np.clip(frame.astype(np.float32) * mask[None, :, None], 0, 255).astype(np.uint8)


def test_minute_refreshes_follow_a_shadow_edge_that_would_age_the_capture_out():
    """The reason refresh exists: a shadow edge creeping across a cell. Each minute changes it a little,
    the sum ends below the veto threshold against the original capture."""
    x, _ = _cell_centre(4, 4)
    frames = [to_gray(_shadow_edge(_board_frame(), x + dx)) for dx in range(-40, 1, 8)]
    original = ReferenceFrame(_sampler(), frames[0], _empty_board())
    refreshed = original
    for frame in frames[1:]:
        refreshed, _ = refreshed.refreshed(frame, ZNCC, REFERENCE_ANCHOR_ZNCC)
    assert original.similarity(frames[-1])[4][4] < ZNCC  # without refresh the rule would go quiet here
    assert refreshed.similarity(frames[-1])[4][4] >= ZNCC  # with it, the cell is still protected


def test_a_sampler_compares_and_hashes_by_identity():
    sampler = _sampler()
    assert sampler == sampler and sampler != _sampler()  # no elementwise ndarray comparison
    assert len({sampler}) == 1


def test_a_frame_of_the_wrong_size_is_refused():
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame()), _empty_board())
    with pytest.raises(ValueError):
        reference.similarity(np.zeros((640, 640), np.uint8))


from types import SimpleNamespace
from unittest.mock import patch as mock_patch

from katrain.vision.board_state import EMPTY
from katrain.vision.ipc import CommandType, WorkerCommand
from katrain.vision.worker_inprocess import (
    REFERENCE_HOLD_KEEP,
    REFERENCE_ANCHOR_ZNCC,
    REFERENCE_HOLD_SUPPRESS,
    REFERENCE_REFRESH_S,
    REFERENCE_ZNCC,
    InProcessAdapter,
)


def _adapter(mode="on"):
    with mock_patch("katrain.vision.worker_inprocess.StoneDetector"):
        adapter = InProcessAdapter({"board_size": 19, "reference_check": mode}, camera=None)
    adapter._geometry = SimpleNamespace(points=None)
    adapter._bound = True
    return adapter


def _with_reference(mode, ref_frame, ref_board):
    adapter = _adapter(mode)
    adapter._ref_sampler = _sampler()
    adapter._reference = ReferenceFrame(adapter._ref_sampler, to_gray(ref_frame), ref_board)
    return adapter


def test_the_threshold_the_worker_uses_is_the_one_the_unit_tests_assert():
    assert REFERENCE_ZNCC == ZNCC


def test_a_stone_the_game_knows_survives_a_detector_that_lost_it():
    truth = _empty_board()
    truth[4][4] = BLACK
    frame = _board_frame([(4, 4, BLACK)])
    adapter = _with_reference("on", frame, truth)
    detector_says = truth.copy()
    detector_says[4][4] = EMPTY  # glare ate the stone
    effective = adapter._reference_check(detector_says, to_gray(frame))
    assert effective[4][4] == BLACK
    assert detector_says[4][4] == EMPTY  # the caller's array is never mutated


def test_an_invented_stone_is_suppressed_but_only_for_a_few_frames():
    frame = _board_frame()
    adapter = _with_reference("on", frame, _empty_board())
    detector_says = _empty_board()
    detector_says[12][3] = WHITE
    for _ in range(REFERENCE_HOLD_SUPPRESS):
        assert adapter._reference_check(detector_says, to_gray(frame))[12][3] == EMPTY
    # the detector keeps insisting: it wins that cell for the rest of this reference's life
    assert adapter._reference_check(detector_says, to_gray(frame))[12][3] == WHITE
    assert adapter._ref_released[12][3] and adapter._reference is not None
    assert adapter._reference_check(detector_says, to_gray(frame))[12][3] == WHITE


def test_releasing_an_invented_stone_does_not_cut_the_hold_on_a_lost_one():
    """One daylight glare often does both at once; the review found that dropping the whole reference
    on the first exhausted cell ended the long hold after only REFERENCE_HOLD_SUPPRESS frames."""
    truth = _empty_board()
    truth[4][4] = BLACK
    frame = _board_frame([(4, 4, BLACK)])
    adapter = _with_reference("on", frame, truth)
    detector_says = _empty_board()  # lost (4,4) ...
    detector_says[12][3] = WHITE  # ... and invented (12,3)
    for _ in range(REFERENCE_HOLD_SUPPRESS + 5):
        effective = adapter._reference_check(detector_says, to_gray(frame))
    assert effective[4][4] == BLACK and effective[12][3] == WHITE


def test_a_missing_stone_is_held_far_longer_than_an_invented_one():
    assert REFERENCE_HOLD_KEEP > 5 * REFERENCE_HOLD_SUPPRESS
    truth = _empty_board()
    truth[4][4] = BLACK
    frame = _board_frame([(4, 4, BLACK)])
    adapter = _with_reference("on", frame, truth)
    detector_says = truth.copy()
    detector_says[4][4] = EMPTY
    for _ in range(REFERENCE_HOLD_SUPPRESS + 5):
        assert adapter._reference_check(detector_says, to_gray(frame))[4][4] == BLACK
    assert adapter._reference is not None


def test_a_colour_disagreement_gets_the_short_hold_not_the_long_one():
    """board_state.py:316 releases a wrong colour after 15 raw frames by design; the reference must
    not re-block that for half a minute."""
    truth = _empty_board()
    truth[4][4] = BLACK
    frame = _board_frame([(4, 4, BLACK)])
    adapter = _with_reference("on", frame, truth)
    detector_says = truth.copy()
    detector_says[4][4] = WHITE
    for _ in range(REFERENCE_HOLD_SUPPRESS):
        assert adapter._reference_check(detector_says, to_gray(frame))[4][4] == BLACK
    assert adapter._reference_check(detector_says, to_gray(frame))[4][4] == WHITE


def test_the_hold_budget_is_cumulative_so_a_flapping_detector_cannot_reset_it():
    """A detector that sees the stone only every other frame would never exhaust a *consecutive*
    counter, and the suppression would be permanent."""
    frame = _board_frame()
    adapter = _with_reference("on", frame, _empty_board())
    invented, agreeing = _empty_board(), _empty_board()
    invented[12][3] = WHITE
    for _ in range(REFERENCE_HOLD_SUPPRESS):
        adapter._reference_check(invented, to_gray(frame))
        adapter._reference_check(agreeing, to_gray(frame))  # a frame where the detector agrees again
    assert adapter._reference_check(invented, to_gray(frame))[12][3] == WHITE


def test_a_real_change_is_left_alone_so_the_move_still_lands():
    adapter = _with_reference("on", _board_frame(), _empty_board())
    detector_says = _empty_board()
    detector_says[9][9] = WHITE
    out = adapter._reference_check(detector_says, to_gray(_board_frame([(9, 9, WHITE)])))
    assert out[9][9] == WHITE and adapter._ref_hold[9][9] == 0


def test_shadow_mode_reports_but_returns_the_board_untouched(caplog):
    frame = _board_frame()
    adapter = _with_reference("shadow", frame, _empty_board())
    detector_says = _empty_board()
    detector_says[12][3] = WHITE
    with caplog.at_level("INFO"):
        out = adapter._reference_check(detector_says, to_gray(frame))
    assert out is detector_says  # identical object: nothing downstream can diverge
    assert "would keep" in caplog.text and "(12,3)" in caplog.text


def test_a_lit_lamp_cell_is_left_to_the_detector():
    frame = _board_frame()
    adapter = _with_reference("on", frame, _empty_board())
    adapter._lit_points = {(12, 3)}
    detector_says = _empty_board()
    detector_says[12][3] = WHITE
    assert adapter._reference_check(detector_says, to_gray(frame))[12][3] == WHITE


def test_the_reference_is_taken_only_when_nothing_can_be_hiding_in_it():
    adapter = _adapter("on")
    frame = _board_frame([(4, 4, BLACK)])
    gray = to_gray(frame)
    board = _empty_board()
    board[4][4] = BLACK
    adapter._expected_np = board

    adapter._maybe_capture_reference(_empty_board(), _empty_board(), gray)  # camera disagrees
    assert adapter._reference is None
    adapter._lit_points = {(3, 3)}
    adapter._maybe_capture_reference(board, board, gray)  # a lamp is lit
    assert adapter._reference is None
    adapter._lit_points = set()
    adapter._paused = True
    adapter._maybe_capture_reference(board, board, gray)  # recognition is paused
    assert adapter._reference is None
    adapter._paused = False
    real_detector, adapter._move_detector = adapter._move_detector, SimpleNamespace(pending_move=(4, 4, BLACK))
    adapter._maybe_capture_reference(board, board, gray)  # a move is being confirmed
    assert adapter._reference is None
    adapter._move_detector = real_detector
    adapter._ref_vetoing = True
    adapter._maybe_capture_reference(board, board, gray)  # this frame's board is being corrected
    assert adapter._reference is None
    adapter._ref_vetoing = False
    stale = board.copy()
    stale[4][4] = EMPTY  # this frame's own observation has not caught up with the vote
    adapter._maybe_capture_reference(board, stale, gray)
    assert adapter._reference is None

    adapter._maybe_capture_reference(board, board, gray)
    assert adapter._reference is not None and adapter._reference.board[4][4] == BLACK


def test_the_same_expected_board_is_never_re_captured(monkeypatch):
    """v1 re-took the reference every 2 s while the board was unchanged, which fixated a poisoned one."""
    monkeypatch.setattr("katrain.vision.worker_inprocess.time.monotonic", lambda: 1000.0)
    adapter = _adapter("on")
    board = _empty_board()
    adapter._expected_np = board
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame()))
    first = adapter._reference
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame(seed=1)))
    assert adapter._reference is first

    board = board.copy()
    board[4][4] = BLACK
    adapter._expected_np = board
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame([(4, 4, BLACK)])))
    assert adapter._reference is not first and adapter._reference.board[4][4] == BLACK


def test_a_long_think_refreshes_the_reference_per_cell_once_a_minute(monkeypatch, caplog):
    clock = [1000.0]
    monkeypatch.setattr("katrain.vision.worker_inprocess.time.monotonic", lambda: clock[0])
    adapter = _adapter("on")
    board = _empty_board()
    adapter._expected_np = board
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame()))
    first = adapter._reference
    adapter._ref_hold[2][2] = 7
    adapter._ref_released[3][3] = True
    later = to_gray(_shaded(_board_frame([(4, 4, BLACK)]), 0.05))

    clock[0] += REFERENCE_REFRESH_S - 1
    adapter._maybe_capture_reference(board, board, later)
    assert adapter._reference is first

    clock[0] += 1
    with caplog.at_level("INFO"):
        adapter._maybe_capture_reference(board, board, later)
    assert adapter._reference is not first
    assert adapter._reference.similarity(later)[4][4] < REFERENCE_ZNCC  # the unrecognised stone was not absorbed
    assert adapter._ref_hold[2][2] == 7 and adapter._ref_released[3][3]  # a refresh is not a new reference
    assert "refcheck refreshed" in caplog.text and "(4,4)" in caplog.text

    second = adapter._reference
    clock[0] += 30
    adapter._maybe_capture_reference(board, board, later)
    assert adapter._reference is second  # the minute restarts at each refresh


def test_the_worker_stops_absorbing_a_cell_once_it_has_left_the_original_capture(monkeypatch, caplog):
    """Codex 2026-09-23 P2: minute-to-minute matches are not transitive. A stone fading in over ten
    minutes passes the 0.90 step gate every time; only the anchor gate stops the chain."""
    clock = [1000.0]
    monkeypatch.setattr("katrain.vision.worker_inprocess.time.monotonic", lambda: clock[0])
    empty = to_gray(_board_frame()).astype(np.float32)
    stone = to_gray(_board_frame([(4, 4, BLACK)])).astype(np.float32)
    adapter = _adapter("on")
    board = _empty_board()
    adapter._expected_np = board
    adapter._maybe_capture_reference(board, board, empty.astype(np.uint8))
    for t in np.linspace(0.1, 1.0, 10):
        clock[0] += REFERENCE_REFRESH_S
        caplog.clear()
        with caplog.at_level("INFO"):
            adapter._maybe_capture_reference(board, board, ((1 - t) * empty + t * stone).astype(np.uint8))
    assert "refcheck refreshed" in caplog.text and "(4,4)" in caplog.text


def test_the_reference_is_dropped_by_every_discontinuity():
    for command in (
        WorkerCommand(action=CommandType.UNBIND),
        WorkerCommand(action=CommandType.BIND),
        WorkerCommand(action=CommandType.RESET_SYNC),
        WorkerCommand(action=CommandType.ENTER_SETUP_MODE, data={"target_board": _empty_board().tolist()}),
        WorkerCommand(action=CommandType.SET_PAUSED, data={"paused": True}),
    ):
        adapter = _with_reference("on", _board_frame(), _empty_board())
        adapter._cmd_queue.put(command)
        adapter._drain_commands()
        assert adapter._reference is None, command.action

    adapter = _with_reference("on", _board_frame(), _empty_board())
    adapter.set_geometry(None)
    assert adapter._reference is None and adapter._ref_sampler is None


def test_a_move_keeps_the_reference_but_an_undo_or_a_jump_drops_it():
    ref_board = _empty_board()
    ref_board[4][4] = BLACK
    one_more = ref_board.copy()
    one_more[5][5] = WHITE
    undone = _empty_board()
    jumped = ref_board.copy()
    jumped[5][5] = WHITE
    jumped[6][6] = BLACK

    # the orchestrator re-sends the same board off game state, which must not count as a jump
    for board, kept in ((ref_board, True), (one_more, True), (undone, False), (jumped, False)):
        adapter = _with_reference("on", _board_frame([(4, 4, BLACK)]), ref_board)
        adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_EXPECTED_BOARD, data={"board": board.tolist()}))
        adapter._drain_commands()
        assert (adapter._reference is not None) is kept


def test_one_passing_veto_does_not_freeze_the_reference_for_good():
    """The first draft blocked capture while any hold count was non-zero, and only a capture reset
    them: one frame of glare kept the reference on an old position for the rest of its life."""
    ref_board = _empty_board()
    adapter = _with_reference("on", _board_frame(), ref_board)
    glare = _empty_board()
    glare[12][3] = WHITE
    adapter._reference_check(glare, to_gray(_board_frame()))  # one frame of glare
    adapter._reference_check(_empty_board(), to_gray(_board_frame()))  # and it is gone
    moved = ref_board.copy()
    moved[4][4] = BLACK  # the game moves on, the player plays it
    adapter._expected_np = moved
    adapter._maybe_capture_reference(moved, moved, to_gray(_board_frame([(4, 4, BLACK)])))
    assert adapter._reference.board[4][4] == BLACK


def test_an_unknown_mode_is_reported_and_changes_nothing(caplog):
    with caplog.at_level("WARNING"):
        adapter = _adapter("On")
    assert adapter._ref_mode == "shadow" and "reference_check" in caplog.text


def test_off_mode_never_takes_a_reference():
    adapter = _adapter("off")
    board = _empty_board()
    adapter._expected_np = board
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame()))
    assert adapter._reference is None


# ---- through the real loop -------------------------------------------------------------------
# Helper-level tests cannot prove where the loop puts the two boards. These drive `_loop()` the way
# tests/test_vision/test_sustain_threshold.py does, with a scripted camera, scripted detections and
# scripted warped frames.

from unittest.mock import MagicMock  # noqa: E402

from katrain.vision.board_state import BoardStateExtractor  # noqa: E402
from katrain.vision.stone_detector import Detection  # noqa: E402
from tests.test_vision.board_state_corpus import grid_to_px  # noqa: E402


class _ScriptedDetector:
    instance = None

    def __init__(self, model_path, backend="ultralytics", confidence_threshold=0.5, **kwargs):
        self.confidence_threshold = confidence_threshold
        self.script = []
        _ScriptedDetector.instance = self

    def detect(self, image):
        return list(self.script.pop(0)) if self.script else []


class _ScriptedCamera:
    is_connected = True

    def __init__(self, frames, drop_reference_at=None):
        self.frames = frames
        self.drop_reference_at = drop_reference_at
        self.worker = None

    def read_frame(self):
        self.frames -= 1
        if self.frames == self.drop_reference_at:
            # a pause / resync / re-lock landing mid-placement, which is what opens the window
            self.worker._invalidate_reference("test")
        if self.frames <= 0:
            self.worker._running = False
        return np.zeros((10, 10, 3), dtype=np.uint8)


def _det(row, col, cls, conf=0.9):
    x, y = grid_to_px(CONFIG, float(col), float(row))
    return Detection(x_center=x, y_center=y, class_id=cls, confidence=conf, bbox=(x - 20, y - 20, x + 20, y + 20))


def _run_loop(mode, warped_frames, detection_script, game, averager=None, drop_reference_at=None):
    """Drive the real loop. `warped_frames` is one BGR frame per processed frame (the last repeats),
    `detection_script` one detection list per frame, `game` the expected board."""
    camera = _ScriptedCamera(len(detection_script), drop_reference_at)
    with mock_patch("katrain.vision.worker_inprocess.StoneDetector", _ScriptedDetector):
        worker = InProcessAdapter(
            {"board_size": 19, "enhance": "off", "auto_exposure": "off", "reference_check": mode}, camera=camera
        )
    camera.worker = worker
    worker.needs_frames = lambda: True
    worker._bound = True
    worker._geometry = SimpleNamespace(points=None)
    worker._expected_np = game
    worker._running = True
    worker._config["capture_fps"] = 100000
    worker._motion_is_stable = MagicMock(return_value=True)
    frames = list(warped_frames)
    worker._warp_frame = lambda frame: (frames.pop(0) if len(frames) > 1 else frames[0], True)
    worker._averager = MagicMock()
    worker._averager.add.side_effect = averager or (lambda frame: frame)
    extractor = BoardStateExtractor(CONFIG)
    worker._active_extractor = lambda: extractor
    worker._maybe_send_preview = MagicMock()
    worker._ref_sampler = _sampler()
    _ScriptedDetector.instance.script = [list(frame) for frame in detection_script]
    worker._loop()
    return worker


def _invented_stone_script(n=6):
    """The board is empty and the game agrees; from frame 3 the detector invents a white stone."""
    empty_frame = _board_frame()
    game = _empty_board()
    script = [[]] * 2 + [[_det(12, 3, 1)]] * n
    return [empty_frame], script, game


def test_on_mode_hides_the_invented_stone_downstream_but_keeps_recognition_history_raw():
    frames, script, game = _invented_stone_script()
    worker = _run_loop("on", frames, script, game)
    assert worker._reference is not None  # the first two frames agreed with the game: reference taken
    assert int(worker._last_stable_board[12][3]) == WHITE  # history stays raw, so the detector is visible
    assert int(worker.get_status().detected_board[12][3]) == EMPTY  # downstream got the corrected board


def test_shadow_mode_is_behaviour_identical_to_off():
    frames, script, game = _invented_stone_script()
    shadow = _run_loop("shadow", frames, script, game)
    off = _run_loop("off", frames, script, game)
    assert np.array_equal(shadow._last_stable_board, off._last_stable_board)
    assert np.array_equal(shadow.get_status().detected_board, off.get_status().detected_board)
    assert shadow.get_status().sync_state == off.get_status().sync_state


def test_the_check_runs_on_the_pre_average_frame():
    """If the comparison ever moved behind the frame averager, this fails: the averager here returns a
    flat frame, which has no structure to correlate, so nothing could be vetoed."""
    frames, script, game = _invented_stone_script()
    flat = _run_loop("on", frames, script, game, averager=lambda frame: np.full_like(frame, 128))
    assert int(flat.get_status().detected_board[12][3]) == EMPTY


def test_the_first_frame_of_a_real_stone_is_never_captured_as_a_reference():
    """The poisoning sequence: something drops the reference (pause, resync, re-lock) just as a stone
    is going down. On the first frame that shows it, the two-frame vote still says empty and
    MoveDetector has no pending move yet, so a capture there would photograph the stone and label its
    cell empty -- and then erase that stone for as long as the reference lives."""
    game = _empty_board()
    script = [[]] * 2 + [[_det(9, 9, 1)]] * 4
    frames = [_board_frame(), _board_frame(), _board_frame([(9, 9, WHITE)])]
    worker = _run_loop("on", frames, script, game, drop_reference_at=3)
    assert worker._reference is None or int(worker._reference.board[9][9]) == EMPTY
    if worker._reference is not None:  # a later frame may legitimately re-take it
        _, sim = worker._reference.unchanged(to_gray(_board_frame([(9, 9, WHITE)])), REFERENCE_ZNCC)
        assert sim[9][9] < REFERENCE_ZNCC, "the reference contains the stone it calls empty"


def test_the_worker_config_carries_the_reference_check_mode():
    from katrain.vision.config_service import VisionServiceConfig

    assert VisionServiceConfig().to_worker_config()["reference_check"] == "shadow"
    assert VisionServiceConfig(reference_check="on").to_worker_config()["reference_check"] == "on"
