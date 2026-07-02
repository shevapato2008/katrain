# Codex Review Feedback: kiosk physical tsumego plan

审阅对象：
- `superpowers/tracks/kiosk-physical-tsumego/review-request.md`
- `superpowers/tracks/kiosk-physical-tsumego/prd.md`
- `superpowers/tracks/kiosk-physical-tsumego/plan.md`

结论：总体架构“判题在前端，所以物理编排在前端”是成立的；后端 monitor/setup 接线方向也合理。但 `plan.md` 当前不能直接开工，核心前端状态机存在事件丢失、应手竞态、答错含提子恢复、提示/试下、屏幕输入并存这些会在实机上卡死或状态分叉的问题。下面的 Blocker 建议先改计划，再实施。

## Findings

### [Blocker] `latestEvent` 单事件消费会丢关键事件，必须现在改队列

位置：`plan.md Task 8 Step 1`，`latestEvent`/`processedEventRef`；`plan.md 已知风险 #4`；现有 `useVisionSync.ts` 已维护 `syncEvents`。

判断：不要等实机出问题。丢 `setup_progress` 多数可自愈，但丢 `setup_complete` 会让 clearing/setup/replying/removing 永久卡住；丢 `move_confirmed` 会直接漏判用户物理落子。

具体修改：
- `Task 6` 给前端事件加本地递增序号，避免 `syncEvents` 被 `MAX_EVENTS` 裁剪后按数组下标处理出错。
- `Task 8` 的 hook 入参从 `latestEvent` 改为 `syncEvents`。
- 把事件处理函数拆成 `handleVisionEvent(evt)`，在 effect 中顺序消费所有 `seq > processedSeqRef.current` 的事件。

建议计划片段：

```ts
export interface VisionSyncEvent {
  seq: number; // frontend-local sequence, not from wire
  type: SyncEventType;
  data: Record<string, unknown>;
}

const nextSeqRef = useRef(0);
const handleMessage = useCallback((event: MessageEvent) => {
  const parsed = JSON.parse(event.data) as Omit<VisionSyncEvent, 'seq'>;
  const evt = { ...parsed, seq: nextSeqRef.current++ };
  setLatestEvent(evt);
  setSyncEvents((prev) => [...prev, evt].slice(-MAX_EVENTS));
}, []);
```

```ts
const processedSeqRef = useRef(-1);

useEffect(() => {
  if (!enabled) return;
  for (const evt of syncEvents) {
    if (evt.seq <= processedSeqRef.current) continue;
    processedSeqRef.current = evt.seq;
    handleVisionEvent(evt);
  }
}, [enabled, syncEvents, handleVisionEvent]);
```

### [Blocker] `replying` 会先把“用户正确手”当作“对方应手”收敛

位置：`plan.md Task 8 Step 1` 的 `phase === 'replying'` stones watcher；`useTsumegoProblem.placeStone()` 中 AI 应手是 `setTimeout(300ms)` 后落屏。

失败场景：
1. 物理 `move_confirmed` 到达，hook 调 `placeStone()`，结果为 `correct`。
2. `placeStone()` 立即把用户正确手加到 `stones`，AI 应手 300ms 后才加。
3. hook 立刻 `setPhaseBoth('replying')`。
4. `stones` effect 在 `phase === 'replying'` 下看到的第一次 `stones` 变化是“用户正确手”，于是 POST setup target 为“只有用户手、没有 AI 应手”的盘面，并点亮最后一子。
5. 物理盘本来就有用户手，可能立即 `setup_complete`，hook 回到 `ready`。
6. 300ms 后 AI 应手出现在屏幕，但 hook 已经不是 `replying`，不会再要求用户摆应手。屏幕和物理盘分叉。

具体修改：
- 不要靠“stones 的最后一子”推断应手。
- 在 `useTsumegoProblem.placeStone()` 的 `MoveResult` 增加只读元数据，不改变判题逻辑：

```ts
export interface MoveResult {
  type: 'correct' | 'incorrect' | 'solved' | 'continue';
  sound?: 'stone' | 'capture' | 'correct' | 'incorrect' | 'solved';
  captured?: number;
  scheduledReply?: { player: 'B' | 'W'; coords: [number, number] };
}
```

- `getAIResponse(matchingChild)` 存在时，`return { type: 'correct', scheduledReply: aiResponse, ... }`。
- `usePhysicalTsumego` 记录 `pendingReplyRef`，stones watcher 只在 `stones` 中已经包含这颗 `scheduledReply` 时 POST setup target 并点灯。
- 如果 `correct` 但没有 `scheduledReply`，直接 rebase expected board 并回到 `ready`，不要进入 `replying`。

