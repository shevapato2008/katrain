# league20 独立代码审查 — 2026-10-06

**结论：APPROVE。无代码阻塞项。**

范围：main 工作树相对 `56526b59` 的 `scripts/kifu_raw_event_title_owners.py`、`tests/web_ui/test_kifu_raw_event_title_owners.py`，对应计划 Continuation 3。生产差异仅新增固定 `league20` profile 两行。

## 核对结果

- 独立比较 producer 包 `raw-members.json`、`research-manifest.json`、TEST/PROD `owner-capture.json` 与测试 fixture：20 个 exact raw 及每条局数完全一致，总计 **214 局**。
- 独立重算 sorted raw-set canonical SHA-256，等于生产常量 **`a56431132255fce798e22d0b8a0869f677f9ec8784fad6bba0a72babe615de9a`**；未纳入该集合之外的 raw。
- 两库实际捕获的全部 214 album 均为对应 exact raw、`event_id IS NULL`、非重复、公开且无 selection，适用原纯无关联路径。所有标题使用已有 year/core/round 结构，此 diff 没有修改语法或 reader。
- first24 默认值及既有 profiles 未变。固定 raw/count 校验、完整 owner 前像、album scope、inventory/catalog、独立签署、外部哈希、事务锁、ledger 与 undo 都复用原实现；没有新的宽松分支、schema、名称、FK 或 album 写操作。
- 新测试只增加实际 20 raw/count fixture 并复用原参数化流程，包含成功、错误 profile/raw/owner 数量、scope CAS、apply 与 undo。实现者报告 RED unknown profile → GREEN，11 个聚焦测试通过；本次未重复运行测试套件。

`git diff --check` 对这两个文件通过。独立纯读取 Python 检查确认两库来源集合、每项数量、总量、可见性/关联/selection 条件及 profile SHA，均通过。

## 非阻塞的哈希说明

任务描述中的 `d081d3c4550d9e1d522102b3f9a3b1314e8513a32f399ecfaaab2640f6828ce1` 实际是当前 `research-manifest.json` **文件字节 SHA-256**。该 JSON 当前的 **canonical SHA-256** 为 `a98420744ba5add3e22aa8ccb97c12f913e2382193a25292ef8989b1efa9229c`。执行 owner 流程时应使用最终装配 manifest 的 canonical 值作为 `expected_manifest_sha256`；既有门禁会拒绝错误值。此差别已通知 root，不影响本次 profile 代码批准。

本轮未修改代码、连接数据库、SSH 或部署；仅写本审查报告。来源语种与具体译名的独立内容审核仍由既定数据流程完成，不由这次两行代码审查代替。
