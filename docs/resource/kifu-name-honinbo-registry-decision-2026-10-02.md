# Honinbo: independent registry and conventional-name decision

Reviewed 2026-10-02 by `/root/honinbo_registry_decision_astra`, independently of the name-form producers. Code inspected at `f94f3902`. This is a source-admission and evidence-path decision, not a controlled candidate signature or authorization to write a database.

## Decision

**Create registry `2026-10-02.5` from `.4` with one additional Russian Go-library source; do not add Uluyama for this batch.** This preserves the eleven forms accepted by the [eleven-language review](kifu-name-honinbo-11lang-independent-review-2026-10-02.md) and its [Ukrainian follow-up decision](kifu-name-honinbo-ua-independent-decision-2026-10-02.md). An existing registered Turkish Wikipedia article supplies the exact Turkish form and a clearer Japanese professional-event context than the association's republication.

| Language | Exact display form retained | Qualifying name evidence for future candidate preparation |
|---|---|---|
| `ru` | `Турнир Хонинбо` | Named Russian Go book hosted by Nikorai Do; admit the host as `language_go`, actual language `ru`. |
| `tr` | `Honinbo Turnuvası` | Existing `wikipedia-tr`, pinned article revision `24969706`, with separately published Japanese identity evidence. No new Turkish registry entry is needed. |

The previously reviewed **1,617 ordinary-EV rows** remain the maximum identity scope for this proposed batch. This decision does not re-audit that membership or extend it to the 1,704 adjacent Honinbo-like rows, women's/amateur/local events, honorary names, or the historical house.

## What the current validators actually require

- [`name_evidence.py`](../../katrain/web/kifu/name_evidence.py), `_source_url_matches`, checks registered host or subdomain membership, not the path in `home_url`. Source admission therefore needs a stated editorial boundary; a `/files/` URL would not technically restrict use to books.
- `validate_research_record` binds each record to the full canonical registry hash and version. A positive `found` record may use any source in `sources`; it need not search every `required_source_ids` entry. Those obligations govern search plans and negative closures, not whether a credible positive may stop research.
- [`name_candidates.py`](../../katrain/web/kifu/name_candidates.py), `_validate_candidate`, requires exact case-sensitive agreement between display, research candidate and captured text. Its qualifying name-source tiers are **`official`, `language_go`, `wikipedia_article`, `encyclopedia`**. `reference` alone does not qualify, despite the error message mentioning only discovery sources.
- `_validate_article_evidence` additionally requires the Wikipedia revision, title, exact passage and passage hash, subject identity, and a different publisher's registered `official`/`language_go`/`reference` corroboration containing the exact original name.
- `validate_bundle` checks all research against its one registry, and requires a new event identity to have an approved album link and all eleven approved language names. A source-level PASS does not satisfy those signatures or link/preimage checks.

These rules and the [immutable-snapshot policy](kifu-name-registry-snapshots.md) require one newly reviewed eleven-language bundle if `.5` is selected. They do not require a validator change.

## Russian admission and scope

