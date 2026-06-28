# PRD：Kiosk 直播模块对齐网页端（Galaxy）

- **Track**: `sbc-live-parity`
- **目标分支**: `feature/sbc-live`（从 `develop` 创建；在 RK3562/RK3576/RK3588 上以 kiosk 模式 + board 模式运行）
- **Worktree**: `/Users/fan/Repositories/katrain-sbc-live`
- **作者**: fan
- **日期**: 2026-06-23
- **状态**: 草案 (Draft) — 核心决策已锁定（见 §0）
- **范围**: 仅直播（Live / 直播）模块

---

## 0. 已锁定决策（2026-06-23 确认）

| # | 决策点 | 结论 |
|---|---|---|
| D1 | API 基址判定 board 模式 | **编译期 `__KIOSK_2D_ONLY__` 切换**：kiosk 构建恒走 `/api/v1/board/live`，full 构建走 `/api/v1/live`。零运行时开销、不影响 Galaxy。（不引入运行时模式探测） |
| D2 | Galaxy 分析组件复用策略 | **提升到共享区**：7 个组件移入 `components/live/`，两端共用；同步改 Galaxy import 路径。（不在 kiosk 复制重写） |
| D3 | 本期功能范围 | **全量对齐 Galaxy**：棋盘预览 + 回放 + AI 推荐 + 趋势图 + 形势/手数/试下/AI 标记开关 + 即将开始 + 译名，全部复刻。评论除外（Galaxy 自身已停用）。 |
| D4 | 瘦客户端不变式 | **kiosk/board 直播 = 纯展示**：零设备端计算，且零由 kiosk 请求触发的服务器端计算/翻译 token。所有数据为服务器预计算、经只读代理获取；仅 GET，绝不触碰写/learn 路径。（已核实：`translator.py` 翻译为只读 DB 查表、绝不调 LLM；analysis 由服务器后台 worker 计算，端点为纯 DB 读。详见 §1.3） |
| D5 | 轮询 freshness gate | **先廉价探更新、再按需拉重型数据**：落在共享 hook（Galaxy + kiosk 同享、单一代码路径），保持 Galaxy 现有间隔（详情 5s / 列表 30s）。详情页 analysis 仅在「最新手 / 当前查看手未分析」时按需重拉（**position-aware 判据**，非裸计数；无 delta 触发器，理由见 §4.8），追平即稳态零重型刷新。详见 §4.8。 |

---

## 1. 背景与问题

KaTrain 从同一份前端代码产出两套 Web UI 构建（见 `CLAUDE.md` 的「SBC 构建边界契约」）：

| 构建产物 | 入口 | 面向 |
|---|---|---|
| `katrain/web/static/` | `npm run build` | 完整网页端（Galaxy UI） |
| `katrain/web/static-kiosk-2d/` | `npm run build:kiosk-2d` | SBC kiosk 终端（RK3562/RK3576/RK3588，**board 模式**） |

直播模块在两套 UI 下分别实现。**Galaxy 端功能完整**：列表页（棋盘预览 + 回放控制 + 「热门对局/即将开始」双 Tab + 历史对局列表）、单局详情页（棋盘 + AI 推荐落子 + 形势趋势图 + 形势判断/手数/试下/AI 标记 四个开关 + 回放控制条）。**Kiosk 端目前完全不可用**：进入「直播」页直接报错

```
Request failed 503: {"detail":"Live service unavailable in board mode — use /api/v1/board/live proxy"}
```

并且即使数据能取到，kiosk 现有页面也只是「极简列表 + 纯棋盘」，缺失 Galaxy 的全部分析能力。

### 1.1 根因分析

直播在 board 模式不可用，是**数据链路**和**前端能力**两层都缺：

**数据层（503 的直接原因）**
- 共享的 `api/live.ts` 把请求基址硬编码为 `const API_BASE = '/api/v1/live'`（`api/live.ts:16`）。
- board 模式下服务端**不启动** `live_service`（无本地数据库 / KataGo / 轮询采集），`/api/v1/live/*` 的依赖 `get_live_service()` 直接抛 503 并提示改用 `/api/v1/board/live` 代理（`api/v1/endpoints/live.py:118-134`）。
- 代理 `/api/v1/board/live/*` **存在但只覆盖 2 个端点**：`GET /live/matches`、`GET /live/matches/{id}`（`api/v1/endpoints/board.py:108-147`）。对应 `RemoteAPIClient` 也只有 `get_live_matches` / `get_live_match` 两个方法（`core/remote_client.py` 「Live (read-only)」段）。
- 因此 Galaxy 用到的 `analysis`、`analysis/preload`、`upcoming`、`featured`、`stats`、`translations` 等端点在 board 模式**完全没有代理通道**。

