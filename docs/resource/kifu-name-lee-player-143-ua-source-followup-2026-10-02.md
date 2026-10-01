# Lee Chang-ho, player 143: Ukrainian name source follow-up

Producer: `/root/lee_ua_uncertain_sol` (`gpt-6.1-sol`), 2026-10-02. Source and candidate research only. Registry `2026-10-02.3`, canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`.

## Finding

`Лі Чхан Хо` qualifies as a **pending conventional candidate** for the Korean professional Go player. The exact Ukrainian name appears in the caption of the revisioned Ukrainian Wikipedia [Ґо (гра) article](https://uk.wikipedia.org/w/index.php?title=%D2%90%D0%BE_(%D0%B3%D1%80%D0%B0)&oldid=47335190): `Корейський гравець Лі Чхан Хо`. The caption's `нп` link identifies the English article as `Lee Chang-ho`; its surrounding text calls him a leading Korean player and describes a game with Alexander Dinerchtein. This is target-language article text, though a caption rather than a dedicated biography.

The independently published Ukrainian [Kinorium page for Партія](https://ua.kinorium.com/2674605/) writes `Лі Чхан Хо (이창호)` and explicitly identifies him as Cho Hun-hyun's pupil in a Go context. Kinorium is a film information site, so it serves as a second spelling and identity check, not a professional Go authority. The [Korean Baduk Association profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001) independently establishes `9단 이창호 (李昌鎬)`, birth date 1975-07-29, Korean affiliation and Cho's pupil relationship. These links distinguish the Go player from same-name actors and other people. The Ukrainian article's direct name use plus the independent official original-name/identity anchor meet the runbook's positive-source rule; the Kinorium match adds support.

## Captures and controlled records

| Source | Capture detail | Body hash |
|---|---|---|
| Ukrainian Wikipedia `Ґо (гра)`, revision `47335190` | Firecrawl scrape ID `01a0f958-f4ef-7181-a58b-1ac29736cd87`; HTTP 200; rendered HTML declares `lang="uk"`, `wgRevisionId: 47335190`; exact caption and interwiki link inspected. Hash is of the scrape's `rawHtml` field re-encoded as UTF-8, **not** original HTTP response bytes. | `aeab1b2eb9461dd1c26922478113a66e3b7ca48cfb4075795a1808f6d083024f` |
| Kinorium Ukrainian page | Firecrawl Markdown, Ukrainian Go-film prose with `Лі Чхан Хо (이창호)` and teacher relationship. | `bbaeef3f7667f57d47118a121edc9ccf2da87a856ec0544e512606ba86281c99` |
| Korean Baduk Association player profile | Fresh HTTP 200 response; Korean `이창호`, rank, birth date and professional career directly inspected. | `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6` |

Controlled evidence: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-player-143-ua-source-followup.jsonl`, mode `0600`, file SHA-256 `0e6755e8127f0ee09c8f873a4ad208a1ccd2c80f13b2c131237077e439fe5b61`. Pending candidate: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-player-143-ua-candidate.jsonl`, mode `0600`, file SHA-256 `132373c186086f8b35a07a76d4d5c39563960130429f80df24262f2ffe841d9a`. Candidate `research_sha256` is `d3f46d6d68fa30d00b1869264678ac681951a5bfe6c2aa81c8595ce9046c8a9a`. The research record passes `validate_research_record` with the registered source list.

## Remaining scope

- UFGO: a site-specific search for `Лі Чхан Хо` returned no result and its home page was captured, but its archive and pagination were not exhaustively checked. This is `incomplete`, not a negative finding.
- Wikidata: the exact entity's `uk` labels, aliases and sitelinks were not captured in this bounded pass. This is `incomplete`; any fallback label would be only a lead.
- There is no Ukrainian Wikipedia player biography. The observed caption and Kinorium prose support the candidate spelling, but an independent reviewer still needs to assess this evidence and any variant conflict before approval. No reviewer signature, name preimage, negative closure, bundle approval or database write is present. SGF slot identity links for the player's raw-name occurrences remain a separate task.
