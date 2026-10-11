# 长尾30个赛事core：第二轮新证据复核

耗时 6.208 分钟，平均 0.207 分钟/core；2026-10-04T14:13:18.643405+00:00 至 2026-10-04T14:19:31.148701+00:00。
本轮由同一研究代理另开新证据复核，不冒称另一名独立审核员。计时不含第一轮5.433分钟、入库、翻译以及后续HOLD追加调查。

赛事类型 exact 候选批准 15；HOLD 15；可安全终态为无赛事 0。类型批准不等于关联/去重批准，metadata HOLD须保留。

## 原SGF字段发现

30份库内golaxy导出SGF均无根EV属性；album.event实际是GN首值标签。它不是独立下载的主办方原始棋谱，GN与GC亦非两份独立来源。多值字段全部用现有SGF.parse_sgf保留。
13份首值为文件名、缩写或日期，后GN/GC给出完整中文赛事上下文；exact game IDs：[142468, 72554, 64645, 125773, 148486, 72254, 139417, 64277, 93118, 135942, 96107, 88111, 29383]。
初筛6份source_label、1份fixture、1份undecidable（共8）全部变为具有具名真实赛事上下文；其余5份缩写赛事也获得原SGF完整名称支持。不是全部通过来源复核。#3、#14、#25从HOLD升级；#8官方赛表消除了round2歧义；#7、#29因严格来源门槛降为HOLD。
另#2补第3期、#15补2017年、#19补“历届”、#26补1987年。

| # | game ID | exact raw | 类型候选 | 类型结论 | metadata |
| --- | --- | --- | --- | --- | --- |
| 1 | 82103 | 第2届台湾UMC联电杯快棋争霸战8强战 | 台湾UMC联电杯快棋争霸战 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 2 | 6753 | 2022日本关西围棋公开赛决赛 | 日本关西围棋公开赛 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 3 | 142468 | KobayashiKoichi(w)_NakanoHironari(b)2000-04-05_a | 日本十段战 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 4 | 72554 | 46jp-10duan-heshansgf | 日本十段战 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 5 | 74482 | 2014世界智力精英运动会女子4-5名战 | 世界智力精英运动会 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 6 | 64645 | 32jp-ming-f-6sgf | 日本名人战 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 7 | 628 | 45届韩国SG名人败者决赛 | 韩国名人战 | HOLD | HOLD |
| 8 | 79620 | 第26期日本女子本因坊战,round2 | 日本女子本因坊战 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 9 | 56109 | 第2届台湾大森杯女子围棋名人赛决赛反则3番棋第1局 | 台湾大森杯女子名人赛 | APPROVE_EXACT_TYPE | HOLD |
| 10 | 125773 | weijia-9-qiuzhangsgf | 中国围棋甲级联赛 | HOLD | HOLD |
| 11 | 9200 | 第1届衢州烂柯杯世界围棋公开赛北美选拔赛决赛 | 衢州烂柯杯世界围棋公开赛 | HOLD | HOLD |
| 12 | 941 | 华锐教育杯2022围乙6浙江云林棋禅-云南体彩4 | 中国围棋乙级联赛 | HOLD | HOLD |
| 13 | 148486 | 2007cn-duan-5-zhoukzhuangysgf | 全国围棋段位赛 | HOLD | HOLD |
| 14 | 72254 | 44jp-10duan-sanhesgf | 日本十段战 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 15 | 74570 | 第2届世界智英会女子快棋季军战 | 国际智力运动联盟智力运动精英赛 | APPROVE_EXACT_TYPE | HOLD |
| 16 | 56156 | 2014太阳谷避暑季四城市围棋赛决赛 | 太阳谷避暑季四城市围棋巅峰对决 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 17 | 23368 | 第2届晋城职业围棋公开赛8强 | 晋城职业围棋公开赛 | HOLD | HOLD |
| 18 | 139417 | 22cn-ty-3-wangwangsgf | 中国天元赛 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 19 | 122955 | 2019韩国英才-女子冠军对抗第5局 | 韩国历届英才战冠军对顶尖女子擂台赛 | HOLD | HOLD |
| 20 | 5114 | 20届韩国KB联赛6轮陕川-元益决胜5局 | 韩国KB围棋联赛 | HOLD | HOLD |
| 21 | 64277 | 61byf-f-6sgf | 日本本因坊战 | HOLD | HOLD |
| 22 | 9957 | 第1届龙华杯世界围棋传奇大师赛决赛 | 龙华杯世界围棋传奇大师赛 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 23 | 93118 | 2kr-gglt-10-lijinsgf | GG拍卖杯元老与女棋手擂台赛 | HOLD | HOLD |
| 24 | 135942 | Tengen80_1.13* | 日本天元战 | HOLD | HOLD |
| 25 | 96107 | 32jp-xrw-kongsongsgf | 日本新人王战 | APPROVE_EXACT_TYPE | CONFIRMED_SCOPE; no DB action |
| 26 | 32858 | 日本十段战.败者 | 日本十段战 | HOLD | HOLD |
| 27 | 88111 | 7kr-xrls-9-piaojinsgf | 韩国新锐连胜最强战 | HOLD | HOLD |
| 28 | 11785 | 2024年“金陵无想杯”全国业余围棋公开赛第四轮 | 金陵无想杯全国业余围棋公开赛 | APPROVE_EXACT_TYPE | HOLD |
| 29 | 31125 | 第3届世界未来之星新锐最强战16强战 | 世界未来之星新锐最强战 | HOLD | HOLD |
| 30 | 29383 | 2004-12-25 | 韩国围棋联赛 | HOLD | HOLD |

