# HumanSL Search Semantics Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `humansl_search` execute attested b18 search with humanv0 PIKL influence, fail closed on routing/configuration drift, and rerun only semantically valid experiments.

**Architecture:** `katrain.core.ladder` produces one validated, transport-neutral strength specification. The HTTP boundary alone injects `overrideSettings.model`; the local realtime wrapper strips it before KataGo stdin and returns executed-model metadata. Runtime and calibration verify that metadata, while the self-play harness fingerprints the complete executed configuration and refuses mixed resumes.

**Tech Stack:** Python 3, dataclasses, pytest/pytest-asyncio, FastAPI/httpx, KataGo Analysis Engine, JSONL experiment checkpoints.

**Design:** `docs/superpowers/specs/2026-07-21-humansl-search-semantics-design.md`

---

## File Map

### KaTrain repository

- `katrain/core/ladder.py`: canonical `LadderStrengthSpec`, PIKL baseline, semantic validation, analysis attestation.
- `katrain/core/engine.py`: backend-aware final-wire model routing; native subprocess rejection.
- `katrain/core/ai.py`: request the canonical spec and fail closed on response attestation mismatch.
- `katrain/core/ladder_calibration.py`: accept a validated initial history for paired opening-suite games.
- `superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py`: build the HTTP query from the same spec and verify attestation.
- `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_calibration.py`: pass immutable capabilities through live calibration.
- `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_smoke.py`: pass immutable capabilities through smoke games.
- `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`: valid b18+PIKL players, capability preflight, immutable fingerprints, Wilson decisions, fresh result namespace.
- `superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py`: locked four-way local semantic probe.
- `tests/core/test_ladder.py`: strength-spec and semantic-validation tests.
- `tests/core/test_ladder_strategy.py`: runtime backend/attestation fail-closed tests.
- `tests/test_http_engine.py`: HTTP-only selector injection tests.
- `tests/platforms/test_ladder_query_contract.py`: runtime/harness canonical-spec parity.
- `tests/platforms/test_golaxy_calibration_opponent.py`: adapter attestation behavior.
- `tests/platforms/test_humansl_selfplay.py`: player parsing, fingerprints, resume protection, Wilson rules.
- `superpowers/tracks/golaxy-ai-ladder-parity/calibration/opening_suite_v1.json`: fixed legal randomized openings.

### Local KataGo realtime wrapper repository

- `/Users/fan/Repositories/KataGo/python/realtime_api/main.py`: health capability identities and per-response route attestation.
- `/Users/fan/Repositories/KataGo/tests/test_realtime_api.py`: selector stripping, health identity, and response-attestation tests.

---

## Chunk 0: Preserve Existing Work

### Task 0: Inventory and isolate pre-existing changes

**Files:**
- Inspect: every file in the File Map
- Create: `/tmp/humansl-search-preexisting.patch` (diagnostic backup only; never commit)

- [ ] **Step 1: Record both repository states**

Run `git status --short`, `git diff --stat`, and focused `git diff -- <each planned path>` in both repositories. Record
which hunks and untracked files predate this plan. In particular, preserve existing edits in `ladder.py`, ladder tests,
`run_selfplay.py`, and `EXPERIMENTS.md`.

- [ ] **Step 2: Save a diagnostic patch outside both repositories**

Use `git diff > /tmp/humansl-search-preexisting.patch` for tracked changes and record hashes/copies of the two relevant
untracked text files. This is a recovery aid, not permission to reset or overwrite anything.

- [ ] **Step 3: Establish staging discipline**

Before every commit, inspect `git diff --cached` and use patch-level staging (`git add -p`) for any file that contained
pre-existing hunks. Never run whole-file `git add` on `run_selfplay.py` or `EXPERIMENTS.md`; because they are untracked,
defer committing them until their entire contents have been reviewed as in-scope. Do not use reset/checkout to clean
the worktree.

---

## Chunk 1: Executed Model Contract

### Task 1: Add wrapper route attestation and capability identities

**Files:**
- Modify: `/Users/fan/Repositories/KataGo/tests/test_realtime_api.py`
- Modify: `/Users/fan/Repositories/KataGo/python/realtime_api/main.py`

- [ ] **Step 1: Write failing response-attestation tests**

Extend `test_analyze_routes_to_requested_model` and `test_analyze_defaults_to_default_model` to require reserved metadata without changing KataGo's own fields:

