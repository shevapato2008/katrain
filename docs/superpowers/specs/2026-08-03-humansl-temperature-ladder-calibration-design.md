# HumanSL Temperature Ladder Calibration Design

**Date:** 2026-08-03  
**Status:** approved for autonomous implementation under the user's 2026-08-03 continuation authorization

## 1. Purpose

Build and validate the smallest shared foundation needed to turn HumanSL policy output into a smooth strength control for the future 41-tier promotion/relegation ladder. The first slice proves that temperature-shaped HumanSL sampling produces reproducible policy distributions and an empirically ordered playing-strength direction.

This slice does not change the production ladder, Galaxy UI, kiosk UI, user rank records, placement, promotion, or relegation behavior. Those remain gated on the evidence produced here.

## 2. Product decisions already fixed

- The final ladder has exactly 41 user-visible levels:
  - `20级` through `1级`: 20 native HumanSL levels.
  - `准1段, 1段, ..., 准9段, 9段`: 18 dan levels.
  - `职业水平`, `职业顶尖`, `超越人类`: 3 top levels.
- The target is approximately 50% player win rate against the AI bearing that level, not merely “AI is no weaker than the corresponding Golaxy level.”
- `20级` through `1级` remain native `rank_20k ... rank_1k` HumanSL weighted sampling at one visit.
- Adjacent product levels must not have identical configurations and must not have a known strength inversion.
- The eventual local-device route is permitted only when measured RK3562 P95 move latency is at most three seconds; otherwise the same frozen recipe is served remotely.
- Human-vs-human games never change this AI ladder rank.

## 3. Why a continuous HumanSL control is required

Post-fix evidence shows that a binary choice between native sampling and argmax cannot fill the dan ladder:

- Within the same `rank_nd` profile, `@1s` argmax beat `@1` weighted sampling 165–15 across 180 eligible games.
- A lower-profile argmax beat the next higher profile's native sampling 130–30 across 160 eligible games.
- Same-rank native sampling against Golaxy quasi/full levels from 1D through 6D was generally too strong, ranging from 6–3 to 10–0.

Therefore profile labels alone do not provide two well-spaced configurations for every quasi/full dan pair, while jumping to argmax is much too large.

## 4. Temperature semantics

For valid positive HumanSL policy weights `p_i` and temperature `T > 0`, form the sampling weights

```text
w_i = p_i ** (1 / T)
q_i = w_i / sum(w_j)
```

and sample one legal move from `q`.

- `T = 1`: exactly the existing native weighted sampling distribution.
- `T > 1`: flatten the distribution; lower-probability HumanSL moves become more likely.
- `0 < T < 1`: sharpen the distribution; high-probability HumanSL moves become more likely.
- `T -> 0`: approaches HumanSL argmax but remains a separate finite-temperature mechanism.
- Zero or negative policy entries remain unselectable. The transformer selects a positive-policy board coordinate; it does not independently prove board legality because it receives no board state. The existing engine contract is responsible for assigning nonpositive policy to unavailable moves. A downstream illegal move remains a fail-closed inconclusive game.

This is post-processing of the returned `humanPolicy`. It must not set KataGo's `rootPolicyTemperature`, change the engine query, run an additional model inference, or modify PIKL/search behavior.

The implementation must calculate transformed weights stably. It may use log weights relative to the maximum positive log weight to avoid overflow or underflow. `T` must be a finite, positive, non-boolean number.

## 5. Shared units and interfaces

### 5.1 Core policy transformer

A small pure unit in `katrain/core/ladder.py` owns HumanSL policy validation, stable temperature transformation, and sampling. It accepts:

- the returned HumanSL policy vector;
- board dimensions;
- a temperature;
- one explicit unsigned 64-bit draw.

It returns the same `(column, bottom-origin row)` or `pass` representation as the existing picker. It iterates candidates in the current canonical order (`x` outer, bottom-origin `y` inner, then pass), maps the draw to `u=(draw+0.5)/2**64`, and chooses the first cumulative transformed weight strictly greater than `u * total_weight`, with the last positive candidate as the floating-point fallback.

Existing callers that omit temperature retain the exact legacy weighted-key sampler. Temperature players use the new inverse-CDF sampler, including explicit `T=1`; the two algorithms have the same target distribution but different evidence identities and random sequences.

