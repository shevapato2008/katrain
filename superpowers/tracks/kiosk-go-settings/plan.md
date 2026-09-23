# 围棋 kiosk · 设置(kiosk-go-settings)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让设置屏说的话在别的屏上也成立:① 关掉「落子音效」后研究屏和摆谱屏真的不响;② 「AI 段位详情」换成外壳视图、文案走 `t()`;③ 没摄像头 / 还没问到状态时那一组说实话;④ 把屏幕旋转的死代码清掉,**但保住它那只承重的视口盒子**;⑤ 补一组「关于」(版本 + 两个引擎状态,Fan 2026-09-21 裁定)。

**Architecture:** 纯前端,无后端与数据契约改动。
- ST1:两处发声点读 `utils/audioPrefs` 的 `sfx`(`useSessionBase` 是共享领地,galaxy 行为不变)。
- ST4:新建 `kiosk/components/settings/KioskAiLadderDetail.tsx`(就地展开,不做遮罩层),文案取自 `features/aiLadder/copy.ts`,判别位取自 `startGate.ts`,配 parity 测试;共享件 `AiLadderStatusCard` 不动。
- ST5:设置屏消费 `GeometryContext` 的 `loaded` 与 `phase`,照抄标定屏的三格写法。
- ST6:删旋转机器与一个零消费者组件;`RotationWrapper` 那只 `fixed/100vw/100vh/overflow:hidden` 的盒子换成一个同几何的 `div`,并在真浏览器里量证几何没变。
- ST3-关于:`/api/v1/health` 多回一个 `version`(真源 `katrain/core/constants.py`);屏上第六组三行(版本 + 本机引擎 + 云端引擎),**设备名不画**(`settings.DEVICE_ID` 在没配 env 时是每次启动自铸的 uuid4,不是出厂身份)。

**Tech Stack:** React 18 + TypeScript + Vite,vitest + @testing-library/react,Playwright(承重实测、四图、PO 闸)。

**Spec:** `superpowers/tracks/kiosk-go-settings/prd.md`

## 开工核验(2026-09-22,按真实代码更正;细节在各提交信息里)

- **基线与 i18n 改了**:开工时 develop 已比 `7a152df1` 多 29 个提交,其中 `e7bc651a` 把 kiosk i18n
  闸(`tests/web_ui/test_kiosk_i18n.py`)放宽到全树 ⇒ 下面 Global Constraints 的「不合并 develop /
  不改 `.po`」照旧执行,合并后必红。**Fan 2026-09-22 裁定照直播赛道办**:develop 已本地合入
  (`24dcc7a7`,不 push),本赛道新增的 key 自补 11 语种。
- Task 1:几何探针不用「基线存在 test-results/ 里、测试比 JSON」那种写法(那份 JSON 不进仓,别人一跑就红),
  改成关系式判据 + `GEOMETRY_DUMP` 写读数、改前改后 `diff`;并补量**登录页**(它在 `KioskLayout` 外面,
  `height:100%` 直接取视口盒子 —— 塌陷类,计划原稿漏了)和 1280×800(缩放 ≠ 1 时居中才依赖包含块)。
- Task 2:`playShutter` 从页面文件直接 `export` 会撞 `react-refresh/only-export-components` ⇒ 挪到
  `kiosk/utils/baipuShutter.ts`。
- Task 3:三格措辞照抄标定屏(摄像头 已连接、几何标定 已标定/未标定,原来是「就绪」),LED 照视觉 PRD V4
  写「串口已连接」;没摄像头的原因写进那一行小字,不另加 setnote。
- Task 4:`AI_LADDER_COPY` 里**没有** `placementTitle` / `netScoreTitle` / `netScoreHint` ⇒ 用真实的
  `formatPlacementProgress` / `formatNetScore` / 阈值两句;摘要行也收进组件(parity 要比到它 ——
  改前它自己写了「认证中」「本地对弈」),文件名因此是 `KioskAiLadderRows.tsx`;parity 测试放
  `kiosk/__tests__/`(它要 import MUI 渲染共享卡,而验收要求 `components/settings/` 下零 `@mui`)。
- Task 5:把 `100vw/100vh` 内联进 `KioskApp.tsx` 会让壳契约闸一变红(它只豁免旋转包裹那一个文件)⇒
  盒子单独成 `components/layout/KioskViewport.tsx`,豁免跟着挪;另有 7 份测试还桩着 `OrientationContext`,一并删。
- Task 6:不新建 `kiosk/api/healthApi.ts` —— 共享 `api.ts` 已有 `API.engineHealth()`,只给响应类型加可选
  `version`;行型照稿子「关于」那一组的 lead 列(版本 / 本机 / 云端);验收 5「尾部留白 ref 挂对」是布局事实,
  改由真浏览器闸守(`kiosk-settings-expand.spec.ts` 与 `kiosk-shell-scroll.spec.ts` 那条)。**后端那一行
  按切片流程等 Fan 看过四图再做。**Fan 2026-09-22 确认四图(连同「净胜分出现两次保留」「段位行改用共享词」两条推荐)后才做;
  后端测试没新建 `test_health_version.py`,加在 `/api/v1/health` 已有的 `tests/web_ui/test_backend_scaffolding.py` 里。
- Task 7:四图多拍两对(展开态、「关于」);「关于」的参考图从同一版稿子滚到底补拍(`visual/reference/`)。
- 环境:`playwright.visual.config.ts` 是 `reuseExistingServer:true` 固定 5173 —— 别的 worktree 起着 dev server
  时会量到别人的代码 ⇒ 本地用一份不提交的配置换 5391 + `--strictPort`。`test-results/.last-run.json` 是
  被跟踪的文件,每跑一次 Playwright 都会改它,跑完要还原。壳契约闸四在合入的 develop 上本来就红一条
  (`GamePage.tsx game:connection_dropped`),基线 worktree 上同样红,与本赛道无关。

## Global Constraints

