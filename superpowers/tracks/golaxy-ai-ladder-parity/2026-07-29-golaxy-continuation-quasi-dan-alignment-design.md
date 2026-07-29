# 星阵7D续跑、1星 `b18@1` 与准段 HumanSL 对标设计

日期：2026-07-29

## 目标与顺序

所有真实对局严格串行，按以下顺序执行；前一阶段完成后才进入下一阶段：

1. 星阵7D：复用 `rank_7d@1s` 已有7个有效结果（4–3），只补到累计10盘。
2. 星阵1星：`b18@1` 先取得4个有效结果；3–4胜时补到累计10盘，0–2胜时停止并记为弱侧。
3. 星阵准5段至准9段：依次运行五个独立对标，使用低一段 HumanSL profile 做自适应二分。

任一阶段出现7002、429、配额错误或其他远端异常时立即停止整个执行，不重试，也不进入后续阶段。

## 冻结配置

| 星阵对手 | API level | HumanSL profile |
|---|---:|---|
| 准5段 | 2000 | `rank_4d` |
| 准6段 | 2200 | `rank_5d` |
| 准7段 | 2400 | `rank_6d` |
| 准8段 | 2600 | `rank_7d` |
| 准9段 | 2900 | `rank_8d` |

准段候选网格固定为 `@1s/@4/@8/@16/@32/@64`：

- `@1s` 必须是 humanv0 `humanPolicy` 单 visit、确定性 argmax；wrapper可运行默认主模型，但不得使用主模型结果选点。
- `@4` 及以上必须显式请求 b18 主网 + humanv0 + canonical PIKL，并逐请求校验模型路径、SHA和有效查询参数。
- `b18@1` 必须显式请求纯 b18、1 visit、无 human profile/PIKL；不得回落到默认 b28。KataGo单visit
  只评估根节点、`moveInfos`为空，因此该档固定从b18原生 `policy` 取确定性argmax，不虚构搜索首选手。

## 调度与判定

候选索引固定为 `0=@1s, 1=@4, 2=@8, 3=@16, 4=@32, 5=@64`。4个有效结果中3–4胜记为
强侧，0–2胜记为弱侧。每个准段初始化虚拟弱边界 `lo=-1`、虚拟强边界 `hi=6`，唯一首点为
`floor((lo+hi)/2)=2`，即 `@8`。筛选点 `i` 为强侧时令 `hi=i`，为弱侧时令 `lo=i`；只要
`hi-lo>1`，唯一下一点为 `floor((lo+hi)/2)`。因此 `@8` 强时下一点必为 `@1s`，`@8` 弱时下一点
必为 `@32`。当 `hi-lo=1` 时边界相邻；`hi=6` 表示直到 `@64` 仍无实际强侧，输出
`no_strong_candidate_in_grid`，不做10盘确认。`hi=0` 表示 `@1s` 是实际强侧和网格下界。

找到最低强侧后补到10个有效结果：

- 4–6胜：直接选为最接近五五开的档位。
- 7–10胜：若存在相邻低档弱侧，将该低档也补到10盘，并在两个10盘结果中选择胜数最接近5的一档；
  距离相同时选择计算量更低的一档。若候选已是 `@1s`，直接选择并标记 `overstrong_at_grid_floor`。
- 0–3胜：从相邻高档开始逐级补到10盘，直到首次出现至少4胜或网格耗尽。

最终只比较该对手所有取得10个有效结果的候选，排序键固定为 `(abs(wins-5), candidate_index)`。首次确认
得到4–6胜即可停止；7–10胜时最多再确认相邻低档；0–3胜时逐级上移并在首次至少4胜后停止。若所有已确认
候选均为0–3胜，则输出 `no_qualified_candidate_in_grid`，同时报告按上述排序得到的 `best_observed`，但不把它
称为已对标档。4盘筛选点不参与最终距离比较，除非随后补满10盘。

`b18@1` 是独立固定点：首4盘0–2胜输出 `weak_screen`；3–4胜则补到10盘，最终0–3胜输出
`weak_at_10`、4–6胜输出 `aligned_at_10`、7–10胜输出 `overstrong_at_10`，不自动测试其他b18档。