The unit exposes a separate pure normalized-distribution helper so deterministic tests and the experiment manifest can inspect the mathematical transformation without sampling.

### 5.2 Calibration player identity

`LadderRung` gains a separate optional `human_policy_temperature` field. `None` means the legacy picker; a finite value means the temperature picker. This field is consumed only by local move selection and is never emitted by `rung_strength_spec`, `ladder_override_settings`, or the engine query. The existing `root_policy_temperature` field remains an engine-side setting and must not be reused.

The self-play calibration parser gains a canonical temperature-player syntax:

```text
rank_1d@1t2
rank_5d@1t1.3
rank_9d@1t0.4
```

The numeric grammar is plain unsigned decimal (`0.4`, `1`, `2.0`), with no sign, exponent, whitespace, leading-dot, trailing-dot, NaN, or infinity. The accepted closed range is `[0.05, 10]`. Canonical labels remove leading integer zeroes and trailing fractional zeroes, so `t2.0` becomes `t2`. Explicit `t1` remains the distinct canonical temperature-selection identity `rank_nd@1t1`; it does not alias legacy `rank_nd@1` because the sampling algorithm and audit contract differ. Existing `rank_nd@1` remains legacy native sampling; existing `rank_nd@1s` remains argmax. Temperature syntax is valid only for native HumanSL one-visit players and cannot be combined with `s`, PIKL visits, `b18`, or `b28` players.

The parsed selection is `temperature_weighted`. Its immutable evidence identity contains the canonical label, profile, `temperature-inverse-cdf-v1`, and normalized decimal temperature. `_player_move_certified` receives the `LadderRung` plus an explicit per-game selection context, derives a draw for each temperature-selected move, and passes both temperature and draw to the core picker. The engine request remains native HumanSL at one visit and contains neither local temperature field.

### 5.3 Reproducible experiment RNG

Temperature players use stateless draws under `temperature-draw-sha256-u64-v1`. For every temperature-selected move, encode this exact JSON array with UTF-8, `ensure_ascii=False`, and separators `(',', ':')`:

```text
[protocol_version, manifest_sha256, canonical_matchup_id,
 pair_attempt, color_index, ply, player]
```

`canonical_matchup_id` is exactly `<canonical-A-label>__vs__<canonical-B-label>` with the literal ASCII separator `__vs__` and no escaping; the accepted label grammar contains no underscore sequences that make this ambiguous. Take SHA-256, interpret the first eight digest bytes as an unsigned big-endian integer, and use that integer as the draw. `player` is exactly `A` or `B`; `ply` includes the frozen opening length. The two color legs and any later replenishment attempt therefore have distinct draws. There is no retry-generation concept: the existing monotonically increasing `pair_attempt` is the replenishment identity.

Each game record stores a compact sampling trace for temperature-player turns: `ply`, `player`, canonical temperature, derived `draw_u64`, selected policy index, and a policy digest. To form the digest, convert every policy entry with Python `float(value)`, prefix the vector with its element count as one unsigned big-endian 32-bit integer, append every element as IEEE-754 binary64 big-endian bytes (`struct.pack('>I', count)` followed by `struct.pack('>d', value)` for each element), and SHA-256 the concatenation. This binds the trace to the observed response without storing the large vector or claiming that a resume validator can recompute the historical inverse-CDF choice. Resume validation recalculates the stateless draw and validates trace shape, policy-digest syntax, selected-index bounds, and selected move/index agreement; mathematical correctness of inverse-CDF selection is frozen by unit known-answer vectors, not retroactively proven from the compact ledger. Reissuing a nondeterministic engine query is not expected to recreate the same policy.

Production callers are not switched to deterministic draws in this slice.

### 5.4 Pilot protocol

The pilot freezes three representative profiles and three contrasts per profile:

| Profile | Expected stronger A | Expected weaker B |
|---|---|---|
| `rank_1d` | `T=1.0` | `T=2.0` |
| `rank_1d` | `T=0.4` | `T=1.0` |
| `rank_1d` | argmax | `T=0.4` |
| `rank_5d` | `T=1.0` | `T=2.0` |
| `rank_5d` | `T=0.4` | `T=1.0` |
| `rank_5d` | argmax | `T=0.4` |
| `rank_9d` | `T=1.0` | `T=2.0` |
| `rank_9d` | `T=0.4` | `T=1.0` |
| `rank_9d` | argmax | `T=0.4` |

