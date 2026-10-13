# 非汉字棋手第 161–180 名身份审查（2026-10-04）

**旧精确白名单 `kifu-player-nonhan-ranks-161-180-exact-allowlist-2026-10-04.json` 已废弃，不得导入；`Miyasaka Shinji` 姓名已更正，导入代理正在重冻新计划。** 见[更正说明](kifu-player-miyasaka-shinji-name-correction-2026-10-04.md)。

按冻结 post7 inventory 排名；TEST/PROD 实时只读事务确认 20 个 exact raw 共 1,468 槽，均未关联且无现有 FK 冲突。17 个、1,230 槽列为精确白名单；3 个、238 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 161 | `SeoBongSoo` | 83 | 徐奉洙 | 暂缓 | 暂缓 |
| 162 | `Fujisawa Kuranosuke` | 81 | 藤泽朋斋 | 暂缓 | 暂缓 |
| 163 | `Tamura Hoju` | 80 | 本因坊秀哉 | 4833 / 10619 | 白名单 |
| 164 | `Koyama Shizuo` | 79 | 小山镇男 | 4410 / 10201 | 白名单 |
| 165 | `Fukui Susumu` | 77 | 福井进 | 新建 / 新建 | 白名单 |
| 166 | `JangSuYeong` | 77 | 张秀英 | 4667 / 10457 | 白名单 |
| 167 | `Kawamura Masamichi` | 75 | 川村匡迪 | 4568 / 10358 | 白名单 |
| 168 | `Ito Hiroshi` | 74 | 伊藤弘 | 3882 / 9679 | 白名单 |
| 169 | `Tainaka Shin` | 74 | 鲷中新 | 新建 / 新建 | 白名单 |
| 170 | `YangChae-ho` | 74 | 梁宰豪（候选） | 暂缓 | 暂缓 |
| 171 | `Miyasaka Shinji` | 72 | 宫坂寀二 | 新建 / 新建 | 姓名更正；旧白名单废弃 |
| 172 | `HaChanSeok` | 70 | 河灿锡 | 新建 / 新建 | 白名单 |
| 173 | `HashimotoUtaro` | 70 | 桥本宇太郎 | 6577 / 12341 | 白名单 |
| 174 | `Oka Nobumitsu` | 70 | 冈信光 | 3982 / 9779 | 白名单 |
| 175 | `Sakai Yasujiro` | 70 | 酒井安次郎 | 新建 / 新建 | 白名单 |
| 176 | `Awaji Shuzo` | 69 | 淡路修三 | 591 / 592 | 白名单 |
| 177 | `Karigane Junichi` | 69 | 雁金准一 | 6391 / 12157 | 白名单 |
| 178 | `KimSu-chang` | 69 | 金秀壮 | 6213 / 11979 | 白名单 |
| 179 | `SeoNeung-uk` | 68 | 徐能旭 | 4714 / 10504 | 白名单 |
| 180 | `Asano Hideaki` | 67 | 浅野英昭 | 5394 / 11169 | 白名单 |

## 暂缓及特殊日期

- `SeoBongSoo`、`Fujisawa Kuranosuke`：分别对应徐奉洙、藤泽朋斋，但当前各有两个目录 ID；与先前排除组一起处理。
- `YangChae-ho`：日本棋院英文赛事资料证实这个英文拼写属于韩国职业棋手；与梁宰豪的年份和对手高度一致，但目前缺直接权威别名映射，先暂缓。
- `HashimotoUtaro`：首批 `Hashimoto Utaro` 已建立桥本宇太郎 ID（PROD 6577、TEST 12341）。4 盘原值日期为 1900-01-01，占位日期对应后世棋手或赛事；身份可关联同一现有 ID。

逐条日期、来源和目录操作见[审查 JSON](kifu-player-nonhan-ranks-161-180-review-2026-10-04.json)；原 17 行[精确白名单 JSON](kifu-player-nonhan-ranks-161-180-exact-allowlist-2026-10-04.json)已废弃，待导入代理重冻后使用新计划。未写数据库。
