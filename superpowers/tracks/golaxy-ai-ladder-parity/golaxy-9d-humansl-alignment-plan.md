# Golaxy 9D HumanSL Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed harness that adaptively tests corrected `rank_9d` HumanSL tiers against Golaxy 9D, with at most 20 charged attempts per explicitly confirmed quota, then run the first five valid `rank_9d@8` games.

**Architecture:** Keep ordinary rung calibration unchanged. Put deterministic routing and crash-safe accounting in a pure module; put live HTTP behavior in a separate operator CLI that reuses the corrected self-play player factory and selection-aware move function. Launch only from a reviewed clean detached worktree after offline tests and local identity probes.

**Tech Stack:** Python 3.12, asyncio, httpx, pytest, KaTrain ladder helpers, JSON/JSONL, local KataGo HTTP API.

**Spec:** `superpowers/tracks/golaxy-ai-ladder-parity/golaxy-9d-humansl-alignment-design.md`

---

## File map

- Create `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_9d_alignment.py` for the frozen grid, adaptive state machine, strict evidence loading, and quota ledger. It performs no HTTP.
- Create `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py` for CLI/preflight/live-loop behavior.
- Create `tests/platforms/test_golaxy_9d_alignment_protocol.py` for pure protocol, quota, resume, endpoint, and non-monotonicity tests.
- Create `tests/platforms/test_golaxy_9d_alignment_runner.py` for mocked routing, URL, identity, no-retry, source, and color tests.
- Modify `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py` only to expose a strict
  selection/attestation helper while preserving its existing fail-soft wrapper behavior.
- Modify `superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py` only to expose strict referee
  identity failure while preserving the ordinary calibration default.
- Modify `tests/platforms/test_humansl_selfplay.py` and `tests/platforms/test_golaxy_calibration_opponent.py`
  for those backward-compatible strict-helper contracts.
- Modify `superpowers/tracks/golaxy-ai-ladder-parity/calibration/README.md` with operator commands.
- Modify `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md` with preregistration, provenance, and observed results.

Do not modify KataGo, `katrain/core/ladder.py`, production rungs, or ordinary `run_calibration.py` behavior.

## Chunk 1: Pure protocol and quota ledger

### Task 1: Freeze the adaptive state machine

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_9d_alignment.py`
- Create: `tests/platforms/test_golaxy_9d_alignment_protocol.py`

- [ ] **Step 1: Write the failing grid/initial-batch test**

```python
def test_grid_and_initial_batch():
    assert protocol.CANDIDATES == ("rank_9d@1s", "rank_9d@4", "rank_9d@8", "rank_9d@16", "rank_9d@32")
    assert protocol.next_batch({}) == protocol.Batch("rank_9d@8", 5)
