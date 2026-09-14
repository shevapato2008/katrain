# 围棋 kiosk · 训练营(kiosk-go-tsumego)需求文档

- 日期:2026-09-14
- 分支 / worktree:`feature/kiosk-go-tsumego` @ `/Users/fan/Repositories/katrain-kiosk-go-tsumego`,基于 develop `6f7dc629`
- 输入:2026-09-14 三轮调研条目包(`kiosk-go-tsumego.json`,15 条)+ 全量报告 `go-kiosk-gaps.html`;设计对齐赛道正本 `superpowers/tracks/kiosk-go-shell-align/scope.md`;设计稿 `smartbox-software/superpowers/shared/kiosk-shell/sample-go/go-kiosk.html`
- 实施计划:同目录 `plan.md`

> 本文每条都已回 `6f7dc629` 源码逐条核实过(行号按这个提交)。条目包里说错或过头的地方写在各条的「核实」一行里。

---

## 1. 背景与目标

盒上训练营今天是一条走得通的五层链:屏 11 训练营 → 选择题型(`/tsumego/:level`)→ 屏 12 单元 → 屏 13 题目 → 屏 14 做题。题库在盒上是**在线直读云端**(`core/repository.py` 的 `tsumego_*`,盒上不存题、没有同步);做题进度已经按人存、盒上 token=null 时也能同步(shell-align S1);屏 11–14 已按稿重画;实体盘做题的相位机 / LED / 语音都在。

缺口集中在四处:

1. **屏幕做题的人被标定台整屏挡住(P1)。** 做题路由无条件套着标定守卫,而实体做题开关默认是关的 —— 盒子一重启、或标定失效,只想在屏幕上做题的人点进任何一道题都先被推去标定台。
2. **屏上说的和实际不一致。** 断网时说「这台盒子上还没有题 · 题库随云端同步下来」;首页说「题在实体盘上摆好」;整级页说「六类混在一起」;实体模式下「退一手」说「按灯光提示走」而拿子后机器毫无反应;摆题引导里挂着一颗永远按不动的「开始答题」;答错拿除列表写 `(3,15)` 这种从 0 数的原始下标。
3. **换账号串位。** 「上次那一档 / 那一类」高亮和「接着上次」存在不分人的 localStorage 里,乙登录会看到甲的「继续」。
4. **「只做错过的」没接。** 稿子上屏 12 那张卡和屏 13 那一行都是可点的,实现里标着「还没接」—— 错题数是真的,只是没有去处。

**本轮目标:** 屏幕做题不再被标定挡;屏上每句话与盒上实际一致;换人不串;把「只做错过的」接通。**不**加后端数据字段,**不**给设计稿没画的两屏(选择题型、全部题目)换皮(那件事待 Fan 拍板,见 §4 D2)。

---

## 2. 已经做完、不要动的

| 已完成 | 出处 | 本轮注意 |
|---|---|---|
| 做题进度按人存 `tsumego_progress:u<id>`,同步闸从 `token` 换成 `user` | shell-align S1(08-25),`context/TsumegoProgressContext.tsx:58-84` | N10 的按人存**照这把钥匙的命名**(`:u<id>`),不另起一套 |
| 屏 11 / 12 / 13 / 14 按稿重画;环恒「—」、题面不编、`.qgrid` 格高 76 | `625da7e0` 等(08-22) | 屏 13「满编 20 格一屏装得下」是承重闸(`tests/kiosk-shell-scroll.spec.ts:299`),T1 改屏 13 时它必须照旧绿 |
| 标定守卫带返回键 | `PhysicalBoardGuard.tsx`(08-24) | T9 **不改**这个守卫本身 |
| 对弈路由按偏好决定套不套守卫 | `components/vision/PlayInputGuard.tsx`(08-23) | T9 照它的形状另写一个,**不改** `PlayInputGuard` |
| 实体做题相位机、七句语音、错子白灯闪、试下暂停、19 路限制 | kiosk-physical-tsumego(07 月),`74dd7950` 加固 | 本轮只动文案、死键与坐标写法,不动状态机 |
| 答对乱码:emoji 换 SVG | `d5ee15fe` | —— |
| 离线时进度写本地 + 进同步队列 | `repository.py:229-248`,`tests/web_ui/test_tsumego_offline.py` | N9 只改**题库读取**四个方法,进度那两条不动 |

---

## 3. 需求条目

优先级沿用调研:P0 盒上走不通 / P1 缺功能或屏上承诺不符 / P2 有缺口 / P3 仅记录。

### T9 做题页不再无条件套标定守卫(P1)

