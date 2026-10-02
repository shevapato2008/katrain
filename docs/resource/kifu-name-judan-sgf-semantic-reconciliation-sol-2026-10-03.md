# Judan direct-path SGF byte mismatch: read-only reconciliation

**Finding:** The 1,345 archive-member and production SGF SHA-256 values differ because the importer removes SGF whitespace outside property values when it parses and serializes each file. The games are identical under that exact transformation. All 1,345 production bodies equal both (a) the archived SGF after only that whitespace is removed and (b) the application parser's `root.sgf()` output byte for byte. There are **zero semantic or source-binding exceptions** in this finite direct-path cohort. This resolves the body-hash discrepancy recorded in [the unsigned bundle prep](kifu-name-judan-v2-bundle-prep-2026-10-02.md); it does not sign, approve, or make that bundle write-ready.

## Scope and method

I used the 1,345 IDs and exact CWI member paths in the pinned `direct-path-archive-root-evidence.jsonl` (SHA-256 `368aff854d0d119a26f2e34c5ebb19959426f268ae35c904659f5760d639742d`). Its disjoint 39-row hold file (SHA-256 `f88762f9ccc249516e017e24c3d1e2af68b4352a92f03ae7ee60d01274da668a`) was excluded from the query and all comparisons. I checked the local CWI `games.tgz` SHA-256, `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad`, and streamed its exact members once.

The production query selected only those 1,345 album IDs from `ucloud-v100 / katrain-ucloud-postgres-1 / katrain_prod_20260725` in one `REPEATABLE READ READ ONLY` transaction, then `ROLLBACK`. Its start and end snapshot was `1596833:1596833:` at `2026-10-02T16:03:24.907508+00:00` to `16:03:24.984444+00:00`. SGF bodies were processed in memory and were not saved. Each production body SHA-256 also matched the earlier protected production capture (file SHA-256 `6d0de0108a79f5c9c8ccfee3fd57ec562ba263a3a8af09af1e5ca8e23b9dc44d`). No database or source SGF was written.

For every pair, I checked the complete archive-member hash against its pinned value, exact source path, complete mainline B/W move sequence, all parsed nodes and variations, and root `EV`, `GN`, `RO`, `DT`, `RE`, `PB`, `PW`, `PL`, `AB`, `AW`, and `AE`. Production columns for event, round, date, players, and result agreed with the parsed roots. `GN`, root setup (`AB/AW/AE`), and `PL` are absent in all 1,345; the root black/white names and every B/W move agree. Complete mainlines range from 46 to 357 moves. The parsed tree comparison includes all properties and variation branches, rather than only those named root fields.

| Check | Passing links |
|---|---:|
| Raw archive SHA-256 equals production SHA-256 | 0 / 1,345 |
| Raw archive with only outside-property whitespace removed equals production bytes | 1,345 / 1,345 |
| `SGF.parse_sgf(archive).sgf()` UTF-8 bytes equal production bytes | 1,345 / 1,345 |
| Full parsed tree, mainline, named root fields, source path, pinned archive hash, prior production hash | 1,345 / 1,345 each |

The archive files are 16–47 bytes longer than their production forms. The first, midpoint, and last album IDs illustrate the same transformation:

| Album ID and archive member | Raw archive SHA-256 | Parsed/production SHA-256 |
|---|---|---|
| `159685` `games/Judan/01/L09.sgf` | `ba35edc69098b03558374955c993ee98b4e58c98a390eae2ea08114d93e04f09` | `3ff9244371b462dfb08de6f3df8de4c7c743c383afd671a08080718d5282eb7f` |
| `160357` `games/Judan/09/Q70.sgf` | `a7bf396ecab79f881eaa096fd4c9487e374142664c4cb35ab16969c213e959c7` | `c86305b3698ec6631c23724a0c48913dbf297a3d5e8b7cf4a5cf14ba1d1a6053` |
| `161029` `games/Judan/18/Q07.sgf` | `a943616cdee0de2e4d56db5b6ceb6fb5cee371c1086c91c7d51c6e3c0274e303` | `4563c3c5a51826c31b6a64b8b740e081eae051c99645dfa2be914664d0ae7d02` |

## Evidence and remaining gate

Protected evidence is in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/judan-sgf-semantic-reconciliation/` (directory `0700`, files `0600`). `per-link-reconciliation.jsonl` has all 1,345 album IDs, exact source paths, both hashes, root values, and comparison results; SHA-256 `941adcb87b575d938c090ae55f9a4ac928c522527d8226db733ad23a584b2688`. `summary.json` SHA-256 is `4d203ab05aa6a748298285efd8c7b0833c3e045edc4bcd0b053fee87908226ec`; the reproducible read-only script SHA-256 is `d589bf6c9039ebdd9bb61c1d407b6b473447ea6fa580dd05bb9e8dedda68df3d`. The exception list is empty.

The 39 other-folder rows remain **HOLD** and excluded. The 1,345-link draft remains unsigned and `pending`; its identity approvals, source-check bindings, and name preimage gates still require their separate process. This memo grants no candidate, event-ID, or production-write approval.
