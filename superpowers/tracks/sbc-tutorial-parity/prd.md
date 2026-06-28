# PRD — 棋智盒 Kiosk 教程模块（只读镜像）

> Track: `sbc-tutorial-parity`
> Branch: `feature/sbc-tutorial-parity`
> Worktree: `/Users/fan/Repositories/katrain-sbc-tutorial-parity`
> Status: Draft — 2026-06-28

---

## 1. 背景 Background

服务器端 galaxy 界面的 tutorial 模块已经完成数据库化改造：教程目录、棋谱（board diagrams）、教学视频从「服务器本地文件」迁移到「数据库（元数据）+ MinIO/S3 对象存储（媒体）」。后端的只读接口与 `/api/v1/tutorials/assets/{path}` 媒体网关已经上线（本地后端 Range 流式，S3 后端 302 重定向到 MinIO/OSS）。

棋智盒（SBC kiosk，RK3562/RK3576/RK3588 触屏终端）目前没有教程模块。本 track 要在 kiosk 端新建一个**只读**的教程模块，与服务器端 galaxy 保持一致的目录层级，让学员可以浏览**已经生成好的**教程目录、棋谱、教学视频。

## 2. 目标 Goal

在 kiosk 端（`src/kiosk/`，kiosk-2d 构建产物 `static-kiosk-2d/`）交付一个教程学习入口，使学员能够：

1. 浏览教程目录（分类 → 书 → 章/节），层级与 galaxy 完全一致。
2. 进入某一节（section / 例题）后，以**视频为主**的方式观看该节的教学视频。
3. 在同一页浏览该节的棋谱（变化图 board diagrams），点击放大并按手数复盘。

这是一项**纯前端**工作。后端接口、数据库、媒体存储、数据标注、视频生成逻辑**一律不实现、不改动**。

## 3. 范围 Scope

### 3.1 In-scope（要做）
- kiosk 新增第 7 个主导航标签「教程」，路由挂在 `/kiosk/tutorial/*`。
- 镜像 galaxy 的 4 级目录浏览：分类落地页 → 书列表 → 章/节树 → section 学习页。
- section 学习页采用 **Option B（视频为主 + 棋谱面板）** 布局：
  - 主区：section 级教学视频 HTML5 播放器。
  - 侧区/下区：本节所有变化图（board diagrams）缩略棋盘；点击放大 + 手数滑块复盘。
- 把 galaxy 的 `tutorialApi.ts` 与 `SGFBoard.tsx` **下沉到共享 territory**，galaxy 与 kiosk 共用（详见技术约束）。
- 新建共享的 `TutorialVideoPlayer` 组件（kiosk 当前没有视频播放）。
- 双构建保持绿：`npm run build`（full web）+ `npm run build:kiosk-2d`（+ `verify:kiosk-2d`）。

### 3.2 Out-of-scope / Non-goals（明确不做）
- ❌ 任何后端改动（FastAPI 路由、Pydantic 模型、SQLAlchemy 表、存储抽象）。
- ❌ 数据标注 / 棋盘识别 / 审核（verify）/ 识别调试面板。
- ❌ 旁白（narration）文本编辑、TTS 音频生成、视频生成。
- ❌ 棋盘编辑工具栏（落子/标注/橡皮擦/保存）。
- ❌ 原书页面扫描图（原书内容栏）—— kiosk 是干净的教学终端，不展示书页扫描。
- ❌ 独立音频播放器（旁白音频已经包含在教学视频里）。
- ❌ galaxy 端 UI 的功能变更（只做必要的 import 路径迁移，行为不变）。
- ❌ 三维棋盘（Board3D / three.js）—— kiosk-2d 构建明令禁止。

### 3.3 可选增强（Nice-to-have，本期可不做）
- 放大棋谱弹层中附带显示该图的**旁白文字**（read-only，纯文本，便于自学）。
- section 内某变化图自带 `fig_{id}.mp4` 时，提供单图视频播放入口。
- 教学视频播放进度记忆。

## 4. 用户与使用场景 Users & Use Case

- **用户**：使用棋智盒触屏终端学习围棋的学员（可能是少儿/初学者）。
- **场景**：在 kiosk 上点「教程」→ 选阶段（入门/布局/中盘/官子）→ 选书 → 选章节 → 看本节教学视频，并对照棋谱逐手复盘。
- **设备特征**：触屏（大点击区域 ≥48px）、横屏或竖屏（kiosk 支持旋转，需响应式）、离线/弱网下媒体走 MinIO 网关。

## 5. 功能需求 Functional Requirements

### FR-1 导航入口
- 在 kiosk 主导航（横屏 `NavigationRail` / 竖屏 `TopTabBar`，数据源 `navTabs.tsx`）新增主标签「教程」，图标区别于「棋谱」(MenuBook)，建议 `School`/`AutoStories`，path `/kiosk/tutorial`，pattern `/kiosk/tutorial/*`。
- 必须验证竖屏 `TopTabBar` 在 6→7 个标签 + 设置后不溢出、不换行（必要时缩小间距或允许横向滚动）。

