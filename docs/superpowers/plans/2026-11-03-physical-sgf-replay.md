# Physical SGF replay transaction support

> **For agentic workers:** REQUIRED: superpowers:subagent-driven-development. Independent astra/max plan review at most two rounds; parallel owned-file implementation; spec review then independent astra/max code review, fixing until approved.

**Goal:** Make the three reported SGFs playable on the physical board with correct, explicit replacement/repetition/self-capture behavior, and keep backend, Galaxy/Kiosk screen and saved history positions consistent.

**Architecture:** The backend interprets recorded SGF operations permissively under FF4 and emits authoritative pre-removal, placement and post-removal instructions without changing actual game-rule validation. A physical step is committed only after all its actions finish. Existing camera setup mode, IDs and LEDs implement removal/position convergence. The shared screen matrix gains the corresponding self-capture and setup semantics. Account history persists only completed backend-step cursors using replay schema version2.

**Tech Stack:** Existing Python SGF parser, pure board operations, FastAPI, TypeScript shared replay, physical reducer/hook and existing camera/LED/capture interfaces. No new dependency or vision infrastructure.

## Chunk 1: Evidence, scope and frozen contract

### Authorization and actual problem

The user explicitly chose “一起实现完整回放支持” after being told that FF4 self-capture changes some Galaxy/Kiosk positions. This resolves the earlier semantic scope question; no further approval of that scope is needed.

Currently `/baipu/load` replays the WHOLE SGF strictly before returning. These records therefore show 没读出这份谱 immediately, rather than guiding hundreds of moves and failing later. The first occupied moves are224 A5 /250 T10 /191 C9, but there are many later operations too. Under the previous screen interpretation, records140859/124442/118394 contain respectively47/74/50 opposite-color replacements and37/96/32 same-color repeats. 140859 and124442 also contain own zero-liberty moves.

FF4 primary references: https://www.red-bean.com/sgf/go.html and https://www.red-bean.com/sgf/properties.html . SGF viewing executes B/W even when illegal under playing rules; destination is replaced, opponent captures removed, then zero-liberty own group removed. Setup AB/AW overwrites without captures; AE clears only selected points. Actual game `BaseGame.play` remains strict.

Current Galaxy extraction removes opponent groups but not its own suicidal group. Correcting it changes140859’s terminal count233→232;124442 retains259 terminal stones but differs at intermediate steps;118394 remains202. Final counts alone are insufficient acceptance.

Independent diagnostic oracle `/tmp/baipu-feature-investigation/reference_ff4.py` uses sgfmill1.1.1 parser/Board.play, explicit FF4 setup assignment and destination clearing. Its `/tmp/baipu-feature-investigation/ff4-golden.json` records hashes for EVERY state (initial empty and every dense backend step):347/488/304 steps. Copy the compact golden into test fixtures with provenance; no runtime sgfmill dependency.

### Scope boundaries

- No kifu rows are deleted or rewritten. Reject genuinely malformed/out-of-board/overlapping AB/AW instructions with a clear parse error; occupied moves/self-capture are not such errors.
- Support all physical action types needed by these full records, plus preserve existing AB/AW/AE and square9/13/19 core tests; actual hardware remains19x19.
- The screen parser's general compressed-setup/AE limitations are pre-existing and absent in the audited176,949-record corpus. This patch fixes its observed self-capture and initial-setup semantics; it does not build a new general SGF tree/parser or claim universal FF4 conformance.
- Preserve original dense operation indices. Do not insert synthetic “remove” records into steps; saved cursor, captured frame indices and user SGF move references must not drift.
- Actual camera hardware may be unavailable on RK3562. Verify through deterministic hardware fakes and manual runtime, and report that limit honestly; do not expand into camera repair.

### Backend step contract

Keep existing `kind: setup | move | pass | clear`, dense `move_index`, SGF property, canonical row0-top/col0-left, color and final board_hash. Add:

```ts
pre_removed: {row:number; col:number}[]; // before placement, never mixed with removed
requires_placement: boolean;           // false for same-color repeat/pass/clear
```

Both new fields may default to []/true in response/client types for legacy test/caller compatibility, but v2 backend fills them explicitly. `removed` contains removals AFTER the recorded placement, including the just-placed own stone/group for self-capture. `pre_removed` never deletes the replacement stone after it is placed.

