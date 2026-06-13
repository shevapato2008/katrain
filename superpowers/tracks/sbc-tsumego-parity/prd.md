# PRD：Kiosk 死活题模块对齐网页端（Galaxy）

- **Track**: `sbc-tsumego-parity`
- **目标分支**: `feature/rk3588-ui`（在 RK3562 上以 kiosk 模式启动）
- **作者**: fan
- **日期**: 2026-06-13
- **状态**: 草案 (Draft)
- **范围**: 仅死活题（Tsumego / 死活题）模块

---

## 1. 背景与问题

KaTrain 从同一份前端代码产出两套 Web UI 构建（见 `CLAUDE.md` 的「SBC 构建边界契约」）：

| 构建产物 | 入口 | 面向 |
|---|---|---|
| `katrain/web/static/` | `npm run build` | 完整网页端（Galaxy UI） |
| `katrain/web/static-kiosk-2d/` | `npm run build:kiosk-2d` | SBC kiosk 终端（RK3562/RK3576/RK3588） |

死活题模块在两套 UI 下分别独立实现。Galaxy 端已是较完整的「选级 → 选分类 → 选单元（每 20 题一组）→ 选题 → 做题」五级流程，并带进度追踪、上一题/下一题、做题计时等；而 kiosk 端目前只有「选级 → 全量平铺列表 → 做题」三级流程，缺失大量能力。本 PRD 旨在让 kiosk 死活题模块对齐 Galaxy 的核心体验，并补齐「本地数据库记录 + 联网时与远端同步」的进度持久化。

### 1.1 现状代码索引

**Galaxy（参考实现）**

| 路由 | 文件 | 职责 |
|---|---|---|
| `/galaxy/tsumego` | `galaxy/pages/TsumegoLevelsPage.tsx` | 难度等级网格（15K…，截图所示页面） |
| `/galaxy/tsumego/:level` | `galaxy/pages/TsumegoCategoriesPage.tsx` | 该等级下的分类（死活/手筋/对杀/吃子/官子） |
| `/galaxy/tsumego/:level/:category` | `galaxy/pages/TsumegoUnitsPage.tsx` | **每 20 题一组的单元列表**，带进度圆点与 `已完成/总数` |
| `/galaxy/tsumego/:level/:category/:unit` | `galaxy/pages/TsumegoListPage.tsx` | 单元内 20 道题卡片（`ProblemCard` 显示进度） |
| `/galaxy/tsumego/problem/:problemId` | `galaxy/pages/TsumegoProblemPage.tsx` | 做题页：面包屑、上一题/下一题、键盘快捷键、成功覆盖层、侧栏控件 |

**Kiosk（当前实现）**

| 路由 | 文件 | 职责 |
|---|---|---|
| `/kiosk/tsumego` | `kiosk/pages/TsumegoPage.tsx` | 难度等级网格（无进度） |
| `/kiosk/tsumego/:levelId` | `kiosk/pages/TsumegoLevelPage.tsx` | **该等级全部题目的平铺列表**（分页 50/页 + 「加载更多」，无分类、无 20 题单元、卡片无进度） |
| `/kiosk/tsumego/problem/:problemId` | `kiosk/pages/TsumegoProblemPage.tsx` | 做题页：棋盘 + 控件，显示计时与尝试次数，但无上一题/下一题、无自动进入下一题、无进度持久化 |

**共享逻辑（两端复用，位于共享区，改动需保持两套构建均绿）**

- `hooks/useTsumegoProblem.ts`：做题核心状态机（落子判定、悔棋、重置、提示、试下、计时 `elapsedTime`、尝试 `attempts`、`saveProgress`）。
- `components/tsumego/TsumegoBoard.tsx`：棋盘渲染。
- `utils/sgfParser.ts`：SGF 解析与正解树判定。

