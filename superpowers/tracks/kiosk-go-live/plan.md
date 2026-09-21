# 围棋 kiosk · 直播(kiosk-go-live)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让盒上用户从棋谱屏走得到**完整的直播列表和赛程**、走得回来,并且那一页上不再出现编出来的胜率和走不回来的外链;另外用一个有界探针把「直播源到底给不给剩余时间」查清楚落档。

**Architecture:** 纯前端 + 一份调研文档,没有后端与数据契约改动。
- L1:重写 `kiosk/pages/LivePage.tsx` —— 接壳(页控条 + 滚动区 + 分段 + `.kiosk-row`),不重排信息结构;新建共享钩子 `hooks/live/useUpcomingMatches.ts` 取赛程;棋谱屏直播那一组末尾加一行入口;观战屏返回去向读 `location.state.from`。
- L2:探针只读代码与真实响应,结论写 `findings-clock.md`,不动产品代码(除了把结论补进 `LiveMatchPage.tsx` 的钟注释)。

**Tech Stack:** React 18 + TypeScript + Vite,vitest + @testing-library/react,Playwright(承重实测、真运行时预览、PO 闸)。

**Spec:** `superpowers/tracks/kiosk-go-live/prd.md`

## Global Constraints

> **开工前先读 `prd.md` §6.0**:四条新赛道的共享文件归属与合并顺序(尤其:**先合 `feature/kiosk-go-kifu` 再动 `KifuPage.tsx`**)。与本 plan 冲突时以 §6.0 为准。

- 在 worktree `/Users/fan/Repositories/katrain-kiosk-go-live`(分支 `feature/kiosk-go-live`,基线 develop `7a152df1`)里开发;**不 push、不合并 develop**,合并由 Fan 决定;不在别的 worktree 里 checkout(别人的基线实验会被冲掉)。
- 新建 worktree 后依赖要重装:`cd katrain/web/ui && npm ci`。Python 侧本轮不需要(无 Python 改动)。
- 触及共享领地(`src/hooks/live/`)⇒ `npm run build` 与 `npm run build:kiosk-2d`(含 `verify:kiosk-2d`)都必须绿;共享文件**不许** import `src/kiosk/**` / `src/galaxy/**` / `src/pages/**`。
- 类型检查用 `npx tsc -b`(`npx tsc --noEmit` 检查 0 个文件,无效);`*.test.tsx` 不在 tsc 范围内。
- 盒上 `token` 恒为 `null`:任何「发不发请求 / 渲不渲染」的判别位用 `isAuthenticated`,不用 `token`。直播接口本身不需要登录。
- 新文案一律 `t('ns:key','中文默认')`,**不往 `.po` 里加 key**;沿用 PO 里已有 key 时中文默认串要与 cn PO 的 msgstr 逐字一致(`kiosk-shell-contract.spec.ts` 那条闸会查)。
- **不许画 `current_winrate`**:`pandanet.py:125` 无条件写 `0.5`、`xingzhen.py` 取不到时退回 `0.5` ——「真的均势」和「没有这个数」在库里是同一个值。屏上的胜率只认盒内 KataGo 的 `analysis[n].winrate`。
- **不许 `target="_blank"`**:盒上 chromium 跑 `--kiosk`,新标签页没有地址栏也没有返回键。
- **不改 `src/components/live/*`**(galaxy 在用)。
- 视觉 / 布局改动走 CLAUDE.md 的四图与承重关卡;**新的直播列表屏是稿外屏,没有参考图 —— 不要伪造一张参考图凑四图**(见 PRD §7)。
- 提交信息用中文,风格跟 `git log`(`fix(kiosk): …` / `feat(kiosk-live): …`),结尾加一行 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`。`git add` 逐个写文件名;新建文件 add 之后用 `git diff --cached --stat` 确认确实进了暂存区(`.gitignore` 会静默吞掉某些文件名)。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `katrain/web/ui/src/hooks/live/useUpcomingMatches.ts` | **新建**(共享领地) | 赛程数据钩子:`LiveAPI.getUpcoming` + 30 分钟轮询 + 错误 |
| `katrain/web/ui/src/hooks/live/useUpcomingMatches.test.ts` | **新建** | 钩子单测 |
| `katrain/web/ui/src/kiosk/pages/LivePage.tsx` | 整文件重写 | 屏「直播列表」(稿外屏):页控条 + 三分段 + 行列表 |
| `katrain/web/ui/src/kiosk/utils/scheduleLabel.ts` | **新建** | 赛程时间的中文标签(今天 / 明天 / MM-DD + HH:mm) |
| `katrain/web/ui/src/kiosk/utils/scheduleLabel.test.ts` | **新建** | 纯函数单测(含跨日历天的边界) |
| `katrain/web/ui/src/kiosk/__tests__/LivePage.test.tsx` | 整文件重写 | 新结构的单测(旧的 163 行按 MUI 结构写) |
| `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` | 改 `:378-417` 那一段末尾 | 加「全部直播 · 赛程」一行入口 |
| `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx` | 追加 | 入口单测 |
| `katrain/web/ui/src/kiosk/pages/LiveMatchPage.tsx` | 改 `:145-152`、`:249-253` | 返回去向读 `location.state.from` |
| `katrain/web/ui/src/kiosk/__tests__/LiveMatchPage.test.tsx` | 追加 | 两条返回去向 |
| `katrain/web/ui/tests/kiosk-live-list.spec.ts` | **新建** | 承重实测(50 条 + 20 条时列表可滚、页面不溢出)+ 一帧预览 |
| `superpowers/tracks/kiosk-go-live/findings-clock.md` | **新建** | L2 探针结论 |
| `superpowers/tracks/kiosk-go-live/visual/live-list/README.md` + 实现图 | **新建** | 稿外屏的实现图存档(写明无参考图) |

任务顺序:Task 1 基线 → Task 2 赛程钩子 → Task 3 时间标签 → Task 4 列表屏 → Task 5 两处接线 → Task 6 承重 + 预览 + 存档 → Task 7 L2 探针 → Task 8 收尾。Task 2/3 互相独立;Task 4 依赖 2、3;Task 5 依赖 4。

---

### Task 1: 核对 worktree、装依赖、记录基线

**Files:**
- 不改仓内文件。基线写到 git 目录下(不被跟踪):`$(git rev-parse --absolute-git-dir)/live-baseline/`

**Interfaces:**
- Produces:`$BASE/before-failed.txt`(失败用例名字集合)与 `$BASE/failed-names.cjs`(Task 8 复用)。

- [ ] **Step 1: 核对 worktree**

```bash
cd /Users/fan/Repositories/katrain
# worktree 已于 2026-09-21 建好,本步只核对,不要再 add
git -C /Users/fan/Repositories/katrain-kiosk-go-live rev-parse --abbrev-ref HEAD            # 预期 feature/kiosk-go-live
git -C /Users/fan/Repositories/katrain-kiosk-go-live merge-base --is-ancestor 7a152df1 HEAD && echo base-ok
cd /Users/fan/Repositories/katrain-kiosk-go-live && git rev-parse --abbrev-ref HEAD && git log --oneline -1
```

预期:分支 `feature/kiosk-go-live`,输出 `base-ok`(HEAD 是 develop `7a152df1` 之上的文档提交)。

- [ ] **Step 2: 装依赖**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live/katrain/web/ui && npm ci
```

