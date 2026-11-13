# Implicit Phone Entry and Review Reports Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** Ship the approved same-window phone/name entry, independent report progress and trustworthy platform labels, then publish develop, update the parent main gitlink, and deploy both clouds and an idle RK3562.

**Architecture:** Reuse the existing OTP, canonical UUID, permanent phone claim and billing transaction. Add one backwards-compatible continuation endpoint and one authenticated, freshly phone-verified password-setting endpoint. Report presentation reads the existing per-tier cloud tasks; provenance adds one nullable field through the existing persistence/sync chain. No new queue, account merge, grant store or billing lifecycle.

**Tech Stack:** FastAPI/Pydantic, SQLAlchemy PostgreSQL/SQLite, React/Vite, existing launcher Jinja/identity daemon, Gettext 11 locales, pytest/Vitest, existing config-preserving Docker/native release helpers.

**Authority and baseline:** User approved the final design and explicitly requested development, independent **Astra Max** review and four-step deployment. Spec: `docs/superpowers/specs/2026-11-13-implicit-auth-report-requirements.md`. Auth Artifact: `docs/design/implicit-auth-report-2026-11-13/auth.html`; reports: current Kiosk v5 and Galaxy v4. Child `feature/membership-recharge` was fast-forwarded from `ec6ca09d1` to fetched develop `6a847cd7b`; preserve the other session's Golaxy nickname and vision fixes. Existing dedicated worktree is the user-provided checkout. Preserve unrelated `katrain/web/static/favicon-badge.png`. Parent worktree: `/Users/fan/Repositories/smartbox-software/.worktrees/freeplay-analysis-20261111`; fetch and integrate its current main before editing it.

## Chunk 1: Frozen contracts and review

### Task 0: Approve this plan, at most two plan-review rounds

- [ ] Independent Astra / Max reviews scope, contracts, security, device coordination and deploy compatibility. Fix blocking findings within two rounds; do not turn the display work into infrastructure redesign.
- [ ] Record review result and commit only approved plan/spec/Artifact paths. No production implementation before plan approval.

### Frozen account contract

Keep `/auth/phone/register` unchanged for already published clients. Add:

```text
POST /api/v1/auth/phone/continue
{challenge_id, code, flow_id, public_username, current_password?: string|null}
200: existing Token fields + signup_grant_credits: 0|5000
409 account_password_required: same response for any existing eligible name,
    whether or not that account has a phone; no token, no mutation, no TTL extension.
409 phone_in_use: only after correct old-account password; no phone/mask disclosure.
409 public_username_taken: name race, ambiguity or legacy-profile completion conflict.

POST /api/v1/auth/phone/password   [authenticated non-guest account only]
{challenge_id, code, flow_id, new_password}
204: freshly verified login-purpose challenge belongs to actor's CURRENT phone,
     atomically consumed and password changed. This also permits resetting an
     existing password; no has_password column or initial-password sentinel.
```

Use existing private error envelopes/no-store/redacted validation. `/phone/login` remains phone/code first: a linked complete account logs in; unknown/legacy returns `profile_required` and preserves the challenge. No separate availability API. New accounts get an unguessable random bcrypt password, never a shared/default password or invalid hash. Keep normal password login and legacy `/register` compatibility.

Continuation invariants:

1. Validate flow, active challenge, code and expiry before every name branch. Availability alone grants nothing.
2. For an unknown phone and free valid name: create user/UUID, phone identity, permanent once-only claim, at most5000 credits and consume proof in ONE transaction. Old claim means0 credits.
3. For an existing name: only then request old password; reuse the existing independently committed reauthentication budget. Verify outside long-held locks; final transaction locks phone state/challenge/target, then rechecks current hash, name, eligibility and phone binding. Reject admin/guest/shadow/ambiguous identities. Existing eligible names use the established login-name lookup, not new-name validation first.
4. Correct password binds the verified phone to the same old UUID and grants0; any other bound phone rejects. Do not overwrite identities, merge accounts or move assets.
5. Legacy generated account completion updates the SAME row and grants0; a name collision must never select another account. Preserve its existing password unless the separate password flow changes it.
6. Name/password failures retain the same proof without extending TTL; only successful mutation consumes it. Same-phone/name and two-phones/same-account races are resolved by locks and existing DB uniqueness, never count-then-insert.

