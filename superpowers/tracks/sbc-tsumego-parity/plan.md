# 实施计划：Kiosk 死活题对齐 Galaxy（sbc-tsumego-parity）

- **Track**: `sbc-tsumego-parity`
- **分支**: `feature/rk3588-ui`
- **Spec 来源**: `superpowers/tracks/sbc-tsumego-parity/prd.md`
- **状态**: ✅ 已执行 (Phase 1–6 完成, 2026-06-13) — 见文末「执行记录」。剩真机 + 离线端到端验收待用户。
- **日期**: 2026-06-13

> 本计划面向「无上下文的执行者」（另一 session 或 agent）。每阶段自包含、可独立验证、可单独提交。代码片段是**指导性**的（展示意图与关键属性），落地以实际编译/测试通过为准。
> 所有文件路径以仓库根为基准；前端工作目录 `katrain/web/ui/`，后端 `katrain/web/`。

---

## 0. 锁定的设计决策（brainstorming 已定）

| # | 决策 | 选择 |
|---|---|---|
| D1 | 账号模型 | **始终登录绑定账号**。kiosk 所有死活题路由已强制登录（`KioskAuthGuard`），无游客逻辑。进度=账号级，本地 SQLite 缓存 + 联网同步远端。 |
| D2 | 进度写入时机 | **终态写一次 + 按题去重**。`localStorage` 实时更新；服务器/同步队列仅在「做对」或「离开该题」时写，按 `problem_id` 合并（服务器端队列去重）。**不再每步错招都写**（修当前 hook 缺陷）。 |
| D3 | 汇总来源 | **前端统一进度源** `useTsumegoProgress`：登录后拉一次 `GET /progress`，各层（等级/分类/单元/卡片）从同一份数据本地计算。**不加后端聚合端点**。 |
| D4 | 体验增强 | ✅ 卡片棋形缩略图（共享 `MiniBoard`，纯 SVG）✅ 做对自动跳下一题（默认开、~1.5s、设置可关）✅ 保留「全部题目」平铺视图（迁到 `:level/all`）　❌ 不做键盘快捷键（纯触屏） |
| D5 | 单元分组 | 照 Galaxy：`UNIT_SIZE=20`、`totalUnits=ceil(total/20)`、单元 N → `offset=(N-1)*20, limit=20`。 |
| D6 | 卡片完成态视觉 | 照 Galaxy `ProblemCard`：**边框色**（绿=完成 / 橙=尝试过未完成 / 灰=未做）+「上次用时」。不用对勾。 |
| D7 | 进度圆点 | 照 Galaxy `ProgressDots` 5 档：`0 / ≤20% / ≤40% / ≤60% / ≤80% / >80%`。 |
| D8 | 上下题序列源 | `sessionStorage` 缓存当前分类序列，key `problems_{level}_{category}`（仿 Galaxy）；做题页据此算 prev/next 与边界。 |
| D9 | Galaxy 副作用（已确认 OK） | 共享 hook 加服务器持久化后，Galaxy 也会开始写服务器（兑现其 `// TODO: save to server`）。**Galaxy 的 UI/流程不变**，仅多了持久化。需双端回归。 |

---

## 1. 背景与现状（已读码核验，含 PRD 勘误）

### 1.1 后端离线同步基建（已核验，复用成立）
- **dispatcher** `RepositoryDispatcher`（`core/repository.py:155-281`）。`__init__` 入参（`:161-169`）：`connectivity_manager, remote_tsumego, remote_kifu, remote_user_games, local_user_game_repo, sync_enqueue_fn`。无字符串注册表，操作 = 类方法。
- **user-games 离线样板** `user_games_create`（`:241-264`）：在线→`remote.create_game`；离线/失败→`local_user_game_repo.create(...)` + `self._sync_enqueue(operation="create_user_game", endpoint="/api/v1/user-games/", method="POST", payload=..., user_id=...)`。**这是 tsumego 要照抄的模板。**
- **tsumego 现状**（`:181-217`）：只有**只读**方法，离线降级为空（**无离线写、无 `tsumego_update_progress`**）。
- `enqueue_sync_item`（`:283-303`）：每次 `uuid4().hex` 新建一行 `SyncQueueEntry`，**无去重**。
- `RemoteTsumegoRepository.update_progress`（`:116-117`）与 `remote_client.update_progress`（`remote_client.py:177-180`）**已存在** → 无需新增远端方法。
- **sync_worker** `_execute_item`（`sync_worker.py:104-127`）**通用重放**（读 `method/endpoint/payload`，不按 `operation` 分支），409 视为幂等成功（`:118-119`），退避 `min(2^n*10,300)`、`max_retries=5`。**新增 operation 无需改 worker。**
- **SyncQueueEntry**（`models_db.py:566-592`）：列含 `operation`（注释里**已预留** `"update_tsumego_progress"`）、`endpoint/method/payload(JSON)/status/idempotency_key(unique)/retry_count/next_retry_at/...`。
- **UserTsumegoProgress**（`models_db.py:246-259`）：PK `(user_id, problem_id)`；列 `completed/attempts/first_completed_at/last_attempt_at/last_duration`；`problem_id` 有 **FK→`tsumego_problems.id`**（board 本地库可能无此表 → 见风险 R1）。
- **连通性** `ConnectivityManager.is_online`（`connectivity.py`），OFFLINE→ONLINE 自动触发 `sync_worker.run_sync()`（`connectivity.py:119`）。
- **board 模式**：`settings.KATRAIN_MODE=="board"`（`config.py`）；`server.py:_lifespan_board`（`:214-331`）装配 dispatcher，其中 `local_user_game_repo` 在 `:~239` 实例化、dispatcher 在 `:~279` 组装；端点用 `getattr(request.app.state,"repository_dispatcher",None)` 判 board 模式。board 模式 `DATABASE_URL` 强制本地 SQLite。

