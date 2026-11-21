# Signup 20 / retire weekly free — independent Astra Max code review

Reviewer: fresh independent `gpt-6.2-astra`, reasoning max, `/root/astra_max_signup20_code`; read-only review of both final worktrees.

**Specification: Approved. Code quality: Approved.**

Review followed the first-phone transactional grant and amount-independent historical dedup, strict 0/2000/5000 response validation, modern/legacy retirement, stale free-quote rejection before new authorization, existing-operation/owned precedence, and old task settlement/refunds. It independently checked all 11 language resources, 15 changed keys and tracked compiled catalogs, plus 5 launcher languages and their placeholders.

Findings fixed before approval:
- First-verification hints are shown for actual new registration, not grant-zero legacy profile completion. Launcher uses the already-authoritative register/complete distinction and clears hints on mode changes/stale callbacks.
- Shared continuation/registration receipts say only the actual points received, without incorrectly calling an old-account phone binding a new registration.
- Launcher script reference carries a version query so old cached JavaScript cannot interpret new `{points}` templates or ignore a 2000 receipt.

Verification evidence:
- Backend: 16 focused modules, 344 passed; 1 existing `test_board_mode_balance_needs_online` login-401 failure was reproduced on a clean 26e827f19 archive in the same environment. Dedicated loopback PostgreSQL with a TEST identity covered new gifts, all three concurrent paths, historical receipts and old free-task authorizations; fake SMS sender only.
- Frontend: 20 Vitest files, 250 passed / 5 build-branch skips. Reviewer fixes subsequently passed 43 affected phone-component cases; i18n consistency/compilation passed 12 cases and final 11-language receipt text/placeholder checks. Representative Vite/Chrome Galaxy1440×900 and Kiosk1024×600 previews were inspected; member weekly limits were retained.
- Launcher: 77 auth/template Python cases, 138 logic cases and phone-interaction suite passed. Final hint/cache/neutral-receipt corrections passed 6 focused Python cases and the phone interaction suite. No true SMS or payment.
- Root independently checked strict monetary response parsing (including rejected bool/float/string), new grant2000, trusted-free retirement, final UI test log and previews, launcher syntax and 5-language placeholders, and both trees' whitespace checks.

No unrelated BoxSSO baseline failure or phone-login policy was changed. Release builds, public refs, container/board source verification and device acceptance are separate deployment steps, not claimed by this review.
