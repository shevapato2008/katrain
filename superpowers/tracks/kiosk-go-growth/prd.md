# 围棋 kiosk · 成长 赛道 PRD(kiosk-go-growth)

- 日期:2026-09-20
- 分支 / worktree(**待创建**):`feature/kiosk-go-growth` @ `/Users/fan/Repositories/katrain-kiosk-go-growth`,基线 develop `012e2a04`
- 输入:2026-09-14「围棋 kiosk 缺口账本」成长模块三条(G1 G2 G3)
- **本文所有行号都在 develop `012e2a04` 上重核过(2026-09-20)**。账本成文于 `6f7dc629`,其后 develop 前进 234 个提交,`GrowthPage.tsx`、`endpoints/growth.py`、`models_db.py`、`ai_ladder_ranked.py` 的相关段落一行没动,三条结论全部仍然成立。

---

## 1. 背景与目标

成长屏(屏 22)已经不是占位页了:左栏段位、定级进度 / 净胜分、升降规矩,右栏四格数据条、「按对手强度」战绩、三档 `authority`(云端 / 本机缓存 / 本节点)都是真数据,2026-08-26 起盒上还会**先问云端**再退本机。

剩下三件,用户在屏上看得见:

1. **右下「能力诊断」永远是「样本 0 局」**,还挂着一个蓝标「后端已有 · 界面未接」—— 这句**说多了**:单局报告和逐手七档评级确实有,但「跨局汇总出你哪里弱」的逻辑**前后端都没有**。用户跑了十几份复盘报告,这块还是空的,而屏上那行字在暗示是界面懒得读。
2. **胜率那一格只能算升降级局**。`user_games` 这张表**没有任何一列记这个用户坐的是哪一方**,自由对弈、面对面、跨平台的局算不出胜负,所以标签只能写「升降级胜率」。这是诚实降级,不是假数据 —— 但它也意味着一个只下自由对弈的人,这一格永远是「—」。
3. **看不出自己在进步还是退步**:共享规范 §5(Fan 2026-07-27 定)要求左栏有近 30 天走势图和「本月 / 最高」两格、右栏有本周目标;围棋稿子屏 22 三块都没画,后端 `growth/summary` 也只回计数,没有按日期的序列。

这一轮要让盒上用户得到三件事:
1. 「能力诊断」要么说真话,要么别占着那块地方 —— 本轮让它**说真话**:按开局 / 中盘 / 官子三段算出失误率并写明样本量。
2. 胜率那一格覆盖**所有算得出的局**,而不只是升降级局 —— 办法是在对局库里记下「这个用户坐哪一方」,记不出的局照旧不算(不猜)。
3. 左栏能看出自己这 30 天是升是降 —— 一条**档位**走势,没有对局的那天不补点。

第三件(走势图)**2026-09-21 Fan 已拍板**:走势画**档位**,「本月 / 最高」两格维持现状(定级局 / 已解题),本周目标不做。见 §3 G3。

## 2. 已经做完、不要动的

| 内容 | 出处 |
|---|---|
| 左栏段位、定级 / 净胜分两态进度、升降规矩三条 | `GrowthPage.tsx:144-184` |
| 四格数据条 + 「数没取到就写 `—`,不写 0」的口径 | `GrowthPage.tsx:126-142` |
| 「按对手强度」战绩(打过哪档列哪档,不摆一排 0 胜 0 负) | `GrowthPage.tsx:224-246`、`ai_ladder_ranked.py:640-651` |
| 盒上**先问云端**再退本机,三档 `authority` 与四种退回原因各自记日志 | `endpoints/growth.py:95-131`、`repository.py:320-353` |
| 云端答 200 但少字段时退回本机缓存(`_looks_like_summary`) | `endpoints/growth.py:55-72` |
| 前端 `isGrowthSummary` 运行时校验(防「200 + 一页 HTML」把屏打白) | `kiosk/api/growthApi.ts:51-66` |
| 「一题没做过」和「没读到」分成两句话(已解题那一格) | `GrowthPage.tsx:74-86` |

---

## 3. 需求条目(本轮做)

