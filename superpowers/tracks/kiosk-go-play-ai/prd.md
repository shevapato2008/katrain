# 围棋 kiosk · 对弈·AI/升降级 —— 本轮需求

- 赛道:`kiosk-go-play-ai` · worktree `/Users/fan/Repositories/katrain-kiosk-go-play-ai` · 分支 `feature/kiosk-go-play-ai`(基于 develop `6f7dc629`)
- 输入:2026-09-14 三轮调研条目包 `kiosk-go-play-ai.json`(26 条),本文件逐条回源码核实后写成
- 日期:2026-09-14

---

## 1. 背景与目标

盒上「对弈」这一块(屏 01 对弈首页、屏 02/03 开局设置、屏 04 本地对局设置、屏 05 对局中)的外观在
`kiosk-go-shell-align` 赛道已按 27 屏稿子对齐完,但**对局本身的收尾是坏的**:AI 在思考时按认输会被记成人赢;
由 AI 下出双停第二手或 AI 认输的局不进对局记录,升降级局连结算都不进;盒上逐手分析是关的,数子几乎总是 400,
而屏上把原因说成「手数不足」;9 路 / 13 路整局数不了子;开局可选的 7 档用时在对局屏上既不倒计时也不判超时;
「继续上一局」指向一局已被回收的对局时,对局屏是一个没有任何出口的转圈。另外「实地」「厚势」两个 AI 策略一选就开不了局。

**这一轮要让盒上用户得到的是:一局棋从开局到结束,胜负判对、记进账、结算得了,屏上说的每一句话都是真的。**
判胜负与记账(N21/N22/A12/N23)先于计时(A18)与各类文案/视觉项;升降级局的「终局怎么判目」涉及会动段位的不可变账本,
留给 Fan 拍板,本轮不替它做决定。

## 2. 已经做完、不要动的

- 屏 01/02/03/04/05/10 的版式、四图存档与承重实测(`superpowers/tracks/kiosk-go-shell-align/visual/**`、
  `katrain/web/ui/tests/kiosk-screen-05-game.spec.ts`)。本轮只在列出的条目上改,改到的屏重跑四图、只提交有内容变化的屏。
- 悔棋规则(Fan 2026-08-25:只有人机自由对弈允许悔棋)、胜率块按对弈方式整块不渲染(规范 §8)、游客「登录后可用」三键闸
  (`analysis_delivered`)、AI 思考中药丸居中、显示开关样式(Fan 2026-08-22)。
- 升降级:开局引擎预检(`_preflight_ladder_engine`)、挡局面板、结算 outbox 与重试、`last_ladder_error` 停摆横幅、
  不可变账本(`ai_ladder_ranked.py` 的 `finalize_reserved_game` / `settle_game`)。**本轮不改账本与结算逻辑,只给它补调用方。**
- 盒上 token 恒为 null 的那一批闸(3159d138 / a979132a / 2c2034e0)已修,不要回退成判 token。
- 3D 棋盘已按 Fan 定的范围从 kiosk 移除(2026-07-13);棋盘木纹用 galaxy 的 `board.png`(Fan 2026-08-26)。

## 3. 需求条目(本轮做)

> 验收里凡写「盒上」,指 board 模式(`KATRAIN_MODE=board`,前端 `token === null`、身份走同源 cookie、
> 判别位用 `isAuthenticated`)。本机可用 `python -m katrain --ui web` + 浏览器 1024×600 近似,
> 标「必须上板」的只能在 RK3562 上验。

### N17 · P0 ·「继续上一局」指向已失效的对局时,对局屏无限转圈且没有出口

- **现象**:盒上 katrain 重启、会话闲置超 1 小时被回收、或换了账号后,屏 01 仍挂「继续上一局 · 恢复」;点进去对局屏只有转圈,
  没有返回键、没有 Dock、没有主页键。`useGameSession` 取状态失败时已经 `setError('Failed to connect to game')`,
  但 `GamePage.tsx:352-357` 在 `gameState` 为空时早退只画转圈,错误永远显示不出来。
- **期望**:取状态失败 → 对局屏说清「这一局打不开了」和可能原因,给「回到对弈」出口,并清掉失效的「继续上一局」指针;
  取状态进行中也要有一个可按的出口。
- **验收**:
  1. `/api/state` 返回 404(或 403/网络错)时,对局屏显示「这一局已经打不开了」及原因句,有「回到对弈」按钮,点击后到 `/kiosk/play`;
  2. 同一情形下 `clearActiveSession('game')` 被调用一次,回到屏 01 不再出现「继续上一局」;
  3. 加载中(状态还没回来)屏上除转圈外有同一颗「回到对弈」按钮;
  4. 单测覆盖 1–3(jsdom 只证行为,不证布局);盒上 token=null 下同样成立(本页不读 token 做判断)。
- **依赖**:无。「继续上一局」指针不分账号是 N10(归棋谱/训练营赛道),本条不改指针的存储位置。

### N21 · P1 · AI 思考中按「认输」被记成你赢;AI 那一手随后又落下

