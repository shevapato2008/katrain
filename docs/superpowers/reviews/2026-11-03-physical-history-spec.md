# Physical replay + account history — independent specification review

**Verdict: SPEC COMPLIANT. The integrated findings below are closed.**

Reviewed the actual working tree on `feature/baipu-physical-history-20261103` against baseline `9e83f1ad5`, the approved `2026-11-03-physical-sgf-replay.md` and `2026-11-03-account-baipu-history.md` plans, and both approved ASTRA/MAX round-2 plan reviews. Scope covers physical transactions, completed-step history integration, shared replay/hints, and capture/archive compatibility. The separately reviewed H1/H2 backend protocol remains covered by `2026-11-03-account-baipu-history-backend-spec.md`; this review checked its integration seams without duplicating that protocol review. The new kifu metadata investigation/plan work is excluded.

## Findings closed during this review

### S1 — Initial manual entry and the initial capture lacked an authoritative boundary

Initial manual/collection entry originally defaulted directly to the first action. A leading pass could therefore advance without confirming the entry board. The forced initial `-1` capture also ran before the operator established the empty board, and did not prevent the first placement while that frame was pending.

**Closed:** `BaipuSessionPage.tsx:161` establishes the explicit manual entry stage after a successful authoritative load. Resume, restart, undo and manual fallback also establish entry. The initial capture at line 270 requires the entry acknowledgement; its existing pending overlay prevents placement until the attempt settles. The entry handler sets that pending state in the same batch. Focused regressions prove a leading pass does not advance before acknowledgement, no initial capture occurs before entry, and the initial frame finishes before placement becomes available.

### S2 — Page LED writes could invalidate capture truth

Finishing a manual operation changed the stage to `settled` while starting `/capture`. The page's independent LED effect could then clear the server's next guidance LED during exposure, despite the manifest recording that LED as training truth.

**Closed:** `BaipuSessionPage.tsx:131` serializes generation-tagged page LED requests. Initial and completed-step captures await that tail before transferring LED control to the capture endpoint (lines 246 and 274). The page LED effect and relight action refrain from writes while capture is pending (lines 305 and 350). The deferred-LED regression verifies that the old page request settles before capture starts and that no page clear occurs during the server-owned capture interval. No additional LED class or capture infrastructure was added.

### S3 — Exit could cancel the final save and falsely claim it was saved

The session lifecycle controller originally also cancelled dispatched keepalive cursor PUTs on unmount. The page offered immediate exit with an unconditional saved-progress claim, and a failed final cursor had no retry action.

**Closed:** `useBaipuSessionHistory.ts:126` captures owner/token for the mutation without the page lifecycle signal. An already-dispatched PUT retains the API's bounded independent 10-second lifetime and keepalive behavior. The pre-dispatch `alive` guard still cancels unsent work, and stale responses do not update the new session. The regression exercises the actual API wrapper with deferred fetch: unmount does not abort the sent request, queued work does not send, and the original expected-identity header/token remain fixed. Page Exit/collection Finish wait while saving; errors expose a retry of the current committed cursor and an explicit “exit anyway” choice. The real-hook page regression verifies pending exit, failed final save and retry.

### S4 — Same-cursor source/account changes could retain old AI hints

Hint visibility and response eligibility originally depended only on numeric `k`. Reloading another source/account at the same cursor could retain old rows/LEDs, accept its late analysis response, or leave the new physical session paused.

**Closed:** `useBaipuHint.ts:114` binds the request/visible result to the exact steps, cursor, size, credentials and session key, hides a previous scope synchronously, and invalidates late callbacks on scope cleanup. `BaipuSessionPage.tsx:215` supplies account/source/exact-SGF scope and clears trial mode on scope changes. Focused same-cursor source/account/credential/reload and late-response regressions pass.

## Contract assessment

| Boundary | Implementation evidence and assessment |
| --- | --- |
| Authoritative FF4 operations | `core/baipu.py` emits dense schema-2 operations with distinct `pre_removed`, recorded assignment, `removed` and `requires_placement`. Replacement, repetition, opponent capture, own-group removal, noncapturing setup, AE, passes and coordinate/setup rejection are covered. `BaseGame` remains strict. All three real records match the independent golden at every dense state; final counts are 232/259/202. |
| Physical transaction atomicity | `physicalBaipuMachine.ts:54` gives every setup stage a fresh session/stage ID. Entry → pre-removal → placement witness → post-removal stays on the completed cursor. One-motion replacement accepts the correct-color placement with allowed partial post-removals. A self-capture's final equality never proves placement. Post-removal cannot promote another move, and `advancing` suppresses duplicate completion. |
| Cancellation and reconciliation | `usePhysicalBaipu.ts` serializes device commands, invalidates queued commands/timers at cursor, pause, source/account and lifecycle boundaries, rejects stale setup IDs, and restores the completed board on resume/undo. Recheck resends the authoritative target. Manual fallback disarms monitoring and retains ordered operator confirmation. The unfinished-replacement undo regression keeps `k` fixed. |
| Durable history journey | The session opens history only after successful authoritative load; the durable ID is written to `?history=...`. Reload reads the exact authenticated snapshot. Stable `open`/`save` functions serialize cursor writes, coalesce only unsent work, use returned revisions and retain retry mutation IDs. Page commits are outside React state updaters and occur only after completion; completion, undo and explicit zero restart remain durable. |
| Identity and conflict honesty | History hooks gate resolved ownership, identity-tag navigation, suppress stale list/detail/load/save results, and keep guest APIs/disk silent. Recent rows distinguish loading, failure, local cache, pending and conflict. Successful explicit resolution reconciles the physical cursor; stale/superseded resolution does not move it. The reviewed backend authority/CAS/owner rules remain intact. |
| Shared replay and hints | Both physical adapters apply pre-remove → assignment → post-remove without recomputing Go rules. Shared screen replay applies own-group removal and noncapturing initial setup. Hints switch to authoritative snapshots after replacement/repetition/self-capture/AE and preserve recorded pass players and existing budgets. |
| Collection and archive interpretation | `next_guided_placement_index` leaves LEDs dark before pending replacement/removal/clear and distinguishes nonfinal dark frames from the final operation. Capture and offline autolabel share `validate_capture_archive`: exact frozen SGF, version/size/index and every real-frame board hash are checked before reuse, overwrite, append or output. Compatible proven legacy archives continue; incompatible/missing evidence preserves archived files, including `overwrite_existing`. Initial-empty legacy evidence is handled explicitly. |

## Independent verification

Executed against the reviewed working tree:

```text
CI=true .venv/bin/python -m pytest tests/test_baipu_load.py tests/test_baipu_api.py tests/test_baipu_capture.py tests/test_vision/test_baipu_autolabel.py -q
146 passed in 5.36s

CI=true .venv/bin/python -m pytest tests/test_board.py -q
7 passed in 0.13s
```

The final frontend run covered reducer/hook, session and real-history integration, session history, recent history, history API, physical entry button, both replay adapters and hints: **12 files / 141 tests passed in 6.39s**. A separate unchanged return-navigation suite passed **1 file / 2 tests in 1.17s**. Thus **143 focused frontend tests passed**. `npx tsc -b --pretty false` exited 0, and `git diff --check` passed. An earlier run caught the initial-entry regression while its owner was completing the fix; the final settled-tree run is green.

This is a specification review, not hardware acceptance or the independent ASTRA/MAX code-quality verdict. Device camera/LED behavior, the actual 1024×600 runtime journey, and deploy/build acceptance remain the controller's separate delivery checks. No production or developer database, device, service, commit or deployment was touched. The reviewer changed only this report; implementation owners made the fixes above.