### 1.2 后端 tsumego 端点
- `update_progress`（`api/v1/endpoints/tsumego.py:309-364`）：**离线直接 `raise HTTPException(503)`（`:~322`）**；在线 `remote.update_progress`。字段合并（`:338-363`，**server 模式直连 DB 路径**）：`attempts=max`、`completed=existing OR incoming`、`last_attempt_at=now`、`last_duration=incoming if not None`、`first_completed_at=now if completed and not set`。
- `get_progress`（`:277-306`）：离线返回 `{}`（`:~288`）。

### 1.3 前端共享层 / 鉴权
- **共享 hook** `hooks/useTsumegoProblem.ts`：`saveProgress`（`:601-618`，**仅 localStorage** + `// TODO: save to server` 于 `:617`）；auto-save effect（`:621-625`，**`isSolved||isFailed` 每次翻 true 都触发** → 每步错招都保存，**这是要修的缺陷**）。`reset()` 自增 `attempts`（`:555`）。返回接口起于 `:627`（含 `problem,isSolved,isFailed,attempts,elapsedTime,startTime,...` 及 `placeStone/undo/reset/toggleHint/enterTryMode/exitTryMode/saveProgress`）。closure 依赖 `[problem,isSolved,attempts,elapsedTime]`。
- **API 层** `api.ts`：`apiPost(path,payload,token?)`（`:117-132`，token→`Authorization: Bearer`）。**`api.ts` 无任何 tsumego 函数**。子模块样板 `api/kifuApi.ts` 存在。
- **鉴权** `context/AuthContext.tsx`（**共享区**）：`token` 存 localStorage `'token'`，`useAuth()` 暴露 `user/token`；`isAuthenticated=!!user`。Galaxy 与 kiosk 均用之。
- **前端无任何在线/离线检测**（无 `navigator.onLine`）。**无 tsumego 进度 context**（Galaxy 各页自行 `localStorage ⊕ GET /progress`）。

### 1.4 kiosk 现状（路由 `KioskApp.tsx:52-54`）
- `tsumego`→`TsumegoPage`（等级网格，无进度）；`tsumego/:levelId`→`TsumegoLevelPage`（**全量平铺 50/页+加载更多**，卡片无进度、无缩略图）；`tsumego/problem/:problemId`→`TsumegoProblemPage`（棋盘+控件+计时+尝试；**无上下题/无自动跳转/无服务器持久化**；**有 Vision 棋盘 setup 集成**——PRD 未提，navigate 时需清理）。
- **PRD 勘误**：①kiosk **无游客模式**，强制登录（`KioskAuthGuard`）——「无级别」只是 `rank` 字段未展示。②kiosk **已写 localStorage**（经共享 hook），非「无任何持久化」。③kiosk 有 Vision 集成。
- `OrientationContext.isPortrait` **恒 false**（外壳固定横屏）→ 新页按横屏布局。
- kiosk 有 `SettingsPage`（`KioskApp.tsx:62` `settings`）→ 自动跳转开关落此处。

### 1.5 Galaxy 参考（照搬逻辑、重写 UI）
- 5 级路由 `GalaxyApp.tsx:42-46`。`TsumegoUnitsPage.tsx`：`ProgressDots`（**内联 `:16-49`**）、`UNIT_SIZE=20`、`?limit=1000` 取全 ID 后 `slice` 分单元（`:122-137`）、`localStorage ⊕ GET /progress` 合并（`:95-117`，`{...prev,...data}` 浅合并）。`TsumegoListPage.tsx`：单元 `offset=(unit-1)*20`（`:50`）、`?offset&limit=20`（`:54`）、`completed/total` Chip。`ProblemCard.tsx`：边框色态 + `MiniBoard size=100 blackStones whiteStones`（**纯 SVG，无 three.js**）+ 上次用时。`TsumegoProblemPage.tsx`：`sessionStorage` key `problems_{level}_{category}`（`:91-115`，缺失则 `?limit=100` 拉取并存）、键盘（`:199-234`）、`<SuccessOverlay show={isSolved}>`（`:297`，**未传 `onComplete` → Galaxy 实际不自动跳**）、胜利音（`:177-180`）。`SuccessOverlay.tsx`：`onComplete` 存在则 `setTimeout(onComplete,2000)`。
- **共享可复用**：`hooks/useTsumegoProblem.ts`、`utils/sgfParser.ts`、`components/MiniBoard.tsx`（SVG）、`components/tsumego/TsumegoBoard.tsx`（canvas 2D，kiosk 已用）。
- **禁止 import 进 kiosk**：`galaxy/**`（含其 `SuccessOverlay/ProblemCard/ProgressDots/TsumegoProblemControls`）。kiosk 需自建 kiosk 版。