- **现象:** `KioskApp.tsx:132` 把做题路由整个包在 `PhysicalBoardGuard` 里。守卫只看几何是不是「ready 且本次开机已确认」(`PhysicalBoardGuard.tsx:25-28`),不看做题自己的「用实体盘」偏好(`tsumegoUnits.ts:113-121`,默认**关**)。盒子重启后几何恒为 `required`(`geometry_calibration_service.py:60-64`)⇒ 屏幕做题的人也被整屏换成「先标定棋盘」;标定失效 / 失败时「沿用上次标定」按不了,屏幕做题整块不可用。页面里专为这种情况写的「物理棋盘需先确认棋盘标定」+ 页控条「去标定」键(`TsumegoProblemPage.tsx:102-114`、`:465-469`)因此永远渲染不到。
- **核实:** 成立,行号准。对弈侧 08-23 的 `PlayInputGuard` 正是同一形状的修法。
- **期望:**
  1. 做题路由外面套一层 `TsumegoInputGuard`:偏好 `kiosk_tsumego_physical` 为真才套 `PhysicalBoardGuard`(不要求识别就绪,与今天一致),否则直接渲染做题页。偏好在守卫里只在挂载时读一次(渲染时读会让页内一拨开关就把做题页整个卸载重挂)。
  2. **页内实体开关的放行条件补上「几何本次开机确认过」**(与 `PhysicalBoardGuard` 同一条:`disabled`,或 `ready && session_calibrated && geometry_ready`)。原因:守卫摘掉后这颗开关是唯一的关,而它今天只看 `recognitionReady`(`TsumegoProblemPage.tsx:92`)—— `server.py` 启动时把持久化的标定锁直接推进识别 worker(「Push a persisted geometry lock into the vision worker at startup」那段),盒子一重启 `recognition_ready` 就是真、几何却是 `required / session_calibrated=false`。不补的话,屏幕做题的人进题后能直接拨开实体开关,在本次开机没人确认过的标定上判对错、记进度;下面验收 3 那句「物理棋盘需先确认棋盘标定」也渲染不到(它只在 `!physicalAvailable` 时出现)。
- **验收:**
  1. 单测 `TsumegoInputGuard.test.tsx`:几何状态造成 `required / session_calibrated=false` 的前提下,①偏好 `true` → 渲染标定台(`data-testid="calib-screen"`),不渲染做题内容(先钉住「挡得住」,否则下一条是假绿);②偏好未设 → 直接渲染做题内容,不出标定台。`TsumegoProblemPage.test.tsx`:识别就绪 + 19 路 + 几何 `required / session_calibrated=false` → 实体开关 `disabled`、提示含「物理棋盘需先确认棋盘标定」、页控条有「去标定」;几何 `ready / session_calibrated=true` → 开关可按。
  2. `KioskApp.tsx` 里做题路由不再出现裸 `PhysicalBoardGuard`;摆谱路由(`baipu/session/:source`)保持原样。
  3. **盒上(board 模式,token=null)**:重启 katrain 服务 → 实体开关关着时(开关**按盒存**,和谁登录无关)点进任意一题直接出题,实体开关是灰的,开关旁写「物理棋盘需先确认棋盘标定…」,页控条有「去标定」键;在做题屏里确认过标定、把开关打开后再重启服务,点进题仍被带去标定台,「沿用上次标定」后回到题。无摄像头的盒子行为不变。
- **依赖与卡点:** 纯前端,无依赖。余留一个出口问题见 §4 D3。

### N9(训练营这一半)断网 / 云端出错时说「连不上」,不说「没有题」(P2)

- **现象:** `repository.py:189-227` 四个题库读取方法在盒子离线、连不上、云端回错时一律 `return []` / `None`;端点(`endpoints/tsumego.py:106`、`:141-150`、`:194`、`:228`、`:269-271`)把它当成真结果 ⇒ 前端看到空列表或 404。训练营首页于是写「这台盒子上还没有题 · 题库随云端同步下来，同步过来才有题可做」(`TsumegoPage.tsx:112-115`),单元屏 / 题目屏写「这一类下面还没有题 · 题库随云端同步下来」,做题屏写「这道题读不到 · Problem not found」(`hooks/useTsumegoProblem.ts:283`)。另有一处同形:`RemoteTsumegoRepository.get_all_problems`(`repository.py:98-106`)用 `gather(return_exceptions=True)` 静默丢掉取失败的分类,返回一份缺块的列表。
- **核实:** 成立。「随云端同步下来」这句本身就不实:盒上题库没有任何同步,是在线直读。条目包的 kifu 那一半归棋谱赛道。
- **期望:**
  - 后端:四个方法改走同文件已有的 `_remote_only`(`repository.py:364-376`,复盘报告那一族在用):离线 / 传输失败 / 云端 5xx → `RemoteServiceUnavailableError`,云端 4xx → 原样抛 `httpx.HTTPStatusError`;`get_all_problems` 任一分类失败即整体失败。端点把前者翻成 **503**、后者翻成**同一个状态码**。服务器模式(无 dispatcher)一行不变。
  - 前端:接口回 503 时,训练营首页、单元屏、题目屏、做题屏、选择题型页、全部题目页写「**连不上云端题库**」+「题库在云端，盒子上不存题。等网络或云端恢复后再点重试。」;有重试键的三屏保留重试。空态(接口真回了空)去掉「随云端同步」那句。
