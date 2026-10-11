# Existing 17 raws: independent identity and exact-slot decision

Decision: **3,576 approved NULL player slots; 807 HOLD**, identically scoped in TEST and PROD. The original 661 slots for 鹤山淳志、大桥拓文、李小溪 remain HOLD; 146 more slots are held for unresolved record context. No database write or production-code edit was performed.

Machine-readable decision: [kifu-player-existing17-independent-decision-astra-2026-10-04.json](kifu-player-existing17-independent-decision-astra-2026-10-04.json); SHA-256 `71ea900692f13ba6c499e13c9777d17c607a5a7721c5e469303ec34766cda684`.

| Exact raw | Approved | HOLD | TEST ID | PROD ID |
| --- | ---: | ---: | ---: | ---: |
| 李昌锡 | 388 | 20 | 194 | 193 |
| 金庭贤 | 357 | 11 | 34 | 34 |
| 姜升旼 | 347 | 7 | 399 | 398 |
| 金升宰 | 343 | 11 | 147 | 146 |
| 小县真树 | 301 | 5 | 443 | 442 |
| 朴键昊 | 289 | 16 | 146 | 145 |
| 鹤山淳志 | 0 | 280 | HOLD | HOLD |
| 宫泽吾朗 | 245 | 5 | 543 | 542 |
| 梶原武雄 | 206 | 34 | 12342 | 6578 |
| 高根台 | 212 | 3 | 485 | 484 |
| 大桥拓文 | 0 | 214 | HOLD | HOLD |
| 加藤启子 | 199 | 1 | 422 | 421 |
| 桥本昌二 | 184 | 15 | 12346 | 6582 |
| 金东烨 | 193 | 1 | 12545 | 6776 |
| 东野弘昭 | 173 | 16 | 12456 | 6687 |
| 李小溪 | 0 | 167 | HOLD | HOLD |
| 上村阳生 | 139 | 1 | 12454 | 6685 |

## Evidence and exceptions

- The 14 identities have official Korea Baduk Association, Nihon Ki-in or Kansai Ki-in identity anchors. Raw, official and current canonical spellings each resolve to the same sole owner in each environment. Existing canonical spellings remain unchanged.
- 金庭贤 is the older 金庭賢 (1991 / pro 2009); the younger homophone is 金楨玹 (1999 / pro 2023). [Official older profile](https://www.baduk.or.kr/record/player_view.asp?pkey=10000522), [younger profile](https://www.baduk.or.kr/record/player_view.asp?pkey=10001244).
- Album **65479 black 李昌锡** is independently corroborated as an amateur in the 2013-07-09 MLily first round; **90745 white 金庭贤** is corroborated as an amateur in the 2009-02-28 BC Cup. Their frozen rank/result metadata is not corrected by this approval. [MLily result](https://www.nihonkiin.or.jp/match/mlily/001.html), [BC Cup result](https://www.nihonkiin.or.jp/match/bc/001.html).
- Album **62748 black 高根台** has matching identity/date/event/source and 176 moves; the missing result remains missing. This is an identity-only exception.
- All 4,318 complete SGFs and both full frozen snapshots were checked. Context HOLD reasons include source/SO mismatch, unresolved January 1 dates, career/rank chronology conflicts, handicap or study setups, garbled metadata and incomplete game data. Reason counts overlap; exact slot reasons are in JSON.

## Execution boundary

- Write only the enumerated NULL player foreign keys. No alias, translation, canonical, raw-staging, metadata, event or edition writes.
- Preserve all earlier player HOLD slots, including 19 opposite-side slots found inside this frozen album scope. The approved set intersects no previous held player slot.
- The six-league event batch committed after this freeze. Before capture, the executor must accept **only the exact 137 already-applied event_id changes** enumerated in this decision. Both applied-plan preimages matched every shared column and SGF hash; edition IDs remain NULL. No other drift is permitted.
- Use the pinned full preimages, collision checks, target catalogs, transaction locks, exact NULL compare-and-set, rollback dry runs and independent post-commit full-scope verification required by the JSON.

## Input pins

- Frozen manifest: `95cd914fb3836b78dfa44e15503afe31c8c78f942bb547d8aa888b8b5a7dfb1e`.
- TEST full snapshot: `760cda467edb413f9ffeb7659599e2865e36b75614d2ba058ec30d7aecb75a43`.
- PROD full snapshot: `8165e684c9ddbc374b030d871d82198dd2045d0bdc3d4f405c696101a0e20838`.
- Source capture manifest: `89cf93235966c5482e9b4e1acf907a95c81f85e3e5e767152cd12002d87c782f`.