### FR-2 分类落地页 `/kiosk/tutorial`
- 调 `GET /api/v1/tutorials/categories`，展示分类卡片（入门/布局/中盘/官子），含 summary 与 `book_count`。
- 点击进入 `/kiosk/tutorial/:category`。
- 采用 kiosk 卡片风格（参考 `ModeCard`/`PlayPage`），而非 galaxy 的 MUI 默认 Card 风格；卡片大小遵循既有 kiosk 习惯（参考 [[feedback_play_page_layout]]：卡片不要过大、尽量一屏可见）。

### FR-3 书列表页 `/kiosk/tutorial/:category`
- 调 `GET /api/v1/tutorials/categories/{category}/books`，展示书卡片（标题、作者、`chapter_count`）。
- 点击进入 `/kiosk/tutorial/book/:bookId`；提供返回。

### FR-4 章/节树页 `/kiosk/tutorial/book/:bookId`
- 调 `GET /api/v1/tutorials/books/{bookId}` 得到章列表，对每章调 `GET /api/v1/tutorials/chapters/{chapterId}/sections` 得到节列表。
- 以可折叠/列表方式展示章 → 节；每节显示 `section_number. title` 与 `figure_count`；`has_video` 为真的节给出可视提示（如播放图标）。
- 点击某节进入 `/kiosk/tutorial/section/:sectionId`。

### FR-5 Section 学习页 `/kiosk/tutorial/section/:sectionId`（核心）
- 调 `GET /api/v1/tutorials/sections/{sectionId}` 得到 `TutorialSectionDetail`（含 `figures[]`）。
- **视频**：若 `has_video` 为真，主区渲染 section 级教学视频：
  - URL = `assetUrl('tutorial_assets/{slug}/video/section_{sectionId}.mp4')`，`poster` = 同名 `.jpg`，`preload="none"`，`controls`。
  - **book slug 来源**：从任一 figure 的 `page_image_path`（形如 `tutorial_assets/{slug}/page/...`）解析得到，无需后端改动、对深链/刷新稳健。
  - 无视频时优雅降级：不显示播放器，只显示棋谱区，并给出「本节暂无视频」提示。
- **棋谱区**：展示 `figures[]` 每个变化图的缩略棋盘（`SGFBoard` 渲染 `board_payload`，`showFullBoard=false` 用 viewport 裁剪）。
  - 点击缩略图 → 放大棋盘（弹层或切换面板），带**手数滑块**（`maxMoveStep`，复用 `SGFBoard` 已有的 `maxMoveStep` 逻辑），可前后复盘。
  - 缩略图带 `figure_label`。
- **布局响应式**：
  - 横屏：视频在左、棋谱缩略图网格在右（参考 Option B mockup）。
  - 竖屏：视频在上、棋谱缩略图网格在下。
- 提供返回到章/节树页与面包屑（书名 ▸ 章 ▸ 节）。

### FR-6 媒体加载与错误处理
- 所有媒体走 `assetUrl()` → `/api/v1/tutorials/assets/...` 网关（本地 Range / S3 302）。
- 视频/图片加载失败要有占位与错误提示，不能白屏。
- 列表/详情请求遵循 kiosk 既有 loading→error→content 模式（`CircularProgress` + `Alert` + 重试）。

## 6. UX / 布局参考

Section 学习页（Option B，横屏）：

```
┌─────────────────────────────────────────────┐
│ 中国围棋史 ▸ 第3章 ▸ 例2                     │
├───────────────────────────┬─────────────────┤
│                           │ 本节棋谱         │
│     ┌─────────────────┐   │ ┌────┐ ┌────┐   │
│     │                 │   │ │图1 │ │图2 │   │
│     │   教学视频 ▶     │   │ └────┘ └────┘   │
│     │                 │   │ ┌────┐ ┌────┐   │
│     └─────────────────┘   │ │图3 │ │图4 │   │
│     ━━━━●──────── 2:14     │ └────┘ └────┘   │
└───────────────────────────┴─────────────────┘
```

放大棋谱弹层：大棋盘 + `◀ 手数 ▶` 滑块（+ 可选旁白文字）。

视觉与交互遵循 kiosk `kioskTheme`（深色、jade/wood、Noto Sans SC），而非 galaxy 风格；触屏友好（大按钮、`:active` 缩放）。

## 7. 技术约束 Technical Constraints（SBC 构建边界契约）

> 见仓库根 `CLAUDE.md` 的「SBC 构建边界契约」。

