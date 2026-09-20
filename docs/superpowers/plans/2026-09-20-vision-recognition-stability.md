# 棋子识别稳定性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the vision pipeline from injecting phantom moves, starving real moves, flipping the colour of already-placed stones, and reporting a briefly-occluded stone as a board mismatch.

**Architecture:** Five independent defences. L0 re-checks the stone is still physically present immediately before the irreversible commit, and closes the cross-platform turn-check gap in the same function. L1 replaces MoveDetector's single "the whole board must show exactly one change" slot with per-cell candidates, so one bad intersection can no longer starve a real move. L2 gives each intersection a reputation counter inside MoveDetector, so a cell that repeatedly lies must clear a higher bar while honest cells keep the low global gate. L3 extends BoardStateExtractor's presence sustain to cover colour, so an established stone cannot change colour on a single frame's misread. L4 splits SyncStateMachine's "a stone is missing" path from its "there is an extra stone" path and puts the missing path on a wall-clock hold.

**Tech Stack:** Python 3.11+, numpy, pytest. No frontend changes. `uv run pytest` for tests, `uv run black -l 120` for formatting.

**Spec:** `docs/superpowers/specs/2026-09-20-vision-recognition-stability-design.md` — read it first; it carries the device measurements every threshold in this plan is derived from.

## Global Constraints

- **Both vision workers must stay in parity.** `katrain/vision/worker.py` (subprocess) and `katrain/vision/worker_inprocess.py` (in-process; **this is the one that actually runs on RK3562**) contain near-identical move-confirmation blocks. Any change to one must be mirrored in the other. Changes that live in `move_detector.py` / `board_state.py` / `sync.py` are shared and need no worker edit — prefer those.
- **No frontend changes in this plan.** Do not touch `katrain/web/ui/**`. No `npm run build` / `npm run build:kiosk-2d` is required.
- **Do not change any global threshold.** `--vision-confidence 0.40`, `--vision-confidence-keep 0.30`, `--vision-ambiguous-confidence 0.42`, `move_confirm_frames=5` all stay exactly as they are. Raising them blocks the weak real stones the low gate exists for (spec §1).
- **Do not touch the RK3562 board.** No ssh, no rsync, no service restart, no deploy. The board is in use. Verification in this plan is local `pytest` only; device acceptance is a separate step the user runs.
- **Formatting:** `uv run black -l 120 katrain tests` before every commit.
- **Test command:** `CI=true uv run pytest <path>` — `CI=true` skips GPU-dependent tests.
- **Comment language:** these four modules are commented in English; keep new comments in English. Explain *why* (with the measured number), not *what*.
- **Never use bare `git stash` / `git stash pop`** — the stash stack is shared with other worktrees and other sessions.
- **Commit message footer** (every commit):
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  ```

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `katrain/vision/service.py` | `get_detected_board()` must read a *fresh* status, not the cached copy | 1 |
| `katrain/web/server.py` | `_handle_confirmed_move`: submit-time presence re-check (L0a) + cross-platform turn guard (L0b) | 1, 2 |
| `katrain/web/interface.py` | new `next_player_to_move()` accessor — the live-game turn authority L0b needs | 2 |
| `katrain/vision/move_detector.py` | per-cell reputation (L2) and per-cell candidates (L1) | 3, 4 |
| `katrain/vision/worker.py` | mirror: suspect-cell ambiguous gate + reputation reset on UNBIND | 3 |
| `katrain/vision/worker_inprocess.py` | mirror: same two edits | 3 |
| `katrain/vision/board_state.py` | colour invariant on established stones (L3) | 5 |
| `katrain/vision/sync.py` | missing/extra decoupling + wall-clock missing hold (L4) | 6 |
| `tests/test_vision_move_poller.py` | L0a + L0b coverage | 1, 2 |
| `tests/test_vision/test_move_detector.py` | L1 + L2 coverage; three existing tests change premise | 3, 4 |
| `tests/test_vision/test_board_state.py` | L3 coverage | 5 |
| `tests/test_vision/test_sync.py` | L4 coverage | 6 |

**Dependency chains (four independent chains — Tasks 1→2, 3→4, 5, 6):**

```
Task 1 (L0a) ──▶ Task 2 (L0b)          server.py, same function
Task 3 (L2)  ──▶ Task 4 (L1)           move_detector.py, same class
Task 5 (L3)                            board_state.py, standalone
Task 6 (L4)                            sync.py, standalone
```

Tasks 1, 3, 5, 6 may start in parallel. Task 2 must wait for Task 1; Task 4 must wait for Task 3.

---

### Task 1: L0a — submit-time presence re-check, gated on a *newer* observation

**Files:**
- Modify: `katrain/vision/ipc.py` (two new fields)
- Modify: `katrain/vision/worker_inprocess.py` (stamp the observation counter)
- Modify: `katrain/vision/worker.py` (mirror)
- Modify: `katrain/vision/service.py:212-214`
- Modify: `katrain/web/server.py` (`_handle_confirmed_move`, insert before `if is_ai_ladder_ranked_session(session):`)
- Test: `tests/test_vision_move_poller.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `WorkerStatus.observation_seq: int = 0` and `ConfirmedMove.observation_seq: int = 0` in `katrain/vision/ipc.py`
  - `VisionService.get_board_observation() -> tuple[list[list[int]] | None, int]`
  - `FakeVision.detected_board` / `FakeVision.observation_seq` / `FakeVision.get_board_observation()` in `tests/test_vision_move_poller.py` — Task 2's tests reuse the same fake.

**Background (do not skip):** the vision worker confirms a move, puts a `ConfirmedMove` on a queue, and `_vision_move_poller` picks it up on its next 0.1s tick and commits it. Measured on RK3562 2026-09-20 that gap is 0.45s median but was **3.02s** for one phantom, whose stone had already vanished from the observed board **1.46s before** submission. Nothing re-read the board in between.

**Why a plain "is the cell empty now?" check is not safe.** `VisionService.refresh_status()` only drains whatever the worker last *published*, and `katrain/vision/worker.py:827` publishes at **1 Hz**. At 8 fps a stone can appear at t=0.25 and finish its five sightings at t=0.75 while the newest published status is still the empty board from t=0.00 — the check would drop a real move, which is exactly what D1 promises it will never do. (`worker_inprocess.py` publishes every loop, so it is much less exposed, but it is not the only worker and the plan must be sound for both.)

So the cancel condition is not "the cell is empty" but **"an observation strictly newer than the one that produced this confirmation shows the cell empty"**. A wall-clock timestamp will not do this job: the two workers are different processes and the comparison must be transport-agnostic. A counter the worker owns and stamps onto both the status and the move is.

- [ ] **Step 1: Write the failing tests**

In `tests/test_vision_move_poller.py`, extend the existing `FakeVision` class (around line 64) — add the lines marked NEW:

```python
class FakeVision:
    def __init__(self):
        self.expected_pushes = []
        self.expected_node_ids = []
        self.detected_board = None  # NEW: None = "no usable observation"
        self.observation_seq = 0  # NEW: which observation `detected_board` came from

    def set_expected_from_stones(self, stones, board_size=19, *, expected_node_id=None):
        self.expected_pushes.append(stones)
        self.expected_node_ids.append(expected_node_id)

    def get_board_observation(self):  # NEW
        return self.detected_board, self.observation_seq
```

Then add this test class at the end of the file:

```python
def _board_with(cells):
    """19x19 vision board (row-major, 0=empty/1=black/2=white) with `cells` set."""
    board = [[0] * 19 for _ in range(19)]
    for (row, col), color in cells.items():
        board[row][col] = color
    return board


def _confirmed(col=3, row=3, color=BLACK, seq=0):
    return ConfirmedMove(col=col, row=row, color=color, observation_seq=seq)


# vision (row=3, col=3) -> katrain coords (col=3, 19-1-3=15). The gateway is called with
# katrain coords, so every "it was submitted" assertion below uses 15, not 3.
SUBMITTED = ("s1", 3, 15)


class TestSubmitTimePresenceRecheck:
    """L0a: confirm -> submit has a real gap (0.45s median, 3.02s measured worst case on
    RK3562 2026-09-20). A stone that vanished during that gap must not be committed.

    Two conditions must BOTH hold to cancel: the board reading is from an observation
    strictly newer than the one that confirmed the move, and the cell is empty in it.
    Anything else — no board, an observation no newer than the confirmation, an
    unreadable board — is "unknown", and unknown always submits. Dropping a real move
    is a worse failure than letting a rare phantom past the other three defences."""

    def test_move_dropped_when_a_newer_observation_shows_the_cell_empty(self):
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = _board_with({})
        vision.observation_seq = 12  # strictly newer than the confirmation below

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=11), log))

        assert delay == 0.5
        assert gateway.calls == []  # never reached the tunnel
        assert vision.expected_pushes  # re-armed so a real stone gets another chance

    def test_stale_observation_never_cancels(self):
        """THE regression this gate exists for: worker.py publishes status at 1 Hz, so
        the newest published board can predate the stone entirely. An observation that
        is not newer than the confirmation proves nothing."""
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = _board_with({})  # empty, but from BEFORE the stone landed
        vision.observation_seq = 11

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=11), log))

        assert gateway.calls == [SUBMITTED]

    def test_move_submitted_when_the_stone_is_still_present(self):
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = _board_with({(3, 3): BLACK})
        vision.observation_seq = 12

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=11), log))

        assert gateway.calls == [SUBMITTED]

    def test_move_submitted_when_there_is_no_observation(self):
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = None
        vision.observation_seq = 99

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=11), log))

        assert gateway.calls == [SUBMITTED]

    def test_wrong_colour_at_the_cell_is_not_a_disappearance(self):
        """Only EMPTY cancels. A stone of the other colour is a colour misread, which the
        turn guard and the colour invariant handle — not a vanished stone."""
        sm = FakeSessionManager({"s1": FakeSession(player_to_move="B")})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()
        vision.detected_board = _board_with({(3, 3): WHITE})
        vision.observation_seq = 12

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _confirmed(seq=11), log))

        assert gateway.calls == [SUBMITTED]
```

`BLACK`, `WHITE` and `ConfirmedMove` are already imported at the top of the file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `CI=true uv run pytest tests/test_vision_move_poller.py::TestSubmitTimePresenceRecheck -v`
Expected: every test errors on the unexpected `observation_seq` keyword to `ConfirmedMove`. Once Step 3 lands, only `test_move_dropped_when_a_newer_observation_shows_the_cell_empty` should still fail — the other four are the regression guards proving the fix does not over-reach.

- [ ] **Step 3: Add the observation counter to the IPC types**

