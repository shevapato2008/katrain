# 计划审核 Prompt — sbc-live-parity

> 把本文件连同 `plan.md`、`prd.md` 一起发给 Codex / Gemini 进行独立审核。

## 你的任务

你是一名**持怀疑态度的资深评审者**，对 `superpowers/tracks/sbc-live-parity/plan.md`（及其 PRD `superpowers/tracks/sbc-live-parity/prd.md`）做一次**严苛、可执行性导向**的评审，覆盖三个维度：

- **正确性** — 逻辑、边界、语义是否真的成立（尤其 freshness gate 的核心断言）。
- **完整性** — 是否漏掉必须改的文件、必须覆盖的边界、必须加的测试。
- **执行风险** — 落地时会不会破坏 Galaxy、破坏两套构建、留下静默 bug。

**不要盖橡皮图章。** 默认假设计划可能是错的。每条结论必须给出 `file:line` 级证据（对照**真实代码**，不是计划自述）。若你判断某处无误，也请说明你是怎么对照代码核实的。本 prompt 内已嵌入内部初审发现的若干疑似缺陷——请独立**证实或推翻**它们，不要直接采信。

## 本轮修订摘要（已据内部初审修正，请重点复核「修正是否正确、是否引入新问题」，而非再报原问题）

以下 6 项已在 `plan.md`/`prd.md` 修正：

1. **gate off-by-one** → 改为 **position-aware 判据**：`analysis[move_count]`(tip)/`analysis[currentMove]` 未分析、或 tip 胜率就地变化 时才重拉 + no-progress 兜底（FAILED 洞）；delta 触发器由「可选」升为**强制**。（plan §2.2、prd §4.8）请复核：tip 索引是否真是 `move_count`、N=6 是否合理、Galaxy 是否仍无回归、no-progress 是否会漏掉应拉的更新。
2. **路由顺序** → `featured` 显式声明在 `{match_id}` 之前。（plan P1.2）
3. **502 一刀切** → 加 `_proxy` 包装：上游 4xx 原样透传、仅连接/超时→502。（plan P1.2）
4. **`fetch_detail` 幽灵参数** → 已核实上游 `get_match` 无此参数、恒返回 moves，**整体删除**透传；连带 `fetchDetail=false` 优化作废。（plan P1/§2.2、prd §4.1）
5. **P3 漏 report 页 import + `vi.mock` + `MatchCard` 硬编码 `/galaxy/live`** → 已纳入 P3（含参数化 MatchCard 路由）。（plan P3）
6. **触屏 PV「页面层不改组件」不可行** → 改为给共享 `AiAnalysis` 加 **opt-in `onMoveSelect`**（Galaxy 不传、hover 不变）。（plan P5、prd §4.6/R6）

**仍开放、未在本轮修订**（请照下方清单照常审）：kiosk i18n `loadLiveTranslations` 接线、竖屏布局（Q3，竖屏为主设备的 de-facto blocker）、gate 不被页面测试覆盖、验收标准客观性、试下规则（Q5）、非 19 路棋盘、共享 bundle 仍含 comment/refresh 死方法、proxy 无缓存。

## 待审产物与如何获取

**核心待审文档**（仓库相对路径）：
- `superpowers/tracks/sbc-live-parity/plan.md` — 实施计划（P0–P6，含代码骨架与验收点）
- `superpowers/tracks/sbc-live-parity/prd.md` — 需求与验收（D1–D5、R8/R9、§1.3/§4.8/§5）

**必须打开对照的关键代码文件**（计划的正确性几乎全部取决于这些文件的真实语义）：
- 后端代理与上游：`katrain/web/api/v1/endpoints/board.py`、`katrain/web/core/remote_client.py`、`katrain/web/api/v1/endpoints/live.py`、`katrain/web/api/v1/api.py`（路由注册）、`katrain/web/server.py`（board 模式 token/lifespan）
- 上游分析语义（gate 正确性的真相来源）：`katrain/web/live/{analysis_repo.py,analyzer.py,poller.py,service.py}`（重点：`analysis_repo.py:127-139/192-227/252-254/281`、`analyzer.py:191-193/347-355/378`、`poller.py:376`、`live.py:264-328`）
- 前端数据层：`katrain/web/ui/src/hooks/live/useLiveMatch.ts`、`katrain/web/ui/src/api/live.ts`、`katrain/web/ui/src/types/live.ts`、`katrain/web/ui/src/i18n.ts`
- 待提升的 7 组件：`katrain/web/ui/src/galaxy/components/live/{MatchList,MatchCard,MatchInfo,AiAnalysis,TrendChart,PlaybackBar,UpcomingList}.tsx`，及消费者 `galaxy/pages/live/{LivePage,LiveMatchPage}.tsx`、`galaxy/pages/report/{ReportDetailPage,ReportsPage}.tsx`（含对应 `*.test.tsx` 的 `vi.mock` 路径）
- 共享棋盘：`katrain/web/ui/src/components/live/LiveBoard.tsx`
- 构建边界：`katrain/web/ui/eslint.config.js`、`vite.config.ts`、`src/vite-env.d.ts`、kiosk 校验脚本（`verify:kiosk-2d` 对应的 `verify-kiosk.sh`）、`src/kiosk/KioskApp.tsx`、`src/kiosk/components/layout/navTabs.tsx`

