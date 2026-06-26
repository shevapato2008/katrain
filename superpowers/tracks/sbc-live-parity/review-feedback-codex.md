# Plan Review — sbc-live-parity

**Verdict:** Needs rework

本轮计划已经修正了原始 prompt 里的若干硬伤：`fetch_detail` 透传应删除、`featured` 路由顺序要提前、`AiAnalysis` 触屏 PV 必须改共享组件、report 页 import/mock 也要纳入 P3。这些方向基本正确。但计划仍有几处会让执行者按文档落地后得到错误行为，尤其是 freshness gate 仍在观察错误的新鲜度信号。

## (a) 问题清单

### [blocker] gate 的“tip 就地重分析”触发器观察的是错误字段，无法检测 KataGo 分析更新

计划把 delta 触发器定义为 `current_winrate/current_score` 变化（`superpowers/tracks/sbc-live-parity/plan.md:198-201`）。真实代码里这两个字段来自直播源，不是本地 KataGo 分析：`LiveMatch.current_winrate/current_score` 注释为 XingZhen 来源，而 `katago_winrate/katago_score` 是单独字段（`katrain/web/live/models.py:79-82`）。分析器完成最新手时写的是 `katago_winrate/katago_score`（`katrain/web/live/analysis_repo.py:97-98`），但 live API 响应只返回 `current_winrate/current_score`（`katrain/web/api/v1/endpoints/live.py:288-290`），前端类型也只有这两个字段（`katrain/web/ui/src/types/live.ts:18-20`）。

后果：即使 `update_analysis_result` 覆盖同一个 analysis key（`katrain/web/live/analysis_repo.py:192-227`），P2 gate 也看不到任何 summary 字段变化；Galaxy 和 kiosk 都会在“追平”后漏掉就地重分析。

**修复建议**：不要用 `current_winrate/current_score` 作为 analysis freshness 信号。新增并暴露一个真实的轻量信号，例如 `analysis_updated_at`、`latest_analysis_revision`、`katago_winrate/katago_score`，或 `/analysis/meta`；P2 gate 用该信号触发 `getMatchAnalysis`。如果本期不加服务端信号，就不能承诺就地重分析正确性。

### [blocker] P1 的 404 透传验收按计划执行会失败

计划新增 `_proxy`，但又写“现有 `proxy_live_matches` / `proxy_live_match` 不改逻辑”（`superpowers/tracks/sbc-live-parity/plan.md:158`），同时验收要求 `board/live/matches/__nope__` 返回 404（`superpowers/tracks/sbc-live-parity/plan.md:171`）。真实 `proxy_live_match` 仍然 `except Exception -> 502`（`katrain/web/api/v1/endpoints/board.py:138-146`），而 `RemoteAPIClient.get_live_match` 会 `raise_for_status()`（`katrain/web/core/remote_client.py:220-223`）。

后果：缺失 match 仍会被 board 代理压成 502，P1 验收不可能通过，断网/不存在的 UX 语义仍混在一起。

**修复建议**：P1 必须把现有 `proxy_live_matches` 和 `proxy_live_match` 也迁到 `_proxy`，不是“可选顺手”。后端测试要覆盖三条：existing detail 404 透传、matches 列表上游 4xx/5xx 行为、连接失败映射 502。

### [blocker] no-progress 兜底的代码骨架不会在 `move_count/currentMove` 变化时恢复

计划文字说 no-progress 暂停直到 `move_count` 或 `currentMove` 变化（`superpowers/tracks/sbc-live-parity/plan.md:203`），但骨架只在 `Object.keys(a).length` 变化时重置 `staleRef`（`superpowers/tracks/sbc-live-parity/plan.md:222-225`）。真实 analysis 只返回 `SUCCESS` 行（`katrain/web/live/analysis_repo.py:127-134`），永久失败会进入 `FAILED` 且不再出现在返回 map 里（`katrain/web/live/analysis_repo.py:252-254`）。

后果：某个 tip 永久失败并耗尽 6 次后，如果下一手到来但 key 数还没增长，`staleRef.streak` 仍然 exhausted，新 tip 也可能不再拉 analysis。

**修复建议**：`staleRef` 里同时记录 `keyCount`、`moveCount`、`currentMove`。任一变化都清零 streak。测试里加入“FAILED tip 耗尽后，新手到来恢复拉取”的 case。

### [major] P4 列表页预览会无条件拉整局 analysis

