# 棋手预处理：41–60 名次安全 15 项双库执行记录

截至 2026-10-04，TEST／PROD 事务预演经独立审查后，已先 TEST 后 PROD 正式写入并全量核验。研究来源为
[`kifu-player-nonhan-ranks-41-60-exact-allowlist-2026-10-04.json`](kifu-player-nonhan-ranks-41-60-exact-allowlist-2026-10-04.json)
（SHA-256 `cd96c693a7285702a47cf95523404583471144eb94dfe0664e3d748879043095`）。
本批从其 16 个原文中精确排除 `Iwata Tatsuaki` 的 255 槽，因为该项还
需要将同一目录 ID 的旧主名“岩田正男”改为“岩田达明”。独立子清单
[`kifu-player-nonhan-ranks-41-60-safe15-exact-allowlist-2026-10-04.json`](kifu-player-nonhan-ranks-41-60-safe15-exact-allowlist-2026-10-04.json)
SHA-256 为 `02164cc8889d3a6a790834ad35f64ee96316ecebf61493e3a3fb220f251e483e`，
明确记录来源哈希和隔离项；原 16 项文件未改。

| 环境 | 冻结计划 SHA-256 | exact raw | 实际新增 FK | 黑／白席位 | 复用 ID／新建 ID |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `ca863f8742c808baf285caaa3c382d4798c3ff7a3806244c51e2f73a676866b3` | 15 | 3,957 | 1,876／2,081 | 12／3 |
| PROD | `e1ea7a4acd970614c87e7da9aa2d74fcb0feccd5639d586d768da4dfb6c9f620` | 15 | 3,957 | 1,876／2,081 | 12／3 |

计划文件分别为 `kifu-player-nonhan-ranks-41-60-safe15-plan-test-2026-10-04.json.gz`
和 `kifu-player-nonhan-ranks-41-60-safe15-plan-prod-2026-10-04.json.gz`。
新建三个中文主名“杉内雅男”“本因坊秀和”“高木祥一”：TEST ID
分别为 `12350`、`12351`、`12352`，PROD 为 `6586`、`6587`、
`6588`。导入器对带 `catalog_action` 的行拒绝改名
动作，故隔离项不能混入当前计划。

逐项核对了冻结与实时盘号、黑白位置、exact raw、日期、对手原文、重复
标记和完整来源链接；全部 3,957 个实时 FK 均为空，15 个原文审核行均
`pending` 且元数据为空。事务预演再次捕获全部前像，执行建 ID、回填
和原文审核映射，检查影响行数后回滚；正式执行沿用相同计划。聚焦
SQLite 测试 4/4 通过。

提交后只读全量复查：TEST 为 3,760 棋手 ID、249,528／346,050
个席位已有 FK（72.107%，未决 96,522）；PROD 为 3,582 棋手 ID、
251,133／346,050（72.571%，未决 94,917）。安全 15 项原文均为
`approved` 且审核元数据指向本批目标 ID；3,957 个目标 FK 全部正确。
两库全部 173,025 盘棋的 346,050 个黑白原始姓名逐行与冻结清单相同。
`Iwata Tatsuaki` 仍为 `pending`，其 255 槽与旧主名改名动作另待审；
原审查中的其他 4 个暂缓原文合计 1,027 槽也未入本批。