### G1 · 「能力诊断」是写死的空态,而且标反了 —— P2

- **现象**:`GrowthPage.tsx:212-222` 整块没有任何 state / fetch,`<h4>` 恒为「样本 0 局」,标题右边挂着 `wip have` 蓝标「后端已有 · 界面未接」,说明里还写着「界面还没读(见复盘屏)」—— 复盘屏早就在读报告了。
- **根因(已核实)**:`endpoints/reports.py` 的路由只有 `POST /`、`GET /`、`GET /summary`、`retry`、`GET /{task_id}`、`GET /{task_id}/moves`,**全是单局粒度**;跨局聚合前后端都没有。逐手数据本身是齐的:`report_task_moves` 有 `grade`(七档,真源 `katrain/core/move_grade.yaml`)、`move_number`,`katrain/core/move_grade_core.py:40` 有 `phase_of(move_number, cfg)` 能判开局 / 中盘 / 官子。
- **期望**:
  - **口径(本赛道自裁,理由见下)**:诊断 = 最近 `N` 份**已完成**报告里,按 `phase_of` 分成开局 / 中盘 / 官子三段,各段算**失误率** = `isBad` 那三档(小亏 / 失误 / 恶手)的手数 ÷ 该段**被评级过**的手数。只数**本用户执的那一方**的手;`grade` 为空或 `unrated` 的手**不计入分母**(它们是「不知道」,不是「没问题」)。
  - 屏上说人话:三段各一行「开局 · 每 N 手有 M 手失误」,最弱的那段标出来;底下一行写**样本量**(「来自最近 X 份报告的 Y 手」)。
  - 样本不够(被评级的手数 < 200,或报告数 < 3)时**照实说**「样本还不够,再下几局」,并且仍然把已有的数显示出来 —— 但要带上样本量,不能让人拿 20 手的数当结论。
  - 一份报告都没有时:「还没有复盘报告」+ 一颗「去复盘」按钮(跳 `/kiosk/report`),**不写「样本 0 局」**(那句话在暗示是系统还没算)。
  - 那个蓝标 `wip have`**去掉**(不是改成琥珀):这块接上了就不是「未接」。
- **为什么是这个口径**:① 七档判级已经在服务端做完并落库,不用重新分析棋局;② `phase_of` 已有,阶段是玩家能听懂、也能行动的分法(「你官子弱」可以去做官子题);③ 不引入新的阈值轴 —— 仓里为「妙手 / 失误」散过五份阈值,那条路不能再走。
- **盒上怎么拿到数**:盒子(board 模式)上报告在云端,本机库里没有 ⇒ 这个端点必须和 `growth/summary` 同形:**先问云端,拿不到退本机,并如实标 `authority`**。屏上沿用已有的「本机记录」那句。
- **验收**:
  1. 后端单测:造两份报告的逐手数据(含 `grade` 为 NULL 的手、含对手执的手),断言分母只算**本用户执色且已评级**的手;三段的分子分母逐个对。
  2. 后端单测:一份报告都没有时回 `{"reports": 0, "graded_moves": 0, "phases": []}`,**不是 404、也不是 0.0 的三段**。
  3. 后端单测:盒上(有 dispatcher)云端可达时 `authority == "cloud"`;云端 503 时退本机并 `authority == "local_cache"`,且日志里写了退回原因。
  4. 前端单测:三段各一行、最弱那段有标记、样本量那句话在;样本不足时多一句「样本还不够」而数照显示。
  5. 前端单测:`reports === 0` 时屏上是「还没有复盘报告」+「去复盘」按钮,**屏上不出现「样本 0 局」**;点按钮落 `/kiosk/report`。
  6. 前端单测:请求失败时说「诊断没读到」,**不退回「样本 0 局」**(那是「没有数据」,不是「没读到」)。
  7. `rg 'diag_wip|后端已有 · 界面未接' katrain/web/ui/src` 零命中。
- **依赖 / 卡点**:无。后端 + 前端,本赛道自闭环。部署要按 §7 的顺序(先测试环境再生产)。

### G2 · 对局库不记「用户执哪一方」,自由 / 人人 / 跨平台局算不出胜率 —— P2

