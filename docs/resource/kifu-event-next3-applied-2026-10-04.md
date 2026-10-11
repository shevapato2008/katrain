# 三类赛事精确关联：TEST 与 PROD 已提交

2026-10-04。独立审核最终决定：`kifu-event-after6810-next3-independent-decision-astra-2026-10-04.json`，SHA-256 `87251ecea191f7cce337ee488e7daf82a71908dfda28455576197c9c499c872d`。初版决定已撤销。

执行器 `katrain/web/kifu/event_next3_exact.py` 的独立复审结果为 PASS，模块 SHA-256 `4cf6717fbfaf6e27c2e9fb634d7edf2b5920c930f4982d1edeb9611967aec7c4`。测试库和正式库分别捕获完整执行计划、核对 SHA、执行真实事务回滚演练并重新读取原像，然后依次提交并独立读取后像。

| 环境 | 数据库 | 已批准计划 SHA-256 | 新赛事 ID | 新增赛事关联 | 保留 HOLD |
|---|---|---|---|---:|---:|
| TEST | `katrain_db` | `42729bf088e9e8646d51c011b1a13ac3734a5cf01fe8f068f35b3bbf0fa5de5d` | 79/80/81 | 2,153 | 268 |
| PROD | `katrain_prod_20260725` | `3c9fdb2ce84b72d6d5d0b42fcde1ce1a9496494d84022d63de338eb829f5dfca` | 79/80/81 | 2,153 | 268 |

已保存两库完整执行计划：`kifu-event-next3-TEST-applied-plan-2026-10-04.json.gz`、`kifu-event-next3-PROD-applied-plan-2026-10-04.json.gz`。

| 新赛事类型 | ID | 精确关联盘数 |
|---|---:|---:|
| 台湾友士杯十段赛 | 79 | 1,002 |
| 韩国KBS杯围棋王战 | 80 | 748 |
| 台湾联电杯职业围棋赛 | 81 | 403 |

全部 2,421 盘范围在提交前均未关联赛事或届次。只写入 2,153 个已批准的 `event_id`；268 盘（含 10 盘仅有 KBS Cup 简称的记录）继续 HOLD，所有 `event_edition_id` 仍为 NULL。既有 27 个棋手 FK、完整棋谱、来源关联和目录行均纳入环境精确后像校验。

提交后独立 SQL 核对：TEST 为赛事关联 `101,042/173,025`、棋手关联槽 `303,530/346,050`、双方棋手及赛事均已关联 `80,333` 盘；PROD 为 `101,524/173,025`、`305,135/346,050`、`81,488` 盘。两库新类型关联数量均为 1,002/748/403。服务无需重启。
