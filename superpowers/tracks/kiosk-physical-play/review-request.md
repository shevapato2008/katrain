# Review Request — Kiosk 物理棋盘对弈（一期）Implementation Plan

**To:** Gemini, Codex (independent technical reviewers)
**From:** fan (via Claude)
**Date:** 2026-07-02
**What I need:** A critical review of the **implementation plan** before we execute it. Find design flaws, missed edge cases, wrong assumptions about the codebase, and places where the task decomposition or the concrete code will not survive contact with reality. Style nitpicks are welcome but secondary — I care most about **correctness, concurrency, and whether the architecture is right**.

---

## How to review

1. Read the three track documents in this directory (in order):
   - `prd.md` — product requirements (what/why, the 6 open questions Q1–Q6)
   - `feasibility.md` — codebase reconnaissance + risk analysis
   - `plan.md` — **the artifact under review**: 15 tasks, TDD, drop-in code for every step
2. The plan targets branch `feature/kiosk-physical-play` (worktree at repo root, based on `develop @ 96e64f53`). You have full repo access — please **verify the plan's claims against the actual code**, not just its prose. The plan cites exact `file:line` refs throughout; several were already found stale-or-wrong during planning (see "Codebase facts" below), so treat every cited line number as "approximately here, grep to confirm."
3. Respond however is easiest for you. Ideal format: a list of findings, each tagged **[Blocker] / [Important] / [Minor]**, with `file:line` or `Task N / Step M` anchors and a concrete suggested fix. If you think the whole architecture is wrong, say so first and loudly.

**Status note:** Task 1 (a one-line-×2 bugfix, see below) is already committed (`bd583d71`) and reviewed-clean. Everything from Task 2 onward is unexecuted and fully open to redesign. Do not assume any code past Task 1 exists yet.

---

## Project in one paragraph

KaTrain is a Go/Baduk app (Python FastAPI backend + React/TS kiosk frontend) that already has, merged on this branch: a **YOLO vision pipeline** (camera → warp → 4-class stone/LED detection → 19×19 board, running as a subprocess worker on SBC / in-process thread on Mac), a **361-LED WS2812 board** driven over serial (`LedService`, authoritative row/col→chain-index LUT on the host), and a **vision→game move-injection path** (`_vision_move_poller` submits camera-confirmed moves into the game like a UI click). This plan turns those capture-tools into a **physical-board playing experience**: you place stones on a real board (vision auto-confirms and injects), and the AI's moves / captures are shown by lighting LEDs on the physical board; the screen becomes a scoreboard + fallback-confirmation panel + AI-hint control. Phase 1 (this plan) = local human-vs-AI (free + ranked). Phase 2 (online lobby) is explicitly out of scope.

---

## Architecture the plan commits to

**One new backend object: `PhysicalPlayOrchestrator`** (`app.state.physical_play`), plus a pure-logic core `LedPlanner`.

- **Reconciliation loop, not event-driven.** Every ~0.5s tick, the orchestrator diffs the *authoritative digital board* (from the latest `game_update` state dict) against the *observed physical board* (from the vision worker), and the difference IS the LED batch:
  - digital stone not yet on the physical board → stone-color guidance lamp (black stone → red LED, white → green LED)
  - stone that must come off (capture / undo) → blue lamp
  - one `set_points` batch mixes colors (LedService batches are clear+set, so mixed-color is native)
- **The only input is the `game_update` state dict.** This is deliberate (PRD R8.1/Q5): a phase-2 remote opponent or a second human produces identical updates, so the physical loop is reused with zero change.
- **Single-slot callback wrapping.** `WebKaTrain.update_state_callback` is a single assignable slot already claimed by `SessionManager`. The orchestrator wraps it at bind time (capture original → call original → then `on_game_state`). Same for driving vision's "expected board" push.
- **Hint = suspend + blink.** AI-hint (选点白灯) suspends both move-detection and reconciliation, blinks white lamps on top-N points via an asyncio task, auto-restores on timeout/dismiss.
- **Vision masking + pause.** New worker commands: pause/resume detection, and a "lit points" set so LED glare on *expected-empty* intersections can't be misread as a stone.

Frontend: a set of `src/kiosk/` components (confirming-chip, mismatch/restore dialog, ambiguous-move card, hint panel, LED-health badge, pose-lost banner) wired into the existing `GamePage`, plus small shared-territory edits (`api.ts`, `useGameSession.ts`).

---

## Adopted decisions (PRD's open questions Q1–Q6)

The user was away when asked, so the plan adopts the PRD's own recommended answers. **All are overridable — flag any you think are wrong:**

- **Q1 (branch/billing):** Hint ships with a **`HintGate` protocol stub** (scene + ranked gate + engine routing only). Real billing (the paid-analysis track on another branch) is deferred; a `BillingHintGate` implements the protocol later. Also: board-mode billing REST currently 503s all balance ops, so local charging is impossible anyway.
- **Q3 (ranked timing):** Move timestamp = **vision-confirmation instant** (current behavior, no code change); UI shows a "确认中" chip.
- **Q4 (AI-stone wait):** **Block the user's next move** until the physical board catches up. Mechanically: the poller *holds* an already-confirmed user move while `board_caught_up == False`, exempts that held point from "extra stone" cleanup lamps, and injects once caught up. A 30s reminder toast nags if the board lags.

