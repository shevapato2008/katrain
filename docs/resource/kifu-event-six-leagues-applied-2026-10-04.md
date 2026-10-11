# Six-league exact event types: applied on 2026-10-04

The [independent decision](kifu-event-after743-leagues-independent-decision-astra-2026-10-04.json) approved 6,810 exact album IDs for type-only event links and held 1,784 IDs. The approved target IDs in both databases were 41 中国围棋甲级联赛 (5,062), 42 中国女子围棋甲级联赛 (415), 50 韩国围棋联赛 (192), 51 韩国女子围棋联赛 (722), and 52 韩国元老围棋联赛 (419). Korean second division (186 candidates plus 1,025 earlier held records) remained held. No event edition IDs were assigned.

The [executor](../../katrain/web/kifu/event_leagues_exact.py) was independently reviewed after two capture fixes. Final module SHA-256: `b772b92fdd0a28b44672492550c428ac971594beae69af78f83c224218722227`. Focused tests: 4 passed. TEST and PROD each captured all 8,594 approved/held rows and their SGF/source/catalog preimages. Both real transaction dry runs rolled back and recaptured the same plan. Apply ran TEST then PROD, with independent post-commit full-scope reads passing inside the executor.

| Environment | Approved plan SHA-256 | New type links | Held | Event links after commit / 173,025 | Fully linked games / 173,025 |
| --- | --- | ---: | ---: | ---: | ---: |
| TEST | `9c3b0f0a796fcecd5c08a7eb6dd04fe11c5106e96c869357eeb0c0ca2eb46ced` | 6,810 | 1,784 | 98,889 | 76,521 |
| PROD | `715ba92e45749d76bd00e9518efef3c6c7a05d07b320b5baeb8177d38667e383` | 6,810 | 1,784 | 99,371 | 77,673 |

Only approved `kifu_albums.event_id` values changed. Existing SGF, raw event strings, player IDs, dates, sources, event catalog/aliases and held rows were preserved. PROD player FK coverage remained 301,559/346,050. Full preprocessing and five-language translation remain outstanding.
