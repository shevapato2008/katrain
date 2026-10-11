# 非汉字棋手第 81–100 名身份审查（2026-10-04）

TEST/PROD 实时只读事务确认 20 个 exact raw 共 3,876 槽，均未关联且无现有 FK 冲突。14 个、2,701 槽列为精确白名单；6 个、1,175 槽暂缓。目录 ID 是快照值，执行前需实时 dry-run 重查。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 81 | `Hasegawa Akira` | 218 | 长谷川章 | 6270 / 12036 | 白名单 |
| 82 | `Ishida Yoshio` | 217 | 石田芳夫 | 5649 / 11422 | 白名单 |
| 83 | `Tsujii Ryotaro` | 216 | 辻井良太郎 | 暂缓 | 暂缓 |
| 84 | `Kadono Jowa` | 212 | 本因坊丈和 | 3 / 3 | 白名单 |
| 85 | `Takagawa Shukaku` | 206 | 高川格 | 暂缓 | 暂缓 |
| 86 | `Watanabe Hideo` | 203 | 渡边英夫 | 5413 / 11188 | 白名单 |
| 87 | `Tsuchiya Shuwa` | 200 | 本因坊秀和 | 暂缓 | 暂缓 |
| 88 | `Fukui Masaaki` | 199 | 福井正明 | 5665 / 11438 | 白名单 |
| 89 | `Kato Masao` | 199 | 加藤正夫 | 878 / 1090 | 白名单 |
| 90 | `Kobayashi Koichi` | 191 | 小林光一 | 暂缓 | 暂缓 |
| 91 | `Yasuda Shusaku` | 187 | 本因坊秀策 | 4 / 4 | 白名单 |
| 92 | `Takeda Hakuai` | 186 | 武田博爱 | 5297 / 11074 | 白名单 |
| 93 | `Sakai Takeshi` | 184 | 酒井猛 | 暂缓 | 暂缓 |
| 94 | `Ando Takeo` | 181 | 安藤武夫 | 4365 / 10157 | 白名单 |
| 95 | `Komatsu Nobuaki` | 181 | 小松伸昭 | 新建 / 新建 | 白名单 |
| 96 | `Kawamoto Noboru` | 180 | 川本升 | 4567 / 10357 | 白名单 |
| 97 | `Naganuma Makoto` | 180 | 长沼信 | 6267 / 12033 | 白名单 |
| 98 | `Kobayashi Tetsujiro` | 179 | 小林铁次郎 | 新建 / 新建 | 白名单 |
| 99 | `Shusai Meijin` | 179 | 本因坊秀哉 | 4833 / 10619 | 白名单 |
| 100 | `Honinbo Shuei` | 178 | 本因坊秀荣 | 暂缓 | 暂缓 |

## 暂缓

- `Tsujii Ryotaro`、`Takagawa Shukaku`、`Kobayashi Koichi`、`Sakai Takeshi`：各有两个现有目录 ID，需先归并。
- `Tsuchiya Shuwa`：[CWI](https://homepages.cwi.nl/~aeb/go/games/games/ancient/Honinbo_Jowa/)证实与第 49 名 `Honinbo Shuwa` 同人。后者还未建立目录 ID，避免两个批次重复创建。
- `Honinbo Shuei`：PROD game 155283 原始日期 1846-03-24，早于日本棋院[历史资料](https://www.nihonkiin.or.jp/teach/history/rekidai.html)记载的 1852 年出生；先核实这盘棋。

`Kadono Jowa`、`Yasuda Shusaku`、`Shusai Meijin` 为已有本因坊身份的历史别名，分别使用现有 ID 3、4、4833（TEST 秀哉 10619）。逐条年份、来源与目录操作见[审查 JSON](kifu-player-nonhan-ranks-81-100-review-2026-10-04.json)；14 行导入候选见[精确白名单 JSON](kifu-player-nonhan-ranks-81-100-exact-allowlist-2026-10-04.json)。未写数据库。
