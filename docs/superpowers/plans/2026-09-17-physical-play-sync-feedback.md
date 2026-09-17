# Physical Play Synchronization and Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让实体棋盘对弈中数字落子先于声音呈现，把 AI 落子提示移到右侧状态区并在对应实体盘同步后自动消失，同时把摆偏、低置信度、盘面不一致和棋盘丢失收敛为一个不叠层的恢复界面。

**Architecture:** 后端用现有 `current_node_id` 为落子声音和期望盘面增加因果标识；视觉同步状态机只在对应期望盘面被摄像头精确观测到时发一次带节点号的 `synced`。前端分别用节点号控制声音的“提交后、绘制后”播放和 AI 摆子提示的消失，并用一个判别联合状态管理所有阻塞式视觉恢复界面。部署继续由 `smartbox-software/provisioning/provision.sh --section katrain` 负责，盒上有严格预构建包时不要求安装 npm。

**Tech Stack:** Python 3.11、FastAPI、NumPy、pytest；React 18、TypeScript、Material UI、Vitest、Vite；RK3562、systemd、Chromium kiosk。

**Approved spec:** `docs/superpowers/specs/2026-09-17-physical-play-sync-feedback-design.md`

---

## Global constraints

- 当前分支是 `fix/kiosk-ui-debug`；计划编写时相对 `develop` 为 `84 behind / 1 ahead`，唯一领先提交是已批准规格 `289e893b`。实现前先把 `develop` 合进来，不改写或丢弃现有提交。
- `katrain/vision/worker.py` 与 `katrain/vision/worker_inprocess.py` 的命令处理必须同步修改；真机实际运行 `worker_inprocess.py`。
- 不运行 Black 格式化整个 `katrain/web/server.py`，避免产生无关大 diff。
- 前端 TypeScript 闸是 `npx tsc -b`；不要用本仓空转的 `tsc --noEmit` 代替。
- 测试只覆盖这次四个缺陷和最可能的回归点；不把已知全量 pytest 噪声当作验收。
- 不再增加推理优化。性能结论来自 RK3562 事件链和现有 `enh=...ms infer=...ms` 日志。
- 每个代码任务完成并通过其聚焦测试后提交一次；部署前必须先完成本地构建与差异检查。

## File map

### Backend contracts

- Modify: `katrain/web/interface.py`
- Modify: `katrain/vision/service.py`
- Modify: `katrain/vision/sync.py`
- Modify: `katrain/vision/worker.py`
- Modify: `katrain/vision/worker_inprocess.py`
- Modify: `katrain/web/core/physical_play_orchestrator.py`
- Modify: `katrain/web/api/v1/endpoints/vision.py`
- Modify: `katrain/web/server.py`
- Test: `tests/web_ui/test_move_sound_order.py` (new)
- Test: `tests/test_vision/test_sync.py`
- Test: `tests/test_vision/test_worker_commands.py`
- Test: `tests/test_physical_play_orchestrator.py`
- Update test doubles only where the new optional keyword reaches them: `tests/test_engine_physical_integration.py`, `tests/test_play_ai_endgame.py`, `tests/test_vision_bind_state.py`, `tests/test_vision_move_poller.py`, `tests/test_physical_play_recovery.py`, `tests/web_ui/test_ai_ladder_api.py`

### Frontend presentation

- Modify: `katrain/web/ui/src/hooks/useGameSession.ts`
- Test: `katrain/web/ui/src/hooks/useGameSession.sound.test.tsx` (new)
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/GamePageLedBadge.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx`
- Create: `katrain/web/ui/src/kiosk/components/vision/visionRecovery.ts`
- Create: `katrain/web/ui/src/kiosk/components/vision/visionRecovery.test.ts`
- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/physical/AmbiguousMoveCard.tsx`
- Modify: `katrain/i18n/locales/{cn,de,en,es,fr,jp,ko,ru,tr,tw,ua}/LC_MESSAGES/katrain.po`
- Regenerate (ignored runtime artifacts): `katrain/i18n/locales/*/LC_MESSAGES/katrain.mo`

### Build and deployment

- Modify: `katrain/web/server.py` (`build_frontend` ordering only)
- Test: `tests/web_ui/test_frontend_build.py` (new)
- Do not modify: `scripts/board_upgrade.sh`
- Deployment owner: `/Users/fan/Repositories/smartbox-software/provisioning/provision.sh`
- Submodule pointer: `/Users/fan/Repositories/smartbox-software/vendor/katrain`

---

## Chunk 1 — Backend causal contracts

### Task 0: Bring the implementation branch onto current `develop`

**Files:** Git history only; preserve the approved design commit.

- [ ] **Step 1: Confirm the worktree only contains intended state**

  Run: `git status --short`

  Expected: empty output. If not empty, stop and inspect; do not stash or overwrite user changes.

- [ ] **Step 2: Fetch and merge current remote `develop` into the feature branch**

  Run: `git fetch origin develop`

  Run: `git merge origin/develop`

  Expected: a normal merge containing at least the 84 commits currently ahead on `develop`, with `289e893b` preserved. Resolve only actual conflicts; never run a broad formatter.

- [ ] **Step 3: Run a narrow post-merge baseline**

  Run: `.venv/bin/python -m pytest tests/test_vision/test_sync.py tests/test_physical_play_orchestrator.py -q`

  Run: `cd katrain/web/ui && npx vitest run src/kiosk/components/vision/VisionSyncOverlay.test.tsx src/kiosk/pages/GamePage.test.tsx`

  Expected: both pass before new behavior is introduced.

- [ ] **Step 4: Record the merge state**

  Run: `git status --short && git log --oneline --max-count=3`

  Expected: clean worktree and merge commit (or an already-up-to-date result if branch topology changed before execution).

### Task 1: Emit one exact-match acknowledgement for each expected-board node revision

**Files:**

- Modify: `katrain/vision/sync.py`
- Test: `tests/test_vision/test_sync.py`

- [ ] **Step 1: Write the failing state-machine tests**

  Add a focused `TestExpectedBoardAcknowledgement` block to `tests/test_vision/test_sync.py` that proves:

  ```python
  def _synced_events(events):
      return [event for event in events if event.type == SyncEventType.SYNCED]

  def test_exact_board_acks_new_revision_even_when_state_was_already_synced():
      sm = SyncStateMachine()
      sm.bind()
      sm.confirm_pose_lock()
      expected = board_with({(3, 3): BLACK})
      sm.set_expected_board(expected, expected_node_id=101)

      synced = _synced_events(sm.update(expected.copy(), mean_confidence=0.9))

      assert [event.data for event in synced] == [{"expected_node_id": 101}]

  def test_revision_ack_is_emitted_only_once():
      # First exact frame emits node 101; later exact frames emit no second ack.

  def test_same_matrix_with_new_node_id_rearms_ack_without_requiring_board_change():
      # Ack node 101, call set_expected_board(same_board, expected_node_id=102),
      # then require exactly one {expected_node_id: 102} ack.

  def test_placement_pending_empty_board_does_not_ack_expected_stone():
      # Expected contains the AI stone, observed remains empty: no versioned synced.

  def test_degraded_recovery_event_does_not_ack_revision_until_a_later_exact_frame():
      # The frame that exits DEGRADED may emit the legacy unversioned synced event,
      # but must not consume the revision; the next usable exact frame acks it.

  def test_reset_cancels_an_unacknowledged_revision():
      # Arm 101, reset, then an exact empty frame cannot emit expected_node_id=101.

  def test_exact_observation_promotes_live_board_for_later_removal_detection():
      # Arm an expected stone from an empty previous board, observe it exactly,
      # then remove it physically without a digital change. Five stable frames must
      # produce ILLEGAL_CHANGE/missing, never silently classify it as placement_pending.
  ```