In `katrain/vision/ipc.py`, add one field to each dataclass:

```python
@dataclass
class WorkerStatus:
    """Periodically published by worker to main process."""

    camera_status: str = "disconnected"  # "disconnected" | "connected"
    pose_lock_status: str = "unlocked"  # "unlocked" | "locked"
    sync_state: str = "unbound"  # SyncState value
    mean_confidence: float = 0.0
    detected_board: list[list[int]] | None = None  # 19x19 grid (0=empty, 1=black, 2=white)
    camera_ready: bool = False
    geometry_ready: bool = False
    model_ready: bool = False
    recognition_ready: bool = False
    last_motion_at: float | None = None  # monotonic; lets hint lamps yield when a hand enters
    # Which board observation `detected_board` came from. Consumers compare it against a
    # ConfirmedMove's own observation_seq to tell "a genuinely newer look at the board"
    # from "the last thing this worker happened to publish" — worker.py publishes at 1 Hz,
    # so the newest published board can easily predate a move confirmed since.
    observation_seq: int = 0


@dataclass
class ConfirmedMove:
    """A confirmed move detected by the vision worker."""

    col: int
    row: int
    color: int  # BLACK=1, WHITE=2
    observation_seq: int = 0  # the observation this confirmation was made on
```

- [ ] **Step 4: Stamp the counter in both workers**

In `katrain/vision/worker_inprocess.py`:

(a) In `__init__`, next to `self._last_stable_board: np.ndarray | None = None`, add:

```python
        # Counts board OBSERVATIONS (a frame that produced a stable board), not camera
        # reads or loop iterations. Stamped onto both the published status and every
        # ConfirmedMove so a consumer can tell whether a board reading is newer than the
        # confirmation it is being used to judge.
        self._observation_seq = 0
```

(b) In `_loop`, immediately after `observed_board = stable_board` (the line that ends the voting block), add:

```python
                    self._observation_seq += 1
```

(c) In the bound confirm branch, change `self._event_queue.put(ConfirmedMove(col=col, row=row, color=color))` to:

```python
                                    self._event_queue.put(
                                        ConfirmedMove(
                                            col=col, row=row, color=color, observation_seq=self._observation_seq
                                        )
                                    )
```

(d) In the `WorkerStatus(...)` construction near the end of `_loop`, add the argument:

```python
                observation_seq=self._observation_seq,
```

Apply the identical four edits to `katrain/vision/worker.py` at these exact anchors:
- (a) `worker.py:169`, next to `self._last_stable_board: np.ndarray | None = None`
- (b) `worker.py:356`, immediately after `self._last_detected_board = self._last_stable_board.tolist()`
- (c) `worker.py:475`, the `ConfirmedMove(col=col, row=row, color=color)` construction in its bound branch
- (d) `worker.py:830`, its `WorkerStatus(...)` construction (note it passes `detected_board=self._last_detected_board`, not a local)

**Do not reuse `self._frame_count` in either worker** — it counts camera reads in `worker.py` (`worker.py:271`, incremented right after `read_frame`) and inference frames in `worker_inprocess.py`, so the same name means two different things. A board observation is neither.

- [ ] **Step 5: Expose the observation through the service**

In `katrain/vision/service.py`, replace lines 212-214 with:

```python
    def get_detected_board(self) -> list[list[int]] | None:
        """Return the latest detected board state (19x19 grid).

        Pulls fresh status first. The cached `_latest_status` is only refreshed by
        whoever last touched another status property, so it can be arbitrarily old.
        """
        self.refresh_status()
        return self._latest_status.detected_board

    def get_board_observation(self) -> tuple[list[list[int]] | None, int]:
        """The latest board reading together with the observation it came from.

        The sequence number is what makes a presence check sound: `worker.py` publishes
        status at 1 Hz, so "the newest board we have" can easily predate a move confirmed
        since. Callers must require a sequence strictly greater than the one stamped on
        the ConfirmedMove before treating an empty cell as a disappearance.
        """
        self.refresh_status()
        return self._latest_status.detected_board, int(self._latest_status.observation_seq)
```

- [ ] **Step 6: Add the presence re-check**

In `katrain/web/server.py`, inside `_handle_confirmed_move`, insert this block immediately **after** the `_rearm_unless_terminal` function definition and immediately **before** the line `if is_ai_ladder_ranked_session(session):`:

```python
    # L0a: the stone must still be on the board when we commit. Measured on RK3562
    # 2026-09-20: confirm -> submit is 0.45s median but was 3.02s for the O1 phantom,
    # and that stone had already vanished from the observed board 1.46s before
    # submission — nothing re-read the board in between.
    #
    # Cancelling needs a board reading from an observation STRICTLY NEWER than the one
    # that confirmed this move. worker.py publishes status at 1 Hz, so the newest board
    # we hold can predate the stone entirely; treating that as a disappearance would drop
    # real moves. Everything that is not a newer-and-empty reading — no board, an
    # observation no newer than the confirmation, an unreadable board — is "unknown", and
    # unknown always submits.
    observed_board = None
    observed_seq = 0
    try:
        observed_board, observed_seq = vision.get_board_observation()
    except Exception:  # a status read must never be able to break move submission
        observed_board = None
    if observed_board is not None and observed_seq > int(getattr(move_data, "observation_seq", 0)):
        try:
            still_present = int(observed_board[move_data.row][move_data.col]) != 0
        except (IndexError, TypeError, ValueError):
            still_present = True  # unreadable board == unknown == let it through
        if not still_present:
            log.info(
                "Vision move dropped: observation %d shows no stone at (row=%d,col=%d)",
                observed_seq,
                move_data.row,
                move_data.col,
            )
            _rearm_detection()
            return 0.5
```

- [ ] **Step 7: Run the new tests**

Run: `CI=true uv run pytest tests/test_vision_move_poller.py -v`
Expected: all PASS, including every pre-existing test in the file.

- [ ] **Step 8: Run the regression neighbours**

Run: `CI=true uv run pytest tests/test_vision_move_poller.py tests/test_vision_bind_state.py tests/test_vision tests/test_vision_pump.py -q`
Expected: all PASS. These cover the other consumers of `WorkerStatus`, `ConfirmedMove`, and the move poller. Both new IPC fields have defaults, so no existing construction site needs changing — if one fails, it is asserting on the dataclass shape and must be updated to include the new field rather than the field being removed.

- [ ] **Step 9: Format and commit**

```bash
uv run black -l 120 katrain tests
git add katrain/vision/ipc.py katrain/vision/service.py katrain/vision/worker.py katrain/vision/worker_inprocess.py katrain/web/server.py tests/test_vision_move_poller.py
git commit -m "$(cat <<'EOF'
fix vision: re-check the stone is still present before committing a confirmed move

Confirm -> submit is 0.45s median on RK3562 but was measured at 3.02s, and one
phantom stone had vanished 1.46s before it was sent to the remote platform.
Nothing re-read the board in that window.

The check is gated on an observation sequence rather than just "is the cell empty
now": worker.py publishes status at 1 Hz, so the newest board reading we hold can
predate the stone entirely, and treating that as a disappearance would drop real
moves. Only a strictly newer observation showing the cell empty cancels.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: L0b — cross-platform turn guard

**Files:**
- Modify: `katrain/web/interface.py` (add `next_player_to_move`, next to `get_sgf` / other public accessors)
- Modify: `katrain/web/server.py` (`_handle_confirmed_move`, platform branch)
- Test: `tests/test_vision_move_poller.py`

**Interfaces:**
- Consumes: `FakeVision.get_board_observation()` from Task 1. (Earlier drafts said `get_detected_board()` — that is the *real* `VisionService` method name, not anything Task 1 puts on the fake.)
- Produces: `WebKaTrain.next_player_to_move() -> str | None` returning `"B"`, `"W"`, or `None`.

**Background (do not skip):** `_handle_confirmed_move` checks the turn against `session.last_state`, and the code's own comment at the local branch says that is *"可能过期的广播帧"* (a possibly-stale broadcast frame) and that *"真正的判别在对局提交锁里"* (the real adjudication happens inside the commit lock). That real adjudication is `guard=True, expected_player=move_player` — and it only exists on the **local** branch (`else`). The cross-platform branch passes the stale check and goes straight to `gateway.play_move`. The gateway serialises (`ctx.is_pending`) and checks legality (`_check_move_legal`) but never re-checks whose turn it is.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_vision_move_poller.py`. First give `FakeKatrain` the new accessor — add the two lines marked NEW to the existing class (around line 26):

```python
class FakeKatrain:
    def __init__(self, player_to_move="B"):
        self.plays = []
        self.live_player_to_move = player_to_move  # NEW: the *live* game's turn
        self._state = {
            "stones": [],
            "board_size": [19, 19],
            "player_to_move": player_to_move,
            "current_node_id": 5150,
        }

    def get_state(self):
        return self._state

    def next_player_to_move(self):  # NEW
        return self.live_player_to_move

    def __call__(self, command, coords=None, **kwargs):
        if command == "play":
            self.plays.append(coords)
```

Then add this test class at the end of the file:

```python
class TestPlatformTurnGuard:
    """L0b: the turn check at the top of _handle_confirmed_move reads
    session.last_state, which the code's own comment calls a possibly-stale
    broadcast frame. The local branch re-checks inside the commit lock via
    guard=True/expected_player; the cross-platform branch had no equivalent, so a
    move could reach the remote tunnel on a turn that had already passed."""

    def test_stale_broadcast_does_not_let_a_late_move_reach_the_tunnel(self):
        session = FakeSession(player_to_move="B")  # broadcast frame still says B
        session.katrain.live_player_to_move = "W"  # but the live game has moved on
        sm = FakeSessionManager({"s1": session})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()

        delay = asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(color=BLACK), log))

        assert delay == 0.5
        assert gateway.calls == []
        assert vision.expected_pushes  # re-armed

    def test_live_turn_agreeing_still_submits(self):
        session = FakeSession(player_to_move="B")
        session.katrain.live_player_to_move = "B"
        sm = FakeSessionManager({"s1": session})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(col=3, row=3, color=BLACK), log))

        assert gateway.calls == [SUBMITTED]  # katrain coords: row 3 flips to 19-1-3=15

    def test_unavailable_live_turn_does_not_block(self):
        """No game yet / accessor missing -> None -> fall back to the existing behaviour
        rather than refusing every move."""
        session = FakeSession(player_to_move="B")
        session.katrain.live_player_to_move = None
        sm = FakeSessionManager({"s1": session})
        gateway = FakeGateway()
        app = _app(sm, gateway=gateway)
        vision = FakeVision()

        asyncio.run(_handle_confirmed_move(app, vision, "s1", _move(col=3, row=3, color=BLACK), log))

        assert gateway.calls == [SUBMITTED]  # katrain coords: row 3 flips to 19-1-3=15
```

