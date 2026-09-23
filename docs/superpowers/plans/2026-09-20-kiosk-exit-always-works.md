# kiosk 永远退得出对局 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The user can always leave a game from the kiosk screen — whatever the server, the network or the remote platform does — and never sees a raw HTTP/JSON error string while doing it.

**Architecture:** One signal, one unconditional exit, honest words. Task 1 makes the server close a gone session's WebSocket on every path that drops one. Task 2 makes the two end-game endpoints answer honestly instead of 404-ing, **without claiming the game ended**. Task 3 gives `useGameSession` a single "this session is gone" signal fed by all three transports (WS close, HTTP 404, HTTP `session_gone` body) so every consumer of the shared hook sees it. Task 4 makes leaving unconditional and replaces every raw error string on the kiosk game screen with controlled copy.

**Tech Stack:** FastAPI + Starlette 0.50 (`WebSocket.close(code, reason)` supported), React + TypeScript + Vite, pytest, vitest.

**Spec:** `docs/superpowers/specs/2026-09-20-kiosk-exit-always-works-design.md` — read it first, including its **Revision** section, which records six defects an adversarial review found in the first draft of this plan and the design changes they forced.

## Global Constraints

- **Do not touch the RK3562 board.** No ssh writes, no rsync, no service restart, no deploy. It is in use.
- **Never tell the user something the code does not know.** The server losing a session says **nothing** about whether the remote platform's game ended — `SessionManager` eviction does not call the platform adapter (real remote resignation is `gateway.py:399-420`), and `PlatformManager` keeps its own separate active-game context. Payloads and copy must say "this game is gone **on this box**", never "you resigned" or "the game ended".
- **Do not change `ApiError`'s message format** (`katrain/web/ui/src/api.ts:355,377`). `api.ts:284-285` records that `KifuPage.test.tsx` asserts on the literal `"Request failed 500"`. R2 is solved in the UI layer.
- **Do not invent new error-presentation machinery.** Use `requestFailureKind()` (`src/utils/requestFailure.ts`) and `failureLine(prefix, kind, t)` (`src/kiosk/components/report/reviewPresentation.ts:245`). Sample: `kiosk/pages/ReportDetailPage.tsx:290-299`.
- **Reuse existing copy.** `game:unavailable_title` / `game:unavailable_reason` / `game:back_to_play` already exist at `GamePage.tsx:548-558`. Do not add new keys for the same sentence.
- **i18n:** every new user-facing string is `t('key', '中文默认')`.
- **`useGameSession.ts` and `src/utils/` are SHARED territory** — both builds consume them. Any task touching them runs `npm run build` AND `npm run build:kiosk-2d` before its commit. Galaxy consumes the same hook and does **not** read `connectionLost`, so a change that informs only the kiosk leaves galaxy silently worse off.
- **`session.py` is hot:** `_cleanup_locked`'s docstring records a production lock-queue incident. No I/O and no `await` inside `self._lock`.
- **Never use bare `git stash` / `git stash pop`** — the stash stack is shared across worktrees and sessions.
- **Formatting:** `uv run black -l 120 katrain tests` before each Python commit.
- **Tests:** `CI=true uv run pytest <path>`; `cd katrain/web/ui && npx vitest run <path>`.
- **Commit footer** (every commit):
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  ```

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `katrain/web/session.py` | close sockets on **every** removal path; log the eviction | 1 |
| `katrain/web/server.py` | log the session miss; honest `session_gone` reply on resign/timeout | 1, 2 |
| `katrain/web/ui/src/hooks/useGameSession.ts` | one `'gone'` signal fed by WS close, HTTP 404 and `session_gone` body | 3 |
| `katrain/web/ui/src/kiosk/pages/GamePage.tsx` | leaving is unconditional; no raw error text anywhere | 4 |
| `tests/test_session_socket_close.py` | new — Task 1 | 1 |
| `tests/test_resign_unknown_session.py` | new — Task 2 | 2 |
| `katrain/web/ui/src/hooks/useGameSession.test.ts` | Task 3 | 3 |
| `katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx` | Task 4 | 4 |

**Order: 1 → 2 → 3 → 4.** Task 3 consumes Task 1's close reason and Task 2's body; Task 4 consumes Task 3's signal.

---

### Task 1: Close the game WebSocket on every path that drops a session

**Files:**
- Modify: `katrain/web/session.py` — `_shutdown_all` (:205-214), `remove_session` (:185-189), `cleanup_expired` (:198-203)
- Modify: `katrain/web/server.py` — `_get_session_or_404` (:3394-3398)
- Test: `tests/test_session_socket_close.py` (create)

**Interfaces:**
- Produces: a gone session's sockets are closed with **code 1008**, reason **`"session_gone"`**. Task 3 keys on that exact string.
- Produces: `SessionManager._schedule_socket_close(session)`; `_shutdown_all` becomes an **instance method**.

**Background (do not skip):** evicting a session does not close its WebSocket today. `remove_session` (:185-189) and `_cleanup_locked` (:216-243) only pop the dict and call `session.katrain.shutdown()`, which (`interface.py:1923-1929`) only stops KataGo. The `/ws/{session_id}` loop (`server.py:3205-3208`) never re-checks `_sessions`. The browser keeps a live socket to a session the server has forgotten.

**`_shutdown_all` must become an instance method.** It has **three** call sites, and two of them are the capacity path that `cleanup_expired` never runs: `create_session` calls `self._cleanup_locked()` directly and then `self._shutdown_all(evicted)` at `session.py:73` (limit reached) and `session.py:87` (normal). Putting the socket close only in `cleanup_expired` would miss both — an adversarial review reproduced an engine shutdown with **zero** socket closes on that path. Putting it inside `_shutdown_all` covers all three at once, but `_shutdown_all` is currently a `@staticmethod` and cannot reach `self`.

**Threading:** `_cleanup_locked`'s docstring records a real production lock queue. Closing a socket is `await`-only work on the loop. Follow `_schedule_broadcast` (:298-309) exactly, and never inside `self._lock`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_session_socket_close.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `CI=true uv run pytest tests/test_session_socket_close.py -v`
Expected: the four closing tests FAIL (`closed_with is None`); `test_a_live_session_keeps_its_socket` PASSES — it is the guard that the change does not over-reach.

- [ ] **Step 3: Add the close scheduling**

In `katrain/web/session.py`, add after `_broadcast_payload` (~:309):

```python
    def _schedule_socket_close(self, session: WebSession):
        """Close a gone session's game sockets, on the loop, never under self._lock.

        A session the server has forgotten whose socket is still open is worse than a
        closed one: the browser cannot tell a dead game from a live one, so it keeps
        offering actions that can only fail. Measured on RK3562 2026-09-20.

        Same thread discipline as _schedule_broadcast — _cleanup_locked's docstring
        records the production lock queue that came from slow work inside the lock.
        """
        if not session.sockets:
            return
        if not self._loop or not self._loop.is_running():
            return
        if threading.get_ident() == self._loop_thread_id:
            self._loop.create_task(self._close_sockets(session))
        else:
            future = asyncio.run_coroutine_threadsafe(self._close_sockets(session), self._loop)
            future.add_done_callback(
                lambda f: f.exception()
                and logging.getLogger("katrain_web").warning("closing sockets failed: %s", f.exception())
            )

    @staticmethod
    async def _close_sockets(session: WebSession):
        """1008 + "session_gone" is the wire contract the client keys its recovery on
        (useGameSession.ts). Iterate a snapshot and discard as we go — the /ws handler
        discards the same socket from its own cleanup, and Set.discard is idempotent.
        One socket failing must not strand the rest of the room.
        """
        for ws in list(session.sockets):
            try:
                await ws.close(code=1008, reason="session_gone")
            except Exception:
                pass  # already disconnected — nothing left to tell it
            session.sockets.discard(ws)
