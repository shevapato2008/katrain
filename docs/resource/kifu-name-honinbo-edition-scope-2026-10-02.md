# Honinbo edition cohort and identity boundary (2026-10-02)

This read-only scope note audits the exact `Honinbo` English-ordinal cohort referenced by [the 11-language source memo](kifu-name-honinbo-11lang-source-memo-2026-10-02.md). It characterizes the frozen production and clone inventories and adjacent raw labels. It does not approve translations, event IDs, or production coverage, and it does not modify the database or SGFs.

## Cohort definition and confidence

The reproducible cohort is the `event-components-v4` group whose exact parsed pair is `grammar=english_ordinal_edition`, `core=Honinbo`. It contains **34 exact raw strings and 1,617 album rows**: the numbered strings `1st Honinbo` through `34th Honinbo`. The leading ordinal is an edition component; the remainder is the series stem. Every one of the 1,617 rows has a separate non-null `round_name`, so preliminary rounds, league, and other stages remain row-level metadata and are not part of this cohort's event-name string.

Series identity confidence is **high for this exact cohort**: the Nihon Ki-in Honinbo archive and the CWI archive identify a recurring numbered Honinbo title series, while the source memo records the language evidence and holder/series boundary. Confidence is **not high for importing adjacent raw spellings into this cohort**. The archive artifacts show substantial additional Honinbo-like labels that may be alternate encodings, stages, related competitions, or historical/exhibition descriptions. Do not attach those records to the same event identity without source-row review.

| Edition | Games | Edition | Games | Edition | Games | Edition | Games |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1st | 46 | 10th | 4 | 19th | 83 | 28th | 120 |
| 2nd | 27 | 11th | 4 | 20th | 81 | 29th | 106 |
| 3rd | 20 | 12th | 2 | 21st | 87 | 30th | 118 |
| 4th | 8 | 13th | 3 | 22nd | 82 | 31st | 97 |
| 5th | 8 | 14th | 4 | 23rd | 86 | 32nd | 27 |
| 6th | 1 | 15th | 1 | 24th | 92 | 33rd | 33 |
| 7th | 3 | 16th | 70 | 25th | 9 | 34th | 33 |
| 8th | 1 | 17th | 74 | 26th | 102 | | |
| 9th | 4 | 18th | 76 | 27th | 105 | | |

The largest four exact round values are `2nd Preliminary` (969), `3rd Preliminary` (333), `League` (86), and `1st Preliminary` (45). The remaining 184 games have 73 other distinct round strings. Across the cohort there are **77 distinct round strings**, none null. Round strings include numbered preliminaries, rank sections, rounds, finals, playoffs, league and demotion-playoff labels; retain their exact values unless separately normalized with evidence.

Rows span source dates `1939` through `1978-12-07`; 10 rows have no date. The ordinal cohort includes first-edition games dated as early as 1939, before the final/title match concluded in 1941. Do not treat the edition's complete source-row date span as the title-match date or derive edition from calendar year.

## Source and linkage facts in the frozen inventories

| Check | Production inventory | Clone inventory |
|---|---:|---:|
| Snapshot timestamp | `2026-10-01T18:11:45.460901Z` | same |
| Internal canonical inventory SHA-256 | `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3` | same |
| Exact selected raw values / game rows | 34 / 1,617 | 34 / 1,617 |
| Per-raw-value occurrence counts match production | — | yes |
| Selected rows with non-null event ID | 0 | 0 |
| Selected rows with `duplicate_of_id` | 0 | 0 |
| Selected row IDs | 1,617 unique; 24,525–172,954 | same |
| Linked source records | 1,617 `CWI` `source_path` rows (`source_id=2`), 1,617 distinct paths | same |

These are claims about the pinned snapshot artifacts, not live query results. The 1,617 paths and album IDs establish traceability in that inventory; this pass did not hash or inspect every SGF body and does not claim 1,617 unique game contents. A null `event_id` means this cohort has no event-identity linkage in the snapshot.

## Adjacent Honinbo-like labels to keep outside the current cohort

The full production inventory contains **234 other exact raw event strings / 1,704 rows** containing `Honinbo` case-insensitively. The following disjoint bins are a transparent text-based triage, not a classification of real-world event identity:

| Raw-label family | Raw values | Rows | Boundary guidance |
|---|---:|---:|---|
| Reversed/comma-tail ordinal (`Honinbo,29th`, etc.) | 54 | 913 | Potential alternate edition encoding; preserve for source-specific reconciliation. |
| League, qualifier, or preliminary labels | 51 | 375 | Preserve stage/competition wording. These may cover qualification phases, but should not be auto-merged. |
| Joined or otherwise unparsed ordinal forms (`1stHoninbo`, etc.) | 38 | 197 | Some may be orthographic alternatives to this cohort. Resolve from source/event records before aliasing. |
| Women’s / female Honinbo | 34 | 85 | Separate competition family; exclude from the open/professional Honinbo identity. |
| `Title`/`Final` wording | 23 | 48 | May be match- or stage-scoped labels; keep unresolved and separate pending citation-level mapping. |
| Exhibition, commemorative, history, or special-match wording | 23 | 45 | Not the recurring title-series identity solely by containing the name. |
| `JapaneseHoninbo` forms | 4 | 34 | Geographic qualifier is material; exclude unless source evidence proves otherwise. |
| Pro-am / amateur | 5 | 5 | Separate competition or exhibition family. |
| Bare `Honinbo` | 1 | 1 | Ambiguous without source context. |
| Other (one Sansa anniversary label) | 1 | 1 | Historical reference, not evidence of the title-series event. |
| **Total outside exact cohort** | **234** | **1,704** | No alias or identity association was made. |