```python
data = resp.json()
assert data["_wrapper"]["selected_model"] == "b18"
assert data["_wrapper"]["model_sha256"] == "b18-sha"
assert data["_wrapper"]["human_model_sha256"] == "human-sha"
assert data["_wrapper"]["katago_version"].startswith("KataGo v")
```

Configure the mocked `app_config.katago.models` with b18/b28 paths and hashes. Also assert the dict forwarded to
`wrapper.query` contains no `_wrapper` field and no `overrideSettings.model`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
cd /Users/fan/Repositories/KataGo
pytest -q tests/test_realtime_api.py -k 'routes_to_requested_model or defaults_to_default_model'
```

Expected: FAIL because `_wrapper` is absent.

- [ ] **Step 3: Write failing health identity test**

Require each `/health` model record to contain configured main/human paths and hashes plus a schema version:

```python
assert data["capability_schema"] == 1
assert data["models"]["b18"]["sha256"] == "b18-sha"
assert data["models"]["b18"]["human_model_sha256"] == "human-sha"
assert data["katago_version"].startswith("KataGo v")
```

- [ ] **Step 4: Run the health test and verify RED**

Run:

```bash
pytest -q tests/test_realtime_api.py -k health_reports_all_models
```

Expected: FAIL on missing capability fields.

- [ ] **Step 5: Write and run failing artifact-verification tests**

Before changing `_ensure_single_model`, add parametrized tests for a main-model checksum mismatch and a human-model
checksum mismatch with `auto_download=False`, plus a failed post-download verification with `auto_download=True`.
Assert startup raises and no wrapper/process is registered. Run them and confirm RED because current code can log and
continue after a mismatch.

- [ ] **Step 6: Implement the minimal wrapper metadata helper**

In `main.py`, resolve the selected `NamedModelConfig` once and build:

```python
def _model_identity(name: str) -> dict:
    model = next(m for m in app_config.katago.models if m.name == name)
    return {
        "selected_model": name,
        "model_path": model.path,
        "model_sha256": model.sha256,
        "human_model_path": model.human_model.path if model.human_model else None,
        "human_model_sha256": model.human_model.sha256 if model.human_model else None,
        "katago_version": katago_version,
    }
```

After `result = await wrapper.query(query)`, copy the result and attach `result["_wrapper"] = _model_identity(name)`.
At lifespan startup, run the configured binary's `version` command once, capture its complete normalized output, and
cache it as `katago_version`; failure to identify the binary makes health unavailable. Compute/cache the actual SHA-256
of every main and human model after download/readiness checks. Any configured-vs-actual mismatch is a startup failure,
including `auto_download=False` (replace the current log-and-continue behavior). Attest actual hashes, not unchecked
configuration strings. Expose the same version and verified identities from `/health` with `capability_schema: 1`.
Reject missing/empty model paths or expected hashes in the new multi-model schema. Preserve legacy one-model
configuration by using the normalized model list, but mark absent legacy hashes explicitly so certified routes cannot
accept them.

- [ ] **Step 7: Run wrapper tests and verify GREEN**

Run:

```bash
pytest -q tests/test_realtime_api.py tests/test_realtime_api_multitenancy.py tests/test_config.py
```

Expected: PASS.

- [ ] **Step 8: Commit the wrapper contract in the KataGo repository**

```bash
git -C /Users/fan/Repositories/KataGo add -p python/realtime_api/main.py tests/test_realtime_api.py
git -C /Users/fan/Repositories/KataGo commit -m "attest realtime API model routing"
```

### Task 2: Define the canonical HumanSL strength specification

**Files:**
- Modify: `tests/core/test_ladder.py`
- Modify: `katrain/core/ladder.py`

- [ ] **Step 1: Write failing canonical-spec tests**

Add tests using a minimal experimental rung:

```python
def _humansl_search_rung(**overrides):
    values = dict(
        rung=0, golaxy_level_name=None, golaxy_api_level=None, display_elo=None,
        ref_rank="rank_9d", rank_name="rank_9d", net="b18",
        mechanism="humansl_search", human_sl_profile="rank_9d", max_visits=40,
        human_sl_params=dict(HUMANSL_PIKL_BASELINE), backend_hint="server",
        root_policy_temperature=1.0,
    )
    values.update(overrides)
    return LadderRung(**values)