```

`asyncio`, `threading` and `logging` are already imported in this file (:289, :48, :211).

- [ ] **Step 4: Make `_shutdown_all` an instance method that also closes sockets**

Replace `_shutdown_all` (:205-214) with:

```python
    def _shutdown_all(self, sessions: List[WebSession]):
        """逐个关停，一个失败不影响其余 —— 关停路径上再抛异常只会漏掉后面那些。

        Socket close lives HERE, not in cleanup_expired, because this method is the one
        thing all three eviction paths share: cleanup_expired's periodic sweep, and
        create_session's two capacity paths (session.py:73 and :87), which never go
        through cleanup_expired at all.
        """
        for session in sessions:
            self._schedule_socket_close(session)
            try:
                session.katrain.shutdown()
            except Exception:
                logging.getLogger("katrain_web").warning(
                    "shutting down session %s failed", session.session_id, exc_info=True
                )
```

It was a `@staticmethod`; all three call sites already call it as `self._shutdown_all(...)`, so no call site changes.

Give `remove_session` the same treatment (:185-189):

```python
    def remove_session(self, session_id: str):
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            self._shutdown_all([session])
```

and add the eviction log to `cleanup_expired` (:198-203):

```python
    def cleanup_expired(self):
        """回收过期会话。**同步方法，不要直接在事件循环上调用** —— 见 `_cleanup_locked`。"""
        with self._lock:
            evicted = self._cleanup_locked()
        for session in evicted:
            logging.getLogger("katrain_web").info(
                "session evicted after %.0fs idle: %s", time.time() - session.last_access, session.session_id
            )
        # 关引擎与关 socket 都在**锁外**做。理由见 `_cleanup_locked` 的注释。
        self._shutdown_all(evicted)
```

The `info` line is deliberate: the spec's section 2 records that this eviction leaves **no trace at all** today, which is why the root cause could only be established as time-consistent rather than proven.

- [ ] **Step 5: Log the session miss behind the 404**

In `katrain/web/server.py`, `_get_session_or_404` (:3394-3398):

```python
def _get_session_or_404(manager: SessionManager, session_id: str):
    try:
        return manager.get_session(session_id)
    except KeyError as exc:
        # Otherwise the only trace is the 404 the user sees: uvicorn runs with
        # access_log=False, so a session miss is invisible in journalctl.
        logging.getLogger("katrain_web").warning("session miss: %s", session_id)
        raise HTTPException(status_code=404, detail="Session not found") from exc