```

Also reject `rank_9d@1`, wrong ranks, b28, visits 7/64, and malformed specs.

- [ ] **Step 2: Run RED**

Run: `CI=true KIVY_NO_ARGS=1 .venv/bin/pytest tests/platforms/test_golaxy_9d_alignment_protocol.py -q`

Expected: import failure.

- [ ] **Step 3: Implement constants and immutable results**

```python
PROTOCOL_VERSION = "golaxy-9d-humansl-alignment-v1"
CANDIDATES = ("rank_9d@1s", "rank_9d@4", "rank_9d@8", "rank_9d@16", "rank_9d@32")
START_PLAYER = "rank_9d@8"
GOLAXY_API_LEVEL = 3000
LOCAL_BASE_URL = "http://127.0.0.1:8000"
DAILY_CHARGED_CAP = 20
```

Add frozen `Batch(player, target_conclusive)`, `ProductDecision(measured_tier, product_tier, basis, reason)`,
and `ProtocolStop(reason)` dataclasses. A completed outcome must carry the measured tier, product tier (possibly
`None`), and whether it is direct 10-game evidence or monotonic safety inference; a reason string alone is not
enough for a product decision.

- [ ] **Step 4: Write table-driven failing transition tests**

For every interior candidate: 0–1 wins moves one level higher, 2–3 tops up the same tier to 10, and 4–5 moves lower. At `@1s`, 4–5 tops up to 10. At `@32`, 0–3 tops up to 10. No five-game result may select a product tier.

At 10 valid games test: 6+ wins qualifies; 5–5 aligns and points to the next-higher safety tier; <=4 fails. Test `@32` 5–5 as “aligned/no in-grid safety tier,” `@32` failure as grid exhaustion, and contradictory 10-game failure of the proposed safety tier as `inconclusive_non_monotonic`.

Assert exact returned actions: an interior 6+ win tier next tests its adjacent lower tier when budget/evidence
permits; an interior 5–5 tier next collects the adjacent higher safety tier to 10 when that tier lacks evidence;
an interior failure moves higher. Cover partial totals 1–4 and 6–9, returning the same player's next milestone;
revisiting a previously screened tier; choosing the lowest of multiple qualified tiers; and rejecting unreachable
states such as >10 evidence, losses without a preceding reachable batch, or two simultaneously partial batches.

- [ ] **Step 5: Implement one pure `next_batch(evidence)` function**

Evidence is per-player valid wins/losses plus the ordered completed/active batch history. Return exactly one
`Batch`, `ProductDecision`, or `ProtocolStop`. Use candidate indices; perform no clock, filesystem, or network
access. The transition function must encode the priority “complete active milestone → establish/validate safety
tier → probe adjacent lower cost tier → stop.”

- [ ] **Step 6: Run GREEN and commit**

Run: `CI=true KIVY_NO_ARGS=1 .venv/bin/pytest tests/platforms/test_golaxy_9d_alignment_protocol.py -q`

Expected: PASS.

Commit: `git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_9d_alignment.py tests/platforms/test_golaxy_9d_alignment_protocol.py && git commit -m 'add Golaxy alignment protocol'`

### Task 2: Add durable quota and evidence reconstruction

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_9d_alignment.py`
- Modify: `tests/platforms/test_golaxy_9d_alignment_protocol.py`

- [ ] **Step 1: Write failing quota tests with `tmp_path`**

Test: a new quota needs `confirm_new=True`; existing quotas resume and never reset; reservations have globally monotonic unique IDs; crashed/unknown reservations remain charged; exactly 20 reservations are allowed; a second explicitly confirmed quota starts its own count but continues global IDs; no date-based auto-rollover; malformed/duplicate JSONL or IDs fail closed.

- [ ] **Step 2: Write failing evidence tests**

Before a candidate's first reservation, create and fsync an immutable checkpoint header containing protocol,
source revision, candidate, selection/configuration fingerprint, and schema. Result rows contain `attempt_id`,
`player`, `scheduled_color`, `conclusive`, `our_win`, and the same fingerprint. Inconclusives do not enter
denominators or advance valid color. Ten valid games must be five black/five white. Resume uses cumulative totals.
Fingerprint drift aborts before reservation, including a crash after a reservation but before any result row.

Test unknown attempt IDs, reservation/result candidate/color/quota/fingerprint mismatches, duplicate result
references, and a reservation with no result followed by configuration drift.

- [ ] **Step 3: Run RED**

Run the protocol test file; expect missing ledger/checkpoint APIs.

- [ ] **Step 4: Implement strict append-only storage**

Use strict JSON, canonical SHA-256, append-only JSONL, `flush()` and `os.fsync()`. Expose an experiment-session
cross-process OS-lock context that the CLI holds continuously from batch selection through normal/error exit.
The OS releases it automatically after a crash; never emulate ownership with a durable “active” marker. While
that session lock is held, re-read every quota ledger and checkpoint, choose the unique batch and next valid
color, create/fsync the candidate header if needed, enforce the cap, and atomically append the globally unique
attempt ID together with candidate, color, quota ID, and fingerprint. Never split color selection from
reservation, recycle reservations, or permit `reserve_next_attempt` without the caller's live session lock.

