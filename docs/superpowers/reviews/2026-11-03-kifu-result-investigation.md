# Kifu result investigation — 2026-11-03

Investigation only. No product code, SGF, database, locale, or plan changes were made. Systematic debugging was used to trace the value and reproduce the formatter behavior before recommending a bounded repair.

## Finding

Bare `B+` / `W+` are valid SGF results: the winner is known, but the score and winning method are unspecified. They must display the existing localized winner label, without inventing resignation, a score, or a scoring unit. The [SGF FF[4] RE definition](https://www.red-bean.com/sgf/properties.html#RE) explicitly makes the score optional and separately defines resignation, timeout, and forfeit.

The shared formatter requires a nonempty suffix in `/^([BW])\+(.+)$/i` (`katrain/web/ui/src/utils/resultTranslation.ts:114`). Bare wins therefore miss the SGF branch and reach the raw-string fallback. This affects both library screens. Kiosk additionally omits bare wins from `otherWinner`, leaving the winner styling unset.

## Evidence and limits

The input was the existing compressed production snapshot `/tmp/kifu-preview-investigation/prod-full.jsonl.gz`, read as a stream. No files under `data/kifu-album` were read or enumerated. The snapshot contains 176,949 albums; applying the API's public-list predicate (`duplicate_of_id IS NULL AND list_hidden_reason IS NULL`) leaves 176,690. It has 363 distinct root `RE` values, including missing and empty values.

The snapshot **does not contain the DB `result` column**. Counts below describe root SGF `RE`, not a complete DB-column equality audit. Root extraction used the repository's SGF tokenizer and unescape behavior; representative records were independently checked with `SGF.parse_sgf`. The import/storage/API code below establishes the intended unchanged mapping.

| Raw RE | All albums | Public albums | Public raw-name Wu subset |
| --- | ---: | ---: | ---: |
| `B+` | 52 | 51 | 3 |
| `W+` | 74 | 72 | 2 |
| `b+` | 8 | 8 | 0 |
| `w+` | 10 | 10 | 0 |
| **Bare wins total** | **144** | **141** | **5** |

The Wu subset means raw `PB`/`PW` matching 吴清源, 吳清源, Go Seigen, or Wu Qingyuan. It contains 1,246 public records; this is not claimed to equal the prepared-search endpoint's canonical identity membership.

Bare wins occur in current and historical sources. Of the 141 public records, 65 have the `19x19` source-path prefix, 4 `Go_Seigen`, 4 `CWI_Dosaku`, 2 `CWI_Jowa`, 1 `CWI_Shusaku`, 43 `CWI_History_Full`, and 22 `CWI_1950_1978`. The issue is therefore relevant to the requested Starpoint/19x19 source standard, including future imports.

Full-parser-verified raw examples (only selected root properties shown):

| Album | PB | PW | DT | RE | RU |
| --- | --- | --- | --- | --- | --- |
| 24658 | Ida Isaburo | Go Seigen | `1947-07` | `B+` | absent |
| 24621 | Fukuda Yasuo | Go Seigen | `1943-04-17` | `W+` | absent |
| 25939 | 天狗 | 逸乐 | `2020-12-07` | `b+` | absent |
| 25938 | 隐智 | 采薇 | `2020-12-07` | `w+` | absent |

Other public Wu bare-win examples are 25046 (`B+`, Go Seigen–Cho Chikun, 1976-11-20), 25050 (`W+`, Akimoto Shinji–Go Seigen), and 152117 (`B+`, Go Seigen–Cho Chikun, 1976-11-20). Duplicate identity policy is a separate investigation; these counts preserve the existing public-list predicate.

## Value path

1. `scripts/import_kifu.py:112` assigns `root.get_property("RE")` directly to `result`. Incremental metadata derivation does the same in `katrain/kifu_ingest/preparation.py:119`; SGF/source conflicts are handled separately rather than reinterpreting a win as resignation.
2. `KifuAlbum.result` is a nullable `String(64)` in `katrain/web/core/models_db.py:1130`. Raw `sgf_content` is retained independently.
3. `KifuAlbumSummary.result` is `Optional[str]` (`katrain/web/api/v1/endpoints/kifu.py:139`). Both prepared and legacy list paths converge on `_summary`, whose `model_validate(record)` copies the scalar; its updates localize names/ranks/rounds, not the result (`:941`). The preview is built from the same summary. The remote dispatcher forwards the response.
4. `katrain/web/ui/src/api/kifuApi.ts` returns JSON without result normalization. Both screens use this API.
5. Kiosk `KifuPage.tsx:314` calls `listResult(a.result, t, a.rules, lang)` and sends its label and winner to `RecordMatchLine`. `listResult` delegates non-resignation labels to the shared formatter, while `otherWinner` (`listRecordPresentation.ts:61`) recognizes detailed SGF wins but excludes empty suffixes.
6. Galaxy `KifuLibraryPage.tsx:58` calls `translateResult` in the card badge; its selected-preview header calls the same helper at `:437`. Its badge currently chooses color from the raw prefix, so uppercase bare wins receive color even while their label remains untranslated. Lowercase prefixes do not receive equivalent color treatment.
7. `useTranslation` delegates to `i18n.t`, using loaded PO translations, then the supplied fallback. Existing catalogs already contain the relevant keys.

Direct execution of the current TypeScript helpers reproduced these outputs:

| Input | Shared formatter with cn catalog | Kiosk list result |
| --- | --- | --- |
| `B+` | `B+` | `{label: 'B+', winner: null}` |
| `W+` | `W+` | `{label: 'W+', winner: null}` |
| ` b+ ` | `b+` | `{label: 'b+', winner: null}` |
| `B+R` | `黑胜中盘` | `{label: '黑中盘胜', winner: 'B'}` |
| `W+banana` | unchanged | winner `null` |

The working detailed-win case and failed bare-win case isolate the nonempty-suffix assumption. Translating the stored data, appending `R`, or inferring a score from move count would change the record's meaning and is unnecessary for this repair.

## Locale reuse

Return `result:black_win` / `result:white_win` directly for a bare win. Do not strip a trailing plus from an existing locale label: several locales intentionally use their own SGF-like notation. The fallback should remain `B+` / `W+` when translations are unavailable.

| Locale | Existing black / white labels |
| --- | --- |
| cn | 黑胜 / 白胜 |
| tw | 黑勝 / 白勝 |
| en | B+ / W+ |
| jp | 黒勝 / 白勝 |
| ko | 흑승 / 백승 |
| fr, es | N+ / B+ |
| de | S+ / W+ |
| ru, ua | Ч+ / Б+ |
| tr | S+ / B+ |

All 11 catalogs have these keys. No new catalog entries are required. The existing `review:*` fragments are for the Kiosk Chinese resignation wording and must not be used to imply a method for bare wins.

## Related observed parser defects and conservative fallback

These are the bounded defects found at the same result-parsing boundary; they merit focused fixes in the shared helper, without replacing the entire result grammar.

| Actual root RE | Public count | Verified album | Current cn output | Required conservative interpretation |
| --- | ---: | ---: | --- | --- |
| `W+11.5?` | 1 | 25057 (Go Seigen) | 白胜11.5 | Preserve the raw uncertainty suffix; do not assert an exact score. |
| `B+1?` | 1 | 173006 | 黑胜1 | Preserve `?` as above. |
| `白胜4分之1子` | 1 | 149547 | 白胜4子 | Arabic denominator-first fraction is 1/4, not 4. |
| `白胜1\/4子` | 1 | 26132 | 白胜1子 | Recognize the escaped slash as the fraction separator; 0.25 子. |
| `黑胜3\/4子` | 1 | — | 黑胜3子 | Same observed escaped-separator form; 0.75 子. |

`parseFloat` at `resultTranslation.ts:124` accepts a numeric prefix and drops the remaining suffix. Chinese parsing similarly uses prefix matches and falls through to decimal parsing (`:17–58`), so an unrecognized fraction becomes its first integer. This can produce false precision or a wrong margin.

The small repair boundary is: accept an SGF numeric detail only when the entire detail matches the supported numeric syntax, then convert it; otherwise preserve the original string. For Chinese results, normalize the observed escaped fraction separator, recognize Arabic `denominator分之numerator`, and match the whole score after removing only a recognized final unit. Retain the existing mixed-fraction, fraction, Chinese-text fraction, `目半`, and decimal cases. Reject zero denominators/nonfinite results rather than falling through to an integer. An unknown suffix or annotation should remain raw, preserving its evidence. This avoids silently deleting penalty annotations while keeping their interpretation outside scope.

Other observed variants illustrate why broad inference is unsafe: `N+R` (4 public), `WB+R` (1), `Both lost` (1), `W+ (but Black does not lose)` (1), unqualified scores such as `185`, and penalty prose. Preserve these raw unless separately specified. `Unfinished` (168 public), `Game suspended` (26), `Unknown` (2), `Left unfinished` (1), and `Incomplete` (1) are also currently raw fallbacks; this investigation does not equate these distinct states with a resignation or a known winner.

Chinese variants such as `白棋中盘胜` (34 public) and `黑棋中盘胜` (27) are recognized by Kiosk's list-only resignation helper but remain raw in the shared formatter/Galaxy. Chinese point-order variants and `半目` also remain raw. These are localization coverage differences, not evidence that the stored game data should be rewritten. Any expansion should be bounded by explicit forms and tests rather than first-color heuristics.

## Minimal implementation and verification scope for the plan author

- Extend the shared SGF branch to accept an empty detail and return the existing winner key in that case; retain trimming and case-insensitivity. Extend Kiosk's complete-result winner recognition for the same bare form. Keep malformed nonempty suffixes unrecognized.
- Apply the bounded full-numeric-match and fraction repairs above in the same shared helper. Preserve valid score units and raw unknown suffixes. No backend schema, importer, data rewrite, new locale, or generalized parser framework is necessary for these display defects.
- Add shared-helper cases for `B+`, `W+`, lowercase/outer whitespace, cn/tw and an SGF-notation locale, plus missing-translation fallback. Check `B+R` still means resignation and `W+banana` remains raw.
- Add strict-score cases for `W+11.5?`, `B+1?`, an invalid trailing word, valid `W+0` / `B+2.5`, `白胜4分之1子`, both observed escaped fractions, existing `黑胜2又3/4子`, `白胜二又四分之一子`, `白胜3目半`, and an annotated score remaining raw. One zero-denominator guard is sufficient; no fuzzing layer is needed.
- Add Kiosk helper assertions that bare wins return winner `B` / `W` while unknown suffixes keep winner `null`. Add one focused bare-win fixture/assertion in each existing screen localization suite, including the Galaxy preview label. A representative cn/tw rendering plus an SGF-notation locale is sufficient; no new browser harness or full visual matrix is warranted.

Existing baseline command:

```sh
npm test -- src/utils/resultTranslation.test.ts src/kiosk/utils/listRecordPresentation.test.ts src/kiosk/__tests__/KifuPage.localization.test.tsx src/galaxy/pages/KifuLibraryPage.localization.test.tsx
```

Result: **27 passed, 1 failed across 4 files**. The existing failure is Galaxy `重复点击已选卡仍保留棋盘预览` (`KifuLibraryPage.localization.test.tsx:167`): `getAlbum` was called twice instead of once. This is independent of result translation and was reported to the parent investigation. The result helper currently has only one unit test (scoring-unit fallback); neither library suite covers bare wins. No changes were made to make the baseline pass.

Derived census artifact: `/tmp/kifu-preview-investigation/result-variants-summary.json` (counts and selected root metadata only; no SGF body dump).
