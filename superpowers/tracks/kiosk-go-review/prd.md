# 围棋 kiosk · 复盘/报告 赛道 PRD(kiosk-go-review)

- 日期:2026-09-14
- 分支 / worktree:`feature/kiosk-go-review` @ `/Users/fan/Repositories/katrain-kiosk-go-review`(基于 develop `6f7dc629`)
- 输入:2026-09-14 三轮调研条目包 `kiosk-go-review.json`(R1 R2 R3 R5 R6 N7 N24 S1)
- 本文所有行号都已在本 worktree 源码上逐条核实过(2026-09-14);develop 此后到 `b50fb32b` 的提交没有碰 `katrain/web/ui/src`。

---

## 1. 背景与目标

复盘在盒上**已经能用了**:2026-09-13 的 `2c2034e0` 把复盘链的请求闸从 `token` 换成 `isAuthenticated` 之后,屏 19(复盘列表)能读到云端的对局与报告,屏 20(报告详情)能打开、五个分析 tab 与 galaxy 同源。剩下的问题有两类。一类是**说的话不对**:同一局棋在屏 19 和屏 20 上的「失误 / 妙手」数字对不上,因为两屏用的是两套判据;断网时屏 20 说「未找到复盘。」,下面还印着一段 `Request failed 503: {"detail":…}`。另一类是**一条路没走通**:从屏 20 点「去研究」,盒上打开的是一块空棋盘。

这一轮要让盒上用户得到三件事:
1. 屏 19、屏 20 两屏说同一套话。「失误 / 妙手」和胜率图上的红段,都用服务端七档判级。
2. 请求失败时,屏上说清是**连不上**、**找不到**还是**积分不足**,不再把后端原文印到屏上。
3. 复盘 → 研究这一步在盒上走得通(token 为 null、cookie 认证)。

## 2. 已经做完、不要动的

| 内容 | 出处 |
|---|---|
| 复盘链请求闸改判 `isAuthenticated`,包括 `useReportTasks`、`useReportDetail`、`ReportsPage` 的列表、预览、逐手几处 | `2c2034e0` |
| 屏 20「发挥水准」14 根柱高 | `6f7dc629` |
| 屏 20 五个 tab(走势 / 妙手 / 失误 / 发挥水准 / AI 吻合度),名字、顺序、图标都与 galaxy 对齐,数据来自共享的 `features/analysis/moveGrade.ts` | `156e38c7` |
| 七档判级在服务端做(真源 `katrain/core/move_grade.yaml`);旧报告缺 `grade` 时由 `GET /reports/{id}/moves` 按需补算(`_moves_with_grades`) | `6796fb87` |
| 屏 19 来源筛选、本地 / 棋谱库导入、删除确认、行的六种状态、「共 N 局 / 本机 N 局」按 `authority` 说 | `14ed1603` `aa4ed4d1` `2ba24189` 等 |
| 屏 20 耗时行、单开手风琴、显示开关的名字与图标对齐 galaxy | `72b8a09f` `156e38c7` |
| 让子局报告从空盘算的问题(cron SGF 解析) | `41549eb5` |

---

## 3. 需求条目(本轮做)

### S1 · 盒上从报告点「去研究」进来是空棋盘 —— P1

