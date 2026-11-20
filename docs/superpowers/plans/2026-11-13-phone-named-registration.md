# Named Phone Registration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Ship concise, named phone registration and login across Galaxy, Kiosk and launcher, preserving every existing identity and balance, then publish and deploy both clouds and an idle RK3562.

**Architecture:** One optional public-name column, unique only in the authoritative server identity store, and the existing SMS proof/phone locks. Board shadows cache trusted display names without local uniqueness or name-based authentication. Keep canonical identity unchanged; finalize registration/completion atomically and project the trusted public name only at display boundaries. Reuse the user's accepted Artifact and existing generation/CAS, SSO, permanent grant claim and release transactions.

**Tech Stack:** FastAPI, SQLAlchemy/PostgreSQL/SQLite, React/Vite, Jinja, existing Aliyun SMS adapter, pytest/real isolated PG, Vitest, existing native/Docker deployment helpers.

**Authority:** `docs/superpowers/specs/2026-11-13-phone-named-registration-design.md`. User approved Kiosk and specified the Galaxy corrections, then authorized direct traditional development/deployment. Preserve the existing worktrees and unrelated `katrain/web/static/favicon-badge.png`; do not recreate worktrees.

## Chunk 1: Plan and accepted UI contract

### Task 0: Review and freeze

- [x] Use `writing-plans`; independent **Astra / Max** plan/spec review, at most two rounds total. Fix actual blocking issues; do not expand scope into authentication-platform redesign.
- [x] `ui-ux-pro-max` Artifact: accepted Kiosk 1024×600 and corrected Galaxy 1440×900 modal with real Galaxy background, no Galaxy guest button. All primary controls at least 44px; no explanatory paragraphs.
- [x] Record the concrete response/error fields before parallel writers begin. Reviewer confirms backwards compatibility of canonical lookup and preservation of grant claims.
- [x] Commit only the plan/spec/Artifact paths after approval; ordinary implementation commits follow per slice.

## Chunk 2: Minimal foundation and one closed registration journey

### Task 1: Public-name schema and trusted projection foundation

**Owning files:** `katrain/web/core/models_db.py`, `katrain/web/core/migrations.py`, `katrain/web/core/auth.py`, `katrain/web/models.py`, `katrain/web/api/v1/endpoints/auth.py`; targeted `tests/web_ui/test_migrations.py`, a new `tests/web_ui/test_public_username_pg.py`, relevant auth tests.

- [x] Write failing real-PG tests for idempotent migration/backfill, preserved user/UUID/credits/membership rows, exact unique-name collisions, malformed same-name index rejection, and login-name vs canonical lookup isolation. Cover server SQLite authority as well as PostgreSQL. In a separate board SQLite, prove two historical canonical shadows may cache the same public name and that a server migration in the same test process has not polluted shared model metadata with a unique index.
- [x] Add nullable `public_username` with **no uniqueness/index attached to shared ORM metadata**. Add a small role-aware idempotent migration before repositories query it. On server authority only, create and verify `uq_user_public_username` as a real ordinary full one-column unique index (no predicate/expression, exact expected column); on board, leave the cache nonunique and do not perform public-name password authentication. Reuse migration serialization/DDL practices; do not mutate shared metadata when constructing the server index. No protected-table rebuild/drop, unrelated data normalization or reward writes.
- [x] Backfill server human names exactly, leave eligible generated phone accounts unset per spec. Board shadows stay unset until trusted cloud synchronization; the cloud's null also overwrites stale inferred cached values. Keep reserved/legacy names and roles intact. Update server creation paths to populate human public names so canonical/public namespaces cannot cross silently; shared shadow creation instead accepts only the authoritative field. Prove cloud A deletion/name reuse by B does not block the same RK and does not reassign A's canonical ID/UUID or history.
- [x] Add `get_user_by_login_name` only for password authentication; reject a canonical/public result pointing to different users. Token/refresh/SSO still use canonical lookup.
- [x] Propagate optional `public_username` through authoritative User/repository/OTP projection, safe OnlineUser where relevant, and cloud→board shadow/bootstrap. Never replace existing DTO `username` with a nickname.
- [x] Run focused migration/auth tests (real PG, SQLite where required), then spec/quality review. Commit the foundation.

