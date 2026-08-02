# HumanSL Temperature Pilot Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add audited HumanSL policy-temperature sampling and complete the frozen 180-game internal pilot for the future 41-tier AI ladder.

**Architecture:** Keep the production ladder unchanged. Put pure temperature math in `katrain.core.ladder`, extend the existing self-play path only behind explicit `@1tT` player identities, and isolate manifest/draw/classification rules in a protocol module plus a narrow serial runner. Commit implementation first, then generate a manifest bound to that implementation commit before live play.

**Tech Stack:** Python 3.11+, pytest/pytest-asyncio, existing KataGo HTTP wrapper, append-only JSONL checkpoints.

**Spec:** `docs/superpowers/specs/2026-08-03-humansl-temperature-ladder-calibration-design.md`

---

## Chunk 1: Temperature foundation and pilot execution

### File responsibilities

- `katrain/core/ladder.py`: stable temperature transform, inverse-CDF picker, and local-only rung temperature.
- `calibration/run_selfplay.py`: narrow `@1tT` parser, temperature-selection call, trace pass-through, and exact opening allocation hook; all pilot-specific math/validation stays out of this already-large file.
- `calibration/temperature_pilot.py`: manifest, stateless draw, policy digest, trace validation, and gate classification.
- `calibration/run_temperature_pilot.py`: create/check/dry-run/run/summarize CLI.
- `tests/core/test_ladder.py`: pure math and legacy compatibility.
- `tests/platforms/test_humansl_selfplay.py`: only parser/request compatibility integration.
- `tests/platforms/test_temperature_pilot.py`: draw/digest/trace, self-play pilot hooks, immutable protocol, and orchestration.

Paths beginning with `calibration/` below mean `superpowers/tracks/golaxy-ai-ladder-parity/calibration/`.

### Task 1: Core HumanSL temperature math

**Files:**
- Modify: `katrain/core/ladder.py`
- Modify: `tests/core/test_ladder.py`

- [ ] **Step 1: Write failing transformation tests**

Cover `T=1`, flatten/sharpen entropy, non-mutation, negative/zero exclusion, all-nonpositive rejection, wrong vector length, nonfinite values, temperature bool/zero/range errors, pass, exact inverse-CDF edge draws, and draw rejection for boolean, negative, non-integer, and values above `2**64-1`. Freeze `0/A19`, `18/T19`, `342/A1`, `360/T1`, `361/pass`. Add a regression that the existing 37 production rungs and legacy weighted picker behavior are unchanged.

```python
def test_temperature_distribution_flattens_and_sharpens():
    policy = [0.7, 0.2, 0.1]
    cold = temperature_policy_distribution(policy, 0.5)
    native = temperature_policy_distribution(policy, 1.0)
    hot = temperature_policy_distribution(policy, 2.0)
    assert native == pytest.approx(policy)
    assert cold[0] > native[0] > hot[0]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/core/test_ladder.py -q`  
Expected: FAIL because temperature helpers do not exist.

- [ ] **Step 3: Implement the pure core API**

Add `TEMPERATURE_MIN/MAX`, `temperature_policy_distribution`, `policy_index_to_gtp`, and `pick_temperature_policy`. Use max-relative log weights and one unsigned 64-bit inverse-CDF draw. Return selected move plus policy index. Add `human_policy_temperature: Optional[float] = None` to `LadderRung`, validate it, and never project it into engine overrides. Preserve the legacy picker unchanged.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/core/test_ladder.py tests/core/test_ladder_strategy.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add katrain/core/ladder.py tests/core/test_ladder.py
git commit -m "add HumanSL temperature sampling"
```

### Task 2: Pilot draw, digest, trace, manifest, and classification primitives

**Files:**
- Create: `calibration/temperature_pilot.py`
- Create: `tests/platforms/test_temperature_pilot.py`

- [ ] **Step 1: Write failing draw, digest, and trace tests**

Freeze SHA-256/u64 vectors for the exact JSON array and binary64 policy digest, including pass. Validate trace shape, recalculated draw, index bounds, and exact index/GTP mapping. Assert the pure helpers need no self-play import.

- [ ] **Step 2: Write failing manifest and classification tests**

Assert nine ordered matchups, canonical evidence identities, `phase=screen`, target 10, cap 20, first 20 no-cycle openings, exact six-file runtime set, source/base ancestry, drift rejection, self-digest, and exclusive creation. Cover every per-match category and overall pass/fail/incomplete branch, including profile aggregate ties, 7/9 versus 8/9 direction, persuasive inversion, and incomplete evidence.

- [ ] **Step 3: Run RED**

Run: `python -m pytest tests/platforms/test_temperature_pilot.py -q`  
Expected: FAIL because the protocol module does not exist.

- [ ] **Step 4: Implement the pure protocol module**

Keep canonical JSON, digest, draw, policy digest, trace validation, manifest, and classification in focused functions. Restrict file I/O to manifest/checkpoint validation. Implement the schema-1 creation/check API and exact paths from the spec.

- [ ] **Step 5: Run GREEN and commit**

Run: `python -m pytest tests/platforms/test_temperature_pilot.py -q`  
Expected: PASS.

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot.py tests/platforms/test_temperature_pilot.py
git commit -m "add HumanSL temperature pilot protocol"
```

