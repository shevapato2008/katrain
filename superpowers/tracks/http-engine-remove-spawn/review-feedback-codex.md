## Plan Review — http-engine-remove-spawn

**Verdict:** Approve with changes

The core direction is sound: `_post_json()` is already called from a per-query daemon thread, so replacing the extra `multiprocessing.spawn` hop with direct synchronous HTTP is the right fix for the measured RK3562/RK3588 latency problem. I would not reopen the A-vs-B decision for this track.

I would not execute the plan exactly as written, though. A few claims in the plan are stronger than what `requests`/`HTTPAdapter` actually guarantee, and the tests do not yet cover the lifecycle/concurrency risks introduced by a shared session.

**Blocking issues** (would cause a wrong build, a regression, or a production hazard):

- [Task 2 / Step 3, plan.md:233-241]: The plan calls the adapter pool "bounded" and says `max_retries=0` keeps wall-clock bounded by `http_timeout`. Both claims are wrong as written. In `requests`, `HTTPAdapter(pool_maxsize=10)` limits how many idle connections are retained per pool; with the default `pool_block=False`, it does not cap concurrent connections. Extra concurrent requests can still open extra sockets and then discard them. Also, `max_retries=0` only disables urllib3 retry loops; it does not make the request total-duration-bounded. Fix the plan comments/self-review and choose an explicit strategy:
  - If connection concurrency must be bounded, add an engine-level semaphore with a documented acquire timeout, or set `pool_block=True` only after deciding that indefinite pool waits are acceptable. I would not silently set `pool_block=True` without a test, because pool acquisition can wait outside the normal request timeout path.
  - If the goal is only keep-alive reuse, keep `pool_block=False` but describe `pool_maxsize=10` as an idle connection cache size, not a server-scale limiter.

- [Task 2 / Step 4, plan.md:292-297; engine.py:724-731]: Timeout semantics are not equivalent. The old parent process path used `parent_conn.poll(self.http_timeout + 1.0)`, which was a rough wall-clock cap for the whole child request. `requests.post(..., timeout=self.http_timeout)` is a connect/read inactivity timeout, not a total deadline. A slow streaming or trickling response can keep a query thread alive longer than the old cap. KataGo normally returns one JSON response, so this may be acceptable, but the plan must stop claiming strict equivalence. At minimum, change the implementation to a tuple and document the tradeoff:

  ```python
  timeout = (min(2.0, self.http_timeout), self.http_timeout)
  response = session.post(url, json=payload, headers=self._headers, timeout=timeout)
  ```

  Add a test or note proving the accepted behavior: delayed first byte times out, non-JSON 200 is caught by `_handle_request`, and no retries stretch the request. If a true total deadline is required, plain blocking `requests` cannot provide it without adding another cancellation layer.

- [Task 2 / Step 5, plan.md:315-329; engine.py:622-627, 634-642, 659-676]: The shutdown/restart race is under-specified. `shutdown()` only joins `worker_thread`; it does not join the per-query `_handle_request` daemon threads created at `engine.py:641-642`. Closing `self._session` while an old request thread is in flight can make that thread report an error and set `_available=False` after a normal shutdown or after `restart()` has already created a fresh session. The plan says this is fine because `_handle_request` catches the exception, but catching it is not the same as preserving engine state. Add one of these safeguards before closing the session:
  - Track per-query threads and either join them up to a small bounded grace period before `session.close()`, or deliberately leave the old session alive until its in-flight users exit.
  - Add a generation token (`self._generation`) so stale request threads from before `restart()` cannot mutate `_available`, `queries`, or callbacks for the new generation.
  - At least make `_post_json()` capture the session locally and raise a clear error if it is closed:

    ```python
    session = self._session
    if session is None:
        raise RuntimeError("HTTP engine session is closed")
    response = session.post(...)
    ```

  Add a regression test: start a delayed `_post_json`/`request_analysis`, call `restart()` or `shutdown(finish=False)` before the server responds, and assert no stale callback or stale `_available=False` survives into the restarted engine.