## Chunk 2: Account journey

### Task 1: Atomic continuation, password setting and API/remote plumbing

**Files:** `katrain/web/core/phone_otp.py`, `api/v1/endpoints/phone_auth.py`, `core/remote_client.py`; focused tests `tests/web_ui/test_phone_signup_pg.py`, `test_phone_bind_pg.py`, `test_phone_otp_api_pg.py`, `test_phone_auth_remote.py` and a small continuation/password test module if separation improves readability.

- [ ] Write failing service/API tests for the contract and unchanged `/register` compatibility.
- [ ] Reuse existing helpers for proof checks, phone locks, unique-name conflict handling, persistent reauthentication and claim/ledger writes. Add only methods needed by the two endpoints; keep JWT subjects/canonical lookup unchanged.
- [ ] Extend the existing cloud proxy rather than authenticating phone accounts against board shadows. Private payloads/errors never enter logs.
- [ ] Test fresh-name50 once, same-UUID legacy completion, password-before-conflict privacy, wrong-password persistent budget, old UUID/assets preservation, forbidden overwrite, proof expiry/resend/flow/replay, same-phone/name/account concurrency and transaction rollback.
- [ ] Password tests: valid freshly verified actor phone succeeds; other phone/guest/stale challenge fails; no gift or identity switch; normal password login works afterwards.
- [ ] Run real isolated PG tests with the existing loopback TEST-marked runner. This worker owns PG test execution while changing auth; other workers must not concurrently truncate that database. Spec and quality review; commit owned files.

### Task 2: Same-window React flow and optional password settings

**Files:** `ui/src/api.ts`, `context/AuthContext.tsx`, `features/auth/PhoneOtpForm.tsx`, `LoginMethods.tsx`, new focused password dialog plus existing `PhoneBindingEntry.tsx` entry if appropriate; existing auth CSS, Galaxy `LoginModal.tsx` and kiosk login only as needed. Tests: existing `PhoneOtpForm.test.tsx`, `NamedSignup.test.tsx`, `LoginMethods.identity.test.tsx`, API/auth-context tests and the password dialog test.

- [ ] After Task1 contract is fixed, implement phone/code → same popup username → only on `account_password_required` show old password. Do not navigate to registration or ask new users to set a password. Existing explicit registration remains compatible but primary unified entry follows approved Artifact.
- [ ] On username change, clear old password/error. On cancel, back, tab/identity change, clear private state and abort. Reuse revision/identityKey/AbortController protection; a late token must not install the wrong identity.
- [ ] Reuse existing token candidate verification and trusted public-name projection. New grant success alone shows the existing brief50-credit notice; binding/completion never repeats it. Preserve Galaxy modal background/no guest and Kiosk guest entry.
- [ ] Add a concise optional password setting/reset dialog under account/phone settings, requiring logged-in actor, phone, a NEW OTP and new password. Do not add these fields to first login. Reuse existing validation and challenge UI where practical.
- [ ] Focused tests cover the conditional field sequence, privacy errors, same-form retries/expiry, proof reuse, stale responses and correct post-success identity. No real SMS sends.
- [ ] Compare one representative Kiosk1024×600 and Galaxy1440×900 runtime flow with the approved Artifact, recording geometry/copy/state differences. Remove temporary fixtures from production paths. Review and commit.

### Task 3: Parent launcher and strict RK SSO continuation

**Files in the published parent:** `setup-wizard/app/services/identity.py`, `routers/auth.py`, `static/js/launcher.js`, `templates/launcher.html`; current five `app/locales/*.json`. Tests: `test_phone_otp_auth.py`, existing identity/box-identity tests and `tests/ui/launcher.phone.test.js`.

**Concrete baseline decision:** target published `origin/main=19aa5487` (or a later fetched published main). The original parent worktree has a local, unpublished identity-daemon refactor at `168b1b06`; it is not this task's source, must not be copied/rebuilt/published opportunistically, and stays untouched. The initially audited daemon module names are not present in the published parent. If that other work is later published, merge it normally and adapt this task's narrow continuation/password delta to its actual modules, with final independent review before release.

