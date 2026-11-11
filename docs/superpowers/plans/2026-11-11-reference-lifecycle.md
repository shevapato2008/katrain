# Reference Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve qualified same-source reference evidence across redundant BIND and bind each newly adopted photograph to its true accepted position; report limited evidence honestly without blocking normal game rules.

**Architecture:** Add immutable camera-owner frame metadata and a synchronous lighting-owner eligibility gate; use one bounded candidate and one existing-detector same-source witness per specified adoption event. Keep ordinary BIND epoch/queue fencing, precise local commit receipts, monotonic target revisions, historical cell permissions and nonblocking reference status separate from A's authoritative game state and recovery. Do not promise a missing clean16 image can be recovered from physical17.

**Tech Stack:** Existing Python dataclasses/threading/NumPy/FastAPI, existing detector instance, React/TypeScript/MUI and pytest/Vitest fakes. No new package, model instance, owner thread or test framework.

**Authorization:** User authorized implementation on 2026-11-11 and requested independent Astra Max code review then a combined A+B release. Approved specification is `docs/superpowers/specs/2026-11-11-reference-lifecycle.md`; proposal SHA `77f7288a53562716687722e1883b3447765bb226108d8a44b9b837b043ee50af`, cause review SHA `7f7e2a63988d92d655f2b9796a8b26f1ae77ddb44fe2faa139c220716e570f33`, final solution review SHA `513d1da14aa89d7608fd819a98937ed55c802db8c7c50dd79d90d71756550e35`.

**Workspace:** `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/reference-lifecycle-20261111`, branch `fix/reference-lifecycle-20261111`, base `7f3a60a929da87f4f8696bb66d1fe86b5801daf1`. It is already clean. This docs-only phase runs no code tests; use focused baselines before editing each owner task. Python executable for all tasks is `/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python`. UI may use an ignored symlink to the root's existing node_modules; no npm install. Root alone handles push, develop/parent integration, device actions, SSH and deployment.

---

## Chunk 1: Fixed cross-task contracts

These names/data shapes are fixed before delegation. Owners may add private implementation details but must coordinate any externally visible change with the controller. No third proposal review is opened. A genuine uncovered contract problem is reported instead of silently broadening scope.

### C1. Camera owner metadata (T1; T4 consumer)

Define `@dataclass(frozen=True) FrameMetadata` in `katrain/vision/camera.py` with:

```python
stream_generation: int
frame_seq: int
camera_read_monotonic: float
controls_requested_generation: int
controls_applied_generation: int | None
controls_effective: bool | None
controls_completed_at: float | None
ownership_known: bool
advisory: bool = False
```

`CameraManager.read_frame_with_metadata() -> tuple[np.ndarray | None, FrameMetadata | None]` returns the exact frame and metadata atomically stored together under _frame_lock. Owner stream generation changes on open/reopen; controls use existing _controls_generation plus an applied completion stamp. A transition across cap.read produces ownership_known=False. Never stamp an older frame from a later global controls property. `advisory=True` means explicitly known unsupported/unverified-control operation with completed ownership, not every arbitrary controls_effective=False failure; pending/unknown does not qualify. Preserve read_frame/read_frame_identified compatibility.

`CameraHub.read_frame_with_metadata()` uses its existing nonblocking lifecycle lock and _can_read/USB gates and forwards the manager pair unchanged; unavailable is `(None, None)`. Hub never reconstructs generations. Normal free worker consumes this method regardless of tracing. A camera without this interface keeps normal recognition but cannot gain new reference/retention privileges.

Fresh T1 spec review closed a necessary current-owner gap: Manager and Hub also expose `is_frame_metadata_current(metadata: FrameMetadata) -> bool`. It compares the frozen historical stream/control stamp with the current owner under established locks; pending/new completed controls, reopen, unavailable/unknown reject it without restamping/capturing. T4 requires this public validator before/after witness, before historical comparison/retention and promotion. A pre-inference False consumes no attempt and never blocks ordinary recognition. Do not call camera or hold another owner lock inside the LED local_commit callback.

### C2. Lighting owner gate (T2; T3 wiring; T4 consumer)

Define immutable `ReferenceLightingSnapshot` in `katrain/web/core/led_service.py`:

