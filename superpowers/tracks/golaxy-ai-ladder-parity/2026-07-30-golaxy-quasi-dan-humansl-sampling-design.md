# 星阵准5D–准9D HumanSL `@1` 加权采样对标设计

## 目标

验证同段位 HumanSL 加权采样模型是否比此前低一段 `@1s` argmax 更接近星阵准段位：

| 星阵对手 | 本地模型 |
|---|---|
| 准5D | `rank_5d@1` |
| 准6D | `rank_6d@1` |
| 准7D | `rank_7d@1` |
| 准8D | `rank_8d@1` |
| 准9D | `rank_9d@1` |

星阵1星的产品对标结论固定为 `b18@1`，本轮不重复该实验。

## 实验协议

- 每组有10个有效结果槽位，HumanSL 首槽执黑，随后按槽位黑白交替，最终5黑5白。一次不可判定 attempt
  只重跑当前槽位，因此实际 attempt 序列可能连续同色。
- `@1` 的本地请求固定对应 `rank_nd` HumanSL profile、`maxVisits=1` 和该 profile 的
  `humanPolicy`。362个权重必须均为有限数；负值及当前局面非法点权重忽略，pass作为合法候选保留，正权重
  总和必须大于零，然后按剩余正权重归一化采样。不得使用 argmax、`moveInfos`、普通 `policy`、搜索结果或
  失败回退。
- 判定协议固定为 `golaxy-sampling-adjudication-v1` 并写入 header：19路、中国规则、贴7.5目、400手上限；
  b28裁判首次200 visits。除已验证的星阵认输外，初判胜负再以800 visits复核，要求 settled 且两次黑方
  `scoreLead` 差值严格小于1.0目。满足这些条件的我方胜或负才是有效结果；move cap本身仍可经上述两次
  稳定判定成为有效结果，未验证终局、和棋或复核不稳定记为不可判定。HTTP/API错误、超时、断线或无效
  响应属于停止错误，不属于不可判定样本。
- 不可判定局不进入10盘分母，并以相同颜色补跑。
- 五组按准5D到准9D顺序执行；任何时刻只允许一盘对局，盘间冷却5秒。
- 关闭HTTP/SDK隐式重试。遇到任意HTTP非成功状态、API错误码（包括7002）、429、超时、断线、限流、
  配额/软封禁、缺失或无效响应时，先用当前 reservation 写 stopped，再立即退出；即使 stopped 落盘失败也
  必须退出，不再发送远端请求或启动后续组。
- 5秒冷却是从前一个 attempt 终止到下一条 reservation/远端请求的最短间隔，不可判定同色补跑也适用；
  远端错误停止时不等待。测试通过可注入时钟验证。

## 账本与恢复

建立不可覆盖、仅追加的新版本 child ledger，父路径固定为
`calibration/results/golaxy_alignment_campaign_20260730/campaign_v2.jsonl`，父 SHA-256 固定为
`4eff5434cd864215a35171d635e4268d06f31f45ca6be27e82e4e0a1105f64d5`。首次远端请求前必须验证父 header、
摘要及 `completed` 状态。新阶段使用独立名称，
不改变或重新解释 v1/v2 的 `@1s` 二分结果。每次请求先写 reservation，再写 result 或 stopped；恢复时只允许
从闭合账本计算唯一下一盘。

账本 header 固定协议版本、父账本路径与摘要、候选映射、样本量、颜色策略、冷却时间、随机种子和引擎身份。
一条 reservation 对应一个完整对局 attempt。写入均需追加并同步到磁盘后才能继续；独占锁保证第二实例拒绝
启动。启动或恢复时验证唯一 header、连续序号、JSONL完整性、每条 reservation 至多闭合一次、origin ID
唯一以及阶段/槽位/颜色合法性。发现损坏、重复、截断或未闭合 reservation 时 fail closed，不自动重发。

加权采样使用 SHA-256 counter PRNG；每个本地回合由 header seed、reservation ID和手数派生均匀随机值，
映射到候选累计权重区间。每步记录局面哈希、`humanPolicy` 摘要、正权重总和、随机值、命中区间和最终落子；
不保存完整362维策略。这样可审计实际选点且控制账本体积，不得因恢复而重新抽样已完成对局。

采样编码固定为 `golaxy-humansl-weighted-v1`：候选按 KataGo policy index `0..361` 升序，`0..360` 映射为
`x=i%19, y=18-floor(i/19)`，361为pass；过滤非法点后保持原顺序。权重使用解析后的IEEE-754 binary64，
按候选顺序用 `math.fsum` 求累计值。PRNG输入为ASCII域分隔串 `golaxy-humansl-weighted-v1\0`、header中的
无符号64位大端seed、UTF-8 reservation ID的无符号16位大端长度及字节、无符号32位大端手数；取SHA-256
前8字节为无符号大端整数 `r`，令 `u=r/2^64`、目标值 `u*总权重`，选择首个累计上界严格大于目标值的
候选。策略摘要为362个binary64大端字节依次拼接后的SHA-256；局面摘要使用规范SGF历史JSON
（UTF-8、无空格分隔符）SHA-256。

策略维度错误、非有限权重、正权重总和为零、非法profile/身份、引擎异常或其他本地协议错误，均须关联当前
reservation写 stopped 并立即停止；若 stopped 写入失败仍退出，开放 reservation 保持 fail closed。

## 实现与验证

在现有串行 campaign runner 上增加独立的 HumanSL sampling 协议，不修改已完成协议的调度语义。测试覆盖：

- 五组精确映射及顺序；
- `humanPolicy` 加权采样而非 argmax；
- 每组10个有效结果与5黑5白；
- 不可判定同色补样；
- 任一远端错误立即停止；
- 父 SHA、父 completed 状态、引擎身份、reservation闭合和 origin ID 唯一性校验；
- PRNG golden case、非法策略停止、开放 reservation fail-closed、独占锁和可注入冷却时钟。

实跑完成后，将每组胜负、不可判定次数、最终状态、账本路径和 SHA-256 追加到 `EXPERIMENTS.md`。
