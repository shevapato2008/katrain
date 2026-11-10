# Physical SGF replay — independent ASTRA/MAX plan review, round 2

**Decision: APPROVED.** The three material round-1 gaps are resolved in the amended plan. No further plan-review round is needed; P1/P2/P3 can begin their owned-file implementation.

Reviewed `docs/superpowers/plans/2026-11-03-physical-sgf-replay.md` and the round-1 report on `feature/baipu-physical-history-20261103`, physical product baseline `9e83f1ad5eaf61f354b71bd6e8bb3dab28717531`. Account-history work in progress was treated as separate, authorized work. This review changes only this report; it does not certify implementation or hardware acceptance.

## Round-1 findings closed

### R1 — Placement evidence is distinct from transaction completion

Plan lines 57–67 now keep the durable cursor fixed through pre-removal, placement and post-removal. A correct-color placement observation can acknowledge a one-motion replacement with pending or partially completed authoritative captures, then enter removal guidance without completing the step. A final board equal to the entry/pre-cleared board cannot substitute for the required suicidal placement observation. Post-removal promotion is explicitly disabled, and completion occurs once after the final board is established.

This is implementable using the existing setup mechanism. `katrain/vision/sync.py` reports all missing points and all extra stones with colors, sufficient to evaluate the amended placement witness against an authoritative target. The existing frontend API, endpoint and vision service already carry `setup_id` through to progress/completion events. P2 can extend its reducer and consume these IDs without adding another camera protocol or Go-rules implementation.

The round-1 M3/L3 one-motion replacement and S9 suicidal-placement cases remain concrete implementation checks for this contract. The plan also explicitly covers final-step removal, no-op/clear distinctions and cancellation on undo/resume/source changes.

### R2 — Retry and manual fallback retain authoritative boards

Plan lines 67–71 explicitly prohibit the existing `adopt(observedBoard)` behavior. Recheck resends the same authoritative stage target under a new setup ID. The separate operator-confirmed manual path disarms camera/monitor and retains the ordered instructions; it does not silently turn a mismatching observation into SGF truth.

The current unsafe path is localized to `usePhysicalBaipu.ts` and its `BaipuSessionPage.tsx` action, both owned by P2. Its replacement fits the existing status/action components. The declared generation and stage cancellation rules cover pending requests and stale events. No additional plan contract is needed.

### R3 — Capture and autolabel share an interpretation guard

Plan lines 75–89 now pin replay version 2 and exact SGF identity, and require SGF/size/index plus every archived real-frame board hash to be checked before idempotent reuse, overwrite/append or autolabeling. Missing or mismatching evidence fails without modifying archived files; `overwrite_existing` cannot bypass the guard. Legacy archives are eligible only when their existing hashes prove compatibility, with the initial empty frame handled explicitly.

Both capture and offline autolabel are explicitly assigned to P1, with one shared validator. The existing capture lock provides a place to validate before the current early idempotent return or destructive overwrite branch; autolabel can validate when loading its manifest and SGF, before producing labels. The shared `baipu_identity.py` already provides version 2 and an exact-content SHA-256 helper. The actual capture module is `katrain/web/core/baipu_capture.py`, the file abbreviated as `core/baipu_capture.py` in the ownership list.

The incompatible legacy AB/AW example, compatible ordinary legacy archive and byte-for-byte preservation checks are explicitly assigned. A legacy interpreter, migration or archive-schema redesign is unnecessary.

## Integration and scope

The frozen H3 hook matches the current exported argument/result shape, including stable `open`/`save`, durable `?history=ID` routing and conflict resolution. P2's integration point is after authoritative load, and history saves follow the committed cursor rather than a transient placement or React updater. The plan keeps history ownership separate from physical implementation.

The scope remains proportionate: a permissive record interpreter with strict live gameplay preserved, corresponding shared-screen semantics, authoritative physical stages, and archive compatibility. Full intermediate-state oracle checks and focused hardware fakes address the changed behavior; camera repair, generalized parser work and production deployment remain outside this task. No tests or device actions were run for this plan-only review.