- **验收:**
  1. pytest `tests/web_ui/test_tsumego_board_unavailable.py`:dispatcher 离线 / `ConnectError` / 云端 503 时四个方法都抛 `RemoteServiceUnavailableError`;云端 404 抛 `HTTPStatusError`;在线成功时原样返回;一个分类失败时 `get_all_problems` 抛错而不是返回缺块列表。端点层:离线时 `GET /api/v1/tsumego/levels` 回 503;云端 404 时 `GET /api/v1/tsumego/problems/x` 回 404。
  2. vitest:各页 fetch 回 `{ ok:false, status:503 }` 时出「连不上云端题库」;回 404 时仍写「题库读不到 · HTTP 404」(不许把所有错误都说成没网)。
  3. **盒上**:断开盒子网络后进训练营 → 「连不上云端题库」;恢复网络点「重试」→ 出题。
- **依赖与卡点:** 后端 + 前端,数据契约只加「503 = 连不上云端」一条语义,前后端同一个任务链里做完(垂直切片:先后端契约,再前端文案)。

### N10(训练营这一半)「上次」和「接着上次」按账号存(P2)

- **现象:** `tsumegoUnits.ts:89-111`、`:139-160` 的上次档位 / 上次分类,和做题屏写进 `activeSession.ts` 的 `kiosk_active_practice`(`TsumegoProblemPage.tsx:174-179`),键里都没有用户 id ⇒ 盒子共用时乙登录看到甲的「接着上次 · 15 级 · 吃子 · 第 3 题」和两处高亮。
- **核实:** 成立。条目包另一半「无痕 chromium 一重启全丢」是跨仓 smartbox 的事(存持久 profile 还是存服务端,报告已列为 ST2/N10 待 Fan 拍板),**不在本条**。
- **期望:** 三样东西都改成按账号存,钥匙照进度那把的命名:`kiosk_tsumego_last_level:u<id>`、`kiosk_tsumego_last_category:u<id>`、`kiosk_tsumego_resume:u<id>`(值 `{label, route}`)。读写都在 `tsumegoUnits.ts` 里,调用方从 `useAuth().user?.id` 取 id;没有 user(理论上进不来这些路由)时读返回 `null`、写什么都不做。旧的不分人键**不迁移、不再读**(它没有主人)。「接着上次」不再走 `activeSession.ts` —— 那个文件的 `practice` 槽只有训练营两处在用,挪走后零消费者;**本轮不改 `activeSession.ts`**(对弈赛道在同一个文件上有活),删 `practice` 槽登记给该文件的主人。
  - 实体开关 `kiosk_tsumego_physical` **仍按盒存**:它描述的是这台盒子上那块盘接没接好,和谁登录无关。
- **验收:**
  1. vitest:以 user 7 渲染训练营首页,预置 u8 的三把键 → 不出「接着上次」、分类作用域取最弱那一档、没有高亮;预置 u7 → 三样都出。单元屏 / 题目屏进入时写的是 `kiosk_tsumego_last_category:u7`。做题屏写 `kiosk_tsumego_resume:u7`。
  2. 真浏览器 fixture(屏 11 四图、`kiosk-shell-scroll.spec.ts` 训练营两条)里的钥匙跟着改 —— **改一把存储钥匙要 grep 的不只是源码,还有 fixture**(shell-align 屏 13 那一次的教训)。
  3. **盒上**:甲做两题后退出,乙登录进训练营,看不到甲的「接着上次」和高亮;甲再登录,自己的都还在。
- **依赖与卡点:** 纯前端;与 T1 共享 `writePracticeResume` 的签名(T1 在它之后做)。

### T1 「只做错过的」接通(P2)

