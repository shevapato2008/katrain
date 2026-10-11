# Read-only timed pilot: missing unlinked readable player raws

- Sample: **20 raw values / 2,945 unlinked slots** from supplied pool of 3,007 raws / 30,621 slots.
- Yield: **6 REUSE_EXISTING_ID, 3 NEW_CHINESE_CANONICAL, 11 HOLD**; 9/20 have a candidate identity classification.
- These are evidence classifications only, not authoritative FK approvals. Database writes: **0**; translations: **0**; FK approvals: **0**.
- Overall elapsed estimate: **765 sec (~12.8 min)** from first PROD read through bundle completion; individual seconds are retrospective estimates, not stopwatch measurements.
- Read-only `REPEATABLE READ` snapshot. Top 10 excludes exact raw names in the reviewed top-8 decision. Hash band uses `md5(raw)` ordering over 1–30-slot raws, excluding Unknown/Black/White.
- Catalog checks used exact canonical/alias equality plus targeted substring scans for likely orthographic collisions; one representative unlinked slot per raw.

| Raw | Slots | Stratum | Representative | Catalog candidate | Classification | Est. sec |
|---|---:|---|---|---|---|---:|
| 小松英树 | 445 | top | 2023-09-25 vs 安达利昌 (album 5554) | 535 | REUSE_EXISTING_ID | 60 |
| 韩升周 | 317 | top | 2022-08-29 vs 金庭贤 (album 413) | 513 | REUSE_EXISTING_ID | 60 |
| Ito Tomoe | 301 | top | 1934-10-03,04 vs Shimamura Toshihiro (album 153089) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 60 |
| 鹤山淳志 | 280 | top | 2022-09-08 vs 平田智也 (album 507) | none | NEW_CHINESE_CANONICAL | 60 |
| 杨一 | 272 | top | 2022-11-15 vs 林立祥 (album 9621) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 60 |
| Okubo Ichigen | 268 | top | 1968-01-11 vs Go Seigen (album 24966) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 60 |
| 尹灿熙 | 263 | top | 2022-12-05 vs 金彩瑛 (album 993) | none | NEW_CHINESE_CANONICAL | 60 |
| Kano Yoshinori | 256 | top | 1956-08-06,07 vs Go Seigen (album 24825) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 60 |
| Iwata Tatsuaki | 255 | top | 1961-12-20,21 vs Go Seigen (album 24915) | 4519 | REUSE_EXISTING_ID | 60 |
| Sumino Tsunehiro | 252 | top | 1941-04-30,05-01 vs Takagawa Kaku (album 156750) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 60 |
| Aoyagi Hideo | 14 | hashband | 1973-08-02 vs Takemiya Masaki (album 157117) | 6400 | REUSE_EXISTING_ID | 35 |
| 王祥云初段 | 8 | hashband | 2007-05-30 vs 曹又尹初段 (album 37877) | 559 | REUSE_EXISTING_ID | 35 |
| Hayashi Tennyu | 6 | hashband | 1750-12-15 vs Honinbo Hakugen (album 155635) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 35 |
| OnoYutaka | 2 | hashband | 1968-09-25 vs ChoChikun (album 143513) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 35 |
| Koga Yoshio | 1 | hashband | 1957-06-02 vs Go Seigen (album 24844) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 35 |
| Nikkai, 1st Honinbo Sansa | 1 | hashband | 1582-06-20 vs Kashio Rigen (album 154458) | none | NEW_CHINESE_CANONICAL | 35 |
| OkumuraNoboru | 1 | hashband | 1977-09-21 vs 横山孝一 (album 29761) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 35 |
| YamaguchiShigeharu | 1 | hashband | 1941-07-31 vs 村岛谊纪 (album 51153) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 35 |
| 久島国夫 | 1 | hashband | 1991-07-21 vs 彦坂直人 (album 94444) | 6669 | REUSE_EXISTING_ID | 35 |
| 小山滿鶴 | 1 | hashband | 2001-12-05 vs 佃亜紀子 (album 58040) | none | HOLD_HOMONYM_OR_INSUFFICIENT | 35 |

## Evidence

### 小松英树 — REUSE_EXISTING_ID

