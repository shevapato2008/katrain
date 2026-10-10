# Guest Access and Spectator Sound Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** Ship the approved Galaxy/RK3562 guest login guidance and restore correct live stone sounds in kiosk self-hall and Golaxy spectating/play.

**Architecture:** Extend the existing AuthContext with explicit checking/authenticated/guest/expired/unavailable states and a bounded retry, retaining the current direct-login and strict HttpOnly box SSO contracts. Share a small visual access prompt and static protected-page outlines, with surface adapters handling existing login entry points and route metadata. Spectators reuse the existing sound service, tracking the live snapshot frontier independently of initial loading and replay.

**Tech Stack:** React 19, TypeScript, MUI 7, React Router 6, Vitest/Testing Library, existing FastAPI/box SSO and Chromium kiosk.

## Approved scope and acceptance

- User approved both `docs/design/guest-access-2026-10-10/index.html` surface variants on 2026-10-10. Implement that artifact, not a new visual design. Galaxy 1440×900 and mobile430×880; actual kiosk1024×600. Existing Kai font stacks and shell remain authoritative.
- Page gates show blurred STATIC placeholders, never actual protected content underneath. They must decide before protected components/hooks mount. No fake user/game counts. Crisp shell dims under a focus-trapped modal; 48px controls, no backdrop dismissal; Escape safely returns to public entry. Initial focus is primary (or enabled return while checking).
- Guest/expired/checking/unavailable copy follows the artifact. Network/5xx/timeout never removes credentials or claims login expired; retry available. Only `/auth/me`401 establishes invalid credentials. Generic403 remains a permissions error; do not globally reinterpret it as logged out.
- Galaxy uses existing LoginModal and stays on safe current route after successful login; cancel returns to gate. Strict RK uses existing launcher login URL, no new password form/token storage and no unimplemented automatic return promise. Technical username `guest` cannot enter functions requiring a real account. Preserve existing guest permissions outside those real-account features.
- Keep existing access policy: public Galaxy free play/research/kifu/tutorial/tsumego/live remain public. Galaxy whole-page gates cover self hall/room, rated setup and reports; integrate private cloud group/action prompts where an existing guard exists rather than hiding public pages. Kiosk existing guarded routes keep their access limits, ranked-only shared setup needs gate; free setup/game remains public.
- On logout/account change, guarded contents unmount immediately; in-flight reads/polling/WS cleanup must prevent late private data from reappearing. Key guarded content by stable identity. Bounded probe/retry must ignore stale results if login/logout wins the race. Do not add auto refresh-token infrastructure or change server expiry.
- Sound: first snapshot/history and page refresh silent; one sound for a newly observed placed stone; duplicate snapshot, pass, rewind/replay, game change and hidden/reconnect catchup silent. A snapshot jumping multiple moves makes at most one sound, not a burst. Respect existing global SFX toggle. Existing actual stone assets and output channel reused.
- Confirm Golaxy spectator and own/third-party hall participant sounds from code and meaningful tests. Do not claim physical audible verification from merely a call count; verify actual RK playback/output if possible, or state exact limitation.

## Chunk 1: Authentication and approved UI

### Task 1: Shared authentication state and access UI

**Files:**
- Modify `katrain/web/ui/src/context/AuthContext.tsx`, existing AuthContext tests.
- Create focused components under `katrain/web/ui/src/components/auth/` for presentation/state metadata and CSS/tests.
- Modify `galaxy/components/guards/AuthGuard.tsx`, `galaxy/components/auth/AuthRequiredDialog.tsx`; add surface gate adapter as needed.
- Modify `GalaxyApp.tsx`, `kiosk/components/guards/KioskAuthGuard.tsx`, `kiosk/KioskApp.tsx`, two surface `AiSetupPage.tsx` wrappers and current relevant private/action prompts.
- Existing shell adapters `MainLayout.tsx`, `KioskLayout.tsx` only if required to suppress private shell rail content when gated. Keep strict2D build free of Galaxy imports.

