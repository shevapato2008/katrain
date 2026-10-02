# Honinbo corrected name preimage binding (2026-10-02)

Created a fresh pending binder copy for the symbolic event `event:@honinbo-series-2026-10-02`. Binder `/root/honinbo_corrected_binder_luna`, configured `gpt-6-luna` / high. Binding time: `2026-10-02T15:21:20.553178+00:00`. The eleven candidates retain their source producer metadata and exact source-reviewed display forms; each has explicit `name_preimage_sha256: null` and a `preimage_binding` pinning the source-reviewed candidate hash. They remain `pending`; this is not final name approval.

## Fresh production capture

`capture.sql` ran through `ssh ucloud-v100` and `docker exec -i katrain-ucloud-postgres-1 psql` in one `REPEATABLE READ READ ONLY` transaction against `katrain_prod_20260725`. It read the six catalog tables plus all `kifu_event_names` rows and ended with `ROLLBACK`. Start/end snapshot was `1594742:1594742:`; start `2026-10-02T15:19:26.141093+00:00`, end `2026-10-02T15:19:26.155030+00:00`.

The capture contains 876 players, 22 events, 23 player aliases, 8 event aliases, zero raw player/event values, and 108 event-name rows. Recomputed full importer catalog SHA-256 is `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`, matching the signed identity bundle. Proposed canonical `本因坊戦` has no exact or normalized canonical-name or alias collision and no exact event-name display match. All eleven new symbolic-owner name preimages are null.

## Inputs and outputs

The candidate set combines the seven corrected source-reviewed rows (`en cn tw de es tr ua`) with the four unaffected source-reviewed rows (`jp ko fr ru`). The two source sets, matching research rows, registry `.5`, pinned inventory, and signed 1,617-link identity bundle were hash-pinned in the manifest. The correction and unaffected candidate producer metadata and research hashes were retained. The bundle’s album-link objects and link/member/owner set hashes were preserved.

Protected outputs are in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-corrected-binder-luna/` (directory `0700`, files `0600`).

| Artifact | SHA-256 |
|---|---|
| `capture.sql` | `d23e898e6f2879b6cc063a1a2d9bc2d3f25cbeaac5f18d6e307760114dff4242` |
| `capture.jsonl` | `e73f1ec827cd0bb1b3397f8f9ff87512c7320e15b55650a30714becc4ff9e745` |
| `honinbo-series-2026-10-02-v2-bundle.preimage-bound.pending.json` | `c56618f3a9fb0ed04db29bf40cd03182fd6627197fd79d9d61fcbc2cc50ffbbf` |
| `honinbo-series-2026-10-02-candidates.preimage-bound.pending.jsonl` | `c3bb49802ec337e768fc6db8c5111e8bb739fd607de822fe620ae7af00396927` |
| `preimage-binding-manifest.json` | `6636a59cc0953161b5ef2231d8d8505b27ad9a4333bb95a09561dcb3a2500472` |
| `offline-validation.json` | `d854a2cd04534bcae0d9b6790dd1884dab8004d2da412ef410d840c58668fad1` |

## Offline validation

The v2 validator reports 11 pending, 0 approved, `write_errors: []`, `ready: false`, and `write_ready: false`. Its exact blocker is: `linked identity lacks all eleven approved language names: event:@honinbo-series-2026-10-02`. The signed identity links have no reported link/member errors; the eleven names still require an independent final review. No production database or SGF writes occurred.