- [ ] **Step 2: Run tests to verify the first one fails**

Run: `CI=true uv run pytest tests/test_vision_move_poller.py::TestPlatformTurnGuard -v`
Expected: `test_stale_broadcast_does_not_let_a_late_move_reach_the_tunnel` FAILS (the move reaches the tunnel, so `gateway.calls == [SUBMITTED]` and `delay == 0.0`). The other two PASS.

- [ ] **Step 3: Add the live-turn accessor**

In `katrain/web/interface.py`, add this method to `WebKaTrain` (place it directly above `_do_play`, around line 1438):

```python
    def next_player_to_move(self) -> str | None:
        """The colour the LIVE game expects next ("B"/"W"), or None if there is no game yet.

        Same authority `_do_play`'s `expected_player` guard uses
        (`current_node.next_player`). Exposed so the cross-platform vision path can
        re-check the turn against the live game instead of `session.last_state`, which
        is a broadcast frame and can be stale by the time a confirmed move is committed.
        """
        game = self.game
        node = game.current_node if game is not None else None
        return node.next_player if node is not None else None
```

- [ ] **Step 4: Guard the platform branch**

In `katrain/web/server.py`, inside `_handle_confirmed_move`, find the platform branch:

```python
    gateway = getattr(app.state, "platform_gateway", None)
    if gateway and (gateway.is_platform_game(session_id) or is_platform_engine_session(session)):
        game_id = gateway.get_game_id(session_id) or ""
```

Insert this block between the `if gateway and (...)` line and the `game_id = ...` line:

```python
        # L0b: the `expected_player` check above reads session.last_state — a broadcast
        # frame that can be stale by now. The local branch re-adjudicates inside the
        # commit lock (guard=True/expected_player); this branch had no equivalent, and
        # the gateway only serialises (ctx.is_pending) and checks legality. Re-read the
        # live game. None (no game yet) falls through rather than refusing everything.
        live_turn = None
        try:
            with session.lock:
                live_turn = session.katrain.next_player_to_move()
        except Exception:  # a turn read must never be able to break move submission
            live_turn = None
        if live_turn is not None and live_turn != move_player:
            log.info(
                "Vision move %s out of turn at commit (live turn %s) — ignored",
                move_player,
                live_turn,
            )
            _rearm_detection()
            return 0.5
        game_id = gateway.get_game_id(session_id) or ""
```

(Delete the now-duplicated original `game_id = gateway.get_game_id(session_id) or ""` line.)

- [ ] **Step 5: Run the tests**

Run: `CI=true uv run pytest tests/test_vision_move_poller.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the regression neighbours**

Run: `CI=true uv run pytest tests/test_vision_move_poller.py tests/web_ui -q`
Expected: all PASS. `tests/web_ui` covers `WebKaTrain`; the new accessor must not disturb it.

- [ ] **Step 7: Format and commit**

```bash
uv run black -l 120 katrain tests
git add katrain/web/interface.py katrain/web/server.py tests/test_vision_move_poller.py
git commit -m "$(cat <<'EOF'
fix vision: re-check the live turn before sending a move to a remote platform

The turn check in _handle_confirmed_move reads session.last_state, which the
code's own comment calls a possibly-stale broadcast frame, and says the real
adjudication happens inside the commit lock. That adjudication only existed on
the local branch. The cross-platform branch went straight to the tunnel.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: L2 — per-cell reputation

> **AMENDED 2026-09-21 — read this before using any code below.** Task 3 shipped as written
> (`b882e99e`) and was then amended (`917c3e98`) after review: the **suspect frame-count
> multiplier and the `SUSPECT_REQUIRED_FRAMES_FACTOR` constant were deleted.** The multiplier
> gated `detect_new_move`'s return value, which sits upstream of BOTH auto-play and the manual
> confirmation card — so a suspect cell could produce nothing at all, turning a recoverable
> situation into a silent lost move (failure F2, manufactured by the fix for F1). L2's whole
> enforcement is now the ambiguous **routing** gate: a suspect cell still confirms on the normal
> count and always reaches the user; it just never auto-plays. The text below therefore still
> mentions the constant in several places — those are historical, not instructions.


**Files:**
- Modify: `katrain/vision/move_detector.py`
- Modify: `katrain/vision/worker_inprocess.py` (two edits: ambiguous gate, UNBIND reset)
- Modify: `katrain/vision/worker.py` (mirror of the same two edits)
- Test: `tests/test_vision/test_move_detector.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces, on `MoveDetector`:
  - `suspicion_of(row: int, col: int) -> int`
  - `is_suspect(row: int, col: int) -> bool`
  - `reset_suspicion() -> None`
  - module constants `SUSPICION_ABANDON`, `SUSPICION_THRESHOLD`, `SUSPICION_DECAY_FRAMES`, `SUSPECT_REQUIRED_FRAMES_FACTOR`, `SUSPECT_CONFIDENCE_BONUS`
  - Task 4 relies on `self._suspicion`, `self._frame_index` and `self._penalize(cell, points)` existing.

**Background (do not skip):** vision `(18,13)` produced 69 candidate flashes across three processes on 2026-09-20 (405 seconds lit) and was auto-confirmed twice at 0.50–0.57 confidence, while the device's global add gate sits at 0.40 and its ambiguous gate at 0.42. Raising those globals would have blocked it — and would equally have blocked the genuinely weak stones the low gates exist for (one such stone never entered its game all day). So the penalty must be **per cell**.

**One signal only**, fully observable inside `MoveDetector`, no IPC: **abandoned** — a cell became a pending candidate and then vanished without confirming (`+1`). This is what `(18,13)` did 69 times. **The clause that used to follow here — "and it is exactly what a real stone never does" — is FALSE, see the amendment banner above and spec D4.** `MoveDetector`'s own class docstring says why `miss_grace` exists: a weak but real stone oscillating near the keep gate produces this exact signal. Abandonment is a *suspicion* signal, not proof; that is why L2 may only raise the routing bar, never the confirmation frame count.

**A "the same cell confirmed twice in a short window" signal was considered and rejected.** The class docstring's caller-owned-baseline contract deliberately makes an *unactioned* confirmation re-fire every `consistency_frames` — that is how a real stone below the ambiguous gate keeps asking the user instead of being lost forever. Penalising repeats would therefore charge a legitimate weak stone every few frames while decay removes one point per 300 frames, so its score runs away and the raised gate blocks it permanently even after its confidence improves. The abandonment signal alone already fires 69 times for the measured false-positive point, so the second signal buys little and costs a real-move regression.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_vision/test_move_detector.py`:

```python
from katrain.vision.move_detector import (  # widen the module-level import at test_move_detector.py:3
# NOTE: that line is currently just `from katrain.vision.move_detector import MoveDetector`.
# AmbiguousPromoter / PendingConfidencePeak are imported LOCALLY inside two test methods
# (~:128 and ~:196), not at module level. Widen line 3 to the list below and leave those
# local imports alone.
    AmbiguousPromoter,
    MoveDetector,
    PendingConfidencePeak,
    SUSPECT_REQUIRED_FRAMES_FACTOR,
    SUSPICION_THRESHOLD,
)


class TestCellReputation:
    """L2: a cell that repeatedly produces candidates which never become real moves
    must clear a higher bar. Measured on RK3562 2026-09-20: vision (18,13) flashed 69
    times across 3 processes (405s lit) and was auto-confirmed twice at 0.50-0.57,
    while the global add gate was 0.40. Raising the global gate would also have blocked
    the weak real stones it exists for — so the penalty is per-cell."""

    def _boards(self):
        empty = np.zeros((19, 19), dtype=int)
        flashed = empty.copy()
        flashed[18][13] = WHITE
        return empty, flashed

    def _flash_once(self, d, empty, flashed, miss_grace):
        """One appear-then-vanish cycle: seen once, then absent past the grace."""
        d.detect_new_move(flashed)
        for _ in range(miss_grace + 1):
            d.detect_new_move(empty)

    def test_abandoned_candidate_accrues_suspicion(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        assert d.suspicion_of(18, 13) == 0

        self._flash_once(d, empty, flashed, miss_grace=2)
        assert d.suspicion_of(18, 13) == 1

    def test_repeated_flashing_makes_the_cell_suspect(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(SUSPICION_THRESHOLD):
            self._flash_once(d, empty, flashed, miss_grace=2)
        assert d.is_suspect(18, 13)

    def test_suspect_cell_needs_more_frames_to_confirm(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(SUSPICION_THRESHOLD):
            self._flash_once(d, empty, flashed, miss_grace=2)
        assert d.is_suspect(18, 13)

        # 3 frames used to be enough; a suspect cell now needs 3 * FACTOR.
        needed = 3 * SUSPECT_REQUIRED_FRAMES_FACTOR
        for _ in range(needed - 1):
            assert d.detect_new_move(flashed) is None
        assert d.detect_new_move(flashed) == (18, 13, WHITE)

    def test_an_honest_cell_is_never_penalised(self):
        """A real stone appears and confirms — it never appears-then-vanishes."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = np.zeros((19, 19), dtype=int)
        stone = empty.copy()
        stone[3][3] = BLACK
        d.detect_new_move(empty)
        d.detect_new_move(stone)
        d.detect_new_move(stone)
        assert d.detect_new_move(stone) == (3, 3, BLACK)
        assert d.suspicion_of(3, 3) == 0
        assert not d.is_suspect(3, 3)

    def test_an_unactioned_confirmation_is_never_penalised_for_re_firing(self):
        """The caller-owned-baseline contract makes an unactioned confirmation re-fire on
        purpose (a weak real stone waiting on the user's confirmation card). Charging
        those repeats would run the score away and block the stone permanently."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(6):  # two full confirmation windows, nothing actioned in between
            d.detect_new_move(flashed)
        assert d.suspicion_of(18, 13) == 0
        assert not d.is_suspect(18, 13)

    def test_reset_suspicion_clears_everything(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(SUSPICION_THRESHOLD):
            self._flash_once(d, empty, flashed, miss_grace=2)
        assert d.is_suspect(18, 13)

        d.reset_suspicion()
        assert d.suspicion_of(18, 13) == 0

    def test_force_sync_does_not_clear_suspicion(self):
        """force_sync runs on every expected-board push (several times a second).
        Clearing there would mean the counter never accumulates."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, flashed = self._boards()
        d.detect_new_move(empty)
        for _ in range(SUSPICION_THRESHOLD):
            self._flash_once(d, empty, flashed, miss_grace=2)
        d.force_sync(empty)
        assert d.is_suspect(18, 13)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `CI=true uv run pytest tests/test_vision/test_move_detector.py::TestCellReputation -v`
Expected: collection error — `ImportError: cannot import name 'SUSPECT_REQUIRED_FRAMES_FACTOR'`.

- [ ] **Step 3: Add the reputation state and constants**

In `katrain/vision/move_detector.py`, after the `from katrain.vision.board_state import EMPTY` import, add:

```python
# --- per-cell reputation -----------------------------------------------------
# Measured on RK3562 2026-09-20: vision (18,13) produced 69 candidate flashes across
# 3 processes (405 seconds lit) and was auto-confirmed twice at 0.50-0.57 confidence,
# while the device's global add gate was 0.40 and its ambiguous gate 0.42. Raising
# those globals would have blocked it — and would equally have blocked the genuinely
# weak stones the low gates exist for (one real stone never entered its game all day).
# So the extra bar is charged per intersection, to the ones that have actually lied.
# Only ONE signal is charged: a candidate that appeared and then ran out of miss grace
# without confirming. A "confirmed twice in a short window" signal was deliberately NOT
# added — the caller-owned-baseline contract makes an unactioned confirmation re-fire on
# purpose, so penalising repeats would condemn a legitimate weak stone that is waiting on
# the user's confirmation card.
SUSPICION_ABANDON = 1  # became a candidate, then vanished without confirming
SUSPICION_THRESHOLD = 3  # at or above this, the cell is suspect
SUSPICION_DECAY_FRAMES = 300  # every N frames every cell loses a point — nothing is condemned forever
SUSPECT_REQUIRED_FRAMES_FACTOR = 2  # a suspect cell must persist this many times longer
SUSPECT_CONFIDENCE_BONUS = 0.25  # ...and clear this much more ambiguous gate (applied by the workers)
```

In `MoveDetector.__init__`, after `self.misses = 0`, add:

```python
        self._suspicion: dict[tuple[int, int], int] = {}
        self._frame_index = 0