- [ ] Begin after contract freeze, in the existing clean parent worktree after integrating fetched main `19aa5487` or any newer published main. Preserve unrelated original parent worktree changes.
- [ ] Extend the published `identity.py` phone operation allowlist/helper and router schemas with continuation/password setting, safe error envelopes and response projections. A cloud password204 response is success without JSON parsing; retain installed identity. If a published daemon implementation supersedes this baseline before release, update both client and daemon strict wire method/field validation together, including private password encoding, instead of silently dropping fields.
- [ ] Continue using existing candidate token→cloud `/auth/me`→generation/CAS→installed box identity. `profile_required`/name/password errors must not create a local session or retire the existing identity. Password mutation retains the current identity and checks its generation.
- [ ] Implement the same progressive name/old-password sequence and separate optional password settings in the launcher. Keep existing guest/other-game capabilities; primary touch controls≥44px. Add translations in its current five locales.
- [ ] Test proxy roundtrip (and strict daemon wire only if it becomes part of the published baseline), replay/generation guards, password204, no secret logging, stale response, old-binding conflict and successful new/old account continuation. Use `SUB2API_MOCK=1` and the parent Python3.11 venv; no real device or SMS calls from workers. Review and commit owned parent files.

## Chunk 3: Review reports and provenance

### Task 4: Trustworthy platform provenance end to end

**Files:** `katrain/web/core/models_db.py`, existing `migrations.py` path, `core/user_game_repo.py`, `api/v1/endpoints/user_games.py`, `platforms/manager.py`, `server.py`, `ui/src/api/userGamesApi.ts`, a small shared report-origin label helper. Tests: `tests/test_user_game_repo.py`, `tests/web_ui/test_migrations.py`, `test_user_game_cloud_owner.py`, `tests/platforms/test_engine_manager.py`, engine/OGS save tests and DTO/sync roundtrip tests.

- [ ] Add nullable `UserGame.platform:String(32)` with accepted `golaxy/ogs/fox` IDs; reuse additive missing-column migration for server and board. No index, old-row rewrite, SGF/hash update or inferred backfill.
- [ ] Add optional platform to POST schema and explicitly pass through local create, `_to_dict` get/list, frontend types and existing dict-based cloud/queue transport. Test cloud validation does not silently drop it and offline replay retains owner/platform.
- [ ] At trustworthy platform game start, before first AI result, write private SGF root `KTP[platform]`; new games start clean. Ended engine contexts may already be gone, so save reads this trusted root metadata. OGS save also passes reliable `ctx.platform`. Preserve the newly merged `my_username` logic; do not add a historical-player-name rewrite.
- [ ] Keep `source` and `game_type` unchanged for statistics/permissions/billing. Import remains `source=import` even with KTP; platform metadata never proves participation, rank or ownership. Do not expand research/SGF editor metadata paths unnecessarily.
- [ ] UI source labels: imported/library/research classifications keep priority; reliable played-platform data displays cross-platform＋localized platform; unknown old records keep existing broad source fallback. Do not promise legacy source recovery.
- [ ] Test both colors, context-gone save, ordinary next-game no leakage, OGS, additive SQLite/PG migration, POST/list/get/queue roundtrip and import isolation. Review and commit.

### Task 5: Approved compact progress presentation, real tasks only

**Files:** `features/report/reportModel.ts`, `kiosk/components/report/reviewPresentation.ts`, `kiosk/pages/ReportsPage.tsx`, `personalGamesReviewed.css`, `galaxy/components/report/ReportGameCard.tsx`, `galaxy/pages/report/ReportsPage.tsx`; a small shared pure per-tier presenter/component where it avoids duplication. Tests: existing reportModel, useReportTasks, reviewPresentation, Kiosk ReportsPage/polling and Galaxy ReportsPage tests.

