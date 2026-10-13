# classification-v2 独立代码审查（2026-10-03）

审查任务：`/root/generic_v2_independent_review_sol`。任务名中的 sol 不作为具体模型子型号认证。对照 [三赛事协议决策](kifu-name-generic-three-event-protocol-decision-astra-2026-10-03.md) 的阶段一，独立检查未提交的 `name_candidates.py`、`test_kifu_name_candidates.py`、`test_kifu_name_batch.py` 改动。

**结论：PASS。未发现具体 P0/P1/P2 问题。** 本结论限于阶段一代码和测试，不构成真实候选包签署、生产导入审批或三组 33 格完成证明。

- 从 Git HEAD 提取旧模板并与当前表逐项比较，v1 完全一致；默认版本和 `strict_fallback` 引用仍保留 v1 含义。v2 恰有协议要求的 11 处精确文字替换，其他文字保持原值。所有十一语的 v2 hash 均不同于 v1，包括文字未变的语言。
- 候选按 `generation_rule_version` 选择模板；批准记录须匹配版本、语言、完整模板 hash 和审核者，未知版本拒绝。现有独立签署、精确 raw/parser 分类以及前像绑定检查仍执行。
- v2 generic owner 必须有固定 owner manifest、完整十一语 member 和候选，且全部为批准的 v2 generic。现有语言有效性和重复校验使数量检查等价于精确语言集合；混用 v1、缺语、缺候选和 pending 均拒绝。新增门槛未追溯限制旧 v1 包。
- 新增真实调用路径测试证明十一语字面值和规则版本入库，严格显示、搜索、覆盖率遵守同一批准状态；撤销批准后不再显示或计为批准。代表性导入/undo 不创建 event/alias，不修改棋谱或目标 `event_id`。

验证命令及结果：

```text
.venv/bin/python -m pytest -q tests/web_ui/test_kifu_name_candidates.py tests/web_ui/test_kifu_name_batch.py::test_classification_v2_raw_bundle_apply_display_search_coverage_and_undo
72 passed in 0.51s

.venv/bin/python -m pytest -q tests/web_ui/test_kifu_name_batch.py::test_dry_run_is_strictly_read_only_and_reports_scope tests/web_ui/test_kifu_name_batch.py::test_apply_is_atomic_audited_idempotent_and_preserves_sgf tests/web_ui/test_kifu_name_batch.py::test_matching_existing_name_preimage_allows_audited_update_and_undo tests/web_ui/test_kifu_name_batch.py::test_v2_new_raw_owner_fixture_dry_run_apply_and_undo
4 passed in 0.55s
```

最初启动两模块完整运行，在 85 项通过、无失败后于 75 秒收敛停止；上述聚焦命令均正常结束，不把中止运行计为全模块通过。数据库行为验证仅使用测试临时 SQLite；未连接生产数据库、操作另一审查者的隔离 clone、修改实现或提交。生产 PostgreSQL 和实际 22 格候选仍须按协议完成库存/前像绑定、独立最终签署及既有 dry-run/apply 核验；Hoensha 阶段二不在此次审查范围。