- **现象:** 屏 12 那张卡(`TsumegoUnitsPage.tsx:215-221`)带 `soon='还没接'` 所以按不动;屏 13 那一行(`TsumegoUnitListPage.tsx:292-307`)行尾只有琥珀「还没接」。副标里的「现在有 N 道」是真数(`attempts>0 && !completed`,整类口径)。
- **核实:** 成立,但修正条目包一处:卡点**不是**后端缺按错题筛的接口 —— 前端已经拿到整类题号和进度,集合算得出来;真正缺的是做题屏只认一条按「级别+分类」存的整类顺序表(`tsumegoUnits.ts:21`、`TsumegoProblemPage.tsx:118-158`),没有地方装一份筛过的题单。稿子两处都画成可点(`go-kiosk.html:2456`、`:2518`),屏 13 那组标题的稿子原注写着「同一副骨架，只换题从哪儿来」。无人裁定不做。
- **期望(纯前端):**
  1. 新路由 `/kiosk/tsumego/:level/:category/wrong`,渲染**屏 13 同一副骨架**(`TsumegoUnitListPage` 以 `set="wrong"` 渲染):
     - 页控条「15 级 · 吃子 · 错题」,副标「现在有 N 道 · 落子即判」,返回键回屏 12;
     - 数据条三格:「N 道 / 做错过、还没做对」「平均尝试次数」「X / 总数 / 这一类已做对」;
     - 格子是这一类里「试过、还没做对」的全部题,格上写**该题在这一类里的真题号**和「N 次」,不画 `now`;
     - 「换一批」只留「整级」一行(错题那一行指向自己,不画);
     - 0 道时空态「这一类现在没有做错过的题」+ 回「单元」的键。
  2. 点一格的那一刻,把**当前这份错题题号列表**写进 `sessionStorage` 的 `kiosk_problems_<level>_<category>_wrong`(快照),再进 `/kiosk/tsumego/problem/<id>?set=wrong`。快照是为了做题途中做对一道、它不会从上/下一题的序列里消失。
  3. 做题屏在 `?set=wrong` **且快照里有这道题**时:上/下一题、做对自动下一题、实体模式做对后的翻页,全部只在快照里走(导航带着 `?set=wrong`);页控条标题「错题 第 i / n 道」;返回键和最后一题的「返回错题」回错题页;「第 N 单元」那一块换成「错题 · n 道」+ 点阵(**点阵最多 20 个**,取当前这道所在的那 20 个 —— 右栏五块摆满 516 不滚,`.dots` 10 列,快照 60 道就是 6 行、把动作区顶出画布;上限与整类模式一个单元相同 ⇒ 右栏高度来源不变);「接着上次」记下带 `?set=wrong` 的路由与「… · 错题第 i 道」。快照读不到或不含这道题(深链、换了标签页)⇒ 退回整类行为,**不假装还在错题里**。
  4. 屏 12 卡、屏 13 行:有错题时可点 / 有「开始」键,都进错题页;0 道时 `disabled`,副标照写「现在有 0 道」。两处不再出现「还没接」。
- **验收:**
  1. vitest:屏 12 卡 2 道时可点并导航到 `/kiosk/tsumego/15k/capturing/wrong`,0 道时 `disabled`;屏 13 行「开始」同理;错题页只列 `attempts>0 && !completed` 的题、格上是整类真题号、点格写快照并导航到 `…?set=wrong`;0 道空态。做题屏:`?set=wrong` + 快照 `['q3','q9','q12']`、当前 `q9` → 标题「错题 第 2 / 3 道」、上一题去 `q3?set=wrong`、下一题去 `q12?set=wrong`;当前是最后一道时键写「返回错题」并回错题页;快照 45 道、当前第 26 道时点阵是 20 个;快照不含本题时上/下一题走整类序列。
  2. 真浏览器承重关:错题 60 道时错题页滚动区**确实溢出**(先断言前置),真滚轮滚到 `data-at="end"` 且最后一格在视口内;屏 13 原有「满编 20 格一屏装得下」闸照旧绿。
  3. 四图:错题页对屏 13 参考图、做题屏错题模式对屏 14 参考图各取一组,**Fan 视觉确认**。
  4. 盒上:做错两题后回屏 12,卡上「现在有 2 道」可点,进去做对一道,回到错题页只剩 1 道。
- **依赖与卡点:** 依赖 N10(`writePracticeResume` 签名)与 N8(屏 12/13 同一处文案)先落。

### N8(文案这一半)整级页不再说「六类混在一起」(P2)

- **现象:** 屏 12「整级一起做」卡副标「六类混在一起，不分单元」(`TsumegoUnitsPage.tsx:211`),屏 13 整级那一行「六类混在一起，练「认出这是哪一类」」(`TsumegoUnitListPage.tsx:280`)。实际全部题目页按分类再按题号排(服务器模式 `endpoints/tsumego.py:204-206`;盒上 `repository.py:98-106` 逐分类拼接),每张卡贴着分类标签,做题屏上/下一题只在本分类里走。
- **核实:** 成立。稿子的意图确实是混排(`go-kiosk.html:2419` 注释),所以「做真混排」和「改文案」是两条路 —— 真混排连着那一屏重画与做题屏要不要藏分类,见 §4 D2。
- **期望:** 本轮先把话说成真的:屏 12 卡副标「按分类排好，不分单元」;屏 13 行「这一级的全部题，按分类排好」。
- **验收:** vitest 两屏断言新句且不再出现「混在一起」「认出这是哪一类」;四图屏 12/13 标签带登记「这一句与稿子不同,原因 N8」。

