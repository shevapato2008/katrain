# PRD：Kiosk 棋谱库模块对齐网页端（Galaxy）

- **Track**: `sbc-kifu-library-parity`
- **目标分支**: `feature/rk3588-ui`（在 RK3562 上以 kiosk 模式启动）
- **作者**: fan
- **日期**: 2026-06-13
- **状态**: 草案 (Draft)
- **范围**: 仅棋谱库（Kifu Library / 棋谱库）模块及其「在研究中打开」跳转链路

---

## 1. 背景与问题

KaTrain 从同一份前端代码产出两套 Web UI 构建（见 `CLAUDE.md` 的「SBC 构建边界契约」）：

| 构建产物 | 入口 | 面向 |
|---|---|---|
| `katrain/web/static/` | `npm run build` | 完整网页端（Galaxy UI） |
| `katrain/web/static-kiosk-2d/` | `npm run build:kiosk-2d` | SBC kiosk 终端（RK3562/RK3576/RK3588） |

棋谱库模块在两套 UI 下分别独立实现。Galaxy 端「列表 + 棋盘预览 + 在研究中打开」链路完整可用；kiosk 端虽复刻了相同视觉，但**「在研究中打开」无法把棋谱加载进研究界面**，且**底部操作栏的「在研究中打开」按钮在 kiosk 窄屏下文字竖排换行，严重压缩棋盘**。本 PRD 旨在让 kiosk 棋谱库的核心体验对齐 Galaxy，并修复上述两个主要缺陷及若干衍生差异。

### 1.1 现状代码索引

**Galaxy（参考实现）**

| 路由 | 文件 | 职责 |
|---|---|---|
| `/galaxy/kifu` | `galaxy/pages/KifuLibraryPage.tsx` | 棋谱列表 + 搜索 + 分页 + 右侧棋盘预览 + 「在研究中打开」 |
| `/galaxy/research` | `galaxy/pages/ResearchPage.tsx` | **研究棋盘页本身**，支持 `?kifu_id=xxx` 深链：拉取棋谱 SGF 并 `board.loadFromSGF()` 加载 |

**Kiosk（当前实现）**

| 路由 | 文件 | 职责 |
|---|---|---|
| `/kiosk/kifu` | `kiosk/pages/KifuPage.tsx` | 棋谱列表 + 搜索 + 右侧棋盘预览 + 「在研究中打开」 |
| `/kiosk/research` | `kiosk/pages/ResearchPage.tsx` | **研究「新建会话」设置向导**（黑白方/规则/盘面/让子 → 「开始研究」）。**不读取 `kifu_id`，不加载 SGF** |
| `/kiosk/research/session/:sessionId` | `kiosk/pages/GamePage.tsx` | 研究会话真正的棋盘页（由设置向导创建会话后跳入） |

> **关键架构差异**：Galaxy 的 `/galaxy/research` 即棋盘页，自带深链加载棋谱的能力；而 kiosk 把研究拆成「设置向导（`/kiosk/research`） → 会话棋盘页（`/kiosk/research/session/:sessionId`）」两步，棋谱无处注入。这是「在研究中打开」失效的根因（详见 §2.1）。

**共享逻辑（两端复用，位于共享区，改动需保持两套构建均绿）**

- `api/kifuApi.ts`：`KifuAPI.getAlbums({q,page,page_size})`、`KifuAPI.getAlbum(id)`（返回含 `sgf_content`）。
- `types/kifu.ts`：`KifuAlbumSummary` / `KifuAlbumDetail` / `KifuAlbumListResponse`。
- `utils/sgfSerializer.ts`：`sgfToMoves()`（SGF → 落子序列，用于预览）。
- `components/live/LiveBoard.tsx`：只读棋盘预览渲染。
- `hooks/useResearchSession.ts`：`createSession(sgf?, { skipAnalysis?, initialMove? })` —— **已支持传入 SGF 并跳到指定手数**（内部走 `/api/sgf/load` + `/api/redo`）。当前 kiosk 设置向导调用的是 `createSession()`（不传 SGF）。

**后端 API**：无需改动。`/api/v1/kifu/albums`、`/api/v1/kifu/albums/{id}`、`/api/session?mode=research`、`/api/sgf/load`、`/api/redo` 均已就绪。

---

## 2. 需要修改的内容

### 2.1 缺陷一（P0）：「在研究中打开」无法把棋谱加载进研究界面

**现象**：在 `/kiosk/kifu` 选中一局棋谱后点击「在研究中打开」，进入研究界面后棋盘是空的，棋谱未被加载。

**根因（两层）**：

