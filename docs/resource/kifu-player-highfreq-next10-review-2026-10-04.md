> 本准备资料已被实时预检淘汰；不是执行或批准范围。最终可审查范围见 `kifu-player-highfreq-next6-review-2026-10-04.md`。三村智保、李维清、邬光亚已关联；张涛暂缓。

# 下一批高频中文姓名：10 人，4,934 槽

冻结 review 来自 TEST/PROD post7 inventory。只纳入下表完整 exact raw，既有 canonical 唯一，冻结别名无异人冲突，两环境各 4,934 NULL 候选、0 保护旧 FK、0 exact 同名对手、0 当前目标 FK 对手。目录扫描与排除变体见 `kifu-player-highfreq-next10-catalog-scan-2026-10-04.json`。这些冻结检查需经实时 capture 与事务回滚验证；当前未 apply。

| exact raw | 槽 | PROD | TEST | 官方身份来源 |
|---|---:|---:|---:|---|
| 卢奕铨 |559|474|475|[海峰棋院：盧奕銓](https://haifong.org/news/content/5E2067B4207E82F4F463D53DDA730A89)|
| 伊田笃史 |550|75|75|[日本棋院：伊田篤史 / IDA Atsushi](https://www.nihonkiin.or.jp/player/htm/ki000427.htm)|
| 淡路修三 |514|591|592|[日本棋院：淡路修三 / AWAJI Shuzo](https://www.nihonkiin.or.jp/player/htm/ki000043.html)|
| 杨子萱 |489|197|198|[海峰棋院：楊子萱](https://www.haifong.org/venue/C52F5EFDF989D8CE3BA53AB7A2355F45)|
| 张涛 |465|246|247|[国家体育总局：围棋棋手张涛](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22694119/content.html)|
| 杨楷文 |450|14|14|[国家体育总局：杨楷文天元赛挑战权](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c29367234/content.html)|
| 苏耀国 |448|167|168|[日本棋院：蘇耀国](https://www.nihonkiin.or.jp/player/htm/ki000330.htm)|
| 三村智保 |482|190|191|[日本棋院：三村智保](https://archive.nihonkiin.or.jp/player/htm/ki000223.htm)|
| 李维清 |495|382|383|[国家体育总局：李维清王中王夺冠](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c25899654/content.html)|
| 邬光亚 |482|568|569|[国家体育总局：理光杯邬光亚](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c23073971/content.html)|

官方来源原名与既有简体中文 canonical 对应是本批身份判断。未创建、重命名或合并目录，未把名含目标子串的其他目录当作此人。

段位变体共12槽排除：淡路修三全角空格九段1、七段1、六段1、八段1、九段3；张涛三段1；三村智保九段1、五段1；苏耀国八段1；邬光亚六段1。其他排除：杨楷文文兆京1、楊杨子萱1、建桥李维清2。

暂缓姓名：周鹤洋（PROD不存在正确 canonical）；赵善津（目录为趙善津）；林士勋、工藤纪夫、周俊勋（新 canonical 或传统字目录需单独核对）；桥本宇太郎（当前冻结旧目录缺失，需最新目录核）；李志贤（韩国同音不同汉字身份需独立验证）。上述不在本批范围。

Review SHA-256：PROD `e7823756c148a8e06ee141730c4c16a72d6bdd93e950b74bc59bb76ee6a9d7e9`；TEST `7d91a98d6efdaab02ff4770e2e02eb29f33cf10eb29bb8890fd2a07d21e7b3de`。