```python
request_revision: int
shown_revision: int | None
connection_generation: int
all_dark: bool
shown_at: float | None
available: bool
```

Expose `reference_lighting_snapshot() -> ReferenceLightingSnapshot` and `try_commit_reference_lighting(token: ReferenceLightingSnapshot, local_commit: Callable[[], None]) -> bool`. Both use existing `_usb_lock`. _submit revokes dark and increments request_revision synchronously before any new batch can enter the serial queue; every points/clear/RGB route and lifecycle invalidation participates. A successful final-dark SHOW ACK may certify only its exact latest request/connection generation; no obsolete ACK revival.

`try_commit...` validates the immutable token against current owner state and performs only a short worker-local object/budget assignment. No inference, image preparation, trace, service, camera, other-owner call or serial wait under the LED lock; retain existing intent_lock→usb_lock order. This direct gate works even when orchestrator tick is skipped. Do not use a cached async snapshot as final authority.

T3 extends `VisionService(..., lighting_owner=None)` and `InProcessAdapter(..., lighting_owner=None)` and server passes the actual LedService; None means unknown/unavailable unless service/server passes explicit `lighting_disabled=True` from known config. `lighting_disabled` is a boolean opt-in, never inferred from a disconnected owner. Unsupported process-worker gets unavailable reference status; no reference algorithm port. T4 qualifies two distinct stable post-ACK frames with read timestamp>shown_at+0.2 seconds and no newer light token. Advisory median delta is explicitly new `REFERENCE_ADVISORY_MEDIAN_DELTA=5.0` in 8bit gray, not an existing hardware guarantee.

### C3. Source identity, target and receipt (T3; T4 consumer)

Keep ConfirmedMove.token unchanged: `(binding_epoch, expected_revision, observation_seq)`. Define immutable `ReferenceTargetKey` in ipc.py:

```python
source_nonce: str
worker_generation: str
binding_epoch: int
expected_revision: int
expected_node_id: int | None
board_digest: str  # sha256 of canonical int8 row0-top board bytes
```

Service owns source_nonce: same session object/sessionId/actual binding_game_identity/mode and same worker instance may retain it; any real change rotates it. Worker_generation rotates on service worker start. BIND payload adds source_nonce, worker_generation, mode_generation and preserve_reference intent; ordinary epoch increments and queue clearing remain. SET_EXPECTED_BOARD adds this source identity and board_digest without changing A recovery_id/force_rearm semantics. Worker checks latest owner continuity before preservation; BIND always clears prior candidates and waits for the new target before claiming current.

Add `CommandType.ACCEPT_REFERENCE_CANDIDATE`. Its data is:

```python
move_token: tuple[int, int, int]
baseline_target: ReferenceTargetKey
accepted_target: ReferenceTargetKey
accepted_parent_node_id: int | None
accepted_board: list[list[int]]
```

`VisionService.capture_reference_baseline(source, move) -> ReferenceTargetKey | None` returns the currently published baseline only if source/epoch/revision matches. `publish_accepted_reference(source, move, baseline, accepted_node_id, accepted_parent_node_id, accepted_board) -> bool` is called while the actual game commit lock is held; under one service metadata critical section it validates source+baseline, publishes SET_EXPECTED_BOARD for this exact accepted position (or reuses its already-published revision), then enqueues ACCEPT_REFERENCE_CANDIDATE. Existing publish_expected_from_stones return semantics stay bool; factor only a private locked enqueue helper if needed. Failed optional bookkeeping never turns a committed move into a reported move rejection.

`WebKaTrain._do_play(..., _reference_committed=None)` accepts an optional internal collector. On played=True only, immediately after successful game.play/end facts and still inside ai_ladder_commit_lock, call it with the actual committed game, parent node, committed node and immutable board snapshot; copy from those facts, not later current state. Capture errors are logged without undoing or misreporting the legal move. No callback on IllegalMove/minimum-use rejection/EndgameConflict. __call__ already forwards kwargs; it need not start returning new result types.

Only ordinary local free-vs-AI server submission supplies the collector initially; remote/ranked/gateway do not fabricate support. A's final live-source checks remain. FIFO is exact accepted SET_EXPECTED→ACCEPT, then any later state publication, then existing finally RELEASE. _submit_confirmed_move still returns its float throttle. Match baseline parent, source and token, not board equality alone.

