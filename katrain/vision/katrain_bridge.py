"""
Bridge between vision grid coordinates and KaTrain's Move objects.

Vision grid: board[row][col], (0,0) = image top-left.
KaTrain Move: coords=(col, row), row 0 = bottom (GTP convention).

This module does NOT reimplement GTP/SGF conversion — it reuses
katrain.core.sgf_parser.Move which already handles all of that correctly.
"""

from katrain.core.sgf_parser import Move
from katrain.vision.board_state import BLACK, WHITE


def vision_move_to_katrain(col: int, row: int, color: int, board_size: int = 19) -> Move:
    """
    Convert a vision-detected move to a KaTrain Move object.

    Args:
        col: Column index in vision grid (0 = left of image)
        row: Row index in vision grid (0 = top of image)
        color: BLACK (1) or WHITE (2)
        board_size: Board size (default 19)

    Returns:
        katrain.core.sgf_parser.Move with correct GTP/SGF coordinates
    """
    player = "B" if color == BLACK else "W"
    katrain_row = board_size - 1 - row  # flip Y: vision top → GTP bottom
    return Move(coords=(col, katrain_row), player=player)
