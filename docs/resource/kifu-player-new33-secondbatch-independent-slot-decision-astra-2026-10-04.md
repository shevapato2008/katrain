# new33 第二批：独立逐槽身份决定

只读审核，2026-10-04。决定 JSON SHA-256：`dde6d06c6ada0b1520a9854a212a8a28de3e72809abffe2ccc2945e44bb795fb`。
配套精确重基线 JSON SHA-256：`70d57853166704203003935186c68de1e78e6f2382db8a1e29d2c1df1af06509`。

**16 raw / 3,298 槽已逐槽评估；批准 2,755 槽 / 2,697 局，HOLD 543 槽。** 允许每库各新建 16 个明确中文 canonical，仅绑定固定 approved_slots。没有数据库写入或代码修改；本文件不是执行回执。

首批 8 raw /1,606 槽的原决定不变（1,451 已批准、155 HOLD）；原 9 raw /2,469 身份 HOLD 全部保留。累计 new33 为 **4,206 APPROVE + 3,167 HOLD = 7,373**。六种其他语言维持英文回退，尚未进入翻译。

| raw /拟 canonical | 批准 | HOLD | 官方身份依据 |
|---|---:|---:|---|
| 周平强 | 303 | 30 | [官方档案](https://www.haifong.org/profession/venue/FD4F71FF30877A4D784D40B82F6ABA13) |
| 刘耀文 | 235 | 35 | [官方档案](https://www.haifong.org/profession/venue/96D22F1BFCD9F6FC92CC958E167EC390) |
| 刘曦 | 190 | 47 | [官方档案](https://wqapi.cwql.org.cn/playerInfo/CWA000094) |
| 黄彦诚 | 176 | 46 | [官方档案](https://www.haifong.org/profession/venue/7CE0B44C8D68B4C450E08D17864AA4D9) |
| 陈逸达 | 208 | 13 | [官方档案](https://www.haifong.org/profession/venue/AE397B760DDE4789458D37C595AA3E9C) |
| 夏大铭 | 156 | 50 | [官方档案](https://www.haifong.org/profession/venue/70228523DBA5896634FC5837AC5CA377) |
| 杨嘉源 | 160 | 45 | [官方档案](https://www.nihonkiin.or.jp/player/htm/ki000222.htm) |
| 汤川光久 | 170 | 32 | [官方档案](https://kansaikiin.jp/kisi_prof/yukawamitsuhisa.html) |
| 陈义翔 | 182 | 16 | [官方档案](https://www.haifong.org/profession/venue/98406AFBE07BEF7B4CA1DD035F6AD998) |
| 横田茂昭 | 150 | 47 | [官方档案](https://kansaikiin.jp/kisi_prof/yokotashigeaki.html) |
| 张学斌 | 132 | 52 | [官方档案](https://wqapi.cwql.org.cn/playerInfo/CWA000119) |
| 后藤俊午 | 139 | 33 | [官方档案](https://www.nihonkiin.or.jp/player/htm/ki000147.htm) |
| 秦悦欣 | 141 | 31 | [官方档案](https://wqapi.cwql.org.cn/playerInfo/CWA000190) |
| 曹潇阳 | 141 | 23 | [官方档案](https://wqapi.cwql.org.cn/playerInfo/CWA000147) |
| 张正平 | 140 | 20 | [官方档案](https://www.haifong.org/profession/venue/8EF756A53BCB8BD1D3C8CF8EEFDF2A69) |
| 党希昀 | 132 | 23 | [官方档案](https://www.haifong.org/profession/venue/058D14C68533983342FAF53879C0BCE2) |

## 身份与逐槽证据

曹潇阳的[中国棋协 CWA000147 详情](https://wqapi.cwql.org.cn/playerInfo/CWA000147)本次成功取得，确认 2006-07-24 入段、2024-05-31 六段及全部中间升段日期。陈义翔的[台湾棋院 2009 专访](https://taiwangorg.blogspot.com/2009/01/blog-post_12.html)确认 2001 年入段，与海峰棋院的后续升段记录衔接。刘曦与 CWA000316 刘熙保持不同身份；杨嘉源不与业余语境的杨耀源模糊归并。

逐槽重新解析完整 SGF，核对字节 SHA、PB/PW/BR/WR/DT/首项 GN/SO/结果与行内容、手数、19 路、让子/摆子、完整来源关联、对手 FK/目录及官方入段/升段区间。两库原始精确成员一致；16 个身份在冻结全目录 players/aliases/names 中按列明字形、本名、读音和罗马字变体重查均为零 owner。所有 guard 重新计算，与首批原有 deferred 前像逐项一致。

对全 7,168 局捕获检查完整 SGF 与精确主线走子重复，发现的两组 13178/13278、25764/36190 均在本批之外。本结论不声称覆盖全数据库、旋转棋盘或前缀重复。

保守 HOLD 包含：170 个文件名式标题槽、95 个紧凑拉丁赛事标题槽、特殊/交流/教学等语境、79 个段位年代冲突、39 个入段年份区间内记录、22 个一月一日精度疑点；原因可重叠。紧凑拉丁标题中有真实职业赛事，HOLD 表示本轮没有专门裁定该语境，不表示身份无效。逐槽理由全部在 JSON。

官方升段只有年/月精度时保留相邻段位；未捏造精确日期。497、602、1348 的首项 SO 为空，但第二项 SO 和完整 19x19 来源关联一致，按精确成员接受。73249、106142 的日期、双方、结果和手数与 [CWI 1990 交流赛索引](https://homepages.cwi.nl/~aeb/go/games/games/CJGoExchange/1990/index.html)一致；75293 的胜负与该索引冲突，继续 HOLD。未改任何原始字段。

## 已提交批次的精确重基线

| 前置批次 | 本批重叠 | 核对 |
|---|---|---|
| next3，2,153 个赛事 FK | 170 局 /178 槽，其中批准 172 槽 | 重放已固定补充及两库实际后像；只允许对应 event_id |
| 首批，1,451 个棋手 FK | 37040、75303 两局 | 完整实际后像仅 white_player_id 变化；目标分别为李泰贤和既有本田寿子 |
| next514，474 个赛事 FK | 73249、75293、106142 三局 | 完整实际后像仅 event_id: NULL→75；75293 玩家仍 HOLD |

两库 7 个新增棋手目录行，以及 75/86/87 赛事目录行的 ID、名称、created_at 和完整 SHA 均已固定。还重放了 next514 与旧 HOLD 相交的 35821、66361、139660；它们的事件变化不释放任何玩家 HOLD。这三行也包含在 full8 新捕获中，完整实际后像与精确推导一致。

执行必须同时使用[身份决定](kifu-player-new33-secondbatch-independent-slot-decision-astra-2026-10-04.json)与[精确重基线](kifu-player-new33-secondbatch-committed-batches-exact-rebase-2026-10-04.json)。后者列出所有 3,298 槽的有效完整前像、首批 1,439 局/1,451 槽及 next514 六局的完整 delta、实际八行后像与完整目录守卫。身份与已知漂移门禁通过；仍须新的只读捕获、环境计划及事务回滚演练。任何未解释字段差异必须失败，禁止跳过 event_id、对手 FK、created_at、SGF 或目录守卫。

新增来源 manifest SHA-256：`7374774d484be4b74f9502b93e6ce0eb6046f3ecda5073bb003d4d2302ebc1b7`。
