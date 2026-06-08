# Plan Review Prompt — http-engine-remove-spawn

> Paste this whole file to the reviewer (Codex / Gemini). It is self-contained; everything
> you need is referenced by path or quoted below. Read the two source files in the repo
> before reviewing.

## Your role

You are a senior Python / backend reviewer. Review an **implementation plan** (not yet executed)
for correctness, completeness, and risk. Be adversarial and specific — your job is to find what
will bite us during implementation or in production, and to challenge the design decisions where
you disagree. Approve only if you'd be comfortable an engineer could execute it as-written and
ship it to a multi-user server.

## Files to read (in the repo)

1. **Plan under review:** `superpowers/tracks/http-engine-remove-spawn/plan.md`
2. **Requirements / spec:** `superpowers/tracks/http-engine-remove-spawn/requirements.md`
3. **Code being changed:** `katrain/core/engine.py` — class `KataGoHttpEngine`
   (focus: `__init__` ~L539, `start`, `_request_loop` ~L634, `_handle_request` ~L644,
   `_post_json` ~L716, `shutdown` ~L622, `create_engine` ~L795).
4. **Module being deleted:** `katrain/core/http_worker.py`
5. **Existing tests:** `tests/test_http_engine.py`, `tests/test_http_engine_subprocess.py`
6. **Adjacent (NOT being changed, verify the claim):** `katrain/web/core/engine_client.py`
   (`KataGoClient`, async httpx) and `katrain/web/api/v1/endpoints/analysis.py` /
   `katrain/web/core/router.py`.

## Context (what this change does and why)

`KataGoHttpEngine._post_json()` currently spawns a **new Python process per analyze query**
(`multiprocessing.get_context("spawn").Process` → `http_worker.do_request`). On Linux, `spawn`
re-execs the interpreter and re-imports the entry module `katrain.web.server` (SQLAlchemy /
FastAPI / SQLite init) **every query**. Measured on an RK3562 board: ~11s per AI move, of which
~9s is spawn + re-import (KataGo itself answers in ~1s; direct `curl` is ~1.2s).

`_post_json` already runs on a dedicated daemon thread per query (`_request_loop` →
`threading.Thread(_handle_request)` → `_post_json`). So the subprocess is a redundant second
isolation layer. The plan replaces it with a **synchronous `requests.post` on that same thread**,
plus a **shared `requests.Session`** (keep-alive + sized `HTTPAdapter` pool). A temporary on-board
patch of exactly this shape already produced **1.3s/move with zero spawns**.

### Locked decisions (do not re-open unless you find them unsound)
- **Approach A** (sync `requests`), not async httpx. Rationale in the plan: B's "one client"
  benefit doesn't hold (galaxy game-play and the analysis endpoint are legitimately different
  abstractions), and `asyncio.run()`-per-thread adds a loop per query on weak ARM.
- Shared `requests.Session` per engine instance; drop the `Connection: close` header;
  `HTTPAdapter(pool_connections=4, pool_maxsize=10, max_retries=0)`.
- Delete `http_worker.py`; remove `import multiprocessing`, `import urllib3`, the `do_request`
  import, and the vestigial `self._timeout`.