> **开工前先读 `prd.md` §6.0**:四条新赛道的共享文件归属与合并顺序。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-settings`(分支 `feature/kiosk-go-settings`,基线 develop `7a152df1`)里开发;**不 push、不合并 develop**。
- `cd katrain/web/ui && npm ci`。本轮**没有 Python 改动**。
- **`GeometryContext.tsx` / `geometryApi.ts` 不许改**(归视觉赛道,§6.0 第 2 条);本赛道只消费 `loaded` / `phase` / `capabilities`。
- **`features/aiLadder/*` 不许改**(galaxy 在用);ST4 另起 kiosk 视图。
- **本轮有一行 Python 改动**(ST3-关于:`endpoints/health.py` 加 `version`)⇒ 新 worktree 要 `uv sync --extra web`,改完 `uv run black -l 120 <文件>`、`CI=true uv run pytest tests/web_ui -q -k health`。
- **`BaipuSessionPage.tsx` 与 kifu 分支重叠**(它在那条分支上 +180 行)⇒ 先确认 kifu 是否已并入 develop;没并就照做,合并时由后合的一方解冲突。
- 共享领地(`src/hooks/useSessionBase.ts`)改动 ⇒ `npm run build` 与 `npm run build:kiosk-2d` 都要绿。
- 类型检查 `npx tsc -b`(`--noEmit` 检查 0 个文件,无效)。
- 新文案一律 `t('ns:key','中文默认')`,**不改 `.po`**;沿用已有 key 时中文默认串要与 cn PO 逐字一致。
- **ST6 是承重改动**:判据是真浏览器量出来的数(页面溢出 + `.kiosk-screen` 几何),**jsdom 与截图都不作证**。
- 屏 27 有参考图 ⇒ ST4 / ST5 改完走四图关卡(`npm run fourup`,跑两次排抖动),**交 Fan 确认后**才算过。
- 提交信息用中文,结尾加 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`;`git add` 逐个写文件名并 `git diff --cached --stat` 回读。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `katrain/web/ui/src/hooks/useSessionBase.ts` | 改 `:49-56` | ST1:发声前读 `sfx` |
| `katrain/web/ui/src/hooks/useSessionBase.sound.test.tsx` | **新建** | ST1 单测 |
| `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx` | 改 `:31-48`(或 `:218` 调用点) | ST1:快门声读 `sfx` |
| `katrain/web/ui/src/kiosk/__tests__/BaipuShutterSound.test.tsx` | **新建** | ST1 单测 |
| `katrain/web/ui/src/kiosk/components/settings/KioskAiLadderDetail.tsx` | **新建** | ST4:外壳版段位详情 |
| `katrain/web/ui/src/kiosk/components/settings/KioskAiLadderDetail.parity.test.tsx` | **新建** | ST4:两视图同一套文案 |
| `katrain/web/ui/src/kiosk/components/settings/AccountSection.tsx`(+`.test.tsx`) | 改 `:1-2`、`:108-145` | ST4:就地展开、去 MUI、文案走 `t()` |
| `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` | 改 `:93`、`:161-163`、`:227-259` | ST5 |
| `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx` | 追加 | ST5 三条 |
| `katrain/web/ui/src/kiosk/KioskApp.tsx` | 改 `:34`、`:41`、`:200-215` | ST6:删旋转、保留视口盒子 |
| `katrain/web/ui/src/kiosk/context/OrientationContext.tsx`、`components/layout/RotationWrapper.tsx`、`components/settings/PhysicalBoardStatus.tsx` + 四份测试 | **删** | ST6 |
| `katrain/web/ui/tests/kiosk-viewport-geometry.spec.ts` | **新建** | ST6 承重实测(改前基线 + 改后比对) |
| `katrain/web/api/v1/endpoints/health.py` | 改(加 `version`) | ST3-关于 |
| `tests/web_ui/test_health_version.py` | **新建** | 一条:`version` == `constants.VERSION` |
| `katrain/web/ui/src/kiosk/api/healthApi.ts`(+ `.test.ts`) | **新建** | ST3-关于:取数 + 状态翻译的纯函数 |
| `katrain/web/ui/tests/kiosk-screen-27-settings.fourup.spec.ts` | 可能需微调 | 四图重取 |

任务顺序:Task 1 基线(**含 ST6 的改前几何基线**)→ Task 2 ST1 → Task 3 ST5 → Task 4 ST4 → Task 5 ST6 → **Task 6 ST3-关于** → Task 7 四图与 PO 闸 → Task 8 收尾。Task 2/3/4/6 互相独立;Task 5 必须在 Task 1 记下改前几何之后做;Task 6 与 Task 3 改同一个文件(`SettingsPage.tsx`),按序做。

---

### Task 1: 核对 worktree、装依赖、记录基线(含改前几何)

**Files:** 不改仓内文件;基线写到 `$(git rev-parse --absolute-git-dir)/settings-baseline/`。

**Interfaces:** Produces:`$BASE/before-failed.txt`、`$BASE/failed-names.cjs`、`$BASE/geometry-before.json`。

- [x] **Step 1: 核对 worktree 与装依赖**

```bash
cd /Users/fan/Repositories/katrain
# worktree 已于 2026-09-21 建好,本步只核对,不要再 add
git -C /Users/fan/Repositories/katrain-kiosk-go-settings rev-parse --abbrev-ref HEAD            # 预期 feature/kiosk-go-settings
git -C /Users/fan/Repositories/katrain-kiosk-go-settings merge-base --is-ancestor 7a152df1 HEAD && echo base-ok
cd /Users/fan/Repositories/katrain-kiosk-go-settings/katrain/web/ui && npm ci
```

- [x] **Step 2: 单测基线**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings/katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-settings rev-parse --absolute-git-dir)/settings-baseline"; mkdir -p "$BASE"
cat > "$BASE/failed-names.cjs" <<'EOF'
const report = require(process.argv[2]);
const out = [];
for (const file of report.testResults) {
  const rel = file.name.replace(/^.*\/katrain\/web\/ui\//, '');
  if (file.status === 'failed' && file.assertionResults.length === 0) out.push(`${rel} :: <文件级失败>`);
  for (const a of file.assertionResults) if (a.status === 'failed') out.push(`${rel} :: ${a.fullName}`);
}
console.log(out.sort().join('\n'));
EOF
npx vitest run --reporter=json --outputFile="$BASE/before.json" > "$BASE/before.log" 2>&1; echo "vitest_exit=$?"
node "$BASE/failed-names.cjs" "$BASE/before.json" > "$BASE/before-failed.txt"
npx tsc -b; echo "tsc_exit=$?"
```

- [x] **Step 3: 写 ST6 的几何探针(**先写,先量改前**)**

```ts
// katrain/web/ui/tests/kiosk-viewport-geometry.spec.ts
import { test, expect } from '@playwright/test';
import { writeFileSync, existsSync, readFileSync } from 'node:fs';

/**
 * ST6 承重实测。`RotationWrapper` 即使在 rotation=0 下也是一个
 * `position:fixed; 100vw×100vh; overflow:hidden` 的盒子 —— **整棵 kiosk 树的高度来源和裁切边界**。
 * 删它属承重改动,判据只能是真浏览器量出来的数。
 *
 * 用法:改之前 `SNAPSHOT=1 npx playwright test ...` 写基线;改之后不带 SNAPSHOT 跑,比对。
 */
const OUT = 'test-results/kiosk-viewport-geometry.json';
const SCREENS = ['/kiosk/settings', '/kiosk/report', '/kiosk/play'];

