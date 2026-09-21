# 围棋 kiosk · 直播 赛道 PRD(kiosk-go-live)

- 日期:2026-09-20
- 分支 / worktree(**已创建 2026-09-21**):`feature/kiosk-go-live` @ `/Users/fan/Repositories/katrain-kiosk-go-live`,基线 develop `7a152df1`
- 输入:2026-09-14「围棋 kiosk 缺口账本」直播模块三条(L1 L2 L3)
- **本文所有行号都在 develop `012e2a04` 上重核过(2026-09-20)**。账本成文于 `6f7dc629`,其后 develop 前进 234 个提交,直播相关文件(`LivePage.tsx`、`LiveMatchPage.tsx`、`KifuPage.tsx`、`models_db.py`、`cron/clients/*`)一行没动,三条结论全部仍然成立。 **2026-09-21 基线移到 develop `7a152df1`**(其后 43 个提交是视觉识别稳定性与退出兜底):本文引用的文件里只有 `server.py` 行号漂移(§6.0 那两处),已按新基线改。

---

## 1. 背景与目标

盒上今天能看直播:棋谱屏(屏 15)底部「职业直播」摆 4 行,点进去是重画过的观战屏(屏 18),跟到最新手、试下、AI 标记、领地都在,盒上走 `/api/v1/board/live` 代理。

缺的是**这 4 行以外的一切**:

- 后端一次给 8 条、库里可能有几十条,屏上只画前 4 行,**没有「更多」**。
- 「即将开始」的赛程只在 `/kiosk/live` 那一页渲染,而那一页**全 kiosk 没有任何入口**,进去了也没有返回键、没有 Dock —— 它是个孤儿路由,盒上等于不存在。
- 那一页还是 7 月的 MUI 皮:里面的胜率条读的是 `current_winrate`,而这个数在三个源里**有两个是编的**(`pandanet.py:125` 无条件写 `0.5`;`xingzhen.py` 取不到时退回 `0.5`);「官方信息」是 `target="_blank"` 外链,盒上 chromium 跑 `--kiosk`,点开就是一条没有返回路的死胡同。

这一轮要让盒上用户得到两件事:
1. 从棋谱屏能走到**完整的直播列表和赛程**,并且走得回来。
2. 那一页上不再出现编出来的数和走不回来的链接。

第三件(观战屏的钟)不是做不做的问题,是**数据在不在**:整条直播链从抓取到库到前端类型都没有时间字段。本轮先用一个有界的探针把「三个源到底给不给剩余时间」查清楚并落档,再决定要不要开这个工。

## 2. 已经做完、不要动的

| 内容 | 出处 |
|---|---|
| 观战屏(屏 18)重画:跟到最新、试下、AI 标记、领地、着法表、折叠头胜率 | `cfe19c54`(2026-08-24) |
| 观战屏那台「跟着直播长」的状态机(从 `PlaybackBar` 搬进本页) | `LiveMatchPage.tsx:100-108` |
| 「`current_winrate` 不许上屏」这条裁定:屏上胜率只认盒内 KataGo 算出来的 `analysis[n].winrate` | `LiveMatchPage.tsx:74-77` 注释 |
| 棋谱屏那四行直播(状态标、来源名、断网整块不渲染) | `KifuPage.tsx:378-417` |
| 盒上直播走云端代理 | `/api/v1/board/live` |
| kiosk 构建下 `api/live.ts` 的写操作一律抛错(观战是只读的) | `api/live.ts:19-24` |

---

## 3. 需求条目(本轮做)

### L1 · 盒上看不到第 5 场以后的直播和「即将开始」赛程 —— P2

