# Kiosk 物理棋盘对弈（一期）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 kiosk 人机对弈（自由 + 升降级）在物理棋盘上闭环：用户在真实棋盘摆子（视觉自动确认注入），AI 落子/提子由 LED 指示，屏幕承担混合确认兜底、AI 支招（白灯 top-N）与降级徽标。

**Architecture:** 核心新增一个后端 **PhysicalPlayOrchestrator**（挂 `app.state.physical_play`）：以「对账循环」而非事件驱动——每 tick 比较权威数字盘面（`game_update` state）与视觉观测盘面，差集即 LED 批次（缺子→按棋色红/绿引导摆放，多余待提→蓝）。一个循环同时覆盖 AI 落子灯、提子灯、悔棋恢复、让子引导、开局残子清理。事件源只有 `game_update` state dict（PRD R8.1/Q5 抽象：二期远程对手、双人类玩家零改动接入）。支招白灯 = hint 端点（门控链）+ 编排器闪烁任务 + vision 挂起/亮灯点遮蔽。

**Tech Stack:** Python 3.11 / FastAPI / numpy（后端）；React + TS + MUI + Vitest（kiosk 前端）；pytest；现有 LedService（串口）与 VisionService（worker 进程）。

## Global Constraints

- **LED 硬规则（PRD D2③，永久）**：LED 绝不为几何自动闪灯；一切 LED 几何重标定必须由用户屏幕按钮触发。
- **构建边界（CLAUDE.md SBC 契约）**：新前端文件只放 `src/kiosk/**`，只 import 共享区 + `src/kiosk/`；改共享文件（`src/api.ts`、`src/hooks/useGameSession.ts`）后必须双构建绿：`npm run build` **和** `npm run build:kiosk-2d`。
- **回归基线**：`CI=true uv run pytest tests` 相对 develop@96e64f53 基线（**53 failed + 10 errors 预存**，Task 1 执行时实测；早前草稿写的 37 已过时）无新增失败；摆谱模块行为不变。
- Python 格式：`uv run black -l 120 katrain tests`；提交信息用仓库现有 conventional 风格（`feat(vision): …` / `fix(web): …` / `feat(kiosk): …`）。
- 前端新增文案用 `t('English', '中文')` 模式（`useTranslation`），默认中文。
- 不改固件（`SETI/SHOW/CLEAR/BRIGHT` 够用，闪烁由主机驱动）；不动拍谱/摆谱流程。
- LED 写一律 `strict=False`（UI 容忍路径）；LED 失败不阻塞对局（R2.6）。
- 编排器直驱 LedService 时必须自行刷新 `app.state.led_last_activity`，否则 5 分钟失效保护会盘中熄灯。
- 坐标约定：**vision 网格 = LED LUT 网格**（row 0 = 顶、col 0 = 左）；KaTrain `stones` 的 `[x, y]` 是 GTP 系（y 自底向上），换算 `row = board_size - 1 - y, col = x`（即 `game_state_stones_to_board` 的语义）。

## 已拍板决定（2026-07-02，PRD §9 待确认问题的落地）

| # | 决定 |
|---|---|
| Q1 | **计费留接口后接**：一期 hint 只做「场景 + ranked 门控 + 引擎路由」，定义 `HintGate` 协议；paid-analysis（feature/rk3588-ui）合入后实现 `BillingHintGate` 即接通。本分支不合 rk3588-ui。（另：board 模式 billing REST 现返回 503 need_online，本地扣费本来就不可行，见 Task 8 注释。） |
| Q2 | hint 默认值（后端可配置）：top-N=3、闪烁周期 0.8s、展示超时 30s、visits=100；每局次数上限不做（后接计费时天然限制）。 |
| Q3 | ranked 计时 = **视觉确认时刻**（现状注入即计时，无代码改动）；UI 显示「确认中」状态条（Task 10）。 |
| Q4 | AI 子未摆好前**阻塞**用户下一手。**实现方式（2026-07-02 外部评审后重设计）**：盘面未追平时编排器**暂停 worker 的落子确认**（pause move detection）——期间用户抢下的子不会被确认；追平后检测恢复，抢下的子相对 force_sync 基线自然确认注入，顺序正确。~~poller 持有已确认落子~~ 方案否决：`MoveDetector` 在确认瞬间推进基线（`prev_board = board.copy()`），持有会产生陈旧 ConfirmedMove，极端情形（held 一手提掉 AI 刚落的子）会注入错着。30s 屏幕提醒 + 120s 升级对话框（重试/已恢复/改屏幕落子）。 |
| Q5 | 落子事件源抽象 = 编排器只消费 `game_update` state dict（Task 4 docstring 固化）。 |
| Q6 | 音效：复用现有 `sound` 广播（AI 落子已有 stone/capturing 音）；异常/提醒不加新音效，一期从简。 |

## 探索发现的关键事实（写代码前必读，均已核实）

1. **现存 bug**：`server.py:1854` 与 `api/v1/endpoints/vision.py:123` 调 `session.get_game_state()`，但 `WebSession` 无此方法（正确是 `session.katrain.get_state()`）→ 视觉绑定/落子注入的「更新期望盘面」步骤今天必然 AttributeError。Task 1 修。
2. **事件队列双消费者竞态**：`/ws/vision` 循环的 `poll_events()` 会把 `ConfirmedMove`（非 dict）**排干并丢弃**，与 `_vision_move_poller` 的 `get_confirmed_move()` 竞争同一队列 → 前端开着对局页时用户落子可能丢失。Task 2 修。
3. `ambiguous_stone` / `move_confirmed` 事件在枚举里**从未被发出**；vision 无 pause/遮蔽命令。Task 7 补。
4. **新命令必须同时加到两个分发器**：`worker.py:_process_commands`（SBC 子进程）和 `worker_inprocess.py:_drain_commands`（Mac 开发线程）——`SET_GEOMETRY` 只在 in-process 有、子进程漏掉，是前车之鉴。
5. `update_state_callback` / `message_callback` 是**单槽**（非列表），已被 `SessionManager.create_session`（session.py:59-60）占用 → 编排器必须包装（wrap）再链式调用。
6. `game_update` payload（`interface.py:288-466` `get_state()`）**无提子差分**，只有全量 `stones` 与累计 `prisoner_count` → 编排器自己 diff 相邻两次 expected。payload 已含 `game_type` 与 `analysis_allowed`（前端 TS 类型未声明，Task 9 补）。
7. sync 状态机现有 capture 分类是「expected 有、observed 无 → capture_pending」——数字侧提子（引擎已提、物理盘还在）反而落到 illegal_change。编排器每次 game_update 推送期望盘面后，AI 刚落的子会被误报 capture_pending。Task 5 用 prev-expected 快照重分类（数字权威语义），**必须先于 Task 6 的接线**。
8. ranked 后端**未禁悔棋**（`ANALYSIS_ACTIONS` 只盖分析）。Task 13 补。
9. LED 相关：`LedService.set_points/set_rgb_points/clear/is_connected`（无 `status()` 方法）；`COLOR_RGB`: black→红、white→绿、remove→蓝；`set_points` 每批 = 清屏+重设（天然混色批次）。配置走「settings 下划线私有属性注入」惯例（`settings._led_config` 式），**不要**给 pydantic Settings 加非声明字段（会 ValueError）。
10. 引擎路由：`await app.state.router.route(payload)`，`payload["is_analysis"]=True` 走云端（board 模式 cloud=None 自动回落本地）。top-N 现成来源 = KataGo `moveInfos`（`quick-analyze` 端点是样板，`analysis.py:40-66`）。
11. 前端：`GamePage` 无 `mode` 路由参数（用 state 里的 `game_type`）；`MovePendingOverlay`/`AmbiguousStoneAlert` 是死代码可随意重写；LED 健康不在 vision status payload（Task 9 加 `led_connected` 搭现有 3s 轮询便车）；`src/api/geometryApi.ts` 已存在（Task 14 复用，**签名 `calibrate(trigger: 'auto' | 'manual')` 必须传参**，geometryApi.ts:85）。

## 外部评审采纳记录（2026-07-02，Codex + Gemini 审阅 plan.md 草稿）

**采纳（已并入下方任务）：**
- **[Codex Blocker] Q4 hold-gate 不可行** → Task 3/4/6/7 重设计为「未追平即暂停落子确认」（见 Q4 行）。单测覆盖：Task 3（抢跑子无蓝灯）+ Task 4（TestPauseDrive）+ Task 7（分发器）；端到端抢跑序列 = Task 15 验收项 12。
- **[Codex Blocker] Task 5 误分类**：`prev!=空 ∧ expected!=空 ∧ observed==空`（活子被误拿走）原方案会走 CAPTURE_PENDING→秒清除，掩盖真实异常 → 改四分类：该情形入 missing-异常（走 mismatch 防抖流），removal_needed 只收 `expected==空 ∧ observed!=空 ∧ prev==observed`（数字侧提子待拿）。
- **[Codex Blocker + Gemini Blocker] LED 失效保护熄灯后不再重亮**（review-request §A 确认为真）→ Task 4 加周期重申（`led_reassert_interval_s=240 < 300s` 窗口，写后盖活动戳）；同时覆盖手动清灯/USB 重插恢复。采 Codex 方案（Gemini 的 touch-per-tick 不覆盖 caught-up 态的蓝灯与手动清灯）。
- **[双方 Important] 摆放目标灯眩光**：to_place 条件改为 `expected!=空 ∧ observed==空`——目标点一出现任何棋子检测灯即灭（1 tick），检测消失自动回亮；错色子转 sync 异常流（不再常亮引导灯）。
- **[Codex Important] hint payload 重建不完整** → Task 8 镜像 `BaseEngine.request_analysis`（engine.py:123-190）语义：`nodes_from_root` 全路径收集 moves/placements、`clear_placements` 拒绝（400）、带 `initialPlayer`。
- **[Codex Important + Gemini Important] 物理失同步需逃生舱** → 提醒升级两档：30s toast、120s 对话框（重试检测 / 已手动恢复 / 改用屏幕落子=visionUnbind）。Task 4 广播 `kind` 字段，Task 10 前端。
- **[Codex Important] `GeometryAPI.calibrate` 需 trigger 参数** → Task 14 改 `calibrate('manual')`。
- **[Codex Minor] visionBind 双重调用** → Task 9 移除 GamePage 直调（单一 owner = useVisionSync）；Task 4 on_bind 幂等。
- 基线数字修正（53+10）；Task 15 增补验收项（>5min 灯重申、抢跑回归、逃生舱路径）。

**驳回（已核实为误）：**
- **[Gemini "Blocker" G]** 称 `get_state()` 不含 `game_type`/`analysis_allowed` —— **错**，interface.py:464-465 明确发出（Codex 亦独立核实）。前端只补 TS 类型即可，无后端改动。
- **[Gemini Important F]** 称 hint 依赖不存在的 `get_engine(force_strong=True)` —— 计划从未如此写；走真实 `RequestRouter.route(payload)`（core/router.py:10-19，Codex 核实 OK）。其合理残余（payload 完整性）已按 Codex I2 修。
- **[Gemini Important C]** 建议给 expected 推送加序号/哈希防漏 —— 不必要：250ms 节流**合并到最新态**，prev = 上次成功推送的期望盘；漏推只会让更多点落入「待摆放」安全桶（removal_needed 要求 `prev==observed` 精确成立，漏推不会伪造它）。Task 5 加注释说明即可，不加机制（YAGNI）。

**双方一致确认 OK**：对账循环架构、Task 2 双 deque 修复无竞态（单线程 asyncio、drain 无 await）、RequestRouter 云端优先语义。

## File Structure（新增/主要改动一览）

```
katrain/web/core/physical_play.py                 [新] PhysicalPlayConfig + LedPlanner（纯逻辑）
katrain/web/core/physical_play_orchestrator.py    [新] 编排器（async 壳）
katrain/web/core/hint_gate.py                     [新] HintGate 协议 + DefaultHintGate
katrain/web/api/v1/endpoints/hint.py              [新] POST /api/v1/hint, /hint/dismiss
katrain/web/api/v1/endpoints/vision.py            [改] bug 修复、bind/unbind 挂编排器、status 加 led_connected
katrain/web/server.py                             [改] poller 加固(回合色校验/lock)、lifespan 装配、CLI args、/api/undo ranked 禁用
katrain/vision/service.py                         [改] 事件路由竞态修复、pause/resume/set_lit_points
katrain/vision/ipc.py                             [改] 新 CommandType×3
katrain/vision/worker.py + worker_inprocess.py    [改] pause 门控、遮蔽、move_pending/ambiguous_stone 发射
katrain/vision/sync.py                            [改] prev-expected 快照 + 数字权威 diff 重分类
katrain/vision/board_state.py                     [改] masked_cells 参数 + cell_confidences
katrain/web/ui/src/api.ts                         [改·共享区] GameState 补字段、hint API、vision status 补字段
katrain/web/ui/src/hooks/useGameSession.ts        [改·共享区] physical_reminder 消息透出
katrain/web/ui/src/kiosk/context/VisionContext.tsx [改] ledConnected
katrain/web/ui/src/kiosk/pages/GamePage.tsx        [改] 徽标/状态条/支招/悔棋拦截/漂移横幅
katrain/web/ui/src/kiosk/components/physical/*     [新] PhysicalPlayStatusChip, BoardMismatchDialog, AmbiguousMoveCard, HintPanel, PoseLostBanner
katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx [改] 接新事件/新对话框
tests/test_vision_bind_state.py, tests/test_physical_play.py, tests/test_physical_play_orchestrator.py,
tests/test_hint_api.py, tests/test_vision/*（扩） , src/kiosk/__tests__/*（扩）
```

**PRD 阶段 ↔ 任务映射**：P1=T1–T4,T6,T9 · P2=T3,T5 · P3=T7(事件),T10,T11,T14 · P4=T7(挂起/遮蔽),T8,T12 · P5=T13 · P6=T15。任务按编号顺序执行即满足依赖。

---

### Task 1: 修复 `session.get_game_state()` AttributeError

**Files:**
- Modify: `katrain/web/api/v1/endpoints/vision.py:123`
- Modify: `katrain/web/server.py:1854`
- Test: `tests/test_vision_bind_state.py`（新）

**Interfaces:**
- Consumes: `WebSession.katrain.get_state()`（interface.py:288，返回含 `stones` 的 dict）
- Produces: bind 端点与 poller 能真正调用 `vision.set_expected_from_stones(state["stones"])`；后续所有任务默认此路径可用

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vision_bind_state.py
"""Bind a session to vision and assert the expected board is seeded from katrain state."""
import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import vision


class FakeVision:
    def __init__(self):
        self.bound = None
        self.expected_stones = None

    def bind_session(self, sid):
        self.bound = sid

    def unbind_session(self):
        self.bound = None

    def set_expected_from_stones(self, stones, board_size=19):
        self.expected_stones = stones


class FakeKatrain:
    def get_state(self):
        return {"stones": [["B", [3, 15], None, 1]], "board_size": [19, 19]}


class FakeSession:
    def __init__(self):
        self.katrain = FakeKatrain()


class FakeManager:
    def get_session(self, sid):
        return FakeSession()


def _client(vision_obj, manager):
    app = FastAPI()
    app.include_router(vision.router, prefix="/vision")
    app.state.vision = vision_obj
    app.state.session_manager = manager
    return TestClient(app, raise_server_exceptions=False)


class TestVisionBind:
    def test_bind_seeds_expected_board_from_katrain_state(self):
        fake = FakeVision()
        c = _client(fake, FakeManager())
        r = c.post("/vision/bind", json={"session_id": "s1"})
        assert r.status_code == 200
        assert fake.bound == "s1"
        assert fake.expected_stones == [["B", [3, 15], None, 1]]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/test_vision_bind_state.py -v`
Expected: FAIL——bind 返回 500（`AttributeError: 'FakeSession' object has no attribute 'get_game_state'`），`expected_stones` 为 None。

- [ ] **Step 3: 修两处调用点**

`katrain/web/api/v1/endpoints/vision.py:123`，把

```python
    game_state = session.get_game_state()
```
改为
```python
    game_state = session.katrain.get_state()
```

`katrain/web/server.py:1854`（`_vision_move_poller` 内），把
```python
                        game_state = session.get_game_state()
```
改为
```python
                        game_state = session.katrain.get_state()
```

- [ ] **Step 4: 跑测试确认通过 + 无回归**

Run: `CI=true uv run pytest tests/test_vision_bind_state.py tests/test_vision_api.py -v`
Expected: 新测试 PASS；test_vision_api.py 与基线相同。

- [ ] **Step 5: Commit**

```bash
git add tests/test_vision_bind_state.py katrain/web/api/v1/endpoints/vision.py katrain/web/server.py
git commit -m "fix(web): vision bind/poller called nonexistent session.get_game_state()"
```

---

### Task 2: 修复 VisionService 事件队列双消费者竞态

**Files:**
- Modify: `katrain/vision/service.py`（`__init__`、`poll_events`、`get_confirmed_move`）
- Test: `tests/test_vision/test_service_event_routing.py`（新）

**Interfaces:**
- Consumes: worker 的 `get_event()`（返回 `ConfirmedMove | dict | None`）
- Produces: `poll_events() -> list[dict]`（只含 dict 事件，永不吞落子）；`get_confirmed_move() -> ConfirmedMove | None`（FIFO，不再丢中间落子、不再 poke `_event_queue`）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vision/test_service_event_routing.py
"""poll_events must never swallow ConfirmedMove; get_confirmed_move must be FIFO."""
from katrain.vision.ipc import ConfirmedMove
from katrain.vision.service import VisionService
from katrain.vision.config_service import VisionServiceConfig


class FakeWorker:
    def __init__(self, events):
        self._events = list(events)

    def get_event(self):
        return self._events.pop(0) if self._events else None


def _service(events):
    svc = VisionService(VisionServiceConfig(enabled=True))
    svc._worker = FakeWorker(events)
    return svc


class TestEventRouting:
    def test_poll_events_preserves_moves_for_move_consumer(self):
        move = ConfirmedMove(col=3, row=4, color=1)
        svc = _service([{"type": "synced", "data": {}}, move])
        events = svc.poll_events()
        assert events == [{"type": "synced", "data": {}}]  # dict 事件正常返回
        assert svc.get_confirmed_move() == move  # 落子没有被 poll_events 吞掉

    def test_get_confirmed_move_is_fifo_and_requeues_nothing(self):
        m1 = ConfirmedMove(col=1, row=1, color=1)
        m2 = ConfirmedMove(col=2, row=2, color=2)
        svc = _service([m1, {"type": "degraded", "data": {}}, m2])
        assert svc.get_confirmed_move() == m1
        assert svc.get_confirmed_move() == m2
        assert svc.get_confirmed_move() is None
        assert svc.poll_events() == [{"type": "degraded", "data": {}}]
```

