# Golaxy Alignment Campaign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute one fail-closed serial campaign that completes 7D `rank_7d@1s`, screens 1-star `b18@1`, and aligns Golaxy quasi-5D through quasi-9D with the lower HumanSL profile.

**Architecture:** A pure protocol module owns deterministic scheduling, evidence replay, and append-only recovery. A thin live runner reuses the existing Golaxy transport, adjudication, and model-attestation helpers. One campaign ledger persists stage transitions and stops all later stages after any remote error.

**Tech Stack:** Python 3.13, dataclasses, JSONL, pytest, httpx, existing KaTrain ladder calibration helpers.

**Spec:** `superpowers/tracks/golaxy-ai-ladder-parity/2026-07-29-golaxy-continuation-quasi-dan-alignment-design.md`

---

## Chunk 1: Deterministic protocol and ledger

### Task 1: Campaign state machine

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_alignment_campaign.py`
- Create: `tests/platforms/test_golaxy_alignment_campaign.py`

- [ ] **Step 1: Write failing protocol tests**

  Freeze `GameRequest(stage, player, color, target_valid, phase)` and
  `StageDecision(stage, status, selected_player, best_observed, evidence)`. Add table-driven tests for grid indices
  `1s/4/8/16/32/64`, initial `@8`, every exact midpoint transition, independent per-candidate B/W alternation,
  inconclusive denominator/color behavior, and these exact terminal statuses:

  - 7D: `completed_at_10`.
  - `b18@1`: `weak_screen`, `weak_at_10`, `aligned_at_10`, `overstrong_at_10`.
  - quasi-dan: `aligned_at_10`, `overstrong_at_grid_floor`, `selected_closest_confirmed`,
    `no_strong_candidate_in_grid`, and `no_qualified_candidate_in_grid` with non-null `best_observed`.

  Assert lower-neighbor comparison after 7–10 wins, upward exhaustion after repeated 0–3 confirmations,
  `(abs(wins-5), candidate_index)` ordering, and that 4-game-only screens never enter final ranking.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py -q`

  Expected: FAIL because `golaxy_alignment_campaign` and its scheduling API do not exist.

- [ ] **Step 3: Implement the minimal pure protocol**

  Define immutable `Candidate`, `GameRequest`, `StageDecision`, stage constants, evidence counting, `next_action(records)`, deterministic binary bounds, and final selection. Freeze stage order as 7D, 1-star, quasi-5D, quasi-6D, quasi-7D, quasi-8D, quasi-9D.

- [ ] **Step 4: Verify GREEN**

  Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py -q`

  Expected: all protocol tests pass.

### Task 2: Append-only campaign recovery

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_alignment_campaign.py`
- Modify: `tests/platforms/test_golaxy_alignment_campaign.py`

- [ ] **Step 1: Write failing ledger tests**

  Cover header validation, reservation/result pairing, campaign stop, same-ledger refusal after stopped/unmatched records,
  and operator-created child recovery from a stopped parent. Build a three-generation result→carry→carry fixture that:

  - validates SHA at every parent edge;
  - preserves the first `origin_result_id` across both carries;
  - records direct-parent SHA and line on each carry;
  - rejects a generation-three duplicate across result and carry rows;
  - rejects a tampered intermediate SHA;
  - ignores inherited `stage_completed` control rows;
  - excludes a stopped parent's unmatched reservation as `unknown_charged_attempt` while importing its completed results.

  Verify replay-based resume independently from the 7D, `b18@1`, and quasi-dan stages.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py -q`

  Expected: FAIL on missing ledger/recovery functions while the Task 1 protocol tests remain green.

- [ ] **Step 3: Implement minimal ledger and recovery functions**

  Add fsync append, strict loader, stable result IDs, recursive ancestor import with edge-by-edge SHA-256 verification,
  stage reconstruction from evidence, same-ledger stopped/unmatched rejection, and explicit child-ledger recovery. Normalize
  the seven legacy 7D results from
  `calibration/results/golaxy_humansl_rank7_rank9_refinement_20260728/refinement_v1.jsonl` SHA
  `c3a782609b47f812df26c1aacf871c72c2661581687773b2059eac642b4efbc2` using immutable IDs
  `legacy:<source_sha256>:<source_line_number>`; preserve those IDs in every later carry generation.

- [ ] **Step 4: Verify GREEN and commit Chunk 1**

  Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py -q`

  Expected: all campaign tests pass.

  Commit only the protocol module and its test with message `add Golaxy campaign protocol`.

---

## Chunk 2: Live runner and experiment execution

### Task 3: Player, opponent, and identity adapters

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_alignment_campaign.py`
- Modify: `tests/platforms/test_golaxy_alignment_campaign.py`

- [ ] **Step 1: Write failing adapter tests**

  Assert exact opponent mappings `(准5段,2000)` through `(准9段,2900)` and lower-rank profiles. Add separate identity/query
  matrices:

  - native `@1s`: query omits `model`, frozen default process advertises attached humanv0, valid `humanPolicy` is required,
    selection is argmax-only, and `_wrapper` is neither required nor trusted for move selection;
  - `@4+`: query explicitly routes b18, includes humanv0 profile + canonical PIKL, and every response must attest
    `_wrapper.selected_model=b18` plus frozen b18/humanv0 paths and SHAs;
  - pure `b18@1`: query explicitly routes b18, contains no HumanSL/PIKL controls, requires empty `moveInfos` plus a valid
    362-entry native b18 `policy`, selects its deterministic argmax, and every response must attest actual b18 identity.
    A b28 or missing-wrapper response fails closed for both explicit-b18 modes.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py -q`

  Expected: FAIL because `run_golaxy_alignment_campaign` is absent; Chunk 1 tests remain green.