- [Task 1 / Step 1 and Task 4 / Step 2, plan.md:69-154, 417-420]: The tests do not prove the key new concurrency and lifecycle guarantees. They cover direct `_post_json()` success/error/timeout, but not `_handle_request` error routing for new exception types, not session close behavior, not concurrent requests on one shared session, and not keep-alive reuse. Add focused tests before calling the plan complete:
  - `_handle_request`/`request_analysis` routes HTTP 500, timeout, connection failure, and invalid JSON to `error_callback` instead of losing the thread.
  - Two or more concurrent `_post_json()` calls on one engine succeed against `ThreadingHTTPServer`.
  - `shutdown()` closes the session exactly once and does not let a stale request flip availability after restart.
  - Keep-alive reuse is actually exercised. The proposed `HTTPServer`/`BaseHTTPRequestHandler` fixture defaults to HTTP/1.0, so it will not validate persistent connections. Use `ThreadingHTTPServer`, `protocol_version = "HTTP/1.1"`, and set `Content-Length`.

**Non-blocking concerns** (worth fixing, not gating):

- [Task 1 / Step 1, plan.md:130-133]: `mock.patch("multiprocessing.get_context").assert_not_called()` proves the old spawn call site is gone, but it would miss a future switch to `multiprocessing.Process` or `subprocess.Popen`. Keep this test, but add one static/import-level assertion that `katrain.core.engine` no longer exposes `do_request`/`multiprocessing`, and/or patch `subprocess.Popen` during `_post_json()` to ensure this transport method does not create OS processes.

- [Task 1 / Step 1, plan.md:69-154]: The timeout test uses a real sleep and asserts only `pytest.raises(Exception)`. Make it more diagnostic. Assert the exception type or message for `_post_json()` where practical, and add an `_handle_request`-level test that the user-visible error payload contains the query id. For the sleeping server, catch `BrokenPipeError` in the handler so the test output is not noisy after the client times out.

- [Task 3 / Step 2, plan.md:379-380]: The grep expectation says only the `urllib3` logger string should remain. That is correct, but use `rg` consistently with the repo guideline:

  ```bash
  rg -n "multiprocessing|urllib3|do_request|http_worker|_timeout" katrain/core/engine.py
  ```

- [Task 3 / Step 3, plan.md:382-386]: Deleting `tests/test_http_engine_subprocess.py` is fine, but it currently tests a large response shape (`moveInfos` repeated 1000 times). The pipe-deadlock premise is obsolete, but migrating one "large response returns without truncation" assertion into `test_http_engine_no_spawn.py` is cheap and preserves useful coverage.

- [Task 4 / Step 2, plan.md:417-420]: `tests/web_ui/test_analysis_endpoint.py` does not confirm "galaxy analysis behavior" in the game-play engine sense. The fixture calls `create_app(enable_engine=False)` at `tests/web_ui/test_analysis_endpoint.py:19`, then manually installs a `RequestRouter` with `KataGoClient` at lines 32-37. That validates the REST `/api/v1/analysis/analyze` route only. Either reword the expected result to "REST analysis endpoint unaffected" or add a web-session/game-play regression that exercises `WebKaTrain.start()` with `backend=http`.

- [Task 2 / Step 3, plan.md:233-241]: If using a shared `requests.Session`, document the thread-safety assumption precisely. urllib3's pool is intended for concurrent use, but `requests.Session` also owns mutable cookies and session state. The KataGo `/analyze` server is controlled and should not set cookies, so this is probably acceptable. A short comment should say "we do not mutate session headers/cookies after construction; `/analyze` is expected not to set cookies." If that assumption is not acceptable, use a lock or switch to a lower-level pool/client design.