T4 promotes only if accepted_target==current full TargetKey, token/baseline/source/continuity/TTL all match, and same-target existing evidence is not newer. Late17 after target18 is discarded even if no18 reference exists; no second historical warehouse. Duplicate receipts do not reset budgets. Legitimate undo creates a fresh revision; no depth/stone-count ordering.

### C4. Reference status/API/UI (T3 types/API; T4 producer; T5 presentation)

Add WorkerStatus fields with backward-compatible defaults:

```python
reference_status: str = 'unavailable'  # current|pending|limited|unavailable
reference_reason: str | None = None
reference_target_node_id: int | None = None
reference_target_revision: int | None = None
reference_source_node_id: int | None = None
reference_source_revision: int | None = None
```

Expose these snake_case fields in `/api/v1/vision/status`; optional TS API fields default safely in VisionContext to unavailable. Context maps to camelCase. Missing unsupported backend does not claim current. Do not mix with recognition_ready, recovery acknowledgements or device readiness.

Existing status chip receives referenceStatus/referenceReason (optional props) and retains move_pending priority. Only limited/unavailable after known target/active physical binding uses one nonmodal line “参考尚未更新，继续核对盘面”; initial disabled/target-null is not a warning. Existing missing/extra/device reminders take precedence. current/pending add no repeated toast. One 1024-wide representative preview, no visual redesign. This display must not block independent camera/LED/backend work.

### C5. T4 local worker limits and qualification

**Approved retry increment:** Astra Max review `3a7822582ef75ca84885684a4c8383fbf4b5212682e7935379e6d256c5922480` accepts delta `54884e71b6ebb4baa28691b227414aa7c881c6d6136f3c0db93dd0afe3df0920`; see the authorization supplement appended after the unchanged original spec. T4 may implement the two-attempt contract once reviewed T1/T2/T3 interfaces are available.

The hand visible in event000004 was NOT adopted as a reference; do not claim it was, add hand segmentation/classes, or promise absolute absence of hands. Apply only approved motion/exposure/owner/witness qualifications. No new detector instance or background loop. Freeze the LAST frame in the consecutive stable owner-qualified sequence: its actual unaveraged BGR generates ref_gray before averager/enhancement. The selected image alone is reused for witness/reference; promotion never reads or reselects a newer photograph. One same-instance witness detect over an independently enhanced copy; BoardStateExtractor.detections_to_board uses no prior/stable/expected fill and does not mutate main extractor voting, hysteresis, detector counts or promoter. Deny adjustment follows existing user-denial policy, and no LED detection/invalid exposure may certify the picture. Pre-vote/voted only gate main-flow stability, never prove contents of raw pixels.

At most TWO ordinary witness attempts per actual target/recovery generation; one candidate witness per ConfirmedMove.token; one refresh witness per60s; one conflict witness per actual reference. Promotion reuses an already-witnessed photo, no second infer. Debit ordinary attempt when inference starts (including exception/final owner rejection); pre-inference gate rejection consumes none. Retry requires>=1s monotonic cooldown and two distinct newer qualified stable frames, both newer than the failed frame in the same stream; a changed stream requires its own post-transition pair without replenishing spent count. Limited after5s retains an unused retry; attempt2 failure remains limited. No sleeps/background retries. One gray candidate (~1.1MiB) plus small boards; transient BGR (~3.3MiB); no model/GPU run during fake tests.

Ordinary budget is one small record, not image history: spent count, not_before, failed stream/seq, fresh-pair gate, and target/recovery ownership. Across redundant BIND preserve it pending the same source/game/mode/worker and actual node+canonical board SET_EXPECTED, remapping epoch/revision without refill. Genuine target advance/undo or new verified recovery_id changes owner; stream/control/LED changes only requalify. Force_rearm without a new recovery_id, status refresh, rename or duplicate receipt cannot refill or restore dispute permissions. A new successful current reference cancels obsolete ordinary retry.

