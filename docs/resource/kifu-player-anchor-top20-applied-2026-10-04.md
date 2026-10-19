# Top20 棋手精确关联执行记录

2026-10-04。根据独立决策 `kifu-player-exact-anchor-top20-independent-decision-astra-2026-10-04.json`（SHA-256 `6d53699a34bbcc4006020b9089977d4ca44eb4e192cd70db6021edb21dc5f39b`），TEST 与 PROD 各关联 **1,933 个**已核实的棋手 FK 槽位；**1,415 个 HOLD** 保持原状。仅更新 `kifu_albums.black_player_id` / `white_player_id`，没有写译名、别名、raw staging、赛事或 SGF。

执行器 `katrain/web/kifu/player_anchor_top20_exact.py` SHA-256 `fb2bf8d9435f24f3a4bf7483aca62c76d039f6a27c284fd86a219c74d74bcf95`。聚焦测试 14 项通过；独立代码审核修复提交后复核错误提示问题后复审 PASS。两库均按各自完整前像 capture、计划字节 SHA 核对、dry 回滚、apply、独立提交后复核的顺序执行。

| 环境 | 计划文件 | SHA-256 | 写入前棋手槽 | 写入后棋手槽 | 赛事关联 |
|---|---|---|---:|---:|---:|
| TEST | `kifu-player-anchor-top20-TEST-captured-plan-2026-10-04.json.gz` | `f900cde8311614122ea3527d70f5786560621fb2c60a8c8660c61b38f5f784de` | 308,337 | 310,270 | 103,046（不变） |
| PROD | `kifu-player-anchor-top20-PROD-captured-plan-2026-10-04.json.gz` | `17ea7cb99b2fccb56a74f87f9fe6c2f5d7beef370348fc67177e83a4eb31eb91` | 309,942 | 311,875 | 103,528（不变） |

两库独立 SQL 均确认 173,025 盘棋。执行未重启服务。
