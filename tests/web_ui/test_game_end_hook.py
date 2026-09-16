"""N22:对局在**请求之外**结束(AI 后台线程下出双停第二手 / AI 认输)时,SessionManager 要把收尾交给事件循环。

从前 AI 线程结束对局时 `_on_state` 只置 `game_ended`,不落账:由 AI 收尾的局不进对局记录,升降级局不进结算、心跳停掉。

触发点是 `WebKaTrain.game_ended_callback`(只有 AI 线程调),**不是** `_on_state` 里「end_result 由无变有」——
后者在「对局会话里载入一份 SGF 再翻到双停终点」时同样成立(galaxy `ZenModeApp` 就用 play 会话 `loadSGF`),
会把一份不是在这里下的棋谱补分、再记成这个用户的对局。「每局只收尾一次」由 server 的 `_finish_ended_game` 保证。
"""

import asyncio
from unittest.mock import MagicMock

from katrain.web.models import GameEnd
from katrain.web.session import SessionManager, WebSession

#: 钩子只转发,不看里面装的是什么;真对象的收尾在 tests/test_play_ai_endgame.py 证。
END = GameEnd(None, None, "B+R")


async def _manager_with_hook(session):
    manager = SessionManager(enable_engine=False)
    manager._sessions[session.session_id] = session
    manager.attach_loop(asyncio.get_running_loop())
    seen = []

    async def hook(s, end):
        seen.append((s.session_id, end))

    manager.on_game_ended = hook
    return manager, seen


async def test_the_ai_thread_ending_a_game_runs_the_hook():
    session = WebSession(session_id="s-ai-pass", katrain=MagicMock())
    manager, seen = await _manager_with_hook(session)
    # AI 线程就是从事件循环以外的线程回调的
    await asyncio.to_thread(manager._on_game_ended, session.session_id, END)
    await asyncio.sleep(0.05)
    assert seen == [("s-ai-pass", END)]  # 捕获的终局事实原样交给收尾(C4),不在事件循环里按游标重推
    assert session.game_ended is True


async def test_research_sessions_never_run_the_hook():
    """研究模式载入一份带结果的棋谱不是「下完了一局」,不许被当成对局记下来。"""
    session = WebSession(session_id="s-research", katrain=MagicMock(), mode="research")
    manager, seen = await _manager_with_hook(session)
    await asyncio.to_thread(manager._on_game_ended, session.session_id, END)
    await asyncio.sleep(0.05)
    assert seen == []


async def test_a_broadcast_that_merely_shows_an_ended_game_does_not_run_the_hook():
    """翻到载入棋谱的双停终点同样会推一帧带 end_result 的状态 —— 那不是在这里下完的一局。"""
    session = WebSession(session_id="s-nav", katrain=MagicMock())
    manager, seen = await _manager_with_hook(session)
    await asyncio.to_thread(manager._on_state, session.session_id, {"end_result": "B+R"})
    await asyncio.sleep(0.05)
    assert seen == []
    assert session.game_ended is True  # `_on_state` 原有语义不变(心跳靠它停)


def test_create_session_wires_the_ai_thread_callback(monkeypatch):
    """接线只有一行;漏了它,上面几条全绿而 N22 在真机上整条是死的。"""
    import katrain.web.session as session_module

    monkeypatch.setattr(session_module, "WebKaTrain", MagicMock())
    manager = SessionManager(enable_engine=False)
    session = manager.create_session(user_id=7)
    called = []
    monkeypatch.setattr(manager, "_on_game_ended", lambda sid, end: called.append((sid, end)))
    session.katrain.game_ended_callback(END)
    assert called == [(session.session_id, END)]