### [Blocker] 答错含提子的恢复设计不正确，`undo()` 不能恢复被提子

位置：`plan.md Task 8` 说明依赖 `undo()` 的 `isFailed` 分支；`plan.md 已知风险 #5`。

当前 `useTsumegoProblem.undo()` 的 failed 分支只做 `stones.slice(0, -1)`。如果错着提走了对方子，`placeStone()` 已经通过 `removeCaptures()` 从 `stones` 删除了被提子，`slice(0, -1)` 只能移除错着，不能把被提子放回屏幕状态。物理引导即使要求用户放回，屏幕也恢复不到错着前局面。

具体修改：
- 在 `useTsumegoProblem` 内部保存 failed 前完整快照，而不是让物理 hook 自己猜：

```ts
const failedRecoveryRef = useRef<{
  stones: Stone[];
  lastMove: [number, number] | null;
  moveHistory: Stone[];
  currentNode: SGFNode | null;
  nextPlayer: 'B' | 'W';
} | null>(null);
```

- 两个 incorrect 分支在修改 `stones` 前写入快照。
- `undo()` 的 `isFailed` 分支恢复这个快照并清掉 `isFailed`。
- `usePhysicalTsumego` 的 removing UI 必须同时展示：
  - `extra`: 需要取走的子。
  - `missing`: 需要放回的子，颜色从 target board 映射出来。

泛语音可以保留，但屏幕必须明确列出“取走”和“放回”。否则含提子的错着会让用户困惑甚至卡死。

### [Blocker] 屏幕点击落子在物理模式下没有同步路径

位置：`PRD TR1` 要求物理模式下屏幕点击仍可用；`plan.md Task 9` 保留 `TsumegoBoard.onPlaceStone` 直调 `placeStone()`，但 `usePhysicalTsumego` 只处理视觉 `move_confirmed`。

失败场景：用户在屏幕上点一手正确棋，屏幕进入下一状态，物理盘少一颗用户手，随后还可能少一颗 AI 应手。当前计划没有任何 `setup target = screen stones` 的路径把物理盘拉回一致。

具体修改：
- 页面不要让屏幕点击绕过物理状态机。把 `onPlaceStone` 包成物理感知入口：

```tsx
const handleScreenPlace = (x: number, y: number) => {
  const preBoard = stonesToVisionBoard(stones, boardSize);
  const result = placeStone(x, y);
  if (result?.sound) playSound(result.sound);
  if (physical.enabled) {
    physical.onScreenMove({ x, y, result, preBoard });
  }
};
```

- `usePhysicalTsumego` 暴露 `onScreenMove` 或等效命令：
  - 正解且有 `scheduledReply`：等屏幕 AI 应手落下后，进入 setup 收敛到包含用户手和 AI 应手的目标盘面。
  - 正解且无应手：收敛到当前屏幕盘面后回 `ready`。
  - 错解：物理盘通常仍是 preBoard，可进入 removing/checking，`setup_complete` 后恢复屏幕 failed 快照。
  - solved：如果屏幕点完成题，也要先处理物理收敛或明确允许直接庆祝并清盘。

### [Blocker] 提示白灯和试下退出校验没有落地

位置：`PRD T4/TR4/TR7`；`plan.md Task 8` 只传 `paused: showHint || isTryMode`，pause effect 还会 `ledClear()`；`plan.md Self-Review` 说提示白灯由页面 hint 按钮触发，但 Task 9 没有实现。

问题：
- 提示：hook 只有 `paused`，没有 `hintCoords`，无法点白灯。即使页面先点白灯，hook 在 `paused` 变 true 后会清灯，反而擦掉提示。
- 试下：进入试下只 pause，退出时直接 `exitTryMode()` 恢复屏幕。若用户试下期间动了物理盘，退出后没有 setup 校验，下一次 move detector 的 baseline 也可能是错的。

具体修改：
- `usePhysicalTsumego` 入参拆成明确原因：

```ts
showHint: boolean;
hintCoords: [number, number] | null;
isTryMode: boolean;
```

- hint true：`visionPause(true)`，对白灯做单点闪烁或常亮；hint false：`visionPause(false)` 并重新发当前 phase 的 LED frame。
- 页面 wrap `exitTryMode`：物理模式下先退出屏幕试下，然后进入 `restoring`/setup target = 当前屏幕盘面；完成后才回 `ready` 并 `visionExpectedBoard(target)`。
- 计划里要新增测试覆盖：提示期间 `move_confirmed` 不会调用 `placeStone`；退出试下且物理盘不一致时进入恢复引导。

