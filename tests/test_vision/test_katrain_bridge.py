import pytest
from katrain.core.sgf_parser import Move
from katrain.vision.katrain_bridge import vision_move_to_katrain
from katrain.vision.board_state import BLACK, WHITE


class TestVisionToKatrain:
    def test_black_stone_at_origin(self):
        """Vision (col=0, row=0) = image top-left = GTP A19 on 19x19 board."""
        move = vision_move_to_katrain(col=0, row=0, color=BLACK)
        assert move.player == "B"
        assert move.coords == (0, 18)  # col=0, katrain_row = 18-0 = 18
        assert move.gtp() == "A19"

    def test_black_stone_bottom_left(self):
        """Vision (col=0, row=18) = image bottom-left = GTP A1."""
        move = vision_move_to_katrain(col=0, row=18, color=BLACK)
        assert move.coords == (0, 0)
        assert move.gtp() == "A1"

    def test_tengen(self):
        """Vision (col=9, row=9) = center = GTP K10."""
        move = vision_move_to_katrain(col=9, row=9, color=WHITE)
        assert move.player == "W"
        assert move.coords == (9, 9)
        assert move.gtp() == "K10"

    def test_d4_star_point(self):
        """Vision (col=3, row=15) = GTP D4 (bottom-left star point)."""
        move = vision_move_to_katrain(col=3, row=15, color=BLACK)
        assert move.coords == (3, 3)
        assert move.gtp() == "D4"

    def test_sgf_roundtrip(self):
        """Verify SGF output matches KaTrain convention."""
        move = vision_move_to_katrain(col=3, row=15, color=BLACK, board_size=19)
        sgf = move.sgf((19, 19))
        reconstructed = Move.from_sgf(sgf, (19, 19), player="B")
        assert reconstructed.coords == move.coords

    def test_to_api_coords(self):
        """Output format compatible with MoveRequest.coords (web API)."""
        move = vision_move_to_katrain(col=9, row=9, color=BLACK)
        # MoveRequest.coords = list(Move.coords) = [col, row]
        assert list(move.coords) == [9, 9]
