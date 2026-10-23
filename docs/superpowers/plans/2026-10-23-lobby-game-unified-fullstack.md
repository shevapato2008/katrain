# Lobby Game Unified Fullstack Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the approved 06a 大厅对局 layout with real private, read-only territory requests and preserve authoritative online play/scoring.

**Architecture:** Keep `GamePage` and existing game-session/count/exit flows. Add a narrow territory endpoint using the current KataGo HTTP client and authoritative multiplayer tree, forwarded through the existing authenticated box-room bridge; expose only ownership, never suggestions/winrate or a terminal result. Add a lobby-only presentation component/hooks and scoped CSS, without modifying free/ladder/local/OGS presentation or general analysis permissions.

**Tech Stack:** Existing FastAPI/Python sessions and KataGo client; React/TypeScript, kiosk shared shell, Vitest and Playwright.

---

## Approved design and constraints

- Source (read-only sibling repository): `/Users/fan/Repositories/katrain-kiosk-ui-redesign/docs/design/kiosk-current-based-redesign-2026-10-14.html#game-lobby`, `kiosk-unified/game.{js,css}`, `core.css`, `tactile.css`, and `KIOSK-UNIFIED-REDESIGN-RULES-2026-10-14.md`.
- Accepted image: `/Users/fan/Repositories/katrain-kiosk-ui-redesign/output/playwright/lobby-game-four-actions-1024.png`. User already approved its appearance and four actions; no further design gate is required.
- At 1024×600: board 516×516 at (16,70), rail 460×516 at (548,70), 8px rail gap, header 62px, paired 104px equal trapezoid seats, 152px status panel, 54px toggle row, 50px action row and footer. Chinese 18/22/28px, existing mono for numerical values. Four actions in order 领地/数子/停一手/认输, each 109×50 and 8px gap. 坐标/手数 match those button dimensions. The territory icon matches the approved 05 AI game artifact: reuse existing `map-trifold`, distinct from coordinates `grid-nine` (the legacy production AI icon is outside scope).
- Bind names, colors, captures, turn, rules, threshold and status to actual state. No fixture user/scenario controller in production. Existing initial empty state is legitimate but must not force an empty board.
- Preserve physical-board synchronization, count negotiation, degraded auto-count retry, official end result, turn enforcement, leave/resign dialogs, session disappearance and central reconnect. A territory error must never claim success or block continuing a legitimate game.
- Scope is local implementation and evidence only. No push, merge to develop, deployment, service restart or external messages. Base `5016186ed` includes `fb19e95c2`; preserve both. Worktree: `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/lobby-game-unified-20261023`, branch `feature/lobby-game-unified-20261023`.
- Baseline: `GameControlPanel.test.tsx` + `.clock.test.tsx` = 45 passing. Shared `PhysicalBoardGuard.test.tsx:62` text mismatch is already known; no unrelated changes. Reuse existing local node_modules/.venv via ignored symlinks.

## Source findings and contract

