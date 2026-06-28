# Codex Review Feedback — sbc-tutorial-parity

评审对象：`prd.md`、`plan.md`  
评审日期：2026-06-28  
结论：方向基本正确，Phase 拆分也便于逐步交付；但当前计划存在几处会直接影响验收的契约缺口，建议先修订计划再进入执行。

## 总体评价

Claude 的计划抓住了主线：kiosk 只读教程入口、共享下沉、避免 kiosk 触碰 `galaxy/**` 与 three.js、双构建验证。这些决策与 PRD 基本一致。

主要问题不在页面数量，而在数据契约和验证闸门：计划假设 section 详情接口的 `has_video` 可用、假设迁移搜索命令能覆盖当前相对 import、假设 deep link 能拿到足够的 book/slug/breadcrumb 信息。这些假设与当前代码不完全一致，会导致“按计划实现但核心视频不显示”或“构建/测试遗漏”的风险。

## 必须修正的问题

### P0 — Section 详情页的视频判断会错误隐藏视频

计划在 Phase 5 中写的是：

> `section.has_video && slug` → 渲染 `TutorialVideoPlayer`

但后端当前只在 `GET /chapters/{chapter_id}/sections` 里计算 `has_video`，见 `katrain/web/api/v1/endpoints/tutorials.py:98-115`；`GET /sections/{section_id}` 只做 `model_validate`、填 `figure_count` 和 `figures`，没有计算 `has_video`，见 `katrain/web/api/v1/endpoints/tutorials.py:118-126`。由于 DB model 本身没有 `has_video` 字段，section 详情返回值会默认 `false`。

影响：直接进入 `/kiosk/tutorial/section/:sectionId` 时，即使对象存储里有 `section_{id}.mp4`，页面也会显示“本节暂无视频”。这是核心验收项。

优化：

- 在纯前端约束下，不要把 `TutorialSectionDetail.has_video` 作为最终视频开关。
- 如果能从 figure asset path 解析到 slug，就先构造 section 视频 URL 并渲染播放器；播放器 `onError` 后再降级为“本节暂无视频/视频加载失败”。
- 可选增强：从上一页进入 section 时通过 router `state` 传入 `bookSlug`、`hasVideo`、book/chapter/title；刷新或深链时回退到 slug 解析 + 媒体错误态。
- 如果需求方允许极小后端修正，则最佳方案是在 `get_section` 中与 `get_sections` 一样计算 `has_video`，但这与 PRD “后端一律不改”冲突，需要先确认。

### P0 — 共享迁移的搜索命令漏掉当前真实 import

Phase 1 写了：

- `grep -rn "galaxy/api/tutorialApi" src/`
- `grep -rn "components/tutorials/SGFBoard" src/`

当前 galaxy 页面实际使用的是相对 import，例如 `../../api/tutorialApi`、`../../components/tutorials/SGFBoard`。第一个命令不会命中这些 import；如果删除 `src/galaxy/api/tutorialApi.ts`，很容易留下断裂引用。现有测试 mock 也引用旧路径，例如 `TutorialFigurePage.test.tsx` mock `../../api/tutorialApi`。

优化：

- 用 `rg` 代替 `grep`，并按符号/路径双重搜索：
  - `rg -n "TutorialAPI|api/tutorialApi|components/tutorials/SGFBoard|SGFBoard" katrain/web/ui/src`
  - `rg -n "galaxy/api/tutorialApi|\\.\\./\\.\\./api/tutorialApi|\\.\\./\\.\\./components/tutorials/SGFBoard" katrain/web/ui/src`
- Phase 1 明确包括测试文件 import/mock 的迁移。
- 更稳妥的增量方案：先在旧路径保留 re-export：
  - `src/galaxy/api/tutorialApi.ts` → `export * from '../../api/tutorialApi';`
  - `src/galaxy/components/tutorials/SGFBoard.tsx` → re-export shared component
- 等 kiosk 页面落地、galaxy 回归稳定后，再决定是否删除旧路径。

### P1 — “只读 kiosk”边界没有被类型或测试保护

计划把整个 `TutorialAPI` 移到 shared。当前 `TutorialAPI` 同时包含读接口和写接口：`saveBoardPayload`、`saveNarration`、`generateFigureAudio`、`verifyFigure`，见 `katrain/web/ui/src/galaxy/api/tutorialApi.ts:43-80`。

影响：这不一定会把写 UI 带进 kiosk，但会让 kiosk 代码可以直接 import 并调用写方法，和 PRD 的“只读镜像”约束不够一致。

优化：

- 拆成只读导出与管理导出，例如：
  - `src/api/tutorialApi.ts`：只读 `TutorialReadAPI`
  - `src/galaxy/api/tutorialAdminApi.ts` 或同文件 named export：写接口仅 galaxy 使用