- [ ] **Step 2: Run the new tests and confirm the missing API fails**

  Run: `.venv/bin/python -m pytest tests/test_vision/test_sync.py -k ExpectedBoardAcknowledgement -v`

  Expected: FAIL because `set_expected_board` does not accept `expected_node_id` and no versioned ack exists.

- [ ] **Step 3: Add revision state without disturbing board-diff history**

  In `SyncStateMachine.__init__`, add a current revision and a pending-ack flag. Change the public method so board changes and revision changes are handled independently:

  ```python
  def set_expected_board(self, board: np.ndarray, *, expected_node_id: int | None = None) -> None:
      board_changed = not np.array_equal(board, self._expected_board)
      if board_changed:
          self._prev_expected_board = self._expected_board.copy()
          self._expected_board = board.copy()

      if expected_node_id != self._expected_node_id:
          self._expected_node_id = expected_node_id
          self._expected_ack_pending = expected_node_id is not None
  ```

  The exact field names may vary, but preserve these semantics:

  - repeated commands for the same node do not re-arm;
  - the same matrix with a different node does re-arm;
  - repeating the same matrix command must not replace `_prev_expected_board`, because doing so turns a still-unplaced AI stone into `missing_anomaly`;
  - `expected_node_id=None` cancels any older pending acknowledgement.

  When a later frame is an **exact** physical match, promote `_prev_expected_board = _expected_board.copy()`. That safe promotion records that all live stones have actually been seen, so removing one later becomes `missing_anomaly`. Never promote merely because the same expected-board command was repeated.

- [ ] **Step 4: Emit the acknowledgement only in exact board comparison**

  In `_compare_boards`, keep the existing capture-cleared handling first, then split the bottom “no anomaly” path into two explicit cases. Only the real `diff_count == 0` case may consume a revision:

  ```python
  if diff_count == 0:
      self._prev_expected_board = self._expected_board.copy()
      data = {"expected_node_id": self._expected_node_id} if self._expected_ack_pending else {}
      if self._state != SyncState.SYNCED or self._expected_ack_pending:
          events.append(SyncEvent(SyncEventType.SYNCED, data=data))
      self._state = SyncState.SYNCED
      self._expected_ack_pending = False
  elif self._state != SyncState.SYNCED:
      # placement_pending-only: preserve legacy state behavior, but do not ack.
      self._state = SyncState.SYNCED
      events.append(SyncEvent(SyncEventType.SYNCED))
  ```

  Do not attach `expected_node_id` to `_check_degraded` recovery. In `update()`, snapshot `was_degraded` before `_check_degraded`; if that call exits degraded state on this frame, return its legacy recovery event immediately instead of falling through to `_compare_boards`. The next usable frame may perform exact comparison and acknowledge the pending revision.

- [ ] **Step 5: Cancel revision state at lifecycle boundaries**

  Clear the revision and pending flag in `reset()`. `UNBIND` creates a new `SyncStateMachine`, so no separate state survives unbind. Setup completion may keep legacy unversioned `synced`; it must not fabricate an expected-node acknowledgement.

- [ ] **Step 6: Run focused state-machine regression**

  Run: `.venv/bin/python -m pytest tests/test_vision/test_sync.py -q`

  Expected: all tests pass, including capture, placement-pending, stolen-stone, degraded, and new revision cases.

- [ ] **Step 7: Commit the state-machine contract**

  Run: `git add katrain/vision/sync.py tests/test_vision/test_sync.py && git commit -m "ack exact physical board revisions"`

### Task 2: Carry `expected_node_id` through the service, both workers, and game-state call sites

**Files:**

- Modify: `katrain/vision/service.py`
- Modify: `katrain/vision/worker.py`
- Modify: `katrain/vision/worker_inprocess.py`
- Modify: `katrain/web/core/physical_play_orchestrator.py`
- Modify: `katrain/web/api/v1/endpoints/vision.py`
- Modify: `katrain/web/server.py`
- Test: `tests/test_vision/test_worker_commands.py`
- Test: `tests/test_physical_play_orchestrator.py`
- Update the listed fake vision methods that receive the optional keyword.

- [ ] **Step 1: Write failing service/worker/orchestrator tests**

  Add tests for these contracts:

  1. `VisionService.set_expected_from_stones(..., expected_node_id=77)` sends a `SET_EXPECTED_BOARD` command whose data contains both `board` and `expected_node_id`.
  2. Both worker command handlers pass `expected_node_id` into `SyncStateMachine.set_expected_board` even when `board` equals `_expected_np` and the move-detector baseline is already clean.
  3. `PhysicalPlayOrchestrator.on_game_state` calls:

     ```python
     vision.set_expected_from_stones(
         state["stones"], state["board_size"][0], expected_node_id=state["current_node_id"]
     )
     ```

  Extend the test helper `state(...)` to include a deterministic `current_node_id`.
  Also extend the existing vision-bind and move-poller tests to assert that their call sites forward the actual `game_state["current_node_id"]`, not merely that their fakes tolerate a new keyword.

- [ ] **Step 2: Run the new transport tests and confirm they fail**

  Run: `.venv/bin/python -m pytest tests/test_vision/test_worker_commands.py tests/test_physical_play_orchestrator.py -k "expected or revision or node_id" -v`

  Expected: FAIL on missing keyword/payload forwarding.

- [ ] **Step 3: Extend `VisionService` with an optional keyword-only revision**

  Implement:

  ```python
  def set_expected_board(self, board: np.ndarray, *, expected_node_id: int | None = None) -> None:
      data = {"board": board.tolist()}
      if expected_node_id is not None:
          data["expected_node_id"] = expected_node_id
      self._worker.send_command(WorkerCommand(action=CommandType.SET_EXPECTED_BOARD, data=data))

  def set_expected_from_stones(
      self, stones: list[list], board_size: int = 19, *, expected_node_id: int | None = None
  ) -> None:
      self.set_expected_board(
          game_state_stones_to_board(stones, board_size),
          expected_node_id=expected_node_id,
      )
  ```

  Keep the keyword optional for raw/manual callers and compatibility with non-game vision flows.

- [ ] **Step 4: Update both copied worker handlers identically**

  In both `worker.py` and `worker_inprocess.py`, always call:

  ```python
  self._sync.set_expected_board(
      board,
      expected_node_id=cmd.data.get("expected_node_id"),
  )
  ```

  Keep `MoveDetector.force_sync()` and `_expected_np` behind the existing `unchanged and baseline_ok` optimization. The revision update must occur outside that conditional.

- [ ] **Step 5: Pass the authoritative node at every game-state source**

  Update:

  - `PhysicalPlayOrchestrator.on_game_state`
  - vision bind in `katrain/web/api/v1/endpoints/vision.py`
  - `_rearm_detection` in `katrain/web/server.py`

  Use `game_state.get("current_node_id")`; raw board API callers continue without a revision.

- [ ] **Step 6: Update only affected test doubles**

  Change fake signatures from:

  ```python
  def set_expected_from_stones(self, stones, board_size=19):
  ```

  to:

  ```python
  def set_expected_from_stones(self, stones, board_size=19, *, expected_node_id=None):
  ```

  Record the keyword in `FakeVision.expected_pushes` where the test asserts it. For ad-hoc lambdas in `tests/web_ui/test_ai_ladder_api.py`, accept `**_kwargs`; do not weaken production typing to accommodate test fakes.

