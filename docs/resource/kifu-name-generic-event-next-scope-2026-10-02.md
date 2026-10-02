# Next scope: high-frequency non-proper event labels (2026-10-02)

## Purpose and evidence boundary

This is a read-only scope memo over the frozen production snapshot described in [the Top 100 inventory](kifu-name-event-top100-readonly-batch-2026-10-02.md) and its controlled files under `/Users/fan/.local/share/kifu-event-inventory/2026-10-02/`. The snapshot was captured from `kifu_albums` on 2026-10-02; `top100.jsonl` SHA-256 is `a85748683cf754f9da3a8ac1673cd661f314cb49ca03cd7d03ec9bb703da2381`. Counts below are affected games for exact raw values, except the null event count. They are not identity approval or translation coverage.

The existing [11-language review of 段位赛 / 个人赛](kifu-name-generic-event-11lang-review.md) covers those two labels and their provisional terminology only. This memo extends scope to neighboring frequent values, keeps historic labels separate, and does not propose tournament IDs or approve any candidate.

## Frozen counts and provisional class

| Exact raw event / condition | Games | Dates in snapshot | Provisional reading | Safe current direction |
|---|---:|---|---|---|
| SQL `event IS NULL` | 2,811 | — | Absent metadata | Keep hidden / empty display; do not conflate SQL NULL with literal strings without inspecting the full snapshot. |
| `GNUGo3.8` | 1,160 | 1959-02-24–2024-02-20 | Software/source label; not a competition name | Hide as source metadata. Ask importer/source owners why engine version landed in event. The second-GN examples and the 1,160-game legacy selection work are a separate recovery path; do not create an event alias from this label. |
| `段位赛` | 901 | 1982-03-23–2002-07-25 | Rank/grade competition descriptor | Candidate for generic template after checking source context; see prior memo. |
| `个人赛` | 638 | 1977-08-25–2002-09-19 | Individual-format descriptor | Candidate for generic template after checking source context; see prior memo. |
| `团体赛` | 324 | 1900-01-01–2002-04-25 | Team-format descriptor in isolation | Candidate for generic template, but its broad date span and single source group make source-dataset semantics important. Do not infer it means one recurring team championship. |
| `升段赛` | 125 | 1960-04-20–1996-04-24 | Promotion/rank-advancement descriptor | Candidate for generic template only if source confirms it is a category rather than shorthand for a named promotion event. |
| `Hoensha game` | 595 | 1879-05-11–1900-05-09,06-06 | Historical institution/event label or editorial source label; ambiguous | Hold identity and display classification. Needs game-level bibliography and source-field definition. |
| `Castle Game` | 539 | 1624,1630–1863 | Historical match/context label; ambiguous | Hold identity and display classification. Appears in four source groups (`CWI_Dosaku`, `CWI_History_Full`, `CWI_Jowa`, `CWI_Shusaku`); establish whether it is one named series, a class of castle games, or editorial shorthand. |
| `10-game match` | 245 | 1706-02–1955-03-24,25 | Match-format description, possibly used as a historical series/event label | Do not treat as a generic competition template from wording alone. Four source groups (`CWI_1950_1978`, `CWI_History_Full`, `CWI_Jowa`, `CWI_Shusaku`) indicate distinct source contexts; inspect records individually. |

The four Chinese format/rank labels (`段位赛`, `个人赛`, `团体赛`, `升段赛`) total **1,988 games** (Top 100 ranks 2, 3, 14, and 42). This matches the prior inventory's “generic competition category” bucket; it is a triage bucket, not proof that every use is generic. The three ambiguous historical English labels above total **1,379 games**. Including `GNUGo3.8`, the requested non-proper / non-event-like worklist accounts for **4,527 games**; this subtotal excludes the 2,811 SQL-NULL rows and is not a complete inventory of every non-proper value in the full 50,222-value corpus.

## Parser and template implications

`parse_event` currently recognizes only empty values, SGF fragments, GNU Go / Engine version labels, the Oteai date form, four exact Chinese generic values (`段位赛`, `段位賽`, `个人赛`, `個人賽`), and game-result text. It does **not** classify `团体赛`, `升段赛`, `Hoensha game`, `Castle Game`, or `10-game match`; those currently fall to `unclassified_pending`. Candidate decision validation permits `hidden` for `empty` / `program_source_label` and `generic` for `generic_event_description` only. Therefore expanding approved generic templates requires a reviewed category rule and eleven-language display wording; adding translations alone would not make those values safely classifiable.

