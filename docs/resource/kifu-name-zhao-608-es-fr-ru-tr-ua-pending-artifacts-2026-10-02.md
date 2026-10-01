# Zhao/Cho Chikun ES, FR, RU, TR, UA pending artifacts

> **Supersession notice (2026-10-02):** The initial JSONL artifacts and hashes in the original memo body below were rejected because several excerpts were not literal contiguous source text. They are preserved in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/zhao-chikun-secondary-rejected-20261001T223805Z/` as mode-`0600` files. Use only the corrected JSONLs and hashes in the addendum at the end of this memo.

Prepared research-only records for production-bound player ID `608` using registry `2026-10-02.3`, canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. These proposals follow the source-level decisions in the referenced review memos. Every candidate remains `pending`; none approves a database value, alias, or raw-slot identity.

## Controlled artifacts and validation

Under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/`:

- `zhao-chikun-es-fr-ru-tr-ua-pending-research.jsonl`: mode `0600`, SHA-256 `cb857d58c0090c2db085b484ebf4276292ed2387a2fc7bd004b0cf4fc783a232`.
- `zhao-chikun-es-fr-ru-tr-ua-pending-candidates.jsonl`: mode `0600`, SHA-256 `8cbe1e2c96fd9b0276bdc04708c686c53408c95c8b022b43f6b5356fd130c86f`.

All five research records pass `validate_research_record` with the pinned `.3` registry. Each pending candidate's `research_sha256` matches its canonical record:

| Language | Pending display proposal | Research SHA-256 | Attested alternatives retained in research metadata |
|---|---|---|---|
| `es` | `Cho Chikun` | `c12efcfa461a481ca45af1b36e241930d7408370df463eeb8280f355c892a8f4` | `Cho Chihun` |
| `fr` | `Cho Chikun` | `dcf7390b7bcd7dcfb35270cdfa2b614f9548b7cdbf2eece73a56e4038c0f54fa` | FFG's `CHO Chikun`; Wikipedia's `Cho Chihun` |
| `ru` | `Тё Тикун` | `401e6424de78e3d68c2118e77be6e0d0f8eae252515d47179a4a62b42bda4c55` | `Чо Чикун` |
| `tr` | `Cho Chikun` | `96e08ca40577db34d5d1ce80f4e9c7e8bff462d25ba4aa12c1a382936520df31` | — |
| `ua` | `Чо Чікун` | `392c991fdbc40833d7bec76f4083d300af692a7cd37b77bbd5d4c8797602ba94` | `Cho Chikun`; inflected `Чо Чікуна` |

The selected evidence and all retained variant-note body hashes were checked against the controlled raw captures. Source anchors are: revisioned Spanish Wikipedia (revision `174242434`); French Wikipedia (`239830835`) plus Fédération Française de Go; Russian Go Federation GoLibrary plus GoMagic; Istanbul Go School plus Turkish Wikipedia revision `24969706`; and UFGO Ukrainian posts/reports. The Spanish, French, Russian, and Ukrainian variant conflicts remain explicit in `source_variant_notes`; the Russian record also retains the GoLibrary Seoul versus Nihon Ki-in Busan birthplace discrepancy and excludes birthplace from identity matching. The source-level editorial decisions are linked in each record to their Spanish, `de/fr/ru`, Turkish/Ukrainian, or Ukrainian Astra review memo. They are not alias approvals.

## Candidate gate and limits

Each `validate_candidate` call against the pinned production snapshot `kifu-name-inventory-prod-v2-20261002.json.gz` returned only `entity ID/ref absent from pinned inventory and approved links`. The snapshot derives player presence from album associations, so this reports no matching ID 608 association in that snapshot; it does not say the production player entity is missing. An in-memory-only structural probe adding an ID 608 association allowed all five candidates to validate, confirming the stored candidate/research structures have no additional validation error. No snapshot, candidate, preimage, album link, or database was modified.

These are language-name proposals only. No candidate is approved, no alias is authorized, and the 2,052 raw `赵治勋` slots still need their own identity review and game-context associations.

## Superseding excerpt-correction addendum

The corrected controlled JSONLs are mode `0600`:

- Research: `zhao-chikun-es-fr-ru-tr-ua-pending-research.jsonl`, SHA-256 `9d64c1614cc971a97a47fe62d98639bf63ab0b9bc8e493b6dc5cb0e1c622aa0d`.
- Candidates: `zhao-chikun-es-fr-ru-tr-ua-pending-candidates.jsonl`, SHA-256 `49b194d149c10c2398fc01584905c1b301201c85bd49221d33133fe43a174e23`.

All `body_excerpt` values in the five selected source checks and seven retained variant notes now match contiguous visible-text passages from their corresponding hash-bound response bodies. All five `article_evidence.passage` values also match the captured visible text; the French article passage was already literal, and its oversized stitched `body_excerpt` was replaced by the exact passage. The original-name and reading evidence excerpts were rechecked and remain literal. Response hashes, timestamps, and captured bodies were not changed. All five corrected records pass `validate_research_record` against registry `.3`; candidate research hashes match these canonical record hashes:

| Language | Candidate | Canonical research SHA-256 |
|---|---|---|
| `es` | `Cho Chikun` | `ac6d0c3a251709fb8a1f3f3ec173216978798f41bafe92de53f6b5f6648f1c14` |
| `fr` | `Cho Chikun` | `8bf551416b51b96ca0fd49ce3fb96968b9e1c4692a58e307808d90602e6d0b79` |
| `ru` | `Тё Тикун` | `925990730197b832f748bcdfbc158d449cacea724c7f5be1c0e83089fb009431` |
| `tr` | `Cho Chikun` | `e2b75a5eaed01f1948a690f8ef232bfe7c2c18cdc2703e1a99532c4126482c0d` |
| `ua` | `Чо Чікун` | `ac7dd84d8a6014a3b8e24569ccee00e6cccc133697d18e4201025986020e8592` |

Every corrected candidate still fails the pinned production inventory check only with `entity ID/ref absent from pinned inventory and approved links`; the in-memory-only structural probe passes. Candidate status remains pending. This addendum supersedes the initial hashes, without changing the language decisions or treating them as approval.
