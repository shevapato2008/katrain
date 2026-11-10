# Calibration Preview Stability Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent transient frame contention or slow JPEG decode from repeatedly blanking the calibration preview, while retaining honest disconnect handling and the working camera/LED hotplug recovery.

**Architecture:** Keep the existing single-owner camera and bounded USB recovery unchanged. The snapshot endpoint briefly retries a missing frame before reporting unavailable; the snapshot component tolerates a transient failure with a clearly marked, time-bounded last frame and gives HTTP body transfer its own timeout independent of bitmap decoding. Each source/revision remains isolated.

**Tech Stack:** Python/FastAPI/OpenCV, React/TypeScript, pytest, Vitest, existing strict SBC kiosk build and RK deployment tooling.

## Chunk 1: Evidence, behavior, and implementation

### Diagnosis and scope

The user's current report is **periodic left preview reconnecting on the calibration page**. Camera USB and LED board Type-C hotplug now recover successfully; do not substitute the older USB enumeration failure for this task.

Observed evidence on 2026-11-10:

- Installed RK application baseline is `aea1f6d955deadea2e5cccda63919bc0ccaace58`. Git feature branch is `fix/kiosk-ui-debug`; implementation workspace is the isolated `fix/calibration-preview-stability-20261110` worktree.
- Persistent USB recovery `last_attempt` remains 11:09 China time. No repeated reset accompanies the later read-only observation. This does not prove every historical incident was unrelated to USB.
- At 15:19 China time, 40 raw scale3 snapshots at 2 fps all returned 200, median 32.421ms, maximum 110.387ms. Camera and LED stayed connected, recovery state unchanged, no new USB kernel events. Vision was unbound, so this did **not** reproduce active-game/calibration contention.
- Deterministic reproduction using real `CameraHub` and real snapshot handler: healthy camera + concurrent `grab_fresh()` lifecycle lock returns immediate 503; before/after return 200. Drift capture can do this every second during a bound physical session; calibration capture also uses this lock.
- `GeometryVideoPanel` hides canvas/overlay for every failed frame and retries after 1s. Its 1500ms abort includes image decode; deterministic all-200 responses with 1601ms decode repeatedly hide the preview. Ordinary callback/status rerenders do not restart its effect.
- Local read-only diagnostic artifacts live under ignored `output/diagnostics/calibration-preview-20261110/` in the original workspace. Old PORT_POWER probe is suspended and has never run; it is outside this change.

We choose a narrow endpoint retry + bounded frontend continuity. Releasing `CameraHub.grab_fresh`'s lifecycle lock would require new lifecycle/generation guarantees around USB quiescence and stop; merely raising all timeouts would not fix the error-to-blank transition. Neither is necessary here.

### Acceptance contract

1. Brief busy frame reads that recover within a 200ms retry window return one current JPEG, encoded once. A truly absent camera still returns 503. Existing warped invalidation returns 409, including geometry invalidated while waiting.
2. Snapshot handling adds no direct camera reopen, reset, LED commands, geometry actions, or new background threads. Respect a capture's existing `is_connected` function/property where available: skip reads when already known disconnected/USB-paused. This check is not atomic with the existing capture read API; it cannot eliminate its existing check-then-disconnect/reconnect race. Existing capture implementations without that capability remain compatible.
3. Keep `CameraHub.read_frame` nonblocking and preserve lifecycle/USB tests. The retry budget bounds retry waiting, not an arbitrary blocking third-party capture call; do not claim a hard HTTP deadline that this API cannot guarantee.
4. Frontend keeps max 1 request/decode in flight and existing 5fps success / 1s failure scheduling. First-frame failure has no image or overlay. A transient failure after success keeps the last canvas for at most **3000ms since the last successful draw**, displays the existing small reconnect warning, and removes the geometry overlay while the frame is known stale. At expiry hide the stale canvas even if another request/decode is pending.
5. A successful draw restarts that 3000ms expiry and restores canvas/overlay. A failed request never extends it. Prolonged failures show existing reconnect text. A new `src`, view/revision, missing source, or unmount clears old ready/error/timers and ignores/closes late bitmaps.
6. The 1500ms transport abort ends only once the complete response body is available; slow bitmap decode alone does not trip it. Cleanup/source change must still abort and invalidate pending work. Delayed decode cannot keep an old frame visible beyond the independent stale timer.
7. No new UI layout, navigation, login, payment, membership, USB reset configuration, or recovery episode state changes. Existing strings/style suffice; last-frame warning must not imply that a frozen frame is live.

### Task 1: Bounded snapshot frame acquisition (backend owner)

**Modify:** `katrain/web/api/v1/endpoints/geometry.py` (`geometry_snapshot` and narrowly scoped helpers/constants only).
**Test:** `tests/test_geometry_api.py`.

- [ ] Add failing tests: a capture with `None, None, latest_frame` returns 200/no-store and current downscaled JPEG; permanent unavailable returns 503 after bounded attempts; a known disconnected capture is not read/reopened; a real Hub held briefly by `grab_fresh` can still serve a snapshot; warped phase/revision invalidation while waiting returns 409 both when a frame eventually arrives and when it remains unavailable. Keep tests deterministic with events or a fake monotonic clock rather than timing-sensitive sleeps.
- [ ] Run `/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest tests/test_geometry_api.py -k snapshot -q`. Record the new failures before product changes.
- [ ] Implement the acquisition inside the existing `asyncio.to_thread` worker, using a single monotonic deadline and bounded sleep (e.g. 25ms) only after `None`. Conceptual code:

```python
deadline = time.monotonic() + 0.2
while True:
    connected = getattr(capture, "is_connected", None)
    if connected is not None and not (connected() if callable(connected) else connected):
        frame = None
        break
    frame = capture.read_frame()
    if frame is not None:
        break
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        break
    time.sleep(min(0.025, remaining))
# On ALL acquisition exits, revalidate warped lock identity, phase, and revision;
# report geometry_not_available if invalidated, then handle None as unavailable.
# Downscale/warp and JPEG encode exactly once, with existing quality/cache headers.
```

  Preserve validation errors (invalid view 400, missing capture404, geometry409). Do not create a second owner/capture or change CameraHub/CameraManager. Keep late invalidation handling inside thread-safe existing calibration status APIs.
- [ ] Run `...python -m pytest tests/test_geometry_api.py tests/test_camera_hub.py tests/test_usb_hub_recovery.py -q` (confirm exact recovery test filename via `rg --files tests`). Address related failures only.
- [ ] Self-review and commit only these two owned files with a short present-tense commit message. Report commit, red/green evidence, and any constraint concern.

### Task 2: Bounded preview continuity and decode timeout separation (frontend owner)

**Modify:** `katrain/web/ui/src/kiosk/components/vision/GeometryVideoPanel.tsx`.
**Test:** `katrain/web/ui/src/kiosk/__tests__/GeometryVideoPanel.test.tsx`.

- [ ] Write failing fake-timer tests for: one 503 after a good draw retains marked canvas but removes overlay; recovery restores it; successive failures never extend the original 3000ms age limit; expiry hides while another fetch or decode is pending; a 1601ms decode after a prompt full body draws normally; body still downloading at 1500ms aborts; source/revision switch and unmount discard/close old bitmaps and clear old expiry. Retain existing no-tight-retry and bitmap cleanup tests, changing old immediate-blank expectations to this contract. Add a normal status/callback rerender assertion if needed to protect the diagnosed non-cause.
- [ ] Run `npm test -- src/kiosk/__tests__/GeometryVideoPanel.test.tsx`; record the new failures before implementation.
- [ ] Use one source-scoped stale timer and the existing ready/error states, avoiding a generic state machine. On successful draw, clear previous expiry, ready=true/error=false, arm 3000ms expiry; on failure error=true and retain ready only until that timer expires. Hide overlay when error. Expiry must not falsely expire a newly drawn frame and must not allow late previous-source work to publish.
- [ ] In `pull`, await `response.blob()` separately; clear the transport deadline after full body receipt and before `createImageBitmap`. Keep live/abort checks before and after decode, close every created bitmap, and clear all timers/controllers during effect cleanup. Source reset precedes drawing from the new source. Do not depend on inline callback or overlay identity.
- [ ] Run focused video plus calibration screen/context tests (resolve exact paths with `rg --files src/kiosk | rg 'Geometry(VideoPanel|CalibrationScreen|Context).*test'`) and `npx tsc -b`. Self-review and commit only these two owned files. Report commit and red/green results.

Tasks 1 and 2 have disjoint files and may run in parallel **after plan approval**, per the user's explicit parallel SDD instruction. Commits in the shared isolated worktree are serialized by the controller; implementers may prepare patches/tests in parallel and request the controller to commit if Git operations overlap.

### Task 3: Review and combined verification (controller)

- [ ] Independent Astra Max reviews this entire plan with clean context, maximum **two total plan-review rounds**; controller revises the document. No product code before approval. This review includes scope/design adequacy; do not add a redundant review hierarchy.
- [ ] Execute Tasks 1 and 2 via fresh SDD implementers. Perform spec compliance review first, then a fresh independent Astra Max code-quality review over the complete diff. Implementers fix every blocking finding and reviewers re-review until Approved. The final reviewer must not be an implementer.
- [ ] Inspect actual diff and run combined focused pytest, frontend tests and TypeScript using `npm ci` against committed lock in the isolated worktree. Do the **single final strict release build and package only after Step 2 has fixed the published develop SHA**, as detailed below; do not build a stale pre-integration release.

## Chunk 2: Authorized publishing and RK deployment

### Task 4: Four-step integration and release

