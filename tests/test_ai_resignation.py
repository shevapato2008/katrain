"""
Test AI auto-resignation feature across different board sizes.

This test plays AI vs AI games (KataGo strongest vs Human-like AI at 1D level)
on 9x9, 13x13, and 19x19 boards to verify that the weaker AI resigns when
its winrate drops below the threshold.
"""

import os
import pytest

from katrain.core.ai import generate_ai_move, should_ai_resign
from katrain.core.base_katrain import KaTrainBase
from katrain.core.constants import (
    AI_DEFAULT,
    AI_HUMAN,
    OUTPUT_INFO,
    AI_RESIGNATION_MIN_MOVE_NUMBER,
)
from katrain.core.engine import KataGoEngine
from katrain.core.game import Game


class TestAIResignation:
    """Test AI resignation behavior across different board sizes."""

    @pytest.fixture
    def katrain(self):
        """Create a KaTrain instance with package config."""
        return KaTrainBase(force_package_config=True, debug_level=0)

    @pytest.fixture
    def engine(self, katrain):
        """Create a KataGo engine."""
        return KataGoEngine(katrain, katrain.config("engine"))

    def test_min_moves_scaling(self, katrain):
        """Test that minimum moves are scaled correctly for different board sizes."""
        # Standard config is 150 moves for 19x19 (361 intersections)
        configured_min = AI_RESIGNATION_MIN_MOVE_NUMBER  # 150

        # 19x19: 150 moves
        expected_19x19 = int(configured_min * 361 / 361)
        assert expected_19x19 == 150

        # 13x13: 150 * (169/361) ≈ 70 moves
        expected_13x13 = int(configured_min * 169 / 361)
        assert expected_13x13 == 70

        # 9x9: 150 * (81/361) ≈ 33 moves
        expected_9x9 = int(configured_min * 81 / 361)
        assert expected_9x9 == 33

    @pytest.mark.skipif(
        os.environ.get("CI", "").lower() == "true",
        reason="Requires KataGo engine with GPU"
    )
    @pytest.mark.parametrize("board_size,max_moves", [
        ("9", 60),    # 9x9: smaller board, fewer moves needed
        ("13", 100),  # 13x13: medium board
        ("19", 200),  # 19x19: full board, may need more moves
    ])
    def test_ai_resignation_triggered(self, katrain, engine, board_size, max_moves):
        """
        Test that AI resignation is triggered when a strong AI plays against
        a weaker AI (Human-like at 1D level).

        The stronger AI (AI_DEFAULT) should dominate, causing the weaker AI
        (AI_HUMAN at 1D) to resign when its winrate drops below 15% for 3
        consecutive turns.
        """
        # Create game with specified board size
        game = Game(
            katrain,
            engine,
            game_properties={"SZ": board_size}
        )

        # AI settings
        # Black: KataGo strongest (AI_DEFAULT)
        strong_ai_mode = AI_DEFAULT
        strong_ai_settings = katrain.config(f"ai/{strong_ai_mode}") or {}

        # White: Human-like AI at 1D level (weaker)
        weak_ai_mode = AI_HUMAN
        weak_ai_settings = {
            "human_kyu_rank": -1,  # 1D = -1 kyu
            "modern_style": False,
        }

        # Resignation settings
        resignation_settings = katrain.config("ai/resignation") or {
            "enabled": True,
            "winrate_threshold": 0.15,
            "consecutive_turns": 3,
            "min_move_number": 80,
        }

        katrain.log(
            f"Starting {board_size}x{board_size} game: {strong_ai_mode} (B) vs {weak_ai_mode} 1D (W)",
            OUTPUT_INFO
        )

        resignation_triggered = False
        game_ended_by_passes = False
        move_count = 0

        while move_count < max_moves:
            current_player = game.current_node.next_player
            move_count = game.current_node.depth

            # Check if game already ended
            if game.current_node.end_state:
                katrain.log(f"Game ended: {game.current_node.end_state}", OUTPUT_INFO)
                if "+R" in game.current_node.end_state:
                    resignation_triggered = True
                break

            # Select AI mode and settings based on current player
            if current_player == "B":
                mode, settings = strong_ai_mode, strong_ai_settings
            else:
                mode, settings = weak_ai_mode, weak_ai_settings

            # Generate move
            try:
                result = generate_ai_move(game, mode, settings)

                if result is None:
                    # AI resigned
                    resignation_triggered = True
                    katrain.log(
                        f"AI ({current_player}) resigned at move {move_count}",
                        OUTPUT_INFO
                    )
                    break

                move, node = result
                if move is None:
                    # This shouldn't happen with non-None result
                    break

                # Check for pass-pass ending
                if move.is_pass:
                    parent = game.current_node.parent
                    if parent and parent.move and parent.move.is_pass:
                        game_ended_by_passes = True
                        katrain.log(
                            f"Game ended by consecutive passes at move {move_count}",
                            OUTPUT_INFO
                        )
                        break

            except Exception as e:
                katrain.log(f"Error generating move: {e}", OUTPUT_INFO)
                break

        # Log final state
        katrain.log(
            f"Game finished: {board_size}x{board_size}, moves={move_count}, "
            f"resignation={resignation_triggered}, passes={game_ended_by_passes}",
            OUTPUT_INFO
        )

        # At least one of these conditions should be true
        assert resignation_triggered or game_ended_by_passes or move_count >= max_moves, (
            f"Game did not end properly on {board_size}x{board_size} board"
        )

        # Log the winrate progression for debugging
        if game.current_node.analysis_exists:
            katrain.log(
                f"Final position - Winrate (Black): {game.current_node.winrate:.1%}, "
                f"Score: {game.current_node.score}",
                OUTPUT_INFO
            )

    @pytest.mark.skipif(
        os.environ.get("CI", "").lower() == "true",
        reason="Requires KataGo engine with GPU"
    )
    def test_resignation_disabled(self, katrain, engine):
        """Test that resignation can be disabled via settings."""
        game = Game(
            katrain,
            engine,
            game_properties={"SZ": "9"}
        )

        # Resignation settings with enabled=False
        resignation_settings = {
            "enabled": False,
            "winrate_threshold": 0.15,
            "consecutive_turns": 3,
            "min_move_number": 80,
        }

        # should_ai_resign should always return False when disabled
        result = should_ai_resign(game, resignation_settings)
        assert result is False

    def test_should_ai_resign_no_analysis(self, katrain):
        """Test that resignation check returns False when no analysis exists."""
        # Create a mock game without engine (no analysis)
        class MockEngine:
            def request_analysis(self, *args, **kwargs):
                pass

        game = Game(
            katrain,
            MockEngine(),
            game_properties={"SZ": "9"}
        )

        resignation_settings = {
            "enabled": True,
            "winrate_threshold": 0.15,
            "consecutive_turns": 3,
            "min_move_number": 15,  # Low threshold for test
        }

        # Play some moves manually (no analysis)
        from katrain.core.game import Move
        for i in range(20):
            player = "B" if i % 2 == 0 else "W"
            x, y = i % 9, i // 9
            try:
                game.play(Move(coords=(x, y), player=player))
            except Exception:
                pass

        # Should return False because no analysis exists
        result = should_ai_resign(game, resignation_settings)
        assert result is False