## 逐项来源与结论

1. **第2届台湾UMC联电杯快棋争霸战8强战**（exact core `台湾UMC联电杯快棋争霸战8强战`；game 82103）：Organizer report identifies second rapid championship and same player pairing; distinct from 联电杯职业围棋赛.
   来源：https://www.haifong.org/news/content/F3914781A7088AA194160D9AC5EA7463
2. **2022日本关西围棋公开赛决赛**（exact core `2022日本关西围棋公开赛决赛`；game 6753）：Official third edition, 2022 final pairing/date; 2022 retained by parser core is year, not identity.
   来源：https://www.nihonkiin.or.jp/match/k_open/003.html
3. **KobayashiKoichi(w)_NakanoHironari(b)2000-04-05_a**（exact core `KobayashiKoichi(w)_NakanoHironari(b)2000-04-05_a`；game 142468）：GN后值日本第38期十段战；日本棋院同日同棋手同黑白胜负，原文件名可按此exact album补全。
   来源：https://www.nihonkiin.or.jp/match/jyudan/038.htm
4. **46jp-10duan-heshansgf**（exact core `46jp-10duan-heshansgf`；game 72554）：日本棋院档案本赛首轮河野临对山城宏5/31，原SGF后GN明示第46期。赛事年度2008，实际本赛对局2007，分开保存。
   来源：https://www.kifudepot.net/kifucontents.php?id=jVWo0UXmj2PF8k6fakkLlg%3D%3D；https://archive.nihonkiin.or.jp/match/jyudan/046.html
5. **2014世界智力精英运动会女子4-5名战**（exact core `2014世界智力精英运动会女子4-5名战`；game 74482）：Contemporaneous exact date/pairing and placing; edition 4 additionally documented in event history. Do not merge with later IMSA elite games by 智英 abbreviation.
   来源：https://sports.sina.com.cn/go/2014-12-14/17547447128.shtml；https://zh.wikipedia.org/wiki/第四届世界智力精英运动会
6. **32jp-ming-f-6sgf**（exact core `32jp-ming-f-6sgf`；game 64645）：Official schedule: November 1–2, Takao white versus Cho black; shorthand ming-f-6 resolves. DB has start date only.
   来源：https://archive.nihonkiin.or.jp/match/meijin/032.html
7. **45届韩国SG名人败者决赛**（exact core `韩国SG名人败者决赛`；game 628）：原SGF核准同日同配对，但外部仍以二手目录为主；严格门槛下HOLD，不能把两份目录或源内GC视作独立权威。
   来源：https://kifubara.app/zh/players/a42b2257-fad2-4fc5-b978-b76b607239ee?year=2022
8. **第26期日本女子本因坊战,round2**（exact core `日本女子本因坊战,round2`；game 79620）：官方本赛表6/7谢依旻对吉田美香，round2确认为本赛第二轮；不是挑战赛第2局。
   来源：https://www.nihonkiin.or.jp/match/fhoninbo/archive.html；https://archive.nihonkiin.or.jp/match/fhoninbo/026.html
9. **第2届台湾大森杯女子围棋名人赛决赛反则3番棋第1局**（exact core `台湾大森杯女子围棋名人赛决赛反则3番棋`；game 56109）：官方台湾棋院同日同配对同结果确认第2届大森杯女子名人赛，因此仅类型可批准；原GN第1局与官方第2局冲突，所有局序/关联仍HOLD。
   来源：https://taiwangorg.blogspot.com/2019/10/blog-post_24.html
