# 古力与张栩：五种严格语言来源矩阵（2026-10-03）

状态：仅研究与 pending 显示名，未批准、未写数据库。生产目录背景：古力 ID `201`（1,353 raw slots）；张栩 ID `80`（1,269 raw slots）。这些计数仅用于排序，本研究没有抽样 SGF 证实具体 raw slot 的人物归属。

## 现有研究与捕获情况

既有 [古力 / 李世石 11 语初步矩阵](kifu-name-gu-li-lee-sedol-source-matrix-2026-10-02.md) 已列出本次五语名称线索，但没有原始页面正文或 body 哈希；[张栩 11 语初步矩阵](kifu-name-zhangxu-11lang-source-matrix-2026-10-02.md) 已列出同样的五语线索，也没有原始正文哈希。本轮复用并核对已有古力简体中文官方档案捕获，其受控 Markdown 正文保存在 `/Users/fan/.local/share/kifu-player-top100-20261002/five-player-source-index/bodies/gu_li_sportgov.md`，SHA-256 `677b524ed63447f1802759ff2d6591f884c350e48a3e2fd23213b07442373b6b`；这是 Firecrawl main-content Markdown 抽取，不是原始 HTTP body。本轮其余来源均直取响应并保存为原始正文。

徐奉洙 / 王立诚上一份 memo 所列的 10 个响应 body 没有留存；当时的 SHA-256 只绑定当时取回的响应，本地无法复算。候选批准前须重抓并保存受控正文。

