# HTTP Engine Remove Per-Query Spawn — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `KataGoHttpEngine._post_json` send each analyze query as a direct synchronous `requests.post` on its own already-isolated request thread, eliminating the per-query `multiprocessing.spawn` subprocess (and its re-import of `katrain.web.server`).

**Architecture:** `_post_json` already runs on a dedicated daemon thread per query (`_handle_request`), so a blocking `requests.post` is safe and head-of-line-free. We replace the spawn/Pipe machinery with one shared `requests.Session` (keep-alive + idle connection cache) built per engine instance in `start()`. Timeout and HTTP-error conditions raise exceptions that `_handle_request`'s existing `except Exception` already routes to `error_callback`/`on_error`. Because `start()`/`restart()` now build and tear down a shared `Session`, a generation counter guards the `_available` flag so a stale in-flight request from before a `restart()` cannot corrupt the freshly restarted engine's state. The dead subprocess module (`http_worker.py`) and its imports are removed. No observable behavior change for board/kiosk/galaxy/desktop — pure transport speedup.

**Tech Stack:** Python 3, `requests` (already a dependency, already imported in `engine.py`), `requests.adapters.HTTPAdapter`, pytest with `http.server.ThreadingHTTPServer` mock + `unittest.mock`.

**Requirements source:** `superpowers/tracks/http-engine-remove-spawn/requirements.md`

**Locked decisions (from brainstorming 2026-06-08, refined after Codex/Gemini plan review 2026-06-08):**
- **A** — synchronous `requests.post` on the current thread (NOT async httpx). Validated on-board (1.3s/step). Eliminates 100% of per-query process creation, which is the dominant scalability problem for the server too.
- Shared `requests.Session` per engine instance, keep-alive, `HTTPAdapter` with an idle-connection cache (`pool_maxsize=10`), `max_retries=0`. Drop the `Connection: close` header.
- **Timeout is a `(connect, read)` inactivity tuple, not a hard total deadline.** This is a *deliberate, documented* deviation from the old `parent_conn.poll(http_timeout + 1.0)` wall-clock cap. KataGo returns a single non-streaming JSON body, so a read-inactivity cap is adequate in practice; plain blocking `requests` cannot provide a true total deadline without an extra cancellation layer, which is out of scope.
- **Generation guard:** `start()` bumps `self._generation`; `_handle_request` captures the generation at entry and only writes `self._available` if it still matches. This prevents a stale request whose `Session` was closed by `restart()`/`shutdown()` from flipping availability on the new generation.
- Delete `katrain/core/http_worker.py`; remove `import multiprocessing`, the `do_request` import, the now-unused `import urllib3`, and the vestigial `self._timeout`.
- Preserve: error routing (exceptions reach `_handle_request.except`), return value `== response.json()`, no behavior change for any of the four surfaces.

---

## Resolved unknowns (verified during brainstorming + review — do not re-investigate)

- **§7 待确认①:** Galaxy game-play goes through `KataGoHttpEngine` (`web/session.py:55` → `web/interface.py:254` `create_engine` → `backend="http"`). It is the spawn path and **must** be fixed. `web/core/engine_client.py::KataGoClient` (async httpx — though it currently constructs a **new** `httpx.AsyncClient` inside every `analyze()` call, i.e. it is *not* a persistent pooled client) is wired **only** to the `/api/v1/analysis/analyze` REST endpoint via `RequestRouter` — a *separate* surface from game-play. Converging `KataGoHttpEngine` onto async would NOT merge it with `KataGoClient` (different abstractions). So acceptance criterion #6 ("收敛到同一 HTTP 客户端") is **out of scope** for this plan — game-play and the analysis endpoint legitimately stay two clients.
- `_post_json` has exactly one caller: `_handle_request` (`engine.py:659`), already on its own daemon thread.
- `_handle_request` runs on a per-query daemon thread (`engine.py:642`) and is **not** joined by `shutdown()` (which only joins `worker_thread`). This is why closing a shared `Session` requires the generation guard + local-session capture below.
- `import multiprocessing` (L2) and `from katrain.core.http_worker import do_request` (L30) are used **only** inside `_post_json`. `vision/worker.py` has its own unrelated `multiprocessing` — leave it alone.
- `requests` is already imported (L3) and already used by `create_engine`'s health check (L803). No new dependency.
- `self._timeout` (`urllib3.Timeout`, L561) is set but never read. `urllib3` is otherwise only used as the string logger name `logging.getLogger("urllib3")` (L563), which does NOT require the import.