- **现象**:`interface.py:1464-1465` `_do_resign` 写 `current_node.player + "+R"`(胜方 = 最后落子的一方)。
  人刚落子、AI 在算时点认输(或「退出对局 → 认输并退出」),结果写成人胜并记进对局记录;AI 算完照常落子,
  新节点没有终局标记,盘面回到对局中。本地对局弹窗只写「确认认输？」,不说哪一方。
  大厅房间局在对方回合按认输,盘上胜方与按用户 id 记的胜方相反。升降级按开局执色判,结果本身不受影响,但同样会被 AI 后续着法「复活」。
- **期望**:认输方判对;一局一旦有了终局结果,后台还在算的 AI 着法不再落到盘上;本地对局确认框写明是哪一方认输。
- **验收**:
  1. 人机局(只有一方是 `player:human`):无论轮到谁,认输结果都是「AI 一方 + R」;
  2. 本地对局(两方都是人):仍判「轮到落子的一方」认输,确认框标题为「黑方认输？」/「白方认输？」;
  3. 大厅房间局:`/api/resign` 以请求者的座位判负,盘上结果与记账胜方一致;
  4. AI 生成着法期间对局被认输/超时结束,生成结束后不产生新节点,`end_result` 保持不变(升降级分支与普通分支都成立);
  5. 后端单测覆盖 1、3、4;前端单测覆盖 2。星阵(跨平台)局认输走平台网关,不经 `_do_resign`,不受影响。
- **依赖**:无。先于 N22/A12(它们依赖「结果写对」)。

### N23 · P2 · 9 路和大多数 13 路对局永远数不了子

- **现象**:`config.json:68` `count_min_moves: 100` 不分路数;`server.py:2017-2019` 与 `GameControlPanel.tsx:188-190` 都按 100 判。
  同一份配置里 AI 认输门槛按交叉点数缩放(`core/ai.py` `should_ai_resign`),数子没有。
- **期望**:数子门槛按「交叉点数 / 361」等比缩放,前后端同源(前端只读 `get_state` 下发的值)。
- **验收**:`get_state()["count_min_moves"]` 在 19/13/9 路分别为 100/46/22;`/api/count/request` 用同一个值拒绝;
  前端「数子要下满 N 手」随之显示 22/46/100;后端单测覆盖三种路数。
- **依赖**:无。与 A12 同改 `request_count`,排在它前面。

### A12 · P1 · 盒上「数子」依赖当前手已有分析分数,失败时还说错原因

- **现象**:`server.py` `_complete_count` 读 `current_node.score`,为空回 400。board 模式不做逐手分析
  (`interface.py` `should_suppress_auto_eval`),当前手常常没有分数:游客会话(`/api/analysis/current` 要求登录)、
  关掉领地和图表、分析没回来就点,都会 400;升降级局必然 400(分析被反作弊闸禁掉)。
  前端 `GamePage.tsx` catch 一律提示「暂时不能数子（对局手数不足或已结束）」。
- **期望**:非升降级局(自由对弈 / 本地对局)点「数子」时,服务端自己给当前手补一次快速分析并等它算完再数(上限 15 秒),
  不再依赖前端「图表」开关;数子期间屏上如实说「正在数子…」;失败时按服务端给出的真实原因说话。
  升降级局的数子怎么判由 Fan 拍板(见 §4 A12-R),本轮它继续数不了,但原因要说对。
- **验收**:
  1. 自由对弈/本地对局:当前手无分数时 `/api/count/request` 触发一次分析并返回 `B+x`/`W+x`,不再 400;已有分数时不重复请求;
  2. 引擎不可用(`NullEngine`)时 15 秒内不挂死,立即返回 400「Analysis not available…」;
  3. 前端按 400 detail 分别提示「手数还不够」「这一局已经结束了」「轮到你落子时才能数子」「形势分析没算出来,请稍后再试」,
     升降级局提示「升降级对局现在数不了子(本局不做形势分析)」;
  4. 数子请求在途时重复点击不再发第二个请求,屏上有「正在数子…」;
  5. 后端单测覆盖 1、2 与「升降级局不补分析」;前端单测覆盖 3、4;**必须上板**:RK3562 上自由对弈关掉图表、第 100 手后点数子得出结果并记录耗时。
- **依赖**:N23。修完后 A9(图表默认开/关)不再影响数子。

### N22 · P1 · 双方停一手分不出胜负;AI 收尾的局不落账、升降级不结算

- **现象**:① `core/game.py:313-317` 双停时 `end_result = manual_score or "board-game-end"`,盒上没有分数就只有「终局」;
  ② `server.py:996-1002` 自然终局只在人发出的 `/api/move` 里记账;AI 后台线程下出双停第二手或 AI 认输时,
  `session.py:240-246` `_on_state` 只置 `game_ended`,不记账 —— 对局记录不落,升降级局不进结算、心跳停掉,
  「复盘本局」取棋谱被「结算完成前不可用」挡住。
- **期望**:② 不论终局由人还是 AI 触发,都走同一个收尾函数:先(非升降级局)补分出胜负,再落账/进结算,每局只一次;
  ① 非升降级局双停后服务端补一次分析,把结果写成与数子同格式的 `B+x`/`W+x` 并推给前端。升降级局的双停仍记「无结论」(A12-R 待拍板)。
