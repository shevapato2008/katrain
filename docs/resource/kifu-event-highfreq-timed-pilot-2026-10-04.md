# 高频未关联事件预处理计时试点（只读）

- 抽样：PROD 中 `event_id IS NULL` 且类别 `unclassified_pending`，按 occurrence 数排序，跳过已有独立事件决定范围后取前 20 个 core。
- 总计：20 cores，458 个 raw，4195 盘。可安全分类 6 个 core / 952 盘；其余 HOLD。
- 计时：首个生产库查询 2026-10-04 13:42:12 UTC；结束打包 13:50:20 UTC，共 8.13 分钟 / 20 core = 0.41 分钟每 core（含筛选、查询和查找）。
- 边界：只读重复读事务；无数据库写入、代码改动、权威身份批准或翻译。年份、届次、轮次仅提取为原始字段结构，不批准关联。

| 排名 | core | 盘数 | raw数 | 结论 | 中文类型（仅安全分类项） |
|---:|---|---:|---:|---|---|
| 1 | `Castle Game` | 539 | 1 | HOLD | generic game label; not enough competition identity evidence |
| 2 | `团体赛` | 324 | 1 | HOLD | bare team-game descriptor; no country or competition identity |
| 3 | `中国围棋段位赛` | 294 | 39 | HOLD | multiple rank/promotion formats may share wording; no source ties all 39 exact values to one series |
| 4 | `友情杯` | 271 | 7 | HOLD | generic Friendship Cup label; sponsor/organizer and event scope unresolved |
| 5 | `围棋甲级联赛` | 267 | 42 | HOLD | bare league label omits country and league tier; explicit China/Korea variants must remain separate |
| 6 | `10-game match` | 245 | 1 | HOLD | format description, not a unique event identity |
| 7 | `招商银行杯电视快棋赛` | 222 | 17 | CLASSIFY | 中国电视围棋快棋赛 |
| 8 | `2020中国国家队积分大循环` | 213 | 13 | HOLD | national-team internal round robin / ranking fixture; no independent tournament identity evidence |
| 9 | `2015同里杯中国升段赛` | 177 | 12 | CLASSIFY | 同里杯中国围棋升段赛 |
| 10 | `Tokyo Shinbun Cup` | 175 | 11 | HOLD | real historical tournament established, but no confident Chinese canonical form from consulted sources; do not infer editions from bare English ordinal strings |
| 11 | `中日围棋友谊赛` | 170 | 65 | HOLD | label spans early exchanges and later friendship matches; scope can overlap broader exchange series |
| 12 | `中日对抗赛` | 169 | 1 | HOLD | generic bilateral match wording; no unique series identity |
| 13 | `Kiseong` | 152 | 16 | HOLD | romanized Korean event fragment ambiguous; no authoritative mapping found |
| 14 | `All-Japan Women's Championship` | 151 | 16 | HOLD | historical event is plausible, but exact event type and confident Chinese canonical name unresolved |
| 15 | `P'aewang` | 147 | 25 | CLASSIFY | 韩国霸王战 |
| 16 | `2013职业棋手精英赛` | 137 | 1 | HOLD | single-year named event label may be selection/training program; no organizer source found |
| 17 | `韩国GG拍卖杯绅士淑女擂台赛` | 137 | 137 | CLASSIFY | 韩国GG拍卖杯绅士淑女擂台赛 |
| 18 | `2014日本国家队新浪网络训练赛` | 136 | 1 | HOLD | explicit online national-team training session/fixture, not shown to be a public competition series |
| 19 | `日本女子名人战败者复活赛` | 135 | 47 | CLASSIFY | 日本女流名人战；败者复活赛保留为阶段/轮次属性 |
| 20 | `日本幽玄杯精锐循环赛` | 134 | 5 | CLASSIFY | 日本幽玄杯精锐联赛 |

## 核心判断

- 赛事类型可安全识别：招商银行杯电视快棋赛 → 中国电视围棋快棋赛；同里升段赛；韩国霸王战；韩国 GG 拍卖杯绅士淑女擂台赛；日本女流名人战的败者复活阶段；日本幽玄杯精锐联赛。
- 赛事类型名不等于逐盘身份批准。所有原文保留精确 year/edition/round spans；本试点没有 event FK 或 edition FK 提案。
- 主要误合并陷阱：裸“围棋甲级联赛”不能并到中国男子围甲；“友情杯”是泛称；“团体赛”与“10-game match”是格式描述；“中日围棋友谊赛”可能覆盖多个双边交流阶段，不能与中日擂台赛或常规对抗赛并成一类。
- `2015同里杯中国升段赛`原文届次/轮次单独保留；“中国电视围棋快棋赛”的招商银行冠名只支持这一家族，不可仅凭共同快棋字样吞并其他CCTV/中信赛事原文。

## 来源

- 中国围棋电视快棋赛沿革：[赛事专页](https://zh.wikipedia.org/wiki/中国电视围棋快棋赛)。
- 同里升段赛：[2025年同里杯赛事报道](https://www.ttplus.cn/publish/app/data/2025/11/17/573593/os_news.html)。
- 日本东京新闻杯历史范围：[职业棋谱专题](https://homepages.cwi.nl/~aeb/go/games/games/TokyoShinbun/index.html)（研究了身份但中文 canonical 暂 HOLD）。
- 幽玄杯终止于第4回：[日本棋院官方档案](https://www.nihonkiin.or.jp/match/u-gen/001.html)。
- GG 拍卖杯赛事阶段与届次：[野狐围棋赛事报道](https://www.foxwq.com/news/13421.html)。
- 日本女流名人战官方历届记录：[日本棋院](https://www.nihonkiin.or.jp/match/fmeijin/index.html)。
- 中日交流类型边界：[历史回顾](https://www.sohu.com/a/257181592_820343)。
- 韩国霸王战：[职业围棋档案](https://kifubara.app/tournaments/1f7c04ae-8849-40df-ae17-5197a9e6f85f)。

- JSON 中逐 core 保存所有 exact raw、occurrences 和 parser component spans，便于复查。

- JSON SHA-256: `b20ae1dbfbc6edc337eafa5baf1fbe382c291bcd6875e0c5145b464bf56176cb`.