---

## 2. 约束与护栏（每阶段适用）

- **共享区改动影响双端**：`hooks/useTsumegoProblem.ts`、新 `context/TsumegoProgressContext.tsx`、新 `api/tsumegoApi.ts`（或 `api.ts`）→ **改后双构建 + Galaxy 回归必验**。
- **kiosk 新文件仅 import**：共享区（`hooks/ context/ api/ api.ts utils/ components/`(非 `Board3D/`)`types/ theme`）+ `src/kiosk/**` + `@mui/material`。**禁** import `src/galaxy/**`、`Board3D/**`、`VideoRecorderPage*`（`eslint.config.js` 强制）。
- **离线分流改动覆盖**：board 模式（dispatcher 在）与非 board（端点直连 DB）两条路径。
- **i18n**：UI 文案走 `useTranslation` 的 `t(key, '中文兜底')`（仿 kifu plan）；尽量复用既有 `tsumego:*` key。
- **收尾闸门**：`npm run build` ✅、`npm run build:kiosk-2d`（含 `verify:kiosk-2d`，dist 无 `three`/`@react-three`/`THREE.`）✅、`npm test` ✅、`npx tsc --noEmit` ✅、`CI=true uv run pytest tests/web_ui tests/test_user_game_repo.py`（相关）✅。
- **进度字段不变式**：`completed` 单调（本地 upsert 与远端合并都 OR）；`attempts=max`；`last_duration=最近`；`first_completed_at=最早`。队列按 `endpoint`(含 problem_id) 去重时**最新覆盖**安全（completed 由 OR 兜底不回退）。

---

## 3. 阶段拆解

### Phase 0 — 基线（绿色起点）
1. `cd katrain/web/ui && npm install`（若未装）。
2. `npm test`（记录现有 kiosk tsumego 用例：`src/kiosk/__tests__/{TsumegoPage,TsumegoLevelPage,TsumegoProblemPage,navigation.integration}.test.tsx` 全绿）。
3. `npx tsc --noEmit` ✅。
4. 后端：`CI=true uv run pytest tests/web_ui/test_tsumego_api.py tests/test_user_game_repo.py tests/web_ui/test_board_auth.py`（记录基线）。

**完成标准**：双构建可跑、相关测试绿、无未提交改动。

---

### Phase 1 — 后端：tsumego 进度本地落库 + 离线分流（G8 核心）
**目标**：`POST /progress/{id}` 离线由「503」改为「本地写 + 排队」；`GET /progress` 离线读本地；队列按题去重。`sync_worker`/`remote_client` 不动。

**1.1 抽出字段合并为可复用函数**（消除端点内联与本地仓储重复）
- 在 `core/` 新增（或就近）`merge_tsumego_progress(existing: dict|None, incoming: dict) -> dict`，实现 §1.2 合并规则（attempts=max、completed=OR、last_duration=incoming if not None、first_completed_at=最早、last_attempt_at=now）。`endpoints/tsumego.py:338-363` server 模式改调用之。

**1.2 本地仓储** `core/tsumego_progress_repo.py`（仿 `core/user_game_repo.py`）
```python
class LocalTsumegoProgressRepository:
    def __init__(self, session_factory): self._sf = session_factory
    def upsert(self, user_id: int, problem_id: str, data: dict) -> dict:
        # SELECT UserTsumegoProgress PK=(user_id, problem_id)；merge_tsumego_progress(existing, data)；写回；返回 dict
    def list(self, user_id: int) -> dict:
        # 返回 { problem_id: {completed, attempts, first_completed_at, last_attempt_at, last_duration} }
```
- **R1 FK**：board 本地库可能无 `tsumego_problems` 行。确认本地 engine 未开 `PRAGMA foreign_keys=ON`（SQLite 默认关）；若开，去掉该 FK 强制或允许悬空 `problem_id`。执行时实测一次 insert 未知 problem_id 不报错。

