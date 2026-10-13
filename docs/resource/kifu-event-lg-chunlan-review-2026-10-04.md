# LG 杯与春兰杯世界赛结构审查

状态：**TEST / PROD 已按冻结计划写入**。执行脚本 `scripts/import_kifu_lg_chunlan.py`；两环境分别使用自己的 post7 冻结清单。原始 EV 中的地区选拔、网络预选、轮次和冠名保留，仅统一赛事类型与明确届期。

| 统一类型 | 棋局 | 届期键 | 仅类型 | TEST 计划 SHA-256 | PROD 计划 SHA-256 |
| --- | ---: | ---: | ---: | --- | --- |
| LG杯世界棋王赛 | 1,841 | 30 | 3 | `3608087719334734c2e42dc74b8ff836ab87eca3f27b736241228dbb020e8371` | `78836ebafe934b6f5ec63b938e38be36029952fc2e03b442c4e35dffd26ba447` |
| 春兰杯世界职业围棋锦标赛 | 587 | 15 | 9 | `d724e500f06173c70bda3ddef24e38fb34700a9898df424f323d251bef12e93c` | `e1075bdd62b8e976ae23368b3bf80ca91c8463f5f6337bfbc276d028aa1a7717` |

合计 2,428 盘。两库先 `database_mode=dry_run` 并确认两组无现有 FK 冲突，再按各自计划 SHA 执行 `--apply`；各新建 1 类型，LG 3 个别名、春兰 2 个别名，全部目标棋局已回填类型。LG 3 盘与春兰 9 盘仅关联类型。聚焦测试 `tests/web_ui/test_import_kifu_lg_chunlan.py`：2 passed。

## 历届与边界

- [日本棋院 LG 杯历届记录](https://www.nihonkiin.or.jp/match/lg/archive.html)列出从第 1 届 1996–1997 赛季到第 30 届 2025–2026 赛季；[韩国棋院第 30 届公告](https://www.baduk.or.kr/news/report_view.asp?news_no=5338)确认“朝鲜日报主办、LG 后援”的正式名称。因此 `LG杯世界棋王赛`、`LG杯世界棋王战`、`朝鲜日报LG杯世界棋王战` 和 `LGCup` 按同一世界赛处理，赛季只允许该届起始年或次年。LG 精油杯是另一项韩国国内赛事，`LGRefinedOilsCup`、`韩国LG精油杯` 不纳入；LG 杯周年纪念邀请赛亦排除。三盘无届数的选拔/本赛原值仅连类型。
- [海峰棋院春兰杯历届档案](https://www.haifong.org/game/classes/0D13ACB8AFE22F9BDE07FDAABECD53AA)逐届列出第 1 届 1998 年至第 15 届 2024–2025 年；早期第 1–5 届年份并非严格每两年递增，脚本按逐届起始年核对。地区选拔允许在正赛前一年，跨年决赛可落在下一或下二年；[春兰集团第 14 届赛事页面](https://www.chunlan.com/igo/14th/)亦确认 2022–2023 赛程。九盘缺明确届数的“春兰杯 / 选拔赛 / 第二轮”只连类型。

写入入口在事务内复核冻结原值、总盘数与已有 FK；按环境使用不同计划 SHA 门禁。
