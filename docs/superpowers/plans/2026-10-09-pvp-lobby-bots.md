# Self-Owned PvP Lobby Bots Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one non-ranking self-owned Go lobby for Galaxy and Kiosk, with rank-matched virtual bot opponents and an audited admin control page.

**Architecture:** Keep idle bots as lightweight virtual identities; create a `WebSession` and KataGo work only for an actual game. The web process owns matchmaking, bot moves, and a bounded bot-vs-bot scheduler. The separate admin process exchanges configuration and a timestamped runtime snapshot through the existing `system_config` table. Both frontends consume the same public lobby contract and never receive a bot marker.

**Tech Stack:** FastAPI/WebSocket, SQLAlchemy, existing AI ladder recipes and `WebKaTrain`, React/TypeScript, Vitest, pytest, Playwright.

---

## Product contract and limits

- Source of rank truth: `AiLadderProfile.ai_ladder_rung`, not legacy `users.rank`. The playable catalog is derived from `katrain.core.ladder.LADDER_LEVELS` entries with a fitted, available recipe (currently 29). Show rank name and rung on public roster responses; do not reveal participant kind there.
- One matchmaking queue, no free/rated selector, and all self-owned PvP sessions have `game_type="free"`. The only rank-changing activity remains AI 升降级对弈. Match request for a user without a placed rung returns `PLACEMENT_REQUIRED`; the client shows a dialog leading to AI placement. Direct human invitations retain today's non-ranking behavior, including for unplaced users.
- A placed human waits briefly for another human at the **same** rung, then a free bot at that rung accepts. A bot invitation can start a game directly when the bot is free. The server rechecks participant, rank, availability and session capacity under one runtime lock before reserving either side. One real user cannot enter two games through simultaneous requests.
- Admin setting: `enabled=false` until an administrator explicitly saves it; `bot_game_limit=3`; per-playable-rung `idle_target=2` with accepted range 1..20. There must be at least `idle_target` **unreserved** virtual bots per rung while enabled. Bot-vs-bot games use two extra identities; they rotate across rungs, never occupy the reserve, and are bounded by `bot_game_limit` and a hard server safety cap of 6. Human games take priority over starting new bot games.
- Bot moves use the existing certified ladder recipe of the bot's rung, with a fresh randomized 5..30-second delay per turn. No strategy fallback to random or an uncalibrated model. Cap simultaneous bot move generation at 2; an engine failure marks the game stalled/degraded and is visible in admin, never silently substitutes a move. Release session resources on game end, cancellation, server stop and timeout. Idle bots have no engine or socket.
- Public user roster and active-game response expose only nickname, rank, presence/game fields and stable IDs. The admin response may identify human/bot. Nonparticipants cannot mutate bot games. Existing stranger spectating remains unavailable; neither UI promises a watch action.
- `system_config["pvp_lobby_bot_config"]` stores versioned config JSON and an increasing revision; `system_config["pvp_lobby_bot_runtime"]` stores a timestamped aggregate and participant snapshot with `applied_config_revision`. Admin treats snapshots older than 30 seconds as stale; it never calls configured targets “current idle.” Admin write and `AdminAuditLog` insert share one transaction. The UI distinguishes saved settings from settings applied by the web process.
- Deployment topology gate: central web and physical board mode currently each own a separate in-memory `LobbyManager` and DB. Central web is the only bot and match authority. Board mode must not start an independent bot population from its local SQLite. A physical Kiosk uses a local authenticated bridge to the central lobby and a local vision/LED mirror of the central room; the central room is authoritative for turns and result. Local and central user/session IDs are distinct. Strict Box SSO generation change invalidates the bridge and mirror. A two-process test with deliberately different IDs must prove vision bind and one physical move round-trip before calling the Kiosk slice complete or enabling bots in production.

### Shared wire contract (freeze before parallel work)