**1.3 dispatcher 加方法 + 入参**（`core/repository.py`）
- `__init__` 增 `local_tsumego_progress_repo=None`，存 `self._local_tsumego_progress_repo`。
- 新增（仿 `user_games_create:241-264`）：
```python
async def tsumego_update_progress(self, user_id: int, problem_id: str, data: Dict) -> Dict:
    if self.is_online:
        try:
            return await self.remote_tsumego.update_progress(problem_id, data)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning("tsumego_update_progress remote failed, falling back to local: %s", e)
    result = self._local_tsumego_progress_repo.upsert(user_id, problem_id, data)
    if self._sync_enqueue:
        self._sync_enqueue(
            operation="update_tsumego_progress",
            endpoint=f"/api/v1/tsumego/progress/{problem_id}",
            method="POST", payload=data, user_id=str(user_id),
            coalesce_on_endpoint=True,          # 按题去重（见 1.4）
        )
    return result

async def tsumego_get_progress_local(self, user_id: int) -> Dict:
    return self._local_tsumego_progress_repo.list(user_id)
```

**1.4 队列按题去重**（`enqueue_sync_item`）
- 加形参 `coalesce_on_endpoint: bool = False`；为真时插入前 `DELETE FROM sync_queue WHERE endpoint=:endpoint AND status='pending'`（endpoint 含 problem_id → 每题仅留最新一条）。最新覆盖安全（见 §2 不变式）。

**1.5 端点接入**（`api/v1/endpoints/tsumego.py`）
- `update_progress` board 分支：删 503，改
  ```python
  return await dispatcher.tsumego_update_progress(current_user.id, problem_id, data.model_dump())
  ```
- `get_progress` board 分支：离线 `return {}` 改为 `return await dispatcher.tsumego_get_progress_local(current_user.id)`（Gap E）。
- server（非 board）分支不变，但合并改用 1.1 的函数。

**1.6 server 接线**（`server.py:_lifespan_board`）
- 实例化 `LocalTsumegoProgressRepository(SessionLocal)`，作 `local_tsumego_progress_repo=` 传入 `RepositoryDispatcher(...)`（`:~279`）。

**1.7 后端测试**（新增 `tests/web_ui/test_tsumego_offline.py` + `tests/test_tsumego_progress_repo.py`，仿 `test_user_game_repo.py`/`test_board_auth.py`）
- `merge_tsumego_progress`：completed OR、attempts max、first_completed_at 最早、last_duration 覆盖。
- `LocalTsumegoProgressRepository.upsert/list`（内存 SQLite）：重复 upsert 不回退 completed、attempts 取大。
- dispatcher `tsumego_update_progress`：mock 在线→走 remote；离线→本地 upsert + enqueue 一条（operation/endpoint/method 正确）；同题二次 enqueue 后 pending 仅 1 条（去重）。
- 端点离线：board+offline POST 返回 200 且本地可见、`get_progress` 返回本地数据（非 {}）。

**完成标准**：上述 pytest 全绿；`sync_worker.py`/`remote_client.py` 零改动。

---

### Phase 2 — 共享前端：统一进度源 + 终态服务器持久化（共享区，双端均验）
**目标**：单一 READ 源 `useTsumegoProgress`；WRITE 终态一次、token-gated、不再每步错招写。Galaxy 仅获持久化、UI 不变（D9）。

**2.1 API 函数** `api/tsumegoApi.ts`（新，共享）
```ts
export interface TsumegoProgressEntry { completed: boolean; attempts: number; firstCompletedAt?: string; lastAttemptAt?: string; lastDuration?: number; }
export const TsumegoAPI = {
  getProgress: (token: string): Promise<Record<string, TsumegoProgressEntry>> => /* GET /api/v1/tsumego/progress, Bearer */,
  saveProgress: (id: string, data: {completed:boolean; attempts:number; lastDuration?:number}, token: string) => apiPost(`/api/v1/tsumego/progress/${id}`, data, token),
};
```

**2.2 统一进度源** `context/TsumegoProgressContext.tsx`（新，共享）
- Provider 状态 `progress: Record<id, TsumegoProgressEntry>`。
- 初始化：同步读 localStorage `'tsumego_progress'`；`token` 存在则 `TsumegoAPI.getProgress` 字段级合并（completed OR、attempts max、最新 lastDuration/lastAttemptAt、最早 firstCompletedAt）。
- `markProgress(id, {completed, attempts, lastDuration})`：内存 + localStorage 立即字段级合并（UI 即时）；`token` 存在则 `TsumegoAPI.saveProgress` fire-and-forget（`.catch` 吞，离线由后端落本地+排队）。
- 暴露聚合 helper：`unitProgress(ids:string[])→{completed,total}`、`categoryProgress(ids)`、`isCompleted(id)`、`refresh()`。
- **安全默认**：`useTsumegoProgress()` 默认 context 给 no-op `markProgress` + 空 progress（无 Provider 时 hook/测试不崩）。
- Provider 包裹 **KioskApp 与 GalaxyApp**（tsumego 用到处）。

