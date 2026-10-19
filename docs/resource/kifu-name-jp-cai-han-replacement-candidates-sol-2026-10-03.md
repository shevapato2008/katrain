# 蔡竞／韩卓然 JP 替代名称候选（pending）

2026-10-03；范围仅两个确切人物的日文显示名称证据。新候选尚未获独立审核；旧候选及既有签名范围不变。没有批准人物 FK、QID、读音、导入或数据库写入。

| 原名／CWA ID | DOB／GoRatings ID | 旧 JP 值 | 新 JP 候选 | 本次状态 |
|---|---|---|---|---|
| 蔡竞／CWA000061 | 1993-06-23／1108 | `蔡竞`：HOLD | `蔡競` | pending independent name review |
| 韩卓然／CWA000710 | 2005-01-26／2037 | `韩卓然`：HOLD | `韓卓然` | pending independent name review |

## 原文和人物对应

**蔡竞。** [日本棋院第 21 回三星杯](https://www.nihonkiin.or.jp/match/sansei/021.html)的历史正文 `a021_01` 标注 2016-09-06～08、中国参赛名单、B 组 `蔡競六段`。该组依次对兪斌九段、申真諝六段、兪斌九段，蔡竞分别执白、执黑、执白。[GoRatings 1108](https://www.goratings.org/zh/players/1108.html)的三条对应日期记录对手和黑白一致，分别胜、负、负；其日文同 ID 页的姓名仍为 `蔡竞`，保留冲突。日本表双方单元格均有 `class="winner"`，不能据此属性判胜；原表仅给日期范围，单轮日期由 GoRatings 提供。三轮对应关系支持确切人物的名称证据，不推断 SGF 归属。

**韩卓然。** [日本棋院 2024 年中国男子团体联赛](https://www.nihonkiin.or.jp/match/chugokuleague/013.html)历史正文为**丙级**联赛；第 4 战 6 月 3 日，北京市围棋协会队 `韓卓然三段` 对日中友好队酒井佑规五段，酒井一侧记胜。[GoRatings 2037](https://www.goratings.org/zh/players/2037.html)同日记韩卓然执黑负于酒井佑规（1945），并链接日本棋院 `Heikyuuleague_Han_Sakai_20240603.sgf`。日文同 ID 页姓名仍为 `韩卓然`，保留冲突。日本联赛摘要未给黑白，黑方只由 GoRatings 记录支持。

**共同身份锚点。** 新留存的[中国围棋协会职业棋手目录](https://wqapi.cwql.org.cn/playerInfo/professional/list)中，两人的原名各有且仅有一条记录；编号、完整生日均与冻结候选及上述 GoRatings 中／日同 ID 资料相符。这是官方人物资料加实际赛事上下文的对应推断；GoRatings 含日本棋院棋谱链接，不能把它与日本原表计为两份独立采集的赛事事实。当前段位为蔡六段、韩四段，历史原文韩 2019 初段／2024 三段；没有把当前四段回填历史。

[日本棋院 2019-05-22 梦百合杯报道](https://www.nihonkiin.or.jp/match_news/match_result/42_39.html)另实际使用蔡竞的新字形，并在第 24 组采用韩卓然的新字形。蔡条属于 5 月 21 日结果，韩条属于 5 月 22 日**预定组合**；该预定组合不充当已完成对局的桥接证据。

## 留存来源及限制

原始 HTTP 正文于北京时间 2026-10-03 留存；8 个请求均返回 200，最终 URL 与请求相同。2019 新闻正文印有发布日期 2019-05-22；另外 7 项未观察到发布日期。赛事日期、HTTP Last-Modified 和抓取时间分开记录。

日本棋院历史页正文混入当前赛事模块；网页抽取工具也返回当前年度正文。核验以完整 HTTP 字节及指定历史章节、表头、人员行为准，不使用混入的当前赛季内容或搜索摘要。保护包保留完整原文、精确 HTML 片段及片段哈希，便于独立复核。

| 文件 | SHA-256 |
|---|---|
| cwa-roster.body | `18ba2a04efdca69d47528cbe703d9c54e1005b7f986af782434cbc3f1dd316f9` |
| nihonkiin-cai-sansei21.body | `760b60320fda3fe17867520d1d9a5dbf67463e86bcaafec7dfff8e9d3793b988` |
| nihonkiin-han-chinese-league2024.body | `0410de01f556b8ad9898ff5f85f07f7d877f140644a590679f66ea4b87140c4b` |
| nihonkiin-han-mlily4.body | `45e985f487fb6c830b53808ec616f623e060808de0c8141f6daea54bf6602fa7` |
| goratings-zh-cai.body | `4f789a8ad272a967ffe570359c6361166a6af253f72a59396c0297c14743cde0` |
| goratings-ja-cai.body | `c54643aa27052f66ae289b57a7701d388e34c857adda90fc21ea9f00bcfaef59` |
| goratings-zh-han.body | `9dba35d4b3d31799e7c9d464eeb44d7806fb7e1932dd107ba981b543737305b9` |
| goratings-ja-han.body | `d415cc51828e8037e18f23ef7acf7920c97975c8f46b74fbf988ca402e2f95b7` |

按 `NFKC → casefold → 合并空白` 核查两条新 JP 值：批内和冻结目录 canonical name／alias／同语 display name 碰撞均为 0。目录 SHA `420ed4a10445a8d50c49d1132cd47ee8eee893b871dce2a968e8593775fa6105`；未重查当前数据库，零碰撞不证明人物身份或全网唯一性。

## 保护包与后续审核

目录：`~/.local/share/kifu-name-audit/2026-10-03/jp-cai-han-replacement-candidates-sol/`（目录 0700、文件 0600）。

- `replacement-candidates.pending.jsonl`：恰好两条 JP 候选；SHA `3064482f3c756ab274c4c4f5ac08be7b83d56fc7108868a70efa7048d554ab92`。
- `manifest.pending.json`：SHA `ec2e0ad6a1d28a636b12e23f7b69f34910cac3d927e233eee22789b1084c7314`；绑定全体候选、8 份来源正文、抓取元数据和有限碰撞结果。
- 旧 40 人候选／审核 SHA：`60fcccf509cd961da72b6e3a30d97cf384e1b151ebdf02683044306848e29d4a`／`6763f04bb05b0293c6ce10b739689e3ba425e582aaad0c6cbb780d979f14d907`。
- 旧 19 人候选／审核 SHA：`438012112ce330e6faf097d26073d4472360c76dbe8cf212d7830aa1a595e8ec`／`65b7dacde279288cb4e13535d53c24dc128c42be0a6eb2b5e76e88985ae121be`；四份既有文件均复核未变。

两条新候选均 `name_approved=false`、`identity_fk_approval=false`、`write_ready=false`，没有审核者签名。交独立审核者逐字、逐人、逐来源复核后再决定；不得直接替换旧签名包或导入。