- **现象**:
  - 棋谱屏 `useLiveMatches({ limit: 8 })`(`KifuPage.tsx:94`)只画 `matches.slice(0, 4)`(`:386`),没有「更多」。
  - `/kiosk/live`(`KioskApp.tsx:157`)没有任何入口:全仓唯一跳转是它自己第 52 行进观战;观战屏返回**特意去棋谱**(`LiveMatchPage.tsx:149`、`:252`),不回它。
  - 那一页没有页控条、没有返回键,`dockLevelOf` 判它是 L2 ⇒ 无 Dock。**进去出不来**。
  - 赛程 `UpcomingList`(`LivePage.tsx:230`)只在这一页渲染 ⇒ 盒上完全看不到。
- **附带缺陷(只在这一页里,补了入口就会暴露)**:
  - `MatchCard.tsx:25` `const blackAdvantage = match.current_winrate > 0.5;` —— 这个数在 pandanet 源里恒为写死的 `0.5`,在 xingzhen 源里取不到时也退回 `0.5`。**「真的均势」和「没有这个数」在库里是同一个值**,画成胜率条就是编。屏 18 已经为同一件事裁过一次(见 §2)。
  - `UpcomingList.tsx:159-160` `href={event.source_url} target="_blank"` —— 盒上 chromium 是 `--kiosk`,新标签页没有地址栏也没有返回键。
- **期望(方案 B,Fan 2026-09-21 已定)**:
  - `/kiosk/live` **接壳**:加页控条(返回去棋谱)、滚动区、分段控件(直播中 / 已结束 / 即将开始),列表换成外壳的 `.kiosk-row`。**不重排信息结构**(仍是「一列比赛 + 一段赛程」),这是 Fan 2026-08-20 对稿外五屏的裁定。
  - 去掉三样东西:棋盘预览(`LiveBoard` 是 canvas,盒上那一族实测只有 6–15fps,列表页不需要)、胜率条(数是编的)、`target="_blank"` 外链(改成把来源写成文字)。
  - 棋谱屏那一组补一行「全部直播 · 赛程」入口(不是第 5 张卡,是那一组的末行),跳 `/kiosk/live`。
  - 观战屏返回:从直播列表进来的回列表,从棋谱进来的回棋谱(带 `state.from`,缺省回棋谱,与今天一致)。
- **验收**:
  1. 单测:`/kiosk/live` 渲染出页控条返回键,点它落在 `/kiosk/kifu`。
  2. 单测:8 条直播里全部 8 行都在列表上(棋谱屏仍只画 4 行,这一条同时钉住两屏的分工)。
  3. 单测:「即将开始」分段渲染出赛程行,且整页 `container.querySelectorAll('[target="_blank"]').length === 0`。
  4. 单测:整页不出现任何 MUI 类名(`[class*="Mui"]` 零命中)。
  5. 单测:`current_winrate` 不出现在屏上(渲染一条 `current_winrate: 0.5` 的比赛,断言没有百分比文本、没有 `.wrbar` 之类的条)。
  6. 单测:棋谱屏那一行入口点下去落在 `/kiosk/live`。
  7. 单测:观战屏带 `state.from='live'` 时返回落 `/kiosk/live`,不带时落 `/kiosk/kifu`。
  8. 真运行时预览一帧(vite dev + Playwright,拦 `/api/v1/live/*` 给桩数据),人眼确认 1024×600 里列表不溢出、分段与页控条位置与屏 18 一致。
- **依赖 / 卡点**:无(Fan 2026-09-21 选 B,见 §4)。纯前端,无后端改动。

### L2 · 观战屏不显示剩余时间/读秒 —— P2(本轮只做探针,不做实现)

- **现象**:稿子屏 18 画了 `28:14 剩余`(`go-kiosk.tmpl.html:1693`),实现里玩家卡的钟整格不渲染。
- **根因(已核实,`012e2a04` 仍然如此)**:
  - `models_db.py` `LiveMatchDB`(:332-357)没有任何时间列;`types/live.ts:6-26` `MatchSummary` 也没有。
  - `cron/clients/xingzhen.py` 只读 `startTime`;`cron/clients/pandanet.py:193` 解析出来的 `byo_time` 是**读秒设定**(每手几秒),不是剩余时间。
