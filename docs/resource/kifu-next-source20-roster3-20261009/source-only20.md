# Next 20 source-only roster research

Snapshot `2026-10-08T20:49:29.266394+00:00`; source packet SHA-256 `9d6bfab35dd5dbca5d1bcc79f49cfa022c304c77e769e6008fa00cf5a7aa3b1a`.

Selection is based on linked-slot frequency among one-hole owners. It excludes the pending20 and held IDs listed in `selection20.json`.

## Disposition

Five candidates have Korean Go roster evidence from TVBaduk and official Korea Baduk Association player pages, paired with a Go database identity bridge. They remain source-only and unbound. Fifteen rows are honestly held, including spelling conflicts and candidates with no independent Korean or Traditional Chinese page captured.

| PID | Slots | Missing | Lead | Status |
|---:|---:|:---:|---|---|
| 4071 | 38 | ko | 화웨이룽 | honest_hold_lead_only |
| 6714 | 34 | tw | — | honest_hold_traditional_chinese_source_missing |
| 6366 | 30 | ko | 천루이 | provisional_direct_korean_go_roster_match |
| 6531 | 29 | ko | — | honest_hold_identity_anchor_only |
| 5101 | 26 | ko | — | honest_hold_no_independent_korean_source |
| 6329 | 22 | ko | — | honest_hold_no_independent_korean_source |
| 5495 | 19 | ko | — | honest_hold_no_independent_korean_source |
| 5806 | 19 | ko | — | honest_hold_identity_anchor_only |
| 6552 | 18 | ko | 황진셴 | honest_hold_conflicting_korean_roster_spelling |
| 5115 | 17 | ko | — | honest_hold_no_independent_korean_source |
| 5214 | 16 | ko | — | honest_hold_no_independent_korean_source |
| 5349 | 15 | ko | 선징 | provisional_direct_korean_go_roster_match |
| 5468 | 15 | ko | 왕예후이 | honest_hold_conflicting_korean_roster_spelling |
| 5952 | 15 | ko | 자오쯔지 | provisional_direct_korean_go_roster_match |
| 5543 | 14 | ko | — | honest_hold_no_independent_korean_source |
| 5814 | 14 | ko | — | honest_hold_no_independent_korean_source |
| 5940 | 12 | ko | — | honest_hold_no_independent_korean_source |
| 6045 | 12 | ko | — | honest_hold_no_independent_korean_source |
| 6322 | 12 | ko | 천더룽 | provisional_direct_korean_go_roster_match |
| 6550 | 12 | ko | 황번 | provisional_direct_korean_go_roster_match |

## Confirmed roster pages (provisional source-only)

- PID 6366: TVBaduk profile code `20002017` and KBA pkey `20002017` print 천루이, 1단; u-go.net bridges Chen Rui to 陈瑞.
- PID 5349: TVBaduk profile code `20002031` and KBA pkey `20002031` print 선징, 1단; u-go.net bridges Shen Jing to 沈静.
- PID 5952: TVBaduk profile code `20002000` and KBA pkey `20002000` print 자오쯔지, 1단; u-go.net and GoRatings bridge Zhao Ziji to 赵子骥.
- PID 6322: TVBaduk profile code `20002015` and KBA pkey `20002015` print 천더룽, 1단; u-go.net bridges Chen Delong to 陈德龙. Profile Hanja is incomplete.
- PID 6550: TVBaduk profile code `20002047` and KBA pkey `20002047` print 황번, 1단; u-go.net bridges Huang Bi to 黄贲. Profile Hanja is blank.

## Holds

- PID 4071 has only the old Daum spelling lead 화웨이룽; Hotongo confirms 华伟荣 as a seven-dan professional but gives no Korean spelling.
- PID 6552 conflicts: the TVBaduk and KBA code `20002048` pages say 황진쉬안 while this owner is anchored as 黄进先 / Huang Jinxian.
- PID 5468 conflicts: TVBaduk and KBA code `20002080` pages say 왕예훙이 while this owner is anchored as 王业辉 / Wang Yehui; its Hanja field is truncated.
- PIDs 6531 and 5806 have direct Haifong pro roster identity anchors, but no Korean spelling source was found.
- Other names remain hold with no Korean name generated. PID 6714 also lacks a captured zh-Hant/TW source.

`capture-index.json` has each URL, request method/data, status, timestamp, byte count, SHA-256, and body path. Raw captures are in `captures/`.
