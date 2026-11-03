# Membership i18n — independent Astra review

Date: 2026-11-04  
Baseline: `8cc4b6dcdd236bd8339643043f176708ff499503`  
Plan: `docs/superpowers/plans/2026-11-04-membership-i18n.md`  
Final verdict: **Approved for integration and the scoped TEST → new PROD release.** No unresolved material code, translation or representative visual findings. This is implementation approval, not a claim that deployment has occurred.

## Resolved findings

**P2 — Ambiguous CNY symbol, resolved.** The initial `money()` helper used `currencyDisplay: 'narrowSymbol'`, producing `￥30` in Japanese, indistinguishable from a yen amount in checkout. It now uses the standard currency symbol while retaining `currency: 'CNY'` and the original amount. Independently checked Intl output (`CN¥30` in English, `元 30` in Japanese) and the added regression; updated checkout screenshots identify CNY clearly. No conversion or billing arithmetic changed.

QA found mobile German refresh/tab clipping, a Kiosk German Max action extending outside its card, and a narrow mobile top-up option overflowing after the currency correction. The final local CSS changes allow the tabs/cards to scroll and grow, keep refresh visible, and reduce only the mobile amount font. Independently inspected the corrected screenshots: card actions remain inside their cards, footer content is reachable, `100 CN¥` fits on one line and the mobile Max/top-up actions are reachable.

The early browser test expected the wrong Galaxy tab key (`api_recharge` instead of shared `api_topup`); this harness mismatch is corrected. The minor missing space between adjacent translated Galaxy sentences is also corrected in the final source and mobile screenshot.

The focused catalog test's in-memory compilation alone was insufficient evidence for shipped MO files. The integrator added separate actual on-disk verification of all 328 keys in all eleven catalogs. Independently verified every MO hash against `output/i18n/compiled-catalog-verification.json`. The release packager also compiles and compares the actual artifact MOs.

## Code and specification review

- Read repository instructions, `katrain-i18n-expert`, the implementation plan and approved R1 report; independently inspected the actual changed product files and focused tests against the baseline. Legacy billing admin and unrelated UI remain outside this review.
- Affected rendered surfaces subscribe through `useMembershipI18n` / `useTranslation`, including quota/receipt/helper components, entry points and membership auth presentation. The generic Galaxy navigation consumers already subscribe.
- Checkout selections retain raw plan/top-up values, and errors retain semantic codes until render. Locale and translation-function identity do not enter order/paid-work scope, polling, quote authorization or identity-cleanup dependencies. Existing abort, idempotency and payment guards remain in place.
- Display locale mappings include the nonstandard project codes. Formatting keeps CNY and `Asia/Shanghai`; raw quota percentages remain numeric for Galaxy progress, Kiosk CSS width and ARIA. German comma-decimal regressions exercise that distinction.
- Known billing errors map to local messages and unknown paid-operation errors use safe fallbacks. Page-local report catches no longer freeze raw exception strings. Only an explicit refunded analysis receipt produces the refund-success claim.
- Membership auth copy is isolated from existing non-membership branches. Kiosk membership help/order bodies use existing scroll zones; wrapping changes are local. Existing shared consumption-dialog typography already permits scrolling, wrapped actions and variable button height.
- No billing backend, price/quota arithmetic, payment authorization or deployment-helper change was present in the reviewed product diff.

## Translation review

Read all 328 Chinese/English pairs and checked the billing, whole-request API fallback, calendar-week reset, renewal, full-use savings, Free eligibility, quote/source, TEST, pending/paid/refund and expiry templates across Traditional Chinese, Japanese, Korean, German, Spanish, French, Russian, Turkish and Ukrainian. No material semantic mistranslation found in those critical messages. Placeholder/catalog coverage is exercised for all keys, not just this semantic sample. The batch workflow loads the complete membership data, and the PO diffs append feature copy without rewriting existing messages.

## Verification and visual evidence

- Read the final execution logs: `output/i18n/ui-final.log` has **14 files / 190 tests passed**; `output/i18n/catalog-final.log` has **14 tests passed**. Read the focused switching, raw numeric progress, safe-error, auth and quote tests themselves; did not duplicate the complete test runs.
- The integrator reports that the required legacy `i18n.py` global sync returned exit 2 for pre-existing missing/default keys. Its unrelated normalizations were restored; the feature PO additions and all-eleven MO compilation/equality checks pass. This does not establish that the unrelated legacy catalog is globally clean.
- Read `output/i18n/strict-kiosk-final.log`: final strict build and both SSO/Kiosk boundary checks passed. The ordinary build previously passed; packaging will rebuild the exact published commit.
- Browser QA reports all **7 current-code checks passing**: six in the post-currency run plus the final focused mobile rerun. Coverage includes all eleven actual PO catalogs on three tabs in both surfaces, German localized percentages with numeric CSS/ARIA, and open checkout/receipt/error switching without extra orders.
- Independently inspected screenshots in `output/playwright/membership-i18n-20261104/`: Chinese Galaxy baseline, German Galaxy 1440×900 and 375px plans, mobile top-up and Max action, Kiosk 1024×600 German plans plus scrolled footer/top-up, German checkout on both surfaces, and the English Kiosk receipt. In particular, `galaxy-mobile-de-topup-action.png`, `galaxy-mobile-de-plans-max.png`, `kiosk-de-plans-footer.png`, `kiosk-de-checkout.png` and `kiosk-en-receipt.png` show the resolved issues and clear payment state. No additional material clipping, overlap or hidden action found in these representatives.
- Independently ran final `git diff --check`: clean.

## Scoped release review

Read the current `server-deploy` instructions and briefly inspected the one-off `output/releases/membership-i18n-20261104/release.py` wrapper and the relevant unchanged native helper contracts. The wrapper packages an exact source commit, overlays only static assets plus eleven PO/MO catalogs onto the captured base image, checks immutable base identities and artifact bytes, and requires the native clone's HostConfig, networks and all non-build environment values to remain unchanged. It does not apply the cutover itself. No blocking issue found in this scoped review; no deployment was executed by this reviewer.

The release owner must still complete the planned published-commit build, four-step integration, TEST-before-new-PROD cutover, actual eleven-language HTTP/catalog comparisons and service/configuration checks. Paused membership, disabled payments, enforced billing, Free 0, Max gate and unrelated containers remain release invariants. Record those deployment results in the release receipt rather than treating this pre-deployment approval as runtime evidence.
