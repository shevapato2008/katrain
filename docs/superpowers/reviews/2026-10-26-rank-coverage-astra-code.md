**Spec 合规：通过。**

本次是新覆盖缺口的独立审核。基线为 `93f2038a0020d43b3090b1a71c8877980580f740`，最终审核 backend 为 `ebfb965a893efb718be2b5657de25f8605ad524f`（包含 `1d15aa661` 的等级反证修复、`8e36e5a0f` 的冲突原因日志及末次 Haifong 增量）。`26df83e19` 合入的独立 icons/UI/docs 未修改本次 backend，不在此扩大复审。先审核原三项改动，再复核本轮发现问题及最小站点增量；不沿用上次三盘的 Approved，也不将工作树代码视为已上线版本。

已读取主仓库及工作树 AGENTS、适用 kifu-album-sync、requesting/receiving-review、计划及指定根因证据。仅写本报告；没有数据库写入、迁移、导入、采集、翻译、模型调用、服务/锁/调度变更、RK 操作或 `data/kifu-album/` 文件系统访问。

1. 官网身份消费者符合范围。[player_ranks.py:161](../../../katrain/web/kifu/player_ranks.py) 删除的是姓名/人员键白名单，保留了 HTTPS、精确支持 host/path/key schema、唯一主体标题或 roster 记录及主体等级字段。日本标题、韩国主体韩文/括号名、中国唯一 `playerNo` 均不以简介中的亲属或任意等级代替主体。末次海峰增量只接受 `www.haifong.org/profession/venue/{32hex}`，并要求页首标题与唯一「職業棋士 … 段 歷史成績」主体同名。同条已审核 `approved_name` 只是额外 exact 候选；没有姓名硬码、简繁、括号、相似名推断或新网络请求。
2. 权威没有移到自报 proof。[player_ranks.py:476](../../../katrain/web/kifu/player_ranks.py) 仍要求 verified 姓名与 independently approved evidence 的 owner、语言、revision、候选名和规则一致，且 research/candidate owner 与 display 均相符。`_validate_identity` 重做主体解析；[verify_rank_fact_for_player:619](../../../katrain/web/kifu/player_ranks.py) 还要求完整 proof 属于该本地 owner 的批准证据，并校验等级原谱、side FK、原始等级/姓名、来源和摘要。因此知道合法 URL key、修改 approved alias 并重新计算摘要不能自行获得权威。官网等级没有被写成新的 rank fact；来源日期仍属于原谱，`valid_from` 保持 null。
3. [correction scope:85](../../../scripts/kifu_rank_correction.py) 为不可变副本，限定 1–20 个唯一数字 source ID（最多 64 字符）、160 字符 publication key、精确小写 SHA-256 和允许字段；旧默认三盘兼容且旧 key 不得配异 pins。同包多个成员只读一份原包。build、freeze、已有文件 reuse、apply 全程使用同一 scope，固定原 SGF/原 manifest/成员；不携带可替代当地绑定的 album ID。
4. 原包与发布边界保留。[本地 preimage:208](../../../scripts/kifu_rank_correction.py) 检查已 applied 原 native 包、logical game、source/receipt、当地公开 album、原 SGF/metadata、同侧 canonical FK 和原 snapshot/fact；[native correction:1578](../../../katrain/kifu_ingest/catalog.py) 继续在原写事务内执行当地绑定、snapshot CAS、原事实核验和同 key 异 manifest 拒绝，精确 replay 核对已有绑定。新增 scope 没有更改 native/schema/manifest 合约，也没有重置旧 `prod_synced` 或让历史谱动态读取 today's current。
5. [日志:290](../../../katrain/kifu_ingest/orchestration.py) 只扩展原 INFO。`lookup_reasons` 按本次 lookup 的 owner 计数；`unresolved_slots` 以 source ID/side/固定 reason 关联，最多 200 项。未知自由文本 reason 被固定占位替换。cached unknown 始终写 `frozen_unknown`，即使同 owner 在新谱中被查询，也不伪称历史 unknown 是本次 lookup 结论。

**代码质量与数据完整性结论：Approved，无剩余 must-fix。**

审核中确认一个真实 must-fix，已由 `1d15aa661` 关闭：候选页 `91633894` 白方李小溪05 / owner 182 的最新明确库内原谱是 `41407549`，2020-07-28 一段（SGF SHA `f71d3875d4c0201a43356a7ca8be5e638f846549aedd9d31d1b5f2a5e8a1481e`）；同 owner 已审核的韩国 mobile 主体 `PRPL_CODE=20002111` 却明确为 `6단`，正文含 2026.08.19 升六段。原实现会给本次新 fallback 返回 qualified 1p；“库内最新”不能消除这份已知反证。