**前端层（即便有数据也不达标）**
- kiosk 的列表/详情页是 Galaxy 的「青春版」，无 AI 分析、无趋势图、无回放条、无即将开始、无形势/手数/试下/标记开关。
- Galaxy 这些能力封装在 `galaxy/components/live/` 下的组件里，而 kiosk **不允许** import `galaxy/**`（eslint 强制，见 `CLAUDE.md` 边界规则）。所以不能直接复用，必须先把组件「提升」到共享区或在 kiosk 重写。

### 1.2 现状代码索引

**Galaxy（参考实现，功能完整）**

| 路由 | 文件 | 职责 |
|---|---|---|
| `/galaxy/live` | `galaxy/pages/live/LivePage.tsx` | 左侧棋盘预览 + 回放条；右侧「热门对局 / 即将开始」双 Tab + 进入对局按钮 |
| `/galaxy/live/:matchId` | `galaxy/pages/live/LiveMatchPage.tsx` | 棋盘 + 四开关（试下/形势/手数/AI 标记）+ `MatchInfo` + `AiAnalysis` + `TrendChart` + `PlaybackBar` |

Galaxy 专属组件（`galaxy/components/live/`）：`MatchList.tsx`、`MatchCard.tsx`、`MatchInfo.tsx`、`AiAnalysis.tsx`、`TrendChart.tsx`、`PlaybackBar.tsx`、`UpcomingList.tsx`、`CommentSection.tsx`（**Galaxy 自己已停用，第 7 阶段延后**，见 `LiveMatchPage.tsx:18-19,239-244`）。
Galaxy 专属 hook（`galaxy/hooks/live/`）：`useComments.ts`（随评论一起延后）。

**Kiosk（当前实现，不可用）**

| 路由 | 文件 | 职责 |
|---|---|---|
| `/kiosk/live` | `kiosk/pages/LivePage.tsx` | 左侧「直播预览」**占位文字**（`LivePage.tsx:16-18`，无棋盘）+ 右侧极简对局列表 |
| `/kiosk/live/:matchId` | `kiosk/pages/LiveMatchPage.tsx` | 纯 `LiveBoard` + 少量文字信息，**无任何分析/回放控件** |

导航：`kiosk/components/layout/navTabs.tsx`（`直播` Tab → `/kiosk/live`）；路由：`kiosk/KioskApp.tsx`（`live` / `live/:matchId`）。

**共享逻辑（两端复用，位于共享区，改动需保持两套构建均绿）**

- `api/live.ts`：直播 API 客户端（**当前硬编码 `/api/v1/live`，是 503 的源头**）。
- `hooks/live/useLiveMatches.ts`、`hooks/live/useLiveMatch.ts`：列表 / 单局轮询状态。
- `components/live/LiveBoard.tsx`：**已是共享组件**，且已支持 `pvMoves` / `aiMarkers` / `showAiMarkers` / `showMoveNumbers` / `showTerritory` / `ownership` / `tryMoves` / `onTryMove` 全套 props（关键利好——棋盘层无需重写）。
- `types/live.ts`：直播类型定义。

**后端 API**

| 方法 | 路径 | 用途 | board 模式状态 |
|---|---|---|---|
| GET | `/api/v1/live/matches` | 对局列表 | 直连 503；代理 ✅ `board/live/matches` |
| GET | `/api/v1/live/matches/{id}` | 单局详情（含 moves/SGF） | 直连 503；代理 ✅ `board/live/matches/{id}` |
| GET | `/api/v1/live/matches/{id}/analysis` | 单局 KataGo 分析 | 直连 503；代理 ❌ **缺** |
| GET | `/api/v1/live/matches/{id}/analysis/preload` | 进入对局时预热分析 | 直连 503；代理 ❌ **缺** |
| GET | `/api/v1/live/matches/featured` | 焦点对局 | 直连 503；代理 ❌ **缺** |
| GET | `/api/v1/live/upcoming` | 即将开始对局 | 直连 503；代理 ❌ **缺** |
| GET | `/api/v1/live/stats` | 直播服务统计 | 直连 503；代理 ❌ **缺** |
| GET | `/api/v1/live/translations` | 棋手/赛事/规则译名批量表 | 直连 503；代理 ❌ **缺** |
| GET/POST/DELETE | `/api/v1/live/.../comments...` | 评论 | **本期不做**（Galaxy 自身已停用） |