**后端 API（`katrain/web/api/v1/endpoints/tsumego.py`）**

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/v1/tsumego/levels` | 等级列表（含每分类计数） |
| GET | `/api/v1/tsumego/levels/{level}/categories` | 等级下分类列表 |
| GET | `/api/v1/tsumego/levels/{level}/categories/{category}?offset&limit` | 分类内题目（支持分页，Galaxy 用其做 20 题单元） |
| GET | `/api/v1/tsumego/levels/{level}/problems?page&page_size` | 等级全量题目（kiosk 当前用此） |
| GET | `/api/v1/tsumego/problems/{problemId}` | 单题详情（含 SGF） |
| GET | `/api/v1/tsumego/progress` | 当前用户全部进度（需鉴权） |
| POST | `/api/v1/tsumego/progress/{problemId}` | 上报单题进度（需鉴权） |

**数据与同步基础设施（已存在）**

- 远端进度表 `UserTsumegoProgress`（`models_db.py`）：`completed / attempts / first_completed_at / last_attempt_at / last_duration`，主键 `(user_id, problem_id)`。
- 后端写入已实现「字段级合并」（attempts 取 max、completed 取 OR、first_completed_at 取最早），见 `update_progress`。
- 离线发件箱 `SyncQueueEntry` + `sync_worker.py` + `repository.py`（`enqueue_sync_item`）：已为 `create_user_game` 实现「在线→远端 / 离线→本地+排队同步」；但**死活题进度尚未接入该离线管线**——`update_progress` 在 board 模式离线时直接返回 503，而非本地落库 + 排队。

---

## 2. 目标与非目标

### 2.1 目标

1. kiosk 死活题导航对齐 Galaxy：补「分类」与「每 20 题一组单元」两层。
2. kiosk 做题页支持**直接进入下一题**（以及上一题），并在做对后可一键/自动进入下一题。
3. **进度追踪**：在题目列表、单元、分类、等级各层展示「已完成/总数」与每题完成态。
4. **每题耗时**：做题计时持久化（`last_duration`），并在已做题目上可见。
5. **本地数据库记录 + 联网同步**：kiosk 端进度先写本地，联网时与远端数据库双向对齐；后端进度写入接入既有离线发件箱（`SyncQueueEntry`）。

### 2.2 非目标

- 不改动 Galaxy（网页端）死活题的现有行为，仅以其为对齐基准。
- 不新增题库、不改 SGF 正解判定逻辑、不引入 3D / `three.js`（kiosk 构建禁止）。
- 不做跨设备实时推送；同步为「联网即拉取 + 本地变更排队上报」的最终一致模型。
- 不涉及死活题以外的模块（对局/研究/复盘/教程等）。

---

## 3. 详细差异清单（kiosk 缺失项）

| # | 能力 | Galaxy | Kiosk 现状 | 需求 |
|---|---|---|---|---|
| G1 | 分类导航层 | 有（`TsumegoCategoriesPage`） | 无（等级直接到平铺列表） | 新增分类页 |
| G2 | 每 20 题一组的单元 | 有（`TsumegoUnitsPage`，`UNIT_SIZE=20`，进度圆点） | 无（一次 50 题分页平铺） | 新增单元页 |
| G3 | 列表卡片显示进度/完成态 | 有（`ProblemCard` 用 `progress[id]`） | 无（卡片仅显示序号/分类/提示） | 列表卡片接入进度 |
| G4 | 上一题 / 下一题 | 有（含键盘 `[` `]` `←` `→`） | 无 | 做题页加上下题导航 |
| G5 | 做对后进入下一题 | 有（`Enter` 进入下一题） | 无 | 做对后「下一题」按钮 + 可选自动跳转 |
| G6 | 进度持久化到服务器 | 部分（`saveProgress` 仅写 localStorage，含 `TODO: save to server`） | 无 | POST `/progress/{id}` 落库 |
| G7 | 每题耗时记录 | 计时存在，`lastDuration` 仅入 localStorage | 仅界面显示，不持久化 | 持久化 `last_duration` 并展示 |
| G8 | 本地 DB + 离线同步 | 不涉及（网页端在线） | 无 | 本地落库 + 接入 `SyncQueueEntry` 发件箱 |
| G9 | 各层进度汇总（已完成/总数、完成圆点） | 有 | 无 | 单元/分类/等级层汇总 |

> 注：G6/G7 在共享 hook `useTsumegoProblem.ts` 中以 `// TODO: Also save to server if user is logged in` 形式留空，是两端共同的欠账。修复需保持 Galaxy 与 kiosk 两套构建均绿（共享区改动影响双端）。

---

## 4. 需求详述

### 4.1 导航结构对齐（G1、G2）

kiosk 死活题路由由三级扩展为五级，与 Galaxy 对齐（路径前缀 `/kiosk`）：

```
/kiosk/tsumego                              → 等级网格（沿用 TsumegoPage，补进度汇总）
/kiosk/tsumego/:level                       → 分类网格（新增，对应 TsumegoCategoriesPage）
/kiosk/tsumego/:level/:category             → 单元列表，每 20 题一组（新增，对应 TsumegoUnitsPage）
/kiosk/tsumego/:level/:category/:unit       → 单元内题目卡片（新增/改造，对应 TsumegoListPage）
/kiosk/tsumego/problem/:problemId           → 做题页（改造，补上下题/进度/同步）
```

