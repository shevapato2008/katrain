# 非汉字棋手第 141–160 名身份审查（2026-10-04）

按冻结 post7 inventory 排名；TEST/PROD 实时只读事务确认 20 个 exact raw 共 1,855 槽，均未关联且无现有 FK 冲突。17 个、1,601 槽列为精确白名单；3 个、254 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 141 | `Sakai Toshio` | 105 | 酒井利雄 | 新建 / 新建 | 白名单 |
| 142 | `Takamizawa Tadao` | 105 | 高见泽忠夫 | 6496 / 12260 | 白名单 |
| 143 | `Hayashi Shuei` | 103 | 本因坊秀荣 | 4835 / 10621 | 白名单 |
| 144 | `Segoe Kensaku` | 102 | 濑越宪作 | 5434 / 11209 | 白名单 |
| 145 | `Kato Shin` | 101 | 加藤信 | 4053 / 9849 | 白名单 |
| 146 | `Kuwata Yasuaki` | 101 | 桑田泰明 | 5239 / 11018 | 白名单 |
| 147 | `Shimohira Akio` | 96 | 下平昭夫 | 3771 / 9569 | 白名单 |
| 148 | `Handa Dogen` | 94 | 半田道玄 | 4069 / 9865 | 白名单 |
| 149 | `Mizutani Nuiji` | 92 | 水谷缝治 | 新建 / 新建 | 白名单 |
| 150 | `Osawa Ginjiro` | 91 | 大泽银次郎 | 新建 / 新建 | 白名单 |
| 151 | `Ito Makoto` | 90 | 伊藤诚 | 3885 / 9682 | 白名单 |
| 152 | `KubouchiShuchi` | 89 | 洼内秀知 | 新建 / 新建 | 白名单 |
| 153 | `Sakaguchi Ryuzo` | 89 | 坂口隆三 | 4224 / 10019 | 白名单 |
| 154 | `Nakamura Hidehito` | 87 | 中村秀仁 | 3795 / 9593 | 白名单 |
| 155 | `SeoNeungUk` | 87 | 徐能旭 | 4714 / 10504 | 白名单 |
| 156 | `Sekiyama Riichi` | 86 | 关山利一 | 暂缓 | 暂缓 |
| 157 | `Shusai` | 85 | 本因坊秀哉 | 4833 / 10619 | 白名单 |
| 158 | `Takahashi Shigeyuki` | 85 | 高桥重行 | 暂缓 | 暂缓 |
| 159 | `Maetani Shingo` | 84 | 前谷信吾 | 新建 / 新建 | 白名单 |
| 160 | `Kubouchi Shuchi` | 83 | 洼内秀知 | 暂缓 | 暂缓 |

## 暂缓与别名

- `Sekiyama Riichi`：目录中关/関字形两个 ID；先归并。
- `Takahashi Shigeyuki`：高桥重行是高桥俊光旧名，目录已有两个 ID；与第 74 名同批处理。
- `Kubouchi Shuchi`：与本批 `KubouchiShuchi` 是同一窪内秀知；后者先建立唯一 ID，再关联有空格原值。
- `Hayashi Shuei`：日本国立国会图书馆[围棋史资料](https://www.ndl.go.jp/kaleido/e/entry/22/2.html)确认林秀栄后来为本因坊秀栄；本组 1866–1879 年份吻合。第 100 名 `Honinbo Shuei` 因另有早于出生年的一盘棋仍单独暂缓。

逐条日期、来源和目录操作见[审查 JSON](kifu-player-nonhan-ranks-141-160-review-2026-10-04.json)；17 行导入候选见[精确白名单 JSON](kifu-player-nonhan-ranks-141-160-exact-allowlist-2026-10-04.json)。未写数据库。
