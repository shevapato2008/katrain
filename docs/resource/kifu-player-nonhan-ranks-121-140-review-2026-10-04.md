# 非汉字棋手第 121–140 名身份审查（2026-10-04）

排名按冻结 post7 inventory；TEST/PROD 实时只读事务确认 20 个 exact raw 共 2,417 槽，均未关联且无现有 FK 冲突。16 个、1,896 槽列为精确白名单；4 个、521 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 121 | `YangJaeHo` | 142 | 梁宰豪 | 5249 / 11028 | 白名单 |
| 122 | `Fujisawa Shuko` | 141 | 藤泽秀行 | 暂缓 | 暂缓 |
| 123 | `Inagaki Koichi` | 135 | 稻垣弘一 | 暂缓 | 暂缓 |
| 124 | `Kubomatsu Katsukiyo` | 133 | 久保松胜喜代 | 新建 / 新建 | 白名单 |
| 125 | `Sato Masaharu` | 131 | 佐藤昌晴 | 3896 / 9693 | 白名单 |
| 126 | `Ishida Akira` | 128 | 石田章 | 5648 / 11421 | 白名单 |
| 127 | `Nabeshima Akira` | 125 | 锅岛昭 | 6261 / 12027 | 白名单 |
| 128 | `Yasui Sanchi` | 123 | 安井算知（不同代） | 暂缓 | 暂缓 |
| 129 | `Shirae Haruhiko` | 122 | 白江治彦 | 5611 / 11384 | 白名单 |
| 130 | `Shuwa` | 122 | 本因坊秀和 | 暂缓 | 暂缓 |
| 131 | `Hiroe Katsuhiko` | 119 | 广江胜彦 | 4587 / 10377 | 白名单 |
| 132 | `Hayase Gendo` | 118 | 早濑玄堂 | 新建 / 新建 | 白名单 |
| 133 | `Onoda Chiyotaro` | 118 | 小野田千代太郎 | 新建 / 新建 | 白名单 |
| 134 | `Takahashi Kinesaburo` | 116 | 高桥杵三郎 | 新建 / 新建 | 白名单 |
| 135 | `Kitamura Hiroshi` | 111 | 北村洋司 | 4063 / 9859 | 白名单 |
| 136 | `Amayake Nobuo` | 107 | 天宅信雄 | 4266 / 10061 | 白名单 |
| 137 | `Honda Sachiko` | 107 | 本田幸子 | 4837 / 10623 | 白名单 |
| 138 | `Shioiri Itsuzo` | 107 | 塩入逸造 | 4235 / 10030 | 白名单 |
| 139 | `Fukuhara Yoshitora` | 106 | 福原义虎 | 新建 / 新建 | 白名单 |
| 140 | `Ishii Senji` | 106 | 石井千治 | 新建 / 新建 | 白名单 |

## 暂缓及身份边界

- `Yasui Sanchi`：原值跨 1669–1671 年 17 槽、1838–1858 年 106 槽，代际不同，须按盘分拆。
- `Fujisawa Shuko`、`Inagaki Koichi`：分别有藤泽/藤沢、稲/稻两个现有目录 ID，先归并。
- `Shuwa`：与第 49 名本因坊秀和同人，待前批新 ID 建立，避免双建。
- `Ishii Senji`：CWI [秀哉棋谱](https://homepages.cwi.nl/~aeb/go/games/games/Shusai/index.html)明示石井千治后来成为二世中川龟三郎。与第 120 名含两代的 `Nakagawa Kamesaburo` 原值分开；此处可独立新建身份。
- `Honda Sachiko` 与第 112 名 `Sugiuchi Kazuko` 是不同的姐妹，不合并。

逐条日期、来源和目录操作见[审查 JSON](kifu-player-nonhan-ranks-121-140-review-2026-10-04.json)；16 行导入候选见[精确白名单 JSON](kifu-player-nonhan-ranks-121-140-exact-allowlist-2026-10-04.json)。未写数据库。