**给两类评审者的取材说明**：
- **Codex（有完整仓库读权限）**：直接逐行打开上述文件核实，不要凭计划自述下结论。重点把上游 `analysis_repo.py / analyzer.py / poller.py` 的 analysis key 集合语义与前端 gate 条件、`live.py` 的 `get_match` 是否真有 `fetch_detail`、`AiAnalysis.tsx` 是否真无 click 事件 对齐核对。
- **Gemini（无仓库）**：请用户附上 `plan.md` + `prd.md` + 至少 `useLiveMatch.ts`、`api/live.ts`、`analysis_repo.py`、`analyzer.py`、`live.py`、`AiAnalysis.tsx`、`MatchCard.tsx`、`eslint.config.js`、`vite.config.ts`、`verify-kiosk.sh`。无法对照的断言请标注「需代码核实」，不要凭空判断。

## 背景速览

本计划把 Galaxy 已有的「直播观战」能力**平移到 SBC kiosk（RK35xx 触摸终端，多为竖屏）**，分 6 阶段：P1 后端补全 `/api/v1/board/live/*` 只读代理（解 503）；P2 前端数据层（`api/live.ts` 基址自适应 + `useLiveMatch.ts` 加 freshness gate）；P3 把 7 个 `galaxy/components/live/*` 提升到共享 `components/live/`；P4/P5 搭 kiosk 列表页/详情页 + 触屏适配；P6 收尾。三大支柱：

1. **瘦客户端不变式** — kiosk 只走 GET 只读代理，绝不触发服务端写/learn 或消耗 token。
2. **分析新鲜度 gate** — 详情页 analysis 仅在 `analyzed_moves.length < move_count` 时重拉，宣称「稳态零重型刷新」。
3. **两套构建边界** — `api/`、`hooks/`、`components/`、`types/` 为共享区，任何改动**同时影响** `npm run build`（full/Galaxy）与 `npm run build:kiosk-2d`（kiosk），靠 ESLint 边界 + `verify:kiosk-2d` + 双构建守护。

**审查重点：gate 的语义正确性、瘦客户端是否真「稳态便宜」、触屏 PV 预览是否真能不改共享组件、共享区改动是否静默破坏 Galaxy 或两套构建。**

---

## 重点审查清单

### A. 后端只读代理（P1）

