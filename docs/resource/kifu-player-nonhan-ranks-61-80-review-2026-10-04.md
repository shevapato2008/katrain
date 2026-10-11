# 非汉字棋手第 61–80 名身份审查（2026-10-04）

TEST/PROD 实时只读事务确认 20 个 exact raw 共 4,712 槽，均未关联且无现有 FK 冲突。15 个、3,534 槽列为精确白名单；5 个、1,178 槽暂缓。目录 ID 是快照值，执行前需实时 dry-run 重查。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 61 | `Yamabe Toshiro` | 251 | 山部俊郎 | 4510 / 10301 | 白名单 |
| 62 | `Abe Yoshiteru` | 250 | 安倍吉辉 | 新建 / 新建 | 白名单 |
| 63 | `ChoChikun` | 246 | 赵治勋 | 暂缓 | 暂缓 |
| 64 | `Nakaoka Jiro` | 245 | 中冈二郎 | 3778 / 9576 | 白名单 |
| 65 | `Kodama Kunio` | 242 | 儿玉国夫 | 暂缓 | 暂缓 |
| 66 | `Tanimiya Teiji` | 240 | 谷宫悌二 | 新建 / 新建 | 白名单 |
| 67 | `Isogawa Masao` | 239 | 五十川正雄 | 3830 / 9628 | 白名单 |
| 68 | `Ishige Kakuo` | 238 | 石毛嘉久夫 | 5646 / 11419 | 白名单 |
| 69 | `Izumo Eiji` | 238 | 出云荣次 | 3993 / 9789 | 白名单 |
| 70 | `Murase Shuho` | 238 | 村濑秀甫 | 新建 / 新建 | 白名单 |
| 71 | `Kurosawa Tadanao` | 236 | 黑泽忠尚 | 6562 / 12326 | 白名单 |
| 72 | `Mukai Kazuo` | 234 | 向井一男 | 4121 / 9917 | 白名单 |
| 73 | `Takemiya Masaki` | 234 | 武宫正树 | 暂缓 | 暂缓 |
| 74 | `Takahashi Toshimitsu` | 233 | 高桥俊光 | 暂缓 | 暂缓 |
| 75 | `Tsuchida Masamitsu` | 231 | 土田正光 | 4218 / 10013 | 白名单 |
| 76 | `Kuroda Yukio` | 230 | 黑田幸雄 | 6563 / 12327 | 白名单 |
| 77 | `Ota Yuzo` | 224 | 太田雄藏 | 新建 / 新建 | 白名单 |
| 78 | `Cho Chikun` | 223 | 赵治勋 | 暂缓 | 暂缓 |
| 79 | `Yamazaki Masuo` | 221 | 山崎祐男 | 4499 / 10290 | 白名单 |
| 80 | `Tanaka Minaichi` | 219 | 田中三七一 | 5568 / 11342 | 白名单 |

## 暂缓

- `ChoChikun` 与 `Cho Chikun`：均指赵治勋，但目录有多个变体 ID，归入现有汉字高频去重批次；`ChoChikun` 的 1900-01-01 原始日期也需先核查。
- `Kodama Kunio`：児玉国夫 / 児玉国男 两个目录 ID，先归并。
- `Takemiya Masaki`：归入武宫正树的汉字变体去重批次。
- `Takahashi Toshimitsu`：高橋俊光 / 旧名高橋重行两个目录 ID，先归并。

每个 raw 的日期、精确来源 URL、目录操作和排除理由见[审查 JSON](kifu-player-nonhan-ranks-61-80-review-2026-10-04.json)。15 行导入候选见[精确白名单 JSON](kifu-player-nonhan-ranks-61-80-exact-allowlist-2026-10-04.json)。未写数据库。
