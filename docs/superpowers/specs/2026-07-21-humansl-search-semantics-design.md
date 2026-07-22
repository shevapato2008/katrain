# HumanSL Search Semantics Design

**Date:** 2026-07-21

## Problem

The ladder and calibration harness can label a player `humansl_search`, but the request currently only carries a
`humanSLProfile`. The rung's `net` is metadata, and every HumanSL blending parameter is left at KataGo's zero/default
value. Against the local multi-model HTTP service this silently routes search to the default b28 model, so every
`rank_Xd@V` player with `V > 1` is pure b28 search. The old self-play results therefore do not measure HumanSL search.

KataGo already supports the desired operation. This is a KaTrain request construction, backend-routing, validation,
and experiment-identity defect; no KataGo C++ changes are required.

## Goals

1. Make `humansl_search` mean b18 main-model search influenced by the selected humanv0 rank profile.
2. Ensure a rung's requested main model is executed by backends that support per-query model selection.
3. Fail closed instead of silently degrading to the default model or zero-weight HumanSL.
4. Give runtime and calibration one canonical strength configuration and a complete player fingerprint.
5. Validate the semantics locally before rerunning invalidated experiments.

## Non-goals

- Changing KataGo's C++ search implementation or model files. The local Python HTTP wrapper may add routing
  attestation/capability metadata; that is transport observability, not a search change.
- Replacing the current 37-rung product layout in this change. Its active rungs remain native HumanSL @1 for rungs
  1–25 and explicit b28 search for rungs 26–37.
- Claiming that KataGo's example PIKL parameters are calibrated product values.
- Supporting per-query model switching in a single native KataGo subprocess.

## Considered Approaches

### A. Put `model` inside every rung's KataGo `overrideSettings`

This is the smallest request change and works with the local HTTP wrapper, but `model` is wrapper routing metadata,
not a native KataGo override. Sending it through the generic engine path could break native subprocess backends and
keeps routing concerns mixed with search parameters.

### B. Add a backend-aware model selector and a canonical strength request (recommended)

Keep KataGo search overrides separate from transport routing. A strength specification exposes visits, KataGo
overrides, and the requested main model. The HTTP backend emits the wrapper's selector; a native subprocess accepts
only its already-loaded model and fails closed on an incompatible request. Calibration consumes the same canonical
specification. This makes the model boundary testable and prevents another metadata-only `net` field.

### C. Run humanv0 as the main model

This makes HumanSL participate in tree search without PIKL, but changes both policy and value to the human model and
does not implement the intended "b18 ceiling plus human style" behavior. It remains useful as a future experimental
control, not the product mechanism.

## Architecture

### Canonical rung strength specification

`katrain/core/ladder.py` remains the source of truth for rung semantics. It will define:

- A named baseline PIKL recipe based on KataGo's official HumanSL search example.
- Validation rules for each mechanism.
- A pure helper that returns the requested main model, auxiliary human model identity, top-level visits, and native
  KataGo overrides as separate fields.

`LadderRung.net` is not reused as both identities: for native HumanSL it names the move-producing human network, not
the main search network. The canonical specification therefore exposes explicit `main_model` and `human_model`
identities. Experimental `humansl_search` players declare `main_model="b18"` and `human_model="humanv0"`.

The baseline recipe starts with:

```python
{
    "humanSLChosenMoveProp": 1.0,
    "humanSLChosenMovePiklLambda": 0.08,
    "humanSLRootExploreProbWeightless": 0.8,
    "humanSLCpuctPermanent": 2.0,
    "useUncertainty": False,
    "subtreeValueBiasFactor": 0.0,
    "useNoisePruning": False,
}
```

These are semantic-enablement defaults, not calibrated strength claims. Experiments may copy the recipe and vary one
declared parameter, especially PIKL lambda.

### Backend routing

For the HTTP analysis service, the exact wrapper selector is `overrideSettings.model`. The HTTP adapter injects that
key only at the final HTTP wire boundary. The wrapper removes it before writing JSON to KataGo stdin. The canonical
native override dictionary remains model-free, and tests make it structurally impossible for `model` to enter a
`KataGoEngine` subprocess request.

The wrapper's `/health` capability document must advertise every model alias, path/hash identity, running state, and
HumanSL availability. Each `/analyze` response must attest the selected model alias and identity (for example in
reserved wrapper metadata) after routing. Product and calibration reject a mismatch between requested and attested
models. This catches default-model fallback and prevents “request said b18” from being mistaken for executed b18.

For an in-process/native subprocess backend, this change does not attempt alias-to-file inference. Any rung requiring
an explicit main-model identity, including `humansl_search` and b28-certified search rungs, requires the multi-model
HTTP backend and fails closed on `KataGoEngine`. Supporting native model identity through model-path hashes,
`altcommand`, or a multi-process engine pool is outside this change. Native HumanSL @1 may continue only when its
existing human-model capability is present because its main search identity is irrelevant to its move selection.

### Selection semantics

Native HumanSL rungs (`humansl`, one visit) continue to sample `humanPolicy`, with the existing deterministic argmax
mode retained only for explicit experimental players. A valid `humansl_search` player uses KataGo's searched
`moveInfos` and selects `order == 0`.

