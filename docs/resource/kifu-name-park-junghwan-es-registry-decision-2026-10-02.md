# Park Junghwan (player 54): independent Spanish registry decision

**PASS for source admission:** create registry `2026-10-02.4` with `chile-go-federation` as `language_go`, language `es`, home URL `https://igochile.cl/igochile2/`. **FAIL for the proposed `official` tier and for treating this memo as candidate approval.** The evidence is sufficient to produce a new pending `conventional` Spanish candidate, `Park Junghwan`, subject to the gates below.

Reviewer: `/root/park_es_registry_decision`, independent of producer `/root/park_es_tr_sources`. Reviewed 2026-10-02. Dispatch configuration confirmed by the parent: model `gpt-6-astra`, reasoning effort `max`; runtime model/effort are not independently exposed to this child, so these are dispatch metadata, not verified runtime self-report. Inputs: producer commit `3bd9193b`, the [full eleven-language design](../superpowers/specs/2026-10-02-kifu-full-name-localization-design.md), and registry `.3`, whose canonical SHA-256 I recomputed as `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`.

## Evidence and classification

- The [Chilean federation news page](https://igochile.cl/igochile2/noticias-de-go/) has HTML language `es-CL` and Spanish Go reporting. Its article dated 25 July 2021 contains the exact visible phrase `Park Junghwan 9p de Corea`. The article credits AGA and links its original report; preserve that republication provenance. A live Firecrawl check agreed with the saved passage. This establishes published Spanish usage, without establishing dominance across Spanish-speaking communities or independently verifying every fact in the report.
- The [IGF Chile member page](https://intergofed.org/chile/), opened during this review, identifies the Chile Go Association and links `www.igochile.cl`. This independently corroborates the publisher/domain relationship. `language_go` matches `.3` treatment of AEGO, FFG, DGOB and other language-community Go associations. The news report is not Park's official personnel record, so `official` would overstate its role in this decision.
- The [Kifubara Spanish player page](https://kifubara.app/es/players/a42b2257-fad2-4fc5-b978-b76b607239ee) uses the same name in an `es` page and identifies a Korean 9-dan player, KBA affiliation and birth year 1993. It remains supplemental and unregistered; its localized interface alone does not establish an independently selected Spanish naming convention. The [KBA profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000457) gives `박정환 (朴廷桓)`, 9 dan, Korean affiliation and birth date 1993-01-11. These identity cues are consistent; database owner 54 still needs its own binding review.

I read the three retained bodies and verified their byte counts and SHA-256 values. All files are mode `0600`, with their immediate directories `0700`. Paths below are relative to `/Users/fan/.local/share/kifu-name-audit/2026-10-02/`.

| Body | Bytes | SHA-256 |
|---|---:|---|
| `park-junghwan-es-chile/igochile-noticias.html` | 153135 | `97a893dde530d29ff5bee6e0b844382cd4e48d0e13e76ba32dda2daa014446de` |
| `park-junghwan-player-54/bodies/es_kifubara.html` | 126134 | `597f7dbba7b38a35574c8021600c8d982282d180b69c15dcfa08ead40326c00e` |
| `park-junghwan-player-54/bodies/kba_identity.md` | 11700 | `0d1024775bcb8a8109dc5049aa0c90d9c52d648c36591de0278a6aff608f300e` |

The producer's KBA path under `kifu-name-player-top100-20261002` is absent in this workspace; the verified copy above has the stated hash and an entry in `park-junghwan-player-54/capture-manifest.json`.

## Conditions for using the source

1. Create a new `.4` snapshot and record its canonical hash. Add only the entry specified above and append its ID to the existing Spanish `required_source_ids`. Preserve older snapshots, the default registry, all existing source obligations and every `complete_for_negative_claims: false` value. Registry admission is a research starting point, never blanket name approval.
2. This decision covers the federation-published Spanish reporting at the exact audited news URL. The current validator checks host/subdomain membership, **not** the `home_url` path: the `/igochile2/` value does not enforce a path boundary. Each future page still needs its own actual-language, body, provenance and identity review; other paths, subdomains, comments or linked external reports receive no approval from this memo.
3. Produce new pending research for exactly `player:54:es`, pinned to `.4` and its hash. Retain the exact name excerpt, `observed_lang: es-CL`, `language_basis: html_lang`, source ID, resolved HTTPS URL, genuine capture timestamp, HTTP status, body hash and identity basis. The retained Chile body has no accompanying capture manifest in its directory; recover genuine acquisition metadata or recapture it. Do not derive a fetch time from file modification time or assign a new timestamp to old bytes. Keep the registered KBA anchor available with its verified provenance.
4. A new pending `conventional` candidate must bind to that research hash. A reviewer independent of its producer must inspect the captured Spanish passage, AGA attribution, identity anchor, exact owner/language and registry/research hashes, then record their actual disclosed model and a review timestamp after production and capture. This source memo and old `.3` signatures cannot substitute for that review. Preserve inventory/preimage, alias-conflict, batch validation and database-write gates.
5. A credible positive target-language use permits stopping negative search under the approved plan. No exhaustive Spanish absence claim, generated fallback, or relaxation of finite negative-closure rules follows from this decision. Existing reviewed `.3` languages need not be migrated for this existing player ID; eleven-language/full-library completion remains a separate acceptance requirement.

No registry, research/candidate artifact, validator or database was changed by this review. Only this decision memo is committed.