Every matchup targets ten complete color pairs and twenty eligible games, with a hard cap of twenty pair attempts. The exact allocation is the first twenty entries of the existing 24-entry `opening_suite_v1.json`, in file order, shared identically by all nine matchups. Attempt `i` uses allocation `i`; there is no cycling. Both colors of an attempt use the same opening. If either color leg is inconclusive, exclude the whole pair and advance to the next allocated attempt. Total planned eligible games are 180.

The pilot reuses the post-fix self-play transport, model identity attestation, referee, append-only checkpointing, and pair accounting. A committed schema-1 manifest freezes:

- `protocol=humansl-temperature-pilot-v1` and ordered nine-matchup list;
- exact canonical players, expected stronger side A, target ten pairs, cap twenty attempts;
- opening suite path, file SHA-256, internal checksum, and allocated opening IDs/moves for attempts 0–19;
- the implementation-base revision plus SHA-256 of these runtime sources: `katrain/core/ladder.py`, `katrain/core/ladder_calibration.py`, `superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py`, `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`, and the new temperature pilot protocol/manifest modules named by the implementation plan; a changed or dirty bound file fails preflight even when Git HEAD is a descendant of the base;
- selection, draw, referee, adjudication, symmetry, rules, komi, move-cap, and checkpoint schema versions;
- expected b28/humanv0 model identities obtained from the live preflight and written to a separate launch snapshot rather than mutating the committed manifest.

The lifecycle is two commits and is deliberately non-self-referential. First commit all implementation and tests. The manifest generator binds `implementation_base_revision` to that commit and hashes the files as they exist in it. Then generate and commit the manifest in a later commit. Launch permits HEAD to equal or descend from the base but requires every bound file byte to retain its frozen hash. The manifest has a canonical SHA-256 calculated over the object without its `manifest_sha256` field, then stores that digest in the field. Every checkpoint header includes the manifest path and digest. Creation fails if the target manifest already exists; launch and resume recalculate all bound digests, require exact checkpoint configuration equality, and fail closed on unknown rows or relevant source drift. The launch snapshot is created once with exclusive semantics and is bound into all nine checkpoint configurations.

## 6. Evidence gates

### 6.1 Mathematical gate

For representative policies, automated tests must establish:

- `T=1` preserves the normalized original distribution within floating-point tolerance;
- increasing `T` increases Shannon entropy for a non-uniform positive distribution and decreases its top-move probability;
- decreasing `T` does the converse;
- the frozen unsigned-draw known-answer vectors reproduce the same transformed distribution and selection;
- finite negative and zero policy entries are excluded, matching the existing contract; a mixed vector remains usable when at least one finite entry is positive;
- wrong vector length, any NaN/infinity entry, boolean/nonfinite/out-of-range temperature, and an all-nonpositive vector raise `LadderMoveError` before selection;
- pass remains the final policy index and participates in the same transformed distribution;
- the transform does not mutate the engine response.

### 6.2 Pilot direction gate

The pilot supports proceeding to full-rank fitting when:

1. at least eight of nine completed matchups have A wins greater than 10 of 20; a 10–10 score is a tie, not a direction win;
2. within each of `rank_1d`, `rank_5d`, and `rank_9d`, the predeclared A sides total more than 30 wins across the three 20-game matchups;
3. no completed contrast has a statistically persuasive inversion, defined as a Wilson 95% interval wholly below 50% for the predeclared stronger side;
4. all result rows retain verified engine/model identity and exact selection identity.

A completed matchup is classified as `direction_supported` when A wins exceed 10 and the Wilson interval crosses 50%, `persuasive_direction` when its lower bound exceeds 50%, `point_tie` at 10–10, `point_inversion` below 10 wins while its interval crosses 50%, and `persuasive_inversion` when its upper bound is below 50%. No adaptive extra games are appended after inspecting scores.

