# Oza 五语与 NHK 台湾用名：待审来源事实独立复核

2026-10-03；审核者 `/root/event_oza_nhk_source_review`。仅核对两份待审备忘录及其受控 HTML 的来源事实；**PASS 仅表示指定正文直接支持指定用名**，不签赛事实体、原串归属、显示候选、棋谱 FK 或数据库操作。

## `Oza` 五语

| 目标语 | 原样核心名 | 来源事实结论与核对点 |
| --- | --- | --- |
| `jp` | `王座戦` | **PASS**。[日本棋院第 62 期页](https://www.nihonkiin.or.jp/match/oza/062.html)的棋戦名称为 `王座戦`；列日本经济新闻社、日本棋院、关西棋院为主办，1952 年创设、职业棋手参赛、五番胜负。页面位于国内棋战栏目。 |
| `en` | `Oza Title` | **PASS**。[日本棋院英文页](https://archive.nihonkiin.or.jp/match/oza/index-e.html)的 `Tournament name` 正是 `Oza Title`；三家主办及 1952 年与日文页一致。其表中第 60 期 2012 年井山裕太胜张栩、第 57 期 2009 年张栩胜山田规三生，提供跨来源对应。`Title` 是该官方系列名称的一部分，不能由此把每局预选称为头衔决赛。 |
| `tw` | `王座戰` | **PASS**。[海峰棋院报道](https://www.haifong.org/news/content/8A4A649B26B5007EC2A65A26D77B05D4)的繁中标题含 `第60期王座戰`，正文以 `日本第60期圍棋王座戰` 记述张栩对井山裕太；与英文页同届同对手对应。`日本圍棋王座戰` 并非这份标题中逐字连续出现的无届数名称。 |
| `ko` | `일본왕좌전` | **PASS**。[韩国棋院张栩履历](https://www.baduk.or.kr/record/player_view.asp?pkey=20000106)的韩文正文逐字列出第 59 期夺冠（对羽根直树）和第 60 期失利（对井山裕太），与日本棋院英文历届表对应；另有 `왕좌전` 用例。 |
| `cn` | `日本王座战` | **PASS**。[野狐围棋报道](https://www.foxwq.com/news/4802.html)的简中标题直接使用；正文第 57 期张栩对山田规三生、3:0 的结果与日本棋院英文表对应。野狐为专业围棋媒体，非日本棋院官方。 |

五个来源指向日本职业围棋国内 `王座戦` 系列。其赛事名、主办方、期号、棋手与赛制不能转移给 Toyota–Denso World Go Oza、世界学生王座战、将棋王座战或其他同名赛事。上述来源事实亦不能单独判断任何一个未核原始 `Oza` 棋谱属于哪个系列；原 memo 的三条纯 `Oza` 继续 **HOLD**，其余原串也仍须各自核对。

受控目录 `~/.local/share/kifu-name-audit/2026-10-03/oza-core-source-root/` 内五份 HTML 的实际字节数、SHA-256 与 manifest 均相符；manifest SHA-256 为 `526ae318af928084a8cf82fafe8eeaf42173bdbd27a45b55ad3e6ce4260d7c95`。按 `jp/en/tw/ko/cn` 顺序，正文 SHA-256 分别为 `83f2034303622aa66da56aff74c682444f8e5e02b5d37395ff3d34e65763c4e1`、`712c0a97d81526a1b4b015e1d6a09ec844fda77781400a1a66525206c94c31a7`、`65d8736a0f29abd33600e5217a54c9d44c5693e8518e7eb9c84ef052eb627ad1`、`d788a5fdca0e5154f776796069e8d985146a7714bbc2bf823e79274bf6d30dcf`、`0bab30c405853f3dabcace114a74c6f100098a097b8a29601d48c12da9fbf5e6`。manifest 所列 HTTP 状态均为 200；这里核实的是留存内容及记录，未重新证明抓取时的网络状态。

## NHK 台湾专业语境

| 来源 | 结论 | 实际证据与限制 |
| --- | --- | --- |
| [海峰棋院 2008 中日精英赛公告](https://www.haifong.org/news/content/9464745D69D0A96C03D6E78181679673) | `tw` 核心 `NHK盃` **PASS** | 原生繁中正文称张栩持有 `名人‧碁聖‧NHK盃‧阿含桐山盃‧龍星` 等头衔，并说明是日本棋士队伍；不是嵌入的日文履历。[日本棋院 NHK 杯历届表](https://archive.nihonkiin.or.jp/match/nhk/)列第 55 回、2008 年、张栩夺冠，足以交叉对应围棋 NHK 杯系列。 |
| [海峰棋院 2026 GLOBIS 规程](https://www.haifong.org/news/content/7C63FF0DCE165F81C7C6506C78F8924E) | **PASS：辅助用例** | 繁中正文一次写 `NHK盃賽制`，另一次写 `NHK 盃賽制`（中间有空格），均描述每手 30 秒及 10 次一分钟考虑时间。此处借用赛制名称，不是 GLOBIS 赛事改名，也不能单独证明 NHK 赛事身份。 |

**待审 memo 的一处事实更正：**“两次以 `NHK盃賽制`”须改为“一次 `NHK盃賽制`、一次 `NHK 盃賽制`”。两页共同支持台湾专业语境中的紧凑 `NHK盃`；没有直接支持扩展名称 `NHK盃電視圍棋賽`。115 个原串／647 聚合计数及另一个 fragment 的归属仍 **HOLD**，不由用名证据推定。

受控目录 `~/.local/share/kifu-name-audit/2026-10-03/nhk-tw-source-root/` 的 `haifong_title.html` 为 19,204 字节、SHA-256 `a08a28af44044af8f74cfba3fdef964a09cb25bf0f73fc49df395229bd125b06`；`haifong_timing.html` 为 19,865 字节、SHA-256 `8e72e8ac2da0c6dadcb38302baa222c194dad18e96d7aa82d2e9b07d6117b397`。均与 manifest 相符；manifest SHA-256 `603893a5d95dd7bb2f9323306201740c4d76d48f31b82842b75eb2b52d0d2dc2`。日本棋院 NHK 历届页使用既有受控捕获交叉核对；未在本包中新增该页捕获。

本复核只新增来源事实记录；未改待审 memo、代码、数据库或生产环境，未提交。