- **[blocker] FastAPI 路由顺序：`featured` 被 `{match_id}` 吞掉。** 现有 `board.py` 先声明 `/live/matches`（board.py:121）再 `/live/matches/{match_id}`（board.py:138）。计划 P1 骨架说「append after existing proxy_live_match」，把 `proxy_live_featured` 排在 `{match_id}` **之后**——FastAPI 按声明顺序匹配，`GET /board/live/matches/featured` 会被当成 `match_id='featured'` 转发到上游 `/matches/featured-as-id`（404/502）。计划自己的内联警告（plan.md:166）与其代码块的顺序自相矛盾。上游 `live.py` 把 `/matches/featured`（:210）声明在 `/matches/{match_id}`（:264）**之前**——代理必须复刻此顺序。问：骨架里 `featured` 是否物理上排在 `{match_id}` 之前？是否有测试断言 `featured` 返回焦点局而非 404？
- **[major] `fetch_detail` 可能是幽灵参数（两处内部初审结论冲突，请定论）。** 计划 P1 + PRD §4.1（prd.md:176）声称 `/matches/{id}` 需透传 `fetch_detail` 否则详情页拿不到 `moves`。但初审读 `live.py:264-297` 发现上游 `get_match` **根本没有 `fetch_detail` 参数、且无条件返回含 `moves`+`sgf` 的 `MatchDetail`**（`service.py` 的 `get_match` 同样没有）。若属实，则整套 `fetch_detail` 透传（remote_client + proxy + 前端 `getMatch(id,fetchDetail)` api/live.ts:105）是**基于错误前提的无效工作**，PRD 的理由（prd.md:176）是错的。问：`live.py:264-297` / `service.py` 里 `get_match` 究竟读不读 `fetch_detail`？前端那个参数是否一直是 no-op？该透传应保留还是删除？
- **[major] 一刀切 502 抹掉 404/401/422 语义。** 每个代理都 `except Exception → HTTPException(502)`，而 `remote_client` 调 `resp.raise_for_status()` 对任意 4xx/5xx 抛 `HTTPStatusError`。于是上游 404（match 不存在，live.py:314）、422、401 全塌成「502 Remote server unavailable」。前端无法区分「这局不存在」与「上游宕机」，破坏 §5.8 断网降级 UX。问：missing match 是否应以 404 透传给 kiosk？代理是否应检查 `HTTPStatusError.response.status_code` 原样重抛 4xx、只把连接/超时映射成 502/503？
- **[major] 模块级基址翻转把写/不存在路径重指向 board。** P2 把整个 `api/live.ts` 的 `API_BASE` 翻成 `/api/v1/board/live`，于是**所有** `LiveAPI` 方法都指向 board 代理。`LiveAPI.refresh()` POST `/refresh`（api/live.ts:170）——但上游 `live.py` **根本没有 `/refresh` 路由**；comment 方法（getComments/pollComments/createComment/deleteComment）也指向 P1 不实现的 board 写路径。计划说「不会被调用」，但它们仍在共享 bundle 里、**未被 `__KIOSK_2D_ONLY__` DCE**（是对象方法不是死分支）。问：有什么**结构性**保证 kiosk 可达代码（含被提升的共享组件）永不调用它们？是否应在 kiosk 下用 `define` 守护或剔除，让「零写路径」由构造保证？
- **[major] 上游读端点鉴权与 board 设备凭证。** 计划从未说明上游 live 读是否需登录。初审：所有读端点用 `Depends(get_live_service)`（**非** `get_current_user`），`/translations` 无任何 auth dep（live.py:447）——所以读应免鉴权。但 `RemoteAPIClient._request` 默认 `auth=True`，board 模式 token 来自可选的已存 refresh token（server.py:280-282），**可能缺失**。问：逐一确认 8 个读端点是否真免鉴权？board 设备**无凭证**时这些代理读是否端到端成功（有测试吗）？若上游将来收紧鉴权 401，整个 board-live 是否瘫痪、且被 502 掩盖到无法诊断？
- **[minor] `/translations` 契约收紧 + 参数 None 过滤语义。** 上游 `/translations` 的 `lang` 默认 `'en'`（live.py:449），计划代理把 `lang` 声明为必填 `Query(...)`（plan.md:159）——是行为变化。又：`remote_client` 过滤 None 参数；`move_number=None` 时 `/analysis` 返回全量 map（live.py:319-328，确认是否即「全部手」预期）；`lang=None` 时上游 `translator=None` 不翻译（live.py:153）——但 kiosk 本应始终带 `lang`（F14），确认这是期望默认。
- **[minor] 端点存在性与响应形状 1:1 透传。** `/matches/featured` 返回**无类型** `{'match': MatchSummary|null}`（live.py:210-261），`/analysis`、`/preload`、`/stats` 返回 dict——确认代理不挂 `response_model` 以免丢字段。`/upcoming` 返回 `{matches:[...]}` 是否匹配前端 `UpcomingMatch[]`（types/live.ts）。`/stats` kiosk 是否真消费、否则是死代理面。
- **[minor] 参数边界对齐。** 上游 `/upcoming` `limit ge=1,le=100,default=20`（live.py:361）与计划一致；`/matches` `le=200`（live.py:143）现有代理已镜像（board.py:127）——确认计划未改坏。

### B. 前端 freshness gate（P2，`useLiveMatch.ts`）— 核心新逻辑 + Galaxy 回归

