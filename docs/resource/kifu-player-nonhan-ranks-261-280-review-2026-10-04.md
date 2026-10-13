# 非汉字棋手第 261–280 名身份审查（2026-10-04）

冻结 post7 排名。TEST/PROD 只读事务确认 20 exact raw 各 706 槽，全部棋手 FK 为 NULL；16 个 / 564 槽列精确白名单，4 个 / 142 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 261 | `Honinbo Satsugen` | 37 | 本因坊察元 | 新建 / 新建 | 白名单 |
| 262 | `ImSeon-keun` | 37 | 林宣根 | 5176 / 10957 | 白名单 |
| 263 | `Kosugi Tei` | 37 | 小杉丁 | 4420 / 10211 | 白名单 |
| 264 | `Nagahara Yoshiaki` | 37 | 长原芳明 | 6262 / 12028 | 白名单 |
| 265 | `OtakeHideo` | 37 | 大竹英雄 | 879 / 1091 | 白名单 |
| 266 | `Yasui Shuntetsu` | 37 | 安井俊哲算知（九世） | 暂缓 | 暂缓 |
| 267 | `Honinbo Shusai` | 36 | 本因坊秀哉 | 4833 / 10619 | 白名单 |
| 268 | `IshigureIkuro` | 36 | 石榑郁郎 | 5645 / 11418 | 白名单 |
| 269 | `TakahashiShigeyuki` | 36 | 高桥重行（后高桥俊光） | 暂缓 | 暂缓 |
| 270 | `Hayashi Hakuei` | 35 | 林伯荣／林柏荣（待核） | 暂缓 | 暂缓 |
| 271 | `Kishimoto Saichiro` | 35 | 岸本左一郎 | 新建 / 新建 | 白名单 |
| 272 | `Nakane Hojiro` | 35 | 中根凤次郎 | 新建 / 新建 | 白名单 |
| 273 | `O Rissei` | 35 | 王立诚 | 17 / 17 | 白名单 |
| 274 | `Yamamoto Masato` | 35 | 山本正人 | 4502 / 10293 | 白名单 |
| 275 | `JeongSuHyun` | 34 | 郑寿铉 | 6028 / 11796 | 白名单 |
| 276 | `Tamura Noboru` | 34 | 田村升 | 新建 / 新建 | 白名单 |
| 277 | `YiSang-hun` | 34 | 李相勋（同名未分） | 暂缓 | 暂缓 |
| 278 | `Ch'oeKyu-pyeong` | 33 | 崔珪昞 | 4558 / 10348 | 白名单 |
| 279 | `HwangWonJun` | 33 | 黄元俊 | 6523 / 12287 | 白名单 |
| 280 | `Ito Tamotsu` | 33 | 伊藤有 | 3883 / 9680 | 白名单 |

暂缓：`Yasui Shuntetsu` 与第 226 名同人，先等共享目录 ID；`TakahashiShigeyuki` 有高桥重行/俊光双 ID；`Hayashi Hakuei` 在日本棋院与 CWI 的伯/柏字形不一致；`YiSang-hun` 有韩国棋院认证的大/小两位同名棋手。

逐条来源见[审查 JSON](kifu-player-nonhan-ranks-261-280-review-2026-10-04.json)，候选见[精确白名单 JSON](kifu-player-nonhan-ranks-261-280-exact-allowlist-2026-10-04.json)。未写数据库。