---

## File Structure

- **Modify:** `katrain/core/engine.py`
  - Imports: remove `import multiprocessing` (L2), remove `from katrain.core.http_worker import do_request` (L30), remove `import urllib3` (L17), add `from requests.adapters import HTTPAdapter`.
  - `KataGoHttpEngine.__init__`: drop `self._timeout`, drop `Connection: close` from `self._headers`, add `self._session = None` and `self._generation = 0`.
  - `KataGoHttpEngine.start()`: bump generation, build the shared session.
  - Add `KataGoHttpEngine._build_session()`.
  - `KataGoHttpEngine._handle_request()`: capture generation at entry; guard the two `self._available` writes with the generation check.
  - `KataGoHttpEngine._post_json()`: replace body with a synchronous `session.post(...)` using a locally captured session + `(connect, read)` timeout tuple.
  - `KataGoHttpEngine.shutdown()`: close the session.
- **Delete:** `katrain/core/http_worker.py` (becomes fully dead).
- **Create:** `tests/test_http_engine_no_spawn.py` (success / HTTP-error / timeout / no-subprocess / import-level / large-response / concurrency / `_handle_request` error-routing / restart-race assertions against a real local HTTP/1.1 server).
- **Delete:** `tests/test_http_engine_subprocess.py` (its spawn-deadlock premise no longer exists; its large-response round-trip value is migrated into the new test file).
- **Leave untouched:** `tests/test_http_engine.py` (mocks `_post_json`, must still pass unchanged — it is the behavior-equivalence guard; the generation guard does not affect its mocked path), `web/core/engine_client.py`, `web/interface.py`, `web/server.py`.

---

### Task 1: Failing tests for de-spawned `_post_json`

**Files:**
- Create: `tests/test_http_engine_no_spawn.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_http_engine_no_spawn.py` with exactly this content:

