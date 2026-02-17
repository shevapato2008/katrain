"""
Detects newly placed stones by comparing consecutive board states.

Only detects "new stone added" — automatically handles captures (removed opponent stones
are ignored). Provides force_sync() for undo/endgame scenarios.
"""

import numpy as np

from katrain.vision.board_state import EMPTY


class MoveDetector:
    """Detects new moves by comparing board states across frames."""

    def __init__(self, consistency_frames: int = 3):
        self.consistency_frames = consistency_frames
        self.prev_board: np.ndarray | None = None
        self.pending_move: tuple[int, int, int] | None = None
        self.count = 0

    def detect_new_move(self, board: np.ndarray) -> tuple[int, int, int] | None:
        """
        Compare current board with previous accepted state.

        Returns:
            (row, col, color) if a single new stone is confirmed, None otherwise.
            Only detects stones added to empty positions (captures are ignored).
        """
        if self.prev_board is None:
            self.prev_board = board.copy()
            return None

        # Find positions where a stone was added to a previously empty intersection
        diff_positions = []
        for r in range(board.shape[0]):
            for c in range(board.shape[1]):
                if self.prev_board[r][c] == EMPTY and board[r][c] != EMPTY:
                    diff_positions.append((r, c, int(board[r][c])))

        if len(diff_positions) != 1:
            self.count = 0
            self.pending_move = None
            return None

        move = diff_positions[0]
        if move == self.pending_move:
            self.count += 1
        else:
            self.pending_move = move
            self.count = 1

        if self.count >= self.consistency_frames:
            self.prev_board = board.copy()
            self.count = 0
            self.pending_move = None
            return move

        return None

    def force_sync(self, board: np.ndarray) -> None:
        """Force-update the reference board (for undo, endgame cleanup, manual reset)."""
        self.prev_board = board.copy()
        self.count = 0
        self.pending_move = None
