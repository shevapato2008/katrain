# Golaxy 3-Star HumanSL Conditional Screen Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the approved branch-aware five-game HumanSL `rank_9d` screens against Golaxy 星阵3星 at exact wire level 3300, with strict resumable evidence and no silent retry.

**Architecture:** Extend the existing immutable fixed-screen preset system with one conditional scheduler and a strict replay validator used by the new protocol. Parameterize the shared alignment preflight so protocol identity and exact Golaxy smoke level enter the configuration fingerprint, while preserving all completed legacy preset behavior. Derive a dedicated level-3300 smoke artifact from the existing token-free smoke report only after validating its successful 3300 probe and sentinel evidence.

**Tech Stack:** Python 3.11, pytest, httpx, existing KaTrain/HumanSL calibration helpers, append-only JSONL, SHA-256 evidence manifests.

**Design:** `superpowers/tracks/golaxy-ai-ladder-parity/golaxy-3star-humansl-conditional-screen-design.md`

---

## Chunk 1: Protocol identity and strict conditional ledger

### Task 1: Parameterize preflight protocol and exact smoke level

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py`
- Test: `tests/platforms/test_golaxy_9d_alignment_runner.py`

- [ ] **Step 1: Write failing tests for exact smoke-level verification**

Preserve the current legacy default: `load_verified_smoke_codes(path)` continues checking level 3000 so the completed
9D/8D/7D presets and fingerprints do not change. Add a separate strict dedicated-artifact path for the new preset;
tests prove it accepts only the exact schema frozen in Task 4, exact level 3300, exact protocol/preset/opponent identity,
one successful probe, distinct out-of-board sentinels, and the source report SHA-256. It rejects a generic report,
unexpected keys, token-like keys, duplicate/missing probes, wrong level or identity, and malformed scalar types.

- [ ] **Step 2: Write a failing fingerprint test**

Call `common_preflight(..., protocol_version="golaxy-3star-humansl-conditional-screen-v1",
preset_name="golaxy3star-rank9d-conditional-20260725", opponent=get_rung(36),
strict_smoke_identity=True)` and assert the payload contains both exact identities plus
`{"rung": 36, "api_level": 3300}`. Assert changing either protocol or preset changes the fingerprint. Also assert
the legacy call produces its existing payload/fingerprint shape without a preset field.

- [ ] **Step 3: Run focused tests and verify RED**

Run:
`KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago pytest -q tests/platforms/test_golaxy_9d_alignment_runner.py`

Expected: failures because smoke verification is fixed to 3000 and `common_preflight` has no protocol parameter.

- [ ] **Step 4: Implement the minimal parameters**

Add optional `protocol_version`, `preset_name`, and `strict_smoke_identity` inputs to `common_preflight`. Their legacy
defaults must execute the old level-3000 verifier and preserve the old payload shape. The new preset supplies all three,
resolves the opponent first, consumes only the strict dedicated artifact for exact rung 36 / level 3300, and includes
both identities in the stable payload. Reject partial, empty, or malformed new-protocol identities.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 3 command. Expected: all tests pass, including unchanged legacy 9D tests.

### Task 2: Add the conditional preset and pure scheduler

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py`
- Test: `tests/platforms/test_golaxy_fixed_screen.py`

- [ ] **Step 1: Write failing immutable-preset tests**

Freeze exactly:

```python
ScreenSpec(
    name="golaxy3star-rank9d-conditional-20260725",
    protocol_version="golaxy-3star-humansl-conditional-screen-v1",
    players=("rank_9d@8", "rank_9d@16", "rank_9d@32", "rank_9d@64", "rank_9d@4", "rank_9d@2"),
    starting_colors=(("rank_9d@8", "B"), ("rank_9d@16", "B"), ("rank_9d@32", "B"),
                     ("rank_9d@64", "B"), ("rank_9d@4", "B"), ("rank_9d@2", "B")),
    valid_per_player=5,
    charged_cap=32,
    golaxy_rung=36,
    golaxy_level_name="星阵3星",
    golaxy_api_level=3300,
    expected_out_dir=... / "golaxy_3star_rank_9d_conditional_20260725",
    fixed_quota_id="golaxy3star-rank9d-conditional-20260725-a",
    strict_ledger=True,
)
```