- **本轮只做**:一个有界的可得性探针 —— 逐个源确认「协议里到底有没有剩余时间」,结论写进 `findings-clock.md`,并按结论二选一:
  - 三个源都给不出 ⇒ 把这条从「缺口」改判为「链路上没有这个数」,在 `LiveMatchPage.tsx` 的钟注释里补上探针日期与证据,**本轮到此为止**。
  - 至少一个源给得出 ⇒ 开一份后续计划(加列 + cron 写入 + 类型 + 屏 18 只对有数的源渲染),本轮不实现。
- **为什么不直接做**:加一列、改轮询、改前端是三层改动,而它的前提是一个我们还没验过的事实。先验前提,再决定要不要付这三层的钱。
- **验收**:`findings-clock.md` 里每个源各一段:接口 / 抓取代码路径 / 字段清单 / 结论,每段都要能指到一行代码或一份真实响应。结论是「没有」的,要写明**在哪一层没有**(上游协议 / 抓取代码丢了 / 库没存)。
- **依赖 / 卡点**:第三方接口。探针本身不依赖上板。

---

## 4. 待 Fan 拍板

### L1 · 删掉 `/kiosk/live`,还是补入口并接壳 —— **已定:B(Fan 2026-09-21)**

- **A. 删路由**:`KioskApp.tsx:157` 那条路由连同 `LivePage.tsx` 一起删,棋谱屏那 4 行就是直播的全部;赛程盒上永远不做。成本最低,代价是**后端已经在抓的赛程数据盒上永远用不上**,而且棋谱屏那一组「来源:星阵 · 弈客」在只给 4 行时显得像全部。
- **B. 补入口 + 接壳(推荐)**:按 §3 L1 做。成本是一屏接壳 + 一行入口 + 观战屏返回去向,纯前端。
- **推荐 B 的理由**:① 数据已经在库里、cron 已经在抓,不用它是白抓;② 「即将开始」是这台盒子上唯一的赛事日历,对教室场景有用;③ 接壳的工作量被 Fan 2026-08-20 的「只接壳不重排」限住了,不是重画一屏。
- **裁定(2026-09-21)**:Fan 选 **B**。按计划 Task 2–6 做;plan 附录 A 作废,留作记录不执行。

#### 「补入口并接壳」到底改什么(2026-09-21 Fan 问,答复如下;同日 Fan 选 B)

**一句话**:**不重新设计这一屏**,只把它从「7 月的 MUI 孤儿页」换成和别的屏同一套外壳,并在棋谱屏加一行门。
「接壳」是 Fan 2026-08-20 对稿外五屏的原话「只接壳不重排」——接壳 = 换控件与框架,重排 = 改信息结构,这次只做前者。

| | 今天 | 改完 |
|---|---|---|
| 怎么进去 | **没有入口**,只能手输 URL | 棋谱屏「职业直播」那一组末尾多一行「全部直播 · 赛程」 |
| 怎么出来 | 没有返回键、没有 Dock ⇒ **出不来** | 顶上一条标准页控条,返回去棋谱 |
| 切换 | MUI `Tabs` | 页控条上的分段:直播中 / 已结束 / 即将开始(和标定屏、课程屏同一个控件) |
| 列表 | MUI `Card` 卡片 + 棋盘预览(canvas) | 外壳的 `.kiosk-row` 行,和棋谱屏那四行长得一样;**不画棋盘预览**(canvas 在盒上只有 6–15fps,列表页不需要盘) |
| 胜率条 | 有,读 `current_winrate` | **删掉**(pandanet 源恒写 `0.5`、xingzhen 取不到也退回 `0.5` ⇒ 那是编的;屏 18 早为同一件事裁过) |
| 赛程 | 只有这一页有,但进不来 | 第三个分段;**来源写成文字**,不再是 `target="_blank"` 外链(盒上 chromium 是 `--kiosk`,点开回不来) |
| 观战屏返回 | 恒回棋谱 | 从列表进来的回列表,从棋谱进来的回棋谱 |

