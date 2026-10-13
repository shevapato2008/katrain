# 日本棋院大手合（Oteai）关联研究（2026-10-04）

> **历史快照，不能作为当前导入计划。** 本文基于 `post7` 离线清单。2026-10-04 实时核对正式库 `katrain_prod_20260725`：exact `Oteai YYYY` 的 5,584 盘均已关联 `event_id=22`，未关联数为 **0**。下方“可安全关联”仅是旧快照下的候选判断，不能重放；任何其他大手合原值须重新冻结当前前像并审核。本文也保留了四盘 raw 年份与日期冲突，不能概括为“日期全部同年”。

范围：只读检查 `docs/resource/kifu-event-next-high-coverage-candidates-2026-10-04.md`、`docs/resource/kifu-event-historical-alias-review-2026-10-04.md`、`/tmp/kifu-five-prod-inventory-post7.json.gz`，并以日本棋院沿革/FAQ和 CWI Oteai 档案核对。未写库、未写代码。

## 结论

赛事 ID `22`（canonical `大手合`，aliases `Oteai`、`JapanPromotionTournament`）可以安全作为日本棋院大手合的统一赛事实体。日本棋院沿革记载 1927 年开始“日本棋院大手合・東西対抗”，1929 年改为春秋定期手合，2003 年废止；FAQ 说明 2003 年 4 月起改用一般棋战胜局/头衔升段制度。[日本棋院沿革](https://www.nihonkiin.or.jp/profile/enkaku/)、[日本棋院 FAQ](https://www.nihonkiin.or.jp/profile/faq/)

CWI 将 `Oteai (大手合)` 定义为 1927–2003 的 Nihon Ki-in / Kansai Ki-in 升段赛，并明确当前目录有 7000+ 局；其 1934 档案显示一年分 Spring/Autumn 两场、A/B 组。因此 `Oteai`、`JapanPromotionTournament` 是同一赛事的英文/资料库标签，但“Japan”不能把关西棋院或台湾/韩国同名升段赛并进来。[CWI Oteai](https://homepages.cwi.nl/~aeb/go/games/games/Oteai/)、[CWI Oteai 1934](https://homepages.cwi.nl/~aeb/go/games/games/Oteai/1934/index.html)

## 生产盘点与数量异常

候选文档写作“160 个 raw、1,604 盘”；但 post7 JSON 的 `album_associations` 逐行扫描结果是：

* `event_id IS NULL` 且 exact raw 为 `Oteai YYYY`：48 个 raw、5,584 盘；
* 同一 JSON 中另外还有 1,581 盘 `日本大手合`、`JapanPromotionTournament,YYYY`、session/playoff 等非 canonical raw（其中含关西和特殊对局）；
* `Oteai` 575 盘及早期 `JapanPromotionTournament,YYYY,Spring/Fall` 482 盘已经关联 ID 22。

因此“约 1,600”与当前 post7 行数不一致，不能据此直接生成导入计划。以下建议按 exact raw 给出；数量以 JSON 扫描为准，执行前需重新冻结 PROD 清单。差异交 **gpt-6-astra** 复核。

## 可安全关联：type + year

以下 exact raw 都是 `Oteai YYYY`，旧快照中除下文列出的四盘跨年日期外，其余日期与 raw 年份相符；当时的候选量为 48 raw / 5,584 盘。当前正式库已全部关联类型，不能据此再次导入或推断每盘的年度键已正确。

| exact raw | 盘数 | 建议 |
|---|---:|---|
| `Oteai 1927` | 7 | type + year |
| `Oteai 1928` | 51 | type + year |
| `Oteai 1929` | 5 | type + year |
| `Oteai 1930` | 74 | type + year |
| `Oteai 1931` | 8 | type + year |
| `Oteai 1932` | 2 | type + year |
| `Oteai 1933` | 2 | type + year |
| `Oteai 1934` | 293 | type + year |
| `Oteai 1935` | 3 | type + year |
| `Oteai 1936` | 46 | type + year |
| `Oteai 1937` | 35 | type + year |
| `Oteai 1938` | 28 | type + year |
| `Oteai 1939` | 65 | type + year；含 1 盘跨年日期，见下 |
| `Oteai 1940` | 19 | type + year |
| `Oteai 1941` | 24 | type + year |
| `Oteai 1942` | 14 | type + year |
| `Oteai 1943` | 10 | type + year |
| `Oteai 1946` | 28 | type + year |
| `Oteai 1947` | 9 | type + year |
| `Oteai 1948` | 13 | type + year |
| `Oteai 1949` | 26 | type + year |
| `Oteai 1950` | 3 | type + year；含 1 盘跨年日期 |
| `Oteai 1951` | 3 | type + year |
| `Oteai 1952` | 3 | type + year；含 1 盘跨年日期 |
| `Oteai 1953` | 14 | type + year |
| `Oteai 1954` | 7 | type + year；含 1 盘跨年日期 |
| `Oteai 1955` | 7 | type + year |
| `Oteai 1956` | 5 | type + year |
| `Oteai 1957` | 3 | type + year |
| `Oteai 1960` | 380 | type + year |
| `Oteai 1961` | 23 | type + year |
| `Oteai 1962` | 270 | type + year |
| `Oteai 1963` | 273 | type + year |
| `Oteai 1964` | 284 | type + year |
| `Oteai 1965` | 300 | type + year |
| `Oteai 1966` | 287 | type + year |
| `Oteai 1967` | 252 | type + year |
| `Oteai 1968` | 325 | type + year |
| `Oteai 1969` | 302 | type + year |
| `Oteai 1970` | 233 | type + year |
| `Oteai 1971` | 355 | type + year |
| `Oteai 1972` | 371 | type + year |
| `Oteai 1973` | 329 | type + year |
| `Oteai 1974` | 237 | type + year |
| `Oteai 1975` | 202 | type + year |
| `Oteai 1976` | 147 | type + year |
| `Oteai 1977` | 139 | type + year |
| `Oteai 1978` | 68 | type + year |

## 只可 type-only 或 hold

* `Oteai`：575 盘已有关联 ID 22；不要重复导入。
* `Oteai,SpringSession`（42）、`Oteai,AutumnSession`（45）：含 `1900-01-01` 占位日期且跨多年，只可 type-only；session 不是年度键。
* `Oteai, playoff series`（11）、`Oteai Spring Session playoff series`（5）、`Oteai, round-robin playoff series`（3）、`Oteai Spring Session playoff final`（1）、`Oteai winners' playoff series`（1）、`Oteai, playoff series final`（1）：hold；不能从名称推年度。
* `Kansai Ki-in Oteai`（26）、`KansaiKi-inOteai`（7）、`Kansai Branch Oteai`（6）、`Kansai Branch Summer Oteai`（4）、`Kansai Branch Winter Oteai`（4）、`KansaiBranchOteai`（3）、`KansaiBranchWinterOteai`（2）、`KansaiBetsuinOteai`（1）及带 Kobe Shinbun/Sunday Mainichi 的 Kansai raw：明确排除，不连 ID 22。
* `JapanPromotionTournament,1940/1941/1942/1946/1948/1949/1951/1952/1953/1954/1958/1960/1961/1962/1963/1964/1965/1966/1967/1969/1970/1971/1972/1973/1974/1975/1976/1977/1978/1979/1984/1989/1990/1991/1994/1995/1996/1997/1998/1999/2000`：这些 exact raw 共约 600 盘，部分早期 Spring/Fall 变体已关联，剩余年份/日期边界未冻结；暂只建议 type-only，逐年核对后再 link。`JapanPromotionTournament,1942` 含一盘 1941-11-30，必须 hold。
* `1967年日本大手合`（82）、`1987年日本大手合`（69）、`1986年日本大手合`（57）、`1988年日本大手合`（54）、`1981年日本大手合`（46）、`1969年日本大手合`（44）、`1985年日本大手合`（38）、`1992年日本大手合`（34）、`1990年日本大手合`（32）、`1989年日本大手合`（31）、`1983年日本大手合`（29）、`1991年日本大手合`（28）、`1993年日本大手合`（27）、`1982年日本大手合`（25）、`1984年日本大手合`（22）、`1964年日本大手合`（10）、`1956年日本大手合`（5）、`1963年日本大手合`（4）、`1948年日本大手合`（4）、`1977年日本大手合`（3）、`1953年日本大手合`（3）、`1955年日本大手合`（3）、`1947年日本大手合`（3）、`2002年日本大手合`（2）、`1998年日本大手合`（2）、`1997年日本大手合`（2）、`1999年日本大手合`（2）、`2001年日本大手合`（2），以及 `日本大手合`（3）：名称指向日本棋院，但日期/资料赛季未统一，先 type-only；有跨年或无日期者 hold。
* `AutumnOteaiWinners'tournamentsponsoredbyAsahiShinbun`、`1936AutumnOteaiWinners'PlayoffSeriessponsoredbyAsahiShinbun`、`TournamenttomarkAutumnOteai,sponsoredbyAsahiShinbun`、`AsahiShinbuntournamentfor1935AutumnOteaiwinners`、`1938SpringOteaiwinners'play-offsponsoredbyAsahiShinbun`：朝日赞助优胜者/附加赛，排除；不因含 Oteai 连 type。
* `Great relay game to commemorate 15 years of the Oteai`、`Game to mark Takagawa's promotion to A group of Oteai`、`Match between Oteai A and B groupsponsored by ...`、`Special tournament to select participants in Oteai` 及同类纪念/选拔/接力 raw：表演或特殊对局，排除并交 gpt-6-astra。
* Taiwan/Korea 及其他外部机构 promotion raw：统一排除。`Oteai 1939` 的 album `153470`（日期 1940-02-13,15,03-10,12）、`Oteai 1950` 的 `164724`（1951-01-10）、`Oteai 1952` 的 `164728`（1953-03）、`Oteai 1954` 的 `164747`（1955-03-09,10）日期与 raw 年不符；这些行只能 type-only，不能 year-link。

## 执行边界

本研究支持的最小安全批次是上表 48 个 `Oteai YYYY` raw 的 type + year，但由于数量与候选文档的 1,604 盘不一致，执行前必须重新导出 exact raw + album ID 并确认是否有当前 PROD 快照/去重口径差异。所有 session、playoff、朝日赞助优胜赛、纪念/接力赛、关西棋院及 Taiwan/Korea raw 继续 hold。
