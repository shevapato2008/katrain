# Honinbo edition rules: corrected producer packet v2

This new packet corrects only provenance and hash boundaries from Luna's earlier proposal. Its five display patterns and 1/17/34 examples are unchanged. Astra's content review was PASS, but this producer packet remains **pending independent review**; it is not signed and does not authorize candidate generation or import.

## Corrected records

- `tw` now uses the retained Haifong Go Institute article in Traditional Chinese, which directly writes `第55、56期本因坊戰`. The packet records `zh-Hant`, the `lang="zh-tw"` and excerpt basis, URL, capture time, excerpt and body hash. It does not claim that the article attests every edition from 1–34.
- `es` now quotes the retained FundéuRAE body exactly at the corrected phrase: `con el sustantivo al que acompañan`. The display pattern remains `N.ª edición del Torneo Hon'inbō`.
- Each rule now has an explicit immutable `content` object and a separate `approval` object. `rule_content_sha256` is SHA-256 of UTF-8 canonical JSON for `content` only (`ensure_ascii=false`, sorted keys, compact separators). Status, reviewer identity/model, review time and conclusion are outside the hashed object. All five approval statuses remain `pending_independent_review`, with reviewer fields null.

| Locale | Pattern (unchanged) | Immutable content SHA-256 |
|---|---|---|
| `tw` | `第N期本因坊戰` | `5c924f2f7a2e514f516a78f492063b1bbf1aecf278379500d8a74f255d97d21e` |
| `ko` | `제N기 본인방전` | `636d521866295ea5de14adb513d308419914fbd477acb06c944695304bc19a66` |
| `es` | `N.ª edición del Torneo Hon'inbō` | `085cf47a478941de3233d5eac4dadfc5914d3eb71281c10cce5ee03061b95572` |
| `fr` | `1re édition du Tournoi Hon'inbō`; `2e–34e édition du Tournoi Hon'inbō` | `e0600dc2c46fc0ad5ca22794db68e6eeb9fcaac39431f8770300083ee20a8282` |
| `tr` | `N. Honinbo Turnuvası` | `89323928a52dafca5d6caaaba069249e98f7236df8248e9a3b070c85d10e7416` |

## Packet hashes and retention

The corrected packet is stored separately at `~/.local/share/kifu-name-audit/2026-10-03/honinbo-composition-grammar-luna-v2/` (directory mode `0700`, files mode `0600`). It contains verbatim retained source-body copies, `source-manifest-v2.json`, `rule-proposals-v2.pending.json`, and `packet-manifest.json`.

- Haifong source body SHA-256: `333fee0d9fd15b5112ddc3e5a3961dd253d879d9bd302972d98e0e44f3cf4801`; captured `2026-10-02T16:48:29.013798+00:00`; `27,295` bytes.
- Corrected source manifest canonical SHA-256: `ab042914dd36c28f716e3ca769f05c7e2e2595c3e26aef24d2530857d0c02e61`.
- `source-manifest-v2.json` byte SHA-256: `c886b8610da1d42eadcbb30861f791cae6d508c5c9e1550705755114f426b937`.
- `rule-proposals-v2.pending.json` byte SHA-256: `515138614af4b778735cfd9bcae45927a7794ab0cd3fbaa243f17a4e7866382c`.
- `packet-manifest.json` byte SHA-256: `7b40ea5d45c675c287c1f12be35a9c768de43822bd195aa916aac196d21a3ac3`.
- The packet remains bound to the approved base-candidate file SHA-256 `ec2ba3cde0405df692e1d400c0fc324e63bd4befe60c44acecc44caaace86bfe`; each locale's exact base-line hash remains in its immutable content object.

The prior Luna source bodies, source manifest, rule proposal, memo and hashes are preserved unchanged. No code, database, candidate, approval signature or production record was changed.