- **现象**:屏 20 点「去研究」(`ReportDetailPage.tsx:432`,全仓唯一带 `user_game_id` 进研究屏的入口),研究屏盘是空的,副标题不出现,也没有任何提示。
- **根因(已核实)**:`kiosk/pages/ResearchPage.tsx:440` 写的是 `if (!id || userGameRef.current || !token) return;`,`:134` 只取了 `token`。盒上严格 SSO 的 token 恒为 `null`,而依赖数组 `[searchParams, token]`(`:455`)里的 token 永远不变,所以也不会重试。下游 `UserGamesAPI.get` 接受 `null` token,认证靠 cookie(`api/userGamesApi.ts:96-122`)。取谱失败时的 `.catch` 只打 `console.error`(`:454`)。
- **期望**:已登录(`isAuthenticated`)就按 `?user_game_id` 取谱、载入棋盘、写出「我的对局:…」副标题。取谱失败时,副标题写「这一局读不到」,不留一块没有解释的空盘。返回键回到**这一份报告**(`/kiosk/report/{task}`)。
- **修通后会连带暴露的一处(已核实)**:这条 effect 写 provenance 时用的是 `backTo.path`(`BACK` 表里的报告**列表** `/kiosk/report`),而组件里已经算好了带 `task` 的 `backPath`(`:198-202`,屏 20 单测注释明写 `task` 是为了回到这一份报告)。盒上今天 provenance 恒为 null,返回键碰巧走的是 `backPath`;只改判别位的话,盒上「去研究 → 返回」会从回到报告退成回到列表。所以 provenance 一并改用 `backPath`。
- **验收**:
  1. 单测:`useAuth` 返回 `{ token: null, isAuthenticated: true }` 时,`UserGamesAPI.get` 以 `(null, 'g1')` 被调用,`loadFromSGF` 收到谱。
  2. 单测:`{ token: null, isAuthenticated: false }` 时不发请求。
  3. 单测:`get` 拒绝时,页控条副标题出现「这一局读不到」。
  4. 单测:`?user_game_id=g1&from=report&task=42` 载入后点返回,落在 `/kiosk/report/:taskId`,不是 `/kiosk/report`。
  5. 上板(严格 SSO build,token=null):屏 19 打开一份已完成的报告,点「去研究」,盘上有子,副标题是「我的对局:…」;点「← 复盘」回到同一份报告。
- **依赖 / 卡点**:无,纯前端。研究屏其它问题(S2、S3、S4)不在本轮,见 §5。

### N7 · 复盘列表首帧先闪一下「还没有下过的棋」 —— P3

- **现象**:盒上进屏 19,列表数据回来之前,第一帧可能显示空态「还没有下过的棋」。
- **根因(已核实)**:`kiosk/pages/ReportsPage.tsx:119` 是 `useState(Boolean(token))`,盒上首帧 `gamesLoading=false`、`games=[]`,于是落进 `:543` 的空态分支。要等 effect 跑起来(`:156`)才置成 true。
- **期望**:已登录时,首帧就是加载态「正在读你的对局」。
- **验收**:`ReportsPage.tsx:119` 的初值改为 `isAuthenticated`;屏 19 既有单测全绿。**不新增单测**:jsdom 里 `render` 包在 `act` 里,effect 在断言前已经跑完,测不到「effect 之前那一帧」,写了也是改前改后都绿的假测试。是否肉眼可见,留作上板顺带观察,不作为验收门槛。
- **依赖**:无。

### R1 · 屏 19 三格、两屏红段与屏 20 七档用两套判据 —— P2

- **现象**:同一局棋,屏 19 左栏「失误 N 手 / 妙手 M 手」与屏 20 折叠头「妙 a · 坏 b」、妙手 / 失误 tab 对不上。胜率图上标红的「掉得最狠一手」可能根本不在屏 20 的失误 tab 里。两屏胜率图共用 `ReviewWinratePlot`,所以屏 20 自己内部也是分裂的。
- **根因(已核实)**:
  - `features/report/reportStats.ts:36-39`、`:110-111`:屏 19 两格按 `delta_score`(两次独立搜索之差)计,`≥2` 算妙手、`≤−3` 算失误。这根轴已被 `docs/move-grading/design.md` §1 实测证明,其中的「妙手」基本只是搜索噪声。
  - `kiosk/components/report/ReviewWinratePlot.tsx:1`、`:45`:红段候选同样卡在 `MISTAKE_SCORE_LOSS`。
  - `kiosk/pages/ReportDetailPage.tsx:251-256`:屏 20 走的是 `gradedMoves(analysisByMove)` 加 `isBrilliant` / `isBad`,即服务端七档。「坏」包含小亏、失误、恶手(`gradeTiers.generated.ts:29-31`)。
  - `reportStats.ts:159-228` 的 `keyMoves` 从 2026-09-02 起在产品代码里已经没有消费者,文件自己的注释写着「再过一轮还没有消费者就删」;它是 `MISTAKE_SCORE_LOSS` 仅剩的另一个使用者。
