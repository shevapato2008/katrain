# 棋手预处理：非汉字名次 121–140 双库执行记录

2026-10-04 经独立审查批准，按冻结计划先 TEST 后 PROD 正式写入。
输入为 `kifu-player-nonhan-ranks-121-140-exact-allowlist-2026-10-04.json`，
SHA-256 `81093337d3ae4ccc2657bdccc795538283fa8e9f2d6795619dad80398abfe9f5`。

| 环境 | 冻结计划 SHA-256 | exact raw | 新增 FK（黑／白） | 新建 ID | 写入后已连席位／目录 ID |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `47919246e265e43e6b0d5ac8024ed97724a3bf8284619847302e52c06f65b0f9` | 16 | 1,896（1,001／895） | 6 | 259,935／3,776 |
| PROD | `172095c37aef0c54f4e89a56d3409ebabc1ab7dd05be2814b415fbe88ae4c824` | 16 | 1,896（1,001／895） | 6 | 261,540／3,598 |

两个环境分别使用 `kifu-player-nonhan-ranks-121-140-plan-test-2026-10-04.json.gz`
和 `kifu-player-nonhan-ranks-121-140-plan-prod-2026-10-04.json.gz`。导入器在事务中
重新捕获冻结与实时前像，核对盘号、位置、原文、日期、对手、重复标记、来源链接、
目标目录及现有 FK，再按原文精确写入；影响行数与计划一致。

写入后全量核验：两库各 173,025 盘的 346,050 个黑白原始姓名逐行与冻结
inventory 相同；1,896 个目标 FK 全部指向审核的目录 ID，16 个原文审核行
均为 `approved` 且元数据中的目录 ID 和白名单 SHA 正确。4 个暂缓原文
`Fujisawa Shuko`、`Inagaki Koichi`、`Yasui Sanchi`、`Shuwa`
未列入本次白名单，其身份／目录冲突继续另审。
