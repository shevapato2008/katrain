"""对弈·AI/升降级赛道:终局判定在**真** WebKaTrain 上的行为(superpowers/tracks/kiosk-go-play-ai)。

⚠️ 放在 tests/ 根目录是有意的:`tests/web_ui/conftest.py` 会把 `katrain.web.interface` 整个换成
MagicMock,放进那个目录就只是在测替身。第一条用例先证明拿到的是真类。
"""

# 主线程先把 kivymd 的窗口单例暖起来 —— 理由同 tests/test_local_play_setup.py 顶部那段。
import kivymd.app  # noqa: F401

import threading

import pytest

from katrain.core import ai
from katrain.core.constants import AI_DEFAULT, AI_LADDER, PLAYER_AI, PLAYER_HUMAN
from katrain.core.sgf_parser import Move
import katrain.web.interface as interface_module
from katrain.web.interface import WebKaTrain
from katrain.web.models import EndgameConflict, GameEnd


def _web_katrain():
    w = WebKaTrain(force_package_config=True, enable_engine=False)
    # force_package_config=True 时 save_config 会写回仓里的 katrain/config.json(update_config 末尾就调它)
    w.save_config = lambda *args, **kwargs: None
    # 裸 WebKaTrain 的 message_callback 是 None,而 `_do_update_state` 在终局手上无条件发 `game_report`
    # (interface.py `self.message_callback("game_report", …)` 没判空)。这是**夹具要补的,不是生产 bug**:
    # 生产会话一律由 `SessionManager.create_session` 装上回调(评审 r1 m5 实跑复现过 TypeError)。
    w.message_callback = lambda *args, **kwargs: None
    w.start()
    return w


def _seat(w, human_colors):
    """直接改座位,不走 `w("update_player")`:那条路会 update_state,轮到 AI 时起一条后台线程,
    活得比用例长(见 tests/test_guest_free_play.py `_seat_two_humans` 的说明)。"""
    for bw in ("B", "W"):
        if bw in human_colors:
            w.players_info[bw].update(player_type=PLAYER_HUMAN)
        else:
            w.players_info[bw].update(player_type=PLAYER_AI, player_subtype=AI_DEFAULT)


def test_this_module_runs_against_the_real_interface():
    assert isinstance(WebKaTrain, type)
    assert WebKaTrain.__module__ == "katrain.web.interface"


# ---------------------------------------------------------------- N21 认输方


def test_resigning_while_the_ai_is_thinking_is_a_loss_for_the_human():
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))  # 人刚落子,轮到 AI(白)在算
    assert w.game.current_node.next_player == "W"
    w._do_resign()
    assert w.game.current_node.end_state == "W+R"


def test_resigning_on_the_humans_own_turn_is_still_a_loss_for_the_human():
    w = _web_katrain()
    _seat(w, human_colors={"W"})
    w.game.play(Move(coords=(3, 3), player="B"))  # AI(黑)已落子,轮到人(白)
    w._do_resign()
    assert w.game.current_node.end_state == "B+R"


def test_two_humans_face_to_face_the_side_to_move_resigns():
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w.game.play(Move(coords=(3, 3), player="B"))  # 轮到白
    w._do_resign()
    assert w.game.current_node.end_state == "B+R"


def test_an_explicit_loser_wins_over_the_seats():
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    w._do_resign("W")  # 多人局由 /api/resign 按请求者座位显式传
    assert w.game.current_node.end_state == "B+R"


# ---------------------------------------------------------------- r1 终局事实 + 对局提交锁(C3 / S1–S4 / S7 / S11)


class _Instant(ai.AIStrategy):
    """立即回白 15,15 的桩策略 —— 竞态用例只关心提交段,不关心算什么。"""

    def generate_move(self):
        return Move(coords=(15, 15), player="W"), "instant"


def _ai_parked_inside_its_commit(monkeypatch, w, mode):
    """起一条 AI 线程跑真 `generate_ai_move`,让它停在提交段里(`_game_already_ended` 那一次调用之后)。

    返回 `finish()`:放行、join,返回 `(generate_ai_move 的返回值, 线程里收集到的错误)`。
    停点用 `_game_already_ended` 包装而不是 sleep:提交段里复核终局就是调它,所以停住的那一刻 AI 线程**应当**
    正持有对局提交锁 —— 返回之前先用非阻塞 acquire 查这一点(评审 r1 m10:「锁里复核、放锁再落子」这种错实现
    只靠写入者抢不抢得到锁,只会偶发变红)。`game.play` 也包一层:落子那一刻锁不在 AI 线程手里就记一条错误。"""
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, mode, _Instant)
    reached, release = threading.Event(), threading.Event()
    real_check = ai._game_already_ended
    errors, out = [], {}

    def parked_check(game, node=None):
        verdict = real_check(game, node)
        if threading.current_thread().name == "ai-commit" and not reached.is_set():
            reached.set()
            release.wait(2)
        return verdict

    monkeypatch.setattr(ai, "_game_already_ended", parked_check)
    real_play = w.game.play

    def play_checking_the_lock(*args, **kwargs):
        if threading.current_thread().name == "ai-commit" and not w.ai_ladder_commit_lock._is_owned():
            errors.append("AI 落子时没持有对局提交锁")
        return real_play(*args, **kwargs)

    monkeypatch.setattr(w.game, "play", play_checking_the_lock)

    def run():
        try:
            out["result"] = ai.generate_ai_move(w.game, mode, {})
        except Exception as e:  # noqa: BLE001 —— 线程里的异常要带回主线程断言
            errors.append(repr(e))

    thread = threading.Thread(target=run, name="ai-commit", daemon=True)
    thread.start()
    assert reached.wait(2), "AI 线程没走到提交段里的终局复核"
    got = w.ai_ladder_commit_lock.acquire(blocking=False)
    if got:
        w.ai_ladder_commit_lock.release()
    assert not got, "停在终局复核时 AI 线程没持有对局提交锁"

    def finish():
        release.set()
        thread.join(5)
        assert not thread.is_alive()
        return out.get("result"), errors

    return finish


