# Phone OTP independent final code and visual review

Date: 2026-11-11. Reviewer was not involved in implementation or earlier reviews. Authority: [approved implementation plan](../plans/2026-11-11-aliyun-phone-otp-and-signup-grant.md). This is a code/visual review, not another plan round.

## Current scope and decisions

| Scope | Decision |
|---|---|
| Main repository B0–B5, `97f4b49e1..2bec82394` | **Approved** — no blocking code finding |
| Galaxy 1440×900 and cloud Kiosk 1024×600 representative UI | **Approved** — no blocking visual finding |
| Exact task-local release-helper delta and allowlist | **Approved** for the hashes below |
| Parent repository B6 launcher UI | **Approved** — independent visual/frontend gate recorded in the parent repository |
| Parent repository B6 Python transport/store/backend | **Approved** — independent final source review and focused race/privacy checks passed |
| Fresh private manifests, integration and actual two-cloud release | **Pending root execution/evidence**, outside this completed source slice |

**Final frozen code and representative visual review: Approved.** This covers the main repository B0–B5, exact helper hashes below, and parent B6 UI and Python changes against `f1d3a241`. There are no open blocking findings in that reviewed scope. Fresh private manifests, integration, deployment and runtime acceptance remain root's release work. No real SMS delivery, production migration, deployed version, or RK behavior is certified by this review.

## Independent source review

Read the implementation diff and relevant surrounding code, including `phone.py`, `sms.py`, `phone_otp.py`, private route DTO/error handling, legacy auth seams, board `remote_client`, five model tables and startup migration, shared React forms/context/API, live Galaxy/Kiosk entry points, new catalog entries, and focused tests. Earlier findings were read as evidence and checked against the actual frozen source.

- The only sender makes one domestic POST with six ASCII digits, 300-second OTP semantics, ACS3 HMAC, a 3-second HTTP timeout, no automatic retry and no environment/console/fixed-code fallback. HTTP transport logging is suppressed within the SMS context; public exceptions contain safe classifications rather than provider/request bodies.
- Send reservation locks phone state, phone/day, peer/hour and global/day in order. Unique upserts and conditional updates protect first-send and final-budget races. Reservation commits before network I/O. Rejection, unknown delivery and abandoned pending sends retain budget/cooldown; only sent/unknown challenges can be consumed. Phone failures survive resend, flow, purpose and worker changes until the 15-minute lock expires.
- Successful signup consumes the current HMAC/flow/purpose-bound challenge, creates the random public `u_` handle, private identity, permanent claim and one `billing.apply_adjustment(..., 5000, 'signup_grant', ref)` in the same transaction. Existing identities keep their canonical account; historical claims without identity rebuild with zero grant. Full phone values are absent from public user/token/ref projections. The unverified legacy registration path is closed while existing password login remains.
- Binding reserves the cloud user's fixed 15-minute, five-attempt reauthentication bucket independently before checking the supplied current password. Missing/wrong passwords and later OTP/DB failure retain that attempt. The final transaction rechecks user eligibility and password hash, requires the current correct OTP before target-ownership checks, inserts identity/claim and consumes the OTP without a grant. Existing claim history, balances, membership and UUID are preserved. Same-owner valid replay is bounded by the original active challenge and expiry.
- Private HTTP responses use `no-store`. Request validation and SQLAlchemy/response-validation failures are contained without echoing private fields or logging parameterized database exceptions. The five tables are protected from generic destructive migration; the named additive migration verifies actual uniqueness/PK/FK/index validity and the two nonnegative counter definitions before accepting the schema. No old balance rewrite or reverse migration is introduced.
- Board password/OTP login holds candidate credentials apart, confirms cloud `/me`, then checks generation before the synchronous shadow/credential-install seam. The submitted phone or password-login alias does not choose the shadow username. Private phone operations capture the owning Bearer and generation, refuse stale results, and never retry with a new user's token. `bind_reauth_failed` is a completed business refusal and is no longer refreshed/replayed; actual authentication expiry keeps the snapshot-bound refresh path.
- React defaults to OTP and preserves the password tab. Canonical `/me` precedes token installation. Revision/abort/identity guards clear or retire private work on close, method/identity changes and credential replacement. Binding has explicit loading/error/retry, eligibility and read-only masked success. Kiosk uses the real membership account entry; strict mode routes to launcher and refuses local private authentication calls.