（`VisionServiceConfig(enabled=True)` 若必填字段不同，按 `config_service.py` 的 dataclass 默认值最小化构造。）

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/test_vision/test_service_event_routing.py -v`
Expected: FAIL——第一条：`get_confirmed_move()` 返回 None（move 已被 poll_events 排出且无处安放）；第二条：只拿到最后一手 m2（"keep latest" 丢 m1）。

- [ ] **Step 3: 实现内部路由**

`katrain/vision/service.py`：`__init__` 追加两行；`poll_events`/`get_confirmed_move` 整体替换：

```python
from collections import deque   # 文件头 import 区
```
```python
        # __init__ 末尾追加：
        self._pending_events: deque = deque()
        self._pending_moves: deque = deque()
```
```python
    def _drain_worker(self) -> None:
        """Single drain point: route ConfirmedMove and dict events to separate queues
        so the /ws/vision loop and the move poller no longer race on one queue."""
        if not self._worker:
            return
        while True:
            evt = self._worker.get_event()
            if evt is None:
                break
            if isinstance(evt, ConfirmedMove):
                self._pending_moves.append(evt)
            else:
                self._pending_events.append(evt)

    def poll_events(self) -> list[Any]:
        """Read all pending dict events from worker (never consumes moves)."""
        self._drain_worker()
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def get_confirmed_move(self) -> ConfirmedMove | None:
        """Read and consume the OLDEST pending confirmed move (FIFO — a stalled
        poller no longer silently drops intermediate moves)."""
        self._drain_worker()
        if self._pending_moves:
            return self._pending_moves.popleft()
        return None
```

- [ ] **Step 4: 跑测试确认通过 + vision 全量回归**

Run: `CI=true uv run pytest tests/test_vision/ tests/test_vision_api.py -v`
Expected: 全 PASS（相对基线）。

- [ ] **Step 5: Commit**

```bash
git add katrain/vision/service.py tests/test_vision/test_service_event_routing.py
git commit -m "fix(vision): route ConfirmedMove and dict events to separate queues (ws/poller race)"
```

---

### Task 3: `physical_play.py` — PhysicalPlayConfig + LedPlanner 纯逻辑核

**Files:**
- Create: `katrain/web/core/physical_play.py`
- Test: `tests/test_physical_play.py`（新）

**Interfaces:**
- Consumes: 无（纯 numpy）
- Produces（后续任务按名引用，不得改名）:
  - `PhysicalPlayConfig(tick_interval_s=0.5, reminder_after_s=30.0, escalate_after_s=120.0, led_reassert_interval_s=240.0, extra_stone_debounce_ticks=6, hint_top_n=3, hint_blink_period_s=0.8, hint_timeout_s=30.0, hint_max_visits=100, hint_engine="local")`
  - `LedPlanner(config)`: `.reset()`, `.on_expected(expected: np.ndarray)`, `.tick(expected, observed) -> LedPlan`
  - `LedPlan(points: list[dict], caught_up: bool, to_place: set, to_remove: set)`；`points` 直接喂 `LedService.set_points`
  - 常量 `EMPTY, BLACK, WHITE = 0, 1, 2`；`STONE_LED_COLOR = {BLACK: "black", WHITE: "white"}`
  - 语义要点（评审后）：to_place = `expected!=空 ∧ observed==空`（目标点出现**任何**棋子检测灯即灭，防眩光；错色由 sync 异常流处理）；to_place 非空期间**不做** extras 防抖（用户抢下的子不得被蓝灯误导）

- [ ] **Step 1: 写失败测试（灯态 vs 对局状态转移表，PRD §11）**

```python
# tests/test_physical_play.py
"""LedPlanner: LED batch = f(expected digital board, observed physical board)."""
import numpy as np
import pytest

from katrain.web.core.physical_play import BLACK, EMPTY, WHITE, LedPlanner, PhysicalPlayConfig


def board(stones=()):
    b = np.zeros((19, 19), dtype=int)
    for r, c, v in stones:
        b[r][c] = v
    return b


@pytest.fixture
def planner():
    return LedPlanner(PhysicalPlayConfig(extra_stone_debounce_ticks=2))


class TestPlacementLamps:
    def test_ai_move_lights_stone_color_until_placed(self, planner):
        expected = board([(3, 3, BLACK)])          # AI(黑) 已在数字盘落子
        planner.on_expected(expected)
        plan = planner.tick(expected, board())     # 物理盘还没摆
        assert plan.points == [{"row": 3, "col": 3, "color": "black"}]  # 黑→红灯
        assert plan.caught_up is False
        plan = planner.tick(expected, expected)    # 用户替 AI 摆好
        assert plan.points == [] and plan.caught_up is True             # 灯灭

    def test_any_stone_on_target_extinguishes_lamp(self, planner):
        # 评审 E（眩光）：目标点一出现任何棋子检测，灯立即灭——即便颜色不对。
        # 错色子由 sync 异常流（Task 5 unexpected 分支）弹对话框，不用常亮灯引导。
        expected = board([(3, 3, WHITE)])
        planner.on_expected(expected)
        plan = planner.tick(expected, board([(3, 3, BLACK)]))  # 错色也算「有子」
        assert plan.points == []
        assert plan.caught_up is True

    def test_lamp_relights_when_detection_vanishes(self, planner):
        # 眩光误检消失 → 目标点重新读空 → 灯下一 tick 回亮
        expected = board([(3, 3, BLACK)])
        planner.on_expected(expected)
        assert planner.tick(expected, board([(3, 3, BLACK)])).points == []   # 检测到了（或眩光）
        plan = planner.tick(expected, board())                               # 检测消失
        assert plan.points == [{"row": 3, "col": 3, "color": "black"}]
        assert plan.caught_up is False

    def test_handicap_stones_all_lit(self, planner):
        expected = board([(3, 3, BLACK), (15, 15, BLACK)])
        planner.on_expected(expected)
        plan = planner.tick(expected, board())
        assert {(p["row"], p["col"]) for p in plan.points} == {(3, 3), (15, 15)}
        assert all(p["color"] == "black" for p in plan.points)


class TestRemovalLamps:
    def test_digital_capture_blue_until_physically_removed(self, planner):
        before = board([(5, 5, WHITE), (3, 3, BLACK)])
        after = board([(3, 3, BLACK)])              # 数字盘提掉 (5,5)
        planner.on_expected(before)
        planner.on_expected(after)
        plan = planner.tick(after, before)          # 物理盘白子还在
        assert {"row": 5, "col": 5, "color": "remove"} in plan.points
        assert plan.caught_up is False
        plan = planner.tick(after, after)           # 拿掉后
        assert plan.points == [] and plan.caught_up is True

    def test_undo_then_redo_cancels_removal(self, planner):
        b1 = board([(3, 3, BLACK)])
        planner.on_expected(b1)
        planner.on_expected(board())                # 悔棋：期望盘失去 (3,3) → 待提
        planner.on_expected(b1)                     # 重做：期望盘又有 → 取消待提
        plan = planner.tick(b1, b1)
        assert plan.points == [] and plan.caught_up is True


class TestExtraStones:
    def test_leftover_stone_debounces_to_blue(self, planner):
        empty = board()
        planner.on_expected(empty)
        extra = board([(9, 9, BLACK)])              # 开局残子
        plan = planner.tick(empty, extra)           # 第 1 tick：不点灯（防抖）
        assert plan.points == []
        plan = planner.tick(empty, extra)           # 第 2 tick（=debounce 阈值）：蓝灯
        assert plan.points == [{"row": 9, "col": 9, "color": "remove"}]
        assert plan.caught_up is True               # 残子不阻塞落子注入（Q4 门只看 place/remove-pending）

    def test_extras_not_flagged_while_placement_pending(self, planner):
        # Q4 重设计：AI 子未摆好（to_place 非空）期间，用户抢下的子绝不能被蓝灯
        # 误导为「请拿走」——extras 防抖在 to_place 非空时整体挂起、计数清零。
        expected = board([(3, 3, BLACK)])           # AI 落子待摆
        planner.on_expected(expected)
        premature = board([(9, 9, WHITE)])          # 用户抢下自己的一手（AI 子还没摆）
        for _ in range(5):
            plan = planner.tick(expected, premature)
        assert {"row": 9, "col": 9, "color": "remove"} not in plan.points
        assert plan.points == [{"row": 3, "col": 3, "color": "black"}]  # 只有 AI 落子灯


class TestMixedBatch:
    def test_ai_move_and_capture_one_batch(self, planner):
        before = board([(5, 5, WHITE)])
        after = board([(3, 3, BLACK)])              # AI 落子 + 提掉 (5,5)
        planner.on_expected(before)
        planner.on_expected(after)
        plan = planner.tick(after, before)
        assert {"row": 3, "col": 3, "color": "black"} in plan.points
        assert {"row": 5, "col": 5, "color": "remove"} in plan.points
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/test_physical_play.py -v`
Expected: FAIL——`ModuleNotFoundError: katrain.web.core.physical_play`

- [ ] **Step 3: 实现**

```python
# katrain/web/core/physical_play.py
"""Physical-play LED planning: pure diff between the authoritative digital board
and the observed physical board. No I/O, no clocks — fully unit-testable.

LED semantics (PRD D2): missing digital stone -> stone-color lamp (black stone ->
red LED "black", white -> green LED "white"); stone that must come off -> blue
("remove"). One set_points batch mixes colors (LedService batches are clear+set).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

EMPTY, BLACK, WHITE = 0, 1, 2
STONE_LED_COLOR = {BLACK: "black", WHITE: "white"}


@dataclass
class PhysicalPlayConfig:
    tick_interval_s: float = 0.5
    reminder_after_s: float = 30.0          # Q4: nag toast when board lags the game
    escalate_after_s: float = 120.0         # review B: escape-hatch dialog when still lagging
    led_reassert_interval_s: float = 240.0  # review A: re-send lamps before the 300s idle failsafe
    extra_stone_debounce_ticks: int = 6     # ~3s at default tick before an unexpected stone gets blue
    hint_top_n: int = 3                     # Q2 defaults
    hint_blink_period_s: float = 0.8
    hint_timeout_s: float = 30.0
    hint_max_visits: int = 100
    hint_engine: str = "local"              # "local" | "cloud" | "off"


@dataclass
class LedPlan:
    points: List[Dict]                      # ready for LedService.set_points(...)
    caught_up: bool                         # nothing left to place/remove (Q4 gate)
    to_place: Set[Tuple[int, int]] = field(default_factory=set)
    to_remove: Set[Tuple[int, int]] = field(default_factory=set)


class LedPlanner:
    """Tracks expected-board transitions and computes the LED batch each tick.

    Coordinates are vision-grid (row 0 = top), identical to the LED LUT convention.
    """

    def __init__(self, config: PhysicalPlayConfig):
        self.config = config
        self._prev_expected: Optional[np.ndarray] = None
        self._removal_pending: Set[Tuple[int, int]] = set()
        self._extra_counts: Dict[Tuple[int, int], int] = {}

    def reset(self) -> None:
        self._prev_expected = None
        self._removal_pending = set()
        self._extra_counts = {}

    def on_expected(self, expected: np.ndarray) -> None:
        """Record a new authoritative board. Stones that vanished from the digital
        board (captures, undo) become removal-pending; re-occupied points cancel."""
        if self._prev_expected is not None:
            gone = (self._prev_expected != EMPTY) & (expected == EMPTY)
            for r, c in zip(*np.nonzero(gone)):
                self._removal_pending.add((int(r), int(c)))
        self._removal_pending = {p for p in self._removal_pending if expected[p] == EMPTY}
        self._prev_expected = expected.copy()

    def tick(self, expected: np.ndarray, observed: np.ndarray) -> LedPlan:
        # A pending removal is done once the stone is physically gone.
        self._removal_pending = {p for p in self._removal_pending if observed[p] != EMPTY}

        # Placement guidance: digital stone on an EMPTY physical point. The lamp goes out
        # on the FIRST stone-class detection at the target (review E, glare safety): if
        # that detection was lamp glare and vanishes, the point reads empty again and the
        # lamp relights next tick. A wrong-color stone also extinguishes the lamp — the
        # sync anomaly flow (Task 5 'unexpected' bucket) surfaces it, not a standing lamp.
        to_place = {
            (int(r), int(c)) for r, c in zip(*np.nonzero((expected != EMPTY) & (observed == EMPTY)))
        }

        # Unexpected stones (never in the digital board) debounce into blue cleanup lamps
        # — covers leftover stones at game start. Suspended entirely while a placement is
        # pending (Q4 redesign): the user's premature stone must never get a 'remove' lamp
        # while they still owe the AI's stone.
        if to_place:
            self._extra_counts = {}
            debounced: Set[Tuple[int, int]] = set()
        else:
            extras = {
                (int(r), int(c)) for r, c in zip(*np.nonzero((expected == EMPTY) & (observed != EMPTY)))
            } - self._removal_pending
            self._extra_counts = {p: self._extra_counts.get(p, 0) + 1 for p in extras}
            debounced = {p for p, n in self._extra_counts.items() if n >= self.config.extra_stone_debounce_ticks}

        to_remove = self._removal_pending | debounced

        points = [
            {"row": r, "col": c, "color": STONE_LED_COLOR[int(expected[r][c])]} for r, c in sorted(to_place)
        ] + [{"row": r, "col": c, "color": "remove"} for r, c in sorted(to_remove)]

        # Debounced extras guide cleanup but don't block move injection (Q4 gate).
        caught_up = not to_place and not self._removal_pending
        return LedPlan(points=points, caught_up=caught_up, to_place=to_place, to_remove=to_remove)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `CI=true uv run pytest tests/test_physical_play.py -v`
Expected: 全 PASS。

- [ ] **Step 5: 格式化 + Commit**

```bash
uv run black -l 120 katrain/web/core/physical_play.py tests/test_physical_play.py
git add katrain/web/core/physical_play.py tests/test_physical_play.py
git commit -m "feat(web): LedPlanner pure core — LED batch as diff of digital vs observed board"
```

---

### Task 4: PhysicalPlayOrchestrator（async 壳）

**Files:**
- Create: `katrain/web/core/physical_play_orchestrator.py`
- Test: `tests/test_physical_play_orchestrator.py`（新）

**Interfaces:**
- Consumes: Task 3 全部；`VisionService.get_detected_board()`/`set_expected_from_stones()`；`LedService.set_points/set_rgb_points/clear`；`SessionManager.broadcast_to_session`；`game_state_stones_to_board`（vision/sync.py）
- Produces（Task 6/8 依赖，不得改名）:
  - `PhysicalPlayOrchestrator(config=, led=, vision=, session_manager=, touch_led_activity=, clock=)`
  - `.on_bind(session_id: str, session)`（同一 session 重复调用幂等，评审 M1）/ `.on_unbind()` / `.shutdown()`（async）
  - `.on_game_state(state: dict)`（线程安全：只赋值 + 推期望盘面）
  - `.board_caught_up -> bool`
  - `.show_hint(points: list[tuple[int,int]])` / `.dismiss_hint()`
  - 内部 `_tick_once()`（测试直接调，绕过 asyncio）
  - **暂停驱动（Q4 重设计）**：编排器是 worker 落子确认暂停态的唯一 owner——`_sync_pause_state()` 按 `hint_active or not caught_up` 计算期望态，变化时发 `vision.pause_detection()/resume_detection()`（hasattr 守卫至 Task 7 落地）
  - **灯态周期重申（评审 A）**：非空灯态每 `led_reassert_interval_s`(240s) 强制重发一次（写后盖活动戳），击穿 300s 失效保护窗口，并顺带从手动清灯/串口重连中恢复
  - 会话广播消息：`{"type": "physical_reminder", "data": {"kind": "reminder" | "escalation", "to_place": [[r,c]...], "to_remove": [[r,c]...]}}`（30s 一次 reminder，120s 一次 escalation，追平即复位）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_physical_play_orchestrator.py
"""Orchestrator: game state + observed board -> LED writes, catch-up gate, reminder."""
import asyncio
import time

import numpy as np
import pytest

from katrain.web.core.physical_play import PhysicalPlayConfig
from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator


class FakeLed:
    def __init__(self):
        self.calls = []

    def set_points(self, points, *, strict=False):
        self.calls.append(("set_points", points))
        return {"ok": True}

    def set_rgb_points(self, points, *, strict=False):
        self.calls.append(("set_rgb_points", points))
        return {"ok": True}

    def clear(self, *, strict=False):
        self.calls.append(("clear",))
        return {"ok": True}


class FakeVision:
    def __init__(self):
        self.detected = np.zeros((19, 19), dtype=int).tolist()
        self.expected_pushes = []
        self.paused = False
        self.lit = []

    def get_detected_board(self):
        return self.detected

    def set_expected_from_stones(self, stones, board_size=19):
        self.expected_pushes.append(stones)

    def pause_detection(self):
        self.paused = True

    def resume_detection(self):
        self.paused = False

    def set_lit_points(self, points):
        self.lit = points


class FakeManager:
    def __init__(self):
        self.broadcasts = []

    def broadcast_to_session(self, sid, payload):
        self.broadcasts.append((sid, payload))


def state(stones, end_result=None):
    return {"stones": stones, "board_size": [19, 19], "end_result": end_result}


def _orch(clock=lambda: 0.0, **cfg):
    led, vision, mgr = FakeLed(), FakeVision(), FakeManager()
    orch = PhysicalPlayOrchestrator(
        config=PhysicalPlayConfig(**cfg), led=led, vision=vision, session_manager=mgr,
        touch_led_activity=lambda: None, clock=clock,
    )
    orch._session_id = "s1"  # bypass on_bind (needs a running loop + real session)
    return orch, led, vision, mgr


class TestTick:
    def test_ai_stone_lights_then_clears_when_placed(self):
        orch, led, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]]))  # GTP y=15 -> row 3
        orch._tick_once()
        assert led.calls[-1] == ("set_points", [{"row": 3, "col": 3, "color": "black"}])
        assert orch.board_caught_up is False
        vision.detected[3][3] = 1                              # 用户替 AI 摆好
        orch._tick_once()
        assert led.calls[-1] == ("clear",)
        assert orch.board_caught_up is True

    def test_no_led_rewrite_when_plan_unchanged(self):
        orch, led, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()
        n = len(led.calls)
        orch._tick_once()
        assert len(led.calls) == n                             # 去重：不重复写串口

    def test_game_end_clears_lamps(self):
        orch, led, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]], end_result="W+R"))
        orch._tick_once()
        assert led.calls[-1] == ("clear",)

    def test_expected_pushed_to_vision_on_every_state(self):
        orch, _, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        assert len(vision.expected_pushes) == 1                # AI 落子后立即 force_sync 基线


class TestReminder:
    def test_reminder_then_escalation(self):
        now = [0.0]
        orch, _, vision, mgr = _orch(clock=lambda: now[0], reminder_after_s=30.0, escalate_after_s=120.0)
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()                                      # behind since t=0（首 tick 只记时，不广播）
        now[0] = 31.0
        orch._tick_once()
        assert [b[1]["data"]["kind"] for b in mgr.broadcasts] == ["reminder"]
        assert mgr.broadcasts[0][1]["data"]["to_place"] == [[3, 3]]
        now[0] = 121.0
        orch._tick_once()                                      # 评审 B 逃生舱：升级为对话框
        assert [b[1]["data"]["kind"] for b in mgr.broadcasts] == ["reminder", "escalation"]
        now[0] = 122.0
        orch._tick_once()
        assert len(mgr.broadcasts) == 2                        # 各档只发一次

    def test_counters_reset_when_caught_up(self):
        now = [0.0]
        orch, _, vision, mgr = _orch(clock=lambda: now[0])
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()
        vision.detected[3][3] = 1
        now[0] = 40.0
        orch._tick_once()                                      # 追平 → 计时器/已发标志复位
        assert mgr.broadcasts == []


class TestPauseDrive:
    """Q4 重设计：盘面未追平 → 暂停 worker 落子确认；追平 → 恢复（编排器唯一 owner）。"""

    def test_detection_paused_while_behind_resumed_when_caught_up(self):
        orch, _, vision, _ = _orch()
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()                                      # AI 子未摆 → 暂停确认
        assert vision.paused is True
        vision.detected[3][3] = 1
        orch._tick_once()                                      # 追平 → 恢复
        assert vision.paused is False


class TestLedReassert:
    """评审 A：非空灯态周期重申，击穿 300s 失效保护 + 从手动清灯恢复。"""

    def test_lamps_reasserted_before_idle_failsafe(self):
        now = [0.0]
        orch, led, vision, _ = _orch(clock=lambda: now[0], led_reassert_interval_s=240.0)
        orch.on_game_state(state([["B", [3, 15], None, 1]]))
        orch._tick_once()
        assert len([c for c in led.calls if c[0] == "set_points"]) == 1
        now[0] = 100.0
        orch._tick_once()                                      # 未到间隔：去重生效，不重发
        assert len([c for c in led.calls if c[0] == "set_points"]) == 1
        now[0] = 241.0
        orch._tick_once()                                      # 重申：同一批次再发（并盖活动戳）
        assert len([c for c in led.calls if c[0] == "set_points"]) == 2


class TestHint:
    def test_show_hint_suspends_and_blinks_then_restores(self):
        # 真实时钟：blink 的 deadline 用注入 clock 判定，固定 0.0 的假钟永不超时
        orch, led, vision, _ = _orch(clock=time.monotonic, hint_blink_period_s=0.02, hint_timeout_s=0.05)

        async def run():
            orch.show_hint([(3, 3), (15, 15)])
            assert vision.paused is True
            await asyncio.sleep(0.15)                          # 超时自然结束

        asyncio.run(run())
        assert vision.paused is False                          # 检测恢复
        rgb_calls = [c for c in led.calls if c[0] == "set_rgb_points"]
        assert rgb_calls and rgb_calls[0][1][0]["rgb"] == (255, 255, 255)

    def test_dismiss_hint_restores_immediately(self):
        orch, led, vision, _ = _orch(clock=time.monotonic, hint_blink_period_s=0.02, hint_timeout_s=10.0)

        async def run():
            orch.show_hint([(3, 3)])
            await asyncio.sleep(0.03)
            orch.dismiss_hint()
            assert vision.paused is False

        asyncio.run(run())
```

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/test_physical_play_orchestrator.py -v`
Expected: FAIL——ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# katrain/web/core/physical_play_orchestrator.py
"""PhysicalPlayOrchestrator — drives the physical LED board from authoritative game state.

