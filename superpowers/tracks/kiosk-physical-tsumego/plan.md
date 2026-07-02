# Kiosk 死活棋物理棋盘化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **修订 v2（2026-07-02）**：吸收 Codex/Gemini 外部评审（`review-feedback-codex.md` / `review-feedback-gemini.md`，均已逐条对照代码核实）。主要变化：事件消费改队列式（seq）、`/ws/vision` 改服务端 fan-out 泵、应手竞态用 `scheduledReply` 元数据消解、答错恢复改 failed 快照、屏幕/物理双输入统一走 `MOVE_APPLIED`、提示白灯与试下退出校验落地、move 检测显式 arm、相位机抽纯 reducer 并加 vitest 测试。采纳/否决记录见文末「Review 修订记录」。

**Goal:** kiosk 死活棋做题页接入物理棋盘——LED 引导摆放初始局面/对方应手/提示，摄像头识别物理落子并注入现有前端判题逻辑，答对/答错三通道反馈，并修复答对提示乱码（emoji 缺字形）与两端文案不统一。

**Architecture:** 判题 100% 在前端（`useTsumegoProblem` 沿 SGF 树），因此物理编排放前端。相位机抽成**纯 reducer**（`physicalTsumegoMachine.ts`，输入事件 → 新状态 + 声明式 commands，vitest 可测），hook `usePhysicalTsumego` 负责执行 commands（REST/LED/语音/placeStone）。后端接线：vision worker 增加「monitor 模式」（不绑 game session 也喂帧）、「pause」「move arm」命令、setup 的 extra-子检测（含错色子）、SETUP_COMPLETE 时 rebase MoveDetector，以及 4 个新 REST；`/ws/vision` 事件分发改为**服务端单泵 fan-out**（同时修复既有 bound 路径 WS 抢丢 ConfirmedMove 的隐患）。视觉交互统一为两种模式交替：**「逼近目标盘面」**（setup 语义，覆盖清盘/初始摆放/应手确认/错着拿除/试下恢复）与**「等一手新子」**（move 监测，仅 `ready` 相位显式 arm）。

**Tech Stack:** FastAPI + pytest（后端）；React/TS + MUI + Vite + vitest/@testing-library（前端，kiosk bundle；vitest 与 RTL 仓库已装好，`npm test` = `vitest run`）；edge-tts（语音资产预生成）。

**PRD:** 同目录 `prd.md`（设计决定 T1–T9、验收标准、风险 R1–R5 均在其中）。

## Global Constraints

- 仓库/worktree：`/Users/fan/Repositories/katrain-kiosk-physical-tsumego`，分支 `feature/kiosk-physical-tsumego`（基于 develop@96e64f53）。**所有命令在此目录执行。**
- Python 环境已装好：`uv run --no-sync pytest ...`（venv 含 web/vision/board extras + respx/pytest-asyncio/boto3/moto）。**注意 shell 有 conda 环境激活，`uv pip install` 必须带 `--python .venv/bin/python`。**
- **pytest 基线**：本 commit 上 `CI=true uv run --no-sync pytest tests` 有 ~53 项**预存**环境性失败（需本地 KataGo/数据）。逐任务验证只跑指定测试文件；最终回归对比失败清单，**不新增失败**即通过。
- **前端单测**：`cd katrain/web/ui && npm test`（vitest run；Playwright 的 `tests/**` 已被 vitest exclude）。改前端逻辑的任务须保持 vitest 全绿。
- Python：Black 120 列（`uv run black -l 120 katrain tests`）；前端遵守 kiosk 构建边界——`src/kiosk/**` 只 import 共享区（`src/components/`、`src/hooks/`、`src/api*`、`src/utils/` 等）+ `src/kiosk/`，禁止 three.js/galaxy。
- 改动共享前端文件（`src/hooks/useTsumegoProblem.ts`、`src/api.ts`、`src/api/ledApi.ts` 为共享；`src/kiosk/hooks/useVisionSync.ts` 实为 kiosk 专属）后必须双构建验证：`npm run build && npm run build:kiosk-2d`（在 `katrain/web/ui/`）。
- LED 颜色语义（不可变更）：`black`→红(255,0,0)、`white`→绿(0,255,0)、`remove`→蓝(0,0,255)；本计划新增 `hint`→白(255,255,255)。固件同亮上限 MAX_ON=200，闪烁由主机驱动（固件无 blink）。
- 硬规则：LED 绝不为几何自动闪灯（本计划不触碰几何/标定代码）。
- 坐标约定（全计划统一）：**vision 坐标** = `board[row][col]`，row 0 = 顶；**Stone 坐标** = `coords=[col, y]`，y 0 = 底。转换：`visionRow = boardSize - 1 - y`。LED REST 用 vision 坐标（row 0 = 顶）。
- **pause 契约**：`/vision/pause` 是全局布尔、**single-owner aggregate**——同一时间只有一个页面（做题页）拥有 monitor，页面把 `showHint || isTryMode` 聚合后单点下发；cleanup 必须 `visionPause(false)`。将来若有多 owner，改成 named-lock/引用计数（v1 不做，代码注释写明）。
- git 提交信息用英文 conventional commits，结尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。

---

### Task 1: SyncStateMachine setup 模式 — extra 子检测（含错色子）+ 严格完成判定

`_check_setup`（`katrain/vision/sync.py:236`）目前只统计 target 上的点：摆在**非 target 空点**上的子既不上报也不阻止 SETUP_COMPLETE；**target 点上颜色摆错的子**也只会算 missing、不会提示先取走。物理引导需要 extra 清单（拿除引导、清盘引导全靠它），且完成必须要求观测与目标**完全相等**。

口径（评审修订）：`missing` = target 有子但观测不一致的点；`extra` = 观测有子但与 target 不一致的点（含「target 空点上有子」和「target 点上错色」两类——错色点会**同时**出现在 missing 和 extra，UI 可提示「取走此处白子，放上黑子」）。

**Files:**
- Modify: `katrain/vision/sync.py:236-265`
- Test: `tests/test_vision/test_sync.py`（追加一个 class）

**Interfaces:**
- Produces: `SETUP_PROGRESS` 事件 data 变为 `{"matched": int, "total": int, "missing": [[r,c],...], "extra": [[r,c,color],...]}`；`SETUP_COMPLETE` 仅当 missing 与 extra **均为空**（等价于观测==目标）。下游（Task 7 前端类型、Task 10/11 相位机）依赖 `extra` 字段。

- [ ] **Step 1: 写失败测试**

在 `tests/test_vision/test_sync.py` 末尾追加（文件已有 `empty_board`/`board_with` helpers，见文件头）：

```python
class TestSetupModeExtraStones:
    def _machine_in_setup(self, target):
        m = SyncStateMachine()
        m.bind()
        m.confirm_pose_lock()
        m.enter_setup_mode(target)
        return m

    def test_extra_stone_reported_and_blocks_complete(self):
        target = board_with({(3, 3): BLACK})
        m = self._machine_in_setup(target)
        observed = board_with({(3, 3): BLACK, (5, 5): BLACK})  # 目标满足但多一颗
        events = m.update(observed)
        progress = [e for e in events if e.type == SyncEventType.SETUP_PROGRESS]
        assert progress and progress[0].data["extra"] == [[5, 5, BLACK]]
        assert progress[0].data["matched"] == 1
        assert not [e for e in events if e.type == SyncEventType.SETUP_COMPLETE]
        assert m.state == SyncState.SETUP_IN_PROGRESS

    def test_wrong_color_on_target_in_both_lists(self):
        """target 黑点上摆了白子：missing（缺黑）+ extra（多白）同时上报。"""
        target = board_with({(3, 3): BLACK})
        m = self._machine_in_setup(target)
        events = m.update(board_with({(3, 3): WHITE}))
        progress = [e for e in events if e.type == SyncEventType.SETUP_PROGRESS][0]
        assert progress.data["missing"] == [[3, 3]]
        assert progress.data["extra"] == [[3, 3, WHITE]]
        assert not [e for e in events if e.type == SyncEventType.SETUP_COMPLETE]

    def test_complete_requires_exact_equality(self):
        target = board_with({(3, 3): BLACK, (4, 4): WHITE})
        m = self._machine_in_setup(target)
        events = m.update(board_with({(3, 3): BLACK, (4, 4): WHITE}))
        assert [e for e in events if e.type == SyncEventType.SETUP_COMPLETE]
        assert m.state == SyncState.SYNCED

    def test_empty_target_clearing_flow(self):
        """清盘引导：target=空盘，盘上残子全部作为 extra 上报。"""
        m = self._machine_in_setup(empty_board())
        events = m.update(board_with({(0, 0): WHITE}))
        progress = [e for e in events if e.type == SyncEventType.SETUP_PROGRESS]
        assert progress[0].data == {"matched": 0, "total": 0, "missing": [], "extra": [[0, 0, WHITE]]}
        assert not [e for e in events if e.type == SyncEventType.SETUP_COMPLETE]
        events = m.update(empty_board())
        assert [e for e in events if e.type == SyncEventType.SETUP_COMPLETE]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run --no-sync pytest tests/test_vision/test_sync.py -k ExtraStones -v`
Expected: FAIL —— `KeyError: 'extra'`（前两个）；空 target 时旧代码 `matched==total==0` 直接 COMPLETE（第四个）。

- [ ] **Step 3: 实现**

替换 `sync.py` `_check_setup`（`:236-265`）：

```python
    def _check_setup(self, observed_board: np.ndarray) -> list[SyncEvent]:
        """Compare observed board against the tsumego target board.

        missing = target points whose observed content differs (empty OR wrong color).
        extra   = observed stones that differ from target (on empty target points OR
                  wrong color on a target point — such points appear in BOTH lists).
        SETUP_COMPLETE requires exact equality: missing AND extra both empty.
        """
        assert self._target_board is not None
        events: list[SyncEvent] = []

        total = int(np.count_nonzero(self._target_board != EMPTY))
        missing = [
            [int(r), int(c)]
            for r, c in zip(*np.where((self._target_board != EMPTY) & (observed_board != self._target_board)))
        ]
        extra = [
            [int(r), int(c), int(observed_board[r, c])]
            for r, c in zip(*np.where((observed_board != EMPTY) & (observed_board != self._target_board)))
        ]
        matched = total - len(missing)

        events.append(
            SyncEvent(
                SyncEventType.SETUP_PROGRESS,
                data={"matched": matched, "total": total, "missing": missing, "extra": extra},
            )
        )

        if not missing and not extra:
            events.append(SyncEvent(SyncEventType.SETUP_COMPLETE))
            self._target_board = None
            self._expected_board = observed_board.copy()
            self._state = SyncState.SYNCED

        return events
```

- [ ] **Step 4: 跑测试确认通过 + 原有 setup 测试不回归**

Run: `CI=true uv run --no-sync pytest tests/test_vision/test_sync.py -v`
Expected: 全部 PASS（若文件里既有 setup 测试断言了旧 data 形状，更新其断言加 `"extra": []`）。

- [ ] **Step 5: Commit**

```bash
git add katrain/vision/sync.py tests/test_vision/test_sync.py
git commit -m "feat(vision): setup mode reports extra/wrong-color stones and requires exact equality"
```

---

### Task 2: gating 纯函数 + move 事件构造 + IPC 命令类型（monitor / pause / move-arm）

把「什么时候喂帧、什么时候做 move 检测、move 事件长什么样」抽成纯函数，两个 worker 共用，可单测。评审修订：monitor 路径的 move 检测**不能只看 `SYNCED`**（清盘/摆放/应手/拿除完成后都会短暂 SYNCED），必须由前端相位显式 arm；事件分流契约（bound→dataclass 给对弈 poller，monitor→dict 走 WS）用共享构造函数锁定，防止两个 worker 漂移。

**Files:**
- Create: `katrain/vision/gating.py`
- Modify: `katrain/vision/ipc.py:15-26`（CommandType 增三项）
- Test: `tests/test_vision/test_gating.py`

**Interfaces:**
- Produces: `should_feed_sync(bound, monitor, paused) -> bool`；`should_detect_moves(bound, monitor, paused, move_armed, sync_state) -> bool`（`sync_state` 传 `SyncState.value` 字符串）；`move_event(bound, row, col, color)`（bound→`ConfirmedMove`，否则→dict）；`CommandType.SET_MONITOR`（data `{"active": bool}`）、`CommandType.SET_PAUSED`（data `{"paused": bool}`）、`CommandType.SET_MOVE_ARMED`（data `{"armed": bool}`）。Task 3 的 worker/service、Task 4 的 REST 依赖这些名字。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_vision/test_gating.py`：

```python
from katrain.vision.gating import move_event, should_detect_moves, should_feed_sync
from katrain.vision.ipc import ConfirmedMove


class TestShouldFeedSync:
    def test_bound_feeds(self):
        assert should_feed_sync(bound=True, monitor=False, paused=False)

    def test_monitor_feeds_without_bind(self):
        assert should_feed_sync(bound=False, monitor=True, paused=False)

    def test_paused_blocks_everything(self):
        assert not should_feed_sync(bound=True, monitor=True, paused=True)

    def test_neither_no_feed(self):
        assert not should_feed_sync(bound=False, monitor=False, paused=False)