- [ ] Add tests for ordinary completed＋advanced running, dual running, failed retry, same-tier old completion＋new active task, running100% not ready and remount GET-only.
- [ ] Map each tier independently: its active task takes priority, otherwise available completion/failure according to existing contract. Use one clamped real `analyzed_moves/total_moves` value for fill/text/aria; initialposition0 does not add a hand. Do not create fake progress timers in production.
- [ ] Kiosk v5: 224px preview,752px list; card624×74, row74/gap8; external120×74 with2×34/gap6 green rectangular fills,14px names/12px percent. Preserve card width, original density, pagination and bottom nav. Move selected-delete to preview title with≥44px hit target.
- [ ] Galaxy v4: card416×104, row104/gap8; independent external126×74 report column/gap10, full name＋real-proportion ring. Preserve established Galaxy styling.
- [ ] Right-side status rows are noninteractive. Existing large menus handle generate/view/retry. Check active before completed in each menu as well. Preserve task IDs, polling and cloud list rehydration; no POST from mount/reconnect.
- [ ] Keep paid failure/refund/re-authorized retry semantics. Remove stale claims that any failed prefix means free continuation. The cloud-worker crash/resume enhancement is deferred; do not change `cron/jobs/report_analyze.py` or paid ledger lifecycle.
- [ ] Use the provenance helper even when Galaxy event/title exists, without discarding event/title secondary information. Existing normal-game source labels remain correct.
- [ ] One same-size runtime visual comparison per surface against Kioskv5/Galaxyv4, plus focused state/interaction tests. Do not create a full screenshot matrix. Review and commit.

## Chunk 4: Reliability, translations and final review

### Task 6: Minimal visible startup/error handling

**Files:** `ui/src/AppRouter.tsx`, `main.tsx` only where necessary, focused small error-boundary/fallback module and tests. No new backend telemetry service.

- [ ] Replace top-level `Suspense fallback=null` with a concise localized visible loading state. Catch unrecoverable root render errors with a visible manual retry action, reusing existing UI tokens.
- [ ] Keep a small bounded diagnostic record in browser session storage: build ID, timestamp, fixed failure category and safe surface name only. No account/game IDs, request URLs/query/hash, message bodies, tokens, exception messages/stacks or props. Handle unavailable storage safely.
- [ ] Do not add automatic refresh timers; replace existing preload-error automatic reload with the same visible manual retry if needed to avoid interrupting an active match. Do not claim this identifies or fixes the unproven prior root cause.
- [ ] Test thrown render/preload error produces a visible fallback and diagnostics contain only allowlisted fields; no automatic reload. Manual reload only after explicit click. This is a small containment/observability change, not a hardware investigation.

### Task 7: Eleven-language integration and focused verification

**Files:** `scripts/batch_translate_galaxy.py`, `katrain/i18n/locales/{en,cn,tw,jp,ko,de,es,fr,ru,tr,ua}/LC_MESSAGES/katrain.po`; compiled MO artifacts via current release builder. Read `.agents/skills/katrain-i18n-expert/SKILL.md` and preserve placeholders/subscription-on-language-switch.

- [ ] Freeze new keys from Tasks1–6, reuse existing report/auth wording where accurate. Add all11 translations for continuation, password settings, report labels/provenance/accessibility and startup/error states. Keep concise Chinese; do not import prototype explanatory text.
- [ ] Compile catalogs, check new-key coverage/placeholders and representative language switching. Do not run an unrelated full-catalog translation rewrite.
- [ ] Run focused auth PG suites serially against existing TEST-marked loopback PG, report/source/migration tests, frontend targeted tests and parent identity/launcher tests. No real SMS/payment/paid-analysis automation.
- [ ] Run full web and strict `build:smartbox-kiosk-2d` once after final relevant changes. Strict build must not pull Galaxy/three.js. Repeat builds only for subsequent relevant fixes.
- [ ] Fresh independent **Astra Max** reviews final child＋parent diff, spec compliance then code quality/security, representative actual UI and test evidence. Fix findings through implementers and rerun affected checks until approved. Record exact reviewed SHAs and fixture absence.

## Chunk 5: Four-step publication and serial deployment

### Task 8: Publish exact reviewed source

