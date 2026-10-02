# 王座战五语核心名与 103 个有限原文变体：独立审核

**五语核心名均 PASS；有限适用范围为 99 个变体／2,015 局 PASS，4 个变体／46 局 HOLD。** 审核者 `/root/ja21_independent_review`（实际模型 `GPT-6`）独立于候选作者 `/root`。[原候选](kifu-name-oza-five-primary-candidates-root-2026-10-03.md)中的名字 PASS 不批准有冲突的期号、日期或轮次，也不构成赛事 owner、棋谱链接、导入签名或数据库写入批准。

| 语言 | 核心名与结论 | 核对依据 |
| --- | --- | --- |
| cn | `日本王座战` **PASS** | [野狐围棋专业报道](https://www.foxwq.com/news/listid/id/7453.html)实际标题用名；转载新浪报道的第 60 期张栩／井山裕太五番胜负明确指向日本职业赛事。FoxWQ 仍须在导入前登记来源。 |
| tw | `日本圍棋王座戰` **PASS：受控去期号核心** | [海峰棋院报道](https://www.haifong.org/news/content/8A4A649B26B5007EC2A65A26D77B05D4)正文为 `日本第60期圍棋王座戰`；仅删除 `第60期`，不伪称完整候选字符串逐字连续出现。 |
| jp | `王座戦` **PASS** | [日本棋院官方系列档案](https://archive.nihonkiin.or.jp/match/oza/index.html)棋战名称、职业棋手参赛资格、日本经济新闻社／日本棋院／关西棋院主办方及历届结果一致。 |
| ko | `일본왕좌전` **PASS** | [韩国棋院张栩履历](https://www.baduk.or.kr/record/player_view.asp?pkey=20000106)实际列第 59／60 期该名及羽根直树／井山裕太对手；`일본` 限定日本系列。 |
| en | `Oza` **PASS：系列核心** | [日本棋院英文页](https://archive.nihonkiin.or.jp/match/oza/061-e.html)同时使用 `Oza Title Match` 和 `Oza Challengers Tournament`；核心名适用于系列，不能将全部预选记录称为决赛。 |

五个 HTTP-200 留存正文的 bytes、SHA-256、候选短语和实际语种均独立核对通过。候选文件 SHA-256 为 `6360b33052ab04015441bd392428dc5640c9558928a21d9746a1037f31a7760c`，来源 manifest 为 `d3a5e709e4d8f0be4b895e4a827500f505af0c4da5628c0e6d68f2fa7e4441fb`。中文报道与繁体报道中的首局日期文字并不完全一致；本次用它们核对系列名字和人物／第 60 期上下文，不批准这些日期为棋谱事实。

冻结分组文件 SHA-256 为 `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`；底层完整库存文件 SHA-256 为 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`，库存内部 SHA 为 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`。四个 Oza 分组及全部 103 个精确成员的原有分组哈希、结构、album IDs 和数量已核对，未扩展到其他赛事字符串。

生产只读查询在 `katrain_db` 的 **REPEATABLE READ READ ONLY** 事务中执行并回滚，快照 `4003600:4003600:`，开始时间 `2026-10-02T21:22:08.050678+00:00`。全部 2,061 局的姓名、段位、原始赛事、RO、日期、现有 event ID、来源关联和重复关系均与冻结库存相同。逐局解析生产库保存的 SGF，EV／首个 GN、PB／PW、DT、RO 与数据库字段 **零 mismatch**；每局正文 SHA-256 和根属性已保存。全部 event ID 为 null。本次读取的是生产库 SGF，不声称读取了当前对象存储中的原始来源文件。

日本棋院官方表逐项确认第 1–62 期结果年，覆盖本范围全部有期号变体；创设于 1952 年，而第 1 期结果年为 1953 年。CWI 路径与职业棋手上下文，以及全部 705 个 19x19 棋谱第二 GN／GC 中的明确日本赛事文字，为区分韩国同名棋战、学生赛和将棋提供了来源上下文。有限范围内未发现另一系列的正面证据。日期吻合只是核查线索，未被定义为身份规则；早期预选可发生于结果年前一年。原有 RO 保留，`Round`、数字或 semifinal 不自动解释为本赛或预选层级。

| 完整原始变体 | 局数 | HOLD 理由 |
| --- | ---: | --- |
| `Oza` | 3 | album 121167、130235、131924 未解析出期号／阶段，按要求全部 HOLD。第二 GN 已发现日本赛事线索，但本次未批准它为新的赛事选择。 |
| `28th Oza` | 17 | 全部 SGF 的 EV 是第 28 期，路径却为 `Oza/26/P01–P17.sgf`，日期为 1977／1978；官方第 26 期结果年 1978、第 28 期 1980。未自动改期号。 |
| `45thOza` | 5 | album 54534 日期 `1998-02-06` 晚于官方第 45 期结果年 1997；真实 SGF 同样保留该日期。完整变体保持 HOLD，不推定修正。 |
| `48thOza` | 21 | album 85420 日期 `1998-09-01` 早于官方第 48 期结果年 2000 两年；提前预选时程或源记录错误尚未解决。确认日本系列线索不等于确认该期号／日期。 |

其余 99 个变体的 PASS 只批准**列出的有限 album IDs 使用日本职业 Oza 系列核心名**。`20th Oza` 的 album 25025 虽在此前留存 archive 中缺少对应路径，生产 SGF 现可直接读取，保留 EV、吴清源／藤泽秀行九段、GoGoD95 来源及 `DTX[Published 1972-09-11~20]`。这支持系列核心对应，但 DTX 是出版日期，不能补成对局日；原始文件路径的缺失和空 DT 均显式保留。其他粗粒度、多日期和空日期也未被改写。

受保护审核包：`~/.local/share/kifu-name-audit/2026-10-03/oza-five-independent-review-gpt6/`，目录 `0700`、文件 `0600`。包含五语决定、103 逐变体决定、2,061 逐局决定及 SGF 根核对、只读 SQL／结果、历史期号表、摘要、manifest 和复核脚本。

- `raw-variants.reviewed.jsonl` SHA-256：`1561ed3219a3cbf36db20474299c6b2e5eec1a92256d521e896d7f4b58617164`
- `albums.reviewed.jsonl` SHA-256：`48413aeb26857ab7f53121feab40224ac6ee96e77b13cd3af9c069752a8fc719`
- `language-cores.reviewed.json` SHA-256：`d8c3992832adf3d1eafb3d06da24ac44964adcc1855a3c36a14ff1aa83434d8a`
- `manifest.json` SHA-256：`f86c465ad5a6e36d557db329e85010e42bdde860fdc342b536b9d553db6613df`

未修改原候选、应用代码、数据库记录或提交。正式链接仍须满足十一语、当前清单、来源登记、前像和写入审核要求。
