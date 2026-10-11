# 下一包五赛事名称（f，待独立审核）

2026-10-05；生产者 `/root/hide250_review_astra`，配置模型 `gpt-6-astra`。包 `/tmp/kifu-event-next5f-20261005`；无写库、无自签。两环境各 25 pending，errors/write_errors/missing 均 0；10 conventional，15 translated。复用不变 association/catalog；PROD 目标前像 10:40 UTC、TEST 10:42 UTC 均为空。

| ID | cn | tw | jp | ko | en |
|---|---|---|---|---|---|
| 99 | 韩国十段战† | 韓國十段戰† | 韓国十段戦† | 십단전 | Sibdan Cup |
| 38 | 日本王冠战† | 日本王冠戰† | 王冠戦 | 일본 왕관전† | Okan |
| 86 | 中国围棋霸王战† | 中國圍棋霸王戰† | 中国囲碁覇王戦† | 중국 바둑 패왕전† | Bawang |
| 33 | 韩国物价信息杯† | 韓國物價信息杯† | 物価情報杯 | 한국물가정보배 | Prices Information Cup |
| 32 | 日本广岛铝制杯若鲤战† | 日本廣島鋁製杯若鯉戰† | 広島アルミ杯・若鯉戦 | 히로시마 알루미늄배 와카고이전† | Hiroshima-Aluminum Cup |

† 明确标记直接翻译；无当地惯用名断言。32 韩语保留 Wakagoi 专名发音；86 各直接翻译补中国/围棋，区别韩国霸王战。

- 99：[韩国棋院第七期原益杯报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=409) 原文 십단전，指同一原益（Wonik）赞助的十段赛；Wiki 英文正文实际写 **Sibdan Cup**、Wonik Corporation，采用该页面拼写。
- 38：[日本棋院历届王冠战](https://www.nihonkiin.or.jp/match/okan/archive.html) 与 [CWI Okan](https://homepages.cwi.nl/~aeb/go/games/games/Okan/) 对应；CWI 明示仅日本棋院名古屋支部棋手参加。
- 86：[新浪围棋马晓春履历](https://sports.sina.com.cn/star/maxiaochun.shtml) 明示第二届霸王战冠军；Wiki 英文 **Bawang** 位于中国停办赛事段，区别韩国 Paewang。仅在本包 registry `2026-10-05.events-f` 加 `sina-sports-go` 专业来源；原响应字节完整保留，旧页面少量无效 GB2312 字节按响应解码替换，不影响标题、冠军事实或原始 SHA。
- 33：[韩国棋院金志锡履历](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000408) 实际写 한국물가정보배；Wiki 日语、英语实际分别写 **物価情報杯**、**Prices Information Cup**，英文描述 Korean Prices Information Foundation。
- 32：[日本棋院第13回](https://www.nihonkiin.or.jp/match/wakagoi/013.html) 标题 **広島アルミ杯・若鯉戦**；[CWI 第13回](https://homepages.cwi.nl/~aeb/go/games/games/Alum/13/index.html) 实际写 Hiroshima-Aluminum Cup。两页均为 2018 年富士田明彦击败小池芳弘夺冠，可对应为同一赛事。

来源正文、HTTP 200、SHA-256、摘录、Wiki 修订版均在 sources/ 与 research.pending.jsonl。待主代理独立签署及目标库 dry-run。

PROD bundle file SHA-256: `e5216a18e93c65fd809254ce65653eef83a772368c18c98187ffe37755392847`。

TEST bundle file SHA-256: `ce9ba719f9de31ab9fb15f208be274646f02174820e232558ac02565ec13c962`。

