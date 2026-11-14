# First phone verification and public account names

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Keep implementation and verification focused on this correction.

**Status:** User resumed implementation on 2026-11-14 (“开始实施吧”). Execute after independent review of this updated four-game plan. The previous Astra approval covered the narrower draft, not this expanded scope.

**Requirements:** `docs/superpowers/specs/2026-11-14-phone-first-verification-requirements.md` is the current consolidated requirements document.

**Goal:** Show a short first-verification 50-credit explanation on the box, award it once to eligible old as well as new accounts, and consistently display the same public username across Go, Chess, Xiangqi and Gomoku, including Galaxy/Kiosk account labels and game cards.

**Architecture:** Reuse the authoritative cloud phone transaction, permanent phone claims and immutable credit ledger. Phone/account locking and grant uniqueness stay inside the existing transaction; device proxies carry only an additive grant result. Preserve canonical identity fields for authorization; presentation uses the trusted public username with a safe localized fallback.

**Tech stack:** Existing Python/SQLAlchemy/PostgreSQL, React/Vitest, legacy setup-wizard/Jinja launcher, Gettext 11 languages and the launcher's existing locales.

## Confirmed requirements and evidence

- User confirmed: first verified phone can receive 50 credits; an account OR phone that already received the gift cannot receive it again. This supersedes the previous old-binding-zero policy.
- Scope includes the box. Binding form copy: “首次验证手机号送50积分，已领取不再赠送。” Keep the existing compact layout. Only show an actual grant-success message when the authoritative response reports a new grant.
- Ordinary login, password changes, replay and retries cannot create extra gifts. Existing credited accounts remain credited exactly once. No batch retroactive grants or production-data edits.
- Existing `bound_existing` claims are historical verification records, not proof that money was actually granted. Never infer prior monetary receipt from positive balance. For a fresh first binding/registration with a historical zero claim (e.g. its old account was deleted), check actual account/phone gift history and preserve the original claim attribution if recording its first gift. Already-bound accounts keep the existing bound UI; this repair adds no retroactive re-verification/reward entry and no batch top-ups. Normal login and consumed historical proofs never issue rewards.
- Wrong password/code, expired proof, conflicting ownership and failed transactions grant nothing. Preserve account UUID, membership and existing balance apart from the authorized 50-credit addition.
- Fresh RK read-only evidence: current page `http://127.0.0.1:8003/` has two visible `u_[20hex]` values. Gomoku's local identity DTO discards launcher `public_username`, and its header/greeting use canonical username. Go's current account helper already hides that generated format; verify its shared account labels and repair any direct presentation bypass without changing ownership comparisons.
- User subsequently confirmed ALL FOUR games: Go, Chess, Xiangqi and Gomoku. Shared registration/login must deliver the same public name to each game's available Galaxy/Kiosk surfaces, especially player labels and game/review cards. Gomoku is one reproduced example, not the complete scope. Already-bound and existing accounts must be included.
- Never display canonical generated handles, UUIDs or full phone numbers as fallback account labels. Preserve legitimate legacy human usernames. Prefer authoritative `public_username`; empty/invalid generated names get localized “账号”. Do not invent names or rename canonical accounts.

## Chunk 1: Focused correction

### Task 1: Gift eligibility and authoritative responses

**Files:** `katrain/web/core/phone_otp.py`, phone API response DTOs in `katrain/web/api/v1/endpoints/phone_auth.py`, scoped remote validation in `core/remote_client.py`; `tests/web_ui/test_phone_bind_pg.py`, phone continuation/signup/API tests.

- [ ] Add failing PostgreSQL cases for eligible old binding and continuation binding, account-already-granted with another phone history, phone-already-granted after account deletion, old zero-grant claim during a fresh eligible binding, already-bound challenge rejection, replay, two workers/different phones/same account, wrong/expired proof and transaction rollback.
- [ ] Centralize only the repeated gift check/write. Use established phone→proof→account lock order, the immutable credit ledger and permanent phone records, and an unambiguous idempotency reference. Check actual grant history by account and phone while locked. Historical positive committed `signup` and `signup_grant` rows count at any amount (including old 100-credit grants). Handle the older positive `opening_balance` legacy default-credit evidence explicitly, without using current spendable balance or treating paid top-ups/admin grants as signup gifts.
- [ ] In explicit binding, recheck proof expiry after potentially blocking account locks and before successful finalization; expiry rolls back the identity, claim and gift together. Add an account-lock/expiry PostgreSQL regression.
- [ ] Reuse or minimally extend permanent claim metadata if a historical zero claim needs a once-only grant; preserve claim history/account audit and never permit reuse after deletion. Avoid a new generic rewards subsystem.
- [ ] Return additive `signup_grant_credits: 0 | 5000` from explicit binding, and reuse the existing continuation result field. Replays return 0, never falsely announce a second grant. Propagate through existing remote validation without changing authorization.
- [ ] Run affected PG/API tests with the existing isolated PG harness; no real SMS or production DB writes.

