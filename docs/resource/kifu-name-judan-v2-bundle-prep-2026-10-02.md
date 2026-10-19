# Judan direct-path v2 bundle preparation (2026-10-02)

Prepared an unsigned, read-only v2 bundle draft for symbolic event `judan-series-2026-10-02` with canonical name `十段戦`. It contains exactly the 1,345 direct numbered archive associations approved for identity scope in the independent ordinal review. The 39 held rows are excluded. The 11 candidate rows are pending copies of the separately source-reviewed names; no candidate signatures or identity approvals were added.

## Production and source snapshot

A single `REPEATABLE READ READ ONLY` production transaction captured all 1,384 albums and source links in the 18 exact Judan raw-event values, the complete catalog tables, and event names. It rolled back. The 1,345 selected associations match the frozen inventory context and source-link IDs/paths; all 39 held rows remain outside the bundle. The computed current catalog SHA-256 is `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`. No normalized canonical, alias, or language-name collision was found for the proposed eleven names.

The current production SGF SHA-256 preimage is captured on every proposed link. **Those hashes match the pinned CWI archive-member hashes for 0 of 1,345 links.** The earlier source review binds CWI member paths and parsed roots to the frozen inventory, but the current production SGF content has not been reconciled to those archive members. For that reason, every link remains `pending`; `source_checks` are empty and the draft is not ready for approval or writing.

## Artifacts and validation

Protected evidence is in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-v2-bundle-draft/` (directory mode `0700`, files mode `0600`). The bundle byte SHA-256 is `d7f07bf393e263f96d75a9467fd0791c6b8e65461209b9dee5aa5c88cb0fe31c`; canonical bundle SHA-256 is `f6ebf21ed36e8b1a2824cda3a95658fee721e7a1aadca1806216b9a8fb4cf95b`. The current-production capture SHA-256 is `6d0de0108a79f5c9c8ccfee3fd57ec562ba263a3a8af09af1e5ca8e23b9dc44d`; the artifact manifest SHA-256 is `7e009558f3769bb12b82c9b92a3e15ac4c6d9298a3653dd4bea64c8b5d0d4672`.

Ran `scripts/kifu_name_batch.py validate` with registry `.5`, the pinned inventory, and the 11-row pending research file. Validation returned `ready=false`, `write_ready=false`, exit 1, as expected for the unsigned draft: all 1,345 links need independent identity approval, and name preimage bindings are absent. The report has no unexpected scope/hash errors. No database writes were made.

## Remaining review gate

Before any identity approval, independently capture or parse the current production SGF roots for these 1,345 IDs, reconcile the production/archive member hash difference, and retain per-link source excerpts and body hashes. Then recompute/freeze each exact raw-value scope and have an independent reviewer approve it. Keep all 39 held rows excluded unless separately reviewed.
