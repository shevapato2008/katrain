# Independent review: Lee Chang-ho, German candidate

Reviewer: `/root/lee_de_review_luna` (`gpt-6-luna`), reviewed 2026-10-01 21:02:38 UTC. Scope: `player:143`, German candidate only. This review approves the conventional display name `Lee Chang-ho`. It does not bind a database preimage, authorize a database write, or make a negative-closure claim.

## Decision

**Approve conventional name `Lee Chang-ho` for `player:143`, language `de`.**

I independently fetched the Deutsche Go-Zeitung 3/2018 PDF from the recorded URL. The raw PDF SHA-256 is `57e93aa1b41c2faa27eb5d6bf7ddb91f46b2954f1b11215e51c149204bbb62b4`, matching the research capture. On printed page 14 (PDF page 14), the German body includes both the heading `Lee Chang Ho 9p` and the sentence `Lee Chang-ho 9p, geboren am 29. Juli 1975.` The candidate string occurs exactly in German body text. The 9p rank is surrounding evidence and is not included in the display name.

I independently fetched the separately published Hanguk Kiwon player profile at `https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001`. Its raw response SHA-256 is `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6`, matching the existing independently captured profile evidence. The body associates `이창호 (李昌鎬)` with birth date 1975-07-29 and professional Go details, corroborating the identity described in the German article.

The research row validates using source registry `2026-10-02.3`, canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. Producer provenance remains `/root/lee_west_evidence_luna`, `gpt-6-luna`, produced at `2026-10-01T21:00:11.147452+00:00`; the candidate's `research_sha256` exactly matches its controlled German research row. The candidate itself remains pending in the controlled source file; this memo is the independent approval signature for that exact row.

The German Wikipedia and Wikidata checks are explicitly incomplete. This approval adopts a conventional name directly attested by a German Go publication and corroborated by an independent official identity profile; it does not claim exhaustive German source coverage or absence of competing forms. The `es`, `fr`, `ru`, `tr`, and `ua` rows remain incomplete and are not approved here.

## Signed controlled inputs

| Artifact | SHA-256 |
|---|---|
| Controlled candidate JSONL raw file (`lee-player-143-de-candidate.jsonl`) | `bb858f0d48080f7f2abeec14e14532e809056bedb02302b3e9d457f05fe15f9e` |
| Candidate canonical JSON row | `c5e59a074fd34608ae6b20c101497d8ca906ab93c2dd6f2c331427bd268cbd3b` |
| Controlled evidence JSONL raw file (`lee-player-143-de-es-fr-ru-tr-ua.jsonl`) | `d093222b178965549b2c0f3fa7e385117b15986d121dc6f4f016d78514757a03` |
| German research row canonical JSON (`research_sha256`) | `c4153d05e93970be9fc92d1b65a3cc620441fe88126cbcffb801d58b3f5c20bf` |
| Registry 2026-10-02.3 canonical JSON | `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61` |

Conclusion: `approved_conventional_name` for the exact controlled candidate row above.