@pytest.mark.parametrize("mode", ["test:instant", AI_LADDER])
@pytest.mark.parametrize("writer", ["resign", "commit", "nav"])
def test_a_terminal_write_or_navigation_racing_the_ai_commit_waits_for_it(monkeypatch, mode, writer):
    """C3 + S2:AI 的「复核 → 落子」与认输 / 终局写入 / 挪游标互斥。普通分支与升降级分支是同一段提交。"""
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))  # 轮到 AI(白)
    cn = w.game.current_node
    finish = _ai_parked_inside_its_commit(monkeypatch, w, mode)

    act = {
        "resign": w._do_resign,
        "commit": lambda: w._commit_end_state("W+R"),
        "nav": lambda: w.game.set_current_node(w.game.root),
    }[writer]
    done = threading.Event()
    threading.Thread(target=lambda: (act(), done.set()), daemon=True).start()
    assert not done.wait(0.1), "写入者没等 AI 的提交段 —— 它会在「复核」与「落子」之间改掉局面"

    result, errors = finish()
    assert done.wait(2)
    assert errors == []
    ai_node = result[1]
    assert ai_node.parent is cn
    if writer == "nav":
        assert w.game.current_node is w.game.root
    else:
        # 认输排在 AI 那一手之后,写在 AI 那一手上 —— 从前是认输先写在 cn 上、AI 随后落子把它「复活」
        assert w.game.terminal.node is ai_node is w.game.current_node
        assert w.game.end_result == "W+R"


def test_a_resign_during_generation_does_not_wait_for_the_engine(monkeypatch):
    """锁只包提交段,不包生成:AI 想几分钟,认输也要立刻生效。"""
    go, thinking = threading.Event(), threading.Event()

    class _Slow(ai.AIStrategy):
        def generate_move(self):
            thinking.set()
            go.wait(5)
            return Move(coords=(15, 15), player="W"), "slow"

    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:slow", _Slow)
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    human_node = w.game.current_node
    out = {}
    worker = threading.Thread(
        target=lambda: out.update(result=ai.generate_ai_move(w.game, "test:slow", {})), daemon=True
    )
    worker.start()
    assert thinking.wait(2)

    resigned = threading.Event()
    threading.Thread(target=lambda: (w._do_resign(), resigned.set()), daemon=True).start()
    assert resigned.wait(1.0), "认输在等 AI 算完 —— 锁包住了整段生成"
    go.set()
    worker.join(5)

    assert out["result"] is None
    assert w.game.current_node is human_node and not human_node.children
    assert w.game.end_result == "W+R"


def test_an_ai_move_computed_for_a_position_that_was_undone_is_dropped(monkeypatch):
    """S2:AI 算的这段时间人悔了一手,算出来的着法属于一个已经不在盘上的局面。"""

    class _UndoneMeanwhile(ai.AIStrategy):
        def generate_move(self):
            self.game.undo(1)
            return Move(coords=(15, 15), player="W"), "stale"

    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:undone", _UndoneMeanwhile)
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    human_node = w.game.current_node

    assert ai.generate_ai_move(w.game, "test:undone", {}) is None
    assert w.game.current_node is w.game.root
    assert w.game.root.children == [human_node]  # 根上没有多出一个白子分支


def test_a_position_that_has_ended_accepts_nothing_more(monkeypatch):
    """终局那一手上:带 guard 的落子 / 停一手、再认输、再写结果、AI 着法,一律被拒;结果不被改写。"""
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:instant", _Instant)
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w._do_play((15, 15), guard=True)
    w._do_resign()  # 两人座位、轮到黑 ⇒ 黑认输
    ended = w.game.terminal
    assert isinstance(ended, GameEnd)
    assert ended.node is w.game.current_node and ended.result == "W+R"

    for attempt in (
        lambda: w._do_play((4, 4), guard=True),
        lambda: w._do_play(None, guard=True),
        w._do_resign,
        lambda: w._commit_end_state("B+1.0"),
    ):
        with pytest.raises(EndgameConflict, match="already_ended"):
            attempt()
    assert ai.generate_ai_move(w.game, "test:instant", {}) is None
    assert ended.node.end_state == "W+R" and not ended.node.children
    assert w.get_state()["terminal_result"] == "W+R"


def test_stepping_back_keeps_the_game_ended_but_an_earlier_position_can_branch_off():
    """S1 + 评审 r1 M2:终局事实挂在对局上,翻手看棋不让它消失(kiosk 靠 `terminal_result` 冻住);
    冻结只到「终局那一手和它之后」—— galaxy / ZenMode 悔棋后在更早的局面另开分支,服务端照旧接受,
    那条分支自己还能再结束一次(单机账只落一次,由 `_recorded` 管,与今天相同)。"""
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w._do_play((15, 15), guard=True)
    w._do_resign()
    ended = w.game.terminal

    w.game.undo(1)
    state = w.get_state()
    assert state["end_result"] is None
    assert state["terminal_result"] == "W+R"

    w._do_play((4, 4), guard=True)  # 在白那一手之前另开分支
    branch = w.game.current_node
    assert branch.parent is ended.node.parent and w.game.terminal is ended
    w._commit_end_state("B+3.5")
    assert w.game.terminal.node is branch and w.game.terminal.result == "B+3.5"
    assert ended.node.end_state == "W+R"