P4 计划用 `useLiveMatch` 获取选中局详情用于棋盘预览（`superpowers/tracks/sbc-live-parity/plan.md:293-298`）。真实 hook 初次加载总会 `fetchAnalysis(true)`（`katrain/web/ui/src/hooks/live/useLiveMatch.ts:77-83`），而 `preloadAnalysis` 返回整局 analysis map（`katrain/web/ui/src/api/live.ts:125-131`；后端响应包含 `analysis` 全量，`katrain/web/api/v1/endpoints/live.py:349-354`）。列表预览只需要 `moves/currentMove` 和回放条，不需要 AI analysis。

后果：进入 `/kiosk/live` 或切换选中卡片就会拉重型 analysis，直接削弱 PRD §1.3 的“消除重复重型 analysis 传输”目标（`superpowers/tracks/sbc-live-parity/prd.md:100-104`）。

**修复建议**：给 hook 增加 `analysisMode?: 'none' | 'preload' | 'poll'` 或 `preloadAnalysis?: boolean`。P4 预览用 `none`，P5 详情页才 preload/poll。对应测试断言列表页选中预览不调用 `LiveAPI.preloadAnalysis/getMatchAnalysis`。

### [major] tip fingerprint baseline 从未在追平初始态初始化

骨架中 `lastTipRef` 初始为 `null`（`superpowers/tracks/sbc-live-parity/plan.md:209`），`tipChanged` 在 `lastTipRef.current !== null` 时才成立（`superpowers/tracks/sbc-live-parity/plan.md:220-221`），且只在决定拉 analysis 时写入 baseline（`superpowers/tracks/sbc-live-parity/plan.md:226-229`）。真实 hook 初次加载会先 `fetchMatch()` 和 `fetchAnalysis(true)`（`katrain/web/ui/src/hooks/live/useLiveMatch.ts:77-83`），如果初始就是 caught-up，后续 tick 不会进入写 baseline 的分支。

后果：即便第一个问题改成了真实 freshness 字段，初始追平状态下的第一次 metadata 变化也可能永远不会触发 analysis 重拉。

**修复建议**：在初次 match+analysis 完成后初始化 baseline；或在每次 tick 发现 caught-up 且 baseline 为空时写入 baseline。加测试：初始 caught-up 后，metadata 第一次变化触发一次 `getMatchAnalysis`。

### [major] P2 骨架没有处理现有 `currentMove` 的 nullable 状态

真实 hook 内部 `currentMove` 是 `number | null`，用 `null` 表示尚未初始化（`katrain/web/ui/src/hooks/live/useLiveMatch.ts:26-27`）。计划骨架直接做 `cm >= 0 && a[cm] == null`（`superpowers/tracks/sbc-live-parity/plan.md:215-219`）。在 JavaScript 中 `null >= 0` 为 true，`a[null]` 会访问 `"null"` 键。

后果：首次加载/切 match 的短窗口可能误判 viewed pending，导致不必要的 analysis 请求，测试若只传 number 会漏掉。

**修复建议**：ref 里存 `effectiveCurrentMove`，或显式 `cm !== null && cm >= 0`。TDD case 要覆盖 `currentMoveInternal === null` 的初始状态。

### [major] P2 测试验收低于自己列出的风险

计划列了 8 个 hook case（`superpowers/tracks/sbc-live-parity/plan.md:237-245`），但验收只要求“新 `useLiveMatch.test.ts` 5 用例绿”（`superpowers/tracks/sbc-live-parity/plan.md:250-251`）。被挤掉的往往正是最危险的情况：FAILED 洞、就地更新、历史查看、非 live、live→finished catch-up。

**修复建议**：验收必须明确 8 个 case 全部落地，再额外加上述 baseline、no-progress reset、nullable currentMove、list preview no-analysis case。不要用“5 case”作为门槛。

### [major] PRD 仍保留与计划相反的旧要求

计划 P1 要求 4xx 透传（`superpowers/tracks/sbc-live-parity/plan.md:109-123`），但 PRD §4.1 仍写“失败统一 502”（`superpowers/tracks/sbc-live-parity/prd.md:160-163`）。计划 P3 已补 report 页和测试 mock（`superpowers/tracks/sbc-live-parity/plan.md:271-274`），但 PRD §4.3/风险表仍只说更新两个 Galaxy live 页面（`superpowers/tracks/sbc-live-parity/prd.md:194-197`、`superpowers/tracks/sbc-live-parity/prd.md:271-273`）。

后果：计划开头又声明 PRD 是权威来源（`superpowers/tracks/sbc-live-parity/plan.md:6`），执行者会遇到互相矛盾的指令。