`BAIPU_REPLAY_VERSION=2` lives in tiny `katrain/core/baipu_identity.py`, owned/created by the account-history foundation worker. Core imports it; no worker edits that shared identity file concurrently. `/baipu/load` returns replay_version2. History identity includes version; no unknown-version browser cursor import.

- Empty point B/W: requires_placement=true, no pre-removal, normal opponent then own captures.
- Opposite-color occupied point: pre_removed contains old point, requires_placement=true; apply replacement then normal captures.
- Same-color repeat: requires_placement=false, retain the recorded move/index; evaluate recorded capture/self-capture semantics, but do not wait for an impossible new physical stone event.
- AB/AW: direct overwrite without opponent/self captures; opposite old color becomes pre-removal, identical old color needs no placement. Preserve raw expanded order and repeated values as individual existing operations; reject points simultaneously assigned conflicting colors within the same setup node.
- AE: only actual removed points, requires_placement=false. It requires physical removal and must not be blindly timer-skipped.
- Pass: no physical action; preserve recorded player via property and existing pass fields, and correct AI next-player derivation without silently changing unrelated APIs.

`expected_board_from_steps`, frontend `replayBaipuSteps` and `replayBaipuMatrix` apply pre-remove → recorded placement → post-remove. Preserve legacy board_hash values for ordinary legal positions where practical. New board arithmetic is a pure SGF replay implementation inside core/baipu.py; do not make BaseGame permissive.

### Physical transaction contract

Persisted `k` means exactly k fully completed backend steps. Hold k fixed while current step runs:

1. Establish/restore authoritative board before the step on entry/resume/undo.
2. If pre-removal exists, show blue removal at the original points and converge to the cleared intermediate board.
3. If a placement is required, arm empty-to-stone detection on that intermediate board and show target color. Confirm exact coordinate+color.
4. If post-removal exists, converge to authoritative final board with blue removals; no next-move promotion is allowed in this phase.
5. Only then invoke completion once, persist k+1 and capture a completed frame. Final step cannot enter done until removals finish.

Placement acknowledgement and transaction completion are distinct. A one-motion replacement can be acknowledged when the required new stone is actually observed at its point and all other cells match the pre-placement board except allowed post_removed stones that the user may already have lifted. This includes the post-placement/pre-capture board and partial post-removal boards; acknowledge placement then enter post-removal convergence, rather than waiting for the final board before displaying removal guidance. A final self-capture board may equal the cleared intermediate/entry board: that equality is NEVER evidence that its required placement occurred. Require a separate correct-color placement observation or an explicit operator switch to manual confirmation for such a transient move. Post-removal promotion stays disabled and cannot count the following same-point repeat. Same-color no-change operations and passes can auto-complete after the current entry board is verified. Auto-skip only operations requiring neither placement nor removal.

Reuse existing setup mode and setup_id echo; every entry/pre/post target has a fresh ID tied to session generation+k+stage. Ignore late/nonmatching completion/progress events. Undo, pause/resume, source/identity change and unmount invalidate transient commands/timers. Do not call onMatched twice or leave old lights on after load failure. Keep k unchanged on undo of an unfinished transaction; restoring last completed position is sufficient.

The existing 10-second adopt(observedBoard) escape hatch must NOT certify a non-authoritative position. Recheck resends the unchanged authoritative current-stage target with a new setup ID. Offer explicit switch to manual confirmation using existing action patterns when recognition cannot verify a transient placement; this disarms camera/monitor and retains backend authoritative boards and ordered instructions. Manual completion is explicitly operator-confirmed, not camera-verified. No implicit observed-board adoption.

Camera reducer/hook may extend its current stage/reason while retaining existing setup/await/advancing presentation. Do not create another capture-rules implementation in the browser; all target matrices come from authoritative step instructions. Manual and collection modes expose the same ordered pre-remove/place/post-remove confirmation using existing status-card/button patterns.

AI hint fallback: after an applied replacement/repetition/self-capture/clear, send current authoritative board as initial stones instead of an illegal historical move list. Preserve recorded next player, including passes. No full hint-engine rewrite.