- `GET /api/v1/users/online`: `[{id, username, ladder_rung: number|null, rank_label: string|null, presence: "idle"|"playing"}]`. Stable public IDs are central IDs; bot IDs are negative. No `kind` or bot marker. Presence is the union of active lobby sockets and occupied active rooms, so a human remains visible after leaving the lobby for a game. Preserve legacy fields for existing clients during migration.
- `GET /api/v1/games/active/multiplayer`: retain current fields; add `player_b_id`, `player_w_id`, `player_b_rung`, `player_w_rung`, `player_b_rank_label`, `player_w_rank_label`. A game is visible while active; no public bot marker or spectator action.
- `/ws/lobby`: `start_matchmaking` needs no mode; old `game_type=free|rated` is accepted as the same non-ranking queue. `match_found` always reports `game_type=free`, central `session_id`, central participant IDs, and `my_color`; `stop_matchmaking` cancels. `PLACEMENT_REQUIRED` is returned for unplaced matching; invitations retain `INVITE_NOT_PENDING`. Bot invitations use the same `invite` request, with an immediate match if idle. `lobby_update` prompts roster/game refresh.
- Admin `GET /api/admin/pvp-lobby`: `config`, `config_revision`, `runtime:{reported_at,applied_config_revision,stale,active_bot_games,engine_errors,rungs:[{rung,rank_label,idle_target,idle_now,playing_now}]}`. `PUT .../config` uses `expected_revision`; stale writes return 409. `GET .../participants?page=&page_size=&kind=&presence=&q=` returns `items,total,page,page_size`; this endpoint alone includes `kind:"human"|"bot"`. Server caps `page_size` at 100.
- Physical Kiosk bridge: browser keeps calling box origin. Box validates current local SSO cookie/generation and uses that generation's remote access token, not the shadow user ID, for central REST/WS. A box-origin `GET /api/pvp/identity` response exposes the current **central** user ID to its own authenticated browser, so the Kiosk roster recognizes “me” even when the local shadow ID differs. Its local bridge maps `{generation,central_user_id,central_session_id,local_mirror_id,color}`. Initial room state and every room reconnect return `my_color` from this mapping; the Kiosk uses the central ID and session ID to identify and return to its own room. Central owns moves and result; the local mirror only feeds vision/LED and never settles games. Central token is never sent to the browser. Closing a lobby socket cancels its queue entry but preserves an active room mapping across navigation and reconnect. Only room end/expiry discards that room mapping; generation replacement/logout revokes every mapping and upstream connection for that generation. Network failure shows an explicit disconnected state and does not fabricate moves.

## File and ownership map

| Unit | Files | Responsibility |
| --- | --- | --- |
| Bot domain | Create `katrain/web/core/pvp_lobby_bots.py`; modify `katrain/web/session.py`, `katrain/web/server.py`, `katrain/core/ai.py`, `katrain/web/interface.py` | Pure rank/identity/scheduler decisions; authoritative runtime, AI candidate/commit boundary, multiplayer terminal lifecycle, match and invitation paths. |
| Public contract | Modify `katrain/web/models.py`, `katrain/web/api/v1/endpoints/users.py`, `katrain/web/api/v1/endpoints/games.py` | Safe rank and game projections, no bot identity field. |
| Admin API | Create `katrain/web/admin/routers/pvp_lobby.py`; modify `katrain/web/admin/app.py` | Validate, save, audit config; read complete paged roster and runtime snapshot. |
| Admin UI | Create `katrain/web/ui/src/admin/lobby/{LobbyPage.tsx,LobbyPage.css,types.ts}`; modify `AdminApp.tsx`, `AdminSidebar.tsx`, `adminPages.ts`, `api/client.ts` | Existing 80px/280px graphite/copper shell, KaiTi family, settings and status. |
| Galaxy/Kiosk | Modify `katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx`, `katrain/web/ui/src/kiosk/pages/LobbyPage.tsx` and their local CSS; add small shared API types if needed | Implement the approved HTML layouts and honest states without bot badges. |
| Physical Kiosk route | Focused bridge under `katrain/web/core/`, board-mode wiring in `server.py`, room/vision/LED ingress in `katrain/web/api/v1/endpoints/vision.py` and the existing game/WS paths; adapt Kiosk URL helper only if needed | Central lobby and room authority with local physical-board mirror; distinct IDs and SSO generation. |
| Tests | `tests/web_ui/test_pvp_lobby_bots.py`, `tests/web_ui/test_lobby_api.py`, `tests/web_ui/test_lobby_boundaries.py`, `tests/web_ui/test_admin_pvp_lobby.py`, `katrain/web/ui/src/{admin/lobby/LobbyPage.test.tsx,galaxy/pages/HvHLobbyPage.test.tsx,kiosk/pages/LobbyPage.test.tsx}` | Behavior and the highest-risk auth, placement, reservation, audit and cleanup boundaries. |

The three approved HTMLs in `docs/design/pvp-lobby-2026-10-09/` are the visual references. Fixture names/numbers belong only to those files and test fixtures. Delete any production fixture data after integration.

## Chunk 1: Foundation and authority

### Task 1: Lock the contract and correct the admin design font

