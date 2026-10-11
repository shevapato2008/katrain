# 棋手预处理：非汉字名次 221–240 安全 18 项预演

**后续状态：两库已按审核通过的冻结计划先 TEST 后 PROD 写入并全量核验，
见[执行记录](kifu-player-nonhan-ranks-221-240-safe18-application-2026-10-04.md)。**

2026-10-04 对原 17 项白名单独立核对身份与两库实时目录后，仅增加
`Ito Matsujiro` 一项。原名单未改；[派生白名单](kifu-player-nonhan-ranks-221-240-safe18-exact-allowlist-2026-10-04.json)
和 TEST／PROD 冻结计划分别以 SHA-256 锁定。**只完成事务 dry-run 并回滚，未正式写入。**

| 项目 | TEST | PROD |
| --- | ---: | ---: |
| 棋局总数 | 173,025 | 173,025 |
| 本批 exact raw／待关联席位 | 18／839 | 18／839 |
| 黑方／白方待关联席位 | 481／358 | 481／358 |
| 复用既有目录 ID／拟建中文目录 ID | 11／7 | 11／7 |
| dry-run 实际回填席位／原文审核行／拟建 ID | 839／18／7 | 839／18／7 |
| 事务回滚前后已关联席位 | 264,787／264,787 | 266,392／266,392 |
| 事务回滚前后目录 ID 数 | 3,798／3,798 | 3,620／3,620 |

SHA-256：原 17 项白名单 `e07200807ae5f2cf9ee76500946d35bf7c4465075b206ffd4bed21117acda1c3`；
派生安全 18 项白名单 `aa1dbb9684c6fbca7d93a59b7adba745dd93cecf5189318faa4a9a3b983cb890`；
[TEST 计划](kifu-player-nonhan-ranks-221-240-safe18-plan-test-2026-10-04.json.gz)
`1fce2efa729a1547a6f4a1071c13a84a597f71779443d17273002b984eef8209`；
[PROD 计划](kifu-player-nonhan-ranks-221-240-safe18-plan-prod-2026-10-04.json.gz)
`883450de60339f41763c049972ecf9c5f289edfd2e19f864a597d703541ddf7b`。
冻结棋局 inventory SHA-256 为
`dcc4f547ec196bbe850b79b6ce11a97dfda64e92343fcb2640dbd1aebaaad743`。

## 身份与目录审查

[CWI 丈和棋谱姓名表](https://homepages.cwi.nl/~aeb/go/games/games/ancient/Honinbo_Jowa/)
直接列出“伊藤松次郎／Ito Matsujiro = Ito Showa”，并载有该原值对局。
因此第 227 名 48 席复用此前 `Ito Showa` 建立的同一人 ID：TEST `12441`、
PROD `6672`；没有为别名新建第二人。原 17 项保持原审查决策。

对 11 个复用目标逐项核对，TEST、PROD 的 ID 与中文主名均吻合且主名唯一。
7 个拟建主名“岩佐銈、上村阳生、安井算知（九世）、东野弘昭、林佐野、
本因坊元丈、井上春硕因硕”在两库目录主名及别名表均不存在。
其中 [CWI 职业棋手表](https://homepages.cwi.nl/~aeb/go/misc/progression.html)
同列岩佐銈／Iwasa Kei、東野弘昭／Tono Hiroaki；
[日本棋院上村阳生资料](https://www.nihonkiin.or.jp/player/htm/ki000063.htm)
提供官方原字形和罗马拼写；
[日本棋院历代家谱](https://www.nihonkiin.or.jp/teach/history/rekidai.html)
列九世安井算知、十一世本因坊元丈、五世井上因硕（春硕）。
[CWI 方圆社棋谱](https://homepages.cwi.nl/~aeb/go/games/games/Hoensha/)
载 `Hayashi Sano` 对局；[讲谈社日本人名辞典](https://kotobank.jp/word/%E6%9E%97%E4%BD%90%E9%87%8E-1102162)
载围棋棋手“林佐野”及其方圆社创立经历，姓名读音与时代吻合。
其他逐项证据见[原审查表](kifu-player-nonhan-ranks-221-240-review-2026-10-04.json)。

`Yasui Sanchi IX` 的 `IX` 与 1825–1856 年对局指向九世；部分外部索引
将 `Yasui Sanchi` 无代次写法混入二世，正式执行前仍须按本批的精确原值和九世
主名核对。`TakemiyaMasaki` 的 7 席 `1900-01-01` 是小棋赛日期占位；
剩余 41 席及既有目录身份支持武宫正树，不将该日期解释为真实对局年代。

`KimHi-jun`（48 席）与 `Tsuruoka Saburosuke`（45 席）保持暂缓：
两库共 2 个原文审核行仍为 `pending`、元数据为空，93 席 FK 全空。
安全 18 项的 839 席 FK 在回滚后也全空，18 个审核行均保持 `pending`，
7 个拟建目录主名未出现。导入器对冻结与实时盘号、原文、日期、来源、
既有 FK、目录前像和审核行状态重新检查；聚焦测试 `14 passed`。
