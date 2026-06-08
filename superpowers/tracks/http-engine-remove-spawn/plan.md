# HTTP Engine Remove Per-Query Spawn — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `KataGoHttpEngine._post_json` send each analyze query as a direct synchronous `requests.post` on its own already-isolated request thread, eliminating the per-query `multiprocessing.spawn` subprocess (and its re-import of `katrain.web.server`).

**Architecture:** `_post_json` already runs on a dedicated daemon thread per query (`_handle_request`), so a blocking `requests.post` is safe and head-of-line-free. We replace the spawn/Pipe machinery with one shared `requests.Session` (keep-alive + sized connection pool) built per engine instance in `start()`. Timeout and HTTP-error conditions raise exceptions that `_handle_request`'s existing `except Exception` already routes to `error_callback`/`on_error`. The dead subprocess module (`http_worker.py`) and its imports are removed. No observable behavior change for board/kiosk/galaxy/desktop — pure transport speedup.

**Tech Stack:** Python 3, `requests` (already a dependency, already imported in `engine.py`), `requests.adapters.HTTPAdapter`, pytest with `http.server` mock + `unittest.mock`.

**Requirements source:** `superpowers/tracks/http-engine-remove-spawn/requirements.md`

**Locked decisions (from brainstorming 2026-06-08):**
- **A** — synchronous `requests.post` on the current thread (NOT async httpx). Validated on-board (1.3s/step). Eliminates 100% of per-query process creation, which is the dominant scalability problem for the server too.
- Shared `requests.Session` per engine instance, keep-alive, sized `HTTPAdapter` pool, `max_retries=0`. Drop the `Connection: close` header.
- Delete `katrain/core/http_worker.py`; remove `import multiprocessing`, the `do_request` import, the now-unused `import urllib3`, and the vestigial `self._timeout`.
- Preserve: timeout/error semantics (exceptions reach `_handle_request.except`), return value `== response.json()`, no behavior change for any of the four surfaces.

---

## Resolved unknowns (verified during brainstorming — do not re-investigate)

- **§7 待确认①:** Galaxy game-play goes through `KataGoHttpEngine` (`web/session.py:55` → `web/interface.py:254` `create_engine` → `backend="http"`). It is the spawn path and **must** be fixed. `web/core/engine_client.py::KataGoClient` (clean async httpx) is wired **only** to the `/api/v1/analysis/analyze` REST endpoint via `RequestRouter` — a *separate* surface from game-play. Converging `KataGoHttpEngine` onto async would NOT merge it with `KataGoClient` (different abstractions). So acceptance criterion #6 ("收敛到同一 HTTP 客户端") is **out of scope** for this plan — game-play and the analysis endpoint legitimately stay two clients.
- `_post_json` has exactly one caller: `_handle_request` (`engine.py:659`), already on its own daemon thread.
- `import multiprocessing` (L2) and `from katrain.core.http_worker import do_request` (L30) are used **only** inside `_post_json`. `vision/worker.py` has its own unrelated `multiprocessing` — leave it alone.
- `requests` is already imported (L3) and already used by `create_engine`'s health check (L803). No new dependency.
- `self._timeout` (`urllib3.Timeout`, L561) is set but never read. `urllib3` is otherwise only used as the string logger name `logging.getLogger("urllib3")` (L563), which does NOT require the import.

---

## File Structure

- **Modify:** `katrain/core/engine.py`
  - Imports: remove `import multiprocessing` (L2), remove `from katrain.core.http_worker import do_request` (L30), remove `import urllib3` (L17), add `from requests.adapters import HTTPAdapter`.
  - `KataGoHttpEngine.__init__`: drop `self._timeout`, drop `Connection: close` from `self._headers`.
  - `KataGoHttpEngine.start()`: build the shared session.
  - Add `KataGoHttpEngine._build_session()`.
  - `KataGoHttpEngine._post_json()`: replace body with synchronous `self._session.post(...)`.
  - `KataGoHttpEngine.shutdown()`: close the session.
