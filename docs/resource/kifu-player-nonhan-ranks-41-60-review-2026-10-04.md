# 非汉字棋手第 41–60 名身份审查（2026-10-04）

TEST/PROD 实时只读事务确认 20 个 exact raw 共 5,239 槽，均未关联且无现有 FK 冲突。16 个、4,212 槽列为精确白名单；4 个、1,027 槽暂缓。目录 ID 是快照值，执行前需要实时 dry-run 重查。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 41 | `Kaji Kazutame` | 279 | 梶和为 | 5266 / 11045 | 白名单 |
| 42 | `Kusaka Kaneo` | 277 | 日下包夫 | 4771 / 10560 | 白名单 |
| 43 | `Hamajima Hisayoshi` | 273 | 浜岛久义 | 5397 / 11172 | 白名单 |
| 44 | `Sugiuchi Masao` | 272 | 杉内雅男 | 新建 / 新建 | 白名单 |
| 45 | `Izutani Minoru` | 270 | 泉谷实 | 5365 / 11141 | 白名单 |
| 46 | `Okubo Ichigen` | 268 | 大洼一玄 | 暂缓 | 暂缓 |
| 47 | `Kada Katsuji` | 264 | 加田克司 | 4047 / 9843 | 白名单 |
| 48 | `Ishigure Ikuro` | 263 | 石榑郁郎 | 5645 / 11418 | 白名单 |
| 49 | `Honinbo Shuwa` | 262 | 本因坊秀和 | 新建 / 新建 | 白名单 |
| 50 | `Oeda Yusuke` | 262 | 大枝雄介 | 4252 / 10047 | 白名单 |
| 51 | `Suzuki Masaharu` | 262 | 铃木政春 | 6255 / 12021 | 白名单 |
| 52 | `Otake Hideo` | 261 | 大竹英雄 | 879 / 1091 | 白名单 |
| 53 | `Kano Yoshinori` | 256 | 加纳嘉德 | 暂缓 | 暂缓 |
| 54 | `Iwata Tatsuaki` | 255 | 岩田达明 | 4519 / 10310 | 白名单 |
| 55 | `Matsumoto Tokuji` | 255 | 松本笃二 | 5158 / 10939 | 白名单 |
| 56 | `Haruyama Isamu` | 253 | 春山勇 | 4792 / 10580 | 白名单 |
| 57 | `Hayase Hiroshi` | 253 | 早濑弘 | 4774 / 10562 | 白名单 |
| 58 | `Sumino Tsunehiro` | 252 | 炭野恒广 | 暂缓 | 暂缓 |
| 59 | `Rin Kaiho` | 251 | 林海峰 | 暂缓 | 暂缓 |
| 60 | `Takagi Shoichi` | 251 | 高木祥一 | 新建 / 新建 | 白名单 |

## 需要先处理的目录项

- `Iwata Tatsuaki`：日本棋院的[棋手档案](https://www.nihonkiin.or.jp/player/htm/ki000016.htm)明确岩田達明旧名岩田正男。可保留现有 ID（PROD 4519、TEST 10310），将目录规范名改为「岩田达明」后关联；不得新建第二人。
- `Okubo Ichigen`：现有 `大漥一玄` / `大窐一玄` 两个 ID，暂缓。
- `Kano Yoshinori`：现有 `加纳嘉徳` / `加纳嘉德` 两个 ID，暂缓。
- `Sumino Tsunehiro`：现有 `炭野恒广` / `炭野恒広` / `炭野武司` 三个 ID；[CWI](https://homepages.cwi.nl/~aeb/go/misc/progression.html)确认旧名关系，目录待合并。
- `Rin Kaiho`：与汉字变体批次重叠，目录 `林海峯名誉` 及历史 FK 冲突由该批次处理。

每个 raw 的年份、精确来源 URL、目录操作和排除理由见[审查 JSON](kifu-player-nonhan-ranks-41-60-review-2026-10-04.json)。可供导入器读取的 16 行在[精确白名单 JSON](kifu-player-nonhan-ranks-41-60-exact-allowlist-2026-10-04.json)。未写数据库。
