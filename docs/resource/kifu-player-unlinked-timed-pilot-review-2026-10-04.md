# 独立复核：20 个未关联可读棋手 raw

- 复核范围：20 raws / 2,945 未关联槽位；这是前一 timed pilot 的完整 20 项复核，不是 3,007 raw 全量预处理。
- TEST 与 PROD 的 20 组精确 `(album_id, side, date, rank, opponent, source_path)` 清单一致；raw-player-value ID 也一致。
- 所有查询在 TEST、PROD 各自 `REPEATABLE READ READ ONLY` 事务内完成并回滚；数据库写入 0、译名 0、authoritative FK approval 0。
- `candidate_identity_slots` 仅表示证据支持的精确 raw 槽位候选，不是应用授权。新增规范名没有当前 player ID；TEST/PROD ID 不能互用。

| Raw | Slots | PROD decision / candidate ID | TEST decision / candidate ID | Candidate slots (PROD / TEST) |
|---|---:|---|---|---:|
| 小松英树 | 445 | REUSE_EXISTING_ID / 535 | HOLD_HOMONYM_OR_INSUFFICIENT / 536,1017 | 445 / 0 |
| 韩升周 | 317 | REUSE_EXISTING_ID / 513 | REUSE_EXISTING_ID / 514 | 317 / 317 |
| Ito Tomoe | 301 | HOLD_HOMONYM_OR_INSUFFICIENT / 3878,3879 | HOLD_HOMONYM_OR_INSUFFICIENT / 9675,9676 | 0 / 0 |
| 鹤山淳志 | 280 | REUSE_EXISTING_ID / 536 | HOLD_HOMONYM_OR_INSUFFICIENT / 537,1008 | 280 / 0 |
| 杨一 | 272 | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | 0 / 0 |
| Okubo Ichigen | 268 | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | 0 / 0 |
| 尹灿熙 | 263 | NEW_CHINESE_CANONICAL / new/no ID | NEW_CHINESE_CANONICAL / new/no ID | 263 / 263 |
| Kano Yoshinori | 256 | HOLD_HOMONYM_OR_INSUFFICIENT / 4048,4049 | HOLD_HOMONYM_OR_INSUFFICIENT / 9844,9845 | 0 / 0 |
| Iwata Tatsuaki | 255 | REUSE_EXISTING_ID / 4519 | REUSE_EXISTING_ID / 10310 | 255 / 255 |
| Sumino Tsunehiro | 252 | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | 0 / 0 |
| Aoyagi Hideo | 14 | REUSE_EXISTING_ID / 6400 | REUSE_EXISTING_ID / 12165 | 14 / 14 |
| 王祥云初段 | 8 | REUSE_EXISTING_ID / 559 | REUSE_EXISTING_ID / 560 | 8 / 8 |
| Hayashi Tennyu | 6 | HOLD_HOMONYM_OR_INSUFFICIENT / 436 | HOLD_HOMONYM_OR_INSUFFICIENT / 437 | 0 / 0 |
| OnoYutaka | 2 | HOLD_HOMONYM_OR_INSUFFICIENT / 4264 | HOLD_HOMONYM_OR_INSUFFICIENT / 10059 | 0 / 0 |
| Koga Yoshio | 1 | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | 0 / 0 |
| Nikkai, 1st Honinbo Sansa | 1 | NEW_CHINESE_CANONICAL / new/no ID | NEW_CHINESE_CANONICAL / new/no ID | 1 / 1 |
| OkumuraNoboru | 1 | HOLD_HOMONYM_OR_INSUFFICIENT / 4274 | HOLD_HOMONYM_OR_INSUFFICIENT / 10069 | 0 / 0 |
| YamaguchiShigeharu | 1 | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | HOLD_HOMONYM_OR_INSUFFICIENT / new/no ID | 0 / 0 |
| 久島国夫 | 1 | REUSE_EXISTING_ID / 6669 | REUSE_EXISTING_ID / 12438 | 1 / 1 |
| 小山滿鶴 | 1 | HOLD_HOMONYM_OR_INSUFFICIENT / 4406,4409 | HOLD_HOMONYM_OR_INSUFFICIENT / 10197,10200 | 0 / 0 |

## 结论与边界

