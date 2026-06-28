# 棋智盒 Kiosk 教程模块（只读镜像）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan phase-by-phase, stopping at each Review Checkpoint. Steps use checkbox (`- [ ]`) syntax for tracking.

> Track: `sbc-tutorial-parity` · Branch: `feature/sbc-tutorial-parity`
> Worktree: `/Users/fan/Repositories/katrain-sbc-tutorial-parity` · 前端根：`katrain/web/ui`
> 配套 PRD：`./prd.md` · Status: **Revised after Codex + Gemini review** — 2026-06-28

**Goal:** 在棋智盒（kiosk-2d 构建）新增一个只读教程模块，镜像 galaxy 的「分类→书→章/节→section」层级，section 学习页以视频为主、棋谱缩略图可放大复盘，全程不触碰后端。

**Architecture:** 纯前端。把 galaxy 的 `tutorialApi.ts`、`SGFBoard.tsx` 下沉到共享 territory（满足 kiosk「禁止 import galaxy/」边界），新建共享视频播放器与资源工具，再在 `src/kiosk/` 新建 4 个路由页 + 缩略图/弹层组件。媒体走既有 `/api/v1/tutorials/assets/{path}` 网关。

**Tech Stack:** React + TypeScript + Vite、MUI、react-router-dom v6、Vitest（单测/组件）、Playwright（e2e）、双构建 `npm run build` + `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）。

## Global Constraints

- **后端一律不改**（FastAPI / Pydantic / SQLAlchemy / 存储抽象 / 标注 / 生成）。只读消费既有 `/api/v1/tutorials/*`。
- **kiosk 边界契约**（见仓库根 `CLAUDE.md`）：`src/kiosk/**` 禁止 import `src/galaxy/**`、`src/components/Board3D/**`、`src/pages/VideoRecorderPage*`。
- **改共享文件 → 影响两个构建**：每次相关改动后必须 `npm run build`（full web）+ `npm run build:kiosk-2d`（含 `verify:kiosk-2d`，exit 0）。
- **不实现 PRD §3.2 任何 Non-goal**：无编辑/标注/审核/生成 UI、无原书扫描图、无独立音频播放器、无 three.js / Board3D。
- **触屏标准**：可点击区 ≥48px，`:active` 反馈，横竖屏响应式（`useOrientation().isPortrait`）。
- **视觉**：kiosk `kioskTheme`（深色、jade/wood、Noto Sans SC），卡片不过大、尽量一屏可见（参考 [[feedback_play_page_layout]]）。

---

## 评审意见处理决定 Review Disposition

> Codex 与 Gemini 的两份评审已逐条核对源码。**Codex 的全部具体论断（P0/P1）经验证均属实**；Gemini 偏架构层、部分已被现有代码满足。下表是采纳/不采纳的裁决与依据。计划正文已据此修订。

| # | 来源 | 意见 | 裁决 | 依据（已验证） |
|---|---|---|---|---|
| P0-1 | Codex | `GET /sections/{id}` 不计算 `has_video`，深链/刷新时永远 `false`，会错误隐藏已存在视频 | **采纳** | `tutorials.py:118-126` 仅填 `figure_count`/`figures`；`models.py:52` `has_video: bool = False`。→ **改为：能解析 slug 就尝试播放，`onError` 再降级**；不以详情 `has_video` 作开关 |
| — | Codex | 备选「微调后端在 `get_section` 计算 `has_video`」 | **不采纳** | 违反 Global Constraint「后端一律不改」；纯前端「尝试播放→降级」方案已足够稳健 |
| P0-2 | Codex | 迁移用 `grep "galaxy/api/tutorialApi"` 漏掉真实相对 import | **采纳** | galaxy 实为 `../../api/tutorialApi`（6 处）+ `../../components/tutorials/SGFBoard`（1 处）+ 测试 mock。→ 改用 `rg` 符号+路径双搜，迁移测试 mock，**旧路径保留 re-export 垫片** |
| P1 | Codex | `TutorialAPI` 含写接口，下沉后 kiosk 可调用，违反「只读镜像」 | **采纳** | `tutorialApi.ts:60-77` 有 `saveBoardPayload/saveNarration/generateFigureAudio/verifyFigure`。→ 新增只读视图 `TutorialReadAPI`，kiosk 只用它；加 vitest 守卫 grep `src/kiosk/**` 无写接口名 |
| P1 | Codex | section 深链 breadcrumb/slug 数据不足 | **采纳**（与 Gemini 2.3 合并） | `TutorialSectionDetail` 无 book/chapter title、无 slug。→ 定义 router `state` 契约 + 刷新降级策略（绝不显示 `undefined ▸ undefined`） |
| P1 | Codex | `SGFBoard` 硬编码 `maxWidth: 500`、`showFullBoard` 丢 viewport | **采纳** | `SGFBoard.tsx:216`。→ 加非破坏性 props `maxWidth?`/`style?`/`className?`；弹层默认 viewport 放大 + 可选全盘切换；无数字 labels 时隐藏手数滑块 |
| P1 | Codex | 测试命令/层级写错（`npm test`=vitest，e2e=playwright，类型用 `tsc -b`） | **采纳** | `package.json:6-14`、`vite.config.ts:31-36`（排除 `tests/**`）、`playwright.config.ts` 存在。→ 全部 Verification 命令更正；前置 `npm install` |
| P1 | Codex | 现有 nav 测试停在 "all 6" 且漏「摆谱」，新增「教程」后过时 | **采纳** | `NavigationRail.test.tsx:26-28`、`TopTabBar.test.tsx:26-28` 断言列表确实缺「摆谱」。→ Phase 3 同步升级 nav 测试 |
| 其他-1 | Codex | 数据依赖 e2e 不能静默跳过核心路径 | **采纳** | galaxy spec 有「card 可见才断言」模式。→ kiosk e2e 用 Playwright route mock `/api/v1/tutorials/*`，无数据不静默通过 |
| 其他-2 | Codex | `bookSlugFromFigures` 要覆盖多种路径形态 | **采纳** | → Phase 2 测试覆盖 page/video/audio/缺前缀/空 slug/编码/空数组/首图空路径 |
| 其他-3 | Codex | effect 加取消保护防竞态 | **采纳**（轻量） | → 列表/详情 effect 用 `let cancelled = false` 守卫 |
| 其他-4 | Codex | 固定 route state 形状 | **采纳** | → Phase 0 定义统一 `SectionNavState` |
| 2.1 | Gemini | `TutorialBookDetailPage` 章节加载 N+1 瀑布 | **部分采纳** | galaxy 现有代码**已用 `Promise.all`**（`TutorialBookDetailPage.tsx:41-48`）。→ 复用即满足；计划明确「并行、勿串行」。后端 `?include=sections` 属 out-of-scope，仅记为可选后续债 |
| 2.2 | Gemini | `SGFPayload` 与 `BoardPayload` 类型重复 | **采纳为「记债」** | 本期不统一（控范围）；在计划「技术债登记」记一行，不新建外部 ticket（无 ticket 系统） |
| 2.3 | Gemini | 刷新后 state 丢失致 breadcrumb 不完整 | **采纳**（并入 P1 深链） | 同上降级策略 |
| 2.4 | Gemini | `FigureThumb` 应为展示型，`onClick` 由父注入；可抽 `CardGridPage` | **部分采纳** | `FigureThumb` 展示型、`onClick` 父注入：采纳。`CardGridPage` 通用抽象：**降为可选**（仅 3 页，YAGNI，不强制） |
| 2.5 | Gemini | 「弹层显示 narration 文字」可选功能需决策 | **决策：本期不做** | 视频已含旁白音频；为收紧范围，narration 文字移出 Phase 5 必做项（保留为 PRD §3.3 nice-to-have，默认关闭） |

---

## 文件总览（最终态）

```
# ── 共享 territory（两端可 import）──
src/api/tutorialApi.ts                          # ← 从 galaxy/api 迁入；新增 TutorialReadAPI 只读视图
src/components/tutorials/SGFBoard.tsx           # ← 从 galaxy/components 迁入；加 maxWidth?/style?/className? props
src/components/tutorials/TutorialVideoPlayer.tsx    # 新建：HTML5 播放器 + onError 降级
src/utils/tutorialAssets.ts                     # 新建：slug 解析 + section 视频/poster URL（可单测）
src/utils/tutorialAssets.test.ts                # 新建：slug 解析多形态测试
src/kiosk/types/tutorialNav.ts                  # 新建：SectionNavState 路由 state 契约
# ── kiosk 专属 ──
src/kiosk/pages/TutorialCategoriesPage.tsx      # 新建：分类落地
src/kiosk/pages/TutorialBooksPage.tsx           # 新建：书列表
src/kiosk/pages/TutorialBookDetailPage.tsx      # 新建：章/节树（Promise.all 并行）
src/kiosk/pages/TutorialSectionPage.tsx         # 新建（核心，Option B）
src/kiosk/components/tutorial/FigureThumb.tsx   # 新建：展示型缩略棋盘卡（onClick 父注入）
src/kiosk/components/tutorial/FigureDialog.tsx  # 新建：放大棋盘 + 手数滑块（viewport 默认 + 全盘切换）
src/kiosk/components/layout/navTabs.tsx         # 改：加「教程」标签
src/kiosk/KioskApp.tsx                          # 改：加 4 条路由 + import
# ── galaxy 过渡垫片（保留 re-export，回归稳定后再清理）──
src/galaxy/api/tutorialApi.ts                   # 改为 `export * from '../../api/tutorialApi'`
src/galaxy/components/tutorials/SGFBoard.tsx    # 改为 re-export shared SGFBoard
# ── 测试同步 ──
src/kiosk/__tests__/NavigationRail.test.tsx     # 改：断言全部 primary tabs + active
src/kiosk/__tests__/TopTabBar.test.tsx          # 改：同上 + 竖屏不溢出
src/kiosk/__tests__/KioskApp.test.tsx           # 改：/kiosk/tutorial 可渲染
src/api/__tests__/tutorialReadonly.guard.test.ts    # 新建：kiosk 源码无写接口守卫
tests/tutorial-kiosk.spec.ts                    # 新建：Playwright e2e（route mock）
```

---

## Phase 0 — 契约核对与环境准备（不写功能码）

**目标**：把评审暴露的「接口事实」和「测试命令事实」固化为执行前提，避免按错误假设实现。

### Tasks

- [ ] **0.1 安装前端依赖**（评审发现 worktree 未装依赖，`vitest`/`tsc` 不可用）
  ```bash
  cd katrain/web/ui && npm install
  ```
- [ ] **0.2 记录并核对真实命令**（写进执行笔记，后续 Verification 一律用这些）
  - 单测/组件：`npm test`（= `vitest run`）；监视：`npm run test:watch`
  - 类型检查：`npm run build`（含 `tsc -b`）—— **不要**用 `tsc --noEmit` 作唯一闸门
  - lint：`npm run lint`（= `eslint .`，含 kiosk/galaxy 边界规则）
  - full 构建：`npm run build`
  - kiosk 构建：`npm run build:kiosk-2d`（含 `verify:kiosk-2d`）
  - e2e：`npx playwright test tests/tutorial-kiosk.spec.ts`（**不是** `npm test`；vitest 已排除 `tests/**`）
- [ ] **0.3 固化 `has_video` 事实**（P0-1）：执行者须知 `GET /sections/{id}` 返回的 `has_video` 恒为 `false`（后端未计算）。**section 学习页不得用它作视频开关**。
- [ ] **0.4 固化 deep-link 降级口径**（P1 / Gemini 2.3）：
  - 正常点击：上一页通过 router `state` 传 `SectionNavState`。
  - 刷新/直链：`state` 为空 → slug 从 figure 路径解析；breadcrumb 降级为 `教程 ▸ {section_number}. {title}`；**永不**渲染含 `undefined` 的面包屑。
- [ ] **0.5 确认联调数据**（R3/R5）：检查 dev 是否有可联调的教程数据与本地媒体；缺则 e2e 走 route mock（Phase 7），手测渲染走 mock/占位。
  ```bash
  # 起后端 + 前端 dev，确认 /api/v1/tutorials/categories 有返回
  ```

### Review Checkpoint 0
停下：确认依赖装好、命令清单与两条降级口径无歧义后进入 Phase 1。

---

## Phase 1 — 共享下沉（API + SGFBoard，含只读视图与垫片）

**目标**：把 `tutorialApi.ts`、`SGFBoard.tsx` 迁到共享区，galaxy 改用共享（旧路径保留 re-export 垫片），新增只读视图与守卫，双构建绿、galaxy 零回归。

### Files
- Create: `src/api/tutorialApi.ts`、`src/components/tutorials/SGFBoard.tsx`、`src/api/__tests__/tutorialReadonly.guard.test.ts`
- Modify（改为 re-export）: `src/galaxy/api/tutorialApi.ts`、`src/galaxy/components/tutorials/SGFBoard.tsx`
- Modify（迁 mock）: `src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx`

### Tasks

- [ ] **1.1 全量核对真实引用**（P0-2，用 `rg` 不用 `grep`）
  ```bash
  cd katrain/web/ui
  rg -n "TutorialAPI|api/tutorialApi|components/tutorials/SGFBoard|SGFBoard" src
  rg -n "\.\./\.\./api/tutorialApi|\.\./\.\./components/tutorials/SGFBoard" src
  ```
  预期命中：`galaxy/pages/tutorials/*`（6 处 tutorialApi、1 处 SGFBoard）、`galaxy/components/tutorials/RecognitionDebugPanel.tsx`、`TutorialFigurePage.test.tsx`（mock）。
- [ ] **1.2 迁移 API 客户端到共享区，并加只读视图**
  - 新建 `src/api/tutorialApi.ts`：内容 = 现 `galaxy/api/tutorialApi.ts`，仅把类型 import `'../../types/tutorial'` 改为 `'../types/tutorial'`。
  - 在文件末尾追加只读视图（kiosk 只 import 它）：
    ```ts
    // 只读视图：kiosk 教程模块仅消费读接口（写接口仅 galaxy admin 使用）
    export const TutorialReadAPI = {
      getCategories: TutorialAPI.getCategories,
      getBooks: TutorialAPI.getBooks,
      getBook: TutorialAPI.getBook,
      getSections: TutorialAPI.getSections,
      getSection: TutorialAPI.getSection,
      getFigure: TutorialAPI.getFigure,
      assetUrl: TutorialAPI.assetUrl,
    };
    ```
- [ ] **1.3 galaxy API 改 re-export 垫片**（降低一次性破坏面）
  - `src/galaxy/api/tutorialApi.ts` 全文替换为：
    ```ts
    export * from '../../api/tutorialApi';
    ```
- [ ] **1.4 迁移 `SGFBoard` 到共享区，并加非破坏性 props**（P1）
  - 新建 `src/components/tutorials/SGFBoard.tsx`：内容 = 现 galaxy 版（无相对依赖，可整体搬）。
  - `SGFBoardProps` 增加可选 props（默认行为不变）：
    ```ts
    interface SGFBoardProps {
      payload: SGFPayload;
      maxMoveStep?: number;
      showFullBoard?: boolean;
      onClick?: (...) => void;   // 保持原签名
      maxWidth?: number | string;   // 新增，默认 500
      style?: React.CSSProperties;  // 新增，合并到根 <svg> style
      className?: string;           // 新增
    }
    ```
  - 根 `<svg>` 的 `style` 由硬编码 `{ maxWidth: 500, ... }` 改为：
    ```ts
    style={{ maxWidth: maxWidth ?? 500, display: 'block', background: '#dcb468', borderRadius: 4, ...style }}
    className={className}
    ```
  - `src/galaxy/components/tutorials/SGFBoard.tsx` 改为：
    ```ts
    export * from '../../../components/tutorials/SGFBoard';
    export { default } from '../../../components/tutorials/SGFBoard';
    ```
- [ ] **1.5 迁移测试 mock**：`TutorialFigurePage.test.tsx` 的 `vi.mock('../../api/tutorialApi')` 经垫片仍可工作；若 mock 路径解析失败，改 mock 共享路径 `../../../api/tutorialApi`。运行该测试确认通过。
- [ ] **1.6 新增只读守卫测试**（P1）`src/api/__tests__/tutorialReadonly.guard.test.ts`：
  ```ts
  import { readFileSync } from 'node:fs';
  import { globSync } from 'node:fs';   // 或用 fast-glob/项目既有方式
  import { describe, it, expect } from 'vitest';

  const WRITE_METHODS = ['saveBoardPayload', 'saveNarration', 'generateFigureAudio', 'verifyFigure'];

  describe('kiosk tutorial is read-only', () => {
    it('no kiosk source references tutorial write methods', () => {
      const files = globSync('src/kiosk/**/*.{ts,tsx}');
      const offenders: string[] = [];
      for (const f of files) {
        const src = readFileSync(f, 'utf8');
        for (const m of WRITE_METHODS) if (src.includes(m)) offenders.push(`${f}: ${m}`);
      }
      expect(offenders).toEqual([]);
    });
  });
  ```
  （若 `globSync` 不可用，用项目既有的 fs 遍历方式；保证测试本身能跑。）
- [ ] **1.7 lint 边界自检**：确认 `eslint.config.js` 对新增 `src/components/tutorials/`、`src/api/tutorialApi.ts`（共享区）不报边界错。

### Verification（必须全绿）
```bash
cd katrain/web/ui
npm run lint
npm test                  # 含新守卫测试 + 迁移后的 galaxy 测试
npm run build             # full web（tsc -b 类型 + vite build）
npm run build:kiosk-2d    # kiosk（含 verify:kiosk-2d，exit 0）
```
- 手动：`npm run dev`，访问 galaxy `/galaxy/tutorials` 走分类→书→章节→section，确认 **SGFBoard 正常渲染、视频可播、无回归**。

### Review Checkpoint 1
停下：共享下沉无 galaxy 回归、只读守卫绿、双构建绿后进入 Phase 2。

---

## Phase 2 — 共享构建块（资源工具 + 视频播放器，TDD）

**目标**：补齐 kiosk 缺失的 slug/URL 工具与视频播放能力，放共享区，先写测试。视频播放器支持「尝试播放→失败降级」以服务 P0-1。

### Files
- Create: `src/utils/tutorialAssets.ts`、`src/utils/tutorialAssets.test.ts`、`src/components/tutorials/TutorialVideoPlayer.tsx`

### Tasks

- [ ] **2.1 先写资源工具测试**（TDD，覆盖 Codex 其他-2 全部形态）`src/utils/tutorialAssets.test.ts`：
  ```ts
  import { describe, it, expect } from 'vitest';
  import { bookSlugFromFigures, sectionVideoUrl, sectionPosterUrl } from './tutorialAssets';
  import type { TutorialFigure } from '../types/tutorial';

  const fig = (over: Partial<TutorialFigure>): TutorialFigure =>
    ({ id: 1, section_id: 1, page: 1, figure_label: '图1', book_text: null, page_context_text: null,
       bbox: null, page_image_path: null, board_payload: null, recognition_debug: null, narration: null,
       audio_asset: null, video_asset: null, video_duration_ms: null, video_size_bytes: null,
       order: 0, updated_at: null, ...over });

  describe('bookSlugFromFigures', () => {
    it('parses slug from page_image_path', () => {
      expect(bookSlugFromFigures([fig({ page_image_path: 'tutorial_assets/zhongguo-weiqi-shi/page/page_1.jpg' })]))
        .toBe('zhongguo-weiqi-shi');
    });
    it('parses slug from video_asset', () => {
      expect(bookSlugFromFigures([fig({ video_asset: 'tutorial_assets/abc/video/fig_7.mp4' })])).toBe('abc');
    });
    it('parses slug from audio_asset', () => {
      expect(bookSlugFromFigures([fig({ audio_asset: 'tutorial_assets/abc/audio/fig_7.mp3' })])).toBe('abc');
    });
    it('skips empty first path, uses later figure', () => {
      expect(bookSlugFromFigures([fig({}), fig({ page_image_path: 'tutorial_assets/xyz/page/page_2.jpg' })])).toBe('xyz');
    });
    it('returns null when prefix missing', () => {
      expect(bookSlugFromFigures([fig({ page_image_path: 'something/else/page_1.jpg' })])).toBeNull();
    });
    it('returns null for empty slug segment', () => {
      expect(bookSlugFromFigures([fig({ page_image_path: 'tutorial_assets//page/page_1.jpg' })])).toBeNull();
    });
    it('decodes URL-encoded slug', () => {
      expect(bookSlugFromFigures([fig({ page_image_path: 'tutorial_assets/a%20b/page/p.jpg' })])).toBe('a b');
    });
    it('returns null for empty figures array', () => {
      expect(bookSlugFromFigures([])).toBeNull();
    });
  });

  describe('section URLs', () => {
    it('builds section video url', () => {
      expect(sectionVideoUrl('abc', 42)).toBe('/api/v1/tutorials/assets/tutorial_assets/abc/video/section_42.mp4');
    });
    it('builds section poster url', () => {
      expect(sectionPosterUrl('abc', 42)).toBe('/api/v1/tutorials/assets/tutorial_assets/abc/video/section_42.jpg');
    });
  });
  ```
- [ ] **2.2 运行测试确认失败**：`npm test -- src/utils/tutorialAssets.test.ts`（Expected: FAIL，函数未定义）。
- [ ] **2.3 实现 `src/utils/tutorialAssets.ts`**：
  ```ts
  import type { TutorialFigure } from '../types/tutorial';
  import { TutorialReadAPI } from '../api/tutorialApi';

  const SLUG_RE = /tutorial_assets\/([^/]+)\//;

  /** 从首个含资源路径的 figure 解析 book slug；解析失败返回 null。 */
  export function bookSlugFromFigures(figures: TutorialFigure[]): string | null {
    for (const f of figures ?? []) {
      for (const p of [f.page_image_path, f.video_asset, f.audio_asset]) {
        if (!p) continue;
        const m = SLUG_RE.exec(p);
        if (m && m[1]) {
          try { return decodeURIComponent(m[1]); } catch { return m[1]; }
        }
      }
    }
    return null;
  }

  export function sectionVideoUrl(slug: string, sectionId: number): string {
    return TutorialReadAPI.assetUrl(`tutorial_assets/${slug}/video/section_${sectionId}.mp4`);
  }
  export function sectionPosterUrl(slug: string, sectionId: number): string {
    return TutorialReadAPI.assetUrl(`tutorial_assets/${slug}/video/section_${sectionId}.jpg`);
  }
  ```
- [ ] **2.4 运行测试确认通过**：`npm test -- src/utils/tutorialAssets.test.ts`（Expected: PASS）。
- [ ] **2.5 实现 `TutorialVideoPlayer.tsx`**（shared，含降级）：
  ```tsx
  import { useState } from 'react';
  import { Box, Typography } from '@mui/material';

  interface Props {
    src: string;
    poster?: string;
    onError?: () => void;
    maxHeight?: number | string;
  }
  export default function TutorialVideoPlayer({ src, poster, onError, maxHeight = '60vh' }: Props) {
    const [failed, setFailed] = useState(false);
    if (failed) {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 4, minHeight: 160 }}>
          <Typography color="text.secondary">视频加载失败</Typography>
        </Box>
      );
    }
    return (
      <video
        src={src}
        poster={poster}
        controls
        preload="none"
        onError={() => { setFailed(true); onError?.(); }}
        style={{ width: '100%', maxHeight, background: '#000', borderRadius: 8, display: 'block' }}
      />
    );
  }
  ```
- [ ] **2.6 双构建确认**：`npm run build:kiosk-2d`（新文件不引入 three，应 exit 0）。

### Verification
```bash
cd katrain/web/ui
npm test -- src/utils/tutorialAssets.test.ts   # PASS
npm run build                                   # 类型/构建绿
npm run build:kiosk-2d                          # verify:kiosk-2d exit 0
```

### Review Checkpoint 2
停下：工具有完整异常路径测试、播放器具备降级、双构建绿后进入 Phase 3。

---

## Phase 3 — 导航标签 +「教程」4 条路由（含 nav 测试同步）

**目标**：用占位页打通导航与 4 条路由，更新已过时的 nav 测试，实测竖屏 7 标签不溢出。

### Files
- Modify: `src/kiosk/components/layout/navTabs.tsx`、`src/kiosk/KioskApp.tsx`
- Modify: `src/kiosk/__tests__/NavigationRail.test.tsx`、`src/kiosk/__tests__/TopTabBar.test.tsx`、`src/kiosk/__tests__/KioskApp.test.tsx`
- Create: `src/kiosk/types/tutorialNav.ts`

### Tasks

- [ ] **3.1 定义路由 state 契约**（其他-4）`src/kiosk/types/tutorialNav.ts`：
  ```ts
  export interface SectionNavState {
    bookId?: number;
    bookTitle?: string;
    bookSlug?: string;
    chapterTitle?: string;
    sectionTitle?: string;
    hasVideo?: boolean;
  }
  ```
- [ ] **3.2 加「教程」标签**（FR-1）`navTabs.tsx`：在顶部 `@mui/icons-material` 解构 import 里加 `School as SchoolIcon`（与「棋谱」`MenuBook` 区分），再在 `primaryTabs` 末尾追加：
  ```tsx
  import {
    SportsEsports as PlayIcon,
    /* …既有图标… */
    School as SchoolIcon,   // 新增
    Settings as SettingsIcon,
  } from '@mui/icons-material';
  // primaryTabs 末尾：
  { label: '教程', icon: <SchoolIcon />, path: '/kiosk/tutorial', pattern: '/kiosk/tutorial/*' },
  ```
- [ ] **3.3 加 4 条路由**（先占位）`KioskApp.tsx`：在 `<KioskLayout>` 路由块内（`live` 后、`vision/setup` 前），先用现成 `PlaceholderPage` 占位，保证编译：
  ```tsx
  <Route path="tutorial" element={<PlaceholderPage />} />
  <Route path="tutorial/:category" element={<PlaceholderPage />} />
  <Route path="tutorial/book/:bookId" element={<PlaceholderPage />} />
  <Route path="tutorial/section/:sectionId" element={<PlaceholderPage />} />
  ```
  注：React Router v6 best-match 自动让静态前缀 `book`/`section` 优先于 `:category`（与既有 `tsumego/problem/:id` vs `tsumego/:level` 同理），无需手排顺序。
- [ ] **3.4 更新 NavigationRail 测试**（P1）`NavigationRail.test.tsx`：
  - 用例名/断言改为全部 primary tabs：`['对弈','死活','研究','棋谱','摆谱','直播','教程','设置']`。
  - 新增 active 高亮：渲染于 `/kiosk/tutorial/section/123` 时「教程」高亮（`matchPath('/kiosk/tutorial/*')`）。
  - 新增点击：点「教程」→ 导航到 `/kiosk/tutorial`。
- [ ] **3.5 更新 TopTabBar 测试**（P1）`TopTabBar.test.tsx`：同 3.4 的标签断言；竖屏渲染下断言 8 个入口（7 primary + 设置）均存在且容器不换行（断言渲染数量；视觉溢出靠 3.7 截图）。
- [ ] **3.6 更新 KioskApp 测试**：`KioskApp.test.tsx` 在 authenticated 路由下断言 `/kiosk/tutorial` 能渲染教程入口（占位页文案或 testid）。
- [ ] **3.7 R1 竖屏实测**：`npm run dev`，横屏 + 竖屏各截图：「教程」标签出现、高亮正确、4 路由可达；竖屏 `TopTabBar` 8 入口**不溢出/不换行**；若拥挤，调 `px`/`fontSize` 或允许横向滚动（记录最终方案）。

### Verification
```bash
cd katrain/web/ui
npm test -- src/kiosk/__tests__/NavigationRail.test.tsx src/kiosk/__tests__/TopTabBar.test.tsx src/kiosk/__tests__/KioskApp.test.tsx
npm run build:kiosk-2d
```

### Review Checkpoint 3
停下：导航/路由骨架、nav 测试升级、竖屏布局确认后进入 Phase 4。

---

## Phase 4 — 目录浏览页（分类 / 书 / 章节树）

**目标**：实现 3 个浏览页，镜像 galaxy 层级，用 kiosk 风格 + loading→error→content；章节并行加载；section 跳转携带 `SectionNavState`。

### Files
- Create: `src/kiosk/pages/TutorialCategoriesPage.tsx`、`TutorialBooksPage.tsx`、`TutorialBookDetailPage.tsx`
- Modify: `KioskApp.tsx`（占位 → 真实页）

### Tasks

- [ ] **4.1 `TutorialCategoriesPage.tsx`**（FR-2）：`TutorialReadAPI.getCategories()` → 卡片网格（参考 `PlayPage`/`ModeCard`，遵循 [[feedback_play_page_layout]]），点击 → `/kiosk/tutorial/{slug}`。effect 用 `let cancelled = false` 守卫（其他-3）。loading→error(重试)→content 三态。
- [ ] **4.2 `TutorialBooksPage.tsx`**（FR-3）：`useParams().category` → `getBooks(category)` → 书卡片（标题/作者/`chapter_count`），点击 → `/kiosk/tutorial/book/{id}`；返回按钮；同三态 + cancelled 守卫。
- [ ] **4.3 `TutorialBookDetailPage.tsx`**（FR-4，**并行加载** per Gemini 2.1）：
  - `getBook(bookId)` → 对各章 **`Promise.all(chapters.map(ch => getSections(ch.id)))`**（**勿串行**），建 `Record<chapterId, TutorialSection[]>`。
  - 章可折叠 / 节列表：`section_number. title`、`figure_count`、`has_video` 为真给播放图标提示。
  - 点击节 → `navigate('/kiosk/tutorial/section/'+s.id, { state })`，`state: SectionNavState`：
    ```ts
    { bookId: book.id, bookTitle: book.title, bookSlug: book.slug,
      chapterTitle: chapter.title, sectionTitle: s.title, hasVideo: s.has_video }
    ```
    （注：此处 `s.has_video` 来自 `getSections`，**是可靠的**；section 详情页那个不可靠。）
  - **去掉** galaxy 版的内联 section 视频 dialog（视频改到 section 页播放）。
- [ ] **4.4 接线**：`KioskApp.tsx` 把 `tutorial`、`tutorial/:category`、`tutorial/book/:bookId` 三条占位换成真实页 import。

### Verification
- `npm run dev`：分类→书→章节树走通（缺 dev 数据时先用 mock/占位验证渲染，见 Phase 0.5）。
- 触屏：卡片点击区 ≥48px、`:active` 反馈。
- `npm run build` + `npm run build:kiosk-2d` 绿。

### Review Checkpoint 4
停下：三浏览页 OK、章节并行加载、section 跳转带 state 后进入 Phase 5。

---

## Phase 5 — Section 学习页（Option B：视频为主 + 棋谱面板，核心）

**目标**：核心交付。**不以详情 `has_video` 作开关**——能解析 slug 就尝试播放、`onError` 降级（P0-1）；棋谱缩略图点击放大、按手数复盘；breadcrumb 用 state 优先、刷新降级。

### Files
- Create: `src/kiosk/pages/TutorialSectionPage.tsx`、`src/kiosk/components/tutorial/FigureThumb.tsx`、`src/kiosk/components/tutorial/FigureDialog.tsx`
- Modify: `KioskApp.tsx`（占位 → 真实 section 页）

### Tasks

- [ ] **5.1 `FigureThumb.tsx`**（展示型 per Gemini 2.4，`onClick` 父注入）：
  ```tsx
  import { Box, Typography } from '@mui/material';
  import SGFBoard from '../../../components/tutorials/SGFBoard';
  import type { TutorialFigure } from '../../../types/tutorial';

  export default function FigureThumb({ figure, onClick }: { figure: TutorialFigure; onClick: () => void }) {
    if (!figure.board_payload) return null;   // 空 payload 跳过
    return (
      <Box onClick={onClick} role="button" tabIndex={0}
        sx={{ cursor: 'pointer', minWidth: 48, minHeight: 48, p: 1, borderRadius: 2,
              '&:active': { transform: 'scale(0.97)' } }}>
        <SGFBoard payload={figure.board_payload as any} showFullBoard={false} maxWidth={180} />
        <Typography variant="caption" align="center" display="block">{figure.figure_label}</Typography>
      </Box>
    );
  }
  ```
- [ ] **5.2 `FigureDialog.tsx`**（放大 + 手数滑块；viewport 默认 + 全盘切换；无数字 labels 隐藏滑块，per P1）：
  - MUI `Dialog`，大号 `SGFBoard payload maxWidth={...}`，默认 `showFullBoard={false}`（沿用 viewport 聚焦）；提供「局部/全盘」切换按钮。
  - 手数范围 = `board_payload.labels` 数值的最大值；推导逻辑：
    ```ts
    const maxStep = Math.max(0, ...Object.values(payload.labels ?? {}).map(Number).filter(n => !Number.isNaN(n)));
    ```
  - `maxStep === 0` → **不渲染滑块**（避免 `max=0` 异常交互），仅显示静态棋盘。
  - `maxStep > 0` → `◀ 手数 ▶` 滑块控制传入 `SGFBoard` 的 `maxMoveStep`。
  - 关闭按钮；**不做 narration 文本展示**（本期决策，见 Disposition 2.5）。
- [ ] **5.3 `TutorialSectionPage.tsx`**（FR-5 核心）：
  - `getSection(sectionId)` → `TutorialSectionDetail`（含 `figures[]`），effect 加 cancelled 守卫。
  - `const navState = location.state as SectionNavState | null`。
  - **slug**：`navState?.bookSlug ?? bookSlugFromFigures(section.figures)`。
  - **视频开关（P0-1 关键）**：`const tryVideo = Boolean(slug)`（**不读** `section.has_video`）。
    - `tryVideo` → `<TutorialVideoPlayer src={sectionVideoUrl(slug, id)} poster={sectionPosterUrl(slug, id)} onError={() => setVideoFailed(true)} />`；`videoFailed` 后区域显示「本节暂无视频」。
    - `!slug` → 直接显示「本节暂无视频」，只渲染棋谱区。
  - **棋谱区**：`figures.filter(f => f.board_payload).map` → `<FigureThumb figure onClick={() => setOpen(fig)} />`，网格布局；选中图传入 `<FigureDialog>`。
  - **breadcrumb**（P1 / Gemini 2.3 降级）：
    - 有 state：`{bookTitle} ▸ {chapterTitle} ▸ {section_number}. {title}`。
    - 无 state：`教程 ▸ {section_number}. {title}`（**绝不**出现 `undefined`）。
  - **响应式**：`useOrientation().isPortrait` → 横屏 `flexDirection:'row'`（左视频右棋谱网格）、竖屏 `'column'`（上视频下棋谱网格），参考 `KifuPage`（`KifuPage.tsx:137`）。
  - 返回按钮（回章/节树，优先用 `navState.bookId` 构建链接，否则回 `/kiosk/tutorial`）。
- [ ] **5.4 接线**：`KioskApp.tsx` 把 `tutorial/section/:sectionId` 占位换成 `TutorialSectionPage`。

### Verification
- `npm run dev`：
  - 有视频节：视频可播、可拖进度。
  - **深链验证（P0-1 回归）**：直接打开 `/kiosk/tutorial/section/:id`（清空 state），仍能尝试加载并播放已存在的 section 视频，不因 `has_video=false` 错误隐藏。
  - 棋谱缩略图渲染正确（viewport 裁剪、落子、标号、标注）；点击放大 + 手数滑块前后复盘正常；无数字 labels 的图不出现坏滑块。
  - 无 slug / 视频缺失节：仅棋谱 + 提示，不白屏。
  - breadcrumb 在「点击进入」与「刷新」两种路径都不显示 `undefined`。
- `npm run build` + `npm run build:kiosk-2d` 绿。

### Review Checkpoint 5
停下：核心页验收（尤其深链视频不被错误隐藏）后进入 Phase 6。

---

## Phase 6 — 响应式与打磨

**目标**：横竖屏体验、视觉与 kiosk 一致、边界态统一。

### Tasks
- [ ] **6.1** 分类/书/章节树/section 四页横竖屏布局回归（截图）。
- [ ] **6.2** R1 竖屏 8 入口最终确认（定稿间距/滚动方案）。
- [ ] **6.3** 视觉对齐 `kioskTheme`，与 `PlayPage`/`KifuPage` 一致；卡片尺寸遵循 [[feedback_play_page_layout]]。
- [ ] **6.4** 文案与 kiosk 既有中文导航风格一致（中文为主）。
- [ ] **6.5** 统一媒体错误态、空目录态、加载骨架（`CircularProgress` + `Alert` + 重试）。

### Verification
- 横竖屏全流程截图走查；触屏点击区与反馈检查。
- `npm run build` + `npm run build:kiosk-2d` 绿。

### Review Checkpoint 6
停下：打磨确认后进入 Phase 7。

---

## Phase 7 — 端到端验证与交付

**目标**：自动化 + 手动全面验收，逐条满足 PRD §9 + 本计划新增验收点。

### Tasks

- [ ] **7.1 Playwright e2e（route mock，不静默跳过，per 其他-1）** `tests/tutorial-kiosk.spec.ts`：
  - 用 `page.route('**/api/v1/tutorials/**', ...)` 注入固定分类/书/章/节/section/figures + 一个可解析 slug 的 figure 路径，并 mock section 视频请求返回可加载响应（或断言 `<video>` `src` 正确构建）。
  - 流程：进「教程」→ 选分类 → 选书 → 选章节 → 进 section → 断言视频元素存在且 `src` = 期望 URL → 点缩略图弹出放大棋盘 → 手数滑块可动。
  - **降级用例**：mock 一个无 slug / 视频 404 的 section → 断言显示「本节暂无视频」且棋谱仍渲染、不白屏。
  - **深链用例**：直接 `goto('/kiosk/tutorial/section/:id')`（无 state）→ 断言视频仍尝试加载（不被 `has_video` 隐藏）+ breadcrumb 无 `undefined`。
- [ ] **7.2 galaxy 回归**：手测（或既有 galaxy spec）确认共享下沉未破坏 galaxy tutorial。
- [ ] **7.3 构建/守卫闸门**：
  ```bash
  cd katrain/web/ui
  npm run lint
  npm test
  npm run build
  npm run build:kiosk-2d                 # 含 verify:kiosk-2d
  rg -l "three|@react-three" static-kiosk-2d/ || echo "clean (no 3D)"
  npx playwright test tests/tutorial-kiosk.spec.ts
  ```
- [ ] **7.4 逐条核对 PRD §9（1–9）+ 新增验收点**：
  - 直接打开 section 深链时不因 `has_video=false` 错误隐藏已存在视频。
  - kiosk 源码无写接口调用（守卫测试绿）。
  - nav 测试覆盖「教程」渲染/点击/active。
  - e2e 用固定/mock 数据，不因缺数据静默跳过核心断言。
  - `static-kiosk-2d` 过 `verify:kiosk-2d`，无 galaxy chunk / three.js / `/record` 残留。
- [ ] **7.5（可选）** 真实 SBC / 模拟 kiosk 分辨率下走查媒体经 MinIO 网关播放（生产 S3 路径）。

### Verification / Done 定义
- PRD §9 全部满足 + 上述新增验收点全过；`lint`/`test`/`build`/`build:kiosk-2d`/`verify:kiosk-2d`/e2e 全绿；galaxy 无回归。

### Review Checkpoint 7（收尾）
停下：交人最终 review，决定合并/PR（参考 `superpowers:finishing-a-development-branch`）。本计划不含合并到 develop/master，等显式指示。

---

## 测试策略 Testing Strategy 摘要
- **单测**：`tutorialAssets`（slug 多形态 / URL）—— TDD；只读守卫 `tutorialReadonly.guard`。
- **组件/单测**：nav 测试（NavigationRail/TopTabBar/KioskApp）升级；`FigureDialog` 手数边界（`maxStep=0` 隐藏滑块）可加轻量测试。
- **e2e**：Playwright `tests/tutorial-kiosk.spec.ts`，**route mock**，覆盖主流程 + 降级 + 深链；命令 `npx playwright test`（非 `npm test`）。
- **构建/边界闸门**：每 Phase 末 `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）。
- **回归**：galaxy tutorial（因共享下沉）。
- **命令事实**：`npm test`=vitest（排除 `tests/**`）；类型/构建=`npm run build`（`tsc -b`）；e2e=`npx playwright test`；首次须 `npm install`。