Design (PRD R2 / feasibility §4.1):
- Backend-owned: LEDs are physical-device state; the frontend may refresh or disconnect.
- Reconciliation, not events: each tick diffs the digital board (latest game_update)
  against the observed board (vision) and writes the LED batch. One loop covers AI-move
  lamps, capture lamps, undo restore, handicap guidance and leftover-stone cleanup.
- Event-source abstraction (PRD R8.1 / Q5): the ONLY input is the game_update state dict.
  A remote opponent (phase 2) or a second human produces identical updates — zero changes.
- Threading: on_game_state may be called from the AI thread (wrapped update_state_callback).
  It only stores the dict and pushes the expected board (queue put, thread-safe). All
  planner mutations happen on the event loop inside _tick_once.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from katrain.vision.sync import game_state_stones_to_board
from katrain.web.core.physical_play import LedPlanner, PhysicalPlayConfig

logger = logging.getLogger("katrain_web.physical_play")


class PhysicalPlayOrchestrator:
    def __init__(
        self,
        *,
        config: PhysicalPlayConfig,
        led,  # LedService | None (None => plan/gate only, no serial writes)
        vision,  # VisionService
        session_manager,
        touch_led_activity: Callable[[], None] = lambda: None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.config = config
        self._led = led
        self._vision = vision
        self._manager = session_manager
        self._touch = touch_led_activity
        self._clock = clock

        self._planner = LedPlanner(config)
        self._session_id: Optional[str] = None
        self._session = None
        self._orig_callback = None
        self._latest_state: Optional[Dict] = None
        self._task: Optional[asyncio.Task] = None
        self._last_points: Optional[List[Dict]] = None
        self._caught_up = True
        self._suspended = False
        self._hint_active = False
        self._paused_sent: Optional[bool] = None  # last pause state sent to the worker
        self._hint_task: Optional[asyncio.Task] = None
        self._behind_since: Optional[float] = None
        self._reminded = False
        self._escalated = False
        self._last_assert_ts: Optional[float] = None  # last actual LED write (review A)

    # -- lifecycle -----------------------------------------------------------

    def on_bind(self, session_id: str, session) -> None:
        """Attach to a session: wrap its (single-slot) state callback, seed state,
        start the tick loop. Called from the vision bind endpoint (Task 6).
        Idempotent for the same session (the frontend double-binds today, review M1)."""
        if session_id == self._session_id and session is self._session:
            return
        self.on_unbind()
        self._session_id = session_id
        self._session = session
        self._planner.reset()
        self._orig_callback = session.katrain.update_state_callback
        orig = self._orig_callback

        def wrapped(state, _orig=orig):
            if _orig:
                _orig(state)
            self.on_game_state(state)

        session.katrain.update_state_callback = wrapped
        self.on_game_state(session.katrain.get_state())
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._run())

    def on_unbind(self) -> None:
        """Detach: restore callback, cancel hint, blank the lamps (R2.5)."""
        self.dismiss_hint()
        if self._session is not None:
            self._session.katrain.update_state_callback = self._orig_callback
        self._session = None
        self._session_id = None
        self._orig_callback = None
        self._latest_state = None
        self._caught_up = True
        self._behind_since = None
        self._reminded = False
        self._escalated = False
        self._sync_pause_state()  # resume detection if we had it paused
        self._apply_points([])

    async def shutdown(self) -> None:
        self.on_unbind()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # -- inputs ----------------------------------------------------------------

    def on_game_state(self, state: Dict) -> None:
        """Authoritative game_update. Pushing the expected board here re-baselines
        MoveDetector on EVERY digital change (AI move, undo, nav) — closing the gap
        where placing the AI's stone was itself detected as a new move."""
        if self._session_id is None:
            return
        self._latest_state = state
        try:
            self._vision.set_expected_from_stones(state["stones"], state["board_size"][0])
        except Exception as e:  # never break the broadcast chain
            logger.debug("expected-board push failed: %s", e)

    @property
    def board_caught_up(self) -> bool:
        """False while the physical board still owes a placement/removal (Q4 gate)."""
        return self._caught_up

    def _sync_pause_state(self) -> None:
        """Single owner of the worker's move-detection pause (Q4 redesign + hint).
        While paused, the worker produces NO ConfirmedMove — this replaces the unsound
        'hold a confirmed move' design (MoveDetector advances its baseline at confirm
        time, so held moves could go stale/corrupt — review Blocker 1). A premature
        user stone simply stays unconfirmed and is picked up naturally after resume,
        against the baseline force-synced by the expected-board push."""
        desired = self._hint_active or not self._caught_up
        if desired == self._paused_sent:
            return
        self._paused_sent = desired
        if hasattr(self._vision, "pause_detection"):  # lands in Task 7
            if desired:
                self._vision.pause_detection()
            else:
                self._vision.resume_detection()

    # -- tick loop ---------------------------------------------------------------

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.config.tick_interval_s)
                if self._session_id is None or self._suspended:
                    continue
                try:
                    self._tick_once()
                except Exception as e:  # defensive: LED problems must not kill the loop
                    logger.warning("physical-play tick error: %s", e)
        except asyncio.CancelledError:
            pass

    def _tick_once(self) -> None:
        state = self._latest_state
        if not state:
            return
        observed = self._vision.get_detected_board()
        if observed is None:
            return  # board not visible: keep current lamps (PRD §3.4 BOARD_LOST row)
        if state.get("end_result"):
            self._caught_up = True
            self._sync_pause_state()
            self._apply_points([])
            return
        board_size = state["board_size"][0]
        expected = np.asarray(game_state_stones_to_board(state["stones"], board_size))
        self._planner.on_expected(expected)
        plan = self._planner.tick(expected, np.asarray(observed))
        self._caught_up = plan.caught_up
        self._sync_pause_state()
        # Review A: periodically re-send a non-empty lamp state so the 300s LED idle
        # failsafe — and manual clears / serial reconnects — can't strand a dark lamp
        # while the plan is unchanged (the dedupe below would otherwise never re-send).
        if (
            self._last_points
            and self._last_assert_ts is not None
            and self._clock() - self._last_assert_ts > self.config.led_reassert_interval_s
        ):
            self._last_points = None
        self._apply_points(plan.points)
        self._maybe_remind(plan)

    def _apply_points(self, points: List[Dict]) -> None:
        if points == self._last_points:
            return
        self._last_points = points
        if self._led is not None:
            if points:
                self._led.set_points(points, strict=False)
            else:
                self._led.clear(strict=False)
            self._touch()
            self._last_assert_ts = self._clock()
        # R7.1: tell vision which intersections are lit so lamp glare on empty points
        # can't be misread as stones (VisionService method lands in Task 7 — guarded).
        if hasattr(self._vision, "set_lit_points"):
            self._vision.set_lit_points([(p["row"], p["col"]) for p in points])

    def _maybe_remind(self, plan) -> None:
        """Two escalation tiers (review B escape hatch): a gentle toast at
        reminder_after_s, then a blocking dialog at escalate_after_s offering
        retry / restored / switch-to-screen-play. Each fires once per lag episode."""
        if plan.caught_up:
            self._behind_since = None
            self._reminded = False
            self._escalated = False
            return
        now = self._clock()
        if self._behind_since is None:
            self._behind_since = now
            return
        behind_for = now - self._behind_since
        kind = None
        if not self._escalated and behind_for > self.config.escalate_after_s:
            self._escalated = True
            kind = "escalation"
        elif not self._reminded and behind_for > self.config.reminder_after_s:
            self._reminded = True
            kind = "reminder"
        if kind:
            self._manager.broadcast_to_session(
                self._session_id,
                {
                    "type": "physical_reminder",
                    "data": {
                        "kind": kind,
                        "to_place": [list(p) for p in sorted(plan.to_place)],
                        "to_remove": [list(p) for p in sorted(plan.to_remove)],
                    },
                },
            )

    # -- hint (Task 8 wires the endpoint) ----------------------------------------

    def show_hint(self, points: List[Tuple[int, int]]) -> None:
        """Blink white lamps on the top-N points. Suspends reconciliation AND move
        detection (R4.3) for the duration; auto-restores on timeout or dismiss."""
        self.dismiss_hint()
        self._suspended = True
        self._hint_active = True
        self._sync_pause_state()
        if hasattr(self._vision, "set_lit_points"):
            self._vision.set_lit_points(list(points))
        self._hint_task = asyncio.get_running_loop().create_task(self._blink(points))

    def dismiss_hint(self) -> None:
        if self._hint_task is not None and not self._hint_task.done():
            self._hint_task.cancel()
        self._hint_task = None
        self._end_hint()

    def _end_hint(self) -> None:
        if not self._suspended:
            return
        self._suspended = False
        self._hint_active = False
        self._sync_pause_state()  # stays paused if the board is still lagging
        self._last_points = None  # force the game lamp state to re-send next tick

    async def _blink(self, points: List[Tuple[int, int]]) -> None:
        half = self.config.hint_blink_period_s / 2
        deadline = self._clock() + self.config.hint_timeout_s
        on = True
        try:
            while self._clock() < deadline:
                if self._led is not None:
                    if on:
                        self._led.set_rgb_points(
                            [{"row": r, "col": c, "rgb": (255, 255, 255)} for r, c in points], strict=False
                        )
                    else:
                        self._led.clear(strict=False)
                    self._touch()
                on = not on
                await asyncio.sleep(half)
        except asyncio.CancelledError:
            raise
        finally:
            self._end_hint()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `CI=true uv run pytest tests/test_physical_play_orchestrator.py tests/test_physical_play.py -v`
Expected: 全 PASS。

- [ ] **Step 5: 格式化 + Commit**

```bash
uv run black -l 120 katrain/web/core/physical_play_orchestrator.py tests/test_physical_play_orchestrator.py
git add katrain/web/core/physical_play_orchestrator.py tests/test_physical_play_orchestrator.py
git commit -m "feat(web): PhysicalPlayOrchestrator — reconciliation loop driving game LEDs"
```

---

### Task 5: sync.py 数字权威升级（prev-expected 快照 + diff 重分类）

**背景**：编排器现在每次 `game_update` 都推期望盘面（Task 4），旧分类会把「AI 刚落、用户未摆」判成 capture_pending、把「数字侧提子待拿除」判成 illegal_change。本任务改为**四分类**（2026-07-02 评审 Codex Blocker 2 修正版）：
1. `exp≠空 ∧ obs==空 ∧ prev==空` → **待摆放**（AI 落子/重做，非异常，无事件——编排器灯引导）；
2. `exp≠空 ∧ obs==空 ∧ prev≠空` → **missing 异常**（活子被误拿走，或用户提子先于注入的短暂态）→ 进 mismatch 防抖流、列入 `missing`。**不得**走 CAPTURE_PENDING（旧方案会秒清除吞掉真异常）；
3. `exp==空 ∧ obs≠空 ∧ prev==obs` → **待拿除**（数字侧提子/悔棋 → CAPTURE_PENDING sticky 流，前端 CaptureGuide 复用；这些点 observed 必然有子，`still_pending` 检查语义正确）；
4. 其余（含错色）→ **unexpected 异常** → mismatch 防抖流。

用户提子先于注入的短暂态走 2（防抖 5 帧 > 注入 3 帧，注入后 expected 更新即自愈，不弹框）——旧代码在此场景发瞬时 CAPTURE_PENDING+CLEARED，新行为更安静，需在提交信息注明语义变更。

**关于「漏推 expected」的健壮性（评审 Gemini C 驳回记录）**：`update_state_callback` 250ms 节流是**合并到最新态**，`prev` = 上次成功推送的期望盘。漏推/合并只会让更多点满足 `prev==空` 落入「待摆放」安全桶；分类 3 要求 `prev==observed` 精确成立，陈旧 prev 无法伪造它。故不需要序号/哈希机制（YAGNI），在 `set_expected_board` docstring 写明该不变式即可。

