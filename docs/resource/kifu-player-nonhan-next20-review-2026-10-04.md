# 非汉字棋手第 21–40 名身份审查（2026-10-04）

TEST/PROD 实时只读事务的 exact raw 槽位数一致。20 个原值共 6,028 槽；18 个、5,416 槽通过身份审查，2 个、612 槽暂缓。现有 FK 均为空；目录 ID 只代表快照时点，最终以导入器实时 dry-run 为准。

| exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---|---:|---|---|---|
| `Seo Hisashi` | 318 | 濑尾寿 | 5432 / 11207 | 精确白名单 |
| `Segawa Yoshio` | 317 | 濑川良雄 | 5433 / 11208 | 精确白名单 |
| `Tozawa Akinobu` | 317 | 户泽昭宣 | 4736 / 10526 | 精确白名单 |
| `Nabeshima Ichiro` | 312 | 锅岛一郎 | 6260 / 12026 | 精确白名单 |
| `Hoshino Toshi` | 311 | 星野纪 | 新建 / 新建 | 精确白名单 |
| `Yoshida Yoichi` | 311 | 吉田阳一 / 吉田洋逸 | 暂缓 | 暂缓 |
| `HashimotoShoji` | 310 | 桥本昌二 | 新建 / 新建 | 精确白名单 |
| `Sakata Eio` | 308 | 坂田荣男 | 4227 / 10022 | 精确白名单 |
| `Magari Reiki` | 307 | 曲励起 | 4797 / 10585 | 精确白名单 |
| `Sakai Michiharu` | 307 | 酒井通温 | 6071 / 11839 | 精确白名单 |
| `Ito Tomoe` | 301 | 伊藤友惠 / 伊藤清子 | 暂缓 | 暂缓 |
| `Sakakibara Shoji` | 300 | 榊原章二 | 5282 / 11060 | 精确白名单 |
| `Sanno Hirotaka` | 298 | 三王裕孝 | 3750 / 9548 | 精确白名单 |
| `Kojima Takaho` | 295 | 小岛高穗 | 4415 / 10206 | 精确白名单 |
| `Miwa Yoshiro` | 292 | 三轮芳郎 | 3752 / 9550 | 精确白名单 |
| `Hashimoto Yoshimi` | 286 | 桥本谊 | 5244 / 11023 | 精确白名单 |
| `Ishii Mamoru` | 285 | 石井卫 | 5634 / 11407 | 精确白名单 |
| `Kuwahara Munehisa` | 285 | 桑原宗久 | 5237 / 11016 | 精确白名单 |
| `Suzuki Goro` | 285 | 铃木五良 | 6252 / 12018 | 精确白名单 |
| `Miyashita Shuyo` | 283 | 宫下秀洋 | 4388 / 10180 | 精确白名单 |

## 暂缓

- `Yoshida Yoichi`：CWI [赛事档案](https://homepages.cwi.nl/~aeb/go/games/games/ProBest10/09/index.html)明确有两位同拼写棋手。现目录 `吉田阳一` 和 `吉田洋逸` 分属两人；原值从 1953 年即出现，不能整体指向其中一人。
- `Ito Tomoe`：[升段目录](https://homepages.cwi.nl/~aeb/go/misc/progression.html)把伊藤友恵、伊藤清子列为同人旧名，现目录却有三个独立 ID；先做目录身份归并。

18 个白名单 exact raw、各环境 ID 或新建标记和逐条来源见同名 JSON 及 `kifu-player-nonhan-next18-exact-allowlist-2026-10-04.json`。未写数据库。