def test_two_passes_end_the_game_even_before_a_score_is_known(monkeypatch):
    """S3:双停第二手落下就记终局事实(结果待补分);之后的停一手与 AI 着法都被挡住。"""
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, "test:instant", _Instant)
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play(None, guard=True)
    w._do_play(None, guard=True)
    terminal = w.game.terminal
    assert terminal is not None and terminal.node is w.game.current_node
    assert terminal.node.end_state is None
    with pytest.raises(EndgameConflict, match="already_ended"):
        w._do_play(None, guard=True)
    assert ai.generate_ai_move(w.game, "test:instant", {}) is None


def test_moves_without_the_guard_neither_record_nor_freeze_a_two_pass_end():
    """评审 r1 m9:研究会话与跨平台网关(`_local_play`、`_on_opponent_move`)不带 guard。
    OGS 双停后进点目阶段还能恢复对局,恢复后的落子必须照常落进本地棋盘 —— 双停不记终局事实、也不冻结。"""
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play(None)
    w._do_play(None)
    assert w.game.terminal is None
    w._do_play((3, 3))
    assert w.game.current_node.move.coords == (3, 3)


def test_a_ranked_game_ended_on_another_device_takes_nothing_locally():
    """S11:远端终局标记与本地写入同一把锁;标记之后本地既不写结果,也不接受带 guard 的落子。"""
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w.ai_ladder_remote_ended = True
    with pytest.raises(EndgameConflict, match="remote_ended"):
        w._commit_end_state("W+R")
    with pytest.raises(EndgameConflict, match="remote_ended"):
        w._do_play((4, 4), guard=True)
    assert w.game.terminal is None and w.game.current_node.move.coords == (3, 3)


def test_a_human_move_on_the_ai_seat_is_refused():
    """S4(一半):人机局轮到 AI 时,人发来的落子 / 停一手从前会被记成 AI 的颜色。"""
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w._do_play((3, 3), guard=True)
    for coords in ((4, 4), None):
        with pytest.raises(EndgameConflict, match="not_your_turn"):
            w._do_play(coords, guard=True)
    assert w.game.current_node.move.coords == (3, 3)


def test_a_vision_stone_after_the_game_ended_is_not_played():
    """S7:视觉非平台分支带 guard + 期望颜色。被拒时照「不轮到」那一支重新布防,返回 0.5 秒节流。"""
    import asyncio
    import logging
    from types import SimpleNamespace

    from katrain.vision.ipc import ConfirmedMove
    from katrain.web.server import _handle_confirmed_move

    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w._do_resign()  # 轮到白 ⇒ 白认输,B+R
    ended_node = w.game.current_node
    session = SimpleNamespace(katrain=w, last_state=w.get_state(), lock=threading.Lock())

    class _Manager:
        def get_session(self, session_id):
            return session

    class _Vision:
        def __init__(self):
            self.expected_pushes = []

        def set_expected_from_stones(self, stones, board_size=19):
            self.expected_pushes.append(stones)

    vision = _Vision()
    app = SimpleNamespace(state=SimpleNamespace(session_manager=_Manager()))
    white_stone = ConfirmedMove(col=15, row=15, color=2)  # 颜色 = 帧上轮到的一方,过得了 R1.3 的轮次检查

    delay = asyncio.run(_handle_confirmed_move(app, vision, "s", white_stone, logging.getLogger("play-ai-test")))

    assert delay == 0.5
    assert w.game.current_node is ended_node and not ended_node.children
    assert vision.expected_pushes


def test_two_threads_settling_the_clock_do_not_count_the_same_seconds_twice(monkeypatch):
    """W11:`update_timer` 读 `last_timer_update` → 记 dt → 写回,不互斥时两个并发结算读到同一个基准、把同一段 dt
    记两遍 —— 超时由服务端时钟核实以后(Task 6),这会直接变成「提前判负」。假 `time` 让第一个结算者停在读时钟那一刻,
    第二个结算者 0.2 秒内不许读到时钟(没有锁就会立刻读到)。"""
    # 保留收集时的真模块；全量收集稍后会由 web_ui/conftest 替换 sys.modules。
    w = _web_katrain()
    real_time = interface_module.time
    first_reading, release, second_read = threading.Event(), threading.Event(), threading.Event()

    class _Clock:
        def time(self):
            name = threading.current_thread().name
            if name == "settle-a" and not first_reading.is_set():
                first_reading.set()
                release.wait(2)
            elif name == "settle-b":
                second_read.set()
            return real_time.time()

        def monotonic(self):
            return real_time.monotonic()

        def sleep(self, seconds):
            real_time.sleep(seconds)

    monkeypatch.setattr(interface_module, "time", _Clock())
    first = threading.Thread(target=w.update_timer, name="settle-a", daemon=True)
    first.start()
    assert first_reading.wait(2)
    second = threading.Thread(target=w.update_timer, name="settle-b", daemon=True)
    second.start()
    assert not second_read.wait(0.2), "第二个结算没等第一个 —— 两边读到同一个 last_timer_update"
    release.set()
    first.join(2)
    second.join(2)
    assert second_read.is_set()