The overall pilot is `incomplete` if any matchup has fewer than ten complete pairs or any checkpoint/launch identity is invalid. Otherwise it is `fail` if any persuasive inversion exists, fewer than eight matchups favor A, or any profile aggregate is at most 30. It is `pass` only when all completion conditions hold and none of those failure conditions holds.

If the gate fails, the system must not fit product temperatures. It records the completed evidence and diagnoses implementation, seed coupling, or non-monotonic empirical behavior under a separate reviewed protocol.

## 7. Follow-on 41-tier fitting rule (non-implementing in this slice)

This section fixes how the pilot evidence will be used, without prematurely assigning unmeasured production values.

- For each `rank_1d ... rank_6d`, screen `T={2.0, 1.6, 1.3, 1.15, 1.0}` against the matching Golaxy quasi/full targets; extend to `2.5/3.0` if even `T=2.0` is too strong.
- For targets lying between native sampling and argmax, screen `T={0.8, 0.6, 0.4, 0.2}`.
- Screening uses four eligible games only to find a bracket. The selected candidate is then brought to ten eligible, color-balanced games.
- Existing direct anchors remain the starting points: `rank_7d@1s` for 7段, `rank_8d@1s` for 8段, `rank_9d@4` for 9段, `b18@1` for 职业水平, and provisionally `b18@32` for 超越人类.
- 职业顶尖 starts at pure `b18@12`, between the observed `b18@8` weak side and `b18@16` strong side.
- `b18@32` versus 超越人类 remains explicitly partial at 7–7/14 until the preregistered twenty eligible games complete.
- After external placement, every adjacent product configuration is screened internally. A known inversion blocks release; a statistical tie may trigger a wider sample or candidate adjustment under a frozen follow-up protocol.

The product table may freeze only measured values. Variables such as `T-Q1` are calibration placeholders and cannot ship as runtime defaults.

## 8. Runtime and deployment boundary

This pilot runs through the current server-side post-fix HumanSL engine path. It does not decide local kiosk deployment.

After product recipes are frozen, the device-routing slice benchmarks each distinct model/recipe on RK3562. A recipe may be marked local only if its measured move-latency P95 is at most three seconds under the agreed board and concurrency conditions. Otherwise Galaxy and kiosk request the same server recipe. Routing must not silently substitute a different model, profile, temperature, or visit count.

The 41-tier product ladder does not require b28 as a playing model based on current evidence: native HumanSL uses `humanv0`, PIKL uses `b18 + humanv0`, and top pure search uses `b18`. b28 remains available for analysis, refereeing, and experimental comparison.

## 9. Failure handling and auditability

- Missing/malformed `humanPolicy`, invalid temperature, invalid model identity, selection drift, malformed ledger rows, bound-file/manifest digest drift, or a sampling trace whose stateless draw, shape, index bounds, or selected move/index mapping is inconsistent fails closed. Compact traces do not claim to re-prove historical inverse-CDF selection without the original policy vector.
- Engine/referee inconclusives follow existing complete-pair replenishment; they never enter the win/loss denominator.
- A stopped run resumes only from its validated append-only ledger and immutable manifest.
- Existing post-fix results are read-only evidence and are never rewritten into the new pilot as newly played games.
- Reports show wins/losses from the named A side, eligible/target games, complete/inconclusive pairs, completion state, model identities, temperature, source path, and evidence class.

## 10. Verification and deliverables

The slice is complete when it provides:

1. focused unit tests for temperature transformation, sampling, validation, canonical parsing, deterministic seeds, and unchanged legacy semantics;
2. an immutable pilot manifest and a dry-run/preflight that reports the exact nine-matchup schedule without issuing engine requests;
3. relevant core/platform regression tests passing;
4. a live health/model-identity preflight;
5. all 180 eligible pilot games completed and the overall gate classified as `pass` or `fail`;
6. a generated clean summary artifact with the gate classification and source digests;
7. no change to the production 37-rung provisional table or user-visible promotion/relegation behavior in this slice.

A runtime stop must preserve a truthful resumable ledger and report `incomplete`, but it does not complete this slice. The agent continues from the validated checkpoint when the in-scope runtime is recoverable. The next slice may begin only after the pilot gate is classified. A passing result starts full-rank temperature fitting; a failing result starts diagnosis rather than product integration.
