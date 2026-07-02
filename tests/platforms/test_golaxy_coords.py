"""Golden-value tests for the Golaxy coordinate codec.

Golaxy encodes a board point as a single integer:

    coord = (19 - boardRow) * 19 + colIndex

where boardRow is 1..19 with 19 at the TOP of the board, and colIndex is
0..18 left-to-right (letters A=0, B=1, ..., H=7, J=8 [I skipped], K=9, ...).

KaTrain uses 0-indexed (col, row) from the top-left, row 0 = top (same
convention as the existing generic katrain/web/platforms/coords.py). Golden
values below were captured live on 2026-07-02 and are expressed in GTP
notation (human-verifiable) then converted to KaTrain (col, row) using the
existing, already-tested gtp_to_katrain/katrain_to_gtp helpers -- this test
file does NOT re-derive the GTP<->KaTrain mapping, only golaxy<->KaTrain.
"""

import pytest

from katrain.web.platforms.coords import gtp_to_katrain, katrain_to_gtp
from katrain.web.platforms.golaxy.coords import (
    GolaxyCoordResult,
    Move,
    Pass,
    Resign,
    UnknownSpecial,
    golaxy_to_katrain,
    katrain_to_golaxy,
)

BOARD_SIZE = 19

# Live-captured GTP -> golaxy coord golden pairs.
GOLDEN_GTP_TO_COORD = [
    ("Q16", 72),
    ("Q4", 300),
    ("D4", 288),
    ("D16", 60),
    ("Q10", 186),
    ("R6", 263),
    ("D10", 174),
    ("C6", 249),
    ("K4", 294),
]

# Derived boundary values (verified by the formula).
BOUNDARY_GTP_TO_COORD = [
    ("A19", 0),
    ("T19", 18),
    ("A1", 342),
    ("T1", 360),
    ("K10", 180),  # tengen
]


class TestKatrainToGolaxyGolden:
    @pytest.mark.parametrize("gtp, coord", GOLDEN_GTP_TO_COORD)
    def test_golden_encode(self, gtp, coord):
        col, row = gtp_to_katrain(gtp, BOARD_SIZE)
        assert katrain_to_golaxy(col, row, BOARD_SIZE) == coord

    @pytest.mark.parametrize("gtp, coord", BOUNDARY_GTP_TO_COORD)
    def test_boundary_encode(self, gtp, coord):
        col, row = gtp_to_katrain(gtp, BOARD_SIZE)
        assert katrain_to_golaxy(col, row, BOARD_SIZE) == coord


class TestGolaxyToKatrainGolden:
    @pytest.mark.parametrize("gtp, coord", GOLDEN_GTP_TO_COORD)
    def test_golden_decode(self, gtp, coord):
        col, row = gtp_to_katrain(gtp, BOARD_SIZE)
        result = golaxy_to_katrain(coord, BOARD_SIZE)
        assert result == Move(col, row)

    @pytest.mark.parametrize("gtp, coord", BOUNDARY_GTP_TO_COORD)
    def test_boundary_decode(self, gtp, coord):
        col, row = gtp_to_katrain(gtp, BOARD_SIZE)
        result = golaxy_to_katrain(coord, BOARD_SIZE)
        assert result == Move(col, row)

    def test_decode_249_is_c6(self):
        result = golaxy_to_katrain(249, BOARD_SIZE)
        assert isinstance(result, Move)
        assert katrain_to_gtp(result.col, result.row, BOARD_SIZE) == "C6"

    def test_decode_286_is_b4(self):
        result = golaxy_to_katrain(286, BOARD_SIZE)
        assert isinstance(result, Move)
        assert katrain_to_gtp(result.col, result.row, BOARD_SIZE) == "B4"


class TestRoundTrip:
    def test_round_trip_full_board_19x19(self):
        for col in range(19):
            for row in range(19):
                coord = katrain_to_golaxy(col, row, 19)
                result = golaxy_to_katrain(coord, 19)
                assert result == Move(col, row), f"Roundtrip failed for ({col}, {row})"

    def test_round_trip_full_board_9x9(self):
        for col in range(9):
            for row in range(9):
                coord = katrain_to_golaxy(col, row, 9)
                result = golaxy_to_katrain(coord, 9)
                assert result == Move(col, row), f"Roundtrip failed for ({col}, {row})"


class TestOutOfRangeDecode:
    @pytest.mark.parametrize("raw", [-1, 361, 999])
    def test_out_of_range_returns_unknown_special(self, raw):
        result = golaxy_to_katrain(raw, BOARD_SIZE)
        assert isinstance(result, UnknownSpecial)
        assert result.raw == raw

    def test_negative_is_unknown_special_not_exception(self):
        # golaxy_to_katrain must never raise for untrusted network input.
        result = golaxy_to_katrain(-5, BOARD_SIZE)
        assert isinstance(result, UnknownSpecial)
        assert result.raw == -5

    def test_last_valid_index_decodes_to_move(self):
        # board_size*board_size - 1 is the last valid on-board index.
        result = golaxy_to_katrain(BOARD_SIZE * BOARD_SIZE - 1, BOARD_SIZE)
        assert isinstance(result, Move)

    def test_first_out_of_range_index_is_unknown_special(self):
        result = golaxy_to_katrain(BOARD_SIZE * BOARD_SIZE, BOARD_SIZE)
        assert isinstance(result, UnknownSpecial)


class TestOutOfRangeEncode:
    @pytest.mark.parametrize("col, row", [(19, 0), (0, 19), (-1, 0), (0, -1)])
    def test_out_of_range_raises_value_error(self, col, row):
        with pytest.raises(ValueError):
            katrain_to_golaxy(col, row, 19)

    def test_error_message_names_bad_value(self):
        with pytest.raises(ValueError, match="25"):
            katrain_to_golaxy(25, 0, 19)


class TestResultTypes:
    """Pass/Resign are provided as pattern-matchable types, but decode does
    NOT currently produce them (real sentinel encodings are unverified)."""

    def test_move_is_a_golaxy_coord_result(self):
        assert issubclass(Move, GolaxyCoordResult)

    def test_pass_is_a_golaxy_coord_result(self):
        assert issubclass(Pass, GolaxyCoordResult)

    def test_resign_is_a_golaxy_coord_result(self):
        assert issubclass(Resign, GolaxyCoordResult)

    def test_unknown_special_is_a_golaxy_coord_result(self):
        assert issubclass(UnknownSpecial, GolaxyCoordResult)

    def test_decode_never_produces_pass_or_resign_this_iteration(self):
        # Sentinel encodings for PASS/RESIGN are unverified this iteration;
        # golaxy_to_katrain must classify anything not a valid on-board
        # index as UnknownSpecial rather than guessing.
        for raw in (-1, 361, 999, -100, 10000):
            result = golaxy_to_katrain(raw, BOARD_SIZE)
            assert not isinstance(result, Pass)
            assert not isinstance(result, Resign)
            assert isinstance(result, UnknownSpecial)
