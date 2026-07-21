# 棋力阶梯 — 实验记录 (EXPERIMENTS)

> 本文件是这条 track 的**实测结果单一事实源**。prd.md=需求、plan.md=实现、rename-plan.md=去品牌化改名;
> 本文件专门记录"实际打了哪些对局、结果如何、得出什么结论"。**新结果就地更新本文件,不要另建新文件。**
>
> 最后更新:2026-07-22

---

## 0. 实验环境

| 项 | 值 |
|---|---|
| 引擎 | **仅本机** KataGo HTTP analysis server `http://127.0.0.1:8000`;`/health capability_schema=1`;KataGo v1.16.4,revision `342d2a7b5ac9de9ed11b62065761276585744406-dirty`,Metal |
| 加载的网络 | **b28**(默认主网,最强)、**b18**(备用主网)、**humanv0**(human-SL 网,`-human-model`) |
| 实际模型身份(`/health`) | b28 SHA-256 `798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0`;b18 `9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d`;humanv0 `637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5`;三者均 `*_sha256_verified=true`,b18/b28 均 `running=true` 且 `has_human_model=true` |
| `wideRootNoise` | 0.04(与 shipping `config.json` 一致;用于对局多样性) |
| 判胜方法 | `adjudicate`:b28@200visits、`reportAnalysisWinratesAs=BLACK`、ownership-settled(≥98% 归属确定)+ 稳定性复检。**双方均不认输**(阶梯 never-resign);对手 resign_code=-3 → 我方定胜;pass_code=-1 → 交由 adjudicate。 |
| 校准脚本 | `calibration/run_calibration.py`(打星阵)、`calibration/run_selfplay.py`(自对弈) |
| 胜率→Elo | `elo_from_winrate`;100%/0% 会被 harness 封顶到 **±529**(即极值是下界,不是真实差距) |

**修复后三种阶梯落子机制**(详见 `katrain/core/ladder.py`):
- `humansl` — humanv0 人类策略 @1visit,对 `humanPolicy` 全分布**加权采样**(Band A 配置)。
- `humansl_search` — **b18 主网 + humanv0 + 完整 PIKL 配方**;HTTP 边界显式路由 `model=b18`,并在每次回复核验
  `_wrapper` 的模型/人类模型路径、SHA-256、verified 标志与启动时 capability 快照。实验 harness 仅允许 ≥40 visits。
- `net_search` — b28 主网 @visits,无人类 profile。

---

## A. 星阵 live-play 锚点校准(消耗珍稀预算,~20 局/天)

> ⚠️ 星阵每日对局额度极有限(~20 局/天),**必须珍惜**。token 失效(6003)或疑似限流(7002/断连)立即停,避免封号。
> token 存于 `~/.katrain/golaxy_token.txt`(仅本机读取,永不入库/粘贴/打印)。

### A1. 顶端锚点:确认我方最强档 ≥ 星阵最强档

| 我方档 | 配置 | 对手(星阵) | 结果 | 终局方式 | 结论 |
|---|---|---|---|---|---|
| rung 33 = **9D** | net_search / b28 / **visits=160** | 星阵 **9段**(api level 3000) | **6–0** | 6 局星阵全 resign | 我方 9D 决定性 **强于** 星阵9段 |
| rung 36 = **超职业** | net_search / b28 / **visits=450** | 星阵 **3星**(api level 3300,星阵最强) | **6–0** | 5 局星阵 resign + 1 局我方 pass 判胜(黑 +7.7) | 我方超职业 决定性 **强于** 星阵3星 |

两档均 3黑3白交替,零败。"我方顶端不弱于星阵顶端"以巨大冗余达成。

### A2. Visits 二分:找 b28 对星阵3星(api 3300)50% 胜率的 max_visits

目标:一点点降低 b28 的 `max_visits`,测出与星阵最强档(3星)打平(~50% 胜率)的搜索深度。

