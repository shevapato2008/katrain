# Correction to ranks 101–150 independent source review

Correction issued 2026-10-03. This addendum preserves the historical [independent review](kifu-name-player-ranks101-150-independent-review-sol-2026-10-03.md), SHA-256 `d44776f45ce99049a8f6415d765db481f1abaf77cc6c85f4504906cb170aabc5`, without rewriting it.

The review's per-language PASS sequence says **29 / 2 / 21 / 30 / 30**. Its `cn 29` entry is an arithmetic/transcription error. Independently recounting every row in `~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-source-luna/primary-language-cells-all250.pending.jsonl`, SHA-256 `02b05e101ab6c6b5da2afb7692609479694cfd2a0a14663b892da8d05831f48c`, gives:

| Language | PASS | HOLD | EXCLUDED_APPROVED | PASS raw occurrences |
| --- | ---: | ---: | ---: | ---: |
| cn | **26** | 23 | 1 | 14,430 |
| tw | 2 | 47 | 1 | 1,003 |
| jp | 21 | 28 | 1 | 11,447 |
| ko | 30 | 19 | 1 | 16,551 |
| en | 30 | 19 | 1 | 16,551 |
| **Total** | **109** | **136** | **5** | — |

The [producer pending memo](kifu-name-player-ranks101-150-primary-five-producer-pending-codex-2026-10-03.md), SHA-256 `a1093b1791c20cecba25df1d727cda9dd2dd5f11043be48651dffdde029b324d`, already states the corrected `cn 26` count and flags the earlier typo. Its protected `all250-status.pending.jsonl` (SHA-256 `a6c62e53fb8e7ec4084d7a4ee03ad5d7074da1c763d94292f64efcdacb7ba037`) matches the upstream 250 statuses row for row. Its 109 `primary-five-candidates.pending.jsonl` rows (SHA-256 `d7d4a58729d05da779bf58301738542791cdc2c4987baad88c0f111f05ab3623`) have exactly the same rank/language keys as the upstream PASS cells, including **26 cn** candidates. No source decision, candidate display, or occurrence sum changes because of this correction.

The producer packet and this correction remain pending evidence only. No database or application code change, candidate approval, or commit was made in this correction pass.