- **期望**:
  - 屏 19 两格与屏 20 走**同一条管线**:`toMoveAnalysisMap → gradedMoves`。「失误」= `isBad`(小亏 / 失误 / 恶手,与屏 20「失误」tab 同一个桶),「妙手」= `isBrilliant`。两格**只数视角那一方**,屏 20 折叠头是双方合计。
  - 云端太旧、整份报告一手 `grade` 都没有时,退回规则只在 `gradedMoves` 一处,不另写。
  - 两格**不看准确率的 `counted`**(2026-09-15 计划审查补):`toMoveAnalysisMap` 只要胜率与目差就收一手,`_moves_with_grades` 只补 `grade` 不补 `delta_score`;某方的手都没有 `delta_score` 时准确率是 null,但失误 / 妙手照数,否则与屏 20 的等式破。
  - 胜率图红段只在上面那个「坏手」桶里挑胜率跌幅最大的一手(走子方视角,算法不变)。
  - 删掉 `keyMoves`、`KeyMove`、`BRILLIANT_SCORE_GAIN`、`MISTAKE_SCORE_LOSS` 以及 `keyMoves` 的 6 条单测(源码注释写的「5 条」已过期)。产品代码里不再有任何按 `delta_score` 阈值判妙手 / 失误的地方(`reportModel.ts:202-204` 那三个布尔量只是 `gradedMoves` 的退回输入,保留)。
  - **准确率那一格不换轴**:仍照搬 `katrain/core/ai.py` 的 `game_report()`,与桌面版、web 版对局报告同一个数。ai.py 换轴属于 move-grading 登记的遗留(R2),必须两边一起动。
- **验收**:
  1. 单测(`reportStats.test.ts`):造一份 `grade` 与 `delta_score` 故意打架的逐手数据,屏 19 算出的 `mistakes`、`brilliants` 按 `grade` 走。并且**黑方格 + 白方格 = `gradedMoves(toMoveAnalysisMap(moves)).filter(isBad / isBrilliant).length`**,也就是屏 20 那个数。
  2. 单测:`winrateSeries` 的点带 `bad` 标记,与上面同一个桶。
  3. 单测(`ReportsPage.test.tsx`):一份「两次搜索之差过了旧失误线、服务端判『尚可』」的报告,三格写「0 手」,胜率图上没有红段。
  4. `rg "MISTAKE_SCORE_LOSS|BRILLIANT_SCORE_GAIN|keyMoves" katrain/web/ui/src` 零命中。
  5. 屏 19 / 屏 20 四图 fixture 不带 `grade`,走退回路径,算出的数与红段位置和改前相同(失误 4 / 妙手 1、红段在第 43 手),所以**不重跑 fourup**。
- **依赖**:无,纯前端。`reportStats.ts` 在共享领地,两套构建都要绿。

### N24 · 断网 / 云端出错时印后端原文,「连不上」被说成「未找到」 —— P2

- **现象**(盒上报告相关接口全部走云端代理,云端不可达时本机回 503):
  - 屏 20:标题写「未找到复盘。」,下面印 `Request failed 503: {"detail":"Remote report service unavailable"}`(`ReportDetailPage.tsx:321-331`)。报告已显示、轮询刷新失败时,或点「重算」失败时,告警行同样印原文(`:447-453`,`:290`)。
  - 屏 19:「生成报告」区的告警行(`ReportsPage.tsx:606-608`,来自 `useReportTasks` 的列表 / 创建 / 重试失败)、列表错误块(`:533-540`)、左栏同步行里的预览错误(`:220` → `:448`)、胜率图空态里的逐手错误(`:249` → `:302`)、删除错误(`:389`)、导入对话框错误(`:347`、`:366`),全部 `error.message` 原样上屏。