- **验收**:
  1. AI 线程让对局结束(双停第二手 / AI 认输)时,已登录会话的对局被记录一次(`_record_ai_game` 被调用且只落一行);升降级局进入 `finalize_reserved_game` 路径;
  2. 人发出双停第二手时,补分在落账之前完成:落账的 `result` 是 `B+x`/`W+x` 而非「终局」(引擎可用时);
  3. 人和 AI 两条路同时触发时只收尾一次(会话级串行);研究模式会话、大厅多人局、跨平台局不走这条收尾;
  4. 升降级局双停不补分析,仍按现状记「无结论」且不改账本代码;
  5. 后端单测覆盖 1–4;**必须上板**:RK3562 上一局自由对弈人先停、AI 跟停,屏上出现胜负并在「全部对局」里看到这一局;一局升降级同样收尾后「继续」按钮消失、可开下一局。
- **依赖**:N21、A12(复用 `ensure_current_score` 与数子结果格式)。

### A18 · P1 · 开局选了用时,对局屏不倒计时、不读秒、到点不判负

- **现象**:开局设置自由对弈/本地对局可选 7 档用时(`kiosk/utils/setupOptions.ts:23-31`),升降级写死计时,参数真的送到后端,
  后端也在累加(`interface.py` `update_timer`)。但对局屏玩家卡只在主时间已用 >0 时写「m:ss 本局已下」(正着数),
  否则写「第 N 手 · 不限时」;「仅读秒 30秒×3」整局显示「不限时」;读秒次数不上屏;全 kiosk 没有一处调 `/api/timeout`。
  开局屏写着「屏幕负责记谱、读秒」(`AiSetupPage.tsx:433`)、「走完一步换对方的钟」(`PvpLocalSetupPage.tsx:344`)。
  根因是 08-22 重画屏 05 时依据「kiosk 开局设置里没有时间控件」这条错误前提把计时撤了(scope §27)。
- **核实补充**:大厅房间局和星阵人机局**没有配时限**,却继承 `config.json` 默认的「20 分 + 30 秒×5」,
  且 `timer/paused` 配置缺省 ⇒ 计时不暂停。所以前端不能只看 `timer.settings` 判「这局计不计时」,
  否则星阵局会凭空倒计时并在 20 分钟后自己判负。需要服务端给一个「这一局的时限是开局设置定的」判别位。
- **期望**:开局设置配过时限的局(自由对弈/本地对局/升降级),两张玩家卡的时钟格显示剩余主时间(「剩余」),
  主时间用完后显示本次读秒剩余秒数与剩余次数(「读秒 · 剩 N 次」);轮到的一方走钟、另一方停;
  轮到的一方时间耗尽 → 调 `/api/timeout` 判负。不计时的局维持「第 N 手 · 不限时」。没配过时限的局(星阵/大厅)不显示倒计时、不判超时。
- **验收**:
  1. `get_state()["timer"]["configured"]` 仅在经 `update_config("timer/…")` 设过时限的会话里为 `true`;
  2. 计时局:主时间阶段时钟格 `<b>` 每秒递减、`<span>` 为「剩余」;读秒阶段 `<b>` 为本次读秒剩余、`<span>` 为「读秒 · 剩 N 次」;
  3. 轮到的一方耗尽 → 前端调用一次 `/api/timeout`(同一手不重复);升降级局只在人的回合发;`last_ladder_error` 时不发;
  4. 星阵局(`timer.configured` 为假)不出现倒计时;不计时局文案不变;
  5. 纯函数单测覆盖主时间/读秒/耗尽三段;真浏览器 Playwright 一条:计时局时钟 1.5 秒内数字变化(真实运行时证据);
     屏 05 四图(不计时 fixture)重跑应为抖动级无变化;计时态截一张实现图给 Fan 看(稿子没有计时态参考图,只做单图确认)。
- **依赖**:N21(超时同样要防 AI 着法复活,由 N21 的提交守卫覆盖)。

### A3 · P1(核实后升级)· 「实地」「厚势」一选就开不了局;策略五选一只有「拟人」有说明

- **现象(核实更正)**:条目原写「四个策略本身都能选、能下」,**不成立**。`AiSetupPage.tsx:509-510` 送的是 `ai:territory` / `ai:influence`,
  而真实策略 id 是 `ai:p:territory` / `ai:p:influence`(`core/constants.py:50-51`)。`/api/game/setup` 调 `update_player` →
  `ai_rank_estimation` → `AI_STRENGTH['ai:territory']` 抛 `KeyError`(2026-09-14 本机复现),开局 500,屏上贴英文原文。
  另外 `AI_STRATEGY_HINT` 只有 `ai:human` 一句,另四项说明行空着(实现 agent 登记「核 core/ai.py 后再写」)。
- **期望**:五个策略都能开局;每个策略选中时说明行说一句**与 `core/ai.py` 实现相符**的话。
- **验收**:
  1. 选「实地」「厚势」开局成功,`gameSetup` 收到的 `ai_strategy` 为 `ai:p:territory` / `ai:p:influence`;
  2. 说明行文案(已核实现):KataGo =「每手都下引擎搜索后的第一选择,不放水」(`DefaultStrategy`);
     实地 =「偏爱三线及以下的低位,在随机抽出的一批候选里按这个偏好挑,不是全力」(`TerritoryStrategy` + `threshold 3.5`、`pick_n 5`/`pick_frac 0.3`);
     厚势 =「偏爱四线及以上的高位,在随机抽出的一批候选里按这个偏好挑,不是全力」(`InfluenceStrategy`,三线及以内按 `line_weight 10` 压权);
     策略 =「不看搜索结果,直接下策略网络的第一直觉;开局前 22 手随机一些」(`PolicyStrategy` + `opening_moves 22`);
  3. 前端单测覆盖 1、2;一张真实运行时截图确认说明行不换行溢出(定高 `--opthint-h`)。
