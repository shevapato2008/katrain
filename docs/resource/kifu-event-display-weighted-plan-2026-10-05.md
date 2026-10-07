# 赛事中文显示加权批量计划（只读候选）

PROD与TEST分别读取全库聚合；不逐局考证身份。原始EV、年份、轮次、赛事ID保持原样，仅提出展示文字覆盖。所有候选未自动批准，写库/译表写入0。

|环境|总局数|非空赛事|已有关联|拟中文显示覆盖|总局覆盖率|非空赛事覆盖率|SGF exact album补充|冲突HOLD|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|PROD|173025|170214|104737|163337|94.40%|95.96%|6560|0|
|TEST|173025|170214|104255|162928|94.16%|95.72%|6560|0|

## 最小集合解释

共同使用目录映射和清洗规则，避免人工处理15k core。按互不重叠棋局加权排序的目标显示名称数：
- PROD: {"0.8": 421, "0.9": 2203, "0.95": null}（null表示当前候选总覆盖达不到该比例）。这不是外部考证通过数，也不是映射raw行数。
- TEST: {"0.8": 435, "0.9": 2322, "0.95": null}（null表示当前候选总覆盖达不到该比例）。这不是外部考证通过数，也不是映射raw行数。

## 批量应用顺序

- First use existing event_id -> Chinese catalog canonical, cleaned for display only.
- For remaining labels use exact catalog aliases / established linked core only when one display target.
- Clean already Chinese raw/core conservatively: remove leading year/edition and terminal stage/round only; preserve country, gender, event type.
- Use researched exact non-Chinese core mappings for display, without creating identity aliases.
- Apply supplementary GN/GC names as exact album_id + SGF SHA guarded display overrides; do not promote filename aliases.
- On disagreement or unmapped text keep original event label; preserve original EV, date, round and all identity fields.
- Use one versioned local display mapping artifact + optional per-album overrides consumed at read time; rollout TEST first and compare weighted totals, then PROD. No translation table migration needed.

## 重点非中文 exact core 候选

|core|中文显示候选|来源|
|---|---|---|
|Castle Game|御城碁|[来源](https://en.wikipedia.org/wiki/Oshirogo)|
|Hoensha game|方圆社对局|[来源](https://zh.wikipedia.org/wiki/方圓社)|
|Nihon Ki-in #1|日本棋院第一位决定战|[来源](https://zh.wikipedia.org/wiki/日本棋院第一位決定戰)|
|Kiseong|韩国棋圣战|[来源](https://goldengibo.baduk.or.kr/info/info_view.asp?cmpt_code=1108&cmpt_th=12&cmpt_tnmt_div=1)|
|10-game match|十番棋|[来源](https://gomagic.org/go-term/jubango/)|
|Tokyo Shinbun Cup|日本东京新闻杯|[来源](https://homepages.cwi.nl/~aeb/go/games/games/TokyoShinbun/index.html)|

## 高频目标显示与覆盖（PROD前40）

|显示候选|局数|累计总局覆盖|
|---|---:|---:|
|中国围棋甲级联赛|13057|7.55%|
|大手合|8181|12.27%|
|韩国围棋联赛|6255|15.89%|
|日本本因坊战|5736|19.20%|
|日本十段战|4602|21.86%|
|日本王座战|4033|24.20%|
|日本棋圣战|3682|26.32%|
|日本名人战|3602|28.41%|
|日本天元战|3083|30.19%|
|日本龙星战|2718|31.76%|
|中国女子围棋甲级联赛|2680|33.31%|
|日本碁圣战|2433|34.71%|
|三星杯世界围棋大师赛|2287|36.03%|
|台湾棋王赛|2061|37.23%|
|韩国女子围棋联赛|1999|38.38%|
|LG杯世界棋王赛|1860|39.46%|
|日本NHK杯电视围棋锦标赛|1852|40.53%|
|中国围棋名人战|1785|41.56%|
|日本旧名人战|1696|42.54%|
|中国围棋天元战|1648|43.49%|
|韩国元老围棋联赛|1541|44.38%|
|日本棋院选手权战|1426|45.21%|
|日本职业十杰战|1396|46.01%|
|台湾天元赛|1287|46.76%|
|中国倡棋杯|1263|47.49%|
|日本新人王战|1252|48.21%|
|日本首相杯争夺战|1137|48.87%|
|韩国围乙联赛|1061|49.48%|
|台湾友士杯十段赛|1003|50.06%|
|台湾海峰杯职业围棋赛|980|50.63%|
|韩国名人战|959|51.18%|
|日本SGW杯中庸战|949|51.73%|
|日本女子本因坊战|945|52.28%|
|农心辛拉面杯世界围棋团体赛|922|52.81%|
|段位赛|911|53.33%|
|中国围棋段位赛|902|53.86%|
|日本女子名人战|868|54.36%|
|中日围棋对抗赛|864|54.86%|
|台湾国手赛|844|55.34%|
|富士通杯世界围棋锦标赛|818|55.82%|

## 保留原文/HOLD高频项（PROD，补SGF之后）

剩余原文/缺EV的实际数量见JSON retain_original_nonblank_games / retain_original_or_blank_games。当前0个补充标签互相冲突并不表示没有未映射项。以下为exact album补充后的剩余分布。

|core|局数|
|---|---:|
|None|2811|
|GNUGo3.8|1160|
|All-Japan Women's Championship|151|
|Nihon Saikyo|116|
|P'aewang|75|
|ChinaCityLeagueA|68|
|Hayago Meijin|63|
|TaiwanPromotionTournament,2000|60|
|20-game match|58|
|Saikoi|57|
|PaedalWang|57|
|Hayago Championship|50|
|SaikoiLeague|48|
|NECCup|43|
|21-game match|42|
|HayagoChampionship|40|
|Ch'oegowiFinal|37|
|Shinei|36|
|BCCardCup|35|
|Honinbo Title|32|
|KoreaPromotionTournament,1998|31|
|TokyoShinbunCup|31|
|NTV Women's Meijin|30|
|Joshiki Teai|29|
|BacchusCup|28|

## Artifact与验证

同目录`.py`可从两份capture JSON与enriched gzip复现。两个候选gzip逐raw保存来源/覆盖、逐album保存GN/GC与SGF SHA；冲突保留原文。两环境读取事务均READ ONLY、ROLLBACK，源查询不读取全库SGF、不加写锁。清洗规则与新增史料映射仍需快速抽样确认后应用。


## 2026-10-08 执行检查点

云端/设备语言展示和棋手跨语言精确搜索已实测，Kiosk设置返回保留搜索已部署。翻译不中断；475后整卡五语覆盖111013/173025。下一步按已冻结的字面原文继续BA12（45盘）、BB15（58盘）、BE5（42盘），每批先实际owner审核，再以真实afterimage绑定译文；不把字面标题翻译变成未经证据支持的赛事实体或队伍身份。棋手按高频且身份/中文主源明确的五人并行调查，每五人由主窗口TEST→PROD写入及统计。ret78来源继续，最终binding等待前一SQL批次结束以使用实际catalog和已核名称快照。