10. **weijia-9-qiuzhangsgf**（exact core `weijia-9-qiuzhangsgf`；game 125773）：后GN与GC明示2001中国围甲第9轮，真实赛事待查；具体日期/对阵尚未外部核准。
11. **第1届衢州烂柯杯世界围棋公开赛北美选拔赛决赛**（exact core `衢州烂柯杯世界围棋公开赛北美选拔赛决赛`；game 9200）：Contemporaneous first-edition roster confirms North American Kevin Yang, but no exact November 1 selector final corroboration. Selection took place in 2022 for event later spanning 2023.
   来源：https://k.sina.com.cn/article_1730866981_672aef25019018aei.html
12. **华锐教育杯2022围乙6浙江云林棋禅-云南体彩4**（exact core `华锐教育杯2022围乙6浙江云林棋禅-云南体彩4`；game 941）：League/year/teams supported; exact Nov21 pairing/round not checked. 6 and 4 are round/board hints, never editions.
   来源：https://www.ttplus.cn/publish/app/data/2022/11/23/449346/os_news.html
13. **2007cn-duan-5-zhoukzhuangysgf**（exact core `2007cn-duan-5-zhoukzhuangysgf`；game 148486）：后GN/GC明示2007段位赛；专业报道当日升段赛第5轮且列两位棋手，但未核准本局配对，半决赛或错误，HOLD。
   来源：https://sports.sina.com.cn/go/2007-07-16/20543044188.shtml
14. **44jp-10duan-sanhesgf**（exact core `44jp-10duan-sanhesgf`；game 72254）：官方本赛期间2005-05-19至2006-01-26；首轮三村智保胜河野临5/26，与SGF吻合。届次44赛事年度2006、对局日期2005独立保存。
   来源：https://igorating.com/compare/rin-kono/tomoyasu-mimura；https://archive.nihonkiin.or.jp/match/jyudan/044.htm
15. **第2届世界智英会女子快棋季军战**（exact core `世界智英会女子快棋季军战`；game 74570）：弈城当日报道2017-12-15该赛事藤泽季军、黑嘉嘉第四；SGF后GN给2017。类型/日期核准，届次2仅原值及历史列表候选，不写届次关联。
   来源：https://sports.sohu.com/20171215/n525382838.shtml；https://zh.wikipedia.org/wiki/2017国际智力运动联盟智力运动精英赛；https://www.sohu.com/a/210719469_509310
16. **2014太阳谷避暑季四城市围棋赛决赛**（exact core `2014太阳谷避暑季四城市围棋赛决赛`；game 56156）：Contemporaneous event feature exact Sept27 final/pairing; one-off event is valid identity, not generic fixture description.
   来源：https://sports.sina.com.cn/go/suncityweiqi2014/
17. **第2届晋城职业围棋公开赛8强**（exact core `晋城职业围棋公开赛8强`；game 23368）：专业原始来源不足；另二手报道丁浩胜赵晨宇，而SGF RE[B+R]表示赵晨宇胜，出现对局结果冲突。类型候选保留、整行HOLD。
   来源：https://m.sohu.com/a/964216341_121609438/
18. **22cn-ty-3-wangwangsgf**（exact core `22cn-ty-3-wangwangsgf`；game 139417）：Exact contemporary edition/date/pairing corroborates cryptic 22cn-ty-3 filename; 3 is round, 22 edition.
   来源：https://sports.sina.com.cn/go/2008-02-02/16193457972.shtml
19. **2019韩国英才-女子冠军对抗第5局**（exact core `2019韩国英才-女子冠军对抗`；game 122955）：2020 retrospective establishes 2019 inaugural event and teams, but exact June1 game5 unverified; seventh 영재 event edition should not automatically become confrontation edition.
   来源：https://sports.sina.cn/others/qipai/2020-07-08/detail-iircuyvk2717641.d.html
20. **20届韩国KB联赛6轮陕川-元益决胜5局**（exact core `韩国KB联赛6轮陕川-元益决胜`；game 5114）：Exact match/day supported, season is 2023–2024. Article says Lee black versus Won white; DB colors reversed. Hold before any album association or dedup decision.
   来源：https://www.ntdtv.com/gb/2024/02/07/a103850093.html
21. **61byf-f-6sgf**（exact core `61byf-f-6sgf`；game 64277）：Official exact pairing/edition confirms shorthand but game6 dated July11–12; DB July10 conflicts. No automatic date correction or duplicate merge.
   来源：https://www.nihonkiin.or.jp/match/honinbo/061.html