- [x] Write focused failing auth tests: retained token after503/network/timeout, retry restores; actual401 expires; old probe cannot overwrite successful login/logout; strictcookie restoration; realguest gating.
- [x] Write focused gate integration tests: protected child/request not mounted in guest/loading/unavailable; correct login/retry/back; existing allowed free/public pages not newly blocked; logout unmount; ranked vs free route policy.
- [x] Run focused tests red using `cd katrain/web/ui && npm test -- src/context/AuthContext.test.tsx <new-gate-tests>`.
- [x] Implement explicit auth status + bounded serialized retry using AbortController and generation checks. Keep existing `isLoading/isAuthenticated/token` API for current callers, with clear status as authority for new gates. Do not discard stored Bearer on non401.
- [x] Implement prompt and placeholder markup/CSS by approved artifact. Page title/description/back metadata explicit, not arbitrary external redirect. MUI or existing modality handles focus trap. Shared presentation does not import Galaxy-specific login in strict2D.
- [x] Integrate route/page gates before protected hooks mount; preserve free/public routes and object-specific forbidden behavior. Reuse existing action dialog with approved visual style, no automatic replay of writes after login.
- [x] Run auth/gate/current affected routing/setup tests green; verify normal and strict2D typecheck/build.
- [x] Capture representative Galaxy and kiosk guest/auth failure UI at exact viewport; compare with artifact side-by-side and overlay; record real fonts and geometry. User already approved artifact, implementation reviewed independently.

## Chunk 2: Live spectator and hall sounds

### Task 2: Correct live sound trigger

**Files:**
- Inspect/modify `kiosk/pages/PvpSpectatorPage.tsx`, `kiosk/pages/GolaxySpectatorPage.tsx`, their existing tests.
- Reuse `hooks/useSound.ts`; create one minimal live-snapshot hook only if both flows can genuinely share it.
- Inspect `hooks/useSessionBase.ts`, `hooks/useGameSession.ts`, kiosk GamePage and platform receive paths; change only if an actual missing trigger is proven.
- Modify `katrain/web/core/pvp_lobby_bots.py` and `tests/web_ui/test_pvp_lobby_bots.py`: successful bot commit currently bypasses the normal `_do_play` sound emitter. Emit the same legitimate asset sound with `after_node_id` on placed move exactly once, never pass/rejected candidate.

- [x] Complete root-cause trace of new self-hall snapshot page, Golaxy move polling, participant WS receive and device global sound preference/output. Record findings before patch.
- [x] Add failing tests for new placed move emits once, initial/refresh/duplicate/pass silent, jump at mostonce, visibility restore/catchup silent, remount/game change resets.
- [x] Implement minimum fix preserving snapshot order, game identities and poll serialization. Do not add a polling loop or alter engine/physical-board behavior for sound.
- [x] Add bot-commit backend regression for placed move emits one ordered sound with new node id, pass/rejected candidate emits none; preserve commit locks and identity/generation validity.
- [x] Verify own/remote participant existing sound tests (or add a targeted regression if real bug found).
- [x] Run `pytest tests/web_ui/test_pvp_lobby_bots.py` (existing environment).
- [x] Run `npm test -- src/kiosk/pages/PvpSpectatorPage.test.tsx src/kiosk/pages/GolaxySpectatorPage.test.tsx src/hooks/useSessionBase.sound.test.tsx src/hooks/useGameSession.sound.test.tsx` plus focused new hooktests.

## Chunk 3: Review, integrate and deploy

- [x] Independent `gpt-6-astra` max reviews plan (max2 rounds) before implementation; same model separately checks spec then code/representative screenshots; resolve meaningful issues until approved. Keep review/testing proportional to auth boundary and sound regression.
- [x] Build normal, admin and strict2D once after focused checks. Preserve approved artifacts and camera recovery code6eb154ba.
- [ ] Re-fetch develop, merge into feature/admin-console, commit only this work and approved guest docs, push feature. Merge published feature into develop and push. Wait for remote develop publication before submodule update.
- [ ] Update smartbox-software/vendor/katrain to exact published develop, commit pointer only preserving unrelated changes, push main.
- [ ] Deploy published commit to home-ubuntu/ucloud-v100 web/cron/admin and RK3562. Reuse proven prior release scripts but inspect/update manifests and changed source set, preserve all effective secrets/data/ports/overlays; record rollback artifacts.
- [ ] Verify effective SHA/service health and representative real Galaxy guest gate and RK real live snapshot/sound. Device camera/LED must stay healthy. Do not logout the user's live device merely to test guest; isolated context or existing fixture preview for guest state. Actual browser observes readonly existing game, restore original device route.
- [ ] Report exact commits/versions, sound confirmation and remaining manual hearing check if no audio capture establishes speaker output.

## Review and build result (2026-10-10)

- Plan: independent gpt-6-astra max Approved in round 1.
- Code/visual review initially requested three concrete auth fixes plus heading font inheritance. `b31c563d`, `99399ea4`, `ee55b5d1` addressed them with focused regressions and actual font evidence. Independent final spec/code/visual review: Approved at `99399ea4`.
- Normal/admin/strict SSO kiosk builds all passed after these fixes. Strict build manifest and verification passed.
- Actual RK platform status was disconnected from Golaxy; server/client sound paths and focused tests confirmed, actual Golaxy ear check remains conditional on reconnecting the platform account.
