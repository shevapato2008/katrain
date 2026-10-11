# 富士通杯与应氏杯世界赛结构审查

状态：**TEST / PROD 已按冻结计划写入**。从两环境各自 post7 冻结清单生成计划；脚本为 `scripts/import_kifu_fujitsu_ing_world.py`。原始 EV 中的选拔地区、预赛、正赛、轮次和番棋局数仍保留在原文，不建立额外赛事类型。

| 世界赛类型 | 棋局 | 届期键 | 仅类型 | TEST 计划 SHA-256 | PROD 计划 SHA-256 |
| --- | ---: | ---: | ---: | --- | --- |
| 富士通杯世界围棋锦标赛 | 818 | 24 | 17 | `9b0be0f6b711566e2ced1063c1fe8c9a21b8604465b5b78a7f273b9282133032` | `b0bc3e028289637e33ec3588ac405274d96a961d88fbc37f0af99f6acb25fcab` |
| 应氏杯世界职业围棋锦标赛 | 428 | 10 | 1 | `ddfe1f23265cd426afa398f7040cb7d0b779d0a7ebb4908e157fa613cf81e26e` | `9dc7abf5a9bc09a4a02ccb3da57f5145ab5375969f9d2d66787179e3c239ec09` |

两库先执行 `database_mode=dry_run`，均无已有关联冲突，再以各自的完整计划 SHA 执行 `--apply`：富士通杯 818 盘、应氏杯 428 盘均完整回填赛事类型；各新增 1 类型和 2 别名。富士通 17 盘、应氏杯 1 盘仅连类型。仅入选 `富士通杯` / `FujitsuCup` 及 `应氏杯` 冠军赛的明确 EV；富士通 U15、友谊赛、纪念/讲解对局共 16 盘，以及应氏杯大学生赛、青少年赛、纪念对局共 9 盘不在计划中。

## 历届核验

- [日本棋院富士通杯历届记录](https://www.nihonkiin.or.jp/match/fujitsu/archive.html)列出第 1 届 1988 年至第 24 届 2011 年。正赛只允许 `1987 + 届数` 年；明确选拔或预选允许前一年。17 盘原值届数和棋谱日期不符合这一范围（多为无预选标记的英文短名），只连赛事类型。
- [海峰棋院应氏杯历届档案](https://haifong.org/game/classes/8AD0F09CC001B8A2EEBBC376AEEAB539)列出第 1 至 10 届，赛程为四年一届，部分决赛跨下一年；预选允许前一年。第 9 届正赛始于 2020 年，但因疫情推迟的决赛于 2023 年举行；两盘 2023 年决赛按[上海市围棋协会赛程公告](https://www.shweiqi.org/App/Web/NewsDetail.aspx?masterIds=20230821104757465487513456433898)关联第 9 届。单独一盘原值只有“应氏杯”，缺届数，仅连类型。

脚本以 exact raw EV 和冻结棋局 ID 制定计划；写入入口在事务内重核全库计数、所选 raw 计数及现有 FK。聚焦测试 `tests/web_ui/test_import_kifu_fujitsu_ing_world.py`：2 passed。
