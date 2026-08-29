# KaTrain 现状：着手评价是怎么算的，以及它为什么会给出「妙手 4 / 失误 50」

取证日期：2026-08-29。每条都带 file:line。

## 1. 唯一的评价轴：`delta_score`，而它是单边的

```
katrain/cron/jobs/report_analyze.py:359-366
    delta_score = score_lead - previous_score        # 黑
    delta_score = previous_score - score_lead        # 白
katrain/core/game_node.py:390-395
    points_lost = player_sign * (parent_score - score)      # == -delta_score
```

两者是同一个量的正负两面：**这手棋落下后，KataGo 对局面的 scoreLead 评估变了多少**。

它是单边的：落子前的根评估**已经假定接下来是最优应手**，所以最优的一手大致复现
那个评估，其余任何一手只能更差。正收益只能来自搜索噪声、地平线效应、
引擎看到这手之后修订评估、劫/seki 误判等。

于是 `katrain/web/ui/src/features/report/reportModel.ts:192-194`：

```ts
is_brilliant:    deltaScore >= 2,
is_mistake:      deltaScore <= -3,
is_questionable: deltaScore <= -1.5,
```

把「妙手」和「失误」放在同一根单边轴的两端 —— **失误碾压妙手是结构性的，
不是阈值没调好**。

## 2. 实测：现在的「妙手」测的是噪声，「疑问手」的门槛在噪声地板以下

用 `kata1-b18c384nbt`、500 visits、3 盘真实棋局（15k/15k、4k/5k、李世石 vs AlphaGo 第四局）实测：

| 量 | 结果 |
|---|---|
| 两次搜索之差出现**正收益**的比例 | 21.7% / 27.4% / 37.2% |
| 换成**同一次搜索内**的估计量（`top_moves[0].score_lead − 实战手 score_lead`）后，正收益比例 | 0% / 3.7% / 5.8% |
| 144 手「人类恰好走了引擎首选」（真实损失≈0）上，两次搜索之差的 \|Δ\| | median **0.21**、p90 **0.80**、p95 **1.34**、max **1.90** 目 |
| 这些零损失手里越过 0.5 目的比例 | **24.3%** |
| 越过 1.0 目 | 6.9% |
| 越过 2.0 目 | **0%** |
| 同一局面重复搜索 12 次（每次清缓存）的 sd | 0.02–0.47 目 |

两条结论：

1. **`is_questionable: delta ≤ -1.5` 落在估计量自己的噪声地板里。**
   2.0 目是这份数据造不出来的第一条线。
2. **`is_brilliant: delta ≥ 2` 基本只在噪声上触发。** 截图里的「妙手 (4)」
   在 288 手里占 1.4%，与噪声尾部量级一致。我们的妙手栏在测搜索抖动。

第三条附带发现：重复搜索时**「最佳一手」本身会翻**（turn 30，500 visits：
D3 4 次 / P3 8 次；2000 visits：D3 10 次 / P3 2 次）。任何「他有没有走出最佳」
的布尔量都继承这个不稳定性 —— 判据要么给冗余，要么配 visits 门槛。

## 3. 「失误 (50)」这个数是怎么来的

`katrain/web/ui/src/components/live/TrendChart.tsx`：

- `:204-208` 失误 tab 过滤的是 `is_mistake || is_questionable` ⇒ **实际门槛是 delta ≤ −1.5 目**
- `:198-203` 妙手 tab 过滤 `is_brilliant`
- 两个列表**都没有上限**（无 `slice`），API 也不分页（`reports.py:269-297`，`.all()`）
- **没有阶段筛选**，**没有棋手筛选** —— 黑白混在一条列表里，颜色只用来上色

288 手里 50 手亏 ≥1.5 目 ≈ 17%。对 1980 年的职业棋手 vs 现代 KataGo，
这个数**本身可能是诚实的** —— 问题在于把它原样铺成一面墙。

## 4. 五份互不一致的阈值

| 位置 | 妙手 | 失误 | 疑问手 | 操作数 |
|---|---|---|---|---|
| `features/report/reportModel.ts:192-194` | ≥2 | ≤−3 | ≤−1.5（**不是区间**，失误也算疑问手） | `delta_score` |
| `web/live/models.py:57-59, 189-191` | ≥2 | ≤−3 | 真区间 (−3, −1.5] | `delta_score` |
| `cron/analysis_repo.py:185-187` | >2 | <−3 | [−3, **−1.0**) | `delta_score` |
| `web/interface.py:1370-1374` | pl < −0.5 | pl > 1.0 | 0.5 < pl ≤ 1.0 | **`points_lost`** |
| `galaxy/…/ResearchAnalysisPanel.tsx:93-95` + kiosk 双胞胎 `:95-97` | 2.0 | −3.0 | −1.5 | **相邻 score 历史自己作差** |

三个中文词也在打架：同一个桶，走势图叫「失误」（`live:mistakes`），
研究面板叫「问题手」（`research:mistakes`），另有「疑问手」（`live:questionable`）。

## 5. 三个真 bug（与本题直接相关）

### 5.1 `katrain/config.json:80-87` 的阈值梯子方向反了

现在是**升序** `[0.5, 1.0, 2.0, 4.0, 8.0, 16.0]`，
而 `katrain/core/utils.py:27-31` 的 `evaluation_class()` 要求**降序**
（上游 `[12, 6, 3, 1.5, 0.5, 0]`，被提交 `6f544a3c` 翻掉）。

后果实测（照抄那个循环跑）：六级塌成两级 ——
`< 0.5` → class 5（绿），**`≥ 0.5` 全部 → class 0**，
被 `katrain/gui/theme.py:77-84` 画成最差的深紫色。
`base_katrain.py:106-118` 首次启动是**整份复制**包内配置、不做合并，
所以新装用户直接继承这个坏值。`web/interface.py:1469` 的硬默认反而是对的降序。

顺带：`eval_thresholds[-4]` 是桌面端 THE「失误」阈值，用在四处
（失误音效、上/下一个错误、只重分析错误、web interface），
上游是 3.0，本仓变成了 2.0。

### 5.2 网页版报告的 SGF 解析吃不了让子棋

```
katrain/cron/jobs/report_analyze.py:24   SGF_MOVE_RE = r";([BW])\[([a-z]{0,2})\]"
katrain/cron/jobs/report_analyze.py:320-321   initial_stones=[], initial_player="B"
```

`AB[]/AW[]` 摆子**全丢**，起手方**写死黑**。一盘 9 子局被当成分先黑先走 ⇒
**白棋每一手都像灾难**。这是「分析业余选手棋局失误特别多」的直接嫌疑人。

同一处还有两个坑（实测跑过解析器）：
- 分支 SGF 被拍平进主线：`(;B[pd];W[dp](;B[qp];W[dc])(;B[dc];W[qp]))`
  解析成 6 手，含两次非法重复落子 —— 分析的局面和棋局无关，算出来的评级是垃圾。
- 老式 `;B[tt]` 停一手 → 盘外坐标 `U0` → KataGo 报错 → 3 次重试 → 整个任务失败。
- `C[]` 注释里的 `;W[qq]` 会被当成真着法。

### 5.3 测试会静默改写**被提交的** `katrain/config.json`

这条是修 5.1 的时候被它咬出来的：修好的降序值**被吃掉过两次**，
每次都只表现为 `git diff` 里多出一段看起来与本次改动无关的 diff。

机制：`KaTrainBase(force_package_config=True)` 会把 `_config_store` 指向
包内的 `katrain/config.json`（`base_katrain.py:102-103`），于是这类实例上的
`update_config` / `save_config` 直接写进工作区的那个**源文件**。

已知的一处写手：`tests/web_ui/test_settings_snapshot.py:61` ——
它把 `trainer/eval_thresholds` 写成 `[0.5, 1.0, 2.0, 4.0, 8.0, 16.0]` 并落盘。
**仓里那份升序的 eval_thresholds 极可能就是这么来的**：
有人跑了一次测试套件，然后把这段 diff 一起提交了。

现在 `tests/conftest.py` 有一个 autouse（**按用例**，不是按会话）的夹具，
跑完把文件恢复原样并打印是谁动的。按会话恢复挡不住会话内的顺序耦合 ——
先跑的用例写脏，后跑的断言就读到脏值，表现为「换个 `-k` 顺序结果就不一样」。

