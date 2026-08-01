# Golaxy 3-Star b18 20-Game Extension Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run an auditable continuation that extends Golaxy 星阵3星 versus pure b18 at 32 and 64 visits to exactly 20 conclusive games each.

**Architecture:** Add one focused pure module for the frozen v6 ledger, provenance validation, scheduling, and summaries, plus one live runner that reuses the existing Golaxy transport, b18 analysis, b28 referee, smoke-code, locking, and fail-closed patterns. Keep the historical v5 ledger immutable, selectively carry only its 14 relevant closed results, and record all new attempts in a separate append-only ledger.

**Tech Stack:** Python 3.11+, pytest/pytest-asyncio, httpx, existing KaTrain ladder calibration adapters, JSONL with flush/fsync, fcntl output locking.

**Design spec:** `docs/superpowers/specs/2026-08-01-golaxy-three-star-b18-20-game-extension-design.md`

---

## Chunk 1: Deterministic protocol and ledger

### Task 1: Frozen evidence and scheduler

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_b18_20game_extension.py`
- Create: `tests/platforms/test_golaxy_b18_20game_extension.py`

- [ ] **Step 1: Write failing tests for constants and selective v5 import**

Test the exact parent path/SHA, b18 and b28 SHAs, wire level 3300, candidates `(32, 64)`, target 20, and that source rows 17–20 plus 2–6/21–25 are imported in original parent order as four `@32` and ten `@64` conclusive results. Assert a changed parent byte, wrong level/visits/outcome, duplicate source row, or wrong inherited color balance is rejected.

```python
def test_frozen_parent_imports_only_relevant_balanced_evidence(tmp_path):
    carries = protocol.load_frozen_carries(protocol.PARENT_PATH, protocol.PARENT_SHA256)
    assert [(row["visits"], row["color"]) for row in carries] == [
        (64, "B"), (64, "W"), (64, "B"), (64, "W"), (64, "B"),
        (32, "B"), (32, "W"), (32, "B"), (32, "W"),
        (64, "W"), (64, "B"), (64, "W"), (64, "B"), (64, "W"),
    ]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/platforms/test_golaxy_b18_20game_extension.py -q`

Expected: FAIL because the new module does not exist.

- [ ] **Step 3: Add scheduler tests and run them RED**

Cover initial request `@32/B`, alternation, same-color replenishment after each allowed inconclusive type, transition to
`@64/B` only after 20 valid `@32`, and exact completion after both reach 20.

Run: `python -m pytest tests/platforms/test_golaxy_b18_20game_extension.py -q`

Expected: scheduler API tests FAIL.

- [ ] **Step 4: Implement frozen constants, normalized outcomes, and scheduler**

Implement immutable dataclasses `GameRequest`, `CandidateSummary`, `CampaignDecision`, and functions:

```python
def load_frozen_carries(parent_path: Path, expected_sha256: str) -> tuple[dict, ...]: ...
def summarize_candidate(evidence: Sequence[Mapping[str, object]], visits: int) -> CandidateSummary: ...
def next_action(evidence: Sequence[Mapping[str, object]]) -> GameRequest | CampaignDecision: ...
```

`next_action` returns `@32` until 20 conclusive, then `@64`; color is `B` for an even conclusive count and `W` for odd. Replenishable inconclusives do not advance the count, so the color repeats. Reject more than 20 conclusive results for either candidate.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m pytest tests/platforms/test_golaxy_b18_20game_extension.py -q`

Expected: all Task 1 tests PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_b18_20game_extension.py tests/platforms/test_golaxy_b18_20game_extension.py
git commit -m "add Golaxy b18 extension scheduler"
```

### Task 2: Append-only v6 ledger and recovery validation

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_b18_20game_extension.py`
- Modify: `tests/platforms/test_golaxy_b18_20game_extension.py`

- [ ] **Step 1: Write failing ledger tests**

Test exclusive initialization, exact v6 header, complete initial carry prefix, direct-parent line and SHA provenance, JSON object/schema validation, unique campaign/attempt/result IDs, reservation-to-result matching, replay order, fsync append behavior, and summary mode. Assert stopped ledgers and unmatched reservations cannot resume.

Test the three recovery cases separately:

```python
def test_unmatched_reservation_freezes_ledger_without_mutation(tmp_path): ...
def test_definite_failure_closes_reserved_attempt_with_stopped(tmp_path): ...
def test_authorized_child_excludes_uncertain_attempt_and_carries_only_closed_results(tmp_path): ...
```