Examples of unresolved variants include `1stHoninbo`, `Honinbo,29th`, `10th Honinbo Final`, `3rd Honinbo Title`, and `37thHoninboLeague`. The 1,704 rows are **not** part of the 1,617-row scope above. The punctuation/spacing variants may include main-series material, but present evidence does not support folding them in as a batch. The women’s, pro-am/amateur, Japanese-qualified, and commemorative/exhibition labels have clearer separate-family signals and should remain excluded.

## Reproduction and artifact pins

Inputs are in `/Users/fan/.local/share/kifu-name-audit/2026-10-02/`:

| Artifact | SHA-256 of compressed file |
|---|---|
| `kifu-name-inventory-prod-v2-20261002.json.gz` | `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9` |
| `kifu-name-inventory-clone-v2-20261002.json.gz` | `a2f2bb7f73672958a6d6b742ea39d0545a666e2b94272e75ae168250c440872b` |
| `kifu-event-groups-prod-v4-20261002.json.gz` | `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05` |

The group artifact's internal content SHA-256 is `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`, and its pinned input inventory SHA-256 is `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`. The exact selection rule used below reads the group's declared members, then joins by exact `event` value to the inventory album associations. It does not normalize text or infer aliases.

```sh
python - <<'PY'
import collections, gzip, json, re

base = "/Users/fan/.local/share/kifu-name-audit/2026-10-02/"
groups = json.load(gzip.open(base + "kifu-event-groups-prod-v4-20261002.json.gz", "rt"))
group = next(g for g in groups["groups"]
             if g["grammar"] == "english_ordinal_edition" and g["core"] == "Honinbo")
raws = {member["raw_value"] for member in group["members"]}
for member in sorted(group["members"], key=lambda m: int(re.match(r"(\d+)", m["raw_value"]).group(1))):
    print("edition", member["raw_value"], member["occurrences"])
for filename in ("kifu-name-inventory-prod-v2-20261002.json.gz",
                 "kifu-name-inventory-clone-v2-20261002.json.gz"):
    inventory = json.load(gzip.open(base + filename, "rt"))
    columns = inventory["association_columns"]
    event_i, round_i = columns.index("event"), columns.index("round_name")
    event_id_i, duplicate_i = columns.index("event_id"), columns.index("duplicate_of_id")
    date_i, id_i, sources_i = columns.index("date_played"), columns.index("id"), columns.index("sources")
    rows = [row for row in inventory["album_associations"] if row[event_i] in raws]
    counts = {r["value"]: r["occurrences"] for r in inventory["scopes"]["all"]["values"]["event"]}
    similar = [r for r in inventory["scopes"]["all"]["values"]["event"]
               if isinstance(r["value"], str) and "honinbo" in r["value"].lower()
               and r["value"] not in raws]
    rounds = collections.Counter(row[round_i] for row in rows)
    dates = [row[date_i] for row in rows if row[date_i] is not None]
    source_rows = [source for row in rows for source in (row[sources_i] or [])]
    print(filename, "selected", len(raws), len(rows), sum(counts[value] for value in raws),
          "round_values", len(rounds), "null_rounds", rounds[None], "top_rounds", rounds.most_common(4),
          "null_event_ids", sum(row[event_id_i] is None for row in rows),
          "duplicate_links", sum(row[duplicate_i] is not None for row in rows),
          "nearby_honinbo", len(similar), sum(r["occurrences"] for r in similar),
          "album_id_range", min(row[id_i] for row in rows), max(row[id_i] for row in rows),
          "date_range", min(dates), max(dates), "undated", len(rows) - len(dates),
          "source_types", collections.Counter((s[1], s[2], s[4]) for s in source_rows),
          "distinct_source_paths", len({s[3] for s in source_rows}))
PY
shasum -a 256 /Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-name-inventory-prod-v2-20261002.json.gz /Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-name-inventory-clone-v2-20261002.json.gz /Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-event-groups-prod-v4-20261002.json.gz
```

This prints every edition/raw-string count and reproduces 34 raw strings, 1,617 selected associations, 77 distinct non-null round strings, the four round leaders, no null event IDs or duplicate links, and 234 other Honinbo-like values / 1,704 rows in each artifact. The clone's selected raw-value occurrence map was compared directly with production and matched exactly. The table's family bins above are a subsequent manual text triage over those 234 raw values.

## Review state

The proposed identity scope is only the exact 34-member `Honinbo` core group above, with edition and round preserved as separate components. Adjacent aliases remain unresolved, all 1,617 rows have `event_id=null` in the snapshot, and the language candidates in the source memo remain pending editorial review. No reviewer sign-off, selected-event proof, or production display coverage is asserted.