def test_humansl_search_strength_spec_is_b18_plus_humanv0():
    spec = rung_strength_spec(_humansl_search_rung())
    assert spec.main_model == "b18"
    assert spec.human_model == "humanv0"
    assert spec.visits == 40
    assert spec.override_settings["humanSLChosenMoveProp"] == 1.0
    assert "model" not in spec.override_settings
```

Add failure cases for missing profile, empty/zero blend recipe, humanv0 incorrectly used as main search net, and
HumanSL parameters on `net_search`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/core/test_ladder.py -k 'strength_spec or invalid_humansl_search'
```

Expected: collection/import failure for missing spec/constants or assertion failure.

- [ ] **Step 3: Implement `LadderStrengthSpec` and validation**

Add an immutable dataclass:

```python
@dataclass(frozen=True)
class LadderStrengthSpec:
    visits: int
    main_model: Optional[str]
    human_model: Optional[str]
    override_settings: Dict
```

Define `HUMANSL_PIKL_BASELINE` exactly as approved in the design. Implement `rung_strength_spec(rung)` with explicit
mechanism mapping:

- `humansl`: `main_model=None`, `human_model="humanv0"`;
- `net_search`: `main_model=rung.net`, `human_model=None`;
- `humansl_search`: `main_model=rung.net`, `human_model="humanv0"` and validated nonzero PIKL recipe.

Keep `ladder_override_settings` and `rung_engine_params` as compatibility projections of the canonical spec. Add
`main_model` and `human_model` keys to `rung_engine_params` without putting `model` into `extra_settings`.

- [ ] **Step 4: Run focused and full ladder tests**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/core/test_ladder.py
```

Expected: PASS.

- [ ] **Step 5: Commit the canonical specification**

```bash
git add -p katrain/core/ladder.py tests/core/test_ladder.py
git commit -m "define HumanSL search strength spec"
```

---

## Chunk 2: Backend-Aware Runtime and Calibration

### Task 3: Inject model routing only for the HTTP backend

**Files:**
- Modify: `tests/test_http_engine.py`
- Modify: `katrain/core/engine.py`

- [ ] **Step 1: Write failing backend-routing tests**

Test a small method on real engine classes:

```python
assert http_engine.ladder_extra_settings({"humanSLProfile": "rank_9d"}, "b18") == {
    "humanSLProfile": "rank_9d", "model": "b18"
}
with pytest.raises(ValueError, match="per-query model"):
    native_engine.ladder_extra_settings({}, "b18")
assert native_engine.ladder_extra_settings({"humanSLProfile": "rank_5d"}, None) == {
    "humanSLProfile": "rank_5d"
}
```

Also build a native query and assert `model` is absent from stdin-bound `overrideSettings` for every accepted case.
Directly call `KataGoEngine.build_analysis_query(..., extra_settings={"model": "b18"})` and require it to raise before
constructing an stdin-bound query, even when the caller bypasses `ladder_extra_settings`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/test_http_engine.py -k ladder
```

Expected: FAIL because `ladder_extra_settings` does not exist.

- [ ] **Step 3: Write failing HTTP health-capability tests**

Extend engine-creation tests with capability-schema fixtures. Require `create_engine` to call `raise_for_status`, parse
and retain the capability snapshot, derive HumanSL support per model, and reject missing aliases, stopped requested
models, empty paths/hashes, or a missing human model. Verify legacy top-level `has_human_model` is not accepted for a
certified multi-model route.

- [ ] **Step 4: Run all routing/capability tests and verify RED**

Run `KIVY_NO_ARGS=1 pytest -q tests/test_http_engine.py -k 'health or capability or ladder'`.

- [ ] **Step 5: Implement backend routing and retained immutable capabilities**

Add a copy-only base implementation that rejects non-`None` model identity. Override it on `KataGoHttpEngine` to
validate a nonempty alias against retained health capabilities and add `model` to a copied settings dict. Override or
guard `KataGoEngine.build_analysis_query` itself so any `extra_settings.model` raises at the final native query
boundary. Do not mutate canonical spec dictionaries.

Store a normalized deep copy on `KataGoHttpEngine` (including schema, version, aliases, paths, hashes, running and
HumanSL state). Expose a pure `require_ladder_capability(main_model, human_required)` method used before I/O. Do not
silently fall back to a local engine for a certified explicit-model rung after the HTTP engine was requested but lacks
the capability.

