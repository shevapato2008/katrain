"""End-to-end: shadow boxes from the RK3562 daylight game (2026-09-23) must not reach the board.

Geometry is the deployed go4_s.rknn's own output on that board, run through the live order -- dedup_detections,
then drop_shadow_boxes, then the board-state path (parallax on, occupancy-aware assignment, sticky). See
superpowers/tracks/vision-optimizations/shadow-dedup/design.md §1 for how H5 became a self-sustaining phantom
and D7 a sub-threshold prompt.
"""

import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.classes import STONE_CLASS_IDS
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.parallax import ParallaxParams
from katrain.vision.stone_detector import Detection, dedup_detections

IMG = 1056
FIXTURE = json.loads((Path(__file__).parent / "data" / "shadow_dedup_20260923.json").read_text())
TRUTH = np.array(FIXTURE["truth_board"])
G5, H5 = (14, 6), (14, 7)

# G5 black stone (frame warped_09) and its shadow box at the two positions the live log recorded:
#   frame 1: raw (13.69, 6.364) -> corrected column 6.5006 -> rounds into the EMPTY H5
#   frame 2: raw (13.71, 6.33)  -> corrected column 6.467  -> held on H5 by sticky assignment (0.63 < 0.65)
G5_STONE = Detection(x_center=360.33, y_center=792.29, class_id=0, confidence=0.50, bbox=(332.6, 761.8, 388.0, 822.8))


def _shadow(x, y, conf=0.45):
    return Detection(
        x_center=x, y_center=y, class_id=0, confidence=conf, bbox=(x - 24.95, y - 25.55, x + 24.95, y + 25.55)
    )


FRAME1_SHADOW = _shadow(388.82, 775.63)
FRAME2_SHADOW = _shadow(387.02, 776.69)


def _extractor():
    return BoardStateExtractor(
        BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS), parallax=ParallaxParams(**FIXTURE["parallax"])
    )


def _live(ex, raw):
    """What the worker hands on: dedup inside StoneDetector.detect, then the shadow step."""
    return ex.drop_shadow_boxes(dedup_detections(raw), IMG, IMG)


def _board(ex, dets, prev=None):
    return ex.detections_to_board(
        dets, img_w=IMG, img_h=IMG, occupancy_aware=True, add_threshold=0.40, prev_board=prev, sticky_board=prev
    )


def _frame(name):
    return [Detection(d["x"], d["y"], d["cls"], d["conf"], tuple(d["bbox"])) for d in FIXTURE["frames"][name]]


def _empty_points_hit(ex, dets):
    """Truth-EMPTY intersections that some stone box rounds onto (parallax-corrected)."""
    hits = set()
    for _, _, fy, fx, cls, _ in ex.parallax_points([d for d in dets if d.class_id in STONE_CLASS_IDS], IMG, IMG):
        r, c = int(round(fy)), int(round(fx))
        if 0 <= r < 19 and 0 <= c < 19 and TRUTH[r][c] == 0:
            hits.add((r, c))
    return hits


def test_the_h5_chain_reproduces_without_the_shadow_step():
    """Precondition: the fixture really drives the live phantom path, dedup included. If this goes red, the
    assignment code changed and the tests below no longer prove anything about shadows."""
    ex = _extractor()
    b1 = _board(ex, dedup_detections([G5_STONE, FRAME1_SHADOW]))
    b2 = _board(ex, dedup_detections([G5_STONE, FRAME2_SHADOW]), prev=b1)
    assert b1[H5] == 1 and b2[H5] == 1
    assert b1[G5] == 1 and b2[G5] == 1


def test_the_shadow_step_breaks_the_h5_chain():
    ex = _extractor()
    b1 = _board(ex, _live(ex, [G5_STONE, FRAME1_SHADOW]))
    assert b1[H5] == 0 and b1[G5] == 1
    # Frame 2 starting from a board where the phantom is ALREADY established (sticky would hold it): the
    # shadow step must release it, not merely avoid creating it.
    phantom = _board(ex, dedup_detections([G5_STONE, FRAME1_SHADOW]))
    assert phantom[H5] == 1  # precondition
    b2 = _board(ex, _live(ex, [G5_STONE, FRAME2_SHADOW]), prev=phantom)
    assert b2[H5] == 0 and b2[G5] == 1


def test_sub_threshold_shadow_no_longer_reaches_an_empty_point():
    """The D7 path: a shadow box below the add threshold (0.32, as logged for D7) that rounds onto an EMPTY
    point is a cell_top candidate for the ambiguous-move prompt. In warped_09 the box beside C8 does this
    (its own score there is 0.24; the test lifts it to 0.32)."""
    ex = _extractor()
    raw = _frame("warped_09.jpg")
    hits = _empty_points_hit(ex, dedup_detections(raw))
    assert hits == {(10, 2)}  # precondition: C9, and only C9, after dedup alone
    shadow = next(
        d
        for d in raw
        if d.class_id in STONE_CLASS_IDS
        and (int(round(ex.parallax_points([d], IMG, IMG)[0][2])), int(round(ex.parallax_points([d], IMG, IMG)[0][3])))
        == (10, 2)
    )
    raw = [dataclasses.replace(d, confidence=0.32) if d is shadow else d for d in raw]
    keep_tier = [d for d in dedup_detections(raw) if d.confidence >= 0.30]
    assert (10, 2) in ex.cell_top(keep_tier, IMG, IMG)  # precondition: the prompt path would see it
    kept = [d for d in _live(ex, raw) if d.confidence >= 0.30]
    assert (10, 2) not in ex.cell_top(kept, IMG, IMG)


@pytest.mark.parametrize("name, missed", [("warped_06.jpg", set()), ("warped_09.jpg", {(5, 2)})])
def test_real_frames_lose_no_stone_and_reach_no_empty_point(name, missed):
    """Whole frames: after dedup and the shadow step, the board equals the truth except C14 in warped_09,
    whose box scores 0.365 -- below the 0.40 add threshold, with no previous board -- and no stone box
    rounds onto an empty point."""
    ex = _extractor()
    kept = _live(ex, _frame(name))
    assert _empty_points_hit(ex, kept) == set()
    board = _board(ex, [d for d in kept if d.confidence >= 0.30])
    diff = {(r, c) for r in range(19) for c in range(19) if board[r][c] != TRUTH[r][c]}
    assert diff == missed