```

- [ ] **Step 6: Run the tests**

Run: `CI=true uv run pytest tests/test_session_socket_close.py -v`
Expected: all five PASS.

- [ ] **Step 7: Regression neighbours**

Run: `CI=true uv run pytest tests/test_galaxy_polish.py tests/test_local_play_game_end.py tests/test_play_ai_endgame.py tests/platforms -q`
Expected: all PASS.

- [ ] **Step 8: Format and commit**

```bash
uv run black -l 120 katrain tests
git add katrain/web/session.py katrain/web/server.py tests/test_session_socket_close.py
git commit -F - <<'MSG'
fix kiosk: close a gone session's game socket on every eviction path

Dropping a session left its WebSocket open, so the browser could not tell a dead
game from a live one and kept offering actions that could only fail. Measured on
RK3562 2026-09-20 during a cross-platform game.

The close lives in _shutdown_all (now an instance method) rather than in
cleanup_expired: create_session's two capacity paths evict and shut down without
ever calling cleanup_expired, so a fix placed there would miss them.

Also logs the eviction and the session miss - neither left any trace before.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 2: End-game endpoints answer honestly instead of 404-ing

**Files:**
- Modify: `katrain/web/server.py` — `resign` (:2055-2057), `timeout` (:2447-2453), helper near `_get_session_or_404`
- Test: `tests/test_resign_unknown_session.py` (create)

**Interfaces:**
- Produces: `POST /api/resign` and `POST /api/timeout` with an unknown `session_id` return **200** `{"session_id": <id>, "status": "session_gone"}`.
- **The body deliberately carries no `ended`, no `state` and no result.** Task 3 keys on `status === "session_gone"`.

**Background (do not skip):** both endpoints start with `_get_session_or_404`, so a forgotten session makes resign fail outright and strands the user.

**The honesty constraint is the whole design here.** An earlier draft returned `{"ended": true}`. That is a lie: `SessionManager` eviction removes local state and stops KataGo — it does **not** end the remote game. Real remote resignation is `gateway.py:399-420`, which this early return never reaches, and `PlatformManager` keeps its own separate active-game context. So the honest claim is **"this box no longer has this game"**, not "the game ended". Everything downstream — payload, copy, kiosk behaviour — must respect that.

**Security (spec E6):** `guard_session_terminator` (`server.py:921`) stops a stranger ending someone else's live game; its criterion is `session_owner_ids(session)`. With no session there is no object to act on, so the early return must happen **before** any ledger write or broadcast and must write nothing. **Do not merge "session does not exist" with "session exists but you are not a participant"** — the second must keep returning 403. Enumeration is unchanged: unknown-vs-someone-else's is already distinguishable (404 vs 403).

- [ ] **Step 1: Write the failing test**

Create `tests/test_resign_unknown_session.py`:

```python
"""Ending a game the server has already forgotten answers honestly instead of 404-ing.

On RK3562 2026-09-20 a cross-platform game's session was reclaimed underneath an open
kiosk page; resign then 404'd and the user could not leave the screen.

Two things this must NOT do:
- claim the game ended. Eviction does not call the platform adapter (gateway.py:399-420),
  so the remote game may well still be live.
- weaken guard_session_terminator (server.py:921). A session that does not exist has no
  owner to impersonate and no ledger row to write - see the spec's E6.
"""

# kivymd's first import from Starlette's portal thread opens a real SDL2/Cocoa window
# off the main thread and aborts on macOS. Same preamble as test_local_play_game_end.py.
import kivymd.app  # noqa: F401

import types
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.server import create_app

OWNER = types.SimpleNamespace(id=7, username="owner", uuid="u-7")


@pytest.fixture
def client(isolated_session_factory):
    """Same shape as tests/test_local_play_game_end.py's fixture - one app factory only."""
    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory  # must precede TestClient: lifespan uses it
    with TestClient(app) as c:
        c.app.state.user_game_repo = MagicMock()
        c.app.state.repository_dispatcher = None
        c.app.dependency_overrides[get_current_user_optional] = lambda: OWNER
        yield c
        c.app.dependency_overrides.clear()
        for session in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager.remove_session(session.session_id)


def test_resign_unknown_session_reports_session_gone(client):
    response = client.post("/api/resign", json={"session_id": "no-such-session"})
    assert response.status_code == 200
    assert response.json() == {"session_id": "no-such-session", "status": "session_gone"}


def test_timeout_unknown_session_reports_session_gone(client):
    response = client.post("/api/timeout", json={"session_id": "no-such-session"})
    assert response.status_code == 200
    assert response.json()["status"] == "session_gone"


def test_the_reply_never_claims_the_game_ended(client):
    """Eviction says nothing about the remote game. Claiming a result here would make
    the kiosk tell the user they resigned a game that is still running."""
    body = client.post("/api/resign", json={"session_id": "no-such-session"}).json()
    assert "ended" not in body
    assert "state" not in body
    assert "result" not in body


def test_the_reply_writes_nothing_to_the_ledger(client):
    client.post("/api/resign", json={"session_id": "no-such-session"})
    client.post("/api/timeout", json={"session_id": "no-such-session"})
    assert client.app.state.user_game_repo.create.call_count == 0


def test_other_endpoints_still_404_on_an_unknown_session(client):
    """Only the two END-GAME endpoints change. Silently succeeding on /api/state would
    be lying about a game that does not exist."""
    assert client.get("/api/state", params={"session_id": "no-such-session"}).status_code == 404
```

Confirm `isolated_session_factory` exists in `tests/conftest.py` before running. If it does not, use whatever fixture `tests/test_local_play_game_end.py` actually requests — do not build a second app factory.

