# 高频八家族棋手精确迁移：执行与复查

状态：**TEST / PROD 均已按独立审核通过的计划提交并复查**。身份审查依据[八家族 review](kifu-player-multi-id-family-review-2026-10-04.md)；工具为 [catalog_player_family.py](../../katrain/web/kifu/catalog_player_family.py) 和 [CLI](../../scripts/kifu_player_family_migrate.py)。两库各自使用 post7 冻结库存及实时目录、原始值、来源和逐槽 FK 前像。

| 环境 | 计划 SHA-256 | NULL 新槽 | 旧 FK 重指 | canonical 更正 | metadata `player_id` 同步 | 新 ID |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TEST | `fd47872f33b487b14416e16928a23db7559352af4ab402b9442d46aca979dcc3` | 504 | 20 | 2 | 5 | 0 |
| PROD | `4c5fd9f2691c77c7ba9a1973c41e3f152d96a656c6bbd7e5bddcfd54bb40497a` | 504 | 20 | 2 | 5 | 0 |

计划文件：[TEST](kifu-player-family-test-plan-2026-10-04.json.gz)、[PROD](kifu-player-family-prod-plan-2026-10-04.json.gz)。各计划冻结 album ID、黑白槽、PB/PW 原文、日期、重复指针、来源、旧 FK 和目标 ID，并附目录 alias、译名、evidence 与 raw metadata 前像。`run` 在表锁内重新捕获并比较整份计划，逐槽按原文和旧 FK 做 compare-and-swap；默认 rollback。两库 dry-run 均返回上述预期数量，之后重新只读捕获所得 SHA 不变。独立 gpt-6-astra 审核确认无 blocker 后，仅通过 CLI 的 `pinned()` 文件 SHA 检查与 `--approved-plan-sha256` 门禁，按 TEST→PROD 顺序提交。

| 家族 | 每库 NULL 新槽 | 每库旧 FK 重指 | 目标 ID（PROD / TEST） |
| --- | ---: | ---: | --- |
| 岩田达明 | 267 | 0 | 4519 / 10310 |
| 前田陈尔 | 185 | 0 | 4043 / 9839 |
| 林海峰 | 29 | 1 | 298 / 299 |
| 赵治勋 | 14 | 0 | 608 / 609 |
| 武宫正树 | 9 | 0 | 490 / 491 |
| 岩本薰 | 0 | 15 | 4517 / 10308 |
| 加纳嘉德 | 0 | 3 | 4049 / 9845 |
| 藤泽朋斋 | 0 | 1 | 5854 / 11623 |

岩田正男的 8 个旧 FK 及前田陈二的 1 个旧 FK 均作为保护槽捕获并保持不动。岩田达明七段的 135904/B 仅核身份，1962 年原始段位保留。两个 canonical 更正复用旧目录 ID，并为「岩田正男」「前田陈二」增加同 ID 别名；已有译名和 evidence 原样保留。岩本熏、岩本薫、加纳嘉徳、林海蜂、藤泽朋斎的 5 条 raw metadata 非 FK 引用随 20 个旧 FK 重指同步到主 ID，原 metadata 其他字段保留。任何别名、目标 canonical、译名或已批准 evidence 的异人冲突会中止。旧目录 ID 不删除、不停用，其译名和 evidence 不自动搬迁。

赵治勋重复连写 `赵治勋赵治勋` 7 槽及截断 `趙治勳(` 1 槽仍 hold。原始 `player_black`、`player_white` 和段位字段不在更新集合。聚焦计划及审批门禁测试 2 passed；现有 second-batch 相关测试 2 passed。

提交后两库逐槽核对全部 504 个新增 FK、20 个重指 FK、9 个保护槽及 8 个 hold 槽，并核对原始黑白姓名、日期、两个 canonical 与旧名 alias：全部匹配计划。TEST 棋手关联席位升至 269,243／346,050，PROD 升至 270,848／346,050；目录 ID 数保持 TEST 3,836、PROD 3,658。
