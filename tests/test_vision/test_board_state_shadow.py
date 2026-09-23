"""drop_shadow_boxes: a stone's shadow boxed a second time (side light) is removed after dedup; real stones,
however tightly packed, are not. Geometry from the RK3562 daylight game (2026-09-23) and the labelled set
(kifu_24171); see superpowers/tracks/vision-optimizations/shadow-dedup/design.md."""

import logging
import random

from katrain.vision.board_state import (
    BLACK,
    SHADOW_MIN_OFFSET,
    WHITE,
    BoardStateExtractor,
    _overlap_of_smaller,
)
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig
from katrain.vision.parallax import ParallaxParams
from katrain.vision.stone_detector import Detection
from tests.test_vision.board_state_corpus import IMG, grid_to_px

CFG = BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS)
DAYLIGHT_PARALLAX = ParallaxParams(nadir_fx=19.612, nadir_fy=9.0, k=0.989689)  # the 09-23 board's lock
CELL = 949 / 18  # px per cell in the 1056 px warp


def _box(x, y, cls, conf, w, h=None):
    h = w if h is None else h
    return Detection(
        x_center=x, y_center=y, class_id=cls, confidence=conf, bbox=(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    )


def _at(row, col, cls, conf, cells=1.1):
    x, y = grid_to_px(CFG, col, row)
    return _box(x, y, cls, conf, cells * CELL)


def _drop(dets, parallax=None):
    return BoardStateExtractor(CFG, parallax=parallax).drop_shadow_boxes(dets, IMG, IMG)


def _stubbed(positions):
    """An extractor whose grid positions are given exactly: {id(detection): (row, col)}."""
    ex = BoardStateExtractor(CFG)
    ex._positions = lambda d, w, h: (positions[id(d)][1], positions[id(d)][0]) * 2 + (True,)
    return ex


# G5 black stone in frame warped_09 and its shadow box at the two positions the live log recorded
G5 = Detection(x_center=360.33, y_center=792.29, class_id=0, confidence=0.50, bbox=(332.6, 761.8, 388.0, 822.8))
SHADOW_POSITIONS = ((388.82, 775.63), (387.02, 776.69))  # corrected column 6.501 / 6.467: 0.62 / 0.58 off a point


def _g5_shadow(x, y, conf=0.45):
    return _box(x, y, 0, conf, 49.9, 51.1)


def test_a_stones_shadow_box_is_dropped_and_the_stone_kept():
    for x, y in SHADOW_POSITIONS:
        assert _drop([G5, _g5_shadow(x, y)], DAYLIGHT_PARALLAX) == [G5]


def test_a_box_that_outscores_its_partner_is_never_dropped():
    """A shadow that outscores its stone (never seen live: 0 of 36) is left alone, exactly as before this step
    existed -- the step never deletes the higher-scoring box of a pair."""
    stone = Detection(G5.x_center, G5.y_center, 0, 0.45, G5.bbox)
    for x, y in SHADOW_POSITIONS:
        shadow = _g5_shadow(x, y, conf=0.50)
        assert _drop([stone, shadow], DAYLIGHT_PARALLAX) == [stone, shadow]


def test_two_touching_real_stones_are_both_kept():
    """kifu_24171 frame 098 (labelled set), deployed model's own boxes: two white stones pushed together.
    Their boxes overlap by 0.38 -- as much as a shadow -- but both sit on a point. The first version of this
    fix merged one of them away (gate FAIL, 45 frames)."""
    left = Detection(
        315.4741413116455,
        895.2108535766602,
        1,
        0.3651,
        (287.62708053588864, 866.7678405761718, 343.32120208740236, 923.6538665771484),
    )
    right = Detection(
        354.6771755218506,
        897.7171234130859,
        1,
        0.4284,
        (322.0275512695312, 867.1066223144531, 387.3267997741699, 928.3276245117187),
    )
    assert _overlap_of_smaller(left.bbox, right.bbox) >= 0.27  # precondition: overlap alone would drop one
    assert _drop([left, right]) == [left, right]


def test_a_row_of_five_touching_same_colour_stones_is_kept():
    """Five-in-a-row stress case: every stone touches the next (0.95 cells apart) and the boxes are wide
    enough to overlap their neighbours by 0.30. The row drifts off the grid by 0.05 cells per stone."""
    row = [_at(9, 3 + 0.95 * k, WHITE - 1, 0.7, cells=1.35) for k in range(5)]
    assert all(_overlap_of_smaller(a.bbox, b.bbox) >= 0.27 for a, b in zip(row, row[1:]))  # precondition
    assert _drop(row) == row


def test_the_shadow_at_the_end_of_a_row_is_dropped_and_the_row_kept():
    row = [_at(9, 3 + 0.95 * k, WHITE - 1, 0.7, cells=1.35) for k in range(5)]
    shadow = _at(9, 3 + 0.95 * 4 + 0.6, BLACK - 1, 0.45, cells=1.0)
    assert _drop([*row, shadow]) == row


def test_a_stone_pushed_off_its_point_toward_its_shadow_is_kept():
    """A stone 0.4 cells off its point, its shadow box 0.6 further out -- landing on the next point. Geometry
    alone would call the STONE the shadow (it is the one between points); it scored higher, so it stays."""
    stone = _at(9, 5.4, BLACK - 1, 0.7, cells=1.1)
    shadow = _at(9, 6.0, BLACK - 1, 0.45, cells=1.0)
    assert _overlap_of_smaller(stone.bbox, shadow.bbox) >= 0.27  # precondition: the pair qualifies on overlap
    assert _drop([stone, shadow]) == [stone, shadow]


def test_a_box_is_only_a_shadow_of_a_box_nearer_a_point():
    """Two overlapping boxes both between points: the one nearer a point is not the other one's shadow, even
    when it scored lower."""
    nearer = _at(9, 5.38, BLACK - 1, 0.40, cells=1.1)
    farther = _at(9, 5.55, BLACK - 1, 0.60, cells=1.1)
    assert _overlap_of_smaller(nearer.bbox, farther.bbox) >= 0.27  # precondition
    assert _drop([nearer, farther]) == [nearer, farther]


def test_overlap_threshold_boundary():
    # Two 50 px squares dx apart: overlap = (50 - dx) / 50; dx = 36.5 gives exactly the double 0.27.
    near, far_at, far_below = _box(100, 100, 0, 0.9, 50), _box(136.5, 100, 0, 0.8, 50), _box(137, 100, 0, 0.8, 50)
    ex = _stubbed({id(near): (0.0, 0.0), id(far_at): (0.0, 0.5), id(far_below): (0.0, 0.5)})
    assert ex.drop_shadow_boxes([near, far_at], IMG, IMG) == [near]
    assert ex.drop_shadow_boxes([near, far_below], IMG, IMG) == [near, far_below]


def test_offset_threshold_boundary():
    near, far = _box(100, 100, 0, 0.9, 50), _box(120, 100, 0, 0.8, 50)
    assert SHADOW_MIN_OFFSET == 0.35
    at = _stubbed({id(near): (0.0, 0.0), id(far): (0.0, 0.35)})  # exactly 0.35 (0.35 - round(0.35) == 0.35)
    below = _stubbed({id(near): (0.0, 0.0), id(far): (0.0, 0.34)})
    assert at.drop_shadow_boxes([near, far], IMG, IMG) == [near]
    assert below.drop_shadow_boxes([near, far], IMG, IMG) == [near, far]


def test_side_ratio_boundary():
    big_at, big_above, small = _box(100, 100, 0, 0.9, 100), _box(100, 100, 0, 0.9, 105), _box(150, 100, 0, 0.8, 50)
    ex = _stubbed({id(big_at): (0.0, 0.0), id(big_above): (0.0, 0.0), id(small): (0.0, 0.5)})
    assert ex.drop_shadow_boxes([big_at, small], IMG, IMG) == [big_at]  # side ratio exactly 2.0
    assert ex.drop_shadow_boxes([big_above, small], IMG, IMG) == [big_above, small]  # 2.1


def test_a_big_box_does_not_make_the_stones_under_it_shadows():
    """A hand read as one big box (3x a stone) sitting on a point, scoring higher than everything under it. A stone
    under it pushed 0.4 cells off its point is fully inside the hand box (overlap 1.0), nearer-a-point and
    confidence both point at the stone -- only the side-ratio guard keeps it."""
    hand = _at(9, 9, BLACK - 1, 0.9, cells=3.0)
    stones = [_at(9, 8.6, WHITE - 1, 0.6), _at(9, 10, BLACK - 1, 0.7), _at(10, 9, WHITE - 1, 0.8)]
    assert _overlap_of_smaller(stones[0].bbox, hand.bbox) == 1.0  # precondition
    assert _drop([hand, *stones]) == [hand, *stones]


def test_led_boxes_are_never_dropped():
    stone, lamp = _at(9, 9, BLACK - 1, 0.8), _at(9, 9.5, 2, 0.7)  # led_red, half a cell off, overlapping
    assert _drop([stone, lamp]) == [stone, lamp]


def test_boxes_without_area_or_finite_position_pass_through():
    stone = _at(9, 9, BLACK - 1, 0.8)
    x, y = grid_to_px(CFG, 9.5, 9)
    flat = Detection(x, y, 0, 0.7, (x - 25, y, x + 25, y))
    no_x = Detection(float("nan"), y, 0, 0.7, (x - 25, y - 25, x + 25, y + 25))
    no_y = Detection(x, float("nan"), 0, 0.7, (x - 25, y - 25, x + 25, y + 25))
    far = Detection(float("inf"), y, 0, 0.7, (x - 25, y - 25, x + 25, y + 25))
    dets = [stone, flat, no_x, no_y, far]
    assert _drop(dets) == dets


def test_the_result_does_not_depend_on_input_order():
    row = [_at(9, 3 + 0.95 * k, WHITE - 1, 0.7, cells=1.35) for k in range(5)]
    dets = [*row, _at(9, 3 + 0.95 * 4 + 0.6, BLACK - 1, 0.45, cells=1.0), G5, _g5_shadow(*SHADOW_POSITIONS[0])]
    want = {id(d) for d in _drop(dets, DAYLIGHT_PARALLAX)}
    rng = random.Random(7)
    for _ in range(20):
        shuffled = dets[:]
        rng.shuffle(shuffled)
        assert {id(d) for d in _drop(shuffled, DAYLIGHT_PARALLAX)} == want


def test_the_worker_drops_a_shadow_before_the_board_sees_it():
    """Production wiring: the in-process worker applies the step to what the detector returns. Without it,
    the shadow (0.45, above the 0.40 add threshold) becomes a black stone on the empty point beside the
    stone; the test harness replaces only the detector, so this runs the real loop."""
    from tests.test_vision.test_sustain_threshold import _run

    stone = _at(10, 10, BLACK - 1, 0.8, cells=1.05)
    shadow = _at(10, 10.6, BLACK - 1, 0.45, cells=1.0)
    plain = BoardStateExtractor(CFG).detections_to_board(
        [stone, shadow], img_w=IMG, img_h=IMG, occupancy_aware=True, add_threshold=0.40
    )
    assert plain[10][11] == BLACK  # precondition: without the step the shadow lands on (10, 11)
    board, _ = _run({"confidence_threshold": 0.40, "confidence_keep": 0.30}, [[stone, shadow]] * 6)
    assert int(board[10][10]) == BLACK and int(board[10][11]) == 0


def test_the_worker_logs_how_many_shadow_boxes_it_dropped(caplog):
    """The board test must see the step fire, not infer it from silence."""
    from tests.test_vision.test_sustain_threshold import _run

    stone = _at(10, 10, BLACK - 1, 0.8, cells=1.05)
    shadow = _at(10, 10.6, BLACK - 1, 0.45, cells=1.0)
    caplog.set_level(logging.INFO, logger="katrain.vision.worker_inprocess")
    _run({"confidence_threshold": 0.40, "confidence_keep": 0.30}, [[stone, shadow]] * 30)
    records = [r for r in caplog.records if r.message.startswith("vision: ")]
    assert len(records) == 1
    assert "shadow=30," in records[0].message
