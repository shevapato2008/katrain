# HumanSL Search Boundary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely locate and confirm the corrected HumanSL+PIKL visit boundary, beginning with four `@20` rank-transition screenings.

**Architecture:** Production and ordinary self-play keep the 40-visit floor. An explicit boundary-protocol mode permits a lower experimental floor, binds a completely frozen opening allocation and protocol version into checkpoints, and requires an attested low-visits semantic probe. Pure protocol functions classify fixed samples and create a committed selection manifest before fresh confirmation.

**Tech Stack:** Python 3.13, pytest, asyncio/httpx, strict JSON/JSONL, local KataGo HTTP wrapper.

**Design:** `superpowers/tracks/golaxy-ai-ladder-parity/humansl-search-boundary-design.md`

---

## Chunk 1: Strict `@20` launch gate

### Task 1: Explicit experimental floor and unchanged player semantics

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`
- Test: `tests/platforms/test_humansl_selfplay.py`

**API:** `make_player(spec: str, *, experimental_min_humansl_search_visits: int = 40)`; add CLI `--experimental-min-humansl-search-visits` with default `40`.

- [ ] Add tests named `test_low_humansl_search_requires_explicit_floor`, `test_experimental_floor_scope_and_validation`, and `test_low_humansl_search_preserves_canonical_query_contract`. Assert default rejection of `rank_9d@20`, explicit acceptance at floor 20, rejection at floor 21 and floor 1, and unchanged acceptance of `rank_9d@1s` and `b28@20`. Assert the accepted rung/query uses visits 20, selection `search`, requested main alias b18, requested human alias humanv0, every canonical nonzero PIKL field, and verified capability/response identity fields.
- [ ] Run `CI=true uv run pytest -q tests/platforms/test_humansl_selfplay.py -k 'low_humansl or experimental_floor'`; expect failures because the keyword/CLI does not exist.
- [ ] Implement the keyword-only floor, validate `type(value) is int and value >= 2`, and apply it only to HumanSL profiles at visits greater than one. Thread it through `run_matchup`, `main_async`, and the parser.
- [ ] Extend matchup configuration with `boundary_protocol_version`, effective floor, requested main/human aliases, verified paths/hashes/states, capability schema/version/snapshot, exact effective PIKL overrides, selection algorithm/version, visits, noise/symmetry, board/rules, and referee settings. The existing strict configuration fingerprint covers the new fields.
- [ ] Run `CI=true uv run pytest -q tests/platforms/test_humansl_selfplay.py`; expect all passing.
- [ ] Commit with explicit paths:
  `git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py tests/platforms/test_humansl_selfplay.py && git commit -m 'allow explicit low-visit HumanSL experiments'`.

### Task 2: Generate and freeze all boundary opening allocations

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/generate_boundary_openings.py`
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/opening_suite_boundary_v1.json`
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/opening_allocation_boundary_v1.json`
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/known_endpoints_exp3_v1.json`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`
- Test: `tests/platforms/test_humansl_selfplay.py`

**Frozen procedure:** `random.Random(20260722)` repeatedly samples eight distinct intersections from `range(361)`. Reject any sequence already generated or present in `opening_suite_v1.json`. Allocate in lexical transition order (`5d-6d` through `8d-9d`), then numeric visits, then attempt: screening `4 * 5 * 20` for `{2,5,10,20,30}`; confirmation `4 * 6 * 40` for `{2,5,10,20,30,40}`; total 1360 globally unique sequences. Canonical JSON uses sorted keys and compact separators for SHA-256.

- [ ] Add tests named `test_boundary_allocation_is_complete_and_disjoint`, `test_boundary_allocation_rejects_checksum_or_sequence_drift`, `test_known_endpoints_bind_all_prior_40_screens`, and `test_boundary_checkpoint_fingerprints_exact_assignment`. They must fail before assets/loaders exist; known-endpoint tests reject missing transitions and changed archive/decompressed/summary digests.
- [ ] Create the deterministic generator with `--check` (regenerate in memory and compare byte-for-byte) and `--write PATHS` modes. Generate both strict-JSON assets once; runtime generation remains forbidden.
- [ ] Implement loaders that verify suite/allocation checksums, exact 1360-key coverage, legal/distinct moves per sequence, global canonical-sequence uniqueness, and disjointness from v1.
- [ ] Build `known_endpoints_exp3_v1.json` from the four committed `@40` screening gzip artifacts, recording transition, visits40/pass classification, archive path/SHA-256, decompressed checkpoint SHA-256, and source-summary digest. Implement a strict loader that verifies every committed source before returning the manifest digest.
- [ ] Add CLI `--boundary-protocol` (only value `exp3-boundary-v1`). Infer the allocation key from phase, transition, and A-side visits; reject non-protocol matchups in this mode. Schedule only the assigned sequence list and never modulo-cycle.
- [ ] Fingerprint protocol version, phase, point-estimate pass rule, finite grid/order/stopping rule, target/cap, suite checksum, allocation digest, known-endpoints manifest/relevant source digest, exact assigned IDs and sequences. Add a resume test that changes each and expects rejection.
- [ ] Run `uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/generate_boundary_openings.py --check`; expect `1360 allocations verified`.
- [ ] Run `CI=true uv run pytest -q tests/platforms/test_humansl_selfplay.py`; expect all passing.
- [ ] Commit the generator, all three frozen assets, harness and test paths explicitly with message `freeze HumanSL boundary inputs`.

