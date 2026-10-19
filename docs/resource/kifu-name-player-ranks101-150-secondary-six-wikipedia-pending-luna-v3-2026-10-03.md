# Ranks 101–150: secondary six Wikipedia locale evidence (v3 pending)

2026-10-03. v3 preserves the single French article PASS from v2 and adds direct HTML discovery evidence for rank 118. It is a source-only packet for the 30 primary-five v2 identities × `de`, `es`, `fr`, `ru`, `tr`, and `ua` (Wikipedia language code `uk`). No application/DB edits, self-approval, or commit.

## Bound inputs and packet

- Input review: [primary-five v2 independent correction review](kifu-name-player-ranks101-150-primary-five-v2-independent-correction-review-sol-2026-10-03.md); it records 30/30 external identity evidence PASS and 109/109 combined identity/display evidence PASS at those bounded gates.
- Input protected directory: `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-primary-five-pending-codex-v2/`; manifest SHA-256 `a15c44c1b258f1255541a57bb46e3847682b6bfc4606d0e36e28973781094b9f`; identity proposals SHA-256 `822556916de7ede94919aafb961fa806c70708dae913c101121a70ac564d4e14`.
- v1 and v2 packets remain unchanged. v1 is 0 PASS / 180 HOLD; v2 is 1 PASS / 179 HOLD. The protected v3 packet is `~/.local/share/kifu-name-audit/2026-10-03/secondary-six-wikipedia-pending-luna-v3-2026-10-03/secondary-six-wikipedia.pending.jsonl`; directory mode `0700`, packet and manifest mode `0400`.
- v3 packet SHA-256 `2a9d730c0a23c95ace2dd669799922e1cdc2741b6a21ebd8aa587f4db70a37cf`; manifest SHA-256 `26533bf5f8af043206e307fa8c3ae272db375bff319a0e8fbdf40dd3ba988954`.

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

## PASS: rank 116, Ding Hao, French

The direct English article `https://en.wikipedia.org/wiki/Ding_Hao` links to `https://fr.wikipedia.org/wiki/Ding_Hao` with `hreflang="fr"`. Both article pages identify Wikidata entity `Q25252394`; the entity HTML at `https://www.wikidata.org/wiki/Q25252394` displays birth date 13 June 2000, matching the protected identity anchor DOB `2000-06-13` and GoRatings profile ID 1511. The French displayed H1/name is `Ding Hao`.

The PASS row records the French article URL, language, title, heading, revision ID `233421195`, fetch timestamp, and article HTML SHA-256 `46dc5d7d5c2c9a13c0ea0735e0e346ed931c6c3a414d234d993d35ce7c3811fd`. It also records the English linked page’s revision/body hash and the Wikidata entity body hash supporting the DOB match.

## Additional bounded discovery: rank 118, Kim Chae-young

A direct Korean Wikipedia search found `https://ko.wikipedia.org/wiki/김채영_(바둑_기사)`, H1 `김채영 (바둑 기사)`, revision `42581387`, HTML body SHA-256 `4c609657813f74af2a60001cd67c6ee03bab3141532d215ddc93a64a013ac7ff`. Its Wikidata entity is `Q22973181`; the linked entity page displays DOB 15 January 1996, matching official profile ID 1255 and anchor DOB `1996-01-15`. The discovery article exposed no interlanguage link to any of the six requested locales. All six requested cells therefore remain HOLD, with this identity evidence recorded; no absence claim is made.

## Remaining HOLDs

Bounded direct HTML searches were attempted on corresponding Wikipedia language sites for the other members of the first ten identities by occurrence count. Search misses, unrelated results, and one timeout were retained as HOLD; they do not establish article absence. The initial Wikidata API lookups also encountered HTTP 429. No transliteration was inferred, and no additional local Go source was consulted after the positive French match. Every unverified cell remains available for later authorized transliteration.

The packet provides source correspondence only. It does not approve raw scope, candidate applicability, name preimage, or database writes.