**Files:**
- Modify: `katrain/vision/sync.py`（`__init__`、`set_expected_board`、`reset`、`_compare_boards`）
- Test: `tests/test_vision/test_sync.py`（追加测试类）

**Interfaces:**
- Produces: `ILLEGAL_CHANGE` 事件 `data={"positions": [(r,c,clr)...], "missing": [(r,c,clr)...]}`（positions=多余/错色，missing=**missing 异常 + 待摆放**——恢复对话框的完整「请摆上」清单）；数字提子走 `CAPTURE_PENDING`/`CAPTURES_CLEARED`（前端已渲染）；纯待摆放差异不再产生 mismatch 状态；活子被误拿走 → mismatch 流（不再是秒清除的 capture）

- [ ] **Step 1: 追加失败测试**（`tests/test_vision/test_sync.py` 末尾追加；沿用该文件现有 `empty_board`/`board_with` helper 与 import 面）

```python
class TestDigitalAuthorityDiff:
    """After the orchestrator pushes expected on every game_update (digital authority)."""

    def _synced_machine(self, expected):
        sm = SyncStateMachine()
        sm.bind()
        sm.confirm_pose_lock()
        sm.set_expected_board(expected)
        return sm

    def test_newly_expected_stone_is_placement_pending_not_capture(self):
        sm = self._synced_machine(empty_board())
        with_ai = board_with({(3, 3): 1})
        sm.set_expected_board(with_ai)              # AI 数字落子
        events = sm.update(observed_board=empty_board())  # 用户还没摆
        types = [e.type for e in events]
        assert SyncEventType.CAPTURE_PENDING not in types
        assert SyncEventType.ILLEGAL_CHANGE not in types
        assert sm.state == SyncState.SYNCED         # 待摆放不是异常

    def test_digital_capture_emits_capture_pending_until_removed(self):
        before = board_with({(5, 5): 2, (3, 3): 1})
        sm = self._synced_machine(before)
        sm.update(observed_board=before)
        after = board_with({(3, 3): 1})              # 数字盘提掉 (5,5)
        sm.set_expected_board(after)
        events = sm.update(observed_board=before)    # 物理盘白子还在
        pend = [e for e in events if e.type == SyncEventType.CAPTURE_PENDING]
        assert pend and (5, 5, 2) in [tuple(p) for p in pend[0].data["positions"]]
        events = sm.update(observed_board=after)     # 拿掉
        assert SyncEventType.CAPTURES_CLEARED in [e.type for e in events]

    def test_truly_unexpected_stone_still_illegal_change_with_missing(self):
        # 场景刻意不含「待拿除」差异（removal 会先走 sticky CAPTURE_PENDING 分支）：
        # 期望新增 (9,9) 白（待摆放），观测却在 (15,15) 乱放一子。
        sm = self._synced_machine(empty_board())
        sm.set_expected_board(board_with({(9, 9): 2}))
        bad = board_with({(15, 15): 1})
        events = []
        for _ in range(5):                           # illegal_change_frames 默认 5
            events = sm.update(observed_board=bad)
        illegal = [e for e in events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert illegal
        assert (15, 15, 1) in [tuple(p) for p in illegal[0].data["positions"]]
        # missing = 待摆放清单（供恢复对话框），且它自己不构成异常
        assert (9, 9, 2) in [tuple(p) for p in illegal[0].data["missing"]]

    def test_stolen_live_stone_is_anomaly_not_capture(self):
        # 评审 Codex Blocker 2 回归：盘上活子被误拿走（数字盘没提它）——绝不能走
        # CAPTURE_PENDING→秒清除把异常吞掉；必须进 mismatch 防抖流并列入 missing。
        live = board_with({(3, 3): 1, (5, 5): 2})
        sm = self._synced_machine(live)
        sm.update(observed_board=live)
        sm.set_expected_board(live)                  # prev = live（无数字侧变化）
        gone = board_with({(3, 3): 1})               # (5,5) 白子被拿走
        all_events = []
        for _ in range(5):                           # illegal_change_frames 默认 5
            all_events += sm.update(observed_board=gone)
        types = [e.type for e in all_events]
        assert SyncEventType.CAPTURE_PENDING not in types
        illegal = [e for e in all_events if e.type == SyncEventType.ILLEGAL_CHANGE]
        assert illegal
        assert (5, 5, 2) in [tuple(p) for p in illegal[0].data["missing"]]
```

（若现有 helper 名不同，以 `tests/test_vision/test_sync.py` 顶部实际定义为准改名；board_with 的 value 1=BLACK, 2=WHITE。）

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/test_vision/test_sync.py -v -k DigitalAuthority`
Expected: 3 条 FAIL（capture_pending 误报 / illegal_change 无 missing key）。

- [ ] **Step 3: 实现**

`katrain/vision/sync.py`：

1. `__init__`（构造函数体末尾）追加：
```python
        self._prev_expected_board: np.ndarray | None = None
```
2. `set_expected_board`（sync.py:119 附近；保留现有函数已有的其他行为，若有）改为先快照再覆盖：
```python
    def set_expected_board(self, board: np.ndarray) -> None:
        """Update expected board; keep the previous one so _compare_boards can tell
        'digital stone awaiting placement' from 'stone that must come off'."""
        if self._expected_board is not None:
            self._prev_expected_board = self._expected_board.copy()
        self._expected_board = board.copy()
```
3. `reset()` 方法体内追加一行（接受当前物理盘为新基线时，历史失效）：
```python
        self._prev_expected_board = None
```
4. `_compare_boards` 中 **4b 分类段**（`captures`/`unexpected` 两个列表的构建循环，sync.py:282-298）整体替换为：
```python
        # 4b. Classify against the previous expected board (digital authority).
        #     Newly-expected stone the player hasn't placed yet is NOT an anomaly;
        #     a live stone that vanished physically IS one (review Codex B2) — it must
        #     ride the debounced mismatch flow, never the instantly-self-clearing
        #     capture flow. removal_needed only holds points where a stone is still
        #     physically present, so the sticky still_pending check stays meaningful.
        prev = self._prev_expected_board
        removal_needed: list[tuple[int, int, int]] = []   # physical stone must come OFF
        placement_pending: list[tuple[int, int, int]] = []  # digital stone awaiting placement
        missing_anomaly: list[tuple[int, int, int]] = []  # live stone vanished physically
        unexpected: list[tuple[int, int, int]] = []

        for r, c in diff_positions:
            expected_val = int(self._expected_board[r, c])
            observed_val = int(observed_board[r, c])
            if expected_val != EMPTY and observed_val == EMPTY:
                if prev is not None and int(prev[r, c]) == EMPTY:
                    placement_pending.append((r, c, expected_val))   # e.g. AI move lamp lit
                else:
                    missing_anomaly.append((r, c, expected_val))     # stolen live stone (or pre-injection capture transient)
            elif expected_val == EMPTY and observed_val != EMPTY:
                if prev is not None and int(prev[r, c]) == observed_val:
                    removal_needed.append((r, c, observed_val))      # digital capture/undo pending removal
                else:
                    unexpected.append((r, c, observed_val))
            elif expected_val != EMPTY and observed_val != EMPTY and expected_val != observed_val:
                unexpected.append((r, c, observed_val))
```
5. 紧随其后的 **4c capture 段**：把两处 `captures` 改名 `removal_needed`（`if captures and ...` → `if removal_needed and ...`；`self._pending_captures = captures` → `= removal_needed`），其余 sticky 逻辑不动（removal_needed 各点 observed 必然有子，`still_pending` 的 `observed != EMPTY` 检查语义正确）。
6. **4d mismatch 段**：异常触发集从 `unexpected` 扩为 `unexpected ∪ missing_anomaly`；稳定性指纹须编码两类（missing 用 `clr + 2` 区分值域，避免与 unexpected 同点同值误判稳定）；illegal_change 的 `data=` 改为：
```python
        # 4d. Anomaly tracking: unexpected extras AND missing live stones both count.
        if unexpected or missing_anomaly:
            current_mismatch = np.zeros_like(self._expected_board)
            for r, c, clr in unexpected:
                current_mismatch[r, c] = clr
            for r, c, clr in missing_anomaly:
                current_mismatch[r, c] = clr + 2   # distinct fingerprint values (3/4)
            # …（原有 _mismatch_board/_mismatch_count 稳定计数逻辑不变）…
            if self._mismatch_count >= self._illegal_change_frames:
                self._state = SyncState.MISMATCH_WARNING
                events.append(
                    SyncEvent(
                        SyncEventType.ILLEGAL_CHANGE,
                        data={
                            "positions": [(r, c, clr) for r, c, clr in unexpected],
                            "missing": [(r, c, clr) for r, c, clr in missing_anomaly + placement_pending],
                        },
                    )
                )
                self._mismatch_board = None
                self._mismatch_count = 0
```
（`missing` = missing 异常 + 待摆放，给恢复对话框完整的「请摆上」清单；但**触发**只看 unexpected/missing_anomaly——纯待摆放永不弹框。）

- [ ] **Step 4: 跑 sync 全量 + vision 回归**

Run: `CI=true uv run pytest tests/test_vision/ -v`
Expected: 新增 3 条 PASS；既有 test_sync.py 用例全 PASS（若有用例断言旧的「expected-有-observed-无 ⇒ capture_pending」且其场景没有 prev 快照——`prev is None` 时行为与旧版一致，应不破；如个别用例显式构造了两次 set_expected_board 而期望旧语义，改断言并在提交信息说明语义变更）。

- [ ] **Step 5: Commit**

```bash
uv run black -l 120 katrain/vision/sync.py tests/test_vision/test_sync.py
git add katrain/vision/sync.py tests/test_vision/test_sync.py
git commit -m "feat(vision): digital-authority sync diff — placement-pending vs removal vs anomaly"
```

---

### Task 6: 服务端接线（lifespan 装配 + bind/unbind 挂钩 + poller 加固）

**Files:**
- Modify: `katrain/web/server.py`（lifespan ~430 行区、shutdown ~47-53、`_vision_move_poller` 1810-1861、CLI args ~1949/2001）
- Modify: `katrain/web/api/v1/endpoints/vision.py`（bind/unbind）
- Test: `tests/test_vision_bind_state.py`（追加）

**Interfaces:**
- Consumes: Task 4 编排器全部公共方法
- Produces: `app.state.physical_play`（编排器 | None）、`app.state.physical_play_config`；CLI `--hint-engine {local,cloud,off}`、`--hint-top-n N`

- [ ] **Step 1: 追加失败测试（bind 挂钩编排器）**

`tests/test_vision_bind_state.py` 追加：

```python
class FakeOrchestrator:
    def __init__(self):
        self.bound = None
        self.unbound = False

    def on_bind(self, session_id, session):
        self.bound = session_id

    def on_unbind(self):
        self.unbound = True


class TestOrchestratorHooks:
    def test_bind_and_unbind_notify_orchestrator(self):
        fake_vision, orch = FakeVision(), FakeOrchestrator()
        c = _client(fake_vision, FakeManager())
        c.app.state.physical_play = orch
        assert c.post("/vision/bind", json={"session_id": "s1"}).status_code == 200
        assert orch.bound == "s1"
        assert c.post("/vision/unbind").status_code == 200
        assert orch.unbound is True
```

Run: `CI=true uv run pytest tests/test_vision_bind_state.py -v` → 新增用例 FAIL。

- [ ] **Step 2: bind/unbind 端点挂钩**

`katrain/web/api/v1/endpoints/vision.py` 的 `bind_session`，在 `return {"ok": True, ...}` 前插入：

```python
    orchestrator = getattr(request.app.state, "physical_play", None)
    if orchestrator is not None:
        orchestrator.on_bind(body.session_id, session)
```

`unbind_session`，在 `vision.unbind_session()` 前插入：

```python
    orchestrator = getattr(request.app.state, "physical_play", None)
    if orchestrator is not None:
        orchestrator.on_unbind()
```

Run: `CI=true uv run pytest tests/test_vision_bind_state.py -v` → 全 PASS。

- [ ] **Step 3: lifespan 装配 + shutdown**

`katrain/web/server.py` board 模式 lifespan，**LED service 块之后**（`app.state.led = None` 的 else 之后、capture 块之前）插入：

```python
    # Physical-play orchestrator: drives game LEDs from authoritative state
    # (track kiosk-physical-play; requires vision, LED optional/degraded-tolerant)
    if app.state.vision is not None:
        from katrain.web.core.physical_play import PhysicalPlayConfig
        from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator

        pp_config = getattr(settings, "_physical_play_config", None) or PhysicalPlayConfig()
        app.state.physical_play_config = pp_config
        app.state.physical_play = PhysicalPlayOrchestrator(
            config=pp_config,
            led=app.state.led,
            vision=app.state.vision,
            session_manager=manager,
            touch_led_activity=lambda: setattr(app.state, "led_last_activity", time.monotonic()),
        )
        log.info("Physical-play orchestrator ready (hint_engine=%s)", pp_config.hint_engine)
    else:
        app.state.physical_play = None
        app.state.physical_play_config = None
```

shutdown 段（`led.stop()` 附近，server.py:47-53 区域）追加（放在 led.stop() 之前）：

```python
    physical_play = getattr(app.state, "physical_play", None)
    if physical_play:
        await physical_play.shutdown()
```

- [ ] **Step 4: CLI 参数（沿用 `_led_config` 注入惯例）**

argparse 块（~server.py:1949，`--led-lut-path` 之后）：

```python
    parser.add_argument("--hint-engine", choices=["local", "cloud", "off"], default=None,
                        help="AI hint engine routing for physical play (default: local)")
    parser.add_argument("--hint-top-n", type=int, default=None, help="AI hint top-N points (default: 3)")
```

配置注入（~server.py:2001，`_led_config` 注入之后）：

```python
    if args.hint_engine is not None or args.hint_top_n is not None:
        from katrain.web.core.physical_play import PhysicalPlayConfig

        settings._physical_play_config = PhysicalPlayConfig(
            hint_engine=args.hint_engine or "local",
            hint_top_n=args.hint_top_n or 3,
        )
```

- [ ] **Step 5: 加固 `_vision_move_poller`（回合色校验 + session.lock；Q4 阻塞在 worker 侧，poller 不持有）**

**设计注（评审 Codex Blocker 1）**：曾考虑让 poller「持有」已确认落子等待追平——不可行：`MoveDetector` 在确认瞬间推进基线（`prev_board = board.copy()`，move_detector.py:53-56），持有期间用户再摆 AI 子会产生**第二个陈旧 ConfirmedMove**，极端情形（held 一手恰好提掉 AI 刚落的子使该点变空）会注入真实错着。Q4 阻塞改由编排器暂停 worker 落子确认实现（Task 4 `_sync_pause_state` + Task 7 `PAUSE_DETECTION`）：暂停期间根本不产生确认，恢复后抢下的子相对 force_sync 基线自然确认，顺序正确、无陈旧事件。poller 因此**无需任何持有逻辑**。

`katrain/web/server.py:1810-1861` 整函数替换：

```python
async def _vision_move_poller(app: FastAPI):
    """Poll vision worker for confirmed moves and inject them into the bound session.

    Q4 blocking happens WORKER-SIDE: while the physical board owes a placement or
    removal, the orchestrator pauses move detection, so no ConfirmedMove is produced
    at all. Holding confirmed moves here was rejected — MoveDetector advances its
    baseline at confirm time, so held moves can go stale and corrupt the game.
    Expected-board pushes now happen in the orchestrator's update_state_callback
    wrapper (single authority); a fallback remains for vision-without-orchestrator.
    """
    from katrain.vision.ipc import ConfirmedMove
    from katrain.vision.katrain_bridge import vision_move_to_katrain

    log = logging.getLogger("katrain_web.vision")
    while True:
        try:
            vision = getattr(app.state, "vision", None)
            if vision and vision.bound_session_id:
                orchestrator = getattr(app.state, "physical_play", None)
                move_data = vision.get_confirmed_move()
                if move_data and isinstance(move_data, ConfirmedMove):
                    session_id = vision.bound_session_id
                    manager = app.state.session_manager
                    session = manager.get_session(session_id)
                    if session:
                        # R1.3: only the side to move may inject (color check).
                        expected_player = (session.last_state or {}).get("player_to_move")
                        move_player = "B" if move_data.color == 1 else "W"
                        if expected_player and move_player != expected_player:
                            log.info("Vision move %s out of turn (expects %s) — ignored",
                                     move_player, expected_player)
                            await asyncio.sleep(0.1)
                            continue
                        move = vision_move_to_katrain(move_data.col, move_data.row, move_data.color, board_size=19)
                        gateway = getattr(app.state, "platform_gateway", None)
                        if gateway and gateway.is_platform_game(session_id):
                            try:
                                await gateway.play_move(session_id, move.coords[0], move.coords[1], user_id=0)
                            except Exception as gw_err:
                                log.warning("Platform gateway rejected vision move: %s", gw_err)
                                await asyncio.sleep(0.5)
                                continue
                        else:
                            with session.lock:
                                session.katrain("play", move.coords)
                        log.info("Vision move submitted: col=%d row=%d color=%d",
                                 move_data.col, move_data.row, move_data.color)
                        if orchestrator is None:
                            game_state = session.katrain.get_state()
                            if game_state and "stones" in game_state:
                                vision.set_expected_from_stones(game_state["stones"])
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("Vision move poller error: %s", e)
        await asyncio.sleep(0.1)
