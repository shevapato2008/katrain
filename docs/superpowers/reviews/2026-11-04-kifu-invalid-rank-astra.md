# Kifu Invalid Rank — Independent Astra Review

## Plan review — R1 (2026-11-04)

**Decision: APPROVED.** No blocking findings; a second plan-review round is unnecessary.

Reviewed `docs/superpowers/plans/2026-11-04-kifu-invalid-rank-display.md` against the current formatter, API display fields and existing regression assertions, Kiosk/Galaxy call sites, and the saved-game rank wrapper.

- **Contract:** The API already distinguishes a validated empty display value (`''`) from an optional/missing display field. Existing backend tests explicitly preserve an invalid raw rank while returning an empty display rank. Checking `displayRank === ''` before the fallback loop correctly respects that authoritative result, including when the raw value happens to look valid.
- **Compatibility:** The proposed exact check preserves existing `null`/`undefined` legacy fallback and noncanonical whitespace fallback. It leaves unknown placeholders, generic `formatRank` free text, professional/unspecified Chinese dan wording, and explicitly amateur ranks unchanged. `getListRank` retains its existing nullish promotion for saved-game ranks.
- **Coverage:** Kiosk list/detail/report and Galaxy list/report paths already use the shared formatter. One formatter regression covering the empty/nullish/whitespace boundary, one existing-page regression per interface, and the existing saved-game tests sufficiently cover this patch. The planned failing-then-passing targeted run and one actual Galaxy preview are proportionate; no new backend tests, full suite, screenshot system, or broader filtering is needed.
- **Scope:** The one-line guard and explanatory comment are the smallest correction. No database, API producer, permissions, page design, or rank classification changes are required.

This is a plan-only review: no product code was modified and no tests were executed. The restricted album data directory was not accessed. Implementation review remains a separate subsequent step.

## Code review — R1 (2026-11-04)

**Decision: APPROVED.** No blocking findings.

Reviewed commit `e2f549af44b39a92437851e3ea34024963db9f4d`. Its complete file list contains exactly the approved formatter, three test files, and the plan. The only production change is the exact `displayRank === ''` early return plus its contract comment; the existing fallback loop, generic formatter, page implementations, and saved-game wrapper remain unchanged.

- The guard matches the approved API authority boundary without suppressing nullish or whitespace legacy fallback. Existing professional, amateur, unspecified-dan, kyu, and saved-game behavior remains covered by the targeted tests.
- The new formatter and two page regressions exercise the observed raw-value leak while retaining names and the valid opponent rank. The recorded RED log shows all three new regressions failing before the guard; it also records the pre-existing Galaxy retry test's extra request.
- The additional Galaxy test edit only removes the initial card click before automatic preview readiness. It still waits for the initial board, switches language, observes the failed second request, clicks the same card to retry, and asserts both the third request and restored board. This is a bounded synchronization correction and does not weaken the intended retry behavior.

Independent verification was run in the working tree at `9e2bec2964b5bb89fc6e104626469866bd6a5f94`; the four reviewed source/test files and saved-game wrapper/tests were checked against the reviewed commit with no differences:

```text
npm test -- src/utils/rank.test.ts src/kiosk/pages/KifuPage.test.tsx src/galaxy/pages/KifuLibraryPage.localization.test.tsx src/kiosk/utils/listRecordPresentation.test.ts
Test Files  4 passed (4)
Tests       60 passed (60)
Exit code   0
```

Independent test log: `/tmp/kifu-empty-rank-astra-green.log`. The scoped commit diff also passes `git diff --check`.

No product files were changed during review; no merge or deployment was performed. The restricted album data directory was not accessed. The planned actual-page preview remains with the parent release task after deployment.

## Post-merge test follow-up (2026-11-04)

**Decision: APPROVED.** The approval of `e2f549af44b39a92437851e3ea34024963db9f4d` remains valid.

Reviewed the complete diff of `bd5a48a4d0c268437917e9e7fa26d9fe53dd4a5e`: it changes only the existing Galaxy repeat-click test. Waiting for the automatic initial board before exercising an already selected card makes the test precondition explicit. Both subsequent same-card clicks, both board-presence checks, and the exact `getAlbum` call-count assertion of one remain intact. This does not weaken the tested behavior and changes no production code.

The parent reports the four targeted files pass all 60 tests after this change. Per the bounded follow-up request, this review inspected the diff without repeating that test run or expanding regression scope. No blocking findings.