PROD 有 7 个复用候选、2 个新中文规范名候选、11 个 HOLD，共 1584 个身份候选槽位。TEST 有 5 个复用候选、2 个新中文规范名候选、13 个 HOLD，共 859 个身份候选槽位。差异来自目录状态：TEST 中“小松英樹/小松英树”与“鶴山淳志/鹤山淳志”存在重复所有者，相关槽位因此只在 PROD 可候选。

现有实体候选只对精确 raw 组有效。没有执行简繁归并、自动去后缀扩张、同名归并、翻译或数据库写入。所有槽位 `(album_id, side)` 及日期、段位、对手、SGF source path 均在 JSON 逐项列出。

## 重点 HOLD

- `杨一`：两位同名职业棋手可能交错。原始游戏从 1996 到 2022，2012 以后同时出现 2/3 段和 6/7 段；现有证据不足以按段位可靠切分。近似目录“小杨一”不作为候选。
- `Ito Tomoe`、`Kano Yoshinori`、`小山滿鶴`：权威或专门来源已确认身份/旧名，但目录分别有两种以上 canonical owner，先解决具体 owner。
- TEST `小松英树` 与 `鹤山淳志`：PROD 各只有一个候选，TEST 各有简化/日文异体的两个独立 ID，不能跨库套用 PROD ID。
- `小松英树` 有一条 `1900-01-01` 占位日期槽；个人身份仍由其余年份与职业段位序列支持，日期本身不作为时间线证据。

