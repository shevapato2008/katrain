# 六名高频棋手精确关联：TEST／PROD 执行记录

2026-10-04，独立 gpt-6-astra max 身份及计划审核 PASS 后，按 TEST → PROD 顺序执行下列冻结计划。两库各新增 3,010 个 `kifu_albums` 棋手 FK；未新建或改名棋手 ID。

| 环境 | 批准计划 SHA-256 | 提交后关联槽／346,050 | 赛事关联／173,025 |
| --- | --- | ---: | ---: |
| TEST | `2dcdfbcd37b61f143b729bd86a86973be80550a88c47e0dbbbf140460ec68fa3` | 284,960 | 84,475 |
| PROD | `52daf7fbb6cb2846c98fcdf1b9f2ede90552097b8699a640f4f8db3158815854` | 286,565 | 84,957 |

每库更新：卢奕铨 559、伊田笃史 550、淡路修三 514、杨子萱 489、杨楷文 450、苏耀国 448。事务内重新核对完整 exact raw／日期／来源／旧 FK／目录前像，只更新获批 NULL 槽；提交后再读取六个原值的完整范围，均与计划中目标 FK 相符。六条 raw staging 为 `approved`，其 `player_id` 与 TEST／PROD 各自目录 ID 相符。再次读取全部 173,025 盘并对照冻结清单，PB／PW 原始文本全量不变。

八个段位变体槽、两个混合姓名槽、张涛 465 槽，以及原 next10 中已由其他批次关联的 1,459 槽，均不属于本次执行。两份计划不能重放；再次执行会在 NULL 前像门禁停止。

证据：[TEST dry-run](kifu-player-highfreq-next6-dryrun-test.log)、[PROD dry-run](kifu-player-highfreq-next6-dryrun-prod.log)、[TEST apply](kifu-player-highfreq-next6-apply-test.log)、[PROD apply](kifu-player-highfreq-next6-apply-prod.log)。执行时各 dry-run 均完成真实 SQL 更新后回滚，并复查回滚前像；apply 均返回 `applied: true`、新增 3,010 槽及提交后范围复查成功。