Also assert that v6 cannot use another v6 as its parent, a stopped or unmatched v6 cannot be resumed in place, an
unauthorized v7 continuation is rejected, and v7 requires a distinct output path, exact parent SHA, explicit
authorization marker, and full excluded-reservation descriptor.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/platforms/test_golaxy_b18_20game_extension.py -q`

Expected: new ledger API tests FAIL.

- [ ] **Step 3: Implement the minimal ledger API**

Define these exact row contracts before implementing them:

| Row | Required fields |
|---|---|
| `campaign_header` v6 | `type`, `protocol=golaxy-b18-three-star-20game-extension-v6`, `campaign_id`, `created_at`, `source_v5_path`, `source_v5_sha256`, `target_valid=20`, `candidate_order=[32,64]`, `game_contract`, `complete_health_response` |
| `campaign_header` v7 | all identity/contract fields plus `protocol=...-v7`, `authorization=explicit_user_continue`, `parent_path`, `parent_sha256`, and optional full `excluded_uncertain_reservation` |
| v6 `carry_result` from v5 | `type`, `visits`, `color`, `outcome`, `conclusive=true`, `origin_result_id=legacy:<v5_sha>:<v5_line>`, `direct_parent_sha256`, `direct_parent_line`, `source_outcome` |
| v7 `carry_result` from v6 | same evidence fields, but preserve the parent evidence's existing `origin_result_id`; set `direct_parent_sha256` and `direct_parent_line` to the exact closed parent `carry_result` or `result` row |
| `reservation` | `type`, `attempt_id`, `request_id=<campaign_id>:<attempt_id>`, `visits`, `color`, `target_valid`, `created_at` |
| `result` | reservation identity fields plus `origin_result_id=<campaign_id>:<attempt_id>`, complete serialized `GameOutcome`, `elapsed_seconds`, `completed_at` |
| `stopped` | `type`, `attempt_id`, `request_id`, plain `reason`, `stopped_at` |

`game_contract` freezes every spec parameter and both model SHAs. `complete_health_response` is the complete JSON object
returned by `/health` after validation, not the reduced identity map used by older campaign code. For v5 imports, carry
comparison uses the exact source row's `level`, `level_name`, `api_level`, `visits`, `color`, and nested `outcome`; v7
instead compares against the exact closed normalized v6 evidence row and preserves its evidence and origin ID. Only `our_win`,
`our_loss`, `inconclusive_score`, `inconclusive_unsettled`, and `inconclusive_unstable` are accepted by `append_result`;
engine/terminal classifications must go through `append_stop`.

Add:

```python
def initialize_v6_campaign(path, campaign_id, complete_health_response): ...
def initialize_v7_continuation(path, campaign_id, complete_health_response, *, parent_path, parent_sha256, authorization): ...
def load_campaign(path, *, summary=False): ...
def append_reservation(path, attempt_id, request): ...
def append_result(path, attempt_id, outcome: GameOutcome): ...
def append_stop(path, attempt_id, reason): ...
def campaign_summary(path) -> dict: ...
```

All appends use one JSON line followed by `flush()` and `os.fsync()`. Initialization uses exclusive create plus directory fsync. `load_campaign(summary=False)` rejects any stop or unmatched reservation without changing the file. v6 always imports the frozen v5 evidence. v7 alone may recover a stopped/frozen v6 after explicit authorization; it imports only closed evidence and records the full excluded reservation when applicable.

For v7, validate each carry against a closed parent evidence row, never a reservation or stop row. The
`excluded_uncertain_reservation` is derived by the initializer from the SHA-validated parent and cannot be supplied or
altered by the caller: unmatched-parent recovery records the exact parent line number and reservation object, while a
fully closed stopped parent records no uncertainty descriptor. Before creating v7, require the current canonical
complete health response to equal the SHA-validated parent header's `complete_health_response`; copy that same object
into v7 and bind its `PreflightProof` to it. Authorized recovery with any parent/current health drift must fail without
creating the v7 output. Summary lineage classifies only `legacy:<v5_sha>:...` origins as inherited; v6/v7 campaign
origins remain new even when later carried. Aggregate attempts across the parent chain by unique `request_id`, including
completed, stopped, and explicitly excluded uncertain attempts. Add a recovery fixture containing v5 carries, v6
conclusive and replenishable-inconclusive results, plus a stopped or unmatched final attempt.

Define summary output exactly: ledger path/SHA/protocol, stopped/open-attempt/completion status, next action, per candidate
inherited/new/combined W-L, inherited/new/combined B-W, total attempts, counts for each accepted inconclusive class, and
the descriptive-extension warning.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/platforms/test_golaxy_b18_20game_extension.py -q`

