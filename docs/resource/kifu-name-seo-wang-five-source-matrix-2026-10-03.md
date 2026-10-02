# 徐奉洙与王立诚：五种严格语言名称来源矩阵（2026-10-03）

状态：仅研究和 pending 候选；未审批、未写数据库。目标是当前 production 名称清理中两个高频棋手：徐奉洙 ID `108`（1,257 exact raw slots），王立诚 ID `17`（1,237 slots）。既有资料检查只找到顶 100 只读统计和 top 15 缺口表，没有两人的逐人名称候选/来源研究；参见 `kifu-name-player-top100-readonly-batch-2026-10-02.md`、`kifu-name-top15-near-ready-pipeline-2026-10-02.md`。本研究不将统计中的简体原始写法当成五语覆盖证据。

## Pending 名称矩阵

| Player / ID | `cn` | `tw` | `jp` | `ko` | `en` | 证据与判断 |
|---|---|---|---|---|---|---|
| 徐奉洙 / 108 | `徐奉洙` | `徐奉洙` | `徐奉洙` | `서봉수` | `Seo Bong-soo` | 韩国棋院识别徐奉洙为韩国职业九段，名称及韩文、汉字互证；日本棋院日文赛事报道写作徐奉洙九段并标注韩国；台湾海峰棋院第二届应氏杯冠军记录使用徐奉洙；新浪中文棋手档案和 Korea.net 英文报道分别支持简体中文名与英文连字符写法。五项均为 pending。 |
| 王立诚 / 17 | `王立诚` | `王立誠` | `王立誠` | `왕리청` | `Wang Li Chen` | 日本棋院官方棋士档案给出姓名、日语读音「オウ リッセイ」及英语栏 `Wang Li Chen`；台湾总统府称其为我国旅日棋士，日本棋院九段；韩国棋院以 왕리청(王立誠) 记载并注明所属日本；新浪中文档案为简体字名。英国围棋协会英文简介另写 `Wang Licheng`，记录为英文拼写冲突，英语候选暂采用所属棋院档案的 `Wang Li Chen`，仍待独立批准。 |

## 来源快照

抓取时间为 2026-10-02 UTC 16:56–16:58（Asia/Shanghai 为 2026-10-03 00:56–00:58）。以下 SHA-256 对应 HTTP 200 原始响应 body 字节；正文摘录保留来源语言。链接可供重抓复核。日期为页面可见日期；未标日期者记为页面无明确发布日期。 原始 10 份响应 body 未留存；此前 SHA-256 仅记录了当时响应，当前没有本地 body 可复算。候选批准前需重新抓取并存入受控证据目录。