预期:退出码 0。

- [ ] **Step 3: 写失败名提取脚本**

```bash
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-live rev-parse --absolute-git-dir)/live-baseline"
mkdir -p "$BASE"
cat > "$BASE/failed-names.cjs" <<'EOF'
// 从 vitest JSON 报告里取「失败用例的名字集合」。基线比的是名字,不是条数。
const report = require(process.argv[2]);
const out = [];
for (const file of report.testResults) {
  const rel = file.name.replace(/^.*\/katrain\/web\/ui\//, '');
  if (file.status === 'failed' && file.assertionResults.length === 0) out.push(`${rel} :: <文件级失败>`);
  for (const a of file.assertionResults) {
    if (a.status === 'failed') out.push(`${rel} :: ${a.fullName}`);
  }
}
console.log(out.sort().join('\n'));
EOF
```

- [ ] **Step 4: 跑全量 vitest 与 tsc,落基线**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live/katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-live rev-parse --absolute-git-dir)/live-baseline"
npx vitest run --reporter=json --outputFile="$BASE/before.json" > "$BASE/before.log" 2>&1; echo "vitest_exit=$?"
node "$BASE/failed-names.cjs" "$BASE/before.json" > "$BASE/before-failed.txt"
wc -l < "$BASE/before-failed.txt"
npx tsc -b; echo "tsc_exit=$?"
```

预期:`before-failed.txt` 写出(行数照实记,可以是 0);`tsc_exit=0`。**不提交**。

---

### Task 2: 赛程数据钩子 `useUpcomingMatches`

**Files:**
- Create: `katrain/web/ui/src/hooks/live/useUpcomingMatches.ts`
- Test: `katrain/web/ui/src/hooks/live/useUpcomingMatches.test.ts`

**Interfaces:**
- Consumes:`LiveAPI.getUpcoming(limit: number, lang?: string): Promise<{ matches: UpcomingMatch[] }>`(`src/api/live.ts:147`);`UpcomingMatch`(`src/types/live.ts:41-50`);`useTranslation()` 的 `lang`。
- Produces:`useUpcomingMatches(options?: { limit?: number; pollIntervalMs?: number }): { upcoming: UpcomingMatch[]; loading: boolean; error: Error | null }`。

- [ ] **Step 1: 写失败的单测**

```ts
// katrain/web/ui/src/hooks/live/useUpcomingMatches.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useUpcomingMatches } from './useUpcomingMatches';
import { LiveAPI } from '../../api/live';

vi.mock('../useTranslation', () => ({ useTranslation: () => ({ t: (_k: string, d: string) => d, lang: 'cn' }) }));

const row = (id: string) => ({
  id, tournament: '名人战', round_name: '第 3 局', scheduled_time: '2026-09-21T11:00:00Z',
  player_black: '申真谞', player_white: '柯洁', source: 'foxwq' as const, source_url: 'https://example.com/x',
});

describe('useUpcomingMatches', () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

  it('取到赛程后 loading 落下、数据出来', async () => {
    vi.spyOn(LiveAPI, 'getUpcoming').mockResolvedValue({ matches: [row('u1')] });
    const { result } = renderHook(() => useUpcomingMatches({ limit: 20 }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.upcoming.map((m) => m.id)).toEqual(['u1']);
    expect(result.current.error).toBeNull();
  });

  it('失败时留下 error,并且**不把 upcoming 改成空数组冒充「没有比赛」**', async () => {
    vi.spyOn(LiveAPI, 'getUpcoming')
      .mockResolvedValueOnce({ matches: [row('u1')] })
      .mockRejectedValueOnce(new Error('boom'));
    const { result } = renderHook(() => useUpcomingMatches({ limit: 20, pollIntervalMs: 1000 }));
    await waitFor(() => expect(result.current.upcoming).toHaveLength(1));
    await vi.advanceTimersByTimeAsync(1100);
    await waitFor(() => expect(result.current.error).toBeInstanceOf(Error));
    expect(result.current.upcoming).toHaveLength(1); // 上一批还在,没有被清空
  });
});
```

- [ ] **Step 2: 跑,确认它失败**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live/katrain/web/ui
npx vitest run src/hooks/live/useUpcomingMatches.test.ts
```

预期:FAIL,`Failed to resolve import "./useUpcomingMatches"`。

- [ ] **Step 3: 写实现**

```ts
// katrain/web/ui/src/hooks/live/useUpcomingMatches.ts
import { useCallback, useEffect, useState } from 'react';

import { LiveAPI } from '../../api/live';
import type { UpcomingMatch } from '../../types/live';
import { useTranslation } from '../useTranslation';

interface Options {
  limit?: number;
  /** 0 关掉轮询。赛程是**按天变的东西**,默认 30 分钟一次,和 galaxy 的 `UpcomingList` 同一个数。 */
  pollIntervalMs?: number;
}

/**
 * 赛程(「即将开始」)。galaxy 的 `components/live/UpcomingList.tsx` 自己在组件里抓,
 * 那份**不动** —— 它带着 MUI 卡片和 `target="_blank"` 外链,盒上两样都不能要。
 * 这里只取数;怎么画由消费方决定。
 *
 * ⚠️ **失败时不清空上一批**:「拉不到」和「今天没有比赛」在屏上必须是两句话,
 * 把 `upcoming` 清成 `[]` 就等于替用户断言后者。
 */
export function useUpcomingMatches({ limit = 20, pollIntervalMs = 30 * 60 * 1000 }: Options = {}) {
  const { lang } = useTranslation();
  const [upcoming, setUpcoming] = useState<UpcomingMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchUpcoming = useCallback(async () => {
    try {
      const data = await LiveAPI.getUpcoming(limit, lang);
      setUpcoming(data.matches);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch upcoming'));
    } finally {
      setLoading(false);
    }
  }, [limit, lang]);

  useEffect(() => { void fetchUpcoming(); }, [fetchUpcoming]);

  useEffect(() => {
    if (pollIntervalMs <= 0) return;
    const timer = setInterval(() => { void fetchUpcoming(); }, pollIntervalMs);
    return () => clearInterval(timer);
  }, [fetchUpcoming, pollIntervalMs]);

  return { upcoming, loading, error };
}
```