Add new dataclass fields with compatibility defaults (`protocol_version=None`, `fixed_quota_id=None`,
`strict_ledger=False`) so the three existing preset objects retain their exact header/open/append behavior.

- [ ] **Step 2: Write failing scheduler tests for both complete branches**

Prove the HumanSL color sequence is B/W/B/W/B for every tier and inconclusive results repeat the same tier/color.
Prove:

- `@8 = 5–0` schedules `@4`, then schedules `@2` only if `@4 = 5–0`, and never schedules upper tiers;
- `@8` containing any loss schedules `@16 → @32 → @64`, five valid games each, and never schedules lower tiers;
- no tier begins before the current tier has five valid results;
- the terminal state returns `None` and summaries derive skipped tiers without appending skip records.

- [ ] **Step 3: Run focused tests and verify RED**

Run:
`KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago pytest -q tests/platforms/test_golaxy_fixed_screen.py`

Expected: failures because the preset and conditional scheduler do not exist.

- [ ] **Step 4: Implement the minimal conditional scheduler**

Keep legacy `next_game` behavior unchanged. Add one branch-aware pure scheduling path selected only by
`strict_ledger=True`. Do not add skip records. Thread both preset and protocol identity through preflight and its exact
opponent through strict smoke verification. Require the exact frozen output directory and quota ID for live mode.
Add representative create/open/append regression tests for all three historical presets: legacy 9D's special header,
8D's preset header, and 7D's preset header must remain byte-for-byte unchanged.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 3 command. Expected: all fixed-screen tests pass.

### Task 3: Add strict replay for the new ledger

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py`
- Test: `tests/platforms/test_golaxy_fixed_screen.py`

- [ ] **Step 1: Write failing strict-replay tests**

Freeze and test the new-only record schemas exactly:

```text
header      = type,preset,protocol_version,quota_id,source_revision,players,valid_per_player,charged_cap,golaxy
reservation = type,preset,protocol_version,attempt_id,player,color,fingerprint,quota_id,source_revision
result      = type,preset,protocol_version,attempt_id,player,color,outcome,fingerprint,quota_id,source_revision
```

Fingerprints are bound per player: every reservation/result for one player must equal that player's first accepted
fingerprint; different players may have different fingerprints. Construct one valid history for each branch, then
mutate it one defect at a time. Require rejection of unknown/missing keys or record types, duplicate JSON keys, invalid
JSON, non-object records, booleans masquerading as ints, non-sequential attempt IDs, result without reservation,
duplicate result, result/reservation identity mismatch, wrong quota/source/protocol/preset/fingerprint, player outside
the preset, impossible player/color order, sixth valid result in a tier, and record after terminal state.
Add mutation-between-calls tests proving strict `reserve()` and strict `append_result()` each replay the bytes currently
on disk immediately before writing. `append_result()` must require the sole unmatched tail to be the exact supplied
reservation and reject intervening tampering, an extra record, identity drift, or a different unmatched reservation.

- [ ] **Step 2: Verify RED**

Run:
`KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago pytest -q tests/platforms/test_golaxy_fixed_screen.py -k 'strict or conditional or unmatched'`

Expected: failures because `FixedLedger.open()` currently validates only the header.

- [ ] **Step 3: Implement exact-schema replay**

Implement a duplicate-key-rejecting JSON loader using `object_pairs_hook`, exact plain-scalar checks, and a single replay
function that reads records in order, reconstructs the unique next action before accepting each reservation, checks the
frozen schemas/identities, and counts every reservation toward cap 32. A trailing unmatched reservation is valid
historical evidence but makes the ledger non-resumable. Reorder `_run_async`: if the new ledger exists, strict replay
must happen before local preflight, `load_token()`, or construction/use of a Golaxy client. Add an instrumented test
proving an unmatched reservation reaches none of those seams. Preserve legacy open behavior only for legacy presets.
For the new preset, both `reserve()` and `append_result()` must rerun full strict replay immediately before `_append`;
the result path accepts exactly one unmatched tail only when it byte-for-byte matches the supplied reservation.

Add mutually exclusive `--summarize-only`. Exact invocation:

```bash
conda run --no-capture-output -n py311_katago python \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py \
  --preset golaxy3star-rank9d-conditional-20260725 --summarize-only \
  --expected-source-revision <LEDGER_SOURCE_SHA> \
  --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_3star_rank_9d_conditional_20260725