- **根因(已核实)**:`api/reportApi.ts:88-91` 与 `api/userGamesApi.ts:116-119` 抛出的是 `Error('Request failed {status}: {body}')`,错误对象上没有状态码,调用方只能拿到一串原文。后端 `endpoints/reports.py:221-230` + `core/repository.py:364-376`:盒上云端不可达回 503;上游 4xx 按原码原 detail 透传。
- **期望**:
  - 两个 `authFetch` 在错误对象上挂 `status` 与 `body`,**message 不变**(galaxy 屏上与既有单测都认这句)。
  - 共享的纯函数 `utils/requestFailure.ts` 按**数字 status**分类:502 / 503 / 504 → `offline`;404 → `not_found`;402 且 `detail.code === 'insufficient_credits'` → `no_credits`(R5 防御半,见下);400 且 `detail.code === 'unparsable_sgf'` → `bad_sgf`;其余及没有 status 的一律 `other`,**不猜**。
  - **404 不是处处都权威(2026-09-15 计划审查补)**:报告接口(`_dispatch_remote_only`)与删除(`_remote_only`)上游 404 原码透传,是云端说的;而盒上 `GET /user-games/{id}`(`repository.py` `user_games_get`)云端连不上 / 超时 / 回任何 HTTP 错都退本机缓存,缓存没有也回 404。⇒ 读这个接口的两处(`useReportDetail` 取对局那一路、屏 19 预览)用 `cacheBackedReadFailureKind`,404 降为 `other`,不说「已经不在了」。
  - 棋谱库导入前一步是 `KifuAPI.getAlbum`,今天抛的错不带 status ⇒ 那一步失败落 `other`,只说前半句。本赛道**不改** `kifuApi.ts`(kifu 赛道 T6 改它抛 `ApiError(status)`,合并后自动分得出)。
  - 盒上列表断网时 `user_games_list` 退本机缓存(200 + `authority=local_cache`),不会走到列表错误块;列表那条单测钉的是接线,不是盒上断网路径。
  - `useReportDetail`、`useReportTasks` 在原有 `error` 之外加一个 `errorKind`。只增字段,galaxy 不受影响。
  - kiosk 屏上的话由 `reviewPresentation.ts` 的 `failureReason` / `failureLine` 给出,格式是「做什么没成 · 为什么」。原因分不出(`other`)时只说前半句,**不编原因**(「稍后再试」对一个永久的 409 是假话)。原因词:连不上云端 / 已经不在了 / 积分不足 / 这份谱读不出来。
  - 屏 20 整份读不到时:`not_found` → 「未找到复盘。」;其余 → 「这份报告没读出来」,下面一行写原因。
  - 屏 20 告警行:刷新失败 →「没刷新成功 · 原因」;重算失败 →「重算没发出去 · 原因」。
  - 屏 19:列表块 h4 不变,p 写原因;预览 →「棋谱预览加载失败 · 原因」;逐手 →「报告读不出来 · 原因」;删除 →「删除对局失败 · 原因」;导入 →「导入 SGF 失败 · 原因」 /「从棋谱库导入失败 · 原因」;报告任务 → 只写原因,分不出时写「报告任务出错了」。
- **验收**:
  1. 单测(`requestFailure.test.ts`):上面五类各一例;没有 status 的 `Error`、`TypeError`、字符串、`null` 都是 `other`;402 不带那个 code 时是 `other`。
  2. 单测(`reportApi.test.ts` / `userGamesApi.test.ts`):非 2xx 时拒绝的错误 `toMatchObject({ message: 原句, status, body })`。
  3. 单测(两个钩子):503 → `errorKind === 'offline'`;402 insufficient_credits → `'no_credits'`;非法 task id → `'not_found'`;`clearError` 之后 `errorKind` 为 null。
  4. 单测(屏 20):`game=null, errorKind='offline'` 时屏上是「这份报告没读出来」+「连不上云端」,**没有** `/Request failed/`;`errorKind='not_found'` 时是「未找到复盘。」;重算失败时是「重算没发出去」。
  5. 单测(屏 19):列表 503 → 「对局列表读不到」+「连不上云端」;报告任务 `errorKind='no_credits'` → 告警行「积分不足」;任何一条都不出现 `/Request failed/`。
  6. 真运行时预览一次:vite dev + Playwright 把 `/api/v1/reports/41` 拦成 503,取屏 20 一帧,人眼确认文字在 460 右栏里一行放得下、没有原文。
  7. `kiosk-shell-contract.spec.ts`(PO 占位符 / 默认值两条闸)仍绿。
- **范围边界**:只改复盘这两屏,以及它们用的两个 API 客户端与两个钩子。棋谱详情「这一局读不到」、课程「加载失败」同类问题**不在本轮**,见 §5。
- **依赖**:无,纯前端。

### R5(防御半)· 开闸后 402 积分不足会把 JSON 原文打到屏上 —— P3

