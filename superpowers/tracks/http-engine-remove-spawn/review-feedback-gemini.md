## Plan Review — http-engine-remove-spawn

**Verdict:** Approve

**Blocking issues** (would cause a wrong build, a regression, or a production hazard):
- None.

**Non-blocking concerns** (worth fixing, not gating):
- None. The plan covers edge cases effectively, including test flakiness prevention and correctly handling daemon thread lifecycles during `shutdown()`. The use of `max_retries=0` and connection pooling sizes are sensible given the single localhost target and Katrain's per-game engine instance mapping.

**Decision challenges** (where you'd choose differently and why, with evidence):
- I fully agree with dropping Acceptance #6 (converging to `KataGoClient`). The game-play module inherently requires the stateful abstraction provided by `KataGoHttpEngine`. Unifying them would unnecessarily couple the distinct needs of the stateless REST analysis endpoint and the stateful, queue-driven UI engine integration.
- The choice of a synchronous `requests.post` inside the existing thread queue (`_request_loop` -> `_handle_request`) is elegant. It leverages the existing concurrency architecture rather than reinventing the wheel with an asynchronous reactor event loop in a heavily thread-driven `kivy` UI.

**Verified claims** (state which plan claims you checked against the code and whether they hold):
- **"Galaxy game-play goes through KataGoHttpEngine, KataGoClient only on /analyze"**: Confirmed. In `katrain/web/interface.py` (L254 & L1179), `WebKaTrain` uses `create_engine` which provisions a `KataGoHttpEngine`. In `katrain/web/api/v1/endpoints/analysis.py` (L22, L60), `RequestRouter` delegates strictly to `KataGoClient`. The separation is factual.
- **"_post_json has exactly one caller: _handle_request, already on its own daemon thread"**: Confirmed. `_request_loop` (L642) kicks off `_handle_request` in a daemon thread, and `_handle_request` directly invokes `_post_json` (L659) which means the blocking `requests.post` will not stall any global event loop.
- **"shutdown() race swallowed by _handle_request except"**: Confirmed. `_handle_request` wraps `self._post_json` in a sweeping `except Exception as e:` block. If `self._session` evaluates to `None` and triggers an `AttributeError`, it is caught identically to a networking failure and won't crash the program.
- **"KataGoHttpEngine.start() builds the shared session"**: Confirmed. Note that `start()` is safely called by `KataGoHttpEngine.__init__` (L566), so the `_make_engine` mock in the test suite will correctly have `self._session` populated before `_post_json` is directly tested.
- **"delete test_http_engine_subprocess.py and http_worker.py without impact"**: Confirmed. Grepping the repository confirms `do_request` and `http_worker.py` are purely internal components utilized exclusively by the legacy `KataGoHttpEngine._post_json` spawn strategy. (There is a false-positive in `json_client.py` for `game_undo_request` but it is unrelated).