# Physical Tsumego Direct Reset Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** Kiosk 重摆 restores this problem's initial screen position and directly guides the physical board to that position, preserving correctly placed stones.

**Architecture:** Keep the normal problem-entry empty-board lifecycle. Separate same-problem reset from enable/problem changes and reuse restoring convergence (missing target-color lights, extra/wrong-color flashing lights, screen overlays). Reset must synchronously fence input and invalidate old celebration/reply work; reconnect during reset resumes the initial target without clearing.

**Tech Stack:** Existing React/TypeScript hook, pure reducer, Vitest, existing kiosk preview at 1024×600.

## Chunk 1: Direct reset lifecycle

### Task 1: shared problem reset invalidation (independent worker)
**Files:** `katrain/web/ui/src/hooks/useTsumegoProblem.ts`, `useTsumegoProblem.test.ts`.
- [ ] Add failing tests, then invalidate/cancel delayed AI replies on reset, problem change, unmount; reset exits try mode and clears its saved snapshot. This fixes shared reset semantics for screen mode too; ordinary screen solve/undo behavior remains unchanged.
- [ ] Run focused hook tests and commit.

### Task 2: optional setup identity and reconnect (independent worker)
**Files:** `katrain/web/api/v1/endpoints/vision.py`, `katrain/vision/service.py`, `worker.py`, `worker_inprocess.py`, `sync.py`; `katrain/web/ui/src/api.ts`, `src/kiosk/hooks/useVisionSync.ts`; focused backend sync/API and WS-hook tests.
- [ ] Add optional `setup_id` string to setup request, forward unchanged endpoint→service→both workers→sync; echo it in setup_progress/setup_complete data. Omitted identity preserves legacy callers. Frontend API accepts an optional second argument.
- [ ] Add bounded single timer WS reconnect after close, cleaned on unmount/session change; connected=false immediately gates input, event seq remains monotonic.
- [ ] Test old/new setup identity and legacy behavior; fake WS close→reconnect→unmount cleanup. Commit.

### Task 3: reducer/hook implementation and focused tests
**Files:** `katrain/web/ui/src/kiosk/hooks/physicalTsumegoMachine.ts`, `usePhysicalTsumego.ts`, corresponding `.test.ts`/`.test.tsx`.
- [ ] Inspect reset(), scheduled reply cancellation, vision sync sequence queue and API ordering before choosing minimal fence.
- [ ] Add regression tests: reset from ready/replying/removing/solved/try mode; target contains initial captured stones; retain correct stones and guide missing/extra/wrong-color; no empty target; matching returns ready.
- [ ] Separate reset intent from full ENABLE lifecycle; expose synchronous reset entry if necessary to disarm same-turn events. Use explicit reset target from authoritative reset state or problem initial stones, never stale solve/try snapshot.
- [ ] Generate unique setup_id for every convergence target and accept only matching setup_progress/setup_complete events (legacy mock fixtures updated). Invalidate celebration and discard queued old moves at reset. Serialize vision control requests with generation checks so a superseded setup/arm cannot win; disconnection prevents accepting input.
- [ ] Retain same-problem reset intent across visionConnected=false and enabled=false caused by recognition readiness; reconnect resumes initial target directly. Clear intent only on actual problem change or explicit physical-mode exit. Normal initial entry remains unchanged.
- [ ] Run `npm test -- src/kiosk/hooks/physicalTsumegoMachine.test.ts src/kiosk/hooks/usePhysicalTsumego.test.tsx` and commit.

### Task 4: page integration and acceptance (same worker as Task 3)
**Files:** `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx`, `src/kiosk/__tests__/TsumegoProblemPage.test.tsx`, optional focused existing Playwright fixture.
- [ ] Integrate reset hook API; reset screen/hint/try/solved state using existing problem reset; update misleading clear-board copy and timer rebase for restoring reset.
- [ ] Verify electronic board shows extra/wrong-color red overlays and missing initial stones via existing restoring UI. Distinguish wrong color replacement from missing-only guidance if needed.
- [ ] Focused page regression test proves reset uses initial board and does not clear first, including screen-only behavior unchanged.
- [ ] Run focused page tests and TypeScript check; use 1024×600 actual kiosk preview for the existing restoring panel/overlay (no visual redesign).
- [ ] Independent spec review then code-quality/adversarial review; fix actual issues and rerun affected checks. Record hardware-only LED/recognition limitations, commit and hand off without push/merge/deploy.

**Acceptance:** correct physical stones remain; extras/wrong colors flash and show red removal marks; missing stones show target-color LEDs and screen guidance; auto-resume only after target match; pending reply/celebration/wrong undo/try snapshot cannot override reset; connection loss does not lead to accepting physical moves or clear-board restart.