- **[blocker] gate 条件 off-by-one：analysis 按 position `0..move_count` 闭区间 keying。** 计划核心条件是 `analyzedCount = Object.keys(analysis).length < move_count`（plan.md:204,213,222）。但 analysis 按**棋盘 position**（非 move index）keying：上游 `get_unanalyzed_moves` 调度 `range(max_move + 1)` = `0..move_count` **闭区间**（analysis_repo.py:281），move 0（空盘）被分析（analyzer.py:378），新手入队 `range(old, new+1)`（poller.py:376）。⇒ **一个完全追平的 live 局 `Object.keys(analysis).length == move_count + 1`，不是 `move_count`**。问：`< move_count`（严格小于）会不会在「`0..move_count-1` 都好了、但最新 tip position（key == `move_count`，观众最想看的最新胜率/PV/ownership）仍 pending」时就**停止拉取**，让 tip 永远停在上一手分析直到下一手？正确的「追平」判定应是什么——`>= move_count+1`？`move_count in analysis`？还是 position-aware 的 `currentMove in analysis && move_count in analysis`？计划是否在代码层核实过 key 是 `0..move_count` 闭区间，还是想当然按 `1..move_count`？
- **[blocker] 稀疏覆盖：length ≠ coverage。** `get_successful_analysis` 只返回 `status==SUCCESS` 行（analysis_repo.py:127-134）；pending/RUNNING/永久 FAILED 的 position 全缺席。分析会失败（3 次重试后永久 FAILED，analyzer.py:347-355、analysis_repo.py:252-254），且 live 新手优先级 1000、历史回填 100，**乱序**填洞。⇒ `length` 可能 `== move_count` 而覆盖的是**另一组** position（tip 好了、position 5 失败/pending）。问：若 position 7 永久 FAILED 而余者成功，`length == move_count`（一缺一多相抵），gate 会不会**误判追平并停拉**、把永不回填的洞静默 strand？caught-up 后回填的历史 position（`move_count` 没变、`analyzedCount` 只增）会不会**永远不被重拉**，导致用户翻看历史手时其分析永不出现？这两种情况下，「稳态零重型刷新」是否其实退化成「永远 `length<move_count` ⇒ 每 tick 拉重型 ⇒ 零节省」的反面？
- **[major] 就地重分析（同 key 改值）被 gate 漏掉——「可选」触发器实为必需。** 分析器可 `update_analysis_result` 就地覆盖某 position 的胜率/PV/ownership（analysis_repo.py:192-227）而**不改 key 集**——`length` 不变，gate 永不重拉，观众该手永远看旧数。计划把 `(current_winrate,current_score)` delta 触发器列为「本期可不做」的可选增强（plan.md:229）。问：这个触发器是否其实是**正确性必需**（load-bearing）而非可选？
- **[major] `fetchMatch(fetchDetail=true)` 每 tick 拉重负载，反驳「稳态便宜」。** 计划保留每 5s `fetchMatch()`（plan.md:221），而 `fetchDetail` 默认 `true`（useLiveMatch.ts:21；`LiveMatchPage` 无 options 调用），`MatchDetail` 含完整 `sgf`+`moves[]`（types/live.ts:28-31）。250 手的局每 5s 重传 SGF+全 moves，永远如此；board 代理无缓存（PRD §1.3）。计划把 `fetchDetail=false` 优化**显式推迟**（plan.md:248）。问：这是否直接违反 PRD「稳态零重型刷新」（§5.9）？`move_count`/winrate 能否不带 `moves[]+sgf` 获取？把便宜变体推迟却让头条「降本」目标落空，是不是**范围错误**？是否需要一条断言「稳态总字节下降」（不只是 analysis 请求数）的验收测试？
- **[major] Galaxy 回归——gate 在共享 hook，改变 Galaxy 可观察行为。** PRD D5/R9 称对 Galaxy 是「透明优化」。但今天 Galaxy **每 tick 无条件**重拉 analysis（useLiveMatch.ts:95），任何服务端变化一个 tick 内浮现；加 gate 后，上面的就地重分析、caught-up 回填 **Galaxy 也会停止捕捉**。问：这是不是 Galaxy 的**新鲜度回归**而非透明优化？有没有人核实上游分析器**从不**就地更新已返回 position？Galaxy 与 kiosk 是否用**完全相同**的 `useLiveMatch`（无 `pollInterval`/`fetchDetail` 差异）——若相同，每个 gate bug 都是 Galaxy bug，对「不改 Galaxy 行为」（§2.2）的承诺是否可接受？
- **[major] stale-closure / ref 正确性 + interval churn。** 计划在 setInterval 内读 `analyzedCountRef`/`moveCountRef`，用独立 effect 同步 ref（plan.md:211-227）。但 poll effect deps 含 `fetchMatch`，而 `fetchMatch` 依赖 `currentMove`（useLiveMatch.ts:53），`match?.status` 也在 deps——用户翻手或新手自动前进时 `fetchMatch` 重建，**反复 teardown/重建 5s interval**。问：active 导航时 5s 节拍会不会被反复重置导致漏/多 tick？`fetchMatch` 是否应改 ref 而非 dep？ref 在 commit 后才更新——tick 恰在 state 更新与 ref-sync effect 之间触发时，是否读到旧 ref 整整一个 tick（~5s）？PRD「≤1 poll 周期」（prd.md:262）是否诚实？
- **[major] 边界态：开局 / live→finished / tip 未就绪。** (1) 开局 `move_count=0/1`、`analysis[0]` 可能未就绪——`>move_count` 的 overshoot 会不会让小局**过早**判 caught-up？(2) live→finished 翻转时 poll effect 早退停轮询（useLiveMatch.ts:91）——若此刻回填仍 pending/FAILED，analysis 冻结不完整且 kiosk **无手动刷新**；是否应在过渡时补一次 catch-up 拉取？(3) 新手到达、`currentMove` 自动前进，若 `analysis[move_count]` 未就绪，aiMarkers/ownership 为 null（LiveMatchPage.tsx:63-81）——board 显示空白/旧 overlay，最坏可见 staleness 窗口多大？
- **[minor] gate 仅由新 hook 测试覆盖，页面测试全 mock 掉它。** kiosk 页面测试完全 mock `useLiveMatch`（LiveMatchPage.test.tsx:12-14、LivePage.test.tsx:8-10），gate 的 ref/分支**从不被页面测试触达**，只靠新 `useLiveMatch.test.ts`（5 case）。问：5 个 case 是否忠实建模真实 key 集（`0..move_count` 闭区间、FAILED 洞、就地更新），还是建模理想连续 key 集而照过、真实 gate 是坏的？是否用 `vi.advanceTimersByTimeAsync`（而非同步）以确保 React commit + ref-sync 在 interval 回调读 ref **之前** flush？是否断言每 tick `getMatch` vs `getMatchAnalysis` 的**精确**调用次数？验收 #9（稳态无 `/analysis` 请求）是否只有手动 DevTools 观察、无自动断言？

### C. 构建边界（P2/P3）— 两套构建必须双绿

