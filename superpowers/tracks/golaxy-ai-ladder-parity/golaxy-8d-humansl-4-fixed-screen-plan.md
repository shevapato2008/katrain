# Golaxy 8D HumanSL `@4` Fixed Screen Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run exactly five valid `rank_8d@4` games against Golaxy 8D (`level=2800`) with the existing fail-closed experiment guarantees.

**Architecture:** Parameterize the existing fixed-screen harness with an immutable experiment spec while preserving the completed 9D preset and ledger schema. Generalize the shared alignment preflight/play seams to accept an explicit Golaxy opponent descriptor, defaulting to the existing 9D descriptor so all old callers remain unchanged.

**Tech Stack:** Python 3.11, pytest, httpx, existing KaTrain/HumanSL calibration helpers, append-only JSONL.

---

## Chunk 1: Safe opponent and fixed-screen parameterization

### Task 1: Add an explicit Golaxy opponent seam

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py`
- Test: `tests/platforms/test_golaxy_9d_alignment_runner.py`

- [ ] **Step 1: Write failing tests**

Add tests proving an explicit 8D descriptor is reflected in the preflight payload and passed to `adapters.golaxy_move`, while calls that omit it still use rung 33 / level 3000.

```python
opponent = get_rung(31)  # 8D, level 2800
preflight = await common_preflight(..., opponent=opponent)
assert preflight["payload"]["golaxy"] == {"rung": 31, "api_level": 2800}
```

- [ ] **Step 2: Run tests and confirm RED**

Run:
`KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago pytest -q tests/platforms/test_golaxy_9d_alignment_runner.py`

Expected: failure because `common_preflight` and `play_alignment_game` do not accept `opponent`.

- [ ] **Step 3: Implement the minimal seam**

Add an optional keyword-only `opponent: LadderRung | None = None` to both helpers. Resolve `opponent = opponent or golaxy_9d_opponent()`, require a real `golaxy_api_level`, and build the fingerprint payload from `opponent.rung` and `opponent.golaxy_api_level`. Do not alter the default 9D path.

- [ ] **Step 4: Run tests and confirm GREEN**

Run the command from Step 2. Expected: all tests pass.

### Task 2: Add the immutable 8D fixed-screen preset

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py`
- Test: `tests/platforms/test_golaxy_fixed_screen.py`

- [ ] **Step 1: Write failing preset and scheduling tests**

Cover an immutable `ScreenSpec` selected by `--preset`, with these exact 8D values:

```python
ScreenSpec(
    name="golaxy8d-rank8d4-20260724",
    players=("rank_8d@4",),
    starting_colors={"rank_8d@4": "B"},
    valid_per_player=5,
    charged_cap=9,
    golaxy_rung=31,
    golaxy_api_level=2800,
    expected_out_dir="golaxy_8d_rank_8d_4_20260724",
)
```

Tests must prove B/W/B/W/B scheduling, inconclusive original-color replacement, `rank_8d@4` b18+humanv0+canonical PIKL attestation, cap 9, exact output path, header identity, and preservation of the old 9D default preset.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:
`KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago pytest -q tests/platforms/test_golaxy_fixed_screen.py`

Expected: failures because the preset abstraction and CLI option do not exist.

- [ ] **Step 3: Implement the minimal preset abstraction**

Thread `ScreenSpec` through player validation, scheduling, ledger create/open/reserve/summarize, output validation, preflight and live play. Resolve the Golaxy opponent with `get_rung(spec.golaxy_rung)` and fail unless both name/table identity and API level match the spec. Preserve the old preset as the CLI default and its existing header format; the new preset header must include its name, opponent rung and level.

- [ ] **Step 4: Run focused and related tests**

Run:
`KIVY_NO_ARGS=1 conda run --no-capture-output -n py311_katago pytest -q tests/platforms/test_golaxy_fixed_screen.py tests/platforms/test_golaxy_9d_alignment_runner.py tests/platforms/test_golaxy_9d_alignment_protocol.py`

Expected: all pass.

- [ ] **Step 5: Format and commit implementation**

Run `black -l 120` on the two Python files and two test files, rerun Step 4, then commit only those files.

## Chunk 2: Predeclare, preflight, and run

### Task 3: Freeze and execute the five-game experiment

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`
- Create at runtime: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_8d_rank_8d_4_20260724/fixed_screen.jsonl`

- [ ] **Step 1: Predeclare the exact run**

Record preset, player, opponent `8段/2800`, B/W/B/W/B, five valid results, cap 9, independent quota ID, output directory, source revision and stop policy in `EXPERIMENTS.md`; commit the Markdown-only change.

- [ ] **Step 2: Run local-only preflight**

Use `conda` environment `py311_katago`, `KIVY_NO_ARGS=1`, base URL `http://127.0.0.1:8000`, `--preflight-only`, the 8D preset and exact output path. Confirm b18/humanv0/PIKL identity and record the configuration fingerprint. This step must not load the Golaxy token or create a quota.

- [ ] **Step 3: Start the live run once**

Use a new quota ID `golaxy8d-rank8d4-20260724-a`, `--confirm-new-quota`, the implementation source revision, and the exact output path. Wrap with `caffeinate`; do not use a new worktree or remote KataGo service.

- [ ] **Step 4: Monitor and stop at five valid results**

Read only the append-only ledger for progress. Do not retry transport/token/429 failures and do not exceed nine reservations. The runner must terminate after five wins/losses regardless of score.

- [ ] **Step 5: Verify and document results**

Assert reservation/result pairing, valid count, colors and fingerprints; compute ledger SHA-256; verify the runner stopped; run the related pytest set and `git diff --check`. Update `EXPERIMENTS.md` with the exact result and commit only the documentation.
