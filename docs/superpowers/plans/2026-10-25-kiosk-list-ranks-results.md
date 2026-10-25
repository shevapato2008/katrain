# Kiosk List Historical Ranks and Result Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在 Kiosk 职业棋谱和个人复盘历史卡片中镜像展示真实历史段位，并统一结果的视觉中心和中盘胜中文语序。

**Architecture:** 沿用现有分页返回的历史段位字段，不查询当前账号段位、不额外逐卡请求SGF、不改数据库。以一个仅供这两页使用的无交互名单行组件统一 `[黑子][左姓名][辅助段位] | [结果] | [辅助段位][右姓名][白子]`；卡片外框、高度、点击/选择/删除及报告操作保持。结果只在 Kiosk 列表展示层保守处理明确认输/中盘，其余交给既有 formatter，避免改 Galaxy 或数据库。

**Tech Stack:** React/TypeScript、现有 CSS / KioskTypographyProvider、Vitest、Playwright真实1024×600预览；已有 FastAPI/SQLAlchemy列表合同不变。

---

## Chunk 1: 一个列表卡片旅程

### 已确认的源与参考

- 基线 `origin/develop=209476bd8ce500936cf2eb1e0276c30cec889edc`，含弹窗字体修复。隔离 worktree `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/kiosk-list-player-ranks-20261025`，分支 `fix/kiosk-list-player-ranks-20261025`。
- `KifuPage.tsx` 已按用户所需镜像顺序放置 `<small>`，但只判断 `display_black_rank/display_white_rank`。`KifuAlbumSummary` 同时已有 `black_rank/white_rank`，服务端 `_summary()` 的 `parse_player` 从本谱原始列或明确嵌入段位产生 display 字段。保持已确认 display 优先，空缺时用同一条记录原始 rank，绝不按姓名猜。
- `ReportsPage.tsx::ReviewRow` 只渲染姓名，没有使用已存在的 `UserGameSummary.black_rank/white_rank`。`UserGameRepository._to_dict` 已输出这两项；dispatcher 在线原样转发中央分页、离线本地分页。录谱路径 `_record_ai_game_locked` 保存当局 rank；不读当前账号或当前 AI 配置替代历史。
- 已在原登录页只读核实中央分页200：职业最新3条raw=null/display空；个人历史authority=cloud，其中AI当局white_rank=6k，另一些当局为空。这是客观源缺失与漏渲染的区别，不保证UI回退能补出不存在的源。历史列没有等级时显示克制的辅助 `—` 并给出 `等级未记录` 的可访问说明，不宣称确定等级。另以列表自带首条preview通过SGF parser确认BR/WR本身也缺失，RE为B+R；不把缺失源误归咎于前端。原谱有而列表列未存的旧记录本轮不批量回写，也不对整页新增详情下载；选中记录现有详情/SGF只用于原预览，不把它错贴到其他卡片。若有限真实抽样发现已有必要字段在实际中央响应被漏传，先报告具体依赖、调整最小合同后复核，不能假定云已支持。
- 视觉参考是现有 Kifu 卡片结果：18px 辅助字级、居中边框圆角、透明底/原有文字色。复盘当前独立 `<em>` 无同样容器且继承排版不一致；共享行消除两套样式，真实测量结果容器与两侧棋手行的 centerY，容差≤1px。不是相对整张含标题卡片的中心。
- 通用 `translateResult` 在中文将 `白胜` 与 `中盘` 拼成“白胜中盘”；历史 `historyResult` 又泛化搬动“胜”之后的所有文本，可能错误改动数目结果。新 helper 仅给这两页使用；不全局替换词序、不改通用翻译/其他语言结果规则。

### Task 1: 最小列表展示 helper

**Files:**
- Create: `katrain/web/ui/src/kiosk/utils/listRecordPresentation.ts`
- Create: `katrain/web/ui/src/kiosk/utils/listRecordPresentation.test.ts`
- Existing references only: `src/utils/rank.ts`, `src/utils/resultTranslation.ts`, `kiosk/components/report/reviewPresentation.ts`

- [x] **Step 1:** 写聚焦红测试：rank 使用非空 display、再同记录 raw、无值为未知；`9p→职业9段`、`9d→9段`、`6k→6级`沿用 `formatRank`。不使用账号信息或根据姓名补等级。
- [x] **Step 2:** 写结果红测试，接口建议 `listResult(raw,t,rules,lang): { label: string; winner: 'B'|'W'|null }`，标签与赢家同一窄规则产生：中文 `W+R/B+Resign`、明确“白中盘胜/白胜中盘”→“白中盘胜”；明确“白认输”表示黑中盘胜。只匹配完整明确形式，不把 `W+T/W+F`、数字、Draw/0、Void/?、空值/进行中误判为中盘。英文/其他语言保持既有 `translateResult` 行为；简/繁中文的“中盘/中盤、胜/勝”使用既有翻译词或明确相应模板。
- [x] **Step 3:** Run `npm test -- src/kiosk/utils/listRecordPresentation.test.ts`，确认新增断言先失败；实现小型纯 helper，让测试通过。数字结果继续复用原规则单位，不使用旧泛化“胜后全搬前”逻辑。Reports先保留现有按source区分的空结果和Void分支，才对其他非空结果调用helper；未知/Draw/Void没有赢家。同步更新本次直接改变的旧“黑6.5子胜”测试预期到Kifu规范“黑胜6.5子”，不能把它当作无关基线失败跳过。
- [x] **Step 4:** 实施者自查规格、质量、提交。负责人核实该任务满足源语义，再交下一任务；最终独立 Astra 先复核规格再复核质量/视觉。

