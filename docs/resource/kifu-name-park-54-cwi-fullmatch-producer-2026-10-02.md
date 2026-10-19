# Park Junghwan player 54: CWI full archive match producer audit

Captured 2026-10-02 by `/root/park_cwi_fullmatch_luna`, assigned model **`gpt-6-luna`**. This is a read-only evidence expansion for independent review. It approves no names-to-game associations and authorizes no database write.

## Scope and method

I used the frozen 1,526-row evidence set documented in [the identity-scope producer memo](kifu-name-park-54-identity-scope-producer-2026-10-02.md), whose row evidence is `park-54-full-row-evidence.jsonl` (SHA-256 `602c6ccc9dc2746e47ffc055b110a6854882d75fa5d5f08447a5385d11fa6960`). The independent review of four LG Cup rows remains separately documented in [the four-row review](kifu-name-park-54-identity-independent-review-2026-10-02.md).

The CWI [Go game archive index](https://homepages.cwi.nl/~aeb/go/games/games/) advertises a 90,000+ SGF archive at `https://homepages.cwi.nl/~aeb/go/games/games.tgz`. I downloaded that public archive read-only. It is 46,246,395 bytes, SHA-256 `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad`. The tar contains **96,143 SGF members**; all parsed. The captured index HTML SHA-256 is `388e0f1434799d941720cadf5cfc9d9ee10409f280a785d3af0c8fa5fd4c741a`.

I matched every archive SGF against each frozen source SGF using the normalized board size, exact root setup stones (`AB`/`AW`/`AE`), and the complete first-child mainline including move colors and coordinates. An omitted SGF `SZ` is interpreted as the SGF default size 19. The source-side canonical mainlines were checked against the producer evidence before scanning. I then compared CWI player properties against the frozen target slot, treating `Park Junghwan`, `Park Jung-hwan`/spacing variants, `박정환`, and `朴廷桓` as Park name forms. These rules identify candidate matches; they do not establish that CWI collected its SGFs independently from `19x19`.

## Match results

| Classification | Frozen rows | Interpretation |
|---|---:|---|
| One same-side Park full match | 230 | One CWI member has the exact board/setup/mainline and Park appears in the frozen target color. Bounded cohort for independent row review. |
| Multiple same-side Park full matches | 1 | Album `122392` matches two CWI member paths (`games/Ing/07/19.sgf` and `games/Cho_Chikun/2012-05-27.sgf`). Count as one frozen row, with both archive records retained. |
| Opposite-side Park conflict | 3 | Albums `811`, `4211`, and `4219`: exact sequence/setup/size match, but CWI places Park on the other side. Hold for source/metadata reconciliation. |
| Sequence match; no Park name in either CWI slot | 1 | Album `150967` matches `games/FMeijin/33/06.sgf`, whose names are Xie Yimin and Mukai Chiaki. This is a sequence collision or metadata/source anomaly; do not count as Park evidence. |
| No full tuple match | 1,291 | No CWI archive member matched the complete tuple. This is archive coverage, not evidence that the frozen row is false. |

There are 235 frozen rows with at least one full tuple match, represented by 236 archive members. This is a scalable bounded cohort of 230 unique same-side rows for independent review; the 1,526-row population remains unapproved. The previously reviewed four LG Cup rows are among the full-match cohort, but their separate review decision does not extend to the other rows.

## Metadata and anomaly screen

The following screen concerns the 232 same-side archive-member instances (the 230 unique rows plus the second archive path for album `122392`). It compares fields as recorded; differing source conventions do not by themselves determine which record is correct.

- **Date:** five source/CWI SGF date differences: album `83389` (`2009-02-25` vs `2010-02-25`), `85739` (`2014-08-17` vs `2014-08-16`), `90038` (`2010-02-08` vs `2010-01-29`), `122500` (`2015-09-07` vs `2015-09-08`), and `122588` (`2018-09-26` vs `2018-09-27`). GoRatings dates also differ from the CWI date for `85739` and `122588`.
- **Opponent:** CWI opponent text differs from the corresponding single GoRatings date/color row for 12 frozen rows (`28227`, `28450`, `79543`, `98740`, `98814`, `98856`, `103801`, `122348`, `122350`, `122351`, `122392`, `122405`). These are raw display-string comparisons across transliteration conventions and need reconciliation. The row-level artifact retains both names.
- **Result:** raw source/CWI `RE` strings differ in 34 same-side match instances, including missing source results, draws/voids, and different margin detail. The known GoRatings winner conflict for album `60290` remains present: CWI records `B+5` while the profile lists Park as a winner with Park White. No source/CWI winner-color conflict was found among same-side rows with parseable decisive results; this does not resolve the profile conflict.
- **Rank:** CWI supplies rank properties on many records where the frozen SGF has none (43 target-side and 43 opponent-side instances). Where both sides have comparable numeric ranks, source/CWI target-rank values conflict for albums `72803` and `122324`; opponent-rank values conflict for `98814`, `120680`, `122609`, `122627`, and `122637`. These are review flags, not grounds to reject an exact move-sequence match.
- **Board size/setup:** no board-size conflict among matches. CWI frequently omits `SZ`, which has SGF default 19. Initial setup stones were part of the exact match key.
- **Profile date/result:** CWI dates differ from the GoRatings entry for `85739` and `122588`; one decisive winner conflict appears for `60290`. GoRatings opponent string differences are listed above. Profile screening remains secondary metadata, not full-game proof.

## CWI path and era strata

Counts below are archive member paths for all 236 full tuple matches, including the three opposite-side cases, the name-unresolved sequence collision, and both `122392` paths. The directory labels indicate CWI archive organization, not proof of distinct collection origins.

| CWI directory | Members |
|---|---:|
| Samsung | 70 |
| LG | 40 |
| Ing | 22 |
| Chunlan | 20 |
| Mlily | 17 |
| Bailing | 15 |
| AsianTV | 13 |
| BC | 11 |
| Fujitsu | 7 |
| WC | 7 |
| Tianfu | 5 |
| Shinhan | 4 |
| Xinao | 1 |
| unusual | 1 |
| people | 1 |
| Cho_Chikun | 1 |
| FMeijin | 1 |

Matched archive dates span 2007–2025. The controlled summary artifact contains the complete directory/year cross-tab. Samsung spans 2007–2025 (no match in 2020); LG spans 2010–2025; Bailing 2012–2018; Fujitsu 2010–2011; Chunlan 2010–2025; Ing 2012–2024; Mlily 2013–2023; AsianTV 2011–2018; BC 2010–2012; WC 2017–2019; Tianfu 2018; Shinhan 2025; and the remaining single-path directories occur in 2012, 2016, 2022, 2023, or 2024 as recorded in the controlled cross-tab.

## Controlled evidence

Files are outside the repository in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/park-junghwan-identity-work/cwi-full-archive/`; directory mode is `0700`, evidence files mode `0600`.

| Artifact | SHA-256 | Contents |
|---|---|---|
| `games.tgz` | `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad` | Complete CWI archive download, 46,246,395 bytes |
| `index.html` | `388e0f1434799d941720cadf5cfc9d9ee10409f280a785d3af0c8fa5fd4c741a` | Captured CWI archive index advertising the download |
| `http-headers.txt` | `16c1ac7672429ceb5052d502f9a40c5b9c30ac7e04d84e7d74d54031d676940a` | HTTP response headers captured for the archive URL |
| `park-54-cwi-fullmatch-row-evidence.jsonl` | `91e8f4be80ff40e154f66656065af938c47add5a5c3e570323929d829c1470a7` | All 1,526 frozen rows, source paths and hashes, match categories, exact CWI archive member paths, member-byte hashes, and matched SGF metadata |
| `summary.json` | `9ab5a31ae7b63630f810c888ab458c5103f8992bb1bb1c8de3a6efeef6e047ee` | Archive counts, match classifications, path/era strata, metadata screen, and evidence hashes |

This audit establishes exact full-game record matches within the downloaded CWI archive. It does not establish independent upstream provenance: CWI and `19x19` may share game records. No database, program, or identity assignment was changed.
