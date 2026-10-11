# 下一包五赛事名称（c，待独立审核）

2026-10-05；生产者 `/root/hide250_review_astra`，配置模型 `gpt-6-astra`。无数据库写入、无自签。

包：`/tmp/kifu-event-next5c-20261005`。两环境各 25 pending，errors/write_errors/missing 均 0；9 conventional，16 translated。目标前像沿用本轮10:24 UTC只读捕获；association/catalog 为既有不变快照。

| ID | cn | tw | jp | ko | en |
|---|---|---|---|---|---|
| 30 | 旧名人战† | 舊名人戰† | 旧名人戦 | 구명인전† | Old Meijin |
| 58 | 中国围棋天元赛 | 中國圍棋天元賽† | 中国囲碁天元戦† | 중국 바둑 천원전† | Tianyuan |
| 52 | 韩国元老围棋联赛† | 韓國元老圍棋聯賽† | 韓国シニア囲碁リーグ† | 시니어바둑리그 | Korean Senior Baduk League† |
| 44 | 日本职业十杰战† | 日本職業十傑戰† | プロ十傑戦 | 일본 프로십걸전† | Asahi Pro Best Ten |
| 45 | 日本棋院选手权战† | 日本棋院選手權戰† | 日本棋院選手権戦 | 일본기원 선수권전† | Nihon Ki-in Championship |

† 明确标记直译，保留赛事原文正证，不断言惯用译名。

- 30：[日本棋院沿革](https://www.nihonkiin.or.jp/profile/enkaku/) 与 [CWI Old Meijin](https://homepages.cwi.nl/~aeb/go/games/games/OMeijin/) 对应读卖时期旧名人赛，区别现代朝日名人赛。
- 58：[国家体育总局](https://www.sport.gov.cn/n20001280/n20745751/n20767274/c22033486/content.html) 实见中国围棋天元赛；英语取[英文棋战列表](https://en.wikipedia.org/wiki/List_of_professional_Go_tournaments)中国段 Tianyuan。台湾天元赛会另保留地区限定，避免同名混淆。
- 52：[韩国棋院首届联赛报道](https://m.baduk.or.kr/news/B01_view.asp?news_no=1862) 确认2016年始办的时任总裁杯元老联赛，取不含年度/赞助前缀的核心 시니어바둑리그。
- 44：[日本棋院保存的1971年棋局](https://www.nihonkiin.or.jp/special/100anniversary/kishi_select/47.html) 实见プロ十傑戦；[CWI](https://homepages.cwi.nl/~aeb/go/games/games/ProBest10/) 实见 Asahi Pro Best Ten，明确1964–1975年系列。
- 45：[日本棋院百年沿革](https://www.nihonkiin.or.jp/special/100anniversary/index.html) 与 [CWI](https://homepages.cwi.nl/~aeb/go/games/games/NKCh/) 对应日本棋院選手権戦；区别后继天元战。CWI 英文实际拼写 Nihon Ki-in Championship。

来源正文、HTTP 200、SHA-256 与片段保存在 sources/；既有 importer 校验结果在各环境 validation.pending.json。等待主代理独立签署和目标数据库 dry-run。

PROD bundle file SHA-256: `a6b9c9a0ce4664727017dd4187531eb7049c95e23afcd4f31467ad97f496ee8a`。

TEST bundle file SHA-256: `8cfbd56f1117856d8e56e3dc39c41f5c4af3f5e1dc8786aa6ba53370e9eb205f`。
