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


def test_a_refresh_absorbs_every_comparable_cell_including_the_changed_ones():
    """Fan 2026-09-24 的裁定,推翻了 09-23 那版「变了的格子保留旧样本」。

    参考帧就是「这次落子之前,棋盘像素级的样子」。一团反光只有先进了参考帧照片,
    「照片一样 + 地图说空」这条证据才成立、否决才生效 —— 现场 (18,12) 的 zncc=1.00 正是这么来的。
    跳过变化格意味着反光要一直等到下一次参考帧**重建**才被拦,中间那段窗口它畅通无阻。

    地图(哪格有子)仍然不随刷新变 —— 只有落子确认后的重建才换地图。

    ⚠️ 代价:一颗没被识别出来的真子也会被吸收进照片,日后检测器看见它时会命中
    「照片一样 + 地图说空」而被否决,且同日已取消压制方向的帧数上限 ⇒ 无法自动恢复。
    取舍依据:反光当天多次发作(一颗重播 8 分 48 秒、一局三轮),这一种 0 次。
    """
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame()), _empty_board())
    later = to_gray(_shaded(_board_frame([(4, 4, BLACK)]), 0.05))
    refreshed, absorbed = reference.refreshed(later, ZNCC, REFERENCE_ANCHOR_ZNCC)
    assert absorbed[4][4] and absorbed.sum() == 1  # 只有这一格是「变了才被吸收的」
    sim = refreshed.similarity(later)
    assert sim[4][4] > 0.999, "变了的格子也必须被吸收 —— 否则反光进不了基准,否决就建立不起来"
    assert np.nanmin(sim.reshape(-1)) > 0.999  # 整份基准都是这一帧了
    assert (refreshed.board == reference.board).all() and refreshed is not reference


def test_the_refresh_no_longer_gates_on_either_threshold():
    """09-23 有两道闸(与上一次的照片比、与最初的 anchor 比)挡住"把变化吸收进基准"。
    Fan 2026-09-24 的裁定取消了它们:参考帧就该是落子前那一刻的样子,变了的格更该更新。

    两个阈值参数保留在签名里,只用来统计「哪些格是变了才被吸收的」(第二个返回值),不再决定去留。
    这条用**把 anchor 闸开到最大**来证明:无论阈值怎么设,那颗新子都会被吸收进照片。
    """
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame()), _empty_board())
    later = to_gray(_board_frame([(4, 4, BLACK)]))
    for anchor_threshold in (-1.0, REFERENCE_ANCHOR_ZNCC, 0.999):
        refreshed, absorbed = reference.refreshed(later, ZNCC, anchor_threshold)
        assert absorbed[4][4] and absorbed.sum() == 1  # 它就是「变了才被吸收」的那一格
        assert refreshed.similarity(later)[4][4] > 0.999, "阈值不该再影响是否吸收"


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


def test_an_invented_stone_is_suppressed_for_as_long_as_the_pixels_do_not_change():
    """Fan 2026-09-24 的裁定:只要当前画面和参考帧比对没有变化,就持续否定这里有落子。

    旧行为是压 REFERENCE_HOLD_SUPPRESS 帧(板上 ~4.4 秒)就放行,而放行是**粘的**
    (`_ref_released`),于是那一格在这份参考帧余生里不再被否决;偏偏新参考帧要等
    「读数==记录」才拍得成,而那颗假子正好让两者对不上 —— 死锁。现场 (18,12) 因此
    重播了 8 分 48 秒、一局内复发三轮。

    地图里**不可能**有假子(拍摄前置条件要求读数==记录,一有假阳性就拍不成),所以
    「地图说空 + 像素没变」这条证据不会去否决任何系统已知的真子。
    """
    frame = _board_frame()
    adapter = _with_reference("on", frame, _empty_board())
    detector_says = _empty_board()
    detector_says[12][3] = WHITE
    for _ in range(REFERENCE_HOLD_SUPPRESS * 20):  # 远超旧上限
        assert adapter._reference_check(detector_says, to_gray(frame))[12][3] == EMPTY
    assert not adapter._ref_released[12][3], "凭空多出的子不该因为「耗时够久」就获得放行"


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
    # 丢掉的那颗仍被参考帧按住(长预算);凭空多出的那颗现在**没有上限**,一直被否决
    assert effective[4][4] == BLACK and effective[12][3] == EMPTY


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
    # 「凭空多出一颗子」那一路已经没有上限了(见上),所以这条改用仍有预算的**颜色判错**来守。
    truth = _empty_board()
    truth[4][4] = BLACK
    frame = _board_frame([(4, 4, BLACK)])
    adapter = _with_reference("on", frame, truth)
    wrong_colour, agreeing = truth.copy(), truth.copy()
    wrong_colour[4][4] = WHITE
    for _ in range(REFERENCE_HOLD_SUPPRESS):
        adapter._reference_check(wrong_colour, to_gray(frame))
        adapter._reference_check(agreeing, to_gray(frame))  # a frame where the detector agrees again
    assert adapter._reference_check(wrong_colour, to_gray(frame))[4][4] == WHITE


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