- **Delete:** `katrain/core/http_worker.py` (becomes fully dead).
- **Create:** `tests/test_http_engine_no_spawn.py` (success / HTTP-error / timeout / no-subprocess assertions against a real local HTTP server).
- **Delete:** `tests/test_http_engine_subprocess.py` (its spawn-deadlock premise no longer exists; its real-server round-trip value is migrated into the new test file).
- **Leave untouched:** `tests/test_http_engine.py` (mocks `_post_json`, must still pass unchanged — it is the behavior-equivalence guard), `web/core/engine_client.py`, `web/interface.py`, `web/server.py`.

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
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

import pytest

from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoHttpEngine


class _Handler(BaseHTTPRequestHandler):
    # Class-level knobs the fixture resets before each test.
    status = 200
    delay = 0.0
    body = {
        "id": "x",
        "moveInfos": [{"move": "D4", "visits": 10}],
        "rootInfo": {"visits": 10, "winrate": 0.5},
        "isDuringSearch": False,
    }

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if _Handler.delay:
            time.sleep(_Handler.delay)
        self.send_response(_Handler.status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(_Handler.body).encode("utf-8"))

    def log_message(self, *args):
        pass  # silence server logs


@pytest.fixture
def server():
    _Handler.status = 200
    _Handler.delay = 0.0
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
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
        with mock.patch("multiprocessing.get_context") as get_context:
            result = engine._post_json({"id": "q2", "moves": []})
        assert "moveInfos" in result
        get_context.assert_not_called()
    finally:
        engine.shutdown(finish=False)


def test_post_json_raises_on_http_error(server):
    _Handler.status = 500
    engine = _make_engine(server)
    try:
        with pytest.raises(Exception):
            engine._post_json({"id": "q3", "moves": []})
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
```

- [ ] **Step 2: Run the tests to verify they fail (red)**

Run: `CI=true uv run pytest tests/test_http_engine_no_spawn.py -v`
Expected: `test_post_json_creates_no_subprocess` FAILS (current code calls `multiprocessing.get_context`, so the patched mock is hit and either `assert_not_called` fails or the mocked Pipe unpacking raises). The timeout/http-error tests may pass already; the success and no-subprocess tests define the new contract. The key red signal is `test_post_json_creates_no_subprocess`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_http_engine_no_spawn.py
git commit -m "test: add no-spawn contract tests for KataGoHttpEngine._post_json"
```

---

### Task 2: De-spawn `_post_json` with a shared keep-alive session

**Files:**
- Modify: `katrain/core/engine.py` (imports, `__init__`, `start`, new `_build_session`, `_post_json`, `shutdown`)

- [ ] **Step 1: Add the `HTTPAdapter` import**

In `katrain/core/engine.py`, find:

```python
import requests
```

Add directly below it:

```python
from requests.adapters import HTTPAdapter
```

- [ ] **Step 2: Drop the dead `self._timeout` and the `Connection: close` header in `__init__`**

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
        logging.getLogger("urllib3").setLevel(logging.WARNING)
```

(The session is built in `start()`, which `__init__` calls a few lines later.)

- [ ] **Step 3: Build the shared session in `start()` and add `_build_session()`**

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
        self._session = self._build_session()
        self.worker_thread = threading.Thread(target=self._request_loop, daemon=True)
        self.worker_thread.start()

    def _build_session(self):
        session = requests.Session()
        # Keep-alive + bounded pool so concurrent request threads reuse TCP
        # connections to the KataGo server instead of opening a new one each query.
        # max_retries=0 keeps wall-clock bounded by http_timeout (no silent retry).
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=10, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
```

- [ ] **Step 4: Replace the `_post_json` body**

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
        # Runs on this query's own daemon thread (see _request_loop / _handle_request),
        # so a blocking POST is safe and does not stall the worker or other queries.
        # requests raises Timeout / ConnectionError; _handle_request's except catches
        # them, sets _available=False, and routes to error_callback / on_error.
        response = self._session.post(
            url, json=payload, headers=self._headers, timeout=self.http_timeout
        )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}")
        return response.json()
```

- [ ] **Step 5: Close the session in `shutdown()`**

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
        session = getattr(self, "_session", None)
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
            self._session = None
```

