# 棋手等级历史与小时回退：Astra 计划评审 Round 2

**Verdict: Approved**

审核对象：计划提交 `82f010b71` 中的 `2026-10-25-kifu-rank-history-and-hourly-fallback.md`，业务基线仍为 `2e7640d892e311f3fc8ed70d4dc5a32e470d2ddf`。本轮完整重读修订计划，只复核 Round 1 三项阻塞及其直接兼容边界。未实施业务代码、访问生产或运行采集/发布；仅新增本评审报告。

| Round 1 项 | 本轮核对结果 |
| --- | --- |
| R1：明确源 rank 的观察与 current 更新 | 已闭合。所有可靠绑定人物的 source observations 随 v2 固定；prepare 不写 history，原生同事务更新。较新同值是观察而非升段，旧依据不回退；同日冲突/职业降段/系统冲突进入唯一 conflict current，后续 fallback unknown。唯一索引覆盖所有 `is_current` 状态，锁既有 player 行覆盖首次创建。原谱值和既有快照不随 current 更新。 |
| R2：PROD 接收 rank-aware 验证 | 已闭合。send 与 receive 共用版本化校验，保留并检查准确 source/slot/SGF/snapshot/origin/raw/display、五语详情和公开卡片的有限报告；仅计数的旧式报告即使绑定正确 v2 SHA 也拒绝。包内固定事实可重算 SHA，等级来源和职业身份证据分别绑定准确字段；v1 继续原行为。 |
| R3：后来引用、原生撤销与重放 | 已闭合。snapshot 的本地 `rank_fact_id` 使用 RESTRICT FK 与索引，undo 在写入前检查保留 snapshot/receipt 引用及后来 current 变化，冲突整笔拒绝。普通 replay 只核不可变事实及本盘快照，不要求 current/last_checked_at 回到旧状态。显式 correction 后的旧 overlay 重放可拒绝，不能覆盖新 overlay。 |

相邻实施边界也已收口：catalog 的 source authority、receipt、replay 和 undo 依赖统一识别 v1/v2；旧名称 proof/inventory 与既有 receipt 字节语义保持；新增 DATE journal 支持 ISO 往返。三 ID correction 使用共享 publisher 内有界 rank-only 分支，复用锁、journal 和独立 receipt，跳过全库 SGF 暖缓存及姓名续审，不重置已 `prod_synced` 的小时进度。

本轮没有剩余计划级 must-fix，可以按修订计划实施，不需要第三轮计划审核。两张表、现有 canonical 便携身份、零外部 profile 请求、无新增 LLM、原来源与协作预算、receiver 先于 producer 的部署顺序均足以支撑当前需求；无需扩大为资料平台、爬虫或全库审计。调查报告的早期 TTL 建议已明确标记为被本切片取代。

批准范围是实现方案。现有 129 项基线测试通过由负责人报告，本评审未重复运行；它们不代表尚未实现的 rank 行为已经验证。实现后仍执行计划内的聚焦测试、fresh 独立代码审核及已授权真实 TEST → 同包 PROD → replay/API/UI 验收即可。