test('kiosk 视口几何与溢出', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  const measured: Record<string, unknown> = {};
  for (const path of SCREENS) {
    await page.goto(path);
    await page.waitForSelector('.kiosk-screen');
    measured[path] = await page.evaluate(() => {
      const doc = document.documentElement;
      const screen = document.querySelector('.kiosk-screen') as HTMLElement;
      const r = screen.getBoundingClientRect();
      return {
        horizontalOverflow: doc.scrollWidth > doc.clientWidth,
        verticalOverflow: doc.scrollHeight > doc.clientHeight,
        screen: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      };
    });
  }
  if (process.env.SNAPSHOT) {
    writeFileSync(OUT, JSON.stringify(measured, null, 2));
    test.skip(true, '基线已写入');
  }
  expect(existsSync(OUT)).toBe(true);
  // 关系式期望:**不许溢出**;画布几何与改前**相等**(具体像素只记录,不作判据来源)。
  const before = JSON.parse(readFileSync(OUT, 'utf8'));
  expect(measured).toEqual(before);
  for (const path of SCREENS) {
    expect((measured[path] as any).horizontalOverflow).toBe(false);
    expect((measured[path] as any).verticalOverflow).toBe(false);
  }
});
```

```bash
SNAPSHOT=1 npx playwright test --config=playwright.visual.config.ts tests/kiosk-viewport-geometry.spec.ts
cp test-results/kiosk-viewport-geometry.json "$BASE/geometry-before.json"
```

预期:基线 JSON 写出,三屏 `horizontalOverflow` / `verticalOverflow` 都是 `false`(若改前就溢出,**先记下来**,那不是本轮造成的)。

---

### Task 2: ST1 余下一半 · 研究屏与摆谱屏认「落子音效」

**Files:**
- Modify: `katrain/web/ui/src/hooks/useSessionBase.ts`
- Create: `katrain/web/ui/src/hooks/useSessionBase.sound.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`
- Create: `katrain/web/ui/src/kiosk/__tests__/BaipuShutterSound.test.tsx`

**Interfaces:**
- Consumes:`readAudioPref('sfx')`(`src/utils/audioPrefs.ts`)。
- Produces:无新导出。

- [x] **Step 1: 写失败的单测**

```tsx
// katrain/web/ui/src/hooks/useSessionBase.sound.test.tsx
// 桩的写法照搬 useGameSession.sound.test.tsx(同一族,同一把开关)。
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../api';
import { API } from '../api';
import { useSessionBase } from './useSessionBase';

vi.mock('../api', () => ({ API: { getState: vi.fn() } }));

const state = () => ({ game_id: 'g1', current_node_id: 1 }) as GameState;

const sockets: MockWebSocket[] = [];
class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: { code: number; reason: string; wasClean: boolean }) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  constructor(readonly url: string) { sockets.push(this); }
}

const played: string[] = [];
class MockAudio {
  currentTime = 0;
  constructor(readonly src: string) {}
  play = vi.fn(() => { played.push(this.src.split('/').at(-1) ?? this.src); return Promise.resolve(); });
}

const connect = async () => {
  const hook = renderHook(() => useSessionBase({ token: 'token' }));
  act(() => hook.result.current.setSessionId('session-1'));
  await waitFor(() => expect(sockets).toHaveLength(1));
  return sockets[0];
};

describe('useSessionBase 的落子声认「落子音效」开关', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sockets.length = 0;
    played.length = 0;
    localStorage.removeItem('kiosk_audio_sfx');
    vi.mocked(API.getState).mockResolvedValue({ session_id: 'session-1', state: state() } as never);
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal('Audio', MockAudio);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('关掉之后不响', async () => {
    localStorage.setItem('kiosk_audio_sfx', 'false');
    const socket = await connect();
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: 'sound', data: { sound: 'stone' } }) } as MessageEvent));
    expect(played).toEqual([]);
  });

  it('从没设置过(缺键)时照响 —— 出厂是开的', async () => {
    const socket = await connect();
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: 'sound', data: { sound: 'stone' } }) } as MessageEvent));
    expect(played).toEqual(['stone.wav']);
  });
});
```

```tsx
// katrain/web/ui/src/kiosk/__tests__/BaipuShutterSound.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { playShutter } from '../pages/BaipuSessionPage';   // Step 3 会把它导出

const createOscillator = vi.fn(() => ({
  frequency: { value: 0 }, connect: () => ({ connect: () => undefined }),
  start: vi.fn(), stop: vi.fn(), onended: null,
}));

beforeEach(() => {
  localStorage.clear();
  createOscillator.mockClear();
  vi.stubGlobal('AudioContext', vi.fn(() => ({
    createOscillator,
    createGain: () => ({ gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() }, connect: () => ({ connect: () => undefined }) }),
    currentTime: 0, destination: {}, close: vi.fn(),
  })));
});
afterEach(() => vi.unstubAllGlobals());

describe('摆谱快门声', () => {
  it('关掉「落子音效」后不发声', () => {
    localStorage.setItem('kiosk_audio_sfx', 'false');
    playShutter();
    expect(createOscillator).not.toHaveBeenCalled();
  });

  it('开着时发声', () => {
    playShutter();
    expect(createOscillator).toHaveBeenCalled();
  });
});
```

- [x] **Step 2: 跑,确认它失败**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings/katrain/web/ui
npx vitest run src/hooks/useSessionBase.sound.test.tsx src/kiosk/__tests__/BaipuShutterSound.test.tsx
```

- [x] **Step 3: 两处实现**

`useSessionBase.ts` 顶部加 import,`playSound` 首行加判断:

```ts
import { readAudioPref } from '../utils/audioPrefs';
...
    const playSound = useCallback((sound: string) => {
        // 提示音只留一把:设置屏「落子音效」、屏 04「落子提示音」、`useGameSession`、这里,
        // 读的都是 audioPrefs 的 sfx。galaxy 也走这个 hook —— 它从不写这把键,
        // `readAudioPref` 缺键当开,所以 galaxy 行为不变。
        if (!readAudioPref('sfx')) return;
        if (!audioCache.current[sound]) {
```

`BaipuSessionPage.tsx`:把 `function playShutter()` 改成**导出**并在开头判断:

```ts
import { readAudioPref } from '../../utils/audioPrefs';
...
// Short shutter "click" via WebAudio (no asset). Plays AFTER the frame is written
// (the "you may place the next stone" go-signal). Best-effort; ignored if blocked.
// **它归「落子音效」那把开关**(不是语音那把:语音关的是七句引导语)。
// 导出只为可测:WebAudio 没有 `Audio` 那样的缓存对象可以桩。
export function playShutter() {
  if (!readAudioPref('sfx')) return;
  try {
```

- [x] **Step 4: 跑,确认通过**

```bash
npx vitest run src/hooks/useSessionBase.sound.test.tsx src/kiosk/__tests__/BaipuShutterSound.test.tsx
rg -n "playSound = useCallback" -A 3 src/hooks/   # 两处都应能看到 readAudioPref('sfx')
npx tsc -b
```

- [x] **Step 5: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings
git add katrain/web/ui/src/hooks/useSessionBase.ts katrain/web/ui/src/hooks/useSessionBase.sound.test.tsx \
  katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx katrain/web/ui/src/kiosk/__tests__/BaipuShutterSound.test.tsx
git commit -m "$(cat <<'EOF'
fix(kiosk-settings): 研究屏与摆谱快门声认「落子音效」开关