本轮原始证据目录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/gu-li-zhang-xu-five-strict-sources/`；目录和 `bodies/` 为 `0700`，正文及 `manifest.json` 为 `0600`。每条 URL、最终 URL、抓取 UTC、状态、正文语言、摘录、路径、字节数与 SHA-256 均在 [manifest.json](/Users/fan/.local/share/kifu-name-audit/2026-10-03/gu-li-zhang-xu-five-strict-sources/manifest.json)；manifest SHA-256 `ef0a1b0de61ffaf21be2fea2fe0d9fefc08355c7f307e910d01d1710b20faa34`。新正文在 `bodies/<source-key>.body`；本地时区 Asia/Shanghai 抓取时间为 2026-10-03 01:04–01:05。

## Pending 显示名

| 棋手 / ID | `cn` | `tw` | `jp` | `ko` | `en` |
|---|---|---|---|---|---|
| 古力 / 201 | `古力` | `古力` | `古力` | `구리` | `Gu Li` |
| 张栩 / 80 | `张栩` | `張栩` | `張栩` | `장쉬` | `Cho U` |

## 可复核来源正文

| 棋手 / 语言 | 来源、正文语言、页面日期 | 摘录和身份锚点 | 抓取 / 正文证据 |
|---|---|---|---|
| 古力 / `cn` | [国家体育总局棋牌运动管理中心人物介绍](https://www.sport.gov.cn:8443/qpzx/n27319120/c27440754/content.html)；简体中文；2023-05-23 页内发布日期 | `古力：中国围棋职业九段棋手，国际级运动健将。…1995年入段…1997年底师从聂卫平。`；与职业身份、出生地重庆及棋手生涯吻合。 | 复用受控 Markdown 正文，哈希与路径见上方；抓取 `2026-10-02T03:54:12.904147Z`。 |
| 古力 / `tw` | [海峰棋院 2015 海峡两岸冠军争霸赛报道](https://haifong.org/news/content/5EAE39324A37FB92ABAFE74C8C11FAA1)；繁体中文；2015-08-04 | `古力 棋手簡介 1983年2月3日生於重慶。1995年入段，2006年因奪得LG杯升為九段。`；台湾围棋机构页面及棋手简介。文章注明原文链接到新浪棋牌网，故视为台湾繁体正文见证，不另算独立原始报道。 | `2026-10-02T17:04:59.136612Z`；`949299af224578756038f87112b3838547eb2429ea19f77002d729c5c62f58ff`；`bodies/gu_li_tw_haifong.body`。 |
| 古力 / `jp` | [日本棋院 Toyota & Denso Cup 页面](https://www.nihonkiin.or.jp/match/toyota/002.htm)；日文；第二届赛事资料 | `古 力七段（中国）`；日本棋院赛事名单中与中国棋手同列，符合这位中国职业棋手。展示名不保留版式空格或段位。 | `2026-10-02T17:05:01.793884Z`；`854593c829de968f52515241816372ff92a7257df6cf3e984fbf6914c710e578`；`bodies/gu_li_jp_nihonkiin.body`。 |
| 古力 / `ko` | [韩国棋院棋士档案](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=20000151)；韩文；动态档案，战绩截至 2026-10 | `9단 구리 (古力)`；出生 1983-02-03，所属中国，职业升段履历与官方中文档案相符。 | `2026-10-02T17:05:03.953949Z`；`f2cc9f8243b790edf0ca8971e76cf70a58d5f58ae3a9f804ac39e1b5f8ca75ec`；`bodies/gu_li_ko_kba.body`。 |
| 古力 / `en` | [British Go Association 英文新闻稿 PDF](https://www.britgo.org/files/pressrelease/Press-release-AlphaGo-Feb222016.pdf)；英文；2016-02-22 | `Quotes from Go professionals and commentators ahead of the match: Gu Li 9p`；英文围棋材料直接用 `Gu Li`，9p 指职业九段。实体由中、韩棋院资料交叉锚定。 | `2026-10-02T17:05:06.930256Z`；`f1434f0bfd4d937a6a0cfda4257d30a708ec9625a5fea6c9ed3182250c97bec8`；`bodies/gu_li_en_britgo.body`。 |
| 张栩 / `cn` | [国家体育总局棋牌运动管理中心第六届应氏杯报道](https://www.sport.gov.cn/qpzx/n5387/c651242/content.html)；简体中文；2008-04-30 | `参加第一轮比赛的16名选手是古力、刘星、胡耀宇、谢赫、朴文尧、王磊、高尾绅路、山下敬吾、张栩、赵治勋……`；官方比赛报道将张栩放在国际职业围棋选手名单中。 | `2026-10-02T17:05:09.910241Z`；`b23cbf39ccb47465d5a27fa05d041546997cfc41963f51c5d1d67e520432b682`；`bodies/zhang_xu_cn_sportgov.body`。 |
| 张栩 / `tw` | [台湾总统府新闻档案](https://www.president.gov.tw/NEWS/7749)；繁体中文；页面结构化日期 2017-02-26 | `旅日職業圍棋國手張栩`；同文关联第五十八届本因坊头衔及赴日职业棋手身份。 | `2026-10-02T17:05:10.102129Z`；`6f076c0a75d987c86357dc22c7b774bc2475560b92eb5d6fbea57f6692267cdd`；`bodies/zhang_xu_tw_president.body`。 |
| 张栩 / `tw` | [海峰棋院转载的换日线专访](https://haifong.org/news/content/F05540B657DC16C1402AFFFCCCC72F54)；繁体中文；2017-05-24 | 标题：`從神童到凡人，無冕王的「驚天一手」──換日線張栩專訪`；正文围绕其赴日职业生涯及头衔，台湾围棋机构页面直接使用 `張栩`。 | `2026-10-02T17:05:12.237757Z`；`6f1d5c9077d6cef70e2cbdf9ba95ba5b77166e59fa90a0e7d827a416b74d0f88`；`bodies/zhang_xu_tw_haifong.body`。 |
| 张栩 / `jp` | [日本棋院官方棋士档案](https://www.nihonkiin.or.jp/player/htm/ki000331.htm)；日文；当前棋士页，无发布日期 | `張 栩（チョウ ウ / CHANG, Hsu）`；出生台湾台北，所属日本棋院东京本院，九段。直接记录实际日语读音及个人身份。 | `2026-10-02T17:05:14.227187Z`；`93b1849fb3b4954d551ca902c7e517dc015c7b89a94c6781fd9aa10d264c7d10`；`bodies/zhang_xu_jp_nihonkiin.body`。 |
| 张栩 / `ko` | [韩国棋院棋士档案](https://www.baduk.or.kr/record/player_view.asp?pkey=20000106)；韩文；动态档案，战绩截至 2026-10 | `장쉬(張栩) 9단`；生于 1980-01-20，所属日本，符合台湾出生、日本棋院所属的张栩。 | `2026-10-02T17:05:16.127714Z`；`2b216f4683589e09eea22280d972395431ad19d12ef05ead87ef6ef8b5799840`；`bodies/zhang_xu_ko_kba.body`。 |
| 张栩 / `ko` | [韩国棋院姓名标记规则说明](https://www.baduk.or.kr/news/report_view.asp?news_no=590)；韩文；2012-10-08 | `일본기원에서 활약하는 대만국적의 ‘張栩’와 ‘謝依旻’은 ‘장쉬’와 ‘셰이민’으로 읽습니다.`；明确说明韩国棋院对旅日台湾棋手采用的读法。 | `2026-10-02T17:05:19.662076Z`；`d895103e70909eb5582a5e543fd393dd02f476bb5d9d6c1585f6928f543a5b33`；`bodies/zhang_xu_ko_kba_naming.body`。 |
| 张栩 / `en` | [日本棋院英文 2002 年赛事报道汇编](https://www.nihonkiin.or.jp/english/topics/02/topics2002_12.htm)；英文；2002-12 | `Cho U 7-dan (W) defeated Cho Chikun Oza by resignation.`；英语围棋正文用 `Cho U`，并在同一句中区别于 `Cho Chikun`。 | `2026-10-02T17:05:22.041611Z`；`6d9fe3fc061a1bcfe4ad4aea22a413fbb32090c3b526147afc6e1c0be826015e`；`bodies/zhang_xu_en_nihonkiin.body`。 |

## 读音、称谓与异常

- **张栩**的字形一致不代表读音一致：中文普通话为 `Zhāng Xǔ`；日本棋院档案的日语读音是 `チョウ ウ`，同页附罗马字 `CHANG, Hsu`；韩国棋院将台湾籍、在日本棋院执业的他读作 `장쉬`，并在规则文中明确给出该惯例；英文棋战正文使用 `Cho U`。因此 `jp` 用字形名 `張栩`、`en` 用实际英语围棋用法 `Cho U`，不把任一地区转写强套给其他语言。`Cho U` 也不能与同段出现的 `Cho Chikun` 混为一人；名/段位/头衔不并入显示名。
- **古力**的 `tw` 与 `cn` 恰好字形相同；韩国棋院以 `구리 (古力)` 和中国所属信息消除同音常用词的歧义。繁体地区报道显示的 `古力` 不由简繁转换推断。
- 张栩台湾总统府页面的结构化 `datePublished=2017-02-26` 对应历史人物报道，属于页面日期/迁移异常；只用作身份与名字证据，不以该日期重建生涯年份。古力海峰页面注明新浪原文链接，是转载来源，未算作第二个独立报道。此前古力法语维基线索所载出生年/入段年与官方中国资料不符，本次五语身份核验不采用那些数据。
- 所有建议名仍是 pending；这些来源确认的是名称和棋手身份，不构成生产 ID 到具体 raw slot 的绑定或数据库写入依据。
