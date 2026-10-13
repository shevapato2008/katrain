# 隐藏 250 条未解决赛事尾项：独立审查

日期：2026-10-05。结论：通过，未发现需要修正的阻塞问题。

范围：`scripts/tag_kifu_unresolved_event_tail.py`、`KifuAlbum.list_hidden_reason`、当前及 legacy 棋谱列表接口、本次列表测试变更。

- 独立从 PROD/TEST inventory、展示 asset 和 residual 重算：两环境均为 260 条候选，其中精确隐藏 250 条，保护 10 条 SGF 覆盖记录。250 条对应 238 个未分类 raw；各 raw 频次、ID、原 event/date 及保护 SGF 哈希均匹配计划，三份来源文件哈希一致。
- PROD 计划 SHA256：`788712bc1021d8e420e125cca5a8e5adaf34f651adb88bbe92eea16bcb419a20`。
- TEST 计划 SHA256：`f7a1c30add3136bd7fbe9b1ba2d38c9fcc7452b96f2f5d4b259ad844c914b901`。
- 写入事务核对数据库、锁定棋谱表、检查完整 260 条范围及 250 条前值、检查保护记录 SGF、要求更新恰好 250 行。实际 UPDATE 只写隐藏原因；SGF、赛事关联及源记录保留。
- 两个列表接口均对结果及总数加相同过滤，搜索条件无法绕过；详情接口继续按 ID 返回。legacy 使用列名 SQL 条件，兼容运行时旧 ORM；部署前须按既定顺序先执行加列/标记事务。
- `python -m pytest -q tests/web_ui/test_kifu_list.py`：14 passed、1 skipped。跳过项为原有 PostgreSQL 排序索引性能验证；新增测试覆盖隐藏列表、共享搜索、专属搜索和 SGF 详情保留。

本审查未连接或写入持久数据库；实际 PostgreSQL 事务干跑、提交及部署后的接口核验仍由执行流程完成。未修改受审查代码。
