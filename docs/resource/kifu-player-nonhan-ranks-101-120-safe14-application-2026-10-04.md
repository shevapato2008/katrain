# 棋手预处理：101–120 名次安全 14 项双库执行记录

截至 2026-10-04，TEST／PROD 事务预演经独立审查后，已先 TEST 后 PROD 正式写入并全量核验。研究来源为
[`kifu-player-nonhan-ranks-101-120-exact-allowlist-2026-10-04.json`](kifu-player-nonhan-ranks-101-120-exact-allowlist-2026-10-04.json)
（SHA-256 `cc67ef4d8226a77583411aaaccf950ec1a7cf4ead412770497f29293f3e620e2`）。
本批从原 15 项中精确隔离 `Sugiuchi Kazuko` 的 161 槽：它指向同一
旧目录 ID，但仍需将“本田寿子”改为“杉内寿子”，并与其妹本田幸子
保持区分。派生的[安全 14 项清单](kifu-player-nonhan-ranks-101-120-safe14-exact-allowlist-2026-10-04.json)
SHA-256 为 `08b098919510b18959ec8a1041d24cb75fb68bf141b1a9b9c47bd75217b32b5b`，
保留来源哈希与隔离项；原文件未改。

| 环境 | 冻结计划 SHA-256 | exact raw | 实际新增 FK | 黑／白席位 | 复用 ID／新建 ID |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `809c0ba2e6bfe69cbaef6e4f98d51165821890c76cf5df6931e373ad87cb5dcd` | 14 | 2,276 | 1,170／1,106 | 10／4 |
| PROD | `70e300f2e07fa0f3d08043c7434356d8cc8e7a46faf2535421d5c7ee5228cdb8` | 14 | 2,276 | 1,170／1,106 | 10／4 |

计划文件分别为 `kifu-player-nonhan-ranks-101-120-safe14-plan-test-2026-10-04.json.gz`
和 `kifu-player-nonhan-ranks-101-120-safe14-plan-prod-2026-10-04.json.gz`。
新建四个中文主名“西条雅孝”“村岛谊纪”“菅野清规”“细川千仞”：
TEST ID 分别为 `12369`–`12372`，PROD 为 `6605`–`6608`。10 个
复用 ID 的现主名与审定中文
名一致。导入器明确拒绝混入 `rename_existing_catalog_player` 动作。

冻结与实时盘号、黑白位置、exact raw、日期、对手原文、重复标记和完整
来源链接逐项一致；2,276 个实时 FK 全为空，14 个原文审核行均为
`pending` 且元数据为空。事务预演重新捕获全部前像，执行建 ID、回填
和原文审核映射，核对影响行数后回滚；正式执行沿用相同冻结计划。聚焦
SQLite 测试 7/7 通过。

提交后只读全量复查：TEST 为 3,770 棋手 ID、258,039／346,050 个
席位已有 FK（74.567%，未决 88,011）；PROD 为 3,592 棋手 ID、
259,644／346,050（75.031%，未决 86,406）。安全 14 项原文均为
`approved` 且审核元数据指向本批目标 ID；2,276 个目标 FK 全部正确。
两库全部 173,025 盘棋的 346,050 个黑白原始姓名逐行与冻结清单相同。
`Sugiuchi Kazuko` 仍为 `pending`，两库旧 ID 的主名仍是“本田寿子”；
原排名段另外 5 个暂缓原文／773 槽也未入本批。
