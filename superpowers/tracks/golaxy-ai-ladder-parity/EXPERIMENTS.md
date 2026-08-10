# 棋力阶梯 — 实验记录 (EXPERIMENTS)

> 本文件是这条 track 的**实测结果单一事实源**。prd.md=需求、plan.md=实现、rename-plan.md=去品牌化改名;
> 本文件专门记录"实际打了哪些对局、结果如何、得出什么结论"。**新结果就地更新本文件,不要另建新文件。**
>
> 最后更新:2026-08-04

---

## 0. 实验环境

| 项 | 值 |
|---|---|
| 引擎 | **仅本机** KataGo HTTP analysis server `http://127.0.0.1:8000`;`/health capability_schema=1`;KataGo v1.16.4,revision `342d2a7b5ac9de9ed11b62065761276585744406-dirty`,Metal |
| 加载的网络 | **b28**(默认主网,最强)、**b18**(备用主网)、**humanv0**(human-SL 网,`-human-model`) |
| 实际模型身份(`/health`) | b28 SHA-256 `798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0`;b18 `9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d`;humanv0 `637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5`;三者均 `*_sha256_verified=true`,b18/b28 均 `running=true` 且 `has_human_model=true` |
| `wideRootNoise` | 0.04(与 shipping `config.json` 一致;用于对局多样性) |
| 判胜方法 | 我方棋手从不认输。对星阵校准时,smoke 已验证 Golaxy `resign_code=-3`(认输直接判我方胜;12 局锚点胜局中 11 局如此)与 `pass_code=-1`(交 b28@200、BLACK 视角、ownership-settled 判分);初判 conclusive 且 `end_reason` 属于 `{move_cap,golaxy_terminal,our_pass,golaxy_illegal}` 时,再以最高 b28@800 做稳定性复检。纯自对弈双方均不认输,pass 或 400 手上限后只做一次 b28@200 判分,**不做**第二次稳定性复检。 |
| 校准脚本 | `calibration/run_calibration.py`(打星阵)、`calibration/run_selfplay.py`(自对弈) |
| 胜率→Elo | `elo_from_winrate`;以 `eps=1/(2n+2)` 对 0%/100% 作样本量相关的连续性修正,不是固定封顶。全胜点估计示例:10/10 = +528.9、40/40 = +763.4、80/80 = +882.7 Elo(全败对称为负);极值仍只是差距下界。 |

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
> `rank_*@2/@4/@7/@16/@32` 的战绩、实验(1)(2)(3)由它们导出的全部 **HumanSL-search** 棋力结论,以及实验(4)
> 旧 `rank_9d@20 vs b28@20` 的 **HumanSL-vs-b28** 解释,一律无效。旧原始记录仍可保留作历史 b28 对照/visits
> 诊断(实验4也是同配置随机对照),但不得恢复运行或与修复后 HumanSL 样本合并。新实验只能写入
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
| `@1s` vs `@1` | 10/10 | 100% | +529(连续性修正) | 10 局各异 ✓ |
| `@2` vs `@1s` | 5/5 | 100% | +417(连续性修正) | ⚠️ 仅 2 种棋局(见坑2) |
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
| `@1s` vs `@1` | 10/10 | 100% | +529(连续性修正) | ✓ |
| `@4` vs `@1s` | 9/9 | 100% | +512(连续性修正) | ✓ |
| `@7` vs `@4` | 6/9 | 67% | +120 | ✓ |
| `@16` vs `@7` | 9/9 | 100% | +512(连续性修正) | ✓ |
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
| `rank_5d@4` vs `rank_6d@1s` | 10/10 | 100% | +529(连续性修正) | 5/5、5/5 |
| `rank_6d@4` vs `rank_7d@1s` | 8/10 | 80% | +241 | 5/5、3/5 |
| `rank_7d@4` vs `rank_8d@1s` | 10/10 | 100% | +529(连续性修正) | 5/5、5/5 |
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

### C7. 修复后 screening 结果与确认实验预声明(2026-07-22)

以下四组均来自全新 `selfplay_v2_pikl` namespace,且仅是 **screening**:每组预定恰好10个完整颜色对
(20盘 decision games),不用于显著性结论,也不并入后续 confirmation。若同一开局颜色对中任一盘不可判,
该 pair 的两盘都不进入胜负样本;原始记录仍全部保留。因此表中同时列出完整 pair 样本和所有尝试的原始
结果计数。

| screening 对局(A vs B) | 完整 pair / 尝试 pair (上限) | 完整 pair 样本 | Wilson 95% CI | Elo(A-B)及95%区间 | 不完整 pair / 原始不可判盘 | 所有尝试的原始结果(A胜/A负/不可判) |
|---|---:|---:|---:|---:|---:|---:|
| rank_5d@80 vs rank_5d@40 | 10 / 12 (20) | 14–6 (70%) | [48.10%, 85.45%] | +147.2 [-0.6, +383.3] | 2 / 2 | 16/6/2 |
| rank_7d@80 vs rank_7d@40 | 10 / 12 (20) | 13–7 (65%) | [43.29%, 81.88%] | +107.5 [-41.2, +314.0] | 2 / 3 | 13/8/3 |
| rank_9d@80 vs rank_9d@40 | 10 / 16 (20) | 11–9 (55%) | [34.21%, 74.18%] | +34.9 [-121.5, +208.0] | 6 / 8 | 13/11/8 |
| rank_9d@40 vs b28@20 | 10 / 11 (20) | 2–18 (10%) | [2.79%, 30.10%] | -381.7 [-645.1, -208.5] | 1 / 1 | 2/19/1 |

这些数值只用于选择固定样本的后续对局。即使区间位于50%一侧,本节也**不作显著性、确认性或实验完成
声明**。实验(4)的 `rank_9d@40` 候选因 screening 为 2–18 而淘汰,不会对它启动40-pair confirmation。

原始数据审计(2026-07-22):四个 JSONL 均通过严格 JSON 解析;schema-3 header 的 configuration SHA-256
与 header fingerprint 一致;每条 game record 的 fingerprint、顺序/颜色对、开局、结果字段和逐手执行模型
attestation 均通过 harness `_already_done`/record validators;opening suite checksum 为
`db5bf2f7b1944a26bf6e027d6a32efc13c848f4dcb3d22eb1afd274383fe033e`;用 `complete_pair_sample`、
`wilson_interval` 与 `elo_from_winrate` 独立重算后与 summary 逐字段一致。固定模型身份为 b18
`9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d`、humanv0
`637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5`,b28 对手/裁判为
`798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0`。

| 已提交的不可变 checkpoint 档案 | configuration fingerprint | 原始 JSONL SHA-256 | `.jsonl.gz` SHA-256 |
|---|---|---|---|
| [`selfplay_screen_rank-5d-80__vs__rank-5d-40.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_batch1/selfplay_screen_rank-5d-80__vs__rank-5d-40.jsonl.gz) | `d08bb5318f594a5dbdb50e1006eb9bf56ca89f979dbffb2c37791edf479759b8` | `af4d912b2987649d51f62b004d624b8c88091a0133fbf3dfb99830f7f3d8bcbd` | `f30b1e8c98ff29514aa0ba8301edee3850f07ebe5b1c3cdd6d3786f05fe7fae2` |
| [`selfplay_screen_rank-7d-80__vs__rank-7d-40.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_batch1/selfplay_screen_rank-7d-80__vs__rank-7d-40.jsonl.gz) | `dbe719a9c5f96d48296588e80264b45a1ed4b6bf743bb5b1364419c3157c6770` | `11fb0b385ad8ede150e4008b960d5123dcae9bca85dcddb7dde9165dfe395e98` | `26c017977ccc2a13dcabfbb0c84bae3957b91848af743f49d76236c53d4c6dff` |
| [`selfplay_screen_rank-9d-80__vs__rank-9d-40.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_batch1/selfplay_screen_rank-9d-80__vs__rank-9d-40.jsonl.gz) | `fac29f99e215af1769f64def50785513440c36705361373ed9d3435597300e32` | `f8c512b9f816d31aaf46ee7211c8cb03207800f3af629225f826cf808779bafb` | `abeba92ca8aefcb35c7c6e00bee09880ba9b26dfb901b31f78901bbda56dcbd7` |
| [`selfplay_screen_rank-9d-40__vs__b28-20.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_batch1/selfplay_screen_rank-9d-40__vs__b28-20.jsonl.gz) | `edfa26aa3d7f138a766cc5285b62086de0a2e7e2173f02a1d1c42c080604a3c6` | `8bc9acf9213e2efe880862a033407c71d7e9921a61a911fa4eaa4123b2716d78` | `8ff6b3cdb21dc9931d5dc93333d231482ce0e7b096ec21bafbbb82ba873d23b3` |
| [`selfplay_summary_screen_batch1.json`](calibration/results/selfplay_v2_pikl/selfplay_summary_screen_batch1.json) | — | `0b920fb71627d7f584c23474e4614a8a6e7741ef86f583a3a94a20a47e81f139` | — |

四个档案均以 `mtime=0` 且不保存原文件名的确定性 gzip 生成;从仓库根目录一次复现全部四个档案:
`for f in superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl/selfplay_screen_rank-{5d-80__vs__rank-5d-40,7d-80__vs__rank-7d-40,9d-80__vs__rank-9d-40,9d-40__vs__b28-20}.jsonl; do gzip -n -9 -c "$f" > "superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl/artifacts/screen_batch1/$(basename "$f").gz"; done`。
解压后的字节必须与表中原始 JSONL SHA-256 一致;本地未压缩 checkpoint 保留用于审计/resume,但不提交到 Git。

**后续对局预声明(任何 continuation 之前冻结):**

1. 普通接缝 confirmation 分别为 `rank_5d@80:rank_5d@40`、`rank_7d@80:rank_7d@40`、
   `rank_9d@80:rank_9d@40`;各自使用全新 `phase=confirm` checkpoint,恰好20个完整 pair(40盘 decision
   games),默认最多40次 pair 尝试。screening 记录不加载、不计入 confirmation,固定样本结束后无论分类为何
   都不追样本。
2. 实验(4)尚未选定 confirmation 候选。下一步仅 screening `rank_9d@80:b28@20`,恰好10个完整 pair,
   最多20次 pair 尝试。完成并记账后才允许选择一个40完整-pair confirmation 候选;若 @80 仍不适合作为
   候选,先以同样的独立10-pair screening 规则考察更高 visits,不得把多个 screening 合并或边跑边改确认样本。

### C8. 实验(4) @80 screening 与下一档预声明(2026-07-22)

C7 预声明的 `rank_9d@80:b28@20` 独立 screening 已完成:共尝试11个颜色 pair(预定上限20),其中10个
完整 pair 进入固定筛查样本、1个 pair 因1盘 `inconclusive_unsettled` 整对排除。完整 pair 样本为 A 方
`rank_9d@80` **4–16**(20%,Wilson 95% CI [8.07%, 41.60%]),对应 Elo(A-B) **-240.8**
[-638.6, -88.5]。全部22盘原始结果计数为 A胜/A负/不可判=4/17/1;其中不完整 pair 内的1盘 A负也按
预声明规则排除。该结果仍然**仅是 screening,不作显著性或确认性声明,也不与其他 batch 合并**。

@80 因4–16的 screening 结果被淘汰,不会成为实验(4)的40完整-pair confirmation 候选。原始 checkpoint
与可变 summary 均经严格 JSON、configuration/header/game fingerprint、逐手模型 attestation、开局/pair
调度、`_already_done` resume 及 summary 独立重算校验:

| batch-2 不可变证据 | configuration fingerprint | 原始/摘要 SHA-256 | 压缩档案 SHA-256 |
|---|---|---|---|
| [`selfplay_screen_rank-9d-80__vs__b28-20.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_batch2_exp4_80/selfplay_screen_rank-9d-80__vs__b28-20.jsonl.gz) | `0528ed874fc4596467d510288516d1a3ead1767eff85849e886785add8c40f86` | `0db824d1d6a81af3d1e8971f225153ffe45487e391f29f6ff86bfd4c902ddb6a` | `a589941cebb082d18d182d6d7626c3cdf3657e057ae50cc6bb73bc13fb1ea327` |
| [`selfplay_summary_screen_batch2_exp4_80.json`](calibration/results/selfplay_v2_pikl/selfplay_summary_screen_batch2_exp4_80.json) | — | `a3e7cf16215d949bc4cfc17dd882e3943713fd2cc9348c33c450261219f8ba15` | — |

档案以 `gzip -n -9 -c selfplay_screen_rank-9d-80__vs__b28-20.jsonl > artifacts/screen_batch2_exp4_80/selfplay_screen_rank-9d-80__vs__b28-20.jsonl.gz`
确定性生成,解压字节与未压缩 checkpoint 完全一致;未压缩文件继续仅在本地保留用于审计/resume。

**下一步预声明(任何 continuation 之前冻结):**实验(4)接下来且只运行一次独立 screening
`rank_9d@160:b28@20`,恰好10个完整 pair,最多20次 pair 尝试。完成、固化并记账前不运行其他实验(4)
matchup,也不选择/启动40完整-pair confirmation;是否把 @160 选作 confirmation 候选必须等该固定筛查结束。

### C9. 实验(4) @160 screening 与下一档预声明(2026-07-22)

C8 预声明的 `rank_9d@160:b28@20` 独立 screening 已完成:尝试11个颜色 pair(预定上限20),10个完整
pair 进入固定筛查样本,1个 pair 因1盘 `inconclusive_unsettled` 整对排除。完整 pair 样本为 A 方
`rank_9d@160` **5–15**(25%,Wilson 95% CI [11.19%, 46.87%]),对应 Elo(A-B) **-190.8**
[-477.3, -42.1]。全部22盘原始结果为 A胜/A负/不可判=6/15/1;不完整 pair 内的1盘 A胜依预声明规则
排除。该结果仍然**仅是 screening,不作显著性或确认性声明,也不与 @40/@80 batch 合并**。

@160 因5–15的 screening 结果被淘汰,不会成为实验(4)的40完整-pair confirmation 候选。严格 JSON、
configuration/header/game fingerprint、逐手模型 attestation、开局/pair 调度、`_already_done` resume、
固定样本计数与可变 summary 独立重算均通过:

| batch-3 不可变证据 | configuration fingerprint | 原始/摘要 SHA-256 | 压缩档案 SHA-256 |
|---|---|---|---|
| [`selfplay_screen_rank-9d-160__vs__b28-20.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_batch3_exp4_160/selfplay_screen_rank-9d-160__vs__b28-20.jsonl.gz) | `dd66dbc0550498c7076527d195c443e5d21f1e2ec60601bf79bc7206ad4a99ff` | `baae1060c9147d9ef8cc53c5224ab47d53747b1bb4c6d47e005a7317f5781bac` | `58b0b53e49d4ce7be48ebec18e58a6549e49bfc37e8560da817510058d6d85fa` |
| [`selfplay_summary_screen_batch3_exp4_160.json`](calibration/results/selfplay_v2_pikl/selfplay_summary_screen_batch3_exp4_160.json) | — | `4af5d2dd83bcda0aae088a7b96a69009494c26ac9f1c6ee724e7a72eef5508c8` | — |