- **依赖**:无。

### A2(仅文案)+ A15 · P1/P2 · 升降级 503 一律说成「暂时不可用 / 本机不记成绩」

- **现象**:
  - A15:盒上 `/ai-ladder/status` 整条转发云端,网络异常变 503「Remote server unavailable」;前端 `useAiLadderStatus.ts:18`
    把所有 503 翻成「本机不记升降级成绩,暂时无法开始升降级对弈」—— 这句只对「云端节点没开升降级权威」成立,对盒子断网是错的。
    开局页 `AiSetupPage.tsx:178-182` 把 `/start` 的所有 503 写成「升降级引擎暂时不可用…请稍后再试」。
  - A2:顶端 6 档(准8段…超越人类)要 b18,盒子引擎只宣告 b6c96,开局预检必然 503「Ranked engine cannot serve the seated rung」,
    屏上却让人「请稍后再试」,对这 6 档永远不会恢复。怎么修(盒上挂 b18 / 强档走云端 / 标为不可入座)待 Fan 拍板(§4)。
- **期望**:按服务端 `detail` 分原因说话,不贴英文原文:
  断网/云端不可达 → 状态页「连不上云端。升降级对弈要联网,检查网络后点『重试』」,开局页再加「本次没有开局,也不影响你的段位」;
  节点无权威 → 原句「本机不记升降级成绩,暂时无法开始升降级对弈」;
  引擎带不动这一档 →「这台盒子的引擎现在带不动这一档对手。本次没有开局,也不影响你的段位」(不说「稍后再试」,因为对顶端 6 档不会自己好);
  预约/激活等云端确认(`awaiting cloud expiry` / `awaiting cloud reconciliation`)→「云端还没确认这一局的状态,先别重复开局;回到这一屏会显示它的状态」。
- **验收**:`aiLadderStatusErrorMessage` 与开局页 503 分支按上表分流;每种各一条单测;原有「本次没有开局」单测仍绿。galaxy 不受影响
  (它不会收到 `Remote server unavailable`),两套构建都绿。
- **依赖**:无。四棋类共享的 L1/L2/L3 逐态映射表(统一架构 §17 A 类欠账)不在本轮。

### N14 + A11(+ A9 中与拍板无关的一半)· P2/P3 · 右栏按对局类型摆对

- **现象**:
  - N14:`GameControlPanel.tsx:268-282` 的分析键只排除星阵局,升降级局照样渲染「领地」「AI支招」;领地能按亮,盘上永远不出色块
    (`GamePage.tsx:296` 对升降级不发分析、服务端也拒)。规范 §8「禁的时候整块不渲染」、实体对弈 PRD「升降级:支招按钮不可见」。
  - A11:`moveRows` 与棋谱折叠块钉死在 `engineMode` 上;升降级、本地对局、关掉「图表」的自由对弈,右栏看不到已下着法,中段空一块。
  - A9 的一半:`GamePage.tsx:291-302` 只要 `score` 开关为真就每手请求分析,本地对局根本不渲染胜率块,结果无处显示,白占本机引擎。
    (「图表」默认开还是关是 Fan 的决定,见 §4,本轮不动默认值。)
- **期望**:升降级局不渲染「领地」「AI支招」;凡胜率块不显示的局,右栏中段显示棋谱折叠块(与星阵屏同一构件,grow 吃掉剩余高度);
  「图表」开关只在胜率块真的会渲染的局里触发按需分析。
- **验收**:
  1. 升降级局动作区键为「数子 · 停一手 · 认输」,无「领地」「AI支招」「图表」「悔棋」;
  2. 升降级/本地对局/关掉图表的自由对弈显示 `data-fold="moves"` 棋谱块,开着图表的自由对弈仍显示胜率块(屏 05 四图不变);
  3. 本地对局 `score` 开关为真但领地关时,不调用 `API.analyzeCurrent`;
  4. **承重实测(真浏览器 1024×600)**:升降级局 200 手棋谱时,棋谱 body 自己溢出可滚(`scrollHeight > clientHeight` 且真滚轮拨得动)、
     右栏不滚、动作区贴右栏底、中段没有洞(显示开关排底 + 12 = 动作区顶);0 手时空态说话、中段没有洞、动作区贴底;本地对局同样量一次;
  5. 屏 05 四图重跑(自由对弈 fixture)无内容变化;升降级/本地对局右栏各截一张实现图,Fan 视觉确认。
- **依赖**:无(与 A7 待拍板互不阻塞:本地对局的「AI支招」灰键本轮不动)。

### A20 + A21(前端部分)· P2 · 改用屏幕落子后页面仍当自己在实体盘模式;重标定弹层文案与实际相反

