# Honinbo 1st–34th production SGF binding audit (2026-10-02)

## Result

A single `REPEATABLE READ READ ONLY` transaction on `ucloud-v100 / katrain-ucloud-postgres-1 / katrain_prod_20260725` captured the 1,617 production album rows in the frozen exact `1st Honinbo`–`34th Honinbo` cohort. The query selected each row's association context, PostgreSQL SHA-256 of `sgf_content`, and the SGF body. The body was parsed in memory and omitted from saved evidence. The transaction was rolled back. Snapshot time: `2026-10-02T13:55:48.521719+00:00`.

All **1,617/1,617** IDs and association context values match both the frozen inventory and the current-production preimage manifest. All **1,617/1,617** production SGF SHA-256 values match that preimage manifest. The source paths map to **1,616 distinct** SGFs in the pinned CWI archive.

Parsed comparisons against those mapped archive SGFs:

| Comparison | Exact matches |
|---|---:|
| Mainline move sequences | 1,617 / 1,617 |
| Root setup placements, including AB/AW/AE | 1,617 / 1,617 |
| Root PB, PW, EV, RO, DT, SZ values | 9,701 / 9,702 |
| All requested content checks together | One mismatch |

The sole mismatch is album **24560**, root `DT`: archive `1940`; production has no value. No mainline, setup, association-context, or other requested root-field mismatch occurred.

## Method and limits

The source path from each selected inventory association was mapped to its `games/...` member in the local archive; optional `CWI_1950_1978/` and `CWI_History_Full/` prefixes were removed. The repository SGF parser (`katrain/core/sgf_parser.py`, SHA-256 `59a4d743d0d36ddc22ad1a21ce789110fc56c29b3356d9fe2e0cc5e9f9961cb5`) followed the first child at each variation point to form the mainline, and compared parsed move coordinates and expanded root setup placements. The six named root properties were compared as parsed values. Production bodies were processed in memory during the transaction and are not stored in the evidence bundle.

This binds the current production SGF content to the mapped CWI archive at the compared semantic fields. It does not compare byte formatting, side variations, comments, or root properties outside PB/PW/EV/RO/DT/SZ, and does not approve an event-ID assignment, name candidate, or database write. The cohort and identity boundary are described in the [independent edition review](kifu-name-honinbo-edition-independent-review-2026-10-02.md).

## Pinned inputs and protected evidence

Inputs:

| Artifact | SHA-256 |
|---|---|
| Frozen inventory gzip | `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9` |
| Current-production preimage JSONL | `4a58e70039eaf623aa6ac5d6b33c68b4462954868fb985917ff0a89bb27038e7` |
| CWI `games.tgz` | `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad` |

Protected outputs are under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-game-binding/` with directory mode `0700` and file mode `0600`. They include the read-only capture with parsed production SGF semantics, a per-row manifest with both parsed SGFs and hashes, a one-row mismatch report, and the reproduction script.

| Protected output | SHA-256 |
|---|---|
| `production-capture.json` | `ef80b21935c422e367b3ea10749b0a7969c0f7213b7e15d6e6618ca3ab23b2df` |
| `per-row-manifest.jsonl` | `8af3877ff99d6f08f34eef9bf3f68e0482adfb6a301346ad7245a478344cdf26` |
| `mismatches.json` | `d9aa051bd9d7d36ba1a93b5c147c0c5d68fe0ed13c423e3b696569cf7a41ee96` |
| `reproduce.py` | `d8fd16032bbdaff143df67ad89186048ab246ff40aaba3f0a50d34107c7e75c0` |