### 1.3 成本模型与一致性保证（瘦客户端不变式的依据）

补充探索已验证：D4「kiosk 不做后端计算、不烧 token」在数据层其实**已经成立**，前提是 kiosk 只用只读 GET、不碰写/learn 路径：

- **翻译 = 只读 DB 查表，绝不调 LLM。** `katrain/web/live/translator.py` 顶部明确「LLM translation is handled by katrain-cron. This module is read-only for translations.」。kiosk 带 `lang=` 请求 `/matches`、`/translations`、`/upcoming` 只触发 DB 查表，**消耗 0 token**。唯一烧 token 的路径是 `POST /translations/learn`（鉴权写操作），kiosk 永不调用。
- **分析 = 服务器后台 worker 计算，与客户端请求无关。** `katrain/web/live/analyzer.py` 后台循环按优先级从 DB 取 pending 任务、请求 KataGo、结果落库；`/matches/{id}/analysis`、`/analysis/preload` 仅读已算好的行（`get_successful_analysis`）。kiosk 观看某局**不会**触发服务器跑 KataGo。
- **因此 kiosk 轮询唯一的真实成本** = board→server 链路上**重复传输几乎不变的重型 analysis 负载**（每已分析手含 19×19 ownership + top_moves/pv，整局数百 KB～MB）。board 代理目前 1:1 直通、无缓存（`board.py` / `remote_client.py`）。→ 这正是 §4.8 freshness gate 要消除的浪费。

**freshness 信号语义（已核实，决定 gate 设计）**：`move_count` 可靠（`poller.py` 每出新手 bump）；但「已有手分析落库」不会可靠 bump 缓存摘要的 `last_updated`（analyzer 写 DB 不写缓存对象）；`last_list_update` 每轮询周期都 bump（`cache.py update_matches`），**非**内容变更信号。故 gate 用「分析覆盖落后于手数」判据，且只加在详情页、列表页保持 30s 全量刷新。

---

## 2. 目标与非目标

### 2.1 目标（本期交付）

1. **修复 503**：让 kiosk 直播页在 board 模式下能正常拉到对局列表与详情。
2. **后端代理补全**：把 Galaxy 直播用到的全部**只读**端点纳入 `/api/v1/board/live/*` 代理（analysis、analysis/preload、featured、upcoming、stats、translations）。
3. **前端数据层自适应**：`api/live.ts` 在 board / kiosk 模式自动改走 `/api/v1/board/live`，其余模式不变。
4. **kiosk 直播功能对齐 Galaxy**：列表页与详情页达到 Galaxy 的能力对等——棋盘预览、回放控制、AI 推荐落子、形势趋势图、形势判断/手数/试下/AI 标记开关、即将开始列表、焦点/历史对局列表。
5. **触屏适配**：把 Galaxy 的鼠标交互（hover 预览 PV、tooltip）改为触屏可用的点击交互。
6. **构建边界保持**：kiosk 构建仍不含 three.js；两套构建（`build` + `build:kiosk-2d` + `verify:kiosk-2d`）均绿。
7. **轮询效率（瘦客户端）**：kiosk 直播零设备端计算、零 kiosk 触发的服务器计算/翻译 token；详情页 analysis 仅在服务器端有新分析（position-aware 判据，见 §4.8）时重拉，稳态零重型刷新，结果与服务器端完全一致。

### 2.2 非目标（本期不做）

- **评论系统**：Galaxy 自身已停用（Phase 7 延后），kiosk 对齐其「停用」状态，本期不做。`CommentSection` / `useComments` 不提升、不接入。
- **直播采集 / 分析的产生**：board 设备不跑 `live_service`、不接外部直播源、不跑 KataGo 分析；所有数据来自上游服务器（经代理）。本期不改采集侧（katrain-cron / `live/` 服务）。
- **写操作**：board 模式直播是纯只读；不做 `refresh`、不做评论发表/删除、不做译名学习（`translations/learn`）。
- **Galaxy 端体验改动**：除组件提升带来的 import 路径变更外，不改 Galaxy 直播的行为与外观。
- **离线缓存直播数据**：直播是实时数据，断网即不可用；不做本地 SQLite 缓存 / 同步队列（与 tsumego/kifu 的离线进度不同，直播无此需求）。
- **服务器端改动**：不在服务器端新增 freshness 信号/端点、不动采集与分析侧；gate 完全基于现有响应字段（`move_count` / `analyzed_moves`）。
- **列表页 gate / 增量逐手 analysis**：本轮列表页保持 30s 全量刷新（摘要本就轻、`last_list_update` 不可作变更信号）；不做增量逐手 analysis 拉取。