- 单元分组规则与 Galaxy 一致：`UNIT_SIZE = 20`，`总单元数 = ceil(总题数 / 20)`，单元 N 覆盖第 `(N-1)*20+1` 至 `min(N*20, 总数)` 题。
- 数据来源改用 `GET /levels/{level}/categories/{category}?offset&limit`（与 Galaxy 相同），替代当前等级级全量 `/levels/{level}/problems` 平铺。
- 现有 `TsumegoLevelPage.tsx` 的「加载更多 / 50 题分页平铺」逻辑被分类 + 单元结构取代（保留为回退或删除，二选一在实现阶段定）。
- kiosk 已有「横竖屏（`useOrientation`）」「视觉识别（Vision）」适配，分类/单元/列表页需沿用 kiosk 触屏友好的卡片尺寸与栅格，不照搬 Galaxy 的 MUI 断点。

### 4.2 列表与各层进度展示（G3、G9）

- 题目卡片在完成时显示完成标记（对勾/绿色），未完成显示序号；可参照 Galaxy `ProblemCard` 的 `progress[id]` 用法。
- 单元卡片显示进度圆点（5 点制，与 Galaxy `ProgressDots` 同档位：0/≤20%/≤40%/≤60%/≤80%/>80%）与 `已完成/总数`。
- 分类卡片、等级卡片显示该层 `已完成/总数` 汇总。
- 所有进度数据来自统一的进度状态源（见 4.4），不再各页各自 `fetch`。

### 4.3 做题页：上一题/下一题与做对跳转（G4、G5）

- 做题页需知道「当前题在所属单元/分类内的序列与索引」，据此提供上一题、下一题。
  - 序列来源：进入做题页时携带或缓存当前单元的题目 ID 列表（Galaxy 用 `sessionStorage` 缓存 `problems_{level}_{category}`，kiosk 可复用类似缓存或经路由 state 传入）。
- 触屏交互（kiosk 无键盘为主）：在控件区提供明显的「上一题」「下一题」按钮；键盘快捷键可保留但非必需。
- 做对后（`isSolved`）：
  - 成功覆盖层（可复用 `SuccessOverlay`）+ 显著「下一题」按钮。
  - 提供「自动进入下一题」可选项（延时 N 秒，N 默认值实现阶段定，建议 1.5–2s，且在设置中可关闭）。
  - 到达单元最后一题时，「下一题」转为「返回单元 / 进入下一单元」。

### 4.4 进度状态统一来源与持久化（G6、G7）

- 引入单一进度数据源（建议 React context 或共享 hook，例如 `useTsumegoProgress`），负责：
  - 启动时从本地（4.5）加载；登录且在线时与 `GET /api/v1/tsumego/progress` 合并。
  - 做题完成/失败时写入本地并触发同步（4.5）。
- 完善共享 hook `useTsumegoProblem.ts` 的 `saveProgress`：在仅写 localStorage 之外，调用 `POST /api/v1/tsumego/progress/{problemId}`，提交 `{ completed, attempts, lastDuration }`。
  - **注意**：该文件位于共享区，改动同时影响 Galaxy 与 kiosk，需两套构建均验证。
- 每题耗时：`elapsedTime`（秒）在完成时作为 `lastDuration` 持久化；已完成题目可在卡片/做题页展示「上次用时」。
- 字段语义沿用后端合并规则：`attempts = max`、`completed = OR`、`first_completed_at = 最早`、`last_duration = 最近一次`。

### 4.5 本地数据库记录 + 联网同步（G8）—— 核心需求

用户明确要求：**「本地数据库也应该有记录，联网时随时和远端数据库同步」。**

复用已存在的 board 模式离线基础设施，不另起炉灶：

1. **本地落库**：为死活题进度新增本地仓储（参照 `repository.py` 中 user-games 的 `LocalUserGameRepository` 模式），将 `UserTsumegoProgress` 等价记录写入本地 SQLite。
2. **在线/离线分流**：在 `repository.py` 的 dispatcher 增加 `tsumego_update_progress`：
   - 在线：直接 `POST` 远端；成功即返回。
   - 离线或远端失败：写本地 + `enqueue_sync_item(operation="update_tsumego_progress", endpoint="/api/v1/tsumego/progress/{id}", method="POST", payload=...)`。
3. **后端端点接入发件箱**：`update_progress`（`endpoints/tsumego.py`）在 board 模式离线时，由「返回 503」改为「本地写入 + 排队」，与读路径 `get_progress` 离线返回 `{}` 形成对称、可用的离线体验。
4. **回联同步**：`sync_worker.py` 已能按 `operation` 重放队列项（`_execute_item` 通用重放 + 409 幂等），新增 `update_tsumego_progress` 仅需保证 payload/endpoint 正确，无需改 worker 主体。
5. **拉取对齐**：恢复在线时，前端进度源重新拉取 `GET /progress` 并与本地合并（合并规则同 4.4），保证多设备一致。
6. **幂等与冲突**：依赖既有 `idempotency_key` 与后端字段级合并；同一题多次完成不应回退 `completed`，不应丢失更大的 `attempts`。

> 验收以「断网做题 → 进度本地可见 → 恢复网络后远端出现该进度且字段合并正确」为准。

