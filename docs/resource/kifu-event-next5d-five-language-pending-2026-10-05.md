# 下一包五赛事名称（d，待独立审核）

2026-10-05；生产者 `/root/hide250_review_astra`，配置模型 `gpt-6-astra`。无数据库写入、无自签。

包：`/tmp/kifu-event-next5d-20261005`。两环境各25 pending，errors/write_errors/missing均0；11 conventional，14 translated。独立registry版本 `2026-10-05.events-d` 仅在既有来源中增加 `tygem-naver` 专业韩文围棋新闻来源。目标名称前像为10:24 UTC只读捕获，复用不变association/catalog。

| ID | cn | tw | jp | ko | en |
|---|---|---|---|---|---|
| 59 | 倡棋杯 | 倡棋杯 | 倡棋杯 | 창치배 | Changqi Cup |
| 55 | 台湾天元赛† | 天元賽 | 台湾天元戦† | 대만 천원전† | Taiwan Tianyuan† |
| 37 | 日本新人王战† | 日本新人王戰† | 新人王戦 | 일본 신인왕전† | Shinjin-O |
| 62 | 日本首相杯争夺战† | 日本首相杯爭奪戰† | 首相杯争奪高段者トーナメント | 일본 수상배 쟁탈전† | Prime Minister's Cup |
| 57 | 韩国围乙联赛† | 韓國圍乙聯賽† | 韓国囲碁フューチャーズリーグ† | 퓨처스리그 | Korean Baduk Futures League† |

† 明确标记直译，无惯用名断言。

- 59：[国家体育总局棋牌中心](https://www.sport.gov.cn/qpzx/n5387/c852216/content.html) 原文倡棋杯；简繁、日、英赛事列表实见用名，韩文取[Tygem赛事报道](https://tygem.game.naver.com/news/news/view.asp?find=&findword=&gubun=&pagec=28&seq=7780)的창치배。该赛事为2004年开始的中国职业锦标赛，区别国际应氏杯。
- 55：[海峰天元赛沿革](https://www.haifong.org/game/classes/714DC4215C0E56E366421FBA2ABB6FC0) 确认台湾系列，英文用明确直译 `Taiwan Tianyuan`，与中国 Tianyuan 区分。
- 37：[日本棋院新人王战](https://www.nihonkiin.or.jp/match/shinjin/050.html) 与[CWI Shinjin-O](https://homepages.cwi.nl/~aeb/go/games/games/Shinjin-O/)；中韩直译加日本限定以区别他国新人赛。
- 62：[日本棋院沿革](https://www.nihonkiin.or.jp/special/100anniversary/index.html) 与 [CWI 首相杯](https://homepages.cwi.nl/~aeb/go/games/games/Minister/) 为1957–1981年日本高段者锦标赛，区别韩国总理杯业余赛。
- 57：[韩国棋院2014年赛事制度说明](https://m.baduk.or.kr/news/B01_view.asp?news_no=942) 正文明示二队联赛（2 군 리그），2012年始设 Rock Star，2014年更名Futures。中文/繁体对二队联赛做功能性标题翻译，保留现有目录围乙名称；日英保留Futures。2013/2014原始event样本与沿革对应，未改变任何FK。

所有抓取正文、HTTP 200、SHA-256、片段与Wiki修订版均已保存；待主代理独立审核后目标数据库dry-run。

PROD bundle file SHA-256: `6f2c5d0d993076e8b94a194492f47f0a52f18742faf85a0ffb9520ad48c80b8b`。

TEST bundle file SHA-256: `6fb98ba958555e775ae212b6923c48c563519485acdfce747f791db97b973701`。