### [Blocker] monitor 下 move 检测 gating 过粗，setup complete 后没有可靠 rebase

位置：`plan.md Task 2/3` 的 `should_detect_moves(bound, monitor, paused, sync_state)`；`plan.md Task 1` setup complete 只更新 `SyncStateMachine._expected_board`。

严格相等本身是对的，但 `monitor && sync_state == "synced"` 不足以表达“现在轮到用户下棋”。清盘 complete 后、初始摆放 complete 后、reply/removing complete 后都会短暂进入 `SYNCED`。这些阶段是否允许 move detection 应由前端相位显式控制，而不是用 sync state 间接推断。

具体修改：
- 增加显式 move arm 命令，例如 `CommandType.SET_MOVE_DETECTION` 或把 monitor mode 拆成 `{ feed_sync: true, detect_moves: boolean }`。
- gating 改为：

```python
def should_detect_moves(bound: bool, monitor: bool, paused: bool, sync_state: str, move_armed: bool) -> bool:
    if paused:
        return False
    if bound:
        return True
    return monitor and move_armed and sync_state == "synced"
```

- hook 只在 `phase === 'ready'` 后调用 `visionMoveDetection(true)`；clearing/setup/replying/removing/solved/hint/try 都 false。
- worker 在 setup complete 时应同步 `MoveDetector` baseline：

```python
events = self._sync.update(...)
if any(evt.type == SyncEventType.SETUP_COMPLETE for evt in events):
    self._move_detector.force_sync(observed_board)
```

这可以避免 setup 刚完成后 move detector 仍拿旧基线比较。

### [Major] `/ws/vision` 是破坏性单消费者队列，不能只靠“做题页只开一条”

位置：`plan.md 已知风险 #3`；当前 `server.py /ws/vision` 每个连接都调用 `vision.poll_events()`，`VisionService.poll_events()` 会把 worker queue drain 掉。

判断：按当前实现，多开一个页面或未来复用一个 vision overlay，就会把 `setup_complete`/`move_confirmed` 分流给不同连接。这个问题和 `latestEvent` 一样会造成状态机卡死。

具体修改二选一：
- 首选：server 端做 fan-out。只有一个后台 task drain worker events，然后把 dict event 广播给所有 `/ws/vision` 连接；每个连接不再直接 `poll_events()`。
- 简化版：明确 `/ws/vision` 只允许一个连接，后来的连接关闭旧连接或拒绝，并在代码和测试中锁定。

另外要把 dict 事件和 `ConfirmedMove` dataclass 的分流契约写进 `VisionService`/server 注释，并加测试：monitor move 必须进 WS，bound move 必须进 game poller。

### [Major] `celebrate()` 没有 abort，换题清盘后旧闪烁还会继续写 LED

位置：`plan.md Task 8` `celebrate()`；审阅问题 A4。

具体修改：
- 给 hook 增加 `runIdRef` 或 `AbortController`。
- enabled/restartKey/problemKey 变化、unmount、进入 clearing/setup 时递增 run id。
- `celebrate(runId)` 每次 `await` 后检查 run id，不匹配就停止，不再 `ledPoints()`/`ledClear()`。

```ts
const runIdRef = useRef(0);
const nextRun = () => { runIdRef.current += 1; return runIdRef.current; };

const celebrate = useCallback(async (runId: number) => {
  for (let i = 0; i < 2; i++) {
    if (runId !== runIdRef.current) return;
    ledPoints(pts);
    await delay(350);
    if (runId !== runIdRef.current) return;
    ledClear();
    await delay(250);
  }
}, [ledPoints, ledClear]);
```

### [Major] Task 9 的 restartKey 设计绕且有笔误，直接用 problem key

位置：`plan.md Task 9 Step 3(g)`。

问题：
- `physicalEnabled = ... && physicalCycle >= 0` 是恒 true 条件。
- `physicalCycle` 只是在模拟 key，但 hook 本来可以直接接收 `problemId`/`problem.id`。
- 若 problemId 变化时 `problem` 还没加载完成，不能用旧 `stones` 启动新题的 clearing/setup。

具体修改：

```tsx
const physicalProblemReady = !!problem && problem.id === problemId && boardSize === 19;
const physicalEnabled = physicalMode && physicalAvailable && physicalProblemReady;

const physical = usePhysicalTsumego({
  enabled: physicalEnabled,
  problemKey: problem?.id ?? null,
  ...
});
```

hook 的 enable lifecycle 依赖 `[enabled, problemKey]`。不需要 `physicalCycle`。

### [Major] `BoardSetupGuide` 的 matched/total 口径错误

