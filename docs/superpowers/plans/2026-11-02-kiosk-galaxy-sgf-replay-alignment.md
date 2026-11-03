# Kiosk / Galaxy SGF replay alignment

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. The user explicitly requests parallel implementation of independent files, overriding the skill's default sequential dispatch. Plan review: independent gpt-6-astra / max, at most two rounds. Final code review: independent gpt-6-astra / max; fix findings until approved.

**Goal:** Make Kiosk library previews and screen replay accept the same SGF records and show the same positions as Galaxy, including the three reported Wu Qingyuan records. Determine the full-library rate of rejection by the existing strict Kiosk interpreter. Do not delete or modify database records.

**Architecture:** Extract Galaxy's existing pure move replay functions into a lightweight shared utility, retaining its existing exports for callers. Kiosk's screen-only preview and detail page will use the same SGF parser and replay utility as Galaxy. The camera/LED stone-placement session remains a separate consumer of backend-authoritative steps; this change does not alter that protocol.

**Tech Stack:** Existing React / TypeScript / Vite / Vitest frontend; read-only Python / PostgreSQL audit. No new runtime dependencies.

## Chunk 1: Investigation and acceptance contract

### Confirmed evidence

- Device: RK3562, Chromium page `http://127.0.0.1:8081/kiosk/kifu`, query `wuqingyuan`; actual screenshot and HTTP evidence are under `/tmp/kifu-preview-investigation/`.
- The three album details return 200. Their POST `/api/v1/baipu/load` calls return 422 `Space occupied`. Two 1989 control records load successfully.
- First occupied intersections (move counts exclude initial handicap stones):
  - album 140859, `第二局成名作`: move 224, black A5, white from move 163 still present; 345 moves plus 2 setup stones.
  - album 124442, `吴清源名局细解第10册第1局总第37局`: move 250, white T10, black from move 245 still present; 488 moves.
  - album 118394, `大胆的布局（木谷、吴十番棋第六局）`: move 191, black C9, white from move 132 still present; 304 moves.
- Independent execution of the current Galaxy TS parser and board function confirms the same first occupied points as the backend. Thus these examples are not an earlier capture-calculation discrepancy.
- Root cause: Kiosk `KifuPage.tsx` and `KifuDetailPage.tsx` call `BaipuAPI.load`; `build_steps_from_sgf` invokes `BaseGame._validate_move_and_update_chains`, which rejects occupied intersections and suicide. Galaxy `KifuLibraryPage.tsx` uses `sgfToMoves`, and `LiveBoard.buildReplayBoardState` writes the recorded color over the previous occupant and proceeds.
- Important correction: rejection by Go playing rules is not proof of invalid SGF. SGF FF[4] instructs viewers to execute syntactically correct B/W moves even if illegal under playing rules. Its Go execution procedure explicitly overwrites the destination regardless of its previous content. Setup properties also overwrite and must not be interpreted as normal capturing moves.
- Primary sources: https://www.red-bean.com/sgf/go.html and https://www.red-bean.com/sgf/properties.html . These were read during this investigation.
- Initial scope: all 1,231 public Wu Qingyuan records tested, 32 strict rejections (31 occupied, 1 single-stone suicide). A fixed-ID sample of 886 public records yielded 3 additional rejections. These are interpreter rejection rates, not invalid-SGF rates.
- Full read-only exports completed: production and test each contain 176,949 physical rows and 176,690 visible rows. Both have the same set of 176,940 unique SGF hashes, despite differing recent IDs. Strict outcomes joined back by hash independently yield 718 rejected visible rows (0.406361%) per environment. Independent mainline grammar/move/setup checks flagged 16 records separately; see the evidence report for the exact categories and limitations.

### Scope decisions

