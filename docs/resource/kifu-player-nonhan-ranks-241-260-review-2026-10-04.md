# 非汉字棋手第 241–260 名身份审查（2026-10-04）

冻结 post7 排名。TEST/PROD 只读事务确认 20 exact raw 各 799 槽，全部棋手 FK 为 NULL；17 个 / 682 槽列精确白名单，3 个 / 117 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 241 | `Ogawa Tomoko` | 43 | 小川诚子 | 4418 / 10209 | 白名单 |
| 242 | `Hayashi Monetsu` | 42 | 林门悦 | 新建 / 新建 | 白名单 |
| 243 | `Kimura Yoshio` | 42 | 木村嘉男 | 新建 / 新建 | 白名单 |
| 244 | `MiyamotoNaoki` | 42 | 宫本直毅 | 新建 / 新建 | 白名单 |
| 245 | `UshinohamaSatsuo` | 42 | 牛之滨撮雄 | 5452 / 11227 | 白名单 |
| 246 | `HaCh'an-seok` | 41 | 河灿锡 | 新建 / 新建 | 白名单 |
| 247 | `Honinbo Doetsu` | 40 | 本因坊道悦 | 新建 / 新建 | 白名单 |
| 248 | `MokChin-seok` | 40 | 睦镇硕 | 22 / 22 | 白名单 |
| 249 | `Shiratori Sumiko` | 40 | 白鸟澄子 | 5621 / 11394 | 白名单 |
| 250 | `Suzuki Tamejiro` | 40 | 铃木为次郎 | 6251 / 12017 | 白名单 |
| 251 | `Uchigaki Suekichi` | 40 | 内垣末吉 | 新建 / 新建 | 白名单 |
| 252 | `Umezu Choko` | 40 | 梅主长江（候选） | 暂缓 | 暂缓 |
| 253 | `Sakai Masanori` | 39 | 酒井正则 | 6068 / 11836 | 白名单 |
| 254 | `Yasui Senkaku` | 39 | 安井仙角（跨世同名） | 暂缓 | 暂缓 |
| 255 | `Yasui Sentetsu` | 39 | 安井仙哲 | 新建 / 新建 | 白名单 |
| 256 | `HongT'ae-seon` | 38 | 洪太善 | 5376 / 11152 | 白名单 |
| 257 | `RinKaiho` | 38 | 林海峰 | 暂缓 | 暂缓 |
| 258 | `Suzuki Etsuo` | 38 | 铃木越雄 | 6259 / 12025 | 白名单 |
| 259 | `Tsuchiya Shugen` | 38 | 本因坊秀元 | 新建 / 新建 | 白名单 |
| 260 | `Yasui Chitoku` | 38 | 安井知得 | 新建 / 新建 | 白名单 |

暂缓：`Yasui Senkaku` 跨四世、五世两位同名家督；`RinKaiho` 有旧目录碰撞；`Umezu Choko` 的汉字缺直接对照。`MiyamotoNaoki` 与第 216 名同人，[日本国会图书馆权威记录](https://id.ndl.go.jp/auth/ndlna/00045079)已证实姓名，两 raw 应共用一个新 ID。`HaCh'an-seok` 与第 172 名同人，也应共用 ID。

逐条来源见[审查 JSON](kifu-player-nonhan-ranks-241-260-review-2026-10-04.json)，候选见[精确白名单 JSON](kifu-player-nonhan-ranks-241-260-exact-allowlist-2026-10-04.json)。未写数据库。
