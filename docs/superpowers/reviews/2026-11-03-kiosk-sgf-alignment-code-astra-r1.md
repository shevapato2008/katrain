# Kiosk SGF alignment — independent astra/max code review, round 1

**Verdict: APPROVED. No material findings; no required fixes.**

Reviewed the actual working-tree implementation, new utility/tests/fixtures, and affected callers against baseline `07d1ddce9e8808fa6c7b840e1a0cd928048ac4bd`, the repository instructions, approved implementation plan, and investigation. The conclusion is based on direct code inspection and fresh checks, not implementer or specification-review assurances.

## Code assessment

- `src/utils/goReplay.ts:2–144`: all six extracted functions (`parseMove`, `getNeighbors`, `findGroup`, `countLiberties`, `removeCaptures`, `buildReplayBoardState`) have exactly the same function text as baseline `LiveBoard.tsx`, independently compared using the TypeScript AST. The utility has zero imports. `LiveBoard.tsx:15–19` preserves its public exports and existing component/3D consumers.
- `src/utils/goReplay.ts:147–163`: the SVG adapter calls the shared matrix implementation and converts its bottom-origin coordinates to GTP. It introduces no competing capture/overwrite logic. One matrix cell produces at most one colored point, and orientation is correct for the supported 9/13/19 boards.
- `src/kiosk/pages/KifuPage.tsx:120–135`: preview uses the same SGF parser as Galaxy and the shared replay adapter, retains cancellation checks and selected-record action gating, and rejects missing/blank/zero-entry content. Setup-only content remains viewable. Screen preview no longer requests physical-placement steps.
- `src/kiosk/pages/KifuDetailPage.tsx:42–107`: album and parsed content are stored together; current route/language and scoped errors gate both the board and actions. Cancelled responses cannot replace the current record. Cursor entries exclude initial setup, while the board includes `setupCount + at`; recorded colors, passes, captures, reverse navigation, and initial handicap positions remain coherent.
- `src/kiosk/pages/KifuDetailPage.tsx:220` still passes the original SGF to the unchanged physical-board button. Cache/navigation behavior is covered. The diff does not modify physical-session code, backend contracts, database code, recent-history persistence, or dependencies.

The overwrite behavior is appropriate for SGF viewing: FF4 requires executing syntactically correct moves even when they violate playing rules and describes replacing the destination's prior contents. This is supported by the independently opened [Go execution specification](https://www.red-bean.com/sgf/go.html) and [B/W property specification](https://www.red-bean.com/sgf/properties.html). The patch preserves Galaxy's existing limitations; this approval does not claim complete FF4 conformance or physical-board support for the three original records.

## Independently verified

From `katrain/web/ui`:

```text
npm test -- src/utils/goReplay.test.ts src/components/live/LiveBoard.test.tsx src/utils/sgfSerializer.test.ts src/galaxy/components/board/ReplayBoard3D.test.tsx src/galaxy/pages/KifuLibraryPage.test.tsx src/kiosk/pages/KifuPage.test.tsx src/kiosk/__tests__/KifuDetailPage.test.tsx src/kiosk/__tests__/KifuDetailPage.localization.test.tsx src/kiosk/__tests__/KifuPage.localization.test.tsx --reporter=dot
9 files passed; 119 tests passed; exit 0

npx tsc -b
Exit 0

git diff --check
Exit 0
```

Coverage is sufficient for this change: exact real-record overwrite points and totals, frozen Galaxy final positions, capture removal and reversal, passes, explicit colors, setup offsets, coordinate orientation, all replay controls, unusable content, transport failures/retry, route/language loading, late-language responses, and original-SGF physical navigation. The three fixtures independently byte-match the fetched originals in `/tmp/kifu-preview-investigation/`: 2,309 / 3,251 / 2,162 bytes for 140859 / 124442 / 118394 respectively.

Controller-owned RK3562 evidence was inspected separately in `/tmp/kifu-preview-investigation/device-parity-summary.json`: 17 recorded SVG positions match the baseline Galaxy matrix, including the three overwrite transitions and the two initial stones, with zero screen `/baipu/load` requests. This reviewer did not operate the device or repeat its acceptance run. Production build/import-guard verification remains the controller's separately recorded check.

## Nonblocking existing test debt

An additional run of unchanged `src/kiosk/__tests__/KifuPage.test.tsx` produced 13 passed / 14 failed. It still lacks a `KifuAPI.getAlbum` mock and contains obsolete heading/result/navigation expectations. To establish attribution, I reran that exact test against baseline `KifuPage.tsx` supplied directly from `git show` through an in-memory Vite loader: **the same 14 test names failed, with 13 passed and zero unhandled errors**. No product file was replaced. These failures are pre-existing and do not require widening this SGF fix; the full repository test suite is not claimed green.

Only this review document was authored by this reviewer. No product code, database records, device state, deployed services, or commits were changed.
