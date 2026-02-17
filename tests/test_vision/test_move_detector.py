import numpy as np
import pytest
from katrain.vision.move_detector import MoveDetector
from katrain.vision.board_state import BLACK, WHITE, EMPTY


@pytest.fixture
def detector():
    return MoveDetector(consistency_frames=3)


class TestMoveDetector:
    def test_no_change_returns_none(self, detector):
        board = np.zeros((19, 19), dtype=int)
        for _ in range(5):
            assert detector.detect_new_move(board) is None

    def test_detects_new_black_stone_after_consistency(self, detector):
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK

        assert detector.detect_new_move(with_stone) is None  # count=1
        assert detector.detect_new_move(with_stone) is None  # count=2
        result = detector.detect_new_move(with_stone)  # count=3
        assert result == (3, 3, BLACK)

    def test_resets_count_on_change(self, detector):
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK

        detector.detect_new_move(with_stone)  # count=1
        detector.detect_new_move(with_stone)  # count=2
        different = empty.copy()
        different[5][5] = WHITE
        detector.detect_new_move(different)  # count reset
        assert detector.detect_new_move(with_stone) is None  # count=1 again

    def test_ignores_multiple_simultaneous_new_stones(self, detector):
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        two_stones = empty.copy()
        two_stones[3][3] = BLACK
        two_stones[4][4] = WHITE

        for _ in range(5):
            assert detector.detect_new_move(two_stones) is None

    def test_handles_captures(self, detector):
        """Placing a stone that removes opponent stones: only the new stone is detected."""
        board1 = np.zeros((19, 19), dtype=int)
        board1[3][3] = WHITE  # opponent stone
        detector.detect_new_move(board1)

        board2 = board1.copy()
        board2[3][3] = EMPTY  # captured
        board2[3][4] = BLACK  # new move

        assert detector.detect_new_move(board2) is None  # count=1
        assert detector.detect_new_move(board2) is None  # count=2
        result = detector.detect_new_move(board2)  # count=3
        assert result == (3, 4, BLACK)

    def test_force_sync(self, detector):
        board1 = np.zeros((19, 19), dtype=int)
        board1[3][3] = BLACK
        detector.detect_new_move(board1)

        board2 = np.zeros((19, 19), dtype=int)  # stone removed (undo)
        detector.force_sync(board2)
        assert np.array_equal(detector.prev_board, board2)