- **[major] `MatchCard` 硬编码 galaxy-only 路由。** `MatchCard.tsx:43` 在无 `onSelect` 分支里 `navigate('/galaxy/live/${match.id}')`，而 kiosk router（KioskApp.tsx）只注册 `live`/`live/:matchId`，**没有 `/galaxy/*`**。ESLint 只禁 galaxy *import* 不禁路由 *字符串*；`verify-kiosk.sh` 只 grep `THREE./three/@react-three`——**这个死路由静默通过所有闸门**。P3 称「纯移动、无逻辑改动」不属实。问：提升后什么保证每个 kiosk 消费者都传 `onSelect`？该契约写在 P4/P5 哪里、哪个闸门强制？是否应把路由参数化（`basePath` prop / router-relative）而非硬编码？是否需要 Playwright 实际点击 kiosk MatchCard 断言落到 `/kiosk/live/:id`？
- **[major] P3 import 修复清单漏掉 report 页及其测试 mock。** P3 只列 `galaxy/pages/live/{LivePage,LiveMatchPage}.tsx`，但 `galaxy/pages/report/ReportDetailPage.tsx:28-30` 也 import `AiAnalysis/PlaybackBar/TrendChart`、`ReportsPage.tsx:36` import `PlaybackBar`——移动后路径断裂（应变 `../../../components/live/`）。更隐蔽：`ReportDetailPage.test.tsx:40,46`、`ReportsPage.test.tsx:55` 的 `vi.mock('../../components/live/...')` 会**失配静默失效**（测试照过但跑真实组件）。问：P3 的 grep 是否真能 surface 这些？`vi.mock` 失配通常**静默**、不是 `tsc` 错——「靠 tsc + grep 兜底」兜得住吗？更新它们是否在 P3 commit 范围内？
- **[major] 双构建验证的实际覆盖被高估。** 计划反复以「双构建 + `verify:kiosk-2d` 全绿」作为边界安全证明。但 `verify-kiosk.sh` **只**查 three.js 残留——检测不到 (a) kiosk dist 里的 galaxy 路由串、(b) full-mode `/api/v1/live` 基址泄漏进 kiosk、(c) report 页 import 断裂（那是 full 构建失败、不是 kiosk）。问：流水线里**究竟什么**证明 kiosk bundle 不含 galaxy 路由串和 full-mode 基址？是否应扩展 verify 脚本 grep kiosk dist 的 `/galaxy/` 与 `/api/v1/live`？每阶段「跑两套构建」的次序是否被强制（P3 提交前是否真跑 full 构建，否则 report 断裂会在 kiosk 绿的同时 land）？
- **[minor] `__KIOSK_2D_ONLY__` ternary 的 DCE。** 确认 `define: { __KIOSK_2D_ONLY__: JSON.stringify(kioskMode) }`（vite.config.ts）注入字面布尔，使 `__KIOSK_2D_ONLY__ ? '/api/v1/board/live' : '/api/v1/live'` 在各自构建折叠为单字面量——full 里 `/api/v1/board/live` 被 DCE、kiosk 里 `/api/v1/live` 被 DCE，两边都不泄漏对方基址串。
- **[minor] 相对路径深度 + ESLint 边界。** 核实 `galaxy/components/live`（深 3）→ `components/live`（深 2）即 7 组件 `../../../X → ../../X`；`galaxy/pages/*`（深 3）→ 共享 `components/live`（深 2）即 `../../components/live/X → ../../../components/live/X`——**同规则是否推广到所有深度 3 的 `galaxy/pages/report/*`**？`MatchList → ./MatchCard` 同目录不变是否正确？移动后 ESLint `forbiddenFromKiosk` 是否仍抓 kiosk 误引**旧** galaxy 路径、同时放行**新** `components/live`？

### D. 触屏与交互（P5）

- **[blocker] 触屏 PV 预览的可行性——计划自相矛盾。** 计划「无 Galaxy 回归」的头号缓解是 tap-to-preview **只在 kiosk 页面层接、`AiAnalysis` 不动**（plan.md:295-296、PRD R6）。但 `AiAnalysis` 只通过 `onMoveHover` 暴露 PV，而它**仅**由 `MoveRow` 的 `onMouseEnter/onMouseLeave` 触发（AiAnalysis.tsx:222-223 → 171-176），组件内**没有任何 onClick/onTouch/onPointer**（grep 零）。页面收到的是 hover 形状的回调，**无法在不改组件的前提下重定向到 tap**。计划那句「页面把 onMoveHover 接到点击态即可，不改 AiAnalysis 内部」是自相矛盾的——没有 click 事件逃出 AiAnalysis。问：具体在**哪个 DOM 事件、哪个元素**上拦截来驱动 tap 预览？触屏上点击 MoveRow 是否可靠触发 mouseenter 而**不**触发 mouseleave（预览设了却清不掉），或两者同 tap 触发（预览闪一下立即清）？用户如何**清除** pvMoves（点空白？再点一次？）——而 `onTryMove` 激活时 `LiveBoard.handleClick` 早退（LiveBoard.tsx:710-714）吞掉 `onIntersectionClick`，board tap 还能清 PV 吗？给 `AiAnalysis` 加 onClick/onMoveSelect 是否其实**不可避免**——那就是计划否认的**共享组件改动**（R6），重新打开 Galaxy 回归风险？
- **[minor] 试下规则（Q5）与 board-tap 冲突。** Q5「试下规则」标为 open，但 F12/验收 #4 要求试下在触屏**可用**。`LiveBoard` 的 `onTryMove` 仅 append 坐标串（Galaxy LiveMatchPage.tsx:138）、试下渲染半透明子无吃子/合法性/打劫/轮次校验（LiveBoard.tsx:492-506）。问：这是否即「满足 onTryMove」（计划 Q5 假设），还是 kiosk 需要计划未涵盖的真实落子规则？试下模式下 `LiveBoard.handleClick` 早退导致 PV-tap 与 try-tap 抢同一 board tap——冲突是否已解决、Q5 是否涵盖？
- **[minor] 非 19 路棋盘。** kiosk 现详情页传 `match.board_size`（kiosk LiveMatchPage.tsx:37），但 `parseMove` 硬编码 19×19 边界（LiveBoard.tsx:66）。问：9×9/13×13 的 live 局，平移工作是否会暴露这个潜伏 bug、territory 是否可能镜像错（ownership y 反转假设 LiveBoard.tsx:443-447）？

