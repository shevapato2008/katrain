# 开发计划：Kiosk 直播对齐 Galaxy + 瘦客户端/轮询 freshness gate

- **Track**: `sbc-live-parity`
- **分支**: `feature/sbc-live`（从 `develop` 创建）
- **Worktree**: `/Users/fan/Repositories/katrain-sbc-live`
- **配套 PRD**: [`prd.md`](./prd.md)（功能规格、决策 D1–D5、验收标准的权威来源；本计划是其执行细化）
- **状态**: 待执行

> 本计划面向**无上下文的执行者**：每个阶段都给出要改的文件、改法（含代码骨架）、验收与提交点。功能细节以 PRD 为准；本文件只补「怎么做」。

---

## 0. 总目标与不变式

让 kiosk（board 模式）直播功能对齐 Galaxy，同时贯彻**瘦客户端不变式（PRD D4）**：

- kiosk 只读取服务器预计算的数据并展示，**零设备端计算、零 kiosk 触发的服务器计算/翻译 token**（依据见 PRD §1.3）。
- 仅用 GET 只读端点，经 `/api/v1/board/live/*` 代理转发到上游服务器；绝不调用写/learn 路径。
- 轮询用 **freshness gate（PRD D5/§4.8）**：详情页 analysis 仅在「tip / 当前查看手未分析」时按需重拉（**position-aware 判据**，非裸计数；无 delta 触发器），稳态零重型刷新。

**两套构建边界（CLAUDE.md「SBC 构建边界契约」）**：改动共享区（`api/`、`hooks/`、`components/`、`types/`）会同时影响 `npm run build`（full/Galaxy）与 `npm run build:kiosk-2d`（kiosk）。每个触及共享区的阶段都要跑**两套构建 + `verify:kiosk-2d`**。

---

## 1. 阶段总览与依赖

```
P0 基线 ──► P1 后端代理 ──► P2 前端数据层(基址+gate) ──┬─► P4 kiosk 列表页 ──┐
                                  └─► P3 组件提升 ──────┴─► P5 kiosk 详情页 ─┴─► P6 收尾
```

- **P1** 自包含、最先做，解 503 并打通数据链路。
- **P2** 依赖 P1（代理就位才能拉到数据）；含基址自适应 + freshness gate。
- **P3** 与 P1/P2 正交，可并行；但 P4/P5 依赖 P3（提升后的组件）。
- 每阶段一个 commit；分支独立，整体回滚用 `git revert` 合并提交。

执行建议：用 TaskCreate 把 P1–P6 建为任务，逐个 in_progress→completed。

---

## P0 — 基线（复现现状）

**目标**：确认起点干净、503 可复现。

1. 确认在 `feature/sbc-live` 分支：`git branch --show-current`。
2. 装依赖并跑两套构建：
   ```bash
   cd katrain/web/ui && npm install
   npm run build && npm run build:kiosk-2d && npm run verify:kiosk-2d
   ```
3. （可选）board 模式起服务，复现 503：
   ```bash
   KATRAIN_MODE=board KATRAIN_REMOTE_URL=<server-url> python -m katrain --ui web
   # 浏览器进 /kiosk/live → 预期 503: "Live service unavailable in board mode"
   ```

**验收**：两套构建 + verify 全绿；503 可复现（或确认代理缺口）。无需 commit。

---

## P1 — 后端只读代理补全

**目标**：把 Galaxy 直播用到的全部只读端点纳入 `/api/v1/board/live/*` 代理。

**文件**：
- `katrain/web/api/v1/endpoints/board.py`（「Live Match Proxy」段，现有 `proxy_live_matches` / `proxy_live_match` 之后追加）
- `katrain/web/core/remote_client.py`（「Live (read-only)」段，现有 `get_live_matches` / `get_live_match` 之后追加）

### 任务 1.1：`remote_client.py` 补方法

沿用现有 `_request` + `raise_for_status` + None 过滤写法。新增/改动：

> **已核实（删 `fetch_detail`）**：上游 `get_match`（`live.py:264-297`）**无** `fetch_detail` 参数、**无条件**返回含 `moves`+`sgf` 的 `MatchDetail`（`grep fetch_detail` 全后端零命中）。前端 `getMatch(id, fetchDetail)` 带的 `?fetch_detail` 一直是 no-op。⇒ 现有 `get_live_match(match_id)` **保持两参不变、不加 `fetch_detail`**；P2 也不再依赖它（详情拉取恒为全量）。