压缩档案以 `gzip -n -9` 确定性生成,解压字节与本地未跟踪原始 checkpoint 完全一致。

**下一步预声明(任何 continuation 之前冻结):**实验(4)接下来且只运行一次独立 screening
`rank_9d@320:b28@20`,恰好10个完整 pair,最多20次 pair 尝试。完成、固化并记账前不运行其他实验(4)
matchup,也不选择/启动40完整-pair confirmation;是否把 @320 选作 confirmation 候选必须等该固定筛查结束。

### C10. 实验(4) @320 screening 与 confirmation 预声明(2026-07-22)

C9 预声明的 `rank_9d@320:b28@20` 独立 screening 已完成:尝试11个颜色 pair(预定上限20),10个完整
pair 进入固定筛查样本,1个 pair 因1盘 `inconclusive_unsettled` 整对排除。完整 pair 样本为 A 方
`rank_9d@320` **11–9**(55%,Wilson 95% CI [34.21%, 74.18%]),对应 Elo(A-B) **+34.9**
[-121.5, +208.0]。全部22盘原始结果为 A胜/A负/不可判=12/9/1;不完整 pair 内的1盘 A胜依预声明规则
排除。该结果仍然**仅是 screening,不作显著性、确认性或“已经追平”声明,也不与较低 visits batch 合并**。

@320 是预声明 visits 网格中首个筛查胜率到达50%附近并越过点估计50%的档位,因此仅据此把它选为实验(4)
的固定 confirmation 候选;选择本身不是实验结论。严格 JSON、configuration/header/game fingerprint、逐手
模型 attestation、开局/pair 调度、`_already_done` resume、固定样本计数与可变 summary 独立重算均通过:

| batch-4 不可变证据 | configuration fingerprint | 原始/摘要 SHA-256 | 压缩档案 SHA-256 |
|---|---|---|---|
| [`selfplay_screen_rank-9d-320__vs__b28-20.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_batch4_exp4_320/selfplay_screen_rank-9d-320__vs__b28-20.jsonl.gz) | `488410f084b471503ae6a2b3e88d1fa1752f06246ca12e1ebed01b49e84d8f9c` | `f72378a724728204aedf00abbc25431aba0b31549750ca870bae78d67f274276` | `9fad26d9deca93adb43c160ce021a35714be9ce8146673e089ff43e641f8b481` |
| [`selfplay_summary_screen_batch4_exp4_320.json`](calibration/results/selfplay_v2_pikl/selfplay_summary_screen_batch4_exp4_320.json) | — | `dd66a8361c260f0f42f9fa28d63dc6ff6eedd7d0ddaf835455ce1e357b6b7bb9` | — |

压缩档案以 `gzip -n -9` 确定性生成,解压字节与本地未跟踪原始 checkpoint 完全一致。

**固定 confirmation 预声明(任何 confirmation 运行之前冻结):**实验(4)使用全新 `phase=confirm`、
`--experiment4` checkpoint 运行 `rank_9d@320:b28@20`,恰好40个完整 pair(80盘 decision games),默认
最多80次 pair 尝试。screening checkpoint/summary 永不加载或计入 confirmation;固定样本结束后无论 Wilson
分类为何都不追加样本。先前已预声明的普通 confirmation 保持不变:`rank_5d@80:rank_5d@40`、
`rank_7d@80:rank_7d@40`、`rank_9d@80:rank_9d@40` 各自使用全新 `phase=confirm` checkpoint,恰好20个
完整 pair(40盘 decision games),默认最多40次 pair 尝试,同样不加载 screening 数据且不追样本。

### C11. 实验(1)(2)修复后 confirmation 结果(2026-07-22)

C7 预声明的三个普通接缝 confirmation 均已完成固定样本。每组恰好20个完整颜色 pair(40盘 decision
games),screening 数据未加载、未并入,达到固定样本后未追加对局。结果如下:

| confirmation 对局(A vs B) | 完整 pair / 尝试 pair (上限) | 完整 pair 样本 | Wilson 95% CI | Elo(A-B)及95%区间 | 不完整 pair / 原始不可判盘 | 所有尝试的原始结果(A胜/A负/不可判) |
|---|---:|---:|---:|---:|---:|---:|
| rank_5d@80 vs rank_5d@40 | 20 / 27 (40) | **22–18 (55.0%)** | [39.83%, 69.29%] | +34.9 [-73.5, +150.7] | 7 / 7 | 26/21/7 |
| rank_7d@80 vs rank_7d@40 | 20 / 24 (40) | **21–19 (52.5%)** | [37.50%, 67.06%] | +17.4 [-92.3, +130.8] | 4 / 5 | 22/21/5 |
| rank_9d@80 vs rank_9d@40 | 20 / 24 (40) | **21–19 (52.5%)** | [37.50%, 67.06%] | +17.4 [-92.3, +130.8] | 4 / 4 | 23/21/4 |

**固定样本判定:**三个段位的点估计方向一致,均为 `@80 > @40`,但三组 Wilson 95% CI 都跨过50%,harness
分类均为 `inconclusive`。因此本批数据**没有确认**把 HumanSL+PIKL 搜索从40加到80 visits 会产生可辨识的
棋力提升;也没有观察到反向证据。screening 的70%/65%/55%在独立 confirmation 中回落到
55%/52.5%/52.5%,再次说明不能把小样本 screening 当作实验结论。实验(1)(2)的修复后固定样本采集至此
完成,结论为“方向一致但统计不确定”,而不是“搜索单调增强已证明”。

运行期间曾因 Python HTTP 客户端继承本机代理设置,在断网时由本机代理返回一次502而退出;checkpoint 在
48/60完整 pair 处安全恢复。恢复前 `_already_done` 对 header/configuration/game fingerprint、pair 调度和已有
记录逐条 fail-closed 校验通过;续跑显式设置 `NO_PROXY=127.0.0.1,localhost`,底层连接日志确认直连本机
`127.0.0.1:8000`。该中断没有丢失、重复或跨样本合并数据。

三个 JSONL 均通过严格 JSON、configuration/header/game fingerprint、逐手模型 attestation、开局/pair
调度、固定样本计数及 summary 独立重算校验。不可变证据如下:

| confirmation 不可变证据 | configuration fingerprint | 原始/摘要 SHA-256 | 压缩档案 SHA-256 |
|---|---|---|---|
| [`selfplay_confirm_rank-5d-80__vs__rank-5d-40.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/confirm_exp12/selfplay_confirm_rank-5d-80__vs__rank-5d-40.jsonl.gz) | `1706b3a639c3306fc1b3577fbb5df6f15eb001cbca41ca7a213b98d32b152a42` | `b446f56c9c66187b022906a650c9e98517624d206d933baf0e3de4e39bf0ed6f` | `704c4573dccef60dfdca80252e6425b53d6de3fafc5a566ba25a2a7ca14f9852` |
| [`selfplay_confirm_rank-7d-80__vs__rank-7d-40.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/confirm_exp12/selfplay_confirm_rank-7d-80__vs__rank-7d-40.jsonl.gz) | `473df1dd0325858818a989cd1d650dea6a3471899126705d6ffa5bdba9b53f81` | `9e277283fd9f72c4683e3093f11701f1033d2e9fae5914ecf84ccbe961ba1157` | `bb9ccbc22992c3680026aa8c38bf34eac59ef9ce5c314d431e456af65f955626` |
| [`selfplay_confirm_rank-9d-80__vs__rank-9d-40.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/confirm_exp12/selfplay_confirm_rank-9d-80__vs__rank-9d-40.jsonl.gz) | `dec42908e76e21a563cde07a534ca3e329c062d8d41a1d386e4242b4241132a2` | `f26f8daec0a27e4cfd5a23a3a7ae503478a224c970d34bacd23b753d0f08bdc3` | `acef4d78100fdca02722c693018bc704e5f09e84460c810a7e1482e5b2a725d1` |
| [`selfplay_summary_confirm_exp12.json`](calibration/results/selfplay_v2_pikl/selfplay_summary_confirm_exp12.json) | — | `43213a71b170c5731971f835bfbb63b4981c132189b893dcc3ef9429343393f9` | — |

压缩档案均以 `gzip -n -9` 确定性生成,解压字节与表中原始 JSONL SHA-256 一致;本地未压缩 checkpoint
继续保留用于审计/resume,但不提交到 Git。

### C12. 实验(3)修复后首轮 screening 预声明(2026-07-22)

实验目标保持用户已确认的 apples-to-apples 口径:测“低一段 HumanSL+PIKL 搜索需要多少 visits 才能达到/
超过高一段的 `@1s` humanPolicy argmax”。低一段搜索方使用显式 b18+humanv0+完整 PIKL,高一段基准为
humanv0 `@1s` argmax;不使用会混入加权采样选点损失的普通 `@1`。

**任何本轮运行之前冻结:**首轮只运行以下四个独立 `phase=screen` matchup:

- `rank_5d@40:rank_6d@1s`
- `rank_6d@40:rank_7d@1s`
- `rank_7d@40:rank_8d@1s`
- `rank_8d@40:rank_9d@1s`

每组恰好10个完整颜色 pair(20盘 decision games),最多20次 pair 尝试,使用同一锁定开局套件但各自独立
checkpoint。任一 pair 有不可判盘则整对排除;screening 只用于选择 visits 候选,不作显著性或实验完成声明。
某组若 `@40` 固定筛查点估计达到/超过50%,则把40记为当前支持网格内首个候选(只能表述为“所需 visits
≤40”);若低于50%,须先固化并记账该组结果,再单独预声明其 `@80` screening。不得合并不同 visits 的
screening,也不得在看到中途结果后改变样本量。四组候选全部确定后,再在任何 confirmation 运行之前冻结
各候选的确认样本。

### C13. 实验(3) @40 screening 与 confirmation 预声明(2026-07-22)

C12 预声明的四组独立 screening 均完成固定10个完整颜色 pair。结果只用于选择 confirmation 候选:

| screening 对局(A vs B) | 完整 pair / 尝试 pair (上限) | 完整 pair 样本 | Wilson 95% CI | Elo(A-B)及95%区间 | 不完整 pair / 原始不可判盘 | 所有尝试的原始结果(A胜/A负/不可判) |
|---|---:|---:|---:|---:|---:|---:|
| rank_5d@40 vs rank_6d@1s | 10 / 10 (20) | **19–1 (95%)** | [76.39%, 99.11%] | +511.5 [+307.5, +645.1] | 0 / 0 | 19/1/0 |
| rank_6d@40 vs rank_7d@1s | 10 / 12 (20) | **19–1 (95%)** | [76.39%, 99.11%] | +511.5 [+307.5, +645.1] | 2 / 2 | 21/1/2 |
| rank_7d@40 vs rank_8d@1s | 10 / 13 (20) | **17–3 (85%)** | [63.96%, 94.76%] | +301.3 [+141.9, +645.1] | 3 / 3 | 20/3/3 |
| rank_8d@40 vs rank_9d@1s | 10 / 17 (20) | **16–4 (80%)** | [58.40%, 91.93%] | +240.8 [+88.5, +638.6] | 7 / 8 | 21/5/8 |

四组在支持网格的最低 HumanSL+PIKL 搜索档 `@40` 即达到点估计50%以上,故按 C12 规则全部选择 `@40`
作为固定 confirmation 候选。筛查结果虽然很强,本节仍不作确认性或“已完成实验(3)”声明;在当前 harness
强制下限下,最终可识别的 visits 结论最多只能是 `≤40`,不能外推为恰好40或零搜索。

严格 JSON、configuration/header/game fingerprint、逐手模型 attestation、开局/pair 调度、固定样本计数和
summary 独立重算均通过。不可变证据如下:

| screening 不可变证据 | configuration fingerprint | 原始/摘要 SHA-256 | 压缩档案 SHA-256 |
|---|---|---|---|
| [`selfplay_screen_rank-5d-40__vs__rank-6d-1s.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_exp3_40/selfplay_screen_rank-5d-40__vs__rank-6d-1s.jsonl.gz) | `e40fd441def5e0680d0d94044bec2ef9cb6c9d88fcb9c064b448a36b86d346b2` | `7a856d6a0c76f00784bc8857685a047398dab3db3006411c78879f4ce05668a6` | `70a043250d99dd1c4d32e75b83689b03581d14a32f57a625d378d32d14d9f171` |
| [`selfplay_screen_rank-6d-40__vs__rank-7d-1s.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_exp3_40/selfplay_screen_rank-6d-40__vs__rank-7d-1s.jsonl.gz) | `6998a98ee39c7fc8093740140c86a0a67897b3333df13417a0145d737088e5fb` | `e124dc6635141b19943ffc0cbd9349726b37444b474b9320e8010eaf045766fc` | `3fcdd551476e0a0f54bb2e2e88c10733e2dec11a7d1924f71adaa15e54ee12d4` |
| [`selfplay_screen_rank-7d-40__vs__rank-8d-1s.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_exp3_40/selfplay_screen_rank-7d-40__vs__rank-8d-1s.jsonl.gz) | `dad716038e9ffc730a727b687b2b49823ec284eb23e7517dbee8e5b09962445b` | `3904286460908f1937f073d3a0e6295d97efcf541ad648cdddac201ad2896040` | `8f801c5127975b78751d4449f0ffdb57d3acb72c13625752a1a246c0439e6482` |
| [`selfplay_screen_rank-8d-40__vs__rank-9d-1s.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/screen_exp3_40/selfplay_screen_rank-8d-40__vs__rank-9d-1s.jsonl.gz) | `a9c88d777fdb32c173f7a1552a5edda6f7c574f9dd1cf60028cae0321c0c9fff` | `60eaec1f217cc909ca7c7330366a76502c589735c0bc488bdceecb867df57e8b` | `87bae6b4d51536df064c0694be25ebc44c512ced84674e50be0114b15b299937` |
| [`selfplay_summary_screen_exp3_40.json`](calibration/results/selfplay_v2_pikl/selfplay_summary_screen_exp3_40.json) | — | `dde2e2296ccdbdf77cf5b1ae8905533fc1e8f8f0d340b5d729800a982809d57d` | — |

**固定 confirmation 预声明(任何运行之前冻结):**实验(3)使用四个全新 `phase=confirm` checkpoint,分别
运行上述四个 `低一段@40 vs 高一段@1s` matchup;每组恰好20个完整颜色 pair(40盘 decision games),
默认最多40次 pair 尝试。screening 记录不加载、不计入 confirmation;每组固定样本结束后无论 Wilson 分类
为何都不追加样本。四组均完成后才能作“低一段在支持网格内需要≤40 visits 可超过高一段 @1s”的确认性
判定;若某组确认区间仍跨50%,如实报告该组统计不确定,不追样本、不改候选。

### C14. 实验(3)旧 @40 confirmation 状态与边界 @20 screening 预声明(2026-07-22)