### Task 3: Temperature player grammar and audited self-play hooks

**Files:**
- Modify: `calibration/run_selfplay.py`
- Modify: `tests/platforms/test_humansl_selfplay.py`
- Modify: `tests/platforms/test_temperature_pilot.py`

- [ ] **Step 1: Write failing canonical parser/identity tests**

Test `t2.0 -> t2`, `t0.40 -> t0.4`, leading-zero normalization, distinct `t1`, range endpoints, and rejection of signs, exponent, whitespace, malformed decimal, suffix combinations, search visits, and pure-net temperature. Freeze the full evidence identity: canonical temperature string, `temperature-inverse-cdf-v1`, profile, and distinct explicit `t1`. Assert no engine override contains local temperature.

- [ ] **Step 2: Run parser RED**

Run: `python -m pytest tests/platforms/test_humansl_selfplay.py -q`  
Expected: FAIL on unsupported temperature syntax.

- [ ] **Step 3: Implement the narrow parser hook**

Use `Decimal` for labels, store float temperature in `LadderRung`, return `temperature_weighted`, and delegate evidence identity to `temperature_pilot.py`. Preserve legacy fingerprints.

- [ ] **Step 4: Write failing async selection/trace integration tests**

In `test_temperature_pilot.py`, mock `/analyze` and assert the request stays native one-visit HumanSL; a complete selection context is mandatory; a known stateless draw selects the expected move; trace fields are complete; malformed context fails closed; legacy weighted/argmax paths remain unchanged.

- [ ] **Step 5: Implement minimal selection/trace pass-through**

Pass optional context and trace list through existing closures. Delegate draw/digest/trace construction to `temperature_pilot.py` and move choice to the core picker. Do not add opening-allocation behavior in this task; Task 4 owns that hook after its allocation tests.

- [ ] **Step 6: Run GREEN and commit**

Run: `python -m pytest tests/platforms/test_humansl_selfplay.py tests/platforms/test_temperature_pilot.py -q`  
Expected: PASS.

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py tests/platforms/test_humansl_selfplay.py
git add tests/platforms/test_temperature_pilot.py
git commit -m "support audited HumanSL temperature players"
```

### Task 4: Strict serial runner

**Files:**
- Create: `calibration/run_temperature_pilot.py`
- Modify: `calibration/run_selfplay.py`
- Modify: `tests/platforms/test_temperature_pilot.py`
- Modify: `tests/platforms/test_humansl_selfplay.py`

- [ ] **Step 1: Write failing dry-run/resume/orchestration tests**

Dry-run must print nine serial matchups, 20 allocations each, checkpoint paths, and manifest digest with zero network calls. Live orchestration must stop only on operational/protocol failure or an incomplete matchup, never on an early point-estimate inversion; it must run all nine completed matchups for gate classification, never overlap matchups, resume a half pair, and summarize only validated checkpoints. Add failing tests that the launch snapshot is exclusively created once, reused byte-for-byte on resume, rejected on identity mismatch, and included by digest in all nine checkpoint configurations.

- [ ] **Step 2: Expose exact allocation through self-play**

Add a narrow optional exact-opening list and pilot context to `run_matchup`; use existing `cycle_openings=False`. Freeze allocation and manifest digest in checkpoint configuration. Preserve legacy scheduling and checkpoint semantics.

- [ ] **Step 3: Implement CLI**

Support:

```text
create-manifest --implementation-base REV --out PATH
check --manifest PATH [--results-dir PATH]
dry-run --manifest PATH --results-dir PATH
run --manifest PATH --base-url URL --results-dir PATH
summarize --manifest PATH --results-dir PATH
```

`run` validates files, creates one exclusive health launch snapshot, validates b28/humanv0, binds its digest into each checkpoint, and executes only the frozen order. It never calls Golaxy. A completed inversion is evidence, not an operational stop.

- [ ] **Step 4: Run GREEN and commit**

Run: `python -m pytest tests/platforms/test_temperature_pilot.py tests/platforms/test_humansl_selfplay.py -q`  
Expected: PASS.

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_temperature_pilot.py superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py tests/platforms/test_temperature_pilot.py tests/platforms/test_humansl_selfplay.py
git commit -m "add serial HumanSL temperature pilot runner"
```

### Task 5: Freeze manifest and preflight

**Files:**
- Create: `calibration/temperature_pilot_v1.json`

- [ ] **Step 1: Verify implementation**

Run:

```bash
python -m pytest tests/core/test_ladder.py tests/core/test_ladder_strategy.py tests/platforms/test_humansl_selfplay.py tests/platforms/test_temperature_pilot.py -q
python -m py_compile katrain/core/ladder.py superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot.py superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_temperature_pilot.py
```

Expected: all focused tests pass and all four runtime modules compile.

- [ ] **Step 2: Capture implementation-base SHA**

Run: `PILOT_IMPL_REV="$(git rev-parse HEAD)" && git show -s --format=%H "$PILOT_IMPL_REV"`  
Expected: one full 40-hex commit containing runtime changes, before the manifest exists. Keep `PILOT_IMPL_REV` in the same shell for Step 3.

- [ ] **Step 3: Create/check manifest**

```bash
PILOT_IMPL_REV="$(git rev-parse HEAD)"
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_temperature_pilot.py create-manifest --implementation-base "$PILOT_IMPL_REV" --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot_v1.json
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_temperature_pilot.py check --manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot_v1.json
```

Expected: one immutable manifest, nine matchups, 180 planned games, all hashes valid.

- [ ] **Step 4: Commit manifest and dry-run**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot_v1.json
git commit -m "freeze HumanSL temperature pilot"
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_temperature_pilot.py dry-run --manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot_v1.json --results-dir superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1
```

Expected: exact serial schedule and no network/result ledger.

### Task 6: Run and classify 180 games

**Files:**
- Create: `calibration/results/selfplay_temperature_pilot_v1/launch_snapshot.json`
- Create: nine JSONL checkpoints plus `summary.json` and `report.md` in that directory
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Verify/start authorized local engine**

Run:

```bash
curl -fsS http://127.0.0.1:8000/health | jq -e '.capability_schema==1 and .models.b28.running==true and .models.b28.model_sha256_verified==true and .models.b28.model_sha256=="798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0" and .models.b28.human_model_sha256_verified==true and .models.b28.human_model_sha256=="637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5"'
```

Expected: `true` and exit status 0. If unavailable, run the exact fallback:

```bash
(cd /Users/fan/Repositories/KataGo && env PYTHONPATH=python nohup /opt/miniconda3/envs/py311_katago/bin/python -m realtime_api.main >/private/tmp/realtime_api_temperature_pilot.log 2>&1 & echo $! >/private/tmp/realtime_api_temperature_pilot.pid)
for PILOT_READY_ATTEMPT in {1..60}; do curl -fsS http://127.0.0.1:8000/health >/dev/null && break; sleep 2; done
curl -fsS http://127.0.0.1:8000/health | jq -e '.capability_schema==1 and .models.b28.running==true and .models.b28.model_sha256_verified==true and .models.b28.model_sha256=="798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0" and .models.b28.human_model_sha256_verified==true and .models.b28.human_model_sha256=="637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5"'
```

Expected: a PID file under `/private/tmp`, bounded readiness within 120 seconds, then `true`. If readiness fails, inspect `/private/tmp/realtime_api_temperature_pilot.log` and do not start a second service or weaken preflight.

- [ ] **Step 2: Run/resume serial pilot**

```bash
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost CI=true KIVY_NO_ARGS=1 python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_temperature_pilot.py run --manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot_v1.json --base-url http://127.0.0.1:8000 --results-dir superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1
```

Expected: nine matchups execute one at a time to ten complete pairs. Rerun the exact command after recoverable interruption. Source/identity drift fails closed.

- [ ] **Step 3: Summarize and verify**

Run:

```bash
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_temperature_pilot.py summarize --manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot_v1.json --results-dir superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_temperature_pilot.py check --manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot_v1.json --results-dir superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1
python -m pytest tests/core/test_ladder.py tests/core/test_ladder_strategy.py tests/platforms/test_humansl_selfplay.py tests/platforms/test_temperature_pilot.py -q
git diff --check
shasum -a 256 superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot_v1.json superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1/launch_snapshot.json superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1/summary.json superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1/report.md superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1/*.jsonl
```

Expected: `check` reports nine complete matchups, 90 complete pairs, 180 eligible games, zero identity/trace errors, and overall `pass` or `fail`; pytest passes, diff check is silent, and SHA-256 prints one line for every frozen artifact. `incomplete` is not completion.

- [ ] **Step 4: Record and commit evidence**

Append protocol, nine scores, overall gate, identities, paths, and digests to `EXPERIMENTS.md`. `.jsonl.lock` files are runtime-only and must never be staged. First run `rg --files superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1` and verify the evidence set consists only of the launch snapshot, nine `.jsonl` checkpoints, summary, report, and optional `.jsonl.lock` files. Stage only the named evidence patterns and experiment log:

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1/launch_snapshot.json superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1/summary.json superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1/report.md superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_temperature_pilot_v1/*.jsonl superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md
git commit -m "record HumanSL temperature pilot"
```

If the gate passes, begin a separate reviewed slice for all-profile fitting and later Galaxy/kiosk integration. If it fails, diagnose; never ship guessed temperatures.