```python
# ── Live (read-only) ── 追加（get_live_matches / get_live_match 已存在，均不改）
async def get_live_featured(self, lang: Optional[str] = None) -> Dict:
    params = {k: v for k, v in {"lang": lang}.items() if v is not None}
    resp = await self._request("GET", "/api/v1/live/matches/featured", params=params)
    resp.raise_for_status(); return resp.json()

async def get_live_match_analysis(self, match_id: str, move_number: Optional[int] = None) -> Dict:
    params = {k: v for k, v in {"move_number": move_number}.items() if v is not None}
    resp = await self._request("GET", f"/api/v1/live/matches/{match_id}/analysis", params=params)
    resp.raise_for_status(); return resp.json()

async def preload_live_analysis(self, match_id: str) -> Dict:
    resp = await self._request("GET", f"/api/v1/live/matches/{match_id}/analysis/preload")
    resp.raise_for_status(); return resp.json()

async def get_live_upcoming(self, limit: int = 20, lang: Optional[str] = None) -> Dict:
    params = {k: v for k, v in {"limit": limit, "lang": lang}.items() if v is not None}
    resp = await self._request("GET", "/api/v1/live/upcoming", params=params)
    resp.raise_for_status(); return resp.json()

async def get_live_stats(self) -> Dict:
    resp = await self._request("GET", "/api/v1/live/stats")
    resp.raise_for_status(); return resp.json()

async def get_live_translations(self, lang: str) -> Dict:
    resp = await self._request("GET", "/api/v1/live/translations", params={"lang": lang})
    resp.raise_for_status(); return resp.json()
```

### 任务 1.2：`board.py` 补代理端点

**两条硬性修正**（来自计划评审）：

1. **路由顺序**：`/live/matches/featured` 必须**物理声明在现有 `/live/matches/{match_id}`（board.py:138）之上**，否则 FastAPI 按声明顺序把 `featured` 当成 `match_id='featured'` 转发，命中上游 404 → 误报。`{match_id}/analysis`、`{match_id}/analysis/preload` 是更具体路径，不与 `{match_id}` 冲突，位置不限。**做法**：把 `proxy_live_featured` 插到现有 `proxy_live_match` 定义**之前**；其余 append 即可。
2. **状态保真**：不再一刀切 502。上游 4xx（如 404 match/move 不存在）**原样透传**，只把连接/超时映射 502/503，否则 §5.8 断网降级无法区分「这局不存在」与「上游宕机」。用一个 `_proxy` 包装统一处理：

```python
import httpx

async def _proxy(call, what: str):
    """转发上游只读调用：4xx 原样透传，连接/超时→502。"""
    try:
        return await call()
    except httpx.HTTPStatusError as e:          # 上游返回了 4xx/5xx
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:                        # 连接/超时/DNS 等
        logger.warning(f"{what} proxy failed: {e}")
        raise HTTPException(status_code=502, detail="Remote server unavailable")

# ↓↓↓ 插在现有 proxy_live_match（{match_id}）之前
@router.get("/live/matches/featured")
async def proxy_live_featured(request: Request, lang: Optional[str] = Query(None)):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_live_featured(lang=lang), "Live featured")

# ↓↓↓ 其余 append 到 Live Match Proxy 段尾即可
@router.get("/live/matches/{match_id}/analysis")
async def proxy_live_analysis(request: Request, match_id: str, move_number: Optional[int] = Query(None)):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_live_match_analysis(match_id, move_number=move_number), "Live analysis")

@router.get("/live/matches/{match_id}/analysis/preload")
async def proxy_live_preload(request: Request, match_id: str):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.preload_live_analysis(match_id), "Live preload")

@router.get("/live/upcoming")
async def proxy_live_upcoming(request: Request, limit: int = Query(20, ge=1, le=100), lang: Optional[str] = Query(None)):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_live_upcoming(limit=limit, lang=lang), "Live upcoming")

@router.get("/live/stats")
async def proxy_live_stats(request: Request):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_live_stats(), "Live stats")

@router.get("/live/translations")
async def proxy_live_translations(request: Request, lang: str = Query("en")):  # 默认 'en' 对齐上游
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_live_translations(lang), "Live translations")
```