C13 的旧 confirmation batch 停止时,四个 checkpoint 的实际状态经原始 JSONL 复核如下:

| 旧 confirmation 对局(A vs B) | 完整 pair / 尝试 pair | 完整 pair 样本 | 状态与边界实验用途 |
|---|---:|---:|---|
| `rank_5d@40` vs `rank_6d@1s` | **20 / 22** | **36–4** | 固定样本完成;保留为该精确 `@40` 对局的有效既有证据 |
| `rank_6d@40` vs `rank_7d@1s` | **20 / 24** | **36–4** | 固定样本完成;保留为该精确 `@40` 对局的有效既有证据 |
| `rank_7d@40` vs `rank_8d@1s` | **11 / 16** | **19–3** | 中断;仅作描述,不作固定样本结论且永不并入新样本 |
| `rank_8d@40` vs `rank_9d@1s` | **0 / 0** | — | 未启动 |

前两组各有2/4个不完整 pair;第三组有5个不完整 pair。所有原始 checkpoint 均原样保留。旧 batch
**仅作为寻找 search boundary 的程序被新协议取代**:两组已经完成的 `@40` confirmation 事实不作废,
但旧 batch 的任何棋局都不加载、不追加、不合并到以下 screening 或未来重新冻结的 confirmation。

上述状态已固化为 [`halted_confirmations_manifest.json`](calibration/results/selfplay_v2_pikl/artifacts/confirm_exp3_40_halted/halted_confirmations_manifest.json),
canonical digest 为 `8e6d2f94715f482c294e3593e68a4d5355a3d78fa79a39a3a68ed4f73fab824a`。三个现存
checkpoint 均通过严格 JSONL、schema/header/configuration fingerprint、连续 game fingerprint、pair 调度、
game record 与逐手模型 attestation 校验;表中统计由完整颜色 pair 独立重算。档案使用 `gzip -n -9`
(mtime=0、不写原文件名),解压字节与 raw SHA-256 完全一致:

| halted confirmation 不可变证据 | configuration fingerprint | raw SHA-256 | gzip SHA-256 |
|---|---|---|---|
| [`selfplay_confirm_rank-5d-40__vs__rank-6d-1s.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/confirm_exp3_40_halted/selfplay_confirm_rank-5d-40__vs__rank-6d-1s.jsonl.gz) | `ac2acbfdc4c642c6b4b4991e4a1cd115cafed739da039031ef913e77bab7a0a0` | `a9493fd58b7dcaf76dd058edcca13e3b9aaf46eeb7cc693981a706e1989328c9` | `7566fba2ca9c9c65e254bdd9a9d989a221b872ace029274183a8770ea4da1184` |
| [`selfplay_confirm_rank-6d-40__vs__rank-7d-1s.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/confirm_exp3_40_halted/selfplay_confirm_rank-6d-40__vs__rank-7d-1s.jsonl.gz) | `de53323c474125da5b3f8cc3dfdc59dcea3f0609b56dfa0b63476fb1bc81868b` | `8f1b84d7a1819050ac6fd5e6110f0596e6e6ae9bbbbc91d8ff77d0e769cdeb15` | `168fe27afdf08aa583a36ca68a9c0f30fb7bf4073f5c6e8a371ad25839c98c0a` |
| [`selfplay_confirm_rank-7d-40__vs__rank-8d-1s.jsonl.gz`](calibration/results/selfplay_v2_pikl/artifacts/confirm_exp3_40_halted/selfplay_confirm_rank-7d-40__vs__rank-8d-1s.jsonl.gz) | `f1234fa042abeb8f1b613e8ac1d806363728513299245afc088e94cea8d320ec` | `4365afebe83744199e6f7901f363b9110aa58bc3e7b864de723534be100a58dd` | `aa962af50101c47454eb7ce0f317b08da598fde6d60f0cace68d9249232ef444` |

第4组的 `absent` 状态也写入同一 manifest,但没有伪造空 archive 或 digest。原始本地 JSONL 不删除,
只读档案是其提交后的不可变证据副本。

**任何 boundary query 之前冻结:**协议版本为 `exp3-boundary-v1`。首轮且只启动以下四个独立
`phase=screen` matchup,每组目标恰好10个完整颜色 pair(20盘 decision games),最多20次 pair 尝试:

- `rank_5d@20:rank_6d@1s:10`
- `rank_6d@20:rank_7d@1s:10`
- `rank_7d@20:rank_8d@1s:10`
- `rank_8d@20:rank_9d@1s:10`

每组在恰好10个完整 pair 时按 A 方 decision-game **点估计 `>=50%` 为 pass**,`<50%` 为 fail;
任一 pair 有不可判盘则整对排除。达到20次 pair 尝试仍不足10个完整 pair 时 abort,不分类、不选候选。
`@20` pass 的下一独立 screening 点是 `@10`;`@20` fail 的下一独立 screening 点是 `@30`。
不得在结果出现后追加样本或更改下一点。

本轮绑定的已提交输入如下;生成器/loader 必须在运行前逐字节及逐来源验证它们:

| 冻结输入 | SHA-256 / canonical digest |
|---|---|
| opening suite checksum (`humansl-boundary-opening-suite-v1`) | `8d99e5288ee4e391f4b8429eba9e117864b7fadaa438b80bfe56d988c0f8e292` |
| opening allocation digest (`humansl-boundary-opening-allocation-v1`) | `45a2bbb390f1c27882a82ceea9e5b9dd5c4ab595e9e48a14b6ab5fa1e8a1c9c4` |
| known-endpoints manifest digest (`known-endpoints-exp3-v1`) | `0cdfac46b4b0e55936f8434eebef499a3179762d7cccc5565b35944efb59995f` |
| shared committed source-summary SHA-256 | `dde2e2296ccdbdf77cf5b1ae8905533fc1e8f8f0d340b5d729800a982809d57d` |

| transition / `@20` allocation | known-endpoint source digest | archive SHA-256 | decompressed checkpoint SHA-256 |
|---|---|---|---|
| `rank_5d__rank_6d` / `screen:rank_5d__rank_6d:20` (`b0061`–`b0080`) | `a1982503af2a295832f9358a15b95cf79637fb7bc413a74883083953f8beb4b6` | `70a043250d99dd1c4d32e75b83689b03581d14a32f57a625d378d32d14d9f171` | `7a856d6a0c76f00784bc8857685a047398dab3db3006411c78879f4ce05668a6` |
| `rank_6d__rank_7d` / `screen:rank_6d__rank_7d:20` (`b0161`–`b0180`) | `f58b2b471861b5a6bfbf49f3582cdb57add946218d280bb4ae15c4de9eccd21c` | `3fcdd551476e0a0f54bb2e2e88c10733e2dec11a7d1924f71adaa15e54ee12d4` | `e124dc6635141b19943ffc0cbd9349726b37444b474b9320e8010eaf045766fc` |
| `rank_7d__rank_8d` / `screen:rank_7d__rank_8d:20` (`b0261`–`b0280`) | `f85f3e1013de4fdfc6c4f7bae1694337dd82b0367a0fdb11291e00c5f47a8592` | `8f801c5127975b78751d4449f0ffdb57d3acb72c13625752a1a246c0439e6482` | `3904286460908f1937f073d3a0e6295d97efcf541ad648cdddac201ad2896040` |
| `rank_8d__rank_9d` / `screen:rank_8d__rank_9d:20` (`b0361`–`b0380`) | `bbdbb54feb9c8cab062fb8057420959fa96dc0276541472f7336c47064931c56` | `87bae6b4d51536df064c0694be25ebc44c512ced84674e50be0114b15b299937` | `60eaec1f217cc909ca7c7330366a76502c589735c0bc488bdceecb867df57e8b` |

本预声明及上述冻结输入验证必须先提交;提交前不允许发出 semantic probe 或任何 self-play HTTP query。
source-revision gate 及 live-probe 语义修复已由 commit
`451cd73b27c205f4518576f590943f2c0dd671b7` 实现并通过审核;本轮
canonical launch source **精确固定为该 commit**,不得使用随后仅修改文档的 commit 作为 source revision。
最终 launch 必须从 `451cd73b27c205f4518576f590943f2c0dd671b7` 的独立 clean detached worktree
`/tmp/katrain-exp3-boundary-451cd73b` 执行。low probe 请求中的 `maxVisits` 是精确发出的搜索 cap;
`rootInfo.visits` 是 KataGo 剪枝后的报告统计,不是请求值回显。在 shipping 8-thread 配置下,允许它为
positive plain int 且 `<= requested maxVisits + 7`;结果中分别记录 `requested_max_visits` 与
`reported_root_visits`。旧锁定 fixture 中未被选中(nonselected)候选手的 `order` 可随 live engine 漂移,不再因此否决
有效语义证据;仍要求关键候选存在,并以低 λ 选 `R2`、高 λ 选 `O6` 的 selected-move 变化证明 PIKL
产生了有意义的选点效果。

`requirements.txt` 的固定依赖要求 Python 3.12;在该 clean detached worktree 内必须按顺序执行以下 bootstrap/gate,
且 bootstrap 完成后所有 Python 命令只使用该 worktree 的 `.venv/bin/python`:

```sh
export UV_PYTHON=3.12
uv sync
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -c 'from pathlib import Path; import polib; [polib.pofile(str(p)).save_as_mofile(str(p.with_suffix(".mo"))) for p in Path("katrain/i18n/locales").glob("*/LC_MESSAGES/katrain.po")]'
test "$(git rev-parse HEAD)" = "451cd73b27c205f4518576f590943f2c0dd671b7"
test "$(git rev-parse --abbrev-ref HEAD)" = "HEAD"
test -z "$(git status --porcelain=v1 --untracked-files=no)"
.venv/bin/python superpowers/tracks/golaxy-ai-ladder-parity/calibration/generate_boundary_openings.py --check
```

直接用 `polib` 只编译被忽略的 `.mo`,不运行会改写 `.po` 的 `i18n.py`;上述 tracked-status gate 必须保持
为空。唯一允许的输出目录是原始工作区外置于 detached worktree 的绝对路径
`/Users/fan/Repositories/katrain-golaxy-ai-ladder-parity/superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary`。

上述 gate 全部通过后,依次使用以下 canonical probe、regression 和 screening 命令(这里只预声明,本次文档
提交不执行任何 HTTP/self-play):

`NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost CI=true KIVY_NO_ARGS=1 .venv/bin/python superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py --base-url http://127.0.0.1:8000 --low-visits 20 --experimental-min-humansl-search-visits 20`

`NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost CI=true KIVY_NO_ARGS=1 .venv/bin/python -m pytest -q tests/platforms/test_humansl_selfplay.py tests/platforms/test_humansl_probe.py tests/platforms/test_ladder_query_contract.py tests/platforms/test_golaxy_calibration_opponent.py tests/test_http_engine.py tests/core/test_ladder_strategy.py`

`NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost CI=true KIVY_NO_ARGS=1 .venv/bin/python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py --base-url http://127.0.0.1:8000 --phase screen --boundary-protocol exp3-boundary-v1 --expected-source-revision 451cd73b27c205f4518576f590943f2c0dd671b7 --experimental-min-humansl-search-visits 20 --max-pair-attempts 20 --out /Users/fan/Repositories/katrain-golaxy-ai-ladder-parity/superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl_boundary --matchups 'rank_5d@20:rank_6d@1s:10,rank_6d@20:rank_7d@1s:10,rank_7d@20:rank_8d@1s:10,rank_8d@20:rank_9d@1s:10'`

**正式 `@20` screening 结果（2026-07-24 恢复归档）：**上述四组预声明样本均完成10个完整颜色
pair，并按冻结的点估计 `>=50%` 规则通过：`rank_5d@20` 17–3、`rank_6d@20` 14–6、
`rank_7d@20` 15–5、`rank_8d@20` 16–4。原始 header 均绑定 clean detached source
`451cd73b27c205f4518576f590943f2c0dd671b7`、协议 `exp3-boundary-v1` 及上表三项冻结输入
digest；预声明提交为 `6712b622b6db94c979961ab59e8f17b6a78afaa2` 和
`bcf9080d80d2a991674ba71511c5559cda221170`。正式证据见
[`manifest.json`](calibration/results/selfplay_v2_pikl_boundary_recovery/formal_screen_20/manifest.json)
（canonical digest `0255ceb559ae05ff6660063b8053711eadced75e1dbcd04e5caf869689213a8e`）及
[`summary.json`](calibration/results/selfplay_v2_pikl_boundary_recovery/formal_screen_20/summary.json)
（canonical digest `afeb063d2facb6c81ba2fa5d86d8a2e759a2f13a0f1fb4af514252fa2a008f05`）。

**回溯性手工续跑（仅描述性）：**随后观察到四个 transition 的 `@10/@5/@2` 共12个点也全部达到
同一点估计阈值；`@2` 分别为15–5、13–7、12–8、12–8。但运行时尚无
`boundary_protocol.py`、不可变 `history_*.json` 链及 `--boundary-history-manifest` 门禁，也未建立
`selection_manifest_exp3_v1.json`，故这些点的 `evidence_class` 明确为 `descriptive_only`；
它们不能补造 Task 5 合规性，也不能支持正式“边界 `<=2`”结论。恢复清单见
[`manifest.json`](calibration/results/selfplay_v2_pikl_boundary_recovery/retrospective_manual_continuation/manifest.json)
（canonical digest `027110163aef8e2f0985c0850d4f5971006f6d7181fa5ac501696a3e41d34fc3`）及
[`summary.json`](calibration/results/selfplay_v2_pikl_boundary_recovery/retrospective_manual_continuation/summary.json)
（canonical digest `15ebfd122b7fed3cb7047830fc19de8ff5c7e15558c6819a6592b4cc819b55f7`）。

### C15. 星阵 9D 与 HumanSL 产品档对齐预声明(2026-07-23)

本实验独立于已结束的本地自对弈后台任务,直接在当前
`feature/golaxy-ai-ladder-parity` worktree 运行,不创建额外 worktree。冻结的可执行实现 revision 为
`dd9d7e0130334865f58005c3e714d39505ebb22b`;允许随后仅更新本路径下实验文档,但该 revision 到当前
`HEAD` 之间若任何 alignment runtime/helper/test 源码变化,runner 必须在星阵请求前失败关闭。

目标是找出对星阵 9D(API level `3000`)累计10个有效结果至少5胜的最低 `rank_9d` HumanSL 档,并在恰好
5–5时把产品安全档上调一级。固定候选网格为 `@1s/@4/@8/@16/@32`,`@1` 加权采样不参与。第一批且仅
第一批为 `rank_9d@8` 的5个有效结果;4–5胜下调一档、2–3胜原档补到10、0–1胜上调一档。筛选局累计
进入同候选的10局证据,不另起重复的“确认10局”。每候选独立按有效局交替颜色,10局为5黑5白。