Collection: capture only final settled board for a completed step. If upcoming operation requires removal/replacement/clear, keep capture LEDs off; do not label a blue-removal LED as red/green training truth or light a later move before pending removal. Distinguish “nonfinal frame with no guidance LED” from actual final frame by remaining operation index, not merely next placement index. Keep dense indices and autolabel reconstruction authoritative. Existing red/green labels/schema need no blue-class extension.

New capture manifests pin replay_version2 and exact SGF hash. BEFORE idempotent slot reuse, overwrite/append, or autolabeling, validate pinned SGF/size/index and every archived real-frame board_hash against the interpretation being used. Current manifests have no replay version; compatible legacy archives may continue only when existing hashes prove compatible (initial empty frame is handled explicitly). Missing/mismatched real-frame hashes or different SGF fail clearly and preserve all archived files; overwrite_existing must not bypass this guard. Do not add a legacy interpreter or migration. The same small validator is used by capture and offline autolabel; new manifests can also freeze authoritative step instructions if helpful, but no schema redesign is required.

## Chunk 2: Owned parallel tasks

### P1 — backend FF4 step builder and capture contract

**Own:** `katrain/core/baipu.py`; `katrain/web/api/v1/endpoints/baipu.py` response fields; narrow `core/baipu_capture.py` and `katrain/vision/tools/baipu_autolabel.py` archive guard; focused `tests/test_baipu_load.py`, `test_baipu_api.py`, `test_baipu_capture.py`, `tests/test_vision/test_baipu_autolabel.py`; golden fixture `tests/data/baipu_ff4_golden.json` copied from the independent diagnostic.

- [ ] Failing tests first for opposite overwrite, same-color no-placement, single/multistone self-capture, setup without captures, AE and malformed coordinates/setup overlap. Preserve ordinary captures, ko-recapture viewer behavior, passes, index/hash and9/13/19 cases.
- [ ] Implement pure deterministic FF4 record replay without strict BaseGame construction. Validate coordinates before indexing; no negative-index wrap. Keep actual gameplay validation untouched.
- [ ] Emit v2 fields and version, update authoritative expected-board and next safe capture guidance behavior. Preserve source SGF and dense step indices.
- [ ] Verify all intermediate states for three real SGFs against independent golden hashes, not only terminal counts. Test replacement target is not in post-removed unless self-captured.
- [ ] Update collection LED/no-LED metadata narrowly and test with fakes; no hardware writes or new training class. Add capture/archive identity/hash validation before reuse/write and before autolabel, including a legacy AB/AW example where v1 captured a stone but v2 setup retains it. Prove incompatible archives remain byte-for-byte untouched and compatible legacy archives still work.

### P2 — physical transaction UI

**Own:** `kiosk/hooks/physicalBaipuMachine.ts`, `usePhysicalBaipu.ts` and tests; `BaipuSessionPage.tsx` and its physical/session tests. P3 owns shared screen/types/renderers/hints; coordinate the frozen v2 fields and do not edit P3 files. Coordinate with H3 (account frontend) via the frozen hook; do not edit its files, KifuPage, PhysicalBoardButton or history PO keys concurrently.

- [ ] Failing tests first for camera/manual pre-removal, same-color repeat, self-removal and final capture completion. Test stale setup IDs and one-time completion.
- [ ] Consume the v2 dumb renderers from P3 and implement atomic physical transaction in reducer/hook/manual UI. Entry/resume/undo uses the last completed board; k changes only on completion. Use setup_id and serial IO ordering, generation cancellation and post-removal promotion guard.
- [ ] Wire `useBaipuSessionHistory` supplied by H3 after successful authoritative load. Existing resume/restart choice reads returned durable cursor. Save from committed cursor effect/event, not inside React updater; completed history stays, restart saves0. Do not duplicate authenticated history transport.
- [ ] Collection UI calls capture only after ordered physical actions complete; use P3 hint snapshot fallback. Test clear/no-op actions and preserve ordinary placement behavior.
- [ ] New physical status text uses existing geometry. Send new physical keys to localization owner after H3 history PO edits stabilize; avoid concurrent catalog writes. Account status/conflict snippet comes from H3.

### P3 — shared screen semantics, step adapters and hint requests

