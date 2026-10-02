# Judan v2 scope-hash correction (2026-10-03)

This correction supersedes the scope-hash table in [the prior pending evidence memo](kifu-name-judan-v2-bundle-semantic-evidence-pending-2026-10-03.md). Sol's independent HOLD identified that the earlier hashes were computed before the final evidence-rich review objects were installed.

I copied the pending evidence bundle and retained all 1,345 source records/bodies. For each exact raw-event group, I installed the final shared `identity_review` fields first (including its complete per-link CWI source checks, semantic record references, identity/period basis, truthful producer time and freeze time), then computed `identity_scope_sha256(bundle, group, owner)`. I recomputed each stored hash over the completed final bundle; all **18/18** now match. The 1,345 direct-path links remain in scope and all 39 held rows remain excluded.

| Raw event | Corrected pending scope SHA-256 |
|---|---|
| 1st Judan | `89d14b73b5d2a82f5cdfd02628575c2496d49e5f34857ccd1c81c4796ee80f2b` |
| 2nd Judan | `a64399d1a3b5e85384f0b38177f5b4538bf9e7ebcb2ade6a22928a1d92245e74` |
| 3rd Judan | `0d8e68126987c4f70dd969606ffb2e1b8c35a7396bcb7487426d5a2479602ef8` |
| 4th Judan | `3d6e1e9f90bac3227d0e7993d5d0426f4a64402d8bd2edb7e2a9655252293842` |
| 5th Judan | `432693ffeea36c5ed991f78fda658a7e346dbcbd53c3e5669099ce3e8a80a6d1` |
| 6th Judan | `188d1499670b1ed1dce829a838184948dcc6fc6abb513f89c0977813cd82f3c8` |
| 7th Judan | `5008e8e94344c36a5e290f5c18c1b9af18da22d9699311c9f2761765d48fd7fe` |
| 8th Judan | `b543cb2113ac6998f64eb8812213b972c2dd49231a1cc46fd14f8156e049f7a0` |
| 9th Judan | `8c40dc3494f65a118bf414b01ddb4b3a4da1811039c8eedd6961bead21b75c20` |
| 10th Judan | `c7c2b949415c6df0261b5e17b377ee50ff1baacd7f42643444abd3d67d4b1675` |
| 11th Judan | `fe82e9a33fc8058556a888fcb36acdade2457d6f081983b85fa69b66f29e8862` |
| 12th Judan | `e8317319cc5619d5efdc3cf3b28d5b07a1bd4a4687f96a141c294027ba9c9884` |
| 13th Judan | `38add60db8e37b225265ea1775fb39badd2c46c8541f51b20d609538045a0d42` |
| 14th Judan | `cef932b85b399ee415251da53be33ea64cd294c587a276284b09fa76a40b0fdf` |
| 15th Judan | `e33f09c1fabe429d3ba04f75606d206aeba01291a18c9cb57e04e85d337e1e69` |
| 16th Judan | `2486cbd1b9a016e5648063164c841114ad7a66a182f7c10a795fb2e830b8de08` |
| 17th Judan | `96220dfa2c6f90bebbecae55e14ccf37b5d25247b462e55e502637535a6d5f07` |
| 18th Judan | `ff332ebb1b6cc793302cce09f666deff3532d576ac1a3fe0b66fefbbad16ceac` |

The protected corrected bundle and the per-link CWI body hashes, excerpts, and Sol semantic-record references are in `/Users/fan/.local/share/kifu-name-audit/2026-10-03/judan-v2-bundle-semantic-reconciled-refrozen/` (directory mode `0700`, files `0600`). Bundle SHA-256: `598995d91221b0f8860699631695ebf2813c6df0d5d5922d3ae3bba748870f27`. Evidence manifest SHA-256: `c788f30d6fdddb1e8a1e97b9e4516ef6b345e9ab3c6409e5e393c7cda5652dd3`. The original CWI body manifest SHA-256 remains `c63fac6308b40e05b11d69e3c7d0d8a862903013599ff042eee1f1465febef2f`; all 1,345 body hashes still match their pinned archive-member hashes.

Validation with source registry `.5`, the pinned inventory, and the pending research JSONL returned `ready=false`, `write_ready=false`, exit 1 as expected for pending identity reviews/candidates. It reported no scope-hash errors. This is still an unsigned review draft: no identity or candidate signatures, event ID, database write, or addition of held rows.
