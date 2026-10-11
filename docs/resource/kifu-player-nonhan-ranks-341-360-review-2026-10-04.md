# 非汉字棋手第 341–360 名身份审查（2026-10-04）

冻结 post7 排名。TEST/PROD 只读事务确认 20 exact raw 各 469 槽，全部 FK 为 NULL；16 个 / 376 槽列精确白名单，4 个 / 93 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 341 | `Inoue Shuntatsu` | 24 | 井上春达因硕 | 新建 / 新建 | 白名单 |
| 342 | `Kajikawa Shurei` | 24 | 梶川秀玲（待核） | 暂缓 | 暂缓 |
| 343 | `Kataoka Satoshi` | 24 | 片冈聪 | 5447 / 11222 | 白名单 |
| 344 | `KimIlHwan` | 24 | 金日焕 | 6162 / 11930 | 白名单 |
| 345 | `KimSeung-chun` | 24 | 金承俊 | 163 / 164 | 白名单 |
| 346 | `Kobayashi Satoru` | 24 | 小林觉 | 4432 / 10223 | 白名单 |
| 347 | `NoYeong-ha` | 24 | 卢永夏 | 4085 / 9881 | 白名单 |
| 348 | `Oyama Kunio` | 24 | 大山国夫 | 4246 / 10041 | 白名单 |
| 349 | `ParkYeongChan` | 24 | 朴映璨 | 4890 / 10675 | 白名单 |
| 350 | `Yasui San'ei` | 24 | 安井算英 | 6676 / 12445 | 白名单 |
| 351 | `Yoshida Hanjuro` | 24 | 吉田半十郎 | 新建 / 新建 | 白名单 |
| 352 | `Akedo Kazumi` | 23 | 明户和巳（待核） | 暂缓 | 暂缓 |
| 353 | `Chen Zude` | 23 | 陈祖德 | 6371 / 12137 | 白名单 |
| 354 | `Hanawa Yasutoki` | 23 | 塙保时 | 新建 / 新建 | 白名单 |
| 355 | `HeoChang-heui` | 23 | 许壮会（待核） | 暂缓 | 暂缓 |
| 356 | `Ishigure Makiko` | 23 | 石榑真纪子（待核） | 暂缓 | 暂缓 |
| 357 | `JeongHyeonSan` | 23 | 丁铉山 | 3741 / 9539 | 白名单 |
| 358 | `Matsuoka Akira` | 23 | 松冈章 | 5154 / 10935 | 白名单 |
| 359 | `HongChong-hyeon` | 22 | 洪钟贤 | 5391 / 11166 | 白名单 |
| 360 | `HwangWeon-chun` | 22 | 黄元俊 | 6523 / 12287 | 白名单 |

暂缓项：
- `Kajikawa Shurei`：CWI 秀策棋谱列 Kajikawa Shurei，但无可靠汉字姓名对照，暂缓。
- `Akedo Kazumi`：CWI 列明戸和巳/Akedo Kazumi；目录已有明户和已4781/10569与明户和巳4782/10570两 ID，先去重。
- `HeoChang-heui`：韩国棋院列허장회/許壯會；HeoChang-heui 与该人的具体转写对应尚缺直接可靠出处，与第338名一起暂缓。
- `Ishigure Makiko`：日本棋院列石榑まき子（Ishigure Makiko）；现有石榑真子5644/11417无法由官方资料证实为同一汉字名，且汉字译写未确定。

逐条来源与注释见[审查 JSON](kifu-player-nonhan-ranks-341-360-review-2026-10-04.json)，可导入项见[精确白名单 JSON](kifu-player-nonhan-ranks-341-360-exact-allowlist-2026-10-04.json)。未写数据库。
