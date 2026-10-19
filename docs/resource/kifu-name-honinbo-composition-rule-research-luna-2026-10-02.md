# Honinbo edition grammar source research — 2026-10-02

This is source research and rule-proposal work for the seven requested locales only. It does not approve any rule, sign a candidate, or authorize import. Five locale packets have retained source bodies (`tw`, `ko`, `es`, `fr`, `tr`). `ru` and `ua` remain pending body capture and review.

## Frozen bases and retained artifacts

The proposals bind exact lines from the independently reviewed base-candidate file at `~/.local/share/kifu-name-audit/2026-10-02/honinbo-final-review-astra-v2/honinbo-series-2026-10-02-candidates.final-reviewed.jsonl` (file SHA-256 `ec2ba3cde0405df692e1d400c0fc324e63bd4befe60c44acecc44caaace86bfe`). Locale base values and exact candidate-line hashes are in the controlled proposal file. The file supplies the five bindings below:

| Locale | Approved base | Base candidate line SHA-256 |
|---|---|---|
| `tw` | `本因坊戰` | `5ce0cede100aeec0e34a7daa297b6ffea63d7707eed76074317c7074e1c4518c` |
| `ko` | `본인방전` | `d11b6e9c0175165d24863d53a28e816ba15b266b125ffb74e3c334adb01eea41` |
| `es` | `Torneo Hon'inbō` | `799a44230f198902944e6ccf585c1c06a90f2e72ab6c07bdc890378966b0bdae` |
| `fr` | `Tournoi Hon'inbō` | `80f0e8f41c2b64250cc2b8013e5c9356c997f4687ac23b402b7a982dc7488c61` |
| `tr` | `Honinbo Turnuvası` | `ea4f4b8c5677e302394159a2fbf8152adbcfece0ce7388b3ea4f399a28ba7407` |

Controlled data is stored mode `0700`/`0600` under `~/.local/share/kifu-name-audit/2026-10-02/honinbo-composition-grammar-luna-20261003/`:

- `source-manifest.json` SHA-256: `b926cc55b51ce889319c5d2fc5aca521a3d6ffb1e2ec13cb2ce781dfa21e8530`
- `rule-proposals.pending.json` SHA-256: `49e2b90ba9ab234611155856dd4bd4a1ee1370a8f55eba12e6360b9323f36e3b`
- The JSON records each proposal-content hash separately, without reviewer/signature fields in that hash; each status is `pending_independent_review`.

## Retained source evidence and proposed wording

Captured times are UTC on 2026-10-02. Body hashes are over the retained response bytes, not a normalized text extraction.