### E. i18n / 本地化

- **[major] 两套翻译系统被混为一谈；kiosk 可能从不加载译表。** 存在两条翻译路径：(a) 通用 UI 文案 `/api/translations → i18n.t()` 读 `.po`（server.py:1319）；(b) 棋手/赛事**名**翻译 `LiveAPI.getTranslations → i18n.translatePlayer`（i18n.ts:33-63，走 live 代理）。计划 P6（plan.md:309）把两者混同。关键：78 个 `live:*` key 存在于 `.po`，但**许多是无内联英文兜底的裸 `t('live:xxx')`**（LivePage 98/120/121/132/144/171；MatchInfo/MatchCard/PlaybackBar/UpcomingList），`i18n.t` 在 catalog 未载时**返回原始 key**（`'live:top_matches'`）。且 kiosk 现今**从不**调用 `translatePlayer/translateTournament`（grep 零）——名翻译是**全新接线**，不是「复用」。问：kiosk 启动是否真的调用 `i18n.loadTranslations()/loadLiveTranslations()`？若 kiosk 入口从不调用，则 78 个 `live:*` 标签**和**每个 `translatePlayer` 调用静默 no-op（显示原始 key / 原始 CJK 名）——计划在哪接线？验收 #5（按译名显示）要求 kiosk 新 `LiveMatchPage` 复刻 Galaxy 的 `translatePlayer` 调用（Galaxy LiveMatchPage.tsx:122）并触发 `loadLiveTranslations`——计划是否涵盖？
- **[minor] 新增 kiosk 文案的 key。** 计划列举**零**个新 i18n key。kiosk 专属串（「进入对局/观看复盘」、竖屏标签、「清空」、tooltip→常驻标签）是否都映射到既有 key，还是需要计划未列出的新 `.po` 条目（`i18n.py -todo` 会 flag）？`MatchList.tsx` 还硬编码中文串（「加载失败/正在直播/历史直播/暂无比赛」40,69-70,76）绕过 i18n——提升进 kiosk 后英文 UI 下违反 F14/§5.5；计划是否假设被提升组件「本地化完整」？

### F. 范围、阶段与可测性

- **[major] P5 过度打包 + 竖屏是 de-facto blocker。** P5 一个 commit 内：4 开关 + AiAnalysis + TrendChart + PlaybackBar + MatchInfo + aiMarkers/ownership useMemo + 音效 + 触屏 PV + 触屏试下 + tooltip→标签 + 竖屏堆叠——近乎整页重写（复刻 Galaxy LiveMatchPage 256 行）外加全新触屏逻辑。同时 P5 把竖屏堆叠声明为「先出 Q3 mockup」却又「先做横屏、竖屏占位」（plan.md:300）。但目标 kiosk **多为竖屏**（PRD Q3），且 Galaxy 右栏是 `width:500` 固定列、`xs` 隐藏（LivePage.tsx:107-111）——在竖屏 kiosk 上**根本不显示**。问：P5 是否应拆分（触屏适配 vs 布局/组件接线 各自可测）？竖屏是否其实是 P5 验收的 **blocker** 而非 P6 polish？有人确认过被提升组件（固定 500px 侧栏、AiAnalysis 内 height:150 滚动面板）能在 kiosk 窄/竖屏视口渲染吗，还是「复用」假设了 kiosk 显示不出的桌面布局？
- **[major] 阶段次序与独立可提交性。** 计划称 P1 自包含、P2 依赖 P1、P3 正交但 P4/P5 依赖 P3。但 P2 把**两个无关改动**（D1 基址 + D5 gate）捆在一个 commit；gate 的端到端测试需要 P1 的 analysis 代理，而其单测（mock LiveAPI）不需要——P2 验收 #「kiosk 不再 503」**偷偷**要求 P1 已合并。问：D5 gate（跨切、影响 Galaxy）是否应从 P2 拆成独立 commit？P3 是 `git mv` + 重写 Galaxy 页 import——P4/P5 依赖移动后的文件后，**单独 revert P3** 是否还干净（plan.md:35,352 的回滚承诺是否成立）？
- **[major] 验收标准的客观性。** 多条验收主观或仅手动：#3「行为与 Galaxy 一致」无 oracle；#4「纯触摸可用」手动；#9 靠 DevTools；#2「curl 8 端点与上游一致」需活上游 + 真实 match_id（plan.md:177），不在 pytest 内、CI 只 grep dist。问：#3 的可自动化 oracle 是什么？#2 是否有录制/fixtured 契约测试还是只能手动一次性？#4 是否有 Playwright 触屏模拟（pointer/hasTouch）？P1 验收说「`uv run pytest tests`（若有 board 代理测试）」——**承认可能一个都没有**：6 个新端点是否要求新测试，还是可零后端测试 land？