- [ ] **Step 2: Run tests to verify they fail**

Run: `CI=true uv run pytest tests/test_resign_unknown_session.py -v`
Expected: the first three FAIL with 404. The last two PASS (guards that the change does not over-reach).

- [ ] **Step 3: Add the helper**

In `katrain/web/server.py`, next to `_get_session_or_404` (~:3400):

```python
SESSION_GONE_STATUS = "session_gone"


def _session_gone_reply(session_id: str) -> dict:
    """The honest reply for ending a game whose session this box has forgotten.

    It says exactly one thing - this box no longer has this game - and deliberately
    carries no `ended`, no `state` and no result. SessionManager eviction removes local
    state and stops KataGo; it does NOT end a remote game (real remote resignation is
    gateway.py:399-420, which this early return never reaches). Claiming a result would
    make the client tell the user they resigned a game that may still be running.

    Callers MUST return this before touching any ledger or broadcast. It is NOT a
    substitute for the 403 that guard_session_terminator raises when the session EXISTS
    and the caller is not a participant - merging those two would be an auth bypass.
    """
    return {"session_id": session_id, "status": SESSION_GONE_STATUS}
```

- [ ] **Step 4: Use it in both endpoints**

`resign` (:2055-2057) — replace `session = _get_session_or_404(manager, request.session_id)` with:

```python
        try:
            session = manager.get_session(request.session_id)
        except KeyError:
            return _session_gone_reply(request.session_id)
```

`timeout` (:2453) — the same three lines, keeping the existing docstring above them.

- [ ] **Step 5: Run the tests**

Run: `CI=true uv run pytest tests/test_resign_unknown_session.py -v`
Expected: all five PASS.

- [ ] **Step 6: Regression neighbours**

Run: `CI=true uv run pytest tests/test_local_play_timeout.py tests/test_ai_resignation.py tests/test_local_play_game_end.py tests/test_play_ai_endgame.py -q`
Expected: all PASS. These pin resign/timeout on sessions that DO exist, including the 403 paths.

- [ ] **Step 7: Format and commit**

```bash
uv run black -l 120 katrain tests
git add katrain/web/server.py tests/test_resign_unknown_session.py
git commit -F - <<'MSG'
fix kiosk: ending a game whose session is gone answers honestly, not 404

On RK3562 2026-09-20 a cross-platform game's session was reclaimed underneath an
open kiosk page; resign then 404'd and the user could not leave the screen.

The reply says one thing - this box no longer has this game - and carries no
`ended`, no `state` and no result. Eviction does not call the platform adapter,
so the remote game may still be live; claiming a result would make the client
tell the user they resigned a game that is still running.

"Session does not exist" stays distinct from "session exists and you are not a
participant"; the second still 403s via guard_session_terminator.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 3: One "session is gone" signal, fed by all three transports

**Files:**
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts` (:35, :233-242, :272-308) — **SHARED territory, both builds**
- Test: `katrain/web/ui/src/hooks/useGameSession.test.ts`

**Interfaces:**
- Consumes: Task 1's 1008 `"session_gone"` close; Task 2's `{status: "session_gone"}` body.
- Produces: `connectionLost` gains the value `'gone'` — type becomes `'rejected' | 'dropped' | 'gone' | null`. Whenever it is set, `error` is set to a **plain-language Chinese sentence**, never an exception message.

**Background (do not skip):** the session can be discovered gone through **three** different transports, and a fix that handles only one leaves the others broken:

1. the WebSocket closing (Task 1),
2. an HTTP **404** from any game action (what the user actually hit),
3. an HTTP **200 `session_gone`** body from Task 2 — the sneakiest, because `handleAction` today only looks at `result?.state` (`useGameSession.ts:299-301`) and would treat it as a silent success: the dialog closes, the board never ends, and nothing tells the page the game is dead.

Putting all three in the hook means **every** consumer benefits. That matters because `useGameSession` is shared: galaxy's GamePage reads `error` and never reads `connectionLost`, so a signal only the kiosk understands leaves galaxy showing a stale playable board with no warning at all.

**Why `error` must not be set to `null` here:** for galaxy, `error` is the only channel. A plain Chinese sentence satisfies R2 (it is not raw HTTP text) and keeps the shared hook's existing notification contract.

- [ ] **Step 1: Write the failing tests**

Add to `katrain/web/ui/src/hooks/useGameSession.test.ts`. **Read the file first** — it already drives `handleAction` and asserts on thrown errors (`:23`), and its `API` / `WebSocket` mocking is the harness these tests must reuse.

