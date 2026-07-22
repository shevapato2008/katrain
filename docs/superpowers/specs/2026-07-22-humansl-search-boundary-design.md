# HumanSL Search Boundary Design

## Goal

Measure how many corrected HumanSL+PIKL search visits a lower HumanSL rank needs to reach the next
rank's one-step argmax policy. The experiment must locate a visits boundary rather than merely
confirm the already-dominant `@40` point.

## Scope and safety boundary

- This change applies only to the operator-run self-play and semantic-probe tools under
  `superpowers/tracks/golaxy-ai-ladder-parity/calibration/`.
- Production ladder rungs keep the validated `>=40` visits floor. No production strength label or
  KataGo configuration changes.
- The self-play harness keeps `40` as its default minimum. Visits below 40 require an explicit
  experimental CLI option so an ordinary run cannot silently enter the range that KataGo's PIKL
  example discourages.
- Every low-visits query must retain the corrected semantics: b18 main model, humanv0 human model,
  the canonical nonzero PIKL settings, explicit model routing, and wrapper identity attestation.

## Existing `@40` evidence

The four 10-pair screenings at `@40` remain valid evidence that the boundary is at most 40 visits.
The interrupted `@40` confirmation checkpoint is preserved but marked superseded for the boundary
question. It is not merged into screening or into any later confirmation.

## Boundary-search protocol

Each rank transition is selected independently:

- `rank_5d@V` vs `rank_6d@1s`
- `rank_6d@V` vs `rank_7d@1s`
- `rank_7d@V` vs `rank_8d@1s`
- `rank_8d@V` vs `rank_9d@1s`

Start at `V=20`. Each screening point collects exactly 10 complete color pairs, with the same
opening played once per color. The point passes when the lower-rank player's decision-game point
estimate is at least 50%; otherwise it fails. Incomplete pairs contribute no decision games and the
existing attempt cap remains in force.

After `@20`:

- pass: screen `@10` next;
- fail: screen `@30` next.

Continue by bisecting the remaining integer interval between the nearest known failing and passing
points. Stop screening a transition when the bracket is narrow enough that one additional integer
candidate would not materially improve the operational answer, or when the explicit experimental
floor is reached. Report a bracket such as `V* in (10, 20]`; do not claim exact monotonicity from
screening alone.

After all four transitions have a selected lowest passing candidate on the tested grid, freeze the
candidates and run fresh confirmation checkpoints. Each confirmation uses exactly 20 complete color
pairs. Screening games and interrupted `@40` confirmation games are never merged into these samples.

## Harness changes

Add an explicit experimental minimum-visits CLI parameter with default `40`. Thread it through
player construction without changing the resulting `LadderRung` or query settings. Reject values
below 2, reject low-visits players unless the option is supplied, and record the experimental floor
in the checkpoint configuration so resume validation cannot mix protocols.

The semantic probe accepts the same explicit floor and a player such as `rank_9d@20`. Before any
screening, it must verify the returned wrapper identity and the exact nonzero PIKL override settings.

## Failure handling

- Missing or mismatched b18/humanv0 identity: fail closed; do not start screening.
- Missing PIKL field or zeroed PIKL mix: fail closed.
- Existing checkpoint with a different floor or player configuration: reject resume.
- Interrupted games: preserve the JSONL checkpoint; only complete color pairs count.
- Mac sleep or wrapper failure: stop safely and resume from the validated checkpoint.

## Verification

Tests cover default rejection of `@20`, explicit acceptance, rejection below the experimental floor,
configuration fingerprinting, checkpoint mismatch, and preservation of the canonical b18+humanv0
PIKL player. The existing HumanSL self-play, probe, adapter, ladder, and HTTP-engine tests must remain
green before launching the new screening.
