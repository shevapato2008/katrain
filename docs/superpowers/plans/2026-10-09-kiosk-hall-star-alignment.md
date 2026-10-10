# Kiosk Hall Star Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** 落地用户已确认的 kiosk 在线大厅 v3，保留匹配/邀请/观战旅程，并让观战人数来自中央服务的真实观众身份统计。

**Architecture:** 沿用现有 LobbyPage 控制器和星阵 kiosk 外壳，仅替换大厅展示。中央 WebSession 保存会话级临时观众身份：WebSocket 按连接记录用户，HTTP 观战快照按用户记录最近心跳；统计两者身份并集，排除对局棋手。盒子只转发中央结果，不统计本地镜像。无需数据库、后台任务或额外棋盘/引擎请求。

**Tech Stack:** React/TypeScript/CSS，FastAPI，pytest，Vitest，Playwright/Chrome。

---

## Chunk 1: Approved slice and shared contract

### Task 1: Baseline and scope

**References:**
- `docs/design/play-consistency-2026-10-09/index.html?surface=kiosk&view=hall`
- `docs/design/play-consistency-2026-10-09/KIOSK-HALL-V3-REVIEW.md`
- `docs/design/play-consistency-2026-10-09/kiosk-hall-v3-games.png`
- `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.tsx`
- `katrain/web/ui/src/kiosk-shell/golaxy-home.css`

- [x] Fetch latest `develop` before code changes: `git fetch origin develop`; remote/current HEAD both `9f28d43d`, `git merge --no-edit origin/develop` reports already up to date.
- [x] Preserve prior uncommitted, reviewed Galaxy consistency, direct-invite and kiosk spectator work; use the existing isolated `feature/admin-console` worktree. No reset/checkout or unrelated edits.
- [x] Independent GPT-6-astra max plan review; round 1 notification gap fixed, round 2 Approved.

**Approved scope:** only kiosk online hall visual changes plus real observer count across the hall and existing spectator consumers. No kiosk free/rated redesign, no ranking/engine/robot scheduling changes, no new public robot indicators, no deployment during design implementation.

**Behavior preserved:** only quick match requires completed placement and same rank. Direct invitation permits unplaced users and any rank, retains idle/reservation/auth gates. All hall games stay unranked. Own game returns to `/kiosk/play/pvp/room/:id`, other game opens `/kiosk/play/pvp/watch/:id`. Strict box uses authenticated central identity and cloud IDs for spectators.

### Task 2: Observer count contract

**Files:**
- Create `katrain/web/core/pvp_spectator_presence.py`
- Modify `katrain/web/session.py`
- Modify `katrain/web/api/pvp_spectator.py`
- Modify `katrain/web/api/v1/endpoints/games.py`
- Modify `katrain/web/server.py`
- Tests `tests/web_ui/test_pvp_spectator_presence.py`, `tests/web_ui/test_pvp_spectator.py`, relevant existing lobby/socket tests

**Data rules:**
1. `spectator_count` is a nonnegative integer of unique authenticated non-seat users. Bots have negative seat IDs and create no fake watcher/seat sockets. Duplicate tabs and WS + HTTP from one user count once.
2. Snapshot GET renews HTTP observer presence **after** authentication, public room validation and authoritative state read succeed. Owners do not become observers. Invalid/private/auth-failed requests never register.
3. HTTP heartbeat TTL is 10 seconds, `time.monotonic()`, pruned lazily on read/touch. Existing kiosk polling is every 2 seconds and pauses when hidden; leaving/hidden observers disappear within 10 seconds plus next list refresh. TTL is deliberately approximate presence, not claimed instantaneous leave detection.
4. WebSocket identity is keyed by socket; register after authorization/accept and remove in `finally`. Count only identities whose sockets remain in `session.sockets`; session deletion/server close cannot leave live observer memberships. State is per session and discarded with it; no global never-pruned map. Thread-safe helper because session state callbacks run in engine threads.
5. REST hall rows and public spectator snapshot add `spectator_count`. GameState gets the same additive field. Preserve legacy `sockets_count` and WS message `count` raw-socket semantics; add `spectator_count` to that event and update consumers to read it. Never reinterpret old fields silently.
6. `session_state_for_read`, SessionManager `_on_state`, initial WS state, join/leave WS broadcasts refresh authoritative count. Successful HTTP observer touch compares the old and new count and immediately broadcasts the additive count when it changes. A single cancellable, per-session event-loop expiry callback runs at the next HTTP expiry (10 seconds after last heartbeat), prunes memberships and broadcasts changed counts even in a quiet room with no moves or subsequent reads; rearm only while HTTP members remain. No engine/state reads in the callback, no new polling service. Callback verifies the same session is still registered without touching last_access, and cleanup cancels its handle; session shutdown/replacement cannot broadcast into another room.
7. Strict box forwards central fields and heartbeat under its verified central identity; local mirror never contributes. Private AI/ladder/cross-platform access stays protected, no action route changes.
8. Production frontends display verified integer counts. Missing/invalid values display “观战人数未返回”, never sample/default zero. Legacy raw socket number may remain stored for compatibility but is not presented as a verified watcher count.