```ts
describe('the session-is-gone signal', () => {
  // The session can be discovered gone three different ways. A fix that handles one
  // leaves the others broken - the 200 body is the sneakiest, because handleAction
  // otherwise treats it as a silent success.

  it('flags gone when a game action 404s', async () => {
    // Arrange: make the mocked API.resign reject with ApiError(404, 'Request failed 404: {"detail":"Session not found"}').
    // Act: await act(async () => { await result.current.handleAction('resign').catch(() => undefined); });
    // Assert: result.current.connectionLost === 'gone'
    //         AND typeof result.current.error === 'string' && result.current.error.length > 0
    //             (galaxy's only channel - null would leave it silent)
    //         AND !/Request failed/.test(result.current.error)
  });

  it('flags gone when a game action returns a session_gone body', async () => {
    // Arrange: make the mocked API.resign RESOLVE with {session_id: 's', status: 'session_gone'}.
    // Assert: connectionLost === 'gone', and gameState is unchanged (no invented result).
  });

  it('flags gone when the socket closes with 1008 session_gone', async () => {
    // Arrange: drive the mocked WebSocket's onclose with {code: 1008, reason: 'session_gone', wasClean: true}.
    // Assert: connectionLost === 'gone' AND !/重新登录/.test(result.current.error)
  });

  it('still says re-login for a genuine 1008 credential rejection', async () => {
    // Arrange: onclose with {code: 1008, reason: 'Invalid token', wasClean: true}.
    // Assert: connectionLost === 'rejected'. The two must not be conflated - re-login
    //         cannot fix an evicted session, and telling the user to try is a lie.
  });
});
```

**Implementer:** the four bodies are specified but not written because this file's harness must be read first. Write real assertions matching it. An `it` with no assertion is a task failure, not an acceptable placeholder.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd katrain/web/ui && npx vitest run src/hooks/useGameSession.test.ts`
Expected: the first three FAIL; the fourth PASSES (it pins existing behaviour).

- [ ] **Step 3: Add the `'gone'` state and its copy**

In `katrain/web/ui/src/hooks/useGameSession.ts`, change :35:

```ts
    const [connectionLost, setConnectionLost] = useState<'rejected' | 'dropped' | 'gone' | null>(null);
```

Add the import (shared territory may import from `src/utils/`):

```ts
import { requestFailureKind } from '../utils/requestFailure';
```

and these two near the other module-level constants at the top of the file:

```ts
// 这一局在服务器上已经没有了(闲置回收 / 盒子重启 / 被删)。三条通道都可能先发现它:
// WS 被 1008 "session_gone" 关掉、任何动作回 404、或 200 `session_gone` 体。
// 文案放这里而不是某一屏里:`useGameSession` 是共享件,galaxy 只读 `error`、根本不读
// `connectionLost`,把话只说给 kiosk 听 = galaxy 那边一块陈旧的可下棋盘,一句提示都没有。
// 说的是「本机没有这一局了」,不是「你认输了」—— 回收会话不会结束远端对局。
const SESSION_GONE_MESSAGE = '这一局在服务器上已经没有了，可以离开这一页。';

function isSessionGone(error: unknown): boolean {
    return requestFailureKind(error) === 'not_found';
}
```

- [ ] **Step 4: Feed the signal from the WebSocket**

Replace the `onclose` handler (:233-242):

```ts
                    ws.onclose = (event) => {
                        if (wsRef.current !== ws) return;  // 已被新连接替换或组件卸载
                        clearQueuedSounds();
                        if (event.code === WS_POLICY_VIOLATION && event.reason === 'session_gone') {
                            // 服务端把这局回收了。这不是凭据问题 —— 走下面那条会告诉用户
                            // 「请重新登录」,而重新登录救不了它。说错原因和印原始报错一样不算人话。
                            console.warn('Game session is gone on the server');
                            setConnectionLost('gone');
                            setError(SESSION_GONE_MESSAGE);
                        } else if (event.code === WS_POLICY_VIOLATION) {
                            console.error("Game WebSocket rejected:", event.reason);
                            setConnectionLost('rejected');
                            setError(`实时连接被拒绝（${event.reason || '凭据无效'}），棋盘不会自动更新，请重新登录后重试`);
                        } else if (!event.wasClean) {
                            console.warn("Game WebSocket closed:", event.code, event.reason);
                            setConnectionLost('dropped');
                            setError("实时连接已断开，棋盘不会自动更新，请刷新页面");
                        }
                    };
```

- [ ] **Step 5: Feed the signal from both HTTP shapes**

In `handleAction` (:272-308), change the tail of the `try` and the whole `catch`:

```ts
            // Task 2 的 200 空回执。只看 `result?.state` 会把它当成静默成功:框关掉、棋局
            // 永远不终局、页面完全不知道这局已经死了。它**不带**任何结果 —— 会话没了不等于
            // 远端认输了(真正的远端认输在 gateway.py:399-420,那条路这时根本没走到)。
            if (result?.status === 'session_gone') {
                setConnectionLost('gone');
                setError(SESSION_GONE_MESSAGE);
                return;
            }
            // Apply state from the HTTP response immediately (a WebSocket broadcast may
            // also arrive, but this ensures the acting client updates without waiting)
            if (result?.state) {
                setGameState(result.state);
            }
        } catch (e) {
            console.error(e);
            if (isSessionGone(e)) {
                // 同一个信号的第三条来路。**不能**把 e.message 放进 error:那正是
                // `Request failed 404: {"detail":…}` 上屏的那条路。
                setConnectionLost('gone');
                setError(SESSION_GONE_MESSAGE);
                throw e;
            }
            const message = e instanceof Error ? e.message : 'Game action failed';
            setError(message);
            throw e;
        }
```

`handleAction` still rethrows, so callers keep their existing control flow.

- [ ] **Step 6: Run the tests**

Run: `cd katrain/web/ui && npx vitest run src/hooks/`
Expected: all PASS, including every pre-existing test in the directory.

- [ ] **Step 7: Build both bundles**

```bash
cd katrain/web/ui && npm run build && npm run build:kiosk-2d
```

