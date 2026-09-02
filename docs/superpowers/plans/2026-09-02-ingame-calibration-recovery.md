# 对局内标定恢复 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「棋盘被移动」的警告在该响的时候响、不该响的时候不响，并且在对局屏上永远有一条走得通、不用弃局的重新标定出路。

**Architecture:** 弹窗现在挂在错误的信号上（`pose_locked` 其实是「这一局绑上了没有」），改接真正的漂移信号 `geometry.phase === 'degraded'`；把 `key` 从布尔值改成「本次告警周期」的计数器，让消失走退场动画而不是卸载；把 backdrop/Esc 从「关闭」里摘出去；对局屏页控条补一颗常驻的「重新标定」；`PhysicalBoardGuard` 对对弈路由改成**进门判一次的闩**，不再把正在进行的对局整屏换掉。**后端契约不动** —— 需要的信号 `geometry.phase` 已经存在且前端已经在消费它。

**Tech Stack:** React 19 / TypeScript / MUI 5 / react-router v6 / vitest + @testing-library/react；板上 kiosk 是 Chromium 全屏触摸屏，1024×600。

**Spec:** `docs/superpowers/plans/2026-09-02-physical-board-spec.md`

## Global Constraints

- 仓库 `vendor/katrain`（子模块），前端根目录 `katrain/web/ui`。分支从 `develop` 切出。
- **D2③ 硬规则：LED 绝不为几何标定自动闪灯。** 本计划新增的入口全部由用户点击触发。
- 不得破坏现有测试：`npm test` 当前 `GamePage`(两份) + `PhysicalBoardGuard` 44/44、15 个 vision spec 66/66 全绿。**读退出码**，不要只读好看的数字。
- 状态必须诚实：加载中不得画成「坏了」，未绑定不得画成「标定丢失」。
- **jsdom 无权对「真浏览器里的挂载时序与 MUI 过渡表现」作证**（spec §3 R2）。凡结论属于这一类的，必须在板上用 CDP 复核；本计划把这类验收单列在每个任务的最后一步。
- 前端改动上板后必须 `Page.reload(ignoreCache=True)`，否则 kiosk 拿的还是旧包。

---

### Task 1: VisionContext 说实话 —— 加载态与字段改名

`poseLocked` 这个名字读起来是「位姿锁住了」，而它的真实含义是「这一局绑上了没有」（`worker_inprocess.py:468-470`）。名字本身就是这次 bug 的成因，先把它改对；顺带补上 `GeometryContext` 早就有、而 `VisionContext` 缺的 `loaded` 布尔。

**Files:**
- Modify: `src/kiosk/context/VisionContext.tsx`
- Modify: `src/api.ts:518-519`（补 `res.ok` 检查）
- Test: `src/kiosk/__tests__/VisionContext.test.tsx`（新建）

**Interfaces:**
- Produces: `VisionStatus.sessionBound: boolean`（原 `poseLocked`，语义不变、名字改对）；`VisionContextType.loaded: boolean`（首次成功轮询之后为 true）。
- 后端契约 **不动**：`/api/v1/vision/status` 仍返回 `pose_locked`，映射在 `mapResponse` 里完成。

- [ ] **Step 1: 写失败测试**

新建 `src/kiosk/__tests__/VisionContext.test.tsx`：

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, test, vi, beforeEach } from 'vitest';
import { VisionProvider, useVision } from '../context/VisionContext';
import { API } from '../../api';

vi.mock('../../api', () => ({ API: { visionStatus: vi.fn() } }));

const Probe = () => {
  const { visionStatus, loaded } = useVision();
  return <div data-testid="probe">{`${loaded}|${visionStatus.sessionBound}`}</div>;
};

describe('VisionContext', () => {
  beforeEach(() => vi.mocked(API.visionStatus).mockReset());

  test('loaded 在首次轮询回来之前是 false —— 「还没问过」不许画成「后端说了 false」', async () => {
    let resolve: (v: unknown) => void = () => {};
    vi.mocked(API.visionStatus).mockReturnValue(new Promise((r) => { resolve = r; }));

    render(<VisionProvider><Probe /></VisionProvider>);
    expect(screen.getByTestId('probe').textContent).toBe('false|false');

    resolve({ enabled: true, camera_connected: true, pose_locked: true, sync_state: 'synced',
              bound_session_id: 'g1', recognition_ready: true, led_connected: true });
    await waitFor(() => expect(screen.getByTestId('probe').textContent).toBe('true|true'));
  });

  test('取数失败保留上一次的值,且 loaded 不回退', async () => {
    vi.mocked(API.visionStatus)
      .mockResolvedValueOnce({ enabled: true, camera_connected: true, pose_locked: true,
                               sync_state: 'synced', bound_session_id: 'g1',
                               recognition_ready: true, led_connected: true } as never)
      .mockRejectedValue(new Error('boom'));

    render(<VisionProvider><Probe /></VisionProvider>);
    await waitFor(() => expect(screen.getByTestId('probe').textContent).toBe('true|true'));

    vi.advanceTimersByTime?.(3100);
    await waitFor(() => expect(screen.getByTestId('probe').textContent).toBe('true|true'));
  });
});
```

- [ ] **Step 2: 跑测试确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/VisionContext.test.tsx`
Expected: FAIL —— `visionStatus.sessionBound` 是 `undefined`，`loaded` 不存在

- [ ] **Step 3: 实现**

`src/kiosk/context/VisionContext.tsx`：