- **现状(已核实)**:`katrain/web/core/config.py:39` `Settings(BaseModel)`,`:109` `BILLING_ENFORCED: bool = False`,`:111` `FREE_WEEKLY_REPORTS: int = 1`,两者都**没有 env 映射**,今天用户碰不到 402。开闸后 `endpoints/reports.py:346-348` 回 `402 {"detail":{"code":"insufficient_credits",…}}`,盒上经 `_dispatch_remote_only` 原样透传。
- **本轮只做**:在 N24 的分类器里认出这个 code,屏 19 报告任务告警行写「积分不足」。**不改默认值、不加 env 映射、不做余额 / 兑换页、不开闸。**
- **理由**:分类器反正要写,这只是一个分支。不认它的话,402 会落进 `other`,屏上只剩一句「报告任务出错了」,用户照着点重试也没用。
- **验收**:见 N24 验收 1、3、5 中的 402 用例。

---

## 4. 待 Fan 拍板

### R6 · 复盘要不要记阅读位置(「继续复盘 · 已看到第 N 手 · 还剩 M 手」)

- **核实后的现状(更正条目包)**:条目包说「每次进报告都从第 0 手开始」,**不准确**。`useReportDetail.ts:145-155` 的 `nextAvailableCursor` 在首次加载时把游标放到**已分析的最后一手**(`nextReportCursor(0, 0, frontier) = frontier`,`useReportDetail.test.tsx:184` 钉着)。已完成的报告因此是从终局进入的。不记阅读位置这一点属实:`rg 继续复盘|readProgress|resumeCandidate` 在复盘代码里零命中。国象 / 象棋 / 五子棋都做了(`smartbox-software/chess/ui/src/review/reviewProgress.ts`,localStorage + 首页横幅)。围棋设计稿复盘屏没画 `.kiosk-resume`。
- **另一个牵连**:kifu / tsumego 两条赛道都挂着 **N10**,即盒上「继续上一局 / 继续摆谱 / 训练营上次位置」存在无痕浏览器的 localStorage 里,重启就没,而且不分账号。R6 若照兄弟家用 localStorage 做,会原样继承这个缺陷。
- **选项**:
  - A. 照兄弟家做全套:屏 19 右栏加一条「继续复盘」横幅,屏 20 从上次那一手进。要先出 mockup;横幅会从「历史对局」列表里扣高度(列表是这一屏唯一会长的东西,「露一半」约束会破),要走四图与承重实测。
  - B. 不加横幅:屏 19「已分析」那一行的副行尾部加一句「看到第 N 手」(不增高度),点「查看报告」从那一手进屏 20。几何不变,只需一次真运行时预览。
  - C. 不做,维持「从终局进」。
- **推荐**:B,但**等 N10 的存储方案定了再做**。理由:① 7 寸屏上列表高度是硬约束,A 的横幅代价大,而复盘场景比「继续上一局」弱;② 在 N10 拍板前再新增一把 localStorage 键,等于亲手多造一处 N10;③ 现在从终局进入并不坏,复盘通常先看结果。
- **不拍板时本轮怎么处理**:不做,不进计划。

### I18N-PO · 本轮新文案补不补 PO —— **已定,不需要 Fan 拍板**

- **问题**:本轮新增约 12 个 key(`review:failure_*`、`review:detail_failed`、`review:refresh_failed`、`review:recompute_failed`、`review:tasks_failed`、`research:user_game_failed`)。一律写成 `t('ns:key', '中文默认')`,不进 PO。盒上默认 cn,屏上就是中文默认串;其它 10 种语言会落回中文。
- **结论**:本轮不补,等五条赛道合并后统一交 `katrain-i18n-expert` 补 11 种语言。这是五条赛道共用的协调约束(`t(key,'中文默认')` 不加 PO),不是产品取舍:并行改 11 份 `.po` 必然冲突;kiosk 的 PO 闸只在 key 已存在于 PO 时才比对,不补不会红。交付时附上本轮新增 key 清单。

---

## 5. 不在本轮

