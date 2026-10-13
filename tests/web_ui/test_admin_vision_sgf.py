"""Pure SGF preparation uses the real replay engine, without capture side effects."""

import hashlib
import re
from dataclasses import FrozenInstanceError

import pytest


def test_prepare_preserves_original_sgf_and_stable_identity():
    from katrain.web.admin.vision_sgf import prepare_vision_sgf

    sgf = "(;SZ[19]PB[黑棋];B[pd];W[dp])\n"
    prepared = prepare_vision_sgf(sgf)

    assert prepared.original_sgf == sgf
    assert prepared.sgf_sha256 == hashlib.sha256(sgf.encode("utf-8")).hexdigest()
    assert prepared.game_id == prepare_vision_sgf(sgf).game_id
    assert re.fullmatch(r"[a-z0-9_-]+", prepared.game_id)
    assert prepared.board_size == 19
    assert len(prepared.steps) == 2
    assert prepared.placement_indices == (0, 1)
    assert prepared.next_placement_index() == 0
    assert prepared.next_placement_index(after=0) == 1
    assert prepared.next_placement_index(after=1) is None
    assert (prepared.steps[0].row, prepared.steps[0].col, prepared.steps[0].color) == (3, 15, "B")
    assert not hasattr(prepared.steps[0], "led_point")
    with pytest.raises(FrozenInstanceError):
        prepared.steps[0].row = 10
    with pytest.raises(FrozenInstanceError):
        prepared.game_id = "replaced"


@pytest.mark.parametrize("size", ["13", "9", "19:13", "13:19", "19:20", "20:19", "broken", "19:19:19"])
def test_rejects_non_19_by_checking_source_width_and_height(size):
    from katrain.web.admin.vision_sgf import VisionSgfError, prepare_vision_sgf

    with pytest.raises(VisionSgfError):
        prepare_vision_sgf(f"(;SZ[{size}];B[aa])")


@pytest.mark.parametrize(
    "sgf",
    ["", "not SGF", "(;SZ[19];B[aa]", "(;SZ[19];B[zx])", "(;SZ[19];B[aa];W[aa])", "(;SZ[19]) trailing"],
)
def test_rejects_malformed_sgf_with_validation_error(sgf):
    from katrain.web.admin.vision_sgf import VisionSgfError, prepare_vision_sgf

    with pytest.raises(VisionSgfError):
        prepare_vision_sgf(sgf)


@pytest.mark.parametrize("sgf", [None, b"(;SZ[19])", "(;C[\ud800])"])
def test_requires_utf8_encodable_text(sgf):
    from katrain.web.admin.vision_sgf import VisionSgfError, prepare_vision_sgf

    with pytest.raises(VisionSgfError, match="UTF-8"):
        prepare_vision_sgf(sgf)


def test_size_limit_counts_utf8_bytes():
    from katrain.web.admin.vision_sgf import MAX_SGF_BYTES, VisionSgfError, prepare_vision_sgf

    assert MAX_SGF_BYTES == 2 * 1024 * 1024
    sgf = "(;SZ[19]C[" + "棋" * (MAX_SGF_BYTES // 3) + "])"
    assert len(sgf) < MAX_SGF_BYTES < len(sgf.encode("utf-8"))
    with pytest.raises(VisionSgfError, match="2 MiB"):
        prepare_vision_sgf(sgf)


def test_accepts_exact_byte_limit_and_implicit_19_board():
    from katrain.web.admin.vision_sgf import MAX_SGF_BYTES, prepare_vision_sgf

    sgf = "(;C[" + "a" * (MAX_SGF_BYTES - 6) + "])"
    assert len(sgf.encode("utf-8")) == MAX_SGF_BYTES
    prepared = prepare_vision_sgf(sgf)
    assert prepared.board_size == 19
    assert prepared.steps == ()
    assert prepared.next_placement_index() is None


def test_preserves_setup_capture_pass_and_clear_truth_without_led_data():
    from katrain.core.baipu import build_steps_from_sgf, expected_board_from_steps
    from katrain.web.admin.vision_sgf import prepare_vision_sgf

    sgf = "(;SZ[19]AB[ab][ba][bc]AW[bb];B[cb];W[];AE[ab];W[dd])"
    prepared = prepare_vision_sgf(sgf)
    truth = build_steps_from_sgf(sgf)["steps"]

    assert [step.kind for step in prepared.steps] == ["setup"] * 4 + ["move", "pass", "clear", "move"]
    assert prepared.placement_indices == (0, 1, 2, 3, 4, 7)
    assert prepared.next_placement_index(after=4) == 7
    assert prepared.next_placement_index(after=7) is None
    for step, expected in zip(prepared.steps, truth):
        assert step.move_index == expected["move_index"]
        assert step.property == expected["property"]
        assert (step.row, step.col, step.color) == (expected["row"], expected["col"], expected["color"])
        assert step.board_hash == expected["board_hash"]
        assert [(point.row, point.col) for point in step.removed] == [
            (point["row"], point["col"]) for point in expected["removed"]
        ]
        assert not hasattr(step, "led_point")
    assert [(point.row, point.col) for point in prepared.steps[4].removed] == [(1, 1)]
    assert prepared.steps[5].board_hash == prepared.steps[4].board_hash
    assert [(point.row, point.col) for point in prepared.steps[6].removed] == [(1, 0)]
    assert prepared.steps[6].board_hash != prepared.steps[5].board_hash
    final_board = expected_board_from_steps(truth, 7)
    assert final_board[1][1] is None  # real capture
    assert final_board[1][0] is None  # AE clear
    assert final_board[3][3] == "W"
    with pytest.raises(FrozenInstanceError):
        prepared.steps[4].removed[0].row = 9


@pytest.mark.parametrize(
    "sgf",
    [
        "(;SZ[19]SZ[13];B[aa])",
        "(;SZ[19];B[aaa])",
        "(;SZ[19];AB[xx:zz])",
        "(;SZ[19];AB[ss:aa])",
        "(;SZ[19];B[aa][bb])",
        "(;SZ[19];B[aa]W[bb])",
    ],
)
def test_rejects_ambiguous_size_and_malformed_points(sgf):
    from katrain.web.admin.vision_sgf import VisionSgfError, prepare_vision_sgf

    with pytest.raises(VisionSgfError):
        prepare_vision_sgf(sgf)