> **必须**把现有 `proxy_live_matches` / `proxy_live_match` 也迁到 `_proxy`（Codex #2：否则 `proxy_live_match` 仍 `except → 502`，下方「缺失 match 返 404」验收**不可能通过**，断网/不存在语义仍混）。`get_live_match` 仍两参（无 `fetch_detail`）。

⚠️ **只读**：不代理 `refresh`、`comments`、`translations/learn`（PRD 非目标）。`/translations` 的 `lang` 默认 `"en"` 对齐上游（`live.py:449`），不声明为必填。

**验收（P1）**：
- `uv run pytest tests`（若有 board 代理测试）通过；至少不破坏现有。
- board 模式 `curl` 8 个端点，与上游 Galaxy 直连响应一致：
  ```bash
  for p in "matches" "matches/featured" "upcoming?limit=5" "stats" "translations?lang=zh"; do
    curl -s "http://localhost:<port>/api/v1/board/live/$p" | head -c 300; echo; done
  # 取一个真实 match_id（详情恒含 moves，无需 fetch_detail）：
  curl -s ".../board/live/matches/<id>" | python -m json.tool | grep -c moves          # 应 >0
  curl -s ".../board/live/matches/<id>/analysis" | python -m json.tool | grep analyzed_moves
  curl -s -o /dev/null -w '%{http_code}' ".../board/live/matches/__nope__"             # 应 404，不是 502
  ```
- **新增后端测试**：`proxy_live_featured` 在 `{match_id}` 之前命中（不返 404）；缺失 match 透传 404；上游不可达映射 502。
- **commit**: `feat(sbc-live): complete board-mode live proxy (featured/analysis/upcoming/stats/translations, status-faithful)`

---

## P2 — 前端数据层：基址自适应 + freshness gate

**共享区改动 → 影响两套构建。** 文件：
- `katrain/web/ui/src/api/live.ts`
- `katrain/web/ui/src/hooks/live/useLiveMatch.ts`
- 新增 `katrain/web/ui/src/hooks/live/useLiveMatch.test.ts`（TDD）

### 任务 2.1：基址自适应（D1）

`api/live.ts` 第 16 行：
```ts
// 旧: const API_BASE = '/api/v1/live';
const API_BASE = __KIOSK_2D_ONLY__ ? '/api/v1/board/live' : '/api/v1/live';
```
`__KIOSK_2D_ONLY__` 已在 `vite-env.d.ts` 声明、`vite.config.ts` 经 `define` 注入；编译期常量，full 构建为 `false`，Galaxy 不受影响。评论方法保留不删（本期不调用）。

### 任务 2.2：freshness gate（D5/§4.8）— TDD

> **评审修正（Codex/Gemini）**：原 `analyzedCount < move_count`（裸计数）有 off-by-one（analysis 按 position `0..move_count` 闭区间 keying，`analysis_repo.py:281`/`analyzer.py:378`）+ 稀疏洞（`get_successful_analysis` 只含 `SUCCESS` 行）两类 bug。**并删掉原「`(current_winrate,current_score)` delta 触发器」**——已核实 `current_winrate/current_score` 是**直播源**字段（`models.py:79-80` 注释「from XingZhen」，`poller.py:313-314` 写入），KataGo 分析写的是 `katago_winrate/katago_score`（`analysis_repo.py:97`）且**不在 live API 响应/前端类型里**——该 delta 检测不到分析更新，是错误信号。改用纯 **position-aware 判据 + no-progress 兜底**。
>
> **为何不需要 delta 触发器**：「就地重分析」只在新手到来时发生——`analyzer.py:193` 在新手时同时入队 `move_number` 与 `move_number-1`（重算上一手）；`get_unanalyzed_moves` 只取 `PENDING`（`:286`），**`SUCCESS` 的 position 不会被独立重算**。而新手必 bump `move_count` → tip 键缺失 → 本判据已触发重拉（拿到含重算后 `move_number-1` 的全量 map）。故无独立「同手改值」场景，无 Galaxy 回归。