```

- [ ] **Step 6: 手动冒烟（Mac 无硬件路径）+ 回归**

Run: `CI=true uv run pytest tests/ -x -q 2>&1 | tail -5`（相对基线无新增失败）
Run: `timeout 20 python -m katrain --ui web --port 8003 2>&1 | head -30`
Expected: server 模式正常启动（无 vision → `app.state.physical_play = None` 分支不炸）。

- [ ] **Step 7: Commit**

```bash
uv run black -l 120 katrain/web/server.py katrain/web/api/v1/endpoints/vision.py
git add katrain/web/server.py katrain/web/api/v1/endpoints/vision.py tests/test_vision_bind_state.py
git commit -m "feat(web): wire PhysicalPlayOrchestrator — lifespan, bind hooks, hardened poller"
```

---

### Task 7: vision worker — pause/resume、亮灯点遮蔽、move_pending / ambiguous_stone 事件

**Files:**
- Modify: `katrain/vision/ipc.py`（CommandType）
- Modify: `katrain/vision/service.py`（三个新方法）
- Modify: `katrain/vision/board_state.py`（`masked_cells` 参数 + `cell_confidences`）
- Modify: `katrain/vision/worker.py` 与 `katrain/vision/worker_inprocess.py`（**两处都要**）
- Test: `tests/test_vision/test_board_state_masking.py`（新）、`tests/test_vision/test_worker_commands.py`（新）

**Interfaces:**
- Produces:
  - `CommandType.PAUSE_DETECTION / RESUME_DETECTION / SET_LIT_POINTS`
  - `VisionService.pause_detection()` / `.resume_detection()` / `.set_lit_points(points: list[tuple[int,int]])`
  - **PAUSE 语义（评审后收窄）**：只暂停 **MoveDetector 落子确认**块；`SyncStateMachine.update` 照常运行——追平等待期间 capture_pending/illegal_change 流必须继续工作（引导拿提子、报异常）；hint 白灯期间 sync 由亮灯点遮蔽保护（lit ∧ expected-empty 的检测被丢弃 → observed 不变 → sync 安静）。`BIND` 命令防御性重置 `self._paused = False`（避免上局残留）。
  - `BoardStateExtractor.detections_to_board(..., masked_cells: set[tuple[int,int]] | None = None)`；`.cell_confidences(detections, img_w, img_h) -> dict[(r,c), float]`
  - `/ws/vision` 新事件：`{"type": "move_pending", "data": {"row", "col", "color"}}`、`{"type": "ambiguous_stone", "data": {"row", "col", "color", "confidence"}}`（前端 Task 10/11 消费）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_vision/test_board_state_masking.py
"""masked_cells drops detections landing on lit-and-expected-empty intersections (R7.1)."""
import numpy as np

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.stone_detector import Detection


def _det(cx, cy, class_id=1, conf=0.9):
    return Detection(class_id=class_id, confidence=conf, x_center=cx, y_center=cy, width=20, height=20)


class TestMasking:
    def test_masked_cell_detection_dropped(self):
        ex = BoardStateExtractor()
        # 用 extractor 自己的坐标系造一个落在 (row 0, col 0) 的检测：
        # 先不加 mask 确认它落在哪个格，再对该格做 mask 断言消失。
        img_w = img_h = 800
        d = _det(30, 30)
        base = ex.detections_to_board([d], img_w, img_h, occupancy_aware=True)
        cells = list(zip(*np.nonzero(base)))
        assert len(cells) == 1
        cell = (int(cells[0][0]), int(cells[0][1]))
        masked = ex.detections_to_board([d], img_w, img_h, occupancy_aware=True, masked_cells={cell})
        assert masked.sum() == 0

    def test_unmasked_cells_unaffected(self):
        ex = BoardStateExtractor()
        d = _det(30, 30)
        out = ex.detections_to_board([d], 800, 800, occupancy_aware=True, masked_cells={(18, 18)})
        assert out.sum() > 0

    def test_cell_confidences_maps_max_conf(self):
        ex = BoardStateExtractor()
        d = _det(30, 30, conf=0.42)
        conf = ex.cell_confidences([d], 800, 800)
        assert len(conf) == 1 and abs(list(conf.values())[0] - 0.42) < 1e-9
```

（`Detection` 构造字段以 `katrain/vision/stone_detector.py` 的 dataclass 为准，字段名不同则改 `_det`。）

```python
# tests/test_vision/test_worker_commands.py
"""PAUSE/RESUME/SET_LIT_POINTS must be handled by BOTH dispatchers (SET_GEOMETRY 前车之鉴)."""
import queue

import pytest

from katrain.vision.ipc import CommandType, WorkerCommand


def _drain_with(worker_obj):
    worker_obj._cmd_queue.put(WorkerCommand(action=CommandType.PAUSE_DETECTION))
    worker_obj._drain_or_process()
    assert worker_obj._paused is True
    worker_obj._cmd_queue.put(WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[3, 3], [5, 5]]}))
    worker_obj._drain_or_process()
    assert worker_obj._lit_points == {(3, 3), (5, 5)}
    worker_obj._cmd_queue.put(WorkerCommand(action=CommandType.RESUME_DETECTION))
    worker_obj._drain_or_process()
    assert worker_obj._paused is False


class TestInProcessDispatcher:
    def test_pause_lit_resume(self):
        from katrain.vision.worker_inprocess import InProcessAdapter

        w = InProcessAdapter({"board_size": 19}, camera=None)
        w._drain_or_process = w._drain_commands
        _drain_with(w)


class TestSubprocessDispatcher:
    def test_pause_lit_resume(self):
        from katrain.vision.worker import VisionWorker

        w = VisionWorker.__new__(VisionWorker)  # 跳过重 __init__（相机/模型），只测分发器
        w._cmd_queue = queue.Queue()
        w._paused = False
        w._lit_points = set()
        w._running = True
        w._drain_or_process = w._process_commands
        _drain_with(w)
```

（`InProcessAdapter` 构造参数以实际签名为准（`worker_inprocess.py`，config dict + camera）；`VisionWorker.__new__` 技巧绕过相机初始化，只喂分发器所需属性——若 `_process_commands` 引用其他 self 属性（如 `self._sync`），在测试里补 `w._sync = SyncStateMachine()` 等最小属性。）

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/test_vision/test_board_state_masking.py tests/test_vision/test_worker_commands.py -v`
Expected: FAIL——`detections_to_board() got an unexpected keyword argument 'masked_cells'`；`AttributeError: PAUSE_DETECTION`。

- [ ] **Step 3: ipc.py 加命令**

`CommandType` 枚举（`SET_GEOMETRY` 之后、`SHUTDOWN` 之前）追加：

```python
    PAUSE_DETECTION = "pause_detection"
    RESUME_DETECTION = "resume_detection"
    SET_LIT_POINTS = "set_lit_points"
```

- [ ] **Step 4: board_state.py**

`detections_to_board` 签名加参 `masked_cells: set | None = None`，转发给两条路径：
- legacy 循环里 `pos_x, pos_y = physical_to_grid(...)` 之后加：
```python
            if masked_cells and (pos_y, pos_x) in masked_cells:
                continue  # lit-and-expected-empty intersection: presume LED glare, not a stone
```
- `_assign_occupancy_aware` 加同名参数并在 `cy, cx` 计算后（`if board[cy][cx] == EMPTY` 之前）加：
```python
            if masked_cells and (cy, cx) in masked_cells:
                continue
```
（`detections_to_board` 调 `self._assign_occupancy_aware(board, detections, img_w, img_h, masked_cells)`。）

类末尾新增方法：

```python
    def cell_confidences(self, detections: list[Detection], img_w: int, img_h: int) -> dict:
        """Max detection confidence per rounded intersection — used to classify a
        pending move as confirmed vs ambiguous (PRD §3.4 ambiguous_stone)."""
        out: dict[tuple[int, int], float] = {}
        for det in detections:
            if det.class_id not in STONE_CLASS_IDS:
                continue
            x_mm, y_mm = pixel_to_physical(det.x_center, det.y_center, img_w, img_h, self.config)
            pos_x, pos_y = physical_to_grid(x_mm, y_mm, self.config)
            key = (pos_y, pos_x)
            out[key] = max(out.get(key, 0.0), det.confidence)
        return out
```

- [ ] **Step 5: 两个 worker 分发器 + 检测门控 + 事件发射（改动完全对称）**

**5a `worker_inprocess.py`**：
- `__init__`（`self._sync = SyncStateMachine()` 附近）追加：
```python
        self._paused = False
        self._lit_points: set[tuple[int, int]] = set()
        self._expected_np: np.ndarray | None = None
        self._ambiguous_confidence = self._config.get("ambiguous_confidence", 0.55)
```
- `_drain_commands` 的 `SET_EXPECTED_BOARD` 分支追加一行 `self._expected_np = board`；`BIND` 分支追加一行 `self._paused = False`（防上局残留）；末尾追加三个分支：
```python
            elif cmd.action == CommandType.PAUSE_DETECTION:
                self._paused = True
            elif cmd.action == CommandType.RESUME_DETECTION:
                self._paused = False
            elif cmd.action == CommandType.SET_LIT_POINTS:
                self._lit_points = {tuple(p) for p in cmd.data.get("points", [])}
```
- `_loop` 中 `detections_to_board` 调用（`worker_inprocess.py:163` 附近）替换为：
```python
                    masked = None
                    if self._lit_points:
                        exp = self._expected_np
                        masked = {p for p in self._lit_points if exp is None or int(exp[p[0]][p[1]]) == 0}
                    observed_board = self._active_extractor().detections_to_board(
                        detections, img_w=w, img_h=h, occupancy_aware=True, masked_cells=masked
                    )
```
- MoveDetector 块（`worker_inprocess.py:171-175`）替换为：
```python
                    if self._bound and not self._paused:
                        conf_map = self._active_extractor().cell_confidences(detections, img_w=w, img_h=h)
                        pending_before = self._move_detector.pending_move
                        move_result = self._move_detector.detect_new_move(observed_board)
                        if move_result is not None:
                            row, col, color = move_result
                            conf = conf_map.get((row, col), 1.0)
                            if conf < self._ambiguous_confidence:
                                # PRD §3.4 row 1: low-confidence "move" asks the user instead
                                self._event_queue.put({
                                    "type": "ambiguous_stone",
                                    "data": {"row": int(row), "col": int(col), "color": int(color),
                                             "confidence": round(float(conf), 3)},
                                })
                            else:
                                self._event_queue.put(ConfirmedMove(col=col, row=row, color=color))
                        else:
                            pending_after = self._move_detector.pending_move
                            if pending_after is not None and pending_after != pending_before:
                                r, c, clr = pending_after
                                # "确认中" chip (PRD §3.2/Q3): first frame of the 3-frame window
                                self._event_queue.put({
                                    "type": "move_pending",
                                    "data": {"row": int(r), "col": int(c), "color": int(clr)},
                                })
```
- **sync 块门控不改**（`worker_inprocess.py:179` 保持 `if self._bound:`）——PAUSE 只暂停落子确认，sync 照常跑（收窄语义见 Interfaces）。

**5b `worker.py`**：完全对称——`__init__`（`self._sync = SyncStateMachine()` 之后，~worker.py:103）加同样 4 行；`_process_commands` 的 `SET_EXPECTED_BOARD` 分支追加 `self._expected_np = board`、`BIND` 分支追加 `self._paused = False`、末尾加同样三个分支；`_processing_loop` 中 `detections_to_board` 调用处加同样的 masked 计算与参数（该文件用 `self._state_extractor`）；MoveDetector 块（worker.py:256-260，注意此处喂的是 `self._last_stable_board`——`detect_new_move(self._last_stable_board)` 保持不变，其余包裹逻辑同 5a）；**sync 门控（worker.py:290）不改**。

- [ ] **Step 6: service.py 三个方法**（`set_geometry` 之后）：

```python
    def pause_detection(self) -> None:
        """Suspend move detection + sync (hint display; PRD R4.3)."""
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.PAUSE_DETECTION))

    def resume_detection(self) -> None:
        if self._worker:
            self._worker.send_command(WorkerCommand(action=CommandType.RESUME_DETECTION))

    def set_lit_points(self, points: list[tuple[int, int]]) -> None:
        """Intersections currently lit by the LED board (R7.1 masking)."""
        if self._worker:
            self._worker.send_command(
                WorkerCommand(action=CommandType.SET_LIT_POINTS, data={"points": [[r, c] for r, c in points]})
            )
```

- [ ] **Step 7: 跑测试 + 回归**

Run: `CI=true uv run pytest tests/test_vision/ -v`
Expected: 新测试全 PASS，其余同基线。

- [ ] **Step 8: Commit**

```bash
uv run black -l 120 katrain/vision
git add katrain/vision tests/test_vision/test_board_state_masking.py tests/test_vision/test_worker_commands.py
git commit -m "feat(vision): pause/resume, lit-point masking, move_pending + ambiguous_stone events"
```

---

### Task 8: hint 后端（HintGate + POST /api/v1/hint + 白灯闪烁）

**Files:**
- Create: `katrain/web/core/hint_gate.py`
- Create: `katrain/web/api/v1/endpoints/hint.py`
- Modify: `katrain/web/api/v1/api.py`（注册 router）
- Test: `tests/test_hint_api.py`（新）

**Interfaces:**
- Consumes: `app.state.{session_manager, router, physical_play, physical_play_config, hint_gate}`；`session.katrain.{analysis_allowed, game_type, game}`；`Move.from_gtp`（sgf_parser.py:23）；`node.nodes_from_root / .moves / .placements / .clear_placements / .initial_player`（sgf_parser.py:279-358，与 engine.py:123-190 查询构造同源）；编排器 `.show_hint/.dismiss_hint`
- Produces:
  - `HintDecision(allowed, engine="local", reason="", charge_ref=None)`；`HintGate` Protocol（`.check(game_type=, user_id=) -> HintDecision`、`.settle(charge_ref, success)`）；`DefaultHintGate(hint_engine)`
  - `POST /api/v1/hint` body `{session_id, top_n?}` → `{"moves": [{gtp, coords, vision_rc, winrate, score_lead, visits}], "engine", "timeout_s"}`；403 detail ∈ {`ranked_forbidden`,`disabled`,`hint not allowed in this game`}；`POST /api/v1/hint/dismiss` → `{"ok": true}`

- [ ] **Step 1: 写失败测试（门控矩阵 + 端到端 fake）**

```python
# tests/test_hint_api.py
"""Hint gating matrix (PRD D3) + endpoint behaviour with fake router/orchestrator."""
import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints import hint
from katrain.web.core.hint_gate import DefaultHintGate
from katrain.web.core.physical_play import PhysicalPlayConfig


class TestDefaultHintGate:
    def test_free_allowed_with_engine(self):
        d = DefaultHintGate("cloud").check(game_type="free", user_id=None)
        assert d.allowed and d.engine == "cloud"

    def test_ranked_denied(self):
        d = DefaultHintGate("local").check(game_type="ranked", user_id=1)
        assert not d.allowed and d.reason == "ranked_forbidden"

    def test_engine_off_denied(self):
        d = DefaultHintGate("off").check(game_type="free", user_id=1)
        assert not d.allowed and d.reason == "disabled"


class FakeRouter:
    def __init__(self):
        self.payloads = []

    async def route(self, payload):
        self.payloads.append(payload)
        return {"engine": "local", "moveInfos": [
            {"move": "Q16", "order": 0, "winrate": 0.61, "scoreLead": 2.3, "visits": 100},
            {"move": "D4", "order": 1, "winrate": 0.58, "scoreLead": 1.9, "visits": 80},
            {"move": "pass", "order": 2, "winrate": 0.5, "scoreLead": 0.0, "visits": 10},
            {"move": "C3", "order": 3, "winrate": 0.55, "scoreLead": 1.0, "visits": 60},
        ]}


class FakeOrch:
    def __init__(self):
        self.shown = None
        self.dismissed = False

    def show_hint(self, points):
        self.shown = points

    def dismiss_hint(self):
        self.dismissed = True


class FakeMove:
    def __init__(self, player, gtp):
        self.player, self._gtp = player, gtp

    def gtp(self):
        return self._gtp


class FakeNode:
    def __init__(self):
        self.moves = []
        self.placements = []
        self.clear_placements = []
        self.ruleset = "chinese"
        self.initial_player = "B"
        self.nodes_from_root = [self]


class FakeGame:
    board_size = (19, 19)
    komi = 7.5

    def __init__(self):
        self.current_node = FakeNode()


class FakeKatrain:
    def __init__(self, game_type="free"):
        self.game_type = game_type
        self.analysis_allowed = game_type not in ("rated", "ranked")
        self.game = FakeGame()


class FakeSession:
    def __init__(self, game_type="free"):
        self.katrain = FakeKatrain(game_type)
        self.user_id = 1


class FakeManager:
    def __init__(self, session):
        self._s = session

    def get_session(self, sid):
        return self._s


def _client(session, engine="local"):
    app = FastAPI()
    app.include_router(hint.router, prefix="/hint")
    app.state.session_manager = FakeManager(session)
    app.state.router = FakeRouter()
    app.state.physical_play = FakeOrch()
    app.state.physical_play_config = PhysicalPlayConfig(hint_engine=engine, hint_top_n=3)
    app.state.hint_gate = DefaultHintGate(engine)
    return TestClient(app)