class TestShouldDetectMoves:
    def test_bound_detects_regardless_of_state(self):
        # 保持既有对弈行为：bound 时不看 sync_state 也不看 move_armed
        assert should_detect_moves(True, False, False, False, "capture_pending")

    def test_monitor_requires_armed_and_synced(self):
        assert should_detect_moves(False, True, False, True, "synced")
        assert not should_detect_moves(False, True, False, False, "synced")       # 未 arm
        assert not should_detect_moves(False, True, False, True, "setup_in_progress")  # 摆放中

    def test_paused_blocks(self):
        assert not should_detect_moves(True, True, True, True, "synced")


class TestMoveEvent:
    def test_bound_yields_dataclass_for_game_poller(self):
        evt = move_event(bound=True, row=3, col=4, color=1)
        assert isinstance(evt, ConfirmedMove) and (evt.row, evt.col, evt.color) == (3, 4, 1)

    def test_monitor_yields_dict_for_ws(self):
        evt = move_event(bound=False, row=3, col=4, color=2)
        assert evt == {"type": "move_confirmed", "data": {"row": 3, "col": 4, "color": 2}}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run --no-sync pytest tests/test_vision/test_gating.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'katrain.vision.gating'`

- [ ] **Step 3: 实现**

创建 `katrain/vision/gating.py`：

```python
"""Frame-feeding / move-detection gates + move-event routing, shared by both vision workers.

bound      = game-session BIND (对弈路径，行为保持不变)
monitor    = tsumego/physical monitor mode (无 session)
paused     = 提示白灯/试下期间挂起一切识别
move_armed = 前端相位显式 arm（仅"轮到用户落子"时 true——SYNCED 只是必要条件，
             清盘/摆放/应手完成后都会短暂 SYNCED，不能据此推断轮到用户）

Routing contract (LOCKED BY TESTS): bound moves -> ConfirmedMove dataclass consumed by
the game poller; monitor moves -> dict event fanned out over /ws/vision (Task 5 pump).
"""

from __future__ import annotations

from katrain.vision.ipc import ConfirmedMove


def should_feed_sync(bound: bool, monitor: bool, paused: bool) -> bool:
    return (bound or monitor) and not paused


def should_detect_moves(bound: bool, monitor: bool, paused: bool, move_armed: bool, sync_state: str) -> bool:
    if paused:
        return False
    if bound:
        return True
    return monitor and move_armed and sync_state == "synced"


def move_event(bound: bool, row: int, col: int, color: int):
    if bound:
        return ConfirmedMove(col=col, row=row, color=color)
    return {"type": "move_confirmed", "data": {"row": row, "col": col, "color": color}}
```

在 `katrain/vision/ipc.py` 的 `CommandType` 里 `SET_GEOMETRY = "set_geometry"` 之后追加三行：

```python
    SET_MONITOR = "set_monitor"
    SET_PAUSED = "set_paused"
    SET_MOVE_ARMED = "set_move_armed"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `CI=true uv run --no-sync pytest tests/test_vision/test_gating.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add katrain/vision/gating.py katrain/vision/ipc.py tests/test_vision/test_gating.py
git commit -m "feat(vision): gating helpers, move-event routing contract, SET_MONITOR/SET_PAUSED/SET_MOVE_ARMED"
```

---

### Task 3: worker / worker_inprocess / service 接通 monitor+pause+move-arm + SETUP_COMPLETE rebase

两个 worker 用 gating 函数替换 `if self._bound:` 门槛、用 `move_event()` 构造事件；**SETUP_COMPLETE 时同步 `MoveDetector.force_sync(observed_board)`**（否则 setup 刚完成、move 检测 arm 后 detector 仍拿旧基线比较——评审确认 `SET_EXPECTED_BOARD` 有 force_sync 但 setup 路径没有）；`VisionService` 加 `set_monitor`/`set_paused`/`set_move_armed`。

**Files:**
- Modify: `katrain/vision/worker.py:256-260, 289-297, 302-334`
- Modify: `katrain/vision/worker_inprocess.py:171-186, 211-234`
- Modify: `katrain/vision/service.py`（`unbind_session` 后追加三个方法）
- Test: `tests/test_vision/test_service_monitor.py`

**Interfaces:**
- Consumes: Task 2 的 `should_feed_sync`/`should_detect_moves`/`move_event`/新 CommandType。
- Produces: monitor 模式 WS 事件 `{"type": "move_confirmed", "data": {"row": int, "col": int, "color": int}}`（vision 坐标，color 1=黑 2=白）；`VisionService.set_monitor(active)`、`set_paused(paused)`、`set_move_armed(armed)`。Task 4 REST、Task 11 hook 依赖。

- [ ] **Step 1: 写失败测试（service 命令管道）**

创建 `tests/test_vision/test_service_monitor.py`：

```python
from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import CommandType
from katrain.vision.service import VisionService


class FakeWorker:
    def __init__(self):
        self.commands = []

    def send_command(self, cmd):
        self.commands.append(cmd)


def _service_with_fake():
    svc = VisionService(VisionServiceConfig())
    svc._worker = FakeWorker()
    return svc


class TestMonitorPauseArmCommands:
    def test_set_monitor_sends_command(self):
        svc = _service_with_fake()
        svc.set_monitor(True)
        cmd = svc._worker.commands[-1]
        assert cmd.action == CommandType.SET_MONITOR and cmd.data == {"active": True}

    def test_set_paused_sends_command(self):
        svc = _service_with_fake()
        svc.set_paused(True)
        cmd = svc._worker.commands[-1]
        assert cmd.action == CommandType.SET_PAUSED and cmd.data == {"paused": True}

    def test_set_move_armed_sends_command(self):
        svc = _service_with_fake()
        svc.set_move_armed(True)
        cmd = svc._worker.commands[-1]
        assert cmd.action == CommandType.SET_MOVE_ARMED and cmd.data == {"armed": True}

    def test_noop_without_worker(self):
        svc = VisionService(VisionServiceConfig())
        svc.set_monitor(True)  # must not raise
        svc.set_paused(False)
        svc.set_move_armed(False)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run --no-sync pytest tests/test_vision/test_service_monitor.py -v`
Expected: FAIL —— `AttributeError: 'VisionService' object has no attribute 'set_monitor'`

- [ ] **Step 3: 实现 service 方法**

`katrain/vision/service.py`，在 `unbind_session`（`:126-130`）之后插入：

```python
    def set_monitor(self, active: bool) -> None:
        """Enable/disable monitor mode (tsumego physical board — no game session)."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_MONITOR, data={"active": active}))

    def set_paused(self, paused: bool) -> None:
        """Pause/resume recognition (hint display, try mode). Single-owner aggregate bool."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_PAUSED, data={"paused": paused}))

    def set_move_armed(self, armed: bool) -> None:
        """Arm/disarm monitor-mode move detection (frontend arms only in the 'ready' phase)."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.SET_MOVE_ARMED, data={"armed": armed}))
```

- [ ] **Step 4: 实现 worker.py 改动**

(a) 文件头 import 区加：`from katrain.vision.gating import move_event, should_detect_moves, should_feed_sync`；确认 `SyncEventType` 已 import（否则加 `from katrain.vision.sync import SyncEventType`）。

(b) `__init__`（`_bound = False` 附近，grep `self._bound`）加三个标志：

```python
        self._monitor = False
        self._paused = False
        self._move_armed = False
```

(c) `_processing_loop` 中 move 检测门槛（`worker.py:256-260`）替换为：

```python
                    if should_detect_moves(
                        self._bound, self._monitor, self._paused, self._move_armed, self._sync.state.value
                    ):
                        move_result = self._move_detector.detect_new_move(self._last_stable_board)
                        if move_result is not None:
                            row, col, color = move_result
                            self._event_queue.put(move_event(self._bound, row, col, color))
```

(d) sync 更新门槛（`worker.py:290`）`if self._bound:` 替换为 gating，并在事件里发现 SETUP_COMPLETE 时 rebase move detector：

```python
            if should_feed_sync(self._bound, self._monitor, self._paused):
                events = self._sync.update(
                    observed_board=observed_board,
                    mean_confidence=mean_confidence,
                    board_detected=board_detected,
                )
                if any(evt.type == SyncEventType.SETUP_COMPLETE for evt in events):
                    # Rebase move detection on the freshly converged board so a later
                    # arm doesn't diff against a stale baseline.
                    self._move_detector.force_sync(observed_board)
                for evt in events:
                    self._event_queue.put({"type": evt.type.value, "data": evt.data})
```

(e) `_process_commands`（`:333` `SET_VIEWER_ACTIVE` 分支后）追加：

```python
            elif cmd.action == CommandType.SET_MONITOR:
                self._monitor = cmd.data.get("active", False)
                if not self._monitor and not self._bound:
                    self._sync = SyncStateMachine()  # Reset (mirror UNBIND)
                    self._move_armed = False
            elif cmd.action == CommandType.SET_PAUSED:
                self._paused = cmd.data.get("paused", False)
            elif cmd.action == CommandType.SET_MOVE_ARMED:
                self._move_armed = cmd.data.get("armed", False)
```

- [ ] **Step 5: 实现 worker_inprocess.py 同等改动**

(a) import 加 gating 三函数 + `SyncEventType`；`__init__` 加 `self._monitor = False`、`self._paused = False`、`self._move_armed = False`。

(b) `_loop` 中 move 检测（`:171-175`）：

```python
                    if should_detect_moves(
                        self._bound, self._monitor, self._paused, self._move_armed, self._sync.state.value
                    ):
                        move_result = self._move_detector.detect_new_move(observed_board)
                        if move_result is not None:
                            row, col, color = move_result
                            self._event_queue.put(move_event(self._bound, row, col, color))
```

(c) `:179` `if self._bound:` → `if should_feed_sync(self._bound, self._monitor, self._paused):`，并在其 sync.update 事件循环前加与 worker.py (d) 相同的 SETUP_COMPLETE→`force_sync` 逻辑。

(d) `_drain_commands`（`:211-234`）追加与 worker.py (e) 完全相同的三个分支。

- [ ] **Step 6: 跑测试确认通过 + vision 全量单测回归**

Run: `CI=true uv run --no-sync pytest tests/test_vision/ tests/test_vision_api.py -q`
Expected: 全 PASS（原有失败为 0——`tests/test_vision/` 在基线上是全绿的）

- [ ] **Step 7: Commit**

```bash
git add katrain/vision/worker.py katrain/vision/worker_inprocess.py katrain/vision/service.py tests/test_vision/test_service_monitor.py
git commit -m "feat(vision): monitor mode, pause, explicit move-arm, and SETUP_COMPLETE move-detector rebase in both workers"
```

---

### Task 4: 新 REST — /vision/monitor /pause /move-detection /expected-board

**Files:**
- Modify: `katrain/web/api/v1/endpoints/vision.py`（`/setup-mode` 之后追加）
- Test: `tests/test_vision_api.py`（追加；沿用该文件既有的 fake-vision + TestClient 模式，先 `grep -n "class\|def test" tests/test_vision_api.py` 看清既有 fixture 再追加）

**Interfaces:**
- Produces: `POST /api/v1/vision/monitor {"active": bool}`、`POST /api/v1/vision/pause {"paused": bool}`、`POST /api/v1/vision/move-detection {"armed": bool}`、`POST /api/v1/vision/expected-board {"board": [[int]]}`（board 为 vision 坐标 19×19；内部调 `vision.set_expected_board(np.array(...))`，worker 侧 `SET_EXPECTED_BOARD` 已顺带 `move_detector.force_sync`——见 `worker.py:322-325`）。Task 6 前端 client、Task 11 hook 依赖。

- [ ] **Step 1: 写失败测试**

在 `tests/test_vision_api.py` 追加（fake vision 对象按该文件既有模式，若无现成 fake 则仿 `tests/test_led_api.py` 的 FakeLed 建 FakeVision 记录调用）：

```python
class TestMonitorPauseArmExpectedBoard:
    def test_monitor(self, client_with_vision):
        client, fake = client_with_vision
        r = client.post("/api/v1/vision/monitor", json={"active": True})
        assert r.status_code == 200 and fake.monitor_calls == [True]

    def test_pause(self, client_with_vision):
        client, fake = client_with_vision
        r = client.post("/api/v1/vision/pause", json={"paused": True})
        assert r.status_code == 200 and fake.pause_calls == [True]

    def test_move_detection(self, client_with_vision):
        client, fake = client_with_vision
        r = client.post("/api/v1/vision/move-detection", json={"armed": True})
        assert r.status_code == 200 and fake.arm_calls == [True]

    def test_expected_board(self, client_with_vision):
        client, fake = client_with_vision
        board = [[0] * 19 for _ in range(19)]
        board[3][3] = 1
        r = client.post("/api/v1/vision/expected-board", json={"board": board})
        assert r.status_code == 200
        assert fake.expected_boards[-1][3][3] == 1
```

（fixture `client_with_vision` 若不存在则新建：FastAPI app + `app.include_router(vision.router, prefix="/api/v1/vision")` + `app.state.vision = FakeVision()`，FakeVision 实现 `set_monitor/set_paused/set_move_armed/set_expected_board` 四个记录方法。）

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run --no-sync pytest tests/test_vision_api.py -k MonitorPauseArm -v`
Expected: FAIL — 404 Not Found（路由不存在）

- [ ] **Step 3: 实现端点**

`katrain/web/api/v1/endpoints/vision.py` 末尾追加：

```python
class MonitorRequest(BaseModel):
    active: bool


class PauseRequest(BaseModel):
    paused: bool


