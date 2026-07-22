# 实验（3）HumanSL Search Boundary Design

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
Before the old confirmation batch was stopped, `rank_5d@40` vs `rank_6d@1s` and `rank_6d@40` vs
`rank_7d@1s` each completed their fixed 20-pair samples at 36--4. The `rank_7d@40` vs `rank_8d@1s`
checkpoint was interrupted after 11 complete pairs at 19--3, and `rank_8d@40` vs `rank_9d@1s` never
started. The two completed confirmations remain valid evidence for those exact `@40` matchups; the
interrupted checkpoint is descriptive only. The old batch is superseded only as the procedure for
answering the boundary question. None of these games is merged into boundary screening or any later
confirmation.

## Boundary-search protocol

Each rank transition is selected independently:

- `rank_5d@V` vs `rank_6d@1s`
- `rank_6d@V` vs `rank_7d@1s`
- `rank_7d@V` vs `rank_8d@1s`
- `rank_8d@V` vs `rank_9d@1s`

The finite experimental grid is `V in {2, 5, 10, 20, 30, 40}`. `40` is the known passing endpoint
from the completed screening. Start new screening at `20`. Each screening point collects exactly 10
complete color pairs, with the same opening played once per color. The point passes when the
lower-rank player's decision-game point estimate is at least 50%; otherwise it fails. Incomplete
pairs contribute no decision games. Each point has a fixed cap of 20 pair attempts; if the cap is
reached before 10 complete pairs, abort that rank transition without classifying the point or
selecting a candidate.

After `@20`:

- pass: screen `@10` next, then `@5`, then `@2`, stopping at the first failure;
- fail: screen `@30` next and stop.

The selected candidate is the lowest passing point immediately above the first failing point on the
tested path. If `@30` fails, select the prior known pass `@40`. If `@2` passes, report `V* <= 2` and
select `@2`; do not manufacture a failing endpoint. Do not rerun or append samples after seeing a
classification. If any observed result contradicts the assumed monotone ordering (a higher tested
visits point fails after a lower point passed, including the prior `@40` result), stop that transition
as non-monotonic and select nothing. Screening defines only an empirical tested-grid bracket and is
not a population-level boundary or proof of monotonicity.

After all four transitions have a selected lowest passing candidate on the tested grid, write and
commit an immutable selection manifest containing each candidate and the digests of all source
screening checkpoints. The selection manifest references the already committed opening-allocation
manifest by digest. Only then run fresh confirmation checkpoints. Each confirmation uses exactly 20
complete color pairs and at most 40 pair attempts. Screening games and the earlier `@40` confirmation
games are never merged into these samples.

Confirmation succeeds only when the per-transition 95% Wilson lower bound is greater than 50%.
Otherwise classify it as inconclusive (interval contains 50%) or weaker (upper bound below 50%) and
stop with “candidate not confirmed.” Confirmation results must never be used to select another
visits value. A replacement candidate would require a newly committed manifest and wholly fresh
confirmation under a newly versioned protocol. The four 95% intervals are per-transition intervals;
no familywise 95% claim or joint “all four” inferential claim is made.

## Independent opening allocation

Before any boundary screening starts, generate and commit a frozen opening suite and a separate
immutable opening-allocation manifest. The manifest preassigns every possible rank-transition,
visit-point, and phase allocation needed by the finite protocol, including candidates that may never
run. It is never regenerated after outcomes are observed.

The suite is large enough to avoid cycling at either attempt cap. Disjointness is defined by the
canonical opening move sequence, not merely by ID: every allocated sequence must be unique across
all boundary screening and confirmation allocations and must differ from every sequence in the
earlier `@40` suite. The harness validates sequence uniqueness and allocation coverage before play.
The suite checksum, allocation-manifest digest, exact assigned IDs, and canonical move sequences are
fingerprinted. This prevents relabeling or deterministic replay from masquerading as independent
confirmation.

## Harness changes

Add an explicit experimental minimum-visits CLI parameter with default `40`. Thread it through
player construction without changing the resulting `LadderRung` or query settings. Reject supplied
floors below 2. The floor applies only to `humansl_search` players with visits greater than one: such
a player must satisfy `visits >= supplied floor`. Existing HumanSL `@1`/`@1s` controls and pure-net
players such as `b28@20` retain their current validation.

Retain the existing complete configuration fingerprint and add a boundary-protocol version plus the
experimental floor, tested visits point, phase, pass rule, target pairs, attempt cap, opening-suite
checksum, exact opening assignment, finite-grid search order and stopping rule. Confirmation also
fingerprints the committed selection-manifest digest and source-screening checkpoint digests.
Existing identity fields remain mandatory: requested and attested main/human aliases, paths, hashes,
verified status, KataGo/wrapper capability version and snapshot, exact effective PIKL overrides,
selection algorithm/version, visits, noise/symmetry, board/rules, and referee settings.

The semantic probe accepts the same explicit floor and a player such as `rank_9d@20`. Before any
screening, it must verify the returned wrapper identity and the exact nonzero PIKL override settings.

## Failure handling

- Missing or mismatched b18/humanv0 identity: fail closed; do not start screening.
- Missing PIKL field or zeroed PIKL mix: fail closed.
- Existing checkpoint with any fingerprint or opening-assignment difference: reject resume.
- Interrupted games: preserve the JSONL checkpoint; only complete color pairs count.
- Mac sleep or wrapper failure: stop safely and resume from the validated checkpoint.

## Verification

Tests cover default rejection of `@20`, explicit acceptance, rejection below the experimental floor,
scope exclusions for `@1s` and pure-net players, configuration fingerprinting, checkpoint mismatch,
disjoint opening allocation, selection-manifest validation, attempt-cap aborts, and preservation of
the canonical b18+humanv0 PIKL player. The existing HumanSL self-play, probe, adapter, ladder, and
HTTP-engine tests must remain green before launching the new screening.
