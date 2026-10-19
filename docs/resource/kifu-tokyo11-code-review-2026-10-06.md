# Tokyo11 有限独立代码审查

- 日期：2026-10-06
- 审查者：GPT-6 Astra（独立审查）
- 结论：**APPROVE**。本轮未发现阻塞问题。
- 范围：主工作树的 `scripts/kifu_raw_event_title_owners.py`、`tests/web_ui/test_kifu_raw_event_title_owners.py`、`katrain/web/kifu/raw_event_translation.py`、`tests/web_ui/test_kifu_raw_event_title_translation.py` 中 Tokyo11 未提交改动；不重复审查既有 Castle 或其他已批准功能。

## 范围与实现核对

1. 研究包 `/tmp/kifu-event-title-tokyo11-20261006/` 的 manifest、TEST/PROD 捕获、生产白名单与测试 fixture 一致：11 个 exact raw，175 盘。按届次 1–11 的数量分别为 **4、2、7、2、9、8、40、9、20、57、17**；raw 集合 SHA-256 为 `c5303d78e042bbb83c3e6c666abfd74e0d14127e32dbd52b38b4b9fc02685a1d`。两库捕获中的逐项数量、唯一 album IDs 与 scope hashes 均核对通过；名称 preimage 为空，scope 为公开、NULL event FK、无 selection。
2. 新 ordinal 例外仅允许 `1st` 至 `11th` 的固定 `Tokyo Shinbun Cup` 原文，且 parts 必须恰为先 `edition`（包括其末尾单空格）、后 exact `core: Tokyo Shinbun Cup` 两段。既有 lossless 拼接、一处 core、source core 支持及其他 provenance 检查保留；不能借此允许任意英文届次、其他杯名、round 或 Final。
3. owner CLI 只新增固定 `tokyo11` profile 的集合哈希和 11/175 数量。原纯 unlinked 范围检查、签署、完整 before/CAS、锁、ledger 与 undo 路径未改动。
4. 名称写入与持久化名称 eligibility 继续共用 `validate_raw_title_research`；ORM 与 legacy SQL reader 的既有身份冲突和公开/NULL/nonduplicate/selection 过滤未修改。此次没有新增 ORM、schema 或包依赖。

## 最低充分验证

- 独立本地检查：55 条实际 pending research 均通过新纯校验器；同批数据在 HEAD 基线校验器因英文 ordinal 被拒绝。
- 独立负例：parts 顺序反转、将分隔空格移入 core、添加 round、12th、Final 后缀及双空格，六类均被拒绝。
- 实现者报告先运行 RED：11 fail / 5 pass；主流程随后实际运行 `pytest -q tests/web_ui/test_kifu_raw_event_title_translation.py tests/web_ui/test_kifu_raw_event_title_owners.py`，结果 **64 passed（6.73s）**，`git diff --check` clean。本审查未重复运行该套测试。

## 执行边界

旧运行时的 `raw_event_translation.py` 会拒绝这些英文 edition。实际名称展示/精确搜索验收前，需将这个共享校验模块同步到 TEST、PROD 的运行时；两 reader 无需新增逻辑。本结论不表示运行时已更新或 Tokyo 数据已写入。

本轮仅读取本地代码、已保存的研究与范围捕获，并写入本审查文档；没有修改实现、签署数据、连接数据库、SSH 或部署。