- [ ] **Step 7: Run the focused propagation suite**

  Run: `.venv/bin/python -m pytest tests/test_vision/test_worker_commands.py tests/test_physical_play_orchestrator.py tests/test_engine_physical_integration.py tests/test_play_ai_endgame.py tests/test_vision_bind_state.py tests/test_vision_move_poller.py tests/test_physical_play_recovery.py tests/web_ui/test_ai_ladder_api.py -q`

  Expected: all selected tests pass.

- [ ] **Step 8: Verify the two worker copies did not drift**

  Run: `git diff --check && git diff -- katrain/vision/worker.py katrain/vision/worker_inprocess.py`

  Expected: both `SET_EXPECTED_BOARD` handlers have the same revision behavior; unrelated in-process/subprocess differences remain untouched.

- [ ] **Step 9: Add an observable confirmation-path diagnostic in both workers**

  Without changing the adaptive threshold, snapshot the candidate sighting count before `detect_new_move`, compute the selected slow/fast `required_frames` for logging, and add `required_frames=<n> observed_frames=<n>` to both the ordinary-confirm and ambiguous-confirm log lines. Continue passing `None` to `detect_new_move` for the unknown/slow path so its existing safe default is unchanged.

  This is the device acceptance probe for “unknown confidence really used five frames”; timing alone cannot prove which branch was selected. Apply the identical diagnostic fields in `worker.py` and `worker_inprocess.py`.

- [ ] **Step 10: Commit the transport contract**

  Run: `git add katrain/vision/service.py katrain/vision/worker.py katrain/vision/worker_inprocess.py katrain/web/core/physical_play_orchestrator.py katrain/web/api/v1/endpoints/vision.py katrain/web/server.py tests && git commit -m "carry board revision through vision sync"`

### Task 3: Broadcast state before a node-associated move sound

**Files:**

- Modify: `katrain/web/interface.py`
- Create: `tests/web_ui/test_move_sound_order.py`

- [ ] **Step 1: Write focused failing tests with a real `WebKaTrain` fixture**

  Reuse the smallest existing constructor pattern from `tests/web_ui/test_ladder_injection.py` or `tests/test_play_ai_endgame.py`. Record `message_callback` and the replacement `update_state` into one ordered list.

  Cover:

  ```python
  def test_ai_move_broadcasts_state_before_its_node_associated_sound(...):
      # generate_ai_move commits one deterministic move
      # update_state appends ("state", id(wkt.game.current_node))
      # message_callback records ("sound", payload)
      # assert order == [state, sound]
      # assert payload["after_node_id"] == committed current_node_id

  def test_human_move_sound_contains_the_resulting_node_id(...):
      # call _do_play on a legal point and inspect the sound payload

  def test_capture_sound_contains_the_resulting_node_id(...):
      # Build a deterministic corner capture, commit it, and assert the capturing
      # payload carries id(the capturing node).

  def test_ai_sound_uses_pre_broadcast_snapshot_when_update_state_navigates(...):
      # update_state deliberately undoes/navigates, as the existing terminal race
      # test does. The post-broadcast sound must still describe the committed move
      # and carry the committed node id.

  def test_pass_does_not_emit_a_stone_sound(...):
      # Preserve current behavior.
  ```

- [ ] **Step 2: Run the new tests and verify current ordering fails**

  Run: `.venv/bin/python -m pytest tests/web_ui/test_move_sound_order.py -v`

  Expected: FAIL because AI sound currently occurs inside `_do_ai_move` before `update_state`, and payload lacks `after_node_id`.

- [ ] **Step 3: Make sound payload construction node-aware**

  Split choosing a sound from emitting it. The chooser returns `None`, `capturing`, or a concrete `stoneN` string while the committed game/node state is still stable. Call the emitter **only** for a concrete name, so `None` has one meaning (pass/no sound) and can never trigger a later recomputation from mutable state:

  ```python
  def play_stone_sound(self, sound_name: str, *, after_node_id: int | None = None):
      if self.message_callback:
          payload = {"sound": sound_name}
          if after_node_id is not None:
              payload["after_node_id"] = after_node_id
          self.message_callback("sound", payload)
  ```

  In `_do_play`, use the already-captured successful `node`; snapshot the sound name for that committed move and, only when it is non-`None`, call `play_stone_sound(sound_name, after_node_id=id(node))`. Keep pass suppression unchanged.

- [ ] **Step 4: Move only the AI sound across the state broadcast**

  Remove `self.play_stone_sound()` from `_do_ai_move`. In `_do_ai_move_and_broadcast`:

  - snapshot `before_node` before generation;
  - run `_do_ai_move(cn)`;
  - capture `committed_node` only if the current node changed;
  - before any callback can move the cursor, snapshot the committed move's sound name (including whether it captured or passed);
  - call `update_state()` in the existing `finally` path;
  - only after that call, emit the precomputed `sound_name` with `after_node_id=id(committed_node)`;
  - emit nothing for resign/failure/no-move.

  Preserve the existing terminal snapshot ordering and `game_ended_callback` semantics.

- [ ] **Step 5: Run sound and adjacent interface regression tests**

  Run: `.venv/bin/python -m pytest tests/web_ui/test_move_sound_order.py tests/web_ui/test_session_broadcast_surface.py tests/web_ui/test_ladder_injection.py tests/test_play_ai_endgame.py -q`

  Expected: all pass; `sound` remains a literal callback type for the broadcast-surface AST test.

- [ ] **Step 6: Commit the backend sound fix**

  Run: `git add katrain/web/interface.py tests/web_ui/test_move_sound_order.py && git commit -m "play move sounds after state broadcast"`

---

## Chunk 2 — Frontend synchronization and one recovery surface

### Task 4: Queue node-associated sounds until the matching board has painted

**Files:**

- Modify: `katrain/web/ui/src/hooks/useGameSession.ts`
- Create: `katrain/web/ui/src/hooks/useGameSession.sound.test.tsx`

- [ ] **Step 1: Write failing hook tests around the existing mock WebSocket pattern**

  Reuse the socket harness from `useGameSession.connection.test.tsx`. Stub `Audio`, `requestAnimationFrame`, and `cancelAnimationFrame` deterministically. Test:

  1. sound for node 12 arriving before `game_update` node 12 does not call `play()`;
  2. matching `game_update` commits, first RAF runs, second RAF runs, then exactly one play occurs;
  3. state node 12 arriving first followed by sound node 12 follows the same two-RAF path;
  4. FIFO order is preserved for two node-associated sounds;
  5. a legacy sound without `after_node_id` plays immediately;
  6. changing session/game or closing the socket cancels queued/scheduled playback.

- [ ] **Step 2: Run the new hook test and see immediate playback fail it**

  Run: `cd katrain/web/ui && npx vitest run src/hooks/useGameSession.sound.test.tsx`

  Expected: FAIL because the current `sound` branch calls `playSound` immediately.

- [ ] **Step 3: Add a minimal FIFO and committed-state refs**

  Inside `useGameSession`, add refs for:

  ```ts
  type QueuedSound = { sound: string; afterNodeId: number };
  const soundQueueRef = useRef<QueuedSound[]>([]);
  const committedNodeRef = useRef<number | null>(null);
  const committedGameRef = useRef<string | null>(null);
  const soundRafRef = useRef<number[]>([]);
  ```

  Keep `playSound` as the single audio-cache and duplicate-suppression owner.