class MoveDetectionRequest(BaseModel):
    armed: bool


class ExpectedBoardRequest(BaseModel):
    board: list[list[int]]  # vision coords, row 0 = top


@router.post("/monitor")
async def set_monitor(request: Request, body: MonitorRequest):
    """Enable/disable sessionless monitor mode (physical tsumego)."""
    vision = _get_vision(request)
    vision.set_monitor(body.active)
    return {"ok": True, "active": body.active}


@router.post("/pause")
async def set_paused(request: Request, body: PauseRequest):
    """Pause/resume recognition (hint display, try mode).

    Single-owner aggregate boolean: the one page owning monitor mode sends
    `showHint || isTryMode` — do NOT add independent callers (no ref-counting in v1).
    """
    vision = _get_vision(request)
    vision.set_paused(body.paused)
    return {"ok": True, "paused": body.paused}


@router.post("/move-detection")
async def set_move_detection(request: Request, body: MoveDetectionRequest):
    """Arm/disarm monitor-mode move detection (frontend arms only in 'ready' phase)."""
    vision = _get_vision(request)
    vision.set_move_armed(body.armed)
    return {"ok": True, "armed": body.armed}


@router.post("/expected-board")
async def set_expected_board(request: Request, body: ExpectedBoardRequest):
    """Set expected board + rebase move detector (SET_EXPECTED_BOARD does force_sync)."""
    vision = _get_vision(request)
    import numpy as np

    vision.set_expected_board(np.array(body.board, dtype=int))
    return {"ok": True}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `CI=true uv run --no-sync pytest tests/test_vision_api.py -q`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add katrain/web/api/v1/endpoints/vision.py tests/test_vision_api.py
git commit -m "feat(vision-api): monitor/pause/move-detection/expected-board endpoints for physical tsumego"
```

---

### Task 5: /ws/vision 事件泵 — 服务端单消费者 fan-out（修复破坏性队列）

**评审确认的既有隐患**（比评审报告更严重）：`/ws/vision` handler（`server.py:1716-1722`）每个连接各自 `vision.poll_events()` 抢队列，且**只转发 dict、静默丢弃非 dict**——bound 对弈时若有 WS 客户端连着，`ConfirmedMove` 会被 WS handler 抢走丢掉（与 `_vision_move_poller` 竞态）。多开一个页面/overlay 还会把 `setup_complete`/`move_confirmed` 分流。修复：**唯一后台泵**统一 drain worker 队列，按类型显式路由——dict 事件广播给所有 WS 客户端（经各自的 per-connection queue，避免多 task 并发写同一 socket），`ConfirmedMove` 进专用 `asyncio.Queue` 由对弈 poller 消费。

**Files:**
- Create: `katrain/web/core/vision_pump.py`（纯路由函数，可单测）
- Modify: `katrain/web/server.py`（新泵 task + `/ws/vision` handler 改写 + `_vision_move_poller` 改读队列）
- Test: `tests/test_vision_pump.py`

**Interfaces:**
- Produces: `route_vision_event(evt, client_queues, move_queue, bound) -> None`；`app.state.vision_ws_clients: dict[WebSocket, asyncio.Queue]`；`app.state.vision_move_queue: asyncio.Queue`。Task 11 依赖「单页面多组件也不丢事件」的语义。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_vision_pump.py`：

```python
import asyncio

from katrain.vision.ipc import ConfirmedMove
from katrain.web.core.vision_pump import route_vision_event


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


class TestRouteVisionEvent:
    def test_dict_event_broadcast_to_all_clients(self):
        q1, q2, moves = asyncio.Queue(), asyncio.Queue(), asyncio.Queue()
        evt = {"type": "setup_complete", "data": {}}
        route_vision_event(evt, [q1, q2], moves, bound=False)
        assert _drain(q1) == [evt] and _drain(q2) == [evt]
        assert moves.empty()

    def test_confirmed_move_routed_to_move_queue_when_bound(self):
        q1, moves = asyncio.Queue(), asyncio.Queue()
        mv = ConfirmedMove(col=3, row=4, color=1)
        route_vision_event(mv, [q1], moves, bound=True)
        assert _drain(moves) == [mv]
        assert q1.empty()

    def test_confirmed_move_dropped_when_not_bound(self):
        q1, moves = asyncio.Queue(), asyncio.Queue()
        route_vision_event(ConfirmedMove(col=3, row=4, color=1), [q1], moves, bound=False)
        assert moves.empty() and q1.empty()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run --no-sync pytest tests/test_vision_pump.py -v`
Expected: FAIL —— ModuleNotFoundError

- [ ] **Step 3: 实现路由模块**

创建 `katrain/web/core/vision_pump.py`：

```python
"""Single-consumer fan-out for vision worker events.

The worker event queue is DESTRUCTIVE (each event can be read once). Exactly ONE
pump task drains it and routes by type:
  - dict events (sync/setup/monitor move_confirmed) -> broadcast to every /ws/vision
    client via its per-connection asyncio.Queue (each WS handler owns its socket writes);
  - ConfirmedMove dataclasses (bound game path) -> app-level move queue consumed by
    _vision_move_poller. Dropped when no session is bound (stale moves must not leak
    into a later bind).
Nothing else may call VisionService.poll_events().
"""

from __future__ import annotations

import asyncio
from typing import Iterable

from katrain.vision.ipc import ConfirmedMove


def route_vision_event(
    evt,
    client_queues: Iterable[asyncio.Queue],
    move_queue: asyncio.Queue,
    bound: bool,
) -> None:
    if isinstance(evt, ConfirmedMove):
        if bound:
            move_queue.put_nowait(evt)
        return
    if isinstance(evt, dict):
        for q in client_queues:
            q.put_nowait(evt)
```

- [ ] **Step 4: server.py 接线**

(a) 在 `app.state.vision_poller_task = asyncio.create_task(_vision_move_poller(app))`（`server.py:386`）处，先初始化共享状态并加泵 task（与 poller 同生命周期，shutdown 取消方式照抄 poller 的处理）：

```python
        app.state.vision_ws_clients = {}
        app.state.vision_move_queue = asyncio.Queue()
        app.state.vision_pump_task = asyncio.create_task(_vision_event_pump(app))
        app.state.vision_poller_task = asyncio.create_task(_vision_move_poller(app))
```

(b) 新增泵协程（放 `_vision_move_poller` 旁）：

```python
async def _vision_event_pump(app: FastAPI):
    """Sole consumer of the vision worker event queue — see vision_pump docstring."""
    from katrain.web.core.vision_pump import route_vision_event

    log = logging.getLogger("katrain_web.vision")
    while True:
        try:
            vision = getattr(app.state, "vision", None)
            if vision:
                for evt in vision.poll_events():
                    route_vision_event(
                        evt,
                        list(app.state.vision_ws_clients.values()),
                        app.state.vision_move_queue,
                        bound=bool(vision.bound_session_id),
                    )
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("vision event pump error")
            await asyncio.sleep(1.0)
```

(c) `/ws/vision` handler（`:1707-1744`）改写——注册 per-connection queue，**不再 poll_events**；本 task 独占本 socket 的所有写：

```python
    @app.websocket("/ws/vision")
    async def vision_websocket(websocket: WebSocket):
        """Vision event WebSocket — events arrive via the pump's per-connection queue."""
        await websocket.accept()
        vision = getattr(app.state, "vision", None)
        if vision is None:
            await websocket.close(code=1008, reason="Vision service not enabled")
            return
        queue: asyncio.Queue = asyncio.Queue()
        app.state.vision_ws_clients[websocket] = queue
        try:
            while True:
                while not queue.empty():
                    await websocket.send_json(queue.get_nowait())

                vision.refresh_status()
                await websocket.send_json(
                    {
                        "type": "vision_status",
                        "data": {
                            "camera_connected": vision.camera_status == "connected",
                            "pose_locked": vision.pose_lock_status == "locked",
                            "sync_state": vision.sync_state,
                        },
                    }
                )

                try:
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=0.5)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            pass
        finally:
            app.state.vision_ws_clients.pop(websocket, None)
```

（可选优化：`queue.get()` + `asyncio.wait` 双等待降延迟——v1 保持 0.5s 轮询节奏即可。）

(d) `_vision_move_poller`（`:1810-1822`）不再调 `vision.get_confirmed_move()`，改为 drain 泵路由来的队列（保留「取最新一条」语义）：

```python
            if vision and vision.bound_session_id:
                move_data = None
                q = app.state.vision_move_queue
                while not q.empty():
                    move_data = q.get_nowait()
                if move_data and isinstance(move_data, ConfirmedMove):
                    ...
```

(e) `grep -rn "get_confirmed_move" katrain tests` —— 唯一调用方就是这个 poller 的话，删除 `VisionService.get_confirmed_move`（它的「re-queue 其他事件」逻辑与单泵冲突）；若测试引用则一并更新。

- [ ] **Step 5: 验证**

Run: `CI=true uv run --no-sync pytest tests/test_vision_pump.py tests/test_vision/ tests/test_vision_api.py -q`
Expected: 全 PASS
Run: `CI=true uv run --no-sync pytest tests -q -k "server or websocket or vision" 2>&1 | tail -3`
Expected: 不新增失败

- [ ] **Step 6: Commit**

```bash
git add katrain/web/core/vision_pump.py katrain/web/server.py tests/test_vision_pump.py
git commit -m "fix(vision): single-consumer event pump with WS fan-out; stop /ws/vision stealing ConfirmedMove from the game poller"
```

---

### Task 6: LED hint 白灯颜色（后端）+ 前端 API client 扩展

**Files:**
- Modify: `katrain/web/core/led_service.py:52-59`（COLOR_RGB）
- Modify: `katrain/web/ui/src/api/ledApi.ts:8`（LedColor）
- Modify: `katrain/web/ui/src/api.ts:317` 之后（vision client 方法）+ `VisionStatusResponse`（`:109`）
- Test: `tests/test_led_service.py`、`tests/test_led_api.py`（各追加 1 个测试）

**Interfaces:**
- Produces: LED REST `color: "hint"` → 白光 (255,255,255)（经既有 `/led/point|points`，无需新端点）；前端 `LedColor = 'black' | 'white' | 'remove' | 'hint'`；`API.visionMonitor(active)`、`API.visionPause(paused)`、`API.visionMoveDetection(armed)`、`API.visionExpectedBoard(board)`；`VisionStatusResponse.recognition_ready`。Task 11/12 依赖。

- [ ] **Step 1: 写失败测试**

`tests/test_led_service.py` 追加（仿该文件既有 set_points 测试的 fake-serial 写法；先 `grep -n "def test_set_points\|FakeSerial\|def _service" tests/test_led_service.py` 对齐现有 fixture 名）：

```python
def test_hint_color_maps_to_white(led_service_with_fake_serial):
    svc, sent = led_service_with_fake_serial
    svc.set_points([{"row": 0, "col": 0, "color": "hint"}], strict=True)
    seti = [c for c in sent if c.startswith("SETI")]
    assert seti == ["SETI 0 255 255 255"]  # rc2idx(0,0)=0
```

`tests/test_led_api.py` 的 `TestLedEndpoints` 追加：

```python
    def test_hint_color_accepted(self):
        c, led_obj = make_client()
        r = c.post("/led/point", json={"row": 9, "col": 9, "color": "hint"})
        assert r.status_code == 200
        assert led_obj.calls[-1][0][0]["color"] == "hint"
```

（fixture/helper 名以两文件实际为准，追加前先读其现有测试。）

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run --no-sync pytest tests/test_led_service.py tests/test_led_api.py -q`
Expected: 新测试 FAIL——`hint` 未知颜色回退成 black → `SETI 0 255 0 0`

- [ ] **Step 3: 实现**

`led_service.py` `COLOR_RGB` 加一行：

```python
    "hint": (255, 255, 255),  # AI hint / celebration -> white LED
```

`ledApi.ts:8`：

```ts
export type LedColor = 'black' | 'white' | 'remove' | 'hint';
```

`api.ts` `VisionStatusResponse`（`:109-115`）追加字段（可选，容忍旧后端）：

```ts
  recognition_ready?: boolean;
```

`api.ts` `visionSetupMode`（`:317-318`）之后追加：

```ts
  visionMonitor: (active: boolean): Promise<void> =>
    apiPost("/api/v1/vision/monitor", { active }),
  visionPause: (paused: boolean): Promise<void> =>
    apiPost("/api/v1/vision/pause", { paused }),
  visionMoveDetection: (armed: boolean): Promise<void> =>
    apiPost("/api/v1/vision/move-detection", { armed }),
  visionExpectedBoard: (board: number[][]): Promise<void> =>
    apiPost("/api/v1/vision/expected-board", { board }),
```

- [ ] **Step 4: 验证**

Run: `CI=true uv run --no-sync pytest tests/test_led_service.py tests/test_led_api.py -q`
Expected: 全 PASS
Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd ../../..`（api.ts 是共享文件）
Expected: 双绿

- [ ] **Step 5: Commit**

```bash
git add katrain/web/core/led_service.py katrain/web/ui/src/api/ledApi.ts katrain/web/ui/src/api.ts tests/test_led_service.py tests/test_led_api.py
git commit -m "feat(led): hint color (white) + frontend vision/led client methods + recognition_ready in status type"
```

---

### Task 7: useVisionSync — 解耦 session bind + 本地 seq 队列 + extra 透传

