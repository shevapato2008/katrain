# Existing3：独立身份与执行审核

2026-10-05；决定 JSON SHA-256：`37dc016ed4233e3b234d3a85ebb35b448bf9dc6ff2a94c8d3066bea5665ec988`。

**批准 TEST 与 PROD 各 407 个精确 NULL 棋手关联位，210 / 104 / 93；数据库写入 0。** 仅适用于决定 JSON 中枚举的 album_id + side 及其冻结快照。

| 原文 | 官方姓名 | PROD ID | TEST ID | 数量 | 官方来源 |
|---|---|---:|---:|---:|---|
| 中小野田智己 | 中小野田智己 | 352 | 353 | 210 | [日本棋院](https://archive.nihonkiin.or.jp/player/htm/ki000217.htm) |
| 桥本雄二郎 | 橋本雄二郎 | 486 | 487 | 104 | [日本棋院](https://archive.nihonkiin.or.jp/player/htm/ki000134.htm) |
| 高梨圣健 | 高梨聖健 | 564 | 565 | 93 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000289.htm) |

独立只读连接核对了两个实时数据库：全部 album 行（含 SGF）、目标棋手/name/alias、raw staging 与 source associations 均逐字段等于各自草案。407 个 SGF 的 PB/PW 与对应 exact raw 均一致；来源均为 source_id 1 / 19x19。

中小野田智的截断目录仍存在：PROD 3781、TEST 9579，各 9 个既有关联位。本次明确选完整官方姓名目录 PROD 352 / TEST 353，不合并或迁移截断记录。此选择覆盖此前对完整姓名 raw 的暂缓，范围严格限定为本次枚举的 210 个 NULL 位。

发现的 5 处段位冲突已逐盘找到赛事佐证；仅批准棋手身份关联，原始段位不改。

| album / side | 原始问题 | 核对依据 |
|---|---|---|
| 147467 / black | 中小野田智己，2004 年写六段 | [NHK 52 官方表](https://www.nihonkiin.or.jp/match/nhk/052.html)：5/30 张丰猷胜中小野田智己九段；GoRatings 日期和执黑败吻合。 |
| 124542 / black | 桥本雄二郎，2001 年写 8p | [十段 40 官方表](https://www.nihonkiin.or.jp/match/jyudan/040.html)：橋本雄二郎九段胜中野泰宏；GoRatings 对上 2001-07-19。 |
| 63759 / white | 高梨圣健，2014 年写九段 | [龙星 24 官方表](https://www.nihonkiin.or.jp/match/ryusei/024.html)：A 组高梨八段、洪奭義七连胜；GoRatings 对上 2014-11-20 洪执黑胜。 |
| 63803 / white | 高梨圣健，2019 年写八段 | [碁圣 45 官方表](https://www.nihonkiin.or.jp/match/gosei/045.html)：秀芳 4/4 胜高梨九段；GoRatings 对上 2019-04-04 石田芳夫执黑胜。 |
| 21498 / white | 高梨圣健，2025 年写八段 | [SGW 8 官方表](https://www.nihonkiin.or.jp/match/sgw/008.html)：9/25 内田修平胜高梨聖健九段。 |

另 12 个记录未写段位；其余 390 个段位/年份通过官方升段年份核对（升段当年允许旧段位）。普通记录的逐盘归属为完整姓名、SGF、比赛/对手和生涯时段的综合推断；并未声称全部 407 盘均找到独立赛果页。

代码审核没有发现阻塞本次哈希绑定 CLI 执行的问题：6 表锁、实时完整 preimage 比较、NULL compare-and-swap、完整 postimage 比较、单事务失败回滚与独立连接验证均已检查。`uv run pytest -q tests/web_ui/test_player_existing3_exact.py`：5 passed。SQLite 测试未验证 PostgreSQL 表锁；TEST、PROD 各自 apply 前须执行已有 CLI dry rollback。

决定 JSON 同时记录代码 SHA、每个环境的完整 snapshot SHA 和 407 个 exact slots。最终计划应与对应 draft JSON 完全相同，仅将 `review_sha256` 替换为本决定 JSON 的文件 SHA。最终压缩字节 SHA 须另外独立确认，再原样用于两个 plan SHA 参数；任何 preimage 漂移须重新核对。

事务提交后若独立验证报错，可能已经提交成功，须先查看实时状态。已提交恢复仅允许在同样表锁下完整 postimage 相等时，将枚举 FK 比较后恢复 NULL，并恢复 3 个原始 staging 状态/metadata；完整恢复 preimage 相等后才提交。

既有 15 条多语言姓名仍为 legacy_unverified/review；本审核未认证或修正这些译名，尤其不使用 Koji Takari 作为高梨聖健的证据。