The latest explicit user instruction deploys this fix to **RK3562**; earlier cloud deployment scope is superseded for this iteration.

- [ ] **Step 1:** In original feature workspace ensure unrelated changes are preserved. Fetch latest develop; integrate this approved fix and origin/develop into `fix/kiosk-ui-debug`, resolve conflicts and verify the combined result, commit as needed, push `origin fix/kiosk-ui-debug` without force. If a conflict changes reviewed behavior, re-review that portion.
- [ ] **Step 2:** Use an isolated integration worktree so the user's other develop checkout is untouched. Merge published feature into latest develop; verify ancestry and relevant checks, push `HEAD:develop` without force. Re-fetch/reconcile if concurrent remote advancement occurs.
- [ ] **Freeze artifacts after Step 2:** Use an isolated checkout of the exact published develop SHA for `npm ci --no-audit --no-fund` and `npm run build:smartbox-kiosk-2d`. Extract endpoint source from this same SHA; record the SHA, lockfile/build mode, file hashes and fresh device before hashes in the manifest. Package only that endpoint and strict kiosk static tree. If release source changes subsequently, discard this package and rebuild from the newly published SHA. Do not mix pre-merge UI with post-merge version metadata. Device delivery remains explicitly baseline + allowlisted application delta, not a claim of a whole-device checkout. No unrelated Python, database, systemd or environment changes.
- [ ] **Step 3:** In an isolated smartbox-software worktree based on latest origin/main, update only `vendor/katrain` gitlink to published develop SHA, commit and push `HEAD:main`. Preserve the original `/Users/fan/Repositories/smartbox-software` working tree, including its existing modified submodule. Verify remote gitlink equals develop SHA.
- [ ] **Step 4 preparation:** Read existing deployment receipts and the reviewed previous operator (`output/releases/usb-hub-recovery-20261109/rk-release.py` in original workspace), then adapt the smallest necessary bounded transaction to current installed AEA baseline and the endpoint/static allowlist. Do **not** rerun its old 4235 baseline/USB enable procedure unchanged. Get independent code review of new deployment logic before device mutation. Reuse launcher lock/capture/rollback primitives rather than introducing a new deployment framework.
- [ ] Capture fresh runtime/page/service state and actual deployed hashes. Require a safe idle state; do not interrupt an active game or calibration. Ask a concise asynchronous handoff question only if user activity prevents maintenance; continue independent packaging/review meanwhile. Preserve authentication/session and original page where possible; after release return to original mode/page.
- [ ] Preserve membership guard env/drop-in hashes, enabled billing/membership/zero free quota, SQLite `membership_activated_v1`, device identity, USB enable drop-in and exact writable state paths. Never copy/reset/rearm/restore recovery `state.json` or `operation.lock`, old databases or commercial configuration. Never inject auth or fake accounts.
- [ ] Acquire and heartbeat the existing launcher maintenance lock; back up only allowed app/static targets and exact original service/mode state. Quiesce via reviewed parent Runtime helper; verify processes/cgroups stop. Stage + hash verify + atomically publish the changed endpoint and static directory, start Go, check health, camera/LED and strict build manifest, preserve config hashes. Roll back only app/static files on failure and restore original runtime. Release maintenance lock in finally; retain readable receipt with truthful outcome/version/delta distinction.
- [ ] Verify one real calibration preview observation on RK (using the user's authenticated idle session, without starting calibration/LED commands): at least 60 seconds of existing preview requests and visible canvas state, ensuring no repeated blank/reconnect cycles, healthy camera/LED, and no new Hub resets. If calibration is not open, open only from a freshly verified idle kiosk and restore the page afterward. Avoid hotplug/reset experiments; user does physical insertion/removal acceptance later. Capture one representative screenshot and request timing/status aggregate. Low-level injected contention/slow-decode behaviors are proven by focused tests; do not monkeypatch the deployed app or pretend this idle observation reproduces active-session load.
- [ ] Verify remote feature/develop, parent gitlink and device deployed hashes; report commits and actual version, review/test results, plus any remaining hardware acceptance limitation. Notify the user in this session after deployment so they can test physically.

## Progress and review receipts

- [x] Read-only source investigation and deterministic failure reproduction.
- [x] Low-load field check; current idle state did not reproduce the periodic failure.
- [x] Plan review round 1: revise final build provenance, all-exit warped invalidation and scope of reconnect guarantee.
- [x] Plan review round 2: independent Astra Max Approved, no blocking findings (2/2 rounds complete).
- [x] Backend and frontend implementation: `7ecde3323` and `7f89914cb`; TDD red/green recorded by independent implementers.
- [x] Spec review Approved; fresh independent Astra Max product code review Approved for `fe42557c5..7f89914cb`. Controller verified 140 backend tests, 75 frontend tests, TypeScript and diff checks. Deployment helper review remains required before device mutation.
- [ ] Four publishing/deployment steps and real RK preview verification.