```python
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import pytest

import katrain.core.engine as engine_module
from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoHttpEngine


class _Handler(BaseHTTPRequestHandler):
    # HTTP/1.1 so the server keeps the connection alive — required to actually
    # exercise the keep-alive Session (HTTP/1.0, the BaseHTTPRequestHandler
    # default, would close after every response and never validate reuse).
    protocol_version = "HTTP/1.1"
    # Class-level knobs the fixture resets before each test.
    status = 200
    delay = 0.0
    big = False

    def _payload(self):
        move_infos = [{"move": "D4", "visits": 10}]
        if _Handler.big:
            move_infos = move_infos * 1000  # large-response coverage (migrated)
        return {
            "id": "x",
            "moveInfos": move_infos,
            "rootInfo": {"visits": 10, "winrate": 0.5},
            "isDuringSearch": False,
        }

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if _Handler.delay:
            time.sleep(_Handler.delay)
        body = json.dumps(self._payload()).encode("utf-8")
        try:
            self.send_response(_Handler.status)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", str(len(body)))  # required for HTTP/1.1 keep-alive
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:
            pass  # client timed out and went away — not a server-side failure

    def log_message(self, *args):
        pass  # silence server logs


@pytest.fixture
def server():
    _Handler.status = 200
    _Handler.delay = 0.0
    _Handler.big = False
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield port
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2.0)


def _make_engine(port, timeout=8.0):
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = dict(katrain.config("engine"))
    config["backend"] = "http"
    config["http_url"] = f"http://127.0.0.1:{port}"
    config["http_timeout"] = timeout
    return KataGoHttpEngine(katrain, config)


def test_post_json_returns_parsed_json(server):
    engine = _make_engine(server)
    try:
        result = engine._post_json({"id": "q1", "moves": []})
        assert "moveInfos" in result
        assert result["rootInfo"]["visits"] == 10
    finally:
        engine.shutdown(finish=False)


def test_post_json_creates_no_subprocess(server):
    engine = _make_engine(server)
    try:
        with mock.patch("subprocess.Popen") as popen, mock.patch(
            "multiprocessing.get_context"
        ) as get_context:
            result = engine._post_json({"id": "q2", "moves": []})
        assert "moveInfos" in result
        get_context.assert_not_called()
        popen.assert_not_called()
    finally:
        engine.shutdown(finish=False)


def test_engine_module_drops_spawn_symbols():
    # Static guard: the de-spawn refactor must not reintroduce the worker import
    # or the multiprocessing module reference at the engine module level.
    assert not hasattr(engine_module, "do_request")
    assert not hasattr(engine_module, "multiprocessing")


def test_post_json_raises_on_http_error(server):
    _Handler.status = 500
    engine = _make_engine(server)
    try:
        with pytest.raises(Exception) as excinfo:
            engine._post_json({"id": "q3", "moves": []})
        assert "500" in str(excinfo.value)
    finally:
        engine.shutdown(finish=False)


def test_post_json_raises_on_timeout(server):
    _Handler.delay = 1.0
    engine = _make_engine(server, timeout=0.2)
    try:
        with pytest.raises(Exception):
            engine._post_json({"id": "q4", "moves": []})
    finally:
        engine.shutdown(finish=False)


def test_post_json_large_response_not_truncated(server):
    _Handler.big = True
    engine = _make_engine(server)
    try:
        result = engine._post_json({"id": "q5", "moves": []})
        assert len(result["moveInfos"]) == 1000
    finally:
        engine.shutdown(finish=False)


def test_concurrent_post_json_share_one_session(server):
    engine = _make_engine(server)
    results = {}
    errors = {}

    def worker(i):
        try:
            results[i] = engine._post_json({"id": f"c{i}", "moves": []})
        except Exception as e:  # pragma: no cover - failure path
            errors[i] = e

    try:
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)
        assert not errors
        assert len(results) == 8
        assert all("moveInfos" in r for r in results.values())
    finally:
        engine.shutdown(finish=False)


def test_handle_request_routes_http_error_to_callback(server):
    _Handler.status = 500
    engine = _make_engine(server)
    captured = {}
    done = threading.Event()

    def error_callback(payload):
        captured.update(payload)
        done.set()

    try:
        engine.send_query({"moves": []}, callback=None, error_callback=error_callback)
        assert done.wait(timeout=10.0)
        assert "error" in captured
        assert "id" in captured
        assert engine.available is False
    finally:
        engine.shutdown(finish=False)


def test_restart_during_inflight_does_not_corrupt_availability(server):
    # A slow, erroring request started before restart() must not flip _available
    # on the freshly restarted (new-generation) engine when its torn-down session
    # surfaces the 500 after restart(). The generation guard must block that write.
    _Handler.delay = 0.8
    _Handler.status = 500
    engine = _make_engine(server, timeout=8.0)
    try:
        engine.send_query({"moves": []}, callback=None, error_callback=lambda p: None)
        time.sleep(0.2)  # request is now inside the server's delay window, pre-response
        engine.restart()  # bumps generation, builds a fresh session, closes the old one
        time.sleep(1.2)  # stale request returns 500 and runs _handle_request.except
        assert engine.available is True  # generation guard blocked the stale write
    finally:
        engine.shutdown(finish=False)
```

- [ ] **Step 2: Run the tests to verify they fail (red)**