- 如果不拆文件，至少在 kiosk 页面只 import 一个 `TutorialReadAPI`/`Pick` 视图。
- 增加测试或 lint guard：`src/kiosk/**` 不允许出现 `saveBoardPayload|saveNarration|generateFigureAudio|verifyFigure`。

### P1 — Deep link、breadcrumb、book slug 数据来源不足

PRD 要求 section 页有面包屑，且 book slug 解析对深链/刷新稳健。计划主要从 `figures[].page_image_path` 解析 slug，并把 book/chapter 名在缺失时简化。

当前接口事实：

- `TutorialSectionDetail` 只有 section 字段 + `figures[]`，没有 book title、chapter title、book slug。
- `figures` 为空但 `has_video` 为真的情况在 PRD 风险里也已承认。
- section 详情的 `has_video` 当前又不可靠。

影响：普通点击路径可以通过 router state 补齐信息，但刷新或直接打开 section URL 会退化；若 plan 不明确验收口径，执行阶段容易在 PRD 和实现之间摇摆。

优化：

- 在 `TutorialBookDetailPage` 跳转 section 时传 `state`：`bookId`、`bookTitle`、`bookSlug`、`chapterTitle`、`sectionTitle`、`hasVideo`。
- `TutorialSectionPage` 读取 state 优先；无 state 时：
  - slug：从 `page_image_path` / `video_asset` / `audio_asset` 解析；
  - breadcrumb：降级为 `教程 ▸ {section_number}. {title}`；
  - video：有 slug 则尝试播放，失败后降级。
- 把这个降级策略写进 PRD 或计划验收口径，避免把“不可能由现有接口拿到”的 breadcrumb 当作硬失败。

### P1 — SGFBoard 现有尺寸和全盘策略不适合直接做放大弹层

计划在 `FigureDialog` 中用 `SGFBoard payload showFullBoard`。当前 `SGFBoard` 的 SVG 样式硬编码 `maxWidth: 500`，见 `katrain/web/ui/src/galaxy/components/tutorials/SGFBoard.tsx:212-217`。

影响：

- “放大棋盘”在大屏 kiosk 上仍可能只有 500px 宽，不符合触屏复盘体验。
- 强制 `showFullBoard` 会丢掉 `viewport` 聚焦；很多教程变化图本来依赖裁剪区域，放大后变成全盘反而更小、更难看清。

优化：

- 给 shared `SGFBoard` 增加非破坏性 props，例如 `maxWidth?: number | string`、`ariaLabel?`、`className?` 或 `style?`。
- 弹层默认沿用 `viewport` 放大，即 `showFullBoard={false}`；如确实需要全盘，可加“局部/全盘”切换。
- `FigureDialog` 中没有数字 labels 时隐藏或禁用手数滑块，避免 `max=0` 的异常交互。

### P1 — 测试命令和测试层级需要修正

`package.json` 中 `npm test` 是 Vitest，见 `katrain/web/ui/package.json:6-14`。Vitest 配置排除了 `tests/**`，见 `katrain/web/ui/vite.config.ts:31-36`；Playwright e2e 位于 `katrain/web/ui/tests/`，应通过 `npx playwright test` 执行，而不是 `npm test`。

本地审查时还发现当前 worktree 没有安装前端依赖：`npm test` 失败为 `vitest: command not found`，`npx tsc` 尝试访问 npm registry 但网络不可用。因此计划中的验证命令应先明确依赖安装前置条件。

优化：

- 安装前置：`cd katrain/web/ui && npm install` 或 CI 中使用 `npm ci`。
- 类型检查用项目标准：`npm run build` 或 `npx tsc -b`，不要把 `npx tsc --noEmit` 当作唯一类型闸门。
- 单元/组件测试：`npm test -- src/...` 或直接 `npm test`。
- e2e：新增脚本更清晰，例如 `"test:e2e": "playwright test"`，计划中写 `npm run test:e2e -- tests/tutorial-kiosk.spec.ts`。
- Phase 7 不应只写“Playwright e2e”，要写具体命令和是否需要 seed/mock 数据。

### P1 — 现有导航测试会过时，计划未明确更新

现有 `NavigationRail.test.tsx` 与 `TopTabBar.test.tsx` 的用例名仍是 “all 6”，且断言列表漏掉当前已有的“摆谱”，见：

- `katrain/web/ui/src/kiosk/__tests__/NavigationRail.test.tsx:25-31`
- `katrain/web/ui/src/kiosk/__tests__/TopTabBar.test.tsx:25-31`

新增“教程”后，测试应同步升级，而不是只手测截图。

优化：

