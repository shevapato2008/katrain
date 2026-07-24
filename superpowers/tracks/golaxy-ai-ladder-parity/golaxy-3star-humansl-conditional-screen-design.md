# 星阵 3 星与 HumanSL `rank_9d` 条件筛选实验设计

日期：2026-07-25

状态：用户已确认

## 目标

寻找 HumanSL `rank_9d` 搜索配置与星阵最强公开档“星阵3星”的实测关系。主序列固定为
`rank_9d@8`、`@16`、`@32`、`@64`，每档取得5个有效结果。若最先测试的 `@8` 已经5–0，
则不再消耗额度测试显然更强的主序列高档，转而向 `@4`、必要时 `@2` 搜索较低边界。

本实验只报告固定小样本结果，不据此估计 Elo，也不自动修改产品阶梯。

## 固定配置

- 我方：`rank_9d@N`，b18 主模型、humanv0、canonical PIKL HumanSL 搜索配方；
  `N ∈ {2, 4, 8, 16, 32, 64}`。
- 对手：星阵“星阵3星/星猛虎”，真实 API wire level `3300`，当前分支 core rung 36；不得以展示 Elo
  或旧 b28“超职业”配置替代。
- 棋盘：19路，中国规则，贴7.5目，无让子。
- 每档目标：恰好5个有效结果。
- 每档 HumanSL 执黑/执白顺序：B/W/B/W/B；不可判定局不进入分母，并以原颜色补局。
  本文“5–0”均指 HumanSL 取得5胜0负。

## 条件调度

调度只依据 append-only 账本内已经完成的有效结果：

1. 首先完成 `rank_9d@8` 的5个有效结果。
2. 若 `@8` 为5–0，主序列 `@16/@32/@64` 在汇总中推导为条件跳过，不向账本写入虚拟
   skip 记录；接着完成 `@4` 的5个有效结果。
3. 若 `@4` 也是5–0，再完成 `@2` 的5个有效结果；否则停止。
4. 若 `@8` 不是5–0，则依次完成 `@16`、`@32`、`@64` 各5个有效结果，然后停止；不进入
   向下分支。

不得逐盘提前结束某一已启动档位，也不得根据中途比分改变档位顺序。程序重启后必须从账本唯一重建
同一个下一动作。

## 额度、账本与失败策略

- preset 名固定为 `golaxy3star-rank9d-conditional-20260725`，协议名固定为
  `golaxy-3star-humansl-conditional-screen-v1`，首个 quota ID 固定为
  `golaxy3star-rank9d-conditional-20260725-a`，结果目录固定为
  `superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/golaxy_3star_rank_9d_conditional_20260725/`。
  这些证据不与星阵9段、7段、8段或既有 b28 结果合并。
- 最大有效局数为20（主序列路径），向下路径最多15局。最多预留32次可能计费尝试，为不可判定局
  留出替补空间；每次远端调用前先持久化 reservation。
- 每个棋手配置的有效 query、KataGo capability、模型 identity 和配置 fingerprint 必须在首局前
  通过本地 preflight，并在续跑时保持一致。
- 协议/preset 名和星阵 rung 36 / wire level 3300 必须进入 fingerprint。远端停止码 smoke 证据必须
  由本协议专用的星阵3星 `3300` probe 生成并验证，不得复用只证明 level 3000 的旧 smoke report。
- token/鉴权错误、7002、429、传输中断、远端协议异常、账本冲突或 identity 漂移立即停止，零自动重试。
- reservation 一旦持久化就计入32次上限。若进程未能为它追加 result，该 reservation 保持未配对；
  自动运行和自动续跑必须拒绝继续，不能静默补赛或再预留同一局。本协议不提供自动 abandon/retry；
  后续处置需要单独的人工审计和用户批准的新协议决定。
- 只连接本机 KataGo HTTP `http://127.0.0.1:8000`；真实星阵请求继续使用现有 fail-closed 客户端。

## 实现边界

在现有 fixed-screen runner 中增加一个不可变的星阵3星条件 preset。调度规则应保持为纯函数。新协议
可以继续使用 header/reservation/result 三类 append-only 记录，但打开账本或追加记录前必须严格重放：

- 每条记录只允许精确 schema，attempt ID 从1连续递增；每个 reservation 最多且恰按顺序配对一个
  result，任何未配对 reservation 都阻止继续运行；
- player 必须属于 preset，quota ID、source revision、protocol/preset、fingerprint 必须与 header 和
  对应 reservation 一致；
- 每个 reservation 的 player/color 必须等于此前合法历史唯一推导出的下一动作；不可判定结果保持
  同档同色，有效结果推进 B/W/B/W/B；每档不得超过5个有效结果；
- 分支只能在 `@8` 的第5个有效结果后决定；terminal 分支完成后禁止任何额外记录。

旧的星阵9段 `@5/@6`、星阵8段 `@4`、星阵7段 `@4` preset 和历史 ledger schema 必须保持兼容；
严格重放要求至少强制用于本次新协议，不能把历史宽松记录未经迁移直接解释为新协议证据。

## 验证与报告

- 单元测试覆盖星阵3星 rung 36 / wire level 3300 绑定、协议 fingerprint、3300 smoke evidence、两条
  条件路径、五局颜色、不可判定原色补局、合法重启恢复、未配对 reservation 阻断、恶意/损坏历史
  拒绝、32次额度上限、exact output path 和旧 preset 回归。
- live 前先运行相关 pytest、源修订 attestation 和 local-only preflight；preflight 不读取星阵 token、
  不创建 quota、也不消耗星阵额度。
- live 后核对每个 reservation/result、有效局数、颜色、fingerprint 和停止分支，计算 ledger SHA-256。
- 将预声明、逐档战绩、无结果数、实际分支和证据路径更新到 `EXPERIMENTS.md`；清楚标注5局只是
  小样本筛选。
