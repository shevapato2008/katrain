# high5b：五赛事五语待审核（2026-10-05）

Producer `/root/event10_review_apply` / `gpt-6-astra` / max。16 格有当地直接用例；9 格明确按原文翻译。全部 pending；无 DB 写入。

| ID | 赛事 | 非重复可见棋局/环境 | cn | tw | jp | ko | en |
|---|---|---:|---|---|---|---|---|
| 79 | 台湾友士杯十段赛 | 1002 | [友士杯十段赛](https://www.haifong.org/news/content/5C0B8E819C04BC5F1D554375C86715E1)（直译） | [友士盃十段賽](https://www.haifong.org/news/content/5C0B8E819C04BC5F1D554375C86715E1) | [友士杯十段戦](https://www.use.com.tw/jp/news-detail/26031901/) | [우사배십단전](https://tygem.game.naver.com/news/news/view.asp?seq=36914) | [Shiduan](https://gotoeveryone.k2ss.info/news/tw/sd/14/) |
| 71 | 日本SGW杯中庸战 | 949 | [日本SGW杯中庸战](https://www.nihonkiin.or.jp/match/sgw/004.html)（直译） | [SGW杯中庸戰](https://www.haifong.org/news/content/B8F68BEAAB5C1D8C87ABF1C125EB9AC1) | [SGW杯中庸戦](https://www.nihonkiin.or.jp/match/sgw/004.html) | [SGW배 중용전](https://www.nihonkiin.or.jp/match/sgw/004.html)（直译） | [SGW Cup](https://homepages.cwi.nl/~aeb/go/games/games/SGW/) |
| 31 | 台湾海峰杯职业围棋赛 | 943 | [海峰杯职业围棋赛](https://www.haifong.org/news/content/77362F227C21AD9CBA6AFF7344E1440B)（直译） | [海峰盃職業圍棋賽](https://www.haifong.org/news/content/77362F227C21AD9CBA6AFF7344E1440B) | [海峰杯プロ囲碁戦](https://www.haifong.org/news/content/77362F227C21AD9CBA6AFF7344E1440B)（直译） | [해봉배 프로바둑대회](https://tygem.game.naver.com/news/news/view.asp?seq=38953) | [Haifong Cup](https://gotoeveryone.k2ss.info/news/tw/hc/7/) |
| 49 | 韩国名人战 | 926 | [韩国名人战](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1105)（直译） | [韓國名人戰](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1105)（直译） | [韓国名人戦](https://www.igoshogi.net/igo/korea_ryusei/) | [한국 명인전](https://www.baduk.or.kr/game/game_view.asp?cmpt_code=1105)（直译） | [Myeongin](https://gotoeveryone.k2ss.info/news/kr/mi/47/) |
| 68 | 农心辛拉面杯世界围棋团体赛 | 922 | [农心辛拉面杯世界围棋团体锦标赛](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c30042669/content.html) | [農心辛拉麵盃世界圍棋團體錦標賽](https://baduk.or.kr/news/report_view.asp?news_no=5932)（直译） | [農心辛ラーメン杯 世界囲碁最強戦](https://www.nihonkiin.or.jp/match/noshin/027.html) | [농심신라면배 세계바둑최강전](https://baduk.or.kr/news/report_view.asp?news_no=5932) | [Nongshim Cup](https://www.nihonkiin.or.jp/english/topics/03/topics2003_01.htm) |

TEST、PROD 均覆盖 4,742 盘。仅绑定现有 owner 和空 name 前像；保留既有棋局关联与 raw EV。

包目录：`/tmp/kifu-event-next-high5b-20261005`。两环境 `bundle.pending.json`、`target-preimages.json`、`validation.pending.json`；共享 `registry.json`、`research.pending.jsonl`、`sources/manifest.json`。

## 直译说明

- `79-cn`：Convert the official Traditional Chinese event name to Simplified Chinese; 盃→杯, 賽→赛. Preserve 友士 and 十段.
- `71-cn`：Preserve the official SGW and 中庸 title; convert 戦→战 and add Japan from the official Nihon Ki-in event identity.
- `71-ko`：Retain the Latin sponsor initials SGW; translate 杯 as 배 and 中庸戦 as 중용전. 中庸 is the established Korean Sino-Korean word 중용 (doctrine of the mean), not 中用.
- `31-cn`：Simplify the official Traditional Chinese name, preserving the professional-event qualifier 職業圍棋賽→职业围棋赛 and 海峰.
- `31-jp`：Preserve the source proper name 海峰; render 盃職業圍棋賽 as 杯プロ囲碁戦, preserving the professional competition scope.
- `49-cn`：Render the Korean event title 명인전 as 名人战 and retain an explicit Korea qualifier to distinguish Chinese and Japanese namesakes.
- `49-tw`：Render the Korean event title 명인전 as 名人戰 with an explicit 韓國 qualifier.
- `68-tw`：Render the officially identified Nongshim Shin Ramyun international team championship in Traditional Chinese using 農心/辛拉麵/世界圍棋團體錦標賽 and Taiwan-style 盃. The Chinese sport authority supplies the corresponding published Chinese full title; this cell is explicitly editorial translation, not claimed local conventional evidence.
- `49-ko`：Add the explicit country qualifier 한국 to the native official title 명인전, identifying the Korean Myeongin competition and distinguishing it from the Japanese Meijin title whose approved Korean rendering also uses 명인전. This is a qualified translation from the captured original, not a claim of exact published target usage.

## 身份边界