Expected: both succeed; `verify:kiosk-2d` exits 0.

- [ ] **Step 8: Commit**

```bash
git add katrain/web/ui/src/hooks/useGameSession.ts katrain/web/ui/src/hooks/useGameSession.test.ts katrain/web/static katrain/web/static-kiosk-2d
git commit -F - <<'MSG'
fix kiosk: one "this session is gone" signal, fed by all three transports

The session can be discovered gone by the socket closing, by a 404, or by the new
200 session_gone body - and handleAction only looked at result?.state, so the
third would have passed as a silent success: dialog closed, game never ended,
page unaware it was dead.

The signal lives in the shared hook so galaxy gets it too: galaxy reads `error`
and never reads connectionLost, so a kiosk-only signal would leave it showing a
stale playable board with no warning. `error` therefore carries a plain-language
sentence, never an exception message.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 4: Leaving is unconditional, and no raw error reaches the screen

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx` (:803, :1010-1012, :1173, :1207, :1221, :1331)
- Test: `katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx`

**Interfaces:**
- Consumes: Task 3's `connectionLost === 'gone'` and its plain-language `error`.

**Background (do not skip) — two separate defects:**

**R1.** Every exit affordance requires the server call to succeed first:

```tsx
try { await session.handleAction('resign'); }
catch (error) { setResignError(...); return; }   // GamePage.tsx:1220-1223
navigate('/kiosk/play');                          // :1228 — after the catch
```

The one server-independent escape, `exit-leave-keep` (:1207-1214), is gated on
`session.connectionLost`. **Gating it at all is the bug.** A Golaxy resign rejection returns
**409** (`server.py:2094`) with a perfectly healthy WebSocket — the user is trapped again, by a
different code. And "leave without resigning" is a purely local act that is *always* legitimate:
it is exactly what the button says it does. It must always be offered.

**R2.** The raw string is built at `api.ts:355` and reaches the screen through
`setResignError(error.message)` (:803, :1173, :1221) rendered at `:1333-1334`, **and** through the
connection snackbar's `{session.error}` fallback (:1012). That fallback stays reachable even after
Task 3: a 1008 credential rejection leaves `connectionLost === 'rejected'`, and a later failed
action overwrites `session.error` with the `ApiError` message. Every connection state needs
controlled copy.

- [ ] **Step 1: Fix the test harness, then write the failing tests**

Three harness problems must be fixed first, or the new tests cannot see the defects:

(a) The existing `beforeEach` lives **inside** `describe('GamePage', …)`, so sibling suites get no
mock reset. Move it to file scope (leave the `describe` intact):

```tsx
beforeEach(() => {
  vi.clearAllMocks();
  boardProps.length = 0;
  for (const k of Object.keys(sessionOverrides)) delete sessionOverrides[k];
});
```

(b) The session mock (`:95-111`) returns a fixed object, so no test can vary `connectionLost` or
`error`. Change the hoisted block at `:8-10` to add an override bag:

```tsx
const { boardProps, sessionOverrides } = vi.hoisted(() => ({
  boardProps: [] as Array<Record<string, unknown>>,
  sessionOverrides: {} as Record<string, unknown>,
}));
```

and spread it last in the hook mock, adding the two keys the page now reads:

```tsx
    error: null,
    connectionLost: null,
    clearPhysicalEngineError: vi.fn(),
    // …existing keys unchanged…
    ...sessionOverrides,
```

(c) Add a spy on the stored-active-game helpers (GamePage imports all three at `:28`):

```tsx
const { mockClearActiveSession } = vi.hoisted(() => ({ mockClearActiveSession: vi.fn() }));
vi.mock('../utils/activeSession', () => ({
  readActiveSession: vi.fn(() => null),
  writeActiveSession: vi.fn(),
  clearActiveSession: mockClearActiveSession,
}));
```

Then add the suites:

```tsx
import { ApiError } from '../../api';

const stillLive = () => new ApiError(409, 'Request failed 409: {"detail": "not your turn"}');

function openExitDialog() {
  fireEvent.click(screen.getByRole('button', { name: '退出对局' }));
}

describe('leaving is unconditional (R1)', () => {
  // "我们需要保证这边可以退出棋局就可以了". Leaving without resigning is a purely local
  // act and is always legitimate - gating it on connectionLost trapped the user behind
  // any failure that kept the socket healthy, e.g. Golaxy's 409 (server.py:2094).

  it('offers leave-without-resigning even on a healthy connection', () => {
    renderPage();
    openExitDialog();
    expect(screen.getByTestId('exit-leave-keep')).toBeInTheDocument();
  });

  it('leaves without calling the server at all', async () => {
    renderPage();
    openExitDialog();
    fireEvent.click(screen.getByTestId('exit-leave-keep'));

    expect(await screen.findByText('PLAY_PAGE')).toBeInTheDocument();
    expect(mockHandleAction).not.toHaveBeenCalled();
  });

  it('still offers it after a 409 that leaves the game live', async () => {
    mockHandleAction.mockRejectedValueOnce(stillLive());
    renderPage();
    openExitDialog();
    fireEvent.click(screen.getByRole('button', { name: '退出' }));

    await screen.findByText('认输没成');
    expect(screen.getByTestId('exit-leave-keep')).toBeInTheDocument();
  });

  it('shows the way out and clears the resume pointer once the session is gone', async () => {
    sessionOverrides.connectionLost = 'gone';
    sessionOverrides.error = '这一局在服务器上已经没有了，可以离开这一页。';
    renderPage();

    expect(await screen.findByTestId('game-gone-leave')).toBeInTheDocument();
    expect(mockClearActiveSession).toHaveBeenCalledWith('game');
  });

  it('that way out actually leaves', async () => {
    sessionOverrides.connectionLost = 'gone';
    renderPage();

    fireEvent.click(await screen.findByTestId('game-gone-leave'));
    expect(await screen.findByText('PLAY_PAGE')).toBeInTheDocument();
  });

  it('leave-without-resigning keeps the resume pointer', () => {
    // The game may still be live on the remote side - 继续上一局 is how the user
    // comes back to it. Only the gone signal may clear it.
    renderPage();
    openExitDialog();
    fireEvent.click(screen.getByTestId('exit-leave-keep'));

    expect(mockClearActiveSession).not.toHaveBeenCalled();
  });
});

describe('no raw request errors on screen (R2)', () => {
  // requestFailureKind maps 409 to 'other', and failureLine renders the prefix alone
  // when the reason is unknown - so the expected text is exactly the prefix.

  it('shows a classified sentence, not the ApiError message, when resign fails', async () => {
    mockHandleAction.mockRejectedValueOnce(stillLive());
    renderPage();

    fireEvent.click(screen.getByText('认输'));
    fireEvent.click(await screen.findByRole('button', { name: '认输' }));

    expect(await screen.findByText('认输没成')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(screen.queryByText(/"detail"/)).toBeNull();
  });

  it('never renders an exception message when the failure has no status', async () => {
    // fetch itself throws a bare Error offline; requestFailureKind returns 'other'
    // because it never guesses. That path used to print "TypeError: Failed to fetch".
    mockHandleAction.mockRejectedValueOnce(new Error('TypeError: Failed to fetch'));
    renderPage();

    fireEvent.click(screen.getByText('认输'));
    fireEvent.click(await screen.findByRole('button', { name: '认输' }));

    expect(await screen.findByText('认输没成')).toBeInTheDocument();
    expect(screen.queryByText(/Failed to fetch/)).toBeNull();
  });

  it('does not leak a raw error through the connection snackbar', () => {
    // THE regression the first draft missed: after a 1008 credential rejection,
    // connectionLost stays 'rejected' and a later failed action overwrites
    // session.error with the ApiError message, which the fallback rendered verbatim.
    sessionOverrides.connectionLost = 'rejected';
    sessionOverrides.error = 'Request failed 409: {"detail": "not your turn"}';
    renderPage();

    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(screen.queryByText(/"detail"/)).toBeNull();
  });
});
```

If `getByRole('button', { name: '退出对局' })` does not resolve, the pagebar back control is
`<button className="kiosk-pagebar__back">` with an `<Icon>` plus that label
(`kiosk/shell/KioskPagebar.tsx:81-89`) — fall back to `document.querySelector('.kiosk-pagebar__back')`.
**Do not weaken an assertion to make a test pass.**

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePage.test.tsx`
Expected: most new tests FAIL. `leaves without calling the server at all` and
`leave-without-resigning keeps the resume pointer` may already pass when the button happens to
render — they are guards, not the defect.

- [ ] **Step 3: Ungate the leave-without-resigning button**

`GamePage.tsx:1207` — delete the `session.connectionLost &&` guard so the button always renders:

```tsx
            <Button data-testid="exit-leave-keep" onClick={() => {
              setShowExitConfirm(false);
              navigate('/kiosk/play');
            }}>
              {t('game:leave_keep_game', '先离开，不认输')}
            </Button>
```

This is the unconditional R1 guarantee. It calls no server, makes no claim about the game, and
deliberately does **not** clear the resume pointer — the game may well still be live, and
"继续上一局" is how the user comes back to it.

- [ ] **Step 4: React to the gone signal in one place**

Add next to `resignError` (:225) and among the other effects:

```tsx
  const [gameGoneAcknowledged, setGameGoneAcknowledged] = useState(false);
  const sessionGone = session.connectionLost === 'gone';

  // 一个信号,一处反应。三条通道(WS 关闭 / 404 / 200 session_gone)都汇进 `connectionLost`,
  // 所以这里不用关心是哪条先发现的。清 resume 指针**只在这一支**做:这局在服务端确实没了,
  // 不清的话「继续上一局」会转回这个死会话。
  useEffect(() => {
    if (!sessionGone) return;
    setShowExitConfirm(false);
    setShowResignConfirm(false);
    clearActiveSession('game');
  }, [sessionGone]);
```

`clearActiveSession` is **already imported** at `GamePage.tsx:28` — do not add it again.

Add the notice dialog next to the others, reusing the copy at `:548-558`:

```tsx
      {/* 这局在服务端已经没了。说人话 + 给出口。说的是「本机没有这一局了」,不是「你认输了」:
          回收会话不会结束远端对局(真正的远端认输在 gateway.py:399-420)。 */}
      <Dialog open={sessionGone && !gameGoneAcknowledged}
              onClose={() => { setGameGoneAcknowledged(true); navigate('/kiosk/play'); }}>
        <DialogTitle sx={{ color: 'text.primary' }}>{t('game:unavailable_title', '这一局已经打不开了')}</DialogTitle>
        <DialogContent>
          <Typography>{t('game:unavailable_reason', '可能是盒子重启过、这一局闲置太久被清理，或者它属于另一个账号。')}</Typography>
        </DialogContent>
        <DialogActions>
          <Button data-testid="game-gone-leave"
                  onClick={() => { setGameGoneAcknowledged(true); navigate('/kiosk/play'); }}>
            {t('game:back_to_play', '回到对弈')}
          </Button>
        </DialogActions>
      </Dialog>