- [ ] **Step 4: Flush only the FIFO head whose node matches the committed state**

  Add one callback that:

  - checks the FIFO head against `committedNodeRef.current`;
  - schedules `requestAnimationFrame(() => requestAnimationFrame(() => playSound(...)))`;
  - removes only that head;
  - continues with the next matching head after playback;
  - stores both RAF ids for cancellation.

  Use a layout/commit effect keyed by `gameState?.game_id` and `gameState?.current_node_id` to update the committed refs and ask the queue to flush. Do not play from the WebSocket handler merely because a state message was received.

- [ ] **Step 5: Change the WebSocket sound branch compatibly**

  ```ts
  if (typeof msg.data.after_node_id === 'number') {
    soundQueueRef.current.push({ sound: msg.data.sound, afterNodeId: msg.data.after_node_id });
    flushQueuedSounds();
  } else {
    playSound(msg.data.sound);
  }
  ```

  On socket close, session change, game-id change, and unmount, clear the queue and cancel every recorded RAF. Do not clear merely because an unrelated state field changes.

- [ ] **Step 6: Run the hook tests and the connection regression**

  Run: `cd katrain/web/ui && npx vitest run src/hooks/useGameSession.sound.test.tsx src/hooks/useGameSession.connection.test.tsx src/hooks/useGameSession.test.ts`

  Expected: all pass.

- [ ] **Step 7: Commit frontend audio synchronization**

  Run: `git add katrain/web/ui/src/hooks/useGameSession.ts katrain/web/ui/src/hooks/useGameSession.sound.test.tsx && git commit -m "sync move sounds with painted board state"`

### Task 5: Move the AI placement instruction into the right-rail status slot

**Files:**

- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/__tests__/GamePageLedBadge.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx`

- [ ] **Step 1: Rewrite the old banner tests as failing status-slot tests**

  Replace `ai-move-banner` expectations with assertions that:

  - no `[data-testid="ai-move-banner"]` exists;
  - `.gtoggles .ghint` contains the coordinate instruction in physical AI play;
  - screen-only and human-vs-human games do not show it;
  - a hardware fault replaces the instruction;
  - login/count hints resume only after the physical instruction is cleared.

  Add node-causality cases in `GamePage.test.tsx`:

  - `synced` with matching `expected_node_id` clears;
  - matching `synced` arriving before the corresponding `game_update` prevents a stale hint from appearing;
  - with a hint already visible, a matching `synced` followed by an unrelated vision event in the same React batch still clears it;
  - stale, different-node, and unversioned `synced` do not clear;
  - first game-state load can create the hint (it is not mistaken for a scope change);
  - real game end, `game_id` change, session change, and leaving physical play clear.

  In the `GamePage.test.tsx` mock for `GameControlPanel`, render the received `physicalStatus` into a `.ghint` element. That makes this test prove prop wiring instead of merely proving local state exists.

- [ ] **Step 2: Run the focused page/panel tests and confirm failure**

  Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/__tests__/GamePageLedBadge.test.tsx src/kiosk/components/game/GameControlPanel.test.tsx`

  Expected: FAIL because the old absolute banner still owns the instruction and the panel has no physical status prop.

- [ ] **Step 3: Add the status-slot prop and priority**

  Add `physicalStatus?: string | null` to `GameControlPanel`. Render `.ghint` as:

  ```tsx
  {hardwareFault
    ?? physicalStatus
    ?? (analysisRequiresLogin
      ? t('play:analysis_requires_login_hint', '领地 / 支招 / 图表 登录后可用')
      : !isGameOver && !canCount
        ? t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin))
        : '')}
  ```

  Preserve `data-fault` styling only for actual hardware faults.

- [ ] **Step 4: Store coordinate text and the causal AI node together**

  Replace `aiMoveBanner: string | null` with a single object:

  ```ts
  interface AiPlacementStatus {
    scopeKey: string;
    nodeId: number;
    text: string;
  }
  ```

  Define `scopeKey` from `sessionId` plus `gameState.game_id`. When an AI move leaves the human to move, construct the existing localized coordinate/color instruction and store the scope plus `gameState.current_node_id`. Pass the text to `GameControlPanel` only when its stored scope equals the current scope, `physicalPlay` is true, and an AI seat is active. A changed game id therefore hides stale text synchronously before effects run.

- [ ] **Step 5: Clear only on the correct vision acknowledgement or lifecycle boundary**

  Process `visionSync.syncEvents` by their monotonic `seq` and store versioned `synced` node ids in a small bounded ref-backed set/list (for example, the most recent 128 ids). This cache handles either WebSocket order: an acknowledgement may arrive before or after the matching game state. Process acknowledgement events before the effect that creates an AI placement status.

  While processing every newly sequenced versioned `synced`, add its id to the cache **and** clear the current status when:

  ```ts
  event.type === 'synced'
    && event.data.expected_node_id === aiPlacementStatus.nodeId
  ```

  Do not base this clear on `latestEvent`: React may batch the matching acknowledgement with a later unrelated event. Before creating a status, check the acknowledgement cache; if that node was already acknowledged, do not display a stale instruction. Clear the cache when the bound session changes or the vision connection is recreated, but do not discard a just-arrived node acknowledgement merely because `game_id` arrived later on the other WebSocket.

  For lifecycle clearing, avoid a mount-time `useEffect(() => setStatus(null), [scopeKey])` race. Store `scopeKey` in the status as above, hide mismatched scope during render, and let the same derivation effect either create the new scope's status or clear for end/physical-off. Clear explicitly on session change. Do not clear on a timer, an unversioned event, or an unrelated node.

- [ ] **Step 6: Remove the board-covering markup**

  Delete the absolute bottom `<Box data-testid="ai-move-banner">` and any now-unused `Lightbulb` import. Do not add replacement absolute positioning or CSS.