- **现象**:屏上那格写的是「升降级胜率 · 近 30 天」(`GrowthPage.tsx:137`),只下自由对弈的人这一格永远是「—」。
- **根因(已核实)**:`models_db.py` `UserGame`(:705-742)有 `player_black` / `player_white` / `result`,**没有 `user_color`**;`ai_ladder_game_ledger` 有(`:250`),所以只有升降级局的胜负是从用户视角记下来的。`user_game_repo.count_since`(:261)的 docstring 把这条写得很清楚:「拿玩家名去猜就是在编」。
- **期望**:
  - `UserGame` 加一列 `user_color = Column(String(1), nullable=True)`(取值 `'B'` / `'W'` / NULL)。**仓里没有 alembic**,加列走 `core/migrations.py` 的 `add_missing_columns`(幂等 `ALTER TABLE ADD COLUMN`,SQLite / PG 双兼容,已有链路)。
  - **算得出就写,算不出就 NULL,不猜**:
    - 人机局(`source=play_ai`、含星阵人机):人坐的那一方(`players_info` 里唯一 `human` 的座位;平台引擎局由 `_record_platform_engine_game` 显式给,它本来就知道 `human_color`)。
    - 面对面(`game_type=pvp_local`):两边都是人 ⇒ NULL(这一局没有「你」这一方)。
    - 导入 / 研究存谱:NULL。
    - 大厅房间局:本轮**不动**(它今天在盒上根本不落账,`game_repo` 恒为 None;归人人对弈赛道)。
  - `growth/summary` 多回三个字段:`decided_games_in_window` / `wins_in_window` / `losses_in_window`(只数 `user_color IS NOT NULL` 且 `result` 判得出胜负的局)。**原有的 `ranked_*` 字段一个都不删**(云端老版本、盒上缓存、galaxy 都在用)。
  - 屏上那一格改成「胜率 · 近 30 天」,并在**分母口径**上诚实:只有 `decided_games_in_window > 0` 才显示;窗口内有对局但一局都算不出执色时,写 `—` 并在下面那条 setnote 里加一句「有 N 局没记执色,算不进胜率」。
  - **不回填历史行**:这一列诞生之前的行没有这个事实,追认就是编。屏上那句 setnote 正是它的出口。
- **验收**:
  1. 后端单测:`UserGame.__table__.columns` 里有 `user_color`;新库 `create_all` 之后有,旧库跑 `add_missing_columns` 之后也有(用一个先建旧模型、再迁移的用例)。
  2. 后端单测:人机局落账后该行 `user_color` 是人坐的那一方;`pvp_local` 落账后是 NULL;平台引擎局是 `human_color`。
  3. 后端单测:`growth_summary` 的三个新字段只数 `user_color IS NOT NULL` 的局;`user_color` 为 NULL 的局**计入** `games_in_window`、**不计入**分母(两个数的口径不同,这条钉住)。
  4. 后端单测:老云端(响应里没有三个新字段)⇒ 盒上不崩,屏上退回写 `—`(`_looks_like_summary` 只查必需键,新字段是可选的)。
  5. 前端单测:`decided_games_in_window = 0` 而 `games_in_window = 5` 时,那一格是 `—`,并出现「有 5 局没记执色」那句。
  6. 前端单测:有胜负时那一格是百分比,标签是「胜率 · 近 30 天」。
- **依赖 / 卡点**:要部署到云端才对盒子生效(盒上先问云端)。按 §7:**先 home-ubuntu 再 ucloud**。


### G3 · 左栏没有走势图,看不出在进步还是退步 —— P2(**Fan 2026-09-21 已裁定:画档位**)

- **现象**:成长屏只看得到计数。共享规范 `kiosk-shell-spec.md:269-270`、`:1214`(v1.11,2026-07-27 Fan 定)要求左栏有近 30 天走势图(标出最高点);围棋稿子屏 22(`go-kiosk.tmpl.html:1970-2020`)没画,后端 `growth/summary` 也只回计数。
- **裁定(Fan 2026-09-21)**:
  - 走势画**档位**,不画净胜分(净胜分是 −2…+2 的锯齿,到 ±3 就清零,画成 30 天曲线读不出趋势)。
  - 「本月 / 最高」两格**维持现状**(定级局 / 已解题)—— 规范 §5 的这一处偏差就此登记为已裁定,不再是欠账。
  - **本周目标不做**(四家都没有,而且「目标」要一套设定入口,是一个新 feature 不是一格)。
