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
- Zero or negative policy entries remain unselectable. Temperature never makes an illegal move legal.

This is post-processing of the returned `humanPolicy`. It must not set KataGo's `rootPolicyTemperature`, change the engine query, run an additional model inference, or modify PIKL/search behavior.

The implementation must calculate transformed weights stably. It may use log weights relative to the maximum positive log weight to avoid overflow or underflow. `T` must be a finite, positive, non-boolean number.

## 5. Shared units and interfaces

### 5.1 Core policy transformer

A small pure unit in `katrain/core/ladder.py` owns HumanSL policy validation, stable temperature transformation, and sampling. It accepts:

- the returned HumanSL policy vector;
- board dimensions;
- a temperature;
- an optional random-number source exposing the sampling primitive needed by the implementation.

It returns the same `(column, bottom-origin row)` or `pass` representation as the existing picker. Existing callers that omit temperature retain exact `T=1` behavior and compatible randomness.

The unit exposes a separate pure normalized-distribution helper so deterministic tests and the experiment manifest can inspect the mathematical transformation without sampling.

### 5.2 Calibration player identity

The self-play calibration parser gains a canonical temperature-player syntax:

```text
rank_1d@1t2
rank_5d@1t1.3
rank_9d@1t0.4
```

Canonical labels normalize temperature with a stable decimal representation, so aliases such as `t2.0` cannot create distinct evidence identities. Existing `rank_nd@1` remains native `T=1`; existing `rank_nd@1s` remains argmax. Temperature syntax is valid only for native HumanSL one-visit players and cannot be combined with `s`, PIKL visits, `b18`, or `b28` players.

The parsed selection is `temperature_weighted`. Its immutable evidence identity contains the canonical label, profile, selection algorithm version, and normalized temperature. The engine request remains native HumanSL at one visit.

### 5.3 Reproducible experiment RNG

Each decision game receives a deterministic seed derived from the immutable experiment identity, matchup, opening-pair index, color leg, and retry generation. The ledger records the seed derivation version, not a mutable global RNG state.

The two color legs use distinct seeds. Retrying an inconclusive color pair uses a new recorded generation and therefore a new deterministic seed, while replaying the same completed ledger reproduces every selected move.

Production callers are not switched to deterministic seeds in this slice.

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

Every matchup uses ten frozen openings with colors swapped: ten complete pairs and twenty eligible games. If either color leg is inconclusive, exclude the whole pair and replenish it, subject to the existing bounded-attempt rules. Total planned eligible games are 180.

The pilot reuses the post-fix self-play transport, model identity attestation, referee, opening allocation, append-only checkpointing, and pair accounting. A new immutable manifest freezes exact player identities, opening allocation digest, model digests, source revision, seed derivation version, target pair count, and attempt cap before any game runs.

## 6. Evidence gates

### 6.1 Mathematical gate

For representative policies, automated tests must establish:

- `T=1` preserves the normalized original distribution within floating-point tolerance;
- increasing `T` increases Shannon entropy for a non-uniform positive distribution and decreases its top-move probability;
- decreasing `T` does the converse;
- identical explicit RNG seeds reproduce the same selection sequence;
- zero/negative entries, pass indexing, malformed length, NaN/infinity, invalid temperature, and all-nonpositive input fail or behave according to the existing strict policy contract;
- the transform does not mutate the engine response.

### 6.2 Pilot direction gate

The pilot supports proceeding to full-rank fitting when:

1. at least eight of nine matchup point estimates favor the predeclared stronger side;
2. the aggregate result within each of `rank_1d`, `rank_5d`, and `rank_9d` favors the lower-temperature/argmax direction;
3. no completed contrast has a statistically persuasive inversion, defined as a Wilson 95% interval wholly below 50% for the predeclared stronger side;
4. all result rows retain verified engine/model identity and exact selection identity.

A 10–10 or 11–9 contrast near argmax is not a protocol failure; it means that finite temperature is empirically close to argmax. The report must distinguish “direction supported,” “indistinguishable at this sample,” and “inversion.” No adaptive extra games are appended after inspecting scores.

If the gate fails, the system must not fit product temperatures. It records the completed evidence and diagnoses implementation, seed coupling, or non-monotonic empirical behavior under a separate reviewed protocol.

## 7. Follow-on 41-tier fitting rule

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

- Missing/malformed `humanPolicy`, invalid temperature, invalid model identity, selection drift, malformed ledger rows, digest drift, or non-reproducible completed selections fail closed.
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
5. the 180-game internal pilot completed or a truthful stopped ledger if an external/runtime failure occurs;
6. a generated clean summary artifact with the gate classification and source digests;
7. no change to the production 37-rung provisional table or user-visible promotion/relegation behavior in this slice.

The next slice may begin only after the pilot gate is classified. A passing result starts full-rank temperature fitting; a failing result starts diagnosis rather than product integration.