**2.3 改共享 hook** `hooks/useTsumegoProblem.ts`（**高风险，双端**）
- 引 `useTsumegoProgress()`（来自 2.2）。
- **删除** `:621-625` 「`isSolved||isFailed` 都 saveProgress」的服务器/每步写法；改为：
  - 仍**实时写 localStorage**（保留即时缓存，离线/无 Provider 兜底）。
  - **服务器/统一源写**仅在 `isSolved` 由 false→true 时一次（`useRef` 守卫，防重复）：`markProgress(problem.id, {completed:true, attempts, lastDuration:elapsedTime})`。
  - **离开/卸载 flush**：暴露并在 `TsumegoProblemPage` 卸载时调用；若本题曾有尝试（`attempts>0 || moveHistory.length>0`）但未在解出时写过，则 `markProgress(problem.id, {completed:isSolved, attempts, lastDuration:elapsedTime})` 一次。
  - **不在每步错招写服务器**（仅 localStorage 可继续即时）。
- 保持返回接口向后兼容（`saveProgress` 仍可保留为「写 localStorage + markProgress」入口；新增 `flushProgress`）。

**2.4 Provider 接线**
- `KioskApp.tsx`：在 `OrientationProvider/VisionProvider` 链中加 `TsumegoProgressProvider`（包住 `KioskRoutes`）。
- `GalaxyApp.tsx`：在其 Provider 链加 `TsumegoProgressProvider`。
- 不改 Galaxy 各 tsumego 页的现有读法（可保留；或后续单独迁移——**本 track 不强制改 galaxy 页，避免回归**）。

**完成标准**：`npx tsc --noEmit` ✅；`npm run build` + `npm run build:kiosk-2d`（verify 绿）✅；现有 hook 相关测试绿（更新 mock，见 Phase 5）；**Galaxy `/galaxy/tsumego` 手测：解题后 `GET /progress` 出现该题、刷新进度仍在、UI/流程无变化**。

---

### Phase 3 — Kiosk 导航与进度展示（G1/G2/G3/G9）
**目标**：kiosk 死活题五级；各层进度；卡片缩略图 + 完成态；保留「全部题目」。仅用共享区 + `src/kiosk/`。

**3.1 路由**（`KioskApp.tsx`，替换 `:52-54`）
```
tsumego                         → TsumegoPage           (等级网格 + 进度汇总)
tsumego/:level                  → TsumegoCategoriesPage (新)
tsumego/:level/all              → TsumegoLevelPage      (保留：全部题目平铺，加进度)
tsumego/:level/:category        → TsumegoUnitsPage      (新, 20 题单元 + 圆点)
tsumego/:level/:category/:unit  → TsumegoUnitListPage   (新, 单元内卡片)
tsumego/problem/:problemId      → TsumegoProblemPage    (Phase 4 改造)
```
> 路由顺序：v6 best-match，静态 `problem`/`all` 胜过动态 `:level`/`:category`；分类 slug（死活/手筋/对杀/吃子/官子）不与 `all`/`problem` 冲突。把 `tsumego/:level` 从旧 `TsumegoLevelPage` 改指 `TsumegoCategoriesPage`。

**3.2 kiosk 公共小组件**（`src/kiosk/components/tsumego/`）
- `ProgressDots.tsx`：照 Galaxy `TsumegoUnitsPage.tsx:16-49` 的 5 档阈值（D7），触屏放大尺寸。
- `ProblemCard.tsx`：`MiniBoard`（共享，`size` 触屏友好）+ 边框色态（D6）+「上次用时」+ 题号；从 `useTsumegoProgress` 读 `progress[id]`。
- `SuccessOverlay.tsx`：kiosk 版成功覆盖层（自写，**不** import galaxy；可简化动画）。

**3.3 新页面**（`src/kiosk/pages/`，沿用 kiosk 卡片尺寸/栅格、横屏）
- `TsumegoCategoriesPage.tsx`：`GET /levels/{level}/categories`；卡片显示 `name/count` + 该分类 `已完成/总数`（用 `useTsumegoProgress`，需该分类题 ID → 见 3.5 性能）。点击 → `/kiosk/tsumego/{level}/{category}`。
- `TsumegoUnitsPage.tsx`：`GET /levels/{level}/categories/{category}?limit=1000` 取全 ID；`UNIT_SIZE=20` 切单元（D5）；每单元 `ProgressDots` + `已完成/总数`。点击 → `.../{unitNumber}`。**把该分类全 ID 写入 `sessionStorage['problems_{level}_{category}']`**（供做题页 prev/next，D8）。
- `TsumegoUnitListPage.tsx`：`offset=(unit-1)*20`、`?offset&limit=20`；`ProblemCard` 网格（缩略图来自 detail 的 `initialBlack/initialWhite`）。点击 → `/kiosk/tsumego/problem/{id}`（并确保该单元/分类序列已在 sessionStorage）。

