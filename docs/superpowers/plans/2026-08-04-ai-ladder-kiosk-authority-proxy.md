# RK3562 AI Ladder Authority Proxy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an authenticated RK3562 kiosk start, play, resume, and settle an AI ladder game through the Galaxy server without making the board node authoritative or exposing remote credentials.

**Architecture:** Add an authoritative ranked-session state/action protocol beside the existing ladder status/start API. Board mode consumes it through an auth-epoch-bound async gateway; existing kiosk HTTP/WebSocket and physical-board surfaces delegate only recognized remote-ranked sessions to that gateway. The Galaxy server remains the only writer of ranked games, ledger rows, placement, and promotion/demotion.

**Tech Stack:** FastAPI, Pydantic, httpx, asyncio, SQLAlchemy-backed existing ladder repository, pytest/pytest-asyncio, React/TypeScript/Vitest.

---

## Chunk 1: Authoritative protocol and board gateway

### Task 1: Add the server-owned ranked action protocol

**Files:**
- Create: `katrain/web/core/ai_ladder_authority.py`
- Modify: `katrain/web/api/v1/endpoints/ai_ladder.py`
- Modify: `katrain/web/session.py`
- Modify: `katrain/web/server.py`
- Test: `tests/web_ui/test_ai_ladder_remote_actions.py`
- Test: `tests/web_ui/test_ai_ladder_api.py`
- Test: `tests/web_ui/test_ai_game_autosave.py`

- [ ] **Step 1: Write failing tests for active-game recovery data**

Add a test that starts a ranked game, calls status, and requires an owner-only projection with `session_id`, `game_id`, `owner_subject`, `user_color`, `terminal`, `state_revision`, and `last_action_receipt`. Add a server-restart test proving `_recover_pending` retains a pending game when its in-memory session disappears and reports `server_session_lost`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_ai_ladder_api.py -k "active_game or server_session_lost"`

Expected: FAIL because status has no active-game/recovery projection and currently clears the pending row.

- [ ] **Step 3: Implement monotonic authoritative state revisions and active-game projection**

Add a thread-safe revision/snapshot tracker owned by each ranked `WebSession`. `SessionManager._on_state` and synchronous terminal mutations both publish through it. Increment only when the canonical gameplay fingerprint changes, but return an integer revision that can be ordered:

```python
with session.ranked_state_lock:
    fingerprint = gameplay_fingerprint(state)
    if fingerprint != session.ranked_state_fingerprint:
        session.ranked_state_revision += 1
        session.ranked_state_fingerprint = fingerprint
    snapshot = deepcopy(state)
    snapshot["ai_ladder_state_revision"] = session.ranked_state_revision
```

The fingerprint detects human moves, delayed AI moves, turn changes, and terminal changes without a new move. Repeated reads keep one revision. Status must never clear an unfinished pending row solely because `SessionManager` lost the session. Tests must exercise human action → delayed AI callback → poll, stable repeated reads, count/resign advancement, and rejection of an older revision.

- [ ] **Step 4: Write failing tests for action idempotency and ordering**

Cover move/pass/resign/timeout/count, stale expected revision, duplicate `action_id`, same ID with another payload, and accepted-response-lost replay. Assert only one mutation and one settlement occur.

- [ ] **Step 5: Run the action tests and verify RED**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_ai_ladder_remote_actions.py`

Expected: FAIL because the ranked session state/action endpoints do not exist.

- [ ] **Step 6: Extract the shared authoritative mutation/finalization service and add dedicated endpoints**

Add:

```text
GET  /api/v1/ai-ladder/sessions/{session_id}/state
POST /api/v1/ai-ladder/sessions/{session_id}/actions
```

Move the ranked branches for move/pass, resign, timeout, and count out of nested `server.py` handlers into `AiLadderAuthoritativeGameService`. Both existing Galaxy endpoints and the new protocol call this one service; terminal persistence is injected through one app-scoped trusted recorder, not duplicated and not reached through a module global. The action request contains `action_id`, `expected_state_revision`, `kind`, and a strictly validated payload. Under one per-session `asyncio.Lock`, validate owner/turn/revision, compute a canonical request fingerprint, replay an identical receipt, reject fingerprint mismatch, apply through the shared service, call the same trusted record/settle callback on terminal state, and retain bounded receipts for the session lifetime.