---

## 3. 功能差异清单（Difflist）

| # | 能力 | Galaxy | Kiosk 现状 | 本期目标 |
|---|---|---|---|---|
| F1 | 对局列表（直播中 + 已结束） | ✅ `MatchList`，紧凑卡片、选中态 | ⚠️ 极简自绘列表 | ✅ 复用提升后的 `MatchList`/`MatchCard` |
| F2 | 即将开始（Upcoming）Tab | ✅ `UpcomingList`，倒计时 + 来源链接 | ❌ 无 | ✅ 复用提升后的 `UpcomingList` |
| F3 | 列表页棋盘预览 + 回放条 | ✅ 选中对局即在左侧预览 | ❌ 占位文字 | ✅ 复用 `LiveBoard` + `PlaybackBar` |
| F4 | 单局棋盘渲染 | ✅ 共享 `LiveBoard` | ✅ 已有 | ✅ 保持（启用更多 props） |
| F5 | 回放控制条（首/上/播放/下/末 + 跟随最新） | ✅ `PlaybackBar` | ❌ 无 | ✅ 复用提升后的 `PlaybackBar` |
| F6 | AI 推荐落子面板（前 3 手：访问数/胜率/目差/PV） | ✅ `AiAnalysis` | ❌ 无 | ✅ 复用提升后的 `AiAnalysis` |
| F7 | 形势趋势图（胜率 + 目差双轴，点击跳手） | ✅ `TrendChart` | ❌ 无 | ✅ 复用提升后的 `TrendChart` |
| F8 | 对局信息头（棋手/段位/赛事/状态/胜率条/规则贴目） | ✅ `MatchInfo` | ⚠️ 少量文字 | ✅ 复用提升后的 `MatchInfo` |
| F9 | 棋盘开关：AI 标记 | ✅ 默认开 | ❌ 无 | ✅ |
| F10 | 棋盘开关：形势判断（ownership 覆盖） | ✅ | ❌ 无 | ✅ |
| F11 | 棋盘开关：手数显示 | ✅ | ❌ 无 | ✅ |
| F12 | 棋盘开关：试下模式 | ✅ | ❌ 无 | ✅（触屏点击落子） |
| F13 | PV 变化预览（鼠标 hover） | ✅ hover | ❌ 无 | ✅ **改为点击/长按预览**（触屏适配） |
| F14 | 棋手/赛事/规则译名本地化 | ✅ `lang` 参数 + `i18n.translatePlayer` | ⚠️ 列表代理已透传 `lang`；详情/译名表无 | ✅ 代理补全后全链路本地化 |
| F15 | 焦点对局（featured） | ✅ | ❌ 无 | ✅ 代理补全（列表页可选用于默认选中） |
| F16 | 评论 | ⛔ 已停用 | ❌ 无 | ⛔ 对齐「停用」，不做 |
| F17 | 轮询 freshness gate（详情页 analysis 按需拉取） | ⚠️ 朴素全量轮询 | ⚠️ 朴素全量轮询（复用同一 hook） | ✅ 共享 hook 加 gate，两端受益（见 §4.8） |

---

## 4. 详细需求

### 4.1 后端：补全 board 模式 live 代理

在 `api/v1/endpoints/board.py` 的「Live Match Proxy」段，新增以下只读代理端点，签名与 Galaxy 直连端点一致，内部经 `RemoteAPIClient` 转发到上游服务器。**错误语义**（评审修正）：用统一 `_proxy` 包装——上游 **4xx 原样透传**（如 404 match/move 不存在），仅连接/超时映射 502；现有 `proxy_live_matches`/`proxy_live_match` **也迁到** `_proxy`。详见 `plan.md` P1.2：