Candidate TTL is5s or8 subsequent qualified observations, whichever first; any release/reset/rebind/continuity loss clears it. Expensive ReferenceFrame/features preparation is outside LED lock. Every pixel-writing route, including local-window completion and refresh, must use the same source qualification; an unwitnessed local stored-gray completion must not bypass it. Remote/monitor paths without reliable source identity remain honest limited rather than inventing authority.

Historical valid-cell mask requires reference.board==expected plus usability/current continuity/existing lit/released restrictions. Changed accepted cells lose old-label veto immediately. Main nonempty observations with confidence support against reference-empty accumulate existing move_confirm_frames evidence independent of reference-corrected output. At threshold, one raw-source conflict witness can withdraw empty-label veto; unresolved/unsupported-witness disputes withdraw silent veto but force existing ambiguity/deny handling instead of high-confidence auto-submit. After the one conflict witness is spent, further persistent disputed cells take the ambiguity path without more infer. No global wall-clock veto expiry, no permanent silent empty veto, no budget reset by renaming the same photo. Preserve noninvented missing/color budgets.

## Chunk 2: Ownership, RED/GREEN and commits

Do not start implementation before root's quick contract check. Then use fresh implementers with disjoint file ownership; maximum three implementers concurrently (the global seven slots include root/controller and must leave room for fresh reviewers). No agent spawns another implementer. Controller launches fresh spec reviewer then fresh quality reviewer per completed task; root performs independent final Astra Max whole-code review. Reviews remain bounded to approved changes. `git commit --only <owned files>` prevents staging another owner's work. Do not edit another task's source/test files without explicit controller reassignment.

### T1 — Camera owner metadata and production Hub forwarding (parallel with T2)

**Own:** katrain/vision/camera.py; katrain/web/core/camera_hub.py; tests/test_camera_hub.py; tests/test_vision/test_camera_recovery.py; tests/test_vision/test_shared_camera.py.

- [ ] Step1: run focused existing baseline using root .venv: `python -m pytest -q tests/test_camera_hub.py tests/test_vision/test_camera_recovery.py tests/test_vision/test_shared_camera.py` (substitute the absolute executable specified above).
- [ ] Step2 RED: add fake-reader cases where reopen or controls finish between observations, request changes across read, metadata and image share identity, Hub forwards unchanged and gate returnsNone. Existing 3-value APIs remain compatible.
- [ ] Step3: rerun only new cases; expect missing metadata API/false ownership failures.
- [ ] Step4 GREEN: implement C1 with no extra read and no later-property relabeling; explicit advisory vs unknown semantics.
- [ ] Step5: rerun same focused files; expect all pass. Commit only owned changed files: `git commit --only <owned changed files> -m 'bind camera frames to owner metadata'`.
- [ ] Step6: fresh spec then fresh quality review; resolve scoped findings before marking T1 done.

### T2 — Real lighting generation and atomic eligibility gate (parallel with T1)

**Own:** katrain/web/core/led_service.py; tests/test_led_service.py. No orchestrator tick changes are needed for eligibility because C2 owner access is direct.

- [ ] Step1: baseline `python -m pytest -q tests/test_led_service.py` with root .venv.
- [ ] Step2 RED: fake ACK/request tests: queued new-on immediately invalidates old dark without tick; old ACK cannot revive; token change during witness makes final commitFalse; USB/open/close/failed batch invalidates; valid callback only assigns once under correct lock.
- [ ] Step3: run new cases and confirm failure under absent API/stale-dark behavior.
- [ ] Step4 GREEN: implement immutable C2 snapshot and final gate using existing_usb_lock; expensive operations/callback-to-owner remain outside. All display write routes share _submit revocation.
- [ ] Step5: rerun single test file; commit owned changes only with `git commit --only ... -m 'guard reference capture with current lighting intent'`.
- [ ] Step6: fresh spec then fresh quality review; deliver exact API names without asking T4 to infer private fields.

### T3 — Protocol, same-source binding, local receipt and wiring (can start after contracts; needs T1/T2 APIs for integration)

**Own:** katrain/vision/ipc.py; katrain/vision/service.py; katrain/web/interface.py; katrain/web/server.py; katrain/web/api/v1/endpoints/vision.py; tests/test_vision/test_service_event_routing.py; tests/test_vision_bind_state.py; tests/test_vision_move_poller.py; tests/web_ui/test_interface.py; tests/test_vision_api.py. Do not edit worker_inprocess.py.

