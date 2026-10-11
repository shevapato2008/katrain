# 棋谱赛事关联纠错：37 盘

2026-10-04 在已导入赛事的独立复核中发现两组误关联。只撤销赛事类型或届次 FK；原始 SGF、原始 EV、棋局日期、棋手关联均未改。

| 组别 | TEST | PROD | 处理 |
| --- | ---: | ---: | --- |
| 6 盘关西棋院第一位纪念对局、1 盘 LG 杯特别对局 | 7 | 7 | 类型及届次均置空；原始说明不是正赛届次 |
| 早期日本头衔赛的明显届次日期冲突 | 30 | 30 | 全部撤销届次；其中 27 盘保留确定的赛事类型，3 盘类型也暂缓 |

第二组逐盘判断见[复核记录](kifu-japanese-title-calendar-conflicts-30-review-2026-10-04.md)。所依据的官方历届表包括[十段](https://www.nihonkiin.or.jp/match/jyudan/archive.html)、[棋圣](https://www.nihonkiin.or.jp/match/kisei/archive.html)、[名人](https://www.nihonkiin.or.jp/match/meijin/archive.html)、[本因坊](https://www.nihonkiin.or.jp/match/honinbo/archive.html)、[王座](https://www.nihonkiin.or.jp/match/oza/archive.html)和[天元](https://www.nihonkiin.or.jp/match/tengen/archive.html)。不根据年份猜补新的届次。

两套[7 盘精确前像](kifu-event-exhibition-seven-exact-rollback-2026-10-04.json)和[30 盘精确前像](kifu-japanese-title-calendar-conflicts-30-exact-rollback-2026-10-04.json)先经独立只读审核，再分别在 TEST、PROD dry-run，最后按 TEST → PROD 顺序执行。计划 SHA 分别为 `c7dfb7cde58b16348730a615bce6543d363afe98e1059be4a4bf0b9a6f6ac165`、`55890fe38a5913b31b73e665fb6dfdb58e595264c3e38d33f7d83094b4e58a2f`。事务执行器逐盘验证 ID、原始 EV、日期、原类型及届次前像，锁表后才写入；任一漂移则整批失败。

执行后对 TEST、PROD 的 30 盘重新读取并逐盘与执行前比对：原始 EV 和日期全部一致，30 个届次 FK 全为空，27 个类型 FK 保留，3 个类型 FK 清空。7 盘批次各环境均返回 `updated_albums=7`，30 盘批次各环境均返回 `updated_albums=30`。聚焦回归检查：`pytest -q tests/web_ui/test_import_kifu_event_types.py tests/web_ui/test_import_kifu_four_titles.py tests/web_ui/test_import_kifu_lg_chunlan.py tests/web_ui/test_rollback_kifu_event_links_exact.py`，12 passed。

这次纠错不代表全库赛事预处理完成。PROD 随后的只读统计为赛事类型关联 73,795／173,025 盘、届次关联 72,200／173,025 盘；其余仍按来源和身份逐批核实。
