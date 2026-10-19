# 棋手预处理第二批：TEST／PROD 执行记录

截至 2026-10-04，第二批已先在 TEST、后在 PROD 事务写入并逐项核验。身份输入是
[`kifu-player-second-batch-reviewed-2026-10-04.json`](kifu-player-second-batch-reviewed-2026-10-04.json)
v2，文件 SHA-256 `209d4297e3ae8a815a61dd773b6fba765f888578f89f024abdec0bce9a28f85f`。
导入代码为 `katrain/web/kifu/catalog_player_second.py` 与
`scripts/kifu_player_second_batch.py`。

## 实时范围与实际写入

| 环境 | 计划文件 SHA-256 | 原文 | 审核槽位 | 原已正确 FK | 实际新增 FK | 黑／白新增 | 改主名／新 ID |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TEST | `be9b2d1319dbc2f98ba8a761a28c1eebbb9b3de462546061d3ce642da83d8c4c` | 95 | 26,015 | 20 | 25,995 | 12,991／13,004 | 3／1 |
| PROD | `08805fe12c66d4ea73e0413e9b64abe4d9625228e0efaac842f075f84e2c28a9` | 95 | 26,015 | 20 | 25,995 | 12,991／13,004 | 3／1 |

计划文件分别是 `kifu-player-second-plan-test-2026-10-04.json.gz` 和
`kifu-player-second-plan-prod-2026-10-04.json.gz`。两环境按当前 canonical
主名各自解析 ID，TEST 和 PROD 的数字不同。捕获逐组比较冻结与实时的
album ID、黑白位置、exact raw、日期、对手原文、重复标记及完整来源链接，
并核对 v2 中每个原文的席位数和来源分布。事务预演重新捕获全部前像，
然后实际执行 SQL 回填、原文审核映射、改名与建 ID。两库先通过回滚
预演，完成独立代码审查后再按同一计划正式提交。TEST 的陈诗渊新 ID
为 `12338`；PROD 为 `6574`。

v2 的旧 `frozen_scope_sha256` 未有可复现的生成函数，因此执行门禁使用
导入器明确实现的逐项范围等值核查和各组新 `scope_sha256`，二者写在冻结
计划内。未用未能重算的旧哈希作门禁。

7 个待折叠旧重复 ID 目前没有棋局 FK、别名或研究证据引用，但各有 5 条
旧译名，部分与目标 ID 同语种译名冲突。本批保留这 7 个 ID 及所有译名行，
只把审核原文映射到目标 ID；待译名审查时再决定目录折叠。42 个相似前缀
原文不在白名单内，原始棋谱姓名不改。

提交后再次查询：TEST 为 3,753 棋手 ID、234,143／346,050 席位已有 FK
（67.662%，未决 111,907）；PROD 为 3,575 棋手 ID、235,748／346,050
席位已有 FK（68.125%，未决 110,302）。两库 95 个原文均为 `approved`，
且审核元数据指向本批目标 ID；26,015 审核槽均指向目标。7 个旧重复 ID
和各自译名行与前像相同。逐行读取两库全部 173,025 棋局，346,050 个
黑白原始姓名与原冻结清单完全一致。

`pytest -q tests/web_ui/test_kifu_catalog_player_second.py`：2 passed。