- [ ] **Step 7: Run focused and authoritative regression tests**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_ai_ladder_remote_actions.py tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_ai_game_autosave.py`

Expected: PASS, including parity assertions that generic Galaxy and dedicated action paths persist the same authoritative result and settle exactly once.

- [ ] **Step 8: Commit**

```bash
git add katrain/web/core/ai_ladder_authority.py katrain/web/api/v1/endpoints/ai_ladder.py katrain/web/session.py katrain/web/server.py tests/web_ui/test_ai_ladder_remote_actions.py tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_ai_game_autosave.py
git commit -m "add authoritative ranked session actions"
```

### Task 2: Add remote-client methods and the auth-bound board gateway

**Files:**
- Create: `katrain/web/core/remote_ranked_session.py`
- Modify: `katrain/web/core/remote_client.py`
- Test: `tests/web_ui/test_remote_ai_ladder_methods.py`
- Test: `tests/web_ui/test_remote_ranked_session.py`

- [ ] **Step 1: Write failing remote-client contract tests**

Require exact methods and paths for catalog, status, start, ranked state, and ranked action. Verify authenticated calls and upstream response preservation.

- [ ] **Step 2: Run and verify RED**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_remote_ai_ladder_methods.py`

Expected: FAIL with missing methods.

- [ ] **Step 3: Implement the minimal client methods and immutable auth context**

Expose a context such as `(subject, epoch)`. Token refresh retains the epoch; login/Box bootstrap subject or generation replacement and clear/logout advance it.

- [ ] **Step 4: Write failing gateway tests**

Cover owner/subject/epoch isolation, one local route per remote game, deterministic action IDs, one unresolved mutation at a time, monotonic publication, identical replay after response loss, and recovery from `active_game.last_action_receipt` after constructing a new gateway.

- [ ] **Step 5: Run and verify RED**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_remote_ranked_session.py`

Expected: FAIL because the gateway does not exist.

- [ ] **Step 6: Implement the async gateway**

Use one `asyncio.Lock` per session. Generate IDs from canonical `(subject, game_id, expected revision, kind, payload)`. Rewrite the remote session id to the local id in every returned payload. Publish state only when its authoritative revision changes and never while an unresolved action is unreconciled.

- [ ] **Step 7: Run focused tests and commit**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_remote_ai_ladder_methods.py tests/web_ui/test_remote_ranked_session.py`

```bash
git add katrain/web/core/remote_client.py katrain/web/core/remote_ranked_session.py tests/web_ui/test_remote_ai_ladder_methods.py tests/web_ui/test_remote_ranked_session.py
git commit -m "add board ranked session gateway"
```

## Chunk 2: Board integration and user journey

### Task 3: Proxy ladder catalog, status, and start in board mode

**Files:**
- Modify: `katrain/web/api/v1/endpoints/ai_ladder.py`
- Modify: `katrain/web/server.py`
- Test: `tests/web_ui/test_board_ai_ladder_proxy.py`

- [ ] **Step 1: Write failing board API tests**

Require authenticated forwarding, status/start response rewriting, active-game gateway recovery, honest 401/409 propagation, timeout/connect 503 mapping, and proof that the local ladder repository remains unchanged.

- [ ] **Step 2: Run and verify RED**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_board_ai_ladder_proxy.py`

Expected: FAIL with the current authority-unavailable 503.

- [ ] **Step 3: Implement board delegation**

Initialize the gateway in `_lifespan_board`. In the ladder endpoints, use local authoritative logic only when `ai_ladder_authoritative=True`; otherwise require the remote client/gateway and proxy. Never set board authority true and never invoke the local ranked repository for status/start/settlement.

- [ ] **Step 4: Run tests and commit**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_board_ai_ladder_proxy.py tests/web_ui/test_ai_ladder_api.py`

```bash
git add katrain/web/api/v1/endpoints/ai_ladder.py katrain/web/server.py tests/web_ui/test_board_ai_ladder_proxy.py
git commit -m "proxy ranked ladder setup on board nodes"
```