Run: `CI=true uv run pytest tests/test_http_engine_no_spawn.py -v`
Expected (against the current spawn code): `test_post_json_creates_no_subprocess` FAILS (current code calls `multiprocessing.get_context`, so the patched mock is hit and either `assert_not_called` fails or the mocked Pipe unpacking raises) and `test_engine_module_drops_spawn_symbols` FAILS (`engine_module` still has `multiprocessing` and `do_request`). `test_restart_during_inflight_does_not_corrupt_availability` may also fail or be flaky because the spawn version has no shared session/generation guard. The success / http-error / timeout / large-response / concurrent tests may pass already; the no-subprocess, import-level, and restart tests define the new contract.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_http_engine_no_spawn.py
git commit -m "test: add no-spawn + lifecycle/concurrency contract tests for KataGoHttpEngine._post_json"
```

---

### Task 2: De-spawn `_post_json` with a shared keep-alive session + generation guard

**Files:**
- Modify: `katrain/core/engine.py` (imports, `__init__`, `start`, new `_build_session`, `_handle_request` generation guard, `_post_json`, `shutdown`)

- [ ] **Step 1: Add the `HTTPAdapter` import**

In `katrain/core/engine.py`, find:

```python
import requests
```

Add directly below it:

```python
from requests.adapters import HTTPAdapter
```

- [ ] **Step 2: Drop the dead `self._timeout` / `Connection: close`; add session + generation fields in `__init__`**

Find (in `KataGoHttpEngine.__init__`):

```python
        self.http_timeout = self.config.get("http_timeout", self.config.get("max_time", 8.0) + 30.0)
        self._timeout = urllib3.Timeout(total=self.http_timeout)
        self._headers = {"Content-Type": "application/json", "Connection": "close"}
        logging.getLogger("urllib3").setLevel(logging.WARNING)
```

Replace with:

```python
        self.http_timeout = self.config.get("http_timeout", self.config.get("max_time", 8.0) + 30.0)
        self._headers = {"Content-Type": "application/json"}
        self._session = None
        self._generation = 0
        logging.getLogger("urllib3").setLevel(logging.WARNING)
```

(The session is built in `start()`, which `__init__` calls a few lines later. `_generation` must exist before `start()` runs.)

- [ ] **Step 3: Bump generation + build the shared session in `start()`, and add `_build_session()`**

Find:

```python
    def start(self):
        self._stop_event.clear()
        self.worker_thread = threading.Thread(target=self._request_loop, daemon=True)
        self.worker_thread.start()
```

Replace with:

```python
    def start(self):
        self._stop_event.clear()
        self._generation += 1
        self._session = self._build_session()
        self.worker_thread = threading.Thread(target=self._request_loop, daemon=True)
        self.worker_thread.start()

    def _build_session(self):
        session = requests.Session()
        # Keep-alive: reuse the TCP connection to the KataGo server across queries on
        # this engine instead of opening a new socket per query.
        #
        # pool_maxsize is the IDLE-connection cache size, NOT a concurrency limiter:
        # with pool_block=False (the default), extra concurrent requests still open
        # extra sockets and simply discard them when done. KaTrain runs one engine
        # instance per game against a single localhost target, so concurrency here is
        # low and an idle cache of 10 is ample.
        #
        # max_retries=0: never silently retry; a failed POST surfaces immediately
        # (this disables urllib3's retry loop — it does NOT impose a total-time cap;
        # the per-request cap is the (connect, read) timeout tuple in _post_json).
        #
        # Thread-safety: we never mutate session headers/cookies after construction,
        # and /analyze is expected not to set cookies, so the shared Session is safe
        # across the per-query request threads.
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=10, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
```

- [ ] **Step 4: Add the generation guard to `_handle_request`'s availability writes**

Find:

```python
    def _handle_request(self, item):
        query, callback, error_callback, next_move, node = item
```

Replace with:

```python
    def _handle_request(self, item):
        query, callback, error_callback, next_move, node = item
        generation = self._generation  # so a stale request post-restart can't flip _available
```

Then find:

```python
            analysis = self._post_json(query)
            if analysis is None:
                raise RuntimeError("Empty response from HTTP engine")
            self._available = True
        except Exception as e:
            self._available = False
```

Replace with:

```python
            analysis = self._post_json(query)
            if analysis is None:
                raise RuntimeError("Empty response from HTTP engine")
            if generation == self._generation:
                self._available = True
        except Exception as e:
            if generation == self._generation:
                self._available = False