**Files:** Modify `docs/design/pvp-lobby-2026-10-09/admin-lobby.html`; create `katrain/web/core/pvp_lobby_bots.py`; test `tests/web_ui/test_pvp_lobby_bots.py`; freeze the shared wire contract in this plan.

- [ ] Change the admin HTML font stack to the existing admin app's `"Kaiti SC", "STKaiti", "KaiTi", "LXGW WenKai", serif`; keep its 80px top and 280px side geometry. Preview once at 1440×900.
- [ ] Write failing pure tests for catalog derivation, ID/name uniqueness, config limits, rank-local idle reserve, rotation selection, and 5..30-second delay selection. Run `CI=true pytest tests/web_ui/test_pvp_lobby_bots.py -q`; verify each targeted failure is caused by the absent behavior.
- [ ] Implement small pure functions/dataclasses in `pvp_lobby_bots.py`: `playable_rungs()`, `validate_config()`, `bot_id(rung, slot)`, `bot_name(rung, slot)`, `choose_next_rung()`, `next_move_delay()`. Example accepted config: `{"version":1,"enabled":false,"bot_game_limit":3,"idle_targets":{"1":2}}` (fill omitted playable rungs with 2; reject unknown rungs). Keep runtime session management out of these pure functions. Resolve field naming against the shared wire contract above before dispatching parallel agents.
- [ ] Run the targeted test and commit this unit after green.

### Task 2: Public lobby contract and rank truth

**Files:** Modify `katrain/web/models.py`, `katrain/web/api/v1/endpoints/users.py`, `katrain/web/api/v1/endpoints/games.py`; extend `tests/web_ui/test_lobby_api.py`, `tests/web_ui/test_lobby_boundaries.py`.

- [ ] Test first: placed human online row uses `AiLadderProfile.ai_ladder_rung` and canonical rank name; unplaced row has `ladder_rung=null`; bot rows have no `is_bot`/`kind` key; active game has participant IDs/ranks; no password, UUID or credits leak. Run those cases and see expected failures.
- [ ] Read rank from the shared session factory in one batched query. Add optional `ladder_rung` to the narrow `OnlineUser` response. Merge online humans with `app.state.pvp_lobby_bots.public_online_rows()` only when the runtime is available. Keep existing authentication and room ownership guards.
- [ ] Add IDs and rank labels to `/api/v1/games/active/multiplayer`, preserving existing string keys. Return only self-owned sessions; keep bot kind internal. Run targeted tests, then commit.

### Task 3: Server matchmaking, bots and game lifecycle

**Files:** Modify `katrain/web/session.py`, `katrain/web/server.py`, `katrain/core/ai.py`, `katrain/web/interface.py`; create focused helpers in `katrain/web/core/pvp_lobby_bots.py`; extend `tests/web_ui/test_pvp_lobby_bots.py`, `tests/web_ui/test_lobby_sso_websocket.py`, `tests/web_ui/test_lobby_boundaries.py`.

- [ ] Write failing tests for: all match requests require a placed rung; same-rung human pairing; human-first wait then bot; duplicate queue request/disconnect cleanup; bot invite; reserve count under simultaneous match/rotation; bot-bot cap and rung rotation; no rank/elo mutation; protected bot seat; bot session cleanup; engine failure and stale/cancelled move never commit. Run red tests before code.
- [ ] Replace free/rated queue choice with a single rung-keyed queue. Validate rung using `AiLadderProfile` server-side at request time. Reject legacy `rated` or normalize it to the non-ranking queue **without** creating a ranked game; add a compatibility test for old clients. Keep direct human invitation flow and pending-invite protection.
- [ ] Build an in-process `PvpLobbyBotRuntime` owned by the central web app. Idle identities are data only. Add a bot-vs-bot scheduler that chooses one eligible rung at a time. Extract a generation-only AI_LADDER candidate step from `generate_ai_move` without changing existing callers; run it in a bounded thread (max two). Never hold a session/runtime lock while waiting for engine output. In the existing game commit lock, recheck node, turn, terminal state, session membership and reservation generation, then call `game.play`. Cancellation and deletion invalidate the generation under that same boundary. Test a deleted session and cancelled reservation while generation is in flight. Drive each next turn after an independent 5..30-second delay; no busy spin.
- [ ] Use `SessionManager.create_multiplayer_session(..., initial_game_type="free", skip_initial_analysis=True)` for active games only. Set participant IDs (virtual bot IDs are negative), seat names, and bot metadata on the server session. Suppress automatic per-move analysis and auto-AI scheduling for bot sessions; runtime alone schedules bounded bot turns. Add an action allowlist for a human participant in bot sessions: normal move/pass, resign/leave, scoring request/accept and state read; reject new-game, seat/config/swap and other mutation paths that break the certified bot recipe. Test the participant boundary.
- [ ] Add one idempotent bot-session terminal path for two passes, scoring, resignation, leave, timeout and shutdown. A bot accepts a valid scoring proposal according to the central rule without waiting for a socket. Persist the real user's game history once, broadcast final state, cancel workers, invalidate reservations and free engine/session resources. Verify a bot's second pass and a human scoring request. Disabling the population stops new pairing/bot games but lets existing games finish; lowering the game cap lets existing games finish and blocks replacements. A stalled game remains visible as degraded for a bounded 10-minute recovery window, then ends with an explicit abort and cleanup.
- [ ] Poll config from `system_config` and publish a timestamped runtime snapshot at most every 10 seconds, including `applied_config_revision`. Start only on the central server-mode owner; assert a single owner in the deployment topology. Expose engine failure and active bot-game counters. Stop and free tasks on lifespan shutdown. Run focused backend tests and commit.

