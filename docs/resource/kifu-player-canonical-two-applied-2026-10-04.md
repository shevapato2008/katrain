# 赵善津、工藤纪夫默认名更正执行记录

2026-10-04，独立身份及代码审核 PASS 后，TEST 与 PROD 均原位将 `趙善津` 改为 `赵善津`、`工藤紀夫` 改为 `工藤纪夫`，保留原繁体写法为各自棋手的别名。TEST 目标 ID 为 542／348；PROD 为 541／347。没有新建棋手、迁移游戏 FK 或修改五语名称及其审核状态。

两库 capture、真实事务回滚演练、TEST → PROD 提交和提交后只读核验均通过。原有棋局关联分别保持赵善津66槽、工藤纪夫366槽。审核脚本 SHA-256 `0bff0ca6a782528bb3d74cb8168b0b5dbdf38c2df98373d66889ac4edd1e9048`。

| 环境 | 冻结计划 SHA-256 | 提交后验证 |
| --- | --- | --- |
| TEST | `48950e9d00be28fd7d55eb23b04879c1686acad1557c7eb25582cb590ebe253d` | 2／2 ID、别名、旧五语原像及 FK 分布 |
| PROD | `6b418400b3bf21915ac57edab70446ebcfa2961aaaf64c686c7d8333d2b67ec4` | 2／2 ID、别名、旧五语原像及 FK 分布 |

裁决见 [独立身份说明](kifu-player-canonical-dedup-independent-decision-astra-2026-10-04.md)，执行器见 [apply_kifu_player_canonical_two.py](../../scripts/apply_kifu_player_canonical_two.py)，计划和日志见同目录 `kifu-player-canonical-two-*`。
