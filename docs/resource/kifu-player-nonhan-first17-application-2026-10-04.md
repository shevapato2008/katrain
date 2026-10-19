# 棋手预处理：前 17 个英文原文双库执行记录

截至 2026-10-04，先经 TEST／PROD 事务预演和独立审查，再先 TEST 后 PROD 正式写入并全量核验。
输入为 [`kifu-player-nonhan-first17-exact-allowlist-2026-10-04.json`](kifu-player-nonhan-first17-exact-allowlist-2026-10-04.json)，
SHA-256 `f111f879f12ac98f57b46c264aac5a27911e93c4b57d54f3d9a3a078c43c8ab0`。
导入器是 `katrain/web/kifu/catalog_player_nonhan.py` 与
`scripts/kifu_player_nonhan_batch.py`。

| 环境 | 冻结计划 SHA-256 | exact raw | 实际新增 FK | 黑／白席位 | 复用目标 ID／新建 ID |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `d770bcde81eccd12c5dcac03a90cb9eae2b181b09bfd87d06dfe4f63bd77d586` | 17 | 6,012 | 2,809／3,203 | 15／2 |
| PROD | `ae3d5d65315fe4ab17848af356041499dbd9f024b281d818250b7f8282c16f5c` | 17 | 6,012 | 2,809／3,203 | 15／2 |

计划文件分别为 `kifu-player-nonhan-first17-plan-test-2026-10-04.json.gz`
和 `kifu-player-nonhan-first17-plan-prod-2026-10-04.json.gz`。两库分别按白名单
指定的本地 ID 读取和锁定现有主名；“桥本宇太郎”“梶原武雄”尚无目录 ID，
正式写入在各环境各建两个中文主名 ID：TEST 分别为 `12341`、`12342`，
PROD 分别为 `6577`、`6578`。现有“工藤紀夫”与白名单简中
“工藤纪夫”、现有“岛村俊宏”与白名单“岛村俊广”存在主名差异；本批
只关联原文，**不改这两个旧 ID 的主名**，另待主名审查。

每个原文均精确匹配；冻结与实时盘号、黑白位置、原文、日期、对手原文、
重复标记和完整来源链接逐项一致。6,012 个实时 FK 全为空，17 个审核行
均 `pending` 且元数据为空；同人自对局及对手已指向相同目标 ID 的情况
均排除。事务预演重新捕获并比较全部前像，再执行建 ID、回填 FK 和原文
审核映射，检查影响行数后回滚；正式执行沿用相同计划。聚焦 SQLite
测试 2/2 通过。

提交后只读全量复查：TEST 为 3,755 棋手 ID、240,155／346,050 个席位
已有 FK（69.399%，未决 105,895）；PROD 为 3,577 棋手 ID、
241,760／346,050（69.863%，未决 104,290）。17 个原文均为 `approved`
且审核元数据指向本批目标 ID；6,012 个目标 FK 全部正确。两库全部
173,025 盘棋的 346,050 个黑白原始姓名逐行与冻结清单相同。
`Iwamoto Kaoru`、`Maeda Nobuaki`、`Fujisawa Hosai` 三个歧义原文
（合计 1,105 槽）仍为 `pending`；`Unknown`、`Black`、`White`
占位原文未入本批。