根治要让 `force_package_config` 的实例写到临时文件去，那是另一件事，没做。

**同类的第二处**（本次没动）：`katrain/web/ui/src/kiosk/__tests__/fixtures/engine_game_state.json`
也会被测试重新生成（本次实测每跑一遍套件它就多出 `"analysis_delivered": true`）。
它同样是被提交的文件，同样会以「与本次改动无关的 diff」形式混进提交。

### 5.4 `katrain/core/ai.py:232` 把正收益抹平

```py
points_lost = max(0, points_lost)
```

桌面端管线里唯一的正向信号在源头就没了 —— 妙手在那条路上**从定义上不可能存在**。
（这也是为什么桌面端 6 档里根本没有「妙手」这个词：`grep -rniE "brilliant|妙手|好手"`
在 `katrain/gui/`、`katrain/core/`、`*.kv` 里**零命中**。桌面端只有 最佳/非常好/良好/缓着/失误/恶手，
「最佳」= 零损失，不是有收益。）

## 6. 好消息：难度那根轴的数据已经存着了

`katrain/cron/jobs/report_analyze.py:372-383` 每手都存了 `top_moves[:10]`，字段：
`{move, visits, winrate, score_lead, prior, pv, psv}`。

`prior` 就是 KataGo 的 policy 先验，而且**确实有值** ——
管线虽然传了 `include_policy=False`，但那只关掉顶层 `policy` 数组
（`KataGo/cpp/search/searchresults.cpp:2169`），`moveInfo["prior"]`
是**无条件输出**的（`:2055`）。

所以「AI 首选 ∩ 难以被想到」这个判据**不需要重新分析任何一盘棋**，
现存的 `report_task_moves.top_moves` 就够。

同理，`points lost vs 引擎最佳手` 也已经可以在服务端算出来：
第 N−1 行的 `top_moves[0].score_lead` 对第 N 行的 `score_lead`，
两者都是黑方视角（`reportAnalysisWinratesAs: BLACK`，`cron/clients/katago.py:83`）。

## 7. 改动会碰到哪些文件（kiosk 边界）

- **`components/live/TrendChart.tsx` 是那三个 tab 的唯一渲染者**，
  被 galaxy 报告页、kiosk 报告页、galaxy 直播页、kiosk 直播页四处共用，
  **并且确实打进了 kiosk-2d 产物**。改它必须 `npm run build:kiosk-2d` + `verify:kiosk-2d` 过一遍。
- `features/report/reportModel.ts` 事实上是共享的（kiosk 报告页经 `useReportDetail` 用它）。
- 研究面板双胞胎 882/879 行、约 80% 相同，**那 39 行分类逻辑字节完全一致** ——
  可以直接抽到共享目录。`eslint.config.js:50-61` 只禁两个方向
  （kiosk 不许 import galaxy/Board3D/VideoRecorder；galaxy/pages/ZenModeApp 不许 import kiosk），
  放在 `src/features/` 或 `src/utils/` 两边都能 import，**不违反边界**。
  注意：`src/features/**` 目前**没有任何 eslint 边界规则**，CLAUDE.md 的共享目录清单里也没列它。
- `components/Board.tsx:36-43` 已有一套 6 档 `EVAL_COLORS` + `:167-172` 阈值 `[12,6,3,1.5,0.5,0]`，
  在 `components/Board3D/constants.ts:89-105` 有第二份，两者必须同时改。
- `kiosk-shell/tokens.css:859-901` 里**已经写好了一条 6 档的 `.kiosk-ribbon` 每手评级色带**，
  全仓零消费者。
- 项目里**没有图表库**，所有走势图都是手写内联 SVG；`TrendChart` 的 x 映射本来就是逐手的
  （`:76 xStep = chartWidth / max(1, n-1)`），加一条评级色带就是一个 `<rect>` 循环。
- 没有 Alembic；`web/core/migrations.py:322-345` 的 `add_missing_columns`
  会自动给新加的模型列做 `ALTER TABLE ADD COLUMN`。但 `cron/models.py:212-238`
  是**手抄的镜像**，不同步加列的话 `report_analyze.py:274-276` 的
  `hasattr(record, key)` 会**静默丢掉**新字段。
