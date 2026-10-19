# 下一包五赛事名称（b，待独立审核）

2026-10-05；生产者 `/root/hide250_review_astra`，配置模型 `gpt-6-astra`。无数据库写入、无自签。

包：`/tmp/kifu-event-next5b-20261005`。PROD/TEST 各 25 pending，errors/write_errors/missing 均为 0；16 conventional，9 translated。直译按已授权 `translated_from_original` 路径保存原文正证与明确方法。两环境目标 ID/原主名相同，10:24 UTC 只读捕获的 15 个保留赛事均无五语名称；复用原 association/catalog 快照。

| ID | cn | tw | jp | ko | en |
|---|---|---|---|---|---|
| 51 | 韩国女子围棋联赛† | 韓國女子圍棋聯賽† | 韓国女子囲碁リーグ | 한국여자바둑리그 | Korean Women's Baduk League† |
| 53 | 台湾棋王赛† | 棋王賽 | 台湾棋王戦† | 대만 기왕전† | Qiwang |
| 70 | NHK杯电视围棋淘汰赛 | NHK杯電視圍棋淘汰賽 | NHK杯 | NHK배 | NHK Cup |
| 66 | LG杯世界围棋棋王战 | LG杯世界圍棋棋王戰 | LG杯世界棋王戦 | LG배 세계기왕전 | LG Cup |
| 65 | 中国围棋名人战 | 中國圍棋名人戰† | 中国囲碁名人戦† | 중국 바둑 명인전† | Mingren |

† 为明确标记的直译，无惯用名断言。

## 来源与同赛事决策

- 51：[韩国棋院女子联赛报道](https://www.baduk.or.kr/news/report_view.asp?news_no=2483) 确认 2015 年开始的韩国女子职业联赛；[日本棋院](https://www.nihonkiin.or.jp/match_news/match_info/2025_5.html) 实见日文名。
- 53：[海峰棋院历届棋王赛](https://www.haifong.org/news/content/5F8593D9A30A1F7EC7DD05EFF299C791) 为 2008 年始办的现代台湾赛事；[林至涵英文维基](https://en.wikipedia.org/wiki/Lin_Chih-han) 的 Qiwang 2010 年亚军与海峰记录相合，区别早期中国围棋会棋王赛。
- 70：[日本棋院 NHK 杯](https://www.nihonkiin.or.jp/match/nhk/065.html)、[CWI](https://homepages.cwi.nl/~aeb/go/games/games/NHK/) 与 [韩国棋院王立诚履历](https://www.baduk.or.kr/record/player_view.asp?pkey=20000028)；简繁为维基实际变体，均指围棋而非将棋 NHK 杯。
- 66：[韩国棋院](https://m.baduk.or.kr/news/B01_view.asp?news_no=719) 明示旧名 LG배 세계기왕전 与后续赞助名连续关系；[日本棋院](https://www.nihonkiin.or.jp/match/lg/011.html) 的旧名、维基简繁和英文列表均为同一 LG 赛事。
- 65：[国家体育总局](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22833930/content.html) 确认人民日报/中国棋院举办的中国名人战；[CWI](https://homepages.cwi.nl/~aeb/go/games/games/CJKMeijin/) 明确区分中国 Mingren、日本 Meijin 与韩国 Myeongin，采用其中中国项。

所有实际正文、HTTP 200、SHA-256、原文片段和 Wiki 修订版在 sources/ 与 research.pending.jsonl。pending 包保留独立审核步骤；直译代码须经主代理审核并部署兼容 importer/reader 后才能入库。

PROD bundle file SHA-256: `e338c0eab4798f93571afd7054f7ee533344d8a1c5b0e7e15daa4e54c769ffce`。

TEST bundle file SHA-256: `d499725de746c587fdbd581b2a6d6c82bdc52aff1efc0390fb14c5e94375df59`。