- **现象**:
  - A20:`PhysicalSyncEscalationDialog.tsx:21-24`「改用屏幕落子」只调后端解绑;前端 `physicalPlay` 由挂载时读一次的偏好决定
    (`GamePage.tsx:204-207`),不会变。解绑后识别状态机回到未绑定、`poseLocked` 变假,1–4 秒后「棋盘可能被移动」弹层自动弹出,
    开关排右端常驻「标定丢失 · 请重新标定」,重置识别键、AI 落子坐标横幅、支招键仍按实体盘态显示。
  - A21:`RecalibrationModal.tsx:63` 写「无需 LED,对齐外框即可」,实际点「重新标定」跑的是要清空棋盘、会闪灯的 LED 13 点标定
    (`geometry_calibration_service.py:71-75`、`led_geometry_calibrator.py:276-279`);它的触发条件是识别「未绑定/刚绑定」,
    正常只在进实体盘对局头几秒闪一下;「棋盘检测异常」对话框叫人去点「横幅中的重新定位」,那条横幅早已不挂载(`VisionSyncOverlay.tsx:295`)。
- **期望**:
  - A20:按下「改用屏幕落子」后,本局前端也降级为屏幕模式(关掉识别绑定、重标定弹层、硬件故障句、重置识别键、AI 落子横幅、识别浮层),
    同一局刷新/从「继续上一局」回来仍保持屏幕模式;
  - A21(只做前端能独立改对的部分):弹层文案说真话(重新标定会亮灯、需要先清空棋盘;没挪过盘就「仍要继续」);
    弹层只在**本页已经锁定过位姿之后又丢失**时出现,进局头几秒的「未绑定/刚绑定」不再闪;
    「棋盘检测异常」对话框不再指向不存在的横幅。
- **验收**:
  1. 点「改用屏幕落子」→ `visionUnbind` 调用一次,随后页面不再渲染重标定弹层、识别浮层、AI 落子横幅,页控条无「重置识别」键,开关排无硬件故障句;
  2. `sessionStorage` 记下本局已降级,重挂载同一 `sessionId` 仍为屏幕模式;
  3. 进局时 `poseLocked` 从 false 到 true 之前不弹重标定弹层;锁定过后变 false 才弹;
  4. 弹层与「棋盘检测异常」对话框文案按上面改;前端单测覆盖 1–4;
  5. **必须上板**:RK3562 上实体盘对局触发一次跟不上 → 改用屏幕落子,确认 10 秒内无弹层、可继续屏幕落子。
- **依赖**:A21 的根子 V1(无 LED 外框重定位没接进对局主链)归「视觉/标定」模块;在 V1 落地前,弹层的「重新标定」仍是 LED 13 点标定,本条只让它说真话。

### N25 · P3 · 对局屏红条关不掉、印后端原文;断线后让盒上用户「刷新页面」

- **现象**:`GamePage.tsx:607` 的错误条没有 `onClose` / `autoHideDuration`;`useGameSession.ts:198-201` 一次性动作失败也写进
  `session.error` 且全文件没有 `setError(null)`,内容是「Request failed 409: {...}」;WS 断开只提示「请刷新页面」,全屏 chromium 无刷新手段。
- **期望**:一次性动作失败 → 一句人话,6 秒自动消失且可手动关;连接断开 → 持续显示(Fan 2026-08-21:连接断了是持续状态,不自动消失),
  可手动关,文案给盒上真能做的出口(退出对局后从「继续上一局」回来即重新连上)。
- **验收**:
  1. `useGameSession` 新增 `connectionLost: 'rejected' | 'dropped' | null`(服务端 1008 拒绝 / 意外断开 / 连着)与 `clearError()`(纯增量,`error` 文案不变,galaxy 行为不变);
  2. kiosk 对局屏:动作失败显示「这一步没有成功,请再试一次」,6 秒后消失,× 可关;意外断开显示 kiosk 文案(退出对局后从「继续上一局」回来即重连),不自动消失,× 可关;被拒(1008)仍显示原句(带原因与「请重新登录」,屏 05 几何闸量的就是那一态);
  3. 前端单测覆盖 1、2;两套构建都绿。WS 自动重连不在本轮(见 §5)。
- **依赖**:无。

## 4. 待 Fan 拍板

### A12-R(A12 与 N22 的升降级那一半)· 升降级局终局怎么判目

- **问题**:升降级局禁一切分析(反作弊),所以数子必 400、双停只记「无结论」不动段位。盒上实际只能靠认输分胜负(A18 修完后多一条超时)。
  要不要让升降级局也能「数出」胜负?结果会写进不可变账本、动段位。
- **选项**:
  - (a) 终局时(双停第二手之后,或人在自己回合按数子时)服务端用**本局引擎**补一次不交付的快速分析判胜负,与自由对弈同一套;
    代价:盒上是 b6c96 快速搜索,细棋可能判错且写进账本不可改。
  - (b) 同 (a),但 |目差| 小于阈值(如 2 目)记「无结论」不动段位 —— 判错的代价只落在「这盘白下」,不落在段位上。
  - (c) 维持现状:升降级不数子;数子键在升降级局撤掉,双停如实提示「本盘不计成绩,要分胜负请下完后认输」。
- **推荐**:(b)。账本不可改,判错不对称地贵;阈值只让细棋「不计」,不改变任何大差距的结果,也不需要额外模型。
- **不拍板时本轮**:升降级局维持现状(双停记「无结论」、数子 400),但 A12 把失败原因改成真话,N22 保证这种局至少进结算、不再卡住账号。

