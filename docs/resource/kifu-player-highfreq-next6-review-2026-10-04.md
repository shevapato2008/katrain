# 下一批高频中文姓名：6 人，3,010 槽

冻结 review 来自 TEST/PROD post7 inventory。只纳入下表完整 exact raw，既有 canonical 唯一，冻结别名无异人冲突，两环境各 3,010 NULL 候选、0 保护旧 FK、0 exact 同名对手、0 冻结目标 FK 对手。目录扫描与排除变体见 `kifu-player-highfreq-next10-catalog-scan-2026-10-04.json`。这些冻结检查需经实时 capture 与事务回滚验证；当前未 apply。

| exact raw | 槽 | PROD | TEST | 官方身份来源 |
|---|---:|---:|---:|---|
| 卢奕铨 |559|474|475|[海峰棋院：盧奕銓](https://haifong.org/news/content/5E2067B4207E82F4F463D53DDA730A89)|
| 伊田笃史 |550|75|75|[日本棋院：伊田篤史 / IDA Atsushi](https://www.nihonkiin.or.jp/player/htm/ki000427.htm)|
| 淡路修三 |514|591|592|[日本棋院：淡路修三 / AWAJI Shuzo](https://www.nihonkiin.or.jp/player/htm/ki000043.html)|
| 杨子萱 |489|197|198|[海峰棋院：楊子萱](https://www.haifong.org/venue/C52F5EFDF989D8CE3BA53AB7A2355F45)|
| 杨楷文 |450|14|14|[国家体育总局：杨楷文天元赛挑战权](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c29367234/content.html)|
| 苏耀国 |448|167|168|[日本棋院：蘇耀国](https://www.nihonkiin.or.jp/player/htm/ki000330.htm)|

官方来源原名与既有简体中文 canonical 对应是本批身份判断。未创建、重命名或合并目录，未把名含目标子串的其他目录当作此人。

最终六人范围的段位变体共8槽排除：淡路修三全角空格九段1、七段1、六段1、八段1、九段3；苏耀国八段1。其他排除：杨楷文文兆京1、楊杨子萱1。

暂缓姓名：周鹤洋（PROD不存在正确 canonical）；赵善津（目录为趙善津）；林士勋、工藤纪夫、周俊勋（新 canonical 或传统字目录需单独核对）；桥本宇太郎（当前冻结旧目录缺失，需最新目录核）；李志贤（韩国同音不同汉字身份需独立验证）。上述不在本批范围。

实时报错发现旧 post7 中三村智保482、李维清495、邬光亚482共1,459槽现已正确关联，已从本批删去。张涛465槽因同名身份需进一步核实整体暂缓；冻结日期跨度2004-02-11至2026-01-25，最早样本album147247“聂道少年队VS龙虎少年队第五台袁泽执黑2目半胜张涛”；后续有2012围甲对范蕴若、2014围甲对范廷钰、2016围甲对黄云嵩、2020浙江体彩围甲对李喆及2024烂柯杯对林君谚。官方来源证明成人浙江棋手张涛存在，尚不足以单独证明全部早年原值均是同一人，故不纳入。

最终 review SHA-256：PROD `1cc1a54a0b7771cf7e7984c63d90bad4ed05ceb9db8a5c3e6cbb832fba9ebe83`；TEST `8413ebb91936a1e31aa09046f6a22cd07bcf9dc5c91f83ed08ca32766fed5f72`。

next10 文件是已被实时检查淘汰的准备资料；仅 next6 review 可用于当前候选计划。下一波可独立核对最新目录桥本宇太郎805、黄翊祖432、上野爱咲美426、志田达哉422等。本批坚持六个已验证既有目标。

PROD 已完成实时完整 capture 与事务 rollback dry-run：3,010候选、0保护、0hold、6 exact raw。canonical 唯一性、normalized alias、staging status/metadata、完整 exact scope及对手 FK 通过；回滚后重新 capture 前像完全一致。未 apply。计划 SHA-256 `52daf7fbb6cb2846c98fcdf1b9f2ede90552097b8699a640f4f8db3158815854`。TEST 按相同范围重试成功，实时完整 capture、事务 rollback dry-run通过且回滚后前像完全一致；计划 SHA-256 `2dcdfbcd37b61f143b729bd86a86973be80550a88c47e0dbbbf140460ec68fa3`。两环境均未 apply。