**判据**——每个 live tick，满足任一即重拉 `fetchAnalysis(false)`：
- **tip 未分析**：`analysis[move_count] == null`（最新 position）。
- **当前查看手未分析**：`analysis[currentMove] == null`（覆盖翻看历史/回填到位）。

**no-progress 兜底**：「落后」但 analysis key 数连续 N 个周期（建议 N=6≈30s）不增长，**暂停**拉 analysis，直到 `move_count` **或** `currentMove` 变化——避免某 position 永久 FAILED（不含于 `SUCCESS` 行）时无限重拉。

**实现**（替换 `useLiveMatch.ts` 现有 88–99 轮询 effect）。用单一 ref 镜像渲染态，避免闭包陈旧/interval churn：
```ts
// 镜像 effectiveCurrentMove（恒为 number，非内部 nullable currentMove）——避免 null>=0 / a["null"] 误判
const liveRef = useRef({ analysis, match, currentMove: effectiveCurrentMove });
useEffect(() => { liveRef.current = { analysis, match, currentMove: effectiveCurrentMove }; });
const staleRef = useRef({ keyCount: -1, moveCount: -1, viewed: -1, streak: 0 });

useEffect(() => {
  if (!matchId || pollInterval <= 0) return;
  const id = setInterval(() => {
    const { analysis: a, match: m, currentMove: cm } = liveRef.current;
    if (!m || m.status !== 'live') return;            // 运行时判 status（不进 deps，免 churn）
    fetchMatch();                                      // 每 tick：详情/手数/源胜率恒新鲜（getMatch 恒全量）
    const mc = m.move_count;
    const behind = a[mc] == null || a[cm] == null;     // tip 或 查看手 未分析（cm 恒为 number）
    const keyCount = Object.keys(a).length;
    const s = staleRef.current;
    if (keyCount !== s.keyCount || mc !== s.moveCount || cm !== s.viewed) {  // 任一变化即清零 streak
      staleRef.current = { keyCount, moveCount: mc, viewed: cm, streak: 0 };
    }
    if (behind && staleRef.current.streak < 6) {       // no-progress 兜底
      staleRef.current.streak += 1;
      fetchAnalysis(false);
    }
  }, pollInterval);
  return () => clearInterval(id);
}, [matchId, pollInterval, fetchMatch, fetchAnalysis]);
```
> **注**：① 上游 `get_match` **无 `fetch_detail`**，`getMatch` 恒全量（moves+sgf 相对 analysis 的 ownership 19×19/手仍轻）；「`fetchDetail=false` 优化」作废。② **interval 稳定性**（Gemini）：`fetchMatch`/`fetchAnalysis` 须 `useCallback([], )` 稳定——把它们对 `currentMove` 的依赖改为从 `liveRef.current` 读，去掉 deps，否则翻手时 interval 反复重建。③ 镜像 `effectiveCurrentMove`（`= currentMove ?? move_count ?? 0`，恒 number），不要镜像内部 nullable `currentMove`（`null>=0===true`、`a["null"]` 误判，Codex）。④ live→finished 过渡在 status 变化的 effect 里补一次 `fetchAnalysis(false)`，防冻结在不完整分析。⑤ tip 键按 `analysis[move_count]`，落地核对 `move_count` 即最新 position 键。

**TDD**（先写 `useLiveMatch.test.ts`：vitest + fake timers + mock `LiveAPI`；**必须 `advanceTimersByTimeAsync` flush ref 同步**；用真实 `analyzed_moves` 键集 `0..move_count`，不要手设 length。以下 **全部** 为门槛，非「5 个」）：
1. 初次加载：`getMatch` ×1 + `preloadAnalysis` ×1。
2. tip 未分析：每 tick 调 `getMatchAnalysis`。
3. 追平（`analysis` 含 `0..move_count` 全键）：后续 tick **不**调 `getMatchAnalysis`，仍调 `getMatch`。
4. 新手（`move_count`+1、tip 键缺失）：恢复调 `getMatchAnalysis`。
5. **FAILED tip**：连拉 6 次后暂停；**新手到来（`move_count` 变）即恢复**（即便 key 数未增长——验 streak reset on moveCount，Codex #3）。
6. **查看历史回填**：`currentMove` 指向尚无分析的历史手 → 触发；到位后停；**切走（currentMove 变）reset streak**。
7. **nullable currentMove**：初始 `currentMove===null`（effective= move_count）→ 不产生 `a["null"]` 误拉。
8. `status !== 'live'`：完全不轮询。
9. **Galaxy 平价**：新手触发一次 `getMatchAnalysis`（顺带拿到重算的 `move_count-1`）；追平后稳态零 `getMatchAnalysis`——确认无独立「同手改值」遗漏。

