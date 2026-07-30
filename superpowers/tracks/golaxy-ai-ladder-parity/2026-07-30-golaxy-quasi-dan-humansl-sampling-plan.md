# Golaxy Quasi-Dan HumanSL Sampling Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run auditable, strictly serial 10-game `rank_nd@1` weighted-HumanSL matches against Golaxy quasi-5D through quasi-9D without changing completed v1/v2 campaign semantics.

**Architecture:** Add a small independent sampling campaign state machine and runner beside the existing alignment campaign. The new append-only child ledger binds the completed v2 ledger SHA and frozen engine identity, while a deterministic SHA-256 sampler selects from `humanPolicy`; the runner reuses existing Golaxy transport, adjudication, locking, and identity validation primitives.

**Tech Stack:** Python 3.13, dataclasses, hashlib/struct/math/json, httpx, pytest, existing KaTrain calibration adapters.

**Specification:** `superpowers/tracks/golaxy-ai-ladder-parity/2026-07-30-golaxy-quasi-dan-humansl-sampling-design.md`

---

## Chunk 1: Pure protocol and deterministic sampling

### Task 1: Add the fixed five-stage scheduler

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_sampling_campaign.py`
- Create: `tests/platforms/test_golaxy_sampling_campaign.py`

- [ ] **Step 1: Write failing scheduler tests**

Test exact immutable mappings:

```python
STAGES = (
    ("sampling_quasi_5d", "rank_5d@1", 25),
    ("sampling_quasi_6d", "rank_6d@1", 27),
    ("sampling_quasi_7d", "rank_7d@1", 29),
    ("sampling_quasi_8d", "rank_8d@1", 31),
    ("sampling_quasi_9d", "rank_9d@1", 32),
)
```

Assert each stage requests slots 0–9, with HumanSL colors `B,W,...,W`; an inconclusive attempt repeats the same slot/color; ten wins/losses advance to the next stage; all five completed stages return `CampaignDecision(status="completed")`. Reject unknown result types. Once any stopped record exists, require `CampaignDecision(status="stopped")` and prove that no next `GameRequest` is produced.

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_sampling_campaign.py -q`

Expected: FAIL because `golaxy_sampling_campaign` does not exist.

- [ ] **Step 3: Implement the minimal pure state machine**

Define frozen `GameRequest`, `CandidateSummary`, `StageDecision`, and `CampaignDecision` dataclasses. Count only `result in {"win", "loss"}` toward the ten slots; retain inconclusive count separately. Reject unknown stages/players, invalid colors/slots, duplicate origin IDs, and more than ten valid results.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_sampling_campaign.py -q`

Expected: all new scheduler tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/platforms/test_golaxy_sampling_campaign.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_sampling_campaign.py
git commit -m "add Golaxy HumanSL sampling protocol"
```

### Task 2: Add reproducible weighted HumanSL selection

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_sampling_campaign.py`
- Modify: `tests/platforms/test_golaxy_sampling_campaign.py`

- [ ] **Step 1: Write failing sampler tests**

Cover a frozen golden vector and assert exact `u`, chosen policy index, board coordinate/pass, policy SHA, positive total, and interval. Construct the expected digest bytes independently in the test from the ASCII domain plus NUL, uint64 big-endian seed, uint16 big-endian UTF-8 reservation-ID length and bytes, and uint32 big-endian ply; assert SHA-256 first-eight-byte conversion. Independently calculate ordered `math.fsum` cumulative upper bounds. Also test illegal-point filtering, pass selection, negative-weight ignoring, non-finite/wrong-length/zero-mass rejection, and that argmax differs from the weighted golden selection.

- [ ] **Step 2: Run the sampler tests and verify RED**

Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_sampling_campaign.py -q`

Expected: FAIL because the sampling API is absent.

- [ ] **Step 3: Implement the frozen sampler**

Implement `derive_uniform(seed, reservation_id, ply)` with the design's domain-separated binary encoding, and `sample_human_policy(policy, legal_indices, ...)` using index order `0..361`, IEEE-754 big-endian policy digest, `math.fsum`, and the first cumulative upper bound greater than `u * total`. Return a structured audit record; never fall back to argmax/search.

- [ ] **Step 4: Run the sampler tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_sampling_campaign.py -q`

Expected: all sampler tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/platforms/test_golaxy_sampling_campaign.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_sampling_campaign.py
git commit -m "add reproducible HumanSL policy sampling"
```

## Chunk 2: Ledger, runner, and live campaign

### Task 3: Add strict append-only child-ledger replay

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_sampling_campaign.py`
- Modify: `tests/platforms/test_golaxy_sampling_campaign.py`

- [ ] **Step 1: Write failing ledger tests**

Test the fixed parent path and SHA
`4eff5434cd864215a35171d635e4268d06f31f45ca6be27e82e4e0a1105f64d5`, parent protocol v2 and completed status, unique header, sequence continuity, reservation→exactly-one-result/stopped closure, origin uniqueness, stage/slot/color validation, exclusive lock rejection, truncated JSON rejection, and fail-closed recovery from an open reservation.

Freeze header fields independently: campaign protocol `golaxy-humansl-sampling-v1`, sampler
`golaxy-humansl-weighted-v1`, adjudication `golaxy-sampling-adjudication-v1`, exact five candidates/opponents,
ten valid slots, first-black alternating colors, five-second cooldown, uint64 seed, fixed parent path/SHA, and complete
b28/b18/humanv0 identity snapshot. A closed partial ledger must resume at its unique next stage/slot/color without
resampling finished attempts; an existing file is append-only resumable, never truncated or overwritten. Only an open
reservation, malformed, or inconsistent ledger is fail closed.

- [ ] **Step 2: Run ledger tests and verify RED**

Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_sampling_campaign.py -q`