每次 live invocation 只运行协议许可的一批,完整落盘后停止。每次可能计费的星阵尝试先写入只增不减的
quota ledger,单个操作者显式 quota 最多20次;不可判定、网络失败或进程中断后的未知尝试仍计费且不重试。
本地引擎 URL 必须精确为 `http://127.0.0.1:8000`,运行环境为 conda `py311_katago`,候选必须逐手证明
`@1s=humanv0 argmax` 或 `@4+ = b18+humanv0+canonical PIKL`,禁止把旧 b28 星阵数据并入。

唯一输出目录为
`calibration/results/golaxy_9d_humansl_alignment/`。创建新 quota 前必须由操作者确认对应星阵额度未使用;
首个真实批次前依次通过514项相关回归、离线 smoke 证据、本地 `/health`/模型身份、候选语义 probe、精确
source/output gate。首批结束后先在本节追加 charged attempts、有效胜负、颜色、不可判盘及冻结规则唯一
导出的下一批,再允许继续。

**首批结果(2026-07-23):** `rank_9d@8` 对星阵9D完成首批5个有效结果,战绩 **5–0**;依次执
黑/白/黑/白/黑,即颜色计数3黑2白。5次可能计费尝试全部产生有效胜负,不可判盘0,无网络重试。
quota 为 `golaxy9d-humansl-20260723-a`,本批结束时该 quota 与全实验 charged attempts 均为5。
候选 fingerprint 为 `c431d55a7b9f746a826a8d48415ef63113a89a501da75a945fb12fa8ab66a963`。

| 首批账本证据 | SHA-256 |
|---|---|
| `golaxy_9d_humansl_alignment/quotas.jsonl` | `c1e5e102352d3a3e72dfa2785e2ca0a6caba8bf27a82088a10f5e54493336249` |
| `golaxy_9d_humansl_alignment/checkpoints.jsonl` | `33ea23132464a84363bb61027225bd9cb1b9bd297392af729b7f22bb096736b1` |
| `golaxy_9d_humansl_alignment/attempts.jsonl` | `bbe0b31902ceb497d0770991cd421ad25d50ac0e1a93ae822c0f46700c2ff041` |

该5局仅完成筛选里程碑,不单独形成“产品档已对齐”的10局结论。按冻结规则,4–5胜必须降低搜索强度,
因此唯一下一批为相邻的 **`rank_9d@4` 对星阵9D,目标5个有效结果**;不得先给 `@8` 补局或跳测其他档。

**第二批结果(2026-07-23):** `rank_9d@4` 首批5个有效结果为 **2–3**,逐局为负/负/胜/胜/负,
颜色同样为黑/白/黑/白/黑(3黑2白)。新增5次计费尝试全部有效,不可判盘0;累计 quota 使用10/20。
该档 fingerprint 为 `c0867051b2a5bde164cd8a8e1d2036a3f3c890fd4e9f27849ca46767e1d143c4`。
此时累计账本 SHA-256 为:quotas
`c1e5e102352d3a3e72dfa2785e2ca0a6caba8bf27a82088a10f5e54493336249`,checkpoints
`37dc6c9cfd8b8e0706a430fb51385e3ee122c55a370a19e0acde82c1e5b0089e`,attempts
`85c97d60ab1774f8862a613612d1e642b05a4586e4ffa7dc7cda89b8b5a3e8c7`。

2–3胜命中冻结的边界分支,故唯一下一批为同档 **`rank_9d@4` 再补5个有效结果**,使该档累计达到
10局(最终5黑5白);不得改测其他档或丢弃本批2–3。

第三批首次启动在任何新 reservation 前被 fingerprint gate 拒绝,因此 quota 仍为10/20。根因已复现:
旧 fingerprint 错误包含文档提交后的当前 `HEAD` 及探针 `reported_visits`;相同 `@4` 请求会因正常剪枝把
candidate 报告为1或2 visits,裁判也会在205/206间波动,从而产生假配置漂移。修复 commit
`634ba17cddcdab989763ae9693ef9020ebef3cee` 将配置 fingerprint 限定为请求配置、模型身份、PIKL、裁判、
smoke 证据和冻结实现,排除上述观察统计与文档 HEAD;相关回归 **519 passed**。

既有10局账本继续显式绑定原 ledger revision `dd9d7e0130334865f58005c3e714d39505ebb22b`,不得重写。
续跑 `@4` 必须同时指定新实现 revision、旧 ledger revision 及 checkpoint 中原 fingerprint
`c0867051b2a5bde164cd8a8e1d2036a3f3c890fd4e9f27849ca46767e1d143c4`;缺少或不精确匹配均拒绝。
修复后本地-only preflight 已通过,稳定 configuration fingerprint 为
`deb7fd6ef4d12432d43f4c2aeea0718e09fc4df7a50b368053ce40504bbb42b2`,解析出的唯一下一批仍是
`rank_9d@4` 累计补到10局。该失败未访问星阵、未改变样本或计费分母。

**第三批结果(2026-07-23):** 修复后从原 checkpoint 续跑成功。`rank_9d@4` 后5个有效结果为
胜/负/胜/负/胜,与首批2–3合并后累计 **5–5**,颜色正好5黑5白。期间另有1次
`inconclusive` 不进入分母并按相同预定颜色补局,因此本批使用6次、全日累计16/20次计费尝试。
累计 attempts SHA-256 更新为
`a7ad287edcb732f8cf963fdf4148120d9ac9c54da06a0637d83f2c8dbd6ef22a`;quotas/checkpoints 未变化,
仍分别为 `c1e5e102352d3a3e72dfa2785e2ca0a6caba8bf27a82088a10f5e54493336249` 与
`37dc6c9cfd8b8e0706a430fb51385e3ee122c55a370a19e0acde82c1e5b0089e`。

按冻结规则,`rank_9d@4` 是累计10局的**实测对齐档**,但恰好5–5时产品安全档必须上调一级至
`rank_9d@8`;不得把尚未完成10局的 `@8` 写成最终实测达标。`@8` 已有5–0,故唯一下一批是把它累计
补到10个有效结果。当前 quota 仅余4次,不足以保证完成剩余5个有效结果;按协议使用剩余额度并保存部分
断点,达到20次硬上限即停,下一显式新 quota 再续。

**当日剩余额度结果(2026-07-23):** `rank_9d@8` 又完成4个有效结果且全胜,故累计 **9–0**,
有效颜色5黑4白。第20次结果持久化后,runner 在尝试预留第21次时被 quota 硬上限按设计拒绝;没有发出
第21次星阵请求,也没有产生未知 reservation。全日最终为20次计费尝试、19个有效结果、1个不可判定;
跨档有效总战绩14–5。最终 attempts SHA-256 为
`75c87db809f87f2b821acffb8c5f0a36003256d58fec72e126590e760651035a`;quotas/checkpoints SHA-256 仍为
`c1e5e102352d3a3e72dfa2785e2ca0a6caba8bf27a82088a10f5e54493336249` /
`37dc6c9cfd8b8e0706a430fb51385e3ee122c55a370a19e0acde82c1e5b0089e`。

冻结协议解析出的唯一下一动作仍为 **`rank_9d@8` 累计补到10局**:下一有效局预定执白,只差1局。
在该第10局完成前,`@8` 的9–0只能描述为极强的进行中证据,尚不把它写成最终10局产品安全档结论。
当前 quota 已满且禁止复用/重置;必须等操作者从星阵端确认新额度后,显式创建全新 quota ID 再续。

### C16. `rank_9d@5/@6` 固定星阵9D筛选(2026-07-24)

用户决定不再补 `rank_9d@8` 的第10局,也不实施自适应 v2 确认状态机。2026-07-24 新额度已由用户确认
可以尝试;本轮仅固定运行以下10个有效结果,完成后停止并报告,不自动追加样本或选择产品档:

- `rank_9d@5`：5个有效结果,颜色黑/白/黑/白/黑;
- `rank_9d@6`：5个有效结果,颜色白/黑/白/黑/白。

不可判定局不进分母并以同一颜色补局;所有可能计费尝试使用新 quota
`golaxy9d-fixed56-20260724-a`,上限20次。token/7002/429/断连零重试停止。棋手固定为
b18+humanv0+canonical PIKL,对手为星阵9D level3000,只访问本地 KataGo
`http://127.0.0.1:8000`。独立输出目录为
`calibration/results/golaxy_9d_fixed_5_6_20260724/`,不读写或合并 C15 的旧账本。

固定 runner 实现 revision 为 `2696fd7f8f359dccd8bded008c473d7d93ce0f87`;相关回归
**528 passed**。源码门禁允许本次预声明等后续 Markdown-only commits 推进 `HEAD`,但 runner、共用
alignment helper 或对应测试若相对该 revision 有任何提交/工作区变化,必须在星阵请求前拒绝。

本轮已完成,固定 runner 正常退出(退出码0):

| 棋手 | 有效战绩 vs 星阵9D | 有效胜率 | 有效局颜色 | 不可判定 | 计费尝试 |
|---|---:|---:|---|---:|---:|
| `rank_9d@5` | **5胜0负** | **100%** | B/W/B/W/B | 1(执白,原色补局) | 6 |
| `rank_9d@6` | **4胜1负** | **80%** | W/B/W/B/W | 0 | 5 |
| 合计 | **9胜1负** | **90%** | — | 1 | **11** |

`@5` 与 `@6` 都在这组小样本筛选中明显占优;其中搜索更低的 `rank_9d@5` 已取得5个胜局,因此是当前
更节省搜索的星阵9D产品对齐候选。`@5` 的5–0与`@6`的4–1不能用于反推 `@5` 强于`@6`,两者一盘之差
应视为小样本波动。本轮按用户指定在各5个有效结果后停止,不自动追加确认赛。

两档配置 fingerprint 分别为 `9297756ba210380eae4db8108011683451e525485dfc7a1fe7b683234cfb3752`
与 `2caf4c97d22b2c39ac8e0156f52633a837cbb31da5aad3b84123aa92899511b4`;原始 append-only ledger
`fixed_screen.jsonl` SHA-256 为 `5eb911b697de90dad5dca2d7b51a127af36788b747e13bca822af1725ea895c1`。

### C17. `rank_8d@4` 对星阵8D固定筛选预声明(2026-07-24)

目标是检验用户提出的“星阵8D可能接近 HumanSL `rank_8d@4`”假设。本轮固定取得5个有效结果后停止,
不做二分、自动追加或产品档选择:

- 我方固定为修复后的 b18+humanv0+canonical PIKL `rank_8d@4`;
- 对手固定为星阵“8段/星美鹿”,真实 API wire level **2800**(core rung 31),不是展示 Elo;
- 有效局颜色固定为 B/W/B/W/B;不可判定局不进分母并以原颜色补局;
- 新 quota ID 为 `golaxy8d-rank8d4-20260724-a`,最多9次可能计费尝试;token/7002/429/断连零重试停止;
- 本地 KataGo 固定为 `http://127.0.0.1:8000`,输出固定到
  `calibration/results/golaxy_8d_rank_8d_4_20260724/fixed_screen.jsonl`,不与任何9D账本合并。

固定 preset 为 `golaxy8d-rank8d4-20260724`;实现 source revision 为
`057fb959474e92b1fc91753d2f89e57e3dcf7034`,相关回归 **196 passed**。任何 scoped runner/helper/test
相对该 revision 的提交或工作区变化都必须在星阵请求前 fail closed。结果完成后在本节续写。

**结果:** 固定 runner 正常退出(退出码0),`rank_8d@4` 对星阵8D取得 **5胜0负(100%)**。五个有效结果
严格依次执 B/W/B/W/B,无不可判定局,因此只使用5次计费尝试。实际星阵请求日志和 ledger header 均记录
wire level `2800`;全程使用同一配置 fingerprint
`2b084fa06bb4f3be11ca6943677b03537e4d549566c75411ac9f259bb400914a`。

这5局支持“`rank_8d@4` 至少不弱于星阵8D”的方向性结论,并否定了二者在该小样本中势均力敌的直观预期;
但5–0仍是小样本筛选,不能量化真实胜率或 Elo 差。本轮按预声明停止,不自动追加确认赛。原始 append-only
ledger SHA-256 为 `2f910b18413ed464926348bb71c9f1a65f845fdca90d3116067ba30a8068250a`。

### C18. `rank_7d@4` 对星阵7D固定筛选预声明(2026-07-24)

固定测试修复后的 b18+humanv0+canonical PIKL `rank_7d@4` 对星阵“7段/星奇豚”(core rung 29,
真实 API wire level **2500**)。目标为5个有效结果,颜色固定 B/W/B/W/B;不可判定局原色补局。

今日 §C16/§C17 已分别使用11/5次额度,预计只剩4次。按用户决定先取得可用的4局,随后仍尝试第5局:
若正常返回则累计5个有效结果后停止;若返回额度耗尽/7002/429,零重试停止并保留调用前 reservation,
额度恢复后以同一账本补齐第5个有效结果。本地 reservation cap 为9,只用于容纳被拒绝尝试和不可判定局,
不绕过星阵服务端额度。

固定 preset/quota 分别为 `golaxy7d-rank7d4-20260724` / `golaxy7d-rank7d4-20260724-a`;输出固定为
`calibration/results/golaxy_7d_rank_7d_4_20260724/fixed_screen.jsonl`。实现 source revision 为
`b354c66e7ca8283d099589deb3b0dea33f207e10`,相关回归 **198 passed**。结果或额度停止点完成后在本节续写。

**结果:** 第5次尝试未被额度拒绝,固定 runner 正常退出(退出码0)。`rank_7d@4` 对星阵7D取得
**5胜0负(100%)**,严格依次执 B/W/B/W/B,无不可判定局,共5次 reservation/result。实际星阵请求为
wire level `2500`,全程 fingerprint 为
`3138723fac085758b1718e213730e93ef0a3db3b5eb5e0e888951bfee28e941c`。这说明当天服务端实际允许的
请求数至少超过根据前两批11+5次所推算的20次,此前“只剩4次”仅是保守估计,不是观测到的硬上限。

该5–0支持“`rank_7d@4` 至少不弱于星阵7D”的方向性结论,但仍不足以量化真实胜率/Elo 差。原始
append-only ledger SHA-256 为 `077f85aeab3e1cbbcbddd510df72438e0cf36a4b755ba39ddd0cf105bdfebe3c`。

### C19. 相邻段位纯 HumanSL argmax `@1s` 探索性筛选恢复(2026-07-24)

退出前另行运行了四组低段位 `rank_n@1s` 对 `rank_{n+1}@1s`。双方均为原生 HumanSL
`humanPolicy`、单 visit、确定性 argmax 选点；每组目标为10个完整颜色 pair。该批次没有预声明提交，schema 3
header 也没有 source-revision binding，因此恢复证据明确标记为 **`exploratory_only`**，只能观察相邻段位排序方向
和噪声，不能作为确认性实验，不能据此校准 Elo 或量化真实强度差。