22. **第1届龙华杯世界围棋传奇大师赛决赛**（exact core `龙华杯世界围棋传奇大师赛决赛`；game 9957）：深圳政府/龙华区当日官方报道确认首届11月26日决赛马晓春对刘昌赫，马晓春冠军，与原SGF一致。
   来源：https://www.foxwq.com/news/14902.html?lang=th；https://www.epochtimes.com/gb/23/11/28/n14125373.htm；https://www.sz.gov.cn/cn/xxgk/zfxxgj/gqdt/content/post_11005921.html
23. **2kr-gglt-10-lijinsgf**（exact core `2kr-gglt-10-lijinsgf`；game 93118）：后GN/GC明确类型及届次；百科目录同日配对仅旁证，专业/官方原始赛事页未核准，真实赛事HOLD。
   来源：https://zh.wikipedia.org/wiki/GG拍卖杯元老与女将擂台赛
24. **Tengen80_1.13***（exact core `Tengen80_1.13*`；game 135942）：后GN/GC为日本天元战,6th；类型已有原SGF线索，但1980-05-01配对未外部核准；不解读文件1.13*为日期。
25. **32jp-xrw-kongsongsgf**（exact core `32jp-xrw-kongsongsgf`；game 96107）：后GN明示第32期；官方本赛首轮孔令文对松本武久2/1，松本胜，原SGF同日同胜负。
   来源：https://archive.nihonkiin.or.jp/match/shinjin/032.html
26. **日本十段战.败者**（exact core `日本十段战.败者`；game 32858）：Raw clearly names Japanese 十段战; official page confirms identity only, not 1987 edition/date/round. Do not map 1987 blindly to edition25: qualifying cycles cross years.
   来源：https://www.nihonkiin.or.jp/match/jyudan/043.htm
27. **7kr-xrls-9-piaojinsgf**（exact core `7kr-xrls-9-piaojinsgf`；game 88111）：后GN/GC明确名称与届次，已从来源标签改为真实赛事待查；未核准2007-07-02配对与赛事连续性。
28. **2024年“金陵无想杯”全国业余围棋公开赛第四轮**（exact core `“金陵无想杯”全国业余围棋公开赛`；game 11785）：Chinese Go Association report reposted by source establishes exact 2024 event and explicit rename from 金陵杯. Round from raw; no implied edition1 or rename dedup.
   来源：https://blog.19x19.com/archives/2024_04_08_17_15_30_1031
29. **第3届世界未来之星新锐最强战16强战**（exact core `世界未来之星新锐最强战16强战`；game 31125）：原SGF同日同配对与二手棋谱目录吻合；专业报道可确认赛事系列存在但未核准本届本局上下文，HOLD。
   来源：https://kifudepot.net/index.php?event=&move=&page=3&player=%E7%99%BD%E7%8F%BE%E5%AE%87&sort=
30. **2004-12-25**（exact core `2004-12-25`；game 29383）：日期GN后值与GC为2004韩国围棋联赛；rating同日同配对胜负只是旁证，赛事身份尚需官方源。不能终态归类“无赛事”。
   来源：https://www.goratings.org/en/players/267.html

## 最小批量提取流程

1. Read-only snapshot export album_id, album.event, raw exact/core, sgf_content SHA, source_path; current unlinked/unclassified exact scope.
2. Use existing SGF.parse_sgf root.properties; retain every EV/GN/GC/DT/RO/PB/PW/RE/SO value and ordering, including multiple GN values; never take only first GN.
3. Extract proposed named context from later GN values and GC before result/手数 delimiter; retain raw text and field provenance; same-source repetitions do not count independent evidence.
4. Join named candidates only to verified existing event catalog/aliases; emit review JSON with proposed type, explicit edition/year/round and conflicts. Filenames/date-only candidates use the named context for research, not deletion.
5. Review exact match/day/color/result against professional/organizer event source. Approve type separately from edition/round; unresolved conflict HOLD. No translations, association changes or dedup in extraction phase.

所有批准仅限这里列出的 exact game/raw/core 范围；不推广通配别名，不修改原文、日期、黑白或结果，不自动关联、翻译、去重。初轮快照末尾冒号是PostgreSQL合法空xip字段，非占位。

SGF只读完整捕获：kifu-event-longtail-review-2026-10-04-sgf-capture.json（含每份棋谱原文，SHA见清单）。