1. No deletion, quarantine, metadata rewrite, SGF normalization, import, database migration, or server restart. The user's latest instruction revoked deletion.
2. Fix screen preview and screen replay together. Fixing only the small library preview would leave the same records unviewable in the detail page.
3. Reuse actual Galaxy behavior instead of introducing a third Go implementation. Extract the pure functions so Kiosk does not import React/MUI/Canvas component code just to calculate positions.
4. Preserve the current Galaxy algorithm in this patch, including capture, pass, explicit-color and handicap-count behavior. This patch does not claim full FF4 conformance: compressed setup ranges, AE and self-capture have existing limitations in Galaxy and are not silently redefined here. Enumerate any such cases discovered by the full audit separately from occupied-intersection compatibility.
5. Genuine data transport failures or empty/missing usable SGF continue to show a load failure. Because `sgfToMoves` is tolerant and does not throw for blank/junk input, define usable screen content as nonempty SGF text with at least one parsed move or setup stone (`parsed.moves.length > 0`); test blank, junk, and valid setup-only records. Do not fabricate a successful empty board for an absent record.
6. The separate recent-history finding is documented in the final result, without implementing account-history persistence as part of this SGF fix.

### Acceptance

- The three real records produce successful Kiosk previews and enabled `查看棋谱`.
- Kiosk detail reaches all 345 / 488 / 304 recorded moves, supports start / previous / slider / next / end, and retains the two initial handicap stones at move zero for album 140859.
- For the same parsed moves, cursor and board size, Kiosk's SVG stone coordinates and Galaxy's shared replay matrix agree, including at the first overwrite and at the end.
- Standard captures, empty and `tt` passes, nonalternating explicit colors, handicap offsets and existing Galaxy consumers retain their behavior.
- No Kiosk screen preview/detail call to `/baipu/load`; actual physical-board sessions continue to use backend-authoritative steps.
- No runtime dependency additions, heavy component dependency from the shared utility, or database mutations.

## Chunk 2: Parallel implementation

### Task A: Shared pure replay implementation and real-record fixtures

**Owned files:**
- Create `katrain/web/ui/src/utils/goReplay.ts`.
- Create `katrain/web/ui/src/utils/goReplay.test.ts`.
- Create `katrain/web/ui/src/utils/__fixtures__/kifu-140859.sgf`, `kifu-124442.sgf`, `kifu-118394.sgf` from the exact HTTP-fetched contents in `/tmp/kifu-preview-investigation/`.
- Modify `katrain/web/ui/src/components/live/LiveBoard.tsx` only to import/re-export the extracted pure functions.

**Frozen interface for Task B:**
```ts
export function parseMove(move: string): [number, number] | null;
export function buildReplayBoardState(
  moves: string[], currentMove: number, boardSize: number,
  stoneColors?: ('B' | 'W')[], handicapCount?: number,
): { board: (string | null)[][]; moveNumbers: (number | null)[][];
     lastMove: [number, number] | null; lastPlayer: 'B' | 'W' };
export function buildReplayPosition(
  moves: string[], currentMove: number, boardSize: number,
  stoneColors?: ('B' | 'W')[], handicapCount?: number,
): { black: string[]; white: string[]; last?: string };
```
`buildReplayPosition` delegates to the matrix function and maps x/y-bottom to GTP. It must not introduce a second capture or overwrite algorithm.

- [x] First add tests using real records and focused synthetic capture / pass / setup examples. Confirm expected failure before implementation.
- [x] Move the existing pure helper functions `parseMove`, `getNeighbors`, `findGroup`, `countLiberties`, `removeCaptures`, `buildReplayBoardState` into `goReplay.ts` without changing their semantics. Keep named exports from `LiveBoard.tsx` so existing 3D and other consumers still work.
- [x] Add the small position adapter. Test no duplicated black/white points, proper coordinate orientation, and parity across real-record start / overwrite / end positions.
- [x] Run focused utility and LiveBoard tests. Self-review and report exact files/results. Do not commit other workers' files.

### Task B: Kiosk screen consumers and component regressions

**Owned files:**
- Modify `katrain/web/ui/src/kiosk/pages/KifuPage.tsx`.
- Modify `katrain/web/ui/src/kiosk/pages/KifuDetailPage.tsx`.
- Modify `katrain/web/ui/src/kiosk/pages/KifuPage.test.tsx` and directly related detail tests only when their old backend mocks require updating.