设置里写着「关」而喇叭还在响,正是 audioPrefs 文件头写明要避免的那种 bug。
galaxy 也走 useSessionBase:它从不写这把键,缺键当开 ⇒ 行为不变。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: ST5 · 设置屏分清「还没问到」「没有摄像头」「没连上」

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`(追加)

**Interfaces:**
- Consumes:`useGeometry()` 的 `{ status, loaded }`(`GeometryContext.tsx:20`,**本赛道不改它**)。

- [x] **Step 1: 写失败的单测(追加)**

```tsx
  it('还没问到状态时三格写「—」,不冒充「未连接」', () => {
    mockGeometry({ loaded: false });                  // 沿用本文件既有的 context mock 写法
    renderSettings();
    ['camera', 'calib', 'led'].forEach((k) => {
      expect(screen.getByTestId(`settings-cap-${k}`)).toHaveTextContent('—');
    });
    expect(screen.queryByText('未连接')).toBeNull();
  });

  it('这台盒子没有摄像头(phase=disabled)时,标定入口禁用并写明原因', async () => {
    mockGeometry({ loaded: true, status: { phase: 'disabled' } });
    renderSettings();
    const btn = screen.getByRole('button', { name: '开始标定' });
    expect(btn).toBeDisabled();
    expect(screen.getByTestId('settings-no-camera')).toBeInTheDocument();
    await userEvent.click(btn);
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  // 今天的行为不许退化。
  it('已标定时仍写「这次开机已标定」,按钮可点并进标定屏', async () => {
    mockGeometry({ loaded: true, status: { phase: 'ready', session_calibrated: true } });
    renderSettings();
    expect(screen.getByText('这次开机已标定')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '重新标定棋盘' }));
    expect(navigateSpy).toHaveBeenCalledWith('/kiosk/vision/setup');
  });
```

> 第三条里的按钮名按实现为准:今天那颗键的文案是 `settings:start_calib`「开始标定」。**先跑一次看报错里的可及名字再定**,别照记忆写。

- [x] **Step 2: 跑,确认它失败**

```bash
npx vitest run src/kiosk/__tests__/SettingsPage.test.tsx
```

- [x] **Step 3: 实现**

`SettingsPage.tsx:93` 改成:

```tsx
  const { status, loaded } = useGeometry();
```

标定那一行(`:228-242`)改成:

```tsx
            {/* 这台盒子没起采集服务(/status 404 ⇒ phase='disabled')时,入口**不可点**并说明原因 ——
                不把人送进标定屏再让那屏的空态把他弹回来(多一跳,且那一跳没有解释)。 */}
            <div className="kiosk-row">
              <span className="kiosk-row__t">
                <b>{t('Recalibrate board', '重新标定棋盘')}</b>
                <em>{calibratedAt}</em>
              </span>
              <span className="kiosk-row__end">
                <button
                  type="button"
                  className="kiosk-btn kiosk-btn--secondary"
                  disabled={noCamera}
                  onClick={() => { if (!noCamera) navigate('/kiosk/vision/setup'); }}
                >
                  {t('settings:start_calib', '开始标定')}
                </button>
              </span>
            </div>
            {noCamera && (
              <p className="setnote" data-testid="settings-no-camera">
                {t('settings:no_camera', '这台盒子没有接摄像头，实体棋盘的功能都用不了。')}
              </p>
            )}
```

其中(与 `calibratedAt` 放在一起):

```tsx
  // 「还没问到」和「问到了没连上」是两回事(`GeometryContext` 为此留了 `loaded`);
  // 「这台盒子压根没有摄像头」是第三种。三种在屏上是三句话,不是一句。
  const noCamera = loaded && status.phase === 'disabled';
  const calibratedAt = !loaded
    ? t('settings:calib_unknown', '正在读状态')
    : noCamera
      ? t('settings:calib_no_camera', '没有摄像头')
      : status.session_calibrated
        ? t('settings:calibrated', '这次开机已标定')
        : t('settings:not_calibrated', '还没标定');
```

三格(`:245-258`)改成(**照抄标定屏 `GeometryCalibrationScreen.tsx:325-331` 的口径**):

```tsx
            {([
              ['camera', t('Camera', '摄像头'), status.capabilities.camera_ready],
              ['calib', t('Calibration', '几何标定'), status.capabilities.geometry_ready],
              ['led', 'LED', status.capabilities.led_ready],
            ] as const).map(([key, label, ok]) => (
              <div className="kiosk-row" key={key} data-testid={`settings-cap-${key}`}>
                <span className="kiosk-row__t"><b>{label}</b></span>
                <span className="kiosk-row__end">
                  {/* 没读到之前一律「—」且不给灯色 —— `DEFAULT_STATUS` 三个 capability 全是 false,
                      直接画就会在还没问过的时候说「未连接」。标定屏 :325-331 是同一套写法。 */}
                  {!loaded ? (
                    <span className="kiosk-tag">—</span>
                  ) : (
                    <span className={ok ? 'kiosk-tag kiosk-tag--win' : 'kiosk-tag'}>
                      {ok ? t('settings:ready', '就绪') : t('settings:not_ready', '未连接')}
                    </span>
                  )}
                </span>
              </div>
            ))}
```

同时把 `:243-244` 那条注释补一句:它当初写的是口径,今天才真的做到。

- [x] **Step 4: 跑,确认通过**

```bash
npx vitest run src/kiosk/__tests__/SettingsPage.test.tsx && npx tsc -b
```

- [x] **Step 5: 提交**

```bash
git add katrain/web/ui/src/kiosk/pages/SettingsPage.tsx katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx
git commit -m "$(cat <<'EOF'
fix(kiosk-settings): 实体棋盘那一组分清三种状态

「还没问到」写 —、「没有摄像头」禁用入口并说明、「问到了没连上」才写未连接。
写法照抄标定屏,同一件事只留一套。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: ST4 · AI 段位详情换成外壳视图(就地展开)

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/settings/KioskAiLadderDetail.tsx`
- Create: `katrain/web/ui/src/kiosk/components/settings/KioskAiLadderDetail.parity.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/settings/AccountSection.tsx`(+`AccountSection.test.tsx`)

**Interfaces:**
- Consumes:`AiLadderStatus`(`features/aiLadder/types.ts`)、`AI_LADDER_COPY`(`features/aiLadder/copy.ts`)、`startGate.ts` 的纯函数、`useAiLadderStatus`。
- Produces:`<KioskAiLadderDetail status={...} onRetry={...} />` —— 一块 `.kiosk-rows` 内容,**自己不带标题、不带展开控制**(展开状态归 `AccountSection`)。

- [x] **Step 1: 写失败的单测**

```tsx
// KioskAiLadderDetail.parity.test.tsx —— 照 KioskAiLadderOpponent.parity.test.tsx 的做法
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import KioskAiLadderDetail from './KioskAiLadderDetail';
import { AI_LADDER_COPY } from '../../../features/aiLadder/copy';

