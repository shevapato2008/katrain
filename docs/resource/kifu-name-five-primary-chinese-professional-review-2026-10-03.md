# 40 名中国职业棋手五语名称证据独立复核

**35 人的五语名称证据完整通过，另 5 人各有一语 HOLD；共 195 个精确显示值通过、5 个暂缓。** 全部 200 个候选字符串均确实出现在所引来源中，但字面出现不自动证明适合该人物的目标语言显示。原候选包保持 pending；本次没有签署正式导入候选、人物实体、QID 绑定、SGF 归属、FK、数据库前像或写入。

审核于 `2026-10-02T19:07:10.240756+00:00` 完成（北京时间 2026-10-03）。审核者 `/root/five_primary_40_name_review_astra`，与候选生产者独立。父代理确认本次配置为 `gpt-6-astra / max`；运行时只向审核者标明 GPT-6，精确型号与推理配置未独立认证。签署工件如实记录这一限制，签名是审核者声明及哈希绑定，不是模型身份的密码学认证。

对[固定候选包](kifu-name-five-primary-chinese-professional-candidates-2026-10-03.md)逐项重算并读取原始资料：40 条协会姓名和完整生日、160 个 GoRatings 四语榜单姓名与站内 ID、40 份中文人物页、Wikidata 明确 `zh/en/ja/ko` 标签与日精度生日均相合。40 人全部属于 [Luna 149 人严格来源预检](kifu-name-four-primary-source-precheck-2026-10-03.md)，没有其四个标签例外。另实际读取并留存同 ID 的英、日、韩人物页 **120 份**，全部 HTTP 200，姓名和生日均一致；这些页面含实际目标语的数据标题、生日和棋局表，不仅是榜单入口。GoRatings 四种页面仍算同一出版方；Wikidata 只作交叉线索，不声称其数据独立。