```

(Only the two `self._available` writes are guarded. Error-callback delivery is left unchanged — that matched the spawn version's behavior, where an in-flight request after restart still delivered to its callback. The new hazard is specifically `_available` corruption from the shared-session teardown, which this fixes.)

- [ ] **Step 5: Replace the `_post_json` body**

Find the entire current method (the spawn/Pipe version):

```python
    def _post_json(self, payload: Dict) -> Dict:
        url = f"{self.base_url}{self.analyze_path}"
        ctx = multiprocessing.get_context("spawn")
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        p = ctx.Process(target=do_request, args=(url, payload, self._headers, self.http_timeout, child_conn))
        p.start()
        child_conn.close()
        
        try:
            if parent_conn.poll(self.http_timeout + 1.0):
                res = parent_conn.recv()
            else:
                if p.is_alive():
                    p.terminate()
                p.join()
                raise RuntimeError("HTTP request timed out or returned no data")
        except Exception as e:
            if p.is_alive():
                p.terminate()
            p.join()
            raise e
        finally:
            parent_conn.close()
        
        p.join(timeout=1.0)
        if p.is_alive():
            p.terminate()
            p.join()

        if "error" in res:
            raise RuntimeError(res["error"])
        return res["data"]
```

Replace with:

```python
    def _post_json(self, payload: Dict) -> Dict:
        url = f"{self.base_url}{self.analyze_path}"
        # Capture the session locally: shutdown()/restart() may null/close self._session
        # under us (we run on this query's own daemon thread, which shutdown does not
        # join). Holding a local ref keeps the object alive for the in-flight request.
        session = self._session
        if session is None:
            raise RuntimeError("HTTP engine session is closed")
        # Runs on this query's own daemon thread (_request_loop -> _handle_request),
        # so a blocking POST is safe and does not stall the worker or other queries.
        # requests raises ConnectionError (connect failure) or Timeout (inactivity);
        # _handle_request's `except` catches both and routes to error_callback/on_error.
        #
        # timeout is a (connect, read) INACTIVITY tuple, NOT a hard total deadline.
        # This deliberately differs from the old poll(http_timeout + 1.0) wall-clock
        # cap. KataGo returns a single, non-streaming JSON body, so a read-inactivity
        # cap is adequate; a true total deadline would require an extra cancellation
        # layer that plain blocking requests cannot provide.
        timeout = (min(3.05, self.http_timeout), self.http_timeout)
        response = session.post(url, json=payload, headers=self._headers, timeout=timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}")
        return response.json()
```

- [ ] **Step 6: Close the session in `shutdown()`**

Find:

```python
    def shutdown(self, finish=False):
        self._stop_event.set()
        if self.worker_thread:
            self.worker_thread.join()
            self.worker_thread = None