## Chunk 2: The two user journeys

### Task 4: Galaxy lobby

**Files:** Modify `katrain/web/ui/src/galaxy/pages/HvHLobbyPage.tsx` and its focused CSS; extend `HvHLobbyPage.test.tsx`.

- [ ] Test first: one quick-match action; placement dialog only on match; same-rung roster filter; no bot label; no clickable stranger-watch action; room return for own game; invitation remains usable for unplaced users; cancel clears timer and sends stop. Run `npm test -- --run src/galaxy/pages/HvHLobbyPage.test.tsx` from `katrain/web/ui` and verify red.
- [ ] Implement approved `galaxy-lobby.html` hierarchy inside current Galaxy shell. Consume public `ladder_rung` and player IDs rather than matching names. Show loading/error/empty states. Route placement CTA to `/galaxy/play/ai?mode=rated`. Do not echo backend `kind` if a future API accidentally adds it.
- [ ] Run targeted Vitest and one real 1440×900 preview against a local backend/fixture API; compare reference, implementation, side-by-side and overlay/diff. Commit when aligned.

### Task 5: Kiosk lobby

**Files:** Modify `katrain/web/ui/src/kiosk/pages/LobbyPage.tsx` and kiosk lobby CSS; extend `LobbyPage.test.tsx` and `katrain/web/ui/tests/kiosk-screen-06-lobby.fourup.spec.ts` only for changed states.

- [ ] Test first: single non-ranking match action, placement dialog, two-column list, same-rung filter disabled while unplaced, invite remains usable, no bot badge or fake watch control, own-room return, matching cancel. Run `npm test -- --run src/kiosk/pages/LobbyPage.test.tsx` and verify red.
- [ ] Implement approved `kiosk-lobby.html` at 1024×600 in the real shell. Use canonical rank fields and public IDs; preserve existing guest and invitation states. Route placement CTA to the existing Kiosk AI ladder route.
- [ ] Run targeted Vitest and one 1024×600 real preview; compare reference, implementation, side-by-side and overlay/diff. Commit when aligned.

### Task 6: Physical-box route to central lobby

**Files:** Add a small authenticated box bridge under `katrain/web/core/`; modify `server.py` board-mode lobby/room ingress, `katrain/web/api/v1/endpoints/vision.py` and physical-move/LED integration points, plus Kiosk URL helper only if required; tests `tests/web_ui/test_lobby_sso_websocket.py` and a two-process smoke check.

- [ ] Reproduce the current split by verifying Galaxy server mode and physical Kiosk board mode have distinct `LobbyManager` instances and SQLite/central DB. Record exact route and token behavior.
- [ ] Test a physical Kiosk user entering the same central roster and receiving a central `match_found`/room URL, including auth failure and network outage. Use distinct shadow and central user IDs. Observe red before implementation.
- [ ] Implement the bridge contract above: validate the local strict SSO generation on every box request, reuse the generation's remote credential server-side, proxy central lobby REST/WS, expose `GET /api/pvp/identity` to this browser, map central session to a local vision/LED mirror, and forward physical moves to central. Preserve the room mapping when the lobby socket closes during navigation. Drive physical opponent-stone LED guidance from the mapped opponent color even when both public seats are human; never use a public AI/bot marker for this. Do not run bot scheduler or persist multiplayer results in board mode. Preserve offline local-play and other board API routes.
- [ ] Run two-process/physical-box check for central ID different from shadow ID; exercise the actual `match_found → navigate → room WebSocket → vision bind` path, room refresh/reconnect and return to own room. Check one physical move to central and one central opponent move → local LED guide → stone placement confirmation. Exercise generation replacement and remote disconnection. If central room traffic cannot work, report this as a blocking integration issue before release; do not replace it with local fake bot state.