- [ ] Step1: baseline `python -m pytest -q tests/test_vision/test_service_event_routing.py tests/test_vision_bind_state.py tests/test_vision_move_poller.py tests/test_vision_api.py`; run `python -m pytest -q tests/web_ui/test_interface.py` in a separate interpreter process because its sys.modules fixtures must not contaminate real-runtime integration.
- [ ] Step2 RED: source nonce persists only for same session object/game/mode/worker; epoch/queued move fencing still changes; successful local played snapshot queues exact SET_EXPECTED→ACCEPT before finallyRELEASE; rejection/minimum-use/illegal/collector failure/old epoch cannot produce false acceptance. Interleave later AI publication and source replacement under A live guard.
- [ ] Step3: rerun new receipt/binding tests; expect missing protocol/collector failures.
- [ ] Step4 GREEN: implement C3/C4 and constructor wiring; _reference_committed snapshots real parent/node/board under existing commit lock; optional failure cannot reject committed game. Preserve A's ExpectedRecovery and authoritative state helper. No receipt support claimed remotely.
- [ ] Step5: rerun focused files; commit source/tests owned only: `git commit --only ... -m 'handoff qualified references at the local move commit'`.
- [ ] Step6: fresh spec then fresh quality review. Announce protocol stable to T4. T4 alone then edits adapter signature to consume lighting_owner; T3 must not write worker file.

### T4 — Worker reference lifecycle, same-source witness and disputed cells (single writer; starts when T1/T2/T3 reviewed interfaces are available)

**Own:** katrain/vision/worker_inprocess.py; katrain/vision/reference_frame.py only if the pixel API needs a narrow qualification boundary; tests/test_vision/test_reference_frame.py; tests/test_vision/test_worker_commands.py; tests/test_vision/test_local_confirmation_window.py; tests/test_vision_move_poller.py ONLY for the root-requested full handoff integration case (T3 ownership has ended). No service/camera/LED edits.

- [ ] Step1: focused baseline `python -m pytest -q tests/test_vision/test_reference_frame.py tests/test_vision/test_worker_commands.py tests/test_vision/test_local_confirmation_window.py`.
- [ ] Step2 RED: adapt existing fake fixture to C1/C2; add same-source redundant bind retains image but changed generation clears; explicit target16 pending→limited; realFrameAverager8 with scripted detector sees averaged16/raw17 and cannot create/candidate/refresh current16. Reuse original tiny synthetic lag case, no second framework/artifact pipeline.
- [ ] Step3: confirm red; implement owner qualification and stateless witness for create/candidate/refresh/local completion; assert no main-state mutation and bounded call counts/advisory5/6 eligibility. First ordinary failure then duplicate/cooldown/pending control must not invoke again; after5s limited a genuinely new pair may retry once; persistent failure caps2 including detector exceptions/final-gate rejects. Redundant BIND actual epoch and force_rearm cannot refill; new stream keeps spent count but needs a new pair.
- [ ] Step4 RED: one candidate TTL/observation cap; SETexpected17→ACCEPT17→RELEASE; current18→late17 object/budgets unchanged; undo fresh revision; duplicate old token no reset; unsupported owner metadata does not stop normal moves.
- [ ] Step5 GREEN: implement C3 handoff plus reference TargetKey/status; prepare features outside LED lock; source-only local assignments inside final gate.
- [ ] Step6 RED/GREEN: existing infinite empty-veto expectation is intentionally revised: sustained supported conflict invokes maxone witness, withdraws disputed permission and forces ambiguity where unresolved; unchanged accepted stone cannot be vetoed by historical empty map. Preserve missing/color tests and ambiguity cooling/deny behavior.
- [ ] Step7: add one minimal cross-layer regression using existing real WebKaTrain(enable_engine=False)/VisionService test setup in test_vision_move_poller.py: real game commit→exact service SET/ACCEPT→real worker command promotion (camera/detector/LED fakes only), rejection/late receipt cannot adopt. Run this integration separately from interface/privacy fixtures. Rerun the three worker-focused files; then only direct cross-task regressions from T1/T2/T3, not entire model/GPU suite. Commit owned files only with `git commit --only ... -m 'bind reference evidence to accepted positions and raw frames'`.
- [ ] Step8: fresh spec then fresh quality review; controller checks all pixel-write callsites and accepted receipt boundaries, not just synthetic helpers.

