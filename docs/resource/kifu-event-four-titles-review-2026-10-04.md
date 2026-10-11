# 四组高频赛事类型与届期审查

状态：**TEST / PROD 已按冻结计划写入**。脚本：`scripts/import_kifu_four_titles.py`。两库使用各自的 post7 冻结清单（各 173,025 盘）；原始 EV 的冠名、地区、赛段、队伍及轮次保留。确有赛事身份差异的旁支不在计划中。

| 统一类型 | 棋局 | 届期键 | 仅类型 | TEST 计划 SHA-256 | PROD 计划 SHA-256 |
| --- | ---: | ---: | ---: | --- | --- |
| 日本首相杯争夺战 | 1,089 | 24 | 1 | `88a52887bcc779df4c56b29beb82b8170c32ee5ff8ad4df53305e9a7cc3cc1e5` | `b899eecfb67dbf32113445c40b0471c35a7381085e54af5032a05b15e53f41d8` |
| 日本关西棋院第一位决定战 | 625 | 60 | 5 | `7871b463b65a9153c36cc1cd0d9a13c60486f46df5d5fff471c7143e3c45b944` | `7883d5bfa8f5e20ddccce45667080a9744a1fd5ac030dfdc40a538bad3bbf62e` |
| 中国龙星战 | 806 | 13 | 0 | `860e8c7a281b40c0af1dc97ba7e38886bc3429b82e16017d0b0cea8079035ca3` | `2bcc7ee09e4d251203eed0920485cc56cc2481538f0407eba107118600636ef6` |
| 中国围棋名人战 | 1,676 | 33 | 24 | `664fe07301ef17fe019077c506e12d6e594647d825cff0a8d4a04a742b9c4249` | `42957dd6ab7b3eeebb9dd7dbb7da8eeda5ea59d7e1828ad5ec1453a2a223fab0` |

四组总计 4,196 盘，TEST/PROD 各组先 `database_mode=dry_run`、确认无现有 FK 冲突，再按各自计划 SHA 执行 `--apply`；各新增 4 个赛事类型，回填 4,196 盘。首相杯仅建带“日本”的全局别名，裸值歧义的一盘未入批。聚焦测试 `tests/web_ui/test_import_kifu_four_titles.py`：2 passed。

## 身份与年份

- 日本棋院[沿革](https://www.nihonkiin.or.jp/special/100anniversary/index.html)及[藤泽秀行官方档案](https://www.nihonkiin.or.jp/player/htm/ki000005.htm)确认首相杯职业赛始于 1957 年第 1 期。中文 `日本首相杯争夺战`、`日本首相杯`、`首相杯` 与英文 `Prime Minister's Cup` 的带届次历史棋谱年份吻合，允许本届比赛跨前后一个日历年。优胜纪念对局和“优胜者对本因坊”已排除；另有一盘无日期、无届次的裸值 `Prime Minister's Cup` 无法判断身份，暂不关联。一盘 `19期首相杯` 的日期为 1981 年，与第 19 期不符，只连类型。
- 关西棋院[第 70 期官方对阵表](https://kansaikiin.jp/subpage/tournamenttable.html)、[1999 年第 43 期棋手档案](https://kansaikiin.jp/kisi_prof/moriyamanaoki.html)确认编号连续性。`Kansai Ki-in 1st Place` 与中文“关西棋院第一位”写法归并。`Kansai Ki-in Championship`、`Kansai Ki-in Top Place`、日本棋院第一位战均不在此计划。5 盘无可核实届次只连类型。
- 中国围棋协会在[第 12 届龙星战预选通知](https://www.foxwq.com/news/11977.html)确认 2021 年届次；[第 13 届官方竞赛规程](https://sports.sina.cn/others/qipai/2023-02-21/detail-imyhmnux6050770.d.html)确认 2023 年届次。国家体育总局[2014 年赛历](https://www.sport.gov.cn/n315/n330/c564313/part/304781.pdf)列出第 5 届“钻石杯”全国围棋龙星战。各届对局年份以逐届核过的 2008–2023 年表匹配，容许预选和决赛跨一年；“龙星战冠军对抗赛”另列，不混入。
- 国家体育总局的[2014 年第 27 届赛历](https://www.sport.gov.cn/n315/n330/c564313/part/304781.pdf)、[第 34 届报道](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c28409003/content.html)及深圳市体育局的[2025 年第 34 届总决赛预告](https://wtl.sz.gov.cn/bsfw/mzwhhd/mzty/content/post_11935217.html)确认中国围棋名人战的持续届次。`Mingren` 英文短名及永城杯、春茧杯、嫘祖杯等冠名均按同一类型处理；后期停赛导致第 33 届落在 2023 年，不做简单逐年推断。24 盘缺届次或日期不合，仅连类型。

首相杯全量原始 EV 核查：含“首相杯”或 `Prime Minister` 的共 185 个精确原值、1,092 次出现，日期和带届次值均落在日本历史职业赛时期，没有发现韩国现代业余赛混入。为防今后跨国家同名，目录只建立 `日本首相杯` 一个别名；`首相杯` / `Prime Minister's Cup` 虽仍按 exact raw 链接历史棋局，**不建全局别名**。

风险/后续：中国名人战还有部分赞助商异名被匹配为棋局原值，但未全部建立可搜索别名；如需扩大目录别名，可在类型落库后另审。所有异常原值留在冻结清单待修正。