- [ ] **Step 7: Run focused UI tests**

  Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/GamePage.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/__tests__/GamePageLedBadge.test.tsx src/kiosk/components/game/GameControlPanel.test.tsx`

  Expected: all pass.

- [ ] **Step 8: Commit the non-overlapping placement status**

  Run: `git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.test.tsx katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx katrain/web/ui/src/kiosk/__tests__/GamePageLedBadge.test.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx && git commit -m "move AI placement hint into status rail"`

### Task 6: Make recovery event transitions pure and conservative

**Files:**

- Create: `katrain/web/ui/src/kiosk/components/vision/visionRecovery.ts`
- Create: `katrain/web/ui/src/kiosk/components/vision/visionRecovery.test.ts`

- [ ] **Step 1: Write failing pure-helper tests**

  Define tuple-based test data and cover:

  ```ts
  classifyAdjacentRelocation([[18, 4, 2]], [[18, 5, 2]])
  // => { from: [18, 4], to: [18, 5], color: 2 }

  classifyAdjacentRelocation([[18, 4, 1]], [[18, 5, 2]]) // null: colors differ
  classifyAdjacentRelocation([[18, 4, 2]], [[18, 6, 2]]) // null: too far
  classifyAdjacentRelocation(twoExtras, oneMissing)       // null: ambiguous
  ```

  Add reducer/transition tests for:

  - `move_pending` followed by the exact one-extra/no-missing `illegal_change` is suppressed for four seconds;
  - any extra position or any missing point prevents suppression;
  - deadline expiry releases suppression;
  - node advance, ambiguous, capture, board loss, and synced clear pending;
  - capture outranks/clears ambiguous and mismatch;
  - ambiguous outranks/clears mismatch;
  - `captures_cleared` only relinquishes capture ownership;
  - adjacent relocation becomes a targeted stone recovery; non-adjacent/multi-stone remains mismatch.

- [ ] **Step 2: Run the absent-helper test**

  Run: `cd katrain/web/ui && npx vitest run src/kiosk/components/vision/visionRecovery.test.ts`

  Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement one discriminated recovery state**

  Keep the helper small and presentation-oriented:

  ```ts
  export type VisionPos = [number, number, number];
  export type BlockingRecovery =
    | { kind: 'capture'; positions: Array<{ row: number; col: number; color: number }> }
    | { kind: 'stone'; row: number; col: number; color?: number; unbacked: boolean; from?: [number, number] }
    | { kind: 'mismatch'; positions: VisionPos[]; missing: VisionPos[] };

  export interface RecoveryState {
    pending: { row: number; col: number; color: number; expiresAt: number } | null;
    blocking: BlockingRecovery | null;
  }
  ```

  Export a pure `classifyAdjacentRelocation(positions, missing)` and a pure transition function over an explicit internal action union:

  ```ts
  export type RecoveryAction =
    | { kind: 'vision_event'; event: VisionSyncEvent; nowMs: number }
    | { kind: 'node_advanced' }
    | { kind: 'pending_deadline'; nowMs: number };
  ```

  Use Chebyshev distance `Math.max(Math.abs(dr), Math.abs(dc)) === 1`. Do not guess if counts/colors fail the exact rule. Convert capture tuples from the wire into the object shape already accepted by `CaptureGuide` inside the pure transition, so render code remains type-safe.

- [ ] **Step 4: Implement exact pending-mismatch suppression**

  Suppress only when, before `expiresAt`:

  ```ts
  positions.length === 1
    && missing.length === 0
    && positions[0][0] === pending.row
    && positions[0][1] === pending.col
    && positions[0][2] === pending.color
  ```

  No fuzzy coordinate/color matching and no suppression after expiry.

- [ ] **Step 5: Run the helper tests**

  Run: `cd katrain/web/ui && npx vitest run src/kiosk/components/vision/visionRecovery.test.ts`

  Expected: all pass.

- [ ] **Step 6: Commit the pure transition layer**

  Run: `git add katrain/web/ui/src/kiosk/components/vision/visionRecovery.ts katrain/web/ui/src/kiosk/components/vision/visionRecovery.test.ts && git commit -m "define physical board recovery transitions"`

### Task 7: Render exactly one modal recovery surface

**Files:**

- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/physical/AmbiguousMoveCard.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx` (pass `currentNodeId`)

- [ ] **Step 1: Expand overlay tests before implementation**

  Add `currentNodeId` to the fixture props and use fake timers. Cover:

  - off-centre prompt renders as a dialog and no mismatch dialog is simultaneously present;
  - backed low-confidence ambiguous event retains “检测到疑似落子” wording;
  - `move_pending` plus exact matching `illegal_change` shows no mismatch before four seconds;
  - after four seconds, the same subsequent mismatch can show;
  - changing `currentNodeId` clears pending suppression;
  - one adjacent same-color extra/missing pair says “从 E1 挪到 F1” (coordinates based on fixture) and does not render the generic mismatch title;
  - different color, distance > 1, or multiple stones renders generic mismatch;
  - capture, ambiguous, mismatch, and persistent board loss never produce more than one open MUI dialog;
  - after more than 100 historical events, a newly appended higher-`seq` event is still processed;
  - capture remains the owner after 30 seconds and offers no manual skip; only `captures_cleared` relinquishes it;
  - `synced` clears all blocking recovery state and the board-loss timer.

- [ ] **Step 2: Run overlay tests and confirm the independent states fail**

  Run: `cd katrain/web/ui && npx vitest run src/kiosk/components/vision/VisionSyncOverlay.test.tsx`

  Expected: FAIL because current mismatch/ambiguous/capture flags render independently and ambiguous is a low-z-index card.

- [ ] **Step 3: Replace independent blocking flags with the transition state**

  In `VisionSyncOverlay`:

  - keep toast state independent because it is non-blocking;
  - track the last processed `VisionSyncEvent.seq`, not an array index; process `syncEvents.filter(event => event.seq > lastProcessedSeq)`, then advance to the largest processed seq. This remains correct when `useVisionSync` trims its array to 100 entries;
  - feed every newly sequenced event through the pure transition function in order;
  - schedule one timeout for the current pending candidate's `expiresAt`, cancelling/replacing it when the pending candidate changes;
  - clear pending on the new `currentNodeId` prop changing;
  - retain the 10-second board-lost persistence timer, but derive the visible surface as `blocking ?? persistentBoardLost`;
  - on `synced`, also cancel/close board-lost presentation.

- [ ] **Step 4: Convert the ambiguous/off-centre card to the MUI modal layer**

  Keep the component name to minimize callers, but render `Dialog`, `DialogTitle`, `DialogContent`, and `DialogActions` instead of an absolutely positioned `Card`. Add an optional `from` coordinate for relocation wording:

  ```text
  白子没放正，请从 E1 挪到 F1
  ```

  Existing `unbacked=true` without `from` keeps “请把它挪到 D16 的交叉点上”；`unbacked=false` keeps the low-confidence confirm/ignore language.

- [ ] **Step 5: Localize the new relocation sentence in all 11 catalogs**

  Add one placeholder-based key such as `vision:offcenter_move_from_to` to every tracked `.po` catalog under `katrain/i18n/locales/{cn,de,en,es,fr,jp,ko,ru,tr,tw,ua}/LC_MESSAGES/katrain.po`. Preserve `{color}`, `{from}`, and `{to}` exactly in every translation. The component should call the existing translation hook and replace these placeholders; do not hard-code the Chinese sentence as the only runtime text.

  Run: `.venv/bin/python i18n.py`

  Expected: all 11 `.mo` files regenerate successfully. They are runtime artifacts ignored by Git, so verify their timestamps/existence but commit the `.po` sources only.

- [ ] **Step 6: Render from the single active recovery value**

  Render exactly one of:

  1. `CaptureGuide`;
  2. modal `AmbiguousMoveCard` for off-centre/relocation/low confidence;
  3. `BoardMismatchDialog`;
  4. persistent board-lost dialog.

  Preserve existing callbacks:

  - unbacked/off-centre “我挪一下” must not call `visionResetSync('physical')`;
  - backed low-confidence ignore still adopts the physical baseline;
  - confirm still converts row/col to the correct play coordinate.

  Render `CaptureGuide` without `onDismiss`. Its delayed “跳过” button must not appear, because capture ownership ends only on `captures_cleared`; a local dismiss would hide the only instruction while the physical board still owes removals.

- [ ] **Step 7: Run overlay and page regression tests**

  Run: `cd katrain/web/ui && npx vitest run src/kiosk/components/vision/visionRecovery.test.ts src/kiosk/components/vision/VisionSyncOverlay.test.tsx src/kiosk/pages/GamePage.test.tsx`

  Expected: all pass.

- [ ] **Step 8: Commit the single-surface recovery UI**

  Run: `git add katrain/web/ui/src/kiosk/components/vision katrain/web/ui/src/kiosk/components/physical/AmbiguousMoveCard.tsx katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/i18n/locales/*/LC_MESSAGES/katrain.po && git commit -m "show one physical board recovery dialog"`

---

## Chunk 3 — Runtime build check, integration, and RK3562 acceptance

### Task 8: Accept a valid prebuilt kiosk bundle before checking for npm

**Files:**

- Modify: `katrain/web/server.py`
- Create: `tests/web_ui/test_frontend_build.py`