```

Add these methods to `MoveDetector` (place them above `force_sync`):

```python
    def _penalize(self, cell: tuple[int, int], points: int) -> None:
        self._suspicion[cell] = self._suspicion.get(cell, 0) + points

    def _decay_suspicion(self) -> None:
        """Every cell loses one point, every SUSPICION_DECAY_FRAMES frames.

        Frames, not wall-clock: what is being decayed is "how many chances has this
        cell had to lie", which is counted in observations. (Contrast the missing-stone
        hold in SyncStateMachine, which measures real elapsed occlusion and therefore
        must use wall-clock.)
        """
        for cell in list(self._suspicion):
            if self._suspicion[cell] <= 1:
                del self._suspicion[cell]
            else:
                self._suspicion[cell] -= 1

    def suspicion_of(self, row: int, col: int) -> int:
        """Accumulated evidence that this intersection produces candidates that are not moves."""
        return self._suspicion.get((row, col), 0)

    def is_suspect(self, row: int, col: int) -> bool:
        return self.suspicion_of(row, col) >= SUSPICION_THRESHOLD

    def reset_suspicion(self) -> None:
        """Clear all reputation state — session UNBIND only.

        Deliberately NOT called from force_sync: force_sync runs on every
        expected-board push (several times a second while the engine streams), so
        clearing there would mean the counter could never accumulate.
        """
        self._suspicion.clear()
```

- [ ] **Step 4: Wire the signals into `detect_new_move`**

In `katrain/vision/move_detector.py`, make four edits inside `detect_new_move`.

(a) At the very top of the method body, before the `if self.prev_board is None:` check:

```python
        self._frame_index += 1
        if self._frame_index % SUSPICION_DECAY_FRAMES == 0:
            self._decay_suspicion()
```

(b) In the `len(diff_positions) == 0` branch, penalise the abandoned candidate:

```python
        if len(diff_positions) == 0:
            if self.pending_move is not None:
                self.misses += 1
                if self.misses > self.miss_grace:
                    self._penalize((self.pending_move[0], self.pending_move[1]), SUSPICION_ABANDON)
                    self.count = 0
                    self.pending_move = None
                    self.misses = 0
            return None
```

(c) When a different cell displaces the pending one, the old one was abandoned too:

```python
        move = diff_positions[0]
        if move == self.pending_move:
            self.count += 1
            self.misses = 0
        else:
            if self.pending_move is not None:
                self._penalize((self.pending_move[0], self.pending_move[1]), SUSPICION_ABANDON)
            self.pending_move = move
            self.count = 1
            self.misses = 0
```

(d) Apply the suspect bar:

```python
        needed = self.consistency_frames if required_frames is None else max(1, int(required_frames))
        if self.is_suspect(move[0], move[1]):
            needed *= SUSPECT_REQUIRED_FRAMES_FACTOR
        if self.count >= needed:
            # Baseline deliberately NOT advanced (see class docstring): the caller
            # force_syncs once the move is actually accepted downstream.
            self.count = 0
            self.pending_move = None
            self.misses = 0
            return move
```

- [ ] **Step 5: Run the new tests and the whole module's tests**

Run: `CI=true uv run pytest tests/test_vision/test_move_detector.py -v`
Expected: all PASS, including every pre-existing test — in particular `test_unactioned_confirm_refires`, which pins the contract that a re-firing confirmation must stay free of charge.

- [ ] **Step 6: Raise the ambiguous gate for suspect cells (both workers)**

In `katrain/vision/worker_inprocess.py`, extend the existing move_detector import (line ~34):

```python
from katrain.vision.move_detector import (
    AmbiguousPromoter,
    MoveDetector,
    PendingConfidencePeak,
    SUSPECT_CONFIDENCE_BONUS,
)
```

Then around line 471, replace:

```python
                                if conf < self._ambiguous_confidence:
```

with:

```python
                                # A cell with a track record of lying must clear a
                                # higher bar before it may auto-play; it can still
                                # reach the user via the confirmation card.
                                ambiguous_gate = self._ambiguous_confidence
                                if self._move_detector.is_suspect(row, col):
                                    ambiguous_gate = min(0.95, ambiguous_gate + SUSPECT_CONFIDENCE_BONUS)
                                if conf < ambiguous_gate:
```

and in the `logger.info(...)` call immediately below it, replace the argument `self._ambiguous_confidence,` with `ambiguous_gate,`.

Apply the **identical** three edits to `katrain/vision/worker.py` (import at line **44** — not ~34 — gate at line 423, log argument at line 438).

- [ ] **Step 7: Reset reputation on UNBIND (both workers)**

In `katrain/vision/worker_inprocess.py`, in the `elif cmd.action == CommandType.UNBIND:` block, add after `self._promoter.reset()`:

```python
                self._move_detector.reset_suspicion()  # a new session starts every cell at zero
```

Apply the identical edit to the `UNBIND` block in `katrain/vision/worker.py`.

- [ ] **Step 8: Run the worker tests**

Run: `CI=true uv run pytest tests/test_vision -q`
Expected: all PASS.

- [ ] **Step 9: Format and commit**

```bash
uv run black -l 120 katrain tests
git add katrain/vision/move_detector.py katrain/vision/worker.py katrain/vision/worker_inprocess.py tests/test_vision/test_move_detector.py
git commit -m "$(cat <<'EOF'
fix vision: charge a per-cell bar to intersections that repeatedly produce non-moves

Vision (18,13) produced 69 candidate flashes across 3 processes on RK3562
2026-09-20 (405s lit) and auto-confirmed twice at 0.50-0.57, under a global add
gate of 0.40. Raising the global gate would equally have blocked the weak real
stones the low gate exists for. One signal the detector can already observe — a
candidate abandoned without ever confirming — now raises that cell's required
frames and ambiguous gate, decaying back to zero over time and cleared entirely
on UNBIND.

A second signal ("the same cell confirmed twice in a short window") was
considered and rejected: the caller-owned-baseline contract deliberately re-fires
an unactioned confirmation every consistency_frames, so penalising repeats would
charge a legitimate weak stone every few frames while decay removes one point per
300 frames — running its score away and blocking it permanently.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: L1 — per-cell candidates (stop one bad point starving a real move)

**Files:**
- Modify: `katrain/vision/move_detector.py`
- Test: `tests/test_vision/test_move_detector.py`

**Interfaces:**
- Subsumes: Task 3's edit (c) — the "a different cell displaced the pending one, so the old one was abandoned" penalty — disappears, because with per-cell candidates nothing displaces anything. The `SUSPICION_ABANDON` penalty moves into the aging loop below and is charged on exactly the same event (a candidate that ran out of grace). No Task 3 test depends on the displacement path; they all go through the empty-board aging path.
- Consumes: `self._suspicion`, `self._frame_index`, `self._penalize`, `is_suspect` and the `SUSPICION_*` / `SUSPECT_*` constants from Task 3.
- Accepted limitation: `PendingConfidencePeak` still tracks only one cell, so a non-leading candidate accumulates no confidence peak and, if it later becomes the leader, starts its peak from scratch. That costs it the fast path for a window — i.e. it confirms *more* slowly, never more readily — so the direction is fail-safe and no worker change is needed here.
- Produces: `MoveDetector.pending_move` and `MoveDetector.count` become **read-only properties** over the leading candidate. `MoveDetector(disruption_threshold=...)` is a new constructor keyword (default 4). Nothing outside the class assigns to `pending_move`/`count` today (`worker.py` and `worker_inprocess.py` only read them) — leaving the properties setter-less is deliberate, so any missed assignment site raises instead of silently passing.

**Background (do not skip):** `detect_new_move` currently builds a whole-board diff and hard-resets all state when `len(diff_positions) > 1`. That makes **the whole board** the criterion for whether *your* move counts: one bad intersection anywhere — even one nowhere near where you played — starves every real move. Measured on RK3562 2026-09-20: one real stone never entered its game at all (zero `move confirmed` lines for its cell, all day), and another took 71 seconds and only landed because the user pressed "adopt as my move" in a dialog. The persistent phantom that did the starving was on the other side of the board.

Replacing the single pending slot with per-cell candidates fixes it: a phantom flickers, so its streak keeps breaking; a real stone persists, so its streak accumulates and it confirms regardless of what else is on the board. The hard reset is kept for genuine scene disruption (a hand sweeping across, the board being moved), which is what `disruption_threshold` is for.

- [ ] **Step 1: Rewrite the three tests whose premise this task changes**

Two existing tests assert the starvation behaviour as if it were correct, and one no longer exercises what it claims. Replace them — do not delete them.

In `tests/test_vision/test_move_detector.py`, replace `test_resets_count_on_change` (line 30, in class `TestMoveDetector`) with:

