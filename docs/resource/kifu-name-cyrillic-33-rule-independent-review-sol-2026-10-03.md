# Independent review: Russian and Ukrainian 33-name rule packets

**Reviewer:** independent Sol agent, 2026-10-03 (Asia/Shanghai). **Decision scope:** the finite token maps and mechanically rendered display candidates inherited from 33 *pending* Pinyin readings. This review grants no source-anchor, reading segmentation, person identity, conventional-name, foreign-key, production-rule, or database approval.

## Recomputed scope and evidence

The two frozen input JSONL files hash to `9f63eec84481f317fe1b717b4ef88352e6c8ec75a0eb55c7e2dd49256dfb8a56` (20 records) and `7007d8f55683b7948afb51072fcc763b6df6c7bc8081dc9bfe2ec01ca39a9c29` (13 records). I read their `content.reading_words`, `content.original_name`, and `content.source_reading` directly. The combined IDs are unique; both rule packets have exactly the same 33 IDs and the same 60 distinct tokens. All candidate readings, Han names, and token groups match their input records. These inherited readings remain unsigned.

All retained candidate, input, and source files match the hashes in Luna's manifests. In particular, the [Russian Palladius table](https://cidian.ru/palladius) body is `942c4f4b633939c1da9facfd29c00cfe4e04a549410bd3833f5681ed92a9b6ab`; the [2019 Ukrainian academic system](https://chinese-studies.com.ua/pinyin_to_ukrainian_26.06.2019.pdf) PDF body is `6ac441c5784986b9c127d8db94f83010e49807c0a8f177a6b2fa73391283c0ab`; and the [alternate Ukrainian table](https://teahut-com-ua.github.io/library/articles/chinese-symbols-table/) body is `053ae02182b307dcd6421b1ba8538b61b2614c3375c0aebbb0117d557de3214ac`. The Ukrainian orthography and article captures also match their manifest hashes. I matched each of the 60 proposed entries against the retained body of its **chosen** table, then independently reconstructed every display from the inherited component boundaries. The complete per-token and per-display decisions are in the protected packet.

| Language | Rule token decisions | Display decisions | Mechanical and collision check |
|---|---:|---:|---|
| Russian | 59 pass; `hui` hold | 32 rule-only pass; 宋容慧 hold | 32 exact renders; 32 unique |
| Ukrainian | 59 pass against chosen academic table; `jun` hold | 32 rule-only pass; 邱峻 hold | 33 exact proposed renders; 33 unique, including the held proposal |

### Russian

The Palladius table supports all unheld token values. Its `hui — хуэй (хой)` entry gives two forms without a selector; **宋容慧 / Song Ronghui remains held**, with no Russian display signed. The other 32 proposals reproduce the rule exactly, but are approved here only as outputs of this scoped rule, not as established personal names.

The retained [GoLib “Who Is Who / World”](https://rusgolib.gofederation.ru/KtoEst%27Kto/Mir.html) *web-index excerpt* pairs `Цю Цзюнь (Qiu Jun)` and `Пэн Цюань (Peng Quan)`. Its hash `cc6becaa3022ad736050e0508a901574e19572c20698143671ef3ee6f042a1b3` is the **excerpt hash, not a raw page-body hash**. The page body was not retained. Those two rule outputs match indexed spellings, but this review does not sign body-verified conventional-name evidence or apply any conventional-name override. The other 30 passed strings have no conventional-name finding from this bounded review.

### Ukrainian

The 2019 academic PDF states that surname and given name are written separately, in surname-first order, and gives the proposed syllable entries. The 33 proposed displays mechanically match that selected system. The separate [Ча Дао table](https://teahut-com-ua.github.io/library/articles/chinese-symbols-table/) has `jun → дзюнь`, while the academic PDF has `jun → цзюнь`. **邱峻 / Qiu Jun remains held** pending an explicit choice of Ukrainian system or person-specific conventional form; `Цю Цзюнь` is recorded as the exact academic-system proposal, not a signed display. Other systems also differ on some syllables, so the 32 passes are conditional on the single selected academic table and cannot be mixed with alternate-system spellings. No Ukrainian conventional player form is approved by this review.

## Protected reviewed packet

`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/cyrillic-33-rule-independent-review-sol/` (directory mode `0700`, files `0600`) contains `ru.reviewed.json`, `uk.reviewed.json`, and `manifest.json`. The review-file SHA-256 values are `1e3c39e6f75159b75464170d7a4fc88a3e3ce97ccb5978dbc97f3b4e7d60d27b` and `fca30154b873a2010b9634051748aae9a7f5a76178aa78cea36c833546b991a1`, respectively. The packet records each of the 33 name decisions and each of the 60 token decisions per language. No code or database write was made.