| Player / language | 来源 URL；页面语言；可见日期 | 正文摘录 | 原始 body SHA-256 |
|---|---|---|---|
| 徐奉洙 / `ko` | [韩国棋院棋士档案](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000008)；韩文；动态档案，页面显示截至 2026-10 | `9단 서봉수 (徐奉洙)`；页面还列生年月 1953-02-01、所属韩国。 | `d7ef864da860a8c511dcc1eedb99aece8b14ddee7ee7a71f03500e0667f94e77` |
| 徐奉洙 / `jp` | [日本棋院 1004 岛新安国际老年赛报道](https://www.nihonkiin.or.jp/match_news/match_info/2022_1004_1.html)；日文；2022-10-04 | `徐奉洙九段（韓国）`；同页赛事结果同时列刘昌赫、王立诚等。 | `2175fd7c79b5876bc2e4ab341977b45068aab29a458109607e2ea473e6657fbc` |
| 徐奉洙 / `tw` | [海峰棋院应氏杯赛事档案](https://www.haifong.org/game/classes/8AD0F09CC001B8A2EEBBC376AEEAB539)；繁体中文；页面列第 2 届 1992-07-13–1993-05-20 | `第二屆冠軍 徐奉洙`。棋院记录赛事冠军身份，姓名为繁体地区页面惯用字形；此人名各字在简繁间相同。 | `364efc3b2eff1bd20bccab38e2287dc6de30da9999a75d3be55b78dbde5d0b32` |
| 徐奉洙 / `cn` | [新浪徐奉洙棋手档案](https://sports.sina.com.cn/star/xufengzhu/)；简体中文；未标发布日期 | `徐奉洙：性别：男 生日：1953年2月1日 籍贯：韩国 段位：九段`。 | `c5f63c9502f07d1b5197cf12c18f306fbc822429f2b5487c0a9af970da560d54` |
| 徐奉洙 / `en` | [Korea.net 专业棋手报道](https://www.korea.net/NewsFocus/Culture/view?articleId=121345)；英文；页面发布日期未能从当前正文核实 | `The professionals, widely known in Korea, were Seo Bong-soo, Yoo Chang-hyuk, Lee Chang-ho and more.` | `1f145b4e4ceffafd6de27076d276f82a1331bc567345fa1459a36e09df3984bc` |
| 王立诚 / `ko` | [韩国棋院棋士档案](https://www.baduk.or.kr/record/player_view.asp?pkey=20000028)；韩文；动态档案，页面显示截至 2026-10 | `왕리청(王立誠) 9단`；档案列生年月 1958-11-07、所属日本。 | `077ef7bf5c79cdf5da012177c85c3897f5e5776e9b633057a4e7fa45eda2bb64` |
| 王立诚 / `jp` | [日本棋院官方棋士档案](https://archive.nihonkiin.or.jp/player/htm/ki000065.htm)；日文/双语档案；旧版档案，无可见发布日期 | `氏名/Name 王 立誠 Wang Li Chen`；`ヨミ オウ リッセイ ワン リーツェン`；出生地台湾南投市，所属日本棋院东京本院，九段。 | `12fd6d7c2e517543894f58a15fc29dd37a6b7d4b2f6272626d0a967de6a50c22` |
| 王立诚 / `tw` | [中华民国总统府新闻档案](https://www.president.gov.tw/NEWS/4423)；繁体中文；约 1997（新闻记录） | `王立誠是我國旅日圍棋名家……目前為日本棋院職業九段棋士`。 | `5154ef27596924fa0bfd64f56f02e0ded796162caa8e7abcc23459ba347516e0` |
| 王立诚 / `cn` | [新浪王立诚棋手档案](https://sports.sina.com.cn/star/wang_licheng/)；简体中文；未标发布日期 | `姓名：王立诚（wang_licheng） 国籍：日本 籍贯：中国台北……段位：九段`；传记记其 1971 年赴日、1972 年入段。 | `3432470f72fb21a8ae51dcc6abeced4c22139d903342248f06afa5740c9236ca` |
| 王立诚 / `en` | [British Go Association biography](https://www.britgo.org/general/itd/5.html)；英文；未标发布日期（页面属 In the Dark 棋士简介） | `O Rissei`；`O sensei was born in Taiwan, where he is known as Wang Licheng`。日本棋院双语档案则写 `Wang Li Chen`。 | `ee0a49c6e3a14d20cd9086d75d4e4b0cd685d2415d84474c14cf67cdda8986d8` |

## 混同与范围说明

- **徐奉洙**：韩国棋院档案是身份锚点；中文来源的 `徐奉洙` 与韩文 `서봉수` / 汉字 `徐奉洙` 一一吻合。英语存在常见连字符差别：本次 Korea.net 直接正文支持 `Seo Bong-soo`，另有数据库拼作 `Seo Bongsoo`；候选只采用正文来源支持的连字符形式。未发现本轮证据显示与另一位同名职业棋手混同。
- **王立诚**：不得把日语读音 `オウ リッセイ`（英文常写 O Rissei）误作 `en` 候选；英文来源的 `Wang Li Chen` 与 `Wang Licheng` 有空格差异，暂以日本棋院官方英文栏为候选且留待批准。韩文以韩国棋院在读音转写后括注汉字的原文为准，采用 `왕리청`。
- 两人都是韩国职业棋手/日本棋院所属棋手等跨国身份，检索命中赛事页面时以同一来源中的所属地、对手或职业段位确认实体。没有从六种次要语言推导本轮名称，也未改写任何生产数据。