| max_visits | 结果 | 终局 | 判读 |
|---|---|---|---|
| 450 | **6/6** | 全 resign | 远强于星阵3星 |
| 20 | **4/4** | 全 resign | 仍强于星阵3星 |
| 5 | **0/1** | move_cap,黑 −12.4 | 首败;区间下界 |

**结论:50% 胜率点 V\* ∈ (5, 20)。** 下一二分点 = max_visits=10,待星阵额度恢复后补测(以及把 V=5 的 n=1 做厚)。

**决策(用户 2026-07-21):** 因当前无法继续与星阵对弈,**最强一档暂定使用 KataGo max_visits=20**,先转入自我评估(见 B 部分)。

---

## B. 自对弈 search-strength 实验(不打星阵,无预算限制)

> **硬失效边界:**`calibration/results/selfplay/` 下所有旧结果均为修复前历史数据。凡名称含
> `rank_*@2/@4/@7/@16/@32` 的 HumanSL-search 战绩、实验(1)(2)(3)由它们导出的全部 HumanSL 棋力结论,以及
> 实验(4)旧 `rank_9d@20 vs b28@20` 对照,**一律无效,不得用于新结论、合并统计或恢复运行**。新实验只能写入
> `calibration/results/selfplay_v2_pikl/`,旧 namespace 会被 harness 拒绝。

### B0. 2026-07-21 语义审计勘误(影响实验1–4的解释)

用户对“`rank_9d@20` 怎么会超过 `b28@20`”提出质疑后,对请求→HTTP路由→KataGo搜索的数据流逐层核查:

1. `rank_Xd@V` 请求只带 `humanSLProfile`,**没有** `overrideSettings.model`;
2. 本地多模型服务的 `default_model=b28`,无 model selector 的请求路由到 b28 主进程;
3. KataGo 文档明确:仅提供 `-human-model` + `humanSLProfile` 时,humanv0 只额外输出 `humanPolicy`,
   “all other analysis”仍使用主模型;
4. 当前请求未设置任何 `humanSL*ExploreProb*`/混合参数,其默认值均为 0,故 human policy 不进入搜索树;
5. `run_selfplay.py` 对 `@V (V>1)` 读取 `moveInfos`,所以落子来自纯 b28 搜索,与 `rank_Xd` 无关。

因此下文 `@2/@4/...` 的原始战绩有效,但它们测到的是 **b28 随 visits 增加的强度**,不是
“humanSL/b18 偏拟人模型增加搜索”的曲线。不同 rank 在 V>1 时只是标签不同。实验(1)(2)只能支持
“b28 搜索随 visits 单调增强”;实验(3)只说明“b28@4 能赢 humanPolicy argmax”;原设计的 HumanSL 搜索兑换率
**尚未被测量**,需先定义并实现真正的 human 模型/混合搜索配置后重跑。

**核心问题:humanSL 通过增加搜索,棋力是否单调提升?** 设计:每个 rank 固定 humanSL profile,搭一条按
visits 递增的阶梯,**每档与前一档打 10 盘**,汇总胜率。playerA=我方槽、playerB=对手槽,交替黑白。

以下阶梯档位记法仅描述**旧实验文件**(修复后的 harness 不再接受 2/4/7/16/32 visits 的 HumanSL 搜索):
- `@1` = `humansl` 机制,`humanPolicy` **加权采样**(阶梯真实使用的 Band A 落子法)。
- `@1s` = 1visit 下取 `humanPolicy` 的 **argmax**(确定性"人类最优单手")。这是 "humansl_search@1" 的忠实版本
  —— 因为 **maxVisits=1 时 `moveInfos` 必为空**,真正的 1-visit 搜索无法选手(见 §C1)。
- `@2/@4/@7/@16/@32` = 当时标作 `humansl_search`,实际为纯 b28 价值搜索 @N visits,取搜索最优手。

### 实验(1):rank_9d 全阶梯 ⚠️ 原始数据完成,HumanSL 解释无效

阶梯 `@1 → @1s → @2 → @4 → @7 → @16 → @32`,每档打前一档 10 盘:

| 台阶 | 胜/可判 | 胜率 | Elo(点估) | 对局多样性 |
|---|---|---|---|---|
| `@1s` vs `@1` | 10/10 | 100% | +529(封顶) | 10 局各异 ✓ |
| `@2` vs `@1s` | 5/5 | 100% | +417(封顶) | ⚠️ 仅 2 种棋局(见坑2) |
| `@4` vs `@2` | 6/8 | 75% | +191 | 10 局各异 ✓ |
| `@7` vs `@4` | 6/10 | 60% | +70 | 10 局各异 ✓ |
| `@16` vs `@7` | 7/10 | 70% | +147 | 10 局各异 ✓ |
| `@32` vs `@16` | 8/10 | 80% | +241 | 10 局各异 ✓ |

**勘误后的有效结论:搜索档实际是 b28,故这些接缝说明 b28 visits 增加时棋力单调提升,不能说明
rank_9d humanSL 搜索单调提升。** 另有两点:
- **坑1:`@1→@1s` 的 +529 不是"搜索"的功劳。** 两者都是 1visit 零搜索,差别只是 argmax vs 加权采样。
  argmax 10/10 碾压采样,说明加权采样常抽到人类先验里的冷门坏手、且无搜索纠正。真正"搜索登场"是 `@1s→@2`。
- **坑2:`@2 vs @1s` 欠采样。** 1–2visit 下双方近乎完全确定性(`@1s` argmax 零随机;`@2` 仅 2visit,
  `wideRootNoise=0.04` 几乎不改变结果),10 盘坍缩成 **2 种棋局**(`@2` 执黑→赢/可判,`@2` 执白→终局
  unsettled/inconclusive)。即 `@2>@1s` 仅 n=1 可判棋局支撑,方向对但样本薄。visit ≥4 后多样性恢复。

**用户决策(2026-07-21):后续实验去掉 `@2` 档**(即欠采样的那道接缝),阶梯改为 `@1 → @1s → @4 → @7 → @16 → @32`。

### 实验(2):rank_5d、rank_7d 全阶梯 — ⚠️ 原始数据完成,HumanSL 解释无效

阶梯 `@1 → @1s → @4 → @7 → @16 → @32`(已去掉 @2),每档打前一档 10 盘。跑动史:两段并发 job 于 2026-07-21
在顶端接缝 `@32 vs @16` 第 4 局被外部信号同时杀掉(引擎正常、无 traceback;疑似单次系统事件),前 4 接缝已跑满;
随后**单进程顺序 resume 补满**,并按用户要求把 rank_5d 顶端接缝**加厚到 20 盘**以钉死"是否饱和"。

**rank_5d**:

| 台阶 | 胜/可判 | 胜率 | Elo(点估) | 多样性 |
|---|---|---|---|---|
| `@1s` vs `@1` | 10/10 | 100% | +529(封顶) | ✓ |
| `@4` vs `@1s` | 9/9 | 100% | +512(封顶) | ✓ |
| `@7` vs `@4` | 6/9 | 67% | +120 | ✓ |
| `@16` vs `@7` | 9/9 | 100% | +512(封顶) | ✓ |
| `@32` vs `@16` | **14/19** | **74%** | +179 | ✓ 19 局各异(加厚到 20 盘) |

**rank_7d**:

| 台阶 | 胜/可判 | 胜率 | Elo(点估) | 多样性 |
|---|---|---|---|---|
| `@1s` vs `@1` | 8/10 | 80% | +241 | ✓ |
| `@4` vs `@1s` | 9/10 | 90% | +382 | ✓ |
| `@7` vs `@4` | 6/8 | 75% | +191 | ✓ |
| `@16` vs `@7` | 6/8 | 75% | +191 | ✓ |
| `@32` vs `@16` | 7/9 | 78% | +218 | ✓ |

