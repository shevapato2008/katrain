# 暂定棋手关联首批 20 个原名确认并入库

2026-10-04。先由只读试点调查，再独立复核、Astra 独立决策。复核发现初稿错误地声称吴树浩曾用名娄玺；经双库目录与 2004 年中国棋院消息核对，二人为不同棋手。审核报告已纠正，旧计划保持历史记录但未用于提交。

**实际写入：**TEST、PROD 各把 20 个精确 `kifu_raw_player_values` 行从 `pending/provisional_person_link` 更新为 `approved/verified_person`，对应已存在的 13,633 个黑白棋手槽位。没有修改 `kifu_albums` 外键、棋手目录、别名、译名、赛事或 SGF。

| 环境 | 修订计划 SHA-256 | SQL SHA-256 | 试运行 | 提交后只读核验 |
| --- | --- | --- | --- | --- |
| TEST | `a73a36404a3d8b1da6f3c288a37fdbed91a130c9d48e45b46baff5e8ca7600ac` | `7cec498bf53dd92e2b4dede106db6f149597f5030866decb5531b20b40a82851` | 20 更新并 ROLLBACK | 173,025 棋局；20/20 exact approved；13,633 槽；0 错 FK；0 槽数偏差 |
| PROD | `d6c70182e2c6b02f46857181a66832092453c3e30d5f1796510303553cd9ac47` | `a75a430ba20975f48e768634a8f619da6166de49ad532fe259474d9535bf1871` | 20 更新并 ROLLBACK | 173,025 棋局；20/20 exact approved；13,633 槽；0 错 FK；0 槽数偏差 |

两库均按计划 SHA 核对本地文件与远端 SQL 文件；在 `SERIALIZABLE` 事务中锁内校验完整前像、精确 raw ID/value、各自 player ID 和中文目录名、13,633 槽与 FK，更新后校验 20 行后像，再 `COMMIT`。提交后的独立只读事务复核上述结果。TEST 和 PROD 没有共用数字 player ID。

修订审核报告 SHA-256：`f165db1532009e04f927f4769b75a64fd38b950af542e9a2cd69a28942963fe7`。Astra 独立决策 SHA-256：`836f8a1f3ff7fb74f30cf1e2bb2aeddc03fd1a9e34af63fcdf6830527f576d35`。本批仅确认身份关联，五语言翻译保持暂停。
