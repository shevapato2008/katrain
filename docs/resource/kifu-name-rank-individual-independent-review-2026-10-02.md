# Independent review: exact `段位赛` and `个人赛` event values (2026-10-02)

**Decision:** PASS the lexical classification of each *exact raw value* as a possible generic event description; **HOLD a global eleven-language display/import decision for all 1,539 albums**. Neither value establishes a particular tournament identity, and the production duplicate-`GN` audit shows that the stored first label can conceal a different, sometimes named, event description. This review approves no candidate, event ID, catalog link, SGF selection, or database write.

## Frozen scope and conflicting source context

I independently counted exact `event` matches in the protected production v2 inventory at `~/.local/share/kifu-name-audit/2026-10-02/kifu-name-inventory-prod-v2-20261002.json.gz` (internal canonical `sha256` `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`; compressed-file SHA-256 `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`). Snapshot time: `2026-10-01T18:11:45.460901Z`. These are distinct hashes of different representations, not a discrepancy in the triage memo.

| Exact stored `event` | Albums | `event_id` | Visible | Source links | Date span | Nonempty stored round | Different second root `GN` reported in production audit |
|---|---:|---|---:|---|---|---:|---:|
| `段位赛` | 901 | all null | 901 | all `19x19` | 1982-03-23–2002-07-25 | 0 | 891 |
| `个人赛` | 638 | all null | 638 | all `19x19` | 1977-08-25–2002-09-19 | 0 | 26 |

All selected inventory rows have `duplicate_of_id = null`. Example rank rows include album 27998 (`安官旭`–`朴钟烈`, 1993-10-27, `data/kifu-album/19x19/41289188.sgf`) and album 148430 (`周鹤洋`–`朱燕铭`, 1994-06-10, `.../41609778.sgf`). Example individual rows include album 36444 (`曹大元`–`宋雪林`, 1989-09-10, `.../41300346.sgf`) and album 148426 (`周鹤洋`–`朱松力`, 1997-10-07, `.../41609773.sgf`). The inventory gives source-link paths, not source SGF properties or authoritative event definitions.

The [production duplicate-`GN` audit](kifu-name-duplicate-gn-data-audit-2026-10-02.md) reports that the second root `GN` differs from the stored first label in **891/901** rank rows and **26/638** individual rows. Examples include a rank row with `第4届中国棋王战` and an individual row with `一洲杯全国围棋锦标赛个人赛男子组第6轮` as second `GN`. The audit is the available SGF-level evidence for these totals; this review did not obtain or reparse all 1,539 SGF bodies. The **10** and **612** arithmetic remainders are merely “not reported as different second `GN`”; they are **not** verified single-label/plain games or a safe import subset. A different second label may elaborate the generic category, identify another named event, or contain other provenance issues. The [independent duplicate-`GN` remedy](kifu-name-duplicate-gn-remedy-decision-2026-10-02.md) explicitly requires per-game EV, ordered GN, GC, and context comparison for these generic first labels.

## Classification decision per exact value

