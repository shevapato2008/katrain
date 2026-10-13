# 棋谱赛事长尾计时试验（只读）

生产查询开始：2026-10-04T13:42:49.082434+00:00；结束：2026-10-04T13:48:15.052398+00:00。
30 个 singleton core，5.433 分钟，平均 0.181 分钟/core。SAFE 10，HOLD 20。

生产只读快照：未关联 unclassified 共 62675 局 / 15417 cores；其中单局 cores 9532。
Singleton 定义为当前未关联的棋谱数恰好 1，而非仅有一个原始拼写。

固定种子：`kifu-event-longtail-timed-pilot-2026-10-04-v1`。按 `md5(seed || E'\n' || series_core)`、core C 排序选前 30；完整 SQL 与原始选择数据在 JSON 内。

SAFE 仅表示可供独立复核的赛事类型候选；不等于 edition/round 全字段已权威确认，不授权关联或合并。未独立确认的字段保留原文候选。HOLD 保留所有歧义。计时不含独立复核和入库。未写数据库、未改代码、未翻译、未去重。

| # | 原始赛事值 | 类别 | 中文赛事类型候选 | 决定 |
| --- | --- | --- | --- | --- |
| 1 | 第2届台湾UMC联电杯快棋争霸战8强战 | real_event_type | 台湾UMC联电杯快棋争霸战 | SAFE |
| 2 | 2022日本关西围棋公开赛决赛 | real_event_type | 日本关西围棋公开赛 | SAFE |
| 3 | KobayashiKoichi(w)_NakanoHironari(b)2000-04-05_a | game_fixture_description | — | HOLD |
| 4 | 46jp-10duan-heshansgf | real_event_type | 日本十段战 | SAFE |
| 5 | 2014世界智力精英运动会女子4-5名战 | real_event_type | 世界智力精英运动会 | SAFE |
| 6 | 32jp-ming-f-6sgf | real_event_type | 日本名人战 | SAFE |
| 7 | 45届韩国SG名人败者决赛 | real_event_type | 韩国名人战 | HOLD |
| 8 | 第26期日本女子本因坊战,round2 | real_event_type | 日本女子本因坊战 | HOLD |
| 9 | 第2届台湾大森杯女子围棋名人赛决赛反则3番棋第1局 | real_event_type | 台湾大森杯女子名人赛 | HOLD |
| 10 | weijia-9-qiuzhangsgf | source_label | — | HOLD |
| 11 | 第1届衢州烂柯杯世界围棋公开赛北美选拔赛决赛 | real_event_type | 衢州烂柯杯世界围棋公开赛 | HOLD |
| 12 | 华锐教育杯2022围乙6浙江云林棋禅-云南体彩4 | real_event_type | 中国围棋乙级联赛 | HOLD |
| 13 | 2007cn-duan-5-zhoukzhuangysgf | source_label | — | HOLD |
| 14 | 44jp-10duan-sanhesgf | real_event_type | 日本十段战 | HOLD |
| 15 | 第2届世界智英会女子快棋季军战 | real_event_type | 国际智力运动联盟智力运动精英赛 | SAFE |
| 16 | 2014太阳谷避暑季四城市围棋赛决赛 | real_event_type | 太阳谷避暑季四城市围棋巅峰对决 | SAFE |
| 17 | 第2届晋城职业围棋公开赛8强 | real_event_type | 晋城职业围棋公开赛 | HOLD |
| 18 | 22cn-ty-3-wangwangsgf | real_event_type | 中国天元赛 | SAFE |
| 19 | 2019韩国英才-女子冠军对抗第5局 | real_event_type | 韩国历届英才战冠军对顶尖女子擂台赛 | HOLD |
| 20 | 20届韩国KB联赛6轮陕川-元益决胜5局 | real_event_type | 韩国KB围棋联赛 | HOLD |
| 21 | 61byf-f-6sgf | real_event_type | 日本本因坊战 | HOLD |
| 22 | 第1届龙华杯世界围棋传奇大师赛决赛 | real_event_type | 龙华杯世界围棋传奇大师赛 | SAFE |
| 23 | 2kr-gglt-10-lijinsgf | source_label | — | HOLD |
| 24 | Tengen80_1.13* | source_label | — | HOLD |
| 25 | 32jp-xrw-kongsongsgf | source_label | — | HOLD |
| 26 | 日本十段战.败者 | real_event_type | 日本十段战 | HOLD |
| 27 | 7kr-xrls-9-piaojinsgf | source_label | — | HOLD |
| 28 | 2024年“金陵无想杯”全国业余围棋公开赛第四轮 | real_event_type | 金陵无想杯全国业余围棋公开赛 | SAFE |
| 29 | 第3届世界未来之星新锐最强战16强战 | real_event_type | 世界未来之星新锐最强战 | HOLD |
| 30 | 2004-12-25 | undecidable | — | HOLD |

