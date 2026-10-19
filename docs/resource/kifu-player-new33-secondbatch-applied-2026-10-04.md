# 高频棋手第二批精确关联：TEST 与 PROD 已提交

2026-10-04。独立逐槽决定 `kifu-player-new33-secondbatch-independent-slot-decision-astra-2026-10-04.json` SHA-256 `dde6d06c6ada0b1520a9854a212a8a28de3e72809abffe2ccc2945e44bb795fb`；已提交批次的精确重基线 `kifu-player-new33-secondbatch-committed-batches-exact-rebase-2026-10-04.json` SHA-256 `70d57853166704203003935186c68de1e78e6f2382db8a1e29d2c1df1af06509`。

执行器 `katrain/web/kifu/player_new33_secondbatch.py` SHA-256 `e5e0d95a4f612baebb3aff3eb453d885ffee574154703265534c7c25ac523d8f`，独立代码审核 PASS，5 项聚焦测试通过。两库只读捕获、计划 SHA 核对、真实事务回滚演练通过，再依次提交 TEST、PROD 并独立读取后像。

| 环境 | 数据库 | 已批准计划 SHA-256 | 新棋手 ID | 新增精确 FK 槽位 | 保留 HOLD |
|---|---|---|---|---:|---:|
| TEST | `katrain_db` | `84986ba4751a59449d1f7befc7e86993d47cd885849d83c82b2fb6193f6e8706` | 12588–12603 | 2,755 | 3,167 |
| PROD | `katrain_prod_20260725` | `58147904aa8bc84258948cfe3f4711ed10d5105e0f1b7aab497289ca99f05adc` | 6819–6834 | 2,755 | 3,167 |

完整计划保存在 `kifu-player-new33-secondbatch-TEST-applied-plan-2026-10-04.json.gz` 与 `kifu-player-new33-secondbatch-PROD-applied-plan-2026-10-04.json.gz`。两库均新建周平强、刘耀文、刘曦、黄彦诚、陈逸达、夏大铭、杨嘉源、汤川光久、陈义翔、横田茂昭、张学斌、后藤俊午、秦悦欣、曹潇阳、张正平、党希昀 16 个中文 canonical 棋手身份。543 个本批候选因身份或逐局证据不足维持 NULL；此前排除的槽位也未修改。没有改写 SGF、来源、赛事或译名。

提交后独立 SQL 核对：TEST 棋手关联 `307,736/346,050`、赛事关联 `101,516/173,025`、双方棋手及赛事均关联 `83,215` 盘；PROD 分别为 `309,341/346,050`、`101,998/173,025`、`84,381` 盘。服务无需重启。