---

## 需独立对照代码核实的断言

逐条对照真实代码确认（这些是计划自述，可能与代码不符）：

1. **gate 条件 `analyzed_moves.length < move_count`**（plan.md:204,222；prd.md:21,237）。核实：analysis 按 position `0..move_count` **闭区间** keying（analysis_repo.py:281；move 0 被分析 analyzer.py:378；新手入队 poller.py:376）⇒ 追平局 `Object.keys(analysis).length == move_count+1`，严格 `<` off-by-one+。
2. **`/matches/{id}` 需 `fetch_detail` 才返回 moves**（prd.md:176）。核实：上游 `get_match`（live.py:264-297）**无** `fetch_detail` 参数、**无条件**返回 `moves`+`sgf`（service.py 同）⇒ 该透传可能是 no-op、前提错误。
3. **「唯一浪费是重型分析传输」（prd.md:104），暗示 match-detail 轻。** 核实：`useLiveMatch` 默认 `fetchDetail=true`（useLiveMatch.ts:21），`MatchDetail` 含 `sgf`+`moves[]`（types/live.ts:28-31）⇒ 每 tick 重传 SGF+moves；`fetchDetail=false` 优化被显式推迟（plan.md:248）。
4. **`move_count`/`analyzed_moves` 是可靠 freshness 信号（prd.md:106,R8）。** 核实：`get_successful_analysis` 只返回 `status==SUCCESS` 行（analysis_repo.py:127-134）⇒ dict 稀疏、length≠连续覆盖；FAILED（analysis_repo.py:252）造永久洞。
5. **`(winrate,score)` delta 触发器是可选（plan.md:229；prd.md:241）。** 核实：分析器可 `update_analysis_result` 就地覆盖（analysis_repo.py:192-227）⇒ count-gate 永不重拉就地更新 ⇒ 该触发器实为正确性必需。
6. **gate 对 Galaxy「透明」（prd.md:21,279）。** 核实：gate 在共享 `useLiveMatch.ts`，Galaxy 同样调用、无 options；Galaxy 当前每 tick 无条件拉 analysis（useLiveMatch.ts:95）⇒ 加 gate 后行为变化。
7. **FastAPI 路由顺序**：`board.py` 现声明 `/live/matches`（:121）→ `/live/matches/{match_id}`（:138）；`featured` 必须插在 `{match_id}` **之前**（计划 plan.md:166 警告但骨架排在其后）；上游 `live.py` `featured`（:210）在 `{match_id}`（:264）之前。
8. **上游 live 读端点免鉴权**：均 `Depends(get_live_service)`、`/translations` 无 auth（live.py:447）；只有写（comments live.py:571,620、translations/learn :701）需 `get_current_user`。`RemoteAPIClient._request` 默认 `auth=True`、board token 来自可选 refresh token（server.py:280-282）可能缺失。
9. **无 `/refresh` 上游路由**，但 `LiveAPI.refresh()` POST `/refresh`（api/live.ts:170）；基址翻转后指向不存在的 board 路由。
10. **`MatchCard.tsx:43` 无 onSelect 分支 `navigate('/galaxy/live/${id}')`**，kiosk router 无 `/galaxy/*`（KioskApp.tsx）。
11. **`galaxy/pages/report/{ReportDetailPage,ReportsPage}.tsx` 及其 `*.test.tsx` 的 `vi.mock` 也消费被移动组件**，不在 P3 修复清单内。
12. **`verify-kiosk.sh` 仅 grep `THREE./three/@react-three`**，不查 galaxy 路由串或 `/api/v1/live` 基址泄漏。
13. **`AiAnalysis` 仅经 `onMoveHover`（onMouseEnter/Leave，AiAnalysis.tsx:222-223）暴露 PV，无任何 click/touch 事件**（grep 零）⇒ 页面层 tap 适配的前提不成立。
14. **kiosk 页面测试全 mock `useLiveMatch`/`useLiveMatches`**（LiveMatchPage.test.tsx:12-14、LivePage.test.tsx:8-10）⇒ gate 不被页面测试触达。
15. **kiosk 现今零调用 `i18n.translatePlayer/translateTournament`**（grep 零）⇒ 名翻译是全新接线；许多 `live:*` 是无兜底裸 key（i18n.ts:52-53 miss 时返回原 key）。
16. **路由/导航已存在**：navTabs（navTabs.tsx:25）、KioskApp `live`/`live/:matchId`（KioskApp.tsx:73-74）——路由接线非新工作。
17. **`LiveBoard` 支持全套 props**（LiveBoard.tsx:25-47,300-319：pvMoves/aiMarkers/ownership/tryMoves/onTryMove/boardSize），但 `parseMove` 硬编码 19×19（LiveBoard.tsx:66）；`onTryMove` 激活时 `handleClick` 早退（LiveBoard.tsx:710-714）。

