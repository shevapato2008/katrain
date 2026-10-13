# Judan direct-path v2 evidence draft (2026-10-03)

Prepared a new unsigned, read-only `bundle_format=2` copy for symbolic event `judan-series-2026-10-02`, canonical `十段戦`. It contains exactly the 1,345 direct numbered archive associations from the reviewed scope, 11 pending language candidates, and excludes all 39 held rows. It adds no identity or candidate signatures, preimage bindings, event ID, or database writes.

## Per-link evidence

Captured actual HTTP 200 SGF response bodies from the direct CWI URL for all 1,345 archive members. Each retained response body is under `/Users/fan/.local/share/kifu-name-audit/2026-10-03/judan-v2-bundle-semantic-reconciled/cwi-bodies/`, with a per-link URL, fetch time, byte count, body SHA-256, and file path in the protected capture manifest. All 1,345 response-body hashes equal their pinned archive-member hashes. The bundle includes each exact SGF root excerpt and its source hash.

Each CWI source check also points to that album's canonical record hash in Sol's `per-link-reconciliation.jsonl` (file SHA-256 `941adcb87b575d938c090ae55f9a4ac928c522527d8226db733ad23a584b2688`). The record set reports 1,345/1,345 passes for source path, pinned archive member, whitespace-only normalization, parser serialization, full tree, mainline, named root properties, and production-column comparisons; the exception list is empty. Each raw-value review also carries the retained official Japanese Nihon Ki-in identity source body (SHA-256 `34f445edeaedfc6825d6b56bf077883dcfcfc34c7d308e054848f45099c5caee`).

The v2 validator requires the entire `identity_review` object to be identical across links in a target/raw-value group. Each pending review therefore contains that group's full list of individual CWI body/hash and semantic-record references, shared by every link in that group. The protected `cwi-direct-source-body-manifest.jsonl` contains each album ID, direct source URL, response-body SHA-256, pinned archive-member SHA-256, and fetch time; the bundle and protected manifest contain these 18 scope hashes:

| Raw event | Pending scope SHA-256 |
|---|---|
| 1st Judan | `d144ce585e2ce74e4702b778c44f17d0dff395adba1e2ed370e1022178d23323` |
| 2nd Judan | `2d69e3ed9a533bbd3ad1077dd0ed2fb718f82cd5803e20d01841ddd3d746c48a` |
| 3rd Judan | `8500725e5ca896e66b9bd64ad3210ce88c55f2dddf153b0130749c2d4e199222` |
| 4th Judan | `c4f9e18680428d8915ed81c7083edba36bead8d7fa404ad92de3b8729f89403b` |
| 5th Judan | `6b7a19956a8d1c377954faf73f246a54cd41bb58bec1bbb7acf44d66fca921c9` |
| 6th Judan | `cfe334831036350e1831cb36c5ffde7e24c8a5d63480e349240865cd32904179` |
| 7th Judan | `823594a6381d77436b1817a23d677d5d0da4adfde0bb58f9dd6fc7db19f8d290` |
| 8th Judan | `01152b7c2e16669c9004054e40f37071ef7d8881b1f0ddf5359bceb778e3fa7c` |
| 9th Judan | `73955d76ee4b49f684ad83ae687b6932ec9571992586afaed38c612ae83796e1` |
| 10th Judan | `3502594d1d2ee5886bb34a8bdb5274b8ebfa10234a0ebad2af17d1a611f02110` |
| 11th Judan | `2630770a249da7b85e3c45155c3d01bc0ce0786d310aaaddacf441a7d5047458` |
| 12th Judan | `973572c088f51353da40969f296efa5bc76f5d2f3da0c50a57213ac5845d51ef` |
| 13th Judan | `2faba3e34415f63c2f960f0ef0c882b988c5ac86d041f07b4626926a26f42849` |
| 14th Judan | `5343053346a42958d4b1c63ef3a2fcb2ee069c41bb64d35038450c7cf5c4ba71` |
| 15th Judan | `8fc6356dcefd8819c2ec2e3d46db9652ed2593678730a2c8fac6684805bef894` |
| 16th Judan | `6ecd13f38884e2f8e587e5bdefa1b082552a05409111de12f314614e4a107ed0` |
| 17th Judan | `b54204190e60b7bcfe323e19d6a1f2089767f1640a528725abcd82f46f049d95` |
| 18th Judan | `0b864f66c87e716e5bdb3d8258115e73cc606f8e097981987aa967c0bdff99bf` |

All 1,345 review statuses remain `pending`.

## Artifacts and validation

Protected artifacts are in `/Users/fan/.local/share/kifu-name-audit/2026-10-03/judan-v2-bundle-semantic-reconciled/` (directory and nested directories mode `0700`, files mode `0600`).

- Bundle SHA-256: `9d0591745c784924eeaf66f38f996659e9587b6cc22ce4711f0a6ae5baafa5ff`
- Canonical bundle SHA-256: `ff757bf201979f204acff22b7a140d76de02c5367c1fb3cbd6cdab5e53078924`
- CWI response-body manifest SHA-256: `c63fac6308b40e05b11d69e3c7d0d8a862903013599ff042eee1f1465febef2f`
- Sol per-link semantic evidence SHA-256: `941adcb87b575d938c090ae55f9a4ac928c522527d8226db733ad23a584b2688`
- Evidence manifest SHA-256: `63ef42e64b3bac062670d4597f040ae4308ef14869a5005f59648d4ad33555e6`

Ran `scripts/kifu_name_batch.py validate` with registry `.5`, the pinned inventory, and the 11-row pending research file. It returned `ready=false`, `write_ready=false`, exit 1 as expected: link approvals and preimage bindings remain pending. There were no scope-hash or source-evidence hash errors.

This preparation resolves the previously recorded production/archive byte mismatch using Sol's semantic reconciliation. It does not approve the identity mapping. The 39 held associations remain excluded and require separate review before any later expansion.