| A(较低段位) | B(相邻较高段位) | A 完整-pair 战绩 | A 胜率 | 完整 pair | 不可判定 pair |
|---|---|---:|---:|---:|---:|
| `rank_5d@1s` | `rank_6d@1s` | 6–14 | 30% | 10 | 0 |
| `rank_6d@1s` | `rank_7d@1s` | 9–11 | 45% | 10 | 0 |
| `rank_7d@1s` | `rank_8d@1s` | 6–14 | 30% | 10 | 2 |
| `rank_8d@1s` | `rank_9d@1s` | 7–13 | 35% | 10 | 1 |

四组点估计都指向预期的段位方向，即较高段位胜局更多；但 `rank_6d@1s` 对 `rank_7d@1s` 仅9–11
（A 45%），方向很弱且容易由小样本噪声产生，不能写成已确认的段位分离。恢复过程逐条验证 schema 3 header
及 canonical configuration fingerprint、双方完整 player config、opening suite、capability/model/referee identity、
每局 attestation 和 pair 调度，并从完整 pair 独立重算表中结果。确定性 `gzip -n -9` 档案见
[`manifest.json`](calibration/results/selfplay_v2_policy_argmax_gap_recovery/exploratory_adjacent_rank_1s/manifest.json)
（canonical digest `5d2a9d63cef666def61dab1b1b63917a51aeb2f8728e63f8c36be3ebffc113d0`）及
[`summary.json`](calibration/results/selfplay_v2_policy_argmax_gap_recovery/exploratory_adjacent_rank_1s/summary.json)
（canonical digest `277cb36dad967824809c985ec46e6349a0a29366a127d11953a22ec9afb57555`）。原始工作区文件保持不变。

### C20. 星阵3星对 HumanSL `rank_9d` visits 固定筛选（2026-07-25）

按用户确认的条件筛选，先测试 `rank_9d@8` 对星阵“星阵3星/星猛虎”（core rung 36，真实 API wire
level 3300）。每档取得5个有效结果，HumanSL 颜色为 B/W/B/W/B；若 `@8` 5–0 则向下测试 `@4/@2`，
否则依次测试 `@16/@32/@64`。运行使用本机 b18 + humanv0 + canonical PIKL HumanSL 搜索，source revision
`aefc2076c49214108cdd328f23f4967acad228e6`，独立 quota
`golaxy3star-rank9d-conditional-20260725-a`。

| HumanSL 配置 | 胜–负 | 胜率 | 黑/白有效局 | 不可判定 |
|---|---:|---:|---:|---:|
| `rank_9d@8` | **0–5** | 0% | 3/2 | 0 |
| `rank_9d@16` | **0–5** | 0% | 3/2 | 0 |
| `rank_9d@32` | **0–5** | 0% | 3/2 | 0 |
| `rank_9d@64` | **0–5** | 0% | 3/2 | 0 |

`@8` 首盘即负，因此未进入向下分支，`@4/@2` 均未运行。整轮20次计费尝试全部得到有效结果，HumanSL
合计 **0–20**；runner 在完成 `@64` 第5局后以 `next_game=null` 正常退出。该结果显示在本实验配置下，
即使把 `rank_9d` 搜索从8 visits 增加到64 visits，仍未在20局小样本中战胜星阵3星；它是明确的方向性
筛选结果，但不用于估计 Elo 或证明真实胜率为0。

原始 append-only 账本：
`calibration/results/golaxy_3star_rank_9d_conditional_20260725/fixed_screen.jsonl`，SHA-256
`851b5c5a205a94e203dc5f80b8b6ba99e037042f13c8868465cb019a4d6da37c`。

### C21. 纯 b18 对星阵1–3星 visits 串行二分（2026-07-25，因7002停止）

按用户要求改用纯 `b18`（`requested_human_model=null`，请求无 `humanSLProfile`），同一时刻只运行一盘，
依次计划对标星阵3星、2星、1星。二分网格为 `2/4/8/16/32/64`，首点为对数中点 `@8`；每个筛选点
先取4个有效结果，0–2胜归入非强侧、3–4胜归入强侧，最终最小强侧候选需要对相应星阵等级累计10盘。
任一 `7002`、限流、配额或异常响应立即停止且零重试。

星阵3星已有的纯 `b18@64` 五盘 B/W/B/W/B 结果为 **4–1**，作为强端点。正式 v3 串行结果如下：

| 纯 b18 配置 | 对手 | 有效胜–负 | 不可判定 | 状态 |
|---|---|---:|---:|---|
| `b18@8` | 星阵3星 | **0–4** | 0 | 非强侧，二分上移 |
| `b18@16` | 星阵3星 | **2–2** | 2 | 非强侧，二分上移 |
| `b18@32` | 星阵3星 | **0–1** | 0 | 第2盘触发停止，未完成筛选 |
| `b18@64` | 星阵3星 | **4–1** | 0 | 既有强端点，尚未补到10盘 |

`b18@32` 第2盘（我方白）进行约31.8秒后，星阵返回
`code=7002, msg='illegal query'`。runner 立即停止；该 reservation 没有 result，不计入战绩，也没有重试。
因此本轮尚不能确定星阵3星的最终强侧候选，星阵2星和1星均未启动。此前错误地先从最低点启动的 v2
在用户纠正后中止并由 v3 明确 supersede；其结果不并入本表。

正式 append-only v3 账本共5条 seed result、12条 reservation、11条 result、1条 stopped：
`calibration/results/golaxy_b18_binary_stars_20260725/binary_search_v3.jsonl`，SHA-256
`4dd4cf3a016f139eb0a6fd6387ddcf2f9b58321e591602fdca2773ea212f3015`。

### C22. 纯 b18 对星阵1–3星 visits 串行二分续跑（2026-07-26，因网络异常停止）

v4 校验并继承 C21 的16条已完成结果，明确丢弃 v3 最后一条未配对的 `b18@32` 执白 reservation，
从同一颜色重新开始。执行规则保持不变：单盘串行、盘间5秒、不可判定局不计有效样本并重复颜色；任何远端异常
立即停止且不重试。

| 纯 b18 配置 | 对手 | 有效胜–负 | 不可判定 | 状态 |
|---|---|---:|---:|---|
| `b18@32` | 星阵3星 | **1–3** | 0 | 非强侧 |
| `b18@64` | 星阵3星 | **7–3** | 0 | 最小强侧候选，累计10盘完成 |
| `b18@8` | 星阵2星 | **1–3** | 0 | 非强侧 |
| `b18@16` | 星阵2星 | **8–1** | 1 | 筛选4–0后进入确认；仅9个有效结果，未完成10盘 |

星阵3星的二分边界由 `@32` 的1–3与 `@64` 的强端点确定，最终 `b18@64` 累计10盘为 **7–3**。
星阵2星先测 `@8` 得1–3，再测 `@16`；`@16` 前4个有效结果为4–0，因此选为强侧候选并继续补样。
第10个有效结果对应的我方白棋对局中，星阵接口返回 `Golaxy genmove network error`，runner 立即停止；该次
reservation 由 stopped 记录闭合，不计入战绩且没有重试。故星阵2星尚差1个有效结果，星阵1星尚未启动。

正式 append-only v4 账本共1条 header、16条 carry result、23条 reservation、22条 result、1条
level decision、1条 stopped，所有新 reservation 均有 result 或 stopped 闭合：
`calibration/results/golaxy_b18_binary_stars_20260726/binary_search_v4.jsonl`，SHA-256
`d64be0d257c8c7ce01ca4835ed72c4a0c0015eb4a59194d3b52765d067c02d9d`。

### C23. 纯 b18 对星阵1–2星 visits 串行二分完成（2026-07-26）

经核对，C22 的停止错误是 `Retryable: Golaxy genmove network error`，没有 HTTP/业务错误码，也不是7002。
按用户授权另建 v5 批次，校验并继承 v4 的38条已完成结果，丢弃由该网络错误闭合的 reservation/stopped，
继续保持单盘串行和盘间5秒冷却。本批19条新 reservation 全部由19条 result 闭合，没有远端错误或重试。

| 纯 b18 配置 | 对手 | 有效胜–负 | 不可判定 | 状态 |
|---|---|---:|---:|---|
| `b18@16` | 星阵2星 | **8–2** | 1 | 最小强侧候选，累计10盘完成 |
| `b18@8` | 星阵1星 | **3–1** | 0 | 强侧，二分下探 |
| `b18@4` | 星阵1星 | **3–1** | 0 | 强侧，二分下探 |
| `b18@2` | 星阵1星 | **7–3** | 0 | 网格下界及最小强侧候选，累计10盘完成 |

至此三个星级的纯 b18 对标结果均已完成：星阵3星为 `b18@64`（7–3），星阵2星为 `b18@16`
（8–2），星阵1星为 `b18@2`（7–3）。这些是每点4盘筛选、最终候选10盘确认的小样本分档结果，
不用于精确估计胜率或 Elo。

正式 append-only v5 账本共1条 header、38条 carry result、19条 reservation、19条 result、2条
level decision，所有新 reservation 均由 result 闭合：
`calibration/results/golaxy_b18_binary_stars_20260726/binary_search_v5.jsonl`，SHA-256
`9a5796b624924266efa6eb6937a4cb4833468bfa0270e5f115fc6d2714fc4082`。

### C24. 星阵5D–9D HumanSL 网格对标续跑完成（2026-07-28）

按用户要求，候选网格固定为 `rank_Nd@1s/@4/@8/@16/@32/@64`，复用所有同配置、同星阵等级的既有
有效结果，不重复对局。每个新筛选点取4个有效结果，3–4胜为强侧、0–2胜为弱侧；选出的最低强侧候选
累计到10个有效结果。所有真实对局严格单盘串行，盘间冷却5秒，不可判定局不进分母并重复颜色；7002、
429、配额/软封禁或其他远端异常立即停止且不重试。

新账本已继承29个有效旧结果：星阵7D `rank_7d@4` 5–0、星阵8D `rank_8d@4` 5–0、星阵9D
`rank_9d@4` 5–5及 `rank_9d@8` 9–0。由同一调度器离线重放后，唯一续跑起点为：

| 星阵等级 | 已复用证据 | 下一步 |
|---|---|---|
| 9D | `rank_9d@4` 5–5；`rank_9d@8` 9–0 | `rank_9d@8` 再1个有效结果，补满10局 |
| 8D | `rank_8d@4` 5–0 | 筛选 `rank_8d@1s` |
| 7D | `rank_7d@4` 5–0 | 筛选 `rank_7d@1s` |
| 6D | 无 | 从对数中点 `rank_6d@8` 开始 |
| 5D | 无 | 从对数中点 `rank_5d@8` 开始 |

2026-07-28 权限恢复后从上述唯一断点启动，runner 正常退出（退出码0）。全程同一时刻只运行一盘，新增
56条 reservation 全部由56条 result 闭合，无不可判定局、无 stopped、无7002/429或其他远端错误。
该轮实际得到的“最低强侧档”为：

| 星阵等级 | 筛选路径 | 最终最低强侧档 | 10盘战绩 |
|---|---|---|---:|
| 9D | 继承 `@4` 首4盘2–2；`@8` 原9–0后补1胜 | `rank_9d@8` | **10–0** |
| 8D | `@1s` 首4盘3–1，直接确认 | `rank_8d@1s` | **6–4** |
| 7D | `@1s` 2–2；转回继承5–0的 `@4` 补满 | `rank_7d@4` | **10–0** |
| 6D | `@8` 4–0 → `@4` 4–0 → `@1s` 首4盘3–1 | `rank_6d@1s` | **9–1** |
| 5D | `@8` 4–0 → `@4` 4–0 → `@1s` 首4盘4–0 | `rank_5d@1s` | **10–0** |

五个候选均恰好10个有效结果、5黑5白。后续复核发现4盘筛选规则把2–2视为弱侧，因此这里的结果回答
的是“最低强侧”而非“最接近五五开”：9D已有 `rank_9d@4` **5–5**，应视为比 `@8` 10–0更好的
实测对齐档；7D `rank_7d@1s` 当时只有2–2，仍需补样本。按用户决定，5D `rank_5d@1s` 10–0与6D
`rank_6d@1s` 9–1直接作为产品档保留，不再降低 HumanSL rank profile。8D仍采用 `rank_8d@1s` 6–4。

账本：`calibration/results/golaxy_humansl_rank5_9_alignment_20260727/alignment_v1.jsonl`，包含1条 header、
29条 carry result、56条 reservation、56条 result及5条 level decision，SHA-256
`14ddf05ef0c95e9017bd9e7d4345e7e43da9b4a66fe9a68cb3d300bea306a494`。

### C25. 7D `rank_7d@1s` 与9D `rank_9d@6` 对标续跑（2026-07-28，因7002停止）

按用户要求，7D复用 §C24 的 `rank_7d@1s` 4盘2–2并计划补到累计10盘；9D复用 §C16 的
`rank_9d@6` 5盘4–1并计划补到累计10盘。执行仍为单盘严格串行、盘间冷却5秒，出现7002或任何远端
错误立即停止且不重试。

封禁前7D新增3个有效结果（黑胜、白胜、黑负），累计由2–2变为 **4–3**。第4次新尝试由我方执白，
对局进行中星阵返回 `code=7002, msg=illegal query`；runner 立即写入 stopped 并退出，未再发起对局。
因此7D尚差3个有效结果，9D `rank_9d@6` 尚未开始追加，仍为历史 **4–1**。

账本：`calibration/results/golaxy_humansl_rank7_rank9_refinement_20260728/refinement_v1.jsonl`，包含1条
header、9条 carry result、4条 reservation、3条 result和1条 stopped，SHA-256
`c3a782609b47f812df26c1aacf871c72c2661581687773b2059eac642b4efbc2`。

### C26. 7D、1星与准5D–准9D串行对标活动（2026-07-29，因7002停止）

本轮仅使用修复后、逐请求身份核验的引擎路径。7D继承 §C25 的7个有效结果；1星使用显式 b18
`maxVisits=1` 的原生 `policy` 确定性 argmax（不带 HumanSL/PIKL）；准5D–准9D依次使用低一段
HumanSL profile，在 `@1s/@4/@8/@16/@32/@64` 网格做4盘筛选、最低强侧10盘确认，并在强侧过强时
把相邻弱侧也补到10盘后选取更接近5–5的一档。所有对局严格单盘串行、盘间冷却5秒；任一远端错误
立即停止且不重试。

停止前得到：

| 星阵等级 | 候选 | 战绩 | 状态 |
|---|---|---:|---|
| 7D | `rank_7d@1s` | **5–5 / 10** | 继承4–3后新增1–2，累计确认完成 |
| 1星 | `b18@1` | **2–2 / 4** | 4盘筛选弱侧，按预声明结束 |
| 准5D | `rank_4d@8` | **3–1 / 4** | 强侧筛选 |
| 准5D | `rank_4d@1s` | **9–1 / 10** | 网格下界仍过强，确认完成 |
| 准6D | `rank_5d@8` | **4–0 / 4** | 强侧筛选 |
| 准6D | `rank_5d@1s` | **10–0 / 10** | 网格下界仍过强，确认完成 |
| 准7D | `rank_6d@8` | **4–0 / 4** | 强侧筛选 |
| 准7D | `rank_6d@1s` | **9–1 / 10** | 网格下界仍过强，确认完成 |
| 准8D | `rank_7d@8` | **4–0 / 4** | 强侧筛选 |
| 准8D | `rank_7d@1s` | **2–2 / 4** | 相邻弱侧，尚差6盘确认 |
| 准8D | `rank_7d@4` | **10–0 / 10** | 最低强侧已确认，但阶段尚待弱侧补样 |
| 准9D | — | — | 尚未启动 |