### T4(文案这一半)实体模式「退一手」不再承诺一条不存在的流程(P2)

- **现象:** 实体模式下「退一手」灰掉,原因写「实体棋盘上请直接把子拿掉，按灯光提示走」(`TsumegoProblemPage.tsx:345-354`)。状态机没有「主动收回」事件(`physicalTsumegoMachine.ts:52-60`),WS 循环只认三种事件(`usePhysicalTsumego.ts:239-257`),拿掉一颗已下对的子后没有灯、没有语音、屏幕不退,盘与屏悄悄错位。
- **核实:** 成立。补一处:这句原因只挂在按钮的 `title` 上(`shell/KioskActions.tsx:61`),触屏上几乎看不见,屏上承诺的分量比条目包写的轻;但读屏与悬停仍会读到。
- **期望:** 原因改成「实体棋盘上退不了一手；想重来，按「重摆」」。「重摆」在实体模式下本来就会重走清盘 → 摆题(`TsumegoProblemPage.tsx:87-90`,`resyncKey` 触发 `usePhysicalTsumego` 重跑),这句话是真的。真的「主动悔一步」流程见 §4 D1。
- **为什么本轮只改文案、而不是整条挂起:** ① 今天这句原因是一句**假承诺**,改成真话不预设 D1 的任何选项 —— Fan 选 A 时这句随真流程再换,选 B / C 时它就是终稿;② 真流程(A)要改相位机与 WS 事件分发,且「识别端的 `illegal_change` 够不够判定是哪一手被拿走」只能上板验,不是本轮能在工作站上闭环的事;③ B 那句「盘面和屏幕对不上」的提示要在 `ready` 态消费 `illegal_change`,手悬在盘上遮挡时会不会误报同样只能上板看,所以也不作为默认动作。
- **验收:** vitest:实体模式下「退一手」`disabled` 且 `title` 为新句。

### T8(死键这一半)摆题引导里不再挂一颗永远按不动的「开始答题」(P2)

- **现象:** 做题屏只在 `phase==='setup'` 时挂 `BoardSetupGuide`,写死 `isComplete={false}`、`onStartProblem={() => {}}`(`TsumegoProblemPage.tsx:515-525`);状态机一摆好就自动进答题(`physicalTsumegoMachine.ts:93-99`),引导随之消失 ⇒ 「开始答题」在它可见的整个期间都点不动。引导里的中文写死、不走 `t()`(`BoardSetupGuide.tsx:54-90`)。
- **核实:** 成立。组件只有这一个调用方。
- **期望:** 删掉「开始答题」键和 `isComplete` / `onStartProblem` 两个 prop;「跳过设置」保留;引导里三句中文走 `t('tsumego:…', '中文默认')`。**不换皮**(按壳重画不在本轮,见 §5)。
- **验收:** vitest:渲染引导 → 没有「开始答题」,有「跳过设置」且点了调 `onSkip`;`stage='white'` 时写「请摆放白棋 · 已匹配 3/7 颗子」。

### N12 拿除列表写棋盘坐标(P2)

- **现象:** 答错进入拿除时,右栏标签写「拿除 (3,15)」—— 识别网格的 0 起下标、从上往下数(`PhysicalStatePanel.tsx:126-136`)。蓝灯常被要拿的子压住,屏幕列表本应是主通道。旁边注释「voice-cue slot … stub silent」已过期(状态机早就会念 `wrong_remove`,`physicalTsumegoMachine.ts:210`)。
- **核实:** 成立。对弈侧 `CaptureGuide.tsx:26-33` 自己抄了一份换算;本仓已有唯一换算 `shell/goBoard.ts` 的 `xyToCoord`(跳 I、行号 1 在最下),用它,不再抄第三份。
- **期望:** 标签写「拿除 Q16」;删掉过期注释。
- **验收:** vitest:`extra=[[3,15,1]]` → 「拿除 Q16」(行列不对称,颠倒了会写成 D4)。

### N26 ③(训练营这一句)首页问候副标不说「题在实体盘上摆好」(P3)