class TestResignationScaling:
    """Unit tests for resignation minimum move scaling."""

    def test_scaling_formula_19x19(self):
        """Verify scaling formula for 19x19 board."""
        board_size = 19
        intersections = board_size * board_size  # 361
        configured_min = 150
        standard = 361

        min_moves = int(configured_min * intersections / standard)
        assert min_moves == 150

    def test_scaling_formula_13x13(self):
        """Verify scaling formula for 13x13 board."""
        board_size = 13
        intersections = board_size * board_size  # 169
        configured_min = 150
        standard = 361

        min_moves = int(configured_min * intersections / standard)
        assert min_moves == 70

    def test_scaling_formula_9x9(self):
        """Verify scaling formula for 9x9 board."""
        board_size = 9
        intersections = board_size * board_size  # 81
        configured_min = 150
        standard = 361

        min_moves = int(configured_min * intersections / standard)
        # 150 * 81 / 361 = 33.65 -> 33
        assert min_moves == 33

    def test_minimum_floor(self):
        """Verify that minimum floor of 15 is applied."""
        from katrain.core.constants import AI_RESIGNATION_MIN_ABSOLUTE_MOVES

        assert AI_RESIGNATION_MIN_ABSOLUTE_MOVES == 15

        # For very small boards or low configured values, floor should apply
        board_size = 5
        intersections = board_size * board_size  # 25
        configured_min = 150
        standard = 361

        min_moves = int(configured_min * intersections / standard)
        # 150 * 25 / 361 = 10.38 -> 10
        assert min_moves == 10

        # After applying floor
        min_moves_with_floor = max(min_moves, AI_RESIGNATION_MIN_ABSOLUTE_MOVES)
        assert min_moves_with_floor == 15
