# Golaxy 7D HumanSL `@4` Fixed Screen Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and run a five-valid-game `rank_7d@4` versus Golaxy 7D preset, attempting the fifth game even though only four daily calls are expected to remain.

**Architecture:** Reuse the existing immutable `ScreenSpec` fixed runner and explicit Golaxy opponent seam. Add one data-only preset plus tests; preserve every 8D/9D behavior and use an append-only ledger that can resume after a quota rejection.

**Tech Stack:** Python 3.11, pytest, httpx, existing KaTrain calibration runner, JSONL.

---

## Chunk 1: Preset and live run

### Task 1: Add the exact 7D preset using TDD

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py`
- Test: `tests/platforms/test_golaxy_fixed_screen.py`

- [ ] Add failing tests for preset `golaxy7d-rank7d4-20260724`: player `rank_7d@4`, start B, five valid games,
  charged cap 9, Golaxy rung 29/name `7段`/level 2500, and exact output directory
  `golaxy_7d_rank_7d_4_20260724`.
- [ ] Run focused pytest and confirm the new tests fail because the preset is absent.
- [ ] Add only the immutable `GOLAXY_7D_PRESET` constant and include it in `PRESETS`; do not change shared logic.
- [ ] Run focused plus 8D/9D related tests, format with Black, and commit the two files.

### Task 2: Predeclare and execute

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`
- Create at runtime: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_7d_rank_7d_4_20260724/fixed_screen.jsonl`

- [ ] Predeclare player/opponent, B/W/B/W/B, cap 9, quota ID `golaxy7d-rank7d4-20260724-a`, expected implementation
  revision, output path and the “attempt fifth then stop on quota error” rule; commit Markdown only.
- [ ] Run local-only preflight in conda `py311_katago` against `http://127.0.0.1:8000`; record fingerprint.
- [ ] Launch once with `--confirm-new-quota`, monitor the ledger, and allow the runner to attempt the fifth game.
- [ ] If five results return, verify and document them. If quota rejects the fifth call, verify four valid results plus one unmatched
  reservation, document the stop, and leave the same ledger resumable after quota restoration.
- [ ] Run related tests and `git diff --check`; update and commit `EXPERIMENTS.md`.
