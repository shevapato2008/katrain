# 高频棋手首批精确关联：TEST 与 PROD 已提交

2026-10-04。独立逐槽决定 `kifu-player-new33-firstbatch-independent-slot-decision-2026-10-04.json` SHA-256 `81dfb98ae8afe8ffbaa4fab5154dd31017df368af96b50773e57c03e98e94433`；next3 赛事精确重基线补充 `kifu-player-new33-firstbatch-next3-exact-rebase-2026-10-04.json` SHA-256 `f2716b79e9b053434a7e3bd118bf8c46413752ddfe0878afdc444379ffa47021`。

执行器 `katrain/web/kifu/player_new33_firstbatch.py` 最终 SHA-256 `5e8e869506b4e30734ffa2ec69ba19673662c7599e8f5cb91f4cd88ff63d3e9d`。首次两库只读捕获因引用赛事目录子集／全局目录范围不一致被拒绝，**当时没有写入**。修正后独立复审 PASS；TEST/PROD 完整计划捕获、计划 SHA 核对、真实事务回滚演练及回滚后重读均通过，然后依次提交并独立读取后像。

| 环境 | 数据库 | 已批准计划 SHA-256 | 新棋手 ID | 新增精确 FK 槽位 | 保留 HOLD |
|---|---|---|---|---:|---:|
| TEST | `katrain_db` | `2534207b89dc911a7378f4279a664ce7036d873946ad73b659369f4cbc1261b1` | 12565–12571 | 1,451 | 5,922 |
| PROD | `katrain_prod_20260725` | `eb4c443969a8f998037de9ac241e14562e53bae109fec67ec5a0cdbc835cbe79` | 6796–6802 | 1,451 | 5,922 |

完整计划保存在 `kifu-player-new33-firstbatch-TEST-applied-plan-2026-10-04.json.gz` 与 `kifu-player-new33-firstbatch-PROD-applied-plan-2026-10-04.json.gz`。两库均新建金世东、李泰贤、金主镐、温昭珍、韩友赈、金成进、朴胜文七个中文 canonical 身份；杉内寿子 306 个获批槽位复用既有本田寿子 ID（TEST 10622、PROD 4836）。没有新建别名、译名或修改赛事、届次、SGF、来源。其余 5,922 个槽位维持原样。

提交后独立 SQL 核对：TEST 棋手关联 `304,981/346,050`、赛事关联 `101,042/173,025`、双方棋手及赛事均关联 `81,099` 盘；PROD 分别为 `306,586/346,050`、`101,524/173,025`、`82,254` 盘。服务无需重启。