The two-cloud empty trusted-proxy list deliberately uses the observed connection peer. Root supplied the deployment observation that neither current container sets `FORWARDED_ALLOW_IPS` and that the Docker peer does not match uvicorn's default loopback trust. The reviewer did not SSH or independently inspect either live configuration. Enabling broader trust is not part of this approval.

## Visual evidence and accepted differences

Applied `ui-ux-pro-max` to the existing Galaxy/Zen and Kiosk theme sources, rather than generating a new design system. Independently inspected the four same-viewport reference/implementation pairs in their side-by-side images and overlays at:

- `output/playwright/phone-otp-2026-11-11/`
- `output/playwright/phone-bind-b5-2026-11-11/`

Also inspected OTP unknown/rejected feedback, the Kiosk binding entry and reauthentication-lock state, and Galaxy masked binding success. These are real browser renders of the application components with isolated Fixture responses; they are not real SMS/account/balance/deployment evidence.

- Layout and hierarchy remain coherent with the existing product: default SMS tab, phone/code grouping, explicit first-signup/50-points-once copy, old-account binding guidance, and one extra current-password field only for binding. Necessary actions remain within the target viewport or in the binding dialog's own scroll area. No overlapping labels, clipped primary action or horizontal overflow was observed.
- Accepted geometry differences are the existing MUI title/action spacing and Kiosk's larger typography/controls. Galaxy's local focused-label/button contrast treatment is retained; Kiosk's jade theme, brand assets and font family are preserved. The simplified reference shell is not treated as a requirement to replace the application's existing navigation.
- Unknown delivery is a warning that still permits verification; rejection is an error with no false success; reauthentication lock clears password and disables confirmation. Success replaces editable private inputs with a server mask and the no-repeat-grant policy. These states remain understandable without relying on color alone.
- The new actions retain the intended 44px/48px/56px touch sizing; fields use actual labels and appropriate tel/current-password/one-time-code semantics.

No all-language visual or native-speaker certification is claimed. Product Fixture references and injected account/password identifiers are absent from the checked UI source; archived evidence remains only under `output`.

## Release-helper review

Independently read the complete 366-line `baseline-diff.patch`, the changed helper seams and offline tests. A fresh comparison confirmed that the recorded patch exactly equals both predecessor-to-current helper diffs. `SHA256SUMS` verified all five listed artifacts.

| Helper | Approved SHA-256 |
|---|---|
| `native-release.py` | `153b6f0538f67544c8ebc1cd04467a49fff5d16195cb6139898194bfe6d17a81` |
| `cloud-release.py` | `e8d5e34677b78f2db01b489ab5608600c91980a10f06cc262c9abfce5beac673` |

The allowlist permits only the build SHA, six exact nonsecret SMS fields (approved sign/template, target path, TEST10/PROD50 and empty trust list), and one site-bound single-file read-only bind. Old non-build environment bytes/order, all eight WeChat fields and their mount, enabled/live and billing/Free0/Max settings, runtime User, network/resources and the rest of HostConfig are preserved. Alternate values, target/User/site drift, existing SMS fields and overlapping mount destinations are refused.

Credential checks use metadata only, with regular-file/symlink/link/mode/owner checks and rechecks before switch/create. The tool does not open/hash credential contents. Prepare keeps full before-image/payload in private files without cutover; apply retains manifest-byte hashing and live config CAS. This approval does not substitute for root's fresh private-manifest review or actual runtime verification. Rollback compatibility remains explicitly refused; claims/tables/balances are not deleted by these helpers.