### Task 2: Atomic registration/profile completion service and API

**Owning files:** `katrain/web/core/phone_otp.py` (small name/password validation helper only if it improves reuse), `katrain/web/api/v1/endpoints/phone_auth.py`, `katrain/web/core/remote_client.py`; extend `tests/web_ui/test_phone_signup_pg.py`, `test_phone_otp_api_pg.py`, `test_phone_auth_remote.py`, `test_phone_otp_limits_pg.py`, `test_phone_bind_pg.py`.

- [x] Replace old auto-create test expectations with: correct unknown OTP yields `profile_required`, zero users/claims/ledger rows/tokens and an unconsumed, unextended challenge.
- [x] Reuse `purpose=login`; no new ticket, table or state enum. Complete existing accounts keep ordinary login/consumption behavior. Unnamed historical generated accounts return the same continuation with mode `complete`.
- [x] Add `PhoneRegisterRequest(challenge_id, code, flow_id, public_username, password)` and `/auth/phone/register`; validate new names and passwords according to the frozen spec. Preserve existing password verification semantics.
- [x] Finalization locks phone→challenge→user consistently; rechecks proof; either creates a new account/identity/claim with at most one 5000 adjustment, or completes the existing account in place with zero grant. Full accounts reject overwrite. Compute hash outside long-held locks and revalidate proof before writing.
- [x] Catch only the actual public-name unique conflict as `username_taken`; rollback then allow valid-proof retry. Preserve wrong-code durable counting, cooloffs, TTL, single-use, deleted-account claims and no-op binding gift policy.
- [x] Add a candidate-producing remote registration call and pass-through of expected `profile_required` without identity installation or auth refresh/replay. Keep `/me` canonical validation and generation/CAS.
- [x] Return authoritative `signup_grant_credits` (0 or 5000) for the registration success notice, without leaking tokens into launcher/browser-public data.
- [x] Prove: ledger-failure rollback; same-phone/challenge concurrency; two phones claiming one name; conflict retains code; consumed/expired/flow-mismatched proof fails; old auto user completion preserves ID/UUID/canonical/credits/membership/claim/ledger exactly; old human password and phone binding still work; Unicode/72-byte/NUL password boundaries; no private data in errors/logs.
- [x] Run API/PG/remote regressions plus spec/quality review, then commit. Do not broaden into unrelated SSO baseline failures already documented by the previous release.

### Task 3: Real frontend integration and 11-language names/forms

**Owning files:** `katrain/web/ui/src/features/auth/{PhoneOtpForm,LoginMethods,PhoneBindingEntry}.tsx`, new minimal reusable registration form, existing LoginDialog/RegisterDialog, Galaxy LoginModal/sidebar, Kiosk LoginPage/KioskApp/account and membership surfaces, `context/AuthContext.tsx`, `api.ts`; existing relevant tests; `scripts/phone_otp_translations.json` or one dedicated additive catalog; `katrain/i18n/locales/*/LC_MESSAGES/katrain.po`.

