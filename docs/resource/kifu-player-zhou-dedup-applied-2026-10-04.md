# 周鹤洋重复目录与两盘错字棋谱执行记录

2026-10-04，按[独立身份裁决](kifu-player-canonical-dedup-independent-decision-astra-2026-10-04.md)和独立代码审核 PASS 的固定计划，先 TEST、后 PROD 执行周鹤洋目录 B/C 精确归并。两库提交后均在新只读事务中复核完整后像。

| 操作 | TEST | PROD |
| --- | --- | --- |
| 保留棋手 ID | 1048 周鹤洋 | 4193，原位改名周鹤洋 |
| 棋局 FK 调整 | 87152 白方、148135 黑方，共2槽 | 148135 黑方1槽；87152白方原4193保留 |
| raw 审核 metadata 指向 | 10145、10148，共2行 | 10148，1行 |
| 归档并删除重复棋手 ID | 1028、9988、9989 | 4194 |
| 旧名称 | 1028 的5条全行原像归档；1048五条保留 | 不涉及 |

完整行 CAS、SGF SHA、来源和五类入向 FK 加 raw metadata 引用检查通过；删旧 ID 之前残余引用均为0。没有建立错字 alias，没有改原始棋谱，旧日语／韩语名称冲突及未关联的860槽留待后续姓名归并。

脚本 [kifu_player_zhou_exact_dedup.py](../../scripts/kifu_player_zhou_exact_dedup.py) SHA-256 `91ff92c538ee9b16545ff674dcdade2175b792c7fbe49382e4b98bf316064818`；14项聚焦测试通过。冻结计划 SHA-256：TEST `b5d1f5cb1dc9fd6176bbfad64a7b1f2185565b124e6127205c9adf81163e37fe`、PROD `f4dc01fed501e645e65625a9f086f3725dff457201856d5c10b1ae8741192613`。两库 capture、真实事务回滚 dry-run、apply、独立 verify 的记录在同目录 `kifu-player-zhou-dedup-*`。
