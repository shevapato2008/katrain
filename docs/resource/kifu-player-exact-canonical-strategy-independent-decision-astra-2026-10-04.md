# 中文 exact canonical 批量关联：独立裁决

2026-10-04，独立 gpt-6-astra max。数据库操作仅为 `REPEATABLE READ READ ONLY` 查询；未改数据库或执行器代码。

## 最终决定

**PASS：TEST、PROD 各 1,529 个精确 NULL 槽／1,527 盘。** 只允许冻结清单列出的棋手 FK 回填。检查适用于这三个已核定身份及当前精确成员；不能扩大成全库同名自动关联规则。

| 人物 | TEST 目标 | PROD 目标 | 每库批准槽 | 每库 HOLD 槽 |
|---|---:|---:|---:|---:|
| 周鹤洋 | 1048 | 4193 | 644 | 216 |
| 赵善津 | 542 | 541 | 550 | 129 |
| 工藤纪夫 | 348 | 347 | 335 | 235 |
| 合计 | — | — | **1,529** | **580** |

全量审查原文只有 `周鹤洋`、`赵善津`、`工藤纪夫`，两库各 2,109 个 NULL 槽／2,105 盘。保留目录、旧五语名称、alias、raw staging JSON 与 pending 状态。所有赛事、日期、结果、来源、对手 FK 和原谱正文均保持各库自己的前像。本决定未批准任何新译名、别名或全局 raw 审核升级。

机器文件：

- [TEST review](kifu-player-exact-canonical-three-frozen-review-test-2026-10-04.json)：内部 review SHA `c4cc59abf65e3465306e679c67a45ceb8f13895c94d5fee9ad026478cf25981a`；文件 SHA `e2e4599263d88cf931cf9e0ac454b1f46fe7353fbc11af918c82ff7d8f8d2092`。
- [PROD review](kifu-player-exact-canonical-three-frozen-review-prod-2026-10-04.json)：内部 review SHA `47113ae15d1b82ea5e474b472c412f4e5ba7e7fc552b85955281fd510c8937a6`；文件 SHA `49379c3cca58c3a65b732c7775c22a251d04455d589847f4a9ec03be58f59ef6`。
- [策略与计数 JSON](kifu-player-exact-canonical-strategy-independent-decision-astra-2026-10-04.json)：内部 decision SHA `b7cf57f908c9f3dea30ac54b1af507832e12e749a36fe49a8899aa89a54162ed`；文件 SHA `188913da4272dfcd38e0c268cc11c4c9294e1194c743049d10be9e8209e3db7d`。

`candidate_slots` 的字段顺序为 `[album_id, side, raw_name, date_played, old_fk, target_id]`。`held_slots` 给出全部 HOLD、原因和逐盘 SHA。`live_album_preimage` 保存所有列的前像，其中原谱正文以 `sgf_sha256` 表示，另有包括原谱在内的 `album_row_sha256`。完整原谱、完整行及全目录捕获的文件位置和 SHA 在 `complete_before_image` 中；源关联行、来源行、目标目录／名称／别名及 raw staging 前像也在 review 内。

## 已完成的全量检查

1. 两库分别解析目标 ID；canonical、alias 和旧 cn／tw／jp 名称经过 NFKC、OpenCC t2s、casefold 仅用于检查跨 ID 冲突，不用于扩大原文匹配。
2. 每个 PB／PW 属性值均与对应库内原文一致；允许完全相同的重复属性。排除字面同名、对手 FK 指向同一人或对手经目录／别名归一化后为同一人的棋谱。
3. 原始日期必须是真实 `YYYY-MM-DD`，与 date_sort 及每个 DT 值一致，非 1900 占位，不晚于本次捕获日。入段年份本身暂缓，使用下一完整日历年作为首轮下界。
4. EV／GN 全部值必须与库内 event 完全一致。任何不同附加标题暂缓，包括可能正确的中英文标题对应；本轮不为其延长研究。混双、指导、训练、研究、纪念、表演及让子范围暂缓。
5. 每个 SO 值和库内 source 均为 `https://19x19.com`，路径为该来源的数字 SGF 路径。棋盘为 19 路，主线不少于 40 手，实际完整主线手数与 move_count 相符。全部 RE 与库内 result 相符。
6. 目标段位存在时，与 BR／WR 一致，使用简单段位写法；排除早于官方明确升段年份的记录。空段位只视为缺少信息。
7. 批准集合在两库的 album ID、执色、原文及完整 SGF SHA 完全一致。全部 2,105 盘除双方棋手 FK 和 17 行既有 event_id 环境差异外，其他列一致；不把两库不同 ID 相互覆盖。