After first creating a ledger/checkpoint/lock-sidecar file, fsync its parent directory as well as the file. Quota
creation records must strictly preserve unique `quota_id`, creation timestamp, and Asia/Shanghai operator date;
resuming a quota may not mutate that metadata. Add concurrent-process contention tests proving only one process
can reserve/run a batch, cannot duplicate global IDs/colors, and cannot bypass the cap.

Required APIs: `experiment_session(session_path)` (context manager), `create_or_resume_quota(...)`,
`load_evidence(...)`, one atomic
`reserve_next_attempt(session, quota_id, expected_batch, expected_fingerprint)` operation that returns the
assigned candidate/color/attempt ID, and
`append_attempt_result(session, reservation, outcome, expected_fingerprint)`. The append API validates the
immutable header and exact attempt/player/color/quota/fingerprint cross-reference, rejects duplicates, appends,
fsyncs, and returns only after durability. `next_conclusive_color(...)` remains a private pure helper called only
while the experiment session is held.

Add a subprocess contention test: a second process is rejected while the first holds the session lock, then can
acquire and resume after the first is terminated abruptly. Test duplicate/mismatched result append rejection and
successful durable append through the public API; Task 5 must not write result JSONL directly.

- [ ] **Step 5: Run GREEN and commit**

Run: `CI=true KIVY_NO_ARGS=1 .venv/bin/pytest tests/platforms/test_golaxy_9d_alignment_protocol.py -q`

Expected: PASS.

Commit: `git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_9d_alignment.py tests/platforms/test_golaxy_9d_alignment_protocol.py && git commit -m 'guard Golaxy alignment quota'`

## Chunk 2: Fail-closed live runner

### Task 3: Construct the corrected HumanSL players

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py`
- Create: `tests/platforms/test_golaxy_9d_alignment_runner.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py`
- Modify: `tests/platforms/test_humansl_selfplay.py`
- Modify: `tests/platforms/test_golaxy_calibration_opponent.py`

- [ ] **Step 1: Write failing player tests**

Assert `rank_9d@8` yields b18, `humansl_search`, humanv0 profile, visits 8, canonical PIKL, and selection `search`. Assert `rank_9d@1s` yields humanv0, mechanism `humansl`, visits 1, empty PIKL, and `argmax_human`. Reject `@1` and every non-grid spec.

- [ ] **Step 2: Run RED**

Run: `CI=true KIVY_NO_ARGS=1 .venv/bin/pytest tests/platforms/test_golaxy_9d_alignment_runner.py -q`

Expected: import failure.

- [ ] **Step 3: Write and run failing strict-helper compatibility tests**

Extend the RED tests to inject runtime wrapper/model/hash/selection/policy failures into
the strict player path and referee identity failures into strict adjudication. Assert typed errors. In the same
tests assert the existing `_player_move` and default `adapters.adjudicate` behavior remains fail-soft. Run the
three-file pytest command from Step 4 and confirm these new assertions fail for the intended missing strict API.

- [ ] **Step 4: Reuse, do not duplicate, player semantics**

Call `run_selfplay.make_player(player, experimental_min_humansl_search_visits=2)` and validate its result against
the grid. Extract a public strict selection helper from `_player_move`: the strict helper raises a typed error for
runtime model/human-model/hash/PIKL/selection/policy drift, while the existing `_player_move` wrapper continues
returning `"unavailable"` for ordinary self-play callers. Likewise add an opt-in strict-identity path to
`adapters.adjudicate`; its default result remains unchanged, but the alignment runner receives a typed stop on
referee identity drift. Test both strict behavior and backward-compatible defaults.

Use the strict player helper so `@1s` remains argmax and `@4+` remains attested PIKL search. Use `get_rung(33)`
only for Golaxy opponent level; never mutate it into our player. Do not use `adapters.our_move` for the
experimental player.

- [ ] **Step 5: Run GREEN and commit**

Run: `CI=true KIVY_NO_ARGS=1 .venv/bin/pytest tests/platforms/test_golaxy_9d_alignment_runner.py tests/platforms/test_humansl_selfplay.py tests/platforms/test_golaxy_calibration_opponent.py -q`

Expected: PASS.

Commit: `git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py tests/platforms/test_golaxy_9d_alignment_runner.py tests/platforms/test_humansl_selfplay.py tests/platforms/test_golaxy_calibration_opponent.py && git commit -m 'construct HumanSL Golaxy players'`

### Task 4: Implement source and local-engine preflight

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py`
- Modify: `tests/platforms/test_golaxy_9d_alignment_runner.py`