def test_monitor_mode_can_capture_and_apply_the_same_reference_filter():
    adapter = _adapter("shadow")
    adapter._bound = False
    adapter._monitor = True
    board = _empty_board()
    adapter._expected_np = board
    gray = to_gray(_board_frame())
    adapter._maybe_capture_reference(board, board, gray)
    assert adapter._reference is not None
    false_positive = board.copy()
    false_positive[12][3] = WHITE
    for _ in range(REFERENCE_HOLD_SUPPRESS + 2):
        assert adapter._reference_check(false_positive, gray)[12][3] == EMPTY
    assert not adapter._ref_released[12][3]


def test_monitor_setup_supplies_the_reference_target_and_stop_drops_it():
    adapter = _adapter("shadow")
    adapter._bound = False
    adapter._monitor = True
    board = _empty_board()
    board[4][4] = BLACK
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.ENTER_SETUP_MODE, data={"target_board": board.tolist()}))
    adapter._drain_commands()
    assert np.array_equal(adapter._expected_np, board)
    adapter._maybe_capture_reference(board, board, to_gray(_board_frame([(4, 4, BLACK)])))
    assert adapter._reference is not None
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_MONITOR, data={"active": False}))
    adapter._drain_commands()
    assert adapter._reference is None and adapter._expected_np is None


def test_monitor_keeps_a_clean_reference_through_multiple_forward_moves():
    adapter = _with_reference("shadow", _board_frame(), _empty_board())
    adapter._bound = False
    adapter._monitor = True
    board = _empty_board()
    for row, col, color in ((4, 4, BLACK), (5, 5, WHITE), (6, 6, BLACK)):
        board[row][col] = color
        adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_EXPECTED_BOARD, data={"board": board.tolist()}))
        adapter._drain_commands()
        assert adapter._reference is not None
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_PAUSED, data={"paused": True}))
    adapter._drain_commands()
    assert adapter._reference is not None


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
    adapter._ref_hold[2][2] = 7  # 这一格刷新时会被重新验证
    adapter._ref_hold[4][4] = 5  # 这一格变了(落了子),刷新验不过,只能保留旧样本
    adapter._ref_released[3][3] = True
    later = to_gray(_shaded(_board_frame([(4, 4, BLACK)]), 0.05))

    clock[0] += REFERENCE_REFRESH_S - 1
    adapter._maybe_capture_reference(board, board, later)
    assert adapter._reference is first

    clock[0] += 1
    with caplog.at_level("INFO"):
        adapter._maybe_capture_reference(board, board, later)
    assert adapter._reference is not first
    # Fan 2026-09-24:刷新把**所有**能比对的格子都拍成当前这一帧,变了的也吸收进来。
    assert adapter._reference.similarity(later)[4][4] > 0.999, "变了的格子也该被吸收进基准"
    # 照片刚跟当前帧对齐过,整份基准都是新鲜的 ⇒ 压制预算清零。
    assert adapter._ref_hold[2][2] == 0 and adapter._ref_hold[4][4] == 0
    assert adapter._ref_released[3][3]  # 已放行的格子不会因刷新而回收
    assert "refcheck refreshed" in caplog.text and "(4,4)" in caplog.text

    second = adapter._reference
    clock[0] += 30
    adapter._maybe_capture_reference(board, board, later)
    assert adapter._reference is second  # the minute restarts at each refresh


# ⛔ 2026-09-24 删除:test_the_worker_stops_absorbing_a_cell_once_it_has_left_the_original_capture
# 它守的是 anchor 闸 ——「一颗子用十分钟慢慢淡入,每一步都过得了 0.90 的步进闸,只有与最初那张
# 照片比对才能斩断这条链」。Fan 的裁定把「变了的格也吸收」定为规则,这条守卫按定义不再存在:
# 现在一步就吸收,不需要十分钟。**代价是真的**:一颗没被识别出来的真子会被直接吸收进基准,
# 而压制方向的帧数上限同日已取消 ⇒ 无法自动恢复,只能重新标定或人工确认。
# 取舍依据写在 ReferenceFrame.refreshed 的 docstring 里。