**"rank_5d @32 触顶饱和"假设 → 否决(是噪声)。** 顶端接缝最初 1/4(@32 落后)看似饱和信号,补满到
20 盘后回到 **14/19 (74%)**,@32 明确强于 @16,与阶梯其余部分一致。**教训:n=4 就下结论极危险;护栏(1)驱动的
加厚补跑纠正了这个假信号。**

### 三段位横向对照(exp(1)+exp(2)汇总)—— 每档胜下一档的胜率

| 接缝 | rank_5d | rank_7d | rank_9d |
|---|---|---|---|
| `@1s` vs `@1`(argmax vs 采样*) | 100% (10/10) | 80% (8/10) | 100% (10/10) |
| `@4` vs `@1s`(9d 经 `@2`)† | 100% (9/9) | 90% (9/10) | 75% (6/8) |
| `@7` vs `@4` | 67% (6/9) | 75% (6/8) | 60% (6/10) |
| `@16` vs `@7` | 100% (9/9) | 75% (6/8) | 70% (7/10) |
| `@32` vs `@16` | 74% (14/19) | 78% (7/9) | 80% (8/10) |

\* `@1s→@1` 测的是选点规则(argmax vs 加权采样),非搜索深度;三段位一致地 argmax 大幅胜出。
† rank_9d 阶梯含额外的 `@2` 档(`@2` vs `@1s` 100% 5/5 但欠采样、`@4` vs `@2` 75%);rank_5d/7d 已按用户决策去掉 `@2`,故 `@4` 直接打 `@1s`。

**实验(1)+(2) 勘误判定:HumanSL 结论撤回。** 所有 V>1 的选手实际都是 b28@V;三份“rank”结果只是同一
b28 visits 曲线的重复采样。数据仍稳健支持“b28 搜索随 visits 增加而增强”,但不能支持“humanSL 搜索增强”或
任何跨 rank 差异。

### 实验(3):低一段需要多少搜索可超过高一段 `@1s`? ⚠️ 原始数据完成,目标未测到

**用户决策(2026-07-21):高一段基准统一使用 `@1s` argmax**,与低一段搜索方同为“取最优手”口径,
排除 `@1` 加权采样带来的约 +500 Elo 选点规则混杂。低一段从 `@4` 起逐档增加 visits,直到胜率跨过 50%。

| 对局 | 胜/可判 | 胜率 | Elo(点估) | 黑/白战绩 |
|---|---:|---:|---:|---:|
| `rank_5d@4` vs `rank_6d@1s` | 10/10 | 100% | +529(封顶) | 5/5、5/5 |
| `rank_6d@4` vs `rank_7d@1s` | 8/10 | 80% | +241 | 5/5、3/5 |
| `rank_7d@4` vs `rank_8d@1s` | 10/10 | 100% | +529(封顶) | 5/5、5/5 |
| `rank_8d@4` vs `rank_9d@1s` | 9/10 | 90% | +382 | 4/5、5/5 |

**勘误后的有效结论:**四组 A 方其实都是同一个 `b28@4`(rank 标签不影响 `moveInfos`),B 方才是各高一段的
humanPolicy argmax。因此只能说 **b28@4 对 rank_6d–9d 的 humanPolicy argmax 胜率为 80–100%**;
不能得出“低一段加 ≤4 visits 可跨一段”的兑换关系。原实验目标待真正 HumanSL 搜索配置实现后重跑。

### 实验(4):rank_9d + 搜索能否达到/超过 b28@20? ⚠️ 加厚后确认实际为同配置对照

| 对局 | 胜/可判 | 胜率 | Elo(点估) | 95% CI | 黑/白胜局 |
|---|---:|---:|---:|---:|---:|
| `rank_9d@20` vs `b28@20` | **9/18**(总计20局) | **50%** | **0** | [−174,+174] | 3、6 |

