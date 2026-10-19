# 棋手预处理：21–40 名次中 18 个英文原文执行记录

截至 2026-10-04，TEST／PROD 事务预演经独立审查后，已先 TEST 后 PROD 正式写入并全量核验。输入为
[`kifu-player-nonhan-next18-exact-allowlist-2026-10-04.json`](kifu-player-nonhan-next18-exact-allowlist-2026-10-04.json)，
SHA-256 `7e155806e682fb1346dbe807894d1cf5db07737434e2452bea95f45340a23249`。
导入器沿用 `katrain/web/kifu/catalog_player_nonhan.py` 和
`scripts/kifu_player_nonhan_batch.py`，仅增加此审核清单的格式与槽位数字段支持。

| 环境 | 冻结计划 SHA-256 | exact raw | 实际新增 FK | 黑／白席位 | 复用 ID／新建 ID |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `77754f714711eec8dcdd1b7aa0b94613e384d483008dd73db5106a4edc3573a7` | 18 | 5,416 | 2,575／2,841 | 16／2 |
| PROD | `f13afa8837c54c279da3f36412bd3af8d86ab8eb74bcac58d7001b4c7636814c` | 18 | 5,416 | 2,575／2,841 | 16／2 |

计划文件分别为 `kifu-player-nonhan-next18-plan-test-2026-10-04.json.gz`
和 `kifu-player-nonhan-next18-plan-prod-2026-10-04.json.gz`。两库各自按审核
清单中的本地目标 ID 读取现有中文主名；18 个原文写入前的棋局外键与
原文审核元数据均为空。`Hoshino Toshi` 和 `HashimotoShoji` 分别新建
中文主名“星野纪”“桥本昌二”：TEST ID 为 `12345`／`12346`，PROD
为 `6581`／`6582`。

逐项核对了冻结与实时盘号、黑白位置、exact raw、日期、对手原文、重复
标记及完整来源链接；每个原文的席位数与审定清单一致。程序也检查同原文
自对局和已指向同一目标 ID 的对手 FK。事务预演再次捕获全部前像，执行
建 ID、回填和原文审核映射并校验影响行数，然后回滚；正式执行沿用相同
冻结计划。聚焦 SQLite 测试 3/3 通过。

提交后只读全量复查：TEST 为 3,757 棋手 ID、245,571／346,050
个席位已有 FK（70.964%，未决 100,479）；PROD 为 3,579 棋手 ID、
247,176／346,050（71.428%，未决 98,874）。18 个原文均为 `approved`
且审核元数据指向本批目标 ID；5,416 个目标 FK 全部正确。两库全部
173,025 盘棋的 346,050 个黑白原始姓名逐行与冻结清单相同。
`Yoshida Yoichi`（同音同拼两位职业棋手）和 `Ito Tomoe`（目录三 ID）
共 612 槽继续暂缓，原文审核状态仍为 `pending`。
