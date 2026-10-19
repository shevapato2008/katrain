# 非汉字棋手第 221–240 名身份审查（2026-10-04）

冻结 post7 排名。TEST/PROD 只读事务确认 20 个 exact raw 各 932 槽，全部棋手 FK 为 NULL；17 个 / 791 槽列精确白名单，3 个 / 141 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 221 | `Inoue Ichiro` | 50 | 井上一郎 | 3832 / 9630 | 白名单 |
| 222 | `Iwasa Kei` | 49 | 岩佐銈 | 新建 / 新建 | 白名单 |
| 223 | `Kamimura Haruo` | 49 | 上村阳生 | 新建 / 新建 | 白名单 |
| 224 | `KimIn` | 49 | 金寅 | 6139 / 11907 | 白名单 |
| 225 | `Kobayashi Chizu` | 49 | 小林千寿 | 4430 / 10221 | 白名单 |
| 226 | `Yasui Sanchi IX` | 49 | 安井算知（九世） | 新建 / 新建 | 白名单 |
| 227 | `Ito Matsujiro` | 48 | 伊藤松次郎 | 暂缓 | 暂缓 |
| 228 | `KimHi-jun` | 48 | 未确认 | 暂缓 | 暂缓 |
| 229 | `TakemiyaMasaki` | 48 | 武宫正树 | 490 / 491 | 白名单 |
| 230 | `Ch'oeMyeong-hun` | 47 | 崔明勋 | 188 / 189 | 白名单 |
| 231 | `Sekiyama Toshio` | 47 | 关山利夫 | 3973 / 9770 | 白名单 |
| 232 | `Tanaka Fujio` | 47 | 田中不二男 | 5569 / 11343 | 白名单 |
| 233 | `Tono Hiroaki` | 45 | 东野弘昭 | 新建 / 新建 | 白名单 |
| 234 | `Tsuruoka Saburosuke` | 45 | 鹤冈三郎助（候选） | 暂缓 | 暂缓 |
| 235 | `Hayashi Sano` | 44 | 林佐野 | 新建 / 新建 | 白名单 |
| 236 | `Honda Kunihisa` | 44 | 本田邦久 | 4841 / 10627 | 白名单 |
| 237 | `Kusunoki Teruko` | 44 | 楠光子 | 5278 / 11056 | 白名单 |
| 238 | `Sakai Isao` | 44 | 酒井荣男 | 6070 / 11838 | 白名单 |
| 239 | `Honinbo Genjo` | 43 | 本因坊元丈 | 新建 / 新建 | 白名单 |
| 240 | `Inoue Shunseki Inseki` | 43 | 井上春硕因硕 | 新建 / 新建 | 白名单 |

暂缓：`Ito Matsujiro` 与第 206 名 `Ito Showa` 为同一人，待后者建 ID 后关联；`KimHi-jun` 无可靠棋手汉字来源；`Tsuruoka Saburosuke` 缺一手汉字对照。`TakemiyaMasaki` 的 7 槽 `1900-01-01` 为同一小棋赛的日期占位，对手和余下 41 槽支持武宫正树身份。

逐条来源见[审查 JSON](kifu-player-nonhan-ranks-221-240-review-2026-10-04.json)，可执行候选见[精确白名单 JSON](kifu-player-nonhan-ranks-221-240-exact-allowlist-2026-10-04.json)。未写数据库。