describe('KioskAiLadderDetail 与共享卡说同一套话', () => {
  it('loading 用的是 AI_LADDER_COPY.loading', () => {
    render(<KioskAiLadderDetail status={{ view_state: 'loading' } as never} />);
    expect(screen.getByTestId('ladder-detail')).toHaveTextContent(AI_LADDER_COPY.loading);
  });

  it('error 用的是 AI_LADDER_COPY.loadError,并且「重试」永远画得出来', () => {
    render(<KioskAiLadderDetail status={{ view_state: 'error', message: '' } as never} />);
    expect(screen.getByTestId('ladder-detail')).toHaveTextContent(AI_LADDER_COPY.loadError);
    expect(screen.getByRole('button', { name: AI_LADDER_COPY.retry })).toBeDisabled();
  });

  it('整个组件里没有 MUI 类名', () => {
    const { container } = render(<KioskAiLadderDetail status={{ view_state: 'loading' } as never} />);
    expect(container.querySelectorAll('[class*="Mui"]')).toHaveLength(0);
  });
});
```

```tsx
// 追加到 AccountSection.test.tsx
  it('点「查看AI段位详情」就地展开,再点收起', async () => {
    renderAccount({ view_state: 'ready', /* …既有 ready 夹具… */ } as never);
    await userEvent.click(screen.getByRole('button', { name: /段位详情/ }));
    expect(screen.getByTestId('ladder-detail')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /收起/ }));
    expect(screen.queryByTestId('ladder-detail')).toBeNull();
  });

  it('段位读不到时,顶在列表里的是 .kiosk-row 不是 MUI 卡', () => {
    const { container } = renderAccount({ view_state: 'error', message: 'x' } as never);
    expect(container.querySelectorAll('[class*="Mui"]')).toHaveLength(0);
    expect(screen.getByTestId('ai-ladder-account-fallback')).toHaveClass('kiosk-row');
  });
```

- [x] **Step 2: 跑,确认它失败**

```bash
npx vitest run src/kiosk/components/settings/
```

- [x] **Step 3: 写 `KioskAiLadderDetail.tsx`**

```tsx
import { AI_LADDER_COPY } from '../../../features/aiLadder/copy';
import type { AiLadderStatus } from '../../../features/aiLadder/types';
import { useTranslation } from '../../../hooks/useTranslation';

/**
 * 设置屏「AI 段位详情」——**外壳写法**,与 `features/aiLadder/AiLadderStatusCard`(galaxy 那张 MUI 卡)并行。
 *
 * ## 为什么另起一个文件
 *
 * 和 `kiosk/components/aiLadder/KioskAiLadderOpponent.tsx` 同一条理由:要换的**不是几个尺寸,
 * 是另一套视觉语言**(MUI 的 Card/Chip/LinearProgress 对 `.kiosk-row` / `.kiosk-tag` / `.kiosk-btn`)。
 * 给共享件加一个能切换整套视觉的 prop,就是一个 prop 兼管两件事,而 galaxy 在用它。
 *
 * ⚠️ **两份视图的风险是它们会说不同的话。** 所以每一句都取自 `AI_LADDER_COPY`,
 * 判别位取自 `startGate.ts` 的纯函数,不在这儿重写条件;`*.parity.test.tsx` 逐状态断言两边同源。
 *
 * ## 为什么是就地展开不是弹层
 *
 * 这一屏本来就是一条滚动列表,展开一块内容代价最小;弹层要遮罩、要焦点陷阱,
 * 而 `.kiosk` 画布是缩放的 —— portal 到 body 的层不吃那个缩放(`.rvconfirm` 为此写在画布内)。
 */
const KioskAiLadderDetail = ({ status, onRetry }: { status: AiLadderStatus; onRetry?: () => void }) => {
  // AI_LADDER_COPY 每一句都是 getter;没有这一行,切换语言后它们还念着首次渲染时那一种。
  useTranslation();

  if (status.view_state === 'loading') {
    return (
      <div className="kiosk-row" data-testid="ladder-detail" role="status" aria-live="polite">
        <span className="kiosk-row__t"><b>{AI_LADDER_COPY.loading}</b></span>
      </div>
    );
  }

  if (status.view_state === 'error') {
    return (
      <div className="kiosk-row" data-testid="ladder-detail">
        <span className="kiosk-row__t"><b role="alert">{status.message || AI_LADDER_COPY.loadError}</b></span>
        <span className="kiosk-row__end">
          {/* 重试**永远画得出来**(拿不到 onRetry 时禁用)—— 一颗时有时无的键比灰着更让人以为屏坏了。 */}
          <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={onRetry} disabled={!onRetry}>
            {AI_LADDER_COPY.retry}
          </button>
        </span>
      </div>
    );
  }

  const placement = status.placement_state;
  const entry = placement?.phase === 'placed' ? placement.rung : status.current_opponent;

  return (
    <div data-testid="ladder-detail">
      {placement?.phase === 'placement' ? (
        <div className="kiosk-row">
          <span className="kiosk-row__t">
            <b>{AI_LADDER_COPY.placementTitle}</b>
            <em>{`${placement.completed_games} / ${placement.total_games}`}</em>
          </span>
        </div>
      ) : null}
      {entry ? (
        <div className="kiosk-row">
          <span className="kiosk-row__t">
            <b>{entry.rank_name}</b>
            <em>{AI_LADDER_COPY.route[entry.route]}</em>
          </span>
          <span className="kiosk-row__end">
            <span className={entry.certification_status === 'certified' ? 'kiosk-tag kiosk-tag--win' : 'kiosk-tag'}>
              {AI_LADDER_COPY.certification[entry.certification_status]}
            </span>
          </span>
        </div>
      ) : null}
      <div className="kiosk-row">
        <span className="kiosk-row__t">
          <b>{AI_LADDER_COPY.netScoreTitle}</b>
          <em>{AI_LADDER_COPY.netScoreHint}</em>
        </span>
        <span className="kiosk-row__end"><span className="kiosk-tag">{status.net_score}</span></span>
      </div>
    </div>
  );
};

export default KioskAiLadderDetail;
```

> ⚠️ `AI_LADDER_COPY` 里的键名以 `features/aiLadder/copy.ts` 为准 —— 写之前
> `grep -n "^\s*get \|^\s*[a-zA-Z]*:" katrain/web/ui/src/features/aiLadder/copy.ts` 抄一遍真实键名,
> 缺哪一句就用 `AiLadderStatusCard.tsx` 里对应位置用的那一句,**不要新造文案**(新造=两个视图开始说不同的话)。

- [x] **Step 4: 改 `AccountSection.tsx`**

- 删第 2 行的 MUI import 与第 141-144 行的 `<Dialog>`;
- `:127-129` 那颗按钮改成 `t()` 文案并切换展开:

```tsx
            <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={() => setDetailsOpen((v) => !v)}>
              {detailsOpen ? t('settings:ladder_detail_close', '收起') : t('settings:ladder_detail', '查看 AI 段位详情')}
            </button>
```

- 在那一行之后(仍在 `.kiosk-rows` 内)插入:

```tsx
      {detailsOpen && user && !isGuest && (
        <KioskAiLadderDetail status={status} onRetry={retry} />
      )}
```

- `:135-139` 的兜底改成:

```tsx
      {user && !isGuest && status.view_state !== 'ready' && (
        /* 读不到段位的时候照实说,但用的是外壳的行,不是从别的应用剪进来的一张卡。 */
        <KioskAiLadderDetail status={status} onRetry={retry} />
      )}