### Task 3: Attested low-visits semantic probe

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py`
- Test: `tests/platforms/test_humansl_probe.py`

**CLI:** add `--low-visits` (optional) and `--experimental-min-humansl-search-visits` (default 40); the existing locked 500-visit five-case exchange remains byte/behavior compatible when omitted.

- [ ] Add tests named `test_low_visits_probe_floor_contract`, `test_low_visits_probe_has_exact_canonical_pikl_recipe`, and `test_low_visits_probe_rejects_missing_zeroed_or_mismatched_attestation`. Cover default rejection of 20, explicit acceptance at floor20, rejection below supplied floor, rejection of floor1, every effective PIKL field, and explicit failure for a missing field or zeroed required mix.
- [ ] Run `CI=true uv run pytest -q tests/platforms/test_humansl_probe.py -k low_visits`; expect failures because the API does not exist.
- [ ] Add a separate low-visits request/result section using b18 + requested humanv0 + canonical PIKL at exact visits. Validate health and per-response main/human aliases, paths, hashes, verified states, capability version/snapshot, and returned/effective PIKL field-for-field.
- [ ] Record strict request/response/config JSON and SHA-256 values without changing the locked existing probe mode.
- [ ] Run `CI=true uv run pytest -q tests/platforms/test_humansl_probe.py`; expect all passing.
- [ ] Commit the probe and test paths explicitly with message `verify low-visit HumanSL search semantics`.

### Task 4: Commit preregistration, probe, and launch `@20`

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`
- Runtime output: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary/`

- [ ] Record the completed prior `rank_5d@40 vs rank_6d@1s` confirmation as 36--4; mark only the remaining three-matchup batch superseded for boundary finding.
- [ ] Predeclare four `@20` screens, exactly 10 complete pairs, cap20, point-estimate `>=50%` pass, protocol/allocation/known-endpoints digests, and next step (`@10` after pass, `@30` after fail). Verify the already committed asset digests with the generator `--check` and validate every known endpoint against its committed archive.
- [ ] Before any boundary query, commit only the preregistration inputs with `git add superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md superpowers/tracks/golaxy-ai-ladder-parity/humansl-search-boundary-plan.md superpowers/tracks/golaxy-ai-ladder-parity/calibration/known_endpoints_exp3_v1.json && git commit -m 'predeclare HumanSL boundary screening'`.
- [ ] Run the local probe:
  `NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost CI=true KIVY_NO_ARGS=1 uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py --base-url http://127.0.0.1:8000 --low-visits 20 --experimental-min-humansl-search-visits 20`.
  Expect exit0, b18/humanv0 verified hashes, visits20, and all canonical PIKL fields nonzero where required.
- [ ] Run the regression gate:
  `CI=true uv run pytest -q tests/platforms/test_humansl_selfplay.py tests/platforms/test_humansl_probe.py tests/platforms/test_ladder_query_contract.py tests/platforms/test_golaxy_calibration_opponent.py tests/test_http_engine.py tests/core/test_ladder_strategy.py`.
- [ ] Launch:
  `NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost CI=true KIVY_NO_ARGS=1 uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py --base-url http://127.0.0.1:8000 --phase screen --boundary-protocol exp3-boundary-v1 --experimental-min-humansl-search-visits 20 --max-pair-attempts 20 --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary --matchups 'rank_5d@20:rank_6d@1s:10,rank_6d@20:rank_7d@1s:10,rank_7d@20:rank_8d@1s:10,rank_8d@20:rank_9d@1s:10'`.
- [ ] Inspect `lsof -nP -iTCP:8000`, the first JSONL header, and first game. Expect direct localhost connection, frozen allocation/fingerprint, and b18 + humanv0 attestation. Abort on any mismatch.

---

## Chunk 2: Outcome-locked continuation