def test_the_reference_is_dropped_by_every_discontinuity():
    for command in (
        WorkerCommand(action=CommandType.UNBIND),
        WorkerCommand(action=CommandType.BIND),
        WorkerCommand(action=CommandType.RESET_SYNC),
        WorkerCommand(action=CommandType.ENTER_SETUP_MODE, data={"target_board": _empty_board().tolist()}),
    ):
        adapter = _with_reference("on", _board_frame(), _empty_board())
        adapter._cmd_queue.put(command)
        adapter._drain_commands()
        assert adapter._reference is None, command.action

    adapter = _with_reference("on", _board_frame(), _empty_board())
    adapter.set_geometry(None)
    assert adapter._reference is None and adapter._ref_sampler is None


def test_a_pause_does_not_drop_the_reference():
    """2026-09-24 现场故障:每落一手编排器都会暂停(等盘面跟上),于是参考帧一局被销毁 12 次,
    否决在绝大部分时间里根本不可用 —— (18,12) 那颗假白子被 zncc=1.00 连否 3 帧,参考帧一丢
    它就直冲 UI,弹了 12 次 illegal_change。

    暂停期间**不建**新参考仍然保留(那半边该保守),但**不许销毁**已有的:否决是按像素闸的
    (`disagree` 要求 `unchanged` 到 REFERENCE_ZNCC),人在暂停时真动了子,那一格相关度就掉下来、
    否决不了;剩下的由 REFERENCE_HOLD_* 的预算上限兜住。
    """
    for command in (
        WorkerCommand(action=CommandType.SET_PAUSED, data={"paused": True}),
        WorkerCommand(action=CommandType.PAUSE_DETECTION),
    ):
        adapter = _with_reference("on", _board_frame(), _empty_board())
        adapter._cmd_queue.put(command)
        adapter._drain_commands()
        assert adapter._paused is True, command.action
        assert adapter._reference is not None, f"{command.action} 把参考帧丢了 —— 否决随之失效"


def test_a_pause_still_blocks_taking_a_new_reference():
    """保守的那半边不许一起放开:暂停期间画面里可能正在被人动,不能把那个状态冻成新基准。"""
    adapter = _with_reference("on", _board_frame(), _empty_board())
    adapter._reference = None
    adapter._paused = True
    adapter._maybe_capture_reference(_empty_board(), _empty_board(), _board_frame())
    assert adapter._reference is None


def test_an_undo_or_a_jump_marks_the_reference_stale_but_never_empties_the_slot():
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
        # Fan 2026-09-24 的原则:照到新的参考帧才允许销毁旧的。空置换不来空间(任何时刻只持有
        # 一份),只会让否决整个失效 —— (18,12) 那颗假白子就是从这个空窗逃出去的。
        assert adapter._reference is not None, "记账理由不许把槽位清空"
        assert adapter._ref_stale is not kept


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

    def __init__(self, frames, drop_reference_at=None, on_read=None):
        self.frames = frames
        self.drop_reference_at = drop_reference_at
        self.on_read = on_read
        self.worker = None

    def read_frame(self):
        self.frames -= 1
        if self.on_read is not None:
            self.on_read(self.worker, self.frames)
        if self.frames == self.drop_reference_at:
            # a pause / resync / re-lock landing mid-placement, which is what opens the window
            self.worker._invalidate_reference("test")
        if self.frames <= 0:
            self.worker._running = False
        return np.zeros((10, 10, 3), dtype=np.uint8)


def _det(row, col, cls, conf=0.9):
    x, y = grid_to_px(CONFIG, float(col), float(row))
    return Detection(x_center=x, y_center=y, class_id=cls, confidence=conf, bbox=(x - 20, y - 20, x + 20, y + 20))


def _run_loop(mode, warped_frames, detection_script, game, averager=None, drop_reference_at=None, on_read=None):
    """Drive the real loop. `warped_frames` is one BGR frame per processed frame (the last repeats),
    `detection_script` one detection list per frame, `game` the expected board."""
    camera = _ScriptedCamera(len(detection_script), drop_reference_at, on_read)
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


def test_the_promoter_does_not_push_a_cell_the_reference_is_vetoing():
    """2026-09-24 现场:`(18,12)` 两局复现,refcheck 已经 `zncc=1.00 held=7/10` 连否,
    紧接着 `ambiguous promotion: sustained sub-add stone at (18,12) conf=0.33` 把它推进了盘面。

    两个机制的判据正好相反,而提升器不问否决:参考帧说「像素逐点没变 ⇒ 没有新东西落上去」,
    提升器说「这个弱检测一直在 ⇒ 它是真的」。而「一直在」正是反光的特征(反光不会动),
    于是提升器把反光最强的特征当成了它是真子的证据。

    这不会堵死提升器存在的理由(低置信度真子唯一的通道,move_detector.py:183):
    真子会改变像素,参考帧根本不会否决它 —— 下半段用同一格证明放行路径还在。
    """
    from unittest.mock import MagicMock

    def run(vetoed: bool):
        adapter = _with_reference("on", _board_frame(), _empty_board())
        adapter._add_threshold = 0.50
        adapter._expected_np = _empty_board()
        mask = np.zeros((19, 19), dtype=bool)
        mask[18][12] = vetoed
        adapter._ref_disagree = mask
        extractor = MagicMock()
        extractor.cell_top.return_value = {(18, 12): (0.33, 1)}  # 低于阈值的白子候选
        adapter._active_extractor = MagicMock(return_value=extractor)
        adapter._promoter = MagicMock()
        adapter._promoter.step.return_value = (18, 12, 1, 0.33)
        adapter._promote_stuck_stone([], 1920, 1080, _empty_board(), None)
        return adapter._promoter.step.call_args[0][0]

    assert (18, 12) not in run(vetoed=True), "参考帧正在否决这一格,它不该成为提升候选"
    assert (18, 12) in run(vetoed=False), "没有否决时,低置信度真子的通道必须还在"


