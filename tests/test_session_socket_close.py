"""A session the server has dropped must close its game WebSocket.

Without this the browser keeps a live socket to a session that no longer exists, so
`connectionLost` never flips and the kiosk cannot tell a dead game from a live one.
Measured on RK3562 2026-09-20 — see the spec's section 3.

The capacity path is covered deliberately: create_session evicts and shuts down WITHOUT
going through cleanup_expired (session.py:65-87), so a fix that only touches the
periodic sweep misses it entirely.

**而 `session_gone` 只属于「盒子把这一局忘了」那几条路。** 有意收尾(认输离开 / 登出判负 /
删除会话 / 开局失败回滚)走正常关闭 —— 拿 `session_gone` 关一局刚刚正常结束的棋,赢的那一方
会在「你赢了」之后几毫秒被告知「这一局没了」。两种含义各有用例,下面成对地钉。
"""

import asyncio
import threading
import time

from katrain.web.session import SOCKET_CLOSE_SESSION_CLOSED, SessionManager, WebSession


class FakeSocket:
    def __init__(self):
        self.closed_with = None
        self.sent = []

    async def close(self, code=1000, reason=None):
        self.closed_with = (code, reason)

    async def send_json(self, payload):
        self.sent.append(payload)


class FakeKatrain:
    def __init__(self):
        self.shutdown_calls = 0

    def shutdown(self):
        self.shutdown_calls += 1


def _insert(manager, session_id="s1"):
    """Insert a bare session without create_session (which would build a real engine)."""
    session = WebSession(session_id=session_id, katrain=FakeKatrain())
    with manager._lock:
        manager._sessions[session_id] = session
    return session


def _loop_in_thread(manager):
    ready = threading.Event()
    box = {}

    def runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        box["loop"] = loop
        manager.attach_loop(loop)  # records THIS thread as the loop thread
        loop.call_soon(ready.set)
        loop.run_forever()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    assert ready.wait(5)
    return box["loop"], thread


def _stop(loop, thread):
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)


def _wait_closed(sock, timeout=5.0):
    deadline = time.time() + timeout
    while sock.closed_with is None and time.time() < deadline:
        time.sleep(0.02)
    return sock.closed_with


def test_remove_session_closes_its_sockets_but_not_as_gone():
    """有意收尾也要关 socket(否则浏览器守着一条通向不存在会话的活连接),但**不能**用
    `session_gone` 关 —— 那个暗号说的是「盒子把这一局忘了」,客户端据此报警。"""
    manager = SessionManager(enable_engine=False)
    loop, thread = _loop_in_thread(manager)
    try:
        session = _insert(manager)
        sock = FakeSocket()
        session.sockets.add(sock)

        manager.remove_session("s1")

        closed = _wait_closed(sock)
        assert closed == SOCKET_CLOSE_SESSION_CLOSED == (1000, "session_closed")
        assert closed[1] != "session_gone"
    finally:
        _stop(loop, thread)


def test_a_forfeit_teardown_leaves_the_winner_with_a_result_not_a_gone_signal():
    """`/api/multiplayer/leave` 的形状:先广播 `game_end`,再 `remove_session`。
    `session.sockets` 里坐着**两个**人,其中一个刚刚赢了。用 `session_gone` 关他的 socket,
    galaxy 的 `GameRoomPage` 会用整页错误顶掉胜利画面,kiosk 会弹出三条全假的原因。
    这一条钉的就是「赢家先收到结论,再被正常关闭」。"""
    manager = SessionManager(enable_engine=False)
    loop, thread = _loop_in_thread(manager)
    try:
        session = _insert(manager)
        winner = FakeSocket()
        session.sockets.add(winner)

        manager._schedule_broadcast(session, {"type": "game_end", "data": {"reason": "forfeit", "winner_id": 7}})
        manager.remove_session("s1")

        code, reason = _wait_closed(winner)
        assert reason != "session_gone"
        assert (code, reason) == SOCKET_CLOSE_SESSION_CLOSED
        # 结论先到、关闭后到 —— 同一条 socket,同一个 loop 队列,顺序是 FIFO。
        assert [msg["type"] for msg in winner.sent] == ["game_end"]
    finally:
        _stop(loop, thread)