- `useLiveMatches.ts` **不改**（列表 30s 全量刷新）。退化安全：信号异常最差退回「每 tick 拉」。
- Galaxy 仍需合并后在直播页**人工回归**（Gemini 标记的头号风险：共享 hook 改动）。

### 任务 2.3：`useLiveMatch` 增 `analysisMode` 开关（修 Codex #4：列表预览不该预载整局 analysis）

现 `useLiveMatch` 初次加载**总**调 `fetchAnalysis(true)`（`useLiveMatch.ts:77-83`）→ `preloadAnalysis` 返回**整局** analysis map。P4 列表页只用棋盘预览（`moves`/回放），不需要 analysis——但复用该 hook 会在进 `/kiosk/live`/切卡片时拉重型 analysis，**直接违背瘦客户端目标**。

- 给 `UseLiveMatchOptions` 加 `analysisMode?: 'none' | 'preload' | 'poll'`，**默认 `'poll'`**（= 现行为：preload + gate 轮询，所有现有调用方零变化）。
- `'none'`：跳过初次 `fetchAnalysis(true)` 与 gate 的 `fetchAnalysis`（只拉 match/moves）。
- P4 列表预览用 `useLiveMatch(id, { pollInterval: 5000, analysisMode: 'none' })`；P5 详情页用默认 `'poll'`。
- **测试**：`analysisMode:'none'` 时**不**调用 `LiveAPI.preloadAnalysis`/`getMatchAnalysis`。（可选纯收益：Galaxy `LivePage` 预览也传 `'none'`，无可见变化——但默认保持 `'poll'` 以零改 Galaxy。）

### 任务 2.4：kiosk 下写方法构造性禁用（修 Codex #13，强化 D4）

`LiveAPI` 仍含 `refresh()`/`createComment`/`deleteComment`（写路径）。在 `__KIOSK_2D_ONLY__` 下让它们直接 `throw new Error('write disabled in board mode')`（而非指向不存在的 board 路由），让「零写路径」由**构造**而非约定保证。加测试。

**验收（P2）**：
- `cd katrain/web/ui && npm test`：`useLiveMatch.test.ts` **全部** case（含 no-progress reset、nullable currentMove、analysisMode:'none'、Galaxy 平价）绿。
- `npm run build && npm run build:kiosk-2d && npm run verify:kiosk-2d` 全绿。
- board 模式手测：kiosk `/kiosk/live` 不再 503，能进列表/详情（UI 仍旧版，数据已通）。
- **commit**: `feat(sbc-live): board API base + position-aware analysis freshness gate + analysisMode`

---

## P3 — Galaxy 直播组件提升到共享区

**共享区改动 → 影响两套构建。** 移动文件 + 改相对路径 + **一处必需逻辑修正（MatchCard 路由）**。

把 `galaxy/components/live/` 下 **7 个**组件移到 `components/live/`（与 `LiveBoard.tsx` 同级）：
`MatchList.tsx`、`MatchCard.tsx`、`MatchInfo.tsx`、`AiAnalysis.tsx`、`TrendChart.tsx`、`PlaybackBar.tsx`、`UpcomingList.tsx`。

**不提升**：`CommentSection.tsx`、`galaxy/hooks/live/useComments.ts`（本期不做评论）。