The [Nikorai Do site](https://nikoraido.ru/) identifies itself as an interregional Go club and describes its open electronic Go library. Its role is a Russian-language specialist Go resource. **`language_go` is justified; `official` would overstate its relationship to the Japanese title event.** Hosting is not authorship or blanket editorial approval of every uploaded book.

I fetched and extracted the exact [Russian book PDF](https://nikoraido.ru/files/Grishin-Emelyanov-Myslit-i-pobezhdat-igra-Go-dlya-nachinayushhih.pdf). PDF page 141, printed page 281, lists the selected event phrase and identifies Mainichi as sponsor, alongside the Kisei and Meijin tournaments. The title page names **И. Гришин, М. Емельянов, А. Степанов**, gives *Мыслить и побеждать: игра Го для начинающих*, and shows Moscow, 2005. The filename omits the third author. The imprint also contains placeholder ISBN, print-date and page-count fields, so describe this as the **hosted 2005-labelled book copy**, not a verified final print edition or a verified ISBN. Those bibliographic limitations do not erase the witnessed Russian event wording; prize amounts and historical factual claims are outside this decision.

The exact proposed registry addition is:

```json
{
  "id": "nikoraido-ru",
  "tier": "language_go",
  "language": "ru",
  "home_url": "https://nikoraido.ru/"
}
```

Set the new version to `2026-10-02.5`, retain all `.4` entries, and append only `nikoraido-ru` to `language_scopes.ru.required_source_ids`. The resulting Russian list is `rusgolib`, `wikipedia-ru`, `wikidata`, `nikoraido-ru`. This narrowly adds the admitted specialist library to Russian search scope, following the `.3`/`.4` snapshot precedent; it is not a prerequisite for accepting this already found name. Other language scopes and every `complete_for_negative_claims: false` remain as they are. Keep the default registry and `.2`/`.3`/`.4` immutable. Record `.5`'s canonical hash after creating the file; this review has not created it.

Admission covers use of the inspected book passage for this event-name decision. Every other document or page on the host still needs actual-language, provenance and identity review. The separately reviewed Fairbairn wording remains an attested alternative with its existing exclusion rationale; admission does not automatically approve that alternative as the display.

## Turkish conventional decision and republication boundary

**PASS for preparation of the exact Turkish form as `conventional`, using existing `wikipedia-tr` plus independent identity corroboration. Uluyama alone is insufficient for the current conventional-name gate.**

The [pinned Turkish Wikipedia article](https://tr.wikipedia.org/w/index.php?title=Honinb%C5%8D_Okulu&oldid=24969706), titled *Honinbō Okulu*, has actual Turkish body text, including `Japonya'da yıllık olarak düzenlenen bir profesyonel go etkinliği olan Honinbo Turnuvası`. It says the annual professional Japanese event's winner uses the title after the old school's closure. This is a statement in the article body; the linked tournament article being a red link does not invalidate the visible usage. The school-oriented page title alone would not establish an event name, but the specific paragraph does.

The [Nihon Ki-in page](https://www.nihonkiin.or.jp/match/honinbo/070.html) independently contains `棋戦名称 本因坊戦` and lists Mainichi, Nihon Ki-in and Kansai Ki-in as organizers. Use registered `nihon-kiin` for the nested `identity_corroboration`, preserving the original name `本因坊戦`. The live page mixes an old edition URL/breadcrumb with updated current-format material; use it only for the stable series identity and original name here, not to establish the 70th edition's current dates or format. The approved finite membership has separate evidence.

The [Uluyama article](https://uluyama.org/makale/go-oyunu) visibly uses the same event phrase, is dated 7 June 2025, and expressly says `Vikipedi Özgür Ansiklopedi'den alıntıdır`. This supports the earlier review's limited observation of Turkish usage, but provides no second independent Turkish authorship. Were it registered for supplemental reference, the defensible classification would be **`reference`, language `tr`**, limited editorially to the reviewed article; it should not be added to Turkish required sources for this batch. Do not label this cultural-association republication `official` or `language_go` merely to pass the whitelist, and do not assign it Wikipedia's revision identity. It is unnecessary now that the registered original-language encyclopedia route is available.

Derivative attribution is therefore a reason to keep the source chain and avoid counting two independent uses, not a reason to reject the exact Turkish name. The project expressly accepts a pinned target-language Wikipedia use with independent original-name/identity corroboration. This decision claims observable published usage, not dominance or Turkish federation endorsement.

## Existing-source alternative and its exact limitation

Already registered `gomagic-ru` has an actual Russian [Honinbo glossary entry](https://gomagic.org/ru/go-term/honinbo/) with the lower-case phrase `турнир Хонинбо` in explicit Japanese tournament context. I checked its visible body: the currently approved capitalized display does **not** occur there. The current case-sensitive gate does not permit silently capitalizing the captured string. Its linked [major-titles article under `/ru/`](https://gomagic.org/ru/japans-most-prestigious-go-titles/) returned an English article body with Russian navigation, so that link does not supply Russian name evidence.

Thus an entirely unchanged registry is possible only if a producer chooses the lower-case display and obtains a new source-form/candidate review, or finds a registered source with the exact current capitalized display. This review does not change the Russian display to avoid a registry addition. The bounded existing-site search is not a negative-closure claim. For preserving all eleven accepted forms, the one-source `.5` above is the smallest verified path; adding both proposed hosts is unnecessary.

## Checks and minimal follow-up

I recomputed canonical registry hashes: `.2` `e2ed3cafa9b6f32d8ba30c78aecdf9667801df3cf34745227e5da588e98dd58e`; `.3` `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`; `.4` `b2d0b2fd65ce22b036e0160574301d954545450638edadf3981d1d53faf7a34c`. These are canonical JSON hashes, not hashes of the formatted files' bytes.

The following HTTP bodies were independently read in this review. Timestamps are UTC on 2026-10-02; SHA-256 values cover raw response bytes. All returned HTTP 200. No retained controlled body bundle was created by this memo.

| Source | Capture time | Bytes | SHA-256 |
|---|---|---:|---|
| Russian book PDF linked above | 13:34:41.510348 | 7,094,409 | `169955c5064c0119b0f1a1d692e902a35267b793f13257fbb1867e1ebf0f972b` |
| Pinned Turkish Wikipedia revision | 13:34:38.011378 | 80,435 | `511dc75faaa1ffaf4d2da3546f7c5376b1a1e6c62200f357239f0852eb73a452` |
| Nihon Ki-in identity page | 13:34:41.540098 | 295,850 | `d96c496abca1c292ad0814200cf4d66adb7a7ed233347934a1a4bce11eda6f26` |
| GoMagic Russian glossary | 13:34:44.530802 | 354,909 | `62c78c67a0372d6cea02db255c46ce788725b600dfa11e35b162c6d79e4a1514` |
| Uluyama Turkish article | 13:35:40.720381 | 38,663 | `4c599e300afc030fbbc18704bb78ae474165b4aca8f97a47e169f92e495665ce` |

1. Create the narrow `.5` snapshot and document its canonical hash. No code change or expansion of the event cohort is needed.
2. Capture or reuse genuinely retained evidence with its original acquisition metadata. The Russian PDF requires manual text/page evidence and `observed_lang: "ru"`, `language_basis: "reviewed_text"`; the HTML-only capture routine is not a PDF extractor. For Turkish, bind revision `24969706`, the exact body passage/hash and the separate Japanese corroboration. Reviewers must be able to read the retained raw bodies; this memo's hashes alone do not supply them.
3. Prepare eleven pending research records and exact `conventional` candidates for one new event reference, all pinned to `.5`. Reuse valid bodies where possible, but recompute research hashes and obtain new independent candidate signatures. Preserve known alternate spellings and their adjudication; copying earlier source-level PASS labels or old signatures is insufficient.
4. Bind only the separately approved finite ordinary-EV link set and current inventory/preimages. Complete candidate/bundle validation and the existing clone dry-run/apply/undo checks before a separately reviewed production action. The outcome here is permission to prepare that controlled result, not proof that it already exists or contributes verified production coverage.

Only this new decision document was written by this review. No registry, code, database, SGF, existing document or candidate was edited, and no commit was made. The delegated reviewer identity above is explicit; a runtime model identifier was not independently exposed, so this memo makes no unsupported runtime-model assertion.
