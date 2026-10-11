# Next event exact scope: applied on 2026-10-04

The independently reviewed decision is in `kifu-event-next-scope-independent-decision-astra-2026-10-04.json`. The compared TEST/PROD plan SHA-256 is `7e54d349be3e252ddc27894af82b40221567f494f05d932459ca80ffa6fd6262`. Focused tests: 9 passed. Both transactional dry runs rolled back and matched their read-only before captures byte for byte.

| Environment | Exact event links committed | Held | New `中日围棋对抗赛` type ID | Existing Japanese Pro Best Ten type ID | Independent post-commit verification |
| --- | ---: | ---: | ---: | ---: | ---: |
| TEST | 743 | 453 | 75 | 44 | 743 verified, 453 held |
| PROD | 743 | 453 | 75 | 44 | 743 verified, 453 held |

The 743 links consist of 637 China–Japan regular exchange games and 106 Japanese Pro Best Ten games. Only `kifu_albums.event_id` and the one new event type row were written; edition IDs remain null. Existing SGF, raw event strings, player IDs, aliases, and the 453 held rows were retained.

Read-only post-commit coverage: TEST 92,079/173,025 games have event IDs and 69,485 games have both players and event; PROD 92,561/173,025 and 70,514 respectively. Preprocessing is still incomplete; these counts do not represent translation coverage.