class TestHintEndpoint:
    def test_free_game_returns_topn_skipping_pass_and_blinks(self):
        c = _client(FakeSession("free"))
        r = c.post("/hint", json={"session_id": "s1"})
        assert r.status_code == 200
        body = r.json()
        assert [m["gtp"] for m in body["moves"]] == ["Q16", "D4", "C3"]  # pass 被跳过，补足 top3
        assert body["moves"][0]["vision_rc"] == [3, 15]                  # Q16: x=15,y=15 -> row 3, col 15
        assert c.app.state.physical_play.shown == [(3, 15), (15, 3), (16, 2)]
        assert body["timeout_s"] == 30.0

    def test_ranked_rejected_server_side(self):
        c = _client(FakeSession("ranked"))
        r = c.post("/hint", json={"session_id": "s1"})
        assert r.status_code == 403

    def test_engine_off_rejected(self):
        c = _client(FakeSession("free"), engine="off")
        assert c.post("/hint", json={"session_id": "s1"}).status_code == 403

    def test_dismiss(self):
        c = _client(FakeSession("free"))
        assert c.post("/hint/dismiss").status_code == 200
        assert c.app.state.physical_play.dismissed is True

    def test_handicap_payload_includes_initial_stones_and_player(self):
        # 评审 Codex I2：payload 须镜像 engine.py 语义（placements + initialPlayer）
        c = _client(FakeSession("free"))
        node = c.app.state.session_manager._s.katrain.game.current_node
        node.placements = [FakeMove("B", "D4"), FakeMove("B", "Q16")]
        node.initial_player = "W"
        assert c.post("/hint", json={"session_id": "s1"}).status_code == 200
        payload = c.app.state.router.payloads[0]
        assert payload["initialStones"] == [["B", "D4"], ["B", "Q16"]]
        assert payload["initialPlayer"] == "W"

    def test_clear_placements_rejected(self):
        # AE（清除摆子）KaTrain 自己的查询构造器也拒绝（engine.py:127 "TODO: support these"）
        c = _client(FakeSession("free"))
        node = c.app.state.session_manager._s.katrain.game.current_node
        node.clear_placements = [FakeMove("B", "D4")]
        assert c.post("/hint", json={"session_id": "s1"}).status_code == 400
```

（GTP 坐标核对：Q16 在 19 路 = x=15（GTP 列 Q，跳过 I）、y=15 → `vision_rc=[19-1-15, 15]=[3,15]`；D4 = x=3,y=3 → `[15,3]`；C3 = x=2,y=2 → `[16,2]`。`Move.from_gtp` 的返回以 katrain 实际实现为准——若断言失败先人工核对 `Move.from_gtp("Q16").coords`。）

- [ ] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/test_hint_api.py -v`
Expected: FAIL——ModuleNotFoundError。

- [ ] **Step 3: 实现 hint_gate.py**

```python
# katrain/web/core/hint_gate.py
"""Gating chain for the AI hint (选点白灯): scene → anti-cheat → billing → engine routing.

Q1 decision (2026-07-02): billing is a PROTOCOL STUB. The paid-analysis track
(feature/rk3588-ui phases 4b+) will implement a BillingHintGate over
core/billing.py reserve/commit/refund once the cloud billing proxy exists —
board-mode billing REST currently 503s all balance ops (endpoints/billing.py),
so local charging is impossible anyway. Until then DefaultHintGate routes purely
by static config: 'cloud' | 'local' | 'off'.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class HintDecision:
    allowed: bool
    engine: str = "local"  # "local" | "cloud"
    reason: str = ""  # machine-readable denial reason for the frontend toast
    charge_ref: Optional[str] = None  # billing reservation id (paid-analysis, later)


class HintGate(Protocol):
    def check(self, *, game_type: str, user_id: Optional[int]) -> HintDecision: ...

    def settle(self, charge_ref: Optional[str], success: bool) -> None: ...


class DefaultHintGate:
    """Config-only gate: no billing."""

    def __init__(self, hint_engine: str = "local"):
        self._engine = hint_engine

    def check(self, *, game_type: str, user_id: Optional[int] = None) -> HintDecision:
        if game_type != "free":
            return HintDecision(allowed=False, reason="ranked_forbidden")
        if self._engine == "off":
            return HintDecision(allowed=False, reason="disabled")
        return HintDecision(allowed=True, engine=self._engine)

    def settle(self, charge_ref: Optional[str], success: bool) -> None:
        return None
```

- [ ] **Step 4: 实现 endpoints/hint.py**

```python
# katrain/web/api/v1/endpoints/hint.py
"""POST /api/v1/hint — AI 支招: top-N candidate points, white blinking LEDs on the
physical board, detection suspended while shown (PRD R4)."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from katrain.web.core.hint_gate import DefaultHintGate
from katrain.web.core.physical_play import PhysicalPlayConfig

router = APIRouter()


class HintRequest(BaseModel):
    session_id: str
    top_n: Optional[int] = Field(default=None, ge=1, le=10)


def _build_payload_from_game(game, max_visits: int) -> dict:
    """KataGo analysis payload for the current position — mirrors KaTrain's own
    query builder (BaseEngine.request_analysis, katrain/core/engine.py:123-190,
    review Codex I2): moves AND placements are collected from EVERY node on the
    path (setup stones can appear mid-tree), AE/clear_placements is unsupported
    (KaTrain's builder refuses such positions too), and initialPlayer matters
    for handicap games (White moves first)."""
    nodes = game.current_node.nodes_from_root
    moves = [m for node in nodes for m in node.moves]
    initial_stones = [m for node in nodes for m in node.placements]
    if any(node.clear_placements for node in nodes):
        raise ValueError("unsupported position: AE (clear placements) in game path")
    size_x, size_y = game.board_size
    return {
        "rules": game.current_node.ruleset or "chinese",
        "komi": game.komi,
        "boardXSize": size_x,
        "boardYSize": size_y,
        "analyzeTurns": [len(moves)],
        "maxVisits": max_visits,
        "includeOwnership": False,
        "includePolicy": False,
        "initialStones": [[m.player, m.gtp()] for m in initial_stones],
        "initialPlayer": game.current_node.initial_player,
        "moves": [[m.player, m.gtp()] for m in moves],
    }


@router.post("")
async def request_hint(request: Request, body: HintRequest):
    manager = request.app.state.session_manager
    try:
        session = manager.get_session(body.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    katrain = session.katrain
    game_type = getattr(katrain, "game_type", "free")
    # D3 double gate: analysis_allowed (anti-cheat chokepoint semantics) AND free-only scene.
    if not getattr(katrain, "analysis_allowed", True) or game_type != "free":
        raise HTTPException(status_code=403, detail="hint not allowed in this game")

    config: PhysicalPlayConfig = getattr(request.app.state, "physical_play_config", None) or PhysicalPlayConfig()
    gate = getattr(request.app.state, "hint_gate", None) or DefaultHintGate(config.hint_engine)
    decision = gate.check(game_type=game_type, user_id=getattr(session, "user_id", None))
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)

    router_instance = getattr(request.app.state, "router", None)
    if router_instance is None:
        raise HTTPException(status_code=503, detail="engine not available")

    try:
        payload = _build_payload_from_game(katrain.game, config.hint_max_visits)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    payload["is_analysis"] = decision.engine == "cloud"  # RequestRouter: cloud-preferred routing
    try:
        result = await router_instance.route(payload)
    except Exception as e:
        gate.settle(decision.charge_ref, success=False)
        raise HTTPException(status_code=502, detail=str(e))
    gate.settle(decision.charge_ref, success=True)

    from katrain.core.game import Move

    top_n = body.top_n or config.hint_top_n
    board_size = katrain.game.board_size[0]
    moves = []
    for info in sorted(result.get("moveInfos", []), key=lambda m: m.get("order", 999)):
        if len(moves) >= top_n:
            break
        gtp = info.get("move", "pass")
        if gtp.lower() == "pass":
            continue
        x, y = Move.from_gtp(gtp).coords
        moves.append(
            {
                "gtp": gtp,
                "coords": [x, y],
                "vision_rc": [board_size - 1 - y, x],
                "winrate": info.get("winrate"),
                "score_lead": info.get("scoreLead"),
                "visits": info.get("visits"),
            }
        )

    orchestrator = getattr(request.app.state, "physical_play", None)
    if orchestrator is not None and moves:
        orchestrator.show_hint([tuple(m["vision_rc"]) for m in moves])
    return {"moves": moves, "engine": result.get("engine", decision.engine), "timeout_s": config.hint_timeout_s}


@router.post("/dismiss")
async def dismiss_hint(request: Request):
    orchestrator = getattr(request.app.state, "physical_play", None)
    if orchestrator is not None:
        orchestrator.dismiss_hint()
    return {"ok": True}
```

- [ ] **Step 5: 注册 router**

`katrain/web/api/v1/api.py`：import 元组加 `hint`，末尾加：

```python
api_router.include_router(hint.router, prefix="/hint", tags=["hint"])
```

- [ ] **Step 6: lifespan 装 hint_gate**（Task 6 已装 config；`server.py` 编排器块内、`log.info("Physical-play orchestrator ready ...)` 之前追加）：

```python
        from katrain.web.core.hint_gate import DefaultHintGate

        app.state.hint_gate = DefaultHintGate(pp_config.hint_engine)
```

- [ ] **Step 7: 跑测试 + 回归 + Commit**

Run: `CI=true uv run pytest tests/test_hint_api.py tests/test_physical_play_orchestrator.py -v` → 全 PASS。

```bash
uv run black -l 120 katrain/web/core/hint_gate.py katrain/web/api/v1/endpoints/hint.py tests/test_hint_api.py
git add katrain/web/core/hint_gate.py katrain/web/api/v1/endpoints/hint.py katrain/web/api/v1/api.py katrain/web/server.py tests/test_hint_api.py
git commit -m "feat(web): /api/v1/hint — gate chain, engine routing, white-blink top-N (billing stub)"
```

---

### Task 9: 前端基础（GameState 类型补全 + LED 健康徽标）

**Files:**
- Modify: `katrain/web/ui/src/api.ts`（共享区！）
- Modify: `katrain/web/api/v1/endpoints/vision.py`（status 加 `led_connected`）
- Modify: `katrain/web/ui/src/kiosk/context/VisionContext.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/GamePageLedBadge.test.tsx`（新）

**Interfaces:**
- Produces: `GameState.game_type?: string; analysis_allowed?: boolean`（后端已发，只补 TS）；`VisionStatusResponse.led_connected?: boolean`；`VisionStatus.ledConnected: boolean | null`；GamePage 徽标区第二个图标

- [ ] **Step 1: 后端 status 字段**

`katrain/web/api/v1/endpoints/vision.py` 的 `vision_status`，两个 return dict 各加一行（利用 `request.app.state.led`；vision 关闭分支也加，便于纯 LED 场景排障）：

```python
        "led_connected": bool(getattr(request.app.state, "led", None))
        and request.app.state.led.is_connected(),
```

追加测试到 `tests/test_vision_bind_state.py`：

```python
class FakeLed:
    def is_connected(self):
        return True


class TestStatusLed:
    def test_status_reports_led_connected(self):
        c = _client(FakeVision(), FakeManager())
        c.app.state.led = FakeLed()
        # FakeVision 缺 status 属性时按 vision=None 分支断言：
        c.app.state.vision = None
        r = c.get("/vision/status")
        assert r.status_code == 200
        assert r.json()["led_connected"] is True
```

Run: `CI=true uv run pytest tests/test_vision_bind_state.py -v` → 先 FAIL 后（改完）PASS。

- [ ] **Step 2: api.ts 类型**

`GameState` 接口（api.ts:10-72）追加两个可选字段：

```typescript
  game_type?: string; // "free" | "ranked" | "rated" — backend interface.py get_state()
  analysis_allowed?: boolean;
```

`VisionStatusResponse`（api.ts:109-115）追加：

```typescript
  led_connected?: boolean;
```

- [ ] **Step 3: VisionContext**

`VisionStatus` 接口加 `ledConnected: boolean | null;`；初始值 `null`；`mapResponse`（30-36 行的 snake→camel 映射）加 `ledConnected: data.led_connected ?? null,`。

- [ ] **Step 4: GamePage 徽标**

GamePage 顶右浮动徽标 Box（GamePage.tsx:112-116，现有 `<Videocam>`）内追加：

```tsx
        <Lightbulb
          sx={{
            color: visionStatus.ledConnected === false ? 'error.main'
              : visionStatus.ledConnected ? 'success.main' : 'text.disabled',
          }}
        />
```

（import `Lightbulb` from `@mui/icons-material`。`ledConnected === false` 红 = R2.6 降级徽标；`null` 灰 = LED 服务未启用。）

同一步顺手修 **visionBind 双重调用**（评审 Codex M1）：GamePage.tsx:42-48 的直调 `API.visionBind/visionUnbind` effect **整段删除**——`useVisionSync`（useVisionSync.ts:75,110）已在连接 `/ws/vision` 前 bind、清理时 unbind，是唯一 owner。编排器挂上 bind 钩子后（Task 6），双重调用会触发两次 on_bind/on_unbind 生命周期（后端已做同 session 幂等，但前端仍应单一 owner）。删除后 GamePage 的 vision 生命周期完全由 `useVisionSync(isVisionEnabled ? sessionId : null)` 驱动。

- [ ] **Step 5: Vitest（沿用 GamePage.test.tsx 的 mock 模板：mock OrientationContext/AuthContext/Board/useGameSession，VisionContext mock 改为 enabled + ledConnected: false）**

```tsx
// katrain/web/ui/src/kiosk/__tests__/GamePageLedBadge.test.tsx
// 从 GamePage.test.tsx 复制 mock 头部（vi.mock 全套），仅 VisionContext 改为：
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: { enabled: true, cameraConnected: true, poseLocked: true, syncState: 'synced', boundSessionId: 's1', ledConnected: false },
    isVisionEnabled: true,
    refreshStatus: vi.fn(),
  }),
}));
// useVisionSync 也需 mock 为空事件流：
vi.mock('../hooks/useVisionSync', () => ({
  useVisionSync: () => ({ syncEvents: [], latestEvent: null, setupProgress: null, isSetupComplete: false }),
}));

it('shows a red LED badge when the LED board is down', () => {
  renderGamePage(); // 同模板 helper
  expect(document.querySelector('[data-testid="LightbulbIcon"]')).toBeTruthy();
});
```

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePageLedBadge.test.tsx`

- [ ] **Step 6: 双构建验证（改了共享区 api.ts！）+ Commit**

```bash
cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd -
uv run black -l 120 katrain/web/api/v1/endpoints/vision.py
git add katrain/web/ui/src katrain/web/api/v1/endpoints/vision.py tests/test_vision_bind_state.py
git commit -m "feat(kiosk): LED health badge + GameState game_type/analysis_allowed typing"
```

---

### Task 10: 前端「确认中」状态条 + 追平提醒 toast + 逃生舱对话框

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/physical/PhysicalPlayStatusChip.tsx`
- Create: `katrain/web/ui/src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx`（评审 B 逃生舱）
- Delete: `katrain/web/ui/src/kiosk/components/game/MovePendingOverlay.tsx`（死代码，被本组件取代）
- Modify: `katrain/web/ui/src/kiosk/hooks/useVisionSync.ts`（事件类型）
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts`（共享区：physical_reminder 透传）
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/PhysicalPlayStatusChip.test.tsx`、`PhysicalSyncEscalationDialog.test.tsx`（新）

**Interfaces:**
- Consumes: Task 7 `move_pending` 事件；Task 4 `physical_reminder` 会话消息（含 `kind: 'reminder' | 'escalation'`）
- Produces: `PhysicalPlayStatusChip({ latestEvent, currentNodeId })`；`PhysicalSyncEscalationDialog({ open, toPlace, toRemove, onClose })`；`useGameSession` 返回 bag 新增 `physicalReminder`

- [ ] **Step 1: useVisionSync 事件类型**

`SyncEventType` union（useVisionSync.ts:6-25）追加两个成员：`| 'move_pending' | 'synced'`（`synced` 顺带补上——后端一直在发）。

- [ ] **Step 2: useGameSession 透传**（共享区，最小改动：状态 + case + 返回）

```typescript
  const [physicalReminder, setPhysicalReminder] = useState<{
    kind: 'reminder' | 'escalation';
    to_place: number[][];
    to_remove: number[][];
  } | null>(null);
```
消息 switch（64-95 行）加：
```typescript
      } else if (msg.type === 'physical_reminder') {
        setPhysicalReminder(msg.data);
```
返回 bag（162 行）加 `physicalReminder,`。

- [ ] **Step 3: 组件**

```tsx
// katrain/web/ui/src/kiosk/components/physical/PhysicalPlayStatusChip.tsx
import { useEffect, useState } from 'react';
import { Chip } from '@mui/material';
import { HourglassTop } from '@mui/icons-material';
import { useTranslation } from '../../../hooks/useTranslation';
import type { VisionSyncEvent } from '../../hooks/useVisionSync';

interface Props {
  latestEvent: VisionSyncEvent | null;
  currentNodeId: number | null; // gameState.current_node_id — advance hides the chip
}

/** '确认中…' (PRD §3.2/Q3): shown from move_pending until the game state advances or 6s. */
const PhysicalPlayStatusChip = ({ latestEvent, currentNodeId }: Props) => {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (latestEvent?.type === 'move_pending') {
      setVisible(true);
      const timer = setTimeout(() => setVisible(false), 6000);
      return () => clearTimeout(timer);
    }
  }, [latestEvent]);
  useEffect(() => {
    setVisible(false);
  }, [currentNodeId]);
  if (!visible) return null;
  return (
    <Chip
      icon={<HourglassTop />}
      label={t('Confirming…', '确认中…')}
      color="warning"
      size="small"
      sx={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', zIndex: 50 }}
    />
  );
};

export default PhysicalPlayStatusChip;
```

- [ ] **Step 4: 逃生舱对话框组件（评审 B：长时间失同步不能只靠 nag）**