- [ ] **Step 4: 跑,确认它通过**

```bash
npx vitest run src/hooks/live/useUpcomingMatches.test.ts
```

预期:2 passed。

- [ ] **Step 5: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live
git add katrain/web/ui/src/hooks/live/useUpcomingMatches.ts katrain/web/ui/src/hooks/live/useUpcomingMatches.test.ts
git diff --cached --stat
git commit -m "$(cat <<'EOF'
feat(kiosk-live): 赛程数据钩子 useUpcomingMatches

盒上要显示「即将开始」,而 galaxy 那份 UpcomingList 自带 MUI 与 _blank 外链,
不能直接用。只取数,画法留给消费方。失败时不清空上一批 ——
「拉不到」和「今天没有比赛」在屏上是两句话。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 赛程时间标签 `scheduleLabel`

**Files:**
- Create: `katrain/web/ui/src/kiosk/utils/scheduleLabel.ts`
- Test: `katrain/web/ui/src/kiosk/utils/scheduleLabel.test.ts`

**Interfaces:**
- Produces:`scheduleLabel(ts: number, t: (k: string, d: string) => string, now?: number): string`。
- 同族参考(不复用,方向相反):`kiosk/utils/whenLabel.ts` 说的是过去(今天 / 昨天 / 前天 / MM-DD)。

- [ ] **Step 1: 写失败的单测**

```ts
// katrain/web/ui/src/kiosk/utils/scheduleLabel.test.ts
import { describe, it, expect } from 'vitest';
import { scheduleLabel } from './scheduleLabel';

const t = (_k: string, d: string) => d;
const at = (iso: string) => new Date(iso).getTime();

describe('scheduleLabel', () => {
  const now = at('2026-09-20T20:00:00');

  it('同一日历天写「今天 HH:mm」', () => {
    expect(scheduleLabel(at('2026-09-20T23:30:00'), t, now)).toBe('今天 23:30');
  });

  // 跨的是**日历天**不是 24 小时:23:50 看的赛程,次日 00:10 开赛要写「明天」。
  it('下一个日历天写「明天 HH:mm」,哪怕只差 20 分钟', () => {
    expect(scheduleLabel(at('2026-09-21T00:10:00'), t, at('2026-09-20T23:50:00'))).toBe('明天 00:10');
  });

  it('更远的写「MM-DD HH:mm」', () => {
    expect(scheduleLabel(at('2026-09-23T11:00:00'), t, now)).toBe('09-23 11:00');
  });

  it('已经过去的时刻照实写日期,不写「今天」冒充还没开始', () => {
    expect(scheduleLabel(at('2026-09-18T11:00:00'), t, now)).toBe('09-18 11:00');
  });
});
```

- [ ] **Step 2: 跑,确认它失败**

```bash
npx vitest run src/kiosk/utils/scheduleLabel.test.ts
```

预期:FAIL(模块不存在)。

- [ ] **Step 3: 写实现**

```ts
// katrain/web/ui/src/kiosk/utils/scheduleLabel.ts
/**
 * 赛程时刻的中文标签:「今天 19:00 / 明天 11:00 / 09-23 11:00」。
 *
 * **跨的是日历天,不是 24 小时** —— 23:50 看到的、次日 00:10 开赛的那一场,
 * 说「今天」是错的(`whenLabel.ts` 为过去的那一半写过同一条理由)。
 * 已经过去的时刻一律落到日期格式:说「今天」会让人以为还没开始。
 */
export function scheduleLabel(ts: number, t: (k: string, d: string) => string, now = Date.now()): string {
  const then = new Date(ts);
  const hhmm = `${String(then.getHours()).padStart(2, '0')}:${String(then.getMinutes()).padStart(2, '0')}`;
  const mmdd = `${String(then.getMonth() + 1).padStart(2, '0')}-${String(then.getDate()).padStart(2, '0')}`;
  const days = Math.round(
    (new Date(ts).setHours(0, 0, 0, 0) - new Date(now).setHours(0, 0, 0, 0)) / 86400000,
  );
  if (days === 0 && ts >= now) return `${t('live:today', '今天')} ${hhmm}`;
  if (days === 1) return `${t('live:tomorrow', '明天')} ${hhmm}`;
  return `${mmdd} ${hhmm}`;
}
```

- [ ] **Step 4: 跑,确认它通过**

```bash
npx vitest run src/kiosk/utils/scheduleLabel.test.ts
```

预期:4 passed。

- [ ] **Step 5: 提交**

```bash
git add katrain/web/ui/src/kiosk/utils/scheduleLabel.ts katrain/web/ui/src/kiosk/utils/scheduleLabel.test.ts
git commit -m "$(cat <<'EOF'
feat(kiosk-live): 赛程时刻标签 scheduleLabel

跨日历天不跨 24 小时;已经过去的时刻写日期,不写「今天」冒充还没开始。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 直播列表屏接壳重写

**Files:**
- Modify(整文件重写): `katrain/web/ui/src/kiosk/pages/LivePage.tsx`
- Test(整文件重写): `katrain/web/ui/src/kiosk/__tests__/LivePage.test.tsx`

**Interfaces:**
- Consumes:`useLiveMatches({ limit })`(`src/hooks/live/useLiveMatches.ts:22`,返回 `{ matches, liveCount, total, loading, error }`);Task 2 的 `useUpcomingMatches`;Task 3 的 `scheduleLabel`;`liveSourceLabel`(`src/utils/liveSources.ts`);外壳 `KioskPagebar` / `KioskScrollZone` / `KioskSecLabel`。
- Produces:路由 `/kiosk/live` 的页面;跳观战时带 `state: { from: 'live' }`(Task 5 的 `LiveMatchPage` 读它)。

- [ ] **Step 1: 写失败的单测(整文件替换)**

```tsx
// katrain/web/ui/src/kiosk/__tests__/LivePage.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import LivePage from '../pages/LivePage';
import { LiveAPI } from '../../api/live';

vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_k: string, d: string) => d, lang: 'cn' }),
}));

