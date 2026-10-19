# 大手合剩余关联独立裁决（2026-10-04）

**只批准 131 个 exact raw、1,532 盘关联既有赛事 `event_id=22`（大手合），全部 type-only。未写数据库。** 不批准此前未保存明细的 141 raw／1,585 盘提案；其中存在附加赛身份边界问题，且仅凭其概括无法重建相同集合。

执行范围为 [精确 allowlist 与逐盘前像](kifu-oteai-remaining-type-only-approved-2026-10-04.json)，不得将本文的类别概括转换成新正则并扩大范围。文件中每盘的原始 EV、日期、赛事 FK、届次 FK 均已冻结；所有获准行的两个 FK 当前均为空。只填赛事 FK，不建立届次，不改原文、日期、别名或棋谱。执行前应逐盘验证前像及目标事件身份；任何漂移须重新核对。

实时读取来自 `katrain_prod_20260725`，事务时间 `2026-10-04 04:53:44.463020+00:00`，查询事务设置为只读。未关联宽口径 `(event ~* 'Oteai|JapanPromotionTournament' OR event LIKE '%日本大手合%')` 共 **173 raw／1,664 盘**。既有 exact `Oteai YYYY` 的 5,584 盘当前全部关联 ID 22 且有届次，本裁决不覆盖它们，也不背书其届次正确性。

| 获准类别 | exact raw | 棋谱数 |
|---|---:|---:|
| JapanPromotionTournament 年份、春秋、Later 原值 | 60 | 611 |
| 明确年份的日本大手合 | 37 | 714 |
| 明确 Oteai 年份／场次／延期原值 | 34 | 207 |
| 合计 | 131 | 1,532 |

其余 **42 raw／132 盘** 本批保留未关联，逐项原值、盘数、ID 和理由同样列在 JSON 的 `held_raws`。具体新增边界如下：

- 六类 playoff 原值共 22 盘全部保留：`Oteai Spring Session playoff final`（1）、`Oteai Spring Session playoff series`（5）、`Oteai winners' playoff series`（1）、`Oteai, playoff series`（11）、`Oteai, playoff series final`（1）、`Oteai, round-robin playoff series`（3）。其中 ID 24413、24390、24276、24418 的原始 SGF `EVX` 明示东京／大阪朝日赞助，多个同组对局又有 3、4、5 目贴目。这些是优胜者／场次附加赛标签，不能在排除显式朝日优胜赛的同时仅因简写含 Oteai 就纳入。赞助商本身不是排除依据；未证明附加赛属于本次升段赛事实体才是保留理由。
- `?1953年日本大手合`（ID 134585）原始首个 GN 带问号，另一个 GN 去掉问号不能构成独立确认；保留。
- `Oteai,7and8-danrankingtournament`（ID 33014）是七八段排名赛描述，和普通升段对局的身份边界未解决；保留。
- 四个 raw 整组保留，共 31 盘：`JapanPromotionTournament,1939`（14）、`JapanPromotionTournament,1979`（10）、`1963年日本大手合`（4）、`日本大手合`（3）。其中部分棋谱有非零贴目，与普通大手合无贴目的资料冲突，本次不推断到底是贴目错误还是赛事误标。1939 年的 ID 62949 虽有 CWI 对应谱 ID 156715，两者均写 `KM[3.5]`，现有关联不能消除该疑点。
- `JapanPromotionTournament,1941` 仍可纳入：唯一贴目异常 ID 118235 与 CWI 原谱 ID 156425 的完整 330 手顺序一致，原谱明确 `EV[Oteai]`、`DT[1941-11-19,20]` 且没有 KM 字段；19x19 导入谱额外的 7.5 目不是不同赛事证据。
- Kansai／Kansai Branch 全部继续留在本批之外；纪念、接力、组间对抗、特别选拔、显式朝日优胜者对局，以及 `Probably Oteai`、`Oteai 1949 Special`、`Oteai 1974?`、`Oteai1965` 继续保留。`Oteai 1949 Special` 的 EVX 明确是春季各组优胜者之间的对局。

普通春秋场次与延期对局可以只连赛事类型。日本棋院沿革确认 1927 年大手合开始、1929 年改为春秋定期手合，FAQ 确认 2003 年改制；CWI 的 1934 年档案明确分春秋场次及 A/B 组。跨年／缺日期并不自动否定赛事身份，但本次一律不从日期或原文创建年度届次。[日本棋院沿革](https://www.nihonkiin.or.jp/profile/enkaku/)、[日本棋院 FAQ](https://www.nihonkiin.or.jp/profile/faq/)、[CWI 大手合规则](https://homepages.cwi.nl/~aeb/go/games/games/Oteai/)、[CWI 1934 场次记录](https://homepages.cwi.nl/~aeb/go/games/games/Oteai/1934/index.html)。

本次额外核读了宽口径 1,664 盘的 SGF 根元数据，记录位于 `/tmp/oteai-remaining-all-root-metadata-20261004.json`；有贴目疑点的对应谱核对位于 `/tmp/oteai-komi-anomaly-correspondence-20261004.json`。未读取 `data/kifu-album/` 文件目录。

精确 allowlist SHA-256：`edd2640dfb81619fe836cb88290f5a2c5442764bb2d69ff80e3fdfc572c43772`。

逐盘 `[id,event,date_played,event_id,event_edition_id]` 前像 SHA-256：`cd9383bb470010d22e2409fb46f3f818723621ce1f25ea9c6c5222ecde8d7be2`。

两个摘要均使用 UTF-8 JSON、`ensure_ascii=False, sort_keys=True, separators=(',',':')`；allowlist 按原值排序，前像按 ID 排序。批准的是这份冻结集合，不是对未来同名新增棋谱的自动授权。
