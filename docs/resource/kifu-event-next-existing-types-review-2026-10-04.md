# 既有赛事类型下一批精确候选（只读）

PROD 基线：173,025 盘，赛事关联 87,651 盘。2026-10-04 经 `ssh ucloud-v100` 对 `katrain-ucloud-postgres-1` 只执行 SELECT；没有写库。本包是待审核候选，未获审核也未执行。

冻结包：[JSON gzip](./kifu-event-next-existing-types-candidates-2026-10-04.json.gz)。压缩文件 SHA-256：`dec60fc706bb8b64d55f59168744ff44992752f9b3be8e10455f225cc92d764a`。逐盘保留 ID、原文、当前两个 FK、日期、选手、来源路径、完整 SGF 前像、SGF hash 与根节点 EV/GN；执行必须按冻结 ID/原文核验，不能再用前缀扩大范围。

|目标已有 event ID|canonical|候选盘数|精确原文数|
|---:|---|---:|---:|
|24|日本本因坊战|666|205|
|37|日本新人王战|159|7|
|58|中国围棋天元战|799|149|
|59|中国倡棋杯|638|85|
|65|中国围棋名人战|69|7|

合计 **2,331 盘**。本批只建议类型关联，届期 FK 全部空置；原文届次、年份、冠名与赛段保留，不推断届期。若全部执行，理论关联为 89,982／173,025（52.00%），该数不是执行结果。

根属性选择：有 EV 先用 EV，否则用 GN；所选属性每个值必须与 album.event 精确相同。1,118 盘存在同值重复根属性，冻结选第 0 项。异值附加标题、多值冲突或缺失共 207 盘 hold；候选日期没有空值或 1900 占位。

|hold原因|盘数|
|---|---:|
|KB/Futures first-versus-second division identity requires teams/roster verification|1025|
|Xiamen invitation event is not Chinese Meijin title tournament|12|
|anniversary/exhibition/international match/commentary title|10|
|historical exhibition or institutional match, not title tournament|22|
|identity ambiguity: event 45 versus 46; hold entire family|356|
|known exact erroneous event from earlier reviewed exclusion|1|
|regional qualifying scope requires explicit review|106|
|selected root SGF EV/GN is multiple/missing/different from album event|207|
|short title lacks tournament identity evidence|3|

hold 合计 **1,742 盘**，完整 ID 与前像在包中。韩国“KB…围乙”和带一级联赛队名的原文不能直接归 ID 57；Nihon Ki-in #1 无法仅凭简称判定 ID 45/46。中国名人厦门邀请赛不归中国名人战；本因坊秀哉纪念、吴清源三番棋、方圆社对抗不归本因坊头衔赛。同里杯中韩对抗、周年特别赛、讲解标题亦暂缓。倡棋台湾/台北选拔虽可能属于同一赛事旅程，106 盘留给下一次明确范围审核。已知错误 `第39期日本本因坊战挑战赛5番棋第4局` 继续 hold。

身份来源：已有 [中文赛事审查](./kifu-event-chinese-structural-review-2026-10-04.md)、[天元及倡棋审查](./kifu-event-futures-tianyuan-changqi-review-2026-10-04.md) 和日本棋院[棋战日程](https://www.nihonkiin.or.jp/match/schedule.html)。本批新增的是已有类型的赛段/文字写法，SGF及日期证明来源一致；尚未单独对207盘异值标题进行赛事属性选取。

核验：候选 ID 唯一，候选与 hold 无交集，候选当前 event_id 全空；各类计数和精确原文计数从冻结逐盘前像重新求和。原始宽范围 SELECT 捕获 11,518 盘，本包仅覆盖审查的五类以及两类身份 hold，其余未研究原文没有自动归入。