```tsx
export interface VisionStatus {
  enabled: boolean;
  cameraConnected: boolean;
  /** 后端 `pose_locked`。**它不是「几何标定还在不在」** —— worker_inprocess.py:468-470 里
   *  它是 `sync.state ∉ {UNBOUND, CALIBRATING}`,即「这一局的视觉会话绑上了没有」。
   *  真正的「棋盘被移动」信号是 GeometryContext 的 `phase === 'degraded'`。
   *  改名就是为了防止再有人拿它当标定位用(见 spec §2.4)。 */
  sessionBound: boolean;
  syncState: string;
  boundSessionId: string | null;
  recognitionReady: boolean;
  ledConnected: boolean | null;
}

interface VisionContextType {
  visionStatus: VisionStatus;
  /** 首次成功轮询之后才为 true。DEFAULT_STATUS 里那些 false 是**占位**不是事实,
   *  任何「未就绪就报警」的判据都必须先过这道闸。 */
  loaded: boolean;
  isVisionEnabled: boolean;
  refreshStatus: () => Promise<void>;
}

const DEFAULT_STATUS: VisionStatus = {
  enabled: false,
  cameraConnected: false,
  sessionBound: false,
  syncState: 'idle',
  boundSessionId: null,
  recognitionReady: false,
  ledConnected: null,
};

const mapResponse = (r: VisionStatusResponse): VisionStatus => ({
  enabled: r.enabled,
  cameraConnected: r.camera_connected,
  sessionBound: r.pose_locked,
  syncState: r.sync_state,
  boundSessionId: r.bound_session_id,
  recognitionReady: r.recognition_ready ?? false,
  ledConnected: r.led_connected ?? null,
});
```

Provider 内加 `loaded`：

```tsx
  const [visionStatus, setVisionStatus] = useState<VisionStatus>(DEFAULT_STATUS);
  const [loaded, setLoaded] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      const response = await API.visionStatus();
      setVisionStatus(mapResponse(response));
      setLoaded(true);
    } catch (err) {
      console.error('Failed to fetch vision status', err);
      // Keep the last known status on transient errors rather than
      // resetting to defaults, so the UI does not flicker.
      // loaded 同理不回退:读到过一次就不再是「没问过」。
    }
  }, []);
```

Provider 的 value 加上 `loaded`。

`src/api.ts:518-519` 补 `res.ok`（没有它，任何非 2xx 但 body 是合法 JSON 的响应都会把全部字段写成 `undefined`）：

```ts
  visionStatus: async (): Promise<VisionStatusResponse> => {
    const res = await fetch('/api/v1/vision/status');
    if (!res.ok) throw new Error(`vision status ${res.status}`);
    return res.json();
  },
```

- [ ] **Step 4: 机械改名 3 个消费点 + 测试 mock**

`src/kiosk/pages/GamePage.tsx:406 / :423 / :623` 的 `visionStatus.poseLocked` 改成 `visionStatus.sessionBound`
（**语义留到 Task 2/3 再改，本步只改名，保持行为逐字不变**）。
测试 mock：`GamePage.test.tsx:49`、`GamePageEngine.test.tsx`、`GamePageLedBadge.test.tsx`、
`TsumegoProblemPage.test.tsx` 里的 `poseLocked:` 键名同步改。

- [ ] **Step 5: 跑全套确认它绿**

Run: `cd katrain/web/ui && npm test; echo "exit=$?"`
Expected: `exit=0`，且原有 44/44 + 66/66 数量不变（**改名不该改变任何测试数量**）

- [ ] **Step 6: 提交**

```bash
git add katrain/web/ui/src
git commit -m "refactor(kiosk): VisionStatus.poseLocked 改名 sessionBound 并补 loaded 与 res.ok

pose_locked 的真实语义是「会话绑上了没有」,不是「标定还在不在」。
名字是 spec §2.4 那个 bug 的成因,本次只改名与加载态,行为逐字不变。"
```

---

### Task 2: RecalibrationModal 接对信号、修 key 与 dismissed

**Files:**
- Modify: `src/kiosk/components/game/RecalibrationModal.tsx`
- Modify: `src/kiosk/pages/GamePage.tsx:406 / :621-629`
- Test: `src/kiosk/__tests__/RecalibrationModal.test.tsx`（新建 —— 这个组件目前**连 spec 文件都没有**）

**Interfaces:**
- Consumes: `useGeometry().status.phase`（`'required' | 'waiting_empty' | ... | 'ready' | 'degraded' | 'failed' | 'cancelled'`，`src/api/geometryApi.ts:18`）与 `status.error`。
- Produces: `RecalibrationModal` 新增 props `open: boolean`、`onDismiss: () => void`（父组件持有 dismissed 状态），**移除**组件内部的 `dismissed`。

- [ ] **Step 1: 写失败测试**

新建 `src/kiosk/__tests__/RecalibrationModal.test.tsx`：

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import RecalibrationModal from '../components/game/RecalibrationModal';

const setup = (props = {}) =>
  render(<RecalibrationModal open onDismiss={vi.fn()} {...props} />);

