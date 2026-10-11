# 棋手预处理：81–100 名次 14 项双库执行记录

截至 2026-10-04，TEST／PROD 事务预演经独立审查后，已先 TEST 后 PROD 正式写入并全量核验。输入为
[`kifu-player-nonhan-ranks-81-100-exact-allowlist-2026-10-04.json`](kifu-player-nonhan-ranks-81-100-exact-allowlist-2026-10-04.json)，
SHA-256 `083a20eb93c6a86177b3bc62d306eba9b38a724f203162909a18d3949e095763`。
导入器沿用 `katrain/web/kifu/catalog_player_nonhan.py` 与
`scripts/kifu_player_nonhan_batch.py`，仅增加此审核清单的格式支持。

| 环境 | 冻结计划 SHA-256 | exact raw | 实际新增 FK | 黑／白席位 | 复用 ID／新建 ID |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `19481d5068b190035e583269d47e9568a06c73c0a53cec4df2a640b39c1f31c3` | 14 | 2,701 | 1,304／1,397 | 12／2 |
| PROD | `e636ea57a7ec9e399d7e4b4f52ee8c546f9b222a01c7eb2ec9b6fc312c677b5b` | 14 | 2,701 | 1,304／1,397 | 12／2 |

计划文件分别为 `kifu-player-nonhan-ranks-81-100-plan-test-2026-10-04.json.gz`
和 `kifu-player-nonhan-ranks-81-100-plan-prod-2026-10-04.json.gz`。拟建
两个中文主名“小松伸昭”“小林铁次郎”：TEST 新 ID 为 `12363`、
`12364`，PROD 为 `6599`、`6600`。12 个复用目录 ID 按环境分别取
本地数字；审定原文
`Shusai Meijin` 与已关联的 `Tamura Hoju (later Shusai)` 指向同一
本因坊秀哉 ID，预检排除了对手已连到该 ID 的自对局冲突。

逐项核对了冻结与实时盘号、黑白位置、exact raw、日期、对手原文、重复
标记和完整来源链接。全部 2,701 个实时 FK 为空，14 个原文审核行均
`pending` 且元数据为空。事务预演再次捕获全部前像，执行建 ID、回填
FK 和原文审核映射，核对影响行数后回滚；正式执行沿用相同冻结计划。
TEST 预演后，先完成 61–80 双库正式写入，才执行 PROD 预演；PROD
计划的前像在这次写入后仍逐项一致。聚焦 SQLite 测试 6/6 通过。

提交后只读全量复查：TEST 为 3,766 棋手 ID、255,763／346,050 个
席位已有 FK（73.909%，未决 90,287）；PROD 为 3,588 棋手 ID、
257,368／346,050（74.373%，未决 88,682）。14 个原文均为 `approved`
且审核元数据指向本批目标 ID；2,701 个目标 FK 全部正确。两库全部
173,025 盘棋的 346,050 个黑白原始姓名逐行与冻结清单相同。该排名段
另有 6 个暂缓原文／1,175 槽仍为 `pending`，其中 `Honinbo Shuei`
存在早于人物出生的记录，未入本批。