Minimal helper interface, implementation may match repository conventions:
```python
presence.touch_http(user_id)
presence.join_socket(socket, user_id)
presence.leave_socket(socket)
presence.count(seat_ids=(session.player_b_id, session.player_w_id), live_sockets=session.sockets)
```
Store helper on `WebSession` using `field(default_factory=...)`; guard mocks only where tests use non-WebSession fixtures, not broad error-swallowing fallback to zero.

- [x] Write meaningful focused tests: zero bot-vs-bot spectators; owner exclusion; authenticated viewer; duplicate WS tabs; HTTP+WS union; monotonic TTL; closed sockets/session lifecycle; HTTP join notifies an already-open WS client and TTL expiry notifies without moves/further reads (with deterministic clock/scheduler, no 10-second test sleeps); unauthorized/private GET unchanged; strict-box count forwarding and cloud identity.
- [x] Run new tests to establish failure before implementing count behavior.
- [x] Implement smallest helper and wire it through central endpoints/state and WS lifecycle. Do not persist observers or create new services.
- [x] Run `uv run pytest tests/web_ui/test_pvp_spectator_presence.py tests/web_ui/test_pvp_spectator.py tests/web_ui/test_lobby_boundaries.py -q` plus the directly affected existing WS test file if present. Expected pass; existing authorization, private room and bot invitation coverage retained.

## Chunk 2: Kiosk journey and compatible consumers

### Task 3: Approved kiosk hall view

