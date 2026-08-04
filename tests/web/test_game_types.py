"""The game-type vocabulary, and the one invariant it exists to protect.

Before S3 there were two rank systems writing `users.rank`: the ladder's promotion
ledger and an Elo update that ran on every rated human-vs-human game. These tests
pin the shape that replaced them -- one vocabulary, one rank-moving type.
"""

import importlib.util
from pathlib import Path

from katrain.web.core.ladder_repo import LADDER_GAME_TYPE

# tests/web_ui/conftest.py replaces sys.modules["katrain.web.interface"] with a
# MagicMock at collection time to keep kivy out of its import chain, and
# sys.modules is process-global -- so a plain `from katrain.web.interface import
# WebKaTrain` here would silently assert against a mock whenever both directories
# are collected in the same run. Load the real module from disk under its own name
# instead, so these assertions cannot depend on collection order.
_PATH = Path(__file__).resolve().parents[2] / "katrain" / "web" / "interface.py"
_spec = importlib.util.spec_from_file_location("_real_web_interface_for_tests", _PATH)
_real_interface = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_real_interface)
WebKaTrain = _real_interface.WebKaTrain


def test_exactly_one_game_type_moves_a_rank():
    """A second entry here would silently recreate the two-rank-system bug."""
    assert WebKaTrain.RANK_MOVING_GAME_TYPES == (LADDER_GAME_TYPE,)


def test_rated_pvp_is_anti_cheat_but_not_ranking():
    assert "rated" in WebKaTrain.SCORING_GAME_TYPES, "no analysis, no undo"
    assert "rated" not in WebKaTrain.RANK_MOVING_GAME_TYPES, "but it moves nobody's rank"


def test_the_vocabulary_is_closed():
    assert set(WebKaTrain.SCORING_GAME_TYPES) <= set(WebKaTrain.GAME_TYPES)
    assert set(WebKaTrain.RANK_MOVING_GAME_TYPES) <= set(WebKaTrain.SCORING_GAME_TYPES)


def test_a_new_game_with_no_declared_type_is_a_free_game():
    """The lifecycle reset that stops a casual game played right after a 升降级对弈
    game from being stored as rated and settled into the promotion ledger."""
    k = WebKaTrain(force_package_config=False, enable_engine=False, user_id="test-game-types")
    k.start()
    k("new_game", game_type=LADDER_GAME_TYPE)
    assert k.game_type == LADDER_GAME_TYPE
    assert k.analysis_allowed is False

    k("new_game")  # POST /api/new-game carries no game_type
    assert k.game_type == "free"
    assert k.analysis_allowed is True