- 更新 nav 测试断言所有 primary tabs：`对弈/死活/研究/棋谱/摆谱/直播/教程` + `设置`。
- 增加 active route 测试：`/kiosk/tutorial/section/123` 高亮“教程”。
- 增加 click 测试：点击“教程”导航到 `/kiosk/tutorial`。
- `KioskApp.test.tsx` 增加 authenticated route 下 `/kiosk/tutorial` 能渲染教程入口。

## 其他建议

### 1. 数据依赖的 e2e 不要静默跳过核心路径

现有 galaxy tutorial Playwright spec 里有多处 “如果 card 可见就继续，否则跳过后续断言” 的模式。这类测试能做 smoke，但不能证明新 kiosk 核心流程满足验收。

建议 kiosk e2e 使用以下二选一：

- Playwright route mock `/api/v1/tutorials/*`，提供固定分类、书、章节、section、figures 数据；
- 或在测试前显式 seed 教程数据，并在断言中不允许缺数据时静默通过。

### 2. 资源工具要覆盖更多路径形态

`bookSlugFromFigures` 不应只测 happy path。建议测试：

- `tutorial_assets/{slug}/page/page_1.jpg`
- `tutorial_assets/{slug}/video/fig_7.mp4`
- `tutorial_assets/{slug}/audio/fig_7.mp3`
- 前缀缺失、slug 为空、URL 编码/空格、`figures=[]`
- 多个 figures 中第一个路径为空但后续有路径

### 3. 加载 effect 建议有取消/过期保护

多个页面会在 `useEffect` 中异步请求列表和详情。计划可以要求用 `AbortController` 或 `let cancelled = false` 防止快速切路由后旧请求覆盖新状态。现有代码里已有类似模式可参考。

### 4. Route state 与 URL 参数要定义清楚

建议在计划中固定一套跳转数据：

```ts
navigate(`/kiosk/tutorial/section/${section.id}`, {
  state: {
    bookId: book.id,
    bookTitle: book.title,
    bookSlug: book.slug,
    chapterTitle: chapter.title,
    sectionTitle: section.title,
    hasVideo: section.has_video,
  },
});
```

这样普通路径体验完整，刷新时也有明确降级。

## 建议修订后的执行顺序

1. Phase 0：先补充“真实契约核对”
   - 明确 `GET /sections/{id}` 的 `has_video` 不可靠。
   - 明确 section deep link 的 breadcrumb/slug 降级策略。
   - 明确前端依赖安装与测试命令。

2. Phase 1：共享下沉
   - 先移动到 shared。
   - 旧 galaxy 路径保留 re-export，减少一次性破坏面。
   - 用 `rg` 全量更新/核对 imports 和 tests。
   - 引入只读 API 视图，kiosk 只使用只读导出。

3. Phase 2：资源工具与视频播放器
   - `bookSlugFromFigures` 做足异常路径测试。
   - `TutorialVideoPlayer` 支持 `onMissing/onError`，让 section 页可“尝试播放后降级”。
   - 不依赖 section detail 的 `has_video`。

4. Phase 3：导航与路由
   - 更新 `navTabs`、`KioskApp`。
   - 同步更新 `NavigationRail`、`TopTabBar`、`KioskApp` 测试。
   - 竖屏宽度用自动化或截图实测确认：8 个入口（7 primary + 设置）不会溢出。

5. Phase 4：目录页
   - 复用现有 kiosk loading/error/content 模式。
   - section 跳转时传 route state，避免核心页二次猜测。

6. Phase 5：Section 学习页
   - 视频：有 slug 就尝试播放，失败后明确降级；不要用详情 `has_video` 阻断。
   - 棋谱：缩略图用 viewport；弹层默认 viewport 放大，必要时提供全盘切换。
   - `board_payload=null`、无数字 labels、无 figures 都要有明确 UI。

7. Phase 6/7：验证
   - `npm run lint`
   - `npm test`
   - `npm run build`
   - `npm run build:kiosk-2d`
   - `npm run test:e2e -- tests/tutorial-kiosk.spec.ts`（或明确的 Playwright 命令）
   - 手测 galaxy tutorial 和 kiosk 横/竖屏截图。

## 建议加入计划的验收补充

- 直接打开 `/kiosk/tutorial/section/:sectionId` 时，不因 `has_video=false` 错误隐藏已存在的视频。
- kiosk 源码中不出现教程写接口调用：`saveBoardPayload`、`saveNarration`、`generateFigureAudio`、`verifyFigure`。
- 导航测试覆盖“教程”标签渲染、点击、active 高亮。
- e2e 使用固定数据或 seed 数据，不允许因为没有书/章节/视频而静默跳过核心断言。
- `static-kiosk-2d` 仍通过 `verify:kiosk-2d`，且没有 galaxy chunk、three.js 字符串或 `/record` 路由残留。
