# 五组历史赛事的中英文异名候选

基于 173,025 盘冻结 EV 清单，关联计划把英文赛事核心和中文结构候选归到五个赛事类型。原始 EV 不改，预选、循环圈和决赛留在原文中，不建赛段类型 ID。五组互不重叠；`Pro Best Ten` 由另一批处理。五组已在 TEST、PROD 分别 dry-run、SHA 门禁执行并抽查。

| 类型 | 来源名举例 | 棋局 | 届期键 | TEST/PROD | PROD 计划 SHA |
| --- | --- | ---: | ---: | --- | --- |
| 日本棋院选手权战 | `Nihon Ki-in Championship`、`NihonKi-inChampionship`、中文 | 1,275 | 22 | 已执行 | `c9bcff7f6077cfbee33d3b691080ccc5c78c7c2305fb62e699a96335d08daaa8` |
| 全日本第一位战 | `All Japan #1`、中文 | 480 | 5 | 已执行 | `5af1b2ccb9ea7676dc9604ae9d6f756958143cc3a3a5ab28bba31c6c4bcd6a7d` |
| 韩国国手战 | `Kuksu`、中文 | 665 | 53 | 已执行 | `3546ac180ab639174f809b83773df6a429cebe9ff636593aced4c170e4418563` |
| 韩国王位战 | `Wangwi`、中文 | 670 | 38 | 已执行 | `edd14f1b9d7285a66fe1d4d616c8a31691ef16840fbf313737fbc2c2e84cdfae` |
| 韩国名人战 | `Myeongin`、中文 | 926 | 47 | 已执行 | `9601807b785d5903105238a4bfe084f476a8ce9d21d9c0f9136a36f13a6d03fd` |

TEST 的冻结清单字节与 PROD 不同，album 集与数量一致，计划 SHA 分别为 `b3d7afa8e54eaff704729d022a5fd660a942240b46932788624ff61de483ba5a`、`68d07784c0124ff34f2cc557bd67172adf274e44927b599b3c56225ec9f29a06`、`47c3af2b6c63b784db4ace5b9862346dbbe634e0a2d7b243500fdb474d844bb0`、`45813c39c9406c06feae204485a9de8c4fb36f386f4ff10ac7a24247dd742f81`、`b4af4caff9d0f431e53bfaa7a933b372af1e6395dcc4b03ba92a3b8038607c05`，顺序同表。执行后 PROD 赛事关联 55,404/173,025，49 类型、1,022 届期。

日本棋院[沿革](https://www.nihonkiin.or.jp/profile/enkaku/)分别记载 1954 年第 1 期棋院选手权与 1970 年第 1 期全日本第一位。[大竹英雄的官方棋历](https://www.nihonkiin.or.jp/player/htm/ki000008.html)记载全日本第一位承接“日本棋院第一位决定战”，后者与日本棋院选手权又是不同赛事。因此这批给选手权、全日本第一位各建独立类型与届期，不把它们并入现行天元战。选手权 73 盘日期/届期冲突，连带同 raw 72 盘留未决；有 3 盘日期不可核，计划只连类型。全日本第一位 480 盘来自第 1–5 期，含早一至两年的预选棋局。

韩国棋院[历史档案](https://archives.baduk.or.kr/archives/history/year.asp?years=1950)与[官方报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=124)分别确认国手战 1956、王位战 1966、名人战 1968 年起办；[名人战历届表](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1105)列出第 34 期 2004 年、第 35 期 2007 年、第 43 期 2015 年及第 44 期 2021 年。计划按这份停办后续办的编号核验名人战，不用公历年份机械推届次。国手 13 盘、王位 22 盘、名人 21 盘缺可核届次，均只连类型；名人另有 7 盘日期冲突及同 raw 8 盘留未决，王位 1 盘留未决。

执行脚本：[import_kifu_historical_event_aliases.py](../../scripts/import_kifu_historical_event_aliases.py)，带 SHA 门禁执行。
