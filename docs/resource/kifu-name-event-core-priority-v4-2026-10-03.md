# Frozen v4 event-core priority (2026-10-03)

Read-only aggregation for choosing the next finite event-name batches. Input: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-event-groups-prod-v4-20261002.json.gz`, file SHA-256 `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`, embedded inventory SHA-256 `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`, rule `event-components-v4`.

The aggregation sums all v4 groups sharing the exact `core`; raw variants are the sum of member counts. The reusable count includes `explicit_components`, English ordinal forms, `single_edition_fragment`, `oteai_year`, and `cwi_japan_promotion`. It excludes `unparsed`, `empty`, and other non-component groups. This is prioritization only: no event identity, translation, alias, or production write is approved.

## Top 20 non-excluded cores by affected albums

The explicit exclusions are Honinbo, Judan, Samsung (`三星火灾杯`), and Fujitsu (`富士通杯`). Rows marked unsafe are retained in the ranking to show why raw volume alone is insufficient.

| Rank | Core | Albums | Raw variants | Reusable component coverage | Pattern / scope note |
|---:|---|---:|---:|---:|---|
| 1 | `Oteai` | 6,159 | 49 | 5,584 (90.7%) | `oteai_year` plus 575 unparsed; historical series family, needs boundary review |
| 2 | `Oza` | 2,061 | 103 | 2,058 (99.9%) | ordinal edition/joined/suffix; 3 unparsed |
| 3 | `日本龙星战` | 1,249 | 20 | 1,249 (100%) | edition fragment + explicit components; retain Japan qualifier |
| 4 | `Old Meijin` | 1,199 | 13 | 1,199 (100%) | English ordinal edition; distinct from modern Meijin |
| 5 | `Pro Best Ten` | 1,171 | 12 | 1,171 (100%) | English ordinal edition |
| 6 | `GNUGo3.8` | 1,160 | 1 | 0 (0%) | program/source label; unsafe as event series |
| 7 | `Nihon Ki-in Championship` | 1,156 | 22 | 1,153 (99.7%) | 3 unparsed; historic series boundary required |
| 8 | `Tengen` | 1,014 | 45 | 1,014 (100%) | ordinal edition/joined/suffix |
| 9 | `Meijin` | 927 | 45 | 927 (100%) | ordinal edition/joined/suffix |
| 10 | `段位赛` | 906 | 6 | 5 (0.6%) | generic rank description; unsafe shared identity |
| 11 | `Kisei` | 899 | 52 | 898 (99.9%) | 1 unparsed; ordinal edition/joined/suffix |
| 12 | `日本王座战预选` | 725 | 39 | 725 (100%) | explicit edition/round/stage components |
| 13 | `日本大手合` | 721 | 39 | 718 (99.6%) | 3 unparsed; historical Oteai boundary |
| 14 | `日本NHK杯快棋赛` | 648 | 116 | 648 (100%) | explicit edition/round; 1 edition-fragment variant |
| 15 | `个人赛` | 638 | 1 | 0 (0%) | generic individual-format description |
| 16 | `日本本因坊战预选` | 635 | 59 | 635 (100%) | Honinbo-family stage; excluded from next independent batch |
| 17 | `Gosei` | 624 | 44 | 624 (100%) | ordinal edition/joined/suffix |
| 18 | `Hoensha game` | 595 | 1 | 0 (0%) | organization/archive label, not one tournament |
| 19 | `日本碁圣战预选` | 593 | 36 | 593 (100%) | explicit edition/round/stage components |
| 20 | `日本名人战循环圈` | 593 | 378 | 555 (93.6%) | 38 unparsed; large fragmented raw space |

The generic/unsafe rows (`GNUGo3.8`, `段位赛`, `个人赛`, `Hoensha game`) should not be converted into event IDs. `Oteai` and `日本大手合` may refer to the same historical family but must retain their source distinctions until a boundary review. Stage-labelled cores such as `日本本因坊战预选` are not interchangeable with the title-series core.

## Five promising next finite batches

These are the best unresolved component-backed opportunities after removing the explicit exclusions and obvious generic labels. They maximize reusable coverage while keeping a bounded base, edition, round, or stage grammar.

1. **`日本王座战预选` — 725 albums / 39 raw variants / 100% component coverage.** Edition and stage/round fields are already explicit; review the Japanese professional preliminary-series identity and source-stage semantics.
2. **`日本NHK杯快棋赛` — 648 / 116 / 100%.** High raw-variant count, but one stable base with edition and round components; check whether the single edition-fragment form is within the same Japan NHK Cup scope.
3. **`Gosei` — 624 / 44 / 100%.** Compact ordinal family with a bounded variant set; distinguish the Japanese 碁聖 title series from unrelated “Gosei” labels before localization.
4. **`日本碁圣战预选` — 593 / 36 / 100%.** Explicit edition/round/stage structure and enough volume for a reusable renderer; confirm that all rows are Japanese professional preliminaries.
5. **`日本SGW杯中庸战预选` — 545 / 18 / 100%.** Smaller but exceptionally bounded component set; source review can likely close identity and stage semantics in one finite pass.

`日本名人战预选` (545 / 27 / 100%), `日本天元战预选` (528 / 26 / 99.8%), and `台湾海峰杯职业围棋赛64强战` (481 / 17 / 100%) are the next reserve choices. They remain separate because sponsor, geography, stage, and title-family boundaries need source review.

No new web captures, database reads/writes, code changes, approvals, or deployments were made.

