# Judan ten-language pending candidates (2026-10-02)

This artifact contains ten unsigned `conventional` candidates for `event:@judan-series-2026-10-02`. The nine non-English rows use the matching source-producer research rows from `judan-ten-controlled/research.pending.jsonl`; English uses the corrected `Judan` row from `judan-ten-en-repair/research.pending.jsonl`. The old English `Judan Title` research is excluded. The separately source-reviewed Ukrainian candidate and its artifacts were left unchanged and are not reauthored here.

Each `research_sha256` is the canonical JSON SHA-256 of the exact bound research row. All candidates have producer `/root/judan_ten_controlled_research_luna`, model `gpt-6-luna`, and truthful candidate production time `2026-10-02T15:13:59.228801+00:00`. The owner is the existing symbolic reference `event:@judan-series-2026-10-02`; this does not assign or assert a database event ID.

| Language | Display | Bound research SHA-256 |
|---|---|---|
| `en` | `Judan` | `102417843e8965f899331ac9c7da48670c6939b8842426de2035a578a47e96f4` |
| `cn` | `十段战` | `cb71b386cf3b71d941f5f67d3d97b9160f808cd370d76d802b15a82da7e41acb` |
| `tw` | `十段戰` | `94433b4fdb842152164c68090709eb4218c885678b3ef2a07aafb498554fed13` |
| `jp` | `十段戦` | `3eb2806e621134477b7d3062c37ecf83d43854b6acf114f0ab42aece84a7be34` |
| `ko` | `일본십단전` | `33598ce8c2e0cbd25299c6d32b37e0d4550be00a06697e3cab47a51faa6364a2` |
| `de` | `Judan-Turnier` | `c4756ba68bef63b06130dcb0cdcd88a8174f94385aefc3ece4167f609f714107` |
| `es` | `Judan` | `f420b09cfd3b9025ec74ef224955b323f8f9e14f2e805e00ec5034e80f8d9e96` |
| `fr` | `Judan` | `2208b8d00c40b331c03ce7bf3fb65868ac75e9bb87815d9334a969c6f8430f3a` |
| `ru` | `Дзюдан` | `d8af04d8e3a86baf7d548ffbb2ce04db659075c197fcb32afc1fc834633e6f8c` |
| `tr` | `Judan` | `aa531cbd1c7507c143f7c50a9e5525ece3ed8bd309fd74834c73a74a99593d59` |

## Protected artifact and validation

Files are under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-ten-candidates-source-producer/` (directory mode `0700`, files mode `0600`). Registry `.5` canonical SHA-256 is `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`.

- `candidate.pending.jsonl` SHA-256: `9e7f234115d8cbf21b6c3e73ba00583172d3b58d8c3077e5285973f0e3b42050`
- `field-validation.json` SHA-256: `3e16741f2659bbe50d026f1f405137c5063ab94a56bfe13cb9f86fbfefb39d62`

Field validation passed for all ten rows using `_validate_candidate` against the exact canonical research row. Its temporary `link_targets` contains only `event:@judan-series-2026-10-02`; an empty inventory fixture was used solely to exercise candidate fields and symbolic owner matching. This is not a production inventory, bundle readiness check, approved identity link, eleven-language completeness decision, preimage binding, or write authorization. Every row remains `pending`, with no reviewer fields or signature. No database write or commit was made.
