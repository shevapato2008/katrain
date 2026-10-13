# 日本七大棋战剩余六项：精确赛段候选（只读）

PROD实时基线 **89,979／173,025赛事关联**（2026-10-04 SELECT核验）。本因坊已在上一批处理；本批只研究既有碁圣、十段、棋圣、名人、王座、天元。没有写库。

[冻结JSON gzip](./kifu-event-japanese-major-next-candidates-2026-10-04.json.gz)，SHA-256：`dfe14615acd346b96e722140cf282c3d5afb3b9cf78bcb0c109fa9da3d9eaf5e`。每盘保留exact album ID、原文、日期、两项赛事FK、双方棋手及FK、来源、duplicate、完整SGF前像与SHA、EV/GN根属性和属性索引。将proposed_series_core与已有event ID明确绑定；发现用regex不属于执行规则。

|已有event ID|series_core|候选盘数|exact原文唯一数|
|---:|---|---:|---:|
|23|日本碁圣战|181|72|
|25|日本十段战|506|214|
|26|日本棋圣战|421|156|
|27|日本名人战|302|135|
|28|日本王座战|332|133|
|29|日本天元战|147|87|

合计 **1,889盘、797个精确原文**。全部当前event_id为空。只建议type FK，edition FK留空；未推断或创建届期。理论执行后关联91,868／173,025，该值不是执行结果。

类型身份依据：1,246盘原文显式日本；44盘显式Japanese英文赛事名称；599盘使用明确数字“期”、正式赛段和对应日本赛事年代作为身份推断（逐盘记录identity_basis）。日本棋院[日程](https://www.nihonkiin.or.jp/match/schedule.html)将这些赛段列在六项各自赛事内。国别省略的推断须由独立审核确认，不能仅凭“棋圣/名人”前缀归类。

EV优先，否则GN；所选属性每个值与album.event相同才入候选，807盘同值重复取第0项。331盘有不同附加标题/缺失属性hold；不按第一条或最长标题默默归类。候选无空日期或1900占位。

|hold原因|盘数|
|---|---:|
|country omitted and period/date does not establish Japanese identity|5|
|exhibition/training/news/commentary/additional title|99|
|generic title without explicit Japan or numbered competition stage|558|
|known exact excluded erroneous edition/event from previous review|2|
|pre-1976 Meijin identity belongs to old separate series or needs review|98|
|selected SGF root EV/GN has missing or different additional title|331|
|separate Taiwan Gosei/MLILY family, excluded from Japanese main batch|217|

hold合计 **1,310盘**，逐ID与完整前像在JSON中。台湾中环碁圣/梦百合217盘作为单独赛事家族hold，不纳入主批；泛称558盘不自动归日本；纪念/新闻/训练/交流附加标题99盘暂缓；1976年前名人98盘保留独立旧名人身份审查。继续排除既有审查的 `第44期日本名人战预选赛第1轮` 和 `58期日本名人战循环圈`，各1盘。

示例主批原文：`第41期日本棋圣战B组循环圈赛`40盘、`47期名人战循环圈`34盘、`73期王座战预选a组`23盘、`50期碁圣战预选a组`26盘、`第57期日本十段战最终预选决赛`15盘、`53rdJapaneseOza`13盘。所有exact原文的逐项计数见各组exact_raw_counts。

新捕获中文token范围14,789盘、英文token范围789盘，只用于发现；未进入主批/hold范围的其他赛事原文未审核，不因此被删除或自动归类。此前Oteai/Samsung/本因坊/中国天元/倡棋/新人王/中国名人已处理类型不在本批。初步结构和年代依据亦可对照[已有中文赛事审查](./kifu-event-chinese-structural-review-2026-10-04.md)；[现名人档案](https://archive.nihonkiin.or.jp/match/meijin/)与[棋圣档案](https://archive.nihonkiin.or.jp/match/kisei/)支持两类独立赛事及年代界线。

核验：候选ID唯一、候选hold无交集、逐raw计数和组计数一致、所有候选赛事FK前像空、无上一批五类type ID。本批仍是候选，未capture/dry-run/apply。
