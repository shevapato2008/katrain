# Independent Honinbo production SGF binding review (2026-10-02)

## Decision

**PASS for the finite, exact `1st Honinbo`–`34th Honinbo` cohort of 1,617 album associations.** The saved production capture supports binding these rows to their mapped CWI SGFs for event-series identity: all 1,617 mainline move sequences and PB/PW/EV/RO root values match. The only requested field difference is album **24560**, whose archive root has `DT[1940]` while production has no `DT`. This date omission does not change the event-series identity. The result is **1,617/1,617 mainline matches**, **1,617/1,617 setup matches**, and **9,701/9,702 named root-field matches**, not a claim of complete SGF equivalence.

This PASS does not approve a particular canonical event ID, display names, or a production update. The [edition identity review](kifu-name-honinbo-edition-independent-review-2026-10-02.md) defines the cohort boundary; the 1,704 adjacent Honinbo-like rows remain outside it.

## Independent checks

- Verified SHA-256 of all three pinned inputs (inventory gzip, preimage JSONL, CWI `games.tgz`), the pinned repository SGF parser, and all four protected outputs (`production-capture.json`, `per-row-manifest.jsonl`, `mismatches.json`, `reproduce.py`). Each equals the value in the [binding audit](kifu-name-honinbo-game-binding-audit-2026-10-02.md).
- Inspected `reproduce.py`: capture SQL starts `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY`, selects only from `public.kifu_albums`, checks the reported database/isolation/read-only settings, and ends with `ROLLBACK`. The comparison path reads the saved capture and local archive. No database write SQL is present.
- Independently cross-checked every manifest row against the frozen inventory, the separately pinned preimage file, the saved production capture, and the mapped raw archive member SHA-256. All 1,617 IDs, association-context fields, production/preimage SGF hashes, archive member hashes, and stored production parsed views agree. The 1,617 associations resolve to 1,616 archive members.
- Recounted the saved comparisons independently: moves 1,617; setup 1,617; PB 1,617; PW 1,617; EV 1,617; RO 1,617; DT 1,616; SZ 1,617. The sole mismatch report is `root.DT` for album 24560 (`1940` versus absent). A separate small SGF parser recomputed raw-archive mainlines and root values for eight sampled rows across editions 1, 17, 23, and 34, including album 24560 and its archive-member collision with album 152132; these agreed with the manifest.

## Limits

Every compared root setup list is empty, and every compared root `SZ` is absent; their 1,617 matches do not test nonempty AB/AW/AE or explicit board sizes. The parser follows the first child at each variation and compares the six named root properties. Side variations, comments, other properties, and byte formatting were not compared. Album 24560 and 152132 map to the same archive member but have distinct production SGF hashes; these are association counts, not a count of unique games.

The protected capture stores parsed production semantics and hashes, not production SGF bodies. The source script's read-only SQL and saved transaction metadata were inspected, but this review did not independently query or attest the live database transaction. A later production write needs its own approved event record and a fresh row/preimage check.

Review model configuration reported by the parent: **gpt-6-sol, high reasoning**. This is a configuration report, not runtime attestation.
