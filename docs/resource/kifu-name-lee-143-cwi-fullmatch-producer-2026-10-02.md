# Lee Chang-ho player 143: CWI full archive match producer audit

Captured 2026-10-02 as a read-only evidence expansion. This audit approves no name-to-game associations and authorizes no database write.

## Scope and method

I read the controlling [exact-slot prep](kifu-name-lee-143-exact-slot-prep-2026-10-02.md), [remaining cohort audit](kifu-name-lee-143-remaining-cohort-audit-2026-10-02.md), and [Park CWI full-match producer method](kifu-name-park-54-cwi-fullmatch-producer-2026-10-02.md). The frozen CSV contains 2,140 exact `李昌镐` black/white source slots; its SHA-256 is `5c36cdcedf3303310b05bf68b4ad3cc45c6e5368c76c1fbe373e3ab388844f11`. I fetched the corresponding 2,140 raw source SGF files from `home-ubuntu:/home/fan/Repositories/katrain/data/kifu-album/19x19/` by their pinned source paths. All 2,140 files were found and parsed; no raw SGF bytes were saved. Per-file raw byte hashes and source paths are retained in the row evidence.

The source exact-slot prep's `sgf-sha256.csv` is a separate hash of production `sgf_content` captured from the database, not the raw file-byte hash used here. I did not assert equality between these distinct representations or compare the full 2,140 parser-serialized SGFs back to a single production snapshot. The CSV, production-hash capture and remote source files therefore retain their separate provenance boundaries.

The CWI archive was the existing public capture `games.tgz`, 46,246,395 bytes, SHA-256 `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad`. All 96,143 SGF members parsed successfully. For every source and CWI SGF, the full match key is normalized board size (omitted `SZ` defaults to 19), exact sorted root setup stones (`AB`/`AW`/`AE`), and the complete first-child mainline as ordered move-color and coordinate pairs. The match is independent of player-name metadata; names were inspected only after a tuple match. Recognized Lee forms were `Lee Chang-ho`, spacing variants, `Lee Changho`, `이창호`, `李昌镐`, `李昌鎬`, and corresponding family-name-first romanizations.

## Match results

| Classification | All 2,140 frozen rows | Novel rows after excluding 5 + 34 approved slots |
|---|---:|---:|
| Same-side Lee name on at least one full tuple match | 338 | 335 |
| Opposite-side Lee conflict | 0 | 0 |
| Full tuple match, but no Lee name in either CWI player field | 0 | 0 |
| No full tuple match | 1,802 | 1,766 |

The 338 matched source rows have 344 matching CWI member instances. In every instance, the recognized Lee name is on the same side as the source slot; no matched instance has Lee on the opposite side, on both sides, or on neither side. Six source rows have two CWI member paths for the same exact tuple: `97188/white`, `97296/white`, `97332/white`, `97369/black`, `97385/black`, and `97473/black`. Their paths and member-byte hashes are recorded separately in the row evidence. Duplicate archive paths do not increase the matched source-row count.

The novel cohort removes the separately approved five slots (`40212/black`, `64489/black`, `83228/black`, `97368/white`, `98003/black`) and the separately approved 34 slots listed in [the 34-link prep memo](kifu-name-lee-34-link-bundle-prep-2026-10-02.md). Three of those 39 previously approved rows have CWI tuple matches (`64489/black`, `83228/black`, `98003/black`); the novel results above exclude them. The other 36 excluded rows had no CWI full tuple match. This exclusion affects cohort counts only, not the scan: all 2,140 rows were processed.

## Metadata comparison

The detailed row evidence preserves the exact source CSV fields, parsed raw source SGF root properties, CWI properties, and every matching CWI path and byte hash. Counts below are archive-member instances, so the six duplicate paths contribute a second instance.

- **Date:** four source/CWI SGF date differences: `58369` (source `1999-05-26`, CWI `1999-05-27`), `93520` (`2009-05-20` vs `2009-05-21`), `98056` (`2011-11-23` vs `2011-11-26`), and `98153` (`2015-09-07` vs `2015-09-08`). In each case the source CSV date agrees with the source SGF date.
- **Opponent and event text:** all 344 matched member instances have raw string differences in both opponent and event fields. For example, source `金日焕` / `27届三星杯韩国预选小组8强` corresponds to CWI `Kim Ilwhan` / `27th Samsung Cup`. These cross-script name spellings and differently scoped event labels need source reconciliation; raw text differences alone do not imply a wrong game or identity.
- **Result:** 34 raw `RE` differences. Among them, 16 preserve a White winner and 16 preserve a Black winner while differing in notation, margin, or result detail; two source `Draw` values correspond to CWI `Void`. No parseable decisive winner-color conflict was found. Raw values are retained per row and must not be collapsed into a claim that all result metadata agrees.
- **Ranks:** for each target and opponent side, 319 instances have rank values in both source SGF and CWI, 24 have a CWI-only rank, and one has a source-only rank. Differences between raw strings include standard forms such as `九段` versus `9p`; after mapping Chinese `n段` and numeric `nd` forms to `np`, nine target-side and 20 opponent-side values remain different. Target-side rows are `25131`, `25243`, `46678`, `97199`, `97200`, `97201`, `97202`, `97205`, and `150591`. Opponent-side mismatch rows and raw pairs are in `summary.json` and the JSONL evidence. Rank systems, amateur suffixes, and time-specific ranks may explain some values; these are review flags, not identity disproofs.
- **Source:** two nonempty `SO` values differ: album `97291` has source `https://19x19.com` and CWI `Go World #82`; album `97295` has source `https://19x19.com` and CWI `WT-1998-11`. The archive member path is recorded for every match; it belongs to the CWI tar namespace and is not evidence of independent collection origin.

## Interpretation and limits

These exact tuples show that the CWI archive contains full-game records matching a bounded set of Lee-labeled source slots, with same-side CWI Lee metadata. This is conservative candidate evidence only. It does not approve player identity for any slot or establish that CWI collected the games independently: CWI and `19x19` may share upstream records. The 1,766 novel rows without a full tuple match reflect this archive's coverage, not evidence against the source slot. The broad remaining 2,101-row cohort stays unapproved except for separately recorded earlier reviews; this memo makes no new identity decisions.

## Controlled evidence

Evidence is in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-cwi-fullmatch/`, with directory mode `0700` and files mode `0600`.

| Artifact | SHA-256 | Contents |
|---|---|---|
| `lee-143-cwi-fullmatch-row-evidence.jsonl` | `d1e568fae76cc5c36fdf5078a8ae717bf45569546e2f290a4afa2c7fc36e4228` | All 2,140 rows, raw source file path/hash, full-tuple classification, all CWI member paths/hashes and properties, and metadata comparisons |
| `summary.json` | `0acddd212d4937c7321c44b08e365d1997ef8986eec4a0aaee85d162247a3854` | Archive counts, all-row and novel cohort counts, metadata differences, duplicate paths, and input hashes |
| `match.py` | `1face7f818db5fb7ac1db98615bcd75c5d3ee04ea8bbf17d2c01e58f92d3d99e` | Full archive tuple scan |
| `enrich.py` | `d94ab290710c6973a69b7bb64e76e8cd0b5e95a463ceab58fe58741ce5b5cd8f` | Matched-row root-property capture and metadata enrichment |

The source files were streamed from `home-ubuntu` and held in local process memory for matching; they were not copied into this evidence directory. No database writes, code edits, production changes, or identity approvals were performed.