**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/LobbyPage.tsx`
- Modify `katrain/web/ui/src/kiosk/pages/LobbyPage.css`
- Modify `katrain/web/ui/src/kiosk/pages/LobbyPage.test.tsx`

**Visual criteria at 1024×600:** existing shell topbar 56; pagebar 48; two equal 68px action cards; section labels; full-width tabbed list x16/y248/w992/h330; two-column 90px game cards (x24/y304/w484 first card), 58px players. Native semantic controls, Chinese complete shared Kai stack, existing Latin stacks. Copy approved CSS geometry/materials without new global tokens. Avatar corner black/white stones and text seat labels; center 28px wood grid recognition icon only (not live position); eye + real watcher count at top right. No extra room snapshot requests for thumbnails. No fixture data in production.

**Interactions:**
- Native game card buttons keep existing own/watch destinations.
- Games and players tabs with accessible tablist/panel and roving focus, ArrowLeft/Right/Home/End.
- Invite top card switches to players and focuses panel; show all/same rank filters with real statuses and self/idle/busy logic. Same rank disabled for unplaced.
- Direct invitation confirmation uses chosen real target and sends exactly once on confirm; cancel sends nothing. Placement modal is quick-match only. Keep incoming invite, matchmaking cancellation, errors and retry.
- Dialogs have accessible names, initial focus, focus trap, Escape and restore focus; Escape during matching sends stop, not merely hides pending matching.
- Loading/empty/error/disconnected states must fit viewport and state truthfully; error alerts should not make 330px list overflow the available screen (reduce list height for alerts). No stale users/games after account switch; use minimal abort/sequence guarding if existing async list requests would leak prior identity.

- [x] Extend tests for tabs, watch/own routes, unplaced direct invite confirmation/any rank, matching placement, self/busy filtering, keyboard/focus, missing/invalid counts, no per-card fetch, request results fenced on identity change.
- [x] Run tests and implement presentation over the existing controller; do not rewrite rank/matching/WS business flows.
- [x] Run `cd katrain/web/ui && npx vitest run src/kiosk/pages/LobbyPage.test.tsx src/kiosk/pages/PvpSpectatorPage.test.tsx`. Expected pass.

### Task 4: Consume true count in existing spectator views

**Files:**
- Modify `katrain/web/ui/src/api.ts` (add optional count only to GameState, do not alter external Golaxy room contract)
- Modify `katrain/web/ui/src/hooks/useSessionBase.ts`
- Modify `katrain/web/ui/src/hooks/useGameSession.ts`
- Modify `katrain/web/ui/src/galaxy/pages/GameRoomPage.tsx` and `.test.tsx`
- Modify `katrain/web/ui/src/kiosk/pages/PvpSpectatorPage.tsx` and `.test.tsx` only if watcher metadata is presented there

- [x] Preserve legacy raw socket storage; copy event's valid authoritative spectator_count into GameState, invalid/missing count remains unknown. New field follows the snapshot/state lifecycle, no additive tracking UI timers.
- [x] Galaxy watcher label uses verified spectator_count instead of subtracting two from socket count; unknown is honest. Kiosk spectator shows true count if it already presents room metadata; avoid unrelated re-layout.
- [x] Focused tests demonstrate bot room with one observer = 1, duplicated tabs same user = 1 backend, count events/snapshots propagate, absent field unknown. No unrelated room actions/time controls changes.
- [x] Run relevant frontend tests including both hook specs if existing.

## Chunk 3: Integration and review

### Task 5: Real preview, specs, code quality and completion

**Files:**
- Update `docs/design/play-consistency-2026-10-09/README.md`
- Add implementation screenshots/review report in same design directory
- Update this plan's checkboxes/results

- [x] Use isolated Playwright browser routing fixtures to render actual React hall at 1024×600 with matching design data, count values (2/0/5) only in test fixtures. Capture games + players and focused invitation/placement, shared-shell correct. Reference/implementation/side-by-side/overlay/diff for games and players. Inspect actual Chinese fonts with CDP and console errors; arrows/icon shapes/touch geometry/black-white colors.
- [x] Verify main flows and backend counts with focused automated tests and a real in-process authenticated API session (existing test client is sufficient; no extra infrastructure). Strict box existing auth/bridge tests plus strict kiosk build are required gates.
- [x] Independent GPT-6-astra max spec compliance review first (approved HTML + this plan + actual diff/tests/images); fix must-fix findings. Then independent code quality + visual review using requesting-code-review skill. User requested independent agent max effort. Do not accept self-review as independent approval; no unrelated security fuzzing/full regression.
- [x] Final commands: scoped Vitest files for hall/spectator/room/hooks; backend focused count/spectator/lobby tests; `npm run build`; `npm run build:smartbox-kiosk-2d`; `git diff --check`. Stop testing when concrete risks/gates resolved.
- [x] Record results, implementation screenshots and limits (HTTP presence TTL). Report current branch, synced develop and deliverable link. Preserve unrelated work. No deployment/version claims without actual deployment. Commit reviewed coherent work only; no push/merge/deploy implicitly as part of this UI implementation.

## Ownership and sequencing

After plan approval, independent frontend and backend workers can proceed in parallel **only** with the fixed contract above and disjoint file ownership (user explicitly asks traditional parallel workflow). Frontend owns Task 3 + 4 UI files; backend owns Task 2 Python files. Root owns integration docs/images, coordinates contract, and reviews. No concurrent git commits from workers; root creates coherent commit after reviews. Spec and code review are sequential, can cover both tasks in one focused review each to honor proportionality.

## Plan review results

Round 1: one must-fix, HTTP membership changes/expiry need WS push in a quiet room. Fixed rule 6 and focused notification tests. Round 2 Approved; review recorded in `KIOSK-HALL-IMPLEMENTATION-PLAN-REVIEW.md`.


## Completion evidence — 2026-10-10

- Frontend + backend workers completed with disjoint ownership. Independent spec Approved, then code + actual visual Approved (reports in design directory).
- Root fresh checks: nine related Vitest files 152 passed; presence/spectator/lobby/chat-WS pytest 99 passed; normal build exit 0; strict kiosk build exit 0 with SSO/module boundaries clean; diff check exit 0.
- Actual React 1024×600 games+players captured, reference/side/overlay/diff compared; exact normal-state list/card geometry, Chinese Kai verified by CDP, unknown count behavior and unplaced invite/watch/return tested. Error layout document remains 1024×600 and main has no scroll overflow.
- Implementation remains on feature/admin-console. Release/deployment is outside this development slice; physical RK3562 remains on its previously deployed build.