```

- [ ] **Step 5: Classify every message that reaches the screen**

Add the imports (`ApiError` is already at :27):

```tsx
import { requestFailureKind } from '../../utils/requestFailure';
import { failureLine } from '../components/report/reviewPresentation';
```

At `:803`, `:1173` and `:1221`, replace `error instanceof Error ? error.message : …` with:

```tsx
failureLine(t('game:resign_failed', '认输没成'), requestFailureKind(error), t)
```

Find where `timeoutError` is assigned (rendered at `:1331`) and apply the same conversion **at the
assignment site**, so the state never holds a raw message:

```tsx
failureLine(t('game:timeout_failed', '判超时没成'), requestFailureKind(error), t)
```

Leave the existing 409/retry handling around `:637` alone — only the message changes.

- [ ] **Step 6: Give every connection state controlled copy**

`GamePage.tsx:1010-1012` falls through to `{session.error}`, which is reachable with a raw message.
Replace the whole ternary so no branch renders `session.error`:

```tsx
          {session.connectionLost === 'dropped'
            ? t('game:connection_dropped', '实时连接断了，棋盘不会自动更新。点「退出对局」→「先离开，不认输」，再从「继续上一局」回来就会重新连上')
            : session.connectionLost === 'gone'
              ? t('game:session_gone_notice', '这一局在服务器上已经没有了，点「退出对局」就能离开。')
              : t('game:connection_rejected', '实时连接被拒绝，棋盘不会自动更新，请重新登录后重试')}
```

- [ ] **Step 7: Run the tests**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/`
Expected: all PASS, including every pre-existing test in the directory.

- [ ] **Step 8: Prove no raw error can reach this screen**

```bash
cd /Users/fan/Repositories/katrain-kiosk-debug && grep -n "error.message\|{session.error}\|\.message}" katrain/web/ui/src/kiosk/pages/GamePage.tsx
```

Expected: **no hit renders an exception's `.message` or `session.error` into JSX.** Any remaining
hit must be justified in the task report with the reason it cannot carry raw text.

- [ ] **Step 9: Build both bundles**

```bash
cd katrain/web/ui && npm run build && npm run build:kiosk-2d
```

- [ ] **Step 10: Visual confirmation (hard gate — one representative shot)**

This adds a dialog the user will see, so it needs a real-runtime look; jsdom has no layout engine.
Per the project's proportionality rule this is a focused change: **one** screenshot of the notice
dialog at the kiosk viewport is enough — do not re-shoot the 27-screen four-up set.

Drive it with `/browse` against the built bundle (`npm run test:e2e` serves it from :8002), force the
gone state, and capture. Check: title and body readable at kiosk width, the button reachable, and
**no `Request failed` / `{"detail"` / bare `404` anywhere on screen.** Attach the shot to the report.

- [ ] **Step 11: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/__tests__/GamePage.test.tsx katrain/web/static katrain/web/static-kiosk-2d
git commit -F - <<'MSG'
fix kiosk: leaving a game is unconditional, and no raw error reaches the screen

Leave-without-resigning was gated on connectionLost, so any failure that kept the
socket healthy still trapped the user - Golaxy's resign rejection returns 409 with
a perfectly good connection. Leaving without resigning is a purely local act and
is always legitimate, so it is now always offered, and it deliberately keeps the
resume pointer: the game may still be live.

The resume pointer is cleared only on the one signal that means the game is really
gone, in one effect, whichever transport discovered it.

Every message on this screen is now classified copy. The connection snackbar's
{session.error} fallback was still reachable after a 1008 rejection followed by a
failed action, which rendered the ApiError text verbatim.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

## Final verification (after all four tasks)

- [ ] **Python suite against a baseline** — compare failing test IDs by **name** with `comm` against the merge-base, not by count:

```bash
CI=true uv run pytest tests -q --continue-on-collection-errors 2>&1 | tail -30
```

- [ ] **Frontend tests and both builds**

```bash
cd katrain/web/ui && npx vitest run && npm run build && npm run build:kiosk-2d
```

- [ ] **R2 sweep**

```bash
grep -rn "Request failed" katrain/web/ui/src/kiosk/ | grep -v __tests__
```

Expected: no hit (the string lives only in `api.ts`).

## Device acceptance (the user runs this — do NOT ssh to the board)

1. Mid-game, press 退出 → 「先离开，不认输」 — **you leave**, with no server call, on a healthy connection.
2. Force the failure (let the session expire, or restart the service), press 退出 — **you leave**, and the dialog explains why.
3. No `Request failed`, no `{"detail"`, no bare `404` anywhere on screen, in any of these paths.
4. After case 2, 继续上一局 does **not** return to the dead game. After case 1, it **does**.
5. `journalctl -u <katrain unit> | grep 'session evicted'` shows the eviction line (new in Task 1) — this is what turns the spec's "only time-consistent candidate" into a fact.
