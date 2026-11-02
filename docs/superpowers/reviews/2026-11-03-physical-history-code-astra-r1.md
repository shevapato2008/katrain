# Physical replay + account history — independent ASTRA/MAX code review

**Decision: APPROVED. The P2 finding below is fixed and independently verified; no outstanding P1/P2 findings remain in the reviewed scope.**

Reviewed the combined working tree, including new product files, against `9e83f1ad5` on `feature/baipu-physical-history-20261103`. Read both approved 2026-11-03 plans, their approved round-2 reviews, the H1/H2 backend specification review and the settled combined specification review. The separate kifu source/metadata investigations and proposed standardization are excluded.

## Closed P2 — A setup operation after play could make AI hints analyze a different board

**Location:** `katrain/web/ui/src/kiosk/hooks/useBaipuHint.ts:44` and `:70`.

The new physical interpreter correctly applies `AB`/`AW` at their recorded position without captures. At the initial review, `needsPositionSnapshot` only recognized clears, replacement/repetition and self-capture. An ordinary setup on an empty point after a played move passed that check. The other branch then gathered every applied setup into `initial_stones`, moving that later operation before all recorded moves. This changed earlier captures and produced a different position from the authoritative physical board.

Concrete active-session reproduction:

```sgf
(;SZ[19];B[aa];W[ba];AW[ab];B[ac];B[bb];W[dd])
```

At completed cursor `k=5`, the authoritative board is black `{A19, A17, B18}`, white `{B19}`. The original request instead started with white `A18`, then played `B A19`, `W B19`, `B A17`, `B B18`. That history captured black `A19` too early and retained white `A18`: black `{A17, B18}`, white `{A18, B19}`. The displayed board is a valid settled position and the session still has a next move, so the AI-hint action is available. Its suggestions and evaluation therefore concerned another board.

**Closed:** `useBaipuHint.ts:46–51` now tracks whether recorded play has occurred and selects the existing authoritative snapshot path for any subsequent applied setup. This is confined to the existing request adapter; normal leading setup and ordinary legal history remain unchanged. The added regression in `useBaipuHint.test.tsx` pins the exact backend schema-2 instructions above, the correct four stones at `k=5`, and the black pass needed to retain white as the next player.

**Independent evidence:** a read-only scratch check using the actual Python `build_steps_from_sgf`, transpiled actual `buildHintRequest`/`replayBaipuSteps`, and the existing shared replay helper first reproduced the two different stone sets above. After the fix, a fresh check with actual core-generated steps verified the exact snapshot and white next player at `k=5`, and verified that the future setup does not alter the earlier request at `k=2`. Independently ran `npx vitest run src/kiosk/hooks/useBaipuHint.test.tsx --reporter=dot`: **29 passed in 522 ms**. `git diff --check` also passed. No test or product file was modified by the reviewer, and no engine, database or device was used.

## Other reviewed boundaries

No further material finding was identified in owner-scoped immutable history identity, local CAS/idempotency, causal cloud acceptance, clean adoption, writer rotation, strict bound-owner transport, pending-row drain, stale frontend result suppression, completed-cursor persistence, physical pre/place/post transaction ordering, or archive validation before reuse/overwrite/autolabel output. The specification-review follow-ups for initial manual entry, capture LED ownership, dispatched-save lifetime/exit honesty, and same-cursor hint scope are present in the settled code.

The existing focused verification evidence was inspected rather than repeating the complete suites: the settled specification review records 143 frontend and 153 Python tests, TypeScript success and a clean diff check; the backend review separately records its isolated SQLite/PostgreSQL and ownership/concurrency checks. The new regression and independent focused run cover the additional late-setup finding. Hardware/runtime acceptance remains separate from this code review.

Only this review report was written by the reviewer. The implementation owner made the narrow fix and regression, which are settled and re-reviewed. No production/developer database, device, deployment, commit or `data/kifu-album/` access occurred.