人物身份和职业年代依据：周鹤洋的[春兰杯主办方资料](https://www.chunlan.com/igo/7th/4data/4_data_xsjs_zg.asp)记载 1976-06-18 出生、1988 年初段、2001 年九段，并与此前已核 SHA 的中国围棋协会 `CWA000014` 响应一致；本批下界为 1989-01-01。日本棋院的[赵善津资料](https://www.nihonkiin.or.jp/player/htm/ki000187.htm)和[工藤纪夫资料](https://www.nihonkiin.or.jp/player/htm/ki000026.htm)分别给出 1970-04-18／1984 年入段、1940-08-02／1955 年入段；首轮下界分别为 1985-01-01、1956-01-01。

这是有限身份归属判断。按用户当前的全库预处理与提速要求，外部赛事表逐槽命中不是本批门槛；没有声称对全部成员进行了外部逐手比对，也没有把身份批准表述为原谱所有事实均正确。

## HOLD

580 槽为去重后的完整数量。原因计数可能重叠：不同 EV／GN 标题 553、日期异常 12、DT 冲突 4、入段边界 4、非常规段位 4、让子 3、特殊对局范围 3，以及来源／结果／升段年份等。全部精确 ID 在两库 review 中。

三个明确的外部冲突继续 HOLD：

- **148086／白、148087／黑（赵善津）**：库内分别为 `B+R`、`W+2.5`，而日本棋院[第54期本因坊决赛记录](https://archive.nihonkiin.or.jp/match/honinbo/054.htm)分别记赵善津白胜 2.5 目、黑中盘胜。原谱结果不在本批改写范围。
- **65957／白（工藤纪夫）**：库内记 `B+R`，官方[第23期天元决赛](https://archive.nihonkiin.or.jp/match/tengen/023.htm)记工藤劫争违例判负，保守暂缓。

其他姓名、繁体／段位后缀、仅经 normalization 才相同的原文均未批准。正在单独执行的 mixed11 名单及对应繁体 `孫喆` 原文已从策略候选排除；不得用本文件覆盖其执行。

## 全库提速策略与实际覆盖

06:50:50 UTC 两库 READ ONLY 捕获：

| 阶段 | TEST | PROD |
|---|---:|---:|
| 剩余 NULL 棋手槽 | 55,970 | 54,365 |
| 与唯一 2–5 汉字 canonical 完全相同 | 15,679／132 名 | 13,115／115 名 |
| 排除 mixed11 及繁体孙喆 | 12,726 | 10,162 |
| 排除 canonical／alias／旧名称跨 ID 冲突 | 8,241 | 8,268 |
| 仅留简体 canonical | 7,997 | 7,995 |
| 排除来源、日期、自弈、已知出生前记录及已审非人物 | **7,858** | **7,859** |

最后一行仍是研究候选上限，包含此次三个姓名的部分 HOLD，不是可立即写入数。PROD 同值既有非空 FK 冲突检查为 0；TEST 其余研究队列不能继承此结果。已有旧名称可以暴露 exact canonical 看不到的重复 ID，例如韩升周、奥田彩、金昇珍等。

通用规则必须另外防止既有非人物目录被重新关联：TEST 1074 `丁浩周泓余` 仍精确命中 18704／白、18709／黑、25115／白，但它是已审的双人连写。两库 93943 的黑白均为井山裕太。两库 39168／白的崔明勋日期为 1971-04-28，GN 同时混入日本大手合标题，而[韩国棋院资料](https://www.baduk.or.kr/record/player_view.asp?pkey=10000065)明确其出生于 1975-05-12。这些实例使“唯一 canonical”只能作为候选入口。

后续按少量已核定人物的明确来源与生涯范围分批：一次复用人物证据，全量机器检查根属性／年代／目录碰撞，异常精确 HOLD，再冻结成员。无需逐盘人工搜网页，也不为新增覆盖修改原谱或扩张旧审批。

## 执行衔接

先完成 mixed11，再为本批按环境重新冻结执行计划。两批同槽交集为 0，同盘交集为 8：`7189、8956、61465、66226、66241、132947、134184、134220`。mixed11 会改变这些棋谱的对手 FK；允许在其已批准提交后重取该前像，不能扩大本批成员或目标。应用器应绑定数据库名、上述 review／成员 SHA、全行前像和 SGF SHA，并在锁内执行 NULL→目标 ID CAS；dry 回滚后检查完整复原，提交后验证仅批准槽位改变且所有 HOLD 保持原像。

终检已重新计算两库 review／成员／HOLD／完整行／SGF／来源正文的 SHA，确认 1,529＋580 精确覆盖全部 2,109 槽且无交集，所有全字段 guard 可由完整捕获重建，三项外部冲突在 HOLD 内。两库批准成员及 SGF 相同，环境目标 ID 各自正确。

受控捕获与网页正文在 `~/.local/share/kifu-name-audit/2026-10-04/player-exact-canonical-strategy-independent/`。三人完整捕获时点 TEST 为 06:59:02 UTC、PROD 为 06:59:10 UTC；各完整压缩文件 SHA 已写入 review。官方网页正文已保存并记录各自 SHA。最初 220 盘分层 SGF 抽查仅用于策略排险；最终三人批准依赖其 2,109 槽全量检查。