- [ ] **Step 6: Run engine tests and verify GREEN**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/test_http_engine.py tests/test_ai.py
```

Expected: PASS.

- [ ] **Step 7: Commit backend-aware routing**

```bash
git add -p katrain/core/engine.py tests/test_http_engine.py
git commit -m "route ladder models at HTTP boundary"
```

### Task 4: Make LadderStrategy verify executed identity

**Files:**
- Modify: `tests/core/test_ladder_strategy.py`
- Modify: `katrain/core/ai.py`
- Modify: `katrain/core/ladder.py`

- [ ] **Step 1: Write failing runtime tests**

Upgrade `FakeEngine` with `ladder_extra_settings`. For b28 search responses include:

```python
"_wrapper": {
    "selected_model": "b28",
    "model_path": "/models/b28.bin.gz",
    "model_sha256": "b28-sha",
    "human_model_path": "/models/humanv0.bin.gz",
    "human_model_sha256": "human-sha",
}
```

Add tests that:

- b28 rung sends `model=b28` through an HTTP-capable fake;
- b28 rung rejects a b18 attestation;
- b28 rung rejects missing attestation;
- a HumanSL-search fixture rejects absent human-model attestation;
- native HumanSL @1 remains valid without route attestation;
- an engine that rejects explicit model routing becomes `LadderUnavailable` before I/O.
- retained health says b18 but the response attests b28, a different path/hash, a different HumanSL hash, or a
  different KataGo version: every mismatch fails closed.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/core/test_ladder_strategy.py
```

Expected: new mismatch/missing-attestation tests fail.

- [ ] **Step 3: Implement pure attestation validation**

In `ladder.py`, add `validate_analysis_attestation(analysis, spec)` that validates `_wrapper.selected_model`, main
identity fields, and human identity fields when the spec requires them. Raise `LadderMoveError` with diagnostic text.

- [ ] **Step 4: Wire LadderStrategy to backend routing and validation**

Before request, call `engine.require_ladder_capability(...)`, then
`engine.ladder_extra_settings(params["extra_settings"], params["main_model"])`, converting rejection to
`LadderUnavailable`. After a complete response and before move selection, validate the attestation against both the
requested spec and the engine's retained startup capability snapshot.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/core/test_ladder_strategy.py tests/core/test_ladder.py
```

Expected: PASS.

- [ ] **Step 6: Commit runtime fail-closed behavior**

```bash
git add -p katrain/core/ai.py katrain/core/ladder.py tests/core/test_ladder_strategy.py
git commit -m "verify ladder model execution"
```

### Task 5: Give calibration the same wire contract

**Files:**
- Modify: `tests/platforms/test_ladder_query_contract.py`
- Modify: `tests/platforms/test_golaxy_calibration_opponent.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_calibration.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_smoke.py`

- [ ] **Step 1: Write failing contract tests**

Change the contract to compare:

- canonical visits and native settings exactly;
- HTTP wire settings exactly after `model` is injected on both paths;
- explicit model identity separately.

Assert `overrideSettings.model == "b28"` for a Band B rung and that the canonical native overrides remain model-free.
Add adapter tests for missing/mismatched `_wrapper.selected_model` returning `"unavailable"`. Pass a startup health
snapshot fixture to `our_move`; also reject path/hash/HumanSL hash/KataGo-version differences between response and that
snapshot.

Add referee tests requiring `adjudicate` to send `overrideSettings.model="b28"`, validate the complete b28 response
identity against startup health, and return `(None, False)` for missing/mismatched attestation. Import `run_calibration`
and `run_smoke` and assert each fetches health once and passes the same immutable snapshot into all move/referee calls.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/platforms/test_ladder_query_contract.py tests/platforms/test_golaxy_calibration_opponent.py
```

Expected: failures because the harness omits routing and attestation.

- [ ] **Step 3: Implement HTTP query projection and validation**