### Task 4: Proxy the kiosk game surface and WebSocket

**Files:**
- Modify: `katrain/web/server.py`
- Test: `tests/web_ui/test_board_ai_ladder_game_proxy.py`

- [ ] **Step 1: Write failing tests for state and actions**

Cover `/api/state`, move/pass, resign, timeout, and count. Verify owner isolation, local-id rewriting, action serialization, terminal detach behavior, and that DELETE cannot abandon an active ranked game.

Record local repository/table counts before and after move/pass and each terminal action. Assert the board-side user-game repository, `ai_ladder_pending_games`, `ai_ladder_profiles`, and `ai_ladder_game_ledger` remain unchanged; settlement is visible only through mocked Galaxy status.

- [ ] **Step 2: Write a failing WebSocket test**

Register a remote ranked route, connect to `/ws/{local_id}`, advance mocked authoritative revisions, and require ordered `game_update` messages. Replace auth epoch and require the socket to close.

- [ ] **Step 3: Run and verify RED**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_board_ai_ladder_game_proxy.py`

Expected: FAIL because generic game endpoints only resolve local `SessionManager` sessions.

- [ ] **Step 4: Add narrow remote-ranked branches**

Before local-session lookup, resolve only a recognized owner-bound gateway route and delegate. Keep every non-remote game path byte-for-byte on the existing branch. The WebSocket uses bounded polling through the gateway and emits retryable errors without fabricating state.

- [ ] **Step 5: Run tests and commit**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_board_ai_ladder_game_proxy.py tests/web_ui/test_ranked_rules.py tests/web_ui/test_box_sso.py`

```bash
git add katrain/web/server.py tests/web_ui/test_board_ai_ladder_game_proxy.py
git commit -m "proxy board ranked game actions"
```

### Task 5: Bind Box SSO and physical-board play to the gateway

**Files:**
- Modify: `katrain/web/api/v1/endpoints/auth.py`
- Modify: `katrain/web/api/v1/endpoints/vision.py`
- Modify: `katrain/web/core/physical_play_orchestrator.py`
- Modify: `katrain/web/server.py`
- Test: `tests/web_ui/test_box_sso.py`
- Test: `tests/web_ui/test_board_ai_ladder_vision.py`
- Test: `tests/web_ui/test_physical_play_orchestrator.py`

- [ ] **Step 1: Write failing auth-epoch invalidation tests**

Start/register a remote game, replace Box generation or clear/logout, and require route invalidation, vision unbind, poll stop, and WebSocket close before another remote request can use the new bearer.

- [ ] **Step 2: Write failing physical move tests**

Cover 19x19 bind, human color/turn checks, accepted move state propagation, response-lost replay with the same deterministic ID, stale poll rejection, logout while bound, and backend-restart recovery before detection rearms.