**修复建议**：先同步 PRD：错误语义改为“4xx 透传、连接失败 502”；P3 消费者清单加入 report 页和 `vi.mock`；风险 R2 改成“所有消费者”而不是“2 个页面”。

### [major] P5 把未决 Q5 当作可执行验收项

PRD 要求试下模式可触屏落子（`superpowers/tracks/sbc-live-parity/prd.md:149-150`、`superpowers/tracks/sbc-live-parity/prd.md:256-258`），但 Q5 仍未定义“是否提子校验/是否合法/是否复用现有 try 逻辑”（`superpowers/tracks/sbc-live-parity/prd.md:289-290`；计划也保留开放，`superpowers/tracks/sbc-live-parity/plan.md:380-382`）。真实 `LiveBoard` 的 try 模式只是把点击坐标回调出去（`katrain/web/ui/src/components/live/LiveBoard.tsx:708-714`），渲染时只在空点画半透明子（`katrain/web/ui/src/components/live/LiveBoard.tsx:491-505`），没有规则、提子、打劫或轮次校验。

后果：P5 “F12 达标”没有客观定义，执行者可能交付一个只能叠 ghost stone 的试下模式，而用户期待的是可用的试下。

**修复建议**：P5 前关闭 Q5。若本期只要求“无规则 ghost variation”，就把 PRD/F12/验收改成这个定义；若要求真实试下，计划必须引入规则引擎或复用现有棋局逻辑，并加测试。

### [major] P5 新增共享 `AiAnalysis.onMoveSelect` 缺少具体测试门槛

真实 `AiAnalysis` 目前只通过 `onMouseEnter/onMouseLeave` 暴露 PV（`katrain/web/ui/src/galaxy/components/live/AiAnalysis.tsx:222-223`），计划改成 opt-in `onMoveSelect`（`superpowers/tracks/sbc-live-parity/plan.md:317-322`）。这是共享组件行为扩展，影响 Galaxy/report 消费者的组件边界。

**修复建议**：P5 明确新增组件测试：不传 `onMoveSelect` 时 hover 行为保持；传入时 click/pointer 触发 PV；重复点击/外部清空能清 PV；Galaxy 页面不传该 prop。仅写“npm test 绿”（`superpowers/tracks/sbc-live-parity/plan.md:326`）不够。

### [major] i18n 收尾不够具体，提升组件里已有裸中文/英文错误串

计划 P6 只说“复用 `live:*` key；新增文案用 `t()`”（`superpowers/tracks/sbc-live-parity/plan.md:331-334`）。真实待提升组件里仍有硬编码中文：`MatchList` 错误态、Tab、空态分别在 `katrain/web/ui/src/galaxy/components/live/MatchList.tsx:39-40`、`katrain/web/ui/src/galaxy/components/live/MatchList.tsx:69-76`；`UpcomingList` 错误态是英文 literal（`katrain/web/ui/src/galaxy/components/live/UpcomingList.tsx:35`、`katrain/web/ui/src/galaxy/components/live/UpcomingList.tsx:84-88`）。

已核实 kiosk 启动链路会经 `SettingsProvider` 调 `i18n.loadTranslations()`（`katrain/web/ui/src/AppRouter.tsx:28-43`；`katrain/web/ui/src/context/SettingsContext.tsx:72-80`），且会连带 `loadLiveTranslations()`（`katrain/web/ui/src/i18n.ts:20-27`），所以“完全不加载译表”不是当前主要问题。主要问题是被复用组件自身还没完全本地化。

**修复建议**：P3 或 P6 加明确清单，把 `MatchList`、`UpcomingList`、source label 等裸字符串全部迁到 `t()`/`live:*`，并加英文语言下不出现中文 Tab/空态的测试。

### [minor] `verify:kiosk-2d` 仍只证明 three.js，不证明路由/API 字符串边界

计划 P3 验收要求 kiosk dist 无 `/galaxy/`（`superpowers/tracks/sbc-live-parity/plan.md:282-284`），但当前脚本只 grep `THREE.`、`three`、`@react-three`（`katrain/web/ui/scripts/verify-kiosk.sh:15-27`）。ESLint 也只限制 import，不限制字符串路由（`katrain/web/ui/eslint.config.js:49-52`）。

**修复建议**：把 `/galaxy/` 和非预期 `/api/v1/live` 的 dist grep 纳入 `verify-kiosk.sh`，否则这个验收容易被人工漏跑。