In `build_ladder_analysis_query`, start from `rung_strength_spec`, copy native overrides, then inject
`overrideSettings.model` because this adapter is explicitly HTTP-only. In `our_move`, validate `_wrapper` before
calling `pick_ladder_move`; validate against an explicit retained capability snapshot and convert validation failure to
`"unavailable"`. Make `adjudicate` explicitly inject `overrideSettings.model="b28"` and validate its full response
identity; mismatch becomes an unsettled/inconclusive score. Update existing callers `run_calibration.py`, `run_smoke.py`,
and `run_selfplay.py` to fetch `/health` once, validate it, and pass the immutable snapshot to every
`our_move`/`adjudicate` path. Defer probe integration until Task 9 creates it. No calibration call may validate only the
requested alias or rely on the wrapper default model.

- [ ] **Step 4: Run tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit calibration parity**

```bash
git add -p superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_calibration.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_smoke.py \
  tests/platforms/test_ladder_query_contract.py tests/platforms/test_golaxy_calibration_opponent.py
git commit -m "match calibration model routing"
```

---

## Chunk 3: Safe Experiment Harness and Semantic Proof

### Task 6: Replace mislabeled players with valid b18+PIKL players

**Files:**
- Create: `tests/platforms/test_humansl_selfplay.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`

- [ ] **Step 1: Write failing player-construction tests**

Import the operator script as the existing query-contract test does. Assert:

```python
label, rung, selection = make_player("rank_9d@40")
assert rung.net == "b18"
assert rung.mechanism == "humansl_search"
assert rung.human_sl_params == HUMANSL_PIKL_BASELINE
assert selection == "search"
```

Keep `rank_9d@1` weighted, `rank_9d@1s` argmax, and `b28@20` pure search. Reject HumanSL-search visits 2–39 with a
message explaining the supported minimum.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/platforms/test_humansl_selfplay.py -k player
```

Expected: b18/recipe/minimum assertions fail.

- [ ] **Step 3: Implement valid player construction**

Use `net="b18"` and a fresh copy of `HUMANSL_PIKL_BASELINE` for `rank_*@V`, `V >= 40`. Rewrite the module docstring so
no current path describes these players as default b28.

- [ ] **Step 4: Run player tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 7: Add capability preflight and immutable fingerprints

**Files:**
- Modify: `tests/platforms/test_humansl_selfplay.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`

- [ ] **Step 1: Write failing capability/fingerprint tests**

Test pure helpers with a health fixture. Require:

- requested aliases exist, run, and have required human model;
- fingerprint contains capability schema, model/human hashes, effective overrides, visits, selection algorithm version,
  KataGo version, wide-root noise, symmetry settings, and opening-suite identity;
- canonical JSON hashing is stable across dict insertion order;
- `_already_done`/resume rejects any header or record fingerprint mismatch before opening append mode.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/platforms/test_humansl_selfplay.py -k 'capability or fingerprint or resume'
```

Expected: missing helper failures.

- [ ] **Step 3: Implement preflight and versioned checkpoint schema**

Fetch `/health` once at startup. Build a canonical SHA-256 digest for each matchup. Write a first JSONL header record:

```json
{"record_type":"header","schema":2,"fingerprint":"...","configuration":{...}}
```

Every game record repeats the digest and stores the actual attestation returned for every A/B move (ply plus complete
reserved identity object); every attestation is compared to the startup snapshot before the move is accepted. Resume
validates all records and the recorded attestations. Use a new default directory such as
`results/selfplay_v2_pikl`; never append to the old `results/selfplay` files.

- [ ] **Step 4: Run tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 8: Add a deterministic paired opening suite and Wilson decisions

**Files:**
- Modify: `tests/platforms/test_humansl_selfplay.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`
- Modify: `katrain/core/ladder_calibration.py`
- Modify: `tests/core/test_ladder_calibration.py`
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/opening_suite_v1.json`

- [ ] **Step 1: Write all failing statistics, opening, scheduling, and game-loop tests**

Test `wilson_interval(wins, n)` against locked numerical cases and `classify_seam`:

```python
assert classify_seam(30, 40) == "a_stronger"
assert classify_seam(20, 40) == "inconclusive"
assert classify_seam(10, 40) == "a_weaker"
```

Define inference in complete color pairs, not individual games. Require ordinary seams to refuse confirmatory
classification below 20 fully conclusive pairs (40 games), experiment-4 crossings below 40 complete pairs (80 games),
and screening to stop at exactly 10 complete pairs. An opening pair with either inconclusive game is retained for
diagnostics but contributes zero games to the decision sample.

Add game-loop tests proving a supplied legal `initial_history` is copied (not mutated), determines the correct side to
move, is included in adjudication, and counts only newly played moves against the move cap.

Add failing loader/scheduler/resume tests for suite checksum, coordinate bounds, actual board legality, uniqueness,
pair/color ordering, interrupted-pair completion, incomplete-pair exclusion, maximum-attempt termination, and strict
screen-vs-confirm checkpoint isolation.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/platforms/test_humansl_selfplay.py tests/core/test_ladder_calibration.py \
  -k 'wilson or classify or opening or pair or initial_history or phase or max_attempt'
```

