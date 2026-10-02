# Independent review: controlled Judan 十段戦 positive research

Reviewed `2026-10-02T14:42:08Z` by `/root/judan_ten_source_review_luna`. Reviewer configuration was parent-assigned **`gpt-6-luna`, high reasoning**; runtime model identity is not independently attested. Scope: the ten pending non-Ukrainian positive research rows for `event:@judan-series-2026-10-02`, original name `十段戦` (`ja`). This is a source-level review only; it approves no catalog identity, candidate write, album link, or database change.

## Decisions

| Language | Pending exact form | Decision | Source-level finding |
|---|---|---|---|
| `en` | `Judan Title` | **HOLD** | Exact text occurs in Nihon Ki-in's English headline `Judan Title Match`, but the page does not use `Judan Title` as a standalone competition name. The headline's `Match` is meaningful: in the article body `Judan title` also means the title Iyama wins and Cho loses. Do not promote this headline fragment as the English event display without a source that attests that form as the competition's name. |
| `cn` | `十段战` | **PASS** | The Simplified article identifies 十段战 as one of Japan's major Go competitions, says it is not a player's permanent dan rank, and names Sankei Shimbun, Nihon Ki-in, and Kansai Ki-in as organizers. The candidate is present in the article passage. |
| `tw` | `十段戰` | **PASS** | The Taiwan Traditional rendering gives the same competition, non-rank distinction, and Japanese organizers. The candidate occurs in the article passage. |
| `jp` | `十段戦` | **PASS** | The registered Nihon Ki-in page is in Japanese and identifies the 十段戦 series. The captured page names the tournament and lists its Japanese organizers and challenger format. |
| `ko` | `일본십단전` | **PASS** | The Korean Baduk Association's Korean player record says Iyama defended the `제50기 일본십단전` (50th Japanese Judan) against Chang Hsu. `일본` explicitly distinguishes this Japanese competition from Korean 십단전. |
| `de` | `Judan-Turnier` | **PASS** | The German Go-Zeitung PDF, page 47, uses the exact form in a paragraph about Iyama qualifying as challenger, the final against Shibano, and the result. The source is in German; the saved reviewed extraction corresponds to page 47. |
| `es` | `Judan` | **PASS** | The Spanish article explicitly calls Judan a Japanese Go competition and names Nihon Ki-in, Kansai Ki-in, and Sankei Shimbun. The exact form occurs in the article passage. |
| `fr` | `Judan` | **PASS** | The French article explicitly calls Judan a Go tournament, names the two Japanese organizers and Sankei Shimbun, and describes its challenger format. The exact form occurs in the article passage. |
| `ru` | `Дзюдан` | **PASS** | The Russian article identifies the Go title as Japanese and names Nihon Ki-in and Sankei Shimbun; it distinguishes the shogi namesake and states that the following discussion concerns Go. Its tournament-format section ties the exact form to the competition. |
| `tr` | `Judan` | **PASS** | The Turkish Go-school biography places Judan among Japan's seven major Go titles and uses numbered Judan finals and preliminary rounds in Cho Chikun's history. This is competition usage, not merely an unrelated Go rank. |

## Evidence and validation

I recomputed the protected files' SHA-256 values. The pending research JSONL is `aa05964480bf56b4b4ea880651e8ccacba7854ddd3d6077b0f13341ee2ee52ca`; the validated JSONL is `2f1f8316ea5bb1f0d0b72e1546575e9b08160ceeb41698e50eb05e73acd9d63f`; and the capture manifest is `9719beaf4528895aeca204caac0e51f5dd71ff65b94a8605aaa9e200618ecc64`. These match the producer memo. All ten pending rows revalidate against registry `2026-10-02.5` and compare equal to their saved validated rows. The registry's canonical hash is `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f` (raw file SHA-256 `2ebd1c462887632717f0b281ed983db41de7065d9e5f7c4332a4fef8a5624511`). Every source URL host matches its registry entry.

The target-language source body hashes match the capture manifests and declared checks: `en` `b60ba9a5d2d24f02f1daf218cf586d263cab83b93e5b27a03ce3006c8e61af35`; `cn` `b4ab9a0849dc6956af3417ba94cc8fab884d1f8d9728f49f31818c04a2dbf99e`; `tw` `109b8c816efbe1d80e1ce4a396a6dabbc4c450d455a98cd532c33016d8fb380d`; `jp` `8fbcb6874cb91b68fb9af0edbc548fcee8a6ca94686f51f37c4705439da10d78`; `ko` `7055f612296b446ad305817c5e0c63ca174029983de7334fd972abf0809568ca`; `de` `b9775be1294b1f90dd36f661756a0c7c017cf5d4543a0978f20fd10ec6a8ee1e`; `es` `54e8d2cfc62f19a34072909849c1ff6bdb72f5e8ac6b539e20d37843f8267f49`; `fr` `05bef40ac28618e4b8db46cc80cef7d47d31886ae86dd94fa6b52240269f7458`; `ru` `cccf5ceecce7cbf21685d1eba2e5628ae6d1e7f41495708402fa8766375b7c52`; `tr` `105318b1fb32210a591f013addf7af6b050df5c3a12d4a04f6ba9c2e0b1a8d36`. The retained German page-47 extraction hash is `8b6f67653e73e0b72e8dcfd84130271029b162620d100b25de7cb787d7bb9588`.

Observed target languages were `en` (manual reviewed text; no HTML language attribute), `zh-Hans-CN`, `zh-Hant-TW`, `ja`, `ko`, `de` (reviewed PDF text), `es`, `fr`, `ru`, and `tr`. For each row, the exact candidate appears in its captured source excerpt and raw source body. In particular, the Korean qualifier is literally `일본십단전`; the German form is on PDF page 47; and the English form appears as only the first two words of the headline `Judan Title Match`.

The separately captured Nihon Ki-in identity body is HTTP 200, Japanese, and hash `8fbcb6874cb91b68fb9af0edbc548fcee8a6ca94686f51f37c4705439da10d78`. Its page heading/navigation identify `第64期 十段戦`; its tournament section gives `大和ハウス杯十段戦`, lists Sankei Shimbun, Nihon Ki-in and Kansai Ki-in, and describes the challenger/title-match format. This distinguishes the Japanese professional Go series from dan rank and other games. The same live page includes newer 65th-edition schedule data in its body; that does not alter the series identity but means the route's old-edition heading should not be treated as a frozen historical snapshot.

## Review-artifact constraint

I did not create a signed copy of the research JSONL. `validate_research_record` requires research records to remain `review_status: pending` and rejects `reviewer_id`, `reviewer_model`, or `reviewed_at` fields (`name_evidence.py`, `validate_research_record`). A signed research-row copy would therefore violate the research validator. There is also no pending candidate JSONL in this capture set to sign under the candidate validator. The independent decisions are recorded here; the original pending and validated files remain unchanged.

The English HOLD is the sole source-review blocker in this ten-row batch. No new candidate wording was authored. No code, registry, database, production data, or existing signed artifact was changed, and no commit was made.
