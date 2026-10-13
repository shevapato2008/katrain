# 514 盘赛事候选：TEST 与 PROD 精确关联已提交

2026-10-04。独立决定 `kifu-event-next514-independent-decision-astra-2026-10-04.json` SHA-256 `d310278775a8a1b5e08062b271485effdce8e3e58ac5eb218639cdd66b60ce3e`，批准 474 盘，保留 40 盘。执行器 `katrain/web/kifu/event_next514_exact.py` SHA-256 `dd8b4718ab7fbb1a241b3158d1f6c85fa569d0d8ad3def231e4f06150cddb7ca` 独立复审 PASS。

两库均完成完整前像捕获、SHA 核对、事务回滚演练及回滚后独立重读。棋手首批 1,451 个 FK 提交后，再次对原计划做两库回滚演练，确认 514 盘前像及被引用的 213 个棋手目录行仍完全一致，然后依次提交 TEST、PROD 并独立读取后像。

| 环境 | 数据库 | 已批准计划 SHA-256 | 新赛事 ID | 新增赛事关联 | 保留 HOLD |
|---|---|---|---|---:|---:|
| TEST | `katrain_db` | `ce2ccba64c0780694a64da5a4724a1f195bd219639462119f5eaf239e23af2db` | 86/87 | 474 | 40 |
| PROD | `katrain_prod_20260725` | `8ec2afbe6c0ab5fa7e4524311e9602bc6e955021b65bcdcb129c71827babade1` | 86/87 | 474 | 40 |

完整计划保存在 `kifu-event-next514-TEST-applied-plan-2026-10-04.json.gz`、`kifu-event-next514-PROD-applied-plan-2026-10-04.json.gz`。中日围棋对抗赛复用 ID75，新增 146 盘；中国围棋霸王战新建 ID86，关联 238 盘；中国新体育杯新建 ID87，关联 90 盘。40 盘 HOLD 中包含项目规则复盘确认有非法落子的 31 盘。仅写入获批的 `event_id`，所有届次维持 NULL，原始棋谱、棋手、来源保持原样。

提交后独立 SQL 核对：TEST 赛事关联 `101,516/173,025`、棋手关联 `304,981/346,050`、双方棋手和赛事都关联 `81,538` 盘；PROD 分别为 `101,998/173,025`、`306,586/346,050`、`82,693` 盘。两库新 ID86/87 的关联数均为 238/90。服务无需重启。
