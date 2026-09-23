"""Reference-frame check (2026-09-23): per-cell ZNCC against the last frame whose board matched the
game record, as bounded evidence against daylight false negatives/positives.
Design: superpowers/tracks/vision-reference-frame/design.md
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
        assert abs((xs.min() + xs.max()) / 2 - x) <= 2 and abs((ys.min() + ys.max()) / 2 - y) <= 2


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


def test_a_frame_of_the_wrong_size_is_refused():
    reference = ReferenceFrame(_sampler(), to_gray(_board_frame()), _empty_board())
    with pytest.raises(ValueError):
        reference.similarity(np.zeros((640, 640), np.uint8))