- [ ] **Step 1: Write the failing runtime-build test**

  Use `tmp_path` to create a fake `web/ui/package.json` and `web/static-kiosk-2d/index.html`; monkeypatch `katrain.web.server.__file__`, board mode, and `shutil.which("npm") -> None`.

  Assert that `build_frontend(force=False)` logs “Frontend already built” and does not log “npm not found”. Add a second test that no bundle plus no npm still logs the existing warning.

- [ ] **Step 2: Run the test and confirm current ordering fails**

  Run: `.venv/bin/python -m pytest tests/web_ui/test_frontend_build.py -v`

  Expected: FAIL because npm is checked before `static-kiosk-2d/index.html`.

- [ ] **Step 3: Reorder existing checks only**

  In `build_frontend`:

  1. determine board/full mode and the matching output directory;
  2. if matching `index.html` exists and `force` is false, return successfully;
  3. only then check `shutil.which("npm")` for a build that is actually needed.

  Do not alter the build commands, source-presence check, `--force-build` behavior, or SmartBox manifest validation.

- [ ] **Step 4: Run test and syntax/diff checks**

  Run: `.venv/bin/python -m pytest tests/web_ui/test_frontend_build.py -q`

  Run: `git diff --check -- katrain/web/server.py tests/web_ui/test_frontend_build.py`

  Expected: pass with no formatting spill in `server.py`.

- [ ] **Step 5: Commit the runtime check fix**

  Run: `git add katrain/web/server.py tests/web_ui/test_frontend_build.py && git commit -m "prefer prebuilt kiosk frontend at runtime"`

### Task 9: Run focused integration gates and inspect the final diff

**Files:** all files changed above.

- [ ] **Step 1: Reconcile any `develop` movement that occurred during implementation**

  Run: `git fetch origin develop`

  Run: `git rev-list --left-right --count origin/develop...HEAD`

  If the left count is non-zero, run `git merge origin/develop`, resolve only actual conflicts, and continue with the complete gates below. If the right count is zero, stop: the feature commits are not present.

  Expected: the tree tested below contains both the newest remote `develop` and every feature commit; this exact tree is what will later be merged and deployed.

- [ ] **Step 2: Run the focused Python suite**

  Run:

  ```bash
  .venv/bin/python -m pytest \
    tests/test_vision/test_sync.py \
    tests/test_vision/test_worker_commands.py \
    tests/test_physical_play_orchestrator.py \
    tests/test_engine_physical_integration.py \
    tests/test_physical_play_recovery.py \
    tests/test_vision_bind_state.py \
    tests/test_vision_move_poller.py \
    tests/web_ui/test_move_sound_order.py \
    tests/web_ui/test_frontend_build.py \
    tests/web_ui/test_session_broadcast_surface.py \
    tests/web_ui/test_ladder_injection.py \
    tests/test_play_ai_endgame.py \
    tests/web_ui/test_ai_ladder_api.py -q
  ```

  Expected: all selected tests pass. This is a focused suite, so do not accept failures by count or attribute them to the unrelated full-suite noise.

- [ ] **Step 3: Run focused frontend tests**

  Run:

  ```bash
  cd katrain/web/ui && npx vitest run \
    src/hooks/useGameSession.sound.test.tsx \
    src/hooks/useGameSession.connection.test.tsx \
    src/kiosk/components/vision/visionRecovery.test.ts \
    src/kiosk/components/vision/VisionSyncOverlay.test.tsx \
    src/kiosk/components/game/GameControlPanel.test.tsx \
    src/kiosk/pages/GamePage.test.tsx \
    src/kiosk/__tests__/GamePageEngine.test.tsx \
    src/kiosk/__tests__/GamePageLedBadge.test.tsx
  ```

  Expected: all pass.

- [ ] **Step 4: Run the real TypeScript and production kiosk build gates**

  Run: `cd katrain/web/ui && npx tsc -b`

  Run: `cd katrain/web/ui && npm run build:smartbox-kiosk-2d`

  Expected: exit 0; `katrain/web/static-kiosk-2d/.smartbox-build.json` is generated and strict verification passes.

- [ ] **Step 5: Inspect only the intended final diff**

  Run: `git status --short && git diff origin/develop...HEAD --stat && git diff --check`

  Expected: approved design, focused backend/frontend/test changes, and generated kiosk bundle only if this repository intentionally tracks it. No broad formatting or unrelated files.

- [ ] **Step 6: Run implementation review before integration**

  Use `superpowers:requesting-code-review` on `origin/develop...HEAD`. Address only findings grounded in the approved spec, then rerun the affected focused test plus `npx tsc -b` if TypeScript changed.

### Task 10: Integrate KaTrain and update the SmartBox vendor pointer

**Files/repos:**

- `/Users/fan/Repositories/katrain-kiosk-debug`
- `/Users/fan/Repositories/smartbox-software/vendor/katrain`

- [ ] **Step 1: Confirm the feature branch is complete and clean**

  Run: `git status --short`

  Expected: empty output. If generated files are intentionally ignored, verify them separately; do not force-add unrelated artifacts.

- [ ] **Step 2: Push the feature branch**

  Run: `git push origin fix/kiosk-ui-debug`

  Expected: the reviewed feature head exists remotely before integration.

- [ ] **Step 3: Merge from the worktree that actually owns `develop`**

  `develop` is already checked out at `/Users/fan/Repositories/katrain`; do not try to switch this feature worktree to it. Preserve its unrelated untracked `m.html` and require only tracked/index cleanliness:

  ```bash
  git -C /Users/fan/Repositories/katrain diff --quiet
  git -C /Users/fan/Repositories/katrain diff --cached --quiet
  git -C /Users/fan/Repositories/katrain fetch origin develop
  git -C /Users/fan/Repositories/katrain merge-base --is-ancestor origin/develop fix/kiosk-ui-debug
  git -C /Users/fan/Repositories/katrain merge --ff-only origin/develop
  git -C /Users/fan/Repositories/katrain merge --no-ff fix/kiosk-ui-debug
  git -C /Users/fan/Repositories/katrain push origin develop
  ```

  Capture the deployed revision after the merge:

  Run: `git -C /Users/fan/Repositories/katrain rev-parse HEAD`

  Expected: remote `develop` points at a merge whose tree is the already-reviewed combined tree. If the ancestry check fails, `origin/develop` advanced after Task 9: return to Task 9, merge it into the feature branch, and repeat all gates/review. If tracked/index cleanliness or `--ff-only` fails, stop; do not reset or touch `m.html`.

- [ ] **Step 4: Update only the SmartBox KaTrain gitlink**

  The SmartBox branch is `main` and currently has an unrelated unstaged `vendor/hermes-agent` change. Preserve it. First require an empty index, then fast-forward `main` only if that does not collide:

  ```bash
  git -C /Users/fan/Repositories/smartbox-software diff --cached --quiet
  git -C /Users/fan/Repositories/smartbox-software fetch origin main
  git -C /Users/fan/Repositories/smartbox-software merge --ff-only origin/main
  ```

  Capture the actual KaTrain merge SHA, then detach only the KaTrain submodule at it:

  ```bash
  KATRAIN_DEPLOY_SHA=$(git -C /Users/fan/Repositories/katrain rev-parse HEAD)
  git -C /Users/fan/Repositories/smartbox-software/vendor/katrain fetch origin develop
  git -C /Users/fan/Repositories/smartbox-software/vendor/katrain switch --detach "$KATRAIN_DEPLOY_SHA"
  git -C /Users/fan/Repositories/smartbox-software add vendor/katrain
  git -C /Users/fan/Repositories/smartbox-software diff --cached --name-only
  git -C /Users/fan/Repositories/smartbox-software diff --cached --submodule=short
  ```

  Expected: staged name output is exactly `vendor/katrain`; the displayed old/new gitlink includes `KATRAIN_DEPLOY_SHA`; `vendor/hermes-agent` remains unstaged.

  Commit and push only that gitlink:

  ```bash
  git -C /Users/fan/Repositories/smartbox-software commit -m "update KaTrain physical play synchronization"
  git -C /Users/fan/Repositories/smartbox-software push origin main
  ```

  Capture `git -C /Users/fan/Repositories/smartbox-software rev-parse HEAD` as the SmartBox deploy SHA.

