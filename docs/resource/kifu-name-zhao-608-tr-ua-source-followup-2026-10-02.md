# Zhao/Cho Chikun player 608: Turkish/Ukrainian source follow-up

Research-only source capture, 2026-10-02. Scope: product languages Turkish (`tr`) and Ukrainian (`ua`). No name candidate, transliteration, preimage, album link, or database write is approved. The exact raw-slot identity remains a separate open question; the sources below identify Cho Chikun as a Go professional but do not establish that every occurrence in the reported 2,052 raw slots refers to him.

## Turkish: positive target-language use found

The [Istanbul Go School article](https://www.gookulu.com/cho_chikun/) is a Turkish-language Go source (`html lang="tr"`), titled “Cho Chikun – Japonya’nın efsane Go oyuncusu.” It uses the bare name `Cho Chikun` in its headline and Turkish article text, states that he was born in Korea on 20 June 1956, and discusses his Go career. The article says it originally appeared in issue 3 of *Go Dergisi* and was written/translated by the school’s editors. Direct HTTP 200 body: 138,378 bytes, SHA-256 `105318b1fb32210a591f013addf7af6b050df5c3a12d4a04f6ba9c2e0b1a8d36`, fetched `2026-10-01T22:01:14.146041Z`.

A second Turkish-language use appears in the revisioned [Turkish Wikipedia article “Honinbō Okulu”](https://tr.wikipedia.org/wiki/Honinb%C5%8D_Okulu), revision `24969706` (`2021-02-25T20:33:14Z`): its Turkish text says Nihon Ki-in took action after `Cho Chikun` won the Honinbo tournament ten consecutive times. This is a Go-related encyclopedia passage, though not a biography. The exact revision API response is 4,193 bytes, SHA-256 `b9b35404343710684d94456a6dc0561c09800b077f505ef72c36f96bba1d2398`; the main-slot wikitext SHA-256 is `a3905f928ea5b2c860c1b46dcdd46ac4117b9f6299f98fee9845f685f01a50a6`.

Together these sources give direct Turkish-language support for `Cho Chikun` as a conventional display form. The spelling is the shared Latin form used internationally; the evidence establishes Turkish publication use, not a uniquely Turkish transcription rule. The school article sometimes appends titles such as “25. Honinbo” or “Onursal Meijin”; these are career titles, not part of the name. The supported bare form is `Cho Chikun`.

## Identity and source-name chain

The direct captures of the two official player profiles match the Turkish biography’s subject:

- [Nihon Ki-in official profile](https://www.nihonkiin.or.jp/player/htm/ki000004_2.html): `趙 治勲（チョウ チクン / CHO, Chi Hun）`, born 1956-06-20 in Busan, 9-dan, affiliated with Nihon Ki-in. HTTP 200, 53,611 bytes, SHA-256 `665d169cbf6c893654c238083e7e2a8003d5911bae727561594a291c4c04ac3c`, fetched `2026-10-01T22:01:20.957311Z`.
- [Korea Baduk Association official profile](https://www.baduk.or.kr/record/player_view.asp?pkey=20000020): `조치훈 (趙治勳)`, born 1956-06-20, 9-dan, affiliated with Japan. HTTP 200, 31,465 bytes, SHA-256 `7e84c0da51068e6cb0efdd1db4a6625980828092e96a7369d24f2a302c3fd130`, fetched `2026-10-01T22:01:22.520835Z`.

The Japanese professional profile gives both the Korean-derived hanja identity and Japanese reading, while the Korean association profile supplies Hangul and Korean hanja. They corroborate the Turkish article’s name, profession, birth date and Japan career. `CHO, Chi Hun` is the Nihon Ki-in’s English romanization field; it is an alternative source-specific form and should not silently replace the locally published `Cho Chikun`.

## Ukrainian: no positive local use found in this bounded check

I checked UFGO’s public search for `Cho Chikun`, `Чо Чикун` and `Чо Чихун`. All three responses were HTTP 200 and their Ukrainian-language primary result area says `Нічого не знайдено`. I queried Ukrainian Wikipedia for `Cho Chikun`, `Чо Чикун`, `Чо Чіхун` and `Тьо Чікун`: the first, second and fourth returned zero hits; `Чо Чіхун` returned three unrelated pages (`TO1`, `Таксист (серіал)`, and `Даніель Чхве`), not Cho Chikun. These are bounded search results, not proof of absence.

The exact Wikidata language-field request for Q484087 returned HTTP 200 (863 bytes; SHA-256 `85983f4b6cdd4eccbc0c1d6a320f4af899494939c76e2062f6c64ce138b3c4c5`, fetched `2026-10-01T22:01:29.176326Z`). It has no `tr` or `uk` labels/aliases and no `trwiki` or `ukwiki` sitelink. Other-language sitelinks include `frwiki: Cho Chihun` and `ruwiki: Тё Тикун`; those are discovery leads in other languages, not Ukrainian evidence. The Latin `Cho Chikun` appears in English sources, but that alone does not establish Ukrainian use.

Still unsearched or incomplete for Ukrainian are broader UFGO article/forum content beyond the exact public-search terms, other Ukrainian Go communities, print publications, and unindexed forum posts. No Ukrainian spelling is proposed. In particular, neither a Russian spelling nor a mechanically transliterated Cyrillic form is treated as Ukrainian convention.

## Controlled captures and registry

All 13 direct response bodies and the manifest are stored outside the repository under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/zhao-608-tr-ua-source-captures-20261002/`; the directory is mode `0700`, and all captured files are mode `0600`. The manifest SHA-256 is `952f108f7fbc83488147ed87e91317f165890f066d492f476836cf4af255352a`. It records exact URLs, UTC fetch times, status, response byte counts and SHA-256 values. The failed unescaped-Unicode URL attempt was a local encoding error before any HTTP request; the encoded retry was captured.

The reviewed registry is `2026-10-02.3`, canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. It registers `go-school-tr` and `wikipedia-tr` as Turkish-language sources, `tgod` as another Turkish Go source, `ufgo` and `wikipedia-uk` for Ukrainian, and Wikidata as discovery. `tgod` was not needed to establish the positive Turkish use and was not searched in this pass. The `.3` registry keeps both `tr` and `ua` negative scopes incomplete. This memo makes no negative closure claim and does not resolve raw-slot identity.