首次10局为 6/9(67%,1局不可判),用户认为结果反常后加厚到20局;新增10局使总计回归 **9/18=50%**,
另2局 `inconclusive_unsettled`。代码审计同时证明两方的 `moveInfos` 都来自 b28@20,故这不是
“humanSL/b18 vs b28”的强度对比,而是同配置随机对照。最初 67% 是小样本波动。原实验(4)目标仍待有效的
HumanSL 搜索选手定义后重跑。

---

## C. 关键方法论发现(可复用的经验)

### C1. maxVisits=1 时 `moveInfos` 为空 → 用 argmax_human 做 "humansl_search@1"
1 visit 只评估根节点、不展开搜索树,`moveInfos` 必为空;而 `humanPolicy`(长度 362)仍在。故
`humansl_search@1` 必然失败("unavailable"),这正是实验(1) matchup 1–2 最初全 0/0 的根因。修复:新增
`argmax_human` 选点(直接读 `humanPolicy` 的 argmax),作为"1-visit humansl_search"的忠实替身(=`@1s`)。

### C2. `humanSLProfile` 本身不会让 `moveInfos` 使用 human 模型
修复前请求体只带 profile;`mechanism` 字符串本身**不进请求体**,纯客户端。故旧实现同 profile 下
`humansl@1` 与 `humansl_search@1` 发给引擎的 JSON **字节相同**;差异 100% 在“读回复的哪个字段”
(`humanPolicy` 加权 vs `moveInfos` 最优)。旧默认混合参数为0时,`humanPolicy` 来自 humanv0,但 `moveInfos`
始终来自默认主网 b28。这个 KataGo 语义仍成立:必须像修复后 spec 那样显式选择 b18 并配置非零 PIKL,
不能只设置 `humanSLProfile`。

### C3. 低 visit 自对弈的确定性坍缩
`@1s`(argmax)完全确定;`@2` 仅 2visit,`wideRootNoise=0.04` 几乎不产生分叉 → 两个确定性选手对局会把
"10 盘"坍缩成 ~2 种棋局(每种颜色一局)。visit ≥4 后搜索树够大,多样性恢复(10 局各异)。**低档接缝若要
厚采样,需加开局随机化**(前 N 手加权采样/随机)打散确定性。

### C4. 先验 P 的来源:humanSL=监督人类棋谱,b 系列=自我对弈(AlphaZero 血统)
- humanv0 的 policy = 对人类棋谱做监督学习、按段位 conditioned("rank_X 的人会怎么下"),**模仿人类**,不追求最强。
- b18/b28/b40 的 policy = 自我对弈 RL(AlphaZero 逻辑,不喂人类棋谱),**追求胜率/目数最优**。数字是网络
  大小(残差块数)不是版本新旧;同出 KataGo kata1 训练线。
- 修复前旧 `humansl_search` 的搜索 policy/value **都是 b28**;humanv0 虽输出 `humanPolicy`,但混合权重为0,
  未成为搜索先验。“visit 越多洗淡人类先验”的旧解释不成立,因为旧实现从第一棵搜索树起就没有混入人类先验。

### C5. 根因与官方 HumanSL+search 能力审计

**这不是 KataGo 不支持 HumanSL 搜索,而是我方修复前的 wiring/实验配置 bug。** 官方 `Analysis_Engine.md` 和
`gtp_human9d_search_example.cfg` 明确提供多种整合方式:

1. **humanv0 作为主模型搜索**:用 `b18c384nbt-humanv0.bin.gz` 作为 `-model`,搜索 policy/value 都来自人类网;
2. **正常主网 + humanv0 PIKL 混合**:主网(b18/b28)负责价值判断,用
   `humanSLRootExploreProbWeightless`/`humanSLCpuctPermanent` 保证人类候选手被搜索,再用
   `humanSLChosenMoveProp` + `humanSLChosenMovePiklLambda` 将 `humanPrior` 与搜索 utility 结合到最终选点;
3. **weightful 人类树内偏置**:通过 `humanSL{Pla,Opp,Root}ExploreProbWeightful` 让人类策略影响树内平均价值;
   官方标为实验性更强的玩法。