| 条目 | 类别 | 一句理由 |
|---|---|---|
| R2 七档改造四项遗留(段位缩放 / `ai.py:232` 抹平 / 研究面板换轴 / 棋盘七档色带) | 已裁定不做 | move-grading 会话 2026-08-29 在 `docs/move-grading/design.md:290-300`「没做的(明确留下)」自收的范围,非 Fan 亲裁,可重开。段位缩放要先定 `user_games` 的段位数据源;研究面板换轴现在只剩 galaxy `ResearchAnalysisPanel.tsx:109-112` 一份;`Board.tsx:52-59` 仍是 6 色。另更正:design.md 里「`.kiosk-ribbon` 零消费者」已过期(屏 20 吻合度分布在用)。 |
| R3 研究屏手搭局面生成报告 | 已裁定不做 | `scope.md:2410-2420` §36 改判不做(决策 agent 在 Fan 2026-08-26 授权下裁定,非 Fan 亲裁)。三条解锁条件至今一条没做,根因 `utils/sgfSerializer.ts:95-97` 只在让子时出 AB。报告的分享 / 导出 / 打印 / 语音从来没人承诺过,不是缺口。 |
| R5 其余(env 映射、开闸时点、盒上余额 / 免费额度 / 兑换页、云端 billing 代理联调) | 归 galaxy-payment 赛道 + 等 Fan | `superpowers/tracks/galaxy-payment/plan.md:46` 写死默认关与三项开闸前置(P3 手机绑定、P5 页脚、U4 资质);galaxy 额度文案在未合并的 feature/phone-login 上。 |
| R6 阅读位置 | 待 Fan | 见 §4。 |
| S2 离开研究屏回收会话打到不存在的地址 | 归「研究」模块 | 与复盘旅程无关;本轮五条赛道都不含研究模块。 |
| S3 研究屏手摆子写成着法 | 归「研究」模块 | 同上;也是 R3 的解锁条件①。 |
| S4 研究屏删掉的控件 | 归「研究」模块(已裁定) | 同上。 |
| N24 中棋谱详情「这一局读不到」、课程「加载失败」印原文 | 归 kifu 赛道 / 课程模块 | 不同屏、不同 API 客户端;可以复用本轮的 `utils/requestFailure.ts`。 |
| N9 训练营 / 棋谱库断网说成「没有题」 | 归 tsumego / kifu 赛道 | 同类问题,不同屏。 |
| N25 / X9 对局屏红条印后端原文 | 归 play-ai / cross-platform 赛道 | 同类问题;那边走的是 `api.ts` 的 `ApiError`,本轮分类器同样认它的 `status`。 |
| N18 复盘导入菜单与对话框仍是 MUI 样式 | 归「外壳/横切」 | 视觉重画,五条赛道都不含。 |
| S5 复盘本地导入依赖浏览器文件选择器,从未上板验证 | 归 kifu 赛道(需上板) | 条目包分配在 kifu。 |
| K3 棋谱详情无「送去复盘」 | 归 kifu 赛道 | 入口在棋谱屏。 |
| A6 对弈首页「全部对局」卡不显示局数 / 报告数 | 归 play-ai 赛道 | 入口在对弈首页。 |
| N13 星阵人机局不进棋谱、不能送复盘 | 归 cross-platform 赛道 | 落账在跨平台链路。 |
| P9 大厅 / 房间局不进棋谱与复盘 | 归人人对弈(挂 S4 / P2 决策) | 落账链路问题。 |

## 6. 与其它四条赛道的协调与共享文件

### 6.0 五条赛道统一协调规则（2026-09-14 主会话写定，五份 PRD 同文）

**基线**：五个分支从 develop `6f7dc629` 开出，提交文档前已快进到 develop `bad0c1fb`。中间 28 个提交全是视觉/LED 标定与盒端登录页，**不碰任何一份 plan 要改的文件**，plan 里的行号仍然有效。五个分支在同一个仓里，彼此不用 push 就看得见：`git log feature/kiosk-go-<赛道> -- <文件>`。

**会撞的地方（按风险排序）**

1. **对局结束 → 落账 / 结算（`server.py`）：两条赛道各设计了一套，必须收成一条。**
   - 对弈·AI（N22）：新增 `_finish_ended_game`，挂 `manager.on_game_ended`，`/api/move` 自然终局改走它。
   - 跨平台（N13）：新增 `_record_platform_engine_game` / `_session_owner`，给 `_record_ai_game(_locked)` 加 `data_overrides`，在 resign / move / 视觉三处落账。
   - **规则**：终局收尾的唯一入口归对弈·AI 的 `_finish_ended_game`。跨平台照 plan 做，`data_overrides` 与 `_record_platform_engine_game` 保留为薄 helper；合并时由后合并的一方（默认对弈·AI，见下方顺序）把跨平台的三处调用点收进 `_finish_ended_game`。
   - **合并验收**：`grep -n "_record_ai_game(\|_record_platform_engine_game(" katrain/web/server.py` 里，终局路径的调用只经过 `_finish_ended_game`。两套并存就不算合完（同形状的教训见记忆「两套并行实现」）。