现状（`katrain/web/ui/src/kiosk/hooks/useVisionSync.ts:67-68`）：`if (!sessionId) return;`——传 null 根本不开 WS。改为：**WS 始终打开；bind/unbind 仅在 sessionId 非空时执行**。评审修订：给每个事件打**前端本地递增 seq**——`syncEvents` 有 `MAX_EVENTS=100` 裁剪，消费者不能按数组下标记位；`latestEvent` 单值会在一次渲染间隙覆盖丢事件（丢 `setup_complete`/`move_confirmed` 会卡死相位机），下游一律用 seq 队列消费。同时透传 Task 1 新增的 `extra`。

**Files:**
- Modify: `katrain/web/ui/src/kiosk/hooks/useVisionSync.ts`

**Interfaces:**
- Produces: `useVisionSync(sessionId: string | null)`——null 时也收事件；`VisionSyncEvent` 增加 `seq: number`（前端本地，单调递增，不来自 wire）；`setupProgress` 类型含 `extra`。GamePage（非 null 路径）行为不变。

- [ ] **Step 1: 实现**

(a) 类型改动：

```ts
export interface VisionSyncEvent {
  seq: number; // frontend-local monotonic sequence (survives MAX_EVENTS trimming)
  type: SyncEventType;
  data: Record<string, unknown>;
}
```

`VisionSyncState.setupProgress`（`:30` 与 `:41` 两处）改为：

```ts
  setupProgress: { matched: number; total: number; missing: Array<[number, number]>; extra: Array<[number, number, number]> } | null;
```

(b) handleMessage 改为（seq 用 ref 计数；setup_progress 分支透传 extra）：

```ts
  const nextSeqRef = useRef(0);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const parsed = JSON.parse(event.data) as Omit<VisionSyncEvent, 'seq'>;
      const evt: VisionSyncEvent = { ...parsed, seq: nextSeqRef.current++ };
      setLatestEvent(evt);
      setSyncEvents(prev => {
        const next = [...prev, evt];
        return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
      });

      if (evt.type === 'setup_progress') {
        const { matched, total, missing, extra } = evt.data as {
          matched: number; total: number;
          missing?: Array<[number, number]>; extra?: Array<[number, number, number]>;
        };
        setSetupProgress({ matched, total, missing: missing ?? [], extra: extra ?? [] });
      } else if (evt.type === 'setup_complete') {
        setIsSetupComplete(true);
        setSetupProgress(null);
      }
    } catch (err) {
      console.error('Failed to parse vision sync message', err);
    }
  }, []);
```

(c) effect（`:67-120`）改为（bind 与 WS 解耦；null 时不 bind/unbind）：

```ts
  useEffect(() => {
    let cancelled = false;

    const connect = async () => {
      if (sessionId) {
        try {
          await API.visionBind(sessionId);
        } catch (err) {
          console.error('Vision bind failed', err);
        }
      }
      if (cancelled) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/vision`);
      wsRef.current = ws;
      ws.onmessage = handleMessage;
      ws.onerror = (err) => console.error('Vision WebSocket error', err);
      ws.onclose = () => { wsRef.current = null; };
    };

    connect();

    return () => {
      cancelled = true;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (sessionId) {
        API.visionUnbind().catch((err) => console.error('Vision unbind failed during cleanup', err));
      }
      setSyncEvents([]);
      setLatestEvent(null);
      setSetupProgress(null);
      setIsSetupComplete(false);
    };
  }, [sessionId, handleMessage]);
```

- [ ] **Step 2: 双构建验证**

Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd ../../..`
Expected: 双绿（`verify:kiosk-2d` exit 0）

- [ ] **Step 3: Commit**

```bash
git add katrain/web/ui/src/kiosk/hooks/useVisionSync.ts
git commit -m "feat(kiosk): useVisionSync opens /ws/vision without a session; local event seq + setup extra passthrough"
```

---

### Task 8: useTsumegoProblem — failed 快照恢复 + scheduledReply 元数据（共享文件）

评审确认的两处判题 hook 缺口（均已对照代码核实）：

1. **答错恢复丢被提子**：incorrect 分支（`useTsumegoProblem.ts:391-394, 406-409`）对错着执行 `removeCaptures`（错着提走对方子时，`stones` 里的被提子直接消失），而 `undo()` 的 isFailed 分支（`:509-522`）只做 `stones.slice(0, -1)`——恢复不出被提子；且它还错误地 `moveHistory.slice(0, -1)`（错着根本没进过 moveHistory，弹掉的是最后一手合法棋）。**这是屏幕模式也存在的既有 bug**，修法：incorrect 前保存完整快照，undo 恢复快照。
2. **应手竞态无解药**：`placeStone` 同步落用户子、300ms 后才落 AI 应手，物理编排若从 `stones` 尾巴猜应手会把用户正确手误当应手（评审 Blocker）。修法：`MoveResult` 附带只读 `scheduledReply` 元数据（判题逻辑零改动），物理 hook 据此等应手真实落屏后再收敛。

**这是共享文件（galaxy 也用）**：改动为纯修复 + 附加字段，需双构建 + vitest。

**Files:**
- Modify: `katrain/web/ui/src/hooks/useTsumegoProblem.ts`
- Test: Create `katrain/web/ui/src/hooks/useTsumegoProblem.test.ts`

**Interfaces:**
- Produces: `MoveResult.scheduledReply?: { player: 'B' | 'W'; coords: [number, number] }`（correct 且有 AI 应手时给出，等于 `getAIResponse` 的返回）；`undo()` 在 isFailed 时恢复错着前完整状态（含被提子、moveHistory、nextPlayer、currentNode）。Task 10/11 依赖 scheduledReply；`undoFailed` command 依赖新 undo 语义。

- [ ] **Step 1: 写失败测试**

创建 `katrain/web/ui/src/hooks/useTsumegoProblem.test.ts`（hook 用原生 `fetch('/api/v1/tsumego/problems/:id')` 拉题——测试 stub `global.fetch`；坐标一律用仓库自己的 `sgfToCoords` 换算，避免坐标系假设）：

```ts
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTsumegoProblem } from './useTsumegoProblem';
import { sgfToCoords } from '../utils/sgfParser';

// 9x9：白 aa 仅剩一气 ab；错着 B[ab] 提掉 aa；正解 B[cc]（带 AI 应手 W[dd]，再正解 B[ee]）
const SGF = '(;GM[1]SZ[9]AB[ba]AW[aa]PL[B](;B[cc]C[正解](;W[dd](;B[ee]C[正解]))))';

const problemJson = {
  // 字段名/形状以 fetch 返回的真实 API shape 为准（先读 useTsumegoProblem 的
  // fetch-then-setProblem 映射代码再定稿此 fixture）
  id: 'p1', level: '', category: '', hint: '', board_size: 9,
  initial_black: [], initial_white: [], sgf_content: SGF,
};

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => problemJson })));
});
afterEach(() => vi.unstubAllGlobals());

async function setup() {
  const hook = renderHook(() => useTsumegoProblem('p1'));
  await waitFor(() => expect(hook.result.current.problem).not.toBeNull());
  return hook;
}

describe('failed-state snapshot restore', () => {
  it('undo after an incorrect capturing move restores the captured stone', async () => {
    const { result } = await setup();
    const before = result.current.stones;
    const wrong = sgfToCoords('ab');  // 提掉白 aa 的错着（不在 SGF 树 → incorrect）
    act(() => { result.current.placeStone(wrong[0], wrong[1]); });
    expect(result.current.isFailed).toBe(true);
    act(() => { result.current.undo(); });
    // 完整恢复：被提子回来、错着消失、isFailed 清除、moveHistory 未被误弹
    expect(result.current.stones).toEqual(before);
    expect(result.current.isFailed).toBe(false);
    expect(result.current.nextPlayer).toBe('B');
  });
});

describe('scheduledReply metadata', () => {
  it('correct move exposes the pending AI reply without changing judging', async () => {
    const { result } = await setup();
    const correct = sgfToCoords('cc');
    let moveResult: ReturnType<typeof result.current.placeStone> = null;
    act(() => { moveResult = result.current.placeStone(correct[0], correct[1]); });
    expect(moveResult?.type).toBe('correct');
    expect(moveResult?.scheduledReply).toEqual({ player: 'W', coords: sgfToCoords('dd') });
  });
});
```

（`sgfToCoords` 的实际签名/参数以 `src/utils/sgfParser.ts` 为准——若需要 boardSize 参数则补上；fixture 字段名先读 hook 的 fetch 映射代码再对齐。测试跑不起来先修 fixture，不改断言语义。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd katrain/web/ui && npx vitest run src/hooks/useTsumegoProblem.test.ts && cd ../../..`
Expected: FAIL——快照测试 stones 不相等（被提子没回来）；scheduledReply 为 undefined。

- [ ] **Step 3: 实现**

(a) `MoveResult`（`:139-144`）追加字段：

```ts
export interface MoveResult {
  type: 'correct' | 'incorrect' | 'solved' | 'continue';
  message?: string;
  sound?: 'stone' | 'capture' | 'correct' | 'incorrect' | 'solved';
  captured?: number;
  /** Set on 'correct' when an AI reply is scheduled (~300ms). Read-only metadata for
   *  physical-board orchestration — judging logic is unchanged. */
  scheduledReply?: { player: 'B' | 'W'; coords: [number, number] };
}
```

(b) failed 快照 ref（放 `tryModeSnapshotRef` 旁）：

```ts
  // Full pre-failure snapshot so undo() can restore stones captured by a wrong move.
  const failedRecoveryRef = useRef<{
    stones: Stone[];
    lastMove: [number, number] | null;
    moveHistory: Stone[];
    currentNode: SGFNode | null;
    nextPlayer: 'B' | 'W';
  } | null>(null);
```

(c) `placeStone` 两个 incorrect 分支（`:387-397` 与 `:402-411`）在 `setIsFailed(true)` 前各加：

```ts
      failedRecoveryRef.current = {
        stones: [...stones],
        lastMove,
        moveHistory: [...moveHistory],
        currentNode,
        nextPlayer,
      };
```

（`lastMove` 需加入 placeStone 的 useCallback 依赖数组。）

(d) `undo()` 的 isFailed 分支（`:509-522`）整体替换为快照恢复：

```ts
    // If failed, restore the full pre-failure snapshot (a wrong move may have
    // captured stones — slice(0,-1) cannot bring those back).
    if (isFailed) {
      const snap = failedRecoveryRef.current;
      if (snap) {
        setStones(snap.stones);
        setMoveHistory(snap.moveHistory);
        setLastMove(snap.lastMove);
        setCurrentNode(snap.currentNode);
        setNextPlayer(snap.nextPlayer);
        failedRecoveryRef.current = null;
      } else {
        setStones(stones.slice(0, -1));  // fallback (no snapshot recorded)
      }
      setIsFailed(false);
      return;
    }
```

(e) correct 分支的 return（`:472-476`）改为：

```ts
    return {
      type: 'correct',
      sound: capturedCount > 0 ? 'capture' : 'stone',
      captured: capturedCount,
      ...(aiResponse ? { scheduledReply: aiResponse } : {}),
    };
```

（`aiResponse` 在 `:433` 已计算，无需移动代码。）

(f) `initializeProblem` / `reset` / `enterTryMode` 处把 `failedRecoveryRef.current = null` 一并清掉（防跨题残留）。

- [ ] **Step 4: 验证（vitest + 双构建）**

Run: `cd katrain/web/ui && npm test && npm run build && npm run build:kiosk-2d && cd ../../..`
Expected: vitest 全绿 + 双构建绿（共享文件，galaxy 同样受益于该修复）

- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/hooks/useTsumegoProblem.ts katrain/web/ui/src/hooks/useTsumegoProblem.test.ts
git commit -m "fix(tsumego): failed-state snapshot restore (captured stones) + scheduledReply metadata on MoveResult"
```

---

### Task 9: 语音资产生成脚本 + useVoice hook

**Files:**
- Create: `scripts/generate_tsumego_voice.py`
- Create: `katrain/sounds/voice/`（7 个 mp3，脚本产出，**入库提交**——运行时无网也要能播）
- Create: `katrain/web/ui/src/kiosk/hooks/useVoice.ts`

**Interfaces:**
- Produces: `useVoice()` 返回 `{ speak: (name: VoiceName) => void }`，`VoiceName = 'clear_board' | 'place_black' | 'place_white' | 'setup_done' | 'correct' | 'wrong_remove' | 'capture_remove'`。静态路径 `/assets/sounds/voice/<name>.mp3`（`server.py:484` 已把 `katrain/sounds` 挂到 `/assets/sounds`，vite dev 代理 `/assets` 已有）。Task 10/11 依赖。

- [ ] **Step 1: 写生成脚本**

创建 `scripts/generate_tsumego_voice.py`：