```python
    def test_an_unrelated_cell_no_longer_destroys_a_real_candidate(self):
        """Premise changed by L1. This test used to assert that a diff at ANOTHER cell
        restarts the real stone's count — that was the starvation bug: on RK3562
        2026-09-20 a real stone never entered its game at all because a phantom
        elsewhere kept resetting the shared counter. Each cell now counts for itself,
        and an absent frame is merely a miss (within miss_grace)."""
        detector = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = np.zeros((19, 19), dtype=int)
        detector.detect_new_move(empty)

        with_stone = empty.copy()
        with_stone[3][3] = BLACK

        detector.detect_new_move(with_stone)  # (3,3) count=1
        detector.detect_new_move(with_stone)  # (3,3) count=2
        different = empty.copy()
        different[5][5] = WHITE
        detector.detect_new_move(different)  # (3,3) absent once — graced, not reset
        assert detector.detect_new_move(with_stone) == (3, 3, BLACK)  # count=3 -> confirms
```

Replace `test_multi_stone_change_still_hard_resets` (line 232, in class `TestMoveDetectorMissGrace` — both replacements stay in that class, which is where `self._boards()` is defined) with:

```python
    def test_two_cell_change_no_longer_hard_resets(self):
        """Premise changed by L1. Two diffs is the common phantom-beside-a-real-stone
        case, not scene disruption — the real stone must still be able to confirm."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty, with_stone = self._boards()
        two = with_stone.copy()
        two[5][5] = WHITE
        d.detect_new_move(empty)
        d.detect_new_move(with_stone)  # (3,3) count=1
        d.detect_new_move(with_stone)  # (3,3) count=2
        assert d.detect_new_move(two) == (3, 3, BLACK)  # count=3 -> confirms despite (5,5)

    def test_scene_disruption_still_hard_resets(self):
        """Four or more simultaneous diffs IS scene disruption (a hand sweeping across,
        the board being moved) — everything is abandoned, as before."""
        d = MoveDetector(consistency_frames=3, miss_grace=2, disruption_threshold=4)
        empty, with_stone = self._boards()
        many = with_stone.copy()
        many[5][5] = WHITE
        many[6][6] = BLACK
        many[7][7] = WHITE
        d.detect_new_move(empty)
        d.detect_new_move(with_stone)  # count=1
        d.detect_new_move(with_stone)  # count=2
        d.detect_new_move(many)  # 4 diffs -> hard reset
        assert d.detect_new_move(with_stone) is None  # count=1 again
        assert d.detect_new_move(with_stone) is None
        assert d.detect_new_move(with_stone) == (3, 3, BLACK)
```

- [ ] **Step 2: Write the new failing tests**

Add this class to `tests/test_vision/test_move_detector.py`:

```python
class TestPerCellCandidates:
    """L1: the criterion for "does this move count" must be the candidate cell's own
    evidence, not the whole board's. Measured on RK3562 2026-09-20: a persistent
    phantom on one edge point kept every real move from ever accumulating enough
    consecutive whole-board-clean frames — one real stone never entered its game."""

    def _empty(self):
        return np.zeros((19, 19), dtype=int)

    def test_a_second_changed_cell_no_longer_blocks_a_real_stone(self):
        """THE regression. Under the old `len(diff_positions) > 1` rule, frames 2 and 3
        below each hard-reset everything, so the real stone could never reach 3."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)

        real = empty.copy()
        real[2][10] = WHITE  # the user's stone
        both = real.copy()
        both[18][13] = WHITE  # a phantom lights up on the far edge mid-window

        d.detect_new_move(real)  # real=1
        d.detect_new_move(both)  # real=2, phantom=1
        assert d.detect_new_move(both) == (2, 10, WHITE)  # real=3 confirms; phantom only at 2

    def test_flickering_phantom_loses_its_streak_while_a_real_stone_keeps_its_own(self):
        d = MoveDetector(consistency_frames=3, miss_grace=0)
        empty = self._empty()
        d.force_sync(empty)

        real = empty.copy()
        real[2][10] = WHITE
        both = real.copy()
        both[18][13] = WHITE

        d.detect_new_move(both)  # real=1, phantom=1
        d.detect_new_move(real)  # real=2, phantom absent past grace 0 -> dropped
        assert d.detect_new_move(both) == (2, 10, WHITE)  # real=3 confirms; phantom back at 1

    def test_exact_tie_confirms_nothing(self):
        """Two stones appearing on the SAME frame and advancing in lockstep is genuine
        ambiguity, not a phantom beside a real stone — emit nothing (unchanged)."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = self._empty()
        d.detect_new_move(empty)
        two = empty.copy()
        two[3][3] = BLACK
        two[4][4] = WHITE
        for _ in range(5):
            assert d.detect_new_move(two) is None

    def test_the_older_candidate_wins_a_streak_tie(self):
        """Equal streaks, different first-seen frames -> the one that has been waiting
        longer goes first (FIFO), so a real stone placed before a phantom appeared is
        never queued behind it. The real stone blinks once (graced), which is what lets
        the two streaks draw level in the first place."""
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)

        real_only = empty.copy()
        real_only[2][10] = WHITE  # seen first
        phantom_only = empty.copy()
        phantom_only[18][13] = WHITE  # seen one frame later
        both = real_only.copy()
        both[18][13] = WHITE

        d.detect_new_move(real_only)  # real=1 first_seen=1
        d.detect_new_move(phantom_only)  # real absent (miss 1, graced); phantom=1 first_seen=2
        d.detect_new_move(both)  # real=2, phantom=2
        # real=3, phantom=3 -> counts tie, first_seen breaks it in the real stone's favour
        assert d.detect_new_move(both) == (2, 10, WHITE)

    def test_the_fast_path_is_not_lent_to_another_candidate(self):
        """required_frames is evidence about the ONE cell the caller measured — the
        workers read peak_for(pending_move) immediately before calling, so it is always
        about the leader. The leak only bites when the leader is suspect and therefore
        needs MORE sightings than the shortcut grants: a second, ordinary candidate would
        then confirm early on a shortcut measured on somebody else, and at 0.50 it clears
        the device's 0.42 autoplay gate."""
        d = MoveDetector(consistency_frames=5, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)

        phantom_only = empty.copy()
        phantom_only[18][13] = WHITE
        for _ in range(SUSPICION_THRESHOLD):  # appear-then-vanish until it is suspect
            d.detect_new_move(phantom_only)
            for _ in range(3):  # 3 misses > miss_grace 2 -> abandoned, +1 each cycle
                d.detect_new_move(empty)
        assert d.is_suspect(18, 13)

        both = phantom_only.copy()
        both[2][10] = WHITE  # an ordinary second candidate

        d.detect_new_move(phantom_only)  # phantom=1 (it leads on count from here)
        d.detect_new_move(phantom_only)  # phantom=2
        d.detect_new_move(both, required_frames=3)  # phantom=3, real=1
        d.detect_new_move(both, required_frames=3)  # phantom=4, real=2
        # real now reaches 3 sightings. With the leak it confirms here on the leader's
        # 3-frame shortcut. Without it, it must serve the full consistency_frames (5).
        # (2026-09-21: the suspect multiplier was deleted in 917c3e98; a suspect leader needs
        # not ready either — nothing may confirm on this frame.
        assert d.detect_new_move(both, required_frames=3) is None  # phantom=5, real=3

    def test_pending_move_and_count_report_the_leading_candidate(self):
        """The workers read these two properties every frame (confidence-peak tracking
        and the 'confirming' chip). They must keep working."""
        d = MoveDetector(consistency_frames=5, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)
        assert d.pending_move is None
        assert d.count == 0

        board = empty.copy()
        board[2][10] = WHITE
        d.detect_new_move(board)
        d.detect_new_move(board)
        assert d.pending_move == (2, 10, WHITE)
        assert d.count == 2

        d.force_sync(board)
        assert d.pending_move is None
        assert d.count == 0

    def test_ignore_cells_still_excluded_from_candidates(self):
        d = MoveDetector(consistency_frames=3, miss_grace=2)
        empty = self._empty()
        d.force_sync(empty)
        leftover = empty.copy()
        leftover[3][3] = BLACK
        for _ in range(8):
            assert d.detect_new_move(leftover, ignore_cells={(3, 3)}) is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `CI=true uv run pytest tests/test_vision/test_move_detector.py -v`
Expected: `test_a_second_changed_cell_no_longer_blocks_a_real_stone`,
`test_flickering_phantom_loses_its_streak_while_a_real_stone_keeps_its_own`,
`test_the_older_candidate_wins_a_streak_tie`,
`test_an_unrelated_cell_no_longer_destroys_a_real_candidate`,
`test_two_cell_change_no_longer_hard_resets` FAIL, and `test_scene_disruption_still_hard_resets` errors on the unknown `disruption_threshold` keyword.

- [ ] **Step 4: Replace the single pending slot with per-cell candidates**

In `katrain/vision/move_detector.py`, add a module constant next to the reputation block:

```python
# Simultaneous diffs at or above this count are scene disruption (a hand sweeping
# across the board, the board being moved), not "a phantom next to a real stone".
# Below it, every changed cell is simply its own candidate. The old rule was
# `> 1` — which made the WHOLE BOARD the criterion for whether YOUR move counts,
# and on RK3562 2026-09-20 one persistent edge phantom kept a real stone from ever
# entering its game.
DISRUPTION_THRESHOLD = 4
```

Change the constructor signature and body:

```python
    def __init__(self, consistency_frames: int = 3, miss_grace: int = 2, disruption_threshold: int = DISRUPTION_THRESHOLD):
        self.consistency_frames = consistency_frames
        self.miss_grace = miss_grace
        self.disruption_threshold = disruption_threshold
        self.prev_board: np.ndarray | None = None
        # (row, col, color) -> {"count": int, "misses": int, "first_seen": int}
        self._candidates: dict[tuple[int, int, int], dict[str, int]] = {}
        self._suspicion: dict[tuple[int, int], int] = {}
        self._frame_index = 0
```

(The old `self.pending_move = None`, `self.count = 0`, `self.misses = 0` attribute lines are removed — they become properties below.)

Add the two read-only properties directly after `__init__`:

```python
    def _leader(self) -> tuple[int, int, int] | None:
        """Candidate closest to confirming: longest streak, oldest first-seen breaks ties."""
        if not self._candidates:
            return None
        return min(
            self._candidates,
            key=lambda k: (-self._candidates[k]["count"], self._candidates[k]["first_seen"]),
        )

    @property
    def pending_move(self) -> tuple[int, int, int] | None:
        """The leading candidate. Read by both workers every frame (confidence-peak
        tracking and the "confirming" chip). Read-only on purpose: there is now more
        than one candidate, so any assignment site would be a bug."""
        return self._leader()

    @property
    def count(self) -> int:
        """Consecutive sightings of the leading candidate."""
        leader = self._leader()
        return 0 if leader is None else self._candidates[leader]["count"]
