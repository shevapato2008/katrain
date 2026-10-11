# 国内烂柯杯、韩国棋王战、韩国十段战精确关联执行记录

2026-10-04。独立赛事决定 `kifu-event-after-korean-two-next-independent-decision-astra-2026-10-04.json`（SHA-256 `264606394e2ad40dfec332ae660f8b281372cd4b6d30e6e8d646962ed487289b`）批准 1,209 盘，仅关联赛事类型；本批 476 盘 HOLD、旧有 4,292 盘 HOLD 保留。先依据已提交的 top20 棋手批次形成独立精确重基线 `kifu-event-after-korean-two-next-post-top20-independent-exact-rebase-2026-10-04.json`（SHA-256 `54deecc86c3cf2db41760b7be7af654f262008d35dd76fa34bbbd3c2ee09e926`），仅允许交叉的 29 个棋手 FK 和 3 条新增引用棋手守卫。

执行器 `katrain/web/kifu/event_after_korean_exact.py` SHA-256 `ecdb912f0850de2b42593d28f4c9ae705d215ab2311aac9eada57a531dd7a996`，13 项聚焦测试通过，独立代码复审 PASS。TEST 与 PROD 分别 capture、核对计划字节 SHA、dry 回滚、apply、提交后独立复核。仅新增 3 个赛事类型并写入 1,209 个 `event_id`；不写届次、译名、别名、SGF 或棋手 FK。

| 环境 | 计划文件 | SHA-256 | 赛事关联前 | 赛事关联后 | 新类型 ID |
|---|---|---|---:|---:|---|
| TEST | `kifu-event-after-anchor-TEST-captured-plan-2026-10-04.json.gz` | `83654a43e0dce157705a5218fe596fbb250b2ccdbed79662b25fa177e1e8ad1a` | 103,046 | 104,255 | 97、98、99 |
| PROD | `kifu-event-after-anchor-PROD-captured-plan-2026-10-04.json.gz` | `52d018b60315279b07c1a479ec58802a869fc34e78be72bb1fbb04b103358c5f` | 103,528 | 104,737 | 97、98、99 |

两库独立 SQL 确认棋局仍为 173,025 盘，棋手关联分别为 310,270 / 311,875。执行未重启服务。