@pytest.mark.parametrize("notice", ["too_fast", "illegal_move", "insert_navigation"])
def test_play_notices_are_emitted_after_releasing_the_commit_lock(monkeypatch, notice):
    """UI callbacks can broadcast; they must never run inside the commit lock."""
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    if notice == "too_fast":
        w.timer_paused = False
        w.active_game_timer.update(main_time=0, minimal_use=100)
    else:
        w._do_play((3, 3), guard=True)
    before = w.game.current_node
    emitted, lock_available = [], []

    def capture(message, *args, **kwargs):
        emitted.append(message)

        def probe():
            acquired = w.ai_ladder_commit_lock.acquire(blocking=False)
            lock_available.append(acquired)
            if acquired:
                w.ai_ladder_commit_lock.release()

        worker = threading.Thread(target=probe)
        worker.start()
        worker.join(2)
        assert not worker.is_alive()

    monkeypatch.setattr(w, "log", capture)
    if notice == "insert_navigation":
        w.game.insert_mode = True
        w.game.set_current_node(w.game.root)
    else:
        w._do_play((3, 3), guard=True)

    assert w.game.current_node is before
    assert len(emitted) == 1
    assert lock_available == [True], "状态/错误回调正在持有提交锁时发出"
    if notice == "illegal_move":
        assert "Illegal Move at (3, 3)" in emitted[0]


# ---------------------------------------------------------------- N23 数子门槛按路数


@pytest.mark.parametrize("size,expected", [(19, 100), (13, 47), (9, 22)])
def test_count_threshold_scales_with_board_size(size, expected):
    """配置里的 100 是 19 路的数;小棋盘按交叉点数等比缩小,和 AI 认输门槛(core/ai.py should_ai_resign)同一种缩放。"""
    w = _web_katrain()
    w._do_new_game(size=size)
    assert w.count_min_moves() == expected
    assert w.get_state()["count_min_moves"] == expected


class TestIntegration:
    """Integration tests using WebKaTrain."""

    def test_count_button_disabled_check(self):
        """Verify count button should be disabled with < 100 moves."""
        wkt = _web_katrain()
        _seat(wkt, human_colors={"B", "W"})

        state = wkt.get_state()
        history_length = len(state.get("history", []))

        # At start, should be 1 (root node)
        assert history_length < 100, "New game should have < 100 moves"

        # Make a few moves
        wkt("play", (3, 3))
        wkt("play", (15, 15))
        wkt("play", (3, 15))

        state = wkt.get_state()
        history_length = len(state.get("history", []))
        assert history_length < 100, "Few moves should still be < 100"

    def test_game_state_has_history(self):
        """Verify game state includes history for move counting."""
        wkt = _web_katrain()
        _seat(wkt, human_colors={"B", "W"})

        state = wkt.get_state()
        assert "history" in state
        assert isinstance(state["history"], list)


# ---------------------------------------------------------------- A12 数子前补分


class _InstantEngine:
    """一请求就同步回一份分析的假引擎 —— 只实现 GameNode.analyze 用到的那一个方法。"""

    def __init__(self, score):
        self.score = score
        self.requests = 0

    def request_analysis(self, node, callback, **kwargs):
        self.requests += 1
        callback({"rootInfo": {"scoreLead": self.score, "winrate": 0.6, "visits": 5}, "moveInfos": []}, False)


def _free_game_with_moves(engine):
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w.game.play(Move(coords=(3, 3), player="B"))
    w.game.play(Move(coords=(15, 15), player="W"))
    w.engine = engine  # 落子之后再换:game.play 用的是开局时的 NullEngine,不会先把分补上
    return w


def test_missing_score_is_filled_by_one_analysis():
    engine = _InstantEngine(score=3.5)
    w = _free_game_with_moves(engine)
    assert w.game.current_node.score is None
    assert w.ensure_current_score(timeout_s=1) == 3.5
    assert engine.requests == 1


def test_an_existing_score_is_not_requested_again():
    engine = _InstantEngine(score=-2.0)
    w = _free_game_with_moves(engine)
    w.ensure_current_score(timeout_s=1)
    w.ensure_current_score(timeout_s=1)
    assert engine.requests == 1


def test_ranked_games_are_never_analysed_for_a_score():
    """升降级终局怎么判目等 Fan 拍板(PRD §4 A12-R);在那之前一次都不许替它算。"""
    engine = _InstantEngine(score=3.5)
    w = _free_game_with_moves(engine)
    w.game_type = "ai_ladder_ranked"
    assert w.ensure_current_score(timeout_s=1) is None
    assert engine.requests == 0


def test_no_engine_returns_at_once_instead_of_waiting_out_the_timeout():
    import time

    w = _web_katrain()  # enable_engine=False ⇒ NullEngine,请求永远不会回来
    started = time.monotonic()
    assert w.ensure_current_score(timeout_s=5) is None
    assert time.monotonic() - started < 1


def test_an_explicit_node_is_scored_even_when_the_cursor_has_moved():
    """C2 / C4:补的是「开始数子 / 双停」的那一手,不是游标此刻那一手。"""
    engine = _InstantEngine(score=1.5)
    w = _free_game_with_moves(engine)
    counted = w.game.current_node
    w.game.undo(1)
    assert w.ensure_current_score(timeout_s=1, node=counted) == 1.5
    assert counted.score == 1.5 and w.game.current_node.score is None


# ---------------------------------------------------------------- C2 数子等分析的这几秒里局面变了(真 create_app)