Expected: all protocol and ledger tests PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_b18_20game_extension.py tests/platforms/test_golaxy_b18_20game_extension.py
git commit -m "add resumable Golaxy b18 extension ledger"
```

## Chunk 2: Strict live execution

### Task 3: b18 player, b28 referee, and serial runner

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py`
- Modify: `tests/platforms/test_golaxy_b18_20game_extension.py`

- [ ] **Step 1: Write failing player/query, identity, and complete-preflight tests**

Assert that `b18@32` and `b18@64` produce exact 19x19 Chinese/7.5 queries with `maxVisits` equal to the candidate, `wideRootNoise=0.04`, `model=b18`, `reportAnalysisWinratesAs=BLACK`, and no HumanSL field. Assert health freezes verified b18 and b28 identities at the spec SHAs. Mock responses with wrong/missing wrapper attestation and require rejection.

Before implementing the campaign preflight, add call-order tests proving all six gates (b18@32, b18@64, b28@200,
b28@800, rung/token, verified smoke codes) finish before the executor can append a reservation. Add drift tests for
KataGo version, model path, default model, running state, b18 identity, and b28 identity. Live preflight must canonicalize
the current complete validated health response and compare it exactly with the ledger header; every failure leaves zero
reservations and no attempt-bound stop.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/platforms/test_golaxy_b18_20game_extension.py -q`

Expected: runner import/API tests FAIL.

- [ ] **Step 3: Implement strict player and all-at-once campaign preflight**

Reuse `adapters.build_ladder_analysis_query`, `adapters.validate_analysis_attestation`, `adapters.adjudicate`, and the existing verified smoke/token loaders. Construct a pure b18 `LadderRung` per requested visits. Implement one
`preflight_campaign(...) -> PreflightProof` which validates the current complete health response, both exact model SHAs,
b18@32, b18@64, b28@200, b28@800 queries and response attestations, rung 36 to wire 3300, token availability, and
verified distinct pass/resign codes. Complete the entire proof before the executor can append anything and pass the
proof into the executor; there is no lazy per-candidate preflight callback. Keep `BASE_URL` exactly
`http://127.0.0.1:8000`.

Canonicalize the complete health response and require exact equality with the ledger header before any append. Bind
`PreflightProof` to that canonical object and its SHA-256; the executor verifies both against the loaded header, and
every player/referee response attestation is validated against that same proof.

- [ ] **Step 4: Write failing game and serial-executor tests**

Cover `play_one_game(..., move_cap=400)`, 800-visit stability recheck, allowed inconclusive result append and same-color continuation, five-second cooldown, strict one-at-a-time calls, and exact stop at 20/20.

Only exceptions raised by `play_extension_game` and explicit `inconclusive_engine`/`inconclusive_terminal`
classification may be converted to an attempt-bound `stopped`. Reservation/result/stop append, fsync, lock, sleep, and
emit remain outside that catch boundary. If a ledger mutation, cancellation, interrupt, or emit fails, perform no
compensating append; propagate the error and let strict replay classify any unmatched ledger.

Add fault-injection tests for reservation/result/stop partial-write or fsync failure, cancellation/interrupt and emit
failure. Separately cover definite HTTP/business `7002`, quota/rate-limit, malformed response, and identity drift,
which must close the reserved attempt with `stopped`.

- [ ] **Step 5: Implement game wrapper and executor**

Implement:

```python
async def play_extension_game(..., request, identity_snapshot) -> GameOutcome: ...
async def execute_serial_campaign(path, *, preflight_proof, play_game, sleep=asyncio.sleep, emit=...): ...
async def run_live(args) -> dict: ...
```

The wrapper uses Golaxy rung 36 / wire 3300, verified pass/resign codes, b28 scoring at 200 visits, b28 stability at 800 visits, and the exact result classification in the design. The executor reserves and fsyncs before each game, closes exactly once, sleeps five seconds between attempts, and never catches an error to retry it.

- [ ] **Step 6: Write CLI/mode/output-locking tests and run RED**

Cover mutually exclusive `--audit-parent`, `--initialize`, `--summary`, live default, and
`--authorize-continuation` modes. Canonicalize the lock path and reject a second writer, same-file parent/output,
malformed SHA, recovery into an existing output, v6-to-v6 recovery, and unauthorized v7 creation.