步骤：
1. `git mv` 7 个文件到 `katrain/web/ui/src/components/live/`。
2. 改各组件内对共享区相对路径：`../../../{types,hooks,i18n,api}` → `../../{...}`（少一层）。`MatchList`↔`MatchCard` 同目录互引不变。
3. **修 MatchCard 跨构建 hazard**（评审发现，非纯移动）：`MatchCard.tsx:43` 在无 `onSelect` 分支硬编码 `navigate('/galaxy/live/${match.id}')`——kiosk router 无 `/galaxy/*`，ESLint/`verify:kiosk-2d` 都抓不到路由字符串。改为**参数化**：加必传 `onSelect`（或 `basePath` prop / router-relative 导航），确保提升后 kiosk 用法不指向 `/galaxy/*`；P4 的 `MatchList` 必须**始终传 `onSelect`**。
4. 改**全部**消费者 import（不只 live 两页！）：
   - `galaxy/pages/live/{LivePage,LiveMatchPage}.tsx`：`../../components/live/X` → `../../../components/live/X`（`LiveBoard` 本就共享区，不变）。
   - `galaxy/pages/report/{ReportDetailPage,ReportsPage}.tsx`：同样 `../../components/live/X` → `../../../components/live/X`（消费 `AiAnalysis`/`PlaybackBar`/`TrendChart`）。
   - **测试 mock 路径**（`vi.mock` 失配是**静默**的、`tsc` 抓不到 → 测试假绿）：`ReportDetailPage.test.tsx:40,46`、`ReportsPage.test.tsx:55` 的 `vi.mock('../../components/live/...')` → `../../../components/live/...`。
5. 全量核对：
   ```bash
   grep -rn "components/live/" katrain/web/ui/src | grep -v node_modules    # 改前后对比，无残留旧路径
   grep -rn "/galaxy/live" katrain/web/ui/src/components/live                # 提升后组件不得含 galaxy 路由串
   ```
   靠 `tsc`（**full + kiosk 两套都 build**）+ eslint 边界兜底。

**验收（P3）**：
- `npm run build && npm run build:kiosk-2d && npm run verify:kiosk-2d` 全绿；kiosk dist 无 `three`/`@react-three`，且 `grep '/galaxy/' dist` 无命中。
- Galaxy `/galaxy/live`、`/galaxy/live/:id`、`/galaxy/report/*` 外观/行为**不变**；report 页测试 mock 仍生效（非假绿）。
- **commit**: `refactor(sbc-live): lift 7 live components galaxy→shared (components/live)`

---

## P4 — kiosk 列表页对齐

**文件**：`katrain/web/ui/src/kiosk/pages/LivePage.tsx`（重写）、`kiosk/__tests__/LivePage.test.tsx`（更新）。

参照 Galaxy `galaxy/pages/live/LivePage.tsx` 的信息架构，用 kiosk 触屏布局落地（PRD §4.4 / F1·F2·F3·F15）：
- **左侧**：选中对局的 `LiveBoard` 预览 + `PlaybackBar`（替换现有「直播预览」占位文字）。默认选中沿用 Galaxy「首个直播中」逻辑（`matches.find(m=>m.status==='live') ?? matches[0]`，PRD Q6 取此简单方案）。
- **右侧**：`热门对局 / 即将开始` 双 Tab；热门下分「直播中（计数）」「历史」两组 `MatchList`（`compact` + 选中态）；即将开始用 `UpcomingList`。
- **进入按钮**：`navigate('/kiosk/live/:id')`。
- 复用共享 hook `useLiveMatches`、`useLiveMatch`（取选中局详情用于预览，`{ pollInterval: 5000, analysisMode: 'none' }`——**预览只要 moves/回放、不需 analysis**，用任务 2.3 的开关避免拉整局重型数据，Codex #4）。
- 触屏：Tab / 列表行 / 按钮可点区 ≥44px，沿用 kiosk 既有页面风格（参考 `kiosk/pages/KifuPage.tsx` 等）。
- 测试沿用现有 hook-level mock 模式（`vi.mock('../../hooks/live/useLiveMatches')`）。

**验收（P4）**：F1/F2/F3/F15 达标；列表/预览/双 Tab 可触摸操作；**预览不调用 `preloadAnalysis`/`getMatchAnalysis`**（断言）；两套构建 + `npm test` 绿。
- **commit**: `feat(sbc-live): kiosk live list page parity (board preview + playback + tabs)`

---

## P5 — kiosk 详情页对齐 + 触屏适配

**文件**：`katrain/web/ui/src/kiosk/pages/LiveMatchPage.tsx`（重写）、`kiosk/__tests__/LiveMatchPage.test.tsx`（更新）。