- [ ] **Step 3: Run and verify RED**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_box_sso.py tests/web_ui/test_board_ai_ladder_vision.py`

Expected: FAIL because vision requires a local synchronous `WebSession`.

- [ ] **Step 4: Implement lifecycle invalidation, remote state subscription, and async vision delegation**

Add an explicit `PhysicalPlayOrchestrator.on_bind_remote(session_id, initial_state, subscribe)` path whose subscription callback feeds `on_game_state` and whose disposer is always called on unbind/restart. It must not synthesize a `WebSession` or access `session.katrain`. Route remote-ranked bind and confirmed moves through the async gateway. Feed only accepted monotonic gateway state into expected-board/LED reconciliation. On auth context replacement, invalidate before installing the new context and unbind every matching physical route. Tests cover delayed AI response/capture LED reconciliation and clean subscription disposal.

- [ ] **Step 5: Run tests and commit**

Run: `.venv311/bin/python -m pytest -q tests/web_ui/test_box_sso.py tests/web_ui/test_board_ai_ladder_vision.py tests/web_ui/test_physical_play_orchestrator.py`

```bash
git add katrain/web/api/v1/endpoints/auth.py katrain/web/api/v1/endpoints/vision.py katrain/web/core/physical_play_orchestrator.py katrain/web/server.py tests/web_ui/test_box_sso.py tests/web_ui/test_board_ai_ladder_vision.py tests/web_ui/test_physical_play_orchestrator.py
git commit -m "route physical ranked play to server"
```

### Task 6: Continue active ranked games in Galaxy and kiosk UI

**Files:**
- Modify: `katrain/web/ui/src/features/aiLadder/types.ts`
- Modify: `katrain/web/ui/src/features/aiLadder/AiLadderSetupOpponent.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx`
- Test: `katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx`
- Test: `katrain/web/ui/src/galaxy/pages/AiSetupPage.test.tsx`
- Test: `katrain/web/ui/src/features/aiLadder/AiLadderSetupOpponent.test.tsx`

- [ ] **Step 1: Write failing component tests**

Require `active_game` to render “继续对弈”, keep the action enabled despite `pending_settlement`, navigate without calling start again, and render `server_session_lost` as pending/unavailable with retry rather than a start button.

- [ ] **Step 2: Run and verify RED**

Run: `npm test -- --run src/kiosk/pages/AiSetupPage.test.tsx src/galaxy/pages/AiSetupPage.test.tsx src/features/aiLadder/AiLadderSetupOpponent.test.tsx`

Expected: FAIL because the UI contract has no active game.

- [ ] **Step 3: Implement the minimal shared contract/UI changes**

Reuse existing components and layout. Do not expose subject, remote IDs, receipt fields, model names, visits, or temperatures. The visible route remains `服务器`.

- [ ] **Step 4: Run tests, build, and commit**

Run from `katrain/web/ui`:

```bash
NODE_OPTIONS=--no-experimental-webstorage npm test -- --run src/kiosk/pages/AiSetupPage.test.tsx src/galaxy/pages/AiSetupPage.test.tsx src/features/aiLadder/AiLadderSetupOpponent.test.tsx
npm run build
```

```bash
git add katrain/web/ui/src/features/aiLadder katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx katrain/web/ui/src/kiosk/pages/AiSetupPage.test.tsx katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx katrain/web/ui/src/galaxy/pages/AiSetupPage.test.tsx
git commit -m "resume active ranked games in setup"
```

## Chunk 3: Verification and RK3562 acceptance

### Task 7: Full regression, deployment handoff, and device proof

**Files:**
- Update only if needed: `docs/superpowers/plans/2026-08-04-ai-ladder-kiosk-authority-proxy.md`
- Generated screenshots (not committed): `output/ai-ladder-kiosk-authority-proxy/`

- [ ] **Step 1: Run backend regression tests**

Run the new tests plus `tests/web_ui/test_ai_ladder_api.py`, `test_ai_ladder_ranked.py`, `test_ranked_rules.py`, `test_ai_game_autosave.py`, `test_box_sso.py`, board proxy tests, vision tests, and migrations.

- [ ] **Step 2: Run formatting and static checks**

Run: `.venv311/bin/python -m black -l 120 --check katrain tests`

Run: `git diff --check`

- [ ] **Step 3: Run frontend regression/build**

Run relevant Vitest suites and `npm run build` in `katrain/web/ui`.

- [ ] **Step 4: Request code review and address only in-scope findings**

Use `superpowers:requesting-code-review`, then rerun affected tests.

- [ ] **Step 5: Push/cherry-pick handoff before device deployment**

Push the isolated branch and report its ordered commits. Update smartbox `vendor/katrain` only after the KaTrain commit is available on the requested integration branch.

- [ ] **Step 6: Deploy without touching KataGo port 8000**

Rebuild/restart only the KaTrain/kiosk services required by the existing smartbox deployment flow. Do not stop, restart, or bind `127.0.0.1:8000`.

- [ ] **Step 7: Verify with `fan` and capture proof**

At 1024×600 capture reference, implementation, side-by-side, and diff/overlay images. Verify setup, start/continue, one physical or touchscreen move, server route display, terminal settlement, updated status, relogin persistence, and no authority-unavailable banner. Record any remaining multi-game placement or ±3 acceptance that cannot safely be completed in this run.