官方 9d 强化示例的核心值为 `humanSLChosenMoveProp=1.0`、`humanSLChosenMovePiklLambda=0.08`、
`humanSLRootExploreProbWeightless=0.8`、`humanSLCpuctPermanent=2.0`,并关闭 `useUncertainty`、
`subtreeValueBiasFactor`、`useNoisePruning`;示例使用 400 visits,且明确不建议低于约30–40 visits。
因此旧实验的 `@1/@4/@7/@16/@32` 网格也不适合直接套用该配方。

**修复前具体漏项:**

- `LadderRung.net` 只是元数据,`ladder_override_settings`/HTTP请求从未发 `overrideSettings.model`;本地服务
  `default_model=b28`,所以标作 humanv0/b18 的 V>1 实验仍路由到 b28。
- `human_sl_params` 字段和透传代码虽存在,但阶梯表与 `run_selfplay.make_player` 一直填空字典,所有 HumanSL
  探索/PIKL参数保持 KataGo 默认0(其中 `humanSLChosenMoveProp=0`)。
- `pick_ladder_move(...,"humansl_search")` 直接取 `moveInfos.order=0`;在上述零参数下自然就是纯主网最优手。
- 查询契约测试只证明 runtime 与 harness 的 JSON 完全一致;二者一致地漏掉 model/偏置参数。测试没有断言
  `rung.net` 被执行,也没有构造含非零 `human_sl_params` 的真实 `humansl_search` rung 做语义覆盖。

**本地最小探针(空棋盘,b28@100,wideRootNoise=0):**纯 b28 与“仅加 rank_9d profile”均选 `R16`,且
`rawWinrate` 完全相同(0.331718817);profile 响应虽然额外给出 human top=`D4`,但该手仅排 order 11。
加入官方 PIKL/探索参数后,order 0 改为 `Q16`,human top `D4` 升到 order 3,证明 HumanSL 确实能进入搜索/
最终排序。切到 `model=b18` 也会改变主网结果,但**仅切 b18 不等于拟人**;目标“b18 上限 + 人类偏置”需要
同时显式选择 b18 主网和 humanv0 混合参数。

**影响边界:**37档产品阶梯中,rung 1–25 使用 `humanPolicy` @1,确实是 HumanSL;26–37 明确是 b28
`net_search`;没有正式 rung 正在使用 `humansl_search`。所以现有产品阶梯不会把 `humansl_search` 冒充拟人搜索,
但旧自对弈实验全部受影响。该 dormant mechanism 现已按下节修复并 fail-closed,供新实验使用。

### C6. 2026-07-22 语义修复与本地实机证明

修复不是修改 KataGo 搜索算法;KataGo 原生 PIKL 能力保持不变。改动集中在多模型 HTTP wrapper、KaTrain
查询契约和实验 harness:

- KataGo wrapper commits: `e1b68dd0`(逐请求模型路由/身份 attestation)、`d11d80ea`(身份校验与健康能力加固)。
- KaTrain `74db2c6a` 定义 b18+humanv0+PIKL 唯一 strength spec;`f753acf2`、`6c7de872`、`a46a2ba2`
  实现 HTTP-only model selector、能力快照和 malformed selector fail-closed;`12e0c0e2` 在产品阶梯逐请求核验
  执行身份;`280a56fb` 让 calibration 走同一 wire contract。
- `88506adc`、`623117ce`、`98f29d86`、`6158a4ff`、`3fc1a945`、`076b946a`、`2a6bd953`
  建立 ≥40 visits 的 PIKL player、能力/配置 fingerprint、成对开局、完整 pair checkpoint/resume、Wilson 判读,
  并隔离到 `selfplay_v2_pikl`。
- `ed7299e5`、`8225e098`、`59f46851` 建立并加固可重验的 schema 3 语义探针。

代码回归验证(2026-07-22,均为 `CI=true KIVY_NO_ARGS=1`):7 个直接相关测试文件 **316 passed**;
`tests/core tests/platforms` **723 passed**。未访问远程服务。

