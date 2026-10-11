# 17 个既有目录 owner 的人物身份复核（只读建议）

2026-10-04。根据 TEST `katrain_db` 与 PROD `katrain_prod_20260725` 的实时 `REPEATABLE READ READ ONLY` 捕获，核查此前高频 50 人候选中 PROD 有唯一目录 owner 的 17 个 exact raw；使用日本棋院、关西棋院、韩国棋院及中国围棋协会的原始人物资料复核。机器明细见 [JSON](kifu-player-existing17-independent-identity-proposal-2026-10-04.json)。未改数据库。

**身份层面建议：14 人通过，TEST／PROD 各 3,722 个当前 NULL 槽可进入逐槽审查；3 人 HOLD，各 661 槽。** 所有 raw staging 当前仍为 `pending`。这不是任何 FK 写入批准；来源、日期、SGF、同人对手和槽级异常还需分别冻结。

| exact raw | 每库 NULL 槽 | TEST / PROD 目标 | 官方人物名称与来源 | 身份建议 |
|---|---:|---|---|---|
| 李昌锡 | 408 | 194 / 193 | [李昌錫](https://www.baduk.or.kr/record/player_view.asp?pkey=10000829) | 身份通过，待逐槽 |
| 金庭贤 | 368 | 34 / 34 | [金庭賢](https://www.baduk.or.kr/record/player_view.asp?pkey=10000522) | 身份通过，待逐槽 |
| 姜升旼 | 354 | 399 / 398 | [姜昇旼](https://www.baduk.or.kr/record/player_view.asp?pkey=10000600) | 身份通过，待逐槽 |
| 金升宰 | 354 | 147 / 146 | [金昇宰](https://www.baduk.or.kr/record/player_view.asp?pkey=10000468) | 身份通过，待逐槽 |
| 小县真树 | 306 | 443 / 442 | [小県真樹](https://www.nihonkiin.or.jp/player/htm/ki000100.htm) | 身份通过，待逐槽 |
| 朴键昊 | 305 | 146 / 145 | [朴鍵昊](https://www.baduk.or.kr/record/player_view.asp?pkey=10000831) | 身份通过，待逐槽 |
| 鹤山淳志 | 280 | HOLD / HOLD | [鶴山淳志](https://archive.nihonkiin.or.jp/player/htm/ki000365.htm) | HOLD |
| 宫泽吾朗 | 250 | 543 / 542 | [宮沢吾朗](https://www.nihonkiin.or.jp/player/htm/ki000057.htm) | 身份通过，待逐槽 |
| 梶原武雄 | 240 | 12342 / 6578 | [梶原武雄](https://www.nihonkiin.or.jp/player/htm/ki000012.html) | 身份通过，待逐槽 |
| 高根台 | 215 | 485 / 484 | [高根台](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000385) | 身份通过，待逐槽 |
| 大桥拓文 | 214 | HOLD / HOLD | [大橋拓文](https://archive.nihonkiin.or.jp/player/htm/ki000382.htm) | HOLD |
| 加藤启子 | 200 | 422 / 421 | [加藤啓子](https://www.nihonkiin.or.jp/player/htm/ki000364.html) | 身份通过，待逐槽 |
| 桥本昌二 | 199 | 12346 / 6582 | [橋本昌二](https://kansaikiin.jp/subpage/kiinjouhou.html) | 身份通过，待逐槽 |
| 金东烨 | 194 | 12545 / 6776 | [金東燁](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000044) | 身份通过，待逐槽 |
| 东野弘昭 | 189 | 12456 / 6687 | [東野弘昭](https://kansaikiin.jp/kisi_prof/tonohiroaki.html) | 身份通过，待逐槽 |
| 李小溪 | 167 | HOLD / HOLD | [李小溪(大)](https://www.weiqi.org.cn/player/professional) | HOLD |
| 上村阳生 | 140 | 12454 / 6685 | [上村陽生](https://www.nihonkiin.or.jp/player/htm/ki000063.htm) | 身份通过，待逐槽 |

## 必须保持 HOLD 的三人

- **鹤山淳志（280 槽）**：PROD 536 唯一，但 TEST 的 537 `鶴山淳志` 与 1008 `鹤山淳志` 同时归一化命中；先处理 TEST 重复目录。
- **大桥拓文（214 槽）**：PROD 462 唯一，但 TEST 的 463 `大橋拓文` 与 1086 `大桥拓文` 同时归一化命中；先处理 TEST 重复目录。
- **李小溪（167 槽）**：目录 378／377 的 canonical 为 `李小溪94`，但[中国围棋协会职业棋手名录](https://www.weiqi.org.cn/player/professional)也显示 `李小溪(大)`，[协会首页排名](https://www.weiqi.org.cn/home)出现 `李小溪05`。无年龄标记的 raw 不能直接指向 1994 年棋手，必须按逐槽年代和赛事身份区分。

## 已核的同名边界

- **金庭贤（368 槽）**：[韩国棋院旧棋手档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10000522)明确为 `金庭賢`，而[同音新棋手档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10001244)为 `金楨玹`。本表的 exact 汉字 raw 归一化只匹配旧棋手目录 34；韩文音译 raw 不在范围。
- 简繁或日文汉字仅用于人物身份和目录碰撞复核。建议中文 canonical 为表内 exact raw，不执行现有日文 canonical 改名，不推断段位后缀、英文拼写或其它变体。

## 执行前剩余闸门

分别冻结两库这 14 个 exact raw 的完整 NULL 槽及 SGF SHA；按人物官方入段／年代、原谱 PB/PW/DT/RE/SO、来源、段位、赛事语境和对手 FK 检查并显式 HOLD 异常。再审核目录、alias、名称、raw staging 的全前像与目标 ID，事务 dry 回滚后才能考虑独立执行计划。不得把 3 项 HOLD 或 17 人以外 raw 扩入。