1. `kiosk/pages/KifuPage.tsx:288` 的按钮 `onClick={() => navigate('/kiosk/research')}` —— 跳转时**未携带任何棋谱标识**（对比 Galaxy `KifuLibraryPage.tsx:271` 的 `navigate('/galaxy/research?kifu_id=' + selectedAlbum.id)`）。
2. 即便携带了 `kifu_id`，kiosk 的 `/kiosk/research`（`ResearchPage.tsx`）是**新建会话设置向导**，既不读取查询参数，也不拉取棋谱 SGF，其「开始研究」调用的是 `createSession()`（空会话）。棋谱没有任何注入点。

**需求**：在 `/kiosk/kifu` 选中棋谱并点击「在研究中打开」后，须在研究会话中加载该棋谱的 SGF，并定位到终局（最后一手），用户可在研究界面前后翻阅、试下、分析。

**推荐实现（方案 A，改动最小、复用预览已取数据）**：
直接在 `KifuPage` 内完成「创建会话 + 加载 SGF + 跳转」，绕开设置向导：

- 预览选中棋谱时已调用 `KifuAPI.getAlbum(id)` 拿到 `detail.sgf_content`，当前仅用于解析预览后即丢弃。改为将 `sgf_content` 存入组件 state。
- 点击「在研究中打开」时调用 `useResearchSession().createSession(sgfContent, { initialMove: previewMoves.length, skipAnalysis: true })`，成功后 `navigate('/kiosk/research/session/' + sessionId)`。
- 处理加载态（按钮 loading / 禁用）与失败态（toast 或回退提示）。

**备选实现（方案 B）**：`KifuPage` 跳 `/kiosk/research?kifu_id=X`；在 `kiosk/ResearchPage.tsx` 内检测到 `kifu_id` 时跳过设置向导，自动拉取 SGF → `createSession(sgf)` → 重定向到会话页。
> 方案 A 更聚焦于棋谱库本身、不改动研究向导的既有行为，**建议优先采用方案 A**；若产品希望「带着棋谱进入设置向导再微调规则」，则采用方案 B。实现前二选一并在本节标注最终决定。

**验收**：选中任意棋谱点击「在研究中打开」→ 研究棋盘显示该棋谱终局局面，黑白方信息正确，可前后导航与分析；无棋谱被选中时按钮禁用。

---

### 2.2 缺陷二（P0）：「在研究中打开」按钮竖排换行、压缩棋盘

**现象**：kiosk 底部操作栏的「在研究中打开」按钮文字竖起来（逐字换行），按钮变高，把棋盘可用面积挤小，观感很差。

**根因**：kiosk 横屏下棋谱库为左右各 `flex:1` 的 50/50 布局，右侧预览面板仅约半屏宽。底部栏结构为 `[flex:1 占位][导航按钮 ~280px][flex:1 右侧按钮容器]`，而按钮（`KifuPage.tsx:283-298`）**缺少 `whiteSpace:'nowrap'` 与 `flexShrink:0`**，在被压缩的 `flex:1` 容器内中文「在研究中打开」逐字折行 → 按钮纵向拉高 → 顶高底部栏 → 压缩 `LiveBoard`。Galaxy 因左栏固定 `width:520` 且预览区在宽屏下足够宽，未触发此问题。

**需求**：重新设计底部操作栏，使「在研究中打开」按钮**横向单行显示**，且任何情况下不挤压棋盘。**实现时请调用 `frontend-design` 技能产出最终视觉**。

**设计建议（供 frontend-design 细化）**：
- 立即止血：按钮加 `whiteSpace:'nowrap'`、`flexShrink:0`、`textTransform:'none'`。
- 布局重排（任选其一，以美观与触控友好为准）：
  - (a) 底部栏改为两区：导航控件居中、操作按钮右侧定宽（`minWidth` 保证单行），去掉两侧争抢空间的双 `flex:1`；
  - (b) 窄屏下把「在研究中打开」改为**独占一行的主按钮**（位于导航条下方或上方）；
  - (c) 将操作按钮移至棋盘右上角浮层，底部栏只保留手数导航。
- 同步对齐 §2.3 的导航控件（让两端底部栏体验一致）。

**验收**：在 kiosk 实际分辨率（RK3562 横屏）下，按钮文字单行不换行，棋盘高度不被操作栏挤压；触控目标 ≥ 40px 高。

---

### 2.3 衍生差异（P1，"不限于以上问题"）

调研中发现的其他棋谱库相关差异，建议一并修复以达成体验一致：