| 新增代理 | 转发到上游 |
|---|---|
| `GET /api/v1/board/live/matches/featured` | `/api/v1/live/matches/featured` |
| `GET /api/v1/board/live/matches/{id}/analysis` | `/api/v1/live/matches/{id}/analysis`（透传 `move_number`） |
| `GET /api/v1/board/live/matches/{id}/analysis/preload` | `/api/v1/live/matches/{id}/analysis/preload` |
| `GET /api/v1/board/live/upcoming` | `/api/v1/live/upcoming`（透传 `limit`、`lang`） |
| `GET /api/v1/board/live/stats` | `/api/v1/live/stats` |
| `GET /api/v1/board/live/translations` | `/api/v1/live/translations`（透传 `lang`） |
| （`matches`、`matches/{id}` 已存在，均不改；`matches/{id}` **无需** `fetch_detail`——上游恒返回 moves，见下注） |

对应在 `core/remote_client.py`「Live (read-only)」段补齐方法：`get_live_featured`、`get_live_match_analysis`、`preload_live_analysis`、`get_live_upcoming`、`get_live_stats`、`get_live_translations`。沿用现有 `_request` + `raise_for_status` 写法，并过滤 `None` 参数。

> 注（已核实，删 `fetch_detail`）：上游 `get_match`（`live.py:264-297`）**无** `fetch_detail` 参数、**无条件**返回含 `moves`+`sgf` 的 `MatchDetail`（后端全局 `grep fetch_detail` 零命中）。前端 `getMatch(id, fetchDetail)` 带的参数一直是 no-op ⇒ 代理与 `remote_client` **不加** `fetch_detail`，详情页恒得 `moves`。

### 4.2 前端：`api/live.ts` board 模式自适应基址

把 `API_BASE` 从常量改为运行时解析：在 board / kiosk 模式下用 `/api/v1/board/live`，否则 `/api/v1/live`。

判定方式（择一，见 §7 开放问题 Q1）：
- **首选**：编译期 kiosk 标志 `__KIOSK_2D_ONLY__`（已存在于 `vite-env.d.ts` / `vite.config.ts`）——kiosk 构建恒为 board 模式，直接 `const API_BASE = __KIOSK_2D_ONLY__ ? '/api/v1/board/live' : '/api/v1/live'`。零运行时开销，且不影响 Galaxy 构建。
- 备选：运行时探测服务端模式（如读取 `/api/v1/health` 或新增 `/api/v1/mode`）后切换基址，适用于「同一份 full 构建也可能跑在 board 设备」的情况。

> 评论相关方法（`createComment` 等）本期不接入；若保留代码，board 基址下它们指向不存在的代理即可（不会被调用）。

### 4.3 前端：把 Galaxy 直播组件提升到共享区

已确认下列组件**仅依赖共享区**（`types/live`、`i18n`、`hooks/useTranslation`、`api/live`；`MatchList`→`MatchCard` 互依），提升是干净的：

把 `galaxy/components/live/` 下 `MatchList`、`MatchCard`、`MatchInfo`、`AiAnalysis`、`TrendChart`、`PlaybackBar`、`UpcomingList` **移动到 `components/live/`**（与已在那里的 `LiveBoard.tsx` 同目录）。

- 移动后调整组件内对共享区的相对路径（`../../../` → `../../`）。
- 更新**全部**消费者 import 路径（`../../components/live/X` → `../../../components/live/X`）：`galaxy/pages/live/{LivePage,LiveMatchPage}.tsx` **以及** `galaxy/pages/report/{ReportDetailPage,ReportsPage}.tsx`（消费 `AiAnalysis`/`PlaybackBar`/`TrendChart`），并同步其 `*.test.tsx` 的 `vi.mock` 路径（失配静默失效）。另：`MatchCard.tsx` 硬编码 `/galaxy/live/${id}` 需参数化（kiosk 无此路由）。详见 `plan.md` P3。
- `CommentSection.tsx` / `galaxy/hooks/live/useComments.ts` **不提升**（本期不做评论）。
- eslint 边界：提升后 kiosk 从 `components/live/` 引用，不再触碰 `galaxy/**`，符合边界契约。

### 4.4 前端：kiosk 直播列表页（`kiosk/pages/LivePage.tsx`）

对齐 Galaxy `LivePage` 的信息架构，但以 kiosk 触屏布局落地：

- 左侧：选中对局的 `LiveBoard` 预览 + `PlaybackBar`（替换现有占位文字）。默认选中第一个直播中对局（可用 `featured` 优化，见 F15）。
- 右侧：`热门对局 / 即将开始` 双 Tab；热门对局下分「直播中（含计数）」与「历史」两组 `MatchList`（紧凑模式、选中态）；即将开始用 `UpcomingList`。
- 底部/侧边：「进入对局 / 观看复盘」按钮 → `navigate('/kiosk/live/:id')`。
- 复用共享 hook `useLiveMatches` / `useLiveMatch`（无需改 hook 逻辑）。
- 触屏尺寸：按钮、Tab、列表行的可点击区域适配触摸（≥44px），参考 kiosk 既有页面风格。