### Task 2: Box hint and grant feedback

**Files:** child `ui/src/api.ts`, `features/auth/PhoneBindDialog.tsx` and related tests/locales; parent published worktree `setup-wizard/app/templates/launcher.html`, `app/static/js/launcher.js`, phone proxy response validation/tests and locale JSON.

- [ ] Before binding show the confirmed short hint in the existing form. Show success with 50 credits only for a response value of 5000; otherwise show binding success without an award claim.
- [ ] Preserve async identity-generation guards, retry/expiry handling, password/OTP cleanup and canonical account ownership. Keep the additive field backward compatible with old response consumers.
- [ ] Update scoped translated keys for all existing 11 child languages and existing launcher locales, using `katrain-i18n-expert`; compile/placeholder-check only changed keys. No login-page redesign.
- [ ] Check one real 1024×600 box preview for compact spacing and visible hint; do not navigate the live device during the user's session. The copy/behavior is approved in the conversation, so no extra visual approval cycle for this small repair.

### Task 3: Shared public names across all four games

**Files:** parent shared `setup-wizard/app/{routers/auth.py,services/box_identity.py,services/identity.py}` only where a trusted profile projection/refresh repair is needed; per-game identity DTO and presentation files under `gomoku/`, `chess/`, `xiangqi/`; child Go `features/auth/accountDisplay.ts`, Galaxy/Kiosk account/player/card display call sites and existing user DTOs. Known Gomoku gap: `gomoku/api/gomoku_api/{identity.py,models.py,main.py}`, `gomoku/ui/src/{shell/AppShell.tsx,shell/identityPresentation.ts,play/greeting.ts}`. Resolve exact owning files for the remaining game cards before edits; no new identity service or unrelated daemon refactor.

- [ ] Trace one shared account from authoritative registration/login profile through launcher/session/bootstrap, each game's local identity DTO and UI state. Record a compact four-game coverage matrix with existing available Galaxy/Kiosk surfaces and actual player/game-card owners. Distinguish reproduced gaps from paths already working.
- [ ] Preserve `public_username` through each missing projection, starting with the confirmed Gomoku omission. Keep canonical username/user ID/session digest and all authorization/ownership comparisons unchanged. Make additive display fields compatible with older consumers.
- [ ] Present the trusted public name consistently in account bar, homepage greeting, player labels, lobby and game/review cards for all four games. For historical records, resolve only verifiable site-account identities; do not overwrite external-platform player names or opponent identities.
- [ ] Cover existing and already-bound users, not just fresh registration. Where an existing session's trusted profile is stale, refresh that profile within the current identity/generation boundary rather than creating another account or forcing re-registration. Prevent a late prior-account name appearing after account switch.
- [ ] For missing names use a localized safe account/loading/error label; never expose UUID/generated handles/full phone as fallback, and never fabricate a public name. Preserve legitimate legacy human usernames.
- [ ] Add focused tests per game for generated canonical handle + real public name, own-player/game-card display, legacy human account, unnamed account and guest/loading/error. Include a shared-account/switch-game integration case and retain account-switch race checks.
- [ ] Run affected Python/frontend tests and one representative preview per actually changed interface family at its real viewport, including 1024×600 box and Galaxy. Verify visible public name and zero internal handles in the targeted labels/cards without changing layout or navigating the user's live game.

## Chunk 2: Review, publication and release

- [ ] After the user resumes work, obtain independent Astra Max review of the updated four-game plan, maximum two rounds. Address scope/data-integrity findings before implementation; the earlier narrower approval is not approval of this expanded scope.
- [ ] Execute tasks via SDD. Independently review spec compliance followed by code quality; final Astra Max review fixes until approved. Do not repeat the already completed report/payments feature audit.
- [ ] Fetch newest child develop, integrate feature and verify the combined result; publish feature then develop. Preserve the original workspace's untracked favicon.
- [ ] Update and publish parent `vendor/katrain` in the prepared published parent worktree, preserving unrelated local identity-daemon work in the original parent. Build only changed child and per-game frontends once; reuse unchanged outputs.
- [ ] Once execution is resumed, deploy required authoritative server code and box UI under existing release tools, preserving live membership/payment/SMS configuration. Before RK mutation check exclusive deployment lock/processes, free space and current game; wait for another deployment and do not interrupt an active user game. The user's latest pause takes precedence over prior release authorization; avoid real SMS/payment/paid-analysis tests.
- [ ] Verify installed commit/hash, health, binding hint and the four-game name matrix on actually available Galaxy/Kiosk surfaces, explicitly including existing account player/game-card labels. Retain current rollback evidence, remove only completed incoming staging. Report published/deployed versions and leave the one real SMS/gift path for user acceptance.