const match = (id: string, status: 'live' | 'finished', winrate = 0.5) => ({
  id, source: 'xingzhen' as const, tournament: `${id} 杯`, round_name: '第 1 轮',
  date: '2026-09-20T03:00:00Z', player_black: '黑方', player_white: '白方',
  black_rank: '9p', white_rank: '9p', status, result: status === 'finished' ? 'B+R' : null,
  move_count: 120, current_winrate: winrate, current_score: 0, last_updated: '2026-09-20T05:00:00Z',
  board_size: 19, komi: 7.5, rules: 'chinese',
});

const upcoming = (id: string) => ({
  id, tournament: '名人战', round_name: '第 3 局', scheduled_time: '2026-09-21T11:00:00Z',
  player_black: '申真谞', player_white: '柯洁', source: 'foxwq' as const, source_url: 'https://example.com/x',
});

const renderPage = () => render(
  <MemoryRouter initialEntries={['/kiosk/live']}>
    <Routes>
      <Route path="/kiosk/live" element={<LivePage />} />
      <Route path="/kiosk/kifu" element={<div data-testid="kifu-page" />} />
      <Route path="/kiosk/live/:matchId" element={<div data-testid="watch-page" />} />
    </Routes>
  </MemoryRouter>,
);

describe('屏 直播列表 /kiosk/live', () => {
  beforeEach(() => {
    vi.spyOn(LiveAPI, 'getMatches').mockResolvedValue({
      matches: [...Array(8)].map((_, i) => match(`m${i}`, i < 5 ? 'live' : 'finished')),
      total: 8, live_count: 5,
    });
    vi.spyOn(LiveAPI, 'getUpcoming').mockResolvedValue({ matches: [upcoming('u1')] });
  });
  afterEach(() => vi.restoreAllMocks());

  it('有返回键,点它回棋谱', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /棋谱/ }));
    expect(screen.getByTestId('kifu-page')).toBeInTheDocument();
  });

  it('直播中那一段把 5 条全画出来(棋谱屏只画 4 行,这一屏是「更多」的去处)', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('live-row')).toHaveLength(5));
  });

  it('切到「已结束」分段看到另外 3 条', async () => {
    renderPage();
    await screen.findAllByTestId('live-row');
    await userEvent.click(screen.getByRole('button', { name: '已结束' }));
    await waitFor(() => expect(screen.getAllByTestId('live-row')).toHaveLength(3));
  });

  it('切到「即将开始」看到赛程行,且整页没有一个 target="_blank"', async () => {
    const { container } = renderPage();
    await screen.findAllByTestId('live-row');
    await userEvent.click(screen.getByRole('button', { name: '即将开始' }));
    expect(await screen.findByTestId('upcoming-row')).toHaveTextContent('名人战');
    expect(container.querySelectorAll('[target="_blank"]')).toHaveLength(0);
  });

  it('点一行进观战,并带上 from=live', async () => {
    renderPage();
    await userEvent.click((await screen.findAllByTestId('live-row'))[0]);
    expect(screen.getByTestId('watch-page')).toBeInTheDocument();
  });

  // `current_winrate` 在 pandanet 源里恒为写死的 0.5、xingzhen 取不到时也退回 0.5 ——
  // 屏上画它就是编。屏 18 已经为同一件事裁过一次。
  it('不画 current_winrate', async () => {
    const { container } = renderPage();
    await screen.findAllByTestId('live-row');
    expect(container.textContent).not.toMatch(/%/);
    expect(container.querySelector('[data-testid="live-winrate"]')).toBeNull();
  });

  it('整页没有 MUI 组件', async () => {
    const { container } = renderPage();
    await screen.findAllByTestId('live-row');
    expect(container.querySelectorAll('[class*="Mui"]')).toHaveLength(0);
  });

  it('拉不到直播时说「读不到」,不说「现在没有直播」', async () => {
    vi.spyOn(LiveAPI, 'getMatches').mockRejectedValue(new Error('boom'));
    renderPage();
    expect(await screen.findByTestId('live-list-error')).toBeInTheDocument();
    expect(screen.queryByText('现在没有比赛在下')).toBeNull();
  });
});
```

- [ ] **Step 2: 跑,确认它失败**

```bash
npx vitest run src/kiosk/__tests__/LivePage.test.tsx
```

预期:FAIL(旧页面没有 `live-row` 等 testid,且渲染出 MUI 类)。

- [ ] **Step 3: 重写 `LivePage.tsx`**

```tsx
// katrain/web/ui/src/kiosk/pages/LivePage.tsx
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useLiveMatches } from '../../hooks/live/useLiveMatches';
import { useUpcomingMatches } from '../../hooks/live/useUpcomingMatches';
import { useTranslation } from '../../hooks/useTranslation';
import { liveSourceLabel } from '../../utils/liveSources';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { scheduleLabel } from '../utils/scheduleLabel';

type Tab = 'live' | 'finished' | 'upcoming';

/**
 * 屏「直播列表」`/kiosk/live` —— L2 布局 B(通栏)。**稿子里没有这一屏**:
 * 它属于 Fan 2026-08-20 裁的「稿外五屏,只接壳不重排」那一组,所以这次只换壳
 * (页控条 + 滚动区 + 分段 + `.kiosk-row`),信息结构照旧是「一列比赛 + 一段赛程」。
 *
 * ## 为什么它以前等于不存在
 *
 * 全 kiosk 没有一处跳到这条路由,它自己也没有返回键、没有 Dock(L2)——
 * 进去出不来。棋谱屏只画前 4 行、没有「更多」,赛程只在这一页渲染。
 * 这一轮补了棋谱屏的入口(`KifuPage.tsx` 直播那一组末行),这一屏才真正上线。
 *
 * ## 上线前必须去掉的三样东西
 *
 * ① **棋盘预览**(`LiveBoard`):canvas,盒上那一族实测只有 6–15fps,而列表页不需要盘。
 * ② **胜率条**:`current_winrate` 在 pandanet 源里恒为写死的 `0.5`、xingzhen 取不到时也退回
 *    `0.5` —— 「真的均势」和「没有这个数」在库里是同一个值。屏 18 已经为同一件事裁过一次。
 * ③ **`target="_blank"` 外链**:盒上 chromium 跑 `--kiosk`,新标签页没有地址栏也没有返回键。
 *    来源改成一行字。
 *
 * ## 「没有」和「读不到」是两句话
 *
 * 取数失败时说「读不到」,不说「现在没有比赛在下」—— 后者是替上游断言。
 */
const LivePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('live');

  const { matches, loading, error } = useLiveMatches({ limit: 50 });
  const { upcoming, loading: upLoading, error: upError } = useUpcomingMatches({ limit: 20 });

  const live = useMemo(() => matches.filter((m) => m.status === 'live'), [matches]);
  const finished = useMemo(() => matches.filter((m) => m.status !== 'live'), [matches]);
  const rows = tab === 'live' ? live : finished;

  const secValue = tab === 'upcoming'
    ? `${upcoming.length} ${t('live:count_unit', '场')}`
    : `${rows.length} ${t('live:count_unit', '场')}`;

  return (
    <div className="kiosk-layout-b" data-testid="live-page">
      <KioskPagebar
        testId="live-list-pagebar"
        backLabel={t('live:back_kifu', '棋谱')}
        onBack={() => navigate('/kiosk/kifu')}
        title={t('live:list_title', '职业直播')}
        sub="Live"
        segment={{
          value: tab,
          options: [
            ['live', t('live:tab_live', '直播中')],
            ['finished', t('live:tab_finished', '已结束')],
            ['upcoming', t('live:tab_upcoming', '即将开始')],
          ] as const,
          onChange: (next) => setTab(next as Tab),
          ariaLabel: t('live:list_title', '职业直播'),
        }}
      />

      <KioskScrollZone resetKey={tab}>
        <section className="kiosk-section">
          <KioskSecLabel
            zh={tab === 'upcoming' ? t('live:tab_upcoming', '即将开始') : t('live:list_title', '职业直播')}
            en={tab === 'upcoming' ? 'Upcoming' : 'Live'}
            value={secValue}
          />

          {tab === 'upcoming' ? (
            upError && upcoming.length === 0 ? (
              <div className="empty" data-testid="upcoming-error">
                <h4>{t('live:upcoming_failed', '赛程读不到')}</h4>
                <p>{t('live:retry_later', '稍后再看一次。')}</p>
              </div>
            ) : upLoading && upcoming.length === 0 ? (
              <div className="empty"><h4>{t('live:loading_upcoming', '正在读赛程')}</h4></div>
            ) : upcoming.length === 0 ? (
              <div className="empty"><h4>{t('live:no_upcoming', '这几天没有排定的比赛')}</h4></div>
            ) : (
              <div className="kiosk-rows">
                {upcoming.map((u) => (
                  /* 赛程行**不可点**:这一场还没开始,没有可看的谱。
                     来源写成字,不做外链(见页面头注 ③)。 */
                  <div className="kiosk-row" key={u.id} data-testid="upcoming-row">
                    <span className="kiosk-row__lead">
                      {scheduleLabel(new Date(u.scheduled_time).getTime(), t)}
                    </span>
                    <span className="kiosk-row__t">
                      <b>{[u.tournament, u.round_name].filter(Boolean).join(' · ')}</b>
                      <em>
                        {u.player_black && u.player_white
                          ? `${u.player_black} ${t('live:versus', '对')} ${u.player_white}`
                          : t('live:pairing_tbd', '对阵未定')}
                        {' · '}
                        {liveSourceLabel(u.source)}
                      </em>
                    </span>
                    <span className="kiosk-row__end">
                      <span className="kiosk-tag">{t('live:not_started', '未开始')}</span>
                    </span>
                  </div>
                ))}
              </div>
            )
          ) : error && matches.length === 0 ? (
            <div className="empty" data-testid="live-list-error">
              <h4>{t('live:list_failed', '直播读不到')}</h4>
              <p>{t('live:retry_later', '稍后再看一次。')}</p>
            </div>
          ) : loading && matches.length === 0 ? (
            <div className="empty"><h4>{t('live:loading_list', '正在读直播')}</h4></div>
          ) : rows.length === 0 ? (
            <div className="empty">
              <h4>{tab === 'live'
                ? t('live:none_live', '现在没有比赛在下')
                : t('live:none_finished', '最近没有结束的比赛')}</h4>
            </div>
          ) : (
            <div className="kiosk-rows">
              {rows.map((m) => (
                <button
                  type="button"
                  className="kiosk-row"
                  key={m.id}
                  data-testid="live-row"
                  onClick={() => navigate(`/kiosk/live/${m.id}`, { state: { from: 'live' } })}
                >
                  <span className="kiosk-row__lead">
                    {m.status === 'live'
                      ? `${t('live:move_ordinal', '第')} ${m.move_count} ${t('live:moves_unit', '手')}`
                      : scheduleLabel(new Date(m.date).getTime(), t)}
                  </span>
                  <span className="kiosk-row__t">
                    <b>{[m.tournament, m.round_name].filter(Boolean).join(' · ')}</b>
                    <em>
                      {`${m.player_black} ${t('live:versus', '对')} ${m.player_white}`}
                      {' · '}
                      {liveSourceLabel(m.source)}
                      {m.status !== 'live' && m.result ? ` · ${m.result}` : ''}
                    </em>
                  </span>
                  <span className="kiosk-row__end">
                    {m.status === 'live'
                      ? <span className="kiosk-tag kiosk-tag--live">{t('live:live_now', '直播中')}</span>
                      : <span className="kiosk-tag">{t('live:ended', '已结束')}</span>}
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>
      </KioskScrollZone>
    </div>
  );
};

export default LivePage;
```

- [ ] **Step 4: 跑,确认它通过**

```bash
npx vitest run src/kiosk/__tests__/LivePage.test.tsx
npx tsc -b
```

预期:8 passed;`tsc -b` 退出码 0。

- [ ] **Step 5: 确认旧组件真的不再被这一屏引用**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live
grep -n "LiveBoard\|PlaybackBar\|MatchList\|UpcomingList\|@mui" katrain/web/ui/src/kiosk/pages/LivePage.tsx; echo "exit=$?"
```

预期:零命中(`exit=1`)。galaxy 那三个组件本身**不动**。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/ui/src/kiosk/pages/LivePage.tsx katrain/web/ui/src/kiosk/__tests__/LivePage.test.tsx
git commit -m "$(cat <<'EOF'
feat(kiosk-live): 直播列表屏接壳重写

页控条 + 三分段 + 行列表,信息结构照旧(稿外屏只接壳不重排)。
去掉三样上线前不能留的东西:canvas 棋盘预览、写死 0.5 的胜率条、_blank 外链。
「没有」和「读不到」分成两句话。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 棋谱屏入口与观战屏返回去向

> ⚠️ **先确认 `feature/kiosk-go-kifu` 是否已并入 develop**(PRD §6.0)。已并:先 `git merge develop` 再做这一步。未并:照做,合并时由后合的一方解 `KifuPage.tsx` 的文本冲突。

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/KifuPage.tsx`(直播那一组 `:378-417` 的 `</div>` 之前)
- Modify: `katrain/web/ui/src/kiosk/pages/LiveMatchPage.tsx`(`:145-152` 与 `:249-253` 两处 `onBack`)
- Test: `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx`(追加)、`katrain/web/ui/src/kiosk/__tests__/LiveMatchPage.test.tsx`(追加)

**Interfaces:**
- Consumes:Task 4 传出的 `location.state.from === 'live'`。
- Produces:无新导出。

- [ ] **Step 1: 写失败的单测(两处各一条,追加到既有文件末尾)**

```tsx
// 追加到 katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx 的顶层 describe 里
  it('直播那一组末尾有「全部直播 · 赛程」入口,点它进 /kiosk/live', async () => {
    renderKifuPage(); // 复用本文件既有的渲染助手与 mock
    await userEvent.click(await screen.findByTestId('kifu-live-more'));
    expect(screen.getByTestId('live-page-stub')).toBeInTheDocument();
  });
```

```tsx
// 追加到 katrain/web/ui/src/kiosk/__tests__/LiveMatchPage.test.tsx
  it('从直播列表进来的,返回回列表', async () => {
    renderWatchPage({ state: { from: 'live' } });
    await userEvent.click(await screen.findByRole('button', { name: /返回|直播/ }));
    expect(screen.getByTestId('live-page-stub')).toBeInTheDocument();
  });

  it('不带来路的(从棋谱屏进来),返回回棋谱 —— 今天的行为不变', async () => {
    renderWatchPage();
    await userEvent.click(await screen.findByRole('button', { name: /棋谱/ }));
    expect(screen.getByTestId('kifu-page-stub')).toBeInTheDocument();
  });
```

> 两个测试文件里的 `renderKifuPage` / `renderWatchPage` 若不存在,就照本文件既有写法补一个:`MemoryRouter initialEntries={[{ pathname, state }]}` + `Routes` 里挂 `/kiosk/live` → `<div data-testid="live-page-stub" />`、`/kiosk/kifu` → `<div data-testid="kifu-page-stub" />`。

- [ ] **Step 2: 跑,确认它失败**

```bash
npx vitest run src/kiosk/__tests__/KifuPage.test.tsx src/kiosk/__tests__/LiveMatchPage.test.tsx
```

预期:两条新用例 FAIL(找不到 `kifu-live-more`;返回恒去棋谱)。

- [ ] **Step 3: 棋谱屏加入口**

在 `KifuPage.tsx` 直播那一组的 `{matches.slice(0, 4).map(...)}` 之后、`</div>`(`.kiosk-rows` 的结束)之前插入:

```tsx
              {/* 「更多」的去处。后端一次给 8 条、库里可能有几十条,而这一组按稿子只摆 4 行;
                  完整列表和赛程在 `/kiosk/live`。这一行补上之前那条路由在盒上等于不存在。 */}
              <button
                type="button"
                className="kiosk-row"
                data-testid="kifu-live-more"
                onClick={() => navigate('/kiosk/live')}
              >
                <span className="kiosk-row__t">
                  <b>{t('kifu:live_more', '全部直播 · 赛程')}</b>
                  <em>{t('kifu:live_more_sub', '还有更多场次，以及接下来几天的对局安排')}</em>
                </span>
                <span className="kiosk-row__end">
                  <span className="kiosk-tag">{t('kifu:go', '去看')}</span>
                </span>
              </button>
```

- [ ] **Step 4: 观战屏返回去向**

`LiveMatchPage.tsx` 顶部 import 加 `useLocation`:

```tsx
import { useParams, useNavigate, useLocation } from 'react-router-dom';
```

组件里(`const navigate = useNavigate();` 之后)加:

```tsx
  /**
   * 返回去哪儿。**按来路,不按猜测** —— 这一屏有两个入口:棋谱屏那四行,和直播列表屏。
   * 缺省仍是棋谱(今天的行为),只有列表屏跳进来时才带 `from: 'live'`。
   */
  const location = useLocation();
  const cameFromList = (location.state as { from?: string } | null)?.from === 'live';
  const backLabel = cameFromList ? t('live:back_list', '直播') : t('live:back_kifu', '棋谱');
  const goBack = () => navigate(cameFromList ? '/kiosk/live' : '/kiosk/kifu');
```

把两处页控条(`:146-151` 与 `:249-253`)的 `backLabel={t('live:back_kifu', '棋谱')}` / `onBack={() => navigate('/kiosk/kifu')}` 换成 `backLabel={backLabel}` / `onBack={goBack}`。

同时把文件头注里那句「返回去**棋谱**不是 `/kiosk/live` —— 后者是个孤儿路由…」改写为:

```
 * ## 返回去哪儿
 *
 * 两个入口:棋谱屏那四行,和直播列表屏(2026-09-20 补了棋谱屏的入口,它不再是孤儿路由)。
 * 按来路回:带 `state.from === 'live'` 的回列表,其余回棋谱。**不加二次确认** ——
 * 这一屏没有动作区,观众没有可损失的状态。
```

- [ ] **Step 5: 跑,确认它通过**

```bash
npx vitest run src/kiosk/__tests__/KifuPage.test.tsx src/kiosk/__tests__/LiveMatchPage.test.tsx src/kiosk/__tests__/LivePage.test.tsx
npx tsc -b
```

预期:全绿;`tsc_exit=0`。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/ui/src/kiosk/pages/KifuPage.tsx katrain/web/ui/src/kiosk/pages/LiveMatchPage.tsx \
  katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx katrain/web/ui/src/kiosk/__tests__/LiveMatchPage.test.tsx
git commit -m "$(cat <<'EOF'
feat(kiosk-live): 棋谱屏补「全部直播 · 赛程」入口,观战屏按来路返回

/kiosk/live 从此不再是孤儿路由;观战屏从列表进来的回列表,其余仍回棋谱。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: 承重实测 + 真运行时预览 + 视觉存档

> jsdom 没有布局引擎,对「列表会不会溢出、页控条会不会被顶走」无权作证。这一步在真浏览器里量。

**Files:**
- Create: `katrain/web/ui/tests/kiosk-live-list.spec.ts`
- Create: `superpowers/tracks/kiosk-go-live/visual/live-list/README.md` + 一张实现图

**Interfaces:**
- Consumes:`playwright.visual.config.ts`(vite dev,:5173),路由拦截。
- Produces:一张 1024×600 实现图;承重断言。

- [ ] **Step 1: 写 spec(先造到会溢出:50 条直播 + 20 条赛程)**

```ts
// katrain/web/ui/tests/kiosk-live-list.spec.ts
import { test, expect } from '@playwright/test';

const match = (i: number) => ({
  id: `m${i}`, source: 'xingzhen', tournament: `第 ${i} 届名人战`, round_name: '半决赛',
  date: '2026-09-20T03:00:00Z', player_black: '申真谞', player_white: '柯洁',
  black_rank: '9p', white_rank: '9p', status: 'live', result: null, move_count: 100 + i,
  current_winrate: 0.5, current_score: 0, last_updated: '2026-09-20T05:00:00Z',
  board_size: 19, komi: 7.5, rules: 'chinese',
});
const upcoming = (i: number) => ({
  id: `u${i}`, tournament: `第 ${i} 届春兰杯`, round_name: '第 1 轮',
  scheduled_time: '2026-09-22T11:00:00Z', player_black: '朴廷桓', player_white: '芈昱廷',
  source: 'foxwq', source_url: 'https://example.com/x',
});

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/live/matches**', (r) => r.fulfill({
    json: { matches: [...Array(50)].map((_, i) => match(i)), total: 50, live_count: 50 },
  }));
  await page.route('**/api/v1/live/upcoming**', (r) => r.fulfill({
    json: { matches: [...Array(20)].map((_, i) => upcoming(i)) },
  }));
});