### Task 2: 两页共用镜像名单/结果行

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/records/RecordMatchLine.tsx`
- Create: `katrain/web/ui/src/kiosk/components/records/recordMatchLine.css`
- Modify: `katrain/web/ui/src/kiosk/pages/KifuPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx`
- Modify only conflicting match-line selectors: `kiosk/pages/kifuLibrary.css`, `kiosk/pages/personalGamesReviewed.css`
- Test: existing `kiosk/pages/KifuPage.test.tsx`, `kiosk/pages/ReportsPage.test.tsx`; new focused `RecordMatchLine.test.tsx` if page coverage cannot clearly assert order.

- [x] **Step 1:** 写最少必要断言：两页已知rank均可见，左名字后/右名字前，未知不会猜值；补“白认输→黑中盘胜且仅黑方高亮”、未知结果无赢家断言；整行不是额外交互控件，卡片选中、原删除按钮逻辑不变。覆盖长中文/英文、职业/业余/级位，不给列表逐卡增加 fetch。
- [x] **Step 2:** 纯展示组件使用grid `minmax(0,1fr) auto minmax(0,1fr)`、统一 `align-items:center`；每侧flex `min-width:0`，name独立ellipsis+完整辅助名称，rank `flex-shrink:0`、18px辅助色并给自由文本简单max-width/ellipsis及完整辅助说明，确保姓名仍有可见开头；结果保留原126px宽度上限，stone原有黑白语义。左侧石/名/rank，右侧rank/名/石；结果容器复用Kifu边框/圆角/配色/排版，`display:flex;align-items:center;justify-content:center`，保持结果完整可读，长未知原文可ellipsis+完整辅助描述。姓名保留既有各页主字号(职业22px/历史20px)，段位18px且整体继承全局字体与2/4px字号阶差，不固定11px、不新设字体、不加字体fixed标记。纯“—”不被hasOwnText扫描，rank元素应显式沿用现有data-kiosk-base-size/--kiosk-base-size=18px契约（或同等局部CSS随size-step方式），不修改全局扫描机制；已知与未知都在large/small下实际测量18→14px。
- [x] **Step 3:** Kifu通过 `displayRank || rawRank` helper取本条历史字段；Reports只取本条black_rank/white_rank。两页胜负非数目归类只识别已明确的原始格式，Kifu既有winner高亮取helper解析结果，删除旧首字符推断，避免“白认输”反而高亮白方。没有可判定winner不凭标签猜。Reports空结果沿用source相关unfinished/未记结果、Void沿用无胜负分支和详细辅助说明，只有其他非空结果交公共helper，避免把未完成/未判定讲成胜负。
- [x] **Step 4:** Run `npm test -- src/kiosk/utils/listRecordPresentation.test.ts src/kiosk/pages/KifuPage.test.tsx src/kiosk/pages/ReportsPage.test.tsx src/kiosk/pages/ReportsPage.polling.test.tsx src/kiosk/__tests__/KifuPage.localization.test.tsx`（以及新组件测试）；`npx tsc -b --pretty false`。只修本次回归，基线失败分开记录。
- [x] **Step 5:** 在隔离浏览器fixture真实React预览1024×600，所有fixture仅测试浏览器路由，不进入生产：一页代表已知/未知、长中英文、9p/9d/6k、R/T/F/数字；同viewport保留旧Kifu参照、两页修改前后、并排和叠加/差异。字体加载稳定后记录name/rank字号、大/小字号两档（分别测已知与未知段位18/14px）及一个非默认中文字体、centerY偏差、card高度、删除/选择/分页可操作及无横向溢出。不批量重拍其他页面或开启付费报告/真实删除。
- [x] **Step 6:** 删除/隔离fixture（生产仅纯组件与helper），实施者自查并提交。负责人集成核实，两页视觉达到同一结果表现；最后独立fresh Astra Max按固定代码SHA先规格/源、后代码质量/实际截图与交互评审，修正直到Approved。

### Task 3: 集成与定向 RK 发布

- [x] 独立 Astra Max（gpt-6-astra/max，无历史fork）先审核本计划，修改最多两轮；获批才开始上述产品实现。
- [x] 与弹窗字体发布负责人协调，不并发写develop/Smartboxmain/RK。fetch真正最新develop→合入feature，解决冲突并验证本切片→commit/push feature→合入/push develop。
- [x] Smartbox最新main的隔离worktree只更新vendor/katrain到**published develop的实际完整SHA**，commit/push main；不手猜SHA、不force、不覆盖其他改动。
- [x] 使用最新已验证RK发布脚本，从干净published develop导出全部受控Python、19路policy和同源full/strict产物；备份SQLite/旧代码/静态、动态保护配置/身份/模型/标定/字体；即时核实用户原URL及真实活跃棋局，不能重启活跃真实棋局。只定向重启围棋服务，不跑整机provision。
- [x] 验证实际进程SHA、入口资源哈希、服务与保护状态；必要时走真实主页→围棋恢复原账号与原URL，不读/注入cookie。有限读取现有分页/选中详情确认真实源，无全库扫描、批量历史写入、N+1下载或新建报告/棋局。
- [x] 若真实中央合同缺字段，给主session明确最小云端依赖再执行适当授权范围；不能把fixture或仅RK发布说成真实中央数据已恢复。
- [x] 汇报published两个repo提交、RK进程/入口、最终Astra结论、两页前后图、真实等级例子及客观缺失/实机验收边界；保留回滚并清理本次上传候选。