- **数据源与它的前提**:`ai_ladder_game_ledger` 的 `opponent_rung` + `settled_at`。前提是
  `expected_opponent_rung` 的 docstring 那句「**定级之后玩家面对的就是自己那一档**」——
  所以定级**之后**的 `opponent_rung` 就是本人当时的档位。这个前提要**用一条测试钉住**,前提变了它先红。
- **定级期那 5 局必须排除**:那时的 `opponent_rung` 是二分搜索的中点,不是实力。账本里没有一列写着
  「这局是不是定级局」,唯一摘得出来的办法是**按时间取前 `PLACEMENT_GAMES`(=5)局**。
- **没有对局的那天不补点**:把昨天的值延续到今天,会画出一条「你在进步」的假曲线。折线断开。
- **走势并进 `growth/summary` 的响应(不另开端点)**:那条链已经有「盒上先问云端 → 退本机 → 三档
  `authority`」,新开一个端点等于把那套再写一遍。新键是**可选**的,老云端不回它时屏上不画走势
  (**不画**,不是画一条空轴)。
- **验收**:
  1. 后端单测:定级后 6 局、跨 3 天 ⇒ 每天取**当天最后一局**的档位,共 3 个点。
  2. 后端单测:只有 4 局(还在定级期)⇒ 走势是空数组,**不是**把定级局的中点画出来。
  3. 后端单测(**前提闸**):`expected_opponent_rung(rung, lo, hi) == rung`(已定级)——
     这条一旦红,说明「对手档 = 自己档」的前提变了,走势图的数据源随之作废。
  4. 前端单测:纯函数 `trendPath` 给出折线与最高点;点数 < 2 时返回 `null`(屏上写一句话,不画图)。
  5. 前端单测:老云端(响应里没有 `rung_trend`)⇒ 左栏不出现走势块,其余照常。
- **依赖 / 卡点**:无(与 G2 同一份部署)。左栏加了一块 ⇒ 屏 22 四图重取并交 Fan 确认。

---

## 4. 待 Fan 拍板

### G1-口径 · 诊断的样本量门槛与分法(信息项,不必回复)

本赛道自裁:**按开局 / 中盘 / 官子三段算失误率**,样本量写在旁边,被评级手数 < 200 或报告 < 3 份时加一句「样本还不够」。理由见 §3 G1。若 Fan 想要别的分法(例如按棋形分类),说一声就改 —— 口径只有一处(后端聚合函数),换起来不贵。

---

## 5. 不在本轮

| 条目 | 类别 | 一句理由 |
|---|---|---|
| 「本月 / 最高」两格、本周目标 | **Fan 2026-09-21 裁定不做** | 两格维持「定级局 / 已解题」;本周目标四家都没有,要做得先有一套设定入口。 |
| 大厅 / 房间局的 `user_color` 与落账 | 归人人对弈 | 盒上 `game_repo` 恒为 None,那一族落账问题(P9)整体挂在跨盒路线决策上。 |
| 报告判级按段位缩放(R2) | 归 move-grading(已裁定留下) | `docs/move-grading/design.md:290-300` 自收的范围,要先定段位数据源。 |
| 「能力诊断」做成可下钻(点一段看是哪几局) | 未立项 | 本轮先把一句真话说出来;下钻要新的接口与一屏。 |
| galaxy 成长页 | 归 galaxy | 本轮只动 kiosk 屏 22 与后端;`growth/summary` 的新字段对 galaxy 是可选的。 |

## 6. 与其它赛道的协调与共享文件

### 6.0 四条新赛道统一协调规则(2026-09-20 写定,四份 PRD 同文)