本地实机探针
`calibration/results/semantic_probe/humansl_semantic_probe_20260721T183703.918547Z_c0bedf887cf3.json`
为 `probe_schema=3`,`passed=true`。同一锁定局面与 b18@500 下:纯 b18、profile+零混合、PIKL λ=0.01 均选
`R2`;PIKL λ=100 把 `O6` 从 order 1 推到 order 0 并选 `O6`;显式 b28 基线也选 `O6`。五类请求均保存完整
wire request、request fingerprint、`_wrapper` attestation 与摘要,因此同时证明:

1. `model=b18`/`model=b28` 实际路由到不同且已验证 SHA 的主模型;
2. 仅带 profile、但 HumanSL 权重为0时不改变 b18 排序;
3. 非零 PIKL 参数确实改变 `playSelectionValue`、order 与最终选点。

据此,`humansl_search` **语义修复已完成并经本地实机探针通过**;这只恢复了开展有效实验的前提,不把任何旧
战绩“洗白”为 HumanSL 数据。

---

## D. 待办 / 开放项

- [ ] **实验(1)(2)有效重跑**:使用新 `selfplay_v2_pikl` namespace 与 ≥40 visits 网格重新筛查/确认;旧 V>1
  数据实际测的是 b28 visits 曲线,全部保持失效。
- [ ] **实验(3)有效重跑**:旧 A 方均为 b28@4,未测到低一段 HumanSL 搜索跨高一段所需 visits;改用修复后
  ≥40 visits player 重跑。
- [ ] **实验(4)有效重跑**:加厚到20局后为 9/18(50%,2局不可判),且代码确认双方实为 b28@20;需用真正
  的修复后 HumanSL/b18+PIKL 搜索选手重新对 b28@20。
- [x] **修复 `humansl_search` 语义**:HTTP 实际路由 b18,完整 PIKL 配方、能力/逐请求 attestation、≥40 visits
  实验下限与 schema 3 本地语义探针均已落地并通过。KataGo C++ 引擎无需修改搜索实现;需使用包含上述 wrapper
  commits 的本地服务。
- [ ] **星阵 V=10 二分点**:待每日额度恢复后补测,收窄 V\* ∈ (5,20);并把 V=5 的 n=1 做厚。
- [ ] **display_elo 数值核对**:代码 `_DISPLAY_TOP` 里星阵3星标 **4000**(疑似 +300 等差的整齐推算),用户官网
  截图为 **3900**。待用户给出确切数值(9段/星阵1星/星阵2星/星阵3星)后修正 `engine_client._DISPLAY_TOP`、
  prd.md §2 表、plan.md 断言、ladder 测试。此为展示 Elo(display_elo),**与打棋用的 api level(3300)无关**。
- [ ] **(可选)低档接缝厚采样**:给低 visit 自对弈加开局随机化,把 `@2/@4 vs @1s` 类接缝重跑到 10 局各异。

---

## 附:原始数据位置

| 数据 | 路径 |
|---|---|
| 星阵 9D 锚点 | `calibration/results/rung_33.jsonl` |
| 星阵 超职业 锚点 | `calibration/results/rung_36.jsonl` |
| 星阵3星 visits 二分 | `calibration/results/rung_36_v20.jsonl`、`rung_36_v5.jsonl` |
| 旧自对弈全部接缝(**HumanSL 结论无效**) | `calibration/results/selfplay/selfplay_rank-<Xd>-<V>__vs__rank-<Xd>-<V'>.jsonl` |
| 旧自对弈汇总(**不得续跑/合并**) | `calibration/results/selfplay/selfplay_summary.json` |
| 修复后新自对弈 namespace | `calibration/results/selfplay_v2_pikl/` |
| schema 3 HumanSL 语义探针 | `calibration/results/semantic_probe/humansl_semantic_probe_20260721T183703.918547Z_c0bedf887cf3.json` |
| 冒烟/level 探针 | `calibration/results/smoke_report.json` |