第68次新 reservation 为准8D `rank_7d@1s` 相邻弱侧补样、我方执黑；首个星阵请求返回
`code=7002, msg='illegal query'`。runner 立即写入 attempt stopped 与 campaign stopped，未重试、未再
发起任何对局。该次没有 result，不计入战绩。账本包含1条 header、7条 carry result、68条
reservation、67条 result、6条 stage started、5条 stage completed、1条 attempt stopped和1条
campaign stopped；所有74个有效结果均有唯一 origin ID。账本：
`calibration/results/golaxy_alignment_campaign_20260729/campaign_v1.jsonl`，SHA-256
`da354ddadf07a2bd2963c99cab94798c87be3f62822207c69338364410952699`。

### C27. 同段位 HumanSL `@1` 加权采样 vs `@1s` argmax（2026-07-29）

修复前仅有9D、7D、5D各10盘的旧结果，且位于禁止复用的旧 namespace。本轮在修复后 harness 中
重新覆盖 `n=9...1`：A方为 `rank_nd@1`（同一 `humanPolicy` 的加权采样），B方为
`rank_nd@1s`（同一 `humanPolicy` 的确定性 argmax）。每组使用10个冻结开局，每个开局交换黑白，
恰好取得10个完整 pair、20盘有效结果。这里两方都只从 humanv0 `humanPolicy` 选点；health/header 中
主进程显示 b28 是原生 HumanSL 附载 humanv0 的预期路由，不是旧 `humansl_search` 错把搜索结果取自
b28 的 wiring bug。

| HumanSL profile | `@1` 加权采样 | `@1s` argmax | 完整 pair | 不可判定 pair |
|---|---:|---:|---:|---:|
| `rank_9d` | **0** | **20** | 10 | 0 |
| `rank_8d` | **1** | **19** | 10 | 0 |
| `rank_7d` | **0** | **20** | 10 | 0 |
| `rank_6d` | **2** | **18** | 10 | 0 |
| `rank_5d` | **2** | **18** | 10 | 0 |
| `rank_4d` | **0** | **20** | 10 | 2 |
| `rank_3d` | **3** | **17** | 10 | 2 |
| `rank_2d` | **5** | **15** | 10 | 1 |
| `rank_1d` | **2** | **18** | 10 | 1 |
| **合计** | **15** | **165** | **90** | **6** |

九组全部为 `screen_complete`。4D、3D、2D、1D为补足完整 pair 实际分别运行24、24、22、22盘；
若一个 pair 任一颜色不可判定，则该 pair 两盘都不进入上表20盘有效样本。结果显示差异主要来自选点
规则而非搜索：同一 profile、同一1 visit 下，argmax 在180盘有效样本中取得91.7%胜率。

目录：`calibration/results/selfplay_v2_same_rank_sampling_vs_argmax_20260729/`；汇总文件
`selfplay_summary.json` SHA-256 为
`a81d49c4df13f7e165ece0f6064d1caa47114b4d7e48b48e6696ba5e29252f74`。

### C28. 低一段 HumanSL `@1s` argmax vs 高一段 `@1` 加权采样（2026-07-29）

承接 §C27，测试 `rank_{n-1}d@1s vs rank_nd@1`，覆盖 n=9...2。A方为低一段 profile 的
`humanPolicy` argmax，B方为高一段 profile 的 `humanPolicy` 加权采样。每组10个冻结开局、交换黑白，
取得10个完整 pair、20盘有效结果；不可判定 pair 整对剔除并继续补样。

| A：低一段 `@1s` | B：高一段 `@1` | A胜–负 | 完整 pair | 不可判定 pair |
|---|---|---:|---:|---:|
| `rank_8d@1s` | `rank_9d@1` | **16–4** | 10 | 0 |
| `rank_7d@1s` | `rank_8d@1` | **17–3** | 10 | 1 |
| `rank_6d@1s` | `rank_7d@1` | **17–3** | 10 | 2 |
| `rank_5d@1s` | `rank_6d@1` | **14–6** | 10 | 0 |
| `rank_4d@1s` | `rank_5d@1` | **18–2** | 10 | 0 |
| `rank_3d@1s` | `rank_4d@1` | **18–2** | 10 | 0 |
| `rank_2d@1s` | `rank_3d@1` | **14–6** | 10 | 1 |
| `rank_1d@1s` | `rank_2d@1` | **16–4** | 10 | 2 |
| **合计** |  | **130–30** | **80** | **6** |

八组全部为 `screen_complete`，低一段 argmax 在160盘有效样本中取得81.25%胜率，且每个相邻段位
组合都获胜。这说明普通 `@1` 的加权采样损失在本设置下大于一个 HumanSL profile 段位差；它比较的
仍主要是选点规则，不应解释为1 visit 搜索强度差。

目录：`calibration/results/selfplay_v2_adjacent_argmax_vs_sampling_20260729/`；汇总文件
`selfplay_summary.json` SHA-256 为
`166a46f2b99d977f8e3cae87ffc3212a07991cea9f9837353a6433a5df3c9cdd`。

### C29. 星阵1星与准5D–准9D串行对标续跑完成（2026-07-30）

本轮以 §C26 的停止账本作为只读父账本，并绑定父文件 SHA-256
`da354ddadf07a2bd2963c99cab94798c87be3f62822207c69338364410952699` 创建 v2 child ledger。为满足用户
明确要求，v2 将星阵1星 `b18@1` 从原先4盘筛选改为无条件累计10个有效结果；v1 的历史重放语义保持不变，
避免用新规则解释旧账本。准5D–准9D继续采用低一段 HumanSL profile 和
`@1s/@4/@8/@16/@32/@64` 网格，复用同配置历史结果，不重复对局。

全部新对局严格单盘串行、盘间冷却5秒；出现7002或任何远端错误即停止且不重试。本轮新增41条
reservation，全部由41条 result 闭合，没有 stopped、7002或其他远端错误。连同74条继承结果，离线重放
共校验115条唯一来源证据，最终状态为 `completed`，未知计费尝试为空。

| 星阵等级 | 候选路径与证据 | 最终选定档 | 10盘战绩 | 不可判定 | 结论 |
|---|---|---|---:|---:|---|
| 1星 | `b18@1` 原2–2，续跑4–2 | `b18@1` | **6–4** | 0 | 10盘对齐完成 |
| 准5D | `rank_4d@8` 3–1；`rank_4d@1s` 9–1 | `rank_4d@1s` | **9–1** | 0 | 网格下界仍过强 |
| 准6D | `rank_5d@8` 4–0；`rank_5d@1s` 10–0 | `rank_5d@1s` | **10–0** | 0 | 网格下界仍过强 |
| 准7D | `rank_6d@8` 4–0；`rank_6d@1s` 9–1 | `rank_6d@1s` | **9–1** | 0 | 网格下界仍过强 |
| 准8D | `rank_7d@8` 4–0；`@4` 10–0；`@1s` 7–3 | `rank_7d@1s` | **7–3** | 4 | 已确认候选中最接近5–5 |
| 准9D | `rank_8d@8` 4–0；`@4` 9–1；`@1s` 6–4 | `rank_8d@1s` | **6–4** | 1 | 已确认候选中最接近5–5 |

准5D–准7D的 `@1s` 已是预声明网格下界，因此状态记为 `overstrong_at_grid_floor`，不虚称五五开；准8D、
准9D分别选取已补满10个有效结果且更接近5–5的 `rank_7d@1s` 与 `rank_8d@1s`。不可判定局不进入
10盘有效样本分母。

正式 append-only v2 账本包含1条 header、74条 carry result、41条 reservation、41条 result、
3条 stage started和3条 stage completed：
`calibration/results/golaxy_alignment_campaign_20260730/campaign_v2.jsonl`，SHA-256
`4eff5434cd864215a35171d635e4268d06f31f45ca6be27e82e4e0a1105f64d5`。

### C30. HumanSL policy temperature 单调性试验（2026-08-03）

本轮只验证 41 档 AI 后续拟合所需的选点温度理论，不改生产 ladder。显式 `@1tT` 对 HumanSL
`humanPolicy` 使用 `p^(1/T)` 重新加权，再用绑定到 manifest、对局身份、开局、颜色和手数的确定性
SHA-256/u64 draw 做 inverse-CDF 采样；旧 `@1` 加权采样和 `@1s` argmax 语义均保持不变。

实验由 schema 2 manifest `calibration/temperature_pilot_v2.json` 冻结：实现基线
`052b4253289bbf149f46150cf141b1157d016403`，manifest 提交
`edf1bc8d13a463187bd11d61595debf667e3c765`，canonical self-digest
`573bb59d0242c1916fef220d355849de1ef4afd665d4ab66ebfce40fd2be7f7a`。使用 b28 主模型 SHA
`798da8fe...3d3f0` 与 humanv0 SHA `637746e4...4ab5`，9 组严格串行；每组 10 个完整颜色 pair、
20 盘有效结果，不可判定 pair 整对剔除并按冻结上限补样。

| HumanSL profile | A（预期更强） | B | A胜–负 | 95% Wilson CI | 分类 |
|---|---|---|---:|---:|---|
| `rank_1d` | `@1t1` | `@1t2` | **19–1** | 76.4%–99.1% | persuasive direction |
| `rank_1d` | `@1t0.4` | `@1t1` | **18–2** | 69.9%–97.2% | persuasive direction |
| `rank_1d` | `@1s` argmax | `@1t0.4` | **7–13** | 18.1%–56.7% | point inversion |
| `rank_5d` | `@1t1` | `@1t2` | **20–0** | 83.9%–100% | persuasive direction |
| `rank_5d` | `@1t0.4` | `@1t1` | **15–5** | 53.1%–88.8% | persuasive direction |
| `rank_5d` | `@1s` argmax | `@1t0.4` | **8–12** | 21.9%–61.3% | point inversion |
| `rank_9d` | `@1t1` | `@1t2` | **20–0** | 83.9%–100% | persuasive direction |
| `rank_9d` | `@1t0.4` | `@1t1` | **20–0** | 83.9%–100% | persuasive direction |
| `rank_9d` | `@1s` argmax | `@1t0.4` | **12–8** | 38.7%–78.1% | direction supported |

冻结总门槛要求至少 8/9 组 A 的点估计胜率高于 50%；实际为 **7/9**，因此正式状态为
`fail: fewer_than_8_direction_matchups`。不过六组纯采样温度比较全部方向正确，A 合计
**112–8（93.3%）**；失败完全来自把 argmax 当作 `T→0` 单调端点的假设。三组 argmax 边界合计
**27–33**，且 1D、5D 都发生点估计反转。产品结论是：argmax 不得纳入同一条单调温度轴；由于总
gate 失败，本轮证据也不得用于拟合或发布 41 档配置。下一步只能先用单独冻结、独立审核的诊断协议
解释 argmax 边界与有限正温度区间，诊断通过后再另行决定是否开展产品温度拟合。

证据目录：`calibration/results/selfplay_temperature_pilot_v2/`。`summary.json` 文件 SHA-256 为
`e6ffc35a329931abba07b745bb51e2f87bda4002241268508c6f1bd9c052a7a3`，其内部 summary digest 为
`524b8cfa4b2114024b214a7b15b9de307260174d120c93e2d073d445adc2df07`；`report.md` 文件 SHA-256 为
`56f05fd4cc6344deb78d193e985cd4001dbf35ca5771f00917f708e6f9cea72c`。

审计限制：原始 checkpoint/launch/summary 为保持摘要链不可变，原样保留了操作者机器上的模型绝对路径，
因此这些文件不是环境中立的公开数据格式。KataGo 运行身份报告为 commit
`342d2a7b5ac9de9ed11b62065761276585744406-dirty`；实验后复核的可执行文件 SHA-256 为
`1bc697889072048dc82ee42af5d4529628cd00a4696e8ec5f4e67aaa21fb069e`，但该 executable SHA 未在开跑前
写入 launch snapshot，故不能宣称可从 Git revision 唯一重建引擎二进制。模型权重、HumanSL 权重、
运行源文件、manifest、开局与逐手选择仍由各自 SHA/attestation 绑定。零字节 `.jsonl.lock` 仅是运行期
互斥残留，不属于证据链，不提交。

最终代码复审另发现冻结 runner 的 strict gate 未拒绝“第10个完整 pair 后追加的行”。为避免修改六个
已绑定运行源导致 v2 source drift，提交 `4a9c978d` 新增独立只读
`calibration/audit_temperature_pilot_v2.py`：先复用冻结 strict gate，再对同一 checkpoint snapshot 强制
验证 EOF 半 pair、pair-attempt 上限，以及第10个完整 pair 必须恰为账本终点。post-freeze audit 对9个
checkpoint 全部返回 `audit_status=pass`，且不改变原始 `fail` gate；追加完整 inconclusive pair、半 pair
或超上限记录的回归样本均被拒绝。

---

### C31. 41 档准段位 T=1.15 候选首轮筛选（2026-08-03）

C30 的温度 gate 失败后本轮转入 41 档候选筛选：准 n 段候选取 `rank_nd@1t1.15`，分别对**上档**
`rank_nd@1`（候选应更弱）与**下档** `rank_(n-1)d@1`（候选应更强）各跑 10 个完整颜色 pair、
20 盘有效棋，看候选能否夹在两档之间。

本批与后续 C32–C35 全部**未**使用 `--boundary-protocol`，header 中
`boundary_protocol_version=None`，亦未绑定 `--expected-source-revision`。按 §C19 先例，
以下全部记为 **`exploratory_only`**：无预声明、无源码修订绑定，不支持确认性结论，
不得用于拟合或发布 41 档配置。

首次运行（`ladder_41_t115_screen_20260803`，12:44）17 组全部在引擎层失败：每组 20 次
pair attempt 全部返回 `inconclusive_engine`，0 个完整 pair、0 盘有效棋，未写出
`selfplay_summary.json`。`_player_move` 把 attestation/路由漂移吞成 `unavailable` 并记为
inconclusive 而非崩溃，因此失败表现为静默烧完尝试上限。10 分钟后以同参数重跑为
`ladder_41_t115_screen_v2_20260803`（12:54–14:11），17 组全部 `screen_complete`。

