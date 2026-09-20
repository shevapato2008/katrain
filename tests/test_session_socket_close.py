"""A session the server has dropped must close its game WebSocket.

Without this the browser keeps a live socket to a session that no longer exists, so
`connectionLost` never flips and the kiosk cannot tell a dead game from a live one.
Measured on RK3562 2026-09-20 — see the spec's section 3.

The capacity path is covered deliberately: create_session evicts and shuts down WITHOUT
going through cleanup_expired (session.py:65-87), so a fix that only touches the
periodic sweep misses it entirely.
"""

import asyncio
import threading
import time

from katrain.web.session import SessionManager, WebSession


class FakeSocket:
    def __init__(self):
        self.closed_with = None

    async def close(self, code=1000, reason=None):
        self.closed_with = (code, reason)

    async def send_json(self, payload):
        pass


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


def test_remove_session_closes_its_sockets():
    manager = SessionManager(enable_engine=False)
    loop, thread = _loop_in_thread(manager)
    try:
        session = _insert(manager)
        sock = FakeSocket()
        session.sockets.add(sock)

        manager.remove_session("s1")

        assert _wait_closed(sock) == (1008, "session_gone")
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
        manager._shutdown_all(evicted)

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

        assert _wait_closed(good) == (1008, "session_gone")
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

        assert _wait_closed(good, timeout=1.0) == (1008, "session_gone")
        # Still within the per-socket close timeout (2s) -- if the good socket had to
        # wait its turn behind the hung one, it would not be closed yet either.
        assert hung.closed_with is None
    finally:
        _stop(loop, thread)