```

Replace the whole body of `detect_new_move` from `if len(diff_positions) == 0:` to the final `return None` with:

```python
        if len(diff_positions) >= self.disruption_threshold:
            # Scene disruption: abandon everything, and charge nobody — this is not
            # any one cell's fault.
            self._candidates.clear()
            return None

        # `required_frames` is evidence about ONE stone: the caller measured the
        # confidence peak of whichever cell was leading when it called (the workers read
        # peak_for(pending_move) immediately before this call). Capture that cell BEFORE
        # the candidate update, and let only it use the shortcut — otherwise a confident
        # real stone hands its 3-frame fast path to a weak phantom sharing the frame, and
        # the phantom auto-plays two frames early.
        fast_cell = self._leader()

        current = {(r, c, clr) for r, c, clr in diff_positions}

        # Age out candidates that are not visible this frame. A marginal stone blinks,
        # so a short absence only freezes the streak (miss_grace); a longer one
        # abandons the candidate and charges that cell a point of suspicion.
        for key in list(self._candidates):
            if key in current:
                continue
            cand = self._candidates[key]
            cand["misses"] += 1
            if cand["misses"] > self.miss_grace:
                self._penalize((key[0], key[1]), SUSPICION_ABANDON)
                del self._candidates[key]

        for key in current:
            cand = self._candidates.get(key)
            if cand is None:
                self._candidates[key] = {"count": 1, "misses": 0, "first_seen": self._frame_index}
            else:
                cand["count"] += 1
                cand["misses"] = 0

        if not current:
            return None

        fast_needed = self.consistency_frames if required_frames is None else max(1, int(required_frames))
        ready = []
        for key in current:
            needed = fast_needed if key == fast_cell else self.consistency_frames
            # NOTE (2026-09-21 amendment): the suspect frame-count multiplier that stood here was
            # DELETED in commit 917c3e98. A suspect cell confirms on the NORMAL count and is held
            # back only at the ambiguous ROUTING gate, because the frame count sits upstream of the
            # confirmation card and a doubled count made a weak real stone vanish silently. Do not
            # reintroduce it here.
            if self._candidates[key]["count"] >= needed:
                ready.append(key)
        if not ready:
            return None

        ready.sort(key=lambda k: (-self._candidates[k]["count"], self._candidates[k]["first_seen"]))
        move = ready[0]
        if len(ready) > 1:
            runner_up = ready[1]
            lead, second = self._candidates[move], self._candidates[runner_up]
            if lead["count"] == second["count"] and lead["first_seen"] == second["first_seen"]:
                # Two stones that appeared on the same frame and advanced in lockstep is
                # genuine ambiguity, not a phantom beside a real stone. Emit nothing.
                return None

        # Baseline deliberately NOT advanced (see class docstring): the caller
        # force_syncs once the move is actually accepted downstream.
        del self._candidates[move]
        return move
```

Update `force_sync`:

```python
    def force_sync(self, board: np.ndarray) -> None:
        """Force-update the reference board (for undo, endgame cleanup, manual reset).

        Clears candidates but NOT reputation — force_sync runs on every expected-board
        push, so clearing reputation here would mean it never accumulates. Use
        reset_suspicion() for that.
        """
        self.prev_board = board.copy()
        self._candidates.clear()
```

Update the class docstring's `miss_grace` paragraph — replace the sentence
"Multi-stone changes still hard-reset — that is scene disruption, not flicker."
with:

```
    Changes at or above ``disruption_threshold`` cells in one frame still hard-reset —
    that is scene disruption, not flicker. Below it every changed cell is its own
    candidate with its own streak, so a phantom elsewhere on the board can no longer
    starve a real move (RK3562 2026-09-20: it starved one for an entire game).
```

- [ ] **Step 5: Run the full module's tests**

Run: `CI=true uv run pytest tests/test_vision/test_move_detector.py -v`
Expected: all PASS.

- [ ] **Step 6: Verify no code assigns to the new properties**

Run: `grep -rn --include='*.py' "\.pending_move\s*=\|\.count\s*=\|\.misses" katrain/ tests/ | grep -v "self\._candidates"`
Expected: no hits inside `move_detector.py`, `worker.py`, or `worker_inprocess.py`. `AmbiguousPromoter` has its own unrelated state — hits there are fine. If any hit is a `MoveDetector` instance, fix it to use `force_sync`.

- [ ] **Step 7: Run all vision and poller tests**

Run: `CI=true uv run pytest tests/test_vision tests/test_vision_move_poller.py tests/test_vision_bind_state.py tests/test_vision_pump.py -q`
Expected: all PASS.

- [ ] **Step 8: Format and commit**

```bash
uv run black -l 120 katrain tests
git add katrain/vision/move_detector.py tests/test_vision/test_move_detector.py
git commit -m "$(cat <<'EOF'
fix vision: give every changed intersection its own confirmation streak

detect_new_move hard-reset all state whenever the whole-board diff showed more
than one change, which made the whole board the criterion for whether YOUR move
counted. On RK3562 2026-09-20 one persistent edge phantom kept a real stone from
ever entering its game (zero confirmations all day) and held another for 71
seconds. Each cell now counts for itself; the hard reset is kept for genuine
scene disruption at disruption_threshold (4) simultaneous diffs.

pending_move and count become read-only properties over the leading candidate so
the workers' per-frame reads keep working and any assignment site fails loudly.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: L3 — colour invariant on established stones

**Files:**
- Modify: `katrain/vision/board_state.py`
- Test: `tests/test_vision/test_board_state.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: module constant `COLOR_FLIP_RELEASE_FRAMES`; `BoardStateExtractor` gains instance state `self._color_flip_streak`. Behaviour change is confined to the `occupancy_aware=True` path.

**Background (do not skip):** a stone already established on the board does not change colour. Measured on RK3562 2026-09-20: **65 colour flips on already-placed points in a single game**, one point (vision `(17,15)`, i.e. Q2) flipping **41 times over 27 minutes**, 8 of which reached the client as "the board does not match the game". The digital board held `W` at that point the whole time.

`_assign_occupancy_aware` already has a presence sustain block (`board_state.py:244-251`) that stops an established stone from *vanishing* when a detection is still sitting on it. This task extends the same idea to colour.

**The escape hatch is as important as the invariant.** `sync.py:351-353`'s wrong-colour branch is the only path by which the system can tell the user "you placed the wrong colour there", and it is live today. A flip that *persists* is therefore let through, so that branch stays reachable.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_vision/test_board_state.py`:

```python
from katrain.vision.board_state import COLOR_FLIP_RELEASE_FRAMES  # add to the existing import line

IMG = 640  # square, matching the grid_to_pixel pattern already used at test_board_state.py:**101** (`:99` is just the `from katrain.vision.coordinates import grid_to_pixel` line above it)


def _det_at(cfg, row, col, class_id, confidence):
    """A detection centred on intersection (row, col). grid_to_pixel takes (pos_x=col, pos_y=row)."""
    from katrain.vision.coordinates import grid_to_pixel

    px, py = grid_to_pixel(col, row, IMG, IMG, cfg)
    return Detection(x_center=px, y_center=py, class_id=class_id, confidence=confidence)


class TestColorInvariant:
    """L3: an established stone does not change colour. Measured on RK3562 2026-09-20:
    65 colour flips on already-placed points in one game, one point flipping 41 times
    over 27 minutes, 8 of them reaching the client as a board mismatch."""

    def _prev_with_white(self):
        prev = np.zeros((19, 19), dtype=int)
        prev[17][15] = WHITE
        return prev

    def test_single_frame_flip_is_suppressed(self, extractor, cfg):
        prev = self._prev_with_white()
        black_det = [_det_at(cfg, 17, 15, class_id=0, confidence=0.9)]  # class 0 -> BLACK
        board = extractor.detections_to_board(
            black_det, img_w=IMG, img_h=IMG, occupancy_aware=True, prev_board=prev
        )
        assert board[17][15] == WHITE  # established colour held

    def test_sustained_flip_is_released(self, extractor, cfg):
        """A flip that persists is a real wrong-colour placement, not noise — it must
        get through, or sync.py's wrong-colour warning becomes dead code."""
        prev = self._prev_with_white()
        black_det = [_det_at(cfg, 17, 15, class_id=0, confidence=0.9)]
        board = None
        for _ in range(COLOR_FLIP_RELEASE_FRAMES):
            board = extractor.detections_to_board(
                black_det, img_w=IMG, img_h=IMG, occupancy_aware=True, prev_board=prev
            )
        assert board[17][15] == BLACK

    def test_the_release_latches_until_the_stable_board_adopts_it(self):
        """THE regression. The workers need two CONSECUTIVE agreeing frames before the
        stable board changes, and `prev_board` is that stable board — so a release that
        lasts one frame never lands and the established colour is stuck forever. Reproduce
        the worker's own voting loop rather than trusting a single extractor call."""
        ex = BoardStateExtractor()
        cfg = BoardConfig()
        prev_stable = np.zeros((19, 19), dtype=int)
        prev_stable[17][15] = WHITE
        prev_observed = None
        black_det = [_det_at(cfg, 17, 15, class_id=0, confidence=0.9)]

        for _ in range(COLOR_FLIP_RELEASE_FRAMES + 3):
            observed = ex.detections_to_board(
                black_det, img_w=IMG, img_h=IMG, occupancy_aware=True, prev_board=prev_stable
            )
            if prev_observed is not None:
                prev_stable = np.where(observed == prev_observed, observed, prev_stable)
            prev_observed = observed

        assert prev_stable[17][15] == BLACK  # the correction actually reached the stable board

    def test_streak_resets_when_the_colour_agrees_again(self, extractor, cfg):
        prev = self._prev_with_white()
        black_det = [_det_at(cfg, 17, 15, class_id=0, confidence=0.9)]
        white_det = [_det_at(cfg, 17, 15, class_id=1, confidence=0.9)]  # class 1 -> WHITE

        for _ in range(COLOR_FLIP_RELEASE_FRAMES - 1):
            extractor.detections_to_board(
                black_det, img_w=IMG, img_h=IMG, occupancy_aware=True, prev_board=prev
            )
        # One agreeing frame clears the streak...
        extractor.detections_to_board(white_det, img_w=IMG, img_h=IMG, occupancy_aware=True, prev_board=prev)
        # ...so the next disagreeing frame is back at streak 1 and is suppressed.
        board = extractor.detections_to_board(
            black_det, img_w=IMG, img_h=IMG, occupancy_aware=True, prev_board=prev
        )
        assert board[17][15] == WHITE

    def test_a_new_stone_on_an_empty_point_is_unaffected(self, extractor, cfg):
        prev = np.zeros((19, 19), dtype=int)  # nothing established anywhere
        black_det = [_det_at(cfg, 17, 15, class_id=0, confidence=0.9)]
        board = extractor.detections_to_board(
            black_det, img_w=IMG, img_h=IMG, occupancy_aware=True, prev_board=prev
        )
        assert board[17][15] == BLACK

    def test_removal_is_unaffected(self, extractor, cfg):
        """No detection at all near the cell -> the existing presence sustain does not
        fire either, and the stone leaves the board. The colour invariant must not
        resurrect it."""
        prev = self._prev_with_white()
        board = extractor.detections_to_board([], img_w=IMG, img_h=IMG, occupancy_aware=True, prev_board=prev)
        assert board[17][15] == EMPTY
```