| 准 n 段候选 | 上档对局（上档胜率，应>50%） | 下档对局（候选胜率，应>50%） | 夹住? |
|---|---:|---:|---|
| 准1段 `rank_1d@1t1.15` | `rank_1d@1` 13–7 (0.65) | 对 `rank_1k@1` 11–9 (0.55) | ✅ |
| 准2段 `rank_2d@1t1.15` | `rank_2d@1` 15–5 (0.75) | 对 `rank_1d@1` 13–7 (0.65) | ✅ |
| 准3段 `rank_3d@1t1.15` | `rank_3d@1` 14–6 (0.70) | 对 `rank_2d@1` 7–13 (0.35) | ❌ 弱于下档 |
| 准4段 `rank_4d@1t1.15` | `rank_4d@1` 15–5 (0.75) | 对 `rank_3d@1` 11–9 (0.55) | ✅ |
| 准5段 `rank_5d@1t1.15` | `rank_5d@1` 13–7 (0.65) | 对 `rank_4d@1` 11–9 (0.55) | ✅ |
| 准6段 `rank_6d@1t1.15` | `rank_6d@1` 12–8 (0.60) | 对 `rank_5d@1` 10–10 (0.50) | ⚠️ 与下档持平 |
| 准7段 `rank_7d@1t1.15` | `rank_7d@1s` 18–2 (0.90) | 对 `rank_6d@1` 8–12 (0.40) | ❌ 弱于下档 |
| 准8段 `rank_8d@1t1.15` | `rank_8d@1s` 19–1 (0.95) | 对 `rank_7d@1s` 4–16 (0.20) | ❌ 显著弱于下档 |
| 准9段 `rank_9d@1s` | `rank_9d@4` 17–3 (0.85) | —（本批未测下档） | — |

结论：单一温度 T=1.15 **不能**跨整条阶梯使用。低段（准1、2、4、5）落点合理，高段随段位升高
被削弱得越来越过分——准8段候选对下档只有 0.20，且上档以 0.95 碾压。温度对棋力的边际影响
随基础档位增强而放大。因此 C32 转为逐段重调温度。

设计文档 §7.3 的合格线（对下档 ≥3–1、对上档 ≤1–3）是 4 盘制门槛，本批为 20 盘制，
不适用，故上表只按点估计方向判定，未套用该门槛。

---

### C32. 高段与职业顶尖候选温度重调（2026-08-03）

按 C31 的结论逐段重调：准3段降到 T=1.05，准6段 T=1.1，准7/准8段大幅降到 T=0.4；
同时首次测量职业顶尖段的纯 b18 visits 轴。11 组，各 10 完整 pair / 20 盘有效棋，全部
`screen_complete`。

| 对局 | 结果 | 胜率 | 判读 |
|---|---:|---:|---|
| `rank_3d@1` vs `rank_3d@1t1.05` | 9–11 | 0.45 | 上档未更强，方向反转 |
| `rank_3d@1t1.05` vs `rank_2d@1` | 11–9 | 0.55 | 强于下档 ✅ |
| `rank_6d@1` vs `rank_6d@1t1.1` | 12–8 | 0.60 | 上档更强 ✅ |
| `rank_6d@1t1.1` vs `rank_5d@1` | 9–11 | 0.45 | 弱于下档 ❌ |
| `rank_7d@1s` vs `rank_7d@1t0.4` | 11–9 | 0.55 | 上档略强 ✅ |
| `rank_7d@1t0.4` vs `rank_6d@1` | 18–2 | 0.90 | 远强于下档，夹不住 ❌ |
| `rank_8d@1s` vs `rank_8d@1t0.4` | 10–10 | 0.50 | 与上档持平 ⚠️ |
| `rank_8d@1t0.4` vs `rank_7d@1s` | 12–8 | 0.60 | 强于下档 ✅ |
| `b18@1` vs `rank_9d@4` | 12–8 | 0.60 | b18@1 略强于 9段实测对齐档 |
| `b18@12` vs `b18@1` | 17–3 | 0.85 | b18 visits 轴分离良好 |
| `b18@64` vs `b18@12` | 17–3 | 0.85 | 同上 |

结论：T=0.4 对准7段矫枉过正（对下档 0.90），T=1.05/1.1 对准3、准6段仍不能干净夹住。
**至 2026-08-04 尚无任何一档准段位在 20 盘样本下同时满足「弱于上档且强于下档」的干净区间**，
准1、2、4、5 段只是点估计方向正确、CI 全跨 50%。相比之下纯 b18 的 visits 轴（@1→@12→@64
各 0.85）分离度明显好于 HumanSL 温度轴，是职业顶尖段更可靠的候选轴。

---

### C33. 准1段温度加密与 40 盘 confirm（2026-08-03）

针对准1段把温度网格加密到 T ∈ {1, 1.1, 1.15}，并首次对该档跑 `--phase confirm`
（20 完整 pair / 40 盘有效棋）。

screening（`ladder_41_quasi1_retune_20260803`，10 pair / 20 盘）：

| 对局 | 结果 | 胜率 |
|---|---:|---:|
| `rank_1d@1` vs `rank_1d@1t1.1` | 15–5 | 0.75 |
| `rank_1d@1t1.1` vs `rank_1k@1` | 7–13 | 0.35 |

T=1.1 已经掉到 1k 之下，比 C31 中 T=1.15 对 1k 的 0.55 更弱——同一档上 T=1.1 反而弱于
T=1.15，与「温度越高越弱」的单调假设不符，属点估计反转。

confirm（`ladder_41_quasi1_seeded_20260803`，20 pair / 40 盘，`classify_seam` 双侧 95% Wilson）：

| 对局 | 结果 | 胜率 | 95% Wilson CI | 分类 |
|---|---:|---:|---:|---|
| `rank_1d@1t1` vs `rank_1d@1t1.1` | 28–12 | 0.70 | 0.546–0.819 | **`a_stronger`** |
| `rank_1d@1t1.1` vs `rank_1d@1t1.15` | 19–21 | 0.475 | 0.329–0.625 | `inconclusive` |
| `rank_1d@1t1.1` vs `rank_1k@1t1` | 24–16 | 0.60 | 0.446–0.737 | `inconclusive` |

这是 41 档全部批次里**唯一一条方向性正式分类**：T=1 显著强于 T=1.1。（`classify_seam` 只在
confirm 相位生效；C34 的 4k/5k 与 C35 的 7d/6d、9d/8d 的 CI 同样不跨 50%，但它们是 screen 相位，
只得到 `screen_complete`，不构成方向判定。）但 T=1.1 与 T=1.15
在 40 盘下无法区分，说明 0.05 的温度步长已低于 40 盘样本的分辨率——温度网格再加密不会有回报，
除非同时把样本量抬上去。上一行 screening 里 T=1.1 对 `rank_1k@1` 是 0.35、confirm 里对
`rank_1k@1t1` 是 0.60，两个对手不同（后者带 T=1），不能直接对比。

---

### C34. 级位相邻链 1k–20k 原生 `@1` 筛选（2026-08-03 — 08-04）

分三批跑完级位段全部 19 条相邻缝，A 恒为高一级（如 `rank_8k@1` vs `rank_9k@1`），
每缝 10 完整 pair / 20 盘有效棋，全部 `screen_complete`。

| 缝 | 结果 | 胜率 | 缝 | 结果 | 胜率 |
|---|---:|---:|---|---:|---:|
| 1k/2k | 13–7 | 0.65 | 11k/12k | 14–6 | 0.70 |
| 2k/3k | 13–7 | 0.65 | 12k/13k | 12–8 | 0.60 |
| 3k/4k | 13–7 | 0.65 | 13k/14k | 12–8 | 0.60 |
| **4k/5k** | **16–4** | **0.80** | 14k/15k | 11–9 | 0.55 |
| 5k/6k | 11–9 | 0.55 | 15k/16k | 12–8 | 0.60 |
| 6k/7k | 14–6 | 0.70 | **16k/17k** | **10–10** | **0.50** |
| 7k/8k | 13–7 | 0.65 | 17k/18k | 12–8 | 0.60 |
| 8k/9k | 11–9 | 0.55 | 18k/19k | 12–8 | 0.60 |
| 9k/10k | 12–8 | 0.60 | 19k/20k | 14–6 | 0.70 |
| 10k/11k | 12–8 | 0.60 | | | |

19 条缝的点估计方向**全部** ≥0.50，级位段整体单调；但 20 盘样本下只有 4k/5k 一条
（CI 0.584–0.919）下界高于 50%，其余 18 条 CI 全部跨 50%。**20 盘筛选量对单级约
+70 Elo 的间隔没有分辨力**，这是后续正式验证必须按 §7.5 走 20 盘/边、40 条边的直接依据。
16k/17k 打平是最弱的一条缝。

数据完整性说明：`ladder_41_kyu_adjacent_20260803` 实际跑了 12 条缝，但
`selfplay_summary.json` 只保留 4 条——`run_selfplay.py` 在整轮结束时以全量覆盖写 summary，
只含该次 invocation 的 matchup，后续子集续跑会覆盖掉先前的聚合行。原始 checkpoint 未受影响，
另 8 条已用 `run_selfplay` 自身的 `complete_pair_sample` / `elo_from_winrate` / `wilson_interval`
从原始账本重算为 `selfplay_summary.recovered.json`；`selfplay_summary.json` 中幸存的 4 行
逐字段精确复现，以此校验其余 8 行。

---

### C35. 段位原生相邻链 1d–9d `@1` 筛选与 6d/5d 复现失败（2026-08-03 — 08-04）

对段位段全部 8 条原生相邻缝 `rank_nd@1` vs `rank_(n-1)d@1` 各跑 10 完整 pair / 20 盘有效棋
（`--max-pair-attempts 30`），全部 `screen_complete`。

| 缝 | 结果 | 胜率 | 95% Wilson CI | 判读 |
|---|---:|---:|---:|---|
| 2d/1d | 13–7 | 0.65 | 0.433–0.819 | 方向正确 |
| 3d/2d | 13–7 | 0.65 | 0.433–0.819 | 方向正确 |
| 4d/3d | 14–6 | 0.70 | 0.481–0.855 | 方向正确 |
| **5d/4d** | **10–10** | **0.50** | 0.299–0.701 | **持平** |
| **6d/5d** | **5–15 / 11–9** | **0.25 / 0.55** | 0.112–0.469 / 0.342–0.742 | **两次矛盾**（见 C36 的 40 盘 confirm） |
| 7d/6d | 15–5 | 0.75 | 0.531–0.888 | 下界 >50% |
| **8d/7d** | **10–10** | **0.50** | 0.299–0.701 | **持平** |
| 9d/8d | 15–5 | 0.75 | 0.531–0.888 | 下界 >50% |

8 条缝里只有 7d/6d 与 9d/8d 的 CI 下界高于 50%；5d/4d、8d/7d 完全持平。**原生 HumanSL `@1`
在 5d–8d 区间基本分不开相邻档**，这正是需要温度轴或搜索轴插值的实测依据，也与 C34 的样本量
结论一致。

6d/5d 跑了两次且结论相反（08-03 为 0.25/Elo −190.8，08-04 重跑为 0.55/Elo +34.9，两个
Wilson 区间仅在 0.342–0.469 重叠）。两次运行的 configuration 指纹
`ef7c18df…9099926` 逐字段相同，开局套件校验和 `db5bf2f7…033e` 相同，10 个开局
`o001`–`o010` 与颜色分配一一对应。逐槽位比对 20 个 (pair, 颜色) 槽：**手数 20/20 全不相同，
胜负 9/20 不同**（例：pair0 色0 317 手负 → 363 手胜）。因此该配置下的对局是随机的而非确定性的
——`@1` 加权采样叠加 `wideRootNoise=0.04`，同配置同开局不产生同一局棋。两次结果的差异是采样
方差，不是数据缺陷或引擎漂移；20 盘样本不足以定住这条缝的方向，**6d/5d 方向至今未定**。

（对照：C30 的显式 `@1tT` 使用绑定 manifest/对局身份/开局/颜色/手数的确定性 SHA-256 draw，
与本批的 `@1` 语义不同，不可混用这条随机性结论。）

---

### C36. 6d/5d 加厚 confirm：40 盘仍判不实（2026-08-04）

针对 C35 中方向未定的 6d/5d 缝，用 `--phase confirm --matchups rank_6d@1:rank_5d@1:20
--max-pair-attempts 50` 重新起了一批独立 checkpoint（不与 screen 批合并，phase 进指纹）。

| 项 | 值 |
|---|---|
| 完整 pair | 20 / 20（0 inconclusive，20 次尝试全中） |
| 有效棋 | 40 |
| 结果 | 25–15 |
| 胜率 | 0.625 |
| Elo | +88.7（CI −17.4 – +214.9） |
| 95% Wilson CI | 0.470 – 0.758 |
| `classify_seam` | **`inconclusive`** |

方向与 C35 第二次一致（6段强于5段），点估计也是三轮里最高的，但 **CI 下界 0.470 仍未越过
50%**，双侧检验判不实。

把同一强度配置的三轮放在一起（各自独立冻结批次，此处仅作方差观察，不作合并统计）：

| 批次 | 相 | 结果 | 胜率 |
|---|---|---:|---:|
| 08-03 | screen | 5–15 | 0.25 |
| 08-04 | screen | 11–9 | 0.55 |
| 08-04 | confirm | 25–15 | 0.625 |
| 合计 | — | 41–39 | 0.5125 |

80 盘累计 0.51。**结论：`rank_6d@1` 与 `rank_5d@1` 的真实强度差小于 80 盘能分辨的尺度。**
与 C34/C35 的样本量结论合流，并对设计文档「每边 20 盘有效棋、高档至少 11–9」的正式验证门槛
构成直接反证——该门槛在 5d–8d 区间欠功率，40 组相邻边里至少 5d/4d、6d/5d、8d/7d 三条按现有
证据预期会卡在 10–10 附近，触发「调整可调候选并以新的冻结批次重跑」。

本批同样未带 `--boundary-protocol` 与 `--expected-source-revision`，按 §C19 precedent 仍为
`exploratory_only`，不得用于拟合或发布 41 档配置。

---

## D. 待办 / 开放项

- [x] **实验(1)(2)有效重跑**:新 namespace 的 `@80 vs @40` screening 与预声明 confirmation 已完成;
  三段位确认样本点估计均略高于50%,但95% CI 全跨50%,结论为方向一致、统计不确定。
- [x] **相邻段位纯 HumanSL argmax 探索性筛选恢复**:四组 `rank_n@1s` 对 `rank_{n+1}@1s` 均完成
  10个完整颜色 pair，点估计方向一致；`6d` 对 `7d` 的45%尤其弱/噪声大。因无预声明和 source-revision
  binding，仅为 `exploratory_only`，不支持确认性或校准 Elo 结论。
- [ ] **实验(3)边界定位(进行中)**:旧 @40 batch 的两个 confirmation 已完成、一个中断、一个未启动;
  `exp3-boundary-v1` 四组正式 `@20` screening 已完成且全部通过。另观察到手工续跑的
  `@10/@5/@2` 全部通过，但因 Task 5 历史门禁缺失仅属描述性证据，不能正式报告边界 `<=2`；
  Task 5 实现、合规历史链及后续候选冻结/confirmation 仍待完成。