**3.4 改造 `TsumegoPage.tsx` 与 `TsumegoLevelPage.tsx`**
- `TsumegoPage`：等级卡片补 `已完成/总数` 汇总（可惰性/分层，见 3.5）。导航改指 `/kiosk/tsumego/{level}`（分类页）。
- `TsumegoLevelPage`（保留为「全部题目」）：路由迁 `:level/all`；卡片接 `useTsumegoProgress` 完成态；入口（在分类页加「全部题目」快捷按钮）。

**3.5 进度汇总性能（R2）**
- 各层从 `useTsumegoProgress` 的**单份** `progress` map 本地算，避免每页各自全量 `fetch`。
- 等级/分类「已完成/总数」需要该层题 ID 集合：分类层有（`?limit=1000` 已取）；等级层若需精确完成数，**惰性**（仅在该等级展开/进入时算）或显示「分类数/总题数」弱汇总，避免等级页一次拉全部等级全部题。执行时择一落地并在交付说明记录。

**完成标准**：五级可逐层进入；单元数=`ceil(total/20)`、边界正确；卡片完成态/缩略图、单元圆点、分类/等级汇总显示；`npm run build:kiosk-2d`（verify 绿，无 three）✅。

---

### Phase 4 — Kiosk 做题页增强（G4/G5/G7）
**目标**：上一题/下一题、做对成功反馈 + 自动跳转（默认开/可关）、上次用时；终态经统一源持久化。

**4.1 上一题/下一题**（`src/kiosk/pages/TsumegoProblemPage.tsx`）
- 读 `sessionStorage['problems_{level}_{category}']`（由 Phase 3.3 写入）得序列与 `currentIndex`；缺失则 `GET /levels/{level}/categories/{category}?limit=100` 拉取并存（仿 Galaxy `:91-115`）。
- 控件区加显著「上一题」「下一题」触屏按钮；`navigate('/kiosk/tsumego/problem/{id}')`。边界：首题禁用上一题；**末题「下一题」转「返回单元 / 进入下一单元」**。**不加键盘快捷键**（D4）。

**4.2 做对反馈 + 自动跳转**
- `isSolved` 时显示 kiosk `SuccessOverlay` + 胜利音（仿 Galaxy `:177-180`）+ 显著「下一题」。
- **自动跳转**：默认开、~1.5s 后跳下一题；读 kiosk 设置开关（4.4）；末题不自动跳（转返回）。用 `setTimeout` + 清理（离开/再次落子取消）。

**4.3 计时/上次用时**
- 解出后 `elapsedTime` 经统一源持久化（`markProgress` lastDuration，Phase 2.3）。
- 题目卡片（Phase 3.2 `ProblemCard`）与做题页显示「上次用时」（来自 `progress[id].lastDuration`）。

**4.4 设置开关**（`src/kiosk/pages/SettingsPage.tsx`）
- 加「做对后自动进入下一题」开关，持久化 localStorage（如 `kiosk_tsumego_autoadvance`，默认 `true`）；做题页读取。

**4.5 Vision 清理**
- navigate 到上/下题或卸载前，清理 Vision setup 态（避免后端遗留 setup mode）。执行时核对 `useVisionSync`/`VisionContext` 是否需显式 cancel。

**完成标准**：上/下题可用、边界正确；做对有覆盖层 + 下一题；自动跳转开关生效；上次用时可见；`npm run build:kiosk-2d` ✅。

---

### Phase 5 — 前端测试（更新 + 新增）
**5.1 修既有 mock**：`src/kiosk/__tests__/TsumegoProblemPage.test.tsx` 的 `useTsumegoProblem` mock（`defaultHookReturn`）补 `flushProgress` 等新返回；用 `TsumegoProgressProvider` 包裹或 mock `useTsumegoProgress`。
**5.2 新页面用例**：`TsumegoCategoriesPage`/`TsumegoUnitsPage`/`TsumegoUnitListPage`——fetch 正确端点、单元数=`ceil(total/20)`、卡片读 `progress`、点击导航。`ProgressDots` 档位、`ProblemCard` 边框色态/上次用时。
**5.3 做题页**：prev/next（含边界禁用/末题转返回）、做对覆盖层、自动跳转（fake timers，开/关两态）、上次用时显示、终态调用 `markProgress`（spy）。
**5.4 统一源**：`useTsumegoProgress` 合并规则（localStorage ⊕ server）、`markProgress` 写 localStorage + token-gated POST（spy）、聚合 helper。
**5.5 导航集成**：`navigation.integration.test.tsx` 扩五级路径。

**完成标准**：`npm test` 全绿；新增分支均有用例。

---