# ---- 「不是落子」用户标签 ---------------------------------------------------------------


def _deny_at(adapter, frame, row=9, col=9):
    adapter._last_ref_gray = to_gray(frame)
    adapter._cmd_queue.put(WorkerCommand(action=CommandType.DENY_STONE, data={"row": row, "col": col}))
    adapter._drain_commands()


def test_denial_masks_the_false_stone_without_rewriting_recognition_history():
    adapter = _adapter("on")
    frame = _board_frame()
    _deny_at(adapter, frame)
    raw = _empty_board()
    raw[9][9] = WHITE
    adapter._last_stable_board = raw

    effective = adapter._mask_denied(raw, adapter._live_denials(to_gray(frame)))

    assert effective[9][9] == EMPTY
    assert raw[9][9] == WHITE and adapter._last_stable_board[9][9] == WHITE
    assert (9, 9) in adapter._denied


def test_a_real_stone_changes_pixels_and_releases_the_denial():
    adapter = _adapter("on")
    _deny_at(adapter, _board_frame())
    assert adapter._live_denials(to_gray(_board_frame())) == [(9, 9)]

    live = adapter._live_denials(to_gray(_board_frame([(9, 9, WHITE)])))
    raw = _empty_board()
    raw[9][9] = WHITE

    assert live == [] and adapter._denied == {}
    assert adapter._mask_denied(raw, live)[9][9] == WHITE


def test_denial_unblocks_capturing_the_glare_as_empty_in_the_real_loop():
    # The detector reports a white stone on an unchanged empty-board image. Until the user
    # denies it, board != game record and no reference can be captured. The denial must mask
    # both the voted board and the pre-vote observation before the capture guard runs.
    def deny_after_three_frames(worker, frames_left):
        if frames_left == 4:
            assert worker._reference is None
            worker._deny_stone(9, 9)
            assert (9, 9) in worker._denied

    game = _empty_board()
    worker = _run_loop("on", [_board_frame()], [[_det(9, 9, 1)]] * 8, game, on_read=deny_after_three_frames)

    assert worker._reference is not None and worker._reference.board[9][9] == EMPTY
    assert worker._reference.similarity(worker._last_ref_gray)[9][9] > 0.99
    assert worker._last_stable_board[9][9] == WHITE
    assert worker.get_status().detected_board[9][9] == EMPTY


@pytest.mark.parametrize("level", [0, 255])
def test_uncomparable_cell_is_not_remembered_as_a_denial(level, caplog):
    adapter = _adapter("on")
    adapter._last_ref_gray = np.full((SIZE, SIZE), level, np.uint8)

    with caplog.at_level("WARNING"):
        adapter._deny_stone(9, 9)

    assert adapter._denied == {}
    assert "label was NOT stored" in caplog.text


def test_game_record_releases_a_denial_when_it_has_a_stone():
    adapter = _adapter("on")
    _deny_at(adapter, _board_frame())
    board = _empty_board()
    board[9][9] = WHITE

    adapter._cmd_queue.put(WorkerCommand(action=CommandType.SET_EXPECTED_BOARD, data={"board": board.tolist()}))
    adapter._drain_commands()

    assert adapter._denied == {}
    assert adapter._mask_denied(board, adapter._live_denials(to_gray(_board_frame())))[9][9] == WHITE


@pytest.mark.parametrize("action", ["bind", "unbind", "geometry"])
def test_a_new_session_or_geometry_clears_denials(action):
    adapter = _adapter("on")
    _deny_at(adapter, _board_frame())

    if action == "geometry":
        adapter.set_geometry(SimpleNamespace(points=None))
    else:
        adapter._cmd_queue.put(WorkerCommand(action=CommandType.BIND if action == "bind" else CommandType.UNBIND))
        adapter._drain_commands()

    assert adapter._denied == {} and adapter._denial_sampler is None