- **现象:** `TsumegoPage.tsx:72`「题在实体盘上摆好，落子即判」;实体做题开关默认关(`tsumegoUnits.ts:116-122`),默认在屏幕上做;无摄像头的盒子根本没有实体盘。
- **核实:** 成立。条目包里 ①②④ 三句分属设置 / 对弈模块,不在本赛道。
- **期望:** 改为「落子即判，走错当场退回」—— 在屏幕上、在实体盘上、有没有摄像头都成立。
- **验收:** `TsumegoPage.test.tsx:59` 与 `navigation.integration.test.tsx:92` 断言新句;四图屏 11 标签带登记这一句与稿子不同。

---

## 4. 待 Fan 拍板

### D1(T4)实体盘做题的「退一手」:做真流程,还是停在「请用重摆」

- **问题:** 实体模式下用户从盘上拿走一颗已下对的子,识别端会发「盘面异常变化」,前端直接跳过,盘与屏悄悄错位。立项 PRD 只设计了「答错时系统自动进入的拿除」,从没设计「用户主动悔一步」。
- **选项:**
  - A. **做真流程**:状态机加「主动收回」—— `ready` 态收到识别端的收回变化且与上一手吻合时,屏幕退一手(连 AI 应手一起退)、LED 提示把应手也拿掉、语音一句;不吻合按异常处理。要改 `physicalTsumegoMachine.ts` + `usePhysicalTsumego.ts` 的事件分发,识别端要确认 `illegal_change` 的数据足够判定「是哪一手被拿走」,**只能上板验**。
  - B. **停在改文案**(本轮已做):「实体棋盘上退不了一手；想重来，按「重摆」」;另加一条最小诚实提示 —— `ready` 态收到「盘面异常变化」时右栏写「盘面和屏幕对不上，按「重摆」重新摆题」,不改状态机。
  - C. 只改文案,连 B 的提示也不加。
- **推荐:B。** 死活题一题两三手,「重摆」的代价本来就小;A 要动上板才验得了的状态机,收益是省一次重摆。B 的提示解决的正是条目里最伤人的那一半(盘屏悄悄错位)。
- **不拍板时本轮:** 只做文案(C 的范围);B 的那句提示与 A 都不做。

### D2(T5 + N8)「选择题型」「全部题目」两屏要不要按壳重画,整级要不要真混排

- **问题:** 从首页点「按级别」卡进的 `/tsumego/:level`(`TsumegoCategoriesPage.tsx`)和「整级一起做」进的 `/tsumego/:level/all`(`TsumegoLevelPage.tsx`)仍是 7 月 MUI 卡片皮(slate 配色、`15K 选择题型`、分类图标只配 3 类),和屏 11–14 风格断层。**两屏都不在 27 屏稿子里**,也不在对齐赛道「本轮没做」清单里 —— 两头都漏了(scope.md 早期十屏表把它标 ✅ 从未更新)。稿子注释写着整级页应复用屏 13 的骨架,并且是真混排(「练认出这是哪一类」)。
- **选项:**
  - A. 先补稿(smartbox 设计稿画这两屏),再重画;稿子里一并定「真混排时做题屏藏不藏分类标签、上/下一题跨不跨分类」。
  - B. 不补稿,按屏 12 / 13 的现成骨架直接重画:选择题型页 = 屏 12 的卡片网格(环写各类真完成度),整级页 = 屏 13 骨架分单元;题单仍按分类排(文案已按 N8 改真)。
  - C. 删掉 `/tsumego/:level` 这一层:首页「按级别」卡改成切换上面「按分类」那一排的作用域(那一排本来就是某一档的六类);整级页按 B 重画。少一屏、少一处风格断层。
- **推荐:先出一份 artifact 草图把 B 与 C 摆在一起给 Fan 看再定**(Fan 的惯例是先看图再实现)。真混排(A 的后半)涉及做题屏的信息藏不藏,建议等这两屏定了再单独立项。
- **不拍板时本轮:** 这两屏不动皮;只随 N9 把它们的错误提示改成「连不上云端题库」这一句。

### D3(T9 余留)实体开关开着、标定又修不好时,出口放哪

- **问题:** T9 之后只有「打开过实体开关」的人还会被标定台拦下。标定台有返回键,但实体开关只在做题屏里 —— 标定修不好(灯带坏、摄像头挪了)的人**回不到能关掉开关的地方**,训练营对他整块不可用,直到修好标定。
- **选项:**
  - A. 标定台(屏 26,`GeometryCalibrationScreen`)页控条加一个可选图标键「改在屏幕上做」,只有做题这一路传;按下写 `kiosk_tsumego_physical=false` 并放行。改的是共享的视觉组件,要过屏 26 四图。
  - B. 在屏 12 / 13 的数据条里放一格可点的「实体棋盘 开 / 关」。
  - C. 不做,靠修好标定。
- **推荐:A。** 出口出现在人被拦下的那一屏,只加一颗键;B 让两屏多一个和稿子不符的交互。
- **不拍板时本轮:** 不做,登记。