```

Replace with:

```python
    def shutdown(self, finish=False):
        self._stop_event.set()
        if self.worker_thread:
            self.worker_thread.join()
            self.worker_thread = None
        session = self._session
        self._session = None
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
```

(`restart()` calls `shutdown()` then `start()`, so `start()` rebuilds a fresh session and bumps the generation. An in-flight per-request thread captured the old session locally in `_post_json` (Step 5), so `session.close()` clears the idle pool without yanking the connection the in-flight request currently holds; when that request finishes it errors or completes, and the generation guard from Step 4 prevents it from mutating the new generation's `_available`.)

- [ ] **Step 7: Run the new tests to verify they pass (green)**

Run: `CI=true uv run pytest tests/test_http_engine_no_spawn.py -v`
Expected: all tests PASS. In particular `test_post_json_creates_no_subprocess` and `test_engine_module_drops_spawn_symbols` pass because `engine.py` no longer references `multiprocessing` at all (the `import multiprocessing` line is removed in Task 3, but the method-level call is already gone here — run Task 3 before relying on `test_engine_module_drops_spawn_symbols` going green, see note below).

> Note: `test_engine_module_drops_spawn_symbols` checks the **module-level** `multiprocessing`/`do_request` symbols, which are removed in Task 3 Step 1. If you run the full new test file after Task 2 but before Task 3, that one test stays red — that is expected. All other new tests go green after Task 2.

- [ ] **Step 8: Run the behavior-equivalence guard**

Run: `CI=true uv run pytest tests/test_http_engine.py -v`
Expected: `test_http_engine_request_payload` PASSES unchanged (it mocks `_post_json`, so it asserts the surrounding `_handle_request`/`request_analysis` contract is intact — candidates, visits, `partial=False`, payload shape. The generation guard does not affect this mocked path: a single generation, `_available` writes still occur.)

- [ ] **Step 9: Commit**

```bash
git add katrain/core/engine.py
git commit -m "perf(http-engine): replace per-query spawn with synchronous requests + keep-alive session + generation guard"
```

---

### Task 3: Remove the dead subprocess module and stale imports/tests

**Files:**
- Delete: `katrain/core/http_worker.py`
- Delete: `tests/test_http_engine_subprocess.py`
- Modify: `katrain/core/engine.py` (remove `import multiprocessing`, `import urllib3`, `from katrain.core.http_worker import do_request`)

- [ ] **Step 1: Remove the three now-unused imports from `engine.py`**

Delete the line:

```python
import multiprocessing
```

Delete the line:

```python
import urllib3
```

Delete the line:

```python
from katrain.core.http_worker import do_request
```

- [ ] **Step 2: Verify nothing in `engine.py` still references the removed names**

Run: `rg -n "multiprocessing|urllib3|do_request|http_worker|_timeout" katrain/core/engine.py`
Expected: only `logging.getLogger("urllib3")` (a string literal logger name — fine) and no `multiprocessing`, no `do_request`, no `http_worker`, no `self._timeout`. If anything else appears, stop and fix.

- [ ] **Step 3: Delete the dead worker module and its obsolete test**

```bash
git rm katrain/core/http_worker.py tests/test_http_engine_subprocess.py
```

(The large-response coverage from `test_http_engine_subprocess.py` is preserved by `test_post_json_large_response_not_truncated` in the new file.)

- [ ] **Step 4: Confirm no other module imports the deleted symbols**

Run: `rg -n "http_worker|do_request" katrain tests -g "*.py"`
Expected: no output (empty). If `tests/platforms/kgs` `game_undo_request` shows up that is a false match on a different name — only `http_worker` / standalone `do_request` references matter; there must be none.

- [ ] **Step 5: Re-run the HTTP engine tests after import cleanup**

Run: `CI=true uv run pytest tests/test_http_engine_no_spawn.py tests/test_http_engine.py -v`
Expected: all PASS, including `test_engine_module_drops_spawn_symbols` now that the module-level imports are gone (cleanup did not change behavior).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore(http-engine): delete dead spawn worker and stale imports/tests"
```

---

### Task 4: Regression sweep and format

**Files:**
- None (verification only), plus `black` formatting if needed.

- [ ] **Step 1: Format the modified file**

Run: `uv run black -l 120 katrain/core/engine.py tests/test_http_engine_no_spawn.py`
Expected: "reformatted" or "unchanged" — no errors.

- [ ] **Step 2: Run the broader engine + web regression subset**

Run: `CI=true uv run pytest tests/test_http_engine.py tests/test_http_engine_no_spawn.py tests/test_multi_player.py tests/web_ui/test_analysis_endpoint.py -v`
Expected: all PASS. `test_analysis_endpoint.py` exercises the `KataGoClient`/`RequestRouter` REST analysis path (`create_app(enable_engine=False)` + a manually installed `RequestRouter`), confirming the **REST `/api/v1/analysis/analyze` endpoint is unaffected** — it does not exercise galaxy game-play through `KataGoHttpEngine`. Game-play remains covered by `test_http_engine.py` plus the manual on-device galaxy regression below.

- [ ] **Step 3: Full suite (GPU-free)**

Run: `CI=true uv run pytest tests`
Expected: PASS (or only pre-existing unrelated failures — compare against a clean `git stash` baseline if anything is red, and do not let this task introduce new failures).

- [ ] **Step 4: Commit any formatting changes**

```bash
git add -A
git commit -m "style: black-format http engine changes" || echo "nothing to format-commit"
```

---

## On-device acceptance (manual — run after merge + submodule pull-back, per requirements §8)

These cannot run in this repo's CI; they are the field acceptance gates from the requirements doc. Record results in the track.

- [ ] **Board humanv0 @ 1 visit:** each AI move wall-clock ≤ ~2s. `journalctl -u smartbox-katrain | grep -E "Sending|done\]"` shows `[Xs][done]` with X ≈ 1–2s (was ~11s).
- [ ] **No 8–9s gap:** `:8000`'s `Analysis request HTTP:N` follows katrain's `Sending HTTP:N` immediately.
  `journalctl -u smartbox-katago-api | grep "Analysis request"`
