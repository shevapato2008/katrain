# SGF Chinese bulk 独立代码审查

日期：2026-10-06；审查者：GPT-6 Astra。

审查对象：主工作树相对 `bb6cc46637ef1a6dfb943d107a3584c30a16347c` 的 `raw_event_translation.py`、`name_candidates.py`、owner CLI 及两个聚焦测试文件。按已批准的批量决策检查，没有扩大到无关功能。

## 第一轮结论：REQUEST CHANGES

**一个阻塞项：已应用 plan 的重放可以接受另一份 manifest。**

- 位置：`scripts/kifu_raw_event_title_owners.py:284`，具体为 286–299 的 manifest 自检及 `already_applied` 快速分支。
- 原因：新分支核对了 `canonical_sha256(manifest) == expected_manifest_sha256`，但 `plan.research_manifest_sha256 == expected_manifest_sha256` 只在后面的 `inspect_plan` 检查。已经应用的相同 plan 会提前返回，跳过这项关联检查。
- 独立复现：使用现有 `chinese_manifest_fixture` 在自动清理的临时 SQLite 中，先正常 apply 一项“全运会”；给 manifest 增加 `decision_note`，传入其新的正确 expected manifest SHA，同时保留原 plan 及正确 plan SHA。结果为 `manifest_hash_mismatch=true`、`status=already_applied`、`change_count=0`。未产生额外数据写入，但该成功响应接受了不属于已签 plan 的 frozen artifact，违反本次对 prepare/dry-run/apply 使用同一 manifest 的要求。
- 最小修复：在进入 replay 快速分支前，核对 plan 中的 manifest SHA 与本次 expected manifest SHA 相等。增加一个聚焦重放用例：原 manifest 可返回 already_applied；不同 manifest 即使传入其正确 SHA，也必须拒绝。无需扩大审查或测试范围。

## 其余检查

- manifest 1–150 上限、唯一 raw 集合及 canonical SHA、完整成员/总量、实际 owner 全部 preimage、parts marker 的计算和 inspect 重算符合决策。
- candidate 同时核对真实 parser kind/text、批准 metadata 的 parts hash、完整 scope hash 与 occurrence IDs；持久化 reader 使用同一 metadata marker，未给 legacy reader 增加 ORM/parsed_data 依赖。
- 新 marker 缺失或错误不回退为任意旧 owner；national15 的无 marker 路径仍限定原固定 raw 和原 parts，原外部来源分支保持要求。
- Chinese/主语言/现有 raw_event、source/GN refs、审核时序、player/entity、FK、碰撞、CAS、锁与 undo 边界未发现其他阻塞；两个不同 manifest 的 apply/undo 已有聚焦用例。
- 独立读取冻结的真实 150 raw/parts，全部通过新中文语法检查。实施者报告 **108 focused passed（含 22 个新增用例）**；本审查未重复整套测试，只为上述具体风险执行了一个临时本地复现。

仅写本审查文档；没有修改实现、提交、访问生产数据库、SSH、签署或部署。修复后仅需复核上述重放关联。

## 第二轮最终结论：APPROVE

2026-10-06：已独立复核最小修复及对应测试 diff，第一轮唯一阻塞项已关闭。

- `apply_plan` 的 `sgf_chinese` 分支现在先核对 manifest 自身 canonical SHA，再核对 `plan.research_manifest_sha256 == expected_manifest_sha256`；两项均位于 `_locked_write`、历史 batch 查询和 `already_applied` 分支之前。原 plan 的重放因此不能接受另一份 manifest，即使后者传入自身正确 SHA。
- 原两个参数化用例明确验证同 manifest 重放返回 `already_applied` / `change_count=0`，以及仅增加 `decision_note` 的另一 manifest 携其正确 SHA 仍抛出 `BatchError`。随后原有 undo 路径继续执行。
- 根执行者报告该回归先 **RED：2 failed（DID NOT RAISE）**，修复后 **GREEN：2 passed、19 deselected，0.31s**。本轮通过源码与断言复核确认修复针对上述实际反例，没有重复已通过的 108 项聚焦测试。

批准本次代码变更；无剩余阻塞。本结论不代表 150 标题的数据包已签署、入库或运行时已部署，后续仍按既有冻结、独立审批、TEST → PROD 和验收流程执行。