Run: `python -m pytest tests/platforms/test_golaxy_b18_20game_extension.py -q`

Expected: CLI/mode tests FAIL.

- [ ] **Step 7: Implement CLI, initialization, recovery modes, and locking**

`--audit-parent` is read-only. `--initialize --out PATH` fetches and validates `/health`, exclusively writes the v6
header/carries, runs the complete campaign preflight, and exits without a reservation. `--summary --out PATH` is
offline/read-only. Live default repeats the complete campaign preflight before executing. v7 requires
`--authorize-continuation --parent PATH --parent-sha256 SHA --out NEW_PATH` and an explicit authorization string in the
header. This v7 command validates the parent, derives any excluded uncertain reservation, initializes, preflights, and
exits reservation-free; it does not play. v7 summary and live execution use the same commands as v6 against the new
output path:

```bash
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py --authorize-continuation --parent OLD.jsonl --parent-sha256 EXACT_SHA --out NEW.jsonl
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py --summary --out NEW.jsonl
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py --out NEW.jsonl
```

- [ ] **Step 8: Run focused and regression tests**

Run:

```bash
python -m pytest tests/platforms/test_golaxy_b18_20game_extension.py -q
python -m pytest tests/platforms/test_golaxy_alignment_campaign.py tests/platforms/test_golaxy_9d_alignment_runner.py tests/core/test_ladder_calibration.py tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_ladder_query_contract.py -q
```

Expected: all tests PASS.

- [ ] **Step 9: Commit Task 3**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py tests/platforms/test_golaxy_b18_20game_extension.py
git commit -m "add strict Golaxy b18 extension runner"
```

## Chunk 3: Execute and record the experiment

### Task 4: Initialize, run, validate, and document v6

**Files:**
- Create at runtime: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v6.jsonl`
- Modify after successful completion: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Audit the frozen v5 parent without creating v6**

Run:

```bash
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py --audit-parent
```

Expected JSON: exact v5 path/SHA, 14 relevant valid rows, `@32` 1-3 and 2B/2W, `@64` 7-3 and 5B/5W. No file is created.

- [ ] **Step 2: Initialize v6 with complete health identity and no reservation**

Run:

```bash
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py --initialize --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v6.jsonl
```

Expected: `/health` validates b18 SHA `9d7a...51f1d` and b28 SHA `798d...3d3f0`; all four exact local probes and Golaxy/token/smoke bindings pass; v6 contains one header plus 14 carries and zero reservations.

- [ ] **Step 3: Run the offline summary gate**

Run:

```bash
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py --summary --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v6.jsonl
```

Expected next action: 星阵3星 `b18@32`, color B, current valid 4, target 20; no stop or open reservation.

- [ ] **Step 4: Run the live continuation**

Run:

```bash
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v6.jsonl
```

Run strictly serial until both candidates contain 20 conclusive results or the first failure stops the ledger. Expected maximum additions: 16 valid `@32`, then 10 valid `@64`; replenishable adjudication inconclusives may increase attempts. Do not automatically restart a stopped or ambiguous ledger.

- [ ] **Step 5: Replay-validate and summarize evidence**

Run:

```bash
python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py --summary --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v6.jsonl
shasum -a 256 superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v6.jsonl
```

Require exactly 20 conclusive results and 10B/10W for each candidate, no open reservation, and completion status. Separately report inherited, newly added, and combined W–L figures.

- [ ] **Step 6: Update experiment documentation only if complete**

Add a new `EXPERIMENTS.md` section labeled descriptive extension, including protocol, inherited/new/combined results, inconclusives, final ledger path/SHA, and the warning that the combined 20-game figures are not independent confirmatory estimates. If stopped or unmatched, do not execute the completed-evidence documentation or commit steps; report the partial ledger and exact stop/freeze reason to the user instead.

- [ ] **Step 7: Run final verification**

Run:

```bash
python -m pytest tests/platforms/test_golaxy_b18_20game_extension.py tests/platforms/test_golaxy_alignment_campaign.py tests/platforms/test_golaxy_9d_alignment_runner.py tests/core/test_ladder_calibration.py tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_ladder_query_contract.py -q
git diff --check
git status --short
```

Expected: tests PASS; no whitespace errors; only intended implementation, ledger, and experiment documentation changes are in scope, while pre-existing user changes remain untouched.

- [ ] **Step 8: Commit completed evidence and documentation**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_b18_three_star_20game_20260801/extension_v6.jsonl superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md
git commit -m "record Golaxy three-star b18 extension"
```