@pytest.fixture
def web_client(isolated_session_factory):
    """真 `create_app` + 真 SessionManager / WebKaTrain 的 TestClient。
    会话收尾照 tests/test_guest_free_play.py:进程级会话不跟着 TestClient 走,不收掉会污染后面的文件。"""
    from fastapi.testclient import TestClient

    from katrain.web.server import create_app

    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory  # 必须在 TestClient 之前:lifespan 用它重建全部 repo
    with TestClient(app) as c:
        yield c
        for s in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager.remove_session(s.session_id)


def _two_human_guest_game(client, moves):
    """游客会话、两边坐人(不起 AI 线程),按 `/api/move` 下完 `moves`(None = 停一手)。返回 `(session_id, WebKaTrain)`。"""
    sid = client.post("/api/session", json={}).json()["session_id"]
    for bw, name in (("B", "游客"), ("W", "游客2")):
        r = client.post(
            "/api/player",
            json={"session_id": sid, "bw": bw, "player_type": "player:human", "player_subtype": "human", "name": name},
        )
        assert r.status_code == 200, r.text
    for coords in moves:
        body = {"session_id": sid, "pass_move": True} if coords is None else {"session_id": sid, "coords": list(coords)}
        r = client.post("/api/move", json=body)
        assert r.status_code == 200, r.text
    w = client.app.state.session_manager.get_session(sid).katrain
    assert isinstance(w, WebKaTrain)
    return sid, w


def test_count_that_waited_for_analysis_does_not_overwrite_a_resignation(web_client):
    """C2:补分的阻塞里有人认输了。数子不许把认输改写成目数结果,回 409「这一局已经结束了」。"""
    sid, w = _two_human_guest_game(web_client, [(3, 3), (15, 15)])
    counted = w.game.current_node
    w.count_min_moves = lambda: 0
    seen = {}

    def score_while_someone_resigns(timeout_s=None, node=None):
        assert node is counted  # 补的是开始数子那一手
        seen["resign"] = web_client.post("/api/resign", json={"session_id": sid})
        node.set_analysis({"rootInfo": {"scoreLead": 2.5, "winrate": 0.6, "visits": 5}, "moveInfos": []})
        return 2.5

    w.ensure_current_score = score_while_someone_resigns
    r = web_client.post("/api/count/request", json={"session_id": sid})

    assert seen["resign"].status_code == 200, seen["resign"].text
    assert r.status_code == 409, r.text
    assert "already over" in r.json()["detail"]
    assert w.game.terminal.result == "W+R"  # 两人座位、轮到黑 ⇒ 黑认输
    assert w.game.end_result == "W+R"


def test_count_does_not_finish_a_position_that_changed_while_it_waited(web_client):
    """C2:补分的阻塞里人悔了一手。数子不许把游标上那一手记成结束,回 409「局面变了」。"""
    sid, w = _two_human_guest_game(web_client, [(3, 3), (15, 15)])
    counted = w.game.current_node
    w.count_min_moves = lambda: 0
    seen = {}

    def score_while_someone_undoes(timeout_s=None, node=None):
        assert node is counted
        seen["undo"] = web_client.post("/api/undo", json={"session_id": sid, "n_times": 1})
        node.set_analysis({"rootInfo": {"scoreLead": -1.5, "winrate": 0.4, "visits": 5}, "moveInfos": []})
        return -1.5

    w.ensure_current_score = score_while_someone_undoes
    r = web_client.post("/api/count/request", json={"session_id": sid})

    assert seen["undo"].status_code == 200, seen["undo"].text
    assert r.status_code == 409, r.text
    assert "Position changed" in r.json()["detail"]
    assert w.game.terminal is None
    assert w.game.current_node is counted.parent
    assert counted.end_state is None and counted.parent.end_state is None


# ---------------------------------------------------------------- N22 终局收尾


import asyncio  # noqa: E402
import time  # noqa: E402
import types  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402


@pytest.fixture(scope="module")
def server_module():
    import katrain.web.server as server

    # `_FINISH_ENDED_GAME_FN` 是 create_app 里的闭包,建一次 app 才会挂到模块上(同 tests/test_local_play_recording.py)
    server.create_app(enable_engine=False)
    return server


def _ended_session(*, how="two_pass", game_type="free", user_id=42, mode="play"):
    """真 WebKaTrain + 真 WebSession(r1:MagicMock 版证不出「补分写在哪一手」):两人座位下 B、W 各一手,
    再按 `how` 结束 —— 双停(终局事实已记、结果待补分)或认输(两人座位、轮到黑 ⇒ 黑认输,`W+R`)。
    返回 `(session, end)`;`end` 就是这一局的终局事实,收尾函数只认它,不看游标。
    `game_type` 同时写在会话和运行时上:`"ranked"` 让 `analysis_allowed` 为假,又不走升降级账本那一支。"""
    from katrain.web.session import WebSession

    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w._do_play((3, 3), guard=True)
    w._do_play((15, 15), guard=True)
    if how == "two_pass":
        w._do_play(None, guard=True)
        w._do_play(None, guard=True)
    else:
        w._do_resign()
    w.game_type = game_type
    session = WebSession(session_id=f"s-{how}-{game_type}-{mode}", katrain=w, user_id=user_id, mode=mode)
    session.game_type = game_type
    return session, w.game.terminal


def _recording_app():
    app = MagicMock()
    app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
    return app


_USER = types.SimpleNamespace(id=42, username="小明")


def test_create_app_installs_the_off_request_hook(server_module):
    app = server_module.create_app(enable_engine=False)
    assert app.state.session_manager.on_game_ended is not None


