# Cho Chikun: Ukrainian source-level display decision

**Reviewer:** `/root/zhao_ua_display_astra`. **Actual model:** `gpt-6-astra`, reasoning effort `max`. **Decision time:** `2026-10-01T22:18:35Z` (2026-10-02 in Shanghai), after the last source capture at `2026-10-01T22:17:21.479518Z`.

**Source-level verdict: PASS.** The Ukrainian display may preferentially use **`Чо Чікун`**, classified as `conventional`, with **`Cho Chikun`** retained as an attested Latin alternative for alias preparation. The Cyrillic spelling is copied from Ukrainian Go prose; it is not a generated transliteration. This decision permits preparation of source-bound research and a pending candidate. It is not a candidate approval, database-owner binding, album-link review, or write authorization.

## Evidence and editorial choice

The [earlier independent review](kifu-name-zhao-608-tr-ua-independent-source-review-2026-10-02.md) correctly found a positive that the [producer's bounded searches](kifu-name-zhao-608-tr-ua-source-followup-2026-10-02.md) missed. I inspected the controlled raw bodies and verified their byte counts and SHA-256 values against their manifests.

- **Exact display form:** [UFGO forum post p88623](https://forum.ufgo.org/viewtopic.php?p=88623), by `Артем`, dated 5 July 2016, gives a substantive Ukrainian answer about Go books and names Japanese masters from the 1980s: `Рін Кайхо, Ісіда Йосіо, Кобаясі Коічі, Чо Чікун`. The name occurs in the author's answer, in nominative form. The surrounding account of learning from professional game commentaries establishes the Go context. A fresh Firecrawl read reproduced the passage. This is a community interview contribution, not a federation naming decree; the displayed `2p` profile field alone does not authenticate a professional credential.
- **Additional local publication:** The previously omitted UFGO search for `Чо Чікун` returned a [17 December 2015 report about a Kharkiv children's Go tournament](https://ufgo.org/2015/12/17/pershyj-turnir-z-ho-harkova-sered-ditej-do-12-rokiv/), published by `December`. Its Ukrainian article body describes Go literature brought to the event and uses **`«Позиційний аналіз» Чо Чікуна`**. The surname/given-name sequence has the same spelling, with the final word in the genitive. This supports local use; the exact nominative display remains grounded in p88623, so no inferred lemma is being passed off as a verbatim quotation. The two contributions have different authors and dates but share the UFGO publishing environment; they are not two independent publishers.
- **Latin alternative:** [UFGO post p89714](https://forum.ufgo.org/viewtopic.php?p=89714), by `Bohdan`, dated 10 November 2016, uses `Cho Chikun` in its Ukrainian introduction to the DeepZenGo match, before the English quotation. It is genuine Ukrainian-context Latin usage. Retain it as an alternative rather than describing it as a mistaken spelling.

These sources meet the user's proportionate standard for secondary languages: actual, identifiable local Go usage is sufficient to proceed with a conventional-name candidate. The main-site report strengthens the otherwise isolated forum attestation. Prefer the attested Ukrainian Cyrillic form for the Ukrainian display because it is used naturally in Ukrainian Go prose and supported by the separately authored article's inflected form. This is an editorial preference, not a finding that Ukrainian sources universally use one spelling. No spelling conflict requiring a new generated form has been established.

## Person identity and limits

The independent [Nihon Ki-in profile](https://www.nihonkiin.or.jp/player/htm/ki000004_2.html) identifies `趙 治勲`, reading `チョウ チクン`, born 20 June 1956 in Busan, as a Japanese professional with a substantial Go-book bibliography. The [Korea Baduk Association profile](https://www.baduk.or.kr/record/player_view.asp?pkey=20000020) gives `조치훈 (趙治勳)`, the same birth date, and Japan affiliation. Both controlled bodies were checked; the Korean body is UTF-8.

The Ukrainian name, Japanese-master cohort and Go-author context align with that professional. This is a strong editorial identity inference from the combined sources; the Ukrainian passages themselves do not supply his birth date or kanji. The official profile's Latin field `CHO, Chi Hun` is a source-specific romanization and does not override the observed Ukrainian use.

An additional [EGF report on Artem Kachanovskyi's 2016 professional qualification](https://www.eurogofed.org/artem-kachanovskyii-is-the-5th-egf-professional/) corroborates the background described by the forum author. It does not authenticate control of that account and is not needed as a Ukrainian-name witness. The conclusion rests on the actual Ukrainian passages and the separate player profiles.

**Catalog IDs are environment-specific.** During this review the coordinator clarified that production database `katrain_prod_20260725` has `608 = 赵治勋` and `609 = 金山`, while test database `katrain_db` has `608 = 漆圣颐` and `609 = 赵治勋`. This memo does not independently audit those databases. Earlier `608` labels are therefore not universally invalid, but cannot be transferred between environments. The source-level decision here binds only to the professional described above; any later candidate must bind the correct environment, catalog identity and preimage separately. It establishes nothing about the reported 2,052 raw slots.

## Capture record and next step

| Source body inspected | Captured UTC | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| UFGO p88623 | 2026-10-01T22:10:01.776710Z | 84,507 | `38bb725493331508551abe8112e1f9af98591e50f9e66062e50a00b8abf06705` |
| UFGO p89714 | 2026-10-01T22:10:01.713190Z | 59,535 | `28dd51226abb8fc950c3bccc86745e6915214738b32cec48ebd70ba42a058fa7` |
| Nihon Ki-in profile | 2026-10-01T22:01:20.957311Z | 53,611 | `665d169cbf6c893654c238083e7e2a8003d5911bae727561594a291c4c04ac3c` |
| KBA profile | 2026-10-01T22:01:22.520835Z | 31,465 | `7e84c0da51068e6cb0efdd1db4a6625980828092e96a7369d24f2a302c3fd130` |
| UFGO exact-name site search | 2026-10-01T22:16:06.329372Z | 87,887 | `fd771462e9ae0140ea693cd77f26d73af33dd63f1dae73196cad3ee56487eab3` |
| EGF author-context report | 2026-10-01T22:16:08.899701Z | 49,180 | `bf9d2f03fc41d50fc36d1107b10c9aaa38ce42dfe848d42cd1320597a6db2efe` |
| UFGO Kharkiv report | 2026-10-01T22:17:21.479518Z | 79,847 | `8a4c0f3912d94be9bc3369bcdfd2d686e6f47bbf2d6ae618bf01908e653dbca3` |

The first four bodies remain in the two original controlled directories documented by the earlier review. New captures and a supplemental Firecrawl rendering are under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/cho-chikun-ua-display-astra-20261002/` (directory `0700`, files `0600`). Manifest SHA-256: `381d0d22fd504f8c6d82b987c783c29ac3b661c4f71697c183a905b795d9d206`. The manifest identifies Firecrawl scrape `01a0f988-7250-72ca-859e-a5f9f5b84723`; its exact provider fetch time was not emitted, so the original raw p88623 capture supplies the timestamped binding evidence. All four new saved bodies were checked against that manifest.

Prepare the positive Ukrainian research with the exact p88623 spelling, the main-site corroboration and the retained Latin alternative, then obtain the normal independent candidate review after environment/owner binding. There is no need to exhaust every registered Ukrainian source before this positive route. The main-site search is not a complete forum search, and the positive records preclude treating the current dossier as `no_target_string` or using it to justify a generated Ukrainian spelling.
