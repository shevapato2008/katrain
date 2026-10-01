# Lee Chang-ho (player 143): Russian name variant adjudication

Reviewer: `/root/lee_ru_variant_sol` (`gpt-6.1-sol`), 2026-10-02. Scope: **source-level editorial choice only** for `ru`. This memo is not a candidate approval, reviewer signature on a controlled bundle, preimage binding, alias import, or database write.

## Decision

Use **`Ли Чханхо`** as the preferred Russian display form and retain **`Ли Чхан Хо`** as a sourced search alias when the product's alias workflow is reviewed. Both spellings refer to the same Korean professional Go player, Lee Chang-ho / `이창호` (player 143). The distinction is spacing within the given name, not evidence of a second person. The existing pending `ru` candidate says `Ли Чхан Хо`; it must not be silently treated as if it said `Ли Чханхо`.

The preference follows the user's direction to use credible local Go material for the six additional languages. RusGoLib is the registry's Russian-language Go source and uses `Ли Чханхо` in its [world-player directory](https://rusgolib.gofederation.ru/KtoEst%27Kto/Mir.html) and [individual profile](https://rusgolib.gofederation.ru/LeeChangho.html). The directory identifies its Korean-name transcription method as the Kontsevich system. The profile gives `Lee Changho`, 29 July 1975, South Korea, 9p, the Korean Baduk Association and Cho Hun-hyeon as teacher. The independently published [Korean Baduk Association profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001) gives `이창호 (李昌鎬)`, the same birth date, 9 dan and Cho's pupil relationship. Those details make the identity match specific.

The pinned [Russian Wikipedia article, revision 149787621](https://ru.wikipedia.org/w/index.php?oldid=149787621) uses `Ли Чхан Хо` in its title, name field and biography, and identifies the same `이창호`, birth date, teacher and Go career. It is therefore a genuine Russian form suitable for search. It does not override the preferred spelling of the specialist Russian Go source in this bounded choice.

RusGoLib is a collaborative Go library hosted on a federation subdomain. Its domain does **not** make each spelling an official federation ruling. The directory and profile are one publisher, not two independent votes. Their value here is specialist target-language use plus detailed identity information, corroborated by the Korean association. This is a choice between two attested conventional forms, not a generated transliteration or a claim that Wikipedia's form is erroneous.

## Evidence and limits

| Source | Observed form and identity check | Capture status |
|---|---|---|
| [RusGoLib individual profile](https://rusgolib.gofederation.ru/LeeChangho.html) | `Ли Чханхо (Lee Changho) (29.07.1975)`; South Korea, 9p, Korean association, Cho Hun-hyeon. Its Russian biography also repeats `Ли Чханхо`. | Prior controlled HTTP body SHA-256 `1a2f67fab9cbee409551d0882223cf128978d2ed8fa76a5a2cbaa72e477b9921`, checked against the mode-0600 research record `lee-player-143-ru-tr-source-followup.jsonl`. Independent live Firecrawl, web reader and direct HTTP retries on this review timed out; the web search index returned the same profile text. |
| [RusGoLib world directory](https://rusgolib.gofederation.ru/KtoEst%27Kto/Mir.html) | `Ли Чханхо (Lee Changho) Ю.Корея`; its introduction states the Korean-name transcription convention. The entry is in the main catalog, not the question-marked additions list. | Search index exposed the body, but direct retrieval timed out. No new directory body hash is claimed. The individual profile is the controlled source for the proposed display. |
| [Russian Wikipedia revision 149787621](https://ru.wikipedia.org/w/index.php?oldid=149787621) | `Ли Чхан Хо`, `이창호`, born 29 July 1975, 9 dan and Cho Hun-hyeon's pupil. | Independently opened pinned article; prior controlled parse-response SHA-256 `2487e11bef2a70ec778f3a99bdeb9154f255ce144b2322f7b8efaecc69906e50`. |
| [Korean Baduk Association profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001) | `9단 이창호 (李昌鎬)`, born 1975-07-29, `조훈현 문하`. | Independently opened; prior controlled body SHA-256 `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6`. |

The prior controlled research row is bound to the old candidate `Ли Чхан Хо` by `research_sha256` `23e474476bb6a17ee966a0a5e74f44df57e0b48ab2072ab51b2b45077d0290ef`. If the producer acts on this choice, they should issue a **new pending** `ru` research/candidate pair whose primary is `Ли Чханхо`, which retains and explicitly explains the excluded-primary Wikipedia form. The revised pair needs its own evidence hash and an independent candidate review under the runbook. No controlled files, existing candidate, name preimage, or player table were changed by this adjudication.
