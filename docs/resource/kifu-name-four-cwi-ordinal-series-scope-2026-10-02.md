# Four CWI ordinal event series: bounded source audit (2026-10-02)

This read-only producer audit expands the event-series queue after the separate Honinbo and Judan audits. It covers only four exact `english_ordinal_edition` groups in the frozen production inventory: `Oza`, `Old Meijin`, `Pro Best Ten`, and `Nihon Ki-in Championship`. Existing [source-name memos](kifu-name-event-series-source-matrix-2026-10-02.md) remain separate from identity and language approval. No event ID, alias, translation, or production row was changed.

| Exact series core | Group rows | Same-edition CWI series-directory rows | Held rows | Hold reason |
|---|---:|---:|---:|---|
| Oza | 1,356 | 1,304 | 52 | 35 other directories; **17 source `EV=28th Oza` files under `Oza/26/`** |
| Old Meijin | 1,199 | 1,184 | 15 | Other directories, including one historical package |
| Pro Best Ten | 1,171 | 1,125 | 46 | Other directories |
| Nihon Ki-in Championship | 1,153 | 1,121 | 32 | Other directories |
| **Total** | **4,879** | **4,734** | **145** | No held row is in the direct-path proposal |

For each candidate I required an exact raw ordinal, a unique source path under `CWI_1950_1978/<series-folder>/<edition>/`, and numeric equality between the directory and raw edition. Every selected row has a CWI source and `event_id=null` in the frozen inventory. I then streamed the local public CWI archive once. All **4,734** direct-path rows had their corresponding archive member; its SGF root `EV` or `GN`, `DT`, `PB`, and `PW` each matched the inventory field exactly. These four comparisons had **zero mismatches**. This is source-to-inventory consistency, not independent confirmation that every record belongs to a real-world event or that live production SGF bytes are unchanged.

The Oza anomaly is concentrated: album IDs **170812–170828** are 17 successive source files `Oza/26/P01.sgf` through `P17.sgf`, dated from 1977-12-15 to 1978-05-11, while their raw event is `28th Oza`. Their archive folder and SGF event disagree on the edition. The [Nihon Ki-in's official Oza history](https://archive.nihonkiin.or.jp/match/oza/index.html) lists the 26th term's title year as 1978 and the 28th as 1980, supporting the need to investigate the conflicting source label; it does not identify each of these preliminary games. They are **HOLD** pending official edition/game reconciliation; do not silently rewrite the edition or merge them with the 1,304 direct-path candidates. Other-folder rows may still belong to these series, but require separate row-level verification.

Pinned input: production inventory canonical SHA-256 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`, event-group v4 canonical SHA-256 `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`, CWI `games.tgz` file SHA-256 `935522a59817c12b37227e843cd3b4bc8d702e32e0e6fbc80b66d828dbbffcad`. Controlled files in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/four-cwi-ordinal-series-scope/` have directory mode `0700` and file mode `0600`:

| File | Rows | SHA-256 |
|---|---:|---|
| `direct-archive-root-evidence.jsonl` | 4,734 | `42c29b32b1e990a0712391f7016d6943ef6e0f4b6995522cad9b982dc62263b7` |
| `hold-other-or-mismatch.jsonl` | 145 | `df068cee60a7dd9470b3084f8252358fe4b000cbce9a9b5c1bc770f2e478a659` |

Each direct row retains album ID, exact raw event, numeric edition, source path, old event FK, public archive member hash and observed SGF root fields; each held row records its precise folder/edition reason. These cohorts need independent source/identity review and current transaction-bound preimages before any selected-event bundle. The series' eleven-language names also need separate approved candidate records. None of the 4,734 rows counts as completed production coverage.
