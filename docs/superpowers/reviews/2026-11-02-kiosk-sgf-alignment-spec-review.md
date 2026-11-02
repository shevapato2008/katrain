# Kiosk SGF alignment — independent specification review

**Verdict: SPEC COMPLIANT for combined Tasks A/B.** No material missing requirement or out-of-scope implementation was found. Proceed to the separately required independent astra/max quality review.

Reviewed the actual uncommitted implementation and tests against `docs/superpowers/plans/2026-11-02-kiosk-galaxy-sgf-replay-alignment.md`, with baseline `07d1ddce9e8808fa6c7b840e1a0cd928048ac4bd`. This review does not rely on the implementers' reported results.

## Requirement evidence

| Requirement | Verified implementation / evidence |
| --- | --- |
| Preserve the existing Galaxy replay algorithm exactly | Compared the complete function text of `parseMove`, `getNeighbors`, `findGroup`, `countLiberties`, `removeCaptures`, and `buildReplayBoardState` in baseline `LiveBoard.tsx` with `src/utils/goReplay.ts:2–144`: all six are exact matches. Only surrounding component-specific comments/lint directives were omitted. |
| Pure shared utility; preserve existing callers | `goReplay.ts` has no imports or runtime dependencies. `LiveBoard.tsx:15–19` imports and re-exports both public functions; the existing `ReplayBoard3D.tsx:5` import remains valid and its tests pass. |
| Position adapter delegates to the shared matrix and preserves orientation | `goReplay.ts:147–163` calls `buildReplayBoardState` once and maps matrix `[y][x]` to GTP `${columns[x]}${y + 1}`. It contains no separate capture or overwrite implementation. Focused 9/13/19-board orientation, capture, explicit-color, empty/`tt` pass, setup-offset, overwrite, and final-coordinate tests exist in `goReplay.test.ts:25–142`. |
| Exact three real SGF fixtures | Byte comparisons against `/tmp/kifu-preview-investigation/{140859,124442,118394}.sgf` all match. Fixture sizes are respectively 2,309, 3,251, and 2,162 bytes. Tests assert 345+2 / 488 / 304 entries and the specified overwrite points and colors (`goReplay.test.ts:19–88`). |
| Both screen consumers use the Galaxy parser and shared replay; no screen `/baipu/load` | `KifuPage.tsx:125–132` and `KifuDetailPage.tsx:61–66,91–107` use the same `../../utils/sgfSerializer` parser imported by Galaxy's `KifuLibraryPage.tsx:37`, followed by the shared adapter. Neither screen imports or calls `BaipuAPI.load`. Tests configure that endpoint to reject and assert it is never called. |
| Reject unusable SGF while allowing setup-only records | Both consumers require trimmed nonempty content and `parsed.moves.length > 0`. Blank, whitespace, junk, metadata-only, setup-only and transport-rejection cases are covered in `KifuPage.test.tsx:45–76,154–176`. |
| Correct cursor, colors, passes and initial setup | Detail entries exclude `parsed.setupCount`; replay includes `setupCount + at` (`KifuDetailPage.tsx:91–107`). Existing controls retain start/previous/slider/next/end behavior. The real-record journey test (`KifuPage.test.tsx:192–222`) verifies each total, the first overwrite, start setup counts and end navigation; synthetic tests cover previous/next/slider, consecutive explicit colors and passes. |
| Preserve cancellation/language; prevent stale detail board/actions | Existing cancelled-response guards remain. Loaded game and errors are keyed by current ID and language (`KifuDetailPage.tsx:53–88`), so a different record/language cannot supply the current board or physical actions while loading or failing. Route-loading and language-loading/late-response regressions are covered. Genuine API errors retain their existing classification and visible failure UI. |
| Preserve physical-board behavior and original SGF | The existing `PhysicalBoardButton` invocation still receives `album.sgf_content` directly (`KifuDetailPage.tsx:220`); cache and navigation tests pass (`KifuDetailPage.test.tsx:225–235` and localization test). No physical-session page, Baipu protocol/API/backend, recent-history persistence, package manifest, or database code is modified. |
| Keep scope bounded | The implementation changes are limited to the owned replay utility/fixtures/tests, `LiveBoard` extraction, Kiosk preview/detail consumers, and directly related component tests. Existing Galaxy limitations are retained rather than expanded. |

## Independently run checks

From `katrain/web/ui`:

```text
npx vitest run src/utils/goReplay.test.ts src/components/live/LiveBoard.test.tsx src/kiosk/pages/KifuPage.test.tsx src/kiosk/__tests__/KifuDetailPage.test.tsx src/kiosk/__tests__/KifuDetailPage.localization.test.tsx src/utils/sgfSerializer.test.ts src/galaxy/components/board/ReplayBoard3D.test.tsx
Test Files: 7 passed
Tests:      104 passed

npx tsc -b --pretty false
Exit: 0

git diff --check
Exit: 0
```

Fixture SHA-256 values:

```text
140859 b70092ab25361d6187a1887d19f7357efeaea4fcf3966159aee9ec2bf4ed32a4
124442 eba67b063cebdb9d1e12380b66ea5d24c80fa5ce358ce5ea1155b8b3b978e40d
118394 062bbdac6085da36af6a022e79173eb308b15bf49e0875ce4cbca136cd8ac752
```

The full-library investigation, browser/device acceptance, production build/import guard, and final astra/max quality approval remain separate controller-owned delivery checks. This stage does not claim those checks have been completed. No product files, database records, device state, or commits were changed by this reviewer.
