# Zhao/Cho Chikun ES, FR, RU, TR, UA pending artifacts

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
