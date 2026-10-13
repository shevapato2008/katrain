# 非汉字棋手第 101–120 名身份审查（2026-10-04）

排名按冻结 post7 inventory 复算；前批导入后实时未关联排名已变化。TEST/PROD 实时只读事务确认这 20 个 exact raw 共 3,210 槽，均未关联且无现有 FK 冲突。15 个、2,437 槽列为精确白名单；5 个、773 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 101 | `Matsuoka Teruo` | 176 | 松冈辉夫 | 5155 / 10936 | 白名单 |
| 102 | `Morishima Kaoru` | 169 | 森岛薰 | 5271 / 11050 | 白名单 |
| 103 | `Ozaki Harumi` | 168 | 尾崎春美 | 4485 / 10276 | 白名单 |
| 104 | `Saijo Masataka` | 168 | 西条雅孝 | 新建 / 新建 | 白名单 |
| 105 | `Honma Akio` | 166 | 本间明男 | 4842 / 10628 | 白名单 |
| 106 | `Kobayashi Reiko` | 166 | 小林礼子 | 暂缓 | 暂缓 |
| 107 | `Nishigami Yoshihiko` | 166 | 西上好彦 | 5877 / 11646 | 白名单 |
| 108 | `Murase Yakichi` | 164 | 村濑秀甫 | 暂缓 | 暂缓 |
| 109 | `Yokoyama Koichi` | 164 | 横山孝一 | 5286 / 11064 | 白名单 |
| 110 | `Kosugi Kiyoshi` | 162 | 小杉清 | 4421 / 10212 | 白名单 |
| 111 | `Fukuda Masayoshi` | 161 | 福田正义 | 5668 / 11441 | 白名单 |
| 112 | `Sugiuchi Kazuko` | 161 | 杉内寿子 | 4836 / 10622 | 白名单 |
| 113 | `Murashima Yoshinori` | 159 | 村岛谊纪 | 新建 / 新建 | 白名单 |
| 114 | `Hashimoto Shoji` | 157 | 桥本昌二 | 暂缓 | 暂缓 |
| 115 | `Kanno Kiyonori` | 157 | 菅野清规 | 新建 / 新建 | 白名单 |
| 116 | `Kamimura Kunio` | 155 | 上村邦夫 | 3764 / 9562 | 白名单 |
| 117 | `Sato Kaoru` | 155 | 佐藤馨 | 3902 / 9699 | 白名单 |
| 118 | `Hosokawa Senjin` | 150 | 细川千仞 | 新建 / 新建 | 白名单 |
| 119 | `SeoPong-su` | 144 | 徐奉洙 | 暂缓 | 暂缓 |
| 120 | `Nakagawa Kamesaburo` | 142 | 中川龟三郎（一世／二世） | 暂缓 | 暂缓 |

## 关键边界

- `Nakagawa Kamesaburo`：CWI [秀哉棋谱](https://homepages.cwi.nl/~aeb/go/games/games/Shusai/index.html)明确二世原名石井千治。原值跨一世与二世：1866–1897 年 136 槽、1910–1917 年 6 槽。整组暂缓，之后按每盘年代及对手分离。
- `Kobayashi Reiko`：日本棋院[棋手档案](https://www.nihonkiin.or.jp/player/htm/ki000112.htm)确认旧姓木谷；目录现有小林礼子及木谷礼子两个 ID。
- `Murase Yakichi` 与第 70 名 `Murase Shuho` 同人；`Hashimoto Shoji` 与第 27 名 `HashimotoShoji` 同人。均待前批新目录 ID 建好后指向该 ID。
- `SeoPong-su`：韩国棋院[档案](https://www.baduk.or.kr/record/player_view.asp?pkey=10000008)确认徐奉洙，目录另有错字徐奉诛 ID，先归并。
- `Sugiuchi Kazuko`：日本棋院[档案](https://www.nihonkiin.or.jp/player/htm/ki000048.html)确认杉内寿子旧姓本田。使用现有本田寿子 ID（PROD 4836、TEST 10622）并将规范名改为杉内寿子；与其妹本田幸子分开。

逐条年份、来源、目录操作及排除理由见[审查 JSON](kifu-player-nonhan-ranks-101-120-review-2026-10-04.json)。15 行导入候选见[精确白名单 JSON](kifu-player-nonhan-ranks-101-120-exact-allowlist-2026-10-04.json)。未写数据库。