**Decision challenges** (where I'd choose differently and why, with evidence):

- I agree with Approach A for this track. `_request_loop()` already creates a separate daemon `_handle_request` thread per item at `katrain/core/engine.py:634-642`, and `_handle_request()` calls `_post_json()` at `engine.py:659`. Synchronous `requests` removes the measured spawn/re-import cost with minimal surface area.

- I agree that "converge to one HTTP client" can be out of scope for this plan, but the plan should not describe `KataGoClient` as a clean connection-pooling sample. `katrain/web/core/engine_client.py:11-16` creates a new `httpx.AsyncClient` inside every `analyze()` call, so it is async but not currently a persistent pooled client.

- Per-engine session pooling is acceptable for correctness and preserves per-engine configuration (`base_url`, timeout, headers). It is not a complete server-scale resource strategy. If hundreds of sessions are expected, a future follow-up should consider a process-global pool keyed by `(scheme, host, port)` or a shared client abstraction. That should not block the de-spawn fix.

**Verified claims** (checked against the code):

- "`_post_json` is the spawn point" → confirmed. `katrain/core/engine.py:716-747` calls `multiprocessing.get_context("spawn")`, creates a `Process` targeting `do_request`, and returns `res["data"]`.

- "`_post_json` is called by `_handle_request` on a per-query thread" → confirmed. `_request_loop()` starts a new daemon thread at `katrain/core/engine.py:641-642`; `_handle_request()` calls `_post_json()` at `engine.py:659`.

- "`http_worker.py` / `do_request` deletion is safe" → confirmed for direct imports. `rg` found `from katrain.core.http_worker import do_request` only in `katrain/core/engine.py:30`, the method use at `engine.py:720`, and the obsolete subprocess test. `katrain/vision/worker.py` uses unrelated multiprocessing and should be left alone.

- "`self._timeout` is vestigial" → confirmed. It is assigned from `urllib3.Timeout` at `katrain/core/engine.py:561` and no other code reads it. Removing the `urllib3` import is safe because the remaining use is the logger name string at `engine.py:563`.

- "Galaxy/web session game-play uses `KataGoHttpEngine` when config backend is http" → confirmed. `SessionManager.create_session()` creates `WebKaTrain` at `katrain/web/session.py:55` and calls `katrain.start()` at line 61. `WebKaTrain.start()` calls `create_engine(self, self.config("engine"))` at `katrain/web/interface.py:254`, and `create_engine()` returns `KataGoHttpEngine` for `backend in ["http", "remote", "cloud"]` at `katrain/core/engine.py:790-820`.

- "`KataGoClient` is wired to the REST analysis router" → confirmed. `katrain/web/server.py:118-127` and `server.py:284-289` install `RequestRouter` with `KataGoClient`; `/api/v1/analysis/analyze` calls `router_instance.route(data.payload)` at `katrain/web/api/v1/endpoints/analysis.py:21-25`; `RequestRouter` calls `KataGoClient.analyze()` at `katrain/web/core/router.py:9-18`.

- "The REST analysis route is separate from game-play engine calls" → mostly confirmed by the paths above. The REST endpoint updates `session.katrain.last_engine` and broadcasts state, but it does not call `session.katrain.analysis_engine()` or `KataGoHttpEngine._post_json()`.

**Concrete plan edits I recommend before execution:**

- In Task 2 Step 3, rewrite `_build_session()` comments so they do not claim bounded concurrency or total wall-clock timeout. Optionally add `session.trust_env = False` if the engine should ignore proxy environment variables for localhost analysis calls; otherwise leave old requests behavior unchanged.

- In Task 2 Step 4, use a local `session` variable, handle `None`, and use a connect/read timeout tuple. Keep `status_code >= 400` rather than `raise_for_status()` if preserving the exact `HTTP {code}` message matters.

- In Task 2 Step 5, add either request-thread tracking or generation guarding before closing the session. The current plan's "caught by except" rationale is not enough for restart correctness.

- Expand Task 1 tests to cover `_handle_request` error routing, invalid JSON, concurrent requests, session close/restart, and actual keep-alive. Move the large-response assertion from `tests/test_http_engine_subprocess.py` into the new test file before deleting the old test.

- Reword Task 4 Step 2 expected output: `test_analysis_endpoint.py` proves the REST router path is unaffected, not galaxy game-play. Keep the manual on-device galaxy regression, and add an automated WebKaTrain/http-backend smoke test if feasible.
