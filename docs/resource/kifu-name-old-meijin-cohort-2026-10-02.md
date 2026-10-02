# Old Meijin 原始字段范围核查（只读，2026-10-02）

对固定正式库清单 `kifu-name-inventory-prod-v2-20261002.json.gz`（内部 SHA-256 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`）和 `event-components-v3` 受控分组清单交叉统计：完整核心恰为 `Old Meijin`、语法恰为 `english_ordinal_edition` 的原始赛事实值有 **13 种、1,199 盘**，写作 `2nd` 至 `14th Old Meijin`。这 1,199 盘的 `kifu_album_sources` 均指向数据集 ID 2、来源标签 `CWI`，路径位于 `data/kifu-album/CWI_History_Full/OMeijin/`。其日期原值的年份前缀为 1961–1975。

届次与日期并非简单的同年一一对应。例如 `2nd Old Meijin` 的 60 盘横跨 1961（17）、1962（38）、1963（5）；`14th Old Meijin` 的 118 盘横跨 1973（1）、1974（114）、1975（3）。原始日期有 `1963-07-05,06` 等非 ISO 写法。按年份相等去绑定赛事届次或筛掉 1961 年对局都会造成误判。CWI 的[历史赛事档案](https://homepages.cwi.nl/~aeb/go/games/games/OMeijin/)和[日本棋院沿革](https://www.nihonkiin.or.jp/profile/enkaku/)提供后续身份核对入口；[乌克兰语编辑决策](kifu-name-old-meijin-ua-editorial-decision-2026-10-02.md)中的 `1962–1975` 明确指 CWI 的届次/成绩年份范围，不能当作严格对局日期范围。

统计仅用本地受控只读清单，不表示全部 1,199 盘已获逐盘身份批准，也未生成赛事 ID、十一语名称批准或数据库关联。下一步需按 CWI 目录、届次、赛段及对应日本棋院记录复核；每盘的来源与日期异常需保留在有限待审范围中。