- [x] First implement the accepted forms against an isolated local Fixture (no real SMS/payment). Compare runtime vs Artifact at the same viewport; one representative login/register comparison, including side-by-side/difference evidence. The user already authorized the specified Galaxy corrections; verify those exactly rather than requesting another identical confirmation.
- [x] Login: two tabs/two fields, short inline errors, register link. Kiosk has the existing guest action; Galaxy does not. Preserve Galaxy modal/backdrop/current route; do not replace its page with an auth screen.
- [x] Explicit registration shows four fields. Valid unknown-phone login continues with already verified phone and only the missing name/password inputs; do not send another SMS. Always offer password-login/bind for an existing account, never auto-link by matching text.
- [x] Hold code/flow/name/password only in form memory; clear on close/method/account changes. Clear expired proof and provide an explicit retry. Do not auto-resubmit names, passwords or OTP on identity change.
- [x] Success installs only a canonical-confirmed candidate with generation checks. Display the server's public name; use a safe localized label instead of an internal generated handle for incomplete profiles. Keep guest detection, storage namespaces, ownership parameters and tokens canonical.
- [x] Keep the success reward message only for the authoritative nonzero new signup grant. Existing-account completion and ordinary login never announce another gift.
- [x] Translate new/changed strings in all 11 existing locales, preserve unrelated translations/placeholders; compile all catalogs in release artifacts. No production fixture routes or mock business data remain after integration.
- [x] Verify auth identity-race tests, concise DOM/field-count tests, membership name and guest behavior, no overflow/44px at two accepted sizes; run full and strict builds once after final source changes.
- [x] Independent spec/quality review and commit the integrated journey.

## Chunk 3: Parent launcher and final review

### Task 4: Launcher registration, public name and strict SSO

**Tree:** `/Users/fan/Repositories/smartbox-software/.worktrees/freeplay-analysis-20261111` (original parent tree has unrelated edits; preserve them).

**Owning files:** `setup-wizard/app/routers/auth.py`, `services/{identity,box_identity}.py`, `templates/launcher.html`, `static/js/launcher.js`, existing CSS only if necessary, `locales/{zh,zh-TW,en,ja,ko}.json`; minimal existing `routers/lobby.py` and `xiangqi_ranked_proxy.py` display-name projection; relevant `setup-wizard/tests/test_phone_otp_auth.py`, identity/launcher tests.

- [x] Begin after Task 1's public field and Task 2's outcome contract freeze; work independently from Task 3 in the parent tree.
- [x] Add registration proxy/continuation and register form. `profile_required` must never create a session or retire an existing identity. Successful completion uses existing candidate validation/CAS and opaque `sb_session` only.
- [x] Propagate public display field through the public-user allowlist and trusted Go bootstrap/shadow. Lobby subjects/identity keys remain UUID/canonical; only visible name chooses public field.
- [x] Remove legacy ASCII/new-password validation from the password **login** client. Use the new validator only when setting a password, and retire/route the old unverified register path to verified registration.
- [x] Keep all guest capabilities and retirement guards. Preserve short bind UI and current-password reauthentication. Use the accepted Kiosk visual; no new disclaimer paragraphs. Update existing five catalogs without changing the locale set.
- [x] Test unknown-phone continuation has no local session, old credentials/claims intact, public-name-only lookup never changes JWT subject, Unicode login works, identity-switch errors clear private fields and do not replay a business 401. One representative real template preview is sufficient.
- [x] Spec and quality review; commit only owned parent files. No device connection by workers.

### Task 5: Final independent Astra Max review

- [x] Fresh independent Astra / Max reviews the final child+parent diff, actual runtime screenshots, focused PG/identity/ledger evidence and fixture retirement. Fix findings through owning implementers, rerun only changed behaviors, repeat until Approved.
- [x] No real SMS, account edits, checkout or paid analysis in automation. User will receive/type the real SMS after release. Do not treat mocks as a real payment/SMS acceptance.

## Chunk 4: Publish and deploy, serializing the real device

### Task 6: Four-step integration

- [ ] Fetch current develop, merge into feature, resolve conflicts, verify changed paths and push feature. Merge/push develop; no force push or rewrite of other work.
- [ ] Fetch parent main in the clean prepared tree, merge published parent work and update vendor/katrain to published develop; verify/commit/push main, preserving unrelated original-tree changes. A branch deployment alone does not complete integration.
- [ ] Frozen release carries exact child/parent SHA, all 11 catalogs, source and static hashes. Reuse existing release helpers and prebuilt outputs only when their inputs are byte-identical.

