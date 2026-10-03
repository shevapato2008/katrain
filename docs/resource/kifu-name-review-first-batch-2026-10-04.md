# 棋谱姓名与赛事直译：首批审核

数据口径：2026-10-04 正式库冻结清单，173,025 盘、346,050 个黑白棋手位置。下表的「解析组槽位」包含同一 base name 下的段位写法，但**不是**已经确认的棋谱身份关联。原始字段、赛事冠名和原值次数见 [全量 HTML 报告](kifu-preprocess-report-2026-10-04.html)。

## 棋手：逐人核名

棋院/棋协页面用于确认人物与姓名字形；维基百科用于核对中文惯用写法。下表是候选身份审核，不能仅因原始字符串含有某人姓名就把棋局链接到该 ID。双人连写、同名人物、段位和荣誉称号必须单独处理。

| 简体候选名 | 解析组槽位 | 当前目录 ID | 主要核名依据 | 待处理边界 |
|---|---:|---:|---|---|
| 李昌镐 | 2,199 | 143 | [韩国棋院](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001)、[中文维基](https://zh.wikipedia.org/wiki/李昌鎬) | 李昌锡是另一人；段位后缀分离 |
| 赵治勋 | 2,065 | 608 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000004_2.html)、[中文维基](https://zh.wikipedia.org/wiki/趙治勳) | 名誉、本因坊等称号不进入人名 |
| 曹薰铉 | 1,970 | 46 | [韩国棋院](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000002)、[中文维基](https://zh.wikipedia.org/wiki/曹薰铉) | 曹熏铉、曹熏炫作原值变体待逐项核对 |
| 林海峰 | 1,690 | 仅 298「林海峯名誉」 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000009.htm)、[中文维基围棋人物页](https://zh.wikipedia.org/wiki/林海峰_(围棋)) | 与同名人物区分；名誉称号拆出 |
| 小林光一 | 1,644 | 82；另 338「小林光一名誉」 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000001.htm) | 两个旧 ID 待有依据合并 |
| 朴廷桓 | 1,540 | 54 | [韩国棋院](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000457) | 段位分离；双人连写排除 |
| 李世石 | 1,443 | 无 | [韩国棋院：李世乭](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000119)、[中文维基：李世乭](https://zh.wikipedia.org/wiki/李世乭) | 「李世石」是常见中文替写，先记录两个字形，最终 canonical 待审 |
| 依田纪基 | 1,396 | 57 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000101.htm) | 紀/纪及段位、头衔分离 |
| 大竹英雄 | 1,390 | 无 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000008.html) | 建人物 ID 后再关联棋局 |
| 藤泽秀行 | 1,379 | 无 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000005.htm)、[中文维基](https://zh.wikipedia.org/wiki/藤泽秀行) | 藤沢/藤澤/藤泽字形；旧名另审 |
| 山下敬吾 | 1,376 | 242 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000322.htm) | 排除双人连写 |
| 古力 | 1,365 | 201 | [中国围棋协会职业棋手](https://www.weiqi.org.cn/player/professional) | 拼音变体待逐项核对 |
| 常昊 | 1,329 | 无 | [中国围棋协会职业棋手](https://www.weiqi.org.cn/player/professional) | `changhao` 仅为拼音推断，暂不自动并 |
| 刘昌赫 | 1,320 | 69 | [中文维基](https://zh.wikipedia.org/wiki/刘昌赫)、[英文维基](https://en.wikipedia.org/wiki/Yoo_Chang-hyuk) | 劉昌赫及韩文/罗马字变体 |
| 加藤正夫 | 1,297 | 无 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000002.html) | 段位分离；双人连写排除 |
| 武宫正树 | 1,294 | 490「武宮正樹」 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000003.htm) | 简繁/日字形归并，保留原 ID |
| 井山裕太 | 1,281 | 56 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000385_10.html) | Iyama Yuta 等读音变体 |
| 徐奉洙 | 1,273 | 108 | [中文维基](https://zh.wikipedia.org/wiki/徐奉洙)、[英文维基](https://en.wikipedia.org/wiki/Seo_Bong-soo) | `SeoPong-su` 拼法需逐项关联 |
| 张栩 | 1,272 | 80；另 313「張栩」 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000331_4.html) | 两个旧 ID 待合并 |
| 王立诚 | 1,246 | 17；另 353「王立誠」 | [日本棋院](https://www.nihonkiin.or.jp/player/htm/ki000065.htm) | 两个旧 ID 待合并 |
| 吴清源 | 317；另 `Go Seigen` 949 | 1 | [中文维基](https://zh.wikipedia.org/wiki/吴清源) | 已有中文 canonical 与英语别名；原值与棋局链接另算 |

这 21 个解析组共 30,086 个槽位（8.69%），其中仍含待剔除的混合写法；它只是高频审核范围，**不是已完成关联的槽位数**。

首批可单独建立人物目录身份的四人是常昊、加藤正夫、大竹英雄、藤泽秀行。核名依据分别为[中国围棋协会职业棋手名录](https://www.weiqi.org.cn/player/professional)、日本棋院的[加藤正夫](https://www.nihonkiin.or.jp/player/htm/ki000002.html)、[大竹英雄](https://www.nihonkiin.or.jp/player/htm/ki000008.html)、[藤沢秀行](https://www.nihonkiin.or.jp/player/htm/ki000005.htm)资料；藤泽秀行的简体写法另见[中文维基](https://zh.wikipedia.org/wiki/藤泽秀行)。`katrain.web.kifu.catalog_player_seed` 仅在四个同字简体原值均已存在、且目录中无规范化姓名/别名冲突时，原子地建立缺失的人物 ID。它不关联棋谱、不创建译名展示审核记录，也不表示用户已批准展示。

## 赛事：直接翻译展示，身份另审

先保留赞助商、年份、届次、预选/循环圈等阶段以及轮次，再翻译可识别的核心。下列 13 个拉丁字母核心对应 627 种 EV 原值、21,174 盘（12.24%）；其中 Castle Game 和 JapanPromotionTournament 的身份仍需复核。**本次实际入库的是前 11 个明确核心的 599 种原值、20,153 盘，状态为简中待审草稿；最后两个仅在此列作翻译候选。**翻译后的显示文本不能自动创建赛事类型 ID 或届次 ID。

| 原核心 | 盘数 | 简中显示核心 | 处理 |
|---|---:|---|---|
| Oteai | 6,159 | 日本大手合 | 与中文「日本大手合」暂不自动合并 |
| Honinbo | 2,723 | 本因坊战 | 原文届期保留 |
| Judan | 2,220 | 十段战 | 原文届期保留 |
| Oza | 2,061 | 王座战 | 原文届期保留 |
| Old Meijin | 1,199 | 旧名人战 | 与现代名人战分开；[日本棋院旧名人战资料](https://archive.nihonkiin.or.jp/match/z-obizaka/7final.pdf) |
| Pro Best Ten | 1,171 | 职业十杰战 | 原文届期保留 |
| Nihon Ki-in Championship | 1,156 | 日本棋院选手权战 | 原文届期保留 |
| Tengen | 1,014 | 天元战 | 原文届期保留 |
| Meijin | 927 | 名人战 | 与旧名人战分开 |
| Kisei | 899 | 棋圣战 | 原文届期保留 |
| Gosei | 624 | 碁圣战 | 原文届期保留 |
| Castle Game | 539 | 御城碁 | 显示候选；[日本棋院历史资料](https://archive.nihonkiin.or.jp/history/04.html)，盘数/年代须核对 |
| JapanPromotionTournament | 482 | 日本升段赛 | 字面直译；与 Oteai 的关系另审 |

`10th Honinbo` 可显示「第10期本因坊战」，`Oteai 1960` 可显示「1960年日本大手合」，`2007金立杯围甲联赛第11轮` 可显示「2007年金立杯围甲联赛第11轮」。`金立`、`SGW` 等冠名不得省略。`GNUGo3.8` 是程序名，`段位赛`/`个人赛` 是通用说明，`Hoensha game` 是档案标签，都不应建赛事类型 ID。