### Task 11: Build, checksum, deploy, and reload the actual RK3562 kiosk bundle

**Deployment owner:** `/Users/fan/Repositories/smartbox-software/provisioning/provision.sh --section katrain`

- [ ] **Step 1: Build the strict bundle inside the vendored checkout**

  Run: `cd /Users/fan/Repositories/smartbox-software/vendor/katrain/katrain/web/ui && npm run build:smartbox-kiosk-2d`

  Expected: strict schema-1 `.smartbox-build.json` is written and `verify:kiosk-2d` passes.

- [ ] **Step 2: Generate an exact local entry-asset checksum file**

  Use `apply_patch` to create a temporary `/private/tmp/katrain-kiosk-assets.py` helper. It must:

  - parse `src=` and `href=` references from `index.html`;
  - normalize leading `/` so paths are relative to `static-kiosk-2d`;
  - include `index.html` and `.smartbox-build.json`;
  - fail if any referenced local file is absent;
  - print GNU `sha256sum -c` compatible lines: `<hex><two spaces><relative path>`.

  Run:

  ```bash
  /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python \
    /private/tmp/katrain-kiosk-assets.py \
    /Users/fan/Repositories/smartbox-software/vendor/katrain/katrain/web/static-kiosk-2d \
    > /private/tmp/katrain-kiosk-local-sha256.txt
  ```

  Expected: the file lists `index.html`, `.smartbox-build.json`, and every entry JS/CSS asset, with no missing file.

  Do not treat a directory timestamp as proof of the deployed version.

- [ ] **Step 3: Capture live mode/service state and create a recoverable device backup**

  Before writing anything, verify the direct link/SSH path with:

  Run: `/Users/fan/Repositories/smartbox-software/scripts/deploy-main-to-rk3562.sh check`

  Then create a timestamped same-filesystem hard-link backup of the exact deployed KaTrain tree and record which mutually exclusive target was active:

  ```bash
  ssh rk3562-direct 'set -eu
    stamp=$(date +%Y%m%d-%H%M%S)
    backup=/root/deploy-backups/katrain-$stamp
    mkdir -p "$backup"
    cp -al /root/smartbox-software/vendor/katrain "$backup/katrain-tree"
    : > "$backup/active-target"
    for mode in go hermes chess xiangqi gomoku; do
      if systemctl is-active --quiet "smartbox-$mode.target"; then
        printf "%s\n" "$mode" > "$backup/active-target"
        break
      fi
    done
    systemctl is-active smartbox-kiosk.service > "$backup/kiosk-state" || true
    printf "%s\n" "$backup" > /root/deploy-backups/katrain-latest
    printf "backup=%s active=%s\n" "$backup" "$(cat "$backup/active-target")"
    if [ "$(cat "$backup/active-target")" = go ]; then
      systemctl stop smartbox-go.target
    fi
  '
  ```

  Expected: the backup path and prior active mode are printed. If Go was active, it is stopped before any live Python or hashed asset is overwritten, preventing a mixed-version response. Hard links make the backup fast and recoverable; subsequent rsync's temp-file/rename replacement preserves old file contents in the backup.

  If any later deployment/check step fails, execute the rollback before further testing:

  ```bash
  ssh rk3562-direct 'set -eu
    backup=$(cat /root/deploy-backups/katrain-latest)
    stamp=$(date +%Y%m%d-%H%M%S)
    systemctl stop smartbox-go.target || true
    mv /root/smartbox-software/vendor/katrain "/root/smartbox-software/vendor/katrain.failed-$stamp"
    cp -al "$backup/katrain-tree" /root/smartbox-software/vendor/katrain
    mode=$(cat "$backup/active-target")
    systemctl stop smartbox-go.target smartbox-hermes.target smartbox-chess.target smartbox-xiangqi.target smartbox-gomoku.target || true
    if [ -n "$mode" ]; then systemctl start "smartbox-$mode.target"; fi
    systemctl restart smartbox-kiosk.service
  '
  ```

- [ ] **Step 4: Export tracked KaTrain source and copy source/bundle separately**

  The general SmartBox deploy script does **not** include submodule contents or KaTrain's ignored bundle. Export the exact committed KaTrain source, then copy it without root-level deletion so device-only models remain intact. Copy only the bundle with safely scoped `--delete`:

  ```bash
  KATRAIN_DEPLOY_SHA=$(git -C /Users/fan/Repositories/smartbox-software/vendor/katrain rev-parse HEAD)
  KATRAIN_EXPORT_DIR=$(mktemp -d /private/tmp/katrain-deploy.XXXXXX)
  git -C /Users/fan/Repositories/smartbox-software/vendor/katrain archive "$KATRAIN_DEPLOY_SHA" \
    | tar -x -C "$KATRAIN_EXPORT_DIR"
  LC_ALL=C rsync -azc \
    "$KATRAIN_EXPORT_DIR/" \
    rk3562-direct:/root/smartbox-software/vendor/katrain/
  LC_ALL=C rsync -azc --delete \
    /Users/fan/Repositories/smartbox-software/vendor/katrain/katrain/web/static-kiosk-2d/ \
    rk3562-direct:/root/smartbox-software/vendor/katrain/katrain/web/static-kiosk-2d/
  ```

  Expected: tracked source is copied at the captured SHA; old hashed files are deleted only inside `static-kiosk-2d`; device-only model files and unrelated SmartBox modules are untouched.

- [ ] **Step 5: Prove remote entry assets match before provisioning or restart**

  Run:

  ```bash
  scp /private/tmp/katrain-kiosk-local-sha256.txt rk3562-direct:/tmp/katrain-kiosk-local-sha256.txt
  ssh rk3562-direct 'set -eu
    cd /root/smartbox-software/vendor/katrain/katrain/web/static-kiosk-2d
    sha256sum -c /tmp/katrain-kiosk-local-sha256.txt
  '
  ```

  Expected: every line ends in `OK`. Stop and roll back on the first missing or mismatched asset.

- [ ] **Step 6: Run the production provisioning section**

  Run: `ssh rk3562-direct 'cd /root/smartbox-software && provisioning/provision.sh --section katrain'`

  Expected: the strict schema-1 prebuilt-manifest validation passes and provisioning exits 0. This section installs/compiles; it does not itself prove services restarted.

- [ ] **Step 7: Switch explicitly to Go, restart the changed service, and verify 8081**

  Run:

  ```bash
  ssh rk3562-direct 'set -eu
    systemctl stop smartbox-hermes.target smartbox-chess.target smartbox-xiangqi.target smartbox-gomoku.target || true
    systemctl start smartbox-go.target
    systemctl restart smartbox-katrain.service
    systemctl restart smartbox-kiosk.service
    for i in $(seq 1 90); do
      if curl -fsS http://127.0.0.1:8081/health >/tmp/katrain-health.json \
        && curl -fsS -o /dev/null http://127.0.0.1:8081/kiosk; then break; fi
      sleep 1
    done
    systemctl is-active smartbox-go.target smartbox-katrain.service smartbox-kiosk.service
    curl -fsS http://127.0.0.1:8081/health
    curl -fsS -o /dev/null http://127.0.0.1:8081/kiosk
  '
  ```

  Expected: Go target, KaTrain, and Chromium kiosk service are active; both KaTrain probes succeed on port 8081. Ports 8001 and 8787 are unrelated modes and are not acceptance probes.