2. **`/api/resign` 与 `interface.py` `_do_resign`**：对弈·AI（N21）改判负方；跨平台在旁边加 `_do_end_without_result`，并在 resign 里加平台落账分支。两处 hunk 相邻，属文本冲突。N21 的判负方修正对星阵局同样成立，合并时两边都留。
3. **`GameControlPanel.tsx`（+ test）**：
   - 跨平台只动 `engineMode` 那一支的动作数组与 `.ghint`（X9-a）。
   - 对弈·AI 新建 `gameKinds.ts`（`isFreeVsAi` 保留 `engineMode` 参数），并改 `analysisActions`。
   - **归属**：`engineMode` 局的按钮集合归跨平台，其余局型归对弈·AI。
4. **`GamePage.tsx`**：
   - 跨平台改 `:335-341` `refreshItemCounts`、`:501` `handleEngineAnalysis` 两处 token 闸（X7），另加 `EndgameCard` 的 Void 说明行。
   - 对弈·AI 改 N17 / N21 / N25 / A18 等处。
   - 对弈·AI **不要顺手改那两处 token 闸**（归跨平台）。
   - `tests/kiosk-screen-05-game.spec.ts` 两家都改，后合并方保留两边断言。
5. **`KioskApp.tsx`**：训练营 T9 改 `:132` 做题路由守卫；棋谱 K1/K4 改 `:56` import 与 `:137-145` 摆谱路由。hunk 相邻，属文本冲突，两边都留。
6. **`repository.py`**：两家都只**调用** `RepositoryDispatcher._remote_only`，都不改它本身。
   - 训练营改 `tsumego_*`（`:189-225`）与 `get_all_problems`（`:98-106`）。
   - 棋谱改 `kifu_list_albums` / `kifu_get_album`（`:251-270`）。
7. **请求失败分类**：复盘赛道新建 `src/utils/requestFailure.ts`。其它赛道本轮不依赖它，**也不要另建同职责的共享文件**（各自在本页内处理即可）。五家都合并后再收口，已登记为后续项。
8. **i18n**：五家都只写 `t('ns:key','中文默认')`，本轮不改任何 `.po`（并行改 11 份 `.po` 必冲突）。合并完统一交 `katrain-i18n-expert` 补 11 种语言，各赛道交付时附新增 key 清单。补不补、何时补仍由 Fan 定。
9. **四图存档**：取图目录各家不同，不冲突。跨平台重取 01/10，对弈·AI 重取 05，训练营 11，棋谱 17，复盘 19/20。重取前按 CLAUDE.md 跑两次比对，排除抖动。

**合并顺序（默认）**：改共享文件少的先合；改得最多的最后 rebase，由它负责解冲突。
1. **复盘/报告**：只新建共享文件，不改别家的文件。
2. **棋谱**：含 P0 K1，先落 `KioskApp` / `repository`。
3. **训练营**：rebase 到棋谱之上，解 `KioskApp` / `repository` 的相邻冲突。
4. **跨平台**：落账 helper 先落。
5. **对弈·AI**：13 个 Task，最大。最后 rebase，并按第 1 条把终局收尾收成一条。

例外：单个 P0 Task 只要不碰第 1、2 条所列代码，可以拆出来先合，不必等整条赛道。例如对弈·AI 的 N17 只动 `GamePage` / `useGameSession`。

**每次合并前**：
- `git merge develop`（或 rebase），然后跑本赛道 plan 的 Global Constraints：`npm run build` 与 `npm run build:kiosk-2d`、`npx tsc -b`，再按基线 diff 跑相关测试。
- 下一家 rebase 时，对照本节查**语义**冲突，不只看 git 报不报冲突。git 报「合得干净」不等于合得对。

### 6.1 本赛道会改、可能与别家重叠的文件（writer 按 plan 列出）