```

并把该组件的 `data-testid` 传递/命名调整到测试里断言的 `ai-ladder-account-fallback`(或把测试改成断言 `ladder-detail`,**二选一,别两处各叫各的**)。

- [x] **Step 5: 跑,确认通过**

```bash
npx vitest run src/kiosk/components/settings/ && npx tsc -b
rg "@mui" src/kiosk/components/settings/; echo "exit=$?"
rg "AI段位详情|查看AI段位" src | rg -v "t\('"; echo "exit=$?"
```

预期:单测全绿;两条 `rg` 都零命中(`exit=1`)。

- [x] **Step 6: 提交**

```bash
git add katrain/web/ui/src/kiosk/components/settings/
git commit -m "$(cat <<'EOF'
feat(kiosk-settings): AI 段位详情换成外壳视图,就地展开

不给共享件加 variant(一个 prop 兼管两件事,且 galaxy 在用它);
另起 kiosk 视图,文案全部取自 AI_LADDER_COPY,配 parity 测试防两边说不同的话。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: ST6 · 清掉旋转死代码,**保住那只承重的视口盒子**

**Files:**
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`
- Delete: `src/kiosk/context/OrientationContext.tsx`、`src/kiosk/components/layout/RotationWrapper.tsx`、`src/kiosk/components/settings/PhysicalBoardStatus.tsx` 及 `__tests__/OrientationContext.test.tsx`、`__tests__/RotationWrapper.test.tsx`、`__tests__/orientation.integration.test.tsx`、`__tests__/PhysicalBoardStatus.test.tsx`
- Verify: `katrain/web/ui/tests/kiosk-viewport-geometry.spec.ts`(Task 1 已写)

**Interfaces:**
- Produces:`.kiosk-viewport` 这一个类名(样式内联在 `KioskApp.tsx`,不新开 CSS 文件)。

- [x] **Step 1: 先确认基线在手**

```bash
ls -l "$(git -C /Users/fan/Repositories/katrain-kiosk-go-settings rev-parse --absolute-git-dir)/settings-baseline/geometry-before.json"
```

没有就回 Task 1 Step 3 先量。**改完再量就没有对照了。**

- [x] **Step 2: 换盒子**

`KioskApp.tsx`:删 `:34`、`:41` 两行 import;`:202-214` 换成

```tsx
      <VisionProvider>
        <GeometryProvider>
          <TsumegoProgressProvider>
            {/* ⚠️ **这只盒子是承重的。** 它原来叫 `RotationWrapper` —— 旋转功能 2026-07-08 已按
                「硬件不再旋转」删掉(合并 2bebfd5e),但那个组件即使在 rotation=0 下也渲染一个
                `fixed / 100vw / 100vh / overflow:hidden` 的盒子,**整棵 kiosk 树的高度来源和裁切边界**。
                删机器、留盒子:几何一个像素都不许变(`tests/kiosk-viewport-geometry.spec.ts` 守这条)。 */}
            <div
              className="kiosk-viewport"
              style={{
                position: 'fixed', top: 0, left: 0,
                width: '100vw', height: '100vh', overflow: 'hidden', transformOrigin: 'top left',
              }}
            >
              <EngineReadinessProvider>
                <KioskRoutes />
              </EngineReadinessProvider>
            </div>
          </TsumegoProgressProvider>
        </GeometryProvider>
      </VisionProvider>
```

- [x] **Step 3: 删文件**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings
git rm katrain/web/ui/src/kiosk/context/OrientationContext.tsx \
       katrain/web/ui/src/kiosk/components/layout/RotationWrapper.tsx \
       katrain/web/ui/src/kiosk/components/settings/PhysicalBoardStatus.tsx \
       katrain/web/ui/src/kiosk/__tests__/OrientationContext.test.tsx \
       katrain/web/ui/src/kiosk/__tests__/RotationWrapper.test.tsx \
       katrain/web/ui/src/kiosk/__tests__/orientation.integration.test.tsx \
       katrain/web/ui/src/kiosk/__tests__/PhysicalBoardStatus.test.tsx
rg "OrientationProvider|RotationWrapper|useOrientation|PhysicalBoardStatus|rotation-wrapper" katrain/web/ui/src; echo "exit=$?"
```

预期:`exit=1`(零命中)。若 `KioskApp.test.tsx` 断言过 `rotation-wrapper` 这个 testid,把那条断言改成 `.kiosk-viewport`(**不要直接删** —— 那条断言守的是「视口盒子在」,它仍然该被守着)。

- [x] **Step 4: 承重实测(真浏览器,与基线比)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings/katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-settings rev-parse --absolute-git-dir)/settings-baseline"
cp "$BASE/geometry-before.json" test-results/kiosk-viewport-geometry.json
npx playwright test --config=playwright.visual.config.ts tests/kiosk-viewport-geometry.spec.ts
```

预期:通过(三屏几何与改前**逐字段相等**,且都不溢出)。
**不通过就是这只盒子还有别的作用** —— 回 Step 2 把差的那条样式补上,不要去改断言。

- [x] **Step 5: 单测与类型**

```bash
npx vitest run src/kiosk && npx tsc -b
```

- [x] **Step 6: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings
git add -A katrain/web/ui/src/kiosk katrain/web/ui/tests/kiosk-viewport-geometry.spec.ts
git diff --cached --stat
git commit -m "$(cat <<'EOF'
chore(kiosk-settings): 清掉屏幕旋转死代码,保留承重的视口盒子

旋转 2026-07-08 已按「硬件不再旋转」删掉入口,机器还留着。
删机器不删盒子:RotationWrapper 即使 rotation=0 也是整棵树的高度来源与裁切边界,
换成同几何的 div,并用真浏览器量证三屏几何与改前逐字段相等。
顺带删掉零消费者的 PhysicalBoardStatus。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: ST3-关于 · 补一组「关于」(Fan 2026-09-21 裁定)

**Files:**
- Modify: `katrain/web/api/v1/endpoints/health.py`
- Create: `tests/web_ui/test_health_version.py`
- Create: `katrain/web/ui/src/kiosk/api/healthApi.ts`(+ `healthApi.test.ts`)
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`(`GROUPS`、新 section、`lastGroupRef` 挪位)
- Test: `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`(追加)

**Interfaces:**
- Produces:
  - `/api/v1/health` 响应多一个 `version`(字符串,真源 `katrain/core/constants.py:2`);
  - `getHealth(signal?): Promise<KioskHealth>`,`KioskHealth = { status: string; version?: string; engines: { local: string; cloud: string } }`;
  - 纯函数 `engineLine(state: string, t): { text: string; sub?: string; ok: boolean }`。

- [x] **Step 1: 写失败的后端测试**

```python
# tests/web_ui/test_health_version.py
"""`/api/v1/health` 要带版本 —— 设置屏「关于」那一行的唯一来源。

前端拿不到它:`katrain/web/ui/package.json` 的 `version` 是 `0.0.0`,不是产品版本。
断言比的是 `constants.VERSION` 本身,**不是**一个抄过来的字符串字面量 ——
抄一份就等于多一处会走散的真源。
"""
from katrain.core.constants import VERSION


def test_health_reports_the_package_version(client):      # 沿用 tests/web_ui 既有的 client 夹具
    body = client.get("/api/v1/health").json()
    assert body["version"] == VERSION
```

