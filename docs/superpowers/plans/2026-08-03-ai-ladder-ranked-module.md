# AI Ladder Ranked Module Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the authoritative 41-rung ranked-AI journey across Galaxy and kiosk without modifying the concurrently calibrated catalog.

**Architecture:** UI consumers use one shared `AiLadderStatus` contract whose catalog projection is limited to `rung`, `rank_name`, `certification_status`, `availability`, and `route`. The first chunk is a removable-fixture Galaxy vertical slice and ends at visual approval; the second chunk replaces the fixture with transactional server state, wires settlement and kiosk, then verifies the real journey.

**Tech Stack:** React 19, TypeScript, MUI, Vitest/Testing Library, Playwright CLI, FastAPI, Pydantic, SQLAlchemy, pytest.

**Approved spec:** `superpowers/tracks/golaxy-ai-ladder-parity/2026-08-03-41-tier-ai-ladder-finalization-design.md` section 6 plus the user-confirmed rules in this task.

**Catalog ownership:** `katrain/core/ladder.py` and every calibration/experiment path are read-only in this branch. Product code consumes `LADDER_LEVELS` through query helpers and never copies names, recipes, certification, availability, or routing data.

---

## Chunk 1: Galaxy visual slice (stop for user confirmation)

### Task 0: Correct the approved information architecture