---

## 5. 不在本轮

| 条目 | 归类 | 理由 / 能否重开 |
|---|---|---|
| T2 训练营「每日一题」 | 已登记不做(对齐赛道 track agent 自登记,scope.md §9.4 `:248`,非 Fan 裁定) | 围棋 27 屏稿子没画这一块;规范里「两个来源·含 Lichess」是国象口径,围棋最多本地题库一道且不写分母;选题口径(每日怎么选、盒上断网怎么办)未定。**可重开**:先补稿 + 定选题口径 |
| T3 单元列表「已掌握单元 N/M」与判据句 | 已登记不做(同上,scope.md §9.4) | 稿子没画;`UserTsumegoProgress`(`models_db.py:504-515`)没有连对 / 掌握字段,要做是后端新口径。现在的三格与稿子逐字一致、口径诚实。**可重开**:补稿 + 后端加字段 |
| T6 首页「按级别」进度环恒「—」 | 已自裁(sbc-tsumego-parity track agent,`97080604`,06-13;shell-align 08-22 沿用;非 Fan 裁定) | 围棋稿子该屏六张卡画的正是「—」,不算屏上承诺落空;按级完成度要把整级题号取回,SBC 上太贵。**可重开**:后端给按级聚合 |
| T7 做题屏没有题目标题与题面 | 已自裁(shell-align 实现 agent,`625da7e0`,08-22;非 Fan 裁定) | 题库表和 19461 份原始 SGF 都没有标题 / 题面,只有「黑先 / 白先」;不编。**可重开**:题库补标注之后 |
| T10 实体做题 RK3562 §6 全项验收记录 | 需上板验证的记录项 | 从未在 RK3562 上做过 kiosk-physical-tsumego PRD TP6 的 §6 全项验收;08-22 屏 14 重画后也没人上板走过。本轮改了 T9 / T8 / N12 / T4 四处实体相关代码,**建议本轮合并前顺带走一次 §6**(见 §7)。「.mo 字节核实」已因 emoji 换 SVG 失去意义;「换题整盘清空再摆」是那份 PRD §5 自定的二期 |
| T8 另一半:摆题引导按 kiosk 外壳重画 | 需设计 + 上板 | 稿子没有画实体摆题这一态(只有 7 月 `kiosk-ui-redesign/artifacts/tsumego-states.html`);几种相位只能在真盘上看到。与 T10 上板走查一起做 |
| N26 ①②④(设置页账号副标、对弈首页「有定级队列」、设置里 AI 段位行) | 归其它模块 | ① ④ 归设置 / 外壳横切,② 归对弈·AI(play-ai 赛道) |
| N9 棋谱那一半(`kifu_list_albums` / `kifu_get_album`) | 归棋谱赛道(kiosk-go-kifu) | 同一个文件 `repository.py`,不同方法,见 §6 |
| N10 其余:「继续上一局」、摆谱最近 / 进度、无痕 chromium 重启即丢 | 归对弈·AI(游戏续局)、棋谱(摆谱)、外壳横切(持久 profile 还是存服务端,报告列为 ST2/N10 待 Fan 拍板) | 本赛道只做训练营指针的按人存;存哪儿的大决定不预设 |
| `activeSession.ts` 删掉 `practice` 槽 | 归该文件的主人(对弈赛道在同一文件上有活) | N10 之后 `practice` 槽零消费者;本轮不动共享文件,登记 |
| 新 key 补进 PO | 全局待 Fan 裁定(报告 Z1) | 本轮所有新文案 `t('tsumego:…', '中文默认')`,不往 PO 加 key |
| A19 对弈拿子没有语音 | 归对弈·AI | 与 N12 同形但在对弈侧 |
| A15 四棋类「需要联网」逐态映射表 | 归对弈·AI / 统一架构文档 | N9 这边的文案独立成立;那张表写出来后训练营照它对一次 |

---

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