```tsx
// katrain/web/ui/src/kiosk/components/physical/PhysicalSyncEscalationDialog.tsx
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { API } from '../../../api';

interface Props {
  open: boolean;
  toPlace: number[][];
  toRemove: number[][];
  onClose: () => void;
}

/** Review B escape hatch: after escalate_after_s of physical lag, force a decision
 * instead of stalling the game forever. '改用屏幕落子' unbinds vision (orchestrator
 * clears the lamps, detection stops) and the game continues via on-screen taps. */
const PhysicalSyncEscalationDialog = ({ open, toPlace, toRemove, onClose }: Props) => {
  const { t } = useTranslation();
  const restored = () => {
    API.visionResetSync().catch(() => undefined);
    onClose();
  };
  const screenPlay = () => {
    API.visionUnbind().catch(() => undefined);
    onClose();
  };
  return (
    <Dialog open={open} maxWidth="xs" fullWidth>
      <DialogTitle>{t('Physical board out of sync', '物理棋盘长时间未跟上对局')}</DialogTitle>
      <DialogContent>
        <Typography variant="body2">
          {t(
            'Place / remove the lit stones, then confirm — or continue on screen.',
            '请按亮灯指示摆放（红/绿灯）或拿除（蓝灯）棋子后确认；也可改用屏幕继续对局。'
          )}
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', mt: 1 }}>
          {t('To place', '待摆放')}: {toPlace.length} · {t('To remove', '待拿除')}: {toRemove.length}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={restored} variant="contained">{t('Board restored', '已按指示恢复')}</Button>
        <Button onClick={screenPlay} color="warning">{t('Continue on screen', '改用屏幕落子')}</Button>
        <Button onClick={onClose}>{t('Keep waiting', '继续等待')}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default PhysicalSyncEscalationDialog;
```

- [ ] **Step 5: GamePage 挂载**

- 棋盘容器（Board 所在的相对定位 Box 内）加：
```tsx
        {isVisionEnabled && (
          <PhysicalPlayStatusChip
            latestEvent={visionSync.latestEvent}
            currentNodeId={session.gameState?.current_node_id ?? null}
          />
        )}
```
- 追平提醒（30s toast）与逃生舱（120s 对话框）按 `kind` 分流（AI move Snackbar 旁，177-180 附近）：
```tsx
        <Snackbar
          open={reminderOpen}
          autoHideDuration={8000}
          onClose={() => setReminderOpen(false)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
          message={t('Please place the AI stone at the lit point first', '请先将 AI 棋子摆到棋盘亮灯处')}
        />
        <PhysicalSyncEscalationDialog
          open={escalationOpen}
          toPlace={session.physicalReminder?.to_place ?? []}
          toRemove={session.physicalReminder?.to_remove ?? []}
          onClose={() => setEscalationOpen(false)}
        />
```
配套 state + effect：
```tsx
  const [reminderOpen, setReminderOpen] = useState(false);
  const [escalationOpen, setEscalationOpen] = useState(false);
  useEffect(() => {
    if (!session.physicalReminder) return;
    if (session.physicalReminder.kind === 'escalation') setEscalationOpen(true);
    else setReminderOpen(true);
  }, [session.physicalReminder]);
```
- 删除 `src/kiosk/components/game/MovePendingOverlay.tsx`（grep 确认无引用后 `git rm`）。

- [ ] **Step 6: Vitest**

```tsx
// katrain/web/ui/src/kiosk/__tests__/PhysicalPlayStatusChip.test.tsx
import { render, screen, act } from '@testing-library/react';
import PhysicalPlayStatusChip from '../components/physical/PhysicalPlayStatusChip';

it('shows on move_pending and hides when the node advances', () => {
  const { rerender } = render(
    <PhysicalPlayStatusChip latestEvent={{ type: 'move_pending', data: { row: 3, col: 3 } }} currentNodeId={1} />
  );
  expect(screen.getByText('确认中…')).toBeTruthy();
  rerender(
    <PhysicalPlayStatusChip latestEvent={{ type: 'move_pending', data: { row: 3, col: 3 } }} currentNodeId={2} />
  );
  expect(screen.queryByText('确认中…')).toBeNull();
});
```

```tsx
// katrain/web/ui/src/kiosk/__tests__/PhysicalSyncEscalationDialog.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PhysicalSyncEscalationDialog from '../components/physical/PhysicalSyncEscalationDialog';

const resetSync = vi.fn().mockResolvedValue(undefined);
const unbind = vi.fn().mockResolvedValue(undefined);
vi.mock('../../api', () => ({
  API: { visionResetSync: () => resetSync(), visionUnbind: () => unbind() },
}));

const base = { open: true, toPlace: [[3, 3]], toRemove: [], onClose: vi.fn() };

it('restored resets sync; screen-play unbinds vision', async () => {
  render(<PhysicalSyncEscalationDialog {...base} />);
  fireEvent.click(screen.getByText('已按指示恢复'));
  await waitFor(() => expect(resetSync).toHaveBeenCalledTimes(1));
  render(<PhysicalSyncEscalationDialog {...base} />);
  fireEvent.click(screen.getByText('改用屏幕落子'));
  await waitFor(() => expect(unbind).toHaveBeenCalledTimes(1));
});
```
（`vi.mock` 路径以测试文件相对 `src/api.ts` 的实际说明符为准——从 `__tests__/` 是 `'../../api'`。）

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/PhysicalPlayStatusChip.test.tsx src/kiosk/__tests__/PhysicalSyncEscalationDialog.test.tsx`

- [ ] **Step 7: 双构建 + Commit**

```bash
cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd -
git add -A katrain/web/ui/src
git commit -m "feat(kiosk): confirming chip + catch-up reminder + desync escape-hatch dialog; drop dead MovePendingOverlay"
```

---

### Task 11: 前端混合确认（mismatch 差异视图 / 恢复清单 / ambiguous 确认卡）

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/physical/BoardMismatchDialog.tsx`
- Create: `katrain/web/ui/src/kiosk/components/physical/AmbiguousMoveCard.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/BoardMismatchDialog.test.tsx`（新）

**Interfaces:**
- Consumes: Task 5 `illegal_change` payload `{positions, missing}`；Task 7 `ambiguous_stone` payload `{row, col, color, confidence}`；`API.playMove(sessionId, {x, y})`；`API.visionResetSync()`
- Produces: `VisionSyncOverlay` 新 props：`sessionId: string | null; boardSize: number; playerToMove: string | null`（GamePage 传入）

- [ ] **Step 1: BoardMismatchDialog**（坐标换算工具 `rcToGtpLabel`/`rcToXy` 定义在本文件并导出，AmbiguousMoveCard 复用）

```tsx
// katrain/web/ui/src/kiosk/components/physical/BoardMismatchDialog.tsx
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, List, ListItem, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';

type Pos = [number, number, number]; // [row, col, color] 1=黑 2=白

// vision 网格 (row0=顶) ↔ GTP 标签 / KaTrain (x,y)（AmbiguousMoveCard 亦复用）
export const rcToGtpLabel = (row: number, col: number, boardSize: number): string => {
  const colLabel = String.fromCharCode(65 + (col >= 8 ? col + 1 : col)); // skip I
  return `${colLabel}${boardSize - row}`;
};
export const rcToXy = (row: number, col: number, boardSize: number): { x: number; y: number } => ({
  x: col,
  y: boardSize - 1 - row,
});

interface Props {
  open: boolean;
  positions: Pos[]; // 多余/错色的物理子
  missing: Pos[]; // 该在盘上却缺失的子
  boardSize: number;
  playerToMove: string | null; // 'B' | 'W'
  onAdoptObserved: (x: number, y: number) => void; // 采纳观测（单子且轮到该色时）
  onRestored: () => void; // 恢复完成 → visionResetSync
  onDismiss: () => void;
}

const colorName = (c: number) => (c === 1 ? '黑' : '白');

const BoardMismatchDialog = ({ open, positions, missing, boardSize, playerToMove, onAdoptObserved, onRestored, onDismiss }: Props) => {
  const { t } = useTranslation();
  const adoptable =
    positions.length === 1 && missing.length === 0 && playerToMove != null &&
    ((playerToMove === 'B' && positions[0][2] === 1) || (playerToMove === 'W' && positions[0][2] === 2));
  return (
    <Dialog open={open} maxWidth="xs" fullWidth>
      <DialogTitle>{t('Board mismatch', '盘面与对局不一致')}</DialogTitle>
      <DialogContent>
        {positions.length > 0 && (
          <>
            <Typography variant="subtitle2" color="error">{t('Remove these stones', '请拿走（蓝灯处）')}</Typography>
            <List dense>
              {positions.map(([r, c, clr]) => (
                <ListItem key={`e${r}-${c}`}>{`${colorName(clr)} ${rcToGtpLabel(r, c, boardSize)}`}</ListItem>
              ))}
            </List>
          </>
        )}
        {missing.length > 0 && (
          <>
            <Typography variant="subtitle2" color="warning.main">{t('Place these stones', '请摆上（红/绿灯处）')}</Typography>
            <List dense>
              {missing.map(([r, c, clr]) => (
                <ListItem key={`m${r}-${c}`}>{`${colorName(clr)} ${rcToGtpLabel(r, c, boardSize)}`}</ListItem>
              ))}
            </List>
          </>
        )}
      </DialogContent>
      <DialogActions>
        {adoptable && (
          <Button onClick={() => { const { x, y } = rcToXy(positions[0][0], positions[0][1], boardSize); onAdoptObserved(x, y); }}>
            {t('Accept as my move', '采纳为我的落子')}
          </Button>
        )}
        <Button onClick={onRestored} variant="contained">{t('Board restored', '已按指示恢复')}</Button>
        <Button onClick={onDismiss}>{t('Ignore', '忽略')}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default BoardMismatchDialog;
```

- [ ] **Step 2: AmbiguousMoveCard**

```tsx
// katrain/web/ui/src/kiosk/components/physical/AmbiguousMoveCard.tsx
import { Button, Card, CardActions, CardContent, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { rcToGtpLabel, rcToXy } from './BoardMismatchDialog';

interface Props {
  row: number;
  col: number;
  boardSize: number;
  onConfirm: (x: number, y: number) => void; // 确认 → API.playMove
  onIgnore: () => void;
}

const AmbiguousMoveCard = ({ row, col, boardSize, onConfirm, onIgnore }: Props) => {
  const { t } = useTranslation();
  return (
    <Card sx={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 120, minWidth: 280 }}>
      <CardContent>
        <Typography>
          {t('Possible move detected at', '检测到疑似落子于')} {rcToGtpLabel(row, col, boardSize)}
        </Typography>
      </CardContent>
      <CardActions>
        <Button variant="contained" onClick={() => { const { x, y } = rcToXy(row, col, boardSize); onConfirm(x, y); }}>
          {t('Confirm', '确认落子')}
        </Button>
        <Button onClick={onIgnore}>{t('Ignore', '忽略')}</Button>
      </CardActions>
    </Card>
  );
};

export default AmbiguousMoveCard;
```

- [ ] **Step 3: VisionSyncOverlay 接线**

props 扩为 `{ syncEvents, onDismiss?, sessionId, boardSize, playerToMove }`（GamePage 传 `sessionId={sessionId ?? null} boardSize={session.gameState?.board_size?.[0] ?? 19} playerToMove={session.gameState?.player_to_move ?? null}`）。事件处理改动（沿用 processedRef 游标模式）：

- `illegal_change`（142-144 行）：从 `event.data` 取 `positions`/`missing`，存 state `mismatch = {positions, missing}`，渲染 `<BoardMismatchDialog open={!!mismatch} … />` 取代现有简陋 Dialog；回调：
  - `onAdoptObserved(x, y)`: `API.playMove(sessionId!, { x, y }).catch(() => undefined); setMismatch(null);`
  - `onRestored()`: `API.visionResetSync().catch(() => undefined); setMismatch(null);`
  - `onDismiss()`: `setMismatch(null);`
- `synced` 事件：`setMismatch(null)`（盘面恢复自动消退）。
- `ambiguous_stone`：从 TOAST_MAP 移除；改存 state `ambiguous = {row, col}` 渲染 `<AmbiguousMoveCard … onConfirm={(x,y)=>{API.playMove(sessionId!, {x,y}).catch(()=>undefined); setAmbiguous(null);}} onIgnore={()=>{API.visionResetSync().catch(()=>undefined); setAmbiguous(null);}} />`（忽略 = 接受当前物理盘为基线，防止残余 pending）。
- `board_lost` 10s Dialog 文案微调：加一句副标题 `t('If the board was bumped, use Re-align in the banner', '若棋盘被碰动，请使用横幅中的「重新定位」')`（与 Task 14 呼应）；其余保持。
- `capture_pending`/`captures_cleared`/CaptureGuide 保持不变（Task 5 后数字提子自动走这条既有 UI）。
- 文件内新增 import `{ API } from '../../../api'`（以该文件现有 api import 路径写法为准）。

- [ ] **Step 4: Vitest**

```tsx
// katrain/web/ui/src/kiosk/__tests__/BoardMismatchDialog.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import BoardMismatchDialog from '../components/physical/BoardMismatchDialog';

const base = { open: true, boardSize: 19, onAdoptObserved: vi.fn(), onRestored: vi.fn(), onDismiss: vi.fn() };

it('lists extra and missing stones with GTP labels', () => {
  render(<BoardMismatchDialog {...base} positions={[[15, 15, 1]]} missing={[[3, 3, 2]]} playerToMove="B" />);
  expect(screen.getByText('黑 Q4')).toBeTruthy();   // row15,col15 -> Q4
  expect(screen.getByText('白 D16')).toBeTruthy();  // row3,col3  -> D16
});

it('adopt button only for a single same-color extra stone', () => {
  const onAdopt = vi.fn();
  render(<BoardMismatchDialog {...base} onAdoptObserved={onAdopt} positions={[[15, 15, 1]]} missing={[]} playerToMove="B" />);
  fireEvent.click(screen.getByText('采纳为我的落子'));
  expect(onAdopt).toHaveBeenCalledWith(15, 3);       // x=col=15, y=18-15=3
});
```

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/BoardMismatchDialog.test.tsx`

- [ ] **Step 5: 双构建 + Commit**

```bash
cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd -
git add katrain/web/ui/src
git commit -m "feat(kiosk): hybrid-confirmation UX — mismatch diff dialog, restore checklist, ambiguous card"
```

---

### Task 12: 前端 AI 支招（按钮 + 面板）

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/physical/HintPanel.tsx`
- Modify: `katrain/web/ui/src/api.ts`（共享区：hint API）
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/HintPanel.test.tsx`（新）

**Interfaces:**
- Consumes: Task 8 `/api/v1/hint`、`/api/v1/hint/dismiss`；`GameState.game_type/analysis_allowed`（Task 9）
- Produces: `API.hint(sessionId, topN?)`、`API.hintDismiss()`；`HintMove` TS 类型

- [ ] **Step 1: api.ts**（`visionSetupMode` 之后，沿用 `apiPost` 风格）：

```typescript
export interface HintMove {
  gtp: string;
  coords: [number, number];
  vision_rc: [number, number];
  winrate: number | null;
  score_lead: number | null;
  visits: number | null;
}
export interface HintResponse { moves: HintMove[]; engine: string; timeout_s: number; }
```
`API` 对象内：
```typescript
  hint: (sessionId: string, topN?: number): Promise<HintResponse> =>
    apiPost('/api/v1/hint', { session_id: sessionId, top_n: topN ?? null }) as Promise<HintResponse>,
  hintDismiss: (): Promise<{ ok: boolean }> =>
    apiPost('/api/v1/hint/dismiss', {}) as Promise<{ ok: boolean }>,
