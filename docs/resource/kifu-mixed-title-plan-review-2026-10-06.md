# 有限中文混合标题设计／计划独立审核

审核日期：2026-10-06。第 1 轮，由用户授权的独立 Astra 决策代理执行。

**设计批准：APPROVED。计划批准：APPROVED。必须修改项：无。** 可按该设计进入实施，无需再向用户确认或开展第 2 轮设计审核。g / DK / DL 按原计划继续，不被本扩展阻塞。

已只读核对：

- `docs/superpowers/specs/2026-10-06-mixed-chinese-sgf-title-design.md`
- `docs/superpowers/plans/2026-10-06-mixed-chinese-sgf-title-translation.md`
- 既有 `raw_event_translation.py` 的字符／共同 ordinal、research、owner marker 校验，以及 `kifu_raw_event_title_owners.py` 的 manifest／scope 入口。

批准理由：新 profile 的范围与独立决策一致；只补中文内 ASCII 品牌和实际 edition 形态，保留原 parts、单 core、唯一 kind、有限 manifest 和完整成员；明确隔离旧 profile 与未知／跨 profile marker。设计已覆盖来源、身份、碰撞、审批分离、事务、重放／撤销及 TEST→PROD 实际验收，没有把候选 2,979 局当作实际完成，也未引入 parser 重写、新 schema 或无关设施。

实施时按已有条款落实以下三个检查点即可，不增加流程：

1. 共同 ordinal 检查仅在 `source_basis == sgf_literal_v1` 且显式新 profile 时放行新增 edition；不要修改共享 `_ORDINAL` 让旧入口同时扩展。round 保持旧规则。
2. Owner 脚本当前有多处 `profile == SGF_CHINESE_PROFILE` 分支；新 profile 必须完整经过 prepare、inspect、apply 的 manifest／raw_count／scope／未命名 owner／marker 检查，以及所有模式的必需 manifest 门禁。复用既有拒绝测试时，让至少一个代表性完整范围拒绝用例实际跑新 profile，避免仅证明旧分支仍安全。
3. 两个 reader 继续使用批准后的精确 profile marker 与 parts hash。发布和入库沿用现有小范围 gate；遇到疑似损坏原文或复杂分段，跳过候选，不扩张本实现。

本次批准的是设计及执行计划；实际补丁仍按计划做一次独立代码审查，真实来源／候选仍逐批签审后入库。本次只写此审核文档，未修改设计、计划、代码或数据库。
