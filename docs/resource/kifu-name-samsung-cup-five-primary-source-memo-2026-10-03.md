# Samsung Cup series source memo (2026-10-03)

Read-only research for one high-frequency unresolved event series. This memo records evidence leads only. It does not approve an event identity, display names, aliases, candidate rows, production links, or database writes.

## Frozen scope and reusable components

Source group: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/kifu-event-groups-prod-v4-20261002.json.gz`.

- File SHA-256: `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`
- Embedded inventory SHA-256: `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`
- Rule: `event-components-v4`; inventory format `2`; group count `27119`
- Selected core: `三星火灾杯`; grammar `explicit_components`; **228 affected albums**, **22 exact raw members**
- Edition components: `1`–`5`, `7`–`11` (`6` is absent from this finite raw scope); Arabic forms cover 10 edition values, plus one Han-number spelling, `第五届`.
- Round components: `第一轮`/`1轮` normalized by the parser to `一轮` (**153 albums**), `第二轮`/`2轮` to `二轮` (**73**), and `第三轮` to `三轮` (**2**).

Exact raw values and album counts:

| Raw event | Albums |
|---|---:|
| `第10届三星火灾杯第一轮` / `第二轮` | 16 / 8 |
| `第11届三星火灾杯第一轮` / `第二轮` | 16 / 7 |
| `第1届三星火灾杯第一轮` / `第二轮` | 12 / 5 |
| `第2届三星火灾杯第一轮` / `第二轮` | 16 / 8 |
| `第3届三星火灾杯第一轮` / `第二轮` | 15 / 7 |
| `第4届三星火灾杯第一轮` / `第二轮` | 16 / 7 |
| `第5届三星火灾杯第一轮` | 7 |
| `第7届三星火灾杯第一轮` / `第二轮` | 16 / 8 |
| `第8届三星火灾杯第一轮` / `第二轮` | 16 / 8 |
| `第9届三星火灾杯第一轮` / `第二轮` | 16 / 8 |
| `第五届三星火灾杯第一轮` / `第二轮` / `第三轮` | 7 / 7 / 2 |

The parser's reusable shape is `edition + base + round`, with edition-only rows absent in this selected group. The two numeral systems and missing edition 6 require explicit finite-scope review; they must not be generalized to every event containing `三星`.

## Five primary language source captures

Bodies are in `/Users/fan/.local/share/kifu-name-audit/2026-10-03/samsung-cup-five-strict-captures/`, directory mode `0700`, body files mode `0600`. SHA-256 values below are over the saved response bytes.

| Locale | Direct source and witnessed base wording | Pending source-level display lead | Body SHA-256 |
|---|---|---|---|
| `cn` | China's State General Administration of Sport report on the 28th event calls it `三星杯世界围棋大师赛` and identifies the event as an international Go championship. [Source](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c27069198/content.html) | `三星杯世界围棋大师赛` | `ecaf79d7c77ae96620699e99c9bacb50523f575b9d5e58a88e36b352c2b3f8d5` |
| `tw` | Haifong Go Institute's event archive calls the series `三星盃世界圍棋大師賽`, records its 1996 founding, organizer group, sponsor, and historical renamings. [Source](https://www.haifong.org/game/classes/B0A85C728A240460DBA68725773324CF) | `三星盃世界圍棋大師賽` | `16892f3bc817c9aa0238e72dda43b7420a52e11be7c59fdfcef28b61a26f3c6b` |
| `jp` | Nihon Ki-in's historical record identifies `三星火災杯世界囲碁マスターズ`; it separately records the older `三星火災杯世界オープン囲碁選手権` wording for editions 9–13. [Source](https://www.nihonkiin.or.jp/match/sansei/archive.html) | `三星火災杯世界囲碁マスターズ` | `b940ca399e8f9c3f96635fe29a9eecded1e0787a2384a5e93276fd0cde586a33` |
| `ko` | Korea Baduk Association's title history names `삼성화재배 월드바둑마스터스`, gives the Korean organizer/sponsor, and lists editions 1–19 with years 1996–2014. [Source](https://baduk.or.kr/game/game_view.asp?cmpt_code=2104&etcKey=2) | `삼성화재배 월드바둑마스터스` | `930c482d2f4dd9fff4bd4b5e29822e6a3eeaa11263985fc2c0d8f1c3a0a42b9c` |
| `en` | CWI's professional Go archive identifies the recurring event as `Samsung Cup` and lists the synonymous forms `Samsung Fire Cup`, `Samsung Cup World Open Baduk Championship`, and `Samsung Fire & Marine Insurance World Masters Baduk`. [Source](https://homepages.cwi.nl/~aeb/go/games/games/Samsung/) | `Samsung Cup` (compact archive form; longer official-name choice remains open) | `09e2d596715133e67d92ebd14391ada80d8dab0cbfe23cf24742ce2cede927c5` |

The source conflict is historical naming, not a proven identity conflict: Nihon Ki-in records a terminology change after edition 13, while Haifong records the Chinese Traditional sponsor-name changes. The imported Simplified raw stem is compatible with the series, but it is not by itself sufficient to link unrelated Samsung-sponsored events.

## Secondary locale leads (pending, not approved)

For `de/es/fr/ru/tr/ua`, no direct language-specific body was captured in this pass. Reasonable compact leads for a follow-up are `Samsung-Cup`, `Copa Samsung`, `Coupe Samsung`, `Кубок Samsung`, `Samsung Kupası`, and `Кубок Samsung`, respectively, based on the English professional archive's stable `Samsung Cup` stem and standard local rendering of “cup.” These are transliteration/translation work queues only; they must remain unresolved until a language-specific Go federation, professional archive, or comparable specialist source witnesses the exact form.

## Conflicts and blockers

1. `三星火灾杯` is also used in source collections for Taiwan qualifiers and other Samsung-branded stages. The 228-row scope is finite and must be checked against source paths and full raw event structure before any association.
2. The selected group has no edition 6 and no per-row dates in the v4 artifact. This does not establish that edition 6 is absent from production or that all included rows are correctly staged.
3. Edition wording differs (`届` versus `第五届`), while round wording differs in Arabic/Han numerals. A reviewer must validate the parser's finite component decomposition before reuse.
4. Japanese historical naming and Chinese Traditional sponsor naming changed over time. A single timeless full name would erase source-attested history; the compact base choice needs independent review.

## Next translation batch potential

This is a concrete **228-album / 22-raw-value** batch once identity and scope review pass. The shared base plus edition/round renderer could cover 228 rows across all 11 locales, with only one unresolved series base per locale and finite edition/round components. No translation, identity, or production approval is made by this memo.