## 关键歧义

- 大森杯：原始值第1局与台湾棋院第2局并存，变则三番棋先计一胜可能影响编号，不自动统一。
- 本因坊：61byf-f-6sgf 可确认赛事，但 DT 2006-07-10 与官方第6局 7月11–12日冲突，HOLD。
- 韩国KB联赛：赛季 2023–2024 不能写成纯 2024 届；同日决胜局报道与库内黑白身份冲突，HOLD。
- 联电杯快棋争霸战不因共同赞助商而并入联电杯职业围棋赛。
- 2014 世界智力精英运动会与 2017 IMSA 智力运动精英赛不能因“智英会”简称合并。
- 烂柯杯首届选拔年 2022 与本赛 2023 跨年；年份不自动决定届次。
- `Tengen80_1.13*`、`kr-gglt`、`kr-xrls` 等文件标签无法靠缩写强行映射；日期 EV 亦不是赛事类型。

## 每项证据和保留原因

1. **第2届台湾UMC联电杯快棋争霸战8强战** — Organizer report identifies second rapid championship and same player pairing; distinct from 联电杯职业围棋赛.
   来源：https://www.haifong.org/news/content/F3914781A7088AA194160D9AC5EA7463
2. **2022日本关西围棋公开赛决赛** — Official third edition, 2022 final pairing/date; 2022 retained by parser core is year, not identity.
   来源：https://www.nihonkiin.or.jp/match/k_open/003.html
3. **KobayashiKoichi(w)_NakanoHironari(b)2000-04-05_a** — Player/color/date filename describes a game, does not identify event. Do not turn filename into event type.
4. **46jp-10duan-heshansgf** — External SGF root GN/DT/PB/PW confirms shorthand and matchup. Edition 46 is not year 2007.
   来源：https://www.kifudepot.net/kifucontents.php?id=jVWo0UXmj2PF8k6fakkLlg%3D%3D
5. **2014世界智力精英运动会女子4-5名战** — Contemporaneous exact date/pairing and placing; edition 4 additionally documented in event history. Do not merge with later IMSA elite games by 智英 abbreviation.
   来源：https://sports.sina.com.cn/go/2014-12-14/17547447128.shtml
6. **32jp-ming-f-6sgf** — Official schedule: November 1–2, Takao white versus Cho black; shorthand ming-f-6 resolves. DB has start date only.
   来源：https://archive.nihonkiin.or.jp/match/meijin/032.html
7. **45届韩国SG名人败者决赛** — External exact pairing/date/losers final supports raw label; SG sponsor is not separate event identity.
   来源：https://kifubara.app/zh/players/a42b2257-fad2-4fc5-b978-b76b607239ee?year=2022
8. **第26期日本女子本因坊战,round2** — Official history establishes edition 26/year 2007; exact June 7 pairing/round not verified. Literal round2 cannot be treated as challenge-series game 2.
   来源：https://www.nihonkiin.or.jp/match/fhoninbo/archive.html
9. **第2届台湾大森杯女子围棋名人赛决赛反则3番棋第1局** — Official Taiwan academy same date/pairing says final game 2, raw says game 1. A credited initial win may explain numbering, but must preserve both scopes.
   来源：https://taiwangorg.blogspot.com/2019/10/blog-post_24.html
10. **weijia-9-qiuzhangsgf** — weijia suggests Chinese A league, but year/round/identity unverified; do not infer edition from filename number.
11. **第1届衢州烂柯杯世界围棋公开赛北美选拔赛决赛** — Contemporaneous first-edition roster confirms North American Kevin Yang, but no exact November 1 selector final corroboration. Selection took place in 2022 for event later spanning 2023.
   来源：https://k.sina.com.cn/article_1730866981_672aef25019018aei.html
12. **华锐教育杯2022围乙6浙江云林棋禅-云南体彩4** — League/year/teams supported; exact Nov21 pairing/round not checked. 6 and 4 are round/board hints, never editions.
   来源：https://www.ttplus.cn/publish/app/data/2022/11/23/449346/os_news.html
13. **2007cn-duan-5-zhoukzhuangysgf** — cn-duan may indicate grading competition. No reliable exact identity evidence; retain filename and year only.
14. **44jp-10duan-sanhesgf** — Secondary result list confirms May26 2005 pairing as 十段战; edition44 comes only from filename and round unresolved. Needs official/SGF cross-check.
   来源：https://igorating.com/compare/rin-kono/tomoyasu-mimura
