# Ranks 101–150: secondary six Wikipedia locale evidence (v2 pending)

2026-10-03. Source-only v2 follow-up to the initial pending packet. Scope is the 30 source-positive identities in the primary-five v2 packet × `de`, `es`, `fr`, `ru`, `tr`, and `ua` (Wikipedia language code `uk`). No application/DB edit, self-approval, or commit.

## Bound inputs and output

- Input review: [primary-five v2 independent correction review](kifu-name-player-ranks101-150-primary-five-v2-independent-correction-review-sol-2026-10-03.md), recording 30/30 external identity evidence PASS and 109/109 combined identity/display evidence PASS at those bounded gates.
- Input protected directory: `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-primary-five-pending-codex-v2/`; manifest SHA-256 `a15c44c1b258f1255541a57bb46e3847682b6bfc4606d0e36e28973781094b9f`; identity proposals SHA-256 `822556916de7ede94919aafb961fa806c70708dae913c101121a70ac564d4e14`.
- v1 packet retained unchanged at `~/.local/share/kifu-name-audit/2026-10-03/secondary-six-wikipedia-pending-luna-2026-10-03/`; it has 0 PASS / 180 HOLD and remains the record of the initial API-limited attempt.
- v2 protected packet directory: `~/.local/share/kifu-name-audit/2026-10-03/secondary-six-wikipedia-pending-luna-v2-2026-10-03/` (directory mode `0700`; packet and manifest mode `0400`).
- v2 packet SHA-256: `5bef7f3f9edbd48b4b98ff4d0ad88601552c16b500dae2f133d2467f54865eb3`.
- v2 manifest SHA-256: `475810d5bbf6da42ff625f450f12ce0f7cd55570a314deb0064872cc21f5a3c9`.

## Counts

| Locale | Wikipedia language | Cells | PASS | HOLD |
| --- | --- | ---: | ---: | ---: |
| de | de | 30 | 0 | 30 |
| es | es | 30 | 0 | 30 |
| fr | fr | 30 | 1 | 29 |
| ru | ru | 30 | 0 | 30 |
| tr | tr | 30 | 0 | 30 |
| ua | uk | 30 | 0 | 30 |
| **Total** |  | **180** | **1** | **179** |

## Positive evidence: rank 116, Ding Hao, French

The directly fetched English Wikipedia article `https://en.wikipedia.org/wiki/Ding_Hao` links to `https://fr.wikipedia.org/wiki/Ding_Hao` with `hreflang="fr"`. Both pages identify the same Wikidata entity, `Q25252394`. The Wikidata HTML page `https://www.wikidata.org/wiki/Q25252394` displays birth date 13 June 2000, matching the protected official identity anchor DOB `2000-06-13` and GoRatings profile ID 1511. The French article's displayed H1/name is `Ding Hao`.

The PASS row records the French article URL, language, title, heading, current revision ID `233421195`, retrieval timestamp, and SHA-256 of the fetched article HTML body (`46dc5d7d5c2c9a13c0ea0735e0e346ed931c6c3a414d234d993d35ce7c3811fd`). It also records the English linking article revision/body hash and the entity page body hash used for DOB identity verification. This is a source correspondence result only; it does not approve raw scope, candidate applicability, or any database write.

## HOLD handling

A bounded native-language HTML search was attempted for the other nine members of the first ten identities by occurrence count. Search misses and unrelated result pages were retained as HOLD; they are not absence evidence. The initial Wikidata API lookup had returned HTTP 429, so the remaining unverified cells retain HOLD rather than implying that matching-language articles do not exist. No transliteration was inferred. No additional local Go source was consulted after the positive French match.