- [ ] **Step 1: Write failing URL/source tests**

Accept only exact `http://127.0.0.1:8000`. Reject localhost aliases, other ports, HTTPS, credentials, queries, fragments, trailing slash, redirect, and remote hosts before token/Golaxy access. Live mode requires a full expected revision, clean detached HEAD at it, and output outside that worktree.

- [ ] **Step 2: Write failing semantic-preflight tests**

Mock `/health` and `/analyze`. `@1s` requires humanv0/default identity, verified human hash, valid humanPolicy,
and argmax. `@4+` requires b18+humanv0, verified hashes, exact requested `maxVisits`, canonical nonzero PIKL,
and moveInfos. Do not require `response.rootInfo.visits == maxVisits`: accept a positive plain integer below the
cap (pruning) and up to `requested maxVisits + 7` for the shipped eight search threads; reject boolean, malformed,
zero/negative, or larger reported values. Persist requested and reported visits separately. Reject b28 routing,
missing human model, zero PIKL, wrapper/hash drift, or redirects before Golaxy calls.

Also require verified, distinct, out-of-board smoke pass/resign codes; missing/null/invalid codes fail before live
access. Assert the Golaxy descriptor is exactly API level 3000 and the strict referee configurations are attested
b28 at 200 visits for ordinary adjudication and 800 visits for stability recheck.

- [ ] **Step 3: Run RED**

Run the runner test file; expect preflight failures.

- [ ] **Step 4: Implement strict preflight order**

Common order: args → clean detached source → external output → checkpoints → unique next batch → exact URL →
local capability/semantic probes → strict smoke-code/referee checks. `--preflight-only` stops here: it does not
load a token, create/resume a quota, reserve an attempt, or call Golaxy. Live mode then validates token existence
without printing it and explicitly creates/resumes the requested quota; it still makes no reservation until the
locked game loop.

Add and test `--create-quota-only`: it runs the same common preflight, validates token existence, explicitly
creates/resumes the requested quota, verifies zero attempts when newly created, makes no reservation/Golaxy
call, and exits. Reject combining it with preflight/live/summarize modes.

- [ ] **Step 5: Run GREEN and commit**

Run: `CI=true KIVY_NO_ARGS=1 .venv/bin/pytest tests/platforms/test_golaxy_9d_alignment_runner.py -q`

Expected: PASS.

Commit: `git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py tests/platforms/test_golaxy_9d_alignment_runner.py && git commit -m 'gate live Golaxy alignment runs'`