- Current `GameControlPanel.tsx` still renders sequential `PlayerRow`s for online/local and `SeatRow`s for AI; all use legacy `.pcard` styling. The approved paired design is in the sibling artifact, not this base's production AI component. Port the minimal paired surface only for lobby, without expanding to other modes.
- Physical `pvp_lobby` is a local mirror; authoritative central human multiplayer uses `game_type=free` with two participant IDs and `pvp_lobby_human_session=True`. `guard_bot_mutation` intentionally blocks general analysis on the mirror. Do not relax it.
- Existing `/api/analysis/current` returns broad async state and is unsuitable for a private ownership-only request. Existing ranked territory already uses `app.state.router.local_client.analyze` and validates ownership, but has quota/reservation rules specific to ranked. Reuse the engine/client semantics, not ranked lifecycle or quota storage.
- New narrow `POST /api/pvp/territory` request: `{session_id: string}` only. Browser never supplies SGF, stones, user/color or engine settings. Response: `{session_id, game_id, current_node_id, move_count, board_size:[number,number], ownership:number[], black_area:number, white_area:number, stale:boolean}`. All ownership values finite, within [-1,1], exactly board width×height. Ownership is row-major from top-left (KataGo), converted to existing `EngineOverlay` bottom-origin row coordinates.
- Authentication required. For a mirror, require its participant and live box generation, resolve mapped central ID through `PvpBoxBridge.forward_action`, let central authorize again, and return its private payload with local session ID. Never call `apply_pvp_box_state` for territory, as response has no `state`.
- At authority allow only active ordinary lobby human-vs-human multiplayer, current user one of `player_b_id`/`player_w_id`, positive IDs, free game, no certified bot, platform engine, OGS, rated/ranked or local single-user session. Existing pending-ranked-game guard applies. Reject terminal/awaiting-count games honestly (409), including `terminal_result` and `pvp_lobby_awaiting_count`, not only `current_node.end_state`. Do not require it to be caller's turn: read-only territory is explicitly available during either turn.
- Under session lock snapshot tree identity/current node, board/rules/komi and replayable setup/moves (`nodes_from_root`, placements and moves, as in `core/engine.py` request payload); use server-owned tree only. Use the same `game_id` and `id(current_node)` identifiers as `get_state`. Release lock before awaiting bounded engine analysis. Reuse `temporary_analysis_lease` from `ranked_session_guard.py` without retaining threading locks over await; its finally releases activity on success, failure and cancellation. Reject unavailable/invalid/timeout with 503 (retry permitted), overlapping same-session request with 409 if a minimal single-flight guard is necessary.
- Do not write node analysis, end state, count requests, game records, clock, SGF or broadcast analysis. Recheck participation/pending ranked guard and position after await; stale response is marked and never painted. Bounded analysis uses maxVisits 200, includeOwnership true, includePolicy false; no PV/winrate/score in response.
- Client scope is session+game+node+move count. A response after move/session switch/end/disconnect is ignored/cleared. First click requests with visible loading, errors offer retry, successful overlay can be hidden/re-requested without pretending to have a current answer after a move. No automatic per-move request or new quota. Formal result still uses current count flow.

## Chunk 1: One lobby game journey

### Task 1: Private authoritative territory and box forwarding

**Owner:** backend implementer, independent of Task 2 UI files.
**Files:**
- Modify `katrain/web/server.py` (narrow route and existing guards/activity integration).
- Create `katrain/web/core/pvp_territory.py` only if it keeps replay/validation focused; avoid generic frameworks.
- Modify `katrain/web/core/pvp_box_bridge.py` only if current `forward_action` cannot preserve the response contract (it already rewrites IDs).
- Create `tests/web_ui/test_pvp_territory.py`; add focused cases in `tests/web_ui/test_pvp_box_routes.py` if reuse of its fixture is clearer.

- [ ] Add failing contract tests with deterministic fake analyzer: real server tree snapshot; authenticated B or W can request; anonymous/outsider and non-lobby game denied; mirror forwards current mapped central ID.
- [ ] Add focused error/read-only cases: engine unavailable/invalid output; move/end during await; no analysis/end/count/record mutation or broadcasts; single-flight/activity cleanup if added; stale box generation rejected after await. Bound to new endpoint rather than auditing all existing APIs.
- [ ] Run `./.venv/bin/python -m pytest -q tests/web_ui/test_pvp_territory.py` and record intended failure before implementation.
- [ ] Implement the endpoint and focused helper using existing engine and bridge. Use FastAPI's established body model (`ToggleAnalysisRequest` is already session_id-only) and existing HTTPException patterns.
- [ ] Run focused tests and existing `tests/web_ui/test_pvp_box_routes.py` + `tests/web_ui/test_ai_ladder_territory.py` as appropriate. Expected all pass; no GPU needed for fake analyzer contracts.
- [ ] Self-review and commit only owned files, report contract, tests, SHA and any concern to controller.

### Task 2: Lobby presentation and real territory UI

**Owner:** frontend implementer, can run in parallel with Task 1 against fixed contract above.
**Files:**
- Modify `katrain/web/ui/src/kiosk/pages/GamePage.tsx` and `components/game/GameControlPanel.tsx` only as needed to route lobby to new presentation and hook; preserve all original action handlers.
- Create `katrain/web/ui/src/kiosk/components/game/LobbyGamePanel.tsx` and `katrain/web/ui/src/kiosk/hooks/useLobbyTerritory.ts` (or comparable focused feature paths) with focused tests.
- Add typed call/result to `katrain/web/ui/src/api.ts`.
- Add lobby-scoped styles in `katrain/web/ui/src/kiosk-shell/go-screens.css` or a dedicated stylesheet imported by lobby component; do not restyle `.pcard`/shared toggles globally.
- Add focused component/hook/GamePage tests. Add `katrain/web/ui/tests/kiosk-screen-06a-lobby-game.spec.ts` for actual browser assertions and screenshots; fixtures confined to tests.

