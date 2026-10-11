# 韩国两项赛事精确关联：TEST 与 PROD 已提交

2026-10-04。独立逐局决定 `kifu-event-next-after-china-ahan-independent-decision-astra-2026-10-04.json` SHA-256 `749e066920dcdc0fc181074f15c10128e7f277ba87d98d699e87bc5638595d80`，精确批准 737 盘、HOLD 19 盘，并保护 4,273 盘既有 HOLD。阿含桐山杯提交后的独立重基线保留完整目录守卫。执行器 `katrain/web/kifu/event_korean_two_exact.py` SHA-256 `f354c6a22645f199d5b90d74e6b047660cc954d21510c149479bbd2bffe06e2f`，独立代码审核 PASS；13 项聚焦及前序测试通过，另用真实快照函数完成隔离数据库的捕获、回滚和提交路径验证。

两库各自完成只读计划捕获、计划字节 SHA 核对、真实事务回滚演练和回滚后重读，再依次提交 TEST、PROD。仅批准的 737 个 `event_id=NULL` 被关联到两个新类型；届次、棋手、SGF、来源及其他字段均未改。

| 环境 | 数据库 | 已提交计划 SHA-256 | 新类型 ID | 新增赛事关联 | 本批 HOLD |
|---|---|---|---|---:|---:|
| TEST | `katrain_db` | `58ab0b967f1a1feb78d99bf9b27f63acf99f2537f3280d643aa693ba0d1d3352` | GS 92；女子国手 93 | 737 | 19 |
| PROD | `katrain_prod_20260725` | `bdcda31f78fae21cd4d1087110acc2d04eef0a78d577faaf2da731a268e9d99d` | GS 92；女子国手 93 | 737 | 19 |

完整计划为同目录 `kifu-event-korean-two-{TEST,PROD}-applied-plan-2026-10-04.json.gz`。提交后独立 SQL：两库 ID 92 `韩国GS加德士杯` 各 397 盘，ID 93 `韩国女子国手战` 各 340 盘，均无届次关联。TEST 赛事关联 `103,046/173,025`、棋手关联 `308,337/346,050`、双方棋手及赛事均关联 `85,038` 盘；PROD 分别为 `103,528/173,025`、`309,942/346,050`、`86,224` 盘。服务无需重启。