Conservative template choices for a future review:

1. Retain the existing `rank_event` and `individual_event` templates as provisional terminology, but do not turn the raw labels into event entities. The current review already records unresolved source-identity risk and European-language register concerns.
2. If source context establishes category usage, add separate generic templates for “team competition” and “dan promotion / promotion tournament” rather than mapping either to a named event. Keep source label visible through the candidate record and exact raw scope.
3. Keep software/source labels hidden and traceable as source metadata; never translate the software version as an event.
4. Do not template the historical English strings until sources prove whether they describe an institution, event series, match format, or cataloger's annotation. A generic-sounding English noun phrase can be a normalized label for a set of named historical games.
5. For all eleven languages, ask native Go-domain reviewers for category wording only after the category is established. Preserve local distinctions between event, match, rank promotion, individual, and team formats. Do not create canonical IDs to make the display work.

## Counterexamples and guardrails

- A game can have `GN[GNUGo3.8]` followed by a second `GN` containing a real event. The engine label is not the game identity; selection of the second value is separately provenance-bound and must not be generalized to other albums.
- `段位赛` can coexist with a second GN such as `第4届中国棋王战` in import fixtures. The generic-looking first value does not establish that the later event can be discarded or that all `段位赛` rows share one event.
- `团体赛` and `个人赛` describe format, while formal national championships may use those words in their official titles. Exact equality to a short label is not evidence of a shared championship ID.
- `中国围棋全国个人赛` (279 games) and `中国围棋团体赛` (243 games) are distinct exact values already in the Top 100 and have event-series source research. They must not be collapsed into generic `个人赛` / `团体赛` merely because the phrases overlap.
- The historical values span centuries and multiple source groups. A single English phrase may be a database's family label across multiple events or source conventions; aggregate frequency cannot settle identity.
- A broad match-format phrase such as `10-game match` can name a format, a specific match, or a source's label for a collection. Preserve game-level source distinctions until the source key is understood.

## Source work needed before decisions

| Work item | Evidence required | Decision it can support |
|---|---|---|
| `GNUGo3.8` provenance | Importer mapping and original source schema; compare SGF root properties and source file manifests for representative games; retain the separately documented second-GN selection evidence | Confirm it is software/source metadata and define how display hides it while exposing a verified selected event where applicable. |
| Chinese category values | Identify the `19x19` source collection and its category definitions; sample source pages/books across dates and compare labels against explicit event names / second GN / comments | Decide whether each exact raw label is generic, a collection category, or shorthand that needs exceptions. |
| `Hoensha game` | Identify the CWI book/catalog field and inspect representative game citations around 1879–1900; consult contemporaneous Hoensha records or reliable bibliographies | Distinguish Hoensha institution, a named event series, and editorial grouping. |
| `Castle Game` | Resolve the four source groups to their source works and inspect event headings and adjacent records; check whether “castle” marks location, patronage, historical match class, or a formal series | Determine whether the exact string denotes one stable identity or multiple labels; this is high impact because 539 games and four source groups. |
| `10-game match` | Resolve four source groups and each source's use of the phrase; map the 245 games to opponents, dates, match sets, and surrounding headings | Separate match format from named matches or editorial grouping; do not normalize on phrase alone. |
| Eleven-language category terms | Native Go-domain terminology review after source classification, especially `段位赛`, `升段赛`, and the distinction between team/individual event versus match | Approve template wording without implying an event identity. |

## Escalation to parent

Please send **`Castle Game` (539 games, four source groups), `Hoensha game` (595), and `10-game match` (245, four source groups)** to Sol/Astra for identity-focused review. These are not safe to classify from English wording or counts. `GNUGo3.8` is also high impact (1,160), but its software-version syntax and existing parser classification support the provisional source-label reading; the remaining question is importer provenance and second-GN recovery, not a new tournament identity.

No production database was queried during this follow-up, and no code, candidate, catalog, approval, or commit was changed. The source snapshot itself is frozen and read-only; its import source-group labels are clues, not authoritative citations.