## 可能的缺口

1. **未定义「正确的 caught-up 判定」**——裸 count 比较；需 position-aware 谓词（如「最新 position `move_count` 是否已分析」）。
2. **未处理永久 FAILED 的冻结洞**——count-gate 把 `length==move_count` 当完成、永久 strand 缺口且 UI 无提示。
3. **未处理就地重分析**——被推迟的 delta 触发器是唯一机制却划出本期。
4. **live→finished 无 catch-up 拉取**——可能冻结在不完整分析、kiosk 无手动刷新。
5. **`fetchMatch(fetchDetail=true)` 每 tick 重负载被承认但推迟**——头条降本目标只部分达成；无「稳态总字节下降」验收测试。
6. **5 个 TDD case 可建模理想连续 key 集**，掩盖 off-by-one 与稀疏洞；无 case 建模真实 key 集。
7. **无 Galaxy 新鲜度保持的显式断言**。
8. **`fetchMatch` 在 poll-effect deps（随 currentMove 重建）可能 churn interval**；未处理包 ref/稳定化。
9. **`MatchCard` 硬编码 galaxy 路由未被识别为跨构建 hazard**；kiosk 必须永远传 `onSelect` 的契约未明说、无闸门。
10. **P3 import 修复 + 验证漏掉 report 页及 4 处测试 mock**——风险是 full 构建破裂 + `vi.mock` 静默失效（假绿）。
11. **无验证步骤 grep kiosk dist 的 `/galaxy/` 或 `/api/v1/live`**；「verify 绿」高估边界安全。
12. **共享 bundle 仍含指向未代理 board 路径的 comment/refresh 方法**——靠约定而非构造。
13. **触屏 tap 预览可能逼迫改 `AiAnalysis`**（onClick/onMoveSelect）——计划否认的共享组件改动，重开 Galaxy 回归；无 hover-on-touch 不可靠时的 fallback 设计。
14. **试下合法性/吃子/打劫/轮次未定义（Q5）**；F12/验收 #4 要求触屏可用而 LiveBoard 试下仅渲染、无规则。
15. **kiosk i18n 启动接线未确认**（`loadTranslations/loadLiveTranslations` 是否在 kiosk bootstrap 调用）；无新 key 枚举——风险是显示字面 `live:xxx` 与未翻译 CJK 名。
16. **错误状态保真度**——全塌 502，上游 404「match 不存在」变「server unavailable」，破坏 §5.8。
17. **竖屏布局推迟到 P6 而目标设备竖屏为主**——P5 可能在真机不可演示/不可接受，把疑似 blocker 当 polish。
18. **P3 单 commit 回滚**在 P4/P5 依赖移动后文件后不成立。
19. **被提升的桌面向组件（固定 500px 侧栏、隐藏于 xs 的列）如何适配 kiosk 窄/竖屏**——「复用」可能需未涵盖的重新样式化。
20. **代理无缓存/去重**：两个 kiosk tab 或一次 reload 各自经 board 重拉全量 analysis，零服务端复用；gate 纯客户端。

---

## 期望的产出格式

请返回以下四部分，**全部要证据、不要观点**（每条结论附 `file:line`，凭空推断标注「需代码核实」）：

**(a) 按严重度排序的问题清单。** 每条含：`[blocker]/[major]/[minor]` + 一句话问题陈述 + `file:line` 证据（对照真实代码，不是计划自述）+ **具体修复建议**（改哪个文件、改成什么）。特别请定论这两个争议点：
- gate 的 `< move_count` 在 `0..move_count` 闭区间 + 稀疏/FAILED key 集下，**是否真的会停在最新一手之前一格 / 永远停不下来**——给出你走查 key 集的推导。
- 上游 `get_match`（live.py:264-297）**是否真的无 `fetch_detail` 且无条件返回 moves**——若是，计划的 `fetch_detail` 透传是否应整体删除。
- `AiAnalysis` 是否**真的无法**在不改组件的前提下做 tap 预览——若必须改，这是否违反 R6。

**(b) 逐阶段裁决（P1–P6）：** 每阶段给 **go / needs-changes / no-go** + 一句话门槛（哪个未解问题阻塞该阶段）。

**(c) 你会标记的单一最大风险**（the one thing）+ 若忽略它的后果。

**(d) 范围判断：** 哪些被**过度设计/超范围**（可砍），哪些被**欠设计/漏范围**（必须补进本期，尤其被划为「可选」但实为正确性必需的项：delta 触发器、`fetchDetail=false`、Galaxy 回归测试、kiosk i18n 接线、触屏 PV 的真实方案）。