**Use frozen shared interface above; do not edit Task A files.**

- [x] First add a failing regression proving that an occupied-point record remains viewable when `BaipuAPI.load` would reject. Confirm the existing implementation fails.
- [x] Library preview: fetch detail with the existing Kifu API; require usable SGF; parse with `sgfToMoves`; calculate final board through `buildReplayPosition`. Preserve selected-ID cancellation, board size, loading/error and language handling.
- [x] Detail: keep the loaded album plus `sgfToMoves` result, deriving entries from parsed moves/colors and cursor excluding initial `setupCount`. At cursor zero include initial setup stones; at cursor k replay `setupCount + k` entries. Use the shared position adapter for SVG coordinates. Do not synthesize backend Baipu steps.
- [x] Keep true parse/transport failures visible and prevent stale prior-record board data while a different ID/language loads.
- [x] Keep physical-board button navigation and cached SGF behavior intact. No changes to `BaipuSessionPage`, baipu API or backend.
- [x] Update tests that previously mocked backend steps to use actual SGF. Test successful overwrite preview, detail navigation before/after overwrite, initial handicap and actual API failures.
- [x] Run focused Kiosk tests. Self-review and report exact files/results. Do not commit other workers' files.

### Task C: Read-only full-library investigation (controller, alongside A/B)

**Files:** diagnostics under `/tmp/kifu-preview-investigation/`, with a compact evidence summary in repository review documents after results are known.

- [x] Finish production SGF export and test hash manifest; verify counts and compare `(id, sha256)` so one shared replay audit can represent equal snapshots. Scan any differing content independently.
- [x] Run existing strict interpreter on every physical record using local worker processes. Join results by exact SGF SHA to each environment independently, preserving its row multiplicity and duplicate/hidden flags; hash-set equality alone does not establish equal rejection rates. Record album ID, source path, SGF hash, first failing node/move and exception. Report visible-library and all-rows denominators separately; do not derive prevalence from the earlier sample.
- [x] Examine every error category for setup/range/clear/board-size/rules cases. Classify results as strict Go-rule rejection, interpreter limitation, actual parse failure, or unresolved; none becomes a deletion list.
- [x] Check confirmed occupied examples with the same Galaxy parser/replay helper; identify any additional source-data or format limitations without broadening this fix silently.

## Chunk 3: Review, integration, verification

- [x] Independent astra/max plan review round 1: APPROVED, no material findings. Incorporated nonblocking usable-content, per-environment audit denominators, and physical-session limitation clarifications; second round unnecessary.
- [x] After A/B implement, controller checks spec compliance; request independent review if any uncertain contract remains. Then dispatch independent astra/max code reviewer with final diff, plan, focused tests, real record evidence and known scope.
- [x] Independent astra/max code review round 1 explicitly APPROVED, with no material findings or required fixes. Keep review findings/results in `docs/superpowers/reviews/2026-11-02-kiosk-sgf-alignment-*.md`.
- [x] Run the combined focused tests plus SGF serializer and existing replay/3D consumer tests. Run TypeScript build and the Kiosk 2D build/import guard. Do not expand to unrelated full backend regression.
- [x] Run a representative 1024x600 preview of the real three records through a temporary local frontend/dev or built preview using RK3562 API forwarding. Check previews, one overwrite cursor and end/start navigation. Keep real SGF records/API, no production fixtures.
- [x] Served the local Vite frontend through temporary reverse forwarding on actual RK3562 with its real API; no deployed files replaced or services restarted. Original URL restored. This is a dev runtime smoke check alongside the successful production Kiosk build, not a deployment of the built files. No production release is included unless the user requests integration/release.
- [x] Final report: root cause with normative source links, exact full-scan rejection counts and categories, changed files, test/review result, screenshots and any remaining limits. State explicitly that zero database rows were changed/deleted and whether the fix is local or deployed. Explicitly state that the three original records still hit the existing strict 422 if opened as physical-board sessions; screen compatibility and camera/LED guidance have different contracts.