- [ ] **No per-move subprocess:** `journalctl -u smartbox-katrain | grep -E "Using SQLite|frozen runpy"` no longer emits once per move.
- [ ] **Galaxy regression:** play / analysis / error-handling behave as on the develop baseline (only faster).
- [ ] **Restart under load (optional smoke):** trigger an engine restart/recovery while a move is being analyzed; confirm the engine returns to `available` and the next move analyzes normally (no stuck "engine unavailable" state from a stale request).

---

## Self-Review (completed against requirements.md + Codex/Gemini plan review)

**Spec coverage:**
- R8.1 (no per-query process) → Task 2 Step 5 + Task 3 (imports/worker removed); proven by `test_post_json_creates_no_subprocess` + `test_engine_module_drops_spawn_symbols`. ✅
- R8.2 (timeout + 4xx/5xx raise, caught by `_handle_request`) → Task 2 Step 5 (`timeout=(connect, read)`, `status_code >= 400` raises; Timeout/ConnectionError propagate) + Task 1 timeout/http-error/`_handle_request`-routing tests. **Documented deviation:** the timeout is read-inactivity, not the old wall-clock total cap; acceptable for KataGo's single-shot JSON responses. ✅
- R8.3 (return == `response.json()`) → Task 2 Step 5 `return response.json()` + Task 1 success + large-response tests. ✅
- R8.4 (delete worker + clean imports) → Task 3. ✅
- R8.5 (connection reuse, thread-safety, lifecycle) → Task 2 Steps 3/4/5/6 (shared `Session`, dropped `Connection: close`, idle `HTTPAdapter` cache, local-session capture, generation guard, safe close). Keep-alive is *actually* validated by the HTTP/1.1 `ThreadingHTTPServer` fixture + the concurrency test; the restart race by `test_restart_during_inflight_does_not_corrupt_availability`. ✅
- R8.6 (no behavior change, surfaces shared) → Task 2 Step 8 (`test_http_engine.py` unchanged) + Task 4 Step 2 (REST analysis endpoint untouched) + on-device galaxy regression. ✅
- Acceptance #5 (test: 200 JSON / non-2xx raise / timeout raise / no subprocess) → Task 1 tests, expanded to also cover import-level guard, large response, concurrency, `_handle_request` error routing, and restart-race. ✅
- Acceptance #6 (one HTTP client) → explicitly **out of scope** with documented rationale (game-play vs analysis endpoint are different abstractions; `KataGoClient` is not on the game-play path, and is itself not currently a pooled client — it builds a new `AsyncClient` per call). Stated above so it is not silently dropped. ✅
- §7 cancel/ponder semantics → unchanged: `terminate_query` still drops the id from `self.queries`, and `_handle_request` ignores results whose id is gone (`if not entry: return`). No code change needed. ✅

**Review-driven corrections folded in (do not revert):**
- Pool/`max_retries` comments no longer claim "bounded concurrency" or "total wall-clock cap" — they describe the idle cache and retry-disable accurately. (Codex blocking #1)
- Timeout is a `(connect, read)` tuple and the plan no longer claims strict equivalence with the old poll() cap. (Codex blocking #2)
- Shutdown/restart race addressed via local-session capture + generation guard + safe `close()`. (Codex blocking #3)
- Tests now use `ThreadingHTTPServer` + HTTP/1.1 + `Content-Length` (real keep-alive), plus concurrency, `_handle_request` error-routing, restart-race, import-level, and large-response coverage; `rg` replaces `grep`. (Codex blocking #4 + non-blocking)

**Placeholder scan:** No TBD/TODO/"add error handling" — every code step shows full content. ✅

**Type/name consistency:** `_build_session` defined and referenced in `start()` (Task 2 Step 3). `self._session` initialized `None` in `__init__` (Step 2), built in `start()` (Step 3), captured locally in `_post_json` (Step 5), closed/reset in `shutdown()` (Step 6). `self._generation` initialized in `__init__` (Step 2), bumped in `start()` (Step 3), read in `_handle_request` (Step 4). `self._headers` (no `Connection: close`) used in `_post_json`. Consistent. ✅
```