参照 Galaxy `galaxy/pages/live/LiveMatchPage.tsx`（PRD §4.5/§4.6，F4–F14）：
- 左侧 `LiveBoard` 启用全套 props：`pvMoves` / `aiMarkers` / `showAiMarkers` / `showMoveNumbers` / `showTerritory` / `ownership` / `tryMoves` / `onTryMove`。
- 右栏：`MatchInfo` + 四开关（试下/形势/手数/AI 标记，`ToggleButtonGroup`）+ `AiAnalysis` + `TrendChart` + `PlaybackBar`。
- `aiMarkers` / `ownership` 由 `analysis[currentMove]` 计算——**直接照搬** Galaxy `LiveMatchPage.tsx:62–81` 的 `useMemo` 逻辑。
- 保留落子音效（`useSound('stone')`）。
- 朝向：沿用 kiosk `useOrientation`；竖屏棋盘在上、信息/分析在下。

**触屏适配**（评审修正：`AiAnalysis` 仅经 `onMouseEnter/Leave` 发 `onMoveHover`、**无任何 click 事件**（`AiAnalysis.tsx:222-223`，grep 零 click）——页面层**无法**在不改组件下做 tap，故需一处**加法式**共享组件改动）：
- **PV 预览**：给共享 `AiAnalysis` **新增可选 `onMoveSelect?(pv: string[] | null)` prop**，`MoveRow` 在 `onClick`/`onPointerUp` 调用它。Galaxy **不传**该 prop → hover 语义/行为**字节不变**（opt-in、加法式，护住 Galaxy）；kiosk 传它驱动 tap：点某推荐手 → 预览其 PV，再点同手 / 点空白 → 清空。
- **试下（Q5 已定：ghost variation 平价，无规则引擎）**：本期试下 = 与 Galaxy 现有 try 行为一致——`LiveBoard.onTryMove` 仅回调坐标、空点画半透明子（`LiveBoard.tsx:491-505,708-714`），**无提子/合法性/打劫/轮次校验**。**F12 验收即此定义**（不交付合法落子模拟；如需真实试下另立 scope，Codex #9）。试下与 PV 互斥：`onTryMove` 激活时 `handleClick` 早退吞 board tap → 进试下前先清 PV、两模式互斥。试下直接点交叉点落子 +「清空」按钮。
- **Tooltip**：以图标 + 常驻文字标签替代 hover tooltip。

> **R6 更新**：共享组件改动从「零」变为「`AiAnalysis` 加 opt-in `onMoveSelect`」——仍**不改** hover 路径，Galaxy 行为不变，但需在 Galaxy 直播页跑回归确认。

> **竖屏布局（Q3）——P5 完成的必要条件，非 P6 polish（Codex/Gemini 一致）**：目标 kiosk 多为竖屏，而 Galaxy 右栏是 `width:500` 固定列、`xs` 隐藏（`LivePage.tsx:107-111`），竖屏下不可用。P5 **必须**交付可用的竖屏布局（`AiAnalysis`+`TrendChart`+`PlaybackBar` 简单纵向堆叠即可）——**实现前先出 mockup 给用户确认**（mockup-first 偏好）。横屏占位不算 P5 完成。

**验收（P5）**：F4–F14 达标；PV/试下（ghost variation）/开关纯触摸可用；**竖屏布局可用**；两套构建 + `npm test` 绿。
- **新增 `AiAnalysis` 组件测试**（共享组件行为扩展，Codex #10）：不传 `onMoveSelect` → hover 行为不变（Galaxy 平价）；传入 → click/pointer 触发 PV；再点同手 / 外部清空能清 PV。
- **commit**: `feat(sbc-live): kiosk live match page parity + touch adaptation`

---

## P6 — 收尾

