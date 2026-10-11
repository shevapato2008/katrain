# 非汉字棋手第 281–300 名身份审查（2026-10-04）

冻结 post7 排名。TEST/PROD 只读事务确认 20 exact raw 各 627 槽，全部 FK 为 NULL；18 个 / 566 槽列精确白名单，2 个 / 61 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 281 | `KatoShin` | 33 | 加藤信 | 4053 / 9849 | 白名单 |
| 282 | `OyamaKunio` | 33 | 大山国夫 | 4246 / 10041 | 白名单 |
| 283 | `Tsutsui Katsumi` | 33 | 筒井胜美 | 5705 / 11476 | 白名单 |
| 284 | `Hayashi Genbi` | 32 | 林元美 | 新建 / 新建 | 白名单 |
| 285 | `Kikuchi Yasuro` | 32 | 菊池康郎 | 新建 / 新建 | 白名单 |
| 286 | `Suzuki Hideko` | 32 | 铃木秀子 | 新建 / 新建 | 白名单 |
| 287 | `Takeda Misawo` | 32 | 武田美佐绪 | 新建 / 新建 | 白名单 |
| 288 | `YiYeong-sin` | 32 | 李英信 | 5078 / 10860 | 白名单 |
| 289 | `BaekSeongHo` | 31 | 白成豪 | 5608 / 11381 | 白名单 |
| 290 | `Hayashi Yugen` | 31 | 林祐元 | 新建 / 新建 | 白名单 |
| 291 | `Honinbo Dochi` | 31 | 本因坊道知 | 新建 / 新建 | 白名单 |
| 292 | `MiyamotoYoshihisa` | 31 | 宫本义久 | 新建 / 新建 | 白名单 |
| 293 | `SoYokoku` | 31 | 苏耀国 | 暂缓 | 暂缓 |
| 294 | `TainakaShin` | 31 | 鲷中新 | 6642 / 12411 | 白名单 |
| 295 | `Watanabe Shokichi` | 31 | 渡边升吉 | 5410 / 11185 | 白名单 |
| 296 | `金寅KimIn` | 31 | 金寅 | 6139 / 11907 | 白名单 |
| 297 | `Fujita Toyojiro` | 30 | 藤田丰次郎 | 新建 / 新建 | 白名单 |
| 298 | `Higuchi Kenryo` | 30 | 樋口贤良（待核） | 暂缓 | 暂缓 |
| 299 | `IshikuraNoboru` | 30 | 石仓升 | 新建 / 新建 | 白名单 |
| 300 | `Koizumi Shigeo` | 30 | 小泉重郎 | 4434 / 10225 | 白名单 |

暂缓项：
- `SoYokoku`：CWI 同行列蘇耀国/So Yokoku；目录有苏耀国167/168与蘇耀国316/317两个现存 ID，先去重。
- `Higuchi Kenryo`：CWI 只见 Higuchi Kenryo 罗马字，未找到可靠汉字姓名，暂缓。

逐条来源与注释见[审查 JSON](kifu-player-nonhan-ranks-281-300-review-2026-10-04.json)，可导入项见[精确白名单 JSON](kifu-player-nonhan-ranks-281-300-exact-allowlist-2026-10-04.json)。未写数据库。