- kiosk 文件（`src/kiosk/**`）**禁止** import `src/galaxy/**`、`src/components/Board3D/**`、`src/pages/VideoRecorderPage*`。
- 因此 galaxy 现有的 `src/galaxy/api/tutorialApi.ts` 与 `src/galaxy/components/tutorials/SGFBoard.tsx` **不能被 kiosk 直接 import**。
- **方案：共享下沉**（已与需求方确认）：
  - `tutorialApi.ts` → `src/api/tutorialApi.ts`（shared territory）。
  - `SGFBoard.tsx` → `src/components/tutorials/SGFBoard.tsx`（shared territory，纯 SVG，无 three.js，kiosk 安全）。
  - galaxy 改为从共享路径 import，行为不变。
- 类型 `src/types/tutorial.ts` 已在共享区，直接复用。
- 修改共享文件**同时影响两个构建** → 每次相关改动后必须跑 `npm run build` 与 `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）。
- `verify:kiosk-2d` 会 grep 产物里的 `THREE.`/`three`/`@react-three` —— SGFBoard 为 SVG，不引入这些，应保持 exit 0。

## 8. 数据 / API 契约（均已存在，只读）

| 端点 | 方法 | 返回 |
|---|---|---|
| `/api/v1/tutorials/categories` | GET | `TutorialCategory[]`（slug/title/summary/order/book_count） |
| `/api/v1/tutorials/categories/{category}/books` | GET | `TutorialBook[]` |
| `/api/v1/tutorials/books/{bookId}` | GET | `TutorialBookDetail`（含 `chapters[]`） |
| `/api/v1/tutorials/chapters/{chapterId}/sections` | GET | `TutorialSection[]`（含 `has_video`） |
| `/api/v1/tutorials/sections/{sectionId}` | GET | `TutorialSectionDetail`（含 `figures[]`） |
| `/api/v1/tutorials/figures/{figureId}` | GET | `TutorialFigure`（如需单图） |
| `/api/v1/tutorials/assets/{path}` | GET | 媒体（本地 Range / S3 302） |

- 媒体 key 约定：
  - section 视频：`tutorial_assets/{slug}/video/section_{sectionId}.mp4`（poster 同名 `.jpg`）
  - figure 视频：`tutorial_assets/{slug}/video/fig_{figureId}.mp4`（可选）
  - 书页图：`tutorial_assets/{slug}/page/page_{n}.jpg`（用于解析 slug，不展示）
- `board_payload` 结构见 `src/types/tutorial.ts`：`{ size, stones{B,W}, labels?, letters?, shapes?, highlights?, viewport? }`。

**不会用到的写端点**（POST/PUT board/narration/generate-audio/verify）一律不调用。

## 9. 验收标准 Acceptance Criteria

1. kiosk 主导航出现「教程」标签，横竖屏均可点击进入，且不破坏既有 6 标签布局。
2. 能从分类 → 书 → 章/节 → section 完整走通，层级与 galaxy 一致。
3. section 学习页：有视频的节能播放 section 教学视频；棋谱缩略图能渲染，点击可放大并按手数复盘。
4. 无视频的节优雅降级（仅棋谱 + 提示），不白屏、不报错。
5. 全程不出现任何编辑/标注/审核/生成 UI。
6. `npm run build` 与 `npm run build:kiosk-2d` 均成功；`npm run verify:kiosk-2d` exit 0。
7. galaxy 端 tutorial 仍正常（import 迁移后回归通过）。
8. kiosk-2d 产物中不含 `three`/`@react-three`/galaxy chunk。
9. 关键流程有 Playwright e2e 覆盖（kiosk 教程浏览 + section 播放）。

## 10. 风险与待确认 Risks & Open Questions

- **R1 竖屏 7 标签拥挤**：`TopTabBar` 固定高度 48、每标签 px 1.5；7 标签 + 设置在窄竖屏可能拥挤。缓解：缩小间距/字号或允许横向滚动；实现阶段需实测截图确认。
- **R2 book slug 解析**：依赖 figure 的 `page_image_path` 前缀解析 slug。若某节 `figures` 为空但 `has_video` 为真，则无法构建视频 URL（极少见）。缓解：解析失败时降级为无视频；必要时退一步用 `getBook` 取 slug。
- **R3 媒体后端环境**：dev 默认 `local` 后端，section 视频需本地 `data/tutorial_assets/...` 存在才能联调播放；生产是 S3。需确认本地或测试环境有可播放的样例数据。
- **R4 共享下沉回归**：迁移 `tutorialApi.ts`/`SGFBoard.tsx` 会改 galaxy import，需保证 galaxy 不回归（构建 + 手测）。
- **R5 dev 数据**：分类是后端硬编码（入门/布局/中盘/官子），但书/章/节/图依赖 DB 已有数据；需确认开发库里有教程数据可联调。

## 11. 关联 References
- 仓库根 `CLAUDE.md` →「SBC 构建边界契约」
- galaxy 现有实现：`src/galaxy/pages/tutorials/*`、`src/galaxy/components/tutorials/*`、`src/galaxy/api/tutorialApi.ts`
- kiosk 参考页：`src/kiosk/pages/KifuPage.tsx`（list+preview）、`TsumegoProblemPage.tsx`（board+面板）
- 实施计划：`./plan.md`