- [ ] Fetch latest develop again; merge into feature, preserve other sessions' work, verify the combined result, commit and push feature. No force push.
- [ ] Merge feature into develop and push develop. A deployed feature branch alone is not integration.
- [ ] Fetch parent main again, merge current main and owned launcher work, update `vendor/katrain` to the published develop commit. Verify, commit and push parent main; keep its other gitlinks and unrelated changes.
- [ ] Freeze release manifest with child/parent SHAs and source/static/11-catalog hashes. Reuse reviewed release helpers only after validating the actual additive-schema/source delta and current parent script.

### Task 9: TEST → PROD → idle RK3562

- [ ] Read `server-deploy`. Capture actual cloud Docker config, source/version, health, mounts/networks/image and safe switch values privately. Preserve commercial/live-payment/SMS switches, keys/mounts, collector budget/role, DB/GPU/cron/unrelated services. Never print Env/DSNs/secrets or substitute historic config.
- [ ] Deploy receiver/schema to TEST first, then PROD after TEST passes. Use the current configuration-preserving web replacement helper; additive platform column has no destructive down-migration. Check source/static hashes,11catalogs,health and anonymous actual Galaxy/Kiosk pages. No real quota consumption/SMS/payment.
- [ ] **RK gate BEFORE any upload/maintenance/metadata/cleanup:** verify authenticated `rk3562-local` identity `gzpeite`, current release, launcher maintenance/deployment owner/heartbeat/locks and provisioning/rsync/deploy processes. If another owner is active or unclear, remain read-only, wait and monitor bounded intervals while continuing independent work. Never kill, steal or delete its lock. Recheck immediately before apply and use the standard exclusive lock transaction to close races.
- [ ] Use current parent native app-scope exporter/deployer with frozen committed source＋strict build. Preserve calibration/config/mode, installed identity and hardware settings; require1GiB reserve. If space is inadequate, only archive exact inactive release data using the established verified off-device backup policy. No unrelated cleanup.
- [ ] Detect the actual identity runtime before preparing RK: legacy launcher versus any active identity daemon, including its source/version. Do not enable or migrate an inactive daemon. If an active daemon exists, its existing source must first be published/integrated; do not downgrade it with the legacy tree. Its narrow API delta, stop/restart/readiness and rollback must join the SAME existing maintenance transaction. Existing published app deployer restarts only the wizard; never assume that updates an active daemon's in-memory dispatcher. If the other deployment/publication is still running, wait without modifying its services.
- [ ] Reuse protected database snapshot/migration/backup/rollback/maintenance transaction; do not place cloud/provider secrets on RK. Retain rollback artifacts. Verify health, both games' required camera gates, source/static/catalog hashes and release SHAs.
- [ ] Do not navigate/reload/intercept the user's current active game for screenshots. At an idle maintenance window verify the upgraded existing single renderer; no extra device browser context. For screenshots outside an idle window use local runtime previews and read-only served asset evidence.
- [ ] Clean only this release's regenerable staging on success. Report published/deployed SHAs, test results, lock coordination, real phone/user acceptance gaps and exact RK verification steps in this session. User will perform real SMS and hands-on review; no unattended real charges.

## Focused commands

```text
python3 output/wechat-native/run-tests.py tests/web_ui/test_phone_signup_pg.py tests/web_ui/test_phone_bind_pg.py tests/web_ui/test_phone_otp_api_pg.py tests/web_ui/test_phone_auth_remote.py -q --tb=line
python -m pytest tests/test_user_game_repo.py tests/web_ui/test_migrations.py tests/web_ui/test_user_game_cloud_owner.py tests/platforms/test_engine_manager.py -q
cd katrain/web/ui
npm run test -- src/features/auth src/context/AuthContext.test.tsx src/features/report src/kiosk/components/report src/kiosk/pages/ReportsPage.test.tsx src/kiosk/pages/ReportsPage.polling.test.tsx src/galaxy/pages/report/ReportsPage.test.tsx
npm run build
npm run build:smartbox-kiosk-2d
```

Exact additional file names and targeted commands may follow existing ownership, but cannot change the frozen security contract or enlarge deferred paid-worker scope. Parent tests use its own Python3.11 venv and `SUB2API_MOCK=1`. Stop the task-only local PG after validation; preserve private test credentials and all unrelated working-tree changes.