**基线**:直播 / 成长 / 设置 / 视觉四条赛道都从 develop `012e2a04` 开出。上一轮五条赛道里 4 条已并入 develop,只剩 **`feature/kiosk-go-kifu`(`bd30cc39`)未合并**,它改 `KioskApp.tsx` 的路由段(:133-150)与 `KifuPage.tsx`(顶部 import、搜索卡、列表错误块)。

**会撞的地方(按风险排序)**

1. **`KifuPage.tsx` / `KioskApp.tsx` 与未合并的 kifu 分支**:直播赛道要在 `KifuPage.tsx` 的直播那一段(:378-417)加一行入口,设置赛道要删 `KioskApp.tsx` 的 `OrientationProvider` / `RotationWrapper`(:34、:41、:202-214)。两处与 kifu 的 hunk 都不相邻,属文本冲突。**规则:先合 kifu,再合这两家**;谁后合谁负责 rebase。
2. **`GeometryContext` 的状态词(`phase` / `loaded` / `capabilities`)**:设置赛道 ST5 要在设置屏说「还没问到 / 没有摄像头」,视觉赛道 V2/V3 要改标定屏说「取消了还能沿用 / 这台盒子没有 LED」。**规则:`GeometryContext.tsx` 与 `geometryApi.ts` 归视觉赛道改,设置赛道只消费**;同一件事的措辞以视觉赛道为准,设置赛道照抄。
3. **`server.py`**:成长赛道 G2 只在 `_record_ai_game_locked` 的 `data` 字典(:1829-1843)与 `_record_platform_engine_game` 的 `data_overrides`(:3569)各加一个键,**不碰终局收尾入口 `_finish_ended_game`**(上一轮定的唯一入口);视觉赛道只改挂 `GeometryCalibrationService` 的那一段(:760-825)。两处不相邻。
4. **数据库迁移**:仓里**没有 alembic**(装着包但没有 env.py / 版本链)。加列只走 `katrain/web/core/migrations.py` 的 `add_missing_columns`(在模型上加一列可空列即可,它是幂等的 `ALTER TABLE ADD COLUMN`,SQLite / PG 双兼容)。本轮只有成长赛道 G2 加一列,其余三家零迁移。
5. **i18n**:四家都只写 `t('ns:key','中文默认')`,**本轮不改任何 `.po`**(并行改 11 份必冲突)。合并完统一交 `katrain-i18n-expert`,各赛道交付时附新增 key 清单。
6. **四图存档**:直播取屏 18 与新的直播列表屏、成长 22、设置 27、视觉 26,目录各不相同。重取前按 CLAUDE.md 跑**两次**比对排除抖动(canvas 屏抖动量级 ~4500 像素,DOM 屏 ~200)。
7. **两套构建**:四家只要碰了 `src/hooks/`、`src/api/`、`src/utils/`、`src/components/` 就必须 `npm run build` 与 `npm run build:kiosk-2d` 都绿;共享文件不许 import `src/kiosk/**`。

**合并顺序(默认)**:`kifu`(上一轮遗留) → **视觉** → **设置** → **成长** → **直播**。
理由:视觉改的是标定语义,设置屏要引用它的状态词;成长动数据库和云端,要按「先测试环境再生产」单独排期(见成长 PRD §7);直播要等 kifu 落地后才动 `KifuPage.tsx`。
例外:任一赛道里**不碰上面 1–4 条**的单个 Task 可以拆出来先合。

**每次合并前**:`git merge develop`,跑本赛道 plan 的 Global Constraints(两套构建 + `npx tsc -b` + 基线 diff),并对照本节查**语义**冲突 —— git 报「合得干净」不等于合得对。

### 6.1 本赛道会改、可能与别家重叠的文件