### [minor] “零写路径”仍靠约定而不是构造

`LiveAPI` 里仍保留 `refresh()`、comments create/delete 等写路径（`katrain/web/ui/src/api/live.ts:167-208`）。计划说保留、不调用（`superpowers/tracks/sbc-live-parity/plan.md:192`），而 PRD 非目标明确 board 不做写操作（`superpowers/tracks/sbc-live-parity/prd.md:122-127`）。

**修复建议**：把 read-only live API 和 Galaxy write/comment API 拆开；或在 kiosk build 下让写方法抛出明确错误并加测试。这样 D4 不是靠调用约定维持。

## 已核实的关键争议点

- `get_match` 的确没有 `fetch_detail` 参数，且无条件返回 `sgf`/`moves`（`katrain/web/api/v1/endpoints/live.py:264-297`）。删除后端 `fetch_detail` 透传是正确方向。
- analysis key 的确是 position `0..move_count` 闭区间：未分析集合用 `range(max_move + 1)`（`katrain/web/live/analysis_repo.py:273-281`），新手调度也用 `range(old_move_count, new_move_count + 1)`（`katrain/web/live/poller.py:375-383`）。计划从裸 count 改成 position-aware 是正确方向。
- `preload_analysis` 在当前 `LiveService` 中是 read-only，只返回 successful analysis（`katrain/web/live/service.py:135-141`）。live endpoint 注释“boosts priority”（`katrain/web/api/v1/endpoints/live.py:337-347`）已经过时。
- `AiAnalysis` 目前确实没有 click/touch/pointer 选择事件，只有 mouse enter/leave（`katrain/web/ui/src/galaxy/components/live/AiAnalysis.tsx:222-223`）。计划改为 opt-in `onMoveSelect` 是必要修正，不是可选增强。

## (b) 逐阶段裁决

- **P0 — go**：基线步骤合理。
- **P1 — no-go until changed**：必须把现有 `proxy_live_matches/proxy_live_match` 也迁到 `_proxy`，并同步 PRD 的错误语义。
- **P2 — no-go**：freshness gate 仍用错误字段检测就地重分析，且骨架有 no-progress reset、baseline、nullable currentMove 三个执行级漏洞。
- **P3 — needs-changes**：计划正文基本补齐 report 页和 `MatchCard` 路由，但 PRD 仍旧、verify 脚本未覆盖 `/galaxy/`/API base 泄漏。
- **P4 — no-go until hook option exists**：列表预览不能复用会自动 preload analysis 的 `useLiveMatch` 默认路径。
- **P5 — needs-changes**：`AiAnalysis` opt-in 方向正确，但必须补测试；Q5 试下规则和竖屏 mockup 在实现前要关闭。
- **P6 — needs-changes**：不能只当 polish；i18n 硬编码、verify 扩展、离线错误态需要可执行清单和测试。

## (c) 单一最大风险

**最大风险：freshness gate 以为自己有正确的新鲜度信号，但实际没有。**

如果忽略这一点，P2 会把 Galaxy 现有“每 tick 必拉 analysis”的强一致行为替换成“追平后停止观察”，而它观察的 `current_winrate/current_score` 又不是 KataGo analysis 的更新字段。结果是 kiosk 和 Galaxy 都可能静默显示旧 AI 推荐/趋势图，且没有错误提示。这比多拉一点 analysis 更危险。

## (d) 范围判断

**可砍/后移：**

- `/stats` 代理如果没有前端消费者，可以后移；当前计划没有说明 kiosk 哪个界面用它。
- `featured` 若 Q6 最终不用作默认选中，只保留代理覆盖即可，不要在 P4 额外引入默认逻辑复杂度。
- 共享 `LiveAPI` 的评论/refresh 写方法不应继续作为 kiosk bundle 的普通可调用方法；拆出去比继续解释“不会调用”更简单。

**必须补进本期：**

- 真实 analysis freshness metadata：`katago_*`、`analysis_updated_at` 或 revision；否则 delta 触发器不成立。
- `useLiveMatch` 的 analysis 加载模式开关，P4 预览禁用 analysis preload。
- P1 existing proxies 的状态保真改造。
- P2 完整测试门槛：position-aware、FAILED/no-progress、新手恢复、baseline、nullable currentMove、live→finished、Galaxy 回归。
- P5 前关闭 Q5，并明确试下到底是 ghost variation 还是合法落子模拟。
- P3/P6 的 i18n 硬编码修复和 kiosk dist 边界 verify 脚本扩展。
