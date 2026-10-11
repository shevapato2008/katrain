# 棋手预处理：61–80 名次 15 项双库执行记录

截至 2026-10-04，TEST／PROD 事务预演经独立审查后，已先 TEST 后 PROD 正式写入并全量核验。输入为
[`kifu-player-nonhan-ranks-61-80-exact-allowlist-2026-10-04.json`](kifu-player-nonhan-ranks-61-80-exact-allowlist-2026-10-04.json)，
SHA-256 `1fb53fb5ef8b424f20f36bd4f7615b8c741a5f1b0e4a0de57a2db17ac21555d7`。
导入器沿用 `katrain/web/kifu/catalog_player_nonhan.py` 与
`scripts/kifu_player_nonhan_batch.py`，只增加此清单格式支持。

| 环境 | 冻结计划 SHA-256 | exact raw | 实际新增 FK | 黑／白席位 | 复用 ID／新建 ID |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `22ce659255740ab13721c5c724a5177a1091e6d0e1ad7cdb1dd61373bd37a928` | 15 | 3,534 | 1,643／1,891 | 11／4 |
| PROD | `454dc6645e4ca96716da38ec58494f2d6f5fb540d398d4661a14067520aeabd5` | 15 | 3,534 | 1,643／1,891 | 11／4 |

计划文件分别为 `kifu-player-nonhan-ranks-61-80-plan-test-2026-10-04.json.gz`
和 `kifu-player-nonhan-ranks-61-80-plan-prod-2026-10-04.json.gz`。拟建四个
中文主名“安倍吉辉”“谷宫悌二”“村濑秀甫”“太田雄藏”；TEST 新 ID
分别为 `12359`–`12362`，PROD 为 `6593`–`6596`。11 个复用目录 ID
的现主名均与审核中文名
一致，按环境分别取本地 ID。

逐项核对了冻结与实时盘号、黑白位置、exact raw、日期、对手原文、重复
标记和完整来源链接。全部 3,534 个实时 FK 为空，15 个原文审核行均
`pending` 且元数据为空；导入器排除同原文自对局及对手已指向同一目标
ID 的冲突。事务预演重新捕获全部前像，执行建 ID、回填 FK 和原文审核
映射，核对影响行数后回滚；正式执行沿用相同冻结计划。聚焦 SQLite
测试 5/5 通过。

提交后只读全量复查：TEST 为 3,764 棋手 ID、253,062／346,050 个
席位已有 FK（73.129%，未决 92,988）；PROD 为 3,586 棋手 ID、
254,667／346,050（73.593%，未决 91,383）。15 个原文均为 `approved`
且审核元数据指向本批目标 ID；3,534 个目标 FK 全部正确。两库全部
173,025 盘棋的 346,050 个黑白原始姓名逐行与冻结清单相同。该排名段
另有 5 个暂缓原文／1,178 槽仍为 `pending`，未入本批。