describe('RecalibrationModal', () => {
  test('点背景不关闭 —— 触摸屏上一次误触不该让唯一的标定出口消失', () => {
    const onDismiss = vi.fn();
    setup({ onDismiss });

    // MUI Dialog 的 backdrop 关闭要先 mousedown 再 click,且都打在 .MuiDialog-container 上。
    const container = document.querySelector('.MuiDialog-container') as HTMLElement;
    fireEvent.mouseDown(container);
    fireEvent.click(container);

    expect(onDismiss).not.toHaveBeenCalled();
    expect(screen.getByText('棋盘可能被移动')).toBeInTheDocument();
  });

  test('按 Escape 不关闭', () => {
    const onDismiss = vi.fn();
    setup({ onDismiss });

    fireEvent.keyDown(document.querySelector('.MuiDialog-root') as HTMLElement, { key: 'Escape' });

    expect(onDismiss).not.toHaveBeenCalled();
  });

  test('只有「仍要继续」这颗键会关闭,而且是通知父组件而不是自己记账', () => {
    const onDismiss = vi.fn();
    setup({ onDismiss });

    fireEvent.click(screen.getByText('仍要继续'));

    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 跑测试确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/RecalibrationModal.test.tsx`
Expected: FAIL —— 前两条会红（backdrop / Escape 当前会触发 `handleDismiss`）

- [ ] **Step 3: 实现 RecalibrationModal**

```tsx
interface Props {
  open: boolean;
  /** 用户显式按下「仍要继续」。**父组件持有这个状态** —— 组件内部的本地 dismissed
   *  加上 `key={String(poseLocked)}` 那套复位机制,正是 spec §2.5 机制 β 的成因。 */
  onDismiss: () => void;
}

const RecalibrationModal = ({ open, onDismiss }: Props) => {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recalibrate = async () => { /* 原样保留,不动 */ };

  return (
    <Dialog
      open={open}
      // backdrop 与 Escape **不关闭**:这是 kiosk 触摸屏上一块阻塞式告警,
      // 唯一的关闭方式是显式按「仍要继续」。MUI 默认会把这两者都送进 onClose
      // (RecalibrationModal 旧版正是这样把自己闩死的)。
      onClose={(_event, reason) => { if (reason !== 'backdropClick') onDismiss(); }}
      disableEscapeKeyDown
      maxWidth="xs"
      fullWidth
    >
      {/* DialogTitle / DialogContent 原样保留 */}
      <DialogActions sx={{ justifyContent: 'center', gap: 1.5, pb: 2.5 }}>
        <Button onClick={onDismiss} sx={{ color: 'text.secondary' }}>
          {t('Continue anyway', '仍要继续')}
        </Button>
        <Button variant="contained" color="warning" disabled={busy} onClick={recalibrate}>
          {t('Recalibrate', '重新标定')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
```

- [ ] **Step 4: 实现 GamePage 侧（信号 + 周期 key + 不再按 physicalPlay 挂载）**

`src/kiosk/pages/GamePage.tsx`，在 `recalOpen` 处：

`GamePage.tsx` 顶部补两处 import / 解构（**当前文件里没有 `useGeometry`**）：

```tsx
import { useGeometry } from '../context/GeometryContext';
// ...
  const { visionStatus, loaded: visionLoaded, isVisionEnabled, refreshStatus } = useVision();
```

然后在 `recalOpen` 处：

```tsx
  const { status: geometryStatus } = useGeometry();
  // 真正的「棋盘被移动」信号:漂移监视器写的 phase='degraded' / error='board_moved'
  // (geometry_calibration_service.py:266-282)。
  // **不要**用 visionStatus.sessionBound —— 它只说明这一局绑上了没有,未绑定时为 false,
  // 于是每一局都会在绑定窗口里误报一次(spec §2.4/§2.5)。
  const boardDisplaced = geometryStatus.phase === 'degraded';
  const recalOpen = physicalPlay && boardDisplaced && !isGameOver;

  // 用户按过「仍要继续」之后本轮不再打扰;新的一轮告警(degraded 重新升起)才复位。
  const [recalDismissed, setRecalDismissed] = useState(false);
  useEffect(() => { if (!boardDisplaced) setRecalDismissed(false); }, [boardDisplaced]);
```

渲染处（当前 `:621-629`）改成 **不按 `physicalPlay` 挂载**，照 `EngineMoveErrorDialog`
（`:846-855` 那段注释说的）同款「永远挂载、只 gate prop」：

```tsx
      {/* 永远挂载,只 gate `open`。按 physicalPlay 挂载会在它翻假时把弹窗直接卸载 ——
          没有退场动画、看起来就是「自己突然消失」(spec §2.5)。这正是 :846-855
          给 EngineMoveErrorDialog 打过的那个补丁,这里补上同一个。 */}
      <RecalibrationModal
        open={recalOpen && !escalationOpen && !recalDismissed}
        onDismiss={() => setRecalDismissed(true)}
      />
```

**删掉** `key={String(...)}` 与 `onClose={() => undefined}`。

- [ ] **Step 5: 补一条 GamePage 级的回归测试**

追加到 `src/kiosk/__tests__/GamePage.test.tsx`（沿用该文件既有的 mock 骨架）：

```tsx
  it('未绑定(sessionBound=false)不再弹「棋盘可能被移动」—— 那是假警报', async () => {
    mockIsVisionEnabled = true;
    mockSessionBound = false;          // 进对局那一刻的常态
    mockGeometryPhase = 'ready';       // 几何是好的
    renderGamePage();

    expect(screen.queryByText('棋盘可能被移动')).not.toBeInTheDocument();
  });

  it('几何 degraded 时才弹,且 sessionBound 翻 true 不会把它弄消失', async () => {
    mockIsVisionEnabled = true;
    mockGeometryPhase = 'degraded';
    mockSessionBound = false;
    const { rerender } = renderGamePage();
    expect(await screen.findByText('棋盘可能被移动')).toBeInTheDocument();

    mockSessionBound = true;           // 绑定完成 —— 与「棋盘被没被挪」无关
    rerender(<GamePageUnderTest />);

    expect(screen.getByText('棋盘可能被移动')).toBeInTheDocument();
  });
```

> ⚠️ `mockGeometryPhase` / `renderGamePage` / `GamePageUnderTest` 要按该文件现有的 mock 写法接进去
> （现有文件用的是模块级 `let mockPoseLocked` + `vi.mock`）。照抄它的骨架，别另起一套。

- [ ] **Step 6: 跑全套确认它绿**

Run: `cd katrain/web/ui && npm test; echo "exit=$?"`
Expected: `exit=0`

- [ ] **Step 7: 变异验证 —— 要红得对**

把 `boardDisplaced` 改回 `!visionStatus.sessionBound`，重跑：
第一条新用例（「未绑定不再弹」）**必须红**。红了改回来。
再把 `disableEscapeKeyDown` 删掉：`RecalibrationModal.test.tsx` 的 Escape 那条**必须红**。

- [ ] **Step 8: 提交**

```bash
git add katrain/web/ui/src
git commit -m "fix(kiosk): 重标定弹窗改接 geometry degraded,并停止用 key 当 dismissed 复位器

修 spec §2.5 的两条机制:α(pose_locked 语义错位导致误报,再随 key 翻转被卸载)
与 β(backdrop/Esc 把弹窗闩死)。"
```

- [ ] **Step 9: 板上验收（jsdom 在这一条上无权作证）**

按 `project_board_kiosk_cdp_acceptance` 的配方连 `:9222`，开一局实体自由对弈，然后：

```python
# 进对局后连续读 30 秒,确认整个绑定窗口里弹窗都没出现过
Runtime.evaluate: [...document.querySelectorAll('.MuiDialog-root')]
    .some(d => d.innerText.includes('棋盘可能被移动'))
```
Expected：全程 `false`。
再人为把棋盘挪动一格触发漂移，确认弹窗出现**且不会自己消失**；点背景 3 次，确认它**还在**。

---

### Task 3: 开关排那句话改判据

`hardwareFault` 用 `sessionBound === false` 报「标定丢失 · 请重新标定」，同样的错位；而且它现在是**纯文本、不可点**（`GameControlPanel.tsx:421-428`）。

**Files:**
- Modify: `src/kiosk/pages/GamePage.tsx:421-425`
- Test: `src/kiosk/__tests__/GamePage.test.tsx`

**Interfaces:**
- Consumes: Task 1 的 `loaded`、Task 2 的 `boardDisplaced`。

- [ ] **Step 1: 写失败测试**

```tsx
  it('未加载时一句硬件故障都不报 —— 占位的 false 不是事实', () => {
    mockVisionLoaded = false;
    mockIsVisionEnabled = true;
    mockCameraConnected = false;   // DEFAULT_STATUS 的占位值
    renderGamePage();

    expect(screen.queryByText(/摄像头未连接/)).not.toBeInTheDocument();
  });

  it('绑定中说「正在对准棋盘」,不说「标定丢失」', () => {
    mockVisionLoaded = true;
    mockIsVisionEnabled = true;
    mockSessionBound = false;
    mockGeometryPhase = 'ready';
    renderGamePage();

    expect(screen.queryByText(/标定丢失/)).not.toBeInTheDocument();
    expect(screen.getByText(/正在对准棋盘/)).toBeInTheDocument();
  });
```

- [ ] **Step 2: 跑测试确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GamePage.test.tsx -t 硬件`
Expected: FAIL

- [ ] **Step 3: 实现**

```tsx
  // 硬件故障那一句。优先级按「不修就没法下」排:摄像头 > 标定 > LED。
  // `ledConnected === null` 是**后端没说**,不是「没连上」—— 不报。
  // 同理:`loaded === false` 是**还没问到**,整段都不许报(spec §2.9)。
  const hardwareFault = !physicalPlay || !visionLoaded ? null
    : visionStatus.cameraConnected === false ? t('vision:camera_down', '摄像头未连接 · 已转触屏')
    : boardDisplaced ? t('vision:board_moved', '棋盘被移动 · 需重新标定')
    : visionStatus.sessionBound === false ? t('vision:binding', '正在对准棋盘…')
    : visionStatus.ledConnected === false ? t('vision:led_down', 'LED 未连接 · 不再亮灯引导')
    : null;
```

- [ ] **Step 4/5: 跑测试 + 提交**

Run: `cd katrain/web/ui && npm test; echo "exit=$?"` → `exit=0`

```bash
git add katrain/web/ui/src
git commit -m "fix(kiosk): 开关排硬件故障句改判据,未加载不报、绑定中说实话"
```

---

### Task 4: 补齐新增失败原因的文案

计划一新增了三个 `reason` 取值，而 `not_enough_inliers` **从来就没有前端分支**（板上 bundle grep 0 命中）。契约要求：声明的取值必须有人消费。

**Files:**
- Modify: `src/kiosk/components/vision/GeometryCalibrationScreen.tsx:78-110`（`buildDiagnostic`）
- Test: `src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx`

**Interfaces:**
- Consumes: 计划一 Task 3/6 产生的 `frame_overexposed` / `frame_underexposed` / `too_few_anchors`，以及既有的 `not_enough_inliers`。

- [ ] **Step 1: 写失败测试**

```tsx
  test.each([
    ['frame_overexposed', /太亮/],
    ['frame_underexposed', /太暗/],
    ['too_few_anchors', /找到的定位点太少/],
    ['not_enough_inliers', /对不上一个棋盘/],
  ])('%s 有专属文案,不落兜底', (raw, pattern) => {
    renderScreen({ phase: 'failed', error: raw, last_valid: true });
    expect(screen.getByText(pattern)).toBeInTheDocument();
    expect(screen.queryByText('这次标定没有完成')).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: 跑测试确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx -t 专属文案`
Expected: FAIL —— 四条全部落进兜底「这次标定没有完成」

- [ ] **Step 3: 实现**

在 `buildDiagnostic`（`:78` 起）的 `board_moved` 分支之后插入：

```tsx
  if (raw === 'frame_overexposed') {
    return {
      title: '现在太亮了，看不见盘下的灯',
      body: '标定靠的是「熄灯拍一张、亮灯再拍一张，两张相减」。阳光或顶灯把盘面照到发白时，这个差就没了。',
      action: '拉上窗帘或关掉顶灯，把房间调暗一些再重新开始标定。',
      detail: raw,
    };
  }
  if (raw === 'frame_underexposed') {
    return {
      title: '现在太暗了，摄像头什么都看不见',
      body: '整幅画面接近全黑，连棋盘边框都找不出来。',
      action: '开一盏灯，让棋盘有基本的照明，再重新开始标定。',
      detail: raw,
    };
  }
  if (raw === 'too_few_anchors') {
    return {
      title: '找到的定位点太少',
      body: '十三个定位点里至少要认出九个才能算出棋盘的位置，这次不够。',
      action: '把盘面清空、把房间调暗一些，再重新开始标定。',
      detail: raw,
    };
  }
  if (raw === 'not_enough_inliers') {
    return {
      title: '认出来的点拼不成一个棋盘',
      body: '灯都找到了，但它们的位置排不成规整的方格 —— 多半是把画面里别的亮点当成了灯。',
      action: '把画面里的强光源（窗户、台灯）挡一下，或把房间调暗一些，再重新开始标定。',
      detail: raw,
    };
  }
```

- [ ] **Step 4: 跑测试 + 契约闸**

Run: `cd katrain/web/ui && npm test; echo "exit=$?"` → `exit=0`

契约闸（两集必须相等）：

```bash
# 后端产生的 reason 取值
grep -ohE 'reason="[a-z_]+"|reason=f?"[a-z_:{},]+"' ../../vision/led_geometry_calibrator.py | sort -u
# 前端消费的取值
grep -ohE "raw === '[a-z_]+'" src/kiosk/components/vision/GeometryCalibrationScreen.tsx | sort -u
```
Expected：后端每一个非参数化取值在前端都能找到分支。`anchor_not_found:{r},{c}` 是参数化的，
由 `:81` 的正则分支处理，不在此列。

- [ ] **Step 5: 失败时把「13 个里找到了几个」说出来**

这一屏现在按 `detected_anchors.length` 报「四角 + 九星 13 / 13 已定位」、前三步全绿「完成」——
即使那 13 个全是噪声（spec §2.6）。计划一 Task 2 已经把 `metrics.attempts` 透出来了，用它说实话。

先写失败测试：

```tsx
  test('失败时报的是真实命中数,不是「13/13 已定位」', () => {
    renderScreen({
      phase: 'failed', error: 'too_few_anchors', last_valid: true,
      metrics: { attempts: [
        { row: 0, col: 0, color: 'green', level: 96, ok: true, peak: 44.7, reason: null },
        { row: 0, col: 18, color: 'green', level: 96, ok: false, peak: 8.2, reason: 'low_signal' },
        { row: 0, col: 18, color: 'green', level: 255, ok: false, peak: 12.1, reason: 'low_signal' },
      ] },
    });

    expect(screen.getByText(/找到 1 \/ 13 个定位点/)).toBeInTheDocument();
    expect(screen.queryByText(/13 \/ 13/)).not.toBeInTheDocument();
  });
```

实现分两处。**先加宽类型** —— `api/geometryApi.ts:55` 现在是
`metrics?: Record<string, number | null>`，**装不下 `attempts` 这个数组**，
不改它 `status.metrics?.attempts` 连编译都过不去：

```ts
/** 一次锚点定位尝试。同一颗锚点最多产生 6 条(三色 × 两档亮度)。
 *  后端产生点:led_geometry_calibrator._locate_anchor;
 *  透出点:geometry_calibration_service 的失败分支(计划一 Task 2)。 */
export interface GeometryAttempt {
  row: number;
  col: number;
  color: string;
  level?: number;
  ok?: boolean;
  peak?: number;
  area?: number | null;
  margin?: number | null;
  reason?: string | null;
}

// GeometryStatus 里那一行改成:
  metrics?: {
    inlier_count?: number | null;
    rms_residual?: number | null;
    max_residual?: number | null;
    shift_cells?: number | null;
    drift_response?: string | null;
    attempts?: GeometryAttempt[];
  };
```

⚠️ `shift_cells` / `drift_response` 是漂移路径写进 `metrics` 的
（`geometry_calibration_service.py:279`），一并列出来，别把它们从类型里挤掉。

**再加渲染**（放在 `buildDiagnostic` 结果的 `detail` 旁边，同一块小字区）：

```tsx
  // attempts 里同一颗锚点可能有多条(三色 × 两档亮度),按 (row,col) 去重后再数命中。
  const located = new Set(
    (status.metrics?.attempts ?? []).filter((a) => a.ok).map((a) => `${a.row},${a.col}`),
  ).size;
```

```tsx
  {phase === 'failed' && status.metrics?.attempts?.length ? (
    <p className="kiosk-diag-count">
      {t('vision:anchors_located', '找到 {n} / 13 个定位点').replace('{n}', String(located))}
    </p>
  ) : null}
```

⚠️ 去重是必需的：Task 4（计划一）之后同一颗锚点最多会产生 6 条 attempt
（三色 × 两档亮度），直接 `filter(ok).length` 数出来的是**尝试数不是锚点数**。

- [ ] **Step 6: 跑测试 + 提交**

Run: `cd katrain/web/ui && npm test; echo "exit=$?"` → `exit=0`

```bash
git add katrain/web/ui/src
git commit -m "feat(kiosk): 补齐四条标定失败文案,并按 attempts 报真实的定位点命中数"
```

---

### Task 5: 补两条走得通的标定入口（开局前 + 对局中）

现在对局屏零个通往标定的按钮；唯一的路是「退出对局」，而它在未终局时**强制认输**（spec §2.6）。

**设计约束（先读，别照抄直觉方案）**：`GamePageBar` 的 `action` 是**单个对象不是数组**，
`GamePage.tsx:680-684` 的注释写明「§11 只允许一个页级图标按钮，重置识别在这一屏是**唯一**那个」。
**不许再加一颗页级图标键。** 对局操作行 `KioskActions`（`GameControlPanel.tsx:309-322`）
装的是停一手/数子/认输这类**棋局**动作，把设备维护塞进去语义不对。

⇒ 入口放两处，各自在用户已经在看的地方：

- **5a 开局前**：`PvpLocalSetupPage.tsx:203-214` 那句「这台机器没有标定过摄像头，只能下在屏幕上」
  **只说不给去处** —— 补一颗「去标定」。开局前跳转不丢任何东西。
- **5b 对局中**：把开关排右端那句 `.ghint`（`GameControlPanel.tsx:421-428`）在**可行动**时
  变成按钮。用户已经在那里被告知「棋盘被移动 · 需重新标定」，去处就该在那句话上。

**Files:**
- Modify: `src/kiosk/pages/PvpLocalSetupPage.tsx:203-214`
- Modify: `src/kiosk/components/game/GameControlPanel.tsx:47 / :421-428`
- Modify: `src/kiosk/pages/GamePage.tsx`（把回调传下去）
- Test: `src/kiosk/__tests__/PvpLocalSetupPage.test.tsx`、`src/kiosk/__tests__/GamePage.test.tsx`

**Interfaces:**
- Produces: `GameControlPanelProps.onFaultAction?: (() => void) | null`（`:47` 的 `hardwareFault` 旁边）。
  给了就把 `.ghint` 渲染成 `<button className="ghint ghint--action">`，没给就仍是 `<i>`。
  **`hardwareFault` 的三句话优先级与文案一字不动** —— 只改「这一句可不可点」。

- [ ] **Step 1: 写失败测试（5a）**

```tsx
  test('没标定过摄像头时,那句解释旁边有一条去标定的路', () => {
    renderSetup({ visionEnabled: false });   // reason === 'noCamera'

    expect(screen.getByText(/没有标定过摄像头/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '去标定' }));

    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/vision/setup');
  });

  test('原因是路数而不是标定时,不给「去标定」—— 标定救不了 9 路', () => {
    renderSetup({ visionEnabled: true, boardSize: 9 });   // reason === 'notNineteen'

    expect(screen.getByText(/9 路和 13 路只有屏幕上有/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '去标定' })).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: 写失败测试（5b）**

```tsx
  it('「棋盘被移动」那句话本身就是去处 —— 点它打开重标定弹窗', async () => {
    mockIsVisionEnabled = true;
    mockVisionLoaded = true;
    mockGeometryPhase = 'degraded';
    renderGamePage();

    // 弹窗先出现;按「仍要继续」关掉之后,那句话必须还能把它叫回来。
    fireEvent.click(await screen.findByText('仍要继续'));
    expect(screen.queryByText('棋盘可能被移动')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /棋盘被移动/ }));
    expect(await screen.findByText('棋盘可能被移动')).toBeInTheDocument();
  });

  it('不可行动的故障句仍是纯文本 —— 摄像头没插上,点它没有意义', () => {
    mockIsVisionEnabled = true;
    mockVisionLoaded = true;
    mockCameraConnected = false;
    renderGamePage();

    expect(screen.getByText(/摄像头未连接/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /摄像头未连接/ })).not.toBeInTheDocument();
  });
```

- [ ] **Step 3: 跑测试确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/PvpLocalSetupPage.test.tsx src/kiosk/__tests__/GamePage.test.tsx -t 标定`
Expected: FAIL —— 两处都找不到按钮

- [ ] **Step 4: 实现 5a**

`PvpLocalSetupPage.tsx` 那段 `<p className="kiosk-opthint">` 之后追加：

```tsx
            {/* 「只能下在屏幕上」这句话必须带一个去处 —— 光说不给路,人只能自己去猜
                设置屏在哪(见 feedback_way_out_must_be_reachable_by_a_user)。
                只在 noCamera 时给:notNineteen 是路数问题,标定救不了它。 */}
            {playInput.reason === 'noCamera' && (
              <button
                type="button"
                className="kiosk-btn kiosk-btn--secondary"
                onClick={() => navigate('/kiosk/vision/setup')}
              >
                {t('setup:go_calibrate', '去标定')}
              </button>
            )}
```

- [ ] **Step 5: 实现 5b**

`GameControlPanel.tsx` props 加一项（`:47` 的 `hardwareFault` 之后）：

```tsx
  /** 故障句可不可点。给了就把那句 `.ghint` 渲成按钮 —— 「叫人去重新标定」和
   *  「给他一条去重新标定的路」必须是同一个东西(spec §2.6)。 */
  onFaultAction?: (() => void) | null;
```

`:421-428` 改成：

```tsx
        {hardwareFault && onFaultAction ? (
          <button type="button" className="ghint ghint--action" data-fault="true" onClick={onFaultAction}>
            {hardwareFault}
          </button>
        ) : (
          <i className="ghint" data-fault={hardwareFault ? 'true' : undefined}>
            {hardwareFault
              ?? (analysisRequiresLogin
                ? t('play:analysis_requires_login_hint', '领地 / 支招 / 图表 登录后可用')
                : !isGameOver && !canCount
                  ? t('game:count_min', '数子要下满 {n} 手').replace('{n}', String(countMin))
                  : '')}
          </i>
        )}
```

`GamePage.tsx` 传下去 —— **只有「棋盘被移动」这一句可行动**：

```tsx
            hardwareFault={hardwareFault}
            onFaultAction={boardDisplaced ? () => { setRecalDismissed(false); } : null}
```

（`recalDismissed` 一清，Task 2 的 `open` 判据就重新成立，同一个弹窗回来。**不新增状态**。）

样式：`ghint--action` 在对应的 css 里继承 `.ghint` 的排版，只加 `cursor:pointer` 与下划线，
**不得改变那一格的高度**（定高的条会挤裂字，见 `feedback_fixed_height_bar_crushes_text`）。

- [ ] **Step 6: 跑全套确认它绿**

Run: `cd katrain/web/ui && npm test; echo "exit=$?"` → `exit=0`

- [ ] **Step 7: 变异验证**

把 `onFaultAction` 传成 `() => {}`（恒给）：第二条 5b 测试（摄像头那条仍是纯文本）**必须红**。
把它传成 `null`（恒不给）：第一条 5b 测试**必须红**。两个方向都红过再定稿。

- [ ] **Step 8: 提交**

```bash
git add katrain/web/ui/src
git commit -m "feat(kiosk): 开局设置屏补「去标定」,对局屏故障句变成可点的去处

不新增页级图标键(§11 只允许一个,已被「重置识别」占用),
入口落在用户已经在看的两句解释上。"
```

- [ ] **Step 9: 板上验收 —— 「有这颗键」不等于「够得到」**

CDP 的 click 不管视口，键在屏外也会「点成功」。必须量：

```python
Runtime.evaluate: (() => {
  const b = [...document.querySelectorAll('button')]
    .find(x => /去标定|棋盘被移动/.test(x.innerText));
  if (!b) return {found: false};
  const r = b.getBoundingClientRect();
  return {found: true,
          inView: r.top >= 0 && r.left >= 0 && r.bottom <= innerHeight && r.right <= innerWidth,
          rect: [r.x, r.y, r.width, r.height], vp: [innerWidth, innerHeight]};
})()
```
Expected：`found && inView === true`，视口 1024×600。两屏各量一次。

---

### Task 6: PhysicalBoardGuard 不再把正在进行的对局整屏换掉

`PhysicalBoardGuard` 没有「只在进入时判一次」的闩，几何相位一变就把整屏（连同对局与弹窗）换成标定台。对升降级对弈尤其致命 —— 而按弹窗里那颗「重新标定」**必然**让 `phase` 离开 `'ready'`，也就是说 Task 5 那颗键在没有本任务的情况下会自己把对局屏踢掉。

**Files:**
- Modify: `src/kiosk/components/vision/PhysicalBoardGuard.tsx`
- Modify: `src/kiosk/components/vision/PlayInputGuard.tsx`
- Test: `src/kiosk/__tests__/PhysicalBoardGuard.test.tsx`

**Interfaces:**
- Produces: `PhysicalBoardGuard` 新增可选 prop `latchOnce?: boolean`（默认 `false`）。
  `PlayInputGuard` 传 `latchOnce`。**做题屏 / 摆谱屏行为不变** —— 那两条不传，保持现状。

- [ ] **Step 1: 写失败测试**

```tsx
  test('latchOnce:放行过一次之后,几何相位再变也不把 children 换掉', () => {
    mockGeometry = readyStatus();
    const { rerender } = render(
      <PhysicalBoardGuard latchOnce sub="x"><div>GAME</div></PhysicalBoardGuard>);
    expect(screen.getByText('GAME')).toBeInTheDocument();

    mockGeometry = { ...readyStatus(), phase: 'failed' };   // 用户按了「重新标定」
    rerender(<PhysicalBoardGuard latchOnce sub="x"><div>GAME</div></PhysicalBoardGuard>);

    expect(screen.getByText('GAME')).toBeInTheDocument();   // 对局还在
  });

  test('latchOnce 不改变「进门那一下」的判据:没就绪就还是标定台', () => {
    mockGeometry = { ...readyStatus(), phase: 'failed' };
    render(<PhysicalBoardGuard latchOnce sub="x"><div>GAME</div></PhysicalBoardGuard>);

    expect(screen.queryByText('GAME')).not.toBeInTheDocument();
    expect(screen.getByText('先标定棋盘')).toBeInTheDocument();
  });

  test('不传 latchOnce 时行为逐字不变(做题/摆谱那两条)', () => {
    mockGeometry = readyStatus();
    const { rerender } = render(<PhysicalBoardGuard sub="x"><div>TSUMEGO</div></PhysicalBoardGuard>);
    expect(screen.getByText('TSUMEGO')).toBeInTheDocument();

    mockGeometry = { ...readyStatus(), phase: 'degraded' };
    rerender(<PhysicalBoardGuard sub="x"><div>TSUMEGO</div></PhysicalBoardGuard>);

    expect(screen.queryByText('TSUMEGO')).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: 跑测试确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/PhysicalBoardGuard.test.tsx -t latchOnce`
Expected: FAIL —— 第一条会红（当前实现会把 GAME 换掉）

- [ ] **Step 3: 实现**

`PhysicalBoardGuard.tsx`：

```tsx
const PhysicalBoardGuard = ({
  children, requireRecognition = false, sub, latchOnce = false,
}: {
  children: ReactNode;
  requireRecognition?: boolean;
  sub: string;
  /** 放行一次之后就不再回收这块屏。给**对局**用 —— 把一局正在下的棋整屏换成标定台
   *  是不可接受的(升降级对弈尤甚),而按「重新标定」必然让 phase 离开 'ready',
   *  没有这个闩,那颗键会把自己的宿主踢掉(spec §2.6)。
   *  做题屏 / 摆谱屏不传它,行为不变。 */
  latchOnce?: boolean;
}) => {
  const { status } = useGeometry();
  const navigate = useNavigate();
  const ready = status.phase === 'disabled' || (
    status.phase === 'ready' && status.session_calibrated && status.capabilities.geometry_ready
    && (!requireRecognition || status.capabilities.recognition_ready)
  );

  const [admitted, setAdmitted] = useState(false);
  useEffect(() => { if (latchOnce && ready) setAdmitted(true); }, [latchOnce, ready]);

  if (ready || (latchOnce && admitted)) return <>{children}</>;
  return (
    <GeometryCalibrationScreen
      backLabel="返回" onBack={() => navigate(-1)} title="先标定棋盘"
      sub={sub} requireRecognition={requireRecognition}
    />
  );
};
```

`PlayInputGuard.tsx` 传下去：

```tsx
    ? <PhysicalBoardGuard latchOnce requireRecognition sub="在实体盘上对弈，要先让摄像头看清盘面">{children}</PhysicalBoardGuard>
```

- [ ] **Step 4: 跑测试确认它绿**

Run: `cd katrain/web/ui && npm test; echo "exit=$?"` → `exit=0`

- [ ] **Step 5: 变异验证 —— 闸只覆盖第一家的典型坑**

把 `PlayInputGuard` 里的 `latchOnce` 删掉：第一条测试**必须红**。
再把 `latchOnce` 的默认值改成 `true`：第三条（做题/摆谱不变）**必须红**。
两个方向都红过了，才说明这个开关真的把两家分开了。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/ui/src
git commit -m "fix(kiosk): 对弈路由的标定守卫改成进门判一次,不再中途把对局换成标定台"
```

- [ ] **Step 7: 板上验收**

开一局实体对局 → 按页控条的「重新标定」→ 用 CDP 确认：

```python
Runtime.evaluate: document.body.innerText.includes('先标定棋盘')
```
Expected：`false`（对局屏还在），且盘下 LED 确实开始逐颗闪。

---

## 整体验收（全部任务完成后跑一次）

- [ ] `cd katrain/web/ui && npm test; echo "exit=$?"` → `exit=0`，且**总用例数比开工前多**（新增了 RecalibrationModal / VisionContext 两个 spec）
- [ ] `npm run build:smartbox-kiosk-2d` 通过（含 `verify:kiosk-2d` 严格闸）
- [ ] 部署到板上后 **CDP `Page.reload(ignoreCache=True)`**，并核对 `document.scripts` 的 bundle 名与本机产物一致
- [ ] 板上走一遍完整旅程：
  - [ ] 选「实体盘」开一局自由对弈 → **绑定窗口内不弹任何告警**
  - [ ] 页控条上「重新标定」这颗键 `inView === true`
  - [ ] 按它 → 对局屏**不被换掉**，LED 逐颗闪
  - [ ] 白天按它 → 标定失败，屏上出现「现在太亮了，看不见盘下的灯」而**不是**兜底那句
  - [ ] 挪动棋盘触发漂移 → 弹窗出现，点背景 3 次**它还在**，按「仍要继续」才关
- [ ] 升降级对弈走同一遍（同一个 `GamePage`，但要单独确认一次 —— 它的退出路径会结算段位）

> ⚠️ 本计划的多数验收项属于「真浏览器里的挂载时序与交互」，
> **jsdom 那 66 个 spec 全绿不构成这些项的证据**（spec §3 R2）。
> 上面每一条带 CDP 的项都必须真跑，跑不动就写「没验」，不要用单测顶替。

---

## 已知缺口（本计划**不做**，明写出来免得被当成漏项）

1. **spec §2.7 的 `physicalPlay` 翻假路径**：「9/13 路 + 偏好为实体盘」这个组合仍然可以发生
   （偏好默认 `true`，选路数不写偏好）。Task 2 把弹窗改成**无条件挂载**之后，
   它不再造成「弹窗突然消失」；剩下的表现是「选了实体盘却下在屏幕上」，
   而开局设置屏 `PvpLocalSetupPage.tsx:207-209` 已经用 `notNineteen` 那句话解释了。
   ⇒ 判定为**已有解释、无需新代码**。若日后要更彻底，正确做法是选 9/13 路时把偏好一并写回，
   而不是在 `GamePage` 里补判断。

2. **主动重标（几何一切正常时用户就是想重标一次）**：本计划**不在对局中**提供这条路。
   理由：重标会让 `phase` 离开 `'ready'`、盘下 LED 逐颗闪、并使当前几何失效 ——
   在一局正在下的棋上做这件事代价太大。正确位置是**开局之前**（Task 5a 那颗「去标定」）
   与设置屏。若产品后续要求对局中也能主动重标，那是一次独立的产品决策，
   不要顺手加进来（§11 的页级图标位已被「重置识别」占满，加键要先改规范）。

3. **摄像头在明亮环境下的物理能力**：曝光接线（计划一 Task 1）能把画面拉回 `[120,170]`，
   但 LED 标定需要的是「LED 亮度 > 环境光在盘面上的反射」，那是**硬件约束**。
   本计划只保证这件事变得**可见、可诊断、可缓解**（说清楚要调暗），不保证白天能标定成功。
