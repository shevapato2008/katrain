# 非汉字棋手第 181–200 名身份审查（2026-10-04）

按冻结 post7 inventory 排名；TEST/PROD 实时只读事务确认 20 个 exact raw 共 1,245 槽，均未关联且无现有 FK 冲突。18 个、1,124 槽列为精确白名单；2 个、121 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 181 | `Hattori Rittetsu` | 67 | 井上幻庵因硕 | 新建 / 新建 | 白名单 |
| 182 | `Hirano Masaaki` | 67 | 平野正明 | 新建 / 新建 | 白名单 |
| 183 | `Honinbo Retsugen` | 67 | 本因坊烈元 | 新建 / 新建 | 白名单 |
| 184 | `Takenaka Kotaro` | 67 | 竹中幸太郎 | 5697 / 11469 | 白名单 |
| 185 | `Yasui Chitetsu` | 67 | 安井知哲 | 新建 / 新建 | 白名单 |
| 186 | `ChoSeonJin` | 66 | 趙善津 | 541 / 542 | 白名单 |
| 187 | `Hisajima Kunio` | 65 | 久岛国夫 | 新建 / 新建 | 白名单 |
| 188 | `Miyazaki Hiroshi` | 65 | 宫崎洋 | 4390 / 10182 | 白名单 |
| 189 | `Morikawa Masao` | 65 | 森川正夫 | 5272 / 11051 | 白名单 |
| 190 | `Imai Kinemon` | 64 | 今井金右卫门（候选） | 暂缓 | 暂缓 |
| 191 | `Watanabe Reiji` | 64 | 渡边礼二 | 5412 / 11187 | 白名单 |
| 192 | `Baba Shigeru` | 63 | 马场滋 | 6441 / 12205 | 白名单 |
| 193 | `Hirose Heijiro` | 62 | 广濑平治郎 | 新建 / 新建 | 白名单 |
| 194 | `Suzuki Tsuna` | 58 | 铃木津奈 | 6258 / 12024 | 白名单 |
| 195 | `Kitani Reiko` | 57 | 小林礼子 | 暂缓 | 暂缓 |
| 196 | `Nakayama Noriyuki` | 57 | 中山典之 | 3784 / 9582 | 白名单 |
| 197 | `Ezura Yuichi` | 56 | 江面雄一 | 5323 / 11100 | 白名单 |
| 198 | `Iwasaki Kenzo` | 56 | 巌崎健造 | 新建 / 新建 | 白名单 |
| 199 | `KatoMasao` | 56 | 加藤正夫 | 878 / 1090 | 白名单 |
| 200 | `Kawai Tetsuyuki` | 56 | 河合哲之 | 5354 / 11130 | 白名单 |

## 暂缓及历史别名

- `Kitani Reiko`：日本棋院[档案](https://www.nihonkiin.or.jp/player/htm/ki000112.htm)确认木谷礼子即后来的小林礼子；现有两个目录 ID，与第 106 名同一归并任务。
- `Imai Kinemon`：CWI 有棋手名，浜松市史有相似汉字姓名，但缺直接同人证据，暂不新建。
- `Hattori Rittetsu`：[CWI 历史姓名表](https://homepages.cwi.nl/~aeb/go/games/games/ancient/Honinbo_Jowa/)明确是井上幻庵因硕的早期名字；本组 1812–1818 年份一致。
- `Yasui Chitetsu`：[CWI 道策棋谱](https://homepages.cwi.nl/~aeb/go/games/games/Dosaku/)明确与道策有 45 盘记录，可与第 128 名跨代混名 `Yasui Sanchi` 区分。

逐条日期、来源和目录操作见[审查 JSON](kifu-player-nonhan-ranks-181-200-review-2026-10-04.json)；18 行导入候选见[精确白名单 JSON](kifu-player-nonhan-ranks-181-200-exact-allowlist-2026-10-04.json)。未写数据库。