- [x] **Step 2: 跑,确认失败**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings
CI=true uv run pytest tests/web_ui/test_health_version.py -q
```

- [x] **Step 3: 后端一行**

`katrain/web/api/v1/endpoints/health.py`:顶部 `from katrain.core.constants import VERSION`,结尾

```python
    # 版本:设置屏「关于」那一行的唯一来源(前端没有产品版本号,package.json 里是 0.0.0)。
    result = {"status": "ok", "version": VERSION, "engines": engines}
```

- [x] **Step 4: 写失败的前端单测**

```ts
// katrain/web/ui/src/kiosk/api/healthApi.test.ts
import { describe, it, expect } from 'vitest';
import { engineLine } from './healthApi';

const t = (_k: string, d: string) => d;

describe('engineLine', () => {
  it('reachable → 可用', () => {
    expect(engineLine('reachable', t)).toMatchObject({ text: '可用', ok: true });
  });

  it('unconfigured → 没配置(不是「连不上」——它根本没配)', () => {
    expect(engineLine('unconfigured', t)).toMatchObject({ text: '没配置', ok: false });
  });

  it('unreachable → 连不上', () => {
    expect(engineLine('unreachable', t)).toMatchObject({ text: '连不上', ok: false });
  });

  // 错误码归「连不上」,但码要留给运维看 —— 屏上一行人话,副标一行证据。
  it('error_502 → 连不上,副标里带 502', () => {
    const got = engineLine('error_502', t);
    expect(got.text).toBe('连不上');
    expect(got.sub).toContain('502');
  });

  it('认不出来的值不猜,写原样', () => {
    expect(engineLine('weird', t)).toMatchObject({ text: 'weird', ok: false });
  });
});
```

```tsx
// 追加到 SettingsPage.test.tsx
  it('「关于」一组:版本与两个引擎状态都在', async () => {
    mockHealth({ status: 'ok', version: '1.17.1', engines: { local: 'reachable', cloud: 'unconfigured' } });
    renderSettings();
    expect(await screen.findByTestId('about-version')).toHaveTextContent('1.17.1');
    expect(screen.getByTestId('about-engine-local')).toHaveTextContent('可用');
    expect(screen.getByTestId('about-engine-cloud')).toHaveTextContent('没配置');
  });

  it('响应里没有 version 时那一行不渲染 —— 不写「未知」', async () => {
    mockHealth({ status: 'ok', engines: { local: 'reachable', cloud: 'reachable' } });
    renderSettings();
    await screen.findByTestId('about-engine-local');
    expect(screen.queryByTestId('about-version')).toBeNull();
  });

  // 这一屏自己的硬规矩:导航项数 = 分组数,且词一一对应。
  it('导航多了一项「关于」,项数仍等于分组数', () => {
    renderSettings();
    const navItems = screen.getByTestId('settings-nav').querySelectorAll('button');
    expect(navItems).toHaveLength(document.querySelectorAll('[data-group]').length);
    expect(navItems[navItems.length - 1]).toHaveTextContent('关于');
  });

  // 屏上不许出现自铸的 DEVICE_ID(core/config.py:187-190 在没配 env 时每次启动 uuid4)。
  it('不画设备名', async () => {
    mockHealth({ status: 'ok', version: '1.17.1', engines: { local: 'reachable', cloud: 'reachable' } });
    const { container } = renderSettings();
    await screen.findByTestId('about-engine-local');
    expect(container.textContent).not.toMatch(/设备名|device/i);
  });
```

- [x] **Step 5: 前端实现**

```ts
// katrain/web/ui/src/kiosk/api/healthApi.ts
/**
 * 设置屏「关于」那一组的数据。`/api/v1/health` 是既有端点(不鉴权),本轮给它加了 `version`。
 *
 * **拿不到就不画那一行**,不写「未知」——「未知」看起来像一个值,而我们其实是没问到。
 */
export interface KioskHealth {
  status: string;
  /** 可选:老服务端(还没部署这一版)不回它。 */
  version?: string;
  engines: { local: string; cloud: string };
}

export const getHealth = async (signal?: AbortSignal): Promise<KioskHealth> => {
  const res = await fetch('/api/v1/health', { signal });
  if (!res.ok) throw new Error(`health failed: ${res.status}`);
  const body: unknown = await res.json();
  if (!body || typeof body !== 'object' || typeof (body as KioskHealth).engines !== 'object') {
    throw new Error('health payload not recognised');
  }
  return body as KioskHealth;
};

/**
 * 引擎状态翻成人话。**四种状态是四件事**:
 * `unconfigured`(根本没配云端)说成「连不上」会让人去查网络。
 * `error_<code>` 归「连不上」,但把码留在副标里给运维 —— 屏上一行人话,底下一行证据。
 * 认不出来的值**原样写出来**,不猜。
 */
export const engineLine = (
  state: string,
  t: (k: string, d: string) => string,
): { text: string; sub?: string; ok: boolean } => {
  if (state === 'reachable') return { text: t('settings:engine_ok', '可用'), ok: true };
  if (state === 'unconfigured') return { text: t('settings:engine_unset', '没配置'), ok: false };
  if (state === 'unreachable') return { text: t('settings:engine_down', '连不上'), ok: false };
  const code = /^error_(.+)$/.exec(state)?.[1];
  if (code) {
    return {
      text: t('settings:engine_down', '连不上'),
      sub: t('settings:engine_code', '服务端回了 {code}').replace('{code}', code),
      ok: false,
    };
  }
  return { text: state, ok: false };
};
```

`SettingsPage.tsx`:

```tsx
type GroupKey = 'account' | 'board' | 'move' | 'sound' | 'language' | 'about';
```

```tsx
  { key: 'language', zh: '语言', en: 'Language', icon: 'globe-hemisphere-west' },
  // 关于(Fan 2026-09-21)。**设备名不在这里** —— `settings.DEVICE_ID` 在没配
  // `KATRAIN_DEVICE_ID` 时是每次启动自铸的 uuid4(`core/config.py:187-190`),
  // 不是出厂身份;出厂那份在 launcher 手里(`/etc/smartbox/device.json`),本仓读不到。
  // 显示一个自铸 id 就是编,所以等 launcher 给,不自己造。
  { key: 'about', zh: '关于', en: 'About', icon: 'info' },
```

> `icon` 名要用 `shell/icons.tsx` 里**真有**的那个 —— 写之前 `grep -n "':" katrain/web/ui/src/kiosk/shell/icons.tsx | head -40` 看一眼,没有合适的就挑一个已有的,**不要新画图标**(那是另一件事)。

组件里取数(与既有 state 放在一起):

```tsx
  const [health, setHealth] = useState<KioskHealth | null>(null);
  useEffect(() => {
    const ac = new AbortController();
    getHealth(ac.signal).then(setHealth).catch(() => { /* 拿不到就不画这一组的内容,不写假值 */ });
    return () => ac.abort();
  }, []);
