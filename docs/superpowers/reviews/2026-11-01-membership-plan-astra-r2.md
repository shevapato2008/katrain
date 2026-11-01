# Membership plan — Astra Max review, round 2

**Verdict: Approved. Unresolved Critical: 0. Unresolved Important: 0.**

评审对象：[完整修订计划](../plans/2026-11-01-membership-usage-and-payments.md)，共273行、4个Chunk、9个Task。本轮是用户允许的第2轮、最终轮；独立对照[第1轮报告](2026-11-01-membership-plan-astra-r1.md)，复核I1–I6及本次修订引入的约束，不追加第三轮或另派评审。

结论是**计划可交接执行**。第一轮六项Important均已在计划层面闭合，未发现必须先修改计划才能实现的新增Critical或Important。此结论不表示产品代码已经实现、测试已经通过或正式收费已经获准。

## I1–I6闭合核对

| 项目 | 修订位置 | 复核结论 |
| --- | --- | --- |
| I1：旧v1分析入口旁路 | §3.3，第136–138行；Task 7 Files、7.1、7.5a，第230–237行 | 已明确列入`analysis/analyze`、`quick-analyze`、`hint`和`HintGate`，要求拒绝旧raw输入或映射同一固定profile operation；覆盖触发入口与结果出口，并要求三个真实路由的Free拒绝/零引擎调用及领地、hint共用一次授权结果。闭合。 |
| I2：失败全退但前缀仍可读取 | §1.3，第60–61行；Task 4.3a、4.5a，第196、200行 | 交付明确要求completed、0..N完整且校验通过、operation committed；running/failed/refunded不能返回分析前缀，也不能经UserGameAnalysis泄露。允许结果GET先完成同锁序结算，测试涵盖失败退款、不可读、重新授权成功和免费重复读取。闭合。 |
| I3：删除、旧requeue与回收器越过生命周期 | §3.1，第102行；§3.2，第126–127行；Task 4 Files、4.3b、4.5a | 用户锁内拒绝活跃或未结算v2报告的棋谱删除；终态删除保留账务receipt且不退款；旧requeue写前跳过/拒绝v2，旧reaper及通用TTL排除v2 reason/ref。相应文件和三项回归均明确列出。闭合。 |
| I4：Kiosk本地session与共享远端身份 | §3.3，第135、138行；Task 5.3、7.2，第209、233行 | 已选定有界完整SGF快照，明确历史、setup、rules、komi、合法性与大小上限；local session仅为显示关联，云端自行生成fingerprint并执行中央ranked守卫。请求捕获不可变token、账号和generation，并在发送/refresh时检查绑定，不能仅事后丢弃错账号响应。两个针对性契约测试已列入。闭合。 |
| I5：报告实际调用链未保证深度 | §3.2，第128行；Task 4.3a、4.5a，第196、200行 | 要求v2真实`KataGoClient.analyze()`调用按requested_visits严格校验final、请求/位置、模型、root visits与ownership，并校验0..N共N+1个位置。明确用mock HTTP穿过真实client测试“请求2000返回500”不能完成或结算，避免只测helper。闭合。 |
| I6：mock可能沿全局配置连接正式数据库 | Task 6.1a、6.6，第220、226行 | 要求显式数据库URL、禁止用户级/仓库配置回落，并在初始化/schema写入前只读核对预先建立的TEST标记及预期库身份；未知或不符即拒绝，正常应用不能自行标记。覆盖环境标签为test但缺URL、未知库或非TEST库的拒绝测试。闭合。 |

上述核对同时抽查了现有`endpoints/analysis.py`、`endpoints/hint.py`、`endpoints/reports.py`、`core/repository.py`、`core/report_reaper.py`、`cron/jobs/requeue_reports.py`、`cron/clients/katago.py`及`core/config.py`、`core/db.py`。现有缺口与修订稿指定的改造边界相符，不能把计划承诺误写成现有源码已经具备这些保护。

## 本次新增约束核对

- **功能闸一致性**：§0第22行与Task 6.1b要求v2启用时同时具备原收费开关、schema和运行时保护，统一控制旧入口、新usage及UI能力；关闭时保留legacy语义，避免展示限额却免费直通。
- **模拟退款**：Task 6.5a把自动化限制为可完整冲正的全额退款；会员须未使用、未预留且无后续排期依赖，钱包须有足额available。条件不满足转人工，不要求本期建立复杂部分退款或多批余额平台，与单池credits不冲突。
- **阶段A与Free前置**：Task 9.1a使用隔离TEST数据库中的可信测试主体，生产资格仍由云端受信事实决定。正式身份前置、商户签约及GPU容量验收留在正式启用阶段，不阻断阶段A的软件实现和模拟验收。
- **Kiosk展示与价格语义**：Task 2.1a的分屏避免1024×600内堆叠全部内容；29元/100标准次、增强消耗4次、会员满额参考和低频使用说明彼此一致。10/50/200互动权益仍明确标为本期建议，并通过后续可操作预览获得用户确认。

未提出新增必改项。按现有Task 1开始交接执行，遵守Task 2的用户视觉确认门槛即可；后续实现中的代码评审、PG并发验证、正式渠道与容量验收按计划执行，不再作为追加计划评审轮次的理由。

本轮仅阅读计划及相关源码、写入本评审文件；未实现产品代码、运行GPU、访问生产、读取env/私钥、提交或推送。