def test_idle_expiry_closes_its_sockets_and_still_stops_the_engine():
    manager = SessionManager(session_timeout=0, enable_engine=False)
    loop, thread = _loop_in_thread(manager)
    try:
        session = _insert(manager)
        sock = FakeSocket()
        session.sockets.add(sock)
        session.last_access = time.time() - 10

        manager.cleanup_expired()

        # 回收路径**保留** `session_gone` —— 这才是客户端该报警的那一种。
        assert _wait_closed(sock) == (1008, "session_gone")
        assert session.katrain.shutdown_calls == 1
    finally:
        _stop(loop, thread)


def test_capacity_eviction_closes_its_sockets():
    """create_session evicts via _cleanup_locked + _shutdown_all and NEVER calls
    cleanup_expired (session.py:65-87). A fix placed only in the periodic sweep misses
    this path, leaving the socket open forever."""
    manager = SessionManager(session_timeout=0, max_sessions=1, enable_engine=False)
    loop, thread = _loop_in_thread(manager)
    try:
        stale = _insert(manager, "stale")
        sock = FakeSocket()
        stale.sockets.add(sock)
        stale.last_access = time.time() - 10

        # Drive the same two calls create_session makes, without building an engine.
        with manager._lock:
            evicted = manager._cleanup_locked()
        manager._shutdown_all(evicted, close=(1008, "session_gone"))

        assert evicted and evicted[0].session_id == "stale"
        assert _wait_closed(sock) == (1008, "session_gone")
    finally:
        _stop(loop, thread)


def test_a_live_session_keeps_its_socket():
    manager = SessionManager(session_timeout=3600, enable_engine=False)
    loop, thread = _loop_in_thread(manager)
    try:
        session = _insert(manager)
        sock = FakeSocket()
        session.sockets.add(sock)

        manager.cleanup_expired()

        time.sleep(0.2)
        assert sock.closed_with is None
    finally:
        _stop(loop, thread)


def test_one_dead_socket_does_not_strand_the_others():
    class ExplodingSocket(FakeSocket):
        async def close(self, code=1000, reason=None):
            raise RuntimeError("already gone")

    manager = SessionManager(enable_engine=False)
    loop, thread = _loop_in_thread(manager)
    try:
        session = _insert(manager)
        bad, good = ExplodingSocket(), FakeSocket()
        session.sockets.add(bad)
        session.sockets.add(good)

        manager.remove_session("s1")

        assert _wait_closed(good) == SOCKET_CLOSE_SESSION_CLOSED
    finally:
        _stop(loop, thread)


def test_one_hung_socket_does_not_delay_the_others():
    """A socket that never acks the close handshake -- e.g. a kiosk that lost its
    network, exactly the scenario this whole change exists for -- must not delay
    closing the rest of the room. A sequential `await ws.close()` per socket would
    block on this one for its full timeout before ever reaching the next; closing
    concurrently (each bounded by its own timeout) does not."""

    class HangingSocket(FakeSocket):
        def __init__(self):
            super().__init__()
            self._never = asyncio.Event()  # deliberately never set

        async def close(self, code=1000, reason=None):
            await self._never.wait()

    manager = SessionManager(enable_engine=False)
    loop, thread = _loop_in_thread(manager)
    try:
        session = _insert(manager)
        hung, good = HangingSocket(), FakeSocket()
        session.sockets.add(hung)
        session.sockets.add(good)

        manager.remove_session("s1")

        assert _wait_closed(good, timeout=1.0) == SOCKET_CLOSE_SESSION_CLOSED
        # Still within the per-socket close timeout (2s) -- if the good socket had to
        # wait its turn behind the hung one, it would not be closed yet either.
        assert hung.closed_with is None
    finally:
        _stop(loop, thread)


def test_a_failed_close_schedule_still_stops_every_engine():
    """`_shutdown_all` 的契约是「一个失败不影响其余」。排关闭任务这一步会在事件循环
    `is_running()` 与真正排任务之间抛 RuntimeError(服务退出时 `server.py` 先取消
    cleanup_task 再调 `cleanup_expired`,这个窗口是真的)。它要是掀翻循环,后面每一局的
    KataGo 都关不掉 —— 2G 的 RK3562 上正是这个进程要命。"""
    manager = SessionManager(enable_engine=False)
    first = WebSession(session_id="a", katrain=FakeKatrain())
    second = WebSession(session_id="b", katrain=FakeKatrain())

    def boom(session, close):
        raise RuntimeError("Event loop is closed")

    manager._schedule_socket_close = boom

    manager._shutdown_all([first, second], close=SOCKET_CLOSE_SESSION_CLOSED)

    assert first.katrain.shutdown_calls == 1
    assert second.katrain.shutdown_calls == 1