```

It performs strict offline replay, rejects base URL/smoke/token/quota/confirm flags, reports valid terminal ledgers,
reports an otherwise-valid unmatched tail with `resumable:false`, and rejects tampered ledgers.

- [ ] **Step 4: Verify GREEN and related regressions**

Run:
`KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago pytest -q tests/platforms/test_golaxy_fixed_screen.py tests/platforms/test_golaxy_9d_alignment_runner.py tests/platforms/test_golaxy_9d_alignment_protocol.py`

Expected: all tests pass.

- [ ] **Step 5: Format and commit Chunk 1**

Run Black with line length 120 on the two modified Python files and tests, rerun Step 4, then stage only those files
and commit `add Golaxy 3-star conditional screen`.

## Chunk 2: Dedicated evidence and live execution

### Task 4: Build and validate the dedicated 3300 smoke artifact

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py`
- Test: `tests/platforms/test_golaxy_fixed_screen.py`
- Create at runtime: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_3star_rank_9d_conditional_20260725/smoke_3300.json`

- [ ] **Step 1: Write a failing artifact-builder test**

Given a token-free source smoke report, freeze this exact dedicated artifact schema:

```text
schema_version,type,protocol_version,preset,generated_at,source_report_sha256,
golaxy,level_probe,pass_code,resign_code
```

`schema_version` is plain int 1; `type` is `golaxy_level_smoke`; protocol/preset are the frozen strings; `golaxy` is
exactly rung 36/name 星阵3星/api 3300; `level_probe` is the sole matching source probe with exact keys
`level,level_name,coord,ok,elapsed_s,error`; sentinels are distinct out-of-board plain ints. Require exactly one
successful source level-3300 probe, `errors == []`, source byte SHA-256, RFC3339 UTC generation time, and no unexpected
or token-like keys. Reject missing, duplicate, failed, or wrong-level probes.

- [ ] **Step 2: Run the focused test and verify RED**

Run:
`KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago pytest -q tests/platforms/test_golaxy_fixed_screen.py -k smoke`

Expected: failure because builder mode and strict dedicated loader do not exist.

- [ ] **Step 3: Implement the minimal offline extractor**

Add mutually exclusive `--build-smoke-only` plus `--source-smoke-report`. It requires only `--preset` and exact `--out`;
it rejects `--base-url`, `--expected-source-revision`, `--smoke-report`, token/quota/confirm flags, performs no client
construction/calls, and atomically writes `<exact-out>/smoke_3300.json` using temporary-file + fsync + replace.

- [ ] **Step 4: Run tests and generate the artifact**

Run the focused fixed-screen tests, then invoke exactly:

```bash
KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago python \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py \
  --preset golaxy3star-rank9d-conditional-20260725 --build-smoke-only \
  --source-smoke-report superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/smoke_report.json \
  --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_3star_rank_9d_conditional_20260725