- [ ] Add failing hook tests proving loading/error/retry, current-answer overlay conversion, suppression of late answers across node/game/end/disconnect changes, no duplicate requests and no request on mount/move.
- [ ] Add failing UI/integration cases: four actions/order; real names/my-side/turn/captures; pass disabled outside own turn; no hints/chart/undo; threshold and count-request states; hooks call new endpoint (not help-only); existing count/respond and resign/leave handlers still invoked.
- [ ] Run relevant focused Vitest commands from `katrain/web/ui`; expect tests fail for missing new behavior.
- [ ] Implement typed API/hook; use existing auth transport and `EngineOverlay`. Keep error/loading within status area, explicitly explain reference-only versus official count. Clearing/hiding territory must not alter game state.
- [ ] Port approved paired seat surfaces and fixed-size lobby controls. Use existing Icon semantic (`map-trifold`), soft-button treatment and fonts. Header title 大厅对局. Use real central reconnect state; retain current full-page reconnect branch if authoritative board cannot safely be shown, document it as an honest operational state rather than inventing a connected board.
- [ ] Integrate existing `statusSlot`, opponent count confirmation and result flows without losing urgent identity/count/hardware state. Keep status readable within rail; do not let territory hide count cooperation or real errors. Keep four-button geometry in normal play; cooperation/reconnect may use their existing meaningful controls.
- [ ] Run focused Vitest including GameControlPanel / GamePage variants, ranked territory and local/free behavior touched by integration. Expected no introduced failures.
- [ ] Self-review and commit only owned files; report command results/SHA/concerns to controller.

### Task 3: Integrated verification and local delivery

**Owner:** controller via fresh integration/verification worker as needed; no additional feature design.
**Files:** plan checkboxes, review documents and `docs/superpowers/reviews/2026-10-23-lobby-game-unified-fullstack-verification.md`; screenshot artifacts under `output/playwright/lobby-game-unified/` (normal repo ignore policy).

- [ ] Spec compliance reviewer independently reads final implementation against this contract/design before quality review; fix material mismatches with original implementer and recheck.
- [ ] Run exact focused backend/UI tests once integrated and `npm run build:smartbox-kiosk-2d`. Do not add a new test framework or run all unrelated suites.
- [ ] Run browser test using `KATRAIN_PW_VISUAL_PORT=5187 npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-06a-lobby-game.spec.ts --workers=1` (use another free unique port if occupied). Use stubbed authenticated game socket/API only in tests and exercise real React runtime at 1024×600. Check normal my/opponent turn, territory error/retry/result/stale-on-move, and one meaningful scoring/disconnected state as supported by existing harness; keep scope proportional.
- [ ] Capture representative runtime screenshot, reference at same dimensions, side-by-side and overlay/difference; inspect actual images, record composition, geometry, font/color/material/icon/text/state differences. Test asserts board (16,70,516,516), rail (548,70,460,516), action/toggle 109×50, gap 8, no document/rail overflow. Layout tests alone are not visual approval. Accepted design already authorizes implementation; no additional user gate.
- [ ] Astra Max independent final code-quality review (`gpt-6-astra`, max, fresh context) of all commits against base 5016186ed, focusing on auth/read-only/staleness/contracts and likely online/free/ladder/local regressions. Fix material findings and re-review until approved; record outcome.
- [ ] Mark checklist according to evidence, document engine-mocked validation limitations and unchanged known baseline failure. Restore generated static/build files if they are build artifacts not intended source changes.
- [ ] Commit documentation/evidence references. Preserve separate main-worktree investigation note if it appears. Retain isolated branch/worktree; report exact commits and artifacts to root. Local fast-forward integration only if root explicitly coordinates it and current tree remains safe. No remote/deploy action.

## Review policy

Plan: independent Astra Max review, at most two rounds of review/revision, converge to actionable scope. During implementation follow @superpowers:subagent-driven-development, proportionate TDD for behavioral contracts, spec review then independent quality review. Final claims require @superpowers:verification-before-completion evidence. Do not repeat unrelated verification or expand this slice.

## Plan review outcome

Astra Max independently checked relevant source and approved the plan on 2026-10-23 (one round). Incorporated precise lease reuse, approved map-trifold icon, get_state identity semantics, and terminal/awaiting-count checks. See `docs/superpowers/reviews/2026-10-23-lobby-game-plan-review.md`.