| 文件 | 本赛道改什么(任务) | 可能重叠的赛道 |
|---|---|---|
| `katrain/web/ui/src/kiosk/KioskApp.tsx` | 做题路由换 `TsumegoInputGuard`(T9);加 `tsumego/:level/:category/wrong` 路由(T1)。只动 `:131-137` 训练营那几行和一行 import | play-ai / cross-platform(对局路由、守卫)、kifu(L1 直播路由) |
| `katrain/web/core/repository.py` | `tsumego_get_levels / get_all_problems / get_problems / get_problem` 四个方法改走 `_remote_only`;`RemoteTsumegoRepository.get_all_problems` 去掉 `return_exceptions`(N9)。**不改 `_remote_only` 本身** | kifu(N9 棋谱那一半,同文件 `kifu_*`)、review(N24 报告 503,若动 `_remote_only` 需互通) |
| `katrain/web/ui/src/hooks/useTsumegoProblem.ts`(共享领地,galaxy 也用) | 非 404 的错误抛 `HTTP <status>` 而不是一律 `Problem not found`(N9)。一行 | 预计无;galaxy 做题页会看到更准的错误字 |
| `katrain/web/ui/src/kiosk/__tests__/navigation.integration.test.tsx` | 断言的问候副标换新句(N26③) | 任何改首页 / 导航的赛道 |
| `katrain/web/ui/tests/kiosk-shell-scroll.spec.ts` | 只改训练营那段 fixture 的三把钥匙(`:151-161`,N10) | 所有动滚动闸的赛道(改的是不同段落) |
| `katrain/web/ui/src/kiosk/utils/activeSession.ts` | **不改**(见 §5) | play-ai |
| `katrain/web/ui/src/kiosk/components/vision/`(新增 `TsumegoInputGuard.tsx`;改 `BoardSetupGuide.tsx`) | T9 / T8。`BoardSetupGuide` 只有做题屏一个调用方 | play-ai(`PlayInputGuard` / `PhysicalBoardGuard` 若有人改) |
| `superpowers/tracks/kiosk-go-shell-align/visual/{11-training,12-units,13-problems}/` 四图存档 | 重取这三屏(文案与 T1 的键变了;屏 14 默认态无可见变化,不重取) | 任何重取四图的赛道 —— **只提交本赛道改到的这四屏** |

本赛道独占(不与别家重叠):`kiosk/pages/Tsumego*.tsx`、`kiosk/pages/tsumegoUnits.ts`、`kiosk/components/tsumego/PhysicalStatePanel.tsx`、`katrain/web/api/v1/endpoints/tsumego.py`、对应的 `__tests__` 与 `tests/kiosk-screen-1[1-3]-*.fourup.spec.ts`,以及新增的 `tests/web_ui/test_tsumego_board_unavailable.py`、`tests/kiosk-tsumego-wrong.spec.ts`、`tests/kiosk-tsumego-wrong.fourup.spec.ts`。

---

## 7. 验证方式

| 层 | 覆盖条目 | 怎么验 |
|---|---|---|
| 前端单测(vitest) | 全部 | 每个任务跑它改到的测试文件;判据是**基线 diff**:动手前全量跑一次记下失败用例**名字集合**,改完比名字集合,不比条数 |
| 后端单测(pytest) | N9 | `uv run pytest tests/web_ui/test_tsumego_board_unavailable.py tests/web_ui/test_tsumego_offline.py` |
| 类型 + 两套构建 | 全部(N9 动了共享领地 `useTsumegoProblem.ts`) | `npx tsc -b`;`npm run build` 与 `npm run build:kiosk-2d` 都绿(后者含 `verify:kiosk-2d`) |
| 承重实测(真浏览器) | T1 错题页 | 新 `tests/kiosk-tsumego-wrong.spec.ts`:造 60 道错题 ⇒ 先断言溢出成立,再真滚轮滚到底;屏 13 原有「满编 20 格一屏装得下」、训练营两条滚动闸照旧绿。jsdom 不作布局证据 |
| 四图对比 | N26③(屏 11)、N8 + T1(屏 12 / 13)、T1(屏 14 错题模式、错题页)、N10 fixture(屏 11) | 重取屏 11–13 四图(屏 14 默认态没有可见变化:T4 的原因只挂在按钮 `title` 上,T8 / N12 只在实体模式出现);新增 `tests/kiosk-tsumego-wrong.fourup.spec.ts` 取错题页(对屏 13 参考图)与做题屏错题模式(对屏 14 参考图),输出到本赛道 `visual/`;**Fan 视觉确认**后才算过。T9 / T4 / T8 / N12 / N9 视觉增量很小:T8 / N12 在右栏里,只能上板看;N9 错误态走现有 `.empty` 块 |
| 上板(RK3562,board 模式,token=null) | T9、N9、N10、T8、N12、T4 | ① 重启 katrain 服务,实体开关关着时直接进题且开关灰、提示去确认标定,开关开着时进标定台(开关按盒存,两种状态各走一次);② 断网进训练营看「连不上云端题库」,恢复后重试;③ 甲做题退出、乙登录看不到甲的「接着上次」;④ 实体做题:摆题时引导里没有「开始答题」;故意答错,右栏写「拿除 Q16」这类坐标、且与蓝灯位置一致;「退一手」灰且原因是新句;⑤ 顺带走一次 kiosk-physical-tsumego PRD §6 全项,留记录(T10)。**板上一次只跑一家的测试**(RK3562 2G 内存) |