### A2 · 顶端 6 个 b18 档在盒上开不了局

- **问题**:准8段、准9段、9段、职业水平、职业顶尖、超越人类 6 档 `net="b18"`(`core/ladder.py:486/523/534/551/563/575`),
  盒子 `realtime_api.yaml` 只宣告 b6c96,开局预检必然 503。升到 7 段再升一档的用户从此在盒上开不了升降级局。
- **选项**:(a) 盒上加挂 b18(需先在 RK3562 2G 上量内存,跨仓改 smartbox provisioning);(b) 强档走云端(PRD 写过,`backend_hint/route` 全仓无人读,要从零实现);
  (c) 盒上把这 6 档标为不可入座(档位目录按设备能力裁剪,段位到顶就停在 7 段)。
- **推荐**:先 (c) 止血、同时排期量 (a)。(c) 让屏上说的和盒子能做的一致;(a) 是否可行取决于没人量过的内存数。
- **不拍板时本轮**:只改 503 文案(§3 A2+A15),不说「稍后再试」。设置页 AI 段位行恒标「服务器对弈」归训练营赛道 N26。

### A9 · 对局屏「图表」默认开还是关

- **问题**:规范 §8 写自由对弈「可开、默认关」,实现默认开,每换一手按需分析一次(没配云端分析引擎时与对弈引擎抢同一个本地 KataGo)。
  计划书两处、共享规范 §8 均标「等 Fan 定」,至今无答复。
- **选项**:(a) 维持默认开;(b) 默认关,设置中心加「对局中显示胜率图」开关。
- **推荐**:(b)。A12 修完后数子不再依赖它,原来阻止改默认值的耦合没了;默认关把盒上引擎留给 AI 落子。
- **不拍板时本轮**:默认值不动;只修与拍板无关的一半(本地对局不渲染胜率块却每手请求分析,§3 N14+A11)。

### A7 · 屏幕落子时要不要「AI支招」

- **问题**:支招键只在「自由对弈 + 实体盘落子」时可按(`GamePage.tsx:471-475`),其余局永久灰且不说原因,违反本文件自己的
  「永久不可用撤掉、暂时不可用灰着」判据。后端 `/api/v1/hint` 不要求实体盘(有编排器才亮灯),`HintPanel` 本身是屏上文字列表。
- **选项**:(a) 屏幕模式的自由对弈也开放支招(去掉 `physicalPlay` 条件);(b) 永久不可用的局撤键;(c) 保持灰键并补原因句。
- **推荐**:(a) 用于自由对弈 + (b) 用于本地对局。稿子屏 05 画的七键里就有「AI支招」;收费方向未定(A14)时,支招与领地同为免费,不新增账务风险。
- **不拍板时本轮**:不动(升降级局由 N14 撤键,那是规范已裁定的)。

### A14 · 对局内分析(领地/支招/变化图)收不收费

- **问题**:06-07 定「对弈分析按次付费」,09-03/05 Fan 改为会员制按算力计费(`galaxy-payment/requirements.md §0`),对局内分析没有再裁定;
  `hint_gate.py` 仍是协议桩,盒上所有 billing 接口 503、kiosk 无余额/兑换页面,盒端云端计费代理未做。
- **选项**:(a) 对局内分析免费(会员制只管复盘报告);(b) 纳入会员算力额度(需先做盒端计费代理);(c) 按次扣点。
- **推荐**:(a)。盒上计费链路整条不存在,(b)(c) 都要先做一条跨仓的代理;对局内分析算力小,留在会员权益里说得通。
- **不拍板时本轮**:不动。

### A17 · 围棋终局要不要胜负音效/人声/动画

- **问题**:象棋、国象、五子棋各有 feedback 模块(胜负人声、终局动画、声音设置弹层),2026-07-15 那份共享设计只写了三家,围棋没进范围也没人裁定不做。
  围棋盒上人声只有死活题 7 句;共享声音表无胜/负/和。
- **选项**:(a) 围棋进共享 feedback 范围(需确认词句与触发点:数子/中盘认输/超时,并生成人声素材);(b) 维持不做。
- **推荐**:(a),但排在本轮之后:终局结果本轮才判对(N21/N22/A12/A18),在错的结果上放「你赢了」只会把错说得更响。
- **不拍板时本轮**:不做。

### A19 · 实体盘对弈提子/悔棋时要不要语音提示

- **问题**:kiosk-physical-play PRD R2.3 定「屏幕列表 + 语音为主通道」;同日实施计划 Q6 自裁「复用落子/提子音效,一期从简」,
  没看到 Fan 确认放弃语音。被提的子正好压住蓝灯,屏上有列表但没有人声。可复用死活题里现成的「请拿走被提的子」一句。
- **选项**:(a) 补:`VisionSyncOverlay` 的 `capture_pending`/`illegal_change` 分支接 `useVoice().speak`;(b) 维持计划 Q6 的简化,把 PRD 改成与实现一致。
- **推荐**:(a)。素材已有,改动在一个组件内;记忆里的原则也是「拿除引导屏幕 + 语音为主」。
- **不拍板时本轮**:不做。

### Z6 · 开局设置「我执」加不加「随机」

