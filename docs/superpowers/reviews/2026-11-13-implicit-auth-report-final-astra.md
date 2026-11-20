# Implicit authentication and reports — independent final review

Date: 2026-11-13. Reviewer: independent Astra Max final reviewer.

**Result: Approved after I1 follow-up. No Critical or Important findings remain.** Specification compliance was checked before implementation quality/security. The initial Galaxy presentation finding and its closure are preserved below.

## Exact reviewed source

- Child baseline: `6a847cd7b3e6ec45473b6e6d3dff762655c3dff7`.
- Child initial candidate: `a1be352528e7ab5fb0fec03267a3e3064901b512`.
- Child final approved candidate after I1: `17760ba2f592c0feec4feb3f9059e933fec7eeee`.
- Approved plan/spec commit: `4ec4ded953dce7b9c7739ac6d66b2eba76fd7b7d`.
- Published parent baseline: `19aa5487ba5619f5eada71d19c02c12fa0e7a64e`.
- Prepared parent candidate: `6ea5780af16c775cf339d8628b2f24579682d4c8`, in `/Users/fan/Repositories/smartbox-software/.worktrees/freeplay-analysis-20261111`.

Review basis: repository instructions; the approved requirements and release plan; the round-2 plan review; final Kiosk v5, Galaxy v4 and auth Artifacts; and the independent auth review including its closed proof-retirement finding. The original parent's unpublished `168b1b06` daemon work is excluded, as required by the approved plan. The unrelated untracked favicon is excluded and preserved.

## Important finding

### I1 — Galaxy no longer visibly displays analyzed/total moves (closed)

The following finding describes the initial `a1be35252` candidate; its verified correction is recorded in the follow-up below.

- **Locations:** `katrain/web/ui/src/galaxy/components/report/ReportGameCard.tsx:54`–`58`; `katrain/web/ui/src/features/report/ReportProgressColumn.tsx:24`–`25`. The regression is explicitly asserted in `ReportGameCard.test.tsx:24`.
- **Trigger/reproduction:** open the actual Galaxy report list with ordinary completed plus advanced running, or both tiers running. The supplied 1440×900 runtime screenshot shows `44%`, `50%` and `90%` in the external rings, while the card metadata shows only the date, total game moves and result. No visible text shows the analyzed/total frontier. The existing component test reproduces ordinary completed plus advanced `53/120` and asserts that this text is absent.
- **Impact:** requirement R2 explicitly requires the completed/total steps as well as intuitive progress. The approved Galaxy v4 card displays the per-tier `n/N` metadata. The new implementation retains those counts only in native hover titles and `aria-valuetext`; these do not provide the approved visible progress detail, particularly on touch. Rounded percentages also hide individual completed steps between percentage changes.
- **Minimal fix:** restore compact, noninteractive per-tier analyzed/total metadata in the existing card metadata space, or an equally visible location within the approved layout. Use `presentReportTier` values so the text shares the clamped real frontier with the external percentages/rings. Preserve 416×104 cards, 8px row gaps, the external status column and left-menu-only report actions. Replace the absence assertion with ordinary-completed/advanced-running and dual-running count assertions; one updated 1440×900 runtime comparison is sufficient.

## Other specification and quality/security checks

- The 23 frozen auth production/regression file SHA-256 values exactly match the prior approved auth/I1 review. The final backend still validates the login-purpose proof before name branching; reauthentication is independently budgeted; finalization rechecks locks, proof, current hash, name and phone binding. Signup/claim/grant/proof consumption remains atomic. Binding and legacy completion retain the UUID and assets with no grant; legacy completion preserves its password. New implicit accounts receive a random bcrypt password. The optional password flow requires the actor's current verified phone and consumes a fresh proof without replacing identity.
- React and the published parent retain candidate validation, identity-generation guards, safe error envelopes and 204 handling. Progressive same-window entry, conditional original-password input, grant-only notice and proof retirement are present. No unpublished daemon implementation is pulled into this candidate.
- Platform provenance is one nullable additive column, carried through create/get/list and the existing owner-bound offline queue. Trusted game startup stamps KTP before the first engine reply, and saving still works after the live context disappears. Imported SGF metadata does not change source, participation, ownership, ranking or billing authority. Imported/library/research classification keeps priority; unknown old records are not guessed. The existing Golaxy nickname assignment and vision changes are not replaced by the scoped platform additions.
- Report tiers resolve independently with active-before-completed precedence in both status display and menus. Running at 100% stays non-viewable. Text percentage, bar/ring and aria use the same clamped server frontier. Status rows have no button/tab stop or mutation action. Mount/remount refresh remains GET-based, retaining task IDs and polling rather than resubmitting. Paid failures still use the existing refund/re-authorized retry flow; the paid-worker crash/resume enhancement remains deferred and its worker/ledger code is unchanged.
- Root render and preload failures receive visible localized recovery UI. Reload is manual. Session diagnostics retain at most five records with only build ID, timestamp, fixed failure category and safe surface; no exception messages/stacks, account/game IDs, URLs, request bodies or credentials enter that record.
- Independently compared the 37 new translation keys across all 11 PO catalogs: no missing translations, placeholder mismatches or changed pre-existing values. Existing translation-script values are also preserved. The supplied catalog compile/roundtrip evidence is listed below; unrelated baseline i18n issues are outside this diff.
- No production Fixture route or prototype task generator was found in the modified production auth/report routing and presentation paths.

