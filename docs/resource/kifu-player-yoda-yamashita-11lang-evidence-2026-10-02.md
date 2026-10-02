# 依田纪基、山下敬吾：11 语言姓名来源查证

查证日期：2026-10-02。范围按 `katrain/web/kifu/identity.py` 的产品语言清单：`en, cn, tw, jp, ko, de, es, fr, ru, tr, ua`。本备忘录记录公开来源是否直接出现对应姓名，不作名称批准，也不写数据库。

## 关键来源

| 编号 | 来源 | 可直接核对的内容 | 权威性与局限 |
|---|---|---|---|
| S1 | [日本棋院：依田纪基](https://www.nihonkiin.or.jp/player/htm/ki000101.htm) | 日文棋士档案标题「依田 紀基」 | 棋手所属棋院，一手来源；未见罗马字字段 |
| S2 | [日本棋院：山下敬吾](https://www.nihonkiin.or.jp/player/htm/ki000322_2.html) | 「山下 敬吾（ヤマシタ ケイゴ / YAMASHITA, Keigo）」 | 棋手所属棋院，一手来源，同时直接支持日文读音和英文转写 |
| S3 | [韩国棋院：依田纪基](https://www.baduk.or.kr/record/player_view.asp?pkey=20000019) | 「요다 노리모토(依田紀基)」 | 韩国棋院棋手档案，一手支持韩文及汉字 |
| S4 | [韩国棋院：山下敬吾](https://www.baduk.or.kr/record/player_view.asp?pkey=20000137) | 「야마시타 게이고(山下敬吾)」 | 韩国棋院棋手档案，一手支持韩文及汉字 |
| S5 | [中国体育总局棋牌运动管理中心：应氏杯报道](https://www.sport.gov.cn/qpzx/n5387/c651242/content.html) | 报道参赛名单中有「山下敬吾」 | 官方中文体育机构转载/发布赛事报道；支持简体字写法，不是棋手档案 |
| S6 | [中文维基：依田纪基](https://zh.wikipedia.org/wiki/%E4%BE%9D%E7%94%B0%E7%BA%AA%E5%9F%BA)、[山下敬吾](https://zh.wikipedia.org/wiki/%E5%B1%B1%E4%B8%8B%E6%95%AC%E5%90%BE) | 两个条目标题分别为「依田纪基」「山下敬吾」 | 直接命中简体候选，但属协作百科；依田条目注明日文原名依田紀基 |
| S7 | [English Wikipedia: Norimoto Yoda](https://en.wikipedia.org/wiki/Norimoto_Yoda)、[Keigo Yamashita](https://en.wikipedia.org/wiki/Keigo_Yamashita) | 英文条目标题及正文使用这两个英文名，并列出对应汉字 | 直接支持候选拼写，但属协作百科；非一手来源 |
| S8 | [美国围棋协会：Yoda retains Gosei](https://www.usgo.org/content.aspx?club_id=454497&item_id=95724&page_id=5) | 正文称「Yoda Norimoto 9P」 | 围棋协会赛事报道，一手比赛新闻；姓名顺序为姓在前 |
| S9 | [GoRatings：Yoda Norimoto](https://www.goratings.org/en/players/90.html)、[Yamashita Keigo](https://www.goratings.org/en/players/64.html) | 两个档案标题采用姓在前的罗马字形式 | 围棋评级数据库，直接支持罗马字和棋手对应关系；非棋院来源 |
| S10 | [西班牙语维基：Norimoto Yoda](https://es.wikipedia.org/wiki/Norimoto_Yoda)、[法语维基：Norimoto Yoda](https://fr.wikipedia.org/wiki/Norimoto_Yoda) | 西语、法语页面分别以 Norimoto Yoda 为条目标题 | 直接支持本地化百科中的拉丁字母惯用形式；协作百科，不是官方来源 |
| S11 | [俄语维基：Ёда, Норимото](https://ru.wikipedia.org/wiki/%D0%81%D0%B4%D0%B0%2C_%D0%9D%D0%BE%D1%80%D0%B8%D0%BC%D0%BE%D1%82%D0%BE)、[俄罗斯围棋联合会 Go Library：Yoda Norimoto](https://rusgolib.gofederation.ru/YodaNorimoto.html) | 俄语维基正文用「Норимото Ёда」；联合会资料页以拉丁字母标题，正文误作「Йода Наримото」 | 俄语维基直接支持常见西里尔字形但非官方；联合会站点有拼写错误，不能作为俄文名直证 |

## 逐语言候选矩阵

| 语言 | 依田纪基候选 | 山下敬吾候选 | 证据判定 / 缺口 |
|---|---|---|---|
| `en` | Norimoto Yoda | Keigo Yamashita | 直接支持：S7；另 S8/S9 用「Yoda Norimoto」「Yamashita Keigo」，姓名次序存在正式出版/数据源差异。S2 对山下提供棋院罗马字一手证据。 |
| `cn` | 依田纪基 | 山下敬吾 | 依田：S6 直接命中，官方中文一手来源未找到。山下：S5、S6 直接命中；S5 是官方中文机构赛事名单。 |
| `tw` | 依田紀基 | 山下敬吾 | 字形可由日文汉字原名直接对应（S1/S2），但本轮未找到台湾繁体中文出版/媒体来源直接证明这是当地惯用显示形式；`tw` 是否应区别于 `cn` 仍待本地用例核验。 |
| `jp` | 依田紀基 | 山下敬吾 | 直接支持：S1、S2，日本棋院档案。 |
| `ko` | 요다 노리모토 | 야마시타 게이고 | 直接支持：S3、S4，韩国棋院档案同时给出汉字。 |
| `de` | Norimoto Yoda | Keigo Yamashita | 候选沿用英语/国际罗马字形式；没有找到德语围棋机构或德语出版物的直接用名证据。 |
| `es` | Norimoto Yoda | Keigo Yamashita | 直接支持西语页面中依田名字：S10；山下对应西语条目未查得，当前是国际罗马字候选。 |
| `fr` | Norimoto Yoda | Keigo Yamashita | 直接支持法语页面中依田名字：S10；山下对应法语条目未查得，当前是国际罗马字候选。 |
| `ru` | Норимото Ёда | Кэйго Ямасита | 依田：S11 直接支持「Норимото Ёда」（条目标题倒序）。山下的规范俄文转写及俄语用例未找到，`Кэйго Ямасита` 只是按读音转写的候选。 |
| `tr` | Norimoto Yoda | Keigo Yamashita | 仅国际罗马字候选；未找到土耳其语围棋媒体/机构直接用名证据。 |
| `ua` | Норімото Йода | Кейґо Ямасіта | 仅按日语读音转写的候选；未找到乌克兰语围棋媒体/机构直接用名证据。`г/ґ`、`и/і` 转写规范和姓名顺序均未核实。 |

## 未决项

- 若后续把“逐语言用名”作为已核实数据，`de/tr/ua` 以及 `ru` 的山下姓名需要本地权威用例；目前不能把基于读音的合理转写当作来源证据。
- `tw` 候选与日文汉字一致，但应补台湾地区围棋报道或出版物的实际用例，确认显示惯例及是否与简体 `cn` 分流。
- 英文来源有「given-name family-name」和「family-name given-name」两种顺序。S2 棋院罗马字字段明确为 `YAMASHITA, Keigo`；S7 的英语名条目采用 `Keigo Yamashita`。依田尚缺日本棋院英文档案字段可消除此歧义。
- 日本棋院依田档案 S1 与韩国棋院档案 S3 的汉字「依田紀基」相互印证。简体候选「依田纪基」依赖中文转写惯例和协作百科；本轮未找到官方中文机构对依田名字的直出实例。
