# Korean GS/Women’s Guksu 后：下一批 formal event cores（只读）

状态：`CANDIDATES_ONLY_NO_DB_WRITES`。Korean two 已在 TEST/PROD 写入 ID 92/93；本次只读取其后的 `event_id IS NULL` rows。

| family | proposed canonical | TEST/PROD rows |
|---|---|---:|
| `cn_lanke` | 中国衢州烂柯杯 | 1,032 / 1,032 |
| `kr_kiwang` | 韩国棋王战 | 357 / 357 |
| `kr_ten` | 韩国十段战 | 296 / 296 |

边界：仅精确韩国 Kiwang ordinal/Final、明确韩国十段标题、明确衢州烂柯杯。其他国家棋王、裸棋王、韩国／中国围乙或世界烂柯标题继续 HOLD。19 个 Korean two 新 HOLD 与既有 4,273 个 HOLD 均保护；未作赛事身份、届次或写入决定。每个 TEST/PROD gzip 保留完整 album/SGF、SGF SHA、source associations，并附 post-Ahan 全目录基线。