445 slots; SGF context 2023-09-25 vs 安达利昌, album `5554` (`data/kifu-album/19x19/41288532.sgf`). Catalog 535 小松英樹 exact; Nihon Ki-in confirms 小松英樹 / KOMATSU, Hideki.

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000148.htm](https://www.nihonkiin.or.jp/player/htm/ki000148.htm)

### 韩升周 — REUSE_EXISTING_ID

317 slots; SGF context 2022-08-29 vs 金庭贤, album `413` (`data/kifu-album/19x19/17189794.sgf`). Catalog 513 韩升周 exact; Korean Baduk Association identifies 한승주 (韓昇周).

Sources: [https://www.baduk.or.kr/record/player_view.asp?pkey=10000744](https://www.baduk.or.kr/record/player_view.asp?pkey=10000744)

### Ito Tomoe — HOLD_HOMONYM_OR_INSUFFICIENT

301 slots; SGF context 1934-10-03,04 vs Shimamura Toshihiro, album `153089` (`data/kifu-album/CWI_History_Full/Oteai/1934/180.sgf`). Likely 伊藤友恵, but competing catalog owners 伊藤友恵 / 伊藤友惠 (IDs 3878, 3879); no owner decision.

Sources: [https://kotobank.jp/word/%E4%BC%8A藤友恵-1055196](https://kotobank.jp/word/%E4%BC%8A藤友恵-1055196)

### 鹤山淳志 — NEW_CHINESE_CANONICAL

280 slots; SGF context 2022-09-08 vs 平田智也, album `507` (`data/kifu-album/19x19/17641288.sgf`). Raw Chinese form corresponds to official 鶴山淳志 / Tsuruyama Atsushi; no exact/near catalog candidate found in targeted scan.

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000365.htm](https://www.nihonkiin.or.jp/player/htm/ki000365.htm)

### 杨一 — HOLD_HOMONYM_OR_INSUFFICIENT

272 slots; SGF context 2022-11-15 vs 林立祥, album `9621` (`data/kifu-album/19x19/41421915.sgf`). Sources identify at least two professionals named 杨一 (1984 and 1995); one context cannot partition all 272 slots.

Sources: [https://zh.wikipedia.org/wiki/%E6%9D%A8%E4%B8%80_%281984%E5%B9%B4%29](https://zh.wikipedia.org/wiki/%E6%9D%A8%E4%B8%80_%281984%E5%B9%B4%29), [https://zh.wikipedia.org/wiki/%E6%9D%A8%E4%B8%80_%281995%E5%B9%B4%29](https://zh.wikipedia.org/wiki/%E6%9D%A8%E4%B8%80_%281995%E5%B9%B4%29)

### Okubo Ichigen — HOLD_HOMONYM_OR_INSUFFICIENT

268 slots; SGF context 1968-01-11 vs Go Seigen, album `24966` (`data/kifu-album/Go_Seigen/1968-01-11.sgf`). Go ratings lists a player under this romanization; no authoritative Japanese/Chinese identity form or catalog owner established.

Sources: [https://www.goratings.org/en/players/1376.html](https://www.goratings.org/en/players/1376.html)

### 尹灿熙 — NEW_CHINESE_CANONICAL

263 slots; SGF context 2022-12-05 vs 金彩瑛, album `993` (`data/kifu-album/19x19/21186427.sgf`). KBA confirms 윤찬희 and Korean coverage supplies 尹燦熙; raw is simplified Chinese form. No exact catalog candidate found.

Sources: [https://m.tvbaduk.com/info/info_gisa_view.asp?prpl_code=10000465](https://m.tvbaduk.com/info/info_gisa_view.asp?prpl_code=10000465), [https://www.nocutnews.co.kr/news/5531320](https://www.nocutnews.co.kr/news/5531320)

### Kano Yoshinori — HOLD_HOMONYM_OR_INSUFFICIENT

256 slots; SGF context 1956-08-06,07 vs Go Seigen, album `24825` (`data/kifu-album/Go_Seigen/1956-08-06.sgf`). Official profile identifies 加納嘉徳 / Kano Yoshinori; catalog has competing near variants 加纳嘉徳 (4048) and 加纳嘉德 (4049).

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000015.html](https://www.nihonkiin.or.jp/player/htm/ki000015.html)

### Iwata Tatsuaki — REUSE_EXISTING_ID

255 slots; SGF context 1961-12-20,21 vs Go Seigen, album `24915` (`data/kifu-album/Go_Seigen/1961-12-20.sgf`). Official profile identifies 岩田達明; catalog 4519 岩田达明 has alias 岩田正男.

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000016.htm](https://www.nihonkiin.or.jp/player/htm/ki000016.htm)

### Sumino Tsunehiro — HOLD_HOMONYM_OR_INSUFFICIENT

252 slots; SGF context 1941-04-30,05-01 vs Takagawa Kaku, album `156750` (`data/kifu-album/CWI_History_Full/people/Takagawa/Tak-0201.sgf`). No credible association or dedicated identity page found for this romanization; kanji/Chinese canonical not established.

Sources: [https://www.goratings.org/](https://www.goratings.org/)

### Aoyagi Hideo — REUSE_EXISTING_ID

14 slots; SGF context 1973-08-02 vs Takemiya Masaki, album `157117` (`data/kifu-album/CWI_1950_1978/AJ1st/04/24.sgf`). Kansai Ki-in roster identifies 青柳英雄; exact catalog 6400 青柳英雄.

Sources: [https://kansaikiin.jp/wp/prokisi/](https://kansaikiin.jp/wp/prokisi/), [https://www.igorating.com/players/hideo-aoyagi](https://www.igorating.com/players/hideo-aoyagi)

### 王祥云初段 — REUSE_EXISTING_ID

8 slots; SGF context 2007-05-30 vs 曹又尹初段, album `37877` (`data/kifu-album/19x19/41302094.sgf`). Identity page confirms 王祥云; catalog 559 王祥云.

Sources: [https://zh.wikipedia.org/wiki/%E7%8E%8B%E7%A5%A5%E4%BA%91](https://zh.wikipedia.org/wiki/%E7%8E%8B%E7%A5%A5%E4%BA%91)

### Hayashi Tennyu — HOLD_HOMONYM_OR_INSUFFICIENT

6 slots; SGF context 1750-12-15 vs Honinbo Hakugen, album `155635` (`data/kifu-album/CWI_History_Full/ancient/castle/cg163.sgf`). Historical romanization lacks reliable identity/kanji disambiguation in this pass.

Sources: [https://en.wikipedia.org/wiki/Hayashi_%28Go%29](https://en.wikipedia.org/wiki/Hayashi_%28Go%29)

### OnoYutaka — HOLD_HOMONYM_OR_INSUFFICIENT

2 slots; SGF context 1968-09-25 vs ChoChikun, album `143513` (`data/kifu-album/19x19/41569053.sgf`). Romanization-only raw; no credible dedicated Go identity page found.

Sources: [https://www.goratings.org/](https://www.goratings.org/)

### Koga Yoshio — HOLD_HOMONYM_OR_INSUFFICIENT

1 slots; SGF context 1957-06-02 vs Go Seigen, album `24844` (`data/kifu-album/Go_Seigen/1957-06-02.sgf`). SGF rank says 5d ama; no identity evidence to assign a Chinese canonical.

Sources: [https://www.goratings.org/](https://www.goratings.org/)

### Nikkai, 1st Honinbo Sansa — NEW_CHINESE_CANONICAL

1 slots; SGF context 1582-06-20 vs Kashio Rigen, album `154458` (`data/kifu-album/CWI_History_Full/ancient/Honinbo_Sansa/1.sgf`). Dedicated page ties Nikkai to Honinbo Sansa, 本因坊算砂, and the 1582 game context; no exact catalog candidate found.

Sources: [https://en.wikipedia.org/wiki/Hon%27inb%C5%8D_Sansa](https://en.wikipedia.org/wiki/Hon%27inb%C5%8D_Sansa)

### OkumuraNoboru — HOLD_HOMONYM_OR_INSUFFICIENT

1 slots; SGF context 1977-09-21 vs 横山孝一, album `29761` (`data/kifu-album/19x19/41291526.sgf`). Go ratings lists the romanization, but no credible identity page or Chinese/Japanese name was established.

Sources: [https://www.goratings.org/en/players/1883.html](https://www.goratings.org/en/players/1883.html)

### YamaguchiShigeharu — HOLD_HOMONYM_OR_INSUFFICIENT

1 slots; SGF context 1941-07-31 vs 村岛谊纪, album `51153` (`data/kifu-album/19x19/41333423.sgf`). Romanization is not disambiguated by a credible Go identity source.

Sources: [https://www.goratings.org/](https://www.goratings.org/)

### 久島国夫 — REUSE_EXISTING_ID

1 slots; SGF context 1991-07-21 vs 彦坂直人, album `94444` (`data/kifu-album/19x19/41394166.sgf`). Nihon Ki-in confirms 久島国夫 / Hisajima Kunio; catalog 6669 久岛国夫 is simplified orthographic match.

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000056.htm](https://www.nihonkiin.or.jp/player/htm/ki000056.htm)

### 小山滿鶴 — HOLD_HOMONYM_OR_INSUFFICIENT

1 slots; SGF context 2001-12-05 vs 佃亜紀子, album `58040` (`data/kifu-album/19x19/41341848.sgf`). Profile says 小山滿鶴 is a former name of 小山栄美; production candidate-owner follow-up timed out, so retain HOLD pending owner check.

Sources: [https://igo-kifu.com/en/player/239](https://igo-kifu.com/en/player/239)

## Timing limitation

The initial query start was not separately wall-clock stamped. Overall elapsed and item times are retrospective estimates, suitable only as a rough ETA prior. The sample is frequency weighted and does not represent the raw-count distribution.

JSON SHA-256: `16274ae86c288d4b959170b613f4de98b42de8859e5c59fded2e9efcb81842ed`.
