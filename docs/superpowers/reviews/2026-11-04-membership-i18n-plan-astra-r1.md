# Membership i18n — Astra plan review, round 1

Date: 2026-11-04  
Baseline: `8cc4b6dcdd236bd8339643043f176708ff499503`  
Final verdict: **Approved.** The one material finding was corrected and verified in the focused final pass recorded below. No further plan review is needed.

Reviewed the updated implementation plan, repository instructions, `katrain-i18n-expert` and `server-deploy` skills, and the actual membership, checkout, paid-analysis/report, entry-point and membership auth-boundary code. No product files changed; this review did not rerun tests.

## Resolved finding

**P2, resolved — Separate localized percentage text from numeric progress values in the shared contract.**

The initial helper contract did not distinguish display and machine values. The current `usagePercent()` string is parsed back into a number in `galaxy/pages/membership/MembershipPage.tsx:135–136` and used directly as CSS width in `kiosk/pages/membership/MembershipPage.tsx:59–63`. Localizing that shared string to German/French formatting would truncate fractional values through `parseFloat` or produce an invalid CSS percentage.

Verified the revised Task 2 now freezes display-only number formatting, keeps ASCII machine percentages, requires raw bounded `period.percent` for progress/CSS/ARIA, forbids parsing localized strings and requires a focused German comma-decimal regression. This resolves the finding without adding a new test layer.

## Accepted scope and implementation notes

- The updated Tasks 2–4 now give all audited surfaces an owner, including both Research/Reports pages, KioskTopbar, AccountSection and the membership auth boundary. Keep the legacy admin exclusion explicit.
- The updated acceptance criteria explicitly map project codes to Intl locales, including `cn → zh-CN`, `tw → zh-TW`, `jp → ja-JP` and `ua → uk-UA`.
- Apply the existing render-time error requirement to page-local catches as well as hooks: Kiosk Research currently renders frozen `saveError` before the hook error, and both Research pages copy `Error.message`. The plan's updated file ownership covers this; it is not a separate blocker.
- The extracted catalog inventory must include whichever keys those membership auth/research branches actually render, even if their namespace is `auth:` or `research:`. A `membership:*`-only scan is insufficient. The plan already calls for all feature keys, so this is an implementation reminder.
- The eleven-language PO/MO checks, explicit Spanish compilation, CNY/Beijing semantics, stable async/identity boundaries, representative browser checks, four-step integration and TEST-before-new-PROD deployment are proportionate. Preserve the live production resource limits along with the complete configuration (currently 8 GiB memory, 12 GiB memory-plus-swap, 4 CPUs); existing configuration-preservation steps cover this.

No unresolved material plan objections. Proceed with the shared foundation, then the planned disjoint UI implementation tasks.

## Focused correction verification — second and final pass

Re-read the current plan's formatting acceptance criteria and Task 2 only. Confirmed the locale mappings, raw-versus-display percentage separation, frozen helper contract and German numeric regression are explicit. The R1 finding is resolved. **Approved.**