### Task 5: Implement one resumable batch and zero retries

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py`
- Modify: `tests/platforms/test_golaxy_9d_alignment_runner.py`

- [ ] **Step 1: Write failing loop tests**

Prove the CLI holds `experiment_session()` for its entire run; `reserve_next_attempt()` assigns both ID and color;
valid results use `append_attempt_result()`; inconclusives retain color; resume targets cumulative totals;
summaries separate charged attempts/evidence; a completed batch exits before the next; attempt 21 is blocked
before a live call. Prove every Golaxy request uses level 3000.

Inject runtime player identity/PIKL/selection drift and referee identity drift after a successful preflight. Each
must stop the batch immediately without replenishing the color or starting another Golaxy game. Only genuine
score-settlement/stability ambiguity may append an inconclusive result and replenish the same color.

Add failing `--summarize-only` tests. This mode acquires the experiment session lock, strictly reconstructs all
quota/checkpoint/header/result data, validates fingerprints/cross-references/colors/caps, and emits current
charged/evidence totals plus the unique `Batch`/`ProductDecision`/`ProtocolStop`. It must not access the local
engine, load a token, mutate a quota, reserve an attempt, or call Golaxy.

- [ ] **Step 2: Write failing no-retry tests**

Parameterize AuthExpired, 429/disconnect Retryable, 7002 Fatal, and transport errors. Each permits exactly one Golaxy call, retains the reservation, writes no fake result, and exits non-zero. Never call the ordinary calibration retry helpers.

- [ ] **Step 3: Run RED**

Run the runner tests; expect incomplete-loop failures.

- [ ] **Step 4: Implement the game loop**

Exact flow: acquire `experiment_session()` and hold it through normal/error exit → re-read evidence and derive
the unique batch → call `reserve_next_attempt()` (which assigns candidate, ID, and color atomically) →
`play_one_game` using the strict selection-aware HumanSL helper and direct `adapters.golaxy_move` at level 3000
→ strict b28@200 adjudication and b28@800 stability recheck → `append_attempt_result()` → re-read evidence.
Propagate Golaxy or typed identity errors after redacted logging. Do not write result JSONL directly.

Implement `--summarize-only` as a separate read-only branch before any engine/token setup, using only the public
strict storage/protocol APIs while holding the same session lock.

Fingerprint protocol/source, player/selection version, requested/effective routes, hashes, PIKL, Golaxy level, board/rules/komi, referee, smoke codes, and capability snapshot.

- [ ] **Step 5: Run focused regressions**

Run: `CI=true KIVY_NO_ARGS=1 .venv/bin/pytest tests/platforms/test_golaxy_9d_alignment_protocol.py tests/platforms/test_golaxy_9d_alignment_runner.py tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_humansl_selfplay.py tests/platforms/test_humansl_probe.py tests/core/test_ladder.py tests/core/test_ladder_strategy.py -q`

Expected: PASS with no live network.

- [ ] **Step 6: Commit**

Commit: `git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py tests/platforms/test_golaxy_9d_alignment_runner.py tests/platforms/test_humansl_selfplay.py tests/platforms/test_golaxy_calibration_opponent.py && git commit -m 'run resumable Golaxy alignment batches'`

## Chunk 3: Runbook, verification, and first live batch

### Task 6: Document and preregister

**Files:**
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/README.md`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Add exact operator commands**

Document the grid, cumulative evidence, separate counters, quota creation/resume, exact localhost, preflight-only, summarize-only, no-retry stops, and one-batch exit.

- [ ] **Step 2: Add preregistration**

Record design commit, implementation revision placeholder, `rank_9d@8` to five valid games, Golaxy 3000, charged cap 20, output directory, and that the next batch is derived only after freezing this batch.

- [ ] **Step 3: Check and commit**

Run `git diff --check` and the new runner's `--help`; expect success.

Commit: `git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/README.md superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md && git commit -m 'document Golaxy HumanSL alignment run'`

### Task 7: Verify and review before live access

**Files:**
- No changes except review fixes.

- [ ] **Step 1: Use @superpowers:verification-before-completion**

Run: `CI=true KIVY_NO_ARGS=1 .venv/bin/pytest -q`

Expected: PASS; report intentional GPU skip.

- [ ] **Step 2: Check formatting**

Run Black `--check -l 120` on both new modules, `run_selfplay.py`, `adapters.py`, both new tests,
`test_humansl_selfplay.py`, and `test_golaxy_calibration_opponent.py`, then `git diff --check`; expect PASS.

- [ ] **Step 3: Use @superpowers:requesting-code-review**

Reviewer checks zero retry, no b28/rung-33 substitution for our player, strict/default helper compatibility,
runtime player/referee drift stops, session/quota locking, durable pre-call reservation, fingerprint and result
cross-references, exact localhost, cumulative-color resume, and mutation-free preflight/summarize modes.

- [ ] **Step 4: Fix findings with TDD and repeat**

Expected: reviewer approval and clean full suite.

- [ ] **Step 5: Commit every approved review fix and reverify the exact commit**

Stage only the alignment implementation/tests/docs, commit all approved fixes, require `git status
--porcelain=v1 --untracked-files=no` empty in the implementation worktree, record `git rev-parse HEAD`, and rerun
the full suite and formatting at that exact commit. Do not assign `ALIGNMENT_REV` until this passes.