### Phase 6 — 双构建 + 回归 + 验收闸门
1. `npm run build`（Galaxy）✅；`npm run build:kiosk-2d`（含 `verify:kiosk-2d`，dist 无 `three`/`@react-three`/`THREE.`）✅。
2. `npx tsc --noEmit` ✅；`npm test` ✅。
3. 后端：`CI=true uv run pytest tests/web_ui tests/test_user_game_repo.py tests/test_tsumego_progress_repo.py`（新）✅。
4. **Galaxy 回归（D9）**：`/galaxy/tsumego` 五级 + 解题 → 服务器出现进度、UI/流程无变化。
5. **离线 e2e 验收**（PRD §5.8，board 模式）：断网做对一题 → 本地进度可见（卡片/汇总）→ 恢复网络 → 远端出现该题且字段合并正确（completed 不回退、attempts 取大）。
6. **实机验收（RK 终端，对照 PRD §5）**：五级导航 / 单元分组 / 进度展示刷新保持 / 上下题边界 / 做对跳转开关 / 上次用时 / 登录在线 `GET /progress` 可查 / 离线+恢复同步 / 双构建绿 / 边界规则。

**完成标准**：PRD §5 十条全勾。

---

## 4. 风险与回滚

| ID | 风险 | 处置 |
|---|---|---|
| R1 | board 本地 SQLite `UserTsumegoProgress.problem_id` FK→`tsumego_problems`（本地可能无表/无行）写入失败 | 确认本地 engine 未开 `PRAGMA foreign_keys=ON`（默认关）；如开则放宽 FK/允许悬空。Phase 1 实测一次未知 id insert |
| R2 | 等级/分类汇总一次拉全量进度致 SBC 卡顿 | 统一源单份 `progress` 本地算；等级层惰性/弱汇总（Phase 3.5） |
| R3 | 共享 hook 改动回归 Galaxy（每步错招写、Provider 缺失崩） | 统一源安全默认 no-op；服务器写仅 `isSolved` 一次 + 卸载 flush；Phase 2/6 Galaxy 回归 + 双构建 |
| R4 | 队列同题堆积 | `coalesce_on_endpoint` 按 endpoint(含 problem_id) 去重；completed 由 OR 兜底不回退 |
| R5 | 自动跳转 setTimeout 泄漏/误跳（离开题/再落子） | effect cleanup 清 timer；末题不跳 |
| R6 | Vision setup 残留 | navigate/卸载清理（Phase 4.5） |
| R7 | 离线 token 过期致回联同步阻塞 | 既有 `sync_worker` `auth_required` 暂停机制兜底（user-games 同款），不在本 track 解决 |

**回滚**：后端改动集中 `repository.py`/`tsumego_progress_repo.py`(新)/`tsumego.py`/`server.py`/`enqueue_sync_item`；前端集中共享三文件 + `src/kiosk/**`。分阶段提交，可按 Phase `git revert`。

---

## 5. NOT in scope（显式延后）
- 不新增题库、不改 SGF 正解判定、不引入 three.js/`@react-three`/`/galaxy/*`/`/record`。
- 不改 Galaxy 各 tsumego 页的读法（仅加 Provider；其行为不变）。
- 不做跨设备实时推送（最终一致）。
- 不改 `sync_worker.py`/`remote_client.py`（已通用/已具方法）。
- 游客模式、设备级账号（D1 已排除）。

## 6. What already exists（复用，不重建）
| 子问题 | 既有 | 处置 |
|---|---|---|
| 离线发件箱 + 通用重放 + 409 幂等 | `SyncQueueEntry`/`sync_worker._execute_item`/`connectivity` | 复用，不改 |
| 远端进度方法 | `RemoteTsumegoRepository.update_progress`/`remote_client.update_progress` | 复用，不改 |
| user-games 离线样板 | `dispatcher.user_games_create` + `enqueue_sync_item` | 照抄成 tsumego |
| 做题状态机/SGF/棋盘 | `useTsumegoProblem`/`sgfParser`/`TsumegoBoard`(shared) | 复用 |
| 缩略图 | `components/MiniBoard`（SVG） | 复用（kiosk ProblemCard） |
| 五级 UI 逻辑 | Galaxy 各页 + `ProgressDots`/`ProblemCard` | **照搬逻辑、kiosk 重写 UI**（不 import galaxy） |
| 后端分类/分页端点 | `/levels/{level}/categories`、`?offset&limit` | 复用（kiosk 改用） |

## 7. 并行化策略
- **Phase 1（后端）∥ Phase 2（共享前端）**：不同文件、契约已知，可并行。
- **Phase 3（导航页）∥ Phase 4（做题页）**：均依赖 Phase 2 的 `useTsumegoProgress`/`api/tsumegoApi`；之间不同文件，可并行（注意 Phase 3.3 写 sessionStorage 序列是 Phase 4.1 的输入，接口约定先定）。
- Phase 5 测试随各 Phase 增量补；Phase 6 闸门最后。
- 共享区改动（Phase 2）落地后，Phase 3/4 才动 kiosk 页。

