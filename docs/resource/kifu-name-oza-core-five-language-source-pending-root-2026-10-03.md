# `Oza` 赛事核心：五语正面来源候选

2026-10-03；生产者 `/root`。这是下一批赛事来源研究，未签赛事实体、原串归属、显示候选或棋局 FK。

冻结的 [event-core v4 分组](kifu-name-event-core-priority-v4-2026-10-03.md)将精确核心 `Oza` 汇总为 **2,061 棋局计数、103 种原始写法**：英语届数独立写法 1,356、黏连写法 384、后缀写法 318、纯 `Oza` 未解析 3。前三类只证明结构可解析，不自动证明它们均是日本职业王座战。国际 Toyota–Denso **World Go Oza** 和世界学生王座战是不同赛事，必须在原串、日期与对局层面排除。

| 目标语 | 待审核心名 | 真实专业正文与有限含义 |
| --- | --- | --- |
| `jp` | `王座戦` | [日本棋院第62期王座战页](https://www.nihonkiin.or.jp/match/oza/062.html)明确棋战名、主办方日本经济新闻社／日本棋院／关西棋院及创设年 1952；是日本职业标题赛。 |
| `en` | `Oza Title` | [日本棋院英文王座页](https://archive.nihonkiin.or.jp/match/oza/index-e.html)直接列此 Tournament name，与日文页主办方、1952 创设年及第61–62期对应；另有单独的 World Go Oza 页面，不能混同。 |
| `tw` | `王座戰` | [海峰棋院第60期报道](https://www.haifong.org/news/content/8A4A649B26B5007EC2A65A26D77B05D4)的原生繁中标题用 `第60期王座戰`，正文写日本围棋王座战、张栩与井山裕太之战。核心字形为直接用名；加「日本」和「圍棋」是上下文限定，不把拼接后的全称伪称原文。 |
| `ko` | `일본왕좌전` | [韩国棋院张栩人物页](https://www.baduk.or.kr/record/player_view.asp?pkey=20000106)实际韩文履历写第59期日本王座战夺冠、第60期失利，并另用紧凑 `왕좌전`；其赛事与日本棋院同期记录可核对。 |
| `cn` | `日本王座战` | [野狐围棋张栩卫冕报道](https://www.foxwq.com/news/4802.html)在简中标题直接使用，人物与日本棋院该时期王座历史对应；野狐是专业围棋媒体，不冒称棋院官方。 |

受控原文 `~/.local/share/kifu-name-audit/2026-10-03/oza-core-source-root/` 包含五份 HTTP 200 HTML，分别为 `jp/en/tw/ko/cn`，SHA-256：`83f2034303622aa66da56aff74c682444f8e5e02b5d37395ff3d34e65763c4e1`、`712c0a97d81526a1b4b015e1d6a09ec844fda77781400a1a66525206c94c31a7`、`65d8736a0f29abd33600e5217a54c9d44c5693e8518e7eb9c84ef052eb627ad1`、`d788a5fdca0e5154f776796069e8d985146a7714bbc2bf823e79274bf6d30dcf`、`0bab30c405853f3dabcace114a74c6f100098a097b8a29601d48c12da9fbf5e6`。URL、抓取时间与字节数见 `manifest.json`，其 SHA-256 为 `526ae318af928084a8cf82fafe8eeaf42173bdbd27a45b55ad3e6ce4260d7c95`。

下一步由独立审核者核对五份正文实际语种、名称、赛事身份及 World/Student Oza 排除边界；对原串另做有限逐盘 scope，三条纯 `Oza` 继续 HOLD。六种次要语言另按已审赛事原名/读音规则形成有限生成候选。此次无代码、数据库或部署改动。