### Task 5: Protocol classification and next-point selection

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/boundary_protocol.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`
- Test: `tests/platforms/test_humansl_boundary_protocol.py`

- [ ] TDD pure functions for fixed-grid classification: cap before 10 pairs returns `abort` with no pass/fail/candidate; `>=50%` returns pass; `<50%` returns fail; completed checkpoints are outcome-locked and cannot append; contradictory higher-fail/lower-pass histories return `non_monotonic` with no selection.
- [ ] TDD next-point rules: 20 pass ->10->5->2 until fail; 20 fail->30; `@30` fail selects the prior committed `@40` screening evidence without scheduling or appending any new `@40` screen; floor2 pass reports `<=2`; the lowest tested pass above the first failure becomes candidate/bracket.
- [ ] Implement `boundary_protocol.py record-screen --transition NAME --visits V --checkpoint PATH --allocation-manifest PATH --known-endpoints PATH --history-dir DIR [--previous PATH]`. It validates the fixed sample/cap and all source digests, writes canonical strict JSON named `history_<transition>_step-<NN>_<digest12>.json`, binds the relevant prior `@40` endpoint digest, includes its own digest and exact `classification/next_visit/candidate/bracket`, and fails if that exact output exists. A new step references the previous immutable manifest digest rather than overwriting it.
- [ ] Implement `boundary_protocol.py check-history --history-dir DIR --known-endpoints PATH`, which revalidates every chain and prior `@40` source and prints the four terminal states/digests. Add `--boundary-history-manifest PATH` to self-play, mutually exclusive with manual outcome selection: it verifies the chain, allocation and known-endpoint digests, constructs the exact next matchup from `next_visit`, and rejects terminal/aborted/non-monotonic histories.
- [ ] Run `CI=true uv run pytest -q tests/platforms/test_humansl_boundary_protocol.py tests/platforms/test_humansl_selfplay.py` and commit explicit paths.
- [ ] After the four `@20` checkpoints finish, run four explicit first-step writers (changing only the rank names and checkpoint filename), for example:
  `uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/boundary_protocol.py record-screen --transition rank_5d__rank_6d --visits 20 --checkpoint superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary/selfplay_screen_rank-5d-20__vs__rank-6d-1s.jsonl --allocation-manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/opening_allocation_boundary_v1.json --known-endpoints superpowers/tracks/golaxy-ai-ladder-parity/calibration/known_endpoints_exp3_v1.json --history-dir superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary/history`.
  Repeat for `rank_6d__rank_7d`, `rank_7d__rank_8d`, and `rank_8d__rank_9d`, then run `... boundary_protocol.py check-history --history-dir .../history --known-endpoints superpowers/tracks/golaxy-ai-ladder-parity/calibration/known_endpoints_exp3_v1.json` and commit all four new manifests explicitly.
- [ ] For each nonterminal history, launch the next screen without hand-substituting visits:
  `NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost CI=true KIVY_NO_ARGS=1 uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py --base-url http://127.0.0.1:8000 --phase screen --boundary-protocol exp3-boundary-v1 --experimental-min-humansl-search-visits 2 --max-pair-attempts 20 --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary --boundary-history-manifest <committed-terminal-history-path>`.
  After completion, call `record-screen` with the exact new checkpoint and `--previous <committed-terminal-history-path>`, validate, and commit the new immutable step before continuing.

### Task 6: Freeze candidates and bind fresh confirmation

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/boundary_protocol.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`
- Create at runtime: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary/selection_manifest_exp3_v1.json`
- Test: `tests/platforms/test_humansl_boundary_protocol.py`

- [ ] TDD selection-manifest creation/validation: four candidates, empirical brackets, allocation digest, known-endpoints manifest/relevant `@40` source digests, and SHA-256 of every new source checkpoint; reject missing/changed sources or non-monotonic/aborted histories.
- [ ] Implement `boundary_protocol.py build-selection --history-dir DIR --allocation-manifest PATH --known-endpoints PATH --out PATH`. It discovers exactly one valid terminal chain per transition, writes canonical strict JSON with all terminal-history/new-source/known-`@40`/allocation digests, includes its own digest, and fails if `PATH` exists. Implement `check-selection --manifest PATH --history-dir DIR --allocation-manifest PATH --known-endpoints PATH` to recompute everything before commit and confirmation. Fingerprint the selection, known-endpoints manifest, and relevant `@40` source digest in each confirmation.
- [ ] TDD confirmation binding: `--boundary-selection-manifest` must match transition and A visits; configuration fingerprint contains manifest/source digests and the preallocated confirmation sequences for that exact visit.
- [ ] TDD Wilson classification: lower bound `>50%` confirmed, interval containing50 inconclusive, upper bound `<50%` weaker; no result path selects a replacement candidate.
- [ ] Create and verify the immutable selection manifest before any confirmation query:
  `uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/boundary_protocol.py build-selection --history-dir superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary/history --allocation-manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/opening_allocation_boundary_v1.json --known-endpoints superpowers/tracks/golaxy-ai-ladder-parity/calibration/known_endpoints_exp3_v1.json --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary/selection_manifest_exp3_v1.json`
  followed by the same script's `check-selection` command with those three exact paths. Commit the selection manifest explicitly before continuing.
- [ ] Add `--boundary-selection-manifest PATH` confirmation mode that validates the manifest and runs all four frozen candidates without manual `--matchups`. Run:
  `NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost CI=true KIVY_NO_ARGS=1 uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py --base-url http://127.0.0.1:8000 --phase confirm --boundary-protocol exp3-boundary-v1 --experimental-min-humansl-search-visits 2 --max-pair-attempts 40 --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary --boundary-selection-manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary/selection_manifest_exp3_v1.json`.
- [ ] Run all boundary/self-play tests, recompute summaries from raw JSONL, update `EXPERIMENTS.md`, archive deterministic evidence, and commit explicit evidence paths.