class _Reply(ai.AIStrategy):
    """AI 线程的桩策略:回 `REPLY`(None = 停一手)。走真 `generate_ai_move` —— 双停终局事实是在它的提交段里记的,
    直接调 `game.play` 的替身会绕过那一步(r1)。"""

    REPLY = None

    def generate_move(self):
        return Move(coords=type(self).REPLY, player=self.cn.next_player), "reply"


def _ai_thread_game(monkeypatch, human_first, ai_reply, step_back_on_broadcast=False):
    """真 WebKaTrain:人(黑)先下 `human_first`,AI 线程(`_do_ai_move_and_broadcast`)回 `ai_reply`。
    `ai:default` 换成桩策略;`update_state` 置空 —— 只证回调,不起下一条 AI 线程。
    `step_back_on_broadcast=True`:广播那一刻人点了「上一手」(`update_state` 里悔一手)。"""
    w = _web_katrain()
    _seat(w, human_colors={"B"})
    w._do_play(human_first, guard=True)
    calls = []
    w.game_ended_callback = lambda end: calls.append(end)
    if step_back_on_broadcast:
        w.update_state = lambda **_kwargs: w.game.undo(1)
    else:
        w.update_state = lambda **_kwargs: None
    monkeypatch.setattr(_Reply, "REPLY", ai_reply)
    monkeypatch.setitem(ai.STRATEGY_REGISTRY, AI_DEFAULT, _Reply)
    w._do_ai_move_and_broadcast(w.game.current_node)
    return w, calls


def test_the_ai_thread_reports_a_game_it_ended(monkeypatch):
    """人先停一手、AI 跟停 —— 盒上最常见的收官。这条回调就是 N22 收尾在 AI 这条路上的唯一入口。"""
    w, calls = _ai_thread_game(monkeypatch, human_first=None, ai_reply=None)
    assert len(calls) == 1
    assert calls[0] is w.game.terminal and calls[0].node.is_pass


def test_the_ai_thread_captures_the_end_before_anyone_can_step_back(monkeypatch):
    """C4:广播之后人立刻点「上一手」,回调拿到的仍是那一局、那一手的终局事实。
    错误实现(在 `update_state()` 之后按游标取 `end_result`)在这里一次都不叫。"""
    w, calls = _ai_thread_game(monkeypatch, human_first=None, ai_reply=None, step_back_on_broadcast=True)
    assert len(calls) == 1
    assert calls[0].node.is_pass and calls[0].node.parent.is_pass
    assert w.game.current_node is calls[0].node.parent  # 游标确实被挪走了


def test_an_ordinary_ai_move_reports_nothing(monkeypatch):
    """正对照:没结束就不叫 —— 否则上一条的「叫了一次」可能只是每手都叫。"""
    _, calls = _ai_thread_game(monkeypatch, human_first=(3, 3), ai_reply=(15, 15))
    assert calls == []


async def test_two_pass_end_is_scored_before_it_is_recorded(server_module):
    session, end = _ended_session()
    assert end is not None and end.node.end_state is None  # 双停:终局事实已记,结果待补分
    asked = []
    session.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked.append(node) or 2.5
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end)

    assert asked == [end.node]  # 补的是终局那一手
    data = app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]
    assert data["result"] == "B+2.5"
    assert end.node.end_state == "B+2.5"
    assert session.katrain.game.terminal.result == "B+2.5"


async def test_games_that_forbid_analysis_are_recorded_without_a_score(server_module):
    """升降级局走的就是这一支:不补分,照旧按「终局」落账(无结论)—— 怎么判目等 Fan 拍板。"""
    session, end = _ended_session(game_type="ranked")
    asked = []
    session.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked.append(node)
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end)

    assert asked == []
    data = app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]
    assert data["result"] == end.result
    assert end.node.end_state is None


async def test_a_resigned_game_is_recorded_as_is(server_module):
    session, end = _ended_session(how="resign")
    asked = []
    session.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked.append(node)
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end)

    assert asked == []
    assert app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]["result"] == "W+R"


async def test_request_and_ai_thread_finishing_together_score_and_record_once(server_module):
    session, end = _ended_session()
    calls = []
    session.katrain.ensure_current_score = lambda timeout_s=None, node=None: calls.append(node) or 2.5
    app = _recording_app()

    await asyncio.gather(
        server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end),
        server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end),
    )

    assert len(calls) == 1
    create = app.state.repository_dispatcher.user_games_create
    assert create.await_count == 1
    assert create.await_args.kwargs["data"]["result"] == "B+2.5"  # 后到的那次收尾认的是补过分的终局事实


@pytest.mark.parametrize("action,score", [("undo", 2.5), ("undo", None), ("new_game", 2.5)])
async def test_stepping_back_or_starting_over_while_the_end_is_scored(server_module, action, score):
    """C4:收尾按捕获的终局落账,不看游标。补分的那几秒里人点了「上一手」或开了新局:
    落账的是**那一局那一手**(新局就不落),游标留在人挪到的地方,结果不写到游标那一手上。"""
    session, end = _ended_session()
    w = session.katrain

    def scoring(timeout_s=None, node=None):
        if action == "undo":
            with session.lock:
                w("undo", 1)
        else:
            w._do_new_game()
        return score if node is end.node else 99.0

    w.ensure_current_score = scoring
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(session, app, _USER, end)

    create = app.state.repository_dispatcher.user_games_create
    if action == "new_game":
        create.assert_not_awaited()  # 旧局的 SGF 已经不在会话上,落了就是把新局的空谱记成那一局
        return
    assert w.game.current_node is end.node.parent
    assert create.await_count == 1
    assert create.await_args.kwargs["data"]["result"] == ("B+2.5" if score is not None else end.result)
    assert end.node.parent.end_state is None