繁中逐项核对[台灣棋院 2018 团体赛全文](https://taiwangorg.blogspot.com/2018/06/2018_12.html)的 39 项姓名、队伍及教练/台次语境；从原始 HTML 重新提取的 393 行正文与前轮留存文本一致。蔡競使用[海峰棋院 2025 北海新繹杯正文](https://www.haifong.org/news/content/1A1FC6784E61CEF19A50D168C92AB76B)，保留与 Wikidata `zh-tw` 标签 `蔡竞` 的差异。于富霖、于浩然只批准该来源实际采用的 `於富霖、於浩然`，没有批准通用姓氏转换。彭荃的日文 `彭筌` 另由[日本棋院 2004 农心杯正文](https://archive.nihonkiin.or.jp/match/2004/11/2_112429.html)逐字支持，不把荃/筌差异自动改回原字。

| 原名 / 编号 | HOLD 的精确显示值 | 本次判断 |
| --- | --- | --- |
| 汪逸尘 / CWA000459 | `jp: 汪逸尘` | GoRatings 日语人物页和明确日文标签仍用简体 `尘`；[日语围棋资料目录](https://kifudepot.net/prouserid.php/index.php)另见 `汪逸塵`。该目录只作为冲突线索，未批准替代值，尚未排除源语回退。 |
| 王鹭 / CWA000207 | `jp: 王鹭` | [日语棋局页](https://kifudepot.net/kifucontents.php?id=RyrIWxL5cCOkZFXDXJbp5Q%3D%3D)使用 `王鷺`，注明三段、2009-07-01 及对手汪涛。保留与候选的字形分歧，不自动转换或批准替代值。 |
| 蔡竞 / CWA000061 | `jp: 蔡竞` | [日本棋院第 21 回三星杯](https://www.nihonkiin.or.jp/match/sansei/021.html)明确采用 `蔡競六段`，与 GoRatings/Wikidata 的 `蔡竞` 不同。固定候选 HOLD；新值须另建候选审核。 |
| 袁卫红 / CWA000525 | `jp: 袁卫红` | 页面及明确标签保留 `卫、红`；本轮没有独立日语实际用名资料能判断这是采用的日文形式还是源语回退。未断言该形式错误，也未完成任何未命中闭环。 |
| 黄思源 / CWA000854 | `tw: 黃思源` | 2018 名单确实写成都队第四台、业余 5 段；本候选出生于 2008 年，留存 GoRatings 对局从 2022 年开始。九岁参赛并非错误证据，但原报道没有生日或稳定编号，尚未补足这条业余记载与后来的职业人物之间的对应。[韩国棋院](https://www.baduk.or.kr/record/player_view.asp?pkey=20002337)也写 `黃思源`，其正文为韩语，不能代替繁中用名依据。 |

这 5 人的其余 20 个显示值取得本次名称证据通过。完整五语通过的 35 人为：丁波、于富霖、于浩然、佟禹林、公彦宇、吴肇毅、安冬旭、宋容慧、宋雪林、岳亮、廖桂永、彭荃、曾志豪、李亮、李必奇、李鑫怡、李魁、梁伟棠、汪美成、牛雨田、王子昂、王思尹、王群、王超、王香如、程宏昊、范炳旭、葛凡帆、袁曦、谷宛珊、邱峻、邱金波、金茜倩、高恬亮、高逸典。候选对应的 4,814 个库内槽位仅为背景计数；包括这 35 人的 4,383 个槽位，**本次关联批准均为 0**。

汪美成有一项必须保留的非姓名冲突：Wikidata `Q101543732` 的 `P21` 为男性，而协会 `playerGender=2`、GoRatings 榜的 `♀`、台灣棋院女子团体名单，以及[韩国棋院对应人物页](https://www.baduk.or.kr/record/player_view.asp?pkey=20002115)所列女子组赛事相合。审核排除 Wikidata 该性别字段作为人物对应依据；保留其逐字姓名和完整生日的比对结果，五语名称证据通过。没有修正外部资料或批准正式 QID/人物绑定。

按运行时 `NFKC → casefold → 合并空白` 规则检查冻结目录 `2026-10-02/honinbo-final-review-astra-v2/catalog-recheck.jsonl`（SHA-256 `420ed4a10445a8d50c49d1132cd47ee8eee893b871dce2a968e8593775fa6105`）：五语同语言名称、各候选与 canonical name / alias、以及组内名称碰撞均为 **0**。快照含 876 人、22 条显示名称、23 条别名，未重查当前数据库。零碰撞不证明人物归属。

冻结材料在 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-primary-40-review-astra/`（目录 `0700`、文件 `0600`）。每个条目固定原候选行哈希、名册编号、原名、生日、GoRatings ID、QID、五个精确值、逐语决定、原始来源 URL/字节哈希/上下文，以及审核者信息和时间。Wikidata 原始分组请求 URL 在输入中未留存，记录只给实体定位 URL 和已核对的分组响应哈希，没有伪造请求地址。

| 工件 | SHA-256 |
| --- | --- |
| 输入 `candidates.pending.jsonl` | `60fcccf509cd961da72b6e3a30d97cf384e1b151ebdf02683044306848e29d4a` |
| `complete-five-name-pass-35.scope.json` | `5864ceb269c4e8b91929e56e32d9ed712fea12e581b0097e4dd94535629917a9` |
| `name-evidence-pass-195.scope.json` | `aba00dc062b55530668bd847524ad3cdec92cfb897c28d315218ec215946a65d` |
| `name-evidence-hold-5.scope.json` | `175733f47bca46af951da20dc1335fc0f1f1d08e3c5d0f8956aabc12b4f68977` |
| `reviewed-40.jsonl` | `6763f04bb05b0293c6ce10b739689e3ba425e582aaad0c6cbb780d979f14d907` |
| `review-manifest.json` | `fb66c4091663c3b8b13e903bd78b8e0bc97814db518d291bab88342b5827edd8` |
| `review-signature.json` | `0b347d60aa1c3a8bc14ae83cd8bef2ccbed89a3730aa5862af1f0b474e3c96c5` |

本结论只覆盖这批精确名称证据，不能直接导入。GoRatings 尚未登记为导入器来源，正式研究格式、前像、十一语和独立 SGF 身份审核仍须完成；本次没有改来源登记、代码、数据库或部署，也没有提交 Git commit。
