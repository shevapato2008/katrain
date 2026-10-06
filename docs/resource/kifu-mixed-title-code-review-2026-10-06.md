# 有限中文混合标题独立代码审核

日期：2026-10-06。第 1 轮。角色：`requesting-code-review` 独立 reviewer；依据用户授权的设计与计划。

**结论：APPROVE。Critical / Important / must-fix：无。可提交此四文件补丁并进入计划中的有限 TEST→PROD 部署与数据验收，无需第二轮代码审核。**

审核基线为 `1dc31be3d2409a0fcb0fecb970e53e61144bf3a4`，目标为当前工作区以下四文件的 diff，diff SHA256 为 `3c46e80e8aa5d63a086714aba840793bc3bf346c63d44efa5a228e9f6b8e32ae`：

- `katrain/web/kifu/raw_event_translation.py`
- `scripts/kifu_raw_event_title_owners.py`
- `tests/web_ui/test_kifu_raw_event_title_translation.py`
- `tests/web_ui/test_kifu_raw_event_title_owners.py`

核对结果：

1. **旧规则保持，扩展显式选择。** 原 `_CHINESE_LITERAL` 与 `_ORDINAL` 未修改。新字符集合仅增加 ASCII 字母；新增 edition 规则仅由 SGF literal 且明确 `sgf_chinese_mixed` 的入口选择。round 与 year 仍走原规则，纯 Latin、多个 core、重复 kind、非无损 parts 均不能通过；不修改 parser 或存量 parsed_data。
2. **Owner 全路径接线完整。** 新 profile 在 limits、prepare、inspect、apply 和 CLI 的必需 manifest 分支均纳入同一完整检查。新 manifest 显式绑定 profile，仍限制最多 150 个唯一 raw，核对 raw 集合／数量／总数、完整 owner preimage、member scope、catalog/inventory hash 和未命名状态。原 `_scope_rows` 的 NULL／非隐藏／非重复／无 selection 条件继续适用。`_sgf_chinese_marker` 在 prepare 与 inspect 均从真实 owner 的保存 parts 重新验证并计算 hash。
3. **Research 与批准 marker 精确绑定。** `sgf_literal_owner_matches` 根据受支持的精确 profile 构造完整 marker 并比较，拒绝缺失、未知或跨 profile marker；候选阶段继续以 `check_parser=True` 比较保存的原 parts。SGF first-GN、EV、source、完整范围与证据时间检查没有绕过。legacy reader 根据已签署 marker／hash 读取、无需另载 parsed_data，是本次沿用的已批准契约。
4. **写入边界未扩大。** owner 的修改字段仍仅为 review status／metadata，完整前镜像与 afterimage 检查、锁内事务、账本、重放及撤销路径保持。补丁未改名字碰撞策略，也未增加 identity、alias、FK、rank、SGF 或 source 写入。名称研究、独立审核、两 reader 的现有校验调用继续复用。
5. **测试与规模相称。** 新测试使用实际 KB／期／无“第”形态；研究、owner 和 names/readers 均走真实既有逻辑。新 profile 直接覆盖 scope 改动、已有名称、manifest 改动、错误 marker 与跨 profile manifest 拒绝；旧 profile、national15、来源／碰撞、重放与撤销由指定两文件内的现有用例继续验证。没有需要新增的阻塞测试层。

独立验证：

```text
PYTHONPATH=. .venv/bin/python -m pytest tests/web_ui/test_kifu_raw_event_title_translation.py tests/web_ui/test_kifu_raw_event_title_owners.py -q
127 passed in 10.31s
exit 0
```

四文件 `git diff --check` 通过。另读取实施者 `/tmp/kifu-mixed-title-code-tdd-20261006/red-green-receipt.json`，其 RED/GREEN 记录与这次独立 GREEN 一致；未再次开展无关全量测试、模糊测试或新的审计脚本。

本批准仅针对上述代码 diff。当前线上旧 runtime 未因此自动更新；真实有限来源、五语候选、TEST→PROD 发布／入库和覆盖统计仍由 root 按计划执行。此次仅写本文并运行授权的本地聚焦测试，未修改实现、部署或写入 TEST／PROD 数据库；g / DK / DL 的旧 profile 入库可继续。