- [ ] **Step 3: Implement adapters and preflight**

  Reuse lower-level transport/adjudication pieces, but implement campaign-specific preflight and move callbacks because the old
  alignment helper assumes PIKL for every search selection and wrapper attestation for native `@1s`. Construct pure b18 directly
  as a `LadderRung`; validate exact effective queries. Persist the `/health` snapshot for default model, b18, and attached
  humanv0 into the campaign header before any stage starts. Apply per-response `_wrapper` attestation only to explicitly routed
  b18; validate native `@1s` through the frozen default-process humanv0 mount, humanPolicy presence, and argmax-only selection.
  Add async MockTransport coverage for campaign-specific preflight and per-move behavior in all three modes.

- [ ] **Step 4: Verify GREEN**

  Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py -q`

  Expected: all campaign protocol, ledger, and adapter tests pass.

### Task 4: Strictly serial live loop

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_alignment_campaign.py`
- Modify: `tests/platforms/test_golaxy_alignment_campaign.py`

- [ ] **Step 1: Write failing orchestration tests**

  Test reservation-before-request, result persistence, repeated color after inconclusive, five-second cooldown, exact
  `stage_started`→games→`stage_completed` ordering, predecessor gating, and no later-stage request after stopped. A local
  preflight failure must write `campaign_stopped` before any reservation or Golaxy call. Reinvoking an existing stopped `--out`
  must refuse before local analysis or Golaxy access; recovery succeeds only with a different output and exact matching
  `--parent/--parent-sha256`.

- [ ] **Step 2: Verify RED**

  Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py -q`

  Expected: FAIL on missing async loop/CLI behavior; prior tests remain green.

- [ ] **Step 3: Implement the minimal async loop and CLI**

  Add `--out`, `--parent`, `--parent-sha256`, and read-only `--summary`. Base URL is fixed and validated as
  `http://127.0.0.1:8000`; the access token is loaded through the existing `run_golaxy_9d_alignment.load_token(None)` path,
  so no new token option exists. Never retry. Print concise `game_start/game_result/stage_complete/campaign_stopped` events.

- [ ] **Step 4: Verify GREEN and relevant regressions**

  Run:

  `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py tests/platforms/test_golaxy_humansl_rank_alignment.py tests/platforms/test_golaxy_9d_alignment_runner.py -q`

  Expected: all selected tests pass.

- [ ] **Step 5: Commit the runner**

  Commit only the runner and tests with message `add serial Golaxy alignment campaign runner`.

### Task 5: Execute and document the campaign

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_alignment_campaign_20260729/campaign_v1.jsonl`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Verify local service**

  Run escalated:

  `curl -fsS http://127.0.0.1:8000/health | jq -e '.status=="ok" and .models.b18.running==true and .models.b18.model_sha256_verified==true and .models.b18.model_sha256=="9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d" and .models.b18.human_model_sha256_verified==true and .models.b18.human_model_sha256=="637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5"'`

  Expected: `true` and exit 0.

- [ ] **Step 2: Run the campaign strictly serially**

  Run escalated:

  `NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost CI=true KIVY_NO_ARGS=1 .venv/bin/python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_alignment_campaign.py --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_alignment_campaign_20260729/campaign_v1.jsonl`

  Expected: exit 0 only if every stage reaches a terminal decision; exit 1 immediately on 7002/429/network/identity error.
  Do not create a successor ledger automatically.

- [ ] **Step 3: Validate evidence**

  Run read-only summary:

  `.venv/bin/python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_alignment_campaign.py --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_alignment_campaign_20260729/campaign_v1.jsonl --summary`

  Then run:

  `jq -e -s '([.[]|select(.type=="reservation")]|length)==(([.[]|select(.type=="result")]|length)+([.[]|select(.type=="stopped")]|length)) and ([.[]|select(.type=="carry_result")|.origin_result_id]|length)==([.[]|select(.type=="carry_result")|.origin_result_id]|unique|length)' superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_alignment_campaign_20260729/campaign_v1.jsonl`

  Expected: summary exits 0 without network access; jq prints `true`. Also run `shasum -a 256` on the ledger and compare the
  emitted stage order/colors/decisions against protocol replay.

- [ ] **Step 4: Update experiment documentation**

  Record every tested candidate, valid wins/losses, inconclusives, final or stopped state, ledger path, and SHA. Explicitly state that all HumanSL search requests used actual b18+humanv0+PIKL rather than the historical accidental b28 route.

- [ ] **Step 5: Final verification and commit**

  Run `git diff --check` and `.venv/bin/python -m pytest tests/platforms/test_golaxy_*.py -q`. Commit only the campaign ledger and experiment documentation with message `record Golaxy alignment campaign results`.