- [ ] **Step 8: Navigate Chromium to the exact Go URL, disable cache, and inspect loaded assets**

  Start a local SSH tunnel to the board's loopback-only CDP port and keep its exec session open:

  Run: `ssh -N -L 19222:127.0.0.1:9222 rk3562-direct`

  Use `apply_patch` to create `/private/tmp/katrain-cdp-verify.mjs`. With Node 22's built-in `fetch` and `WebSocket`, it must:

  1. select the page target from `http://127.0.0.1:19222/json/list`;
  2. connect to that target's WebSocket through port 19222;
  3. call `Network.setCacheDisabled({cacheDisabled:true})`;
  4. call `Page.enable` before relying on page-domain notifications;
  5. register a one-shot `Page.loadEventFired` waiter **before** sending `Page.navigate({url:'http://127.0.0.1:8081/kiosk'})`, then await it;
  6. register the next waiter before sending `Page.reload({ignoreCache:true})`, then await it;
  7. evaluate and print JSON containing `location.href`, `document.scripts[*].src`, and stylesheet links.

  Run: `node /private/tmp/katrain-cdp-verify.mjs`

  Expected: href is exactly `http://127.0.0.1:8081/kiosk` (allowing its normal trailing slash/route suffix), and entry JS/CSS basenames equal those listed in `/private/tmp/katrain-kiosk-local-sha256.txt`.

- [ ] **Step 9: Capture and inspect one real 1024×600 kiosk screenshot**

  Run:

  ```bash
  ssh rk3562-direct 'DISPLAY=:0 scrot /tmp/katrain-physical-sync-20260917.png'
  scp rk3562-direct:/tmp/katrain-physical-sync-20260917.png /private/tmp/katrain-physical-sync-20260917.png
  ```

  Open `/private/tmp/katrain-physical-sync-20260917.png` with the image viewer. Verify Chromium is full-screen on the Go kiosk and the right rail is unobstructed. This is one focused visual check, not a full screenshot matrix.

### Task 12: Run the physical-board acceptance script and report measured latency

**Environment:** RK3562 with the final Board B v7, camera calibrated, at least 120 stones on the board.

- [ ] **Step 1: Start a fresh physical free-play game and record identifiers**

  Capture an unambiguous systemd journal cursor before the first test action:

  ```bash
  ssh rk3562-direct "journalctl -u smartbox-katrain.service -n 0 --show-cursor --no-pager" \
    | sed -n 's/^-- cursor: //p' > /private/tmp/katrain-acceptance-cursor.txt
  test -s /private/tmp/katrain-acceptance-cursor.txt
  ```

  Then record `session_id`, `game_id`, and the relevant service log start cursor. Confirm the page is using physical play and the camera pose is locked.

- [ ] **Step 2: Verify paint-before-sound**

  Let the AI play at least three ordinary moves. For each move, observe that the digital stone is visibly painted before the stone sound. Confirm the right-rail instruction names the same coordinate and no bottom banner covers the board.

- [ ] **Step 3: Verify causal hint dismissal**

  Before placing the AI stone, confirm the right-rail instruction remains. Place the stone correctly and verify it disappears only after a log event `synced` carrying that AI node's `expected_node_id`.

- [ ] **Step 4: Verify off-centre recovery**

  Place one stone between adjacent intersections or confidently on the adjacent intersection. Confirm within 3 seconds:

  - exactly one modal instruction is visible;
  - it identifies the point, or says to move from the detected adjacent point to the missing point;
  - the generic mismatch dialog is not stacked with it;
  - correcting the stone produces `synced` and closes the prompt automatically.

- [ ] **Step 5: Verify late-game speed without changing thresholds**

  On a position with at least 120 stones, play a representative series including:

  - at least five clear high-confidence moves;
  - one intentionally marginal/low-confidence move;
  - hand motion outside the calibrated board while a legal move is being confirmed.

  Record from logs:

  - `enh` and `infer` duration for at least 30 consecutive **emitted timing samples**, average and p95. The worker logs timing every 30th processed frame, so these samples span roughly 900 processed frames; do not describe them as 30 adjacent frames;
  - first `move_pending` to `Vision move submitted` or `ambiguous_stone`;
  - the confirmation diagnostic's `required_frames` and `observed_frames` for each tested move;
  - off-centre prompt/correction to matching `synced`.

  Acceptance:

  - representative high-confidence moves confirm within 1.2 seconds;
  - the intentionally low/unknown-confidence move has a confirmation log with `required_frames=5 observed_frames=5` (or more sightings only when documented miss-grace behavior intervened); timing alone is not accepted as proof of the slow path;
  - off-centre targeted prompt appears within 3 seconds;
  - outside-board motion does not postpone confirmation;
  - enhancement plus inference averages approximately 410 ms or less, with p95/spikes reported separately;
  - no legal single-stone move remains blocked for tens of seconds by a stale mismatch.

  Export the exact measurement window:

  ```bash
  ACCEPTANCE_CURSOR=$(cat /private/tmp/katrain-acceptance-cursor.txt)
  ssh rk3562-direct "journalctl -u smartbox-katrain.service --after-cursor '$ACCEPTANCE_CURSOR' --no-pager -o short-unix" \
    > /private/tmp/katrain-physical-acceptance.log
  ```

  Use `apply_patch` to create `/private/tmp/summarize-katrain-vision-timing.py`. It must parse the existing `enh=<n>ms infer=<n>ms` pairs, fail when fewer than 30 emitted samples exist, and print sample count, arithmetic mean of `enh+infer`, nearest-rank p95, and maximum. It must also print every confirmation line containing `required_frames` / `observed_frames` and the timestamped `move_pending`, `ambiguous_stone`, `synced`, and `Vision move submitted` trace used for interaction latency.

  Run: `.venv/bin/python /private/tmp/summarize-katrain-vision-timing.py /private/tmp/katrain-physical-acceptance.log`

- [ ] **Step 6: Report the measured result, not just “deployed”**

  Summarize:

  - deployed KaTrain and SmartBox commit SHAs;
  - local/remote entry asset filename and checksum match;
  - service/health result;
  - paint-before-sound result;
  - right-rail and off-centre recovery result;
  - measured confirmation, recovery, and frame timings;
  - any failed acceptance item with its exact event trace.

---

## Completion criteria

- Backend sounds carry `after_node_id`; AI state broadcasts before its sound.
- Node-associated sounds play only after the matching React state has committed and painted.
- AI placement text is in `.ghint`, never over the board, and clears only on the matching exact-board acknowledgement or an explicit lifecycle boundary.
- Expected-board revision survives unchanged matrices and is acknowledged exactly once only after exact physical equality.
- The vision UI presents at most one blocking recovery surface and conservatively recognizes adjacent same-color relocation.
- Focused pytest/Vitest suites, `npx tsc -b`, and `npm run build:smartbox-kiosk-2d` pass.
- The strict bundle is checksum-verified on RK3562, Chromium loads its entry asset, and the representative 120+-stone device run meets or clearly reports the timing targets.