### 4.5 前端：kiosk 单局详情页（`kiosk/pages/LiveMatchPage.tsx`）

对齐 Galaxy `LiveMatchPage`：

- 左侧棋盘：`LiveBoard` 启用 `pvMoves` / `aiMarkers` / `showAiMarkers` / `showMoveNumbers` / `showTerritory` / `ownership` / `tryMoves` / `onTryMove`。
- 右侧栏：`MatchInfo` + 四开关（试下/形势/手数/AI 标记，`ToggleButtonGroup`）+ `AiAnalysis` + `TrendChart` + `PlaybackBar`。
- `aiMarkers` / `ownership` 由 `analysis[currentMove]` 计算（逻辑同 Galaxy `LiveMatchPage.tsx:62-81`）。
- 落子音效保留（`useSound('stone')`）。
- 朝向：沿用 kiosk 既有 `useOrientation`，竖屏时棋盘在上、信息/分析在下（详情见 §7 Q3）。

### 4.6 触屏交互适配

- **PV 预览**：Galaxy 的 `AiAnalysis` 仅经 `onMouseEnter/Leave` 发 `onMoveHover`、**无 click 事件**（已核实），页面层无法不改组件做 tap。改为给共享 `AiAnalysis` **新增 opt-in `onMoveSelect?(pv)` prop**（`MoveRow` onClick 调用）：Galaxy 不传 → hover 行为字节不变；kiosk 传它 → 点推荐手预览、再点/点空白清空。
- **试下模式**：触屏直接点棋盘交叉点落子（`onTryMove` 已支持），提供「清空」按钮。
- **Tooltip**：Galaxy 用 `Tooltip`（hover 显示），kiosk 上以图标 + 文字标签常驻替代，避免依赖 hover。

### 4.7 i18n

- 复用 Galaxy 直播已有的 `live:*` 文案 key（`PlaybackBar`/`MatchInfo`/`AiAnalysis` 等内部已用 `useTranslation` + `live:` 命名空间）。
- kiosk 页面新增文案沿用 `t('English', '中文')` 双参或 `live:` key（与 kiosk 现有页面一致）。
- 棋手/赛事/规则译名走 §4.1 补全后的 `translations` 代理 + `i18n.translatePlayer`。

### 4.8 轮询与 freshness gate（D5）

**目标**：消除 §1.3 指出的唯一浪费——稳态下重复传输不变的重型 analysis。改在**共享 hook** `hooks/live/useLiveMatch.ts`，Galaxy + kiosk 同享，保持现有间隔（详情 5s / 列表 30s）。

**详情页 gate 判据**（仅 `status==='live'` 时轮询，沿用「非 live 停止」）。analysis 按 position `0..move_count` **闭区间** keying（空盘 move 0 也分析）且只含 `SUCCESS` 行（稀疏、有 FAILED 洞），故**不能**用裸计数 `length < move_count`（off-by-one + 漏洞）。每个 5s 周期 `fetchMatch()` 照旧（详情/手数/源胜率恒新鲜），并满足**任一**即重拉 `fetchAnalysis(false)`：

- **tip 未分析**：`analysis[move_count] == null`（最新 position）。
- **当前查看手未分析**：`analysis[currentMove] == null`（覆盖翻看历史/回填到位；`currentMove` 用恒为 number 的 effective 值）。
- **no-progress 兜底**：落后但 key 数连续 N≈6 周期不增长 → 暂停，直到 `move_count` **或** `currentMove` 变化（防永久 FAILED 无限重拉）。

> **不用 delta 触发器**（评审修正）：`current_winrate/current_score` 是**直播源**字段（`models.py:79-80`「from XingZhen」），KataGo 分析写 `katago_winrate/katago_score`（`analysis_repo.py:97`，不在 live API 响应里）——delta 检测不到分析更新。且「就地重分析」只在新手时发生（`analyzer.py:193` 同时入队 `move_number-1`；`SUCCESS` 不被独立重算），已被 tip 判据覆盖 → 无需 delta、无 Galaxy 回归。

