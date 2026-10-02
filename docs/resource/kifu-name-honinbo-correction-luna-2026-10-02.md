# Honinbo corrected pending research revision — 2026-10-02

Created a new protected revision for exactly `en`, `cn`, `tw`, `de`, `es`, `tr`, and `ua`. The original protected inputs and the four unaffected research/candidate rows were left unchanged. No source pages were recaptured and no source facts were added.

Producer: `/root/honinbo_research_correction_luna`; configured model/reasoning: `gpt-6-luna` / `high`. Research production time: `2026-10-02T15:08:56.531158Z`. Each candidate has its own recorded current production time in the protected provenance record; all follow research production and the nested Nihon Ki-in capture at `2026-10-02T13:45:25.506630Z`. The six chronology rows receive new actual production timestamps. The English record is also newly produced with the language basis corrected from `html_lang` to `reviewed_text`, because the retained CWI `<html>` has no `lang` attribute and its English title/body were reviewed.

## Protected outputs and hashes

All files are in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-research-correction-luna/` with directory mode `0700` and file mode `0600`.

- `honinbo-series-2026-10-02-research-correction.pending.jsonl` — SHA-256 `c33278ed5049aa56f7dd25115b1039e4bb74e7dd967d3c0b011bb5e1ceb5fd86`.
- `honinbo-series-2026-10-02-candidates-correction.pending.jsonl` — SHA-256 `192aefe74876327f55a81c1736d848860625d650e2a63977686d266ffe8b8c12`.
- `provenance.json` retains source file names, actual fetch timestamps, response hashes and byte counts, exact source excerpts, old/new per-row hashes, and production timestamps.

| Lang | Original research row SHA-256 | New research row SHA-256 (candidate binding) | Original candidate row SHA-256 | New candidate row SHA-256 |
| --- | --- | --- | --- | --- |
| `en` | `ac03e34c0e16b137fae06038c224e93b8a7944f5b4518e092f0760a764f68f30` | `52337d32ee693376d9cf50de9beeb0eea6f97ce07a09e783f82fd787e0600634` | `0eca7fcb385291197334c314240c63360e1458861e0a49c70d083d2eadd0a90f` | `1657dae7eb550ac4dc4fd5cf5b292986aa2b2582152ce7d1e2a9e248afea5180` |
| `cn` | `b002d022603f4f828155ee12752eb88ef853e41c062096c30d7a656ad10deec3` | `1bad4ec1f51c84ef943591abb1935ee99b683142f640eda75495f50349cf92bc` | `92b550899dc3c8a5327952deca3a69f4c5628faa5e05144fb69a7e8fc9096e29` | `53ce964cabe806c7811ff08a28cf72036d757415323dbefd0f0794d4349077d8` |
| `tw` | `93c8ec7475e8e6c43eade0e2b2c7062bcf84ec451f0c9ea803530fd629969de5` | `822fa6b8ba37a2318dbd3a016c01b54f8b7f3e15a0700833b2ce4b01b4f7c517` | `8af2fa58d089f06030bcddfd651bb153b3c061ac94b2170b0a02071a4cb50a8f` | `73ffefc165a8f9af55e7205cbc2c7cff6fa7da54db67e43af4021558a604d9e8` |
| `de` | `af8730e258fab3def6cab58293a5586300dd2bd5fe34320cee9074e1ee344a5d` | `4717e4e9416c35f36639b6548686e101724a04bcb86e94cf02f057fcfc2a2f3a` | `181b2ba7af3c41451ee580a46f514d32188e2f9bed1287f59f9e023206f2f2e2` | `17d688d4051294f7f068714e34c5c4a19ed348e8aa2572783c5ecd0d65e91aeb` |
| `es` | `2ca7fb0e0d594937f231e5f296380e8cff400bd63d269e80957060ff447c76a4` | `e0b2b219bd1096230450dc0248f63c0631627a818665a4265df695bcb2807f6f` | `2681d2f26852140d048bdf8963f6a0f2969db8e3e38ab2b880aa923561dfd9ea` | `3669ae1baa0cbf6d7d1bb8ddd4c685477d585d8c2c6febee86f2a7a12e9d823c` |
| `tr` | `cb0797a8e5e358d80d6831c001867489086759d4573d799b1c64a301213a780a` | `ad2b974ab85268fd57c99d256f23b04ee085d50cd2e4259f2bccdbf0f42e7b30` | `fa3fdc112372823f7b250e6b2a0ccb857ce35e8bf8b2b254f1dd7f4a55490c47` | `6b2053556d50ce0d60bbae9203539619bcea97aad4a513e18887687cb51cb1ff` |
| `ua` | `7439b086543da2d7c690cfdb0ad7535de975ce9b2ff3701a2d56251da798b40a` | `f3beda9eb9975f211bd62ddd4db3ebd722209670c24c22e3371bb34fb6d623cb` | `7f0cdd95c0627440759e1f50e16a2d182187f2e17f5e73738619e589bae32e2b` | `e1ee60653a917b28360273911da2b84439c02b83252563c210aa710cbf45c78b` |

## Checks and limits

- Recomputed byte count and SHA-256 for all 12 retained response bodies; each matches `capture-manifest.json`. Source excerpts and their original `fetched_at` values are carried forward. The English CWI check changes only `language_basis` to `reviewed_text`.
- `validate_research_record` passed for all seven rows against registry `2026-10-02.5` (canonical SHA-256 `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`).
- `_validate_candidate` passed for all seven pending conventional candidates with exact revised research hashes. For this structural validation only, the symbolic event owner token was supplied as an in-memory link target. This does not establish production inventory membership, an approved event identity link, or import readiness.
- The candidate and research records remain pending. No independent re-review, preimage binding, signature, signed artifact change, or database write is included. Turkish and Ukrainian qualifications and all prior source limitations remain in effect.
- The four unaffected languages (`jp`, `ko`, `fr`, `ru`) are intentionally absent from this correction set and remain under their original rows/hashes.

No commit was made.
