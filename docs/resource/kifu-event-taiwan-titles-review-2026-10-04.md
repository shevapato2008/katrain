# 台湾四组赛事的“赛 / 战”异名候选

基于冻结的 173,025 盘原始 EV，四组赛事各保留一个类型 ID；“赛 / 战”作为别名，届次另建键，赛段和队伍只保留在原始 EV。各组来源名、届次与对局日期已逐盘核对。

| 类型 | 棋局 | 届期键 | 仅连类型 | TEST dry-run | PROD dry-run | 计划 SHA |
| --- | ---: | ---: | ---: | --- | --- | --- |
| 台湾棋王赛 | 1,069 | 17 | 0 | 通过 | 通过 | `063168f6fa01616925742882cb209afb99d403288e9d72bd6d1aa90dfb43f406` |
| 台湾国手赛 | 842 | 21 | 3 | 通过 | 通过 | `e4169aedacee673b41ff139e9bd018c4fb3dcd4c9a2762115a0c94b9dbc7c3b1` |
| 台湾天元赛 | 529 | 23 | 0 | 通过 | 通过 | `7ae45c871f046d00958a75355067a5e43783082dcda1fec7f4af044c1677c70b` |
| 台湾中环碁圣赛 | 578 | 13 | 0 | 通过 | 通过 | `f05082e9bff39a573ceb078154e2b3c6b7780ef29a8051644c849e9bcfa60219` |

海峰棋院分别列出[棋王赛历届赛程](https://www.haifong.org/game/classes/AF702E6E9FED2AF72DB9109146E2EB41)、[国手赛历届赛程](https://haifong.org/game/classes/A822120A9D857AB7AC88180F76BF3529)与[天元赛历届赛程](https://haifong.org/game/classes/714DC4215C0E56E366421FBA2ABB6FC0)。棋王第 1 届在 2008 年，第 2–4 届有跨年预选；国手第 1 届在 2005 年，天元第 1 届在 2002 年。国手有 3 盘原值届次与日期冲突，计划保留赛事类型链接，届次链接留空，等待原始数据修正。

[海峰棋院中环碁圣赛说明](https://www.haifong.org/game/classes/480E360835EAB350F93094AAECD2A797)明确写出该赛 2013 年由旧碁圣战更名、**届次重新从第 1 届计算**。因此本组第 1–13 届单列，不与 2008 年创办的旧碁圣战或中环杯共用届次 ID。

执行脚本：[import_kifu_taiwan_titles.py](../../scripts/import_kifu_taiwan_titles.py)。四组已按各自 SHA 门禁依次在 TEST 和 PROD 执行，并核对全部计划棋局链接。上表 SHA 为 PROD 冻结清单；TEST 使用独立冻结清单，计划 SHA 如下：

| 类型 | TEST 已执行计划 SHA-256 | PROD 已执行计划 SHA-256 |
| --- | --- | --- |
| 台湾棋王赛 | `4f4b18242934551d0f17855d734a10e46523ff04e35e138d465a3591aa9fe9b2` | `063168f6fa01616925742882cb209afb99d403288e9d72bd6d1aa90dfb43f406` |
| 台湾国手赛 | `e3de9293976fd3150108d8e9361f8f71abe289baa21e5a9830e5f46324c915bf` | `e4169aedacee673b41ff139e9bd018c4fb3dcd4c9a2762115a0c94b9dbc7c3b1` |
| 台湾天元赛 | `7d5b1f41e4cb38a10c04f8229cb96cb39e03697babe296bd896679eaf77678ca` | `7ae45c871f046d00958a75355067a5e43783082dcda1fec7f4af044c1677c70b` |
| 台湾中环碁圣赛 | `95de0dc0a9ce4aa1403fcaeacba96779dbad896c0efbfd2ca3b6e9cdad0fbcde` | `f05082e9bff39a573ceb078154e2b3c6b7780ef29a8051644c849e9bcfa60219` |
