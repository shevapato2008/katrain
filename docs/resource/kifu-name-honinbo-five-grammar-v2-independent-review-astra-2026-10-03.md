# Honinbo five edition rules v2: independent correction review

**PASS — `tw ko es fr tr`, language content and composition-rule eligibility for editions 1–34.** All three requested corrections are complete; no blocking defect was found. This independent approval signs the five exact immutable content hashes below. It does not approve the 374 raw-event candidates, an implementation schema, an import bundle or database writes.

Reviewer: `/root/oza_ua_display_decision_astra`, parent-configured `gpt-6-astra` / max, without runtime attestation. Reviewed at **2026-10-02T17:30:10Z** (2026-10-03 locally). Producer `/root/honinbo_grammar_luna` is a different agent. Scope is the corrections to the [previous content review](kifu-name-honinbo-seven-grammar-content-review-astra-2026-10-03.md), using the [v2 producer memo](kifu-name-honinbo-composition-rule-research-luna-v2-2026-10-03.md) and its retained packet.

## Verified corrections

1. **TW source: PASS.** The retained [Haifong Go Institute article](https://www.haifong.org/news/content/ABC908ABE427697ABC7F960615286E8C) declares `lang="zh-tw"`; its visible Traditional Chinese body describes 王銘琬 with `第55、56期本因坊戰` and Japanese professional context. The exact stored excerpt occurs in the body. The 27,295 bytes hash to `333fee0d9fd15b5112ddc3e5a3961dd253d879d9bd302972d98e0e44f3cf4801`, matching both source records. This supports the unit/order and Traditional Chinese base; individual editions 1–34 remain reviewed compositions.
2. **ES excerpt: PASS.** The corrected excerpt, including `con el sustantivo al que acompañan`, matches the retained [FundéuRAE body](https://www.fundeu.es/recomendacion/numero-ordinales-claves-de-escritura/) after HTML removal and whitespace normalization. Body SHA-256 remains `51c54320c33b508eb2aeffc3bb65ef50eef02c7bab63236334e7d8ad6ff43b44`. Both the manifest and rule source carry the corrected excerpt.
3. **Hash boundaries and bindings: PASS.** Each `rule_content_sha256` equals SHA-256 of `content` alone, encoded as UTF-8 JSON with `ensure_ascii=false`, sorted keys and compact separators. Approval/status/reviewer fields are outside that object; changing the approval envelope in memory leaves the content hash unchanged. All five rule-source objects equal their manifest entries. All five body byte lengths/hashes, manifest canonical/file hashes, proposal file hash, packet references and approved-base file/line hashes were independently recomputed successfully. Base-line hashing includes the trailing LF. Captures precede production, which precedes this review.

The five display instructions, approved bases, 1/17/34 examples and series references are unchanged from v1. Independent expansion of **5 × 34 = 170** labels preserves every output, spacing and suffix, with no duplicate per language. French uses `1re` and `2e … 34e`; Spanish retains feminine `ª`. The Korean, Spanish, French and Turkish source bodies remain byte-identical to v1. The previous review's source limitations and catalog capitalization choices continue to apply.

## Signed content scope

| Locale | Approved pattern | Immutable content SHA-256 |
| --- | --- | --- |
| `tw` | `第N期本因坊戰` | `5c924f2f7a2e514f516a78f492063b1bbf1aecf278379500d8a74f255d97d21e` |
| `ko` | `제N기 본인방전` | `636d521866295ea5de14adb513d308419914fbd477acb06c944695304bc19a66` |
| `es` | `N.ª edición del Torneo Hon'inbō` | `085cf47a478941de3233d5eac4dadfc5914d3eb71281c10cce5ee03061b95572` |
| `fr` | `1re édition du Tournoi Hon'inbō`; otherwise `Ne édition du Tournoi Hon'inbō` | `e0600dc2c46fc0ad5ca22794db68e6eeb9fcaac39431f8770300083ee20a8282` |
| `tr` | `N. Honinbo Turnuvası` | `89323928a52dafca5d6caaaba069249e98f7236df8248e9a3b070c85d10e7416` |

`N` is an Arabic integer from 1 through 34; labels stand alone. Approval is bound to these content hashes, not merely the reused `proposal_id` values.

Packet directory: `~/.local/share/kifu-name-audit/2026-10-03/honinbo-composition-grammar-luna-v2/`.

| Input | Recomputed byte SHA-256 |
| --- | --- |
| `packet-manifest.json` | `7b40ea5d45c675c287c1f12be35a9c768de43822bd195aa916aac196d21a3ac3` |
| `source-manifest-v2.json` | `c886b8610da1d42eadcbb30861f791cae6d508c5c9e1550705755114f426b937` |
| `rule-proposals-v2.pending.json` | `515138614af4b778735cfd9bcae45927a7794ab0cd3fbaa243f17a4e7866382c` |

Source-manifest canonical SHA-256: `ab042914dd36c28f716e3ca769f05c7e2e2595c3e26aef24d2530857d0c02e61`. Approved-base JSONL byte SHA-256: `ec2ba3cde0405df692e1d400c0fc324e63bd4befe60c44acecc44caaace86bfe`. The independently expanded `{locale: {edition: display}}` map has canonical SHA-256 `45f825b2fc373a4cc6f2bdbfda4ff59b805b3e9b03820db6005beb38ffd798f7`.

This memo records the approval separately; the producer's pending envelopes and all existing artifacts remain unchanged. The old manifest/proposal hashes still match the previous review. No code or database was changed. Full eleven-language candidate binding and coverage gates remain in force.