- Preserve: timeout/error semantics (exceptions must reach `_handle_request`'s `except`),
  return value `== response.json()`, no behavior change for board/kiosk/galaxy/desktop.

## What to scrutinize (be concrete — cite Task/Step and file:line)

### Correctness & semantics
1. **Error equivalence.** Old path raised `RuntimeError("HTTP {code}")` for ≥400, `RuntimeError`
   on timeout, and surfaced `str(e)` for other failures. New path: `status_code >= 400` →
   `RuntimeError`, else `response.json()`. Does `_handle_request`'s `except Exception` still
   catch every failure mode (connection refused, DNS, read timeout, non-JSON 200 body)? Any
   case where the new code raises something that escapes the thread and is lost?
2. **Timeout meaning changed.** Old: `parent_conn.poll(http_timeout + 1.0)` — a wall-clock cap on
   the whole round-trip. New: `requests` `timeout=http_timeout` — that is a **connect+read**
   timeout, not a total deadline. With keep-alive + a slow server, could a single query now run
   longer than the old cap? Does that matter given KataGo's behavior? Should it be a `(connect,
   read)` tuple?
3. **`max_retries=0` interaction with `timeout`.** Confirm urllib3 won't silently retry and
   stretch wall-clock. Confirm a refused connection raises promptly rather than blocking.
4. **Return shape.** `_handle_request` branches on `isinstance(analysis, list)`, `"error" in
   analysis`, `isDuringSearch`, `noResults`, `moveInfos`/`rootInfo`. Is `response.json()`
   byte-for-byte equivalent to the old `res["data"]` for all of these? Any place the old worker
   normalized something the new path doesn't?

### Concurrency & lifecycle
5. **Session thread-safety.** One `requests.Session` is shared by all per-query daemon threads of
   an instance. The plan asserts this is safe (urllib3 pool is thread-safe; fixed headers; no
   cookie writes from `/analyze`). Do you agree? Is there a realistic case where `/analyze`
   responses set cookies, or where concurrent `.post` mutates shared session state? Would
   thread-local sessions or an explicit lock be warranted — and what would that cost given threads
   are created **fresh per query** (so thread-local = no reuse)?
6. **Pool sizing for the server.** `pool_maxsize=10` per instance, one instance per game session.
   Under hundreds of concurrent games, is per-instance pooling correct, or should there be a
   process-global pool? Any "Connection pool is full" churn risk? Is `pool_connections=4` (distinct
   hosts) meaningful when every request targets a single `127.0.0.1:8000`?
7. **shutdown/restart race.** `shutdown()` closes the session and sets `_session=None`, but
   in-flight per-query threads aren't joined. The plan relies on `_handle_request`'s `except` to
   swallow a "used a closed/None session" error. Is that acceptable, or can it wedge the engine
   (e.g. `_available` flapping, a callback never firing)? Does `restart()` (shutdown→start)
   correctly rebuild the session before the worker loop dispatches again?
8. **Blocked-thread scaling.** Plan argues N concurrent games = N cheap I/O-bound blocked threads
   (vs N processes today). Is there a thread-count ceiling on the server (default thread stack,
   ulimits) where this still bites at the scale the requirements (§9) describe? Is the win
   real or just deferred?

### Scope, tests, cleanup
9. **Acceptance #6 dropped on purpose.** The plan declares "converge to one HTTP client" out of
   scope, claiming galaxy game-play uses `KataGoHttpEngine` while `KataGoClient` is only on the
   `/analyze` REST endpoint. **Verify this claim from the code** (`web/session.py`,
   `web/interface.py` `create_engine` call, `web/api/v1/endpoints/analysis.py`,
   `web/core/router.py`). Is dropping #6 justified, or is there a live path that makes two clients
   a real maintenance hazard?
10. **Test design.** `tests/test_http_engine_no_spawn.py` asserts no-subprocess via
    `mock.patch("multiprocessing.get_context").assert_not_called()`. Is that a robust proof that no
    process is spawned (vs. e.g. patching at the wrong import site, or a false green)? Are the
    timeout/HTTP-error tests deterministic and not flaky (real `http.server` on an ephemeral port,
    `time.sleep` delays)? Is anything important left untested (keep-alive reuse, `shutdown` closing
    the session, concurrent queries on one session)?
11. **Deletion safety.** Plan deletes `http_worker.py` and `tests/test_http_engine_subprocess.py`
    and removes 3 imports. Grep the repo: is anything else importing `http_worker` / `do_request`,
    or relying on `multiprocessing` / `urllib3` / `self._timeout` from `engine.py`? Any import-time
    side effect lost?
12. **TDD/Buildability.** Could an engineer execute the steps verbatim and get from red → green
    without guessing? Any step where the quoted "find this / replace with" block won't match the
    actual file, or where expected output is wrong?

### Anything else
13. Failure modes, edge cases, or simpler/safer alternatives the plan missed. Push back on the
    locked decisions if you have a concrete, evidenced reason (e.g. a case where async or a total
    deadline is actually required).

## Output format

```
## Plan Review — http-engine-remove-spawn

**Verdict:** Approve | Approve with changes | Needs rework

**Blocking issues** (would cause a wrong build, a regression, or a production hazard):
- [Task X / Step Y or file:line]: <issue> — <why it bites> — <suggested fix>

**Non-blocking concerns** (worth fixing, not gating):
- ...

**Decision challenges** (where you'd choose differently and why, with evidence):
- ...

**Verified claims** (state which plan claims you checked against the code and whether they hold):
- e.g. "galaxy game-play uses KataGoHttpEngine, KataGoClient only on /analyze" → confirmed/refuted at <file:line>
```

Be calibrated: flag things that change the outcome, not style. If you approve, say so plainly and
list only the concerns worth the implementer's attention.