async def test_multiplayer_research_and_guest_games_are_not_recorded_here(server_module):
    lobby, lobby_end = _ended_session()
    lobby.player_b_id, lobby.player_w_id = 1, 2
    research, research_end = _ended_session(mode="research")
    guest, guest_end = _ended_session(user_id=None)
    asked = {"lobby": [], "research": []}
    lobby.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked["lobby"].append(node)
    research.katrain.ensure_current_score = lambda timeout_s=None, node=None: asked["research"].append(node)
    guest.katrain.ensure_current_score = lambda timeout_s=None, node=None: 1.5
    app = _recording_app()

    await server_module._FINISH_ENDED_GAME_FN(lobby, app, _USER, lobby_end)
    await server_module._FINISH_ENDED_GAME_FN(research, app, _USER, research_end)
    await server_module._FINISH_ENDED_GAME_FN(guest, app, None, guest_end)

    assert asked == {"lobby": [], "research": []}
    assert guest_end.node.end_state == "B+1.5"  # 游客的局照样分出胜负,只是不落账
    app.state.repository_dispatcher.user_games_create.assert_not_awaited()


def test_a_resign_on_a_game_already_being_finished_returns_at_once(web_client):
    """评审 r1 M1:撞上已结束的认输是空操作 —— 不许排进正在补分的那次收尾后面(最多 15 秒),也不许再补一次分。
    真实触发路径:galaxy 离页即认输、kiosk 引擎出错框的「认输」、连点。

    双停第二手的 `/api/move` 在补分里被挡住;挡住期间另起线程发 `/api/resign`,最多等 1 秒。
    错误实现(收尾看的是「这局结束过」而不是「这次请求写出了终局」)下认输排在 `end_game_lock` 后面:
    1 秒到了照样放行补分,认输随后进收尾、**再补一次分**(第二次调用立即返回)—— 不会挂死,只会红。"""
    sid, w = _two_human_guest_game(web_client, [None])  # 黑先停一手
    calls = []
    resign = {}

    def blocking_score(timeout_s=None, node=None):
        calls.append(node)
        if len(calls) == 1:
            started = time.monotonic()

            def send():
                resign["response"] = web_client.post("/api/resign", json={"session_id": sid})
                resign["elapsed"] = time.monotonic() - started

            sender = threading.Thread(target=send, daemon=True)
            sender.start()
            sender.join(1.0)
            resign["thread"] = sender
        return None  # 补不出分:收尾照「终局」处理

    w.ensure_current_score = blocking_score
    r = web_client.post("/api/move", json={"session_id": sid, "pass_move": True})  # 白跟停 ⇒ 双停

    resign["thread"].join(5)
    assert r.status_code == 200, r.text
    assert resign["response"].status_code == 200, resign["response"].text
    assert resign["elapsed"] < 1.0, "认输排在补分后面等了"
    assert len(calls) == 1
    assert w.game.terminal.node.end_state is None  # 认输没有改写双停终局


# ---------------------------------------------------------------- A18 计时判别位


def test_timer_is_configured_only_after_a_setup_wrote_it():
    """星阵人机 / 大厅房间局没人设过时限,却继承 config.json 默认的 20 分 + 30 秒×5 且不暂停;
    前端必须能分出「这局的时限是开局设置定的」,否则星阵局会凭空倒计时、20 分钟后自己判负。"""
    w = _web_katrain()
    assert w.get_state()["timer"]["configured"] is False
    w.update_config("timer/main_time", 5)
    assert w.get_state()["timer"]["configured"] is True


# ---------------------------------------------------------------- r1 C1 超时绑定轮次 + 服务端时钟


class _FakeClock:
    """`katrain.web.interface.time` 的替身:只有 `time()` 可以被拨快;`monotonic` / `sleep` 照真的走。"""

    def __init__(self):
        import time as real_time

        self._real = real_time
        self.now = real_time.time()

    def time(self):
        return self.now

    def monotonic(self):
        return self._real.monotonic()

    def sleep(self, seconds):
        self._real.sleep(seconds)

    def advance(self, seconds):
        self.now += seconds


def _timed_game(monkeypatch, *, main_time=0, byo_length=30, byo_periods=3):
    """两人座位、开局设置配过时限(`timer_configured`)、不暂停的真 WebKaTrain,时钟由测试拨。默认「仅读秒 30 秒 × 3」。"""
    clock = _FakeClock()
    monkeypatch.setattr(interface_module, "time", clock)
    w = _web_katrain()
    _seat(w, human_colors={"B", "W"})
    w.update_config("timer/main_time", main_time)
    w.update_config("timer/byo_length", byo_length)
    w.update_config("timer/byo_periods", byo_periods)
    w.update_config("timer/paused", False)
    w.last_timer_update = clock.now
    return w, clock


