# Next20 七条 REVIEW 目标最小修复决策

2026-10-09。**优先选择仅允许精确绑定的无证据 REVIEW 旧行的最小业务修复。** 七份合格 conventional CN 来源及有限字形规则可继续使用；物理 REVIEW 行存在本身不足以要求重新寻找七份官方来源。此为范围决策，代码、最终数据绑定和发布均尚未实施。

已核对 [TW 来源请求](kifu-next20-2026-10-09/tw-source-rule-review.md)、两库来源包、[后续短名单](kifu-pending-tw20-2026-10-09/next20-shortlist-after589.json) 及实际校验/导入/读取代码。PROD 600 肖泽彬、229 叶子萌、595 周雨萱、385 行泓丞、662 朱彦臻、320 桂诗云、391 王琛均有真实 TW 行：`status=review`、`reference_kind=legacy_unverified`，`evidence_id`、`decision_kind`、`generation_rule_version`、`revision` 和 `verified_at` 均为空。当前 NULL 限制来源于初始分支范围，不是证明上述空证据旧行不可被审核替换的独立安全理由。

真正要保留的是同 owner 的合格 CN 完整来源及证据、完整目标前像 CAS、禁止覆盖已合格目标、碰撞检查及独立的完整姓名批准。现有 `name_batch._check_name_preimages()` 在锁定导入事务内比较整个真实名称行的哈希；`_apply_candidate()` 已记录完整 before/after、创建新证据和 revision。因此这些机制可复用，原行的文字相同或不同均不能免除绑定。

最小实现边界可限于 `name_orthographic.py` 和现有聚焦测试：

- 仅对 `verified_chinese_display` 的 CN→TW 非空前像增加明确例外。JP 分支仍用现有 NULL 条件；现有 NULL 候选继续兼容。
- 在已有 `preimage_binding` 内携带完整目标旧行，核对正整数行 ID、相同 owner/语言、`status=review`、`evidence_id=None`，并要求其规范哈希等于已签 `name_preimage_sha256`。其他旧字段也随完整行哈希绑定。该 binding 已由 member 的 `preimage_binding_sha256` 和批次内容批准覆盖。已批准名称保护与来源验证保持原条件。
- `persisted_batch_bindings()` 已复用候选验证，因此同一个旧行证明可同时覆盖离线与持久读取；导入时原有真实整行 CAS 将它落实到当前数据库。七行 `evidence_id=None`，目标证据缺省已包含在名称前像中；本次不扩展到带旧证据的 REVIEW 行，也不声称现有名称 CAS 会自动校验任意证据行正文。

这可避免新增表、写入路径、缓存或日志查询。聚焦验证只需覆盖一例 REVIEW 成功导入/读取及旧行日志保留，以及缺失或伪造旧行、已 verified/带证据目标、绑定后目标漂移的拒绝；复用现有 NULL、来源漂移和碰撞用例。

实际成本仍包括 TEST/PROD 的 web 与 importer 单模块回植及加载：旧读取模块会拒绝非 NULL member，不能只升级 importer。PROD 的 SQL 适配必须保留。相较于现有七份来源已经合格、短名单其他候选仍缺 KO 完整读音或存在排除字，有限代码修复的范围更确定；真实官方中文/稳定 person-ID 或 TW conventional 来源若顺手取得，仍可走已有分支，但不应成为这七人的新增必需研究。

590 的 SQL 完成后再捕获本批最终完整目标前像及 catalog/批准名/别名上下文；不得删除旧行制造 NULL，也不得用先前包替代最终绑定。九个 JP 候选与 KBA446 可继续准备；最终只计实际批准并导入的人数，代码或真实资格未通过的候选仍暂缓。

本轮未捕获绑定、执行 SQL/Git/部署或修改实现。`scripts/render_kifu_name_progress.py` 的未提交改动不是本审查代理所作。

实施前方案第 1 轮复核：**PASS**。[最小实施计划](../superpowers/plans/2026-10-09-kifu-review-name-orthography.md) 符合上述边界。已核实通用 `preimage_binding` 校验允许附加完整前像字段，现有 member 哈希会签住它；现有锁内 CAS 和日志可直接复用，不需要修改 `identity.py` 或 `name_batch.py`。最终代码仍须在持久上下文使用的同一候选校验中验证该完整前像；本 PASS 是方案结论，不是实现或发布完成证明。