## 8. 待确认/真机回报项（不阻塞编码）
1. RK 终端实际分辨率 → 卡片栅格/缩略图尺寸与每页缩略图数性能（Phase 3/6 真机）。
2. 自动跳转默认开 + ~1.5s（已按 D4 默认；真机体感可调）。
3. 等级层汇总精度策略（精确 vs 弱汇总，Phase 3.5 择一并回报）。

## GSTACK REVIEW REPORT
| Review | Runs | Status |
|--------|------|--------|
| CEO / Design / DX | 0 | 未运行（用户直接 write→execute） |
| Eng Review | 0 | 未运行（架构已 brainstorming 锁定；执行中以双构建+回归+离线 e2e 为闸门） |
| Codex Review | 0 | 未运行 |

- **VERDICT**: Architecture LOCKED（brainstorming D1–D9）。直接 executing-plans，按 Phase 0→6 执行，Phase 1∥2、3∥4 可并行。

---

## 执行记录 (2026-06-13, 自主执行)

提交链（feature/rk3588-ui）：`828fb3c6`(docs) → `35c9d68b`(P1) → `9a69e21f`(P2) → `27b5974a`(P3) → `334c13df`(P4) → `f97f8180`(P5) → `5d54828f`(对抗式审查修复)。

**各 Phase 落地**
- P1 后端：新增 `core/tsumego_progress_repo.py`(`merge_tsumego_progress` 共享合并 + `LocalTsumegoProgressRepository`)；`repository.py` dispatcher `tsumego_update_progress`/`tsumego_get_progress_local` + `enqueue_sync_item(coalesce_on_endpoint)`；`endpoints/tsumego.py` 离线 503→本地写+排队、`get_progress` 离线读本地；`server.py` 接线。`sync_worker`/`remote_client` 未改。
- P2 共享前端：`api/tsumegoApi.ts` + `context/TsumegoProgressContext.tsx`(单一进度源 + 安全 no-op 默认)；`useTsumegoProblem` 服务器写仅 isSolved 一次 + 卸载 flush（修「每步错招都写」缺陷）+ `flushProgress`；KioskApp/GalaxyApp 接 Provider。
- P3 kiosk 五级导航 + `ProgressDots/ProblemCard(MiniBoard 缩略图)/SuccessOverlay` + Categories/Units/UnitList 页 + `:level/all` 保留平铺；sessionStorage 序列契约。
- P4 做题页 prev/next（导航前 flush）、做对 SuccessOverlay + 自动跳转(默认开~1.5s，设置可关)、上次用时、Vision 按 problemId 重置。
- P5 测试：tsumego **121 passed / 8 文件**（修 LevelPage、重写 ProblemPage、新增 Categories/Units/UnitList/components/Context、扩 nav 集成）。
- 对抗式自审（2×reviewer）修复：B2 队列去重加 user_id 过滤；B4 在线 get_progress 失败回退本地；F1 persist/flush 改读 latestRef（防 stale）；F4 kiosk sessionStorage key 加 `kiosk_` 前缀（与 galaxy 隔离）。

**闸门结果**
- `npm run build`(galaxy) ✓；`npm run build:kiosk-2d` ✓ + `verify:kiosk-2d` ✅ 无 three.js。
- `npx tsc -b` ✓。
- 前端 tsumego 121 passed；后端 tsumego 34 passed（repo+offline+board_auth）。

**已知/待办（不阻塞，交付回报）**
1. **本分支 pre-existing 测试债**：9 个 stale 测试文件（25 用例）在干净 HEAD 即失败，与本 track 无关（如 `theme.test` 期望 Noto Serif 但已改 Sans、`orientation*` 期望竖屏但外壳固定横屏、`AuthContext/GamePage/KioskLayout/StatusBar/ResearchPage/TeachingSettingsDialog`）。建议另开清理 track。
2. **后端 pre-existing**：`tests/test_user_game_repo.py` 2 条失败（sgf_hash 去重设计），与本 work 无关。
3. **B1 跨切面已知项**：远端 4xx（含 401/403）会静默回退本地+排队（与既有 `user_games_create` 同模式，已 logger.warning）。如需「鉴权失效时提示重登/暂停队列而非永久失败」，应作为同步管线的统一改进另开 track。
4. **真机验收**：RK 终端实际分辨率下的卡片栅格/缩略图性能、横屏布局（PRD §5 物理项）。
5. **离线端到端验收**：断网做对→本地可见→恢复→远端字段合并，目前由 dispatcher 级单测覆盖（`test_tsumego_offline.py`），**未跑活体两端 e2e**（需 board 模式服务 + 远端）。建议真机/联调环境跑一次。
6. **等级层进度**为弱汇总（仅总数，R2 性能权衡）；分类层完成数为惰性并行 best-effort。
7. Galaxy 现获服务器持久化（D9，UrI/流程不变）；其各页仍用自带 localStorage⊕server 读法（未强制迁到 Provider，避免回归）。