test('50 条时列表自己滚,整页不溢出,页控条不动', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  await page.goto('/kiosk/live');
  await expect(page.getByTestId('live-row').first()).toBeVisible();

  // 关系式期望,不钉具体像素。
  const zone = page.locator('.kiosk-side__scroll, .kiosk-layout-b .kiosk-side__scroll').first();
  const metrics = await zone.evaluate((el) => ({ scroll: el.scrollHeight, client: el.clientHeight }));
  expect(metrics.scroll).toBeGreaterThan(metrics.client);            // 真的会长
  const page_ = await page.evaluate(() => ({
    sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
    sh: document.documentElement.scrollHeight, ch: document.documentElement.clientHeight,
  }));
  expect(page_.sw).toBeLessThanOrEqual(page_.cw);                    // 不许横向溢出
  expect(page_.sh).toBeLessThanOrEqual(page_.ch);                    // 整页不滚,只有列表滚

  const before = await page.getByTestId('live-list-pagebar').boundingBox();
  await page.getByRole('button', { name: '即将开始' }).click();
  await expect(page.getByTestId('upcoming-row').first()).toBeVisible();
  const after = await page.getByTestId('live-list-pagebar').boundingBox();
  expect(after?.y).toBeCloseTo(before?.y ?? -1, 1);                  // 切分段页控条不上下跳
});

