# 非汉字棋手第 321–340 名身份审查（2026-10-04）

冻结 post7 排名。TEST/PROD 只读事务确认 20 exact raw 各 508 槽，全部 FK 为 NULL；16 个 / 403 槽列精确白名单，4 个 / 105 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 321 | `Miyamoto Yoshihisa` | 27 | 宫本义久 | 暂缓 | 暂缓 |
| 322 | `Takahashi Shutoku` | 27 | 高桥秀德（待核） | 暂缓 | 暂缓 |
| 323 | `Takeuchi Sumio` | 27 | 竹内澄男／澄夫（待核） | 暂缓 | 暂缓 |
| 324 | `YiSeong-chae` | 27 | 李圣宰 | 114 / 115 | 白名单 |
| 325 | `JangDuJin` | 26 | 张斗轸 | 4650 / 10440 | 白名单 |
| 326 | `SakataEio` | 26 | 坂田荣男 | 4227 / 10022 | 白名单 |
| 327 | `Shiraishi Yutaka` | 26 | 白石裕 | 5617 / 11390 | 白名单 |
| 328 | `Hirako Sho` | 25 | 平光尚 | 新建 / 新建 | 白名单 |
| 329 | `Inoue Kunio` | 25 | 井上国夫 | 新建 / 新建 | 白名单 |
| 330 | `IshidaYoshio` | 25 | 石田芳夫 | 5649 / 11422 | 白名单 |
| 331 | `Kado Hayato` | 25 | 贺户隼人 | 新建 / 新建 | 白名单 |
| 332 | `Kato Minaichi` | 25 | 田中三七一 | 5568 / 11342 | 白名单 |
| 333 | `KimChwa-ki` | 25 | 金坐基 | 6121 / 11889 | 白名单 |
| 334 | `Masubuchi Tatsuko` | 25 | 增渊辰子 | 4238 / 10033 | 白名单 |
| 335 | `Okumura Hideo` | 25 | 奥村英夫 | 4275 / 10070 | 白名单 |
| 336 | `Takasaki Taisaku` | 25 | 高崎泰策 | 新建 / 新建 | 白名单 |
| 337 | `Tokimoto Hajime` | 25 | 时本壱 | 4777 / 10565 | 白名单 |
| 338 | `HoJangHee` | 24 | 许壮会（待核） | 暂缓 | 暂缓 |
| 339 | `Honda Teruko` | 24 | 楠光子 | 5278 / 11056 | 白名单 |
| 340 | `HongJongHyun` | 24 | 洪钟贤 | 5391 / 11166 | 白名单 |

暂缓项：
- `Miyamoto Yoshihisa`：与第292名 MiyamotoYoshihisa 同人；两库尚无共享目录 ID，待第292名建 ID 后复用，避免新建重复目录。
- `Takahashi Shutoku`：CWI 方圆社棋谱只列 Takahashi Shutoku；未找到可靠汉字原名，暂缓。
- `Takeuchi Sumio`：CWI 同一人列竹内澄男、竹内澄夫、竹内清隆三个名，缺少可选定中文默认名的官方证据。
- `HoJangHee`：韩国棋院列허장회/許壯會，但未找到 HoJangHee 与该人直接对照的可靠转写证据，暂缓。

逐条来源与注释见[审查 JSON](kifu-player-nonhan-ranks-321-340-review-2026-10-04.json)，可导入项见[精确白名单 JSON](kifu-player-nonhan-ranks-321-340-exact-allowlist-2026-10-04.json)。未写数据库。
