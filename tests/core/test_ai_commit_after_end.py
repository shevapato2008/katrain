"""N21:对局一旦有了终局结果,后台还在算的 AI 着法不许再落到盘上。

人刚落子、AI 在算时按认输(或超时),结果写在 AI 开算时的那个节点上;从前 AI 算完照常 `game.play(move)`,
新节点没有终局标记,盘面回到对局中。

这里用替身对局,**只证宽窗口**(生成期间写上的结果在提交前被看见;替身没有 `ended_at`,走 `end_state` 回退)。
窄窗口 —— 复核与落子之间的交错、复核是否在对局提交锁里 —— 在 tests/test_play_ai_endgame.py 用真 WebKaTrain 证。
"""

from katrain.core import ai
from katrain.core.constants import AI_LADDER
from katrain.core.sgf_parser import Move


class _Node:
    def __init__(self):
        self.player, self.next_player = "B", "W"
        self.end_state = None
        self.depth = 0


class _Katrain:
    ai_ladder_remote_ended = False
    ai_ladder_commit_lock = None

    def log(self, *a, **k):
        pass

    def config(self, *a, **k):
        return {}


class _Game:
    def __init__(self):
        self.board_size = (19, 19)
        self.current_node = _Node()
        self.katrain = _Katrain()
        self.played = []

    def play(self, move):
        self.played.append(move)
        self.current_node = _Node()
        return self.current_node


def _ends_mid_generation(end_state):
    class _EndsMidGeneration(ai.AIStrategy):
        def generate_move(self):
            self.game.current_node.end_state = end_state  # 人在这段时间里认输/超时了
            return Move(coords=(3, 3), player="W"), "thought"

    return _EndsMidGeneration


def test_a_move_finished_after_the_game_ended_is_not_played(monkeypatch):
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:ends-mid-generation", _ends_mid_generation("W+R"))
    game = _Game()
    assert ai.generate_ai_move(game, "test:ends-mid-generation", {}) is None
    assert game.played == []
    assert game.current_node.end_state == "W+R"


def test_the_ladder_commit_path_refuses_too(monkeypatch):
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, AI_LADDER, _ends_mid_generation("B+R"))
    game = _Game()
    assert ai.generate_ai_move(game, AI_LADDER, {}) is None
    assert game.played == []


def test_an_ordinary_move_is_still_played(monkeypatch):
    """正对照:没有终局时照常落子 —— 否则上面两条的 None 可能只是这条路本来就不通。"""

    class _Plain(ai.AIStrategy):
        def generate_move(self):
            return Move(coords=(3, 3), player="W"), "thought"

    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:plain", _Plain)
    game = _Game()
    assert ai.generate_ai_move(game, "test:plain", {}) is not None
    assert len(game.played) == 1