test('取一帧实现图', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  await page.goto('/kiosk/live');
  await expect(page.getByTestId('live-row').first()).toBeVisible();
  await page.screenshot({
    path: '../../../superpowers/tracks/kiosk-go-live/visual/live-list/live-list--implementation.png',
  });
});
```

- [ ] **Step 2: 跑**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live/katrain/web/ui
npx playwright test --config=playwright.visual.config.ts tests/kiosk-live-list.spec.ts
```

预期:2 passed,图写进 `superpowers/tracks/kiosk-go-live/visual/live-list/`。
失败时先看是不是**断言选错对象**(滚动容器选择器),再改页面。

- [ ] **Step 3: 人眼看那一帧**

打开 `live-list--implementation.png`,逐项确认:行高与屏 15 棋谱一致、页控条 y 在 70–114、分段三段放得下、没有百分比数字、没有外链图标。**有一条不过就回 Task 4 改,不要在存档里记一张自己都不认的图。**

- [ ] **Step 4: 写存档 README**

```bash
cat > /Users/fan/Repositories/katrain-kiosk-go-live/superpowers/tracks/kiosk-go-live/visual/live-list/README.md <<'EOF'
# 直播列表屏(稿外屏)

**没有参考图。** 这一屏不在 27 屏设计稿里,属 Fan 2026-08-20 裁的「稿外五屏,只接壳不重排」。
四图对比的前提是有一张参考图可比 —— 这里没有,所以**只存实现图**,
不做并排图 / 差异图,也**不要伪造一张参考图凑四图**。

判据改为页面头注里那三条(去 canvas 预览、去编出来的胜率、去 _blank 外链)+
`tests/kiosk-live-list.spec.ts` 的承重断言。

- `live-list--implementation.png` — 1024×600,50 条直播桩数据,2026-09-20。
EOF
```

- [ ] **Step 5: PO 闸**

```bash
npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-contract.spec.ts
```

预期:通过。若因新 key 而红,读它的报错:闸只在 key **已存在于 PO** 时比对中文默认串,新 key 不该触发它;红了说明沿用了一个已有 key 但默认串不一致 —— 改默认串,不改 PO。

- [ ] **Step 6: 提交**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live
git add katrain/web/ui/tests/kiosk-live-list.spec.ts superpowers/tracks/kiosk-go-live/visual/
git diff --cached --stat
git commit -m "$(cat <<'EOF'
test(kiosk-live): 直播列表屏承重实测与实现图存档

50 条 + 20 条造到会溢出再量:列表自己滚、整页不溢出、切分段页控条不动。
稿外屏没有参考图,只存实现图并写明理由。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: L2 · 直播源「剩余时间」可得性探针

> 这一步**不改产品代码**(除了把结论补进一句注释)。它要回答的是一个事实问题:三个源给不给剩余时间。答案决定要不要开加列 + cron + 前端那三层的工。