1. **i18n**（Codex 修正：译表加载链路**已存在**——`SettingsContext.tsx:63,77` → `i18n.loadTranslations` → `loadLiveTranslations`（`i18n.ts:26`），kiosk 经同一 `SettingsProvider`，**无需新接线**；Gemini 的「加 loadLiveTranslations」意见不采纳）。真正要做：**把被提升组件里的硬编码串迁到 i18n**——`MatchList.tsx:39-40,69-76`（中文错误/Tab/空态）、`UpcomingList.tsx:35,84-88`（英文 literal）等迁到 `t()`/`live:*`（可并入 P3）；kiosk 新增文案用 `t('English','中文')`；译名走 `translations` 代理 + `i18n.translatePlayer`。验：`uv run python i18n.py -todo` + **英文 UI 下被提升组件无中文 Tab/空态**的测试。
2. **强化 `verify:kiosk-2d`**（两评审一致）：扩展 `katrain/web/ui/scripts/verify-kiosk.sh` 让其 grep kiosk dist 的 `/galaxy/` 与 `/api/v1/live`（现仅查 `THREE.`/three/@react-three），把边界 verify 从「仅 three.js」升为「无跨构建路由/基址泄漏」。
3. **竖屏布局打磨**（P5 已交付可用竖屏，此处仅打磨；接 Q3 mockup 结论）。
4. **断网降级**：拔上游，确认 kiosk 直播显示 502/404 友好态、不白屏不崩溃（验收 §5.8）。
5. **freshness gate 实证**：DevTools Network 观察一局 live——稳态无 `/analysis` 请求；出新手并分析落库后 ≤1–2 个轮询周期内 AI 推荐/趋势刷新。
6. **全量回归**：两套构建 + `verify:kiosk-2d`（含新 grep）+ `npm test` + `uv run pytest tests` + **Galaxy 直播页人工回归**（共享 hook/组件改动，Gemini 头号风险）。
7. `uv run black -l 120 katrain tests` 格式化后端改动。
- **commit**: `chore(sbc-live): i18n, portrait polish, offline fallback, final regression`

---

## 验证清单（对齐 PRD §5）

| # | 验收项 | 怎么验 |
|---|---|---|
| 1 | 503 消除 | kiosk 进直播显示列表，无 503/502（上游有数据） |
| 2 | 代理覆盖 | `curl` 8 个 `board/live/*` 与上游一致 |
| 3 | 功能对等 | 详情页 AI 推荐/趋势/四开关/回放；列表页双 Tab + 预览 |
| 4 | 触屏可用 | PV/试下/开关纯触摸完成 |
| 5 | 本地化 | 中文 UI 下棋手/赛事/规则按译名显示 |
| 6 | 构建绿 | `build` + `build:kiosk-2d` + `verify:kiosk-2d` 全过；kiosk dist 无 three |
| 7 | Galaxy 无回归 | `/galaxy/live*` 行为/外观不变 |
| 8 | 断网降级 | 上游不可达 → 502 友好态 |
| 9 | 轮询效率 | 稳态无重型 analysis 重拉；出新手 ≤1–2 周期内刷新 |
| 10 | 瘦客户端 | board 无 KataGo/live_service/翻译 token；数据全来自上游 |

**关键命令**：
```bash
# 前端
cd katrain/web/ui && npm test && npm run build && npm run build:kiosk-2d && npm run verify:kiosk-2d
# 后端
uv run pytest tests && uv run black -l 120 katrain tests
# board 模式手测
KATRAIN_MODE=board KATRAIN_REMOTE_URL=<server> python -m katrain --ui web
```

---

## 风险与回滚（详见 PRD §6）

- **共享区波及 Galaxy**（`api/live.ts`、提升组件、`useLiveMatch` gate）：每个共享阶段跑两套构建 + hook 单测；gate 纯增量、可退回朴素轮询。
- **import 路径遗漏**（P3 移 7+2 文件）：逐文件 grep + `tsc`/eslint 兜底。
- **代理透传不全**（`move_number`/`lang`/`limit`；`fetch_detail` 已确认上游 no-op，删）：P1 验收逐端点对比上游。
- **analysis 落库探测**（R8）：gate 用 coverage 判据而非 `last_updated`。
- **回滚**：分阶段 commit；`git revert` 合并提交。组件提升若出问题，可临时让 kiosk 复制组件而不动 Galaxy。

## 开放问题（执行中需用户确认）

- **Q3** kiosk 详情页竖屏堆叠 → P5 前出 mockup 确认。
- **Q5** 试下落子规则是否复用 `LiveBoard` 现有 try 逻辑（确认 `onTryMove` 行为满足）。
- **Q6** 列表默认选中：本计划取「首个直播中」（如需改用 `featured` 再调整）。
