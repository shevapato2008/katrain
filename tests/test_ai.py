import os

import pytest

from katrain.core.ai import ai_rank_estimation, generate_ai_move
from katrain.core.base_katrain import KaTrainBase
from katrain.core.constants import (
    AI_STRATEGIES,
    AI_STRATEGIES_RECOMMENDED_ORDER,
    AI_HUMAN,
    AI_PRO,
    AI_LADDER,
    OUTPUT_INFO,
)
from katrain.core.engine import KataGoEngine
from katrain.core.game import Game


class TestAI:
    def test_order(self):
        assert set(AI_STRATEGIES_RECOMMENDED_ORDER) == set(AI_STRATEGIES)

    @pytest.mark.skipif(os.environ.get("CI", "").lower() == "true", reason="GH actions has no OpenCL")
    def test_ai_strategies(self):
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        engine = KataGoEngine(katrain, katrain.config("engine"))

        game = Game(katrain, engine)
        n_rounds = 3
        for _ in range(n_rounds):
            for strategy in AI_STRATEGIES:
                if strategy in [AI_HUMAN, AI_PRO, AI_LADDER]:
                    continue
                settings = katrain.config(f"ai/{strategy}")
                move, played_node = generate_ai_move(game, strategy, settings)
                katrain.log(f"Testing strategy {strategy} -> {move}", OUTPUT_INFO)
                assert move.coords is not None
                assert played_node == game.current_node

        assert game.current_node.depth == (len(AI_STRATEGIES) - 3) * n_rounds

        for strategy in AI_STRATEGIES:
            if strategy in [AI_HUMAN, AI_PRO, AI_LADDER]:
                continue
            game = Game(katrain, engine)
            settings = katrain.config(f"ai/{strategy}")
            move, played_node = generate_ai_move(game, strategy, settings)
            katrain.log(f"Testing strategy on first move {strategy} -> {move}", OUTPUT_INFO)
            assert game.current_node.depth == 1

    def test_ai_rank_estimation(self):
        katrain = KaTrainBase(force_package_config=True, debug_level=0)
        for strategy in AI_STRATEGIES:
            if strategy in [AI_HUMAN, AI_PRO, AI_LADDER]:
                continue
            settings = katrain.config(f"ai/{strategy}")
            rank = ai_rank_estimation(strategy, settings)
            assert -20 <= rank <= 9

    def test_ladder_rank_estimation_is_json_safe(self):
        # The ladder's strength is per-rung (injected at game start), not derivable from strategy
        # settings, and AI_STRENGTH[AI_LADDER] is nan. ai_rank_estimation must NOT return that nan:
        # it flows verbatim into players_info.calculated_rank in the /api/player state response, and
        # FastAPI's JSONResponse cannot serialize nan (ValueError -> HTTP 500, blocking game start).
        # None is the JSON-safe contract (the rung's Golaxy level is surfaced via the player name).
        import json

        rank = ai_rank_estimation(AI_LADDER, {})
        assert rank is None
        json.dumps({"calculated_rank": rank})  # would raise ValueError on nan

    def test_ladder_thought_label_is_rank_name_only(self):
        # User-visible (SGF comment + ZenMode log): the branded 段位 label ONLY — star阵-free AND free
        # of the rung index / visits / debug prefix (codex round 2).
        from katrain.core.ai import _ladder_thought_label
        from katrain.core.ladder import get_rung

        label = _ladder_thought_label(get_rung(39))  # rung 39 == 超越职业 (was 星阵3星)
        assert "超越职业" in label
        for banned in ("星阵", "对标星阵", "rung", "visits", "39", "[LadderStrategy]"):
            assert banned not in label