进入页面初次 `preload`（`fetchAnalysis(true)`）不变；实现用单一 ref 镜像渲染态避免闭包陈旧/interval churn；live→finished 过渡补一次 catch-up。详细实现与 TDD 见 `plan.md` 任务 2.2/2.3。

**列表页**：`hooks/live/useLiveMatches.ts` 不改（30s 全量刷新；`last_list_update` 每周期都 bump，非内容变更信号，不可 gate）。

**为什么可靠**：新手 bump `move_count` → tip 键缺失 → 重拉直到 tip 到位（含重算的 `move_count-1`，≤1–2 周期内 AI 推荐/趋势刷新）；无新手且 tip/查看手均已分析 → 零重型请求。

> 注：上游 `get_match` 无 `fetch_detail`，`getMatch` 恒全量（含 moves+sgf）——无「轻量 match 拉取」，故每 tick 接受 moves+sgf（相对 analysis 仍轻）；原「`fetchDetail=false` 优化」作废。

---

## 5. 验收标准

1. **503 消除**：RK3562 kiosk 进入「直播」，正常显示对局列表，无 503/502（上游有数据时）。
2. **代理覆盖**：board 模式下 `GET /api/v1/board/live/{matches,matches/{id},matches/{id}/analysis,matches/{id}/analysis/preload,matches/featured,upcoming,stats,translations}` 全部可用，数据与上游 Galaxy 直连一致。
3. **功能对等**：kiosk 详情页可见 AI 推荐落子、形势趋势图、形势/手数/试下/AI 标记开关、回放控制，且行为与 Galaxy 一致；列表页可见热门/即将开始双 Tab + 棋盘预览。
4. **触屏可用**：PV 预览、试下、开关切换全部可纯触摸完成，无需鼠标 hover。
5. **本地化**：在中文 UI 下，棋手/赛事/规则名按译名表显示。
6. **构建绿**：`npm run build`、`npm run build:kiosk-2d`、`npm run verify:kiosk-2d` 全部通过；kiosk dist 不含 `three`/`@react-three`。
7. **Galaxy 无回归**：Galaxy 直播页面行为/外观不变（仅 import 路径变更）。
8. **断网降级**：上游不可达时，kiosk 显示明确错误态（502 友好提示），不白屏、不崩溃。
9. **轮询效率**：详情页稳态（无新手且 analysis 已追平）不再发 `/analysis` 请求；服务器端出新手并分析落库后，≤1 个轮询周期（~5s）内 AI 推荐/趋势/胜率刷新；较改动前显著减少重复 analysis 传输。
10. **瘦客户端**：board 设备无 KataGo / 无 live_service / 不烧翻译 token；kiosk 直播全部数据来自上游、经只读代理，渲染结果与服务器端一致。

---

## 6. 影响与风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| R1 共享区改动波及 Galaxy | 组件提升 + `api/live.ts` + `useLiveMatch` gate 属共享区，影响两套构建 | 提升移动文件 + 改相对路径；`MatchCard` 路由参数化；`api/live.ts` 用 `__KIOSK_2D_ONLY__` 分支隔离；两套构建均跑 + Galaxy 人工回归 |
| R2 import 路径遗漏 | 移动 7 组件 + **所有**消费者（live 2 页 + report 2 页 + 各自 `vi.mock`），易漏改路径 | 逐文件 grep `components/live/`；`vi.mock` 失配静默→需显式核对；TS 编译 + eslint 兜底 |
| R3 代理透传不全 | `move_number`/`lang`/`limit` 漏传致数据缺失（`fetch_detail` 已确认为上游 no-op，删） | §4.1 列出每端点透传参数；逐端点对比 Galaxy 直连响应 |
| R4 上游 schema 漂移 | 代理透传，上游字段变更会直达 kiosk | 代理层不做转换，类型由共享 `types/live.ts` 统一 |
| R5 三维依赖误入 kiosk | 直播无 three.js 依赖，但提升组件时若误带入会破坏 kiosk 构建 | 已确认 7 组件零 three.js 依赖；`verify:kiosk-2d` 兜底 |
| R6 触屏改造引入 Galaxy 回归 | `AiAnalysis` 无 click 事件，tap 预览须加 opt-in `onMoveSelect`（共享组件改动） | 加法式 opt-in：Galaxy 不传该 prop、hover 路径字节不变；Galaxy 直播页跑回归确认 |
| R7 board 设备未配置上游 | 设备无 `REMOTE_API_URL` / 上游未跑 live_service | 部署前确认；502 友好降级 |
| R8 分析落库探测可靠性 | analysis 按 position 0..move_count 闭区间 keying、含 FAILED 洞；`current_*` 是源字段非 KataGo | position-aware 判据（tip/查看手键存在性）+ no-progress 兜底（reset on key/move/viewed 变化）；就地重分析随新手被覆盖 |
| R9 共享 hook 改动波及 Galaxy | `useLiveMatch` gate 属共享区 | 纯增量改 + `useLiveMatch` hook 单测（落后→拉取 / 追平→停 / 新手→恢复 / 非 live→停）；Galaxy 仅获透明优化 |