```

Verify the artifact with the strict loader used by preflight and record its SHA-256.

- [ ] **Step 5: Commit Task 4 code and tests**

Format, rerun the related suite, stage only the runner and its test, and commit `add Golaxy 3300 smoke evidence mode`.
Record this commit's full SHA as `RUNTIME_CODE_REVISION`; do not modify scoped code/tests after this point.

### Task 5: Predeclare the executable run and freeze the source revision

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Add the predeclaration**

Record the exact design path, preset/protocol/quota/output, rung 36 / level 3300, branch rules, B/W/B/W/B colors,
cap 32, unmatched-reservation stop, dedicated smoke SHA, and the already-existing `RUNTIME_CODE_REVISION` from Task 4.
State that five games per tier are directional screens, not Elo estimates. Do not attempt to record the future
predeclaration commit SHA.

- [ ] **Step 2: Run the scoped regression suite**

Run:
`KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago pytest -q tests/platforms/test_golaxy_fixed_screen.py tests/platforms/test_golaxy_9d_alignment_runner.py tests/platforms/test_golaxy_9d_alignment_protocol.py tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_humansl_selfplay.py`

Expected: all pass.

- [ ] **Step 3: Commit only the predeclaration and token-free smoke artifact**

Stage exact files, confirm `git diff --cached` contains no token or unrelated worktree changes, and commit
`predeclare Golaxy 3-star live screen`. Runtime continues to use the recorded `RUNTIME_CODE_REVISION` as
`--expected-source-revision`; this docs/artifact commit is a scoped-clean descendant and is not written circularly into
its own contents.

### Task 6: Run local-only preflight

**Files:**
- Runtime read/write only in the exact experiment directory.

- [ ] **Step 1: Ensure the local KataGo HTTP service is healthy**

Use `http://127.0.0.1:8000`; do not substitute a remote analysis server. Start the existing local service only if absent.

- [ ] **Step 2: Run preflight without Golaxy credentials**

Invoke `run_golaxy_fixed_screen.py` with the new preset, `--preflight-only`, exact output, dedicated smoke report, and
`RUNTIME_CODE_REVISION`. Confirm next game `rank_9d@8` as HumanSL black, b18/humanv0/canonical PIKL,
rung 36 / 3300, and a stable fingerprint. The command must reject token/quota flags and make no Golaxy request.

### Task 7: Execute the approved live branch

**Files:**
- Create/append at runtime: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_3star_rank_9d_conditional_20260725/fixed_screen.jsonl`

- [ ] **Step 1: Create the one explicit quota and start once**

Invoke the runner with quota `golaxy3star-rank9d-conditional-20260725-a`, `--confirm-new-quota`,
`RUNTIME_CODE_REVISION`,
exact output, dedicated smoke report, and local base URL. Load the token only from the named environment variable or
the existing redacted user token file. Never print it.

- [ ] **Step 2: Monitor append-only progress**

Report each completed tier. Do not edit the ledger, auto-retry a stopped attempt, or exceed 32 reservations. If an
unmatched reservation or any fail-closed error occurs, stop and report the exact blocker to the user.

- [ ] **Step 3: Follow only the frozen branch**

If `@8` is 5–0, complete `@4` and then `@2` only when `@4` is also 5–0. Otherwise complete `@16`, `@32`, and
`@64`. Every started tier must reach five valid results unless a fail-closed stop occurs.

### Task 8: Verify, summarize, and archive the result

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`
- Runtime evidence: exact experiment result directory.

- [ ] **Step 1: Run offline strict replay and summary**

Run the exact `--summarize-only` command from Task 3 with the ledger's source revision. Verify header identity,
reservation/result pairing, attempts <= 32, per-tier colors/results, fingerprints, actual terminal branch, and absence
of records after terminal state. Compute SHA-256 for ledger and smoke artifact.

- [ ] **Step 2: Update the experiment ledger**

Record every tier's wins/losses/inconclusive/charged attempts, actual branch, evidence paths and hashes. State the
small-sample limitation and do not infer Elo.

- [ ] **Step 3: Run completion verification**

Run the scoped regression suite from Task 5, the offline summary command, `git diff --check`, and a targeted secret
scan of staged evidence. Confirm unrelated dirty files remain untouched.

- [ ] **Step 4: Commit documentation/evidence intentionally**

Stage only `EXPERIMENTS.md` and the approved token-free evidence files, inspect the staged diff, and commit
`record Golaxy 3-star HumanSL screen`.