- **问题**:屏 02 自由对弈和升降级都只有执黑/执白。track agent 2026-08-23 自裁的理由是「随机是搬象棋骨架带来的,四家里只有围棋多一条路」,
  与事实相反:国象开局设置、象棋人机设置都有「随机」,同一台盒子屏 09 星阵开局也有「猜先」。按 Fan 08-20「和另三家一致」判据可重开。
- **选项**:(a) 自由对弈加「随机」,升降级仍只给黑白;(b) 两处都加;(c) 维持两项。
- **推荐**:(a)。升降级的执色写进开局快照与账本,随机要服务端来掷才可信,另议;自由对弈前端掷即可。
- **不拍板时本轮**:不做(改动会动屏 02 四图,需要 Fan 视觉确认)。

## 5. 不在本轮

| 条目 | 理由 | 能否重开 |
|---|---|---|
| A1 左栏实体棋盘镜像是空盘 | 前置是**上板**核实空闲态识别线程是否在跑、2G 内存下轮询 `detected-board` 的开销;左栏由对弈/训练营/棋谱/课程四个一级页共用,属实体盘镜像(视觉/外壳)横切,本赛道单独接会与棋谱赛道同改 `KioskLayout` | 上板量完即可开 |
| A4 终局着法导航无 ±10 手 | 现行 27 屏稿子全是四键,实现与稿子一致;±10 手是 08-22 track agent 登记的欠账,不是屏上承诺 | Fan 说要补即开 |
| A5 终局无死子标记与目/子分解 | kiosk-ui-redesign 2026-07 评审后 descope(plan.md:1041),local-play PRD 沿用;现行稿子无终局屏 | 需先有稿子 + 后端 `dead_stones` |
| A6 「全部对局」卡无局数/报告数 | P3;数字要说清「谁数的」(本机/云端/缓存三档,见复盘列表口径),「已有报告数」另需接口;复盘赛道正在动同一数据链(S1/N7) | 复盘赛道落地后顺手补 |
| A10 升降级赌注不写升/退到哪一档 | 正路是服务端 status 带上相邻可入座档名(`ladder.step_playable_rung`);前端复刻跳封档规则等于另立账本。盒上 status 转发云端,需云端部署配合 | 可开,要排云端发布 |
| N20 AI 引擎挂掉时永远「AI 思考中」 | 本地与 HTTP 两种引擎的 `check_alive(exception_if_dead=True)` 都只记日志不抛(`core/engine.py:402-416`、`:740-745`),修法要改 `core/ai.py` 的等待循环(桌面版共用)并在 RK3562 上复现 OOM 验证;过渡期出口是认输/退出,N21 修完后判负正确 | 下一轮首项 |
| V1 无 LED 外框重定位没接进对局主链 | 归「视觉/标定」模块(A21 的根子) | 归其它模块 |
| N10 「继续上一局」等指针只在无痕浏览器、且不分账号 | 归棋谱/训练营赛道(ST2 待 Fan 定存哪) | 归其它模块 |
| N26 设置页 AI 段位行恒标「服务器对弈」 | 归训练营赛道 N26 | 归其它模块 |
| P8 大厅房间局没有自己的对局类型 | 归「人人对弈」模块;本轮 N21 只修 `/api/resign` 里判负方这一行 | 归其它模块 |
| N25 的 WS 自动重连 | 改的是共享 hook 的连接行为,galaxy 同受影响,需与 galaxy 一起验收;本轮只让红条可关、文案给出口 | 可开 |

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