```
（`apiPost` 若非泛型按其实际签名调整断言写法。）

- [ ] **Step 2: HintPanel**

```tsx
// katrain/web/ui/src/kiosk/components/physical/HintPanel.tsx
import { useEffect } from 'react';
import { Button, Card, CardActions, CardContent, Stack, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import type { HintMove } from '../../../api';

interface Props {
  moves: HintMove[];
  timeoutS: number;
  onClose: () => void; // 关闭/超时 → API.hintDismiss()
}

/** 白灯闪烁期间的屏幕同步面板：各选点胜率/目差（PRD §3.3）。 */
const HintPanel = ({ moves, timeoutS, onClose }: Props) => {
  const { t } = useTranslation();
  useEffect(() => {
    const timer = setTimeout(onClose, timeoutS * 1000);
    return () => clearTimeout(timer);
  }, [timeoutS, onClose]);
  return (
    <Card sx={{ position: 'absolute', top: 56, right: 8, zIndex: 130, minWidth: 240 }}>
      <CardContent>
        <Typography variant="subtitle1">{t('AI suggestions (white lamps)', 'AI 支招（白灯闪烁处）')}</Typography>
        <Stack spacing={0.5} sx={{ mt: 1 }}>
          {moves.map((m) => (
            <Typography key={m.gtp} variant="body2">
              {m.gtp} · {t('winrate', '胜率')} {m.winrate != null ? `${(m.winrate * 100).toFixed(1)}%` : '—'} ·{' '}
              {t('score', '目差')} {m.score_lead != null ? m.score_lead.toFixed(1) : '—'}
            </Typography>
          ))}
        </Stack>
      </CardContent>
      <CardActions>
        <Button fullWidth variant="contained" onClick={onClose}>{t('Close', '关闭')}</Button>
      </CardActions>
    </Card>
  );
};

export default HintPanel;
```

- [ ] **Step 3: GamePage 按钮 + 状态**

```tsx
  const [hint, setHint] = useState<HintResponse | null>(null);
  const [hintError, setHintError] = useState<string | null>(null);

  const hintVisible =
    isVisionEnabled &&
    session.gameState?.game_type === 'free' &&
    session.gameState?.analysis_allowed !== false;

  const handleHint = async () => {
    if (!sessionId) return;
    try {
      setHint(await API.hint(sessionId));
    } catch (e) {
      const msg = String(e);
      setHintError(
        msg.includes('ranked_forbidden') ? t('Not available in ranked games', '升降级对局不可用')
        : msg.includes('disabled') ? t('Hint is not enabled', '支招功能未开放')
        : msg.includes('insufficient') ? t('Insufficient balance', '余额不足')
        : t('Hint failed', '支招失败，请稍后再试')
      );
    }
  };

  const closeHint = () => {
    setHint(null);
    API.hintDismiss().catch(() => undefined);
  };
```
按钮放 Header（Exit 按钮旁，GamePage.tsx:118-127）：
```tsx
        {hintVisible && (
          <Button variant="outlined" size="small" startIcon={<TipsAndUpdates />} onClick={handleHint}>
            {t('AI Hint', 'AI 支招')}
          </Button>
        )}
```
渲染（VisionSyncOverlay 旁）：
```tsx
        {hint && <HintPanel moves={hint.moves} timeoutS={hint.timeout_s} onClose={closeHint} />}
        <Snackbar open={!!hintError} autoHideDuration={5000} onClose={() => setHintError(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }} message={hintError} />
```
（import `TipsAndUpdates` from `@mui/icons-material`、`HintPanel`、`HintResponse`。离开页面卸载时若 hint 未关闭：GamePage 卸载 cleanup 里加 `API.hintDismiss().catch(() => undefined)`——放进现有 visionUnbind 的同一 effect return。）

- [ ] **Step 4: Vitest**

```tsx
// katrain/web/ui/src/kiosk/__tests__/HintPanel.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import HintPanel from '../components/physical/HintPanel';

const moves = [{ gtp: 'Q16', coords: [15, 15] as [number, number], vision_rc: [3, 15] as [number, number], winrate: 0.61, score_lead: 2.3, visits: 100 }];

it('renders winrate/score and closes', () => {
  const onClose = vi.fn();
  render(<HintPanel moves={moves} timeoutS={30} onClose={onClose} />);
  expect(screen.getByText(/Q16/)).toBeTruthy();
  expect(screen.getByText(/61\.0%/)).toBeTruthy();
  fireEvent.click(screen.getByText('关闭'));
  expect(onClose).toHaveBeenCalled();
});
```

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/HintPanel.test.tsx`

- [ ] **Step 5: 双构建（又改了共享区 api.ts）+ Commit**

```bash
cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd -
git add katrain/web/ui/src
git commit -m "feat(kiosk): AI hint button + panel wired to /api/v1/hint (free games only)"
```

---

### Task 13: 升降级差异化（悔棋禁用 + 支招双重拒绝确认）

**Files:**
- Modify: `katrain/web/server.py:577-583`（`/api/undo`）
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`（悔棋拦截）
- Modify: `katrain/web/ui/src/kiosk/components/GameControlPanel.tsx`（按 `悔棋` 文案定位按钮，加 `disableUndo` prop）
- Test: `tests/web_ui/test_ranked_rules.py`（新）

**Interfaces:**
- Produces: ranked/rated 对局 `/api/undo` → 403 `undo not allowed in ranked games`；`GameControlPanel` 新 prop `disableUndo?: boolean`

- [ ] **Step 1: 后端失败测试**

```python
# tests/web_ui/test_ranked_rules.py
"""Ranked games must reject undo server-side (PRD R5.3/R6.1)."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from katrain.web.server import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestRankedUndo:
    def _setup_game(self, client, mode):
        session_id = client.post("/api/session").json()["session_id"]
        r = client.post("/api/game/setup", json={"session_id": session_id, "mode": mode, "settings": {"board_size": 19}})
        assert r.status_code == 200
        return session_id

    def test_ranked_undo_403(self, client):
        sid = self._setup_game(client, "ranked")
        r = client.post("/api/undo", json={"session_id": sid, "n_times": 1})
        assert r.status_code == 403

    def test_free_undo_ok(self, client):
        sid = self._setup_game(client, "free")
        r = client.post("/api/undo", json={"session_id": sid, "n_times": 1})
        assert r.status_code == 200
```

（`create_app` 的实际工厂函数名与 `/api/session`、`/api/game/setup` 的请求模型以 `server.py` 现状为准（Task 6 已通读该文件——分别在 ~500 与 673-718 行）；若 `game/setup` 必须带完整 settings，按 `AiSetupPage` 提交的字段补齐。若既有 `tests/web_ui/` 已有 TestClient fixture 样板，直接沿用。）

Run: `CI=true uv run pytest tests/web_ui/test_ranked_rules.py -v` → `test_ranked_undo_403` FAIL（现在返回 200）。

- [ ] **Step 2: 后端实现**

`server.py` `/api/undo`（577 行）函数体首行加：

```python
        session = _get_session_or_404(manager, request.session_id)
        if session.mode == "play" and getattr(session.katrain, "game_type", "free") in ("rated", "ranked"):
            raise HTTPException(status_code=403, detail="undo not allowed in ranked games")
```
（原有 `session = _get_session_or_404(...)` 行保留一处即可，勿重复。research 会话 `mode="research"` 不受影响。）

Run: 同上 → 全 PASS。

- [ ] **Step 3: 前端隐藏 + 拦截**

- `GameControlPanel.tsx`：props 接口加 `disableUndo?: boolean;`；以 `悔棋` 文案 grep 定位按钮 JSX，包裹 `{!disableUndo && ( …悔棋按钮… )}`（同组的 back/back-10/start 导航按钮一并隐藏——它们同样改变对局，包在同一条件里）。
- `GamePage.tsx`：
```tsx
  const isRanked = session.gameState?.game_type === 'ranked' || session.gameState?.game_type === 'rated';
```
  传 `<GameControlPanel … disableUndo={isRanked} />`；`handleAction` 首部加保险：
```tsx
    if (isRanked && ['undo', 'back', 'back-10', 'start'].includes(action)) return;
```

- [ ] **Step 4: 双构建 + 回归 + Commit**

```bash
cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd -
CI=true uv run pytest tests/web_ui/ tests/test_hint_api.py -q
uv run black -l 120 katrain/web/server.py tests/web_ui/test_ranked_rules.py
git add katrain/web/server.py katrain/web/ui/src tests/web_ui/test_ranked_rules.py
git commit -m "feat(web): ranked games — server-side undo ban + kiosk UI hides undo/nav"
```

（Q3 计时语义 = 视觉确认时刻 = 现状，无代码；「确认中」状态条 Task 10 已交付。hint 的 ranked 双重拒绝已由 Task 8 服务端 + Task 12 前端可见性覆盖，Task 8 测试 `test_ranked_rejected_server_side` 即验收证据。）

---

### Task 14: 漂移兜底 UX（重新定位横幅，守 D2③ 硬规则）

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/physical/PoseLostBanner.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/PoseLostBanner.test.tsx`（新）

**Interfaces:**
- Consumes: `visionStatus.poseLocked`（既有 3s 轮询）；`GeometryAPI.calibrate(trigger: 'auto' | 'manual')`（**已存在**，geometryApi.ts:85，必须传 `'manual'`——评审 Codex I4 核实；后端 `POST /api/v1/geometry/calibrate`，202）；`API.visionResetSync()`
- Produces: 对局中位姿丢失 → 横幅 + **用户手动**触发 LED 基准灯重标定按钮

**语义注**：静默无 LED 外角重标定（主路径）由 vision worker 的 auto-unlock + BoardFinder 重找机制承担，且实机精度待 P6 验证（"P12 Task 9 待硬件"）；本任务只做失败后的**用户触发**兜底——LED 基准灯只能由该按钮点亮，绝无自动路径（D2③）。

- [ ] **Step 1: 组件**

```tsx
// katrain/web/ui/src/kiosk/components/physical/PoseLostBanner.tsx
import { useState } from 'react';
import { Alert, Button } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { GeometryAPI } from '../../../api/geometryApi';
import { API } from '../../../api';

interface Props {
  visible: boolean;
}

/** Shown when board pose is lost mid-game. Recalibration (LED fiducials) is
 * STRICTLY user-triggered — hard rule D2③: LEDs never flash for geometry automatically. */
const PoseLostBanner = ({ visible }: Props) => {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  if (!visible) return null;
  const recalibrate = async () => {
    setBusy(true);
    try {
      // 签名 calibrate(trigger: 'auto' | 'manual') — geometryApi.ts:85（评审 Codex I4）。
      // 'manual' 显式声明这是用户触发（D2③ 硬规则的代码级痕迹）。
      await GeometryAPI.calibrate('manual'); // POST /api/v1/geometry/calibrate (202)
      await API.visionResetSync();
    } finally {
      setBusy(false);
    }
  };
  return (
    <Alert
      severity="warning"
      sx={{ position: 'absolute', top: 48, left: '50%', transform: 'translateX(-50%)', zIndex: 110 }}
      action={
        <Button color="inherit" size="small" disabled={busy} onClick={recalibrate}>
          {t('Re-align board', '重新定位')}
        </Button>
      }
    >
      {t('Board may have moved — recognition paused', '棋盘可能被移动，识别已暂停')}
    </Alert>
  );
};

export default PoseLostBanner;
```

（`GeometryAPI` 的导出名/函数名以 `src/api/geometryApi.ts` 实际内容为准；calibrate 不存在时按该文件的 `post` helper 补一个并顺带补其单测。）

- [ ] **Step 2: GamePage 挂载**（棋盘容器内、状态条附近）：

```tsx
        {isVisionEnabled && (
          <PoseLostBanner visible={!visionStatus.poseLocked && !!session.gameState && !session.gameState.end_result} />
        )}
```

- [ ] **Step 3: Vitest**

```tsx
// katrain/web/ui/src/kiosk/__tests__/PoseLostBanner.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PoseLostBanner from '../components/physical/PoseLostBanner';

const calibrate = vi.fn().mockResolvedValue({});
vi.mock('../../api/geometryApi', () => ({ GeometryAPI: { calibrate: (...a: unknown[]) => calibrate(...a) } }));
vi.mock('../../../api', () => ({ API: { visionResetSync: vi.fn().mockResolvedValue(undefined) } }));

it('recalibration is user-triggered only, with explicit manual trigger', async () => {
  render(<PoseLostBanner visible />);
  expect(calibrate).not.toHaveBeenCalled(); // 渲染本身绝不触发（D2③）
  fireEvent.click(screen.getByText('重新定位'));
  await waitFor(() => expect(calibrate).toHaveBeenCalledTimes(1));
  expect(calibrate).toHaveBeenCalledWith('manual'); // 评审 Codex I4
});
```

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/PoseLostBanner.test.tsx`
（mock 路径按 vitest 解析规则以测试文件相对被测组件的实际 import 说明符为准。）

- [ ] **Step 4: 双构建 + Commit**

```bash
cd katrain/web/ui && npm run build && npm run build:kiosk-2d && cd -
git add katrain/web/ui/src
git commit -m "feat(kiosk): pose-lost banner with user-triggered LED recalibration (D2 hard rule)"
```

---

### Task 15: 回归门 + 实机验证（P6，硬件在场）

**Files:**
- Create: `superpowers/tracks/kiosk-physical-play/acceptance-checklist.md`（验证记录）

- [ ] **Step 1: 全量回归门（每次实机前必跑）**

```bash
CI=true uv run pytest tests 2>&1 | tail -3        # 相对 develop@96e64f53 基线（37 failed 预存）无新增
cd katrain/web/ui && npm run build && npm run build:kiosk-2d && npx vitest run && cd -
```
Expected: pytest 失败数 ≤ 基线且失败集合是基线子集；两个构建 + verify:kiosk-2d + vitest 全绿。

- [ ] **Step 2: SBC 启动参数（实机）**

```bash
python -m katrain --ui web --port 8001 \
  --vision-model <model.onnx|.rknn> \
  --led-serial-port /dev/ttyACM0 \
  --hint-engine local --hint-top-n 3
```

- [ ] **Step 3: 按 PRD §7 验收清单逐项执行并记录**（每项在 `acceptance-checklist.md` 记 PASS/FAIL + 现象）：

1. **纯物理闭环**：19 路自由对弈整盘——只在物理盘摆子；每手 AI 灯色正确（AI 执黑红/执白绿）、灯在摆子后 ≤2 tick 熄灭；提子蓝灯与落子灯同批出现、拿除后灭；终局清灯；退出页 `led/status` 后无残灯。
2. **让子局**：AiSetupPage 设 4 子 → 开局 4 个红灯全亮 → 逐个摆黑子灯逐个灭 → AI（白）正常行棋。
3. **四类异常**：①AI 落子摆错点 → 灯不灭 + mismatch 对话框列出错点 → 纠正后自动消退；②多摆一子 → ~3s 蓝灯 + 对话框「请拿走」→ 拿走恢复；③手遮挡 10s → board_lost 遮罩 → 移开自动消退；④挪动棋盘 → PoseLostBanner → 点「重新定位」恢复。**全程观察：LED 无一次为几何自动闪灯。**
4. **AI 支招**：自由局点按钮 → 白灯 3 点闪烁 + 面板胜率/目差；显示期间故意摆子 → 不注入；关闭后再摆 → 正常注入；`--hint-engine off` 重启 → 按钮报「支招功能未开放」。
5. **升降级**：支招按钮不可见 + `curl -X POST localhost:8001/api/v1/hint -d '{"session_id":"…"}' -H 'Content-Type: application/json'` 返回 403；悔棋按钮不可见 + `/api/undo` 403；落子后「确认中」chip 出现（Q3 语义确认）。
6. **悔棋恢复**（自由局）：悔 2 手 → 蓝灯指示待拿除 2 子 + CaptureGuide → 拿除 → 继续对弈 3 手无错乱。
7. **健壮性**：对局中途拔 LED USB → 对局继续、徽标变红、无异常日志刷屏；重插 → 徽标转绿、下一次状态变化灯态恢复。拔摄像头 → 相机徽标红 + 恢复后识别回归。长考 >5 分钟 → 灯灭（失效保护）→ 下一手 AI 落子灯重新点亮。
8. **NPU（R2 风险项）**：`--vision-model *.rknn` 跑第 1 项闭环，记录单帧推理耗时与 3 帧确认端到端延迟（目标 <1s；CPU 对照 ~2s）。
9. **拥挤盘面重标定（R3 风险项）**：中盘 150+ 子时挪动棋盘 → 验证 auto-unlock → 重新定位流程的成功率与精度，记录数据（此项结果决定二期前是否需要 P12 Task 9 补强）。
10. **摆谱回归**：进摆谱页走一遍 LED 引导（下一手灯/提子闪烁/离开清灯）确认行为不变。
11. **灯态重申（评审 A 验收）**：AI 落子灯亮后长考 >5 分钟不摆子——失效保护熄灯后 ≤`led_reassert_interval_s`(240s) 内引导灯自动回亮，无需任何新状态变化；手动 `curl -X POST localhost:8001/api/v1/led/clear` 清灯后同样自动恢复。
12. **抢跑回归（评审 Codex B1 场景）**：AI 落子灯亮（未摆）→ 用户先下自己的一手 → 该手**不注入**、其位置**无蓝灯**；摆上 AI 子后 ≤3s 用户那手自动确认注入，棋谱顺序正确、无重复/非法着手日志。
13. **逃生舱**：制造持续失同步（AI 灯亮不摆）→ 30s toast → 120s 对话框弹出；「已按指示恢复」摆好后继续对弈正常；重新制造 → 「改用屏幕落子」→ LED 清灯、屏幕点击落子继续对局到终局。
14. **活子被拿走（评审 Codex B2 场景）**：对局中偷偷拿走一颗双方均未提的活子 → 走 mismatch 对话框（missing 列出该子）+ 红/绿灯指示补回，**不得**出现 CaptureGuide 秒开秒关。

- [ ] **Step 4: 记录 + 提交**

```bash
git add superpowers/tracks/kiosk-physical-play/acceptance-checklist.md
git commit -m "docs(kiosk-physical-play): acceptance run record (PRD §7)"
```

---

## Self-Review 记录（对照 PRD 需求）

- R1.1/R1.2 复用现有链路（Task 1/2 修通）；R1.3 回合色校验（Task 6 Step 5）；R1.4 现有按钮（不动，注意 `useGameSession` 的 `count` action 现为 no-op——预存问题，不在本轨道范围）。
- R2.1–R2.6：Task 3/4/6（R2.4 让子取「一次全亮」方案；R2.5 清灯在 on_unbind/end_result/shutdown 三处；R2.6 LED None 容忍 + Task 9 徽标）。
- R3.1–R3.3：Task 5/7/10/11（ambiguous_stone 后端发射为**新增**实现——低置信确认降级为询问；恢复完成 = visionResetSync 走既有 RESET_SYNC → sync.reset + 基线重建）。
- R4.1–R4.5：Task 8/12（R4.5 = HintGate 协议留接口，Q1 决定）；R7.1：Task 7（遮蔽规则 = 亮灯 ∧ 期望为空）；R7.2 长期扩类重训明确不在本计划（PRD §8 依赖表）。
- R5.1–R5.3：Task 3（残子/让子/悔棋差集同一对账循环）+ Task 5（CaptureGuide 复用）+ Task 13。
- R6：Task 13 + Task 8/12 双重拒绝。R8.1：Task 4 docstring 固化的 state-dict 抽象 + poller 的 platform gateway 分支保留。
- 已知取舍（记入验收观察项）：①Q4 暂停窗口有一帧竞态——AI 数字落子到 PAUSE 命令生效之间（~1 worker 帧），抢跑的一手可能已被确认并注入；此时它是合法的用户着手，仅温和违反「先摆 AI 子」政策，无棋局损坏（这正是弃用 hold 方案后残余的最坏情形）。②抢跑的子在等待期间会被 sync 判为 unexpected，5 帧后弹 mismatch 对话框（missing 列出 AI 子）——对话框文案兼作「请先摆 AI 子」引导；逃生舱对话框 120s 兜底。③ambiguous「忽略」后该子已进 MoveDetector 基线，靠 resetSync/恢复流兜底。④「改用屏幕落子」后本局不再自动回到物理模式（重新进对局页才重新 bind），一期接受。
