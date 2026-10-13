# 棋手权威页面字段：独立审核

2026-10-05；审核者 `/root/hide250_review_astra`（配置模型 `gpt-6-astra`），实现者为另一 agent。

**结论：通过，无阻塞问题。** 范围仅 `KifuPlayer.authoritative_pages`、`player_pages.py`、同步 CLI、显式迁移、`name_batch._catalog_sha` 的棋手历史列选择、对应测试与计划 Chunk 3；未重复审核赛事直译功能。

- 采集只读当前 verified、独立 approved 且 owner/语言/revision/候选/rule 一致的姓名证据，再核对持久化候选与研究、registry 哈希绑定。正面来源、原名与同人佐证保留来源角色；检索、负面和无绑定旧证据被跳过。
- 合并保留已有手工字段，仅追加 URL 与证据 ID；dry-run 使用 PostgreSQL 只读事务；apply 的 player 表写入锁先于行锁，读取 JSON 前取得行锁，保持幂等合并。
- JSON 默认空数组；迁移独立执行。catalog 仍精确读取原有 id/canonical_name/created_at 三列，页面数据不改变既有名称包 catalog 哈希或名称前像。

独立复跑 `tests/web_ui/test_kifu_player_pages.py`：**21 passed in 2.30s**。指定改动 `git diff --check` 通过。未执行数据库迁移、生产写入或额外全量回归；部署前须按计划先显式增加列。

## 实际部署与回填

主线程已在 TEST、PROD 显式增加列并使用独立 operational importer 执行回填。2026-10-05 首次回填结果：

| 环境 | 已保存页面的棋手 | 新增 URL | 重复 dry-run 变更 |
|---|---:|---:|---:|
| TEST | 76 | 465 | 0 |
| PROD | 77 | 471 | 0 |

测试库少一位是杨鼎新暂无棋谱 FK 关联，名称写入仍保持原数据闸门；未绕过。新批名称入库后立即同步来源页面，保存 URL、登记来源 ID、语言、实际来源角色、关联 evidence ID；已有手工元数据保留。没有新建棋手主页。