| 文件 | 本赛道改什么(条目) | 可能重叠 |
|---|---|---|
| `katrain/web/server.py` | `/api/resign` 多人局传认输方(N21);`/api/count/request` 用按路数的门槛并先补分(N23/A12);`_apply_counted_result` / `_finish_ended_game` / 装 `manager.on_game_ended`,`/api/move` 自然终局改走收尾函数(N22) | 跨平台 X9(`/api/move` 平台局停一手 :983-984)、N13(平台局落账 :514)——N13 若要给星阵局补落账,应复用 `_finish_ended_game` 而不是另写一条 |
| `katrain/web/interface.py` | `_do_resign(loser=None)`(N21);`count_min_moves()`(N23);`ensure_current_score()`(A12);`game_ended_callback` 与 `_do_ai_move_and_broadcast` 收尾时调它(N22);`update_config` 记 `timer_configured`、`get_state` 下发 `timer.configured`(A18) | 跨平台(平台局状态字段) |
| `katrain/web/session.py` | `SessionManager.on_game_ended` / `_on_game_ended`,`create_session` 装 `game_ended_callback`;`WebSession.end_game_lock`(N22)。`_on_state` 不改 | 跨平台 N13 |
| `katrain/core/ai.py` | `generate_ai_move` 落子前「对局已结束则不落」(N21) | 复盘 R2 提到 `ai.py:232`(本轮不做) |
| `katrain/web/ui/src/kiosk/pages/GamePage.tsx` | 加载失败出口(N17)、本地对局认输框(N21)、数子在途与原因(A12)、超时回调(A18)、按需分析触发条件(A9 一半)、实体盘降级与重标定触发(A20/A21)、错误条(N25) | **跨平台 X7(:335、:501 两道 token 闸)、X9(星阵停一手/数子/AI 认输文案)** —— 同一文件多处并行改,合并时逐段对 |
| `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx` | 玩家卡时钟(A18)、升降级撤分析键(N14)、非胜率局显示棋谱(A11) | **跨平台 X9(:314-319 星阵动作键)** |
| `katrain/web/ui/src/kiosk/components/game/goClock.ts`(新)、`gameKinds.ts`(新) | 计时纯函数与 hook(A18);对局类型判别(N14/A11/A9) | — |
| `katrain/web/ui/src/kiosk/components/game/RecalibrationModal.tsx`、`components/physical/PhysicalSyncEscalationDialog.tsx`、`components/vision/VisionSyncOverlay.tsx` | 文案与降级回调(A20/A21) | 跨平台 X10(同目录 `EngineMoveErrorDialog.tsx`,不同文件) |
| `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx` | 策略 id 与说明(A3)、503 分原因(A2/A15) | — |
| `katrain/web/ui/src/features/aiLadder/useAiLadderStatus.ts`、`startErrors.ts`(新)(`copy.ts` 不改) | 503 分原因(A15)—— **共享领地,galaxy 同用** | — |
| `katrain/web/ui/src/hooks/useGameSession.ts` | 新增 `connectionLost`、`clearError`(N25)—— **共享领地** | 跨平台 X5(平台事件钩子消费者) |
| `katrain/web/ui/src/api.ts` | `GameState.timer.configured?: boolean` 类型(A18)—— **共享领地** | 所有赛道都可能动 |
| `katrain/web/ui/tests/kiosk-screen-05-play-ai.spec.ts`(新) | 升降级/本地对局右栏承重实测、计时态真实运行时证据 | 不改既有 `kiosk-screen-05-game.spec.ts`(跨平台 X9 可能改其中屏 10 用例) |
| 新测试文件:`tests/test_play_ai_endgame.py`、`tests/core/test_ai_commit_after_end.py`、`tests/web_ui/test_game_end_hook.py`、`tests/web_ui/test_play_ai_endgame_api.py`、`src/kiosk/pages/GamePage.playAi.test.tsx`、`src/kiosk/components/game/goClock.test.ts`、`src/kiosk/components/game/GameControlPanel.playAi.test.tsx`、`src/features/aiLadder/startErrors.test.ts`、`src/hooks/useGameSession.connection.test.tsx` | 新建 | — |
| 既有测试文件:`src/kiosk/pages/AiSetupPage.test.tsx`(末尾追加 A3/A15 两组)、`src/kiosk/components/game/GameControlPanel.test.tsx`(改一条被 A11 推翻的「棋谱只在星阵屏」)、`src/kiosk/pages/GamePage.test.tsx`(State B 两条改为「先锁定再丢失」起步,A21) | 追加 / 小改 | `GamePage.test.tsx`、`GameControlPanel.test.tsx` 跨平台 X7/X9 可能也改 |
| `superpowers/tracks/kiosk-go-play-ai/visual/*.png`、`board-checklist.md`(新) | 本赛道实现截图与上板清单 | — |

## 7. 验证方式

- **测试判据是基线 diff**:动手前在干净树上跑一遍全量 `CI=true uv run pytest tests -q -rfE` 与 `npx vitest run`,记下失败用例**名字集合**;
  每个 Task 结束比名字集合(`comm -13`),不比条数。进程级共享状态(`settings.DATABASE_URL`、`sys.modules["katrain.web.interface"]`)会把污染落到无关文件里。
- **后端**:各 Task 的新测试文件单跑 + 全量基线 diff。真 `WebKaTrain` 的测试放在 `tests/` 根目录(`tests/web_ui/conftest.py` 会把
  `katrain.web.interface` 整个换成 MagicMock,放进 web_ui 就只是在测一个替身);每条这类测试首行断言拿到的是真类。
  跑完查 `git status --short katrain/config.json` 为空(`force_package_config=True` 会写回仓里的 config.json)。
- **前端单测**:`cd katrain/web/ui && npx vitest run <文件>`;jsdom 只证行为与文案,不证布局。
- **类型检查**:`npx tsc -b`(`npx tsc --noEmit` 检查 0 个文件)。
- **两套构建**:凡改到共享领地(`src/hooks`、`src/api.ts`、`src/features`)的 Task 结束跑 `npm run build` 与 `npm run build:kiosk-2d`(含 `verify:kiosk-2d`)都绿;全部 Task 结束再各跑一次。
- **四图关卡**(CLAUDE.md,视觉通过需 Fan 确认):屏 05(N14/A11/A18 动了右栏)、屏 02(A3 说明行)重跑 `npm run fourup`,
  每屏跑两次 diff 两次结果得出本屏抖动地板,只提交有内容变化的屏;升降级/本地对局右栏、计时态、加载失败态(N17)稿子没有参考图,各截一张实现图交 Fan 单图确认。
- **承重实测**(真浏览器 1024×600,Playwright 打构建产物 → 先 `npm run build`):N14+A11 的右栏链 —— 满态(200 手)棋谱自己溢出可滚、右栏不滚、动作区贴底;
  最空态(0 手)不塌、动作区贴底;关系式先写死再读数。
- **必须上板(RK3562)**:A12 第 100 手数子耗时;N22 人先停 AI 跟停出胜负并入库、升降级双停后能开下一局;A20 改用屏幕落子后 10 秒无弹层;
  A18 一局「仅读秒 30秒×3」读秒走完判负。上板一次只跑一家(2G 内存)。