**回滚**：本 track 在独立分支 `feature/sbc-live`，按阶段提交；如需回滚整体 `git revert` 合并提交即可。组件提升若出问题，可临时让 kiosk 复制一份组件到 `kiosk/` 而不动 Galaxy。

---

## 7. 开放问题

> Q1 / Q2 / Q4 已在 §0 锁定。以下为待确认项：

- **Q3（详情页竖屏布局）**：kiosk 多为竖屏，右侧 500px 侧栏在 Galaxy 是横屏布局。竖屏下 `AiAnalysis`+`TrendChart`+`PlaybackBar` 如何堆叠？是否需要可折叠/Tab 化分析面板？**建议进 P5 前先出 mockup 确认。**
- **Q5（试下落子规则）**：试下模式在 board 模式是纯前端落子（不提子校验？是否复用 `LiveBoard` 现有 try 逻辑）？确认 `onTryMove` 当前行为是否满足。
- **Q6（焦点对局）**：列表页默认选中是否用 `featured`，还是沿用 Galaxy 的「首个直播中」逻辑即可？

---

## 8. 建议阶段划分

| 阶段 | 内容 | 验收 |
|---|---|---|
| **P0 基线** | 在 worktree 跑通两套构建 + kiosk 复现 503 | 两套构建绿；503 可复现 |
| **P1 后端代理** | `board.py` 补 6 只读代理（`featured` 排在 `{match_id}` 前、4xx 透传）+ `remote_client.py` 补方法 | curl 各端点与上游一致；缺失 match 返 404 非 502 |
| **P2 前端数据层** | `api/live.ts` 基址自适应（D1）+ `useLiveMatch` 加 freshness gate（D5/§4.8）+ hook 单测；kiosk 列表/详情拉到真实数据 | kiosk 不再 503；稳态无重型 analysis 重拉；hook 测试绿 |
| **P3 组件提升** | 7 个 Galaxy 直播组件移入 `components/live/` + 修正所有 import + Galaxy 回归 | 两套构建绿；Galaxy 直播无变化 |
| **P4 kiosk 列表页** | `kiosk/LivePage` 对齐（棋盘预览 + 回放 + 双 Tab + 进入按钮） | F1/F2/F3/F15 达标 |
| **P5 kiosk 详情页** | `kiosk/LiveMatchPage` 对齐（四开关 + AiAnalysis + TrendChart + PlaybackBar）+ 触屏适配 | F4–F14 达标 |
| **P6 收尾** | i18n 补全、竖屏布局打磨、断网降级、两套构建 + verify + 回归 | §5 全部验收项通过 |

---

## 附：关键文件清单

**后端**
- `katrain/web/api/v1/endpoints/board.py`（补代理）
- `katrain/web/core/remote_client.py`（补方法）
- `katrain/web/api/v1/endpoints/live.py:118-134`（503 来源，不改）

**前端（共享区，改动影响两套构建）**
- `katrain/web/ui/src/api/live.ts`（基址自适应）
- `katrain/web/ui/src/components/live/`（接收提升的 7 个组件 + 已有 `LiveBoard.tsx`）
- `katrain/web/ui/src/hooks/live/useLiveMatch.ts`（加 freshness gate，见 §4.8）、`useLiveMatches.ts`（复用，不改）
- `katrain/web/ui/src/types/live.ts`（复用）

**前端（Galaxy，import 路径变更）**
- `katrain/web/ui/src/galaxy/pages/live/{LivePage,LiveMatchPage}.tsx`
- `katrain/web/ui/src/galaxy/components/live/*`（移出至共享区）

**前端（kiosk，重写对齐）**
- `katrain/web/ui/src/kiosk/pages/{LivePage,LiveMatchPage}.tsx`
- `katrain/web/ui/src/kiosk/__tests__/{LivePage,LiveMatchPage}.test.tsx`（同步更新）