位置：`plan.md Task 9 Step 3(e)`；审阅问题 C10。

当前：

```tsx
matched={(stones.length) - physical.missing.length - (physical.stage === 'black' ? 0 : 0)}
total={stones.length}
```

问题：
- 三元表达式恒为 0。
- `stones.length` 是全目标总数，`physical.missing` 是当前 stage 的 missing，黑/白阶段口径不一致，白阶段会虚高。

具体修改：
- 让 `usePhysicalTsumego` 返回 stage 内口径：

```ts
stageMatched: number;
stageTotal: number;
```

- setup progress 中计算：

```ts
const activeMissing = stage === 'black' ? missingBlack : missingWhite;
const activeTotal = countTargetColor(targetBoard, stage === 'black' ? 1 : 2);
setStageTotal(activeTotal);
setStageMatched(activeTotal - activeMissing.length);
```

- 页面直接：

```tsx
<BoardSetupGuide
  matched={physical.stageMatched}
  total={physical.stageTotal}
  missing={physical.missing}
  extra={physical.extra}
  stage={physical.stage}
  ...
/>
```

### [Major] setup `extra` 应覆盖“目标点上颜色不对”的子

位置：`plan.md Task 1` `_check_setup`。

当前计划的 `extra` 只包含 `(target == EMPTY) & (observed != EMPTY)`。如果目标是黑棋，但观测为白棋，这个点会被列入 `missing`，却不会列入 `extra`，用户只会看到“这里缺黑棋”，但实际上该点已被白棋占着，必须先取走。

具体修改：

```python
missing = [
    [int(r), int(c)]
    for r, c in zip(*np.where((self._target_board != EMPTY) & (observed_board != self._target_board)))
]

extra = [
    [int(r), int(c), int(observed_board[r, c])]
    for r, c in zip(*np.where((observed_board != EMPTY) & (observed_board != self._target_board)))
]
```

这样错色点会同时出现在 missing 和 extra 中，UI 可以提示“取走此处白子，放上黑子”。

### [Major] 前端测试计划低估了现有能力，必须加 hook/reducer 测试

位置：`plan.md 审阅问题 C11`；计划正文 Task 6/7/8/9 主要靠 build 和实机。

判断：值得测，而且不需要引入新框架。仓库已有 `vitest`、`@testing-library/react` 和 `renderHook` 用例。

具体修改：
- 把 `usePhysicalTsumego` 的相位转换抽成纯 reducer，例如：

```ts
type PhysicalEvent =
  | { type: 'setup_progress'; missing: ...; extra: ... }
  | { type: 'setup_complete' }
  | { type: 'move_confirmed'; row: number; col: number; color: number }
  | { type: 'screen_move'; result: MoveResult | null; ... };
```

- reducer 只返回新 state 和 declarative commands，例如 `[{ kind: 'visionSetupMode', board }, { kind: 'ledPoints', points }]`。
- hook 负责执行 commands。
- Vitest 覆盖至少这些场景：
  - setup_complete 不丢，clearing -> setup -> ready。
  - correct move with scheduledReply 不会在用户手 stones 更新时提前 ready。
  - incorrect capture 恢复需要 missing+extra。
  - screen click in physical mode 进入 convergence。
  - hint pauses and lights white, exit restores LEDs.
  - try exit mismatch enters restoring, not ready.

### [Major] `physicalAvailable` 应使用 recognition_ready 和 boardSize==19，不只是 `isVisionEnabled`

位置：`plan.md Task 9 Step 3(c)` 和已知风险 #6。

当前 `VisionContext` 已从 `/api/v1/vision/status` 响应拿到后端字段的机会，但类型只保留 enabled/camera/pose/sync/bound。`physicalAvailable = isVisionEnabled` 会允许 camera/model/geometry 还没 ready 时打开物理模式。

具体修改：
- 扩展 `VisionStatus`：

```ts
recognitionReady: boolean;
geometryReady: boolean;
modelReady: boolean;
```

- `mapResponse` 映射 `recognition_ready`。
- 页面：

```ts
const physicalAvailable = visionStatus.enabled && visionStatus.recognitionReady && boardSize === 19;
```

### [Major] 物理落子没有播放既有做题音效，三通道反馈不完整

位置：`plan.md Task 8` 只使用 `useVoice()`；页面的 `playSound(result.sound)` 只在屏幕 `onPlaceStone` 里执行。

具体修改：
- `usePhysicalTsumego` 入参增加：

```ts
playMoveSound: (sound: MoveResult['sound']) => void;
```