`np`, `Detection`, `BoardConfig`, `BoardStateExtractor` and the `extractor` / `cfg` fixtures already exist in that file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `CI=true uv run pytest tests/test_vision/test_board_state.py::TestColorInvariant -v`
Expected: collection error — `ImportError: cannot import name 'COLOR_FLIP_RELEASE_FRAMES'`.

- [ ] **Step 3: Add the constant**

In `katrain/vision/board_state.py`, after the `SUSTAIN_RADIUS = 0.6` block, add:

```python
# Colour invariant: an established stone does not change colour. Measured on RK3562
# 2026-09-20: 65 colour flips on already-placed points in a single game, one point
# (vision (17,15)) flipping 41 times over 27 minutes, 8 of which reached the client
# as "the board does not match the game". The digital board held one colour throughout.
#
# The release window matters as much as the invariant. sync.py's wrong-colour branch is
# the ONLY way the system can tell the user "you placed the wrong colour there", and it
# is live today. A disagreement that PERSISTS this many consecutive frames is therefore
# let through, so that branch stays reachable — one frame of the other colour is noise,
# several seconds of it is a real wrong-colour placement.
COLOR_FLIP_RELEASE_FRAMES = 15
```

**The release must LATCH.** Both workers feed the extractor's output through a two-frame
vote (`stable_board = np.where(observed == prev_observed, observed, last_stable)`), and
`prev_board` here IS that stable board. A release that lasts a single frame therefore
never reaches the stable board at all: frame 15 emits the other colour, frame 16 starts a
fresh streak and suppresses it again, the vote never sees two agreeing frames, and the
established colour is stuck forever — which would make the escape hatch, and with it
`sync.py`'s wrong-colour warning, permanently unreachable. Once a cell is released it
stays released until the stable board actually adopts the new colour.

- [ ] **Step 4: Add the per-cell streak state**

`BoardStateExtractor.__init__` currently is:

```python
    def __init__(self, config: BoardConfig | None = None):
        self.config = config or BoardConfig()
```

Change it to:

```python
    def __init__(self, config: BoardConfig | None = None):
        self.config = config or BoardConfig()
        # (row, col) -> consecutive frames this established cell has been read as the
        # other colour. Instance state, so it only applies to the occupancy-aware path
        # and only to the extractor instance actually in use. The workers hold two
        # instances (margin-aware for the geometry-lock warp, plain for the BoardFinder
        # fallback) and pick one per frame by geometry, which does not change mid-game.
        self._color_flip_streak: dict[tuple[int, int], int] = {}
        # Cells whose flip has been released and must KEEP being released until the
        # caller's stable board adopts the new colour — the workers need two consecutive
        # agreeing frames to change it, so a one-frame release would never land.
        self._color_flip_released: set[tuple[int, int]] = set()
```

- [ ] **Step 5: Apply the invariant**

In `_assign_occupancy_aware`, immediately **after** the existing presence-sustain block (the `if prev_board is not None and all_points:` loop ending with `board[r][c] = prev_board[r][c]`) and **before** `return board`, insert:

```python
        # Colour invariant (see COLOR_FLIP_RELEASE_FRAMES). Runs after presence sustain,
        # so a cell that sustain just resurrected already carries prev's colour and is
        # not re-examined here.
        if prev_board is not None:
            flipped = {
                (int(r), int(c))
                for r, c in zip(*np.where((prev_board != EMPTY) & (board != EMPTY) & (board != prev_board)))
            }
            for cell in list(self._color_flip_streak):
                if cell not in flipped:
                    del self._color_flip_streak[cell]  # agreed again — start over
            for cell in list(self._color_flip_released):
                if cell not in flipped:
                    # No longer a disagreement: either the stable board adopted the new
                    # colour (the release landed) or the stone left. Either way, done.
                    self._color_flip_released.discard(cell)
            for cell in flipped:
                if cell in self._color_flip_released:
                    continue  # latched open until the stable board adopts it
                r, c = cell
                streak = self._color_flip_streak.get(cell, 0) + 1
                if streak >= COLOR_FLIP_RELEASE_FRAMES:
                    del self._color_flip_streak[cell]
                    self._color_flip_released.add(cell)  # a real wrong-colour placement
                else:
                    self._color_flip_streak[cell] = streak
                    board[r][c] = int(prev_board[r][c])
        else:
            self._color_flip_streak.clear()
            self._color_flip_released.clear()
        return board
```

- [ ] **Step 6: Run the tests**

Run: `CI=true uv run pytest tests/test_vision/test_board_state.py tests/test_vision/test_board_state_masking.py -v`
Expected: all PASS, including every pre-existing test in both files.

- [ ] **Step 7: Run the vision suite**

Run: `CI=true uv run pytest tests/test_vision -q`
Expected: all PASS.

- [ ] **Step 8: Format and commit**

```bash
uv run black -l 120 katrain tests
git add katrain/vision/board_state.py tests/test_vision/test_board_state.py
git commit -m "$(cat <<'EOF'
fix vision: an established stone keeps its colour unless the disagreement persists

65 colour flips on already-placed points in one RK3562 game on 2026-09-20, one
point flipping 41 times over 27 minutes and pushing 8 board-mismatch events to
the client. The presence sustain already stopped an established stone from
vanishing; this extends the same idea to colour.

A flip that survives COLOR_FLIP_RELEASE_FRAMES consecutive frames is released, so
sync.py's wrong-colour warning — the only way to tell the user they placed the
wrong colour — does not become dead code.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: L4 — decouple "a stone is missing" from "there is an extra stone"

**Files:**
- Modify: `katrain/vision/sync.py`
- Test: `tests/test_vision/test_sync.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `SyncStateMachine(..., missing_hold_seconds: float = 7.0)` constructor keyword; `_compare_boards` gains a required `now: float` parameter.

**Background (do not skip):** `_compare_boards` puts both kinds of anomaly — `unexpected` (the board has a stone the game does not) and `missing_anomaly` (the game has a stone the board cannot see) — through the same `illegal_change_frames` counter, default **5 frames**. The board runs at 6–15 fps, so five frames is **0.3–0.8 seconds**: an arm passing over the board is enough. Measured on RK3562 2026-09-20: 40% of one game's `illegal_change` events carried `missing`, almost all on a single point.

An extra stone is immediately actionable (you can see which stone to remove), so that path keeps its fast reaction. A missing stone needs a hold.

**The hold needs two conditions, not one.** `gating.py:39`'s `should_feed_sync_frame` stops feeding frames while the scene is moving, so a 3-second occlusion can produce two frames three seconds apart and satisfy a pure elapsed-time test *without the state ever having been observed*. So: elapsed wall-clock **and** a minimum number of frames actually observed in that state.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_vision/test_sync.py`:

```python
class TestMissingStoneHold:
    """L4: a live stone vision cannot see is not reported until it has been
    continuously invisible for both a real elapsed period AND a minimum number of
    frames we actually looked at. The old gate was illegal_change_frames (5), which at
    the board's 6-15 fps is 0.3-0.8s — an arm passing over the board."""

    def _synced(self, expected, **kwargs):
        sm = SyncStateMachine(**kwargs)
        sm.bind()
        sm.confirm_pose_lock()
        sm.set_expected_board(expected)
        return sm

    def _established(self, sm, expected):
        """Drive one matching frame so the stone counts as live, not placement-pending."""
        sm.update(observed_board=expected, timestamp=0.0)

    def test_brief_occlusion_does_not_report_missing(self):
        expected = board_with({(3, 3): 1})
        sm = self._synced(expected, missing_hold_seconds=7.0, illegal_change_frames=5)
        self._established(sm, expected)

        gone = empty_board()
        for i in range(10):  # 10 frames over 2 seconds
            events = sm.update(observed_board=gone, timestamp=1.0 + i * 0.2)
            assert SyncEventType.ILLEGAL_CHANGE not in [e.type for e in events]

    def test_sustained_absence_does_report_missing(self):
        expected = board_with({(3, 3): 1})
        sm = self._synced(expected, missing_hold_seconds=7.0, illegal_change_frames=5)
        self._established(sm, expected)

        gone = empty_board()
        seen = []
        for i in range(40):  # 40 frames over 8 seconds
            seen.extend(e for e in sm.update(observed_board=gone, timestamp=1.0 + i * 0.2))
        illegal = [e for e in seen if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert illegal
        assert [3, 3] in [[r, c] for r, c, _ in illegal[0].data["missing"]]

    def test_elapsed_time_alone_is_not_enough(self):
        """Two frames 10 seconds apart is what a long occlusion looks like from the
        sync machine's side, because moving frames are not fed at all."""
        expected = board_with({(3, 3): 1})
        sm = self._synced(expected, missing_hold_seconds=7.0, illegal_change_frames=5)
        self._established(sm, expected)

        gone = empty_board()
        sm.update(observed_board=gone, timestamp=1.0)
        events = sm.update(observed_board=gone, timestamp=11.0)
        assert SyncEventType.ILLEGAL_CHANGE not in [e.type for e in events]

    def test_extra_stone_still_reports_fast(self):
        """The extra-stone path is unchanged: an extra stone is immediately actionable."""
        expected = empty_board()
        sm = self._synced(expected, missing_hold_seconds=7.0, illegal_change_frames=5)
        extra = board_with({(3, 3): 1})

        seen = []
        for i in range(6):
            seen.extend(sm.update(observed_board=extra, timestamp=float(i) * 0.2))
        assert [e for e in seen if e.type == SyncEventType.ILLEGAL_CHANGE]

    def test_held_missing_does_not_acknowledge_the_expected_board(self):
        """A frame whose only anomaly is a held missing stone is not a clean frame — it
        must not emit the versioned SYNCED ack."""
        expected = board_with({(3, 3): 1})
        sm = self._synced(expected, missing_hold_seconds=7.0, illegal_change_frames=5)
        self._established(sm, expected)
        sm.set_expected_board(expected, expected_node_id=99)

        gone = empty_board()
        events = sm.update(observed_board=gone, timestamp=2.0)
        acks = [e for e in events if e.type == SyncEventType.SYNCED and e.data.get("expected_node_id")]
        assert acks == []

    def test_reset_clears_the_missing_hold(self):
        expected = board_with({(3, 3): 1})
        sm = self._synced(expected, missing_hold_seconds=7.0, illegal_change_frames=5)
        self._established(sm, expected)
        gone = empty_board()
        for i in range(6):
            sm.update(observed_board=gone, timestamp=1.0 + i * 0.2)

        sm.reset(expected)
        # The hold restarts from scratch: 6 more frames, still inside the window.
        for i in range(6):
            events = sm.update(observed_board=gone, timestamp=3.0 + i * 0.2)
            assert SyncEventType.ILLEGAL_CHANGE not in [e.type for e in events]
```