This is not a client-side approximation of PIKL. KataGo's `Search::getPlaySelectionValues` in
`cpp/search/searchresults.cpp` applies `humanSLChosenMoveProp` and `humanSLChosenMovePiklLambda` to the human policy and
searched child utilities. Analysis generation assigns that result to each `AnalysisData.playSelectionValue`;
`operator<(AnalysisData, AnalysisData)` sorts by descending `playSelectionValue`; the sorted index becomes `order`.
Tests and the local probe must prove that changing lambda can change `playSelectionValue`/`order` and the selected
move. Calibration remains deterministic after the opening so strength is not confounded with another sampling rule.

### Fail-closed validation

Before a request is sent, reject:

- `humansl_search` without a HumanSL profile;
- `humansl_search` without an enabled HumanSL final-selection/exploration recipe;
- a requested main model unsupported by the chosen backend;
- a HumanSL mechanism when the backend has no human model;
- a response whose selected-model attestation differs from the request;
- malformed HumanSL response data needed by the mechanism.

The product path reports ladder unavailable. Calibration records an inconclusive engine/configuration outcome rather
than substituting a default-model move.

## Data Flow

1. A product rung or experimental player creates a `LadderRung` with explicit `net`, mechanism, profile, visits, and
   HumanSL parameters.
2. The ladder validates the semantic combination and produces a canonical strength specification.
3. The runtime engine or calibration adapter translates the specification for its backend.
4. The HTTP wrapper routes to b18 or b28, removes `overrideSettings.model`, and forwards only native KataGo settings
   to the selected process.
5. KataGo's loaded humanv0 model supplies `humanPolicy`; the nonzero PIKL recipe changes search exploration/final
   ordering.
6. The wrapper attests the executed model; KaTrain verifies it before `pick_ladder_move` selects the certified result.

## Testing

### Unit and contract tests

- A `humansl_search` rung emits b18 as its requested main model and the full nonzero baseline recipe.
- Invalid profile/recipe combinations fail before I/O.
- Runtime and calibration derive visits, model selector, and native overrides from the same canonical helper.
- HTTP queries put the selector at `overrideSettings.model`; the wrapper strips it before KataGo stdin.
- Native subprocess requests reject all explicit main-model identities rather than guessing from path/command text.
- Health capabilities and analysis-response attestation must agree with the requested model and HumanSL requirement.
- Changing PIKL lambda changes reported `playSelectionValue`/`order` and, on a locked fixture position, selected move.
- Existing native HumanSL and b28 rungs retain their current behavior.

### Local semantic probes

On one fixed asymmetric position, record complete query fingerprints for:

1. b18 without HumanSL;
2. b18 plus a rank profile with zero blend weights;
3. b18 plus the same profile and baseline PIKL recipe;
4. b28 without HumanSL.

The probe must show that (1) and (2) do not gain HumanSL influence, (3) changes HumanSL-sensitive selection values or
ordering relative to (1), and (4) is attested as a different main model. Each response's attestation must match the
requested alias and the health capability snapshot. Failure of any identity check blocks self-play.

## Experiment Redesign

Old `@1` weighted-humanPolicy and `@1s` argmax data remain valid. All old `rank_Xd@V` data for `V > 1` remains only as
a b28-search control and cannot support HumanSL-search conclusions.

Valid PIKL self-play starts at the documented practical range rather than the old 1/4/7/16 grid:

- visits: 40, 80, 160, 320, optionally 640;
- fixed b18 main model, profile, recipe, and lambda while measuring visit monotonicity;
- paired colors and a fixed randomized-opening suite;
- 20 conclusive games may be used only as a screening batch, never as a final monotonicity/crossing claim;
- final seam decisions use a predeclared fixed sample of 40 conclusive games and a 95% Wilson interval: lower bound
  above 50% means A is stronger, upper bound below 50% means A is weaker, otherwise the seam is inconclusive;
- experiment 4's candidate crossing receives 80 conclusive games under the same rule before “reaches/exceeds” is
  claimed; screening results select a candidate but are not reported as confirmatory inference;
- player fingerprints persist requested and wrapper-attested main-model alias/path/hash, KataGo version, auxiliary
  human-model path/hash, profile, all effective overrides, selection algorithm/version, visits, noise and symmetry
  settings, opening-suite ID/seed, and wrapper capability snapshot.

Every JSONL record carries a fingerprint digest. Resume validates the file header and every existing record against
the current digest; a mismatch aborts instead of mixing configurations.

Experiment 3 compares lower-rank b18+PIKL search against the next rank's humanPolicy argmax baseline. If 40 visits is
already decisive, it establishes only an upper bound; lambda is then varied in a separate experiment rather than using
unsupported tiny visit counts.

Experiment 4 compares rank_9d b18+PIKL at 40/80/160/320/640 against b28@20. Not crossing 50% is a valid finding about
the style-constrained ceiling.

## Delivery Order

1. Add failing semantic/configuration tests.
2. Implement canonical strength specification and validation.
3. Implement backend-aware HTTP routing and native-backend rejection.
4. Update calibration to consume the same specification and persist fingerprints.
5. Pass unit/contract tests and local four-way semantic probes.
6. Mark the repaired mechanism ready in `EXPERIMENTS.md`.
7. Run the redesigned experiments; never append new games to old mislabeled result files.
