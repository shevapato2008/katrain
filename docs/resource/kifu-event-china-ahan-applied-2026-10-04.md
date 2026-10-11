# 中国阿含桐山杯精确赛事关联：TEST 与 PROD 已提交

2026-10-04。独立赛事决定 `kifu-event-china-ahan-independent-decision-astra-2026-10-04.json` SHA-256 `53c88b3efb87e0d331aaa27a9a35512129bc5d6896c378d1f0da4f6769f1f891`：批准 793 盘，8 盘本批 HOLD，4,265 盘既有 HOLD 保留，届次不写。执行器 `katrain/web/kifu/event_china_ahan_exact.py` SHA-256 `e98d7c8c2595a4027afc9e09381b3ab965b044e8677a84324c19d6dd023160ff`，独立代码审核 PASS，3 项聚焦测试通过。

两库分别完成只读计划捕获、计划字节 SHA 核对、真实事务回滚演练和回滚后重读；之后先提交 TEST，再提交 PROD。执行器仅把精确批准的 793 个 `event_id=NULL` 改为新建类型 `中国阿含桐山杯` 的 ID 89。两库 `event_edition_id` 均未写入；SGF、来源、棋手及其他棋局字段均未改。

| 环境 | 数据库 | 已提交计划 SHA-256 | 新赛事 ID | 新增赛事关联 | 本批 HOLD |
|---|---|---|---:|---:|---:|
| TEST | `katrain_db` | `dd96d3f50ea7f7458f2b9116f1bb7d0d45a0635c24147c36e80b9c75a4859fb4` | 89 | 793 | 8 |
| PROD | `katrain_prod_20260725` | `3d8f3fe5bdb7110a2b2ff7ec2c32910e2ae7eed689a4fd7b925ba0995da245f1` | 89 | 793 | 8 |

完整计划为同目录 `kifu-event-china-ahan-{TEST,PROD}-applied-plan-2026-10-04.json.gz`。提交后独立 SQL：TEST 赛事关联 `102,309/173,025`、棋手关联 `307,736/346,050`、双方棋手及赛事均关联 `83,931` 盘；PROD 分别为 `102,791/173,025`、`309,341/346,050`、`85,113` 盘。ID 89 各关联 793 盘、届次 0。服务无需重启。

供后续棋手批次精确重基线的只读后像：`kifu-event-china-ahan-TEST-postimage-2026-10-04.json` SHA-256 `72d7c994c4349d47cb6ad04a87cc342ce61a1cf8797c0bcbace3533f4d659829`，PROD 同名文件 SHA-256 `0ac97c1f309e0777e5ab3bf944850c170cc89b416f0128fae2633bdf3350fda0`。它们包含两库完整新赛事行及三个交叉棋局 `103194、125109、134804` 的全字段后像。