## Chunk 3: Admin journey and integration

### Task 7: Audited admin API

**Files:** Create `katrain/web/admin/routers/pvp_lobby.py`; modify `katrain/web/admin/app.py`; test `tests/web_ui/test_admin_pvp_lobby.py`.

- [ ] Write failing tests for admin-only read/write, exact 29-rung validation, 1..20 targets, 0..6 bot-game limit, stale runtime, complete paged human/bot roster, and atomic config-plus-audit rollback. Run red.
- [ ] Implement `GET /api/admin/pvp-lobby` and `PUT /api/admin/pvp-lobby/config` with `get_current_admin`, Pydantic `extra="forbid"`, transaction-bound `AdminAuditLog`. Include `expected_updated_at` for stale edit conflict or an equivalent version check. Derive current counts from runtime snapshot, targets from config. Return a clear `stale` state and never infer “healthy” merely from config presence.
- [ ] Implement `GET /api/admin/pvp-lobby/participants?page=&kind=&presence=&q=` using paged users and virtual bot snapshot. Admin only response contains `kind`. Commit after targeted tests.

### Task 8: Admin React page

**Files:** Create `katrain/web/ui/src/admin/lobby/{LobbyPage.tsx,LobbyPage.css,types.ts,LobbyPage.test.tsx}`; modify `AdminApp.tsx`, `AdminSidebar.tsx`, `adminPages.ts`, `api/client.ts`.

- [ ] Test first: navigation, initial load/error/stale state, draft changes without changing current counts, save/conflict/reload, disabled control when runtime stale, roster filters/paging, bot badges only here. Run red.
- [ ] Implement `admin-lobby.html` within existing Admin shell. Use its KaiTi stack (`"Kaiti SC", "STKaiti", "KaiTi", "LXGW WenKai", serif`), graphite/copper palette and large shell dimensions. Remove fixture data from production component. Include exact runtime status from API and audited save feedback.
- [ ] Run targeted Vitest and one real 1440×900 preview with same-size visual comparison. Commit.

### Task 9: Integration and release readiness

**Files:** Tests and existing docs only as needed; no test-only production hooks.

- [ ] Run focused backend suites (`CI=true pytest tests/web_ui/test_pvp_lobby_bots.py tests/web_ui/test_lobby_api.py tests/web_ui/test_lobby_sso_websocket.py tests/web_ui/test_lobby_boundaries.py tests/web_ui/test_admin_pvp_lobby.py -q`) and focused frontend tests; run `npm run build` and Kiosk build once.
- [ ] Exercise real localhost flows with two human accounts: placement block, same-rung human pairing, delayed bot pairing, bot invitation, bot-vs-bot rotation and live move timing, no bot marker in either user UI, admin roster marking, disable/enable and stale snapshot. Confirm a rank/profile before and after remains unchanged.
- [ ] Measure process RSS, CPU, engine request count and queue depth with bot population configured and three bot games running for a representative period. Record the observed numbers and any engine-capacity limit; no claim of “lightweight” without this measurement.
- [ ] Remove temporary fixtures from production, compare the three implementations against approved HTML at target viewports, and request independent spec and code review. Fix important findings and rerun only affected checks. Keep bot deployment disabled by default until the user approves activation.

## Parallel execution and review handoff

After this plan's independent review, prepare isolated worktrees from the approved plan commit. Run Task 1 first to freeze the public/admin contract. Then dispatch disjoint implementation agents in parallel: backend/runtime (Tasks 2–3), Galaxy/Kiosk UI (Tasks 4–5), and admin API/UI (Tasks 7–8). Task 6 follows the backend contract because it touches the same server and room paths; it may proceed while UI agents run, but does not share edited files concurrently with Task 3. Agents own separate branches and files; integrate commits sequentially into `feature/admin-console`, resolve conflicts, run focused tests, and request a `gpt-6-astra` max-effort independent code review plus `superpowers:requesting-code-review`. Fix until both pass. User approval of visual implementations is required before broad backend release or enabling bots; the HTMLs already received approval with only the KaiTi correction requested.