**Own:** `utils/goReplay.ts` and tests; additive `api/baipuApi.ts` v2 types; `utils/baipuReplay.ts` and tests; `useBaipuHint.ts` and tests; directly affected screen-fixture expectations only (not session-page tests). Do not edit P1 core/capture, P2 physical machine/page, H3 history files or PO catalogs concurrently.

- [ ] Write failing self-capture/initial-setup/pre-removal ordering tests first. Keep shared helper exports and orientation stable.
- [ ] Add own-group removal after opponent captures and make initial setup assignments noncapturing. Keep existing SGF parser and moves-array APIs; no new generalized parser framework.
- [ ] Add optional-compatible pre_removed/requires_placement/replay_version types. Dumb matrices apply pre-remove, assignment, post-remove; they never recompute Go rules from physical steps.
- [ ] Check all three real files at every dense step against independent golden hashes; update old terminal expectation233→232 deliberately and pin intermediate differences for124442. Ordinary captures/pass/colors/setup remain covered.
- [ ] Hint uses position snapshots after applied replacements/repeated placement/self-removal/AE and derives side-to-play from recorded pass property when color is null. Do not send an illegal historical move list into KataGo or alter hint resource budgets.

**Frozen H3 session hook (already being implemented independently):**

```ts
useBaipuSessionHistory({source:string,navigation:{sgf?:string;name?:string;baipuIdentity?:string}|null})
// -> {sgf,name,loading,error,historyId,record,open(total):Promise<{k,total}|null>,
//     save(k):Promise<void>,saving,saveError,
//     resolve('use_cloud'|'keep_local'):Promise<BaipuHistoryDetail|null>}
```

`open`/`save` are stable across result updates. Durable resume uses ?history=ID in URL, not navigation state alone. Hook internally gates resolved identity, exact SGF and queue ownership. P2 owns session-page integration, H3 owns API/hook implementation and all history keys. Account state must not hold up independent backend P1 work.

### Controller integration and review

- [ ] Independent astra/max plan review round1; fix concrete findings; round2 only if needed, maximum2. No physical product implementation before approval.
- [ ] P1, P2 and P3 work in parallel on owned files after frozen fields; H1/H2/H3 history continue their independent files. H1 owns core identity helper, server/model/API-history; P1 must not edit them.
- [ ] Close the actual physical step journey first, then integrate durable recent→resume on that settled-step contract. Avoid multiple divergent reducers/history cursors.
- [ ] Independent spec review then independent astra/max quality review of the combined physical+history diff. Fix material findings until approved; no broad unrelated bootstrap/game engine refactor.

## Chunk 3: Focused acceptance

- [ ] Python core/API/capture/autolabel, TS replay/reducer/hook/page/hint/history tests; all three real SGFs checked at every original step against the independently generated oracle.
- [ ] Ordinary strict Go gameplay still rejects illegal moves in existing focused rule tests. New SGF record interpreter does not make live play permissive.
- [ ] Fake camera/LED sequence: old-color point blue → empty verified → target color armed → placement verified → post-removal blue → final board verified → progress/capture exactly once. Include same-color repeat, self-capture at final move, stale event, undo/resume and source/logout cancellation.
- [ ] Isolated account runtime and actual RK3562 temporary preview at1024x600 where feasible, preserving deployed files. Verify existing geometry and essential status/action states; do not expand into all-state screenshot infrastructure.
- [ ] Actual camera availability is checked once. If unavailable, state simulated-camera/manual coverage and leave hardware acceptance explicitly unclaimed; do not repair unrelated camera stack.
- [ ] TypeScript and Kiosk2D import guard, local commits and review records. No production deployment, kifu deletion or data normalization.

### Plan review record

Round1 requested three narrow corrections (placement acknowledgement vs completion, authoritative fallback, capture/archive compatibility). They are incorporated above; a fresh astra/max second/final review must verify them before physical implementation.

## Implementation record — 2026-11-03

P1/P2/P3 implemented. Independent combined spec review is SPEC COMPLIANT (`2026-11-03-physical-history-spec.md`); independent ASTRA/MAX code review is APPROVED (`2026-11-03-physical-history-code-astra-r1.md`). Its late-setup hint-order finding was corrected and independently rechecked. Actual RK production-build preview/recent/manual-stage evidence and explicit camera limitation are recorded in `2026-11-03-baipu-physical-history-runtime.md`. No production code or data release occurred.