---

## 5. 验收标准

1. **导航**：kiosk 死活题可从等级 → 分类 → 单元（每 20 题）→ 题目卡片 → 做题页逐层进入，层级与 Galaxy 一致。
2. **单元分组**：每个分类按 20 题切分为单元，单元数与边界与 `ceil(total/20)` 一致。
3. **进度展示**：题目卡片显示完成态；单元/分类/等级显示「已完成/总数」与进度圆点；刷新后进度保持。
4. **上下题**：做题页可上一题/下一题；到边界时按钮状态正确（禁用或转为返回）。
5. **做对跳转**：做对后出现成功反馈与「下一题」；自动跳转开关生效。
6. **计时**：每题用时被记录为 `last_duration`，已完成题目可见上次用时。
7. **服务器持久化**：登录在线下做对一题后，`GET /api/v1/tsumego/progress` 能查到该题 `completed=true`、`attempts`、`last_duration`。
8. **离线 + 同步**：断网完成题目 → 本地进度可见；恢复网络后该进度自动同步到远端且字段合并正确（completed 不回退、attempts 取较大值）。
9. **双构建均绿**：`npm run build` 与 `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）均通过；kiosk 构建不含 `three`/`@react-three`。
10. **边界规则未破坏**：新增 kiosk 文件仅 import 共享区 + `src/kiosk/`，符合 `eslint.config.js` 约束。

---

## 6. 影响面与风险

- **共享区改动（高优先关注）**：`useTsumegoProblem.ts` 的 `saveProgress` 与新进度源若放共享区，会同时改变 Galaxy 行为。须确认 Galaxy 端进度写服务器是其期望行为（其代码本就留有 `TODO: save to server`，方向一致），并双端回归。
- **鉴权**：`/progress` 端点需 Bearer token。kiosk 终端的登录/会话态（`无级别` 游客 vs 登录用户）需明确：游客是否仅本地、登录后是否合并本地到账号。**待确认**（见第 7 节）。
- **后端 board 模式**：离线分流改动集中在 `endpoints/tsumego.py` + `repository.py`，须覆盖 board 模式与非 board（本地直连 DB）两种部署。
- **数据量**：单元页只取 20 题，进度汇总需小心避免在等级页一次性拉全量进度导致 SBC 上卡顿；建议进度汇总按需/分层加载或后端提供聚合计数。

---

## 7. 待确认问题（Open Questions）

1. **游客进度**：kiosk 当前账户显示「无级别」。未登录游客的进度只存本地，还是要求登录后才记录/同步？登录后是否把游客期间的本地进度并入账号？
2. **自动进入下一题**：默认开/关？延时多少秒？是否进设置页。
3. **`TsumegoLevelPage`（平铺列表）去留**：被分类/单元结构取代后，是删除还是保留为「全部题目」快捷视图。
4. **进度汇总性能**：等级/分类层的「已完成/总数」是前端用 `GET /progress` 全量在本地算，还是后端新增聚合计数端点。
5. **题目卡片预览**：kiosk 列表卡片是否需要像 Galaxy `ProblemCard` 那样渲染初始局面缩略图（触屏 + SBC 性能权衡）。

---

## 8. 建议实施阶段（非承诺排期）

- **Phase 1 — 导航与展示**：分类页、单元页（20 题分组）、列表卡片进度、等级/分类/单元进度汇总。
- **Phase 2 — 做题页增强**：上一题/下一题、做对跳转、成功覆盖层、计时展示。
- **Phase 3 — 持久化**：完善共享 hook `saveProgress` 写服务器；前端统一进度源。
- **Phase 4 — 本地 DB + 离线同步**：本地死活题仓储、`repository.py` 在线/离线分流、`endpoints/tsumego.py` 接入发件箱、回联拉取合并；端到端离线验收。

---

## 附：关键文件清单

- 前端（kiosk，待改/新增）：`kiosk/pages/TsumegoPage.tsx`、`kiosk/pages/TsumegoLevelPage.tsx`、`kiosk/pages/TsumegoProblemPage.tsx`、`kiosk/KioskApp.tsx`（路由）。
- 前端（共享，谨慎改）：`hooks/useTsumegoProblem.ts`、`components/tsumego/TsumegoBoard.tsx`、`utils/sgfParser.ts`。
- 前端（Galaxy，参考）：`galaxy/pages/Tsumego{Levels,Categories,Units,List,Problem}Page.tsx`、`galaxy/components/tsumego/{ProblemCard,SuccessOverlay,TsumegoProblemControls}.tsx`。
- 后端：`api/v1/endpoints/tsumego.py`、`core/models_db.py`（`UserTsumegoProgress`、`SyncQueueEntry`）、`core/repository.py`、`core/remote_client.py`、`core/sync_worker.py`。
