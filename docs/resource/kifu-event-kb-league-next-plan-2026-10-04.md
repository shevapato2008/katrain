# 韩国 KB 一级围棋联赛：下一批只读前像计划

状态：**TEST/PROD 均已写入并复查**。依据各环境 post7 冻结清单、2026-10-04 的 live album FK 捕获和韩棋院资料，为尚未关联的 KB 一级联赛原始 EV 冻结 exact raw 与 album ID。计划五列为 `[album_id, 原始 EV, 统一赛事类型, 届期键或 null, date_played]`；原始 EV、队伍及轮次保留。

| 环境 | exact raw | 计划棋局 | 有届期键 | 只连类型 | 计划 SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| TEST | 522 | 3,340 | 1,835 | 1,505 | `6a144c0786bc078b9f71311e3a60f4967a61ca2df6e837bd57162d35ec925687` |
| PROD | 522 | 3,340 | 1,835 | 1,505 | `b40112d431bdf11722a8adcb9bdd853050db2172b1892535deedaefa99103867` |

冻结计划分别为 [TEST](kifu-kb-league-next-test-plan-2026-10-04.json.gz) 和 [PROD](kifu-kb-league-next-prod-plan-2026-10-04.json.gz)，由 [只读计划脚本](../../scripts/plan_kifu_kb_league.py)生成。两个 SHA 不同，因为库存包字节哈希不同；album 五列集合相同。计划要求赛事类型 `韩国围棋联赛` 已存在，不创建新类型或别名。

## 身份、届期和 hold

韩国棋院将 [2022–2023 年比赛](https://kbleague.baduk.or.kr/media/news_view.asp?db_div=1&news_no=526) 与 [2024–2025 年比赛](https://m.baduk.or.kr/news/B01_view.asp?news_no=5352) 称作 KB 国民银行围棋联赛。其 [2018 年总结](https://kbleague.baduk.or.kr/media/news_view.asp?db_div=1&news_no=273)明确该年为第 15 个赛季。因此 2004–2018 年中具有明确年份、日期相符的原值可沿用旧届次键。独立复核发现，原谱的 `2021~2022第19届` 与[韩国棋院对该季“第18季”的报道](https://kbleague.baduk.or.kr/media/news_view.asp?db_div=1&news_no=519)冲突；该赛季的原值全部只连类型，不指定第 19 届。对其余显式第 19、20 届也只在日期与已核赛季吻合时使用原届号。不能从跨年年份机械推导近年届号；2019–2026 年无显式可信届号的原值、聚合值及 `1900-01-01` 占位日期均只连类型。

[韩国棋院 2025–2026 选拔赛公告](https://www.baduk.or.kr/square/board_view.asp?noti_no=4366)独立列出选拔赛赛程，因此 `KB国民银行杯2013韩国联赛预选决赛` 这一 raw 的 **2 盘整组 hold**，须确认它是球员选拔还是一级联赛内的预赛后再定类型。裸 `韩国联赛` 的 **4 盘整组 hold**，因缺 KB、围甲、围棋等身份限定。独立审核还排除 7 盘全明星赛和 18 盘赛季前超快棋探索赛；它们不是常规一级联赛对局。女子、围乙、Future／퓨처、新秀、挑战、选拔及比赛说明词不进入此计划；不以棋手或相近队名扩展 raw 集合。

post7 冻结库存的宽谓词范围共有 1,169 raw／5,954 盘；两库 live 捕获中其中 2,583 盘已连一级联赛类型，538 raw／3,371 盘未连。扣除身份不明确的 2 raw／6 盘及特别赛的 14 raw／25 盘，得到计划 522 raw／3,340 盘。较早的[高覆盖率候选文件](kifu-event-next-high-coverage-candidates-2026-10-04.md)记载 525 raw／3,348 盘；这与本次同一宽谓词的逐 album live 捕获不一致，故本计划以冻结 exact ID 集与重查前像为准，不沿用该聚合数。原先 3,365 盘计划的两个 SHA 已作废，未执行。

## 只读验证与后续门禁

生成后从 TEST、PROD 分别重新读取 `id,event,date_played,event_id,event_edition_id`，对计划 3,340 行逐一核对：五列前像未变化、所选 raw 的完整计数一致、计划行无已有赛事或届期 FK。聚焦测试 `tests/web_ui/test_plan_kifu_kb_league.py` 为 2 passed，独立复核通过。共享导入器在两库实时 dry-run 各确认 `existing_links={}`、原值计数及前像一致、计划 SHA 与上表相符，然后 TEST→PROD 顺序按 SHA 提交，各 `updated_albums=3340`。事后两库重新预演均显示 `existing_links={韩国围棋联赛:3340}`；排除的 25 盘仍无 event/edition FK，误标 2021–2022 第 19 届的棋局没有错误届期关联。类型 FK 各新增 3,340，届次 FK 各新增 1,835。最终只读统计：TEST 80,837／173,025 盘有赛事类型，PROD 81,319／173,025。