Expected: missing helper/signature failures. Do not create the suite or alter production code until every intended
behavior has a correctly failing test.

- [ ] **Step 3: Create and validate the fixed opening suite**

Create at least 20 distinct legal 19x19 opening prefixes, generated once with a documented seed and stored as explicit
Golaxy-wire move arrays. Add a loader that validates coordinate bounds, duplicate occupancy/basic legality through the
existing board utilities, uniqueness, suite ID, seed, and checksum. Do not generate a new suite during a run.

Schedule each opening as an inseparable color pair: A is Black once and White once on the same prefix. Checkpoint keys
include phase (`screen` or `confirm`), opening ID, pair-attempt index, and color index. An interrupted run resumes the
missing half of the pair without changing scheduling. A pair contributes exactly two games only when both results are
conclusive; otherwise neither result enters wins/n. Continue with fresh predeclared pair attempts until the exact target
pair count or maximum attempt count is reached.

- [ ] **Step 4: Extend the pure game loop**

Add optional `initial_history` to `play_one_game`, copying it and deriving `to_play` from its length. Keep the default
empty list behavior unchanged for Golaxy calibration. Ensure outcome `num_moves` remains total history length and the
loop permits `move_cap - len(initial_history)` new moves.

- [ ] **Step 5: Implement decision helpers and explicit targets**

Use the 95% Wilson score interval with `z=1.959963984540054`. Store the interval and classification in summaries. Make
the CLI target **fully conclusive pairs**, not attempts or individual games, and derive the exact decision sample as
twice that value. Continue through predeclared opening pairs until the target is met, subject to a separate
maximum-pair-attempt guard.

- [ ] **Step 6: Run the full harness/game-loop tests**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/platforms/test_humansl_selfplay.py tests/core/test_ladder_calibration.py
```

Expected: PASS.

- [ ] **Step 7: Commit the safe harness**

```bash
git add -p katrain/core/ladder_calibration.py tests/core/test_ladder_calibration.py \
  tests/platforms/test_humansl_selfplay.py
# run_selfplay.py is pre-existing and untracked: review its complete diff/content before adding it intentionally
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/opening_suite_v1.json
git commit -m "make HumanSL selfplay reproducible"
```

### Task 9: Add and pass the four-way semantic probe

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py`
- Create: `tests/platforms/test_humansl_probe.py`

- [ ] **Step 1: Write failing probe-construction tests**

Test that the script builds four requests on one locked asymmetric history:

- b18 base;
- b18 plus profile with all blend weights zero;
- b18 plus profile and baseline PIKL;
- b28 base.

Include two nonzero PIKL lambda values on the same b18/profile request and assert the fixture expects a different
selected move, different `playSelectionValue`, and different order.

Assert exact requested aliases/overrides and response-attestation validation.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/platforms/test_humansl_probe.py
```

Expected: import failure because the probe does not exist.

- [ ] **Step 3: Implement the probe**

Use a one-off discovery run to find a stable asymmetric fixture where two predeclared lambdas change the selected
move; discard the discovery code and lock the history/lambdas in the tested probe. Write results to a timestamped JSON
file under `calibration/results/semantic_probe/`. Include request fingerprints,
health capabilities, selected moves, `playSelectionValue`, order, root info, and attestation. Exit nonzero unless:

- every response attests the requested main model;
- b18 profile-only is selection-equivalent to b18 base for the locked position;
- changing PIKL lambda changes `playSelectionValue`, `order`, and the final `order=0` move on the locked fixture;
- b18 and b28 fingerprints differ.

- [ ] **Step 4: Run probe unit tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Restart the local wrapper with the attestation change**

Use the repository's normal local launch command/config. Verify `/health` reports schema 1, b18/b28 running, both
human models present, and configured hashes. Do not access the remote server.

- [ ] **Step 6: Run the real local semantic probe**

Run:

```bash
KIVY_NO_ARGS=1 uv run python \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py \
  --base-url http://127.0.0.1:8000