def test_a_timeout_for_a_turn_the_server_has_moved_past_is_refused(monkeypatch):
    """C1:前端那一帧还轮到白,服务端已经落了白(人在最后一刻落子 / 在途)。黑随后也把钟用完了 ——
    只核时钟不核轮次的实现会把这一帧的「白超时」写成结果。"""
    w, clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)
    stale = w.get_state()
    assert stale["player_to_move"] == "W"
    w._do_play((15, 15), guard=True)
    clock.advance(91)

    with pytest.raises(EndgameConflict, match="stale_turn"):
        w._do_timeout(stale["game_id"], stale["current_node_id"], "W")
    assert w.game.end_result is None and w.game.terminal is None

    fresh = w.get_state()
    w._do_timeout(fresh["game_id"], fresh["current_node_id"], "B")
    assert w.game.end_result == "W+T"


def test_a_timeout_for_an_older_node_of_the_same_colour_is_refused(monkeypatch):
    """同色不同手:漏收了两手广播,两帧都轮到黑。只核 `color` 不核节点的实现会放行。"""
    w, clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)
    w._do_play((15, 15), guard=True)
    stale = w.get_state()
    w._do_play((4, 4), guard=True)
    w._do_play((16, 16), guard=True)
    clock.advance(91)

    with pytest.raises(EndgameConflict, match="stale_turn"):
        w._do_timeout(stale["game_id"], stale["current_node_id"], "B")
    assert w.game.terminal is None


def test_the_server_clock_must_have_run_out(monkeypatch):
    """轮次与方都对,但服务端时钟还没耗尽:拒绝;耗尽之后同一个请求被接受。"""
    w, clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)  # 轮到白
    clock.advance(89)
    s = w.get_state()

    with pytest.raises(EndgameConflict, match="clock_not_expired"):
        w._do_timeout(s["game_id"], s["current_node_id"], "W")
    assert w.game.terminal is None

    clock.advance(2)
    w._do_timeout(s["game_id"], s["current_node_id"], "W")
    assert w.game.end_result == "B+T"


def test_main_time_only_game_expires_exactly_at_main_time_end(monkeypatch):
    """只有主时间(读秒 0 / 0):主时间用完那一刻就算耗尽,与前端 `readGoClock` 同口径。
    复用 `update_timer` 的 `max(1, …)` 会要 61 秒以上 —— 前端停在「超时」而服务端永远不判。"""
    w, clock = _timed_game(monkeypatch, main_time=1, byo_length=0, byo_periods=0)
    w._do_play((3, 3), guard=True)
    clock.advance(60)
    s = w.get_state()

    w._do_timeout(s["game_id"], s["current_node_id"], "W")
    assert w.game.end_result == "B+T"


def test_a_bound_timeout_that_waited_for_the_ai_commit_is_stale(monkeypatch):
    """AI 停在提交段里;另一线程拿 AI 提交之前那一帧做带绑定的超时 —— 它必须等 AI 提交完,然后发现轮次过期。
    轮次核对放在对局提交锁外的实现会读到旧节点、写到 AI 那一手上。"""
    w, clock = _timed_game(monkeypatch)
    _seat(w, human_colors={"B"})  # 白是 AI
    w._do_play((3, 3), guard=True)
    clock.advance(91)  # 白(AI)的钟也耗尽了
    stale = w.get_state()
    finish = _ai_parked_inside_its_commit(monkeypatch, w, "test:instant")

    outcome = {}

    def bound_timeout():
        try:
            w._do_timeout(stale["game_id"], stale["current_node_id"], "W")
            outcome["error"] = None
        except Exception as e:
            outcome["error"] = getattr(e, "reason", str(e))

    worker = threading.Thread(target=bound_timeout, daemon=True)
    worker.start()
    worker.join(0.1)
    was_blocked = worker.is_alive()
    result, errors = finish()
    assert was_blocked, "带绑定的超时没等 AI 的提交段"
    worker.join(2)
    assert errors == [] and result is not None
    assert outcome == {"error": "stale_turn"}
    assert w.game.end_result is None and w.game.terminal is None


def test_an_unbound_timeout_keeps_its_old_meaning(monkeypatch):
    """galaxy 的旧调用不带绑定:语义照旧(最后落子的一方胜、不核时钟),只多了「已经结束过就拒」。"""
    w, _clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)
    w._do_timeout()
    assert w.game.end_result == "B+T"
    with pytest.raises(EndgameConflict, match="already_ended"):
        w._do_timeout()


@pytest.mark.parametrize("condition", ["paused", "unconfigured", "untimed", "analyze", "nonleaf", "missing_game"])
def test_unverifiable_clocks_never_count_as_exhausted(monkeypatch, condition):
    w, clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)
    clock.advance(91)
    w.update_timer()
    if condition == "paused":
        w.timer_paused = True
    elif condition == "unconfigured":
        w.timer_configured = False
    elif condition == "untimed":
        w.update_config("timer/main_time", 0)
        w.update_config("timer/byo_length", 0)
    elif condition == "analyze":
        w.play_analyze_mode = "analyze"
    elif condition == "nonleaf":
        w._do_play((15, 15), guard=True)
        w.game.undo(1)
    else:
        w.game = None
    assert w.clock_exhausted() is False


@pytest.mark.parametrize("field", ["game", "color", "nonleaf"])
def test_bound_timeout_rejects_wrong_identity_and_history(monkeypatch, field):
    w, clock = _timed_game(monkeypatch)
    w._do_play((3, 3), guard=True)
    clock.advance(91)
    state = w.get_state()
    if field == "nonleaf":
        w._do_play((15, 15), guard=True)
        w.game.undo(1)
    with pytest.raises(EndgameConflict, match="stale_turn"):
        w._do_timeout(
            "other" if field == "game" else state["game_id"], state["current_node_id"], "B" if field == "color" else "W"
        )
    assert w.game.terminal is None