```python
"""Generate tsumego physical-board voice prompts via edge-tts (dev-time tool).

Usage: uv run --no-sync python scripts/generate_tsumego_voice.py
Output: katrain/sounds/voice/<name>.mp3 (committed to the repo)
"""

import asyncio
from pathlib import Path

import edge_tts

VOICE = "zh-CN-XiaoxiaoNeural"

LINES = {
    "clear_board": "请清空棋盘",
    "place_black": "请摆放黑棋",
    "place_white": "请摆放白棋",
    "setup_done": "摆放完成，请开始解题",
    "correct": "答对了",
    "wrong_remove": "答错了，请取回棋子",
    "capture_remove": "请提走被吃的棋子",
}


async def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "katrain" / "sounds" / "voice"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in LINES.items():
        path = out_dir / f"{name}.mp3"
        await edge_tts.Communicate(text, VOICE).save(str(path))
        print(f"wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 运行生成（需联网；edge-tts 在 dev 依赖组）**

Run: `uv run --no-sync python scripts/generate_tsumego_voice.py && ls -la katrain/sounds/voice/`
Expected: 7 个 mp3，每个几 KB～几十 KB。听抽 1 个确认可播：`afplay katrain/sounds/voice/place_black.mp3`

- [ ] **Step 3: 写 useVoice hook**

创建 `katrain/web/ui/src/kiosk/hooks/useVoice.ts`：

```ts
// Voice prompts for physical-board tsumego (kiosk only). Pre-generated mp3 assets
// under /assets/sounds/voice/ (see scripts/generate_tsumego_voice.py).
// Non-blocking: playback failures are swallowed (audio is advisory).

import { useCallback, useRef } from 'react';

export type VoiceName =
  | 'clear_board'
  | 'place_black'
  | 'place_white'
  | 'setup_done'
  | 'correct'
  | 'wrong_remove'
  | 'capture_remove';

export function useVoice() {
  // Only one voice line at a time — new line interrupts the previous.
  const currentRef = useRef<HTMLAudioElement | null>(null);

  const speak = useCallback((name: VoiceName) => {
    if (currentRef.current) {
      currentRef.current.pause();
    }
    const audio = new Audio(`/assets/sounds/voice/${name}.mp3`);
    currentRef.current = audio;
    audio.play().catch(() => {
      /* advisory only */
    });
  }, []);

  return { speak };
}
```

- [ ] **Step 4: 构建验证 + Commit**

Run: `cd katrain/web/ui && npm run build:kiosk-2d && cd ../../..`
Expected: 绿

```bash
git add scripts/generate_tsumego_voice.py katrain/sounds/voice/ katrain/web/ui/src/kiosk/hooks/useVoice.ts
git commit -m "feat(kiosk): tsumego voice prompts (edge-tts assets + useVoice hook)"
```

---

### Task 10: physicalTsumegoMachine — 纯 reducer 相位机 + vitest 测试（核心逻辑）

评审修订的核心重构：相位机抽成**纯函数** `reduce(state, event) -> { state, commands }`——事件从 hook 进（携带所需盘面快照），commands（REST/LED/语音/undo/celebrate/advance）由 hook 执行。这样最复杂的状态逻辑可以 vitest 全覆盖，hook（Task 11）只剩薄薄的 IO 层。

相位：`off → clearing(清盘) → setup(摆初始局面，黑→白分阶段) → ready(等用户落子，move 已 arm)
→ replying(等屏幕稳定后引导用户镜像到物理盘：应手/自己的屏幕手/提子) / removing(答错拿除)
/ restoring(试下退出校验) → solved(庆祝) → clearing_next(auto-advance 前置清盘) → advance`。

关键设计（对应评审 Blocker）：
- **屏幕/物理双输入统一**：物理 `move_confirmed`（hook 调 placeStone 后）与屏幕点击（页面 wrapper 上报）都走同一 `MOVE_APPLIED` 事件——物理盘落后于屏幕时由 `replying` 收敛语义自动引导补子/提子。
- **应手竞态消解**：`MOVE_APPLIED(correct)` 只进 `replying` 并记 `pendingReply`（Task 8 的 scheduledReply）；hook 等 `stones` **真实包含**应手后才发 `BOARD_SETTLED` → 此时才 POST setup target。无应手（`pendingReply=null`）则等下一次 stones 渲染即 settle。
- **vision setup target 始终是完整目标盘面**，setup 分阶段只是引导展示（黑阶段只点亮缺的黑子）。
- **move arm 显式化**：仅 `ready` 相位 `armMoves(true)`，其余一律 false。

**Files:**
- Create: `katrain/web/ui/src/kiosk/hooks/physicalTsumegoMachine.ts`
- Test: Create `katrain/web/ui/src/kiosk/hooks/physicalTsumegoMachine.test.ts`

**Interfaces:**
- Produces: `reduce` / `initialState` / 类型 `MachineState, MachineEvent, Command, PhysicalPhase, SetupStage, LedPoint`。Task 11 依赖。
- Consumes: Task 8 `MoveResult`（含 scheduledReply）、Task 9 `VoiceName`、Task 6 `LedColor` 类型。

- [ ] **Step 1: 实现（完整文件）**

创建 `katrain/web/ui/src/kiosk/hooks/physicalTsumegoMachine.ts`：

```ts
// Pure phase machine for physical-board tsumego (kiosk). No IO — reduce() maps
// (state, event) to (state, declarative commands); usePhysicalTsumego executes them.
//
// Vision alternates between two modes: "converge to target board" (setup semantics —
// clearing, initial layout, mirroring screen state, wrong-move removal, try-exit
// restore) and "watch for one new stone" (move detection, explicitly armed ONLY in
// phase 'ready').
//
// Coordinates: vision row 0 = top (all boards here are vision-coord matrices).

import type { LedColor } from '../../api/ledApi';
import type { MoveResult } from '../../hooks/useTsumegoProblem';
import type { VoiceName } from './useVoice';

export type PhysicalPhase =
  | 'off'
  | 'clearing'       // converge to empty board (problem entry)
  | 'setup'          // converge to initial position (black stage, then white)
  | 'ready'          // user's turn — move detection armed
  | 'replying'       // waiting for screen to settle, then converge physical board to it
  | 'removing'       // wrong move — converge back to pre-move board, then undo screen
  | 'restoring'      // try-mode exit — converge physical board back to screen board
  | 'solved'         // celebration
  | 'clearing_next'; // auto-advance: converge to empty, then navigate

export type SetupStage = 'black' | 'white' | null;
export interface LedPoint { row: number; col: number; color: LedColor }

export type Command =
  | { kind: 'setupMode'; board: number[][] }
  | { kind: 'expectedBoard'; board: number[][] }
  | { kind: 'armMoves'; armed: boolean }
  | { kind: 'ledPoints'; points: LedPoint[] }
  | { kind: 'ledClear' }
  | { kind: 'speak'; name: VoiceName }
  | { kind: 'undoFailed' }   // executor: opts.undo() — restores pre-failure snapshot (Task 8)
  | { kind: 'celebrate' }    // executor: abortable white double-flash, then CELEBRATION_DONE
  | { kind: 'advance' };     // executor: opts.onAdvance() — navigate to next problem

export interface MachineState {
  phase: PhysicalPhase;
  stage: SetupStage;
  targetBoard: number[][] | null; // current vision setup target
  missing: Array<[number, number]>; // raw backend scope (full target)
  extra: Array<[number, number, number]>;
  stageMatched: number; // stage-scoped numbers for BoardSetupGuide (evaluation差异见评审 C10)
  stageTotal: number;
  pendingReply: { player: 'B' | 'W'; coords: [number, number] } | null;
  preMoveBoard: number[][] | null; // board before an incorrect move
}

export type MachineEvent =
  | { type: 'ENABLE'; emptyBoard: number[][] }
  | { type: 'SETUP_PROGRESS'; missing: Array<[number, number]>; extra: Array<[number, number, number]> }
  | { type: 'SETUP_COMPLETE'; screenBoard: number[][] }
  | { type: 'MOVE_APPLIED'; result: MoveResult | null; preBoard: number[][] }
  | { type: 'BOARD_SETTLED'; board: number[][] }
  | { type: 'SOLVED' }
  | { type: 'CELEBRATION_DONE'; autoAdvance: boolean; emptyBoard: number[][] }
  | { type: 'TRY_EXIT'; board: number[][] };

export const initialState: MachineState = {
  phase: 'off',
  stage: null,
  targetBoard: null,
  missing: [],
  extra: [],
  stageMatched: 0,
  stageTotal: 0,
  pendingReply: null,
  preMoveBoard: null,
};

const countColor = (board: number[][], color: number) =>
  board.reduce((n, row) => n + row.reduce((m, v) => m + (v === color ? 1 : 0), 0), 0);

const stoneColorAt = (board: number[][] | null, r: number, c: number): LedColor =>
  board?.[r]?.[c] === 2 ? 'white' : 'black';

const blues = (extra: Array<[number, number, number]>): LedPoint[] =>
  extra.map(([row, col]) => ({ row, col, color: 'remove' as LedColor }));

// While converging: still-to-place points in their target stone color, extras in blue.
const convergenceLeds = (state: MachineState, missing: Array<[number, number]>, extra: Array<[number, number, number]>): LedPoint[] => [
  ...missing.map(([row, col]) => ({ row, col, color: stoneColorAt(state.targetBoard, row, col) })),
  ...blues(extra),
];

const toReady = (state: MachineState, board: number[][]): { state: MachineState; commands: Command[] } => ({
  state: { ...state, phase: 'ready', stage: null, missing: [], extra: [], pendingReply: null },
  commands: [
    { kind: 'ledClear' },
    { kind: 'expectedBoard', board },
    { kind: 'armMoves', armed: true },
  ],
});

export function reduce(state: MachineState, evt: MachineEvent): { state: MachineState; commands: Command[] } {
  switch (evt.type) {
    case 'ENABLE':
      return {
        state: { ...initialState, phase: 'clearing', targetBoard: evt.emptyBoard },
        commands: [
          { kind: 'ledClear' },
          { kind: 'armMoves', armed: false },
          { kind: 'speak', name: 'clear_board' },
          { kind: 'setupMode', board: evt.emptyBoard },
        ],
      };

    case 'SETUP_PROGRESS': {
      const { missing, extra } = evt;
      const base = { ...state, missing, extra };
      switch (state.phase) {
        case 'clearing':
        case 'clearing_next':
          return { state: base, commands: [{ kind: 'ledPoints', points: blues(extra) }] };
        case 'removing':
        case 'restoring':
        case 'replying':
          // Guide both directions: put back what's missing (target color), take off extras (blue).
          return { state: base, commands: [{ kind: 'ledPoints', points: convergenceLeds(state, missing, extra) }] };
        case 'setup': {
          const target = state.targetBoard!;
          const missingBlack = missing.filter(([r, c]) => target[r][c] === 1);
          const missingWhite = missing.filter(([r, c]) => target[r][c] === 2);
          const nextStage: SetupStage = missingBlack.length > 0 ? 'black' : 'white';
          const active = nextStage === 'black' ? missingBlack : missingWhite;
          const stageTotal = countColor(target, nextStage === 'black' ? 1 : 2);
          const commands: Command[] = [];
          if (state.stage === 'black' && nextStage === 'white') commands.push({ kind: 'speak', name: 'place_white' });
          commands.push({
            kind: 'ledPoints',
            points: [
              ...active.map(([row, col]) => ({ row, col, color: nextStage as LedColor })),
              ...blues(extra),
            ],
          });
          return {
            state: { ...base, stage: nextStage, stageTotal, stageMatched: stageTotal - active.length },
            commands,
          };
        }
        default:
          return { state: base, commands: [] };
      }
    }

    case 'SETUP_COMPLETE': {
      switch (state.phase) {
        case 'clearing': {
          const target = evt.screenBoard;
          const stage: SetupStage = countColor(target, 1) > 0 ? 'black' : 'white';
          return {
            state: {
              ...state, phase: 'setup', stage, targetBoard: target,
              missing: [], extra: [], stageMatched: 0,
              stageTotal: countColor(target, stage === 'black' ? 1 : 2),
            },
            commands: [
              { kind: 'speak', name: stage === 'black' ? 'place_black' : 'place_white' },
              { kind: 'setupMode', board: target },
            ],
          };
        }
        case 'setup': {
          const r = toReady(state, evt.screenBoard);
          return { ...r, commands: [{ kind: 'speak', name: 'setup_done' }, ...r.commands] };
        }
        case 'replying':
        case 'restoring':
          return toReady(state, evt.screenBoard);
        case 'removing': {
          // Physical board is back at pre-move state; NOW restore the screen (undo snapshot)
          // and rebase on preMoveBoard (screenBoard still contains the wrong stone here).
          const board = state.preMoveBoard ?? evt.screenBoard;
          const r = toReady({ ...state, preMoveBoard: null }, board);
          return { ...r, commands: [{ kind: 'undoFailed' }, ...r.commands] };
        }
        case 'clearing_next':
          return { state: { ...state, missing: [], extra: [] }, commands: [{ kind: 'advance' }] };
        default:
          return { state, commands: [] };
      }
    }

    case 'MOVE_APPLIED': {
      if (state.phase !== 'ready' || !evt.result) return { state, commands: [] };
      const { result, preBoard } = evt;
      if (result.type === 'incorrect') {
        return {
          state: { ...state, phase: 'removing', preMoveBoard: preBoard, targetBoard: preBoard },
          commands: [
            { kind: 'armMoves', armed: false },
            { kind: 'speak', name: 'wrong_remove' },
            { kind: 'setupMode', board: preBoard },
          ],
        };
      }
      if (result.type === 'solved') {
        return {
          state: { ...state, phase: 'solved' },
          commands: [
            { kind: 'armMoves', armed: false },
            { kind: 'ledClear' },
            { kind: 'speak', name: 'correct' },
            { kind: 'celebrate' },
          ],
        };
      }
      // 'correct' (and defensive 'continue'): wait for the screen to settle, then converge.
      const commands: Command[] = [{ kind: 'armMoves', armed: false }];
      if ((result.captured ?? 0) > 0) commands.push({ kind: 'speak', name: 'capture_remove' });
      return {
        state: { ...state, phase: 'replying', pendingReply: result.scheduledReply ?? null },
        commands,
      };
    }

    case 'BOARD_SETTLED':
      if (state.phase !== 'replying') return { state, commands: [] };
      return {
        state: { ...state, targetBoard: evt.board, pendingReply: null },
        commands: [{ kind: 'setupMode', board: evt.board }],
      };

    case 'SOLVED':
      if (state.phase === 'off' || state.phase === 'solved') return { state, commands: [] };
      // May arrive from 'replying' when the AI reply completes the solution — celebrate
      // now; the physical board catches up during the next clearing (v1 simplification).
      return {
        state: { ...state, phase: 'solved', pendingReply: null },
        commands: [
          { kind: 'armMoves', armed: false },
          { kind: 'ledClear' },
          { kind: 'speak', name: 'correct' },
          { kind: 'celebrate' },
        ],
      };

    case 'CELEBRATION_DONE':
      if (state.phase !== 'solved' || !evt.autoAdvance) return { state, commands: [] };
      return {
        state: { ...state, phase: 'clearing_next', targetBoard: evt.emptyBoard },
        commands: [{ kind: 'speak', name: 'clear_board' }, { kind: 'setupMode', board: evt.emptyBoard }],
      };

    case 'TRY_EXIT':
      if (state.phase === 'off') return { state, commands: [] };
      return {
        state: { ...state, phase: 'restoring', targetBoard: evt.board, pendingReply: null },
        commands: [{ kind: 'setupMode', board: evt.board }],
      };

    default:
      return { state, commands: [] };
  }
}
```

（注：`nextStage as LedColor` 成立是因为 stage 值 `'black' | 'white'` 恰好是 LedColor 子集——如 TS 报错就显式映射。）

- [ ] **Step 2: 写 vitest 测试**

创建 `katrain/web/ui/src/kiosk/hooks/physicalTsumegoMachine.test.ts`（helpers：`empty(n)` 生成 n×n 零矩阵、`boardWith(n, cells)` 摆子；`run(events)` 从 initialState 依次 reduce 并收集 states/commands）。至少覆盖：

```ts
import { describe, expect, it } from 'vitest';
import { initialState, reduce, type MachineEvent, type MachineState } from './physicalTsumegoMachine';