```

Expected: exit 0 and a result file demonstrating attested b18/b28 routing plus HumanSL-sensitive ordering.

- [ ] **Step 7: Commit the semantic probe**

```bash
git add -p superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py \
  tests/platforms/test_humansl_probe.py
git commit -m "add HumanSL search semantic probe"
```

---

## Chunk 4: Verification and Valid Experiment Restart

### Task 10: Run regression verification and update the experiment ledger

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Run focused regression suite**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q \
  tests/core/test_ladder.py \
  tests/core/test_ladder_strategy.py \
  tests/test_http_engine.py \
  tests/platforms/test_ladder_query_contract.py \
  tests/platforms/test_golaxy_calibration_opponent.py \
  tests/platforms/test_humansl_selfplay.py \
  tests/platforms/test_humansl_probe.py
```

Expected: PASS.

- [ ] **Step 2: Run the broader ladder/platform suite**

Run:

```bash
KIVY_NO_ARGS=1 pytest -q tests/core tests/platforms
```

Expected: PASS, or document only pre-existing unrelated failures with evidence.

- [ ] **Step 3: Update the ledger with implementation/probe evidence**

Record wrapper/KaTrain commit IDs, capability hashes, probe result path, and the new result namespace. Mark the
`humansl_search` semantic repair complete only after the real probe passes. Keep old experiments explicitly invalid for
HumanSL claims.

- [ ] **Step 4: Commit verified documentation**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md
git commit -m "document verified HumanSL search"
```

### Task 11: Start fresh screening and confirmatory experiments

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl/*`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Predeclare and run 10-complete-pair screening batches**

Start with the redesigned seams, never the old files:

```bash
KIVY_NO_ARGS=1 uv run python \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py \
  --base-url http://127.0.0.1:8000 \
  --phase screen \
  --matchups 'rank_5d@80:rank_5d@40:10,rank_7d@80:rank_7d@40:10,rank_9d@80:rank_9d@40:10,rank_9d@40:b28@20:10'
```

The third matchup field is renamed/documented as target complete pairs, not attempted games.

Expected: each matchup stops at exactly 10 fully conclusive pairs (20 decision games); incomplete attempts are excluded.
All checkpoint headers/records share verified digests, complete per-move attestations, and paired openings. Treat
results as screening only.

- [ ] **Step 2: Select confirmatory seams without claiming screening significance**

Use screening only to choose which visits require fixed confirmatory samples. Predeclare the chosen matchups and target
conclusive counts in `EXPERIMENTS.md` before continuing. Confirmation uses a new `phase=confirm` fingerprint and new
checkpoint filenames; screening records are never loaded or counted as confirmation.

- [ ] **Step 3: Complete fixed confirmatory samples**

Run fresh confirmation checkpoints to exactly 20 fully conclusive pairs (40 decision games) for ordinary seams and 40
fully conclusive pairs (80 decision games) for the experiment-4 candidate. The harness continues pair attempts until
the complete-pair target or predeclared maximum guard is reached. If the fixed sample is inconclusive, report
inconclusive; do not repeatedly extend until significance.

- [ ] **Step 4: Record results and raw-data fingerprints**

Update `EXPERIMENTS.md` with Wilson intervals, decision classifications, inconclusive counts, and direct links to the
fresh files. Do not overwrite the semantic-audit correction.

### Task 12: Final review and handoff

**Files:**
- Review all files listed above.

- [ ] **Step 1: Run `git diff --check` in both repositories**

```bash
git diff --check
git -C /Users/fan/Repositories/KataGo diff --check
```

- [ ] **Step 2: Use superpowers:requesting-code-review**

Request review of the full diff with emphasis on transport boundary, fail-closed behavior, fingerprint resume safety,
and whether test doubles can accidentally bypass attestation.

- [ ] **Step 3: Address review findings one at a time with TDD**

Re-run the smallest relevant test after each change, then the focused regression suite.

- [ ] **Step 4: Use superpowers:verification-before-completion**

Run fresh final commands and report exact pass counts, local health identities, semantic-probe artifact, experiment
status, and both repository commit IDs. Do not claim experiments complete if only screening finished.
