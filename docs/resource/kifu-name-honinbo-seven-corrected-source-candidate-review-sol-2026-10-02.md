# Honinbo seven corrected source candidates: independent review (2026-10-02)

**PASS at source-candidate level** for exactly `en cn tw de es tr ua`. I signed a new seven-row copy as `/root/honinbo_name_preimage_binder_sol`, parent-configured `gpt-6-sol` / high (the runtime did not independently expose a model identifier), at `2026-10-02T15:15:56.944223+00:00`. The correcting producer is `/root/honinbo_research_correction_luna`, configured `gpt-6-luna` / high; our identities differ. This approval covers the witnessed display forms and their corrected source records. It does not bind a fresh name preimage, approve a final import candidate, or write to the database.

## Correction and source checks

I compared each corrected research and candidate row against its original pending row and the protected `provenance.json`. For English, the research row changes only producer ID/time and `source_checks[0].language_basis` from `html_lang` to `reviewed_text`. The retained CWI HTML has a bare `<html>` without `lang`; its English body says it gives Honinbo title games, so the new basis is truthful. For the other six research rows, only producer ID/time change. Each corrected candidate changes only producer ID/time and its exact revised `research_sha256`. The original capture URLs, fetched times, body hashes, excerpts, original Japanese event identity, exact display strings, and `name_preimage_sha256: null` remain unchanged.

The seven corrected research `produced_at` values are actual per-row timestamps around `15:08:56.531Z`; each follows its source capture and, for `cn tw de es tr ua`, the nested Nihon Ki-in identity capture at `13:45:25.506630Z`. Each candidate production time follows its corrected research time, and my review follows all seven candidate times. The provenance file's singular `research_production_time_utc` equals the English row time; the other six exact production times are in their research rows and were checked individually.

I recomputed all 12 retained response lengths and byte SHA-256 values against `capture-manifest.json`. For each corrected row, I verified the recorded target-language excerpt against rendered text from its actual retained body, its requested URL, fetch time and body hash, and the exact candidate string within the passage. The six Wikipedia bodies have the claimed `html lang` values. Their nested identity excerpt appears in the separately captured Nihon Ki-in body. The English body has no HTML language attribute and its English text supports `reviewed_text`. The strings identify the Japanese professional Honinbo event, with these qualifications preserved: Turkish `Honinbo Turnuvası` is observed in a school article, and Ukrainian `Турнір на звання Хон'імбо` is observed in an uncited article. Neither establishes federation endorsement or dominant local usage. The four unaffected `jp ko fr ru` rows were not revised or re-signed here.

All seven corrected research records passed `validate_research_record` against registry `.5` (canonical SHA-256 `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`). All seven pending candidates, then all seven signed copies, passed `_validate_candidate` against their matching revised research rows and the finite symbolic owner target `event:@honinbo-series-2026-10-02`. That focused target input checks candidate/research consistency; it is not a production import check. The correcting producer's provenance file pins each old/new research and candidate hash; the new review manifest pins each corrected and signed candidate row hash.

## Protected outputs

The new directory `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-source-correction-review-sol/` has mode `0700`; its files have mode `0600`.

| Artifact | Byte SHA-256 |
|---|---|
| Corrected pending research input | `c33278ed5049aa56f7dd25115b1039e4bb74e7dd967d3c0b011bb5e1ceb5fd86` |
| Corrected pending candidate input | `192aefe74876327f55a81c1736d848860625d650e2a63977686d266ffe8b8c12` |
| `honinbo-series-2026-10-02-candidates-correction.source-reviewed.jsonl` | `b2a3f471ad03730df8145157469d4e74c8c9af147e92a5a3d7a5e83c0e71ee8c` |
| `source-review-manifest.json` | `685ce5befb5bf87bd01b932ff188a5ccc0c2a6f965937a1d564f917119f5c7fe` |

The revised research rows remain `pending`. The seven signed candidate rows have no `preimage_binding`; historical null values alone do not review a later production capture. A separate binder must issue new pending copies referencing these newly signed source-row hashes, followed by an independent final candidate reviewer. The existing four source-reviewed rows and the independently signed 1,617 identity links remain separate and unchanged. No original candidate, database, SGF, or prior signed artifact was modified.