```

把 `lastGroupRef` 从语言那一组**挪到**新的最后一组,并在语言组那行去掉 `ref={lastGroupRef}`;新组:

```tsx
        <section className="kiosk-section" data-group="about" ref={lastGroupRef}>
          <KioskSecLabel zh={t('settings:nav_about', '关于')} en="About" />
          <div className="kiosk-rows">
            {health?.version && (
              <div className="kiosk-row" data-testid="about-version">
                <span className="kiosk-row__t"><b>{t('settings:version', '版本')}</b></span>
                <span className="kiosk-row__end"><span className="kiosk-tag">{health.version}</span></span>
              </div>
            )}
            {([
              ['local', t('settings:engine_local', '本机引擎'), health?.engines.local],
              ['cloud', t('settings:engine_cloud', '云端引擎'), health?.engines.cloud],
            ] as const).map(([key, label, state]) => {
              // 还没问到就写「—」,不给灯色 —— 和实体棋盘那一组同一条口径(ST5)。
              const line = state ? engineLine(state, t) : null;
              return (
                <div className="kiosk-row" key={key} data-testid={`about-engine-${key}`}>
                  <span className="kiosk-row__t">
                    <b>{label}</b>
                    {line?.sub && <em>{line.sub}</em>}
                  </span>
                  <span className="kiosk-row__end">
                    <span className={line?.ok ? 'kiosk-tag kiosk-tag--win' : 'kiosk-tag'}>
                      {line ? line.text : '—'}
                    </span>
                  </span>
                </div>
              );
            })}
          </div>
        </section>
```

- [x] **Step 6: 跑,确认通过**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings
CI=true uv run pytest tests/web_ui/test_health_version.py -q
uv run black -l 120 katrain/web/api/v1/endpoints/health.py
cd katrain/web/ui && npx vitest run src/kiosk/api/healthApi.test.ts src/kiosk/__tests__/SettingsPage.test.tsx && npx tsc -b
rg -n "DEVICE_ID|device_id" src/kiosk/pages/SettingsPage.tsx; echo "exit=$?"
```

预期:单测全绿;最后一条 `rg` 零命中(`exit=1`)。

- [x] **Step 7: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings
git add katrain/web/api/v1/endpoints/health.py tests/web_ui/test_health_version.py \
  katrain/web/ui/src/kiosk/api/healthApi.ts katrain/web/ui/src/kiosk/api/healthApi.test.ts \
  katrain/web/ui/src/kiosk/pages/SettingsPage.tsx katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx
git commit -m "$(cat <<'EOF'
feat(kiosk-settings): 补一组「关于」(版本 + 两个引擎状态)

版本由 /api/v1/health 带出来(前端没有产品版本号);四种引擎状态是四件事,
unconfigured 不说成连不上,error_<code> 把码留给运维。
**不画设备名**:DEVICE_ID 在没配 env 时是每次启动自铸的 uuid4,显示它就是编。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: 四图对比(屏 27)、承重(展开态)与 PO 闸

- [x] **Step 1: 展开态承重实测**

```ts
// 追加到 tests/kiosk-screen-27-settings.fourup.spec.ts 旁边的功能 spec(没有就新建 tests/kiosk-settings-expand.spec.ts)
test('展开 AI 段位详情后右栏能滚、页面不溢出、左栏高亮仍对', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  await page.goto('/kiosk/settings');
  await page.getByRole('button', { name: /段位详情/ }).click();
  const zone = page.locator('.kiosk-side__scroll').first();
  const m = await zone.evaluate((el) => ({ s: el.scrollHeight, c: el.clientHeight }));
  expect(m.s).toBeGreaterThan(m.c);
  const doc = await page.evaluate(() => ({
    sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
  }));
  expect(doc.sw).toBeLessThanOrEqual(doc.cw);
});

test('未登录 / 无段位(最空)时,账号那一组不塌', async ({ page }) => {
  // 「先造到会溢出」只对溢出类成立;塌陷类要在**最空**状态下量。
  await page.setViewportSize({ width: 1024, height: 600 });
  await page.goto('/kiosk/settings');           // 未登录桩
  const h = await page.locator('[data-group="account"]').evaluate((el) => el.getBoundingClientRect().height);
  expect(h).toBeGreaterThan(0);
});
```

> 屏 27 这一轮有两处结构变化:ST4 的展开态、ST3-关于 新增的一组(导航六项、右栏多一段)。四图要一起看。

- [x] **Step 2: 四图重取(屏 27),跑两次排抖动**

```bash
npm run fourup && cp -r ../../../superpowers/tracks/kiosk-go-shell-align/visual/27* /tmp/fourup-run1
npm run fourup
# 比两次的实现图:差异小于本屏抖动底(DOM 屏约 200 像素)就是抖动,不是内容变化
```

只提交真的变了的那几张;其余 `git checkout HEAD -- <屏目录>` 还原。

- [x] **Step 3: 人眼看四图并交 Fan 确认**

四张一起看(参考 / 实现 / 并排 / 差异),逐项比构图、间距、层级、字体色彩、文案、状态语义。
**这一关要 Fan 明确确认**(CLAUDE.md 硬性关卡),没确认之前不要报完成。

- [x] **Step 4: PO 闸**

```bash
npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-contract.spec.ts
```

- [x] **Step 5: 提交**

```bash
git add katrain/web/ui/tests/ superpowers/tracks/kiosk-go-shell-align/visual/
git commit -m "$(cat <<'EOF'
test(kiosk-settings): 屏 27 展开态承重与四图重取

展开是会长的东西 ⇒ 造满了量;账号组按「塌陷在最空状态下量」再量一次。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: 收尾验证与交付说明

- [x] **Step 1: 基线 diff(**比名字不比条数** —— ST6 删了四个测试文件)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings/katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-settings rev-parse --absolute-git-dir)/settings-baseline"
npx vitest run --reporter=json --outputFile="$BASE/after.json" > "$BASE/after.log" 2>&1
node "$BASE/failed-names.cjs" "$BASE/after.json" > "$BASE/after-failed.txt"
comm -13 "$BASE/before-failed.txt" "$BASE/after-failed.txt"
```

预期:空。

- [x] **Step 2: 类型、两套构建、边界**

```bash
npx tsc -b && npm run build && npm run build:kiosk-2d; echo "exit=$?"
npx eslint src/hooks/useSessionBase.ts src/kiosk/pages/SettingsPage.tsx src/kiosk/components/settings src/kiosk/KioskApp.tsx
```

- [x] **Step 3: 新增 key 清单与交付说明**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-settings
git diff 7a152df1..HEAD -- katrain/web/ui/src | grep -o "t('[a-z]*:[a-z_0-9]*'" | sort -u
```

交付说明写清:① 做了 ST1 余下一半、ST4、ST5、ST6、ST3-关于(Fan 2026-09-21 裁定);ST2 / ST3 剩下两组 / ST7 等 Fan;② 新增 key 清单;
③ 四图结论(附 Fan 确认)与 ST6 的几何比对结果;④ 还没上板,建议的上板走查(关掉音效后去研究屏与摆谱屏;没接摄像头的机器上看那一组)。

---