- [ ] **实验(4)有效重跑**:`@40/@80/@160/@320` screening 已完成并选定 `rank_9d@320`;
  `rank_9d@320 vs b28@20` 的40完整-pair confirmation 已预声明,尚未运行。
- [x] **星阵9D HumanSL产品档固定筛选**:`rank_9d@8` 首批5–0,`rank_9d@4` 首批2–3;
  `rank_9d@4` 已累计5–5成为实测对齐档。按 §C15 唯一下一批为把安全档 `rank_9d@8` 从5局补到
  10局的旧计划已由用户停止;`@8` 保持9–0。§C16 固定筛选已完成:`@5` 5–0、`@6` 4–1;
  搜索更低的 `@5` 是当前产品候选,本轮不自动追加确认赛。
- [x] **星阵8D HumanSL固定筛选**:§C17 的 `rank_8d@4` 已完成5个有效结果并取得 **5–0**;
  无不可判定局,5次计费尝试后按预声明停止。
- [x] **星阵7D HumanSL固定筛选**:§C18 的 `rank_7d@4` 已完成5个有效结果并取得 **5–0**;
  第5次尝试未触发预期中的额度拒绝。
- [ ] **星阵5D–9D HumanSL对标复核**:5D `rank_5d@1s`（10–0）与6D `rank_6d@1s`（9–1）按
  用户决定直接保留，8D采用 `rank_8d@1s`（6–4），9D现有最佳五五开证据为 `rank_9d@4`（5–5）。
  7D `rank_7d@1s` 在 §C25 补至4–3后遇7002，尚差3个有效结果；9D `rank_9d@6` 追加赛未启动，
  保持历史4–1。待软封禁解除后只能从新账本人工审计续跑，不得自动重试 stopped 账本。
- [x] **星阵1星 `b18@1` 与准5D–准9D低一段 HumanSL 对标**:§C29 已从精确绑定 §C26 父 SHA 的
  新 child ledger 恢复并完成。1星 `b18@1` 为6–4；准5D–准7D的网格下界 `@1s` 分别为9–1、
  10–0、9–1，仍明显过强；准8D `rank_7d@1s` 为7–3，准9D `rank_8d@1s` 为6–4。全程串行，
  41条新 reservation 全部闭合且无远端错误。
- [x] **HumanSL policy temperature 单调性 pilot**:§C30 已完成 1D/5D/9D 共9组、180盘有效样本。
  六组有限正温度比较全部方向正确；argmax 边界仅1/3方向正确，总门槛7/9，正式状态为 fail。
- [ ] **温度 gate 失败诊断**:先冻结并独立审核单独的诊断协议，解释 argmax 边界反转以及有限正温度
  区间能否单调复现；在诊断通过并另行批准产品拟合前，不拟合 41 档候选、不写入生产 ladder。
- [ ] **41 档候选温度轴仍未选出可用档**:§C31 单一 T=1.15 跨阶梯失败(高段被削过头,准8段对下档仅
  0.20);§C32 逐段重调 T=1.05/1.1/0.4 仍无一档同时满足「弱于上档且强于下档」;§C33 加密到
  T∈{1,1.1,1.15} 后 T=1.1 与 T=1.15 在 40 盘下不可区分。**温度步长已低于当前样本量的分辨率**,
  再加密网格无回报。下一步要么抬样本量,要么改用分离度更好的轴(见下条)。全部为 `exploratory_only`。
- [ ] **改用 b18 visits 轴做职业顶尖段候选**:§C32 实测 `b18@12` vs `b18@1`、`b18@64` vs `b18@12`
  均为 0.85,分离度明显优于 HumanSL 温度轴;`b18@1` vs `rank_9d@4` 为 0.60。待评估是否把职业顶尖段
  的候选轴从温度改为 b18 visits。
- [ ] **筛选样本量不足以定相邻档方向**:§C34 级位 19 条缝仅 4k/5k 一条 CI 下界 >50%,§C35 段位 8 条缝
  仅 7d/6d、9d/8d 两条。20 盘对单档约 +70 Elo 的间隔没有分辨力。正式验证必须按设计 §7.5 走
  40 条边 × 20 盘有效棋,不能沿用筛选样本下结论。
- [x] **6d/5d 接缝方向未定** — 第三轮已跑完,见 §C36。40 盘 confirm 得 25–15 / 0.625,方向对但
  CI 下界 0.470 仍未过 50%,判定 `inconclusive`;三轮合计 41–39 = 0.51。**该缝在 `@1` 采样下
  不可由 80 盘分辨**,结论从"方向未定"升级为"差距小于可分辨尺度"。同区间 5d/4d、8d/7d 亦为
  10–10 持平。(补正:screen 相已锁死 10 pair,同参数 resume 不会补跑,必须另起 `--phase confirm` 批次。)
- [x] **「提样本量 vs 换轴」已可判定 —— 答案是换轴，样本量这条路走不通（2026-08-10 功效计算）**

  对「胜率 p vs 0.5」的双侧检验（α=0.05、功效 80%、正态近似）反解每条缝所需盘数：

  | 真实间隔 | 对应胜率 | 每缝需要 | 40 条缝合计 |
  |---:|---:|---:|---:|
  | 35 Elo | 0.550 | 771 | 30,840 |
  | 50 Elo | 0.571 | 377 | 15,080 |
  | **70 Elo** | **0.599** | **191** | **7,640** |
  | 100 Elo | 0.640 | 93 | 3,720 |
  | 150 Elo | 0.703 | 40 | 1,600 |

  设计 §7.5 的正式验证是每边 20 盘 × 40 条缝 = 800 盘，**即每缝 20 盘**。
  该样本量对 +70 Elo 间隔的**检验功效只有 13.7%** —— 也就是说，即使每一条缝都真有一档的
  间隔，这套协议也会判掉其中约 86%。**它不是一道验证门槛，它是一次抛硬币。**

  要让 +70 Elo 可验证需要每缝 ~191 盘（合计 ~7,640 盘，约为原计划的 10 倍）。

  而 6d/5d 的实测点估计是 80 盘累计 41–39 = 0.5125，**折合 +8.7 Elo**。它落在上表最上面一行
  之外：这两档不是「难测」，是**根本没有差别**。同区间 5d/4d、8d/7d 均为 10–10，同一诊断。

  ⇒ **结论：不能靠加样本量走到认证。** 5d–8d 区间要动的是配方而不是盘数——原生 HumanSL `@1`
  在该区间不产生可测的强度差。这一条**取代**了原「提高样本量 or 换插值轴」的二选一：
  第一个选项已被算掉。

  ⚠️ 换轴的候选也已收窄：温度轴按 §C30 正式 gate `fail`，且 §C33 显示 T=1.1 与 T=1.15 在 40 盘下
  不可区分、**温度步长已低于当前样本量分辨率**；§C32 实测 b18 visits 轴 `@12 vs @1`、`@64 vs @12`
  均为 0.85（≈ +301 Elo，按上表每缝 40 盘内即可验证）。**b18 visits 是目前唯一有实测分离度的轴。**

- [ ] **正式验证门槛在 5d–8d 区间欠功率**:§C36 反证了设计文档「每边 20 盘、高档至少 11–9」的通过线
  ——6d/5d 在 80 盘下仍是 0.51。40 组相邻边里至少 5d/4d、6d/5d、8d/7d 三条按现有证据预期会卡在
  10–10 附近并触发"调整可调候选并以新的冻结批次重跑",800 盘正式验证需要先决定:是提高每边样本量,
  还是承认原生 `@1` 在该区间必须换用温度轴/搜索轴插值来拉开间距。
- [ ] **`inconclusive_engine` 静默烧尽尝试**:§C31 首轮 17 组 × 20 次 attempt 全部 `inconclusive_engine`、
  0 盘有效棋且不报错——attestation/路由漂移被 `_player_move` 吞成 `unavailable` 并记为 inconclusive。
  建议加一条早停:某组连续 N 次 attempt 全为 `inconclusive_engine` 时中止整轮并非零退出。
- [ ] **🔴 `develop` 从未被 CI 把过关（2026-08-10 实测）** — `test_and_build.yaml` 触发条件只有
  `pull_request` + `workflow_dispatch`,**没有 push**;进 `develop` 的工作全是本地 merge commit、
  **0 个 PR**;最近 40 次 CI 运行的分支为 master 33 / katago-1.17.1 5 / dependabot 2、**develop 侧 0 次**。
  ⇒ 本仓的依赖图与测试集从未被任何自动化验证过。两个已确认的后果:(a) `respx` 只声明在
  `requirements-web.txt` 而不在 `pyproject.toml`,`uv sync` 装不到,导致 `tests/web_ui` **任何子集**
  都在 collection 阶段中断(collection 早于 `-k`),该中断**同时藏住了 34 个存量失败**;
  (b) `smartbox-xiangqi-rules = { path = "../../xiangqi/rules" }` 在 `[project.dependencies]`
  (无条件依赖),使本仓在**任何非 smartbox 父目录布局**下 `uv lock` 直接失败。(a) 已修;(b) 属象棋 track。
- [ ] **`selfplay_summary.json` 全量覆盖会丢聚合行**:§C34 的 `ladder_41_kyu_adjacent_20260803` 跑了 12 条缝,
  summary 只剩最后一次 invocation 的 4 条。原始 checkpoint 无损,已重算出
  `selfplay_summary.recovered.json`。建议改为按 matchup 合并写入,或写入前先读回既有 summary。
- [x] **`tests/core/test_ladder_strategy.py` 21 个用例在 HEAD 红** — **已修复,本条曾长期过期**。
  `9f4c1821` 落地 41 档目录表后未同步该文件,自 2026-08-03 12:58 起红;`7455199c`(2026-08-05,
  「把阶梯策略测试对准 41 档目录」)已修,实测 **29 passed**。本条待办在修复后又挂了 5 天没人划掉——
  因为**没有任何自动化会告诉我们它绿了**:`develop` 从未被 CI 把过关(见下条)。
- [x] **星阵3星 HumanSL visits 固定筛选**:§C20 的 `rank_9d@8/@16/@32/@64` 各完成5个有效结果，
  四档均为 **0–5**，合计0–20；因 `@8` 非5–0，按条件协议未运行 `@4/@2`。
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
| 星阵9D `rank_9d@5/@6` 固定筛选 | `calibration/results/golaxy_9d_fixed_5_6_20260724/fixed_screen.jsonl` |
| 星阵8D `rank_8d@4` 固定筛选 | `calibration/results/golaxy_8d_rank_8d_4_20260724/fixed_screen.jsonl` |
| 星阵7D `rank_7d@4` 固定筛选 | `calibration/results/golaxy_7d_rank_7d_4_20260724/fixed_screen.jsonl` |
| 7D、1星与准5D–准9D串行活动 | `calibration/results/golaxy_alignment_campaign_20260729/campaign_v1.jsonl` |
| 1星与准5D–准9D串行续跑完成 | `calibration/results/golaxy_alignment_campaign_20260730/campaign_v2.jsonl` |
| 同段位 HumanSL `@1` vs `@1s`（1D–9D） | `calibration/results/selfplay_v2_same_rank_sampling_vs_argmax_20260729/` |
| 低一段 HumanSL `@1s` vs 高一段 `@1`（1D–9D接缝） | `calibration/results/selfplay_v2_adjacent_argmax_vs_sampling_20260729/` |
| HumanSL policy temperature 单调性 pilot | `calibration/results/selfplay_temperature_pilot_v2/` |
| 星阵3星 `rank_9d@8/@16/@32/@64` 固定筛选 | `calibration/results/golaxy_3star_rank_9d_conditional_20260725/fixed_screen.jsonl` |
| 旧自对弈全部接缝(**仅作历史 b28 诊断;HumanSL 结论无效**) | `calibration/results/selfplay/selfplay_rank-<Xd>-<V>__vs__rank-<Xd>-<V'>.jsonl` |
| 旧自对弈汇总(**不得续跑或并入修复后样本**) | `calibration/results/selfplay/selfplay_summary.json` |
| 修复后新自对弈 namespace | `calibration/results/selfplay_v2_pikl/` |
| 实验(3)正式 `@20` 恢复档案 | `calibration/results/selfplay_v2_pikl_boundary_recovery/formal_screen_20/` |
| 实验(3)手工续跑描述性恢复档案 | `calibration/results/selfplay_v2_pikl_boundary_recovery/retrospective_manual_continuation/` |
| 相邻段位纯 HumanSL argmax `@1s` 探索性恢复档案 | `calibration/results/selfplay_v2_policy_argmax_gap_recovery/exploratory_adjacent_rank_1s/` |
| schema 3 HumanSL 语义探针 | `calibration/results/semantic_probe/humansl_semantic_probe_20260721T183703.918547Z_c0bedf887cf3.json` |
| 冒烟/level 探针 | `calibration/results/smoke_report.json` |
| 41 档 T=1.15 首轮(引擎失败,0 有效棋) | `calibration/results/ladder_41_t115_screen_20260803/` |
| 41 档 T=1.15 首轮重跑(17 组) | `calibration/results/ladder_41_t115_screen_v2_20260803/` |
| 41 档高段与职业顶尖温度重调(11 组) | `calibration/results/ladder_41_retune_pro_20260803/` |
| 41 档准1段温度重调 screening | `calibration/results/ladder_41_quasi1_retune_20260803/` |
| 41 档准1段 40 盘 confirm | `calibration/results/ladder_41_quasi1_seeded_20260803/` |
| 41 档级位相邻链 1k–20k(12+4+3 条缝) | `calibration/results/ladder_41_kyu_adjacent_20260803/`、`..._part_b_20260803/`、`..._part_c_20260803/` |
| 41 档段位原生相邻链 3d/2d、6d/5d | `calibration/results/ladder_41_native_bounds_20260803/` |
| 41 档段位原生相邻链 6d/5d 重跑 | `calibration/results/ladder_41_native_6d5d_repeat_20260804/` |
| 41 档 6d/5d 40 盘 confirm(§C36) | `calibration/results/ladder_41_native_6d5d_confirm_20260804/` |
| 41 档段位原生相邻链 2d/1d、4d/3d、5d/4d | `calibration/results/ladder_41_native_bounds_missing_low_20260804/` |
| 41 档段位原生相邻链 7d/6d、8d/7d、9d/8d | `calibration/results/ladder_41_native_bounds_missing_high_20260804/` |

> 上表全部 `ladder_41_*` 批次的原始 checkpoint 以 gzip 归档在各批次的 `artifacts/*.jsonl.gz`
> 并已提交（沿用 `selfplay_v2_pikl/artifacts/` 先例，303 MB → 11 MB，逐个校验解压后 SHA-256
> 与活文件一致）；未压缩的 `.jsonl` 留在原地不跟踪，以便 `run_selfplay.py` 按指纹续跑。
> 零字节 `.jsonl.lock` 仅是运行期 flock 残留，任何一次正常结束的运行都会留下，不携带状态信息，不提交。