The supplied production reference establishes that ranked AI is the existing `/galaxy/play/ai?mode=rated` child flow under 对局. The 41-rung contract replaces the rated flow's HumanSL rank control; it is not a standalone Dashboard module. This correction supersedes the Dashboard mounting point in Task 2 while preserving the shared card and removable fixture.

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/Dashboard.tsx`
- Delete: `katrain/web/ui/src/galaxy/pages/Dashboard.aiLadder.test.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.test.tsx`
- Create: `katrain/web/ui/src/features/aiLadder/AiLadderSetupOpponent.tsx`
- Create: `katrain/web/ui/src/features/aiLadder/AiLadderSetupOpponent.test.tsx`
- Modify: `katrain/web/ui/src/features/aiLadder/copy.ts`
- Modify: `docs/superpowers/visual-reviews/2026-08-03-ai-ladder-galaxy.md`

- [x] Write failing tests proving the rated preview stays at `mode=rated`, replaces the HumanSL strategy/rank slider with the 41-rung status, disables the legacy start action, and leaves free play plus rated-without-preview unchanged.
- [x] Add a compact setup opponent summary using the shared status contract and mount it only for `DEV + mode=rated + ai-ladder-demo=<supported-state>` inside the existing 对手与时间 panel; keep the full net-score/recent-five card for the personal profile.
- [x] Restore Dashboard to its pre-slice behavior and delete its obsolete fixture test; keep the fixture isolated for the rated setup preview only.
- [x] Capture the supplied production setup reference and corrected implementation at the same content viewport; regenerate implementation, side-by-side, overlay, and difference evidence for all six states.
- [x] Run the focused/regression suites, scoped ESLint, production build, and fixture-absence check; request independent spec and quality reviews.
- [x] Commit the correction separately from `6435ee63`, exclude `output/`, report both SHAs in cherry-pick order, and stop again for visual approval.

### Task 1: Shared presentation contract and status card

**Files:**
- Create: `katrain/web/ui/src/features/aiLadder/types.ts`
- Create: `katrain/web/ui/src/features/aiLadder/copy.ts`
- Create: `katrain/web/ui/src/features/aiLadder/AiLadderStatusCard.tsx`
- Create: `katrain/web/ui/src/features/aiLadder/AiLadderStatusCard.test.tsx`

- [x] Write failing component tests for placement `3/5`, placed rung, signed net score `-2…+2`, distinct recent-five markers, pending settlement, route, loading, unavailable, retry, and CTA labels. Assert forbidden internal/星阵 terms are absent.
- [x] Run `npm test -- --run src/features/aiLadder/AiLadderStatusCard.test.tsx`; confirm failure because the component does not exist.
- [x] Implement the smallest accessible card and centralized Chinese fallback copy: text accompanies color, progress has an accessible label, CTA is at least 44px, and no internal recipe/model/visits or 星阵 naming is rendered.
- [x] Re-run the focused test and confirm it passes.

### Task 2: Isolated demo fixture and Galaxy mounting point

> Superseded by Task 0: the fixture is mounted in the existing rated AiSetup child flow, not Dashboard.

**Files:**
- Create: `katrain/web/ui/src/features/aiLadder/__fixtures__/galaxyDemo.ts`
- Modify: `katrain/web/ui/src/galaxy/pages/Dashboard.tsx`
- Create: `katrain/web/ui/src/galaxy/pages/Dashboard.aiLadder.test.tsx`

- [x] Write a failing dashboard test proving `DEV + ?ai-ladder-demo=<state>` displays the fixture card and its CTA routes to `/galaxy/play/ai?mode=ai_ladder_ranked`; no demo query retains the current dashboard for both authenticated and anonymous users.
- [x] Run the focused dashboard test and confirm the expected missing-card failure.
- [x] Mount the card above existing module cards. Read the fixture only when `import.meta.env.DEV` and `?ai-ladder-demo=<state>` are both present; the demo query intentionally supplies the preview identity/status without changing `AuthContext`. Otherwise leave production behavior unchanged until the API exists.
- [x] Re-run the two focused suites and the existing Dashboard/sidebar/AiSetup suites.
- [x] Run `npm run build` and confirm the production bundle succeeds.

### Task 3: Exact-viewport visual evidence

**Files:**
- Create locally, do not commit: `output/playwright/ai-ladder-galaxy/reference.png`
- Create locally, do not commit for each `placement|placed|pending|unavailable|error|loading`: `implementation-STATE.png`, `side-by-side-STATE.png`, `overlay-STATE.png`, `diff-STATE.png`
- Create: `docs/superpowers/visual-reviews/2026-08-03-ai-ladder-galaxy.md`

- [x] Start only the Vite dev server on a non-8000 port and intercept auth/translation calls; do not start or contact the KataGo service.
- [x] Capture the current Dashboard as the explicit existing-product Artifact/reference at 1440×900.
- [x] Capture placement, placed, pending-settlement, unavailable/retry, and loading/error implementations at exactly 1440×900.
- [x] Generate side-by-side, 50% overlay, and pixel-difference images for every stable state from equal-size captures.
- [x] Record composition, geometry, hierarchy, typography/color/material, icons/assets, copy, state semantics, loading/error/retry, and fixture deletion condition.
- [x] Commit the plan, visual-review document, and visual-slice code as a single-purpose commit; exclude `output/`. Report its SHA and screenshot paths, then stop for explicit visual approval.

## Chunk 2: Authoritative integration after visual approval

### Task 4: Transactional ladder state and deterministic placement

**Files:**
- Modify: `katrain/web/core/models_db.py`
- Modify: `katrain/web/core/migrations.py`
- Create: `katrain/web/core/ai_ladder_ranked.py`
- Create: `tests/web_ui/test_ai_ladder_ranked.py`

- [ ] Write failing tests asserting the exact 41 names from `LADDER_LEVELS`, with no second name table.
- [ ] Write failing placement tests: old `20k…1k → 1…20`, old `1d…9d → 22,24,…38`, higher clamped to 38; `start=clamp(mapped-16,1,10)` and `[start,start+31]`; no old rank gives `[1,32]`; five updates use `mid=floor((lo+hi)/2)`, win `lo=mid+1`, loss `hi=mid`, and inconclusive consumes no round.
- [ ] Write failing post-placement tests for ±3 single-step/reset, 1/41 saturation, 3–2 recent-form independence, game-type/certification/availability gates, replay idempotency, forced rollback, and proof that legacy `User.rank`/`net_wins` never change.
- [ ] Implement one-to-one `AiLadderProfile(user_id, ai_ladder_rung nullable, placement_lo, placement_hi, placement_completed, net_score, version/timestamps)` and `AiLadderGameLedger(game_id unique, user/color/result, game_type, opponent rung plus catalog/config/certification snapshot, settled_at)`.
- [ ] Implement one repository method that locks/loads the profile, inserts the unique ledger row, and updates placement/rung/net score before one commit; every exception rolls back both rows.
- [ ] Run the focused pytest suite and migration tests; commit the database/domain slice.

### Task 5: Stable API and trusted settlement path

**Files:**
- Create: `katrain/web/api/v1/endpoints/ai_ladder.py`
- Modify: `katrain/web/api/v1/api.py`
- Modify: `katrain/web/server.py`
- Modify: `katrain/web/models.py`
- Modify: `katrain/web/core/user_game_repo.py`
- Modify: `katrain/web/core/repository.py`
- Modify: `katrain/web/core/remote_client.py`
- Create: `tests/web_ui/test_ai_ladder_api.py`

- [ ] Write failing catalog compatibility tests that make legacy `/api/ladder-rungs` delegate to the new projection and assert both surfaces cannot diverge.
- [ ] Write failing API tests for status/catalog/loading-retry semantics, pending settlement, and rejection of client-authored/ordinary/unavailable results.
- [ ] Write failing start/settlement tests for an immutable server session snapshot containing `game_type=ai_ladder_ranked`, user id/color, opponent rung, rank name, certification, availability, route, and configuration digest; reject runtime model/config identity mismatches without adjacent-rung or ordinary-AI fallback.
- [ ] Implement authenticated catalog/status/start endpoints. Generate one stable game id before persistence; pass it through local or remote `user_games_create`, then invoke settlement on the same authoritative server only after the game row exists. The settlement repository owns its transaction and the game id is the ledger idempotency key.
- [ ] Run API, autosave, ranked-rule, and ladder-injection suites; commit the API/settlement slice.

### Task 6: Replace fixture, implement kiosk parity, and verify

**Files:**
- Modify: `katrain/web/ui/src/api.ts`
- Modify: `katrain/web/ui/src/context/AuthContext.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/Dashboard.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx`
- Delete: `katrain/web/ui/src/features/aiLadder/__fixtures__/galaxyDemo.ts`
- Modify: `katrain/web/ui/src/kiosk/components/settings/AccountSection.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx`
- Add/modify matching Vitest and Playwright coverage.

- [ ] Write failing integration tests for shared Galaxy/kiosk state, placement/ranked CTAs, server-issued start payload, local/server route label, unavailable/retry fail-closed behavior, immediate post-settlement refresh, and absence of fixture data from production builds.
- [ ] Replace the demo fixture with the real API hook; make Galaxy `AiSetupPage` and kiosk `AiSetupPage` start only through the ranked start endpoint; reuse the shared card contract in kiosk without importing Galaxy code.
- [ ] Run exact commands: backend focused suites `python -m pytest tests/web_ui/test_ai_ladder_ranked.py tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_ai_game_autosave.py tests/web_ui/test_ranked_rules.py`; UI `npm test -- --run src/features/aiLadder src/galaxy src/kiosk`; `npm run build`; `npm run build:kiosk-2d`; `npm run verify:kiosk-2d`; and the named AI-ladder Playwright spec on an application port other than 8000. Expect zero new failures and explicit PvP/ordinary-AI non-effect assertions.
- [ ] If a real `fan` login and deployed Galaxy/kiosk are available, execute the specified persistence, ±3, recent-five, PvP-non-effect, and cross-client parity acceptance; otherwise record exact reproducible blockers without claiming completion.
- [ ] Commit the integration and kiosk slice, list all SHAs in cherry-pick order, and leave the source branch unmerged.