The helpers `board_with` and `empty_board` already exist at the top of `tests/test_vision/test_sync.py`. If either is missing, read the file and use whatever it defines.

- [ ] **Step 2: Run tests to verify they fail**

Run: `CI=true uv run pytest tests/test_vision/test_sync.py::TestMissingStoneHold -v`
Expected: `test_brief_occlusion_does_not_report_missing`, `test_elapsed_time_alone_is_not_enough`, and `test_held_missing_does_not_acknowledge_the_expected_board` FAIL (the machine reports the missing stone after 5 frames); the constructor also rejects `missing_hold_seconds`.

- [ ] **Step 3: Add the constructor parameter and state**

In `katrain/vision/sync.py`, add `missing_hold_seconds: float = 7.0,` as the last parameter of `SyncStateMachine.__init__`, and in the body next to `self._mismatch_count: int = 0` add:

```python
        # A live stone vision cannot see is held back until it has been continuously
        # invisible for BOTH missing_hold_seconds of real time AND illegal_change_frames
        # of actually-observed frames. Wall-clock alone is not enough: gating.py's
        # should_feed_sync_frame stops feeding frames while the scene moves, so a 3-second
        # occlusion arrives here as two frames 3 seconds apart. The old gate was the frame
        # counter alone, which at the board's 6-15 fps is 0.3-0.8s — an arm passing over.
        self._missing_hold_seconds = missing_hold_seconds
        self._missing_since: dict[tuple[int, int], list] = {}  # (row,col) -> [first_seen_ts, frames]
```

Also add `self._missing_since = {}` to `reset()`, next to `self._mismatch_count = 0`.

- [ ] **Step 4: Thread `now` into `_compare_boards`**

In `update()`, change:

```python
            events.extend(self._compare_boards(observed_board))
```
to:
```python
            events.extend(self._compare_boards(observed_board, now))
```

And change the signature:

```python
    def _compare_boards(self, observed_board: np.ndarray, now: float) -> list[SyncEvent]:
```

- [ ] **Step 5: Split the missing path**

In `_compare_boards`, immediately after the classification `for r, c in diff_positions:` loop ends and **before** the `# 4b.` board-lost block, insert:

```python
        # 4a-bis. Hold back a missing stone until it has been continuously invisible for
        # both a real elapsed period and a minimum number of observed frames — see
        # `_missing_hold_seconds`. `missing_anomaly` itself is left intact because the
        # board-lost check below must still react immediately: a displaced board produces
        # many missing points at once and is not something to wait out.
        held_missing: list[tuple[int, int, int]] = []
        ripe_missing: list[tuple[int, int, int]] = []
        seen_missing: set[tuple[int, int]] = set()
        for r, c, clr in missing_anomaly:
            cell = (r, c)
            seen_missing.add(cell)
            entry = self._missing_since.get(cell)
            if entry is None:
                entry = [now, 0]
                self._missing_since[cell] = entry
            entry[1] += 1
            if now - entry[0] >= self._missing_hold_seconds and entry[1] >= self._illegal_change_frames:
                ripe_missing.append((r, c, clr))
            else:
                held_missing.append((r, c, clr))
        for cell in list(self._missing_since):
            if cell not in seen_missing:
                del self._missing_since[cell]
```

- [ ] **Step 6: Consume `ripe_missing` in the anomaly block**

In the `# 4d. Anomaly tracking` block, make four substitutions:

```python
        if unexpected or ripe_missing:
            # Build a fingerprint of current anomalous positions for stability check.
            current_mismatch = np.zeros_like(self._expected_board)
            for r, c, clr in unexpected:
                current_mismatch[r, c] = clr
            for r, c, clr in ripe_missing:
                current_mismatch[r, c] = clr + 2  # distinct fingerprint values (3/4)
```

and inside the emitted event:

```python
                            "missing": [(r, c, clr) for r, c, clr in ripe_missing + placement_pending],
```

Leave the rest of the block unchanged, including its trailing `return events`.

- [ ] **Step 7: Stop a held-missing frame from counting as clean**

Immediately after that block's `return events` (i.e. between `# 4d` and `# 4e`), insert:

```python
        if held_missing:
            # Still waiting out the hold. Not an anomaly yet, but definitely not a clean
            # frame either: falling through to 4e would acknowledge the versioned expected
            # board while a stone the game believes in is not visible.
            self._mismatch_board = None
            self._mismatch_count = 0
            return events
```

- [ ] **Step 8: Run the tests**

Run: `CI=true uv run pytest tests/test_vision/test_sync.py tests/test_vision/test_sync_regressions.py -v`
Expected: all PASS, including every pre-existing test in both files. If a pre-existing test now fails because it expected a missing stone to be reported after 5 frames, **do not weaken the new behaviour** — check whether the test is about `unexpected` (which is unchanged) or about `missing` (whose premise this task deliberately changes), and if the latter, rewrite it the way Task 4 Step 1 rewrites its three tests, explaining the changed premise in the docstring.

- [ ] **Step 9: Run the vision suite**

Run: `CI=true uv run pytest tests/test_vision tests/test_vision_pump.py -q`
Expected: all PASS.

- [ ] **Step 10: Format and commit**

```bash
uv run black -l 120 katrain tests
git add katrain/vision/sync.py tests/test_vision/test_sync.py
git commit -m "$(cat <<'EOF'
fix vision: hold a missing stone on wall-clock before calling it a board mismatch

"There is an extra stone" and "a stone the game believes in is invisible" went
through the same 5-frame counter. At the board's 6-15 fps that is 0.3-0.8s — an
arm passing over the board. 40% of one RK3562 game's illegal_change events on
2026-09-20 carried `missing`, almost all on one point.

The extra-stone path is unchanged (an extra stone is immediately actionable). The
missing path now needs both elapsed wall-clock and a minimum number of observed
frames, because moving frames are not fed to sync at all and elapsed time alone
would pass on two frames taken three seconds apart.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification (after all six tasks)

- [ ] **Full suite, compared against a baseline**

```bash
git stash list  # confirm you are not about to disturb another worktree's entries
CI=true uv run pytest tests -q --continue-on-collection-errors 2>&1 | tail -40
```

Expected: no new `FAILED` / `ERROR` lines relative to the pre-change baseline. **Take the baseline by name, not by count** — run the same command on the merge-base commit first and `comm` the two sorted lists of failing test IDs. A raw count comparison hides a new failure that coincides with a fixed one.

- [ ] **Both workers really are in parity**

```bash
# Site 1 — the confirmation/routing block. This is the ONLY site the original
# one-liner covered (worker.py 403-517, worker_inprocess.py 451-565).
diff <(sed -n '/pending_peak = /,/self._prev_conf_map = conf_map/p' katrain/vision/worker.py) \
     <(sed -n '/pending_peak = /,/self._prev_conf_map = conf_map/p' katrain/vision/worker_inprocess.py)

# Site 2 — the stuck-stone promoter gate. Sits TWO LINES past the end of site 1's range.
diff <(grep -A2 'if move_result is None and' katrain/vision/worker.py) \
     <(grep -A2 'if move_result is None and' katrain/vision/worker_inprocess.py)

# Site 3 — _run_ae. A different method entirely; site 1's range never reaches it.
diff <(sed -n '/def _run_ae/,/^    def /p' katrain/vision/worker.py) \
     <(sed -n '/def _run_ae/,/^    def /p' katrain/vision/worker_inprocess.py)
```

Expected, at every site: the only differences are the pre-existing ones — `self._last_stable_board`
vs `observed_board`, `self._state_extractor` vs `self._active_extractor()`, and one `(macOS)` word in
`_run_ae`'s comment. Any difference in the suspect-gate, charge, or mute lines is a parity bug — fix it.

> **Corrected 2026-09-21 — this step used to be site 1 alone, and that was a gate aimed at the wrong
> operand.** Fix round 1 added call sites at all three places. Sites 2 and 3 fall outside the sed
> range, so the original one-liner would have reported parity CLEAN while two of the four
> `about_to_confirm` call sites were broken. A gate that cannot see what it guards is worse than no
> gate, because its green gets quoted. Verified: the range is worker.py 403-517 /
> worker_inprocess.py 451-565, while the promoter gate is at 520/568 and `_run_ae` at 650/289.

- [ ] **Nothing in the frontend changed**

```bash
# NOT merge-base with develop: the exit-404 plan landed on this same branch
# between develop and this plan's base, and all of its work is frontend.
git diff --stat 10455ba5..HEAD -- katrain/web/ui/
```

Expected: empty. **Corrected 2026-09-21.** This step originally said
`$(git merge-base HEAD develop)..HEAD`, which spans the exit-404 plan as well and reports 13 files
/ 663 insertions — so it fails against a tree where this plan touched no frontend at all. `10455ba5`
is this plan's base (the exit-404 plan's last commit). Verified: those 13 files come from 6 commits
in `develop..10455ba5`, and the corrected range is empty.

## Device acceptance (the user runs this — do NOT ssh to the board)

Hand these five assertions to the user for a live game on RK3562:

1. An edge stone the camera reads weakly **enters the game by itself**, without the user pressing "adopt as my move".
2. `journalctl` shows `move confirmed: (18,13)` **zero times** for the whole game.
3. `board delta` lines contain no same-point `B`↔`W` alternation.
4. An arm passing over the board produces no `illegal_change`.
5. The move sequence the remote platform received matches the local game record move for move.
