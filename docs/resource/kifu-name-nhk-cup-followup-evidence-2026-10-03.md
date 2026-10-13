# NHK Cup source follow-up: Korean, Traditional Chinese, and six-language structure

Research date: 2026-10-03. This supplements the source and scope review in [the bounded NHK Cup memo](kifu-name-nhk-cup-11lang-research-2026-10-03.md) and independent review `kifu-name-nhk-cup-bounded-source-independent-review-sol-2026-10-03.md`. Research only: no event identity, localized full title, generated display string, owner, alias, album link, or database write is approved here.

## Frozen occurrence scope

Retain the independently checked finite subset: 647 album slots / 115 explicit raw strings for subsequent item-level binding. Keep the one `single_edition_fragment`, raw `日本第43期NHK杯快棋赛`, outside the subset on HOLD. The full priority scope remains 648 slots / 116 raw strings; these are not identity/alias counts. The independent review corrects the edition inventory to 3, 6–9, 11–30, 32–33, 35–45, 47–59, and 63–67. Eight explicit raw strings (61 slots) have no round; keep round nullable. Observed rounds are 1–3 only. Do not map round 1/2/3 to quarterfinal, semifinal, or final. Frozen gzip SHA-256: `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`; grouping-artifact content SHA-256: `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`; embedded inventory SHA-256: `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`.

## Follow-up source captures

New raw captures are outside the repository at `/Users/fan/.local/share/kifu-name-audit/2026-10-03/nhk-core-followup-captures/`, directory mode `0700`, body and manifest files mode `0600`. UTC timestamps, HTTP status, byte size, final URL, and SHA-256 are recorded in its `manifest.json`.

| Language | Exact evidence | Source class and confidence | Capture |
|---|---|---|---|
| Korean (`ko`) | `1997년 : 제44기 NHK배 우승` (1997: 44th NHK Cup champion). | [Korea Baduk Association player record for Wang Licheng](https://www.baduk.or.kr/record/player_view.asp?pkey=20000028), a professional federation record. This is event-specific Korean professional evidence for the compact base `NHK배`, not the full string `NHK배 TV 바둑 토너먼트`. The profile identifies Wang as a Japan-affiliated professional, and cross-language records corroborate the event/result context. Compact base is source-supported for reviewer consideration; full Korean title remains **HOLD** (Wikipedia-only). | Captured `2026-10-03T01:58:41.302956Z`, HTTP 200, 25,508 bytes, SHA-256 `bac30ee44b619b6d65c1f676be649d8b1875371abbd4cdde0b734cf8850a6fc3`. |
| Traditional Chinese (`tw`, `zh-Hant`) | Haifong publishes `第65回NHK杯優勝` in a player's results. | [Haifong Go Institute page](https://www.haifong.org/news/content/18E64F5ECB046179BCAC5B3C2531710B) is a Taiwan professional Go institute, but the cited results lines are Japanese text embedded in its Traditional Chinese page. This verifies that the Taiwan professional site carried the compact glyph string; it does not establish native Traditional Chinese event naming. Expanded `NHK杯電視圍棋淘汰賽` remains Wikipedia-only and **HOLD**. No better event-specific Traditional Chinese professional phrasing was captured in this short follow-up. | Captured `2026-10-03T01:58:43.662095Z`, HTTP 200, 34,061 bytes, SHA-256 `9e454d67519d93b5d8f2b1d6001099e6684a5d0ad77499c3682de38f8604617f`. |

The Korean source identifies the relevant person and event result but its compact `NHK배` occurrence alone cannot justify expansion. The Japanese official page names the event and its organizer (`NHK杯`, full heading `第74回 NHK杯テレビ囲碁トーナメント戦`); see [Nihon Ki-in](https://www.nihonkiin.or.jp/match/nhk/074.html). That page was captured at `2026-10-03T01:40:18.495848Z`, HTTP 200, SHA-256 `2aa660d07433a35dce32b58d7920b5072d7ddae6392676194fd0b88fac968331`.

## Safe structural rule for `de`, `es`, `fr`, `ru`, `tr`, `ua` (`uk`)

No localized full base or lexical tournament/stage wording is proposed. Reuse only the reviewed source-backed invariant token `NHK Cup` as a canonical base token, preserve the edition as an integer, and preserve an observed round 1–3 as a separate integer; use null when a source row has no round. Keep any future phase vocabulary as a separate enum backed by the Japanese organizer's labels, not inferred from raw rounds. Do not translate `Cup`, `Go`, or `round`, transliterate `NHK`, infer locale-specific inflection/word order, or join fields into a display string in this tranche. Apply this same narrow rule to each of the six locales; it is a data-composition constraint, not a language-level translation result.

The Japanese organizer labels the main-table stages `1回戦`, `2回戦`, `3回戦`, `準々決勝`, `準決勝`, `決勝`; see the captured 74th edition page linked above. The frozen source data supports nullable round numbers 1–3. It does not establish that these raw round numbers correspond to any later bracket phase labels. Preserve source edition number as a separate integer; do not convert edition to a year.

## Per-language disposition and next action

| Language | Current follow-up status | Next actionable review |
|---|---|---|
| `ko` | Compact `NHK배` supported by Korea Baduk Association player result; full event title remains **HOLD**. | Independent Korean Go editor may assess compact-base wording. Do not register the Wikipedia full title without a professional/official event-specific source. |
| `tw` | Compact glyph string appears in a Taiwan institute record, but the cited phrase is Japanese; native Traditional Chinese naming and expansion both **HOLD**. | Seek a Traditional Chinese professional Go result/report that uses NHK in Chinese prose; otherwise keep unresolved. |
| `de`, `es`, `fr`, `ru`, `tr`, `ua` (`uk`) | Structural-only rule above; no localized full names or negative-search conclusions. | Reviewer may approve the integer/nullable field composition only. Any locale-specific surface form needs independent vocabulary and language review first. |

All prior controls remain: exact source-slot counts are not evidence of 648 same-event identities; inspect each album's game provenance before binding, and keep the fragment on HOLD. No code or database changes were made.