### Task 7: TEST → PROD → idle RK3562

- [ ] Read `server-deploy`. Capture actual config/health/IDs privately; preserve every old commercial switch, quota, WeChat setting/secret bind, SMS setting/secret bind, budgets, cron/GPU/DB state and unrelated config. Code/schema-only delta; never print Env/DSN/keys. Reuse config-preserving helper with its concrete source delta reviewed for this release.
- [ ] Additive public-name migration is checked before serving new auth. Deploy TEST first; verify schema shape, canonical/public lookup, runtime source/static/11-language hashes and anonymous actual Galaxy/Kiosk UI. Do not consume personal quota or send SMS.
- [ ] Deploy PROD only once TEST passes. Verify the same gates and preserve old containers/backups; no destructive DB down-migration.
- [ ] **RK busy gate before any upload, deletion, maintenance or metadata change:** read the actual launcher maintenance lock and owner/heartbeat, inspect deployment helpers/provisioning/rsync processes and current release journals. Check this task's own sessions separately. A lock or another active deploy means wait and report while continuing independent work; do not kill, overwrite, stale-delete or steal it. If owner is unclear, remain read-only. Acquire the existing standard exclusive lock for apply, so the final race also refuses safely.
- [ ] Verify `rk3562-local` expected authenticated identity (gzpeite/192.168.0.104), actual service config and storage budget. Do not switch to a different host with a mismatched key/name. Use `app` scope; preserve hardware rules/calibration and restore the exact existing Chromium page with no extra renderer.
- [ ] Reuse the existing source/static manifest, maintenance, protected database snapshot/guard, migration, backup and restoration transaction. If only an additive migration is needed on board, still preserve its shadow/public fields; no cloud/provider secrets belong on RK.
- [ ] Keep the 1GiB reserve. If old archival is necessary, first inspect live service **configuration references**, symlinks/open files and deployment owners, not just FD presence; never remove active deployment/config/log roots. Use resumable transfer and local verified-byte caches rather than monolithic SSH streams; preserve content/owner/mode in a private off-device archive before removing exact old copies. No unrelated cleanup.
- [ ] Camera readiness exceptions use only the existing app-scope option when actually needed and are reported honestly; no hardware repair in this slice. Confirm all other health checks, exact release files, 11 catalogs and current actual browser bundle/viewport. Do not navigate or reload an in-progress game for screenshots; use read-only DOM/HTTP evidence and tell the user what awaits hands-on acceptance.
- [ ] Remove only regenerable staging after success; retain rollback evidence. Record final child/parent/runtime versions, tests, device coordination result, real-SMS/payment acceptance gaps and ready-to-use user steps.

## Focused validation commands

Use the existing task-only loopback PG runner (restore its private test env if missing; never use default production DB):

```text
python3 output/wechat-native/run-tests.py tests/web_ui/test_public_username_pg.py tests/web_ui/test_phone_signup_pg.py tests/web_ui/test_phone_otp_api_pg.py tests/web_ui/test_phone_bind_pg.py tests/web_ui/test_phone_auth_remote.py -q --tb=line
```

Run E18 real-runtime tests in their documented separate process, not mixed with auth suites that replace modules. Do not repeat unrelated hardware suites for UI/auth-only changes.

```text
cd katrain/web/ui
npm run test -- src/features/auth src/context/AuthContext.test.tsx src/api.phoneBinding.test.ts src/kiosk/pages/LoginPage.test.tsx src/kiosk/pages/membership/MembershipPage.test.tsx
npm run build
npm run build:smartbox-kiosk-2d
```

Parent uses its Python3.11 setup-wizard venv (not the KaTrain venv), `SUB2API_MOCK=1`, focused phone/identity/launcher tests. Add only tests needed for the new continuation, display-name and privacy/identity boundaries.