1. **预览翻谱控件失效**：kiosk `KifuPage.tsx:265-280` 的 ⏮ ◀ ▶ ⏭ 按钮**无 `onClick`**，手数显示为静态 `move_count / move_count`。Galaxy（`KifuLibraryPage.tsx:432-477`）已接到 `previewCurrentMove` 状态可逐手前后翻阅。需为 kiosk 接上同样的 `previewCurrentMove` 状态与 `LiveBoard` 的 `currentMove`。
2. **列表无分页/无限滚动**：kiosk 仅 `getAlbums({q})` 拉默认首页（约 20 条），全库 15 万+ 棋谱除搜索外无法翻页浏览；Galaxy 有 `Pagination`。建议加分页或无限滚动（kiosk 触控场景下「加载更多/无限滚动」可能优于页码）。
3. **结果徽标与回合信息**：kiosk 用 `KioskResultBadge`（静态），Galaxy 用 `translateResult(result, t, rules)` 并显示 `round_name`。建议对齐结果文案翻译并补充 `round_name` 显示。
4. **标题与计数样式**：kiosk 标题 `variant="h5"`、计数无千分位；Galaxy `h4` + `total.toLocaleString()`。属次要视觉对齐，可随 frontend-design 一并处理。

---

## 3. 范围与非目标（Scope / Non-Goals）

**范围内**：
- `kiosk/pages/KifuPage.tsx`（主要改动）。
- 如采用方案 B，附带 `kiosk/pages/ResearchPage.tsx` 的深链处理。
- 底部操作栏视觉重设计（frontend-design）。

**非目标**：
- 不改动 Galaxy 端任何文件。
- 不改后端 API（现有接口已满足）。
- 不引入 three.js / `@react-three/*` / `/galaxy/*` / `/record` 等非 kiosk 依赖（遵守构建边界契约）。
- 其他模块（研究向导本身的功能、对局、死活题、直播等）由其他 track 负责。

---

## 4. 构建与回归约束

- `KifuPage.tsx` 位于 `src/kiosk/**`，**仅可** import 共享区（`components/`、`hooks/`、`api/`、`utils/`、`types/`）与 `src/kiosk/**`；**不得** import `src/galaxy/**`、`Board3D/**`、`VideoRecorderPage*`（`eslint.config.js` 强制）。
- 若改动落到共享区文件（如 `kifuApi.ts`、`useResearchSession.ts`、`LiveBoard.tsx`），**同时影响 Galaxy**：推送前须 `npm run build` 与 `npm run build:kiosk-2d` 均通过，并跑 `npm run verify:kiosk-2d`（dist 不得含 `three`/`@react-three`/`THREE.`）。
- 优先把新逻辑收敛在 `KifuPage.tsx` 内，避免触碰共享区导致 Galaxy 回归。

---

## 5. 验收清单（Acceptance Criteria）

- [ ] 在 `/kiosk/kifu` 选中棋谱 → 点击「在研究中打开」→ 研究棋盘正确加载该棋谱终局局面，黑白方信息正确，可前后导航/试下/分析。
- [ ] 未选中棋谱时「在研究中打开」按钮为禁用态；加载/失败有明确反馈。
- [ ] kiosk 实际分辨率下，「在研究中打开」按钮文字单行不换行，棋盘高度不被操作栏挤压。
- [ ] 预览区 ⏮ ◀ ▶ ⏭ 可逐手前后翻阅，手数计数随之更新。
- [ ] 列表支持翻页或无限滚动，可浏览首页以外的棋谱。
- [ ] `npm run build` 与 `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）均通过；Galaxy 端棋谱库无回归。
- [ ] 现有 kiosk 单测（`kiosk/__tests__/KifuPage.test.tsx`）更新并通过。

---

## 6. 涉及文件清单

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` | 主改 | 存 `sgf_content`；接「在研究中打开」创建会话并加载 SGF；接预览翻谱控件；底部栏重设计；分页/无限滚动 |
| `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx` | 可选 | 仅当采用方案 B 时新增 `kifu_id` 深链处理 |
| `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx` | 跟随 | 覆盖「在研究中打开」跳转、按钮态、翻谱控件 |
| 共享区（`kifuApi.ts` / `useResearchSession.ts` / `LiveBoard.tsx`） | 尽量不动 | 若需改动，两套构建均须回归 |

---

## 7. 参考

- 构建边界契约：`CLAUDE.md` →「SBC 构建边界契约」
- 同类先例 PRD：`superpowers/tracks/sbc-tsumego-parity/prd.md`
- Galaxy 参考实现：`galaxy/pages/KifuLibraryPage.tsx`、`galaxy/pages/ResearchPage.tsx`（`?kifu_id` 深链段 L176–199）