(`restart()` calls `shutdown()` then `start()`, so `start()` rebuilds a fresh session. An in-flight per-request thread racing a shutdown is caught by `_handle_request`'s existing `except` — same tolerance the spawn version had.)

- [ ] **Step 6: Run the new tests to verify they pass (green)**

Run: `CI=true uv run pytest tests/test_http_engine_no_spawn.py -v`
Expected: all 4 tests PASS. In particular `test_post_json_creates_no_subprocess` passes because `engine.py` no longer references `multiprocessing` at all.

- [ ] **Step 7: Run the behavior-equivalence guard**

Run: `CI=true uv run pytest tests/test_http_engine.py -v`
Expected: `test_http_engine_request_payload` PASSES unchanged (it mocks `_post_json`, so it asserts the surrounding `_handle_request`/`request_analysis` contract is intact — candidates, visits, `partial=False`, payload shape).

- [ ] **Step 8: Commit**

```bash
git add katrain/core/engine.py
git commit -m "perf(http-engine): replace per-query spawn with synchronous requests + keep-alive session"
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

Run: `grep -nE "multiprocessing|urllib3|do_request|http_worker|_timeout" katrain/core/engine.py`
Expected: only `logging.getLogger("urllib3")` (a string literal logger name — fine) and no `multiprocessing`, no `do_request`, no `http_worker`, no `self._timeout`. If anything else appears, stop and fix.

- [ ] **Step 3: Delete the dead worker module and its obsolete test**

```bash
git rm katrain/core/http_worker.py tests/test_http_engine_subprocess.py
```

- [ ] **Step 4: Confirm no other module imports the deleted symbols**

Run: `grep -rnE "http_worker|do_request" katrain tests --include="*.py"`
Expected: no output (empty). If `tests/platforms/kgs` `game_undo_request` shows up that is a false match on a different name — only `http_worker` / standalone `do_request` references matter; there must be none.

- [ ] **Step 5: Re-run the HTTP engine tests after import cleanup**

Run: `CI=true uv run pytest tests/test_http_engine_no_spawn.py tests/test_http_engine.py -v`
Expected: all PASS (cleanup did not change behavior).

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
Expected: all PASS. `test_analysis_endpoint.py` exercises the `KataGoClient`/`RequestRouter` analysis path — it must be unaffected (we did not touch that surface), confirming galaxy analysis behavior is unchanged.

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

---

## Self-Review (completed against requirements.md)

**Spec coverage:**
- R8.1 (no per-query process) → Task 2 Step 4 + Task 3 (imports/worker removed). ✅
- R8.2 (timeout + 4xx/5xx raise, caught by `_handle_request`) → Task 2 Step 4 (`timeout=self.http_timeout`, `status_code >= 400` raises; Timeout/ConnectionError propagate) + Task 1 timeout/http-error tests. ✅
- R8.3 (return == `response.json()`) → Task 2 Step 4 `return response.json()` + Task 1 success test. ✅
- R8.4 (delete worker + clean imports) → Task 3. ✅
- R8.5 (connection reuse, thread-safety) → Task 2 Steps 2/3 (shared `Session`, dropped `Connection: close`, `HTTPAdapter` pool; urllib3 pool is thread-safe for concurrent POSTs with fixed headers / no cookie writes from `/analyze`). ✅
- R8.6 (no behavior change, 3-end shared) → Task 2 Step 7 (`test_http_engine.py` unchanged) + Task 4 Step 2 (analysis endpoint untouched) + on-device galaxy regression. ✅
- Acceptance #5 (test: 200 JSON / non-2xx raise / timeout raise / no subprocess) → Task 1 four tests. ✅
- Acceptance #6 (one HTTP client) → explicitly **out of scope** with documented rationale (game-play vs analysis endpoint are different abstractions; `KataGoClient` is not on the game-play path). Stated above so it is not silently dropped. ✅
- §7 cancel/ponder semantics → unchanged: `terminate_query` still drops the id from `self.queries`, and `_handle_request` ignores results whose id is gone (`if not entry: return`). No code change needed; no task required. ✅

**Placeholder scan:** No TBD/TODO/"add error handling" — every code step shows full content. ✅

**Type/name consistency:** `_build_session` defined in Task 2 Step 3, referenced in `start()` same step. `self._session` initialized `None` in `__init__` (Step 2), built in `start()` (Step 3), used in `_post_json` (Step 4), closed/reset in `shutdown()` (Step 5). `self._headers` (no `Connection: close`) used in `_post_json`. Consistent. ✅