最终 `_library_rank_result` 只在 lookup 的已有 current-row 与 raw-candidate 两条返回路径拦截：professional fact 低于其同一 proof 中可明确解析的日本/韩国/海峰主体等级时，返回 `conflict / official_grade_above_library_grade`。它不产生六段替代事实、不改原谱，不写 history 状态，不推断中国 roster 的 `Z` 代码；原谱等级更高或相同仍可通过。历史 `build_source_rank_fact`、`validate_rank_fact`、`_row_fact`、source-first 与 native replay 的事实校验不调用这条 fallback 限制。对应固定 reason 已加入原日志白名单。

本次独立验证集中在增量风险，没有重跑全套 146/392，也没有运行需写数据库的测试。为遵守只读约束，动态检查从实际源码 AST 取出函数/日志代码块在内存执行；原谱反例为内存合成字符串，未读取 SGF 文件。

| 独立检查 | 结果与证据边界 |
| --- | --- |
| 基线/新代码旧六人兼容 | 读取既有六份真实 captures，基线与新实现生成的完整 proof 和完整 fact 逐项相同；新实现成功重验基线 fact。不是只比较 rank 数值。 |
| 既有当前页 captures | 48 份只读 capture 中，original-only 解析接受 38 份、覆盖 34 owners；於之莹、芮乃伟、党毅飞、辜梓豪均在内。仅据捕获文本检查解析，不声称重新访问官网。 |
| alias 与 native 证据成员 | 真实李05 capture 只接受 exact approved alias；重算摘要的错误 owner/subject 拒绝。另以实际 `_approved_context` 和 `verify_rank_fact_for_player`、只返回 SELECT 结果的内存适配器验证：伪造同条 approved alias 即使通过结构/自哈希，仍在批准 proof membership 被拒；没有执行真实数据库事务。 |
| scope 与冻结 | 12 个重复、数量/长度、额外字段、hash、旧 key、成员/key/SGF/manifest 漂移反例均拒绝。原可变输入及 `.pins` 返回值修改不改变冻结 scope；同一原包选择两个成员通过，另一侧 rank unknown 不阻塞已知侧，实际 manifest 验证通过。 |
| 最终等级反证 guard | 使用真实韩国/日本/中国 captures 与合成原谱验证 6 例：低值冲突、相等通过、较高原值通过、中国代码不推断；fact 内容和摘要未变，`valid_from` 未变。核对 guard 只由 lookup 两出口调用。 |
| 历史/source-first | 真实六段 proof 下的历史一段 fact 仍经 `_row_fact` 完整还原；source-first 一段 snapshot/observation 保留，未被换成六段或丢弃。 |
| 最终日志 | 执行实际日志块验证 cached/new 同 owner 区分、固定冲突原因、任意原因文本不外泄以及 200 项硬上限。 |
| 海峰末次增量 | 读取 `remaining-official-captures.json` 中 owner 197 的真实批准 capture，主体楊子萱/六段接受；错误标题、错误主体、双主体 3 个反例拒绝。同 proof 下原谱五段仅在新 fallback 被否决，七段通过，历史事实验证及 `valid_from=null` 保持。 |
| 差异检查 | `git diff --check 93f2038a..ebfb965a8` 通过；native publisher 和 schema 未在本轮 diff 中修改。 |

原始调查的有限页面为 20 盘/40 侧、已显示 fallback 六侧；三份 10-24 原谱正常 published/prod_synced 且无 snapshot，不是原导入异常。后续只读候选页已因 `91738010` 加入而变化，不能把初始分页数字与后续页混算。李05 的冲突是本轮真实候选证据所揭示，并已用于收紧新 fallback；本报告没有把候选值算作已纠正结果。

另确认一个应披露的版本边界，不列为 must-fix：`91737274` 原 v2 的 unknown snapshot 若经授权 rank-only CAS 纠正，旧 v2 包的 `_check_rank_replay` 会因当前 snapshot 已变而拒绝重发。原 artifact/receipt/raw/IDs/StateStore 仍可保留，但旧 snapshot 已不能代表当前 API；旧包 fail-closed 可防止覆盖新纠正。在原 source 已 `prod_synced`、无正常待重试发布路径的前提下，这符合显式纠正语义，无需放松 native 校验或退回只纠正 v1。实际验收应验证新 correction 同包可幂等，并明确记录「旧 v2 包被显式纠正替代，旧包重发拒绝」；不能宣称所有历史 package 此后仍可按原 snapshot 重放。若真实正常周期仍会重发该旧包，应作为运行阻塞重新评估。

本批准限于上述代码及数据权威边界。仍须以最终只读候选清单冻结有限 scope，完成同一 frozen manifest 的 TEST → 五语言/公开 API → PROD → 精确 replay，再由独立实际数据/API 覆盖审核确认 ID、raw/原包/进度保护、四位显示值及剩余 unknown/conflict 原因。当前报告没有验证这些后续发布动作，也没有证明全历史、整个七天窗口或 RK 当前画面已经修复。
