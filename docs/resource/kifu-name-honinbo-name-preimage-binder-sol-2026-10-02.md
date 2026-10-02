# Honinbo name preimage binding, pending final review (2026-10-02)

I bound the eleven pending name candidate copies for the new symbolic event `event:@honinbo-series-2026-10-02`. Binder: `/root/honinbo_name_preimage_binder_sol`, configured model `gpt-6-sol` (supplied by the parent; the runtime did not independently expose a model identifier). Binding time: `2026-10-02T14:37:48.920492+00:00`. All eleven `name_preimage_sha256` values are explicitly `null` in the candidate and binding record. The historical source approval is retained only as a hashed source reference; the bound candidates remain `pending` and have no final reviewer signature.

## Production capture

The protected directory `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-name-preimage-binder-sol/` has mode `0700`; its files have mode `0600`. `capture.sql` (SHA-256 `d23e898e6f2879b6cc063a1a2d9bc2d3f25cbeaac5f18d6e307760114dff4242`) ran through `ssh ucloud-v100`, `docker exec -i katrain-ucloud-postgres-1`, and `psql -X -q -t -A -v ON_ERROR_STOP=1 -U katrain_user -d katrain_prod_20260725`. It begins `REPEATABLE READ READ ONLY`, reads six catalog tables and every `kifu_event_names` row, and ends with `ROLLBACK`. The captured transaction reported database `katrain_prod_20260725`, user `katrain_user`, isolation `repeatable read`, read-only `on`, snapshot `1592648:1592648:`, and backend PID `752779`. Start: `2026-10-02T14:35:14.73682+00:00`; end: `2026-10-02T14:35:14.750405+00:00`. Start and end reported the same snapshot.

The complete `capture.jsonl` byte SHA-256 is `506c337e730ea380da54bbbaa9f6c68f4e35d64847696dcb877ea6e5c6442386`. Its catalog counts are 876 players, 22 events, 23 player aliases, 8 event aliases, and zero raw player/event values. It also contains 108 event name rows. Recomputing the importer's six-table catalog hash from these rows gives `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`, exactly the draft bundle hash. For proposed canonical `本因坊戦`, exact canonical matches, normalized canonical matches, exact event aliases, stored normalized aliases, recomputed normalized aliases, and exact event-name display matches are each zero. The importer normalizes aliases using Unicode NFKC, casefolding, and collapsed whitespace. No production event ID exists for the new symbolic reference; therefore each of its eleven language name rows has a `null` preimage.

## Bound copies and provenance

| Protected file | Byte SHA-256 |
|---|---|
| `honinbo-series-2026-10-02-v2-bundle.preimage-bound.pending.json` | `181ec9c4add2a7632eadaecb7d8497070e78da0a50dd437f6d417f2954ed43e0` |
| `honinbo-series-2026-10-02-candidates.preimage-bound.pending.jsonl` | `a19b2f078cdb2d1fea2825fb4b33455548fc144e87cfc0a00f2cba6aa4071bf5` |
| `preimage-binding-manifest.json` | `fe1da81ec5ffb922988d95829676a9fec0573d217845ab5174693e592cbb87dd` |

The bound bundle's canonical JSON SHA-256 is `2d432388a5e2b4c9e70c9215411ae18a1e1012aa1e35789d9e0c8346142a1116`. The unchanged source-reviewed candidate file SHA-256 is `c9698402c05fa9863cc024c11f53b30229cd435c132620b4acf4775086bb9001`; the unchanged original pending candidate file is `8b15057a48aea12a47720a22769229d5fc46b3af95cb650a42afb79ea546f113`; the unchanged draft bundle is `15747021dd15d5eacb942ed257a68ca4d15830932812fa1bb36fbc865ad5b3c3`. The manifest pins each source-reviewed row's canonical SHA-256, each original pending row's canonical SHA-256, each bound row's canonical SHA-256, the capture hash, transaction metadata, catalog result, and code hashes.

Each new `preimage_binding` records the actual binder ID/model, capture and binding times, `null` preimage, capture byte hash, and canonical hash of the matching source-reviewed candidate. Source producer metadata and research hashes are unchanged. The 1,617 album links remain identity-review `pending`; link/member/owner sets and their hashes are unchanged. This binding does not certify those links or approve names.

The offline v2 validator reports `write_errors: []` for the bound candidate records. It still reports `ready: false` and `write_ready: false`: all 1,617 identity links lack approval, their pending status prevents the 11 members/candidates from resolving as approved targets, and no final name review follows this binding. Independent final review must follow the binding and differ from both `/root/honinbo_controlled_research_luna` and this binder. The catalog snapshot must be checked again at any later import. No production database or SGF writes occurred.