| Locale | URL, actual body language, capture time, body SHA-256 | Exact excerpt and application | Proposed 1 / 17 / 34; limitations |
|---|---|---|---|
| `tw` | [周俊勳](https://zh.wikipedia.org/wiki/%E5%91%A8%E4%BF%8A%E5%8B%B3); `zh-Hant`; `2026-10-02T16:03:54.608016Z`; `229c97ce910e9e111b5fdda1e0443c21f44b3f4fcaa375089ffab9a0fb983fc3` | `頭銜｜年份｜期數｜通算期數` and `名人｜1995年—2007年｜第21—34期｜14連霸中`. This is a Traditional Chinese Taiwan Go profile using `第N期` for a Taiwan Go title. The page marks its Taiwan results section as uncited, so this is an observed usage sample only. | `第1期本因坊戰` / `第17期本因坊戰` / `第34期本因坊戰`. Proposed `第N期` prefix, series unit `期`, no intervening spaces, Traditional Chinese base as approved. Joining the pattern to the Honinbo base is editorial composition; the excerpt does not publish these full labels. |
| `ko` | [국립국어원 제1기 해외통신원 선발 결과 공고](https://www.korean.go.kr/front/board/boardStandardView.do?b_seq=714&board_id=4&mn_id=17&pageIndex=153); `ko`; `2026-10-02T16:03:57.187650Z`; `3c4f34e4b4e39b8da0e44fffdf3246d1cb340c609ca48332f8a9a795237a4a28` | `국립국어원 제1기 해외통신원 선발 결과 공고`. This official Korean heading directly shows `제1기` followed by a space and a noun. | `제1기 본인방전` / `제17기 본인방전` / `제34기 본인방전`. Proposed prefix `제N기`, then one space and the approved Hangul base, with no punctuation. The source does not attest the Go term `본인방전` or the full Honinbo display. |
| `es` | [FundéuRAE, números ordinales: claves de escritura](https://www.fundeu.es/recomendacion/numero-ordinales-claves-de-escritura/); `es`; `2026-10-02T16:03:59.527777Z`; `51c54320c33b508eb2aeffc3bb65ef50eef02c7bab63236334e7d8ad6ff43b44` | `las abreviaturas deben concordar en género y número con el sustantivo que acompañan: 69.ª edición del Festival de San Sebastián, pero 69.º Festival de San Sebastián`. Supports feminine ordinal marking for `edición`, the point plus raised letter, spacing, and lower/upper noun distinction in examples. | `1.ª edición del Torneo Hon'inbō` / `17.ª edición del Torneo Hon'inbō` / `34.ª edición del Torneo Hon'inbō`. Proposed `N.ª edición del` plus the approved base. The source supports the ordinal grammar, not this Go label. `edición` plus a base already containing `Torneo` may sound repetitive; this remains an editorial choice for review. |
| `fr` | [Académie française, Abréviations des adjectifs numéraux](https://www.academie-francaise.fr/abreviations-des-adjectifs-numeraux); `fr`; `2026-10-02T16:04:02.866102Z`; `5464d70aead40c4261b203320e00c9800a152e9f57b2e8ca7706208a0dea1fec` | `premier et première s’abrègent en 1er et 1re` and `toutes les autres formes s’abrègent en e : 3e, 5e, 100e`. Supports `1re` and `e` forms. | `1re édition du Tournoi Hon'inbō` / `17e édition du Tournoi Hon'inbō` / `34e édition du Tournoi Hon'inbō`. Proposed feminine first suffix, `e` thereafter, no period, and spaces around `édition`/`du`. The source establishes abbreviated ordinal form, not a complete Honinbo title; `édition` and `Tournoi` may repeat the same idea. |
| `tr` | [TDK, Noktalama işaretleri](https://yazim.tdk.gov.tr/content/09-noktalama-isaretleri.html); `tr`; `2026-10-02T16:05:16.358025Z`; `9fdb2d2afee084dd200e1f7c927ae5c9f9a6809ebf0c3eb67e9d617eb8c0d8da` | `Sayılardan sonra sıra bildirmek için konur: 3. (üçüncü), 15. (on beşinci)`. The Turkish Language Association states that a point after a numeral indicates order; the examples show the numeral marker followed by a space before explanatory text. | `1. Honinbo Turnuvası` / `17. Honinbo Turnuvası` / `34. Honinbo Turnuvası`. Proposed numeric-period prefix, one separating space, then the approved base. The punctuation rule does not specifically attest edition-title use or this Go label. |

## Open packets: Russian and Ukrainian

The search-result bodies surfaced useful authority leads, but direct body retention did not succeed, so neither locale has a source manifest entry or a rule hash here.

- `ru`: Gramota.ru's [буквенные наращения после цифр](https://gramota.ru/biblioteka/spravochniki/pismovnik/kogda-nuzhny-bukvennye-narashcheniya-posle-tsifr) search excerpt states that masculine ordinal examples take forms such as `1-й вагон` and `5-й уровень`. A direct capture attempt timed out. Before proposing `1-й турнир Хонинбо` etc., retain the page body and independently check lowercase `турнир` against the capitalized proper name.
- `ua`: the Ukrainian Ministry's 2019 orthography [PDF](https://mon.gov.ua/static-objects/mon/sites/1/zagalna%20serednya/05062019-onovl-pravo.pdf) search excerpt states that digit-written ordinals append their inflected ending with a hyphen and gives `5-й поверх`. A direct capture attempt returned HTTP 403. Before proposing `1-й турнір на звання Хон'імбо` etc., retain the body and independently confirm masculine nominative agreement and lowercasing of the generic noun.

These retrieval limits are not evidence that either language lacks a rule or usage. The two rules remain pending. No negative absence claim is made.

## Independent-review boundary

All five retained proposals are unapproved. Independent review must verify the actual source bodies and language, exact 1/17/34 outputs, every applicable inflection/case, ordering, spacing, punctuation, capitalization, and the full 1–34 rendering table. For French, check feminine first separately. For Spanish and the Korean, Chinese, and Turkish proposals, assess whether the retained construction supports the proposed word order without implying an observed complete Honinbo label. Add `ru` and `ua` only after their source bodies are retained and hashed. No candidate generation or database change was part of this research pass.