| 文件 | 本赛道改什么 | 可能重叠 |
|---|---|---|
| `katrain/web/core/models_db.py` | `UserGame` 加一列 `user_color`(G2) | 无(其余三家零模型改动) |
| `katrain/web/server.py` | `_record_ai_game_locked` 的 `data` 加一键(:1829-1843);`_record_platform_engine_game` 的 `data_overrides` 加一键(:3569) | **无**,但这是上一轮两条赛道打过架的文件 —— **不许碰 `_finish_ended_game`** |
| `katrain/web/core/user_game_repo.py` | `create` / `create_ai_ladder_ranked` 透传 `user_color`;新增按执色数胜负的查询(G2) | 无 |
| `katrain/web/core/ai_ladder_ranked.py` | `growth_summary` 不动;G3 若做则新增 `rung_trend`(**只读**) | 无 |
| `katrain/web/api/v1/endpoints/growth.py` | `summary` 多三个字段;新增 `GET /growth/diagnosis`(G1) | 无 |
| `katrain/web/core/repository.py`、`remote_client.py` | 新增 `growth_diagnosis_remote` / `get_growth_diagnosis`,照抄 `growth_summary_remote` 的四种退回原因 | 无 |
| `katrain/web/ui/src/kiosk/api/growthApi.ts` | 新增 `GrowthDiagnosis` 类型与运行时校验;`GrowthSummary` 加三个**可选**字段 | 无 |
| `katrain/web/ui/src/kiosk/pages/GrowthPage.tsx`(+`__tests__/GrowthPage.test.tsx`) | G1 诊断块、G2 胜率那一格与 setnote | 无 |
| `katrain/i18n/locales/*/katrain.po` | **不改**(见 §6.0 第 5 条) | 全部 |

## 7. 验证方式

| 层 | 适用条目 | 做法 |
|---|---|---|
| 基线 diff(前端) | 全部 | 动手前跑一遍全量 vitest,记失败用例的**名字集合**;收尾再跑,`comm` 比名字集合。 |
| 基线 diff(Python) | G1 G2 | 动手前 `CI=true uv run pytest tests --continue-on-collection-errors -q` 记 `^FAILED\|^ERROR` 的名字集合(新 worktree 要先 `uv sync --extra web`,否则缺 fastapi 会让基线静默为空)。 |
| 后端单测 | G1 G2 | 见各条验收。新用例放 `tests/web_ui/test_growth_diagnosis.py`、`tests/web_ui/test_user_game_color.py`。 |
| 前端单测 | G1 G2 | 见各条验收(`src/kiosk/__tests__/GrowthPage.test.tsx`)。 |
| 类型检查 | 全部 | `npx tsc -b`。 |
| 两套构建 | 全部 | `npm run build` 与 `npm run build:kiosk-2d`。 |
| 格式化 | Python | `uv run black -l 120 <改过的文件>`。 |
| **SQLite 弱于生产的那几条** | G2 | 新列是可空的,不涉及跨 schema 外键 / 行锁;但 `settled_at` / `created_at` 的时区断言**只在 PG 上说了算**(SQLite 不存时区)—— 沿用既有 `test_growth_authority.py` 的 skip 口径,**不许为了变绿改断言**。 |
| 四图对比 | G1 G2 | 屏 22 有参考图 ⇒ **触发**:`npm run fourup` 重取屏 22,四图一起看(参考 / 实现 / 并排 / 差异)。它是 DOM 屏(抖动 ~200 像素),重取前跑两次比对排除抖动。**未经 Fan 确认不得进入后端阶段的收尾**。 |
| 承重结构实测 | G1 | 诊断块是**会长的东西**(三段 + 样本量 + 可能的「样本不够」那句)。把数据造到最满(三段都有、都带长文案)在 1024×600 真浏览器里量:右栏不出现溢出、`gdiag` 两块不被挤扁;另按「塌陷要在最空状态下量」再量一次**最空**(`reports=0`)那一态。jsdom 不作数。 |
| 部署 | G1 G2 | **先 home-ubuntu(go.sailorvoyage.top)再 ucloud-v100(modelstella.com)**(Fan 2026-08-31 裁定)。盒子先问云端 ⇒ 云端没部署时盒上看不到新字段,但**必须不崩**(验收 G2-4 钉的就是这条)。 |
| 上板(建议,Fan 定时机) | G1 G2 | 盒上开成长屏:诊断块有数且样本量说得出、胜率那一格覆盖自由对弈的局;断开云端再看一次,三档 `authority` 的话对得上。RK3562 2G,一次只跑一家。 |