---

## Codebase facts the plan rests on (please sanity-check these — the plan lives or dies by them)

These were found during planning by reading the actual source. If any are **wrong**, the dependent tasks are wrong:

1. **[fixed in Task 1]** `session.get_game_state()` didn't exist — both the vision bind endpoint (`vision.py:123`) and the move poller (`server.py:1854`) called it and would `AttributeError`. Correct call is `session.katrain.get_state()`. Already committed.
2. **Two-consumer queue race (Task 2):** the `/ws/vision` handler's `poll_events()` drains ALL worker events and forwards only `dict`s, **silently dropping `ConfirmedMove`** — which the separate `get_confirmed_move()` (move poller) needs. So with the vision websocket open, user moves can vanish. Plan splits into two internal deques via one drain point. **→ Please scrutinize whether this is actually race-free: both `poll_events` and `get_confirmed_move` run in different asyncio tasks and both mutate the shared deques. Is single-threaded-asyncio + no-await-inside-drain sufficient, or is a lock needed? Is there still a lost-wakeup window?**
3. **`game_update` has no capture/prisoner diff** — only the full `stones` list and a running `prisoner_count`. So the planner must diff consecutive boards itself. (`game.last_capture` exists transiently but isn't in the broadcast.)
4. **`update_state_callback` / `message_callback` are single-slot, not lists**, already claimed by `SessionManager` (`session.py:59-60`). Wrapping is the plan's approach.
5. **`ambiguous_stone` and `move_confirmed` are declared enum members that are NEVER emitted** anywhere in vision. The plan *adds* the emission of `ambiguous_stone` (low-confidence move) and a new `move_pending` event (first frame of the 3-frame confirm window, for the "确认中" chip).
6. **New worker commands must be added to BOTH dispatchers** — `worker.py:_process_commands` (SBC subprocess) and `worker_inprocess.py:_drain_commands` (Mac dev thread). `SET_GEOMETRY` is currently handled only in the in-process one — a real divergence bug that's the cautionary precedent.
7. **Ranked games do NOT block undo server-side today** — `analysis_allowed` gates analysis actions only. Plan adds the undo ban (Task 13).
8. **The AI move is generated on a background `threading.Thread`** (`interface.py:_do_ai_move_and_broadcast`), and `update_state_callback` fires from that thread. So `on_game_state` runs off the event loop. **→ Please scrutinize the threading: `on_game_state` stores the state dict and calls `vision.set_expected_from_stones` (a queue put). The tick loop and hint task run on the event loop. Is the shared state (`_latest_state`, planner internals, `_last_points`) safe across the thread/loop boundary?**

---

## Highest-risk areas — please focus here

I'm most uncertain about these. Adversarial scrutiny wanted:

### A. LED idle-failsafe vs. a persistently-lit pending state (I think this is a latent bug)
There's a 5-minute idle failsafe (`server.py:_led_failsafe_loop`) that calls `led.clear()` after 300s without LED activity. The orchestrator drives the LED **directly** (not via the `/led/*` REST endpoints that stamp `led_last_activity`), so it stamps activity itself — but **only inside `_apply_points`, and only when the LED batch changes** (`if points == self._last_points: return` short-circuits before the stamp). Scenario: AI plays, lamp lights, user thinks for >5 min without placing. The batch never changes, so no activity stamp, so the failsafe fires and clears the physical LED. But `_last_points` still holds the AI point, so the next tick's `_apply_points` sees no change and **won't re-send** — the lamp stays dark forever while the user still owes that stone. Q4's whole premise (block until placed) then strands the user with no lit target. **Is my analysis right? If so, what's the cleanest fix — periodic re-assert, stamp every tick while not caught-up, or make the failsafe orchestrator-aware?** (Plan ref: Task 4 `_apply_points` / `_maybe_remind`; Task 6 `touch_led_activity` lambda; feasibility R6.)

### B. Q4 hold-gate — deadlock and UX traps
The poller holds a confirmed user move until `board_caught_up`. Failure modes I want pressure-tested:
- If the board **never** catches up (user refuses to place the AI stone, or vision can't see it), the user's move is held indefinitely and the game stalls. Is "held forever + 30s nag" acceptable, or does this need an escape hatch?
- The plan acknowledges: while holding, if the user places their *own* next stone anyway, after 5 frames it trips `illegal_change` → mismatch dialog telling them to place the AI stone first. Is routing this through the anomaly path the right UX, or should the held state be surfaced more directly?
- `set_exempt_point` takes a single point. Can there legitimately be more than one held/exempt point (e.g., handicap placement, or rapid play)? (Plan ref: Task 6 Step 5 poller rewrite; Task 4 `board_caught_up`/`set_exempt_point`.)

### C. Digital-authority sync rewrite (Task 5) changes existing state-machine semantics
Task 5 adds a `_prev_expected_board` snapshot and reclassifies `_compare_boards` into three buckets (placement-pending / removal-needed / truly-unexpected). This **changes the meaning** of the existing `SyncStateMachine`, which other code (and existing passing tests) depend on. Risks:
- Does the new classification break any existing sync test or real capture-detection behavior the plan didn't foresee? (The plan claims `prev is None` preserves old behavior — verify.)
- The reclassification hinges on `set_expected_board` being called on *every* `game_update` (so `prev` is meaningful). If the orchestrator is absent (vision without orchestrator) or a push is missed, does the machine degrade sanely?
- Interaction with the sticky `CAPTURE_PENDING` state and the 5-frame `illegal_change` debounce. (Plan ref: Task 5; `katrain/vision/sync.py:_compare_boards`.)

### D. Reconciliation timing vs. the 3-frame confirmation lag
The observed board trails reality by the MoveDetector's 3-frame consistency window (~2s on CPU per feasibility R2). The tick loop is 0.5s. So the planner acts on a stale `observed`. Does this cause lamp flicker, premature "caught up," or oscillation between states? Is 0.5s tick vs. ~2s observation latency well-matched, or should the tick be event-driven off vision status changes?

### E. Masking correctness (R7.1)
The plan masks intersections that are **lit AND expected-empty** (so a guidance lamp on an empty point isn't read as a stone). But a *placement-target* lamp is on an expected-**non**-empty point, so it's **not** masked — meaning when the user places the real stone there, the lamp is still lit under/beside it. Does LED glare + a real stone degrade detection at exactly the point we most need to confirm (did the user place the AI stone correctly)? Should the placement lamp extinguish on first detection rather than waiting for 3-frame confirm?

### F. Hint payload reconstruction (Task 8)
`_build_payload_from_game` walks `current_node.parent` to rebuild the move list and reads `root.placements` for handicap. Please verify: does this correctly reconstruct KataGo analysis input for handicap games, mid-game positions, and after undo? Is `Move.from_gtp(gtp).coords` the right decode, and does `is_analysis=True` actually route to the cloud engine (which is `None` in board mode → falls back to local)?

### G. Frontend `mode` plumbing (Tasks 9/12/13)
`GamePage` has **no `mode` route param**; it must infer free-vs-ranked from `gameState.game_type` (which the plan adds to the TS type, claiming the backend already sends it). Verify the backend actually includes `game_type` + `analysis_allowed` in `get_state()`. If it doesn't, the hint-button-hidden-in-ranked and undo-hidden-in-ranked gating silently fails open on the client (server still enforces, but UX breaks).

---

## Task map (for navigation)

| Task | Layer | What | Risk |
|---|---|---|---|
| 1 ✅ | backend | `get_state()` bugfix | done |
| 2 | vision | event-queue race fix | **B/race** |
| 3 | backend | `LedPlanner` pure core | logic |
| 4 | backend | `PhysicalPlayOrchestrator` | **A/threading** |
| 5 | vision | digital-authority sync diff | **C** |
| 6 | backend | lifespan wiring + hold-gate poller | **A/B** |
| 7 | vision | pause/mask/new events (both dispatchers) | fact #6 |
| 8 | backend | hint endpoint + gate + blink | **F** |
| 9 | frontend | types + LED badge (shared `api.ts`) | **G** |
| 10 | frontend | 确认中 chip + reminder toast | — |
| 11 | frontend | mismatch/restore/ambiguous dialogs | UX |
| 12 | frontend | hint button + panel | **G** |
| 13 | backend+fe | ranked undo ban | fact #7 |
| 14 | frontend | pose-lost banner (D2③ hard rule) | — |
| 15 | — | regression gates + on-hardware acceptance | needs SBC |

**Hard rule to respect (PRD D2③, non-negotiable):** LEDs must NEVER auto-flash for geometry/calibration. Any LED-for-geometry is user-button-triggered only. Please flag anything in the plan that could violate this.

---

## Specific questions

1. Is the **reconciliation-loop** the right model, or should this be event-driven off `game_update` + vision events? (The plan chose polling for robustness against dropped events and frontend disconnects.)
2. Is the **Task 2 queue fix** actually race-free, or does it need a lock / different structure?
3. Is the **idle-failsafe bug (§A)** real, and what's the right fix?
4. Is the **Q4 hold-gate (§B)** sound, or is there a deadlock/UX problem that warrants a different approach to "block until placed"?
5. Does the **Task 5 sync rewrite (§C)** risk breaking existing behavior in ways the plan didn't account for?
6. Any **task ordering / dependency** problems? (e.g., Task 4's `_apply_points` calls `vision.set_lit_points` which doesn't exist until Task 7 — the plan guards with `hasattr`; is that the right seam or a smell?)
7. Anything the plan **over-builds** (YAGNI) or **under-specifies** (a step that won't actually work as written)?

Thanks — brutal honesty preferred over politeness.