**Files:**
- Create: `superpowers/tracks/kiosk-go-live/findings-clock.md`
- Modify: `katrain/web/ui/src/kiosk/pages/LiveMatchPage.tsx`(只改「## 钟不画」那段注释,补探针日期与结论)

**Interfaces:**
- Consumes:`katrain/cron/clients/{xingzhen,yike,pandanet}.py`;`katrain/web/core/models_db.py` `LiveMatchDB`;`katrain/web/ui/src/types/live.ts`。
- Produces:`findings-clock.md`,每个源一段。

- [ ] **Step 1: 把三个源的字段清单抄出来(读代码,不猜)**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live
sed -n '1,240p' katrain/cron/clients/xingzhen.py | grep -n "get(\|\[\"" | head -40
sed -n '1,240p' katrain/cron/clients/yike.py    | grep -n "get(\|\[\"" | head -40
sed -n '150,210p' katrain/cron/clients/pandanet.py
```

对每个源记三件事:① 上游给的原始字段里有没有「剩余时间 / 用时 / 读秒剩几次」;② 抓取代码读了哪些、丢了哪些;③ 库里存没存。

- [ ] **Step 2: 能连上时,抓一份真实响应**

```bash
# 星阵 / 弈客:客户端里有 URL 常量。能连上就取一份,存到 scratchpad(**不入库**)。
cd /Users/fan/Repositories/katrain-kiosk-go-live
uv run python - <<'EOF'
import json, asyncio
from katrain.cron.clients import xingzhen
# 按该文件里真实的入口函数名调用;拿到的原始 dict 直接 dump。
# 连不上就记「本机连不上,需在 home-ubuntu 上复跑」——**不要拿连不上当作「上游没有这个字段」**。
EOF
```

⚠️ 判据纪律:**「我没抓到」不等于「上游没有」**。连不上就照实写「未验证 · 待在测试环境复跑」,不要写成结论。

- [ ] **Step 3: 写 `findings-clock.md`**

模板(每个源一段,结论必须能指到一行代码或一份响应):

```markdown
# 直播源「剩余时间」可得性探针(2026-09-20)

## 结论一句话
<三个源都给不出 / 某某源给得出>

## 星阵(xingzhen)
- 抓取代码:`katrain/cron/clients/xingzhen.py:<行>`
- 上游字段:<清单>
- 有没有剩余时间:<有 / 没有 / 未验证(本机连不上)>
- 证据:<代码行 或 响应片段路径>

## 弈客(yike)
…

## PandaNet
- `pandanet.py:193` 的 `byo_time` 是**读秒设定**(每手几秒),不是剩余时间。
- 上游协议(NNGS)里有没有剩余时间:<结论 + 证据>

## 库与前端
- `models_db.py` `LiveMatchDB`:无任何时间列(2026-09-20 复核)。
- `types/live.ts` `MatchSummary`:无。

## 如果要做,要动哪几层
1. `LiveMatchDB` 加列(仓里**没有 alembic**:在模型上加列,`core/migrations.py` 的 `add_missing_columns` 会补上);2. cron 三个客户端各自写入(给不出的源写 NULL);
3. `types/live.ts` 与 `/live/matches` 响应;4. 屏 18 玩家卡的 `.clock` **只对有数的源渲染** ——
   给不出的源画一个空钟,比不画更坏。
```

- [ ] **Step 4: 把结论补进屏 18 的注释**

在 `LiveMatchPage.tsx` 的「## 钟不画」那段末尾追加一行(按真实结论写):

```
 * (2026-09-20 探针复核:<结论>。见 `superpowers/tracks/kiosk-go-live/findings-clock.md`。)
```

- [ ] **Step 5: 提交**

```bash
git add superpowers/tracks/kiosk-go-live/findings-clock.md katrain/web/ui/src/kiosk/pages/LiveMatchPage.tsx
git commit -m "$(cat <<'EOF'
docs(kiosk-live): 直播源剩余时间可得性探针

先验前提再决定要不要付加列+cron+前端那三层的钱。连不上的源照实写「未验证」,
不拿「我没抓到」冒充「上游没有」。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: 收尾验证

**Files:**
- 不改仓内文件(除非发现回归)。

- [ ] **Step 1: 基线 diff**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live/katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-live rev-parse --absolute-git-dir)/live-baseline"
npx vitest run --reporter=json --outputFile="$BASE/after.json" > "$BASE/after.log" 2>&1; echo "vitest_exit=$?"
node "$BASE/failed-names.cjs" "$BASE/after.json" > "$BASE/after-failed.txt"
comm -13 "$BASE/before-failed.txt" "$BASE/after-failed.txt"
```

预期:`comm` 输出为空(**新增失败必须为空**;比的是名字集合,不是条数)。

- [ ] **Step 2: 类型 + 两套构建 + 边界**

```bash
npx tsc -b; echo "tsc=$?"
npm run build; echo "build=$?"
npm run build:kiosk-2d; echo "kiosk=$?"
npx eslint src/hooks/live/useUpcomingMatches.ts src/kiosk/pages/LivePage.tsx src/kiosk/utils/scheduleLabel.ts \
  src/kiosk/pages/KifuPage.tsx src/kiosk/pages/LiveMatchPage.tsx; echo "eslint=$?"
```

预期:全部 0。`build:kiosk-2d` 里的 `verify:kiosk-2d` 必须 0(共享钩子不许把 galaxy 的东西拖进 kiosk 包)。

- [ ] **Step 3: 新增文案 key 清单**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-live
git diff 7a152df1..HEAD -- katrain/web/ui/src | grep -o "t('[a-z]*:[a-z_0-9]*'" | sort -u
```

把输出抄进交付说明(合并后统一交 `katrain-i18n-expert` 补 11 种语言)。

- [ ] **Step 4: 交付说明**

在 PR / 汇报里写清四件事:① 做了 L1(方案 B,Fan 2026-09-21 定)、L2 只做了探针;② 新增 key 清单;③ 承重与预览的结论;④ **还没上板**,建议的上板走查步骤(棋谱 → 直播列表 → 三个分段 → 观战 → 返回)。

---

## 附录 A:如果 Fan 选方案 A(删掉 `/kiosk/live`)

> **已作废**:Fan 2026-09-21 选了方案 B(补入口并接壳)。本附录不执行,留作记录。

弃掉 Task 2–6,改做这一个 Task:

- [ ] **Step 1: 写失败的单测**

```tsx
// 追加到 src/kiosk/__tests__/KioskApp.test.tsx
it('/kiosk/live 不再是一条路由:进去落到棋谱', async () => {
  renderKioskApp('/kiosk/live');           // 复用该文件既有助手
  expect(await screen.findByTestId('kifu-page')).toBeInTheDocument();
});
```

- [ ] **Step 2: 删页面与路由**

```bash
git rm katrain/web/ui/src/kiosk/pages/LivePage.tsx katrain/web/ui/src/kiosk/__tests__/LivePage.test.tsx
```

`KioskApp.tsx`:删 `:60` 的 import,把 `:157` 的 `<Route path="live" element={<LivePage />} />` 换成
`<Route path="live" element={<Navigate to="/kiosk/kifu" replace />} />`(留重定向接住旧链接,与 kifu 分支删 `/kiosk/baipu` 的做法同形),并把 `:148-151` 那段注释里的「live」去掉。

- [ ] **Step 3: 改棋谱屏那一组的话**

它今天说「来源:星阵 · 弈客」而只给 4 行。删了「更多」之后,这句话要么去掉,要么写成「最近 4 场」——
**屏上不许暗示还有别处可看而实际没有**。

- [ ] **Step 4: 跑、提交**

```bash
npx vitest run src/kiosk/__tests__/KioskApp.test.tsx src/kiosk/__tests__/KifuPage.test.tsx
npx tsc -b && npm run build && npm run build:kiosk-2d
```

然后照 Task 8 收尾。