## 风险登记 Risk Register（详见 PRD §10）
| ID | 风险 | 缓解 | 处理阶段 |
|---|---|---|---|
| R1 | 竖屏 8 入口拥挤 | 间距/字号/横向滚动 + nav 测试 + 截图实测 | Phase 3/6 |
| R2 | slug 解析失败 | 无 slug → 不尝试视频、仅棋谱；route state 携带 `bookSlug` 兜底 | Phase 2/5 |
| R3 | 本地媒体样例缺失 | 联调用 mock；e2e route mock | Phase 0/4/5/7 |
| R4 | 共享下沉致 galaxy 回归 | re-export 垫片 + 双构建 + galaxy 手测/回归 | Phase 1/7 |
| R5 | dev 库无教程数据 | 联调前确认；缺则 mock/seed | Phase 0/4 |
| **P0-1** | **详情 `has_video` 恒 false 误隐藏视频** | **不以它作开关；slug→尝试播放→onError 降级；route state 传 hasVideo** | **Phase 2/5/7** |

## 技术债登记 Tech Debt（本期不做，记录避免遗忘）
- **TD-1**：`SGFBoard` 自带 `SGFPayload` 与共享 `BoardPayload` 类型重复 —— 后续收敛为统一 `BoardPayload`（Gemini 2.2）。
- **TD-2**：后端可选增 `GET /books/{id}?include=sections` 一次返回书-章-节树，根治 1+N（Gemini 2.1，需后端，超本期范围）。
- **TD-3**：清理 galaxy `tutorialApi.ts` / `SGFBoard.tsx` re-export 垫片（待 kiosk 落地 + galaxy 回归稳定后）。
- **TD-4**：若后续允许微调后端，可在 `get_section` 计算 `has_video`，前端即可移除「尝试播放」兜底。

## 执行约定
- 用 `superpowers:executing-plans` 执行：每 Phase 完成后在 Checkpoint 停下交 review。
- 每 Phase 是可独立验证的增量；不跨 Phase 攒大改动。
- 不做 PRD Non-goals 任何项；不触碰后端。