| 文件 | 本赛道改什么 | 可能重叠的赛道 |
|---|---|---|
| `katrain/web/ui/src/utils/requestFailure.ts`(新建,共享领地) | 请求失败分类纯函数 | tsumego(N9)、kifu(N9、棋谱详情)、play-ai(N25)、cross-platform(X9)都是同类「印原文」问题,可能各自新建同名 / 同义工具。建议统一用这一个 |
| `katrain/web/ui/src/api/userGamesApi.ts`(共享) | `authFetch` 错误对象挂 `status` / `body`,message 不变 | play-ai(A6 可能读对局数)、cross-platform(N13 存谱)、kifu |
| `katrain/web/ui/src/api/reportApi.ts`(共享) | 同上 | play-ai(A6 可能读报告数) |
| `katrain/web/ui/src/api/kifuApi.ts`(共享) | **本赛道不改** | **kifu**(T6 改为抛 `ApiError(status)`)。合并后屏 19「从棋谱库导入」那一步失败自动能说原因;kifu 合并时顺手确认 `ReportsPage.test.tsx`「从棋谱库导入失败」那条(桩是今天不带 status 的普通 `Error`)仍绿 |
| `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx` + `ResearchPage.userGame.test.tsx` | S1 判别位与取谱失败副标题(`:134`、`:438-455`) | kifu(S5 研究屏打开 / 保存;棋谱详情 → 研究 `?kifu_id` 深链) |
| `katrain/web/ui/src/features/report/reportStats.ts`、`useReportDetail.ts`、`useReportTasks.ts`(共享,仅复盘消费) | R1 管线;N24 `errorKind` | 预计无 |
| `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx`(+`.test.tsx`)、`ReportDetailPage.tsx`(+`.test.tsx`)、`kiosk/components/report/ReviewWinratePlot.tsx`、`tests/report-kiosk.spec.ts`(一行注释) | R1 / N7 / N24 | 预计无(A6 若要在对弈首页显示报告数,读的是 API 不是这两屏);kifu 计划把 `ReportsPage.test.tsx` 列为负载下易超时名单 |
| `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts` + `.test.ts` | N24 追加 `failureReason` / `failureLine`,顶部加一条 import;测试文件第 4 行 import 加两个名字、末尾追加一个 describe | **cross-platform**(其计划 Task 7 改同文件 `outcomeLine` `:96-101` 与测试 `:98-101`)——都是局部改动,合并时注意测试文件 import 行 |
| `katrain/i18n/locales/*/katrain.po` | **本轮不改** | 全部(见 §4 I18N-PO) |

## 7. 验证方式

| 层 | 适用条目 | 做法 |
|---|---|---|
| 基线 diff | 全部 | 动手前在 worktree 跑一遍 `npx vitest run --reporter=json`,记下失败用例的**名字集合**;收尾再跑一遍,用 `comm` 比名字集合,不比条数。新增失败必须为空。 |
| 单测(vitest) | S1、R1、N24、R5 | 见各条验收。N7 不加单测(理由见 N7)。 |
| 类型检查 | 全部 | `npx tsc -b`(`npx tsc --noEmit` 检查 0 个文件,无效)。测试文件不在 tsc 范围内。 |
| 两套构建 | 全部(动了共享领地) | `npm run build` 与 `npm run build:kiosk-2d`(含 `verify:kiosk-2d`)都绿。 |
| lint / 边界 | 全部 | `npx eslint` 本轮改过的文件,确认共享文件没有 import `src/kiosk/**`。 |
| PO 闸 | N24、S1(新增 kiosk 文案) | `npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-contract.spec.ts`。 |
| 四图对比 | **本轮不触发** | R1 不改版式,四图 fixture 走退回路径,输出与改前相同;N24 改的是设计稿没画的错误态文字;S1 / N7 没有视觉变化。 |
| 承重结构实测 | **本轮不触发** | 把改动撤回去,没有任何元素的高度来源或裁切边界会变:没有改 CSS,没有改盒子链,只是文字内容变短。 |
| 真运行时预览 | N24 | 一次:屏 20 在 `/api/v1/reports/41` 回 503 时的一帧(vite dev + Playwright 拦截),人眼看。截图不入库,预览 spec 用完即删。 |
| 上板(建议,Fan 定时机) | S1、N24、N7 | 严格 SSO 构建(token=null)部署测试环境(先 home-ubuntu 再生产):① 屏 20「去研究」盘上有子、返回回到同一份报告;② 断开云端时屏 20 / 屏 19 的话;③ 顺带看屏 19 首帧有没有闪空态。不作为合并前置,但合并后发布前应走一遍。 |