### Task 8: Pin clean launch source and run local-only preflight

**Files:**
- Runtime output only under the primary repository's `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_9d_humansl_alignment/`.

- [ ] **Step 1: Record approved `ALIGNMENT_REV`**

Run `git rev-parse HEAD`; require a full commit.

- [ ] **Step 2: Use @superpowers:using-git-worktrees**

Create `/tmp/katrain-golaxy9d-alignment-<short-rev>` detached at `ALIGNMENT_REV`; verify exact revision and clean tracked state.

- [ ] **Step 3: Bootstrap Python 3.12**

Install repository/runtime requirements and compile ignored locale `.mo` files with `polib`, following the boundary runbook. Use `.venv/bin/python`.

- [ ] **Step 4: Run `--preflight-only`**

Use exact localhost/revision and external output. Do not create a quota. Require inferred `rank_9d@8`, b18+humanv0+PIKL attestation, search-derived move, and zero Golaxy calls.

- [ ] **Step 5: Freeze provenance**

Put `ALIGNMENT_REV` and the preflight fingerprint in `EXPERIMENTS.md`; commit docs only. Keep launch pinned to `ALIGNMENT_REV`, not this docs commit.

### Task 9: Run only the first five-valid-game batch

**Files:**
- Runtime output: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_9d_humansl_alignment/`
- Modify after completion: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: Reconfirm prerequisites**

Confirm network, local engine, token existence without printing, smoke codes, and still-unused user-confirmed
quota. The live command in Step 3 must run under `caffeinate -dimsu`; verify the `caffeinate` wrapper/process is
active before the first reservation and remains the parent for the full batch.

- [ ] **Step 2: Create the quota explicitly**

From the pinned worktree, set task-specific `ALIGNMENT_REV`, `ALIGNMENT_OUT`, and `ALIGNMENT_QUOTA` values, then
run exactly:

`NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost .venv/bin/python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py --create-quota-only --confirm-new-quota --quota-id "$ALIGNMENT_QUOTA" --base-url http://127.0.0.1:8000 --expected-source-revision "$ALIGNMENT_REV" --out "$ALIGNMENT_OUT"`

Then run exactly:

`.venv/bin/python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py --summarize-only --expected-source-revision "$ALIGNMENT_REV" --out "$ALIGNMENT_OUT"`

Require zero charged attempts plus `rank_9d@8 → target 5 valid`. The create-only command must exit before any
reservation/Golaxy call. Summarize mode omits token, quota creation, base URL, and every Golaxy argument.

- [ ] **Step 3: Run the derived batch only**

Resume that exact existing quota, without `--confirm-new-quota` or `--create-quota-only`, using exactly:

`NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost caffeinate -dimsu .venv/bin/python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py --quota-id "$ALIGNMENT_QUOTA" --base-url http://127.0.0.1:8000 --expected-source-revision "$ALIGNMENT_REV" --out "$ALIGNMENT_OUT"`

The CLI must reject an unknown/different quota ID unless a separate create-only command explicitly confirmed
it. Stop after five valid games or the first Golaxy error/20-attempt cap; never auto-start the next batch.

- [ ] **Step 4: Validate with `--summarize-only`**

Run exactly:

`.venv/bin/python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py --summarize-only --expected-source-revision "$ALIGNMENT_REV" --out "$ALIGNMENT_OUT"`

Verify charged attempts, five valid results if complete, score, 3/2 color split, hashes/fingerprints, and unique
next batch. This command omits token, quota creation, base URL, and every Golaxy argument.

- [ ] **Step 5: Record facts without overclaiming**

Append counts, colors, end reasons, charged attempts, hashes, fingerprint, and next batch to `EXPERIMENTS.md`. Do not claim a 10-game product tier from five games.

- [ ] **Step 6: Commit documentation only**

Commit: `git add superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md && git commit -m 'record first Golaxy HumanSL batch'`

Never commit credentials, mutable locks, large archives, or unrelated dirty files.