- physical `move_confirmed` 调 `placeStone()` 后，如果 `result?.sound` 存在，调用 `playMoveSound(result.sound)`。
- `solved` 可继续播现有 victory，同时语音“答对了”作为附加提示。不要用语音替代原有音效。

### [Major] auto-advance 在物理模式下被直接禁用，和 PRD 的“换题清盘”闭环不一致

位置：`plan.md Task 9 Step 3(f)`；`PRD §3/§4 TR7`。

计划把 `autoAdvanceEnabled` 改成 `... && !physicalMode`。这避免了旧题庆祝和新题清盘竞态，但也改变了“答对后 auto-advance / 下一题 -> 清盘 -> 下一题摆放”的体验。

具体修改二选一：
- 如果 v1 决定禁用物理 auto-advance，PRD 和验收标准要明确改口。
- 更好：保留 auto-advance 设置，但在 physical mode 下把它解释成“进入 pending next 状态”，先清盘，清盘 `setup_complete` 后再 `navigateToProblem(nextId)`。

### [Minor] pause 全局布尔可接受，但计划要写清楚单一 owner 和 cleanup

位置：`plan.md Task 4/8`；审阅问题 B9。

单页面内 `paused = showHint || isTryMode` 可以规避 hint 和 try 同时开启时的引用计数问题，因为 React 只向后端发送聚合后的布尔值。但前提是同一时间只有一个页面拥有 physical monitor。

建议：
- 文档里明确 pause 是“single owner aggregate boolean”。
- cleanup 必须始终 `visionPause(false)`。
- 若以后允许多个页面/组件控制 pause，再改成 `{source, paused}` 或 pause reasons set。

### [Minor] monitor/bound worker 行为测试不够

位置：`plan.md Task 2/3`；审阅问题 B7。

`should_detect_moves(bound=True, ...)` 不看 sync_state 是为了不回归对弈路径，这个决定可以接受。但 Task 3 的测试只验证 service command，不验证两个 worker：
- monitor=true 且 move_armed=true 时发 dict `move_confirmed`。
- bound=true 时仍发 `ConfirmedMove` dataclass。
- paused=true 时两者都不检测。
- `SET_MONITOR false` 应 reset sync 和 move detector baseline。

建议补一个小的 worker-level 单测或更窄的 fake detector/extractor 测试，至少锁住分流契约。

## Answers To The 13 Review Questions

1. **事件消费**：必须现在改成队列式消费。`latestEvent` 不能承载 `setup_complete`/`move_confirmed` 这种一次性关键事件。
2. **replying 收敛**：当前方案有顺序竞态，会把用户正确手误当应手。用 `scheduledReply` 元数据或 callback 等待 AI 应手真实落屏幕后再 setup。
3. **答错含提子**：当前简化不可接受。需要 failed 前快照恢复屏幕状态，并在 removing UI 同时展示 take off 和 put back。
4. **solved 时序**：`celebrate()` 必须有 abort/run id。否则换题清盘后旧闪烁会污染新题 LED。
5. **restartKey 接线**：不要用 `physicalCycle`。直接把 `problemKey` 传入 hook，依赖 `[enabled, problemKey]`，并确保 problem 数据匹配当前 route。
6. **`_check_setup` 严格相等**：严格相等正确；但 setup complete 后要 rebase MoveDetector，并且 monitor move detection 需要显式 arm，不能只看 `SYNCED`。
7. **gating 函数语义**：bound 路径不看 sync_state 可以保留；monitor 路径应增加 `move_armed`。两个 worker 都要加等价测试，别只测 service。
8. **事件路由**：dict/dataclass 分流可用，但要注释和测试锁定。`/ws/vision` 单消费者不够稳，建议改 fan-out 或强制单连接。
9. **REST/pause 设计**：kiosk 单机无鉴权可以接受。pause 全局布尔在单一页面 owner 下可接受，但必须传聚合状态并清理；多 owner 时要改 scoped/ref-count。
10. **matched 计算**：计划里的表达式是错的。让 hook 返回 stageMatched/stageTotal，BoardSetupGuide 直接消费当前阶段口径。
11. **TDD 结构**：应该加前端 unit/hook 测试。仓库已经有 Vitest 和 renderHook，不需要新测试栈。建议抽 reducer 测相位机。
12. **遗漏检查**：计划遗漏或未真正落地：提示白灯、试下退出校验、屏幕输入并存、物理落子的既有音效、物理 auto-advance 清盘闭环；另外 boardSize/recognition_ready gate 要修。
13. **屏幕/物理双输入**：这是当前计划的真空白。必须让屏幕点击走物理收敛路径，否则屏幕和实体盘会立即分叉。