### T5 — Existing nonblocking reference status display (parallel after C4; backend work not blocked)

**Own:** katrain/web/ui/src/api.ts; katrain/web/ui/src/kiosk/context/VisionContext.tsx; katrain/web/ui/src/kiosk/components/physical/PhysicalPlayStatusChip.tsx; katrain/web/ui/src/kiosk/pages/GamePage.tsx; katrain/web/ui/src/kiosk/__tests__/PhysicalPlayStatusChip.test.tsx; katrain/web/ui/src/kiosk/context/HardwareStatusContexts.test.tsx; minimal fixture type adjustments in existing UI tests only after controller assignment.

- [ ] Step1: reuse ignored node_modules symlink if absent (`ln -s /Users/fan/Repositories/katrain-kiosk-debug/katrain/web/ui/node_modules katrain/web/ui/node_modules` after verifying ignored); no npm install. Baseline targeted existing Vitest files.
- [ ] Step2 RED/GREEN: test optional status defaults; limited bound target shows one nonmodal message; pending/current do not repeatedly toast; move_pending and existing physical reminder/device states win. Do not trigger recognitionReady/recovery modal from reference status.
- [ ] Step3: `npm test -- src/kiosk/__tests__/PhysicalPlayStatusChip.test.tsx src/kiosk/context/HardwareStatusContexts.test.tsx` from katrain/web/ui, then `./node_modules/.bin/tsc -b`. No broad screenshot matrix.
- [ ] Step4: one 1024-wide genuine runtime preview using existing fixture/dev shell only (no production game/device); inspect existing status location and readable text. Record one image path for root, no style redesign. Backend remains free to proceed.
- [ ] Step5: commit owned changed source/tests only: `git commit --only ... -m 'show limited reference evidence without blocking play'`; fresh spec then fresh quality review.

## Chunk 3: Integration and independent review gate

- [ ] Controller checks every task's commit/review results, ownership and no introduced trace recorder/import/SCP/source override. Production base has no reference_trace.py, so do not create it; no persistent diagnostics work is needed. Optional existing diagnostic observer metadata may carry current/historical identifiers without adding a collector.
- [ ] Run focused Python checks over compatible task-listed files (same root .venv, CI=true if needed). Always run interface/privacy fixture files in separate interpreter processes from real-runtime integration to avoid sys.modules contamination; no combined all-file invocation. Run targeted Vitest+tsc, and current A E18 regressions: `tests/test_vision_move_poller.py`, `tests/test_vision_bind_state.py`, `tests/test_vision_api.py`, and `GamePage.playAi.test.tsx` when touched integration could affect it. Existing passing files do not need repeated GPU/model tests.
- [ ] Inspect exact diff for cross-source/acceptance ordering, current18 protection, no stale-dark cache use, post-average/raw image qualification and disputed-auto-submit guard. Keep RK incremental inference unmeasured until root's authorized device acceptance; do not claim zero NPU cost.
- [ ] Send exact branch SHA/diff/tests/preview to root. Root launches fresh independent Astra model Max whole-code review as explicitly requested; controller fixes only concrete findings and reruns their targeted regression until review passes. Task reviews are not a substitute for this final independent review.
- [ ] Only after root's final acceptance does root integrate published latest develop, parent submodule and combined A+B deployment following repository workflow. Controller/subagents do not push, SSH, alter develop/parent, restore diagnostic overrides, stop services or interact with real games.

## Execution handoff

Docs-only commit first. Send root the exact commit and fixed contracts for quick check. Do not start implementers until root approves this handoff; this is a coordination checkpoint, not a new user design approval. After approval, launch at most T1/T2/T3 concurrently; let fresh spec/quality reviewers use the remaining slots. Schedule T5 when an implementation slot frees, with no backend blocking. T4 stays single-writer and waits on reviewed foundations. Never issue git add-all or commit another owner's staged files.
