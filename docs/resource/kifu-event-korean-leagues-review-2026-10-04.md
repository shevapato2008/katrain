# 韩国三类职业联赛赛事候选

从冻结的 173,025 盘 EV 清单中，分别归并男子、女子、元老联赛。`韩国围乙`、`韩国围乙联赛` 和新秀/挑战联赛不在这些计划中。原始 EV、队伍、轮次与冠名保留；统一赛事类型，届次单独关联。

| 类型 | 来源名数量 | 棋局 | 届期键 | 仅连类型 | TEST/PROD dry-run | 计划 SHA |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 韩国围棋联赛 | 4 | 2,648 | 17 | 92 | 均通过 | `981ae8e9d66e66677270ba2bbf08aaefcfecc091a328f7d1ca720800a98f81d5` |
| 韩国女子围棋联赛 | 2 | 1,277 | 9 | 0 | 均通过 | `4bbcab9aded4c7c140ece93f3aec16195243fe5fe8a48874d5ab7f3947043e47` |
| 韩国元老围棋联赛 | 3 | 1,122 | 8 | 0 | 均通过 | `e546a040090a681279066ef40a1f34353003ad15e2360833be8a57fd594df4f2` |

韩国棋院记载[男子围棋联赛从 2003 年 Dream League 发展而来](https://m.baduk.or.kr/news/B02_view.asp?news_sum_no=14874)，[2022–2023 赛季进入第 19 年](https://kbleague.baduk.or.kr/media/news_view.asp?db_div=1&news_no=526)。冻结 EV 中较早的纯年份值按 2004 年第 1 期换算，后期明确的第 19、20 届按跨年赛季核对日期；92 盘缺明确届次或日期为 `1900` 占位，只连类型。四种来源名是 `韩国围棋联赛`、`韩国围甲`、`韩国围甲联赛`、`韩国职业围棋联赛`。

韩国棋院记载[女子围棋联赛始于 2015 年](https://m.baduk.or.kr/news/B02_view.asp?news_sum_no=9441)，[元老联赛于 2016 年首次举办](https://m.baduk.or.kr/news/B01_view.asp?news_no=2018)。本批女子 2 种、元老 3 种原名的显式届次与对局日期一致；`韩国平江杯元老联赛`、`韩国扁钢杯元老联赛` 的冠名按原值保留为别名，不另建类型。两组均无自动届次暂缓项。

执行脚本：[import_kifu_korean_leagues.py](../../scripts/import_kifu_korean_leagues.py)。三组已按各自 SHA 门禁依次在 TEST 和 PROD 执行，并核对全部计划棋局链接。上表 SHA 为 PROD 冻结清单；TEST 使用独立冻结清单，计划 SHA 如下：

| 类型 | TEST 已执行计划 SHA-256 | PROD 已执行计划 SHA-256 |
| --- | --- | --- |
| 韩国围棋联赛 | `2ec24aeb390d2dfdaf84abd431ec2acd8717b6539e77d8ca17ea3cf5fd5be343` | `981ae8e9d66e66677270ba2bbf08aaefcfecc091a328f7d1ca720800a98f81d5` |
| 韩国女子围棋联赛 | `762e5a85932260051340489e5185f0d6ef8f638a0df964d72853a9a60c340605` | `4bbcab9aded4c7c140ece93f3aec16195243fe5fe8a48874d5ab7f3947043e47` |
| 韩国元老围棋联赛 | `9d025483c434b5ae95ff24e95bbb335320cb75b7dc2e3b1f3fea7d16efd6d926` | `e546a040090a681279066ef40a1f34353003ad15e2360833be8a57fd594df4f2` |
