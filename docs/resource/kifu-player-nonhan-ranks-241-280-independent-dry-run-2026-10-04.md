# 棋手预处理：非汉字名次 241–280 身份复核与双库预演

**后续状态：两批均按审核通过的冻结计划先 TEST 后 PROD 写入并核验，
见[执行记录](kifu-player-nonhan-ranks-241-280-application-2026-10-04.md)。**

2026-10-04 独立复核原 241–260、261–280 审查表、人物来源及 TEST／PROD
实时目录。原始白名单不改；两份派生白名单只修正跨批次身份目标。
**两库仅完成事务 dry-run 并回滚，未正式写入。**

| 批次 | 派生白名单 SHA-256 | exact raw／席位（黑／白） | 复用／拟建 ID | TEST 计划 SHA-256 | PROD 计划 SHA-256 |
| --- | --- | ---: | ---: | --- | --- |
| 241–260 corrected17 | `6b3cac9843e1491ff34f9086025fc119f432ffff6640388893f66e4ac2ba1968` | 17／682（392／290） | 9／8 | `45b2b4f3be92cce85fae35f782d478c14418ff48d983792e745928d6672b9a98` | `8db3cb54e560974b627259e83c7cffcd707d2f56a7a20d370dd0d96fadea17e5` |
| 261–280 safe17 | `f9354a50e662e535c5053adf9289d291bb9e6b0aafbedd2ba85e92bbb8ab655f` | 17／601（302／299） | 13／4 | `a3047128ed3b199dc5325ada4db46a2c6aa93e57537c4acd30863a6022a5b44c` | `941ef4b61f70c70e476d651bf803b89b4efd5913b5ea5574cb4a5b704066e62a` |

两个批次合计 **34 个 exact raw／1,283 个席位（黑 694、白 589）**，
22 项复用既有 ID、12 项拟建目录 ID。四次事务预演的实际 FK、审核行与
拟建 ID 计数均与冻结计划相同，随后回滚。回滚前后 TEST 均为
265,626 已连席位／3,805 棋手 ID，PROD 均为 267,231／3,627，
两环境各 173,025 盘。冻结 inventory SHA-256 为
`dcc4f547ec196bbe850b79b6ce11a97dfda64e92343fcb2640dbd1aebaaad743`。

## 跨批次身份修正

- `HaCh'an-seok`（41 席）：[韩国棋院棋手页](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000022)
  对应此前 `HaChanSeok` 建立的“河灿锡”。旧 241–260 名单误标为新建；
  派生名单改为复用 TEST `12413`／PROD `6644`，未另建同人。
- `Yasui Shuntetsu`（37 席）：[CWI 丈和棋谱姓名表](https://homepages.cwi.nl/~aeb/go/games/games/ancient/Honinbo_Jowa/)
  直接对照“安井俊哲／Yasui Shuntetsu = Yasui Sanchi”；1828–1838 年
  对局年代与[日本棋院九世安井算知](https://www.nihonkiin.or.jp/teach/history/rekidai.html)
  相符。由暂缓转入派生 261–280 名单，复用 TEST `12455`／PROD `6686`。
  其中文规范主名沿用目录现值“安井算知（九世）”，原始棋谱姓名不变。

其他原白名单人物保留原身份决策；全部拟建名和复用 ID 的实时
主名逐一核对。连同两处修正，共 22 个复用目标均为唯一匹配，12 个拟建
中文主名在两库主名和别名表中均未出现。特别核对：

- `MiyamotoNaoki` 对应[国立国会图书馆典据“宮本直毅／Miyamoto Naoki”](https://id.ndl.go.jp/auth/ndlna/00045079)；
  [CWI 职业棋手表](https://homepages.cwi.nl/~aeb/go/misc/progression.html)
  亦把“宮本直道”列为同一人的另一写法。旧名次 216 的带空格原值
  `Miyamoto Naoki` 本次仍不扩入，仍须另批确认其 51 席前像。
- `Tsuchiya Shugen` 的 1887–1917 年对局指向同一位“本因坊秀元”；
  [日本棋院家谱](https://www.nihonkiin.or.jp/teach/history/rekidai.html)
  列十六、二十世同名再袭，[棋院对局档](https://homepages.cwi.nl/~aeb/go/games/games/Shusai/index.html)
  载 `Tsuchiya Shugen` 与 `Honinbo Shugen` 写法。
- `Uchigaki Suekichi` 的[CWI 方圆社对局](https://homepages.cwi.nl/~aeb/go/games/games/Hoensha/)
  与日本棋史资料中的棋手“内垣末吉”姓名读音和年代一致；
  [国会图书馆文库](https://ndlsearch.ndl.go.jp/file/rnavi/humanities/post_789/segoshi.pdf)
  直接载新建的“中根鳳次郎”著作，罗马名 `Nakane Hojiro` 的明治棋谱
  与其年代一致。其余来源逐项保存在原研究表。

## 暂缓及回滚后状态

6 个 exact raw／222 席继续暂缓：`Umezu Choko` 40 席（汉字对照不足）、
`Yasui Senkaku` 39 席（四、五世同名）、`RinKaiho` 38 席（既有目录碰撞）、
`TakahashiShigeyuki` 36 席（旧 ID 冲突）、`Hayashi Hakuei` 35 席
（伯／柏字形未决）、`YiSang-hun` 34 席（韩国两名同音棋手）。
两库这 6 项与所选 34 项的全部 1,505 席 FK 在回滚后均为空，40 个原文审核行
保持 `pending` 且元数据为空；12 个拟建主名未出现。聚焦导入器测试
`16 passed`。[241–260 派生白名单](kifu-player-nonhan-ranks-241-260-corrected17-exact-allowlist-2026-10-04.json)
及 [261–280 派生白名单](kifu-player-nonhan-ranks-261-280-safe17-exact-allowlist-2026-10-04.json)
各自对应同前缀的 `-plan-{test,prod}-2026-10-04.json.gz`。