| Raw value | Lexical classification | Import/display decision | Reason |
|---|---|---|---|
| `段位赛` | **PASS**, generic rank/dan competition description as a word-level category; no shared `event_id`. | **HOLD** all 901 as a bulk generic display batch. | [Sports administration](https://www.sport.gov.cn/n14471/n14482/n14519/c737737/content.html) also uses the longer named `全国围棋段位赛` and dates that series to 1982. This makes a national-series shorthand possible for some records, while the second-GN conflict proves that the first label alone does not govern every game. No edition or source mapping was established for all 901. |
| `个人赛` | **PASS**, generic individual competition format as a word-level category; no shared `event_id`. | **HOLD** all 638 as a bulk generic display batch. | [Sports administration](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c22762310/content.html) calls the national individual championship `全国围棋个人赛` and also abbreviates it to `个人赛` in context. The exact bare value could therefore be shorthand in some games; the different second-GN sample shows that a bare label can conceal a fuller title. No source establishes one identity for all 638. |

The current [`parse_event`](../../katrain/web/kifu/name_parse.py) returns `generic_event_description` for exact `段位赛` / `个人赛` (and traditional-script variants) without an event candidate. [`name_candidates.py`](../../katrain/web/kifu/name_candidates.py) routes these simplified raw values to `rank_event` / `individual_event` when validating a `generic` decision. These are provisional *string classifications*, not checks of each album's effective SGF event. The high-volume [triage memo](kifu-name-high-volume-event-triage-2026-10-02.md) correctly says the bare strings do not identify one championship, but its proposed **901 + 638 row generic-display scope is too broad unless per-game effective-event selection precedes it**. Likewise, absence of `event_id` shows the rows are unlinked, not that the generic first `GN` is the right display event.

## Existing template review (`classification-v1`)

The table reviews only the two relevant strings in each locale, as category descriptions. “Wording PASS” means the text expresses the generic concept adequately; it does not release an album or sign a template-review record.

| Locale | `rank_event` | Wording | `individual_event` | Wording |
|---|---|---|---|---|
| en | `Rank Tournament` | **HOLD**: “rank” can mean standings rather than Go dan grades. Prefer an explicit dan/rank descriptor after category confirmation. | `Individual Tournament` | **PASS**: clear format descriptor. |
| cn | `段位赛` | **PASS**: exact source wording. | `个人赛` | **PASS**: exact source wording. |
| tw | `段位賽` | **PASS**: direct script conversion. | `個人賽` | **PASS**: direct script conversion. |
| jp | `段位戦` | **PASS**: conveys dan-rank competition; not proof of a Japanese named series. | `個人戦` | **PASS**: ordinary individual-format term. |
| ko | `단위 대회` | **PASS**, with idiom review desirable: `단위` denotes Baduk grades, `대회` an event. | `개인전` | **PASS**: ordinary individual-format term. |
| de | `Rangturnier` | **HOLD**: can describe ranking/standing rather than dan grades; Go-specific wording unverified. | `Einzelturnier` | **PASS**: individual tournament. |
| es | `Torneo de grados` | **HOLD**: “grados” is broad and may imply school/qualification grades; Go-specific wording unverified. | `Torneo individual` | **PASS**: individual tournament. |
| fr | `Tournoi de niveaux` | **HOLD**: level-based wording is broader than dan rank. | `Tournoi individuel` | **PASS**: individual tournament. |
| ru | `Турнир разрядов` | **HOLD**: `разряд` can mean a sports classification distinct from Go dan; Go-specific equivalence unverified. | `Личный турнир` | **PASS with register caveat**: conveys individual rather than team play; idiomatic sports usage merits native review. |
| tr | `Seviye turnuvası` | **HOLD**: general level tournament does not clearly convey dan rank. | `Bireysel turnuva` | **PASS**: individual tournament. |
| ua | `Турнір розрядів` | **HOLD**: `розряд` can mean a sports classification distinct from Go dan; Go-specific equivalence unverified. | `Особистий турнір` | **PASS with register caveat**: conveys individual rather than team play; idiomatic sports usage merits native review. |

This agrees with the earlier [eleven-language terminology memo](kifu-name-generic-event-11lang-review.md) that the European rank renderings are provisional. The [Nihon Ki-in](https://www.nihonkiin.or.jp/event/area/ichigaya/2026_10.html) uses `段級位` for rank grades, while [Korea Baduk Association rules](https://www.baduk.or.kr/story/gameRule.asp) distinguish `개인전` from `단체전`; these support the Japanese/Korean semantic components, not an identity claim for Chinese source games. No immediate code replacement is justified: a new English or European wording would itself need native Go-domain review, and the album-level source selection remains the blocking issue. Avoid changing `classification-v1` or signing any of its templates from this memo alone.

## Finite next boundary

The maximum *review queue* is the **1,539 exact simplified raw-value albums**, split into 901 and 638 members, with no traditional variants, substring matches, `全国围棋个人赛`, `全国围棋段位赛`, `升段赛`, or other labels added by inference. Within it, the production audit flags **917 different-second-`GN` rows** (891 + 26) for ordered-property review. The other **622 rows** also require a direct source-property check before any safe generic import set can be counted. For each proposed generic-display member, verify its effective EV/ordered GN/GC and source context, preserve any fuller named event or stage separately, then freeze only confirmed category-only members with their current preimages and reviewed locale wording. **Current approved generic import subset: zero albums.** This is a finite HOLD, not a claim that all 1,539 are misclassified.