## Fresh focused verification

Independent commands in this review:

```text
python3 output/wechat-native/run-tests.py tests/web_ui/test_phone_signup_pg.py tests/web_ui/test_phone_bind_pg.py tests/web_ui/test_phone_otp_limits_pg.py tests/web_ui/test_phone_auth_remote.py tests/web_ui/test_phone_otp_api.py -q --tb=line -k 'same_challenge_concurrent or ledger_failure_rolls_back or permanent_claim_without or reauth_limit_is_per_user or bind_failure_rolls_back or one_user_two_phones or global_last_budget or sender_observes_committed or pending_candidate_cannot or private_phone_request_never or bind_password_refusal or database_error_is_contained'
# 18 passed, 78 deselected in 13.19s; PG did not skip.

npm test -- src/features/auth/LoginMethods.identity.test.tsx src/features/auth/PhoneBindDialog.test.tsx src/api.phoneBinding.test.ts
# 3 files passed; 13 passed, 1 strict-mode-only skipped.

python3 output/releases/phone-otp-20261111/tools/test_release_tools.py
# 9 offline tests passed.

shasum -a 256 -c SHA256SUMS
# All five helper artifacts matched (run in the helper directory).

git diff --check 97f4b49e1..2bec82394
# Clean.
```

A focused catalog comparison using the existing project Python environment confirmed exactly 45 additions in each of all 11 PO catalogs, all existing message values unchanged, identical new-key sets, nonempty translations, matching placeholders, and exact compiled-MO values for every new entry. System Python lacked `polib`; switching once to the existing project interpreter resolved that tooling-only check without changing dependencies or product code.

Root separately reported the final combined backend run as 206 passed/one known UUID-schema xfail, the broader frontend run as 87 passed/five mode-conditional skips, strict checks as 14 passed, and normal/strict builds passing. Those reports were not added to the independent counts above or rerun as a second full suite. The two baseline-reproduced old SSO failures are outside this diff; no unrelated repair is requested.

## Parent B6 final handoff

The parent UI review is recorded at `smartbox-software/docs/superpowers/reviews/2026-11-11-launcher-phone-visual-code.md`: visual/frontend Approved after closing response-level stale private-state handling, OTP lock labeling and unbound Cancel/Done semantics. Those approved UI sources were unchanged at the final backend handoff.

The independent backend review is recorded at `smartbox-software/docs/superpowers/reviews/2026-11-11-launcher-phone-backend-code.md`. Read the complete three-product-file change and relevant surrounding store/retirement code and tests. The four phone endpoints enforce strict DTOs, same-origin POSTs, safe errors and `no-store`; the browser receives only the existing opaque HttpOnly session cookie. Password/OTP candidates obtain an in-memory attempt epoch before remote waits, confirm canonical `/me`, and pass locked epoch checks before installation and after retirement. Private operations use the request's original session/generation and cloud credential snapshot across HTTP waits; refresh updates that exact session with CAS and never adopts a newer account. Business password refusals do not refresh or repeat the POST. Legacy register fallback requires the explicit `user_exists` code.

Independent focused B6 verification passed **16 tests, 55 deselected**, using the existing parent Python environment, temporary stores and `httpx.MockTransport`. It covered late password/OTP candidates, private results and refresh across account switches, business password 401 behavior, attempt changes during retirement, strict validation, canonical login and register fallback. The backend diff check was clean. Root separately reported 115 phone/auth/store tests and three shared-retirement checks passing; those were not repeated or added to the independent count. No new blocking backend finding was found. The existing requirement for an authenticated logout remains appropriate; a rejected anonymous logout is not a completed identity change.

No product source was changed by this reviewer. No real credential, `.env`, private deployment manifest or DSN was read; no SSH, business database, SMS provider or RK operation was performed. Deployment observations and actual SMS acceptance must be reported separately by root and the user.