每个候选独立交替黑白；不可判定局不进有效分母，并重复原定颜色。筛选局计入同候选的10盘累计，不重复跑。

## 账本与恢复

整次活动使用一个 append-only JSONL 账本，阶段记录固定为 `stage_started/stage_completed`。每盘请求前先写
reservation，结束后写 result；任一异常同时写当前盘 stopped 和活动 `campaign_stopped`。后续阶段启动前必须
验证所有前驱阶段均为 `stage_completed` 且活动没有 stopped，从持久化层保证“停止整个执行”。

旧 stopped 账本永不自动重启。人工恢复必须显式提供旧账本路径和SHA-256并另建新账本；新header记录
`campaign_id/parent_path/parent_sha256`。真实result在首次生成时获得不可变
`origin_result_id=<origin_campaign_id>:<attempt_id>`；任何代的carry必须原样保留该ID，另记直接父账本SHA和行号。
加载完整祖先链时按 `origin_result_id` 拒绝重复，不得用carry所在的新行重新生成ID。只有reservation而无
result/stopped的本地崩溃视为 `unknown_charged_attempt`，不得自动续跑或继承为结果，仍需人工创建新活动。

恢复账本不继承 `stage_completed` 事件，而是从所有去重后的carry/result重放三个确定性状态机：满足终止条件的
前驱阶段自动重建为已完成，首个未满足终止条件的阶段是唯一续跑阶段，后续阶段保持未启动。这样从中途停止恢复
时既不会重跑已完成阶段，也不依赖父账本中的控制事件。7D首个新账本只继承此前7个有效结果；`b18@1` 与准段
实验不混入其他配置或其他对手的历史战绩。

## 错误分类与身份门禁

只有完整完成对局、但最终裁判明确返回 `conclusive=false` 的结果才记为 inconclusive，并重复颜色。Golaxy
7002/429、网络超时、响应缺失或非法、引擎调用失败、身份回显不匹配均记 stopped 并停止活动，不进入有效或
不可判定分母。本地预检失败发生在reservation前，写 `campaign_stopped` 后退出且不访问星阵。

活动header冻结可信 `/health` 返回的默认模型、b18及其所挂载humanv0的路径和SHA。三种模式的唯一身份与
选点断言如下：

| 模式 | 请求与响应身份 | 唯一允许的选点来源 |
|---|---|---|
| `rank_Nd@1s` | 请求省略 `model`；服务端可回显已冻结的默认主模型，但其 `human_model_path/SHA` 必须是humanv0 | 只取返回的 `humanPolicy` argmax，绝不取 `moveInfos` |
| `rank_Nd@4+` | 请求显式 `model=b18`；响应 `_wrapper.selected_model=b18`，b18主模型和humanv0路径/SHA均匹配 | `moveInfos`，且请求含正确profile和完整canonical PIKL |
| `b18@1` | 请求显式 `model=b18`；响应实际b18路径/SHA匹配；服务进程即使挂载humanv0也允许回显 | b18原生 `policy` argmax；请求必须无 `humanSLProfile` 和全部PIKL字段 |

因此“空值”要求作用于请求语义字段，而不是要求服务进程卸载human模型。`b18@1` 响应必须有长度362的合法
`policy` 且 `moveInfos` 为空。每次显式b18分析都必须校验响应中的
实际 `_wrapper` 身份；`@1s` 则校验冻结默认进程挂载的humanv0身份、合法humanPolicy和argmax选择算法。任何
回显缺失、显式b18请求回显为b28、或选点来源漂移都 fail closed，从而防止历史默认路由bug。

## 验证与报告

自动测试覆盖：历史结果只继承一次、至少三代carry去重、颜色续接、固定中点转移、所有端点、4盘强弱判定、
10盘过强/过弱修正、统一候选排序、不可判定不推进有效计数、reservation/result/stopped闭合、活动级停止及拒绝
自动恢复，并分别验证从7D、`b18@1`、准段中途停止后重建唯一续跑阶段。真实运行前检查本地 `/health`，确认
b18和humanv0身份；每阶段报告所有筛选点、有效胜负、不可判定、停止原因、最终候选和账本SHA-256。
