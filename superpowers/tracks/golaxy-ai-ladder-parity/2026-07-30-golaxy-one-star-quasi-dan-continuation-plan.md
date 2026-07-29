# Golaxy One-Star and Quasi-Dan Continuation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Golaxy 1-star `b18@1` to ten valid games, then resume the existing quasi-5D through quasi-9D campaign without repeating evidence.

**Architecture:** Make one protocol-only change so the fixed `b18@1` stage always waits for ten valid results. Recover into a new child ledger bound to the stopped parent SHA, allowing existing replay and strict serial execution to resume at 1-star and then advance through the remaining quasi-dan stages.

**Tech Stack:** Python 3.13, pytest, append-only JSONL campaign ledger, existing local KataGo and Golaxy adapters.

**Spec:** `superpowers/tracks/golaxy-ai-ladder-parity/2026-07-30-golaxy-one-star-quasi-dan-continuation-design.md`

---

## Chunk 1: Protocol revision

### Task 1: Require ten `b18@1` results

**Files:**
- Modify: `tests/platforms/test_golaxy_alignment_campaign.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_alignment_campaign.py`

- [ ] **Step 1: Write the failing tests**

Change the 0-win and 2-win four-game cases to expect no decision and add this explicit replay assertion:

```python
records = completed_seven_d + results("one_star_b18_1", "b18@1", wins(2, 4))
assert campaign.next_action(records) == campaign.GameRequest(
    "one_star_b18_1", "b18@1", "B", 10, "confirm"
)
```

Keep the existing 10-game terminal matrix and change the trailing-evidence regression to expect its appropriate 10-game status.

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py -q`

Expected: failures show the current `weak_screen` decision stops after four games.

- [ ] **Step 3: Implement the minimal protocol change**

In `stage_decision`, remove only the early weak-classification return:

```python
if stage == "one_star_b18_1":
    candidate = summarize_candidate(records, stage)
    if candidate.valid >= 10:
        status = (
            "weak_at_10" if candidate.wins <= 3
            else "aligned_at_10" if candidate.wins <= 6
            else "overstrong_at_10"
        )
        return StageDecision(stage, status, candidate.player, candidate, evidence)
    return None
```

- [ ] **Step 4: Verify GREEN and regressions**

Run: `.venv/bin/python -m pytest tests/platforms/test_golaxy_alignment_campaign.py tests/platforms/test_golaxy_humansl_rank_alignment.py tests/platforms/test_golaxy_9d_alignment_runner.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

Stage only the protocol and campaign test; commit as `require ten-game one-star confirmation`.

## Chunk 2: Child-ledger execution

### Task 2: Recover and run strictly serially

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_alignment_campaign_20260730/campaign_v2.jsonl`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Verify the parent and local engine**

Compute the exact parent SHA and run the read-only campaign summary. Verify `http://127.0.0.1:8000/health` reports the frozen b18 and humanv0 identities.

- [ ] **Step 2: Start child recovery**

Run the campaign with a new output plus exact `--parent` and `--parent-sha256`. Expect the first reservation to be 1-star `b18@1`, target 10, then strict serial continuation through quasi-8D and quasi-9D. Stop immediately on any remote or identity error.

- [ ] **Step 3: Validate evidence**

Run `--summary`, verify reservation closure and unique inherited `origin_result_id` values, compute ledger SHA-256, and compare the replayed next action or final decisions with emitted events.

- [ ] **Step 4: Document and verify**

Append the new 1-star and quasi-dan results or stopping point to `EXPERIMENTS.md`. Run `git diff --check` and the campaign test suite.

- [ ] **Step 5: Commit evidence**

Stage only the new ledger and experiment documentation; commit as `record Golaxy campaign continuation`.