// helpers 略：empty(19)、boardWith(19, {[r,c]: color})、
// step(state, evt) => ({state, commands})、kinds(commands) => command.kind 列表

describe('physicalTsumegoMachine', () => {
  it('ENABLE → clearing：清盘 target=空盘、语音、disarm', ...);
  it('clearing 中 SETUP_PROGRESS：extra 蓝灯', ...);
  it('clearing SETUP_COMPLETE → setup：target=初始盘面、黑阶段语音 place_black', ...);
  it('setup 分阶段：黑缺→红灯+stage 口径；黑摆完→白阶段+place_white 语音；错色子蓝灯并存', ...);
  it('setup SETUP_COMPLETE → ready：setup_done、ledClear、expectedBoard、armMoves(true)', ...);
  it('MOVE_APPLIED incorrect → removing：disarm、wrong_remove、setupMode(preBoard)；
      SETUP_COMPLETE → undoFailed + expectedBoard(preBoard) + 回 ready', ...);
  it('MOVE_APPLIED correct+scheduledReply → replying 且【无 setupMode 命令】（等 BOARD_SETTLED）；
      BOARD_SETTLED → setupMode(新盘面)；SETUP_COMPLETE → ready', ...);
  it('MOVE_APPLIED correct+captured>0 → 附带 capture_remove 语音', ...);
  it('MOVE_APPLIED 在非 ready 相位被忽略（返回原 state、无命令）', ...);
  it('SOLVED 从 replying 到达（AI 应手完成解题）→ solved + celebrate', ...);
  it('CELEBRATION_DONE(autoAdvance=true) → clearing_next + setupMode(空盘)；
      SETUP_COMPLETE → advance 命令', ...);
  it('CELEBRATION_DONE(autoAdvance=false) → 保持 solved、无命令', ...);
  it('TRY_EXIT → restoring + setupMode(屏幕盘面)；SETUP_COMPLETE → ready', ...);
});
```

（`...` 处写实际断言——每条用 helpers 构造事件序列，断言 phase 迁移 + 关键 command 的 kind/payload。这是本计划**测试密度最高**的文件，宁多勿少。）

- [ ] **Step 3: 跑测试 + 构建验证**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/hooks/physicalTsumegoMachine.test.ts && npm run build:kiosk-2d && cd ../../..`
Expected: 全 PASS + 构建绿

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/kiosk/hooks/physicalTsumegoMachine.ts katrain/web/ui/src/kiosk/hooks/physicalTsumegoMachine.test.ts
git commit -m "feat(kiosk): pure phase-machine reducer for physical tsumego + vitest coverage"
```

---

### Task 11: usePhysicalTsumego hook（IO 执行层）

薄 IO 层：消费 `syncEvents`（seq 队列，不丢事件）、把物理 `move_confirmed` 注入 `placeStone`（并播原有做题音效——三通道之一）、执行 reducer 的 commands、管理 enable/problemKey 生命周期、hint 白灯 + pause 聚合、试下退出触发 `TRY_EXIT`、可中止的 celebrate。

**Files:**
- Create: `katrain/web/ui/src/kiosk/hooks/usePhysicalTsumego.ts`
- Test: Create `katrain/web/ui/src/kiosk/hooks/usePhysicalTsumego.test.tsx`（少量 hook 级测试）

**Interfaces:**
- Consumes: Task 6 `API.visionMonitor/visionPause/visionMoveDetection/visionExpectedBoard/visionSetupMode`、`LedAPI.points/clear`（含 `hint` 色）、Task 7 `syncEvents`（含 seq/extra）、Task 8 `placeStone`（含 scheduledReply）/`undo`、Task 9 `useVoice`、Task 10 reducer。
- Produces: `usePhysicalTsumego(opts)` 返回 `{ phase, stage, missing, extra, stageMatched, stageTotal, ledOk, onScreenMove }`；页面（Task 12）依赖。

- [ ] **Step 1: 实现（完整文件）**

创建 `katrain/web/ui/src/kiosk/hooks/usePhysicalTsumego.ts`：

```ts
// IO layer for physical-board tsumego: consumes vision WS events (seq-ordered, no
// loss), injects physical moves into placeStone, executes machine commands
// (REST/LED/voice/undo/celebrate/advance). All phase logic lives in the pure
// reducer (physicalTsumegoMachine.ts) — keep this file thin.

import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../../api';
import { LedAPI } from '../../api/ledApi';
import type { MoveResult, Stone } from '../../hooks/useTsumegoProblem';
import type { VisionSyncEvent } from './useVisionSync';
import { useVoice } from './useVoice';
import {
  initialState,
  reduce,
  type Command,
  type LedPoint,
  type MachineEvent,
  type MachineState,
  type PhysicalPhase,
  type SetupStage,
} from './physicalTsumegoMachine';

export function stonesToVisionBoard(stones: Stone[], boardSize: number): number[][] {
  const board: number[][] = Array.from({ length: boardSize }, () => Array(boardSize).fill(0));
  for (const s of stones) {
    const [col, y] = s.coords;
    if (col >= 0 && col < boardSize && y >= 0 && y < boardSize) {
      board[boardSize - 1 - y][col] = s.player === 'B' ? 1 : 2;
    }
  }
  return board;
}

const emptyBoard = (size: number): number[][] =>
  Array.from({ length: size }, () => Array(size).fill(0));

const STAR_POINTS: Array<[number, number]> = [
  [3, 3], [3, 9], [3, 15], [9, 3], [9, 9], [9, 15], [15, 3], [15, 9], [15, 15],
];

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

export interface PhysicalTsumegoOptions {
  enabled: boolean;
  problemKey: string | null; // problem.id — lifecycle restarts on change
  boardSize: number;
  stones: Stone[];
  isSolved: boolean;
  showHint: boolean;
  hintCoords: [number, number] | null;
  isTryMode: boolean;
  autoAdvance: boolean; // auto-advance setting && next problem exists
  syncEvents: VisionSyncEvent[];
  placeStone: (x: number, y: number) => MoveResult | null;
  undo: () => void;
  playMoveSound: (sound: NonNullable<MoveResult['sound']>) => void;
  onAdvance: () => void; // navigate to next problem (after clearing_next completes)
}

export interface PhysicalTsumegoState {
  phase: PhysicalPhase;
  stage: SetupStage;
  missing: Array<[number, number]>;
  extra: Array<[number, number, number]>;
  stageMatched: number;
  stageTotal: number;
  ledOk: boolean;
  /** Page reports screen clicks here so the physical board is guided to follow (PRD TR1). */
  onScreenMove: (result: MoveResult | null, preBoard: number[][]) => void;
}

export function usePhysicalTsumego(opts: PhysicalTsumegoOptions): PhysicalTsumegoState {
  const { enabled, problemKey, boardSize, stones, isSolved, showHint, hintCoords, isTryMode, syncEvents } = opts;
  const { speak } = useVoice();

  const machineRef = useRef<MachineState>(initialState);
  const [ui, setUi] = useState<MachineState>(initialState);
  const [ledOk, setLedOk] = useState(true);

  // Refs so executors/consumers always see current values without re-subscribing.
  const optsRef = useRef(opts);
  optsRef.current = opts;
  const stonesRef = useRef(stones);
  stonesRef.current = stones;
  const pausedRef = useRef(false);
  pausedRef.current = showHint || isTryMode;

  const runIdRef = useRef(0); // bumps on lifecycle changes → aborts in-flight celebrate
  const lastLedKeyRef = useRef('');
  const processedSeqRef = useRef(-1);

  const ledPoints = useCallback((pts: LedPoint[]) => {
    const key = JSON.stringify(pts);
    if (key === lastLedKeyRef.current) return;
    lastLedKeyRef.current = key;
    LedAPI.points(pts)
      .then((r) => setLedOk(r.connected))
      .catch(() => setLedOk(false));
  }, []);

  const ledClear = useCallback(() => {
    lastLedKeyRef.current = '';
    LedAPI.clear().catch(() => setLedOk(false));
  }, []);

  // Forward declaration pattern: dispatch and celebrate reference each other.
  const dispatchRef = useRef<(evt: MachineEvent) => void>(() => {});

  const celebrate = useCallback(async (runId: number) => {
    const board = stonesToVisionBoard(stonesRef.current, optsRef.current.boardSize);
    const empties = STAR_POINTS.filter(([r, c]) => board[r]?.[c] === 0);
    const pts: LedPoint[] = empties.map(([row, col]) => ({ row, col, color: 'hint' }));
    for (let i = 0; i < 2; i++) {
      if (runId !== runIdRef.current) return; // aborted (problem change / disable)
      ledPoints(pts);
      await delay(350);
      if (runId !== runIdRef.current) return;
      ledClear();
      await delay(250);
    }
    if (runId !== runIdRef.current) return;
    dispatchRef.current({
      type: 'CELEBRATION_DONE',
      autoAdvance: optsRef.current.autoAdvance,
      emptyBoard: emptyBoard(optsRef.current.boardSize),
    });
  }, [ledPoints, ledClear]);

  const execute = useCallback((cmd: Command) => {
    switch (cmd.kind) {
      case 'setupMode':
        API.visionSetupMode(cmd.board).catch(() => {});
        break;
      case 'expectedBoard':
        API.visionExpectedBoard(cmd.board).catch(() => {});
        break;
      case 'armMoves':
        API.visionMoveDetection(cmd.armed).catch(() => {});
        break;
      case 'ledPoints':
        ledPoints(cmd.points);
        break;
      case 'ledClear':
        ledClear();
        break;
      case 'speak':
        speak(cmd.name);
        break;
      case 'undoFailed':
        optsRef.current.undo();
        break;
      case 'celebrate':
        void celebrate(runIdRef.current);
        break;
      case 'advance':
        optsRef.current.onAdvance();
        break;
    }
  }, [ledPoints, ledClear, speak, celebrate]);

  const dispatch = useCallback((evt: MachineEvent) => {
    const { state, commands } = reduce(machineRef.current, evt);
    machineRef.current = state;
    setUi(state);
    commands.forEach(execute);
  }, [execute]);
  dispatchRef.current = dispatch;

  // ---- enable / per-problem lifecycle ---------------------------------------
  useEffect(() => {
    if (!enabled) return;
    runIdRef.current += 1;
    API.visionMonitor(true).catch(() => {});
    dispatch({ type: 'ENABLE', emptyBoard: emptyBoard(boardSize) });
    return () => {
      runIdRef.current += 1; // abort celebrate
      machineRef.current = initialState;
      setUi(initialState);
      API.visionMoveDetection(false).catch(() => {});
      API.visionPause(false).catch(() => {});
      API.visionMonitor(false).catch(() => {});
      LedAPI.clear().catch(() => {});
    };
    // dispatch/boardSize stable across a problem's life; problemKey drives restarts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, problemKey]);

  // ---- WS event consumption (seq queue — every event exactly once, in order) --
  useEffect(() => {
    if (!enabled) return;
    for (const evt of syncEvents) {
      if (evt.seq <= processedSeqRef.current) continue;
      processedSeqRef.current = evt.seq;
      if (pausedRef.current) continue; // hint/try active: recognition is paused backend-side too
      if (evt.type === 'setup_progress') {
        const d = evt.data as { missing?: Array<[number, number]>; extra?: Array<[number, number, number]> };
        dispatch({ type: 'SETUP_PROGRESS', missing: d.missing ?? [], extra: d.extra ?? [] });
      } else if (evt.type === 'setup_complete') {
        dispatch({ type: 'SETUP_COMPLETE', screenBoard: stonesToVisionBoard(stonesRef.current, boardSize) });
      } else if (evt.type === 'move_confirmed' && machineRef.current.phase === 'ready') {
        const d = evt.data as { row: number; col: number; color: number };
        const preBoard = stonesToVisionBoard(stonesRef.current, boardSize);
        const result = optsRef.current.placeStone(d.col, boardSize - 1 - d.row);
        if (result?.sound) optsRef.current.playMoveSound(result.sound); // 三通道：物理落子也播既有音效
        dispatch({ type: 'MOVE_APPLIED', result, preBoard });
      }
    }
  }, [enabled, syncEvents, boardSize, dispatch]);

  // ---- screen settle watcher (replying phase) --------------------------------
  useEffect(() => {
    if (!enabled) return;
    const m = machineRef.current;
    if (m.phase !== 'replying') return;
    const reply = m.pendingReply;
    if (
      reply &&
      !stones.some((s) => s.player === reply.player && s.coords[0] === reply.coords[0] && s.coords[1] === reply.coords[1])
    ) {
      return; // AI reply not on screen yet (~300ms) — do NOT converge early (评审 Blocker)
    }
    dispatch({ type: 'BOARD_SETTLED', board: stonesToVisionBoard(stones, boardSize) });
  }, [enabled, stones, boardSize, dispatch]);

  // ---- solved watcher (AI reply may complete the solution) --------------------
  useEffect(() => {
    if (!enabled || !isSolved) return;
    dispatch({ type: 'SOLVED' }); // reducer ignores if already solved/off
  }, [enabled, isSolved, dispatch]);

  // ---- pause aggregate + hint white LED (order matters: before try-exit effect) --
  useEffect(() => {
    if (!enabled) return;
    const paused = showHint || isTryMode;
    API.visionPause(paused).catch(() => {});
    ledClear(); // wipe convergence frame on pause; wipe hint LED on unpause
    if (paused && showHint && hintCoords) {
      ledPoints([{ row: boardSize - 1 - hintCoords[1], col: hintCoords[0], color: 'hint' }]);
    }
    // On unpause the next SETUP_PROGRESS frame re-lights convergence LEDs; 'ready' has no LEDs.
  }, [enabled, showHint, isTryMode, hintCoords, boardSize, ledPoints, ledClear]);

  // ---- try-mode exit → restore/verify physical board --------------------------
  const prevTryRef = useRef(false);
  useEffect(() => {
    if (!enabled) {
      prevTryRef.current = isTryMode;
      return;
    }
    if (prevTryRef.current && !isTryMode) {
      // exitTryMode restored the screen snapshot in the same render — stonesRef is current.
      dispatch({ type: 'TRY_EXIT', board: stonesToVisionBoard(stonesRef.current, boardSize) });
    }
    prevTryRef.current = isTryMode;
  }, [enabled, isTryMode, boardSize, dispatch]);

  // ---- screen click passthrough (PRD TR1 dual input) --------------------------
  const onScreenMove = useCallback((result: MoveResult | null, preBoard: number[][]) => {
    dispatch({ type: 'MOVE_APPLIED', result, preBoard }); // reducer no-ops outside 'ready'
  }, [dispatch]);

  return {
    phase: ui.phase,
    stage: ui.stage,
    missing: ui.missing,
    extra: ui.extra,
    stageMatched: ui.stageMatched,
    stageTotal: ui.stageTotal,
    ledOk,
    onScreenMove,
  };
}
```

- [ ] **Step 2: hook 级 vitest 测试（IO 接线冒烟）**

创建 `katrain/web/ui/src/kiosk/hooks/usePhysicalTsumego.test.tsx`——`vi.mock('../../api')` 与 `vi.mock('../../api/ledApi')`，renderHook 后 rerender 推进 props。至少覆盖：

1. **seq 队列不丢事件**：一次 rerender 里塞两个新事件（`setup_progress` + `setup_complete`），两个都被消费（phase 前进两步）；重复 rerender 不重复消费（processedSeq 生效）。
2. **物理落子接线**：enabled + phase 推进到 ready 后（喂 setup_complete×2），塞 `move_confirmed` → `placeStone` 被以换算后坐标调用、`playMoveSound` 被调、phase 变 replying。
3. **hint 挂起**：`showHint=true, hintCoords=[x,y]` → `API.visionPause(true)` + `LedAPI.points` 收到 hint 白点；期间塞 `move_confirmed` → `placeStone` **不**被调。
4. **cleanup**：unmount → `visionMonitor(false)`、`visionPause(false)`、`visionMoveDetection(false)`、`LedAPI.clear` 均被调。

- [ ] **Step 3: 验证**

Run: `cd katrain/web/ui && npm test && npm run build:kiosk-2d && cd ../../..`
Expected: vitest 全绿 + 构建绿

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/kiosk/hooks/usePhysicalTsumego.ts katrain/web/ui/src/kiosk/hooks/usePhysicalTsumego.test.tsx
git commit -m "feat(kiosk): usePhysicalTsumego IO layer (seq consumption, dual-input moves, hint/try pause, abortable celebrate)"
```

---

### Task 12: 做题页集成 + BoardSetupGuide 增强 + 路由 guard + VisionContext recognition gate

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/BoardSetupGuide.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx:66`（去掉 tsumego problem 路由的 `requireRecognition` 强制）
- Modify: `katrain/web/ui/src/kiosk/context/VisionContext.tsx`（`recognitionReady` 字段）

**Interfaces:**
- Consumes: Task 11 `usePhysicalTsumego`；Task 6 `VisionStatusResponse.recognition_ready`。
- Produces: localStorage key `kiosk-tsumego-physical`（`'1'`/`'0'`，T1 记忆）。

- [ ] **Step 1: VisionContext 增加 recognitionReady**

`VisionContext.tsx`：`VisionStatus` 接口加 `recognitionReady: boolean;`，`DEFAULT_STATUS` 加 `recognitionReady: false,`，`mapResponse` 加 `recognitionReady: r.recognition_ready ?? false,`。

- [ ] **Step 2: BoardSetupGuide 增加 stage/extra 展示**

`BoardSetupGuide.tsx` props 与渲染改为（保持既有 props 兼容，新增可选项）：

```ts
interface BoardSetupGuideProps {
  matched: number;
  total: number;
  missing: Array<[number, number]>;
  extra?: Array<[number, number, number]>;
  stage?: 'black' | 'white' | null;
  isComplete: boolean;
  onStartProblem: () => void;
  onSkip: () => void;
}
```

进度标签区替换为：

```tsx
      <Typography variant="body1" sx={{ fontWeight: 500 }}>
        {stage === 'black' && '请摆放黑棋 · '}
        {stage === 'white' && '请摆放白棋 · '}
        已匹配 {matched}/{total} 颗子
      </Typography>
      {extra && extra.length > 0 && (
        <Typography variant="body2" color="warning.main">
          盘上有 {extra.length} 颗多余/错色棋子，请先取走（蓝灯指示）
        </Typography>
      )}
```

（函数签名解构处对应加 `extra = [], stage = null,`，并把原 `missing: _missing` 保留。）

- [ ] **Step 3: KioskApp 路由调整**

`KioskApp.tsx:66` 把 tsumego problem 路由从：

```tsx
<Route path="tsumego/problem/:problemId" element={<PhysicalBoardGuard requireRecognition><TsumegoProblemPage /></PhysicalBoardGuard>} />
```

改为：

```tsx
<Route path="tsumego/problem/:problemId" element={<TsumegoProblemPage />} />
```

（理由：物理模式改为页内 opt-in（T1），关着时不得强制标定；就绪检查移到开关按钮上。改完 `grep -n "tsumego/problem" katrain/web/ui/src/kiosk/KioskApp.tsx` 确认无 guard 包裹。若该行 JSX 格式与上述不符，以实际为准只移除 wrapper。）

- [ ] **Step 4: TsumegoProblemPage 集成**

对 `TsumegoProblemPage.tsx` 做以下修改（逐处）：

(a) imports 增加：

```tsx
import { SmartToy } from '@mui/icons-material';
import { usePhysicalTsumego, stonesToVisionBoard } from '../hooks/usePhysicalTsumego';
```

(b) 删除旧的 inert setup 集成：删掉 `:71-72` 的 `setupSkipped`/`setupDone` state、`:194-207` 的 setup-mode effect、`:209-214` 的 setup-complete effect、`:179-183` reset effect 中的 `setSetupDone/setSetupSkipped` 两行、以及 `:365-377` 旧 BoardSetupGuide 渲染块（Step 4(f) 用新块替换）。

(c) `useVisionSync(null)` 行之后加物理模式状态（记忆 + 就绪门控 + 每题 key）：

```tsx
  const [physicalMode, setPhysicalMode] = useState(
    () => localStorage.getItem('kiosk-tsumego-physical') === '1',
  );
  const togglePhysical = useCallback(() => {
    setPhysicalMode((prev) => {
      const next = !prev;
      try { localStorage.setItem('kiosk-tsumego-physical', next ? '1' : '0'); } catch { /* best-effort */ }
      return next;
    });
  }, []);
  // recognition_ready = 相机+模型+几何全就绪；物理盘固定 19 路（PRD Q1：非 19 路题隐藏物理模式）
  const physicalAvailable = visionStatus.enabled && visionStatus.recognitionReady && boardSize === 19;
  // problem 数据必须与当前路由匹配，防止题目切换途中用旧 stones 启动新题流程
  const physicalProblemReady = !!problem && problem.id === problemId;
  const physicalEnabled = physicalMode && physicalAvailable && physicalProblemReady;

  const physical = usePhysicalTsumego({
    enabled: physicalEnabled,
    problemKey: problem?.id ?? null,
    boardSize,
    stones,
    isSolved,
    showHint,
    hintCoords,
    isTryMode,
    autoAdvance: readAutoAdvance() && !isLast && !!nextId,
    syncEvents: visionSync.syncEvents,
    placeStone,
    undo,
    playMoveSound: playSound,
    onAdvance: handleAutoComplete, // 与既有 auto-advance 同一导航路径
  });
```

（`visionStatus` 从 `useVision()` 取；`handleAutoComplete` 为页面既有 auto-advance 导航函数——名字以实际为准，若签名不符包一层。）

(d) **屏幕落子物理感知 wrapper**（评审 Blocker C13——双输入必须同步物理盘）。`:252-254` 的 `onPlaceStone` 改为：

```tsx
          onPlaceStone={(x, y) => {
            // Physical mode: screen clicks only while it's the user's turn (guides own the
            // board in other phases); the machine then guides the physical board to follow.
            if (physicalEnabled && physical.phase !== 'ready') return;
            const preBoard = physicalEnabled ? stonesToVisionBoard(stones, boardSize) : null;
            const result = placeStone(x, y);
            if (result?.sound) playSound(result.sound);
            if (physicalEnabled && preBoard) physical.onScreenMove(result, preBoard);
          }}
```

(e) timer 式 auto-advance 让位给物理清盘闭环（PRD TR7「清盘引导完成后再进入下一题」由 `clearing_next` 相位实现）。`:185` 改为：

```tsx
  const autoAdvanceEnabled = isSolved && !isLast && !!nextId && readAutoAdvance() && !physicalEnabled;
```

(f) Action buttons 区（`:311` 的 `<Box>` 内）追加开关按钮；**提示/试下按钮在物理引导相位禁用**（防止 pause 语义在 clearing/setup 中途搅局）：

```tsx
          <Button
            variant={physicalMode ? 'contained' : 'outlined'}
            color={physicalMode ? 'success' : 'inherit'}
            startIcon={<SmartToy />}
            disabled={!physicalAvailable}
            onClick={togglePhysical}
          >
            {physicalMode ? t('tsumego:physicalOn', '退出物理棋盘') : t('tsumego:physicalOff', '使用物理棋盘')}
          </Button>
```

既有「提示」「试下」按钮的 `disabled` 条件各追加 `|| (physicalEnabled && physical.phase !== 'ready')`。

(g) 原 BoardSetupGuide 位置渲染新引导（物理模式时）：

```tsx
        {physicalEnabled && !['off', 'ready', 'solved'].includes(physical.phase) && (
          <Box sx={{ mt: 2 }}>
            {(physical.phase === 'clearing' || physical.phase === 'clearing_next') && (
              <Alert severity="info">
                请清空棋盘{physical.extra.length > 0 ? `（剩 ${physical.extra.length} 颗）` : ''}
              </Alert>
            )}
            {physical.phase === 'setup' && (
              <BoardSetupGuide
                matched={physical.stageMatched}
                total={physical.stageTotal}
                missing={physical.missing}
                extra={physical.extra}
                stage={physical.stage}
                isComplete={false}
                onStartProblem={() => {}}
                onSkip={togglePhysical}
              />
            )}
            {physical.phase === 'replying' && (
              <Alert severity="info">请按棋盘灯光摆放棋子（应手/提子），使棋盘与屏幕一致</Alert>
            )}
            {physical.phase === 'removing' && (
              <Alert severity="warning">
                答错了：请取回 {physical.extra.length} 颗棋子（蓝灯）
                {physical.missing.length > 0 ? `，并放回被提的 ${physical.missing.length} 颗棋子（红/绿灯）` : ''}
              </Alert>
            )}
            {physical.phase === 'restoring' && (
              <Alert severity="info">正在校验棋盘与题面一致，请按灯光调整棋子</Alert>
            )}
            {!physical.ledOk && <Alert severity="warning" sx={{ mt: 1 }}>LED 未连接，请按屏幕提示操作</Alert>}
          </Box>
        )}
```

- [ ] **Step 5: 双构建 + 手动冒烟**

Run: `cd katrain/web/ui && npm test && npm run build && npm run build:kiosk-2d && cd ../../..`
Expected: vitest 全绿 + 双绿

手动冒烟（Mac 无硬件，验证降级路径）：`uv run --no-sync python -m katrain --ui web` → 打开 `/kiosk/tsumego/problem/<任意id>` → 无 vision 服务时开关按钮 disabled；页面其余行为与改动前一致（判题、试下、提示、上一题/下一题、屏幕落子音效）。

- [ ] **Step 6: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx katrain/web/ui/src/kiosk/components/vision/BoardSetupGuide.tsx katrain/web/ui/src/kiosk/KioskApp.tsx katrain/web/ui/src/kiosk/context/VisionContext.tsx
git commit -m "feat(kiosk): physical-board tsumego page integration (toggle+memory, staged guide, dual-input sync, recognition gate)"
```

---

### Task 13: SuccessOverlay 去 emoji 换图标 + 两端答对文案统一（乱码修复 T9）

调研结论：文字链路干净（`tsumego:solved` cn=「正确！」，`.po/.mo`/传输全 UTF-8），乱码最可能是 kiosk 设备缺 emoji 字体致 `🎉` 豆腐块（kiosk 只自托管 Noto Sans SC + JetBrains Mono，`kiosk/theme.ts:4-8`）。修复：MUI SVG 图标替换 emoji（字体免疫），统一两端文案，并清理 kiosk 用不存在 key `Correct!` 的重复 Alert。

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/tsumego/SuccessOverlay.tsx:117-120`
- Modify: `katrain/web/ui/src/galaxy/components/tsumego/SuccessOverlay.tsx:137-147`
- Modify: `katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx:262, 285-287`

- [ ] **Step 1: kiosk SuccessOverlay**

顶部加 import：`import { EmojiEvents } from '@mui/icons-material';`
`:118-120` 的 `<Typography variant="h2" sx={{ mb: 1 }}>🎉</Typography>` 替换为：

```tsx
        <EmojiEvents sx={{ fontSize: 72, color: '#e6b93d', mb: 1, filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.5))' }} />
```

默认 message（`:54`）从 `'恭喜答对！'` 改为 `'正确！'`（与 i18n 目录值一致）。

- [ ] **Step 2: galaxy SuccessOverlay**

同样加 import，`:137-147` 的 `<Typography variant="h3" ...>🎉</Typography>` 替换为：

```tsx
        <EmojiEvents sx={{ fontSize: 72, color: '#4caf50', mb: 1, filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.5))' }} />
```

默认 message（`:68`）同改 `'正确！'`。

- [ ] **Step 3: kiosk 页面文案统一**

`TsumegoProblemPage.tsx:262` fallback 改为 `t('tsumego:solved', '正确！')`；`:285-287` 的
`{isSolved && (<Alert severity="success">{t('Correct!', '正确!')}</Alert>)}` 整块删除（与 SuccessOverlay 重复且 key 不存在于目录）。（行号为 Task 12 改动前的原始行号——以内容定位为准。）

- [ ] **Step 4: 双构建 + Commit**

Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd ../../..`
Expected: 双绿

```bash
git add katrain/web/ui/src/kiosk/components/tsumego/SuccessOverlay.tsx katrain/web/ui/src/galaxy/components/tsumego/SuccessOverlay.tsx katrain/web/ui/src/kiosk/pages/TsumegoProblemPage.tsx
git commit -m "fix(tsumego): replace emoji with SVG icon in success overlays; unify solved copy (kiosk garbled-text fix)"
```

（实机验证项记入 Task 14：kiosk 设备上 `curl -s http://localhost:8001/api/translations?lang=cn | python3 -c "import json,sys; print(json.load(sys.stdin).get('tsumego:solved'))"` 应输出 `正确！`，排除 `.mo` 不同步的次要嫌疑。）

---

### Task 14: 全量回归 + 收尾

- [ ] **Step 1: 后端全量（对比基线，不新增失败）**

Run: `CI=true uv run --no-sync pytest tests -q 2>&1 | tail -3`
Expected: failed 数 ≤ 基线（~53，环境性）；本计划新增/触碰的测试文件全 PASS：
`CI=true uv run --no-sync pytest tests/test_vision/ tests/test_vision_api.py tests/test_vision_pump.py tests/test_led_service.py tests/test_led_api.py -q` → 全 PASS

- [ ] **Step 2: 前端全量**

Run: `cd katrain/web/ui && npm test && cd ../../..`
Expected: vitest 全绿（含 machine/hook/useTsumegoProblem 新测试与全部既有测试）

- [ ] **Step 3: Black 格式化检查**

Run: `uv run --no-sync black -l 120 --check katrain tests || uv run --no-sync black -l 120 katrain tests`
如有 reformat 需要，追加 commit：`style: black`

- [ ] **Step 4: 双构建终检**

Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd ../../..`
Expected: 双绿，`verify:kiosk-2d` exit 0

- [ ] **Step 5: 实机验收清单（需 SBC + 摄像头 + LED 棋盘，人工执行并记录）**

按 PRD §6 验收标准逐项：完整闭环（清盘→黑红/白绿分阶段摆放→物理落子判题→应手灯→答对三通道→auto-advance 清盘引导后进下一题）、答错拿除流（**含错着提子：取回+放回双向引导**）、含提子的正解流、提示白灯挂起识别、试下挂起+退出校验（一致/不一致两条路径）、**屏幕点击落子后物理盘被引导跟上**、乱码修复实机确认（无豆腐块 + `/api/translations` 字节核实）、开关记忆、LED/摄像头拔插降级、物理模式关闭回归、**bound 对弈路径回归**（开一局对弈+开着 kiosk 页面的 `/ws/vision`，确认物理落子不再被 WS 抢丢——Task 5 修复项）。

- [ ] **Step 6: 最终提交与收尾**

```bash
git add superpowers/tracks/kiosk-physical-tsumego/
git commit -m "docs(kiosk-physical-tsumego): PRD + implementation plan (v2 after external review)"
git log --oneline develop..HEAD
```

Expected: 约 13 个 feature commits + 1 个 docs commit。之后使用 superpowers:finishing-a-development-branch 决定合并方式。

---

## 已知风险与执行注意（对应 PRD §7 + 评审）

1. **R1 已消解**：Task 1 直接实现 extra 检测（含错色子——错色点同时进 missing 和 extra）；空 target 立即 COMPLETE 的旧 bug 由严格相等修复（清盘引导依赖此项）。
2. **事件不丢**：前端 seq 队列（Task 7/11）+ 服务端单泵 fan-out（Task 5）双保险。**不要**在任何新代码里直接调 `VisionService.poll_events()`（泵是唯一消费者）。
3. **应手竞态已消解**：`scheduledReply` 元数据（Task 8）+ `BOARD_SETTLED` 门槛（Task 10/11）——收敛目标永远等屏幕真实稳定后才下发。用户在应手落屏前提前摆子＝setup 语义下的暂时 extra/missing，会被引导自愈，无需特判。
4. **placeStone 闭包**：hook 经 `optsRef` 取最新 `placeStone`（依赖 `stones/nextPlayer` 的 useCallback），事件消费 effect 不依赖它——refs 保证相位与回调都不过期。
5. **答错含提子**：failed 快照（Task 8）保证屏幕可恢复；removing 相位的 LED/文案同时给「取回（蓝）」与「放回（红/绿）」双向引导（Task 10 convergenceLeds + Task 12 (g)）。
6. **SOLVED 途中到达**：AI 应手完成解题时（isSolved 在 replying 相位翻转），v1 直接庆祝、物理盘上缺的最后一颗应手子留给下一次清盘处理（有意简化，Task 10 注释注明）。
7. **boardSize≠19 的题**：`physicalAvailable` 含 `boardSize === 19`（Task 12 (c)），非 19 路题开关禁用。
8. **提示白灯 v1 常亮不闪**：显示期间识别已挂起（pause），闪烁留实机调优（PRD T4 允许）。
9. **pause 单 owner 契约**：见 Global Constraints——页面聚合 `showHint || isTryMode` 单点下发；试下/提示按钮在引导相位被禁用（Task 12 (f)），保证 pause 只在 ready 相位切换。
10. **实机前置**：SBC 上需 `--vision-model` + `--led-serial-port` 启动 board 模式；几何锁已标定（`~/.katrain/geometry_lock.npz`）。

## Review 修订记录（2026-07-02，Codex + Gemini 反馈处理）

**采纳（均已对照代码核实）：**

| 反馈 | 处理 |
|---|---|
| Codex B1/Gemini A1：`latestEvent` 丢事件 | Task 7 seq + Task 11 队列消费（丢 `setup_complete`/`move_confirmed` 会卡死相位机，必须现在改） |
| Codex B2：replying 把用户手误当应手 | Task 8 `scheduledReply` + Task 10/11 `BOARD_SETTLED` 门槛（核实：用户子同步落、AI 应手 +300ms） |
| Codex B3/Gemini A3：`undo()` 恢复不了被提子 | Task 8 failed 快照（核实：incorrect 分支跑 `removeCaptures`、undo 只 `slice(0,-1)` 且误弹 moveHistory——屏幕模式既有 bug 一并修复） |
| Codex B4/Gemini C13：屏幕点击无同步路径 | Task 11 `onScreenMove` + Task 12 (d) wrapper，物理/屏幕双输入统一走 `MOVE_APPLIED` |
| Codex B5：提示白灯/试下退出校验未落地 | Task 11 hint 白灯 effect + `TRY_EXIT`→restoring 相位（Task 10） |
| Codex B6：move gating 过粗、setup 完成无 rebase | Task 2/3 `move_armed` 显式 arm + SETUP_COMPLETE 时 `force_sync` |
| Codex M/Gemini B8：`/ws/vision` 破坏性单消费者 | Task 5 服务端泵 fan-out（核实时发现比评审说的更糟：WS handler 静默丢 `ConfirmedMove`、与对弈 poller 竞态——顺带修复既有 bound 路径隐患） |
| Codex M/Gemini A4：celebrate 无 abort | Task 11 runId 模式（Gemini 的 AbortController 等价，取更简者） |
| Codex M/Gemini A5：restartKey 绕 | Task 11/12 直接用 `problemKey=problem.id` + `physicalProblemReady` 门控 |
| Codex M/审阅 C10：matched 口径错 | Task 10 reducer 内算 `stageMatched/stageTotal`，页面直接消费 |
| Codex M：extra 应含错色子 | Task 1 新口径（错色点同时进 missing+extra） |
| Codex M/Gemini C11：缺前端单测 | 相位机抽纯 reducer（Task 10）+ machine/hook/useTsumegoProblem 三层 vitest。核实：vitest+RTL 仓库已有，无需引入（Gemini「需搭建 vitest」前提不成立） |
| Codex M：`physicalAvailable` 应看 recognition_ready | Task 6/12：`recognition_ready` 端点已返回（核实），补 TS 类型 + VisionContext 映射 + `boardSize===19` |
| Codex M：物理落子没播既有音效 | Task 11 `playMoveSound(result.sound)` |
| Codex M：auto-advance 直接禁用与 PRD TR7 矛盾 | Task 10/11/12 `clearing_next` 相位：庆祝→清盘引导→完成后 `onAdvance` 导航（timer 式 auto-advance 仅物理模式下让位） |
| Codex m：pause 单 owner 要写明 | Global Constraints + 端点 docstring + 按钮相位禁用 |
| Codex m：worker 分流契约缺测试 | Task 2 `move_event()` 共享构造函数 + 契约测试（两 worker 共用防漂移） |

**否决（含理由）：**

| 反馈 | 理由 |
|---|---|
| Gemini A2：replying 期间 pause 视觉 | 治标不治本——竞态根因是「从 stones 尾巴猜应手」，`scheduledReply` 修根因后，用户提前摆子由 setup 语义自然引导（提前摆的恰是应手＝直接 matched），pause 反而拖慢反馈 |
| Gemini C10：BoardSetupGuide 直接用后端 matched/total | 后端数字是**全目标**口径，黑/白分阶段是前端展示概念——直接用会在黑阶段显示含白子的总数。采 Codex 的 stage 口径方案 |
| Gemini B9：pause 改引用计数/named-lock | v1 单页面单 owner（YAGNI）；已用文档+按钮禁用锁定契约，多 owner 时再升级（记为技术债注释） |
| Gemini C11：「计划须新增任务搭建 vitest」 | 前提不成立——vitest/@testing-library 已在 devDependencies 且有大量既有测试，直接写测试即可 |