Expected: FAIL on missing ledger APIs.

- [ ] **Step 3: Implement minimal ledger APIs**

Reuse the existing alignment campaign's durable JSONL append and locking pattern without changing it. Create only a new campaign protocol ID, `golaxy-humansl-sampling-v1`; allow validated closed ledgers to reopen only for append/resume, never truncate or overwrite them, and never reinterpret v1/v2 rows as sampling-stage results.

- [ ] **Step 4: Run ledger tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_sampling_campaign.py tests/platforms/test_golaxy_alignment_campaign.py -q`

Expected: new tests and all legacy campaign tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/platforms/test_golaxy_sampling_campaign.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_sampling_campaign.py
git commit -m "add sampling campaign ledger replay"
```

### Task 4: Add the serial live runner

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_sampling_campaign.py`
- Modify: `tests/platforms/test_golaxy_sampling_campaign.py`

- [ ] **Step 1: Write failing runner tests**

Test exact player/profile queries (`humansl`, `maxVisits=1`) for each `rank_nd@1`, wrapper/humanv0 attestation, and prove selection reads only that response's `humanPolicy`. Supply tempting conflicting `moveInfos`, ordinary `policy`, search order and argmax and assert none can affect the move; invalid `humanPolicy` must stop with no fallback.

Test legal-move filtering and the per-move audit record: canonical no-space UTF-8 SGF-history JSON SHA, policy SHA, positive total, random value, selected cumulative interval, and final move. Test exact opponent levels and adjudication: both 200/800 probes settled, delta strictly `<1.0`; equality at 1.0, draw, unverified terminal and unstable probe are inconclusive; move-cap may become valid after stable probes; only an identity-validated Golaxy resignation skips the second probe.

Test same-color inconclusive replenishment and an injected clock where the next reservation/request is at least five seconds after the previous attempt terminates. Parameterize HTTP non-success, API 7002/429/other codes, timeout, disconnect, missing/invalid response, local policy/identity errors, and stopped append/fsync failure. Every case must exit immediately, issue no later request, start no later stage, and perform no post-error cooldown.

Separately inject reservation append/fsync failure and assert that no Golaxy request is sent; inject result append/fsync
failure and assert immediate exit with no next reservation, request, stage, or cooldown. No external action may occur until
the preceding durable write succeeds.

- [ ] **Step 2: Run runner tests and verify RED**

Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_sampling_campaign.py -q`

Expected: FAIL because the runner does not exist.

- [ ] **Step 3: Implement the minimal runner and CLI**

Reuse `run_golaxy_alignment_campaign` health bootstrap, Golaxy token/smoke loading, opponent construction, `play_one_game`, and strict identity checks. Add `--out`, fixed `--parent`, fixed `--parent-sha256`, and read-only `--summary`; reject any parent argument that differs from the specification. Verify parent header/SHA/completed state before loading token, smoke state, or making any Golaxy request. `--summary` must never open a network client or mutate the ledger. Disable HTTP retries; append and sync reservation before each game and result/stopped afterward.

- [ ] **Step 4: Run runner and regression tests**

Run:

```bash
CI=true KIVY_NO_ARGS=1 .venv/bin/python -m pytest \
  tests/platforms/test_golaxy_sampling_campaign.py \
  tests/platforms/test_golaxy_alignment_campaign.py \
  tests/platforms/test_golaxy_humansl_rank_alignment.py \
  tests/platforms/test_golaxy_9d_alignment_runner.py -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/platforms/test_golaxy_sampling_campaign.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_sampling_campaign.py
git commit -m "add serial Golaxy sampling campaign runner"
```

### Task 5: Execute, verify, and archive the experiment

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_sampling_campaign_20260730/campaign_v1.jsonl`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Verify local engine and immutable parent**

Check `/health` reports the frozen b28, b18, and humanv0 identities. Recompute the parent SHA, replay its read-only summary, and require completed status before any Golaxy request.

- [ ] **Step 2: Start the campaign once**

Run the new CLI with the fixed parent path/SHA and the new output path. Keep one live game at a time with five-second cooling. If any local/remote stopped condition occurs, preserve the ledger and do not retry.

- [ ] **Step 3: Validate the final ledger**

Run read-only summary and `jq` checks proving every reservation has exactly one result/stopped closure, origin IDs are unique, all completed groups have ten valid results and five HumanSL games per color, and unknown charged attempts are empty. Compute SHA-256.

- [ ] **Step 4: Archive results**

Append one `EXPERIMENTS.md` section listing all five records, inconclusive attempts, stop state, parent/child SHA, protocol, and the product conclusion that Golaxy 1-star maps to `b18@1` from the prior campaign.

- [ ] **Step 5: Run final verification**

Run:

```bash
git diff --check
CI=true KIVY_NO_ARGS=1 .venv/bin/python -m pytest tests/platforms/test_golaxy_*.py -q
```

Expected: no diff errors and all Golaxy tests PASS.

- [ ] **Step 6: Commit only the new ledger and experiment document**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_sampling_campaign_20260730/campaign_v1.jsonl
git commit -m "record Golaxy HumanSL sampling results"
```
