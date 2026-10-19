# 日本六项大棋战：独立身份裁决

2026-10-04，Astra 独立只读裁决。**PASS 修订后的 1,839 盘／771 个精确原文；新增 HOLD 50 盘。** 原 1,310 盘 HOLD 全部保留，合计 **1,360 盘 HOLD**。未写数据库，未修改原候选包或原 review。

[机器可读裁决](./kifu-event-japanese-major-next-independent-decision-astra-2026-10-04.json)包含精确十列 `approved_albums`、目标 ID、逐盘 SGF SHA、全部 HOLD 八列前像、两环境完整赛事 catalog 与独立棋手 FK 前像。其[文件 SHA](./kifu-event-japanese-major-next-independent-decision-astra-2026-10-04.json.sha256)可直接核验。

|目标 ID|赛事|批准|其中省略国别|
|---:|---|---:|---:|
|23|日本碁圣战|180|128|
|25|日本十段战|477|59|
|26|日本棋圣战|420|101|
|27|日本名人战|285|84|
|28|日本王座战|330|209|
|29|日本天元战|147|18|

新增 HOLD 的精确 ID、完整根属性和理由均在 JSON：

- **36 盘匿名记录**：PB/PW/RE 全缺，库中双方均为 Unknown；缺少独立具体对局锚点。十段 29、名人 6、碁圣 1。没有仅凭赛事文字批准。
- **10 盘业余名人**：19837、39871、39885、51853、73536、73548、73557、73622、73631、73637。[日本棋院 2025 年报道](https://www.nihonkiin.or.jp/event/area/ichigaya/post_1307.html)直接确认 19837 的日期、季军赛和双方，属于业余系列。
- **51884 职业业余名人**：[官方公告](https://www.nihonkiin.or.jp/event/area/other/10_38.html)确认 2016-02-27 大表拓都对井山裕太是职业与业余名人的特别对局。
- **23498 儿童棋圣**：[官方历届表](https://www.nihonkiin.or.jp/event/amakisen/kurashiki/15/data.html)确认 2025-12-21 田中拓翔对郑智皓属于低学年组决赛。
- **85435 丰田杯世界王座日本选拔**：[日本棋院第二届赛事页](https://archive.nihonkiin.or.jp/match/toyota/002.htm)明确这是国际世界王座系列，不归国内王座。
- **138585 王座误标**：原文「日本第39届王座战第2局」，但[官方第39期十段战](https://archive.nihonkiin.or.jp/match/jyudan/039.htm)精确对应 2001-03-22 小林光一对王立诚、白半目胜、第二局。HOLD 此 ID，不自动改投十段。

599 盘省略国别记录均逐盘记录期数、日期、双方、SGF SHA 和官方历届页。批准依据是正式期数、赛段、相容年代及棋手语境的综合推断，并非宣称外部来源逐盘验证了这 599 份棋谱。[棋圣官方页](https://www.nihonkiin.or.jp/match/kisei/047.html)包括 S/A/B/C 循环圈、FT 和挑战者决定战；[名人](https://www.nihonkiin.or.jp/match/meijin/047.html)、[十段](https://www.nihonkiin.or.jp/match/jyudan/061.html)、[王座](https://www.nihonkiin.or.jp/match/oza/073.html)、[碁圣](https://www.nihonkiin.or.jp/match/gosei/050.html)、[天元](https://www.nihonkiin.or.jp/match/tengen/049.html)各页支持对应预选、本赛及挑战阶段。历史年份采用官方历届表，未按固定年份偏移量创建届期。

**16356 单独说明**：原文「73期王座战挑战赛5番棋4局2-1」的期数与日期不符；[官方第72期王座](https://www.nihonkiin.or.jp/match/oza/072.html)确认 2024-12-06 井山裕太对芝野虎丸、黑中盘胜。批准其王座**类型**，原期数、SGF、日期保持原像，届期 FK 留空。1165 虽缺 RE，双方与 GC 结果及官方棋圣第一局相符；3739 是官方名人第四局首日 30 手记录，保留类型批准，不将其 Draw 字段当作已完赛和棋。

旧名人与现名人保持边界：[现名人历届表](https://www.nihonkiin.or.jp/match/meijin/archive.html)首届头衔赛为 1976 年，[大竹英雄官方履历](https://www.nihonkiin.or.jp/player/htm/ki000008.html)明确称 1975 年为第14期旧名人。原「1976年前」98 盘继续 HOLD，未宣称其中所有预选必属旧系列。台湾碁圣／中环碁圣也独立：[海峰棋院历史说明](https://www.haifong.org/game/classes/480E360835EAB350F93094AAECD2A797)记载 2008 年开办、2013 年改名并重新起算；原合并类别 217 盘实际包含台湾赛事 104 盘、MLILY 113 盘，全部保留 HOLD。原纪念、交流、网络特别对局等 99 盘同样未扩大批准。

两库各在 `REPEATABLE READ READ ONLY` 事务读取候选与原 HOLD 共 3,199 行，结束 `ROLLBACK`：PROD 快照 `1718886:1718886:`，06:55:34–38 UTC；TEST 快照 `4108869:4108869:`，06:55:35–39 UTC。PROD 与候选完整前像零差异；TEST 的八列前像、棋手原文、SGF 完全一致，只有既有棋手 FK 环境差异（黑 1,996、白 2,013 槽位），已分别冻结。两库六个目标 ID/canonical 均一致。关联基线分别为 PROD **89,979**、TEST **89,497**，均有 173,025 盘。

重新解析全部 3,199 份 SGF 并核对 SHA；1,889 份候选均以 GN 精确匹配原文，无 EV、RO 或异值标题，GC 均以原赛事文字开头。两条 C 属性为广告注释，未作为赛事身份依据。完整根属性、SQL、两库只读快照和 23 个来源响应体在 `~/.local/share/kifu-name-audit/2026-10-04/event-japanese-major-independent/`，文件路径及 SHA 已绑定于 JSON。

执行只允许精确 ID 的 `event_id` 更新，`event_edition_id` 保持 NULL；须复核两环境各自 catalog、前像及 SGF 守卫。新增 HOLD 与批准记录有三个共享 raw，不能按 raw 整批更新。

- 原候选 gzip SHA：`dfe14615acd346b96e722140cf282c3d5afb3b9cf78bcb0c109fa9da3d9eaf5e`。
- 十列批准清单 SHA：`d16e4c6e599ab5ff3456d319a1255742c0a5aa8a852aeee30b9689c5fbc7d4a5`。
- assignments SHA：`959ab69db8b92ac99495b0e0039c641fba5904854c2ebb708ed8e8a87512e8fe`。
- 内嵌裁决 SHA：`7e2f3fda3e9e22a74ddda648114634c4d01e7e2bec25afc0932183b269fcd7d7`。
- 最终 JSON 文件 SHA：`ef303fc470a53c44fdcf6f310d413fcbee83a506d2ba868bb76bda06fe76e288`。