## 每项证据
### 小松英树 — PROD REUSE_EXISTING_ID / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=10588，槽位=445。PROD candidates=[535]，target=535；TEST candidates=[536, 1017]，target=None。Nihon Ki-in profile names 小松英樹 / Komatsu Hideki; 1981 pro entry and the SGF rank/opponent timeline support the 1981–2025 group. One SGF DT is 1900 placeholder; its 6p rank/opponent are consistent with the later career, so identity is supported but date metadata is not.

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000148.htm](https://www.nihonkiin.or.jp/player/htm/ki000148.htm), [https://en.wikipedia.org/wiki/Hideki_Komatsu](https://en.wikipedia.org/wiki/Hideki_Komatsu)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### 韩升周 — PROD REUSE_EXISTING_ID / TEST REUSE_EXISTING_ID

raw_id=14163，槽位=317。PROD candidates=[513]，target=513；TEST candidates=[514]，target=514。Korean Baduk Association profile identifies 한승주 (韓昇周). Raw slots run 2013–2026 with rank sequence from 1d/2d to 9d and a professional opponent set consistent with this player.

Sources: [https://www.baduk.or.kr/record/player_view.asp?pkey=10000744](https://www.baduk.or.kr/record/player_view.asp?pkey=10000744)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### Ito Tomoe — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=7837，槽位=301。PROD candidates=[3878, 3879]，target=None；TEST candidates=[9675, 9676]，target=None。Kotobank identifies professional Go player 伊藤友恵. Catalog contains two competing owners 伊藤友恵 / 伊藤友惠 in each environment; their linked albums overlap years, so all 301 raw slots remain unassigned.

Sources: [https://kotobank.jp/word/%E4%BC%8A%E8%97%A4%E5%8F%8B%E6%81%B5-1055196](https://kotobank.jp/word/%E4%BC%8A%E8%97%A4%E5%8F%8B%E6%81%B5-1055196)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### 鹤山淳志 — PROD REUSE_EXISTING_ID / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=14368，槽位=280。PROD candidates=[536]，target=536；TEST candidates=[537, 1008]，target=None。Official Nihon Ki-in identifies 鶴山淳志 / Tsuruyama Atsushi; dates 1999–2026 and rank progression fit one career. PROD has one corresponding owner. TEST has both 鶴山淳志 (537) and simplified 鹤山淳志 (1008), both currently empty; hold TEST slots pending duplicate resolution.

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000365.htm](https://www.nihonkiin.or.jp/player/htm/ki000365.htm)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### 杨一 — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=11859，槽位=272。PROD candidates=[]，target=None；TEST candidates=[]，target=None。Dedicated biographies identify at least two Chinese Go professionals named 杨一 (born 1984 and 1995). Raw spans 1996–2022; mostly 3d–7d, with 2d/3d segments after 2012 mixed with 6d/7d in overlapping years. No defensible slot partition from current evidence; all 272 held. The near catalog row 小杨一 (4424/10215) is a different name and not treated as a candidate.

Sources: [https://zh.wikipedia.org/wiki/%E6%9D%A8%E4%B8%80_%281984%E5%B9%B4%29](https://zh.wikipedia.org/wiki/%E6%9D%A8%E4%B8%80_%281984%E5%B9%B4%29), [https://zh.wikipedia.org/wiki/%E6%9D%A8%E4%B8%80_%281995%E5%B9%B4%29](https://zh.wikipedia.org/wiki/%E6%9D%A8%E4%B8%80_%281995%E5%B9%B4%29)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### Okubo Ichigen — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=8571，槽位=268。PROD candidates=[]，target=None；TEST candidates=[]，target=None。GoRatings lists the romanized Go player; games span 1946–1978 with historic Japanese professionals. No authoritative Japanese spelling or catalog identity was established, so no Chinese canonical is proposed.

Sources: [https://www.goratings.org/en/players/1376.html](https://www.goratings.org/en/players/1376.html)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### 尹灿熙 — PROD NEW_CHINESE_CANONICAL / TEST NEW_CHINESE_CANONICAL

raw_id=10680，槽位=263。PROD candidates=[]，target=None；TEST candidates=[]，target=None。Korean association record confirms 윤찬희 and Hanja 尹燦熙. Raw is the simplified Chinese orthographic form; no current catalog candidate was found. Dates 2006–2025 and ranks progress from 初段 to 九段, consistent with the career. Candidate canonical is the existing raw spelling 尹灿熙; no translation was created.

Sources: [https://m.tvbaduk.com/info/info_gisa_view.asp?prpl_code=10000465](https://m.tvbaduk.com/info/info_gisa_view.asp?prpl_code=10000465), [https://www.baduk.or.kr/record/player_view.asp?pkey=10000465](https://www.baduk.or.kr/record/player_view.asp?pkey=10000465)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### Kano Yoshinori — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=7960，槽位=256。PROD candidates=[4048, 4049]，target=None；TEST candidates=[9844, 9845]，target=None。Nihon Ki-in profile confirms 加納嘉徳 / Kano Yoshinori. Each environment has competing catalog spellings 加纳嘉徳 and 加纳嘉德; existing link history favors one row but does not authorize selecting/merging a canonical. All 256 held.

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000015.html](https://www.nihonkiin.or.jp/player/htm/ki000015.html)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### Iwata Tatsuaki — PROD REUSE_EXISTING_ID / TEST REUSE_EXISTING_ID

raw_id=7862，槽位=255。PROD candidates=[4519]，target=4519；TEST candidates=[10310]，target=10310。Nihon Ki-in profile confirms 岩田達明 / Iwata Tatsuaki; current target canonical is 岩田达明 with alias 岩田正男. 1960–1978 SGF span and named Japanese/Chinese professional opponents fit. Three Chubu 1st rank labels in 1978 are special-format ranks; the official profile places promotion to 9d in 1964, matching the observed rank change. No competing identity evidence appeared.

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000016.htm](https://www.nihonkiin.or.jp/player/htm/ki000016.htm)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### Sumino Tsunehiro — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=8858，槽位=252。PROD candidates=[]，target=None；TEST candidates=[]，target=None。252 SGFs span 1941–1978 against Japanese professionals and ranks mainly 7p/8p, but no credible dedicated identity source or kanji was found. No Chinese canonical is proposed.

Sources: [https://www.goratings.org/](https://www.goratings.org/)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### Aoyagi Hideo — PROD REUSE_EXISTING_ID / TEST REUSE_EXISTING_ID

raw_id=7306，槽位=14。PROD candidates=[6400]，target=6400；TEST candidates=[12165]，target=12165。Kansai Ki-in roster and GoRatings identify 青柳英雄; sole candidate canonical in each environment is 青柳英雄. Dates 1960–1978 and 6p/7p ranks fit.

Sources: [https://kansaikiin.jp/wp/prokisi/](https://kansaikiin.jp/wp/prokisi/), [https://www.igorating.com/players/hideo-aoyagi](https://www.igorating.com/players/hideo-aoyagi)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### 王祥云初段 — PROD REUSE_EXISTING_ID / TEST REUSE_EXISTING_ID

raw_id=12601，槽位=8。PROD candidates=[559]，target=559；TEST candidates=[560]，target=560。Dedicated biography identifies Chinese professional 王祥云; catalog contains one candidate 王祥云 per environment. The eight rank-suffixed raw slots are from 2006–2008 after her 2005 professional entry, against known women professionals; safe exact raw scope only.

Sources: [https://zh.wikipedia.org/wiki/%E7%8E%8B%E7%A5%A5%E4%BA%91](https://zh.wikipedia.org/wiki/%E7%8E%8B%E7%A5%A5%E4%BA%91)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### Hayashi Tennyu — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=7583，槽位=6。PROD candidates=[436]，target=None；TEST candidates=[437]，target=None。Six historical games span 1750–1755 against Go-house players, but the romanization has no dedicated identity page/kanji anchor in this review. A near catalog name 林天予 is not enough to establish equivalence. All six held.

Sources: [https://en.wikipedia.org/wiki/Hayashi_%28Go%29](https://en.wikipedia.org/wiki/Hayashi_%28Go%29)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### OnoYutaka — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=8586，槽位=2。PROD candidates=[4264]，target=None；TEST candidates=[10059]，target=None。Two games vs Cho Chikun in 1968 and 1971, ranks 2d/4d, but no authoritative identity source or kanji anchor. Near name 大野伸行 is not treated as the same person.

Sources: [https://www.goratings.org/](https://www.goratings.org/)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### Koga Yoshio — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=8167，槽位=1。PROD candidates=[]，target=None；TEST candidates=[]，target=None。One 1957 game vs Go Seigen records 5d ama. That establishes an amateur rank only; no specific identity page or catalog candidate supports a canonical identity.

Sources: [https://www.goratings.org/](https://www.goratings.org/)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### Nikkai, 1st Honinbo Sansa — PROD NEW_CHINESE_CANONICAL / TEST NEW_CHINESE_CANONICAL

raw_id=8509，槽位=1。PROD candidates=[]，target=None；TEST candidates=[]，target=None。Dedicated biography identifies Nikkai as Honinbo Sansa (本因坊算砂) and describes the 1582 game against Kashio Rigen. No current catalog row matched the name. Proposed canonical uses the source-attested name 本因坊算砂; one exact slot is an identity candidate.

Sources: [https://en.wikipedia.org/wiki/Hon%27inb%C5%8D_Sansa](https://en.wikipedia.org/wiki/Hon%27inb%C5%8D_Sansa)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### OkumuraNoboru — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=8578，槽位=1。PROD candidates=[4274]，target=None；TEST candidates=[10069]，target=None。One 1977 4p game vs 横山孝一; GoRatings lists Okumura Noboru, and 奥村登 is a near possible Japanese reading in the catalog. No authoritative source establishes this equivalence, so hold.

Sources: [https://www.goratings.org/en/players/1883.html](https://www.goratings.org/en/players/1883.html)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### YamaguchiShigeharu — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=9117，槽位=1。PROD candidates=[]，target=None；TEST candidates=[]，target=None。One 1941 5p game vs 村岛谊纪; no credible dedicated Go identity source or kanji anchor was found. Hold.

Sources: [https://www.goratings.org/](https://www.goratings.org/)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### 久島国夫 — PROD REUSE_EXISTING_ID / TEST REUSE_EXISTING_ID

raw_id=9490，槽位=1。PROD candidates=[6669]，target=6669；TEST candidates=[12438]，target=12438。Nihon Ki-in identifies 久島国夫 / Hisajima Kunio; one catalog candidate 久岛国夫 in each environment, consistent simplified spelling. 1991 九段 game against 彦坂直人 is within his professional career.

Sources: [https://www.nihonkiin.or.jp/player/htm/ki000056.htm](https://www.nihonkiin.or.jp/player/htm/ki000056.htm)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

### 小山滿鶴 — PROD HOLD_HOMONYM_OR_INSUFFICIENT / TEST HOLD_HOMONYM_OR_INSUFFICIENT

raw_id=10556，槽位=1。PROD candidates=[4406, 4409]，target=None；TEST candidates=[10197, 10200]，target=None。Go game-profile source says 小山滿鶴 was a former name of 小山栄美, matching the 2001 五段 SGF. Catalog has separate 小山栄美 / 小山荣美 candidates (4406/4409; TEST 10197/10200), so exact owner resolution is required. All one slot held.

Sources: [https://igo-kifu.com/en/player/239](https://igo-kifu.com/en/player/239)

Exact album-side slot IDs and SGF source paths are in JSON `observed_unlinked_slots_all`; safe candidate subsets are in `prod.candidate_identity_slots` and `test.candidate_identity_slots`.

JSON SHA-256: `de1955a64d4dde46f05f1b1081f2944dcf59aa4da703131a2771b680343b058a`.
