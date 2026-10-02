# Honinbo seven edition rules: independent content review — 2026-10-03

**Content PASS: `tw ko es fr tr ru ua`. HOLD direct final-rule signing of the current packets pending the record corrections below.** The proposed wording is acceptable for standalone Honinbo edition labels, editions 1–34. This approves language content only; it does not sign a code schema, production rule artifact, name candidate or bundle.

Reviewer: `/root/oza_ua_display_decision_astra`, parent-configured `gpt-6-astra` / max, without runtime attestation. Reviewed at `2026-10-02T16:34:40Z` (2026-10-03 locally). Producers `/root/honinbo_grammar_luna` and `/root/honinbo_ru_ua_grammar_sol` are different agents. Inputs: [Luna research](kifu-name-honinbo-composition-rule-research-luna-2026-10-02.md), [Sol Russian/Ukrainian research](kifu-name-honinbo-ru-ua-grammar-research-sol-2026-10-03.md), their retained bodies/manifests/proposals, and the previously approved base candidates.

## Language decisions

`N` is the Arabic edition number. Spaces shown below are single spaces. The proposed 1/17/34 examples all match these patterns exactly.

| Locale | Decision and accepted pattern | Body evidence, application and limits |
| --- | --- | --- |
| `tw` | **PASS** — `第N期本因坊戰` | The [周俊勳 table](https://zh.wikipedia.org/w/index.php?title=%E5%91%A8%E4%BF%8A%E5%8B%B3&oldid=92452674) visibly uses Traditional Chinese `第21—34期` and `第1期`. Prefix `第N期`, no separating spaces, and unchanged `本因坊戰` are natural. The table is uncited and concerns Taiwanese titles: it establishes observed construction, not Honinbo identity or an official complete label. Correct the page-language scope below. |
| `ko` | **PASS** — `제N기 본인방전` | The [National Institute of Korean Language notice](https://www.korean.go.kr/front/board/boardStandardView.do?b_seq=714&board_id=4&mn_id=17&pageIndex=153) has Korean prose and `제1기 해외통신원`. It supports attached `제N기` followed by a space. Apply the already established Honinbo `期` unit, also seen in the earlier Korean Go history packet. This is a grammatical composition with the approved Hangul base; the notice is about a cohort, not Go. |
| `es` | **PASS** — `N.ª edición del Torneo Hon'inbō` | [FundéuRAE](https://www.fundeu.es/recomendacion/numero-ordinales-claves-de-escritura/) supplies the analogous feminine ordinal + `edición del Festival` construction. `edición` controls feminine `ª`; use a period, then `ª`, then a space. `del` suits masculine `Torneo`. Keeping the approved base's capital `T` is an explicit catalog-name style choice. `edición del Torneo` naturally distinguishes an edition from its series; no wording change is required. Fix the copied excerpt below. |
| `fr` | **PASS** — `1re édition du Tournoi Hon'inbō`; otherwise `Ne édition du Tournoi Hon'inbō` | The [Académie française](https://www.academie-francaise.fr/abreviations-des-adjectifs-numeraux) supports feminine `1re` and ordinal `e`. Choose `deuxième`, hence `2e`, for this continuing series; `2de` is the abbreviation of the alternative `seconde`. `édition` is feminine and `du` contracts `de + le` before masculine `Tournoi`. The retained page also uses feminine `La 10e édition`. Retain capital `T` as the selected base-name style. This longer construction is natural; plain-text suffixes need no period. |
| `tr` | **PASS** — `N. Honinbo Turnuvası` | [TDK](https://yazim.tdk.gov.tr/content/09-noktalama-isaretleri.html) explicitly assigns ordinal meaning to a numeral followed by a period; its examples also show a following space and noun. The prefix and preserved proper-name capitalization/terminal dotless `ı` are natural. Do not add a second written ordinal suffix. This is punctuation evidence, not a published Honinbo label. |
| `ru` | **PASS** — `N-й турнир Хонинбо` | [Milchin/Cheltsova § 6.2](https://img.artlebedev.ru/izdal/spravochnik-izdatelya-i-avtora/Milchin-Numbers.pdf), PDF p.12 / printed p.149, supports the numeric ordinal ending. The retained [Chess Federation list](https://ratings.ruchess.ru/tournaments) contains lowercase `1-й турнир` within a sports entry. Masculine nominative `-й`, one following space, lowercase generic `турнир` and capital `Хонинбо` are appropriate here. The list's exact captured query is retained in the manifest. |
| `ua` | **PASS** — `N-й турнір на звання Хон'імбо` | The [official orthography linked by the Potebnia Institute](https://www.inmo.org.ua/pravopys-2026.html), PDF § 106 / p.119, supports digit + hyphen + inflected ending; the [Kharkiv government sports report](https://kharkivoda.gov.ua/news/101010) supplies `17-й міжнародний турнір`. Use masculine nominative `-й`, one space, lowercase generic `турнір`, unchanged `на звання` and the approved proper name/apostrophe. |

For Russian and Ukrainian, the ordinal modifies the generic tournament noun in the complete display phrase. I accept lowercasing only that noun (`Турнир`/`Турнір` → `турнир`/`турнір`); the proper name remains capitalized. Ukrainian § 52, visually checked on p.72, does not expressly settle this numeric-prefix case. The lowercase decision is a documented editorial application supported by the sports usage, not a quotation of an explicit exception in § 52. This does not authorize changing either standalone base record. These rules concern nominative labels, not case-inflected phrases embedded in sentences.

## Completed checks and pinned inputs

All **ten** retained response byte lengths and SHA-256 values match their manifests. Actual bodies are Chinese with a Traditional Chinese cited table, Korean, Spanish, French, Turkish, Russian and Ukrainian respectively. French uses `xml:lang="fr"`; several other pages lack a useful HTML language attribute, so their language was verified from actual text. I extracted and visually checked the Russian PDF p.12 and Ukrainian PDF pp.72/119, verified the institute page's link to the exact retained Ukrainian PDF file, and rechecked the institute/Académie pages online.

All seven approved-base line hashes match the original JSONL **including each trailing LF**; the base file SHA-256 remains `ec2ba3cde0405df692e1d400c0fc324e63bd4befe60c44acecc44caaace86bfe`. I independently expanded all **238** outputs for 1–34: exact sample agreement, preserved base characters except the two declared initial-noun changes, correct spacing and no duplicates within a language. French has `1re`, then `2e … 34e`, including `11e/21e/31e`; Russian/Ukrainian retain `-й` also at `3/13/23/33`. Spanish uses `ª`, not a degree sign or masculine `º`.

Paths below are under `~/.local/share/kifu-name-audit/2026-10-02/`.

| Input file | Recomputed byte SHA-256 |
| --- | --- |
| `honinbo-composition-grammar-luna-20261003/source-manifest.json` | `b926cc55b51ce889319c5d2fc5aca521a3d6ffb1e2ec13cb2ce781dfa21e8530` |
| `honinbo-composition-grammar-luna-20261003/rule-proposals.pending.json` | `49e2b90ba9ab234611155856dd4bd4a1ee1370a8f55eba12e6360b9323f36e3b` |
| `honinbo-composition-grammar-sol-20261003/source-manifest.json` | `25d812ccd393eb523a512f0ce0d62f00f68ba63c66d7c8570bf863f97a1b668d` |
| `honinbo-composition-grammar-sol-20261003/rule-proposals.pending.json` | `4d8ff4c3fe05847ff49c7b9014eef5666361d98c299d079c1ac51557d1a62302` |

## Required producer corrections before final-rule signing

1. **TW language scope and article revision.** In Luna's `source-manifest.json`, `sources.tw.body_language`, and the copied `rules[0].source.body_language`, the value `zh-Hant` overstates the whole page: its HTML declares `lang="zh"` and other passages contain Simplified Chinese. Record the page's actual Chinese/mixed-script scope separately from the **reviewed Traditional Chinese excerpt**; make the language-basis explanation explicit. Preserve body hash `229c97ce910e9e111b5fdda1e0443c21f44b3f4fcaa375089ffab9a0fb983fc3` and add the actual retained `wgRevisionId: 92452674`. The target excerpt supports the grammar; no new wording is needed.
2. **ES exact excerpt.** Luna's `rules[2].source.excerpt` omits `al`: the body reads `sustantivo al que acompañan`, whereas the proposal has `sustantivo que acompañan`. Correct the excerpt from the retained body, preserving body hash `51c54320c33b508eb2aeffc3bb65ef50eef02c7bab63236334e7d8ad6ff43b44`. Update the new-version source explanation accordingly; the display rule remains unchanged.
3. **Five misleading content-hash boundaries.** Each Luna `rules[i].rule_content_sha256` currently equals canonical SHA-256 of the entire rule minus only `rule_content_sha256`. It therefore includes `status`, `reviewer_id: null` and `reviewed_at_utc: null`, contrary to the memo's statement that review fields are excluded. Define an explicit immutable content payload in the finalized format, separate its approval/status fields, and recompute the five hashes and enclosing references. Do not silently reinterpret the existing hashes as hashes of that future payload. The affected original values are pinned below.

| Luna rule | Original `rule_content_sha256` |
| --- | --- |
| `honinbo-edition-tw-v1` | `2ed514d46fd9bfb50a1e9b40810b29c9bf17c44d4cdd9dd8bb26af174391c0a6` |
| `honinbo-edition-ko-v1` | `fb820fe7297cf37cb789a8299621efabdfe91f246bbcfa60535ae29d5acba231` |
| `honinbo-edition-es-v1` | `c889b4b3c341d8e20937800597faf6327b8d79fe9c600866e94d8b9bf0f5100f` |
| `honinbo-edition-fr-v1` | `2700e6e7cc7d905baa3bb6a75914aa468b1ba23e354c8f8fda106cb049731103` |
| `honinbo-edition-tr-v1` | `8b8b1b0adb79d1666553ac0555497a1c6b64e4286ec9e6dfb6cacf4c05a0cf07` |

Have the original producer issue new corrected records and obtain independent re-review. Preserve the old bodies and packets. The current proposals **cannot be directly signed as final rules**. No code, database, existing artifact or producer identity was changed; no production signatures were issued.