**信息结构一个字不动**:仍然是「一列比赛 + 一段赛程」,没有新增内容、没有重新分栏。
**代价**:一屏接壳 + 一行入口 + 观战屏返回去向,纯前端,无后端改动(计划 Task 2–6)。

### L3 · 观战屏要不要把胜率走势图 / 自动播放 / 推荐列表加回来

- **事实**:`cfe19c54`(2026-08-24)删这三块是 track agent 自裁,理由是**放不下**(右栏 516 已排满,余量上限 101px,而 eval 折叠块实测 128)和**旧走势图造假**(`TrendChart.tsx:35-37` 给没算过的手一律补 50)。但 2026-06-23 锁定的 `sbc-live-parity` PRD D3 定的是「全量对齐 Galaxy:回放 + AI 推荐 + 趋势图」,**没有 Fan 推翻那条的记录**。
- **前提**:要加回走势图,得先解决直播分析稀疏(盒内 KataGo 只算得动一部分手),否则又是一条贴着中线的假平线 —— 那正是当初删它的理由之一,`go-screens.css:461` 把这条禁令写成了文字。
- **推荐**:维持现状(不加回),把 PRD D3 的范围改判登记为**已发生**;要重开则先立「直播分析补算」的活,再谈画图。
- **不拍板时本轮怎么处理**:不做,不进计划。

### L3-评论 · 直播评论区

- kiosk 构建下 `api/live.ts:19-24` 写操作一律抛错,盒上没有评论入口;galaxy 那边 `CommentSection` / `useComments` 自 2026-01-26 起零消费者(当时是「暂时隐藏」,不是产品决定停用)。
- **推荐**:盒上继续不做(一体机没有输入法体验可言,且要接内容审核)。galaxy 那半归 galaxy,不在本赛道。

---

## 5. 不在本轮

| 条目 | 类别 | 一句理由 |
|---|---|---|
| L2 的实现(加列 / cron 写入 / 屏 18 渲染) | 探针之后 | 见 §3 L2:先验「源给不给」,再决定开不开工。 |
| L3 走势图 / 自动播放 / 推荐列表 | 待 Fan | 见 §4。 |
| 直播评论区 | 待 Fan(推荐不做) | 见 §4。 |
| galaxy 的 `LivePage` / `MatchCard` / `UpcomingList` | 归 galaxy | 本轮只动 kiosk 那一屏;共享件**不改**(见 §6.1),否则 galaxy 跟着变样。 |
| 直播分析稀疏(盒内 KataGo 算不过来) | 归后端 / 未立项 | 它是 L3 的前提,不是本轮的活。 |
| 棋谱屏其余部分(搜索、摆谱入口、列表错误块) | 归 kifu 赛道 | `feature/kiosk-go-kifu` 尚未合并,见 §6.0。 |

## 6. 与其它赛道的协调与共享文件

### 6.0 四条新赛道统一协调规则(2026-09-20 写定,四份 PRD 同文)

**基线**:直播 / 成长 / 设置 / 视觉四条赛道都从 develop `7a152df1` 开出。上一轮五条赛道里 4 条已并入 develop,只剩 **`feature/kiosk-go-kifu`(`bd30cc39`)未合并**,它改 `KioskApp.tsx` 的路由段(:133-150)与 `KifuPage.tsx`(顶部 import、搜索卡、列表错误块)。

**会撞的地方(按风险排序)**

1. **`KifuPage.tsx` / `KioskApp.tsx` 与未合并的 kifu 分支**:直播赛道要在 `KifuPage.tsx` 的直播那一段(:378-417)加一行入口,设置赛道要删 `KioskApp.tsx` 的 `OrientationProvider` / `RotationWrapper`(:34、:41、:202-214)。两处与 kifu 的 hunk 都不相邻,属文本冲突。**规则:先合 kifu,再合这两家**;谁后合谁负责 rebase。
2. **`GeometryContext` 的状态词(`phase` / `loaded` / `capabilities`)**:设置赛道 ST5 要在设置屏说「还没问到 / 没有摄像头」,视觉赛道 V2/V3 要改标定屏说「取消了还能沿用 / 这台盒子没有 LED」。**规则:`GeometryContext.tsx` 与 `geometryApi.ts` 归视觉赛道改,设置赛道只消费**;同一件事的措辞以视觉赛道为准,设置赛道照抄。
3. **`server.py`**:成长赛道 G2 只在 `_record_ai_game_locked` 的 `data` 字典(:1830-1844)与 `_record_platform_engine_game` 的 `data_overrides`(:3615)各加一个键,**不碰终局收尾入口 `_finish_ended_game`**(上一轮定的唯一入口);视觉赛道只改挂 `GeometryCalibrationService` 的那一段(:761-826)。两处不相邻。
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
| `katrain/web/ui/src/kiosk/pages/LivePage.tsx` | 整屏接壳重写 | 无(kiosk 独占) |
| `katrain/web/ui/src/kiosk/__tests__/LivePage.test.tsx` | 重写(现有 163 行按旧 MUI 结构写的) | 无 |
| `katrain/web/ui/src/kiosk/pages/KifuPage.tsx` | 只在直播那一段(:378-417)末尾加一行入口 | **kifu 分支**(改的是 :1-10 / :90-135 / :233-270) |
| `katrain/web/ui/src/kiosk/pages/LiveMatchPage.tsx` | 返回去向读 `location.state.from` | 无 |
| `katrain/web/ui/src/hooks/live/useUpcomingMatches.ts`(**新建**,共享领地) | 赛程数据钩子(galaxy 的 `UpcomingList` 自己抓,不动它) | 无,但两套构建都要绿 |
| `katrain/web/ui/src/components/live/*`(`MatchCard` / `UpcomingList` / `MatchList` / `LiveBoard`) | **不改**。kiosk 那屏不再引用前三个 | galaxy 在用 |
| `katrain/i18n/locales/*/katrain.po` | **不改**(见 §6.0 第 5 条) | 全部 |

## 7. 验证方式

| 层 | 适用条目 | 做法 |
|---|---|---|
| 基线 diff | 全部 | 动手前跑一遍全量 vitest,记下失败用例的**名字集合**;收尾再跑,用 `comm` 比名字集合,不比条数。 |
| 单测(vitest) | L1 | 见 §3 L1 验收 1–7。 |
| 类型检查 | 全部 | `npx tsc -b`(`npx tsc --noEmit` 检查 0 个文件,无效)。 |
| 两套构建 | 全部(新建了 `src/hooks/live/` 下的共享文件) | `npm run build` 与 `npm run build:kiosk-2d`(含 `verify:kiosk-2d`)都绿。 |
| PO 闸 | L1(新增 kiosk 文案) | `npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-contract.spec.ts`。 |
| 四图对比 | **屏 18 不触发**(没改它的版式);新的直播列表屏**稿子里没有这一屏** ⇒ 没有参考图可比 | 取一帧实现图存进 `superpowers/tracks/kiosk-go-live/visual/live-list/`,并在 README 里写明「稿外屏,无参考图」——**不要伪造一张参考图凑四图**。 |
| 承重结构实测 | L1 | 新列表屏是「会长的东西」:造 50 条直播 + 20 条赛程,在 1024×600 真浏览器里量列表容器 `scrollHeight > clientHeight` 且页面本身不出现横向/纵向溢出;分段切换后页控条 y 坐标不变(70–114)。jsdom 不作数。 |
| 真运行时预览 | L1 | 一帧,人眼看(见 §3 L1 验收 8)。 |
| 上板(建议,Fan 定时机) | L1 | 盒上从棋谱屏走到直播列表、切三个分段、进一局观战、返回落回列表。RK3562 2G,一次只跑一家。 |
