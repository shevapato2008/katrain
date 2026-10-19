# First-time five-value name research pilot

Read-only timed pilot, 2026-10-04 UTC. This run used three newly preprocessed, identity-confirmed PROD IDs from the safe6 batch: `4112` 吉原由香里, `4344` 冈田结美子, and `586` 村松大樹. The PROD snapshot showed zero existing `kifu_player_names` rows with `verified_at` set: IDs 4112 and 4344 had no name rows; ID 586 had five legacy rows, all `status=review`, `verified_at=null`. Snapshot SHA-256: `0a6f05b99a922ae5b14eb4e30860b0a5459ddbb80a1df2e12c759ab2b99e54c6`.

## Bundles

| ID | Raw / identity | cn | tw | jp | ko | en |
|---:|---|---|---|---|---|---|
| 4112 | 吉原由香里 | 吉原由香里 | 吉原由香里 | 吉原 由香里 | 요시하라 유카리 | Yukari Yoshihara |
| 4344 | 冈田结美子 | **missing** | **missing** | 岡田 結美子 | **missing** | Yumiko Okada |
| 586 | 村松大树 | **missing** | **missing** | 村松 大樹 | **missing** | Hiroki Muramatsu |

Sources and confidence are in the JSON artifact. Missing values are deliberate: the bounded pass did not find a target-language source, and existing legacy unverified rows were not promoted to evidence.

## Timing

Timer started before the first external search: `2026-10-04T12:11:07.855Z`. Final bundle ended at `2026-10-04T12:12:58.337Z`. Wall elapsed time was **110.482 s**, or **36.827 s per player**. This includes source lookup, reading and comparison, normalization, and bundle assembly, and excludes database import.

Measured web/command tool latency totaled **25.313 s**. The remaining **85.169 s** is a residual for reading, reasoning, normalization decisions, and orchestration; it is not a direct keystroke-only typing measurement. Per-player direct lookup tool latency was:

| Player | Tool lookup latency | Rank |
|---|---:|---:|
| 吉原由香里 (4112) | 2.272 s | fastest |
| 冈田结美子 (4344) | 10.214 s | slowest |
| 村松大树 (586) | 3.316 s | middle |

Tool latency median was **3.316 s** and range **2.272–10.214 s**. The honest wall-time projection is **36.827 s/name** for this run; because all three names are Japanese professionals, the sample is biased toward Japanese official and Wikipedia coverage and likely understates mixed-origin work. Two of three bundles were partial, so a production-quality five-cell pass would likely take longer.

No person identity was ambiguous. Missing cells remain missing and no transliterations were fabricated.
