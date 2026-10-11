# safe6：独立逐槽棋手身份决定

2026-10-04，只读审核。决定 JSON SHA-256：`38bf557857dd70995d094347c3573230ca5b0adf6ffd0ffaa2691c2fd68c382e`。

**781 个 NULL 槽 / 777 局全部评估：批准 601 槽 / 597 局，HOLD 180 槽。复用 4 个既有身份，仅允许新建 赵哲伦、陈嘉锐 2 个中文 canonical。** 本文件不是执行回执；没有数据库写入。

| raw | 目标目录名 | TEST / PROD ID | 批准 | HOLD | 主要依据 |
|---|---|---|---:|---:|---|
| 赵哲伦 | 赵哲伦 | 每库新建一次 | 107 | 33 | [官方档案](https://wqapi.cwql.org.cn/playerInfo/CWA000185) |
| 梅泽由香里 | 吉原由香里 | 9908 / 4112 | 114 | 24 | [官方档案](https://www.nihonkiin.or.jp/player/htm/ki000346.htm) |
| 冈田结美子 | 安倍结美子 | 10138 / 4344 | 114 | 13 | [官方档案](https://www.nihonkiin.or.jp/player/htm/ki000293.htm) |
| 村松大树 | 村松大樹 | 587 / 586 | 111 | 16 | [官方档案](https://www.nihonkiin.or.jp/player/htm/ki000424.htm) |
| 陈嘉锐 | 陈嘉锐 | 每库新建一次 | 75 | 50 | [官方档案](https://kansaikiin.jp/kisi_prof/chinkaei.html) |
| 石田笃司 | 石田篤司 | 756 / 755 | 80 | 44 | [官方档案](https://www.nihonkiin.or.jp/player/htm/ki000216.htm) |

日本棋院明确记载吉原由香里旧姓梅沢、冈田结美子旧姓安倍。因此复用现有身份，保留现有 canonical，不创建同人的第二行。村松大樹和石田篤司按官方汉字名及目录罗马字复用；仅字形不同，不重命名。

陈嘉锐（关西棋院：1954-08-23 生、1987-03 以五段加入）与现有陈家瑞不同。[中国棋协 CWA000820](https://wqapi.cwql.org.cn/playerInfo/CWA000820)记载后者 2010-02-04 生、2021-07-18 入段；两库现有 499/498 的 40 局全部在 2021–2025 年。英语 Chen Jiarui 的重合被逐项列为同拼音排除，不作身份合并。陈嘉锐中文名另有[中文维基百科](https://zh.wikipedia.org/wiki/陳嘉銳)明确记录。

冻结前像来自四次 REPEATABLE READ READ ONLY 事务：两库完整 scope/catalog 捕获及两库既有目标上下文捕获。主快照 TEST `2026-10-04T11:22:29.021843+00:00`，PROD `2026-10-04T11:22:28.744423+00:00`。JSON 内嵌两库 777 个完整 album 行和 SGF、781 槽、777 来源关联、全局 players/aliases/names/source/event/edition 目录及六条完整 staging；包括旧捕获遗漏的 name revision/verified_at/generation_rule_version 和 staging category/parsed_data/parser_version。

相对 10:43 原捕获，每库恰有 10 个对手 FK 变化，全部重放 new33 第二批已批准成员；并固定该批 16 个新棋手目录完整实际行。所有原捕获其余字段保持一致。完整源文件、完整当前快照、每槽前像、目标目录行、来源、赛事和全局目录都有 SHA 守卫。

逐局重新解析完整 SGF，名字、段位、日期、结果、首项赛事/来源、19 路、手数及来源路径检查均通过；本 scope 未发现 SGF 字节或精确主线重复。HOLD 包括段位年代冲突、文件名式/紧凑拉丁赛事标题、交流或特殊比赛、陈嘉锐加入关西棋院之前尚待单独证实的中国/香港棋谱，以及元旦日期精度疑点。每槽理由完整列于 JSON。

三个精确例外：冈田 62727 的日期在日本棋院记载的 1989-04-05 首场职业胜局之后；52485/62260 的“女流最强位五段”与官方 2002 冠军及 2003 五至六段区间相容。826 的首项 SO 为空、第二项及来源关联完整，保留原字段。五个缺少独立赛事锚点的特殊/小棋圣/团体语境（80239、131762、131767、54664、131742）继续 HOLD。

执行只允许固定 approved_slots 的本方 NULL FK 变化，以及两个人各一次 INSERT；180 HOLD 和其他既有 HOLD 保留。任何后续中国阿含桐山杯或其他提交造成的完整前像漂移，必须新增 SHA 固定的精确重基线，禁止跳过 event_id、对手 FK、SGF、created_at、名字审核字段或目录守卫。必须先构造环境计划、回滚演练并验证完整派生后像。

来源 manifest SHA-256：`a9b67b9129cfbd6e55bb837d53f1ca9204279f99e0a2088fee333112261988f2`。Firecrawl 返回额度不足，实际证据通过普通网页搜索和官方/维基页面直读取回并保存原文及 SHA。

机器决定：[JSON](kifu-player-safe6-independent-exact-slot-decision-astra-2026-10-04.json)。完整基线：[TEST](kifu-player-safe6-TEST-fresh-full-preimages-astra-2026-10-04.json.gz)、[PROD](kifu-player-safe6-PROD-fresh-full-preimages-astra-2026-10-04.json.gz)。
