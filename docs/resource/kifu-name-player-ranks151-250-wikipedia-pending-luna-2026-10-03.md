# Raw-player ranks 151–250: Wikipedia name candidates (pending)

Date: 2026-10-03. Source research only; no code, database, or production changes. The packet contains the complete 100-row frequency scope and a five-language (`cn / tw / jp / ko / en`) status matrix. `PASS` records a same-person Wikipedia page and its displayed name as an unsigned candidate. `HOLD` is unresolved; it does not claim that a page is absent. No candidate is independently reviewed or approved.

## Frozen scope

The scope was counted from `~/.local/share/kifu-name-audit/2026-10-03/raw-player-next7-phase4-signed-batch-binding-sol/inventory.historical-clone.json.gz`, compressed SHA-256 `e320eaf300bbbeffa4fdb1fca006b2d516ccb041653c58e192cd1a483490597e`, embedded base SHA-256 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`, snapshot `2026-10-02T23:25:59.957753Z`. For each album association, nonempty black and white raw-player slots (indexes 2 and 3) were counted separately; results sort by descending occurrences then raw string. The compact JSON for ranks 151–250 has SHA-256 `c2210fb37ad09e546927dcc9a402fda6ac49057d1ce7cdc4b87c27de67626645`. Rank 151 is 白洪淅 (475); rank 250 is 陈临新 (332).

## Source findings and status

| Language | PASS | HOLD |
|---|---:|---:|
| cn | 1 | 99 |
| tw | 0 | 100 |
| jp | 1 | 99 |
| ko | 1 | 99 |
| en | 1 | 99 |
| **Total** | **4** | **496** |

The only independently resolved identity in this pass is rank 151, 白洪淅. The [Korea Baduk Association official profile](https://www.baduk.or.kr/record/player_view.asp?pkey=10000276) gives 백홍석(白洪淅), DOB 1986-08-13. The [GoRatings profile ID 315](https://www.goratings.org/ja/players/315.html) has the heading 白洪淅, the same DOB, and links to the Chinese, Japanese, Korean, and English Wikipedia pages. The linked Wikipedia pages identify the same Go player and show these article display names: cn 白洪淅 ([zh page](https://zh.wikipedia.org/wiki/白洪淅)); jp 白洪淅 ([ja page](https://ja.wikipedia.org/wiki/白洪淅)); ko 백홍석 ([ko page](https://ko.wikipedia.org/wiki/백홍석_(바둑_기사))); en Paek Hong-suk ([en page](https://en.wikipedia.org/wiki/Paek_Hong-suk)). The `tw` cell remains HOLD because this graph did not establish a separate `zh-tw` page; no absence claim is made.

Ranks 152–250 remain HOLD across all five languages: this bounded pass did not establish independent official/Go identity records and Wikipedia interlanguage mappings for them. Search misses are not evidence of absence; no transliteration or alias was invented.

## Protected packet

Protected directory: `~/.local/share/kifu-name-audit/2026-10-03/player-ranks151-250-wikipedia-pending-luna-v1/` (directory mode 0700; packet and manifest mode 0400). The JSONL has 500 rows and SHA-256 `2b75ec23b6c125484d258b3726bf3a48c4d7b9d594fe79e70773e79f039e7bf9`; manifest SHA-256 `7b6b1f396f587d33aa376645771d8ba951b7d0c19da8e5a341e53d03a445e9bc`. Each cell retains exact rank, raw string, occurrences, language, status, candidate display name/URL when present, and reason. No approved-name preimage, production-write readiness, identity binding, or database action is asserted.