15. **第2届世界智英会女子快棋季军战** — Contemporaneous semifinal pairings produce same consolation matchup; 2017 result table corroborates Fujisawa bronze/Hei fourth. Second edition from raw, not collapsed with 2014 SportAccord event.
   来源：https://sports.sohu.com/20171215/n525382838.shtml
16. **2014太阳谷避暑季四城市围棋赛决赛** — Contemporaneous event feature exact Sept27 final/pairing; one-off event is valid identity, not generic fixture description.
   来源：https://sports.sina.com.cn/go/suncityweiqi2014/
17. **第2届晋城职业围棋公开赛8强** — Thirdparty preview gives same Dec12 pairing/quarterfinal. Lack organizer evidence; canonical 全国 qualifier and tournament continuity need review.
   来源：https://m.sohu.com/a/964216341_121609438/
18. **22cn-ty-3-wangwangsgf** — Exact contemporary edition/date/pairing corroborates cryptic 22cn-ty-3 filename; 3 is round, 22 edition.
   来源：https://sports.sina.com.cn/go/2008-02-02/16193457972.shtml
19. **2019韩国英才-女子冠军对抗第5局** — 2020 retrospective establishes 2019 inaugural event and teams, but exact June1 game5 unverified; seventh 영재 event edition should not automatically become confrontation edition.
   来源：https://sports.sina.cn/others/qipai/2020-07-08/detail-iircuyvk2717641.d.html
20. **20届韩国KB联赛6轮陕川-元益决胜5局** — Exact match/day supported, season is 2023–2024. Article says Lee black versus Won white; DB colors reversed. Hold before any album association or dedup decision.
   来源：https://www.ntdtv.com/gb/2024/02/07/a103850093.html
21. **61byf-f-6sgf** — Official exact pairing/edition confirms shorthand but game6 dated July11–12; DB July10 conflicts. No automatic date correction or duplicate merge.
   来源：https://www.nihonkiin.or.jp/match/honinbo/061.html
22. **第1届龙华杯世界围棋传奇大师赛决赛** — Contemporary coverage identifies event and champion final opponent; precise date Nov26 and inaugural edition additionally corroborated by full event report.
   来源：https://www.foxwq.com/news/14902.html?lang=th
23. **2kr-gglt-10-lijinsgf** — kr-gglt abbreviation not safely resolved; number10 could be league round/board. No event mapping.
24. **Tengen80_1.13*** — Tengen80 suggests Japanese Tengen in 1980, but 1.13* could date/position/version and conflicts with DB May1 if read as date. Hold all linkage.
25. **32jp-xrw-kongsongsgf** — jp-xrw may mean Japanese 新人王; numbered filename is insufficient external evidence, round/player romanization encoding ambiguous.
26. **日本十段战.败者** — Raw clearly names Japanese 十段战; official page confirms identity only, not 1987 edition/date/round. Do not map 1987 blindly to edition25: qualifying cycles cross years.
   来源：https://www.nihonkiin.or.jp/match/jyudan/043.htm
27. **7kr-xrls-9-piaojinsgf** — kr-xrls ambiguous newcomer/league abbreviation; names suggest Korean game but no confirmed event. Hold.
28. **2024年“金陵无想杯”全国业余围棋公开赛第四轮** — Chinese Go Association report reposted by source establishes exact 2024 event and explicit rename from 金陵杯. Round from raw; no implied edition1 or rename dedup.
   来源：https://blog.19x19.com/archives/2024_04_08_17_15_30_1031
29. **第3届世界未来之星新锐最强战16强战** — External SGF catalog exact date/pairing/edition/round supports full event identity.
   来源：https://kifudepot.net/index.php?event=&move=&page=3&player=%E7%99%BD%E7%8F%BE%E5%AE%87&sort=
30. **2004-12-25** — EV is only ISO date, matching DT; no event semantics. Date-only value must not become canonical event nor dedup key.

## 成本解释

计时为批次墙钟时间，覆盖生产选择查询到资料整理；平均 0.181 分钟/core，不宣称逐项计时。HOLD 也是完成审核的结果，不冒充已解决。固定 hash 对本次快照可复现，数据库变化后需使用 JSON 固定样本重放。仅抽单局 core，因此不能按游戏数外推整个 62675 局积压。

首次标签12 SAFE/18 HOLD经严格来源门槛更正为10/20（#7、#29尚只依赖二手目录）；本报告计时仅第一轮研究，不含后续复核和入库。后续新证据复核见 kifu-event-longtail-review-2026-10-04.json/.md。