## Visual review

Inspected the approved references, actual React screenshots, same-size side-by-side comparisons and overlays in `output/playwright/implicit-auth-report/`, plus `output/playwright/implicit-auth-{kiosk,galaxy}-name-{side-by-side,overlay}.png` and the auth comparison record.

- Kiosk: 1024×600, 224px preview and 752px list, 624×74 cards with 8px gaps, external 120×74 two-row bars, 14px tier names, 12px percentages and 44px selected-delete target match the approved compact composition. The product's existing navigation/icon/font treatment and actual replay board remain; sample names, dates and game positions differ from the Artifact without changing the task semantics.
- Galaxy: 1440×900, 416×104 cards with 8px gaps, external 126×74 rings and 48px left-menu actions match the required geometry. No report action remains inside the information card. Existing product board rendering, playback controls and sidebar styling remain. The initial missing-count difference I1 is closed by the verified follow-up below.
- Auth: the same-window name step retains the approved panel/modal geometry, field order, minimal copy, verified mask and main action; Galaxy keeps its real page background and no guest entry. The comparison record explains the established runtime font and test-only background translation differences, and that the final icon correction followed the first snapshots. Frozen reviewed source includes the corrected icons.

## Verification and limits

Independently rerun for this review:

- Focused report/model/origin/card/page/polling and root startup/diagnostic suites: **100 passed across 10 files**, zero failures.
- Parent `node setup-wizard/tests/ui/launcher.phone.test.js`: **passed, 0 failed**.
- Frozen auth hashes: **23 matched**.
- New catalog checks: **37 keys × 11 locales**, no missing values/placeholder mismatches; previous values preserved.
- Production child diff (`katrain`, `scripts`, `tests`) and parent diff whitespace checks: clean. The complete child diff has only trailing blank-line warnings in design/review documentation; these are not release findings.

Coordinator-supplied evidence, not independently rerun by this reviewer: 159 unique auth backend cases; provenance SQLite 73 plus engine 43 and additive PG 1; React aggregate 349 passed with 10 expected mode skips across 29 files; parent 179 focused plus the auth I1 subset of 55; startup 7; 407 translations compiled with 11 catalog roundtrips. Full web and strict 2D builds passed before the final Galaxy-only correction; the strict build was 44MB with clean Box SSO boundaries and no Galaxy/three.js or retired routes. The coordinator will regenerate final release artifacts from the approved commit.

No PG execution, SMS, paid analysis, device writes, SSH, deployment or commits were performed. Deployment/runtime acceptance remains the coordinator's required TEST → PROD → idle-RK step. This review is of the exact candidate commits above, not a claim that publication or device acceptance has already occurred.

## I1 follow-up — Approved

Rechecked child `17760ba2f592c0feec4feb3f9059e933fec7eeee` and unchanged parent `6ea5780af16c775cf339d8628b2f24579682d4c8`. The complete child delta from the initial reviewed candidate contains only `ReportGameCard.tsx` and its focused test.

Each active tier now renders its full existing localized label and `analyzed/total` in the card metadata row, using the same `presentReportTier` result as the external ring. Ordinary completion plus advanced running exposes the advanced count; dual-running exposes both counts. The metadata is noninteractive, with report actions still confined to the left menu. No task, auth, backend, billing, translation-key or Kiosk changes are included.

Independently reran the Galaxy card and report-page suites: **27 passed across 2 files**, zero failures. The correction's `git diff --check` is clean.

Inspected the refreshed actual Galaxy 1440×900 screenshot, same-size comparison, overlay and metrics. The first card visibly shows advanced `82/187`; the second shows ordinary `100/200` and advanced `180/200`. Cards remain 416×104 with 8px row gaps; external status columns remain 126×74; internal report buttons remain zero; page overflow remains zero. The visible counts and 44%/50%/90% rings agree. No additional Kiosk capture or broader test matrix was needed.

**I1 is closed. The final child and prepared parent candidates above are approved for the planned publication and deployment workflow.**
