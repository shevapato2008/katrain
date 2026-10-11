# 棋手预处理：非汉字名次 141–160 双库执行记录

2026-10-04 经独立审查批准，按冻结计划先 TEST 后 PROD 正式写入。
输入为 `kifu-player-nonhan-ranks-141-160-exact-allowlist-2026-10-04.json`，
SHA-256 `9c9df1b7e1672f1e63a626b74ec1da3a7d3a38a5aa92ba2ce41a8a58e92e95bb`。

| 环境 | 冻结计划 SHA-256 | exact raw | 新增 FK（黑／白） | 新建 ID | 写入后已连席位／目录 ID |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `996cbc891a5c4496362613418b15b31ee98d57d7861d90c3b883cd044a1493f6` | 17 | 1,601（811／790） | 5 | 261,536／3,781 |
| PROD | `3e6eaf4b69affb36e57b5d4cd485b317022b857ee317408c3840e012dfc874bb` | 17 | 1,601（811／790） | 5 | 263,141／3,603 |

计划文件分别为 `kifu-player-nonhan-ranks-141-160-plan-test-2026-10-04.json.gz`
和 `kifu-player-nonhan-ranks-141-160-plan-prod-2026-10-04.json.gz`。导入器在事务中
重新捕获冻结与实时前像，核对盘号、位置、原文、日期、对手、重复标记、来源链接、
目标目录及现有 FK，再按原文精确写入；影响行数与计划一致。

写入后全量核验：两库各 173,025 盘的 346,050 个黑白原始姓名逐行与冻结
inventory 相同；1,601 个目标 FK 全部指向审核的目录 ID，17 个原文审核行
均为 `approved` 且元数据中的目录 ID 和白名单 SHA 正确。3 个暂缓原文
`Sekiyama Riichi`、`Takahashi Shigeyuki`、`Kubouchi Shuchi`
未列入本次白名单；后者与获准的 `KubouchiShuchi` 同人，仍需单独审查原文归并。
