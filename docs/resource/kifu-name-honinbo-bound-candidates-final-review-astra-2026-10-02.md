# Honinbo bound name candidates: final-review HOLD — 2026-10-02

**HOLD. No candidate copies were signed.** Seven research rows need metadata correction or clarification before the current source-review/preimage-binding chain can receive final approval. The eleven exact display forms remain supported by the retained source bodies; this decision concerns the evidence records and their provenance. The 1,617 identity links remain pending and receive no approval here.

Reviewed the [source-candidate review](kifu-name-honinbo-controlled-candidates-independent-review-2026-10-02.md), [Sol binding memo](kifu-name-honinbo-name-preimage-binder-sol-2026-10-02.md), protected inputs, registry `.5`, and the evidence/candidate validators and importer.

## Seven affected rows

The `en` source check says `observed_lang: "en", language_basis: "html_lang"`. Its retained `en_cwi.html` has a bare `<html>` element with **no `lang` attribute**. Its English prose and exact `Honinbo` are clear; the appropriate basis is an actual text review, not the nonexistent HTML attribute. Body SHA-256: `e04b9168fba2f1b6f06a032ca3afd1b36181c4ce7aeddd5ed970137e3265aac2`.

Six other research rows have `produced_at` earlier than their own nested `identity_corroboration.fetched_at`, which is `2026-10-02T13:45:25.506630Z`. Each row's production time equals its first source-capture time. Those timestamps do not establish when the complete records containing the later corroboration were assembled. If they denote an initial draft, that meaning and the later completion need producer clarification; they must not silently stand in for authentic final-record production times. This is distinct from the later candidate and reviewer chronology, which is correctly ordered.

| Lang | Affected field / recorded UTC production time | Exact original research-row SHA-256 |
| --- | --- | --- |
| `en` | Incorrect `language_basis: html_lang` | `ac03e34c0e16b137fae06038c224e93b8a7944f5b4518e092f0760a764f68f30` |
| `cn` | `2026-10-02T13:44:27.912380Z` | `b002d022603f4f828155ee12752eb88ef853e41c062096c30d7a656ad10deec3` |
| `tw` | `2026-10-02T13:44:30.230064Z` | `93c8ec7475e8e6c43eade0e2b2c7062bcf84ec451f0c9ea803530fd629969de5` |
| `de` | `2026-10-02T13:44:40.302535Z` | `af8730e258fab3def6cab58293a5586300dd2bd5fe34320cee9074e1ee344a5d` |
| `es` | `2026-10-02T13:44:42.521833Z` | `2ca7fb0e0d594937f231e5f296380e8cff400bd63d269e80957060ff447c76a4` |
| `tr` | `2026-10-02T13:44:54.641306Z` | `cb0797a8e5e358d80d6831c001867489086759d4573d799b1c64a301213a780a` |
| `ua` | `2026-10-02T13:44:56.350865Z` | `7439b086543da2d7c690cfdb0ad7535de975ce9b2ff3701a2d56251da798b40a` |

No equivalent language-basis mismatch was found in the other ten rows. The remaining four research rows (`jp`, `ko`, `fr`, `ru`) have no identified metadata blocker in this review.

## Pinned inputs and completed checks

Paths below are relative to `/Users/fan/.local/share/kifu-name-audit/2026-10-02/`.

| Protected input | Recomputed file-byte SHA-256 |
| --- | --- |
| `honinbo-controlled-research/honinbo-series-2026-10-02-research.pending.jsonl` | `21b96c75b47036781a03c14f3240345eba65898514d84535bb64b9955be30aa1` |
| `honinbo-controlled-research/honinbo-series-2026-10-02-candidates.pending.jsonl` | `8b15057a48aea12a47720a22769229d5fc46b3af95cb650a42afb79ea546f113` |
| `honinbo-controlled-research/honinbo-series-2026-10-02-candidates.source-reviewed.jsonl` | `c9698402c05fa9863cc024c11f53b30229cd435c132620b4acf4775086bb9001` |
| `honinbo-name-preimage-binder-sol/honinbo-series-2026-10-02-candidates.preimage-bound.pending.jsonl` | `a19b2f078cdb2d1fea2825fb4b33455548fc144e87cfc0a00f2cba6aa4071bf5` |
| `honinbo-name-preimage-binder-sol/honinbo-series-2026-10-02-v2-bundle.preimage-bound.pending.json` | `181ec9c4add2a7632eadaecb7d8497070e78da0a50dd437f6d417f2954ed43e0` |
| `honinbo-name-preimage-binder-sol/capture.jsonl` | `506c337e730ea380da54bbbaa9f6c68f4e35d64847696dcb877ea6e5c6442386` |

All 12 saved response sizes/hashes match the capture manifest. All eleven research → original candidate → source-reviewed candidate → bound candidate hash chains match. Each bound candidate differs from its original pending row only by `preimage_binding`. All eleven research records and all 33 original/source-reviewed/bound candidate checks passed the existing validators; those validators do not compare a declared HTML-language basis with retained raw HTML, so that result does not cure the defect above.

I checked actual saved text for `Honinbo`, `本因坊战`, `本因坊戰`, `本因坊戦`, `본인방전`, `Hon’inbō`, `Torneo Hon'inbō`, `Tournoi Hon'inbō`, `Honinbo Turnuvası`, and `Турнір на звання Хон'імбо`, including all seven pinned Wikipedia revisions. I also extracted and visually inspected PDF page 141, printed page 281: `Турнир Хонинбо` and the Mainichi sponsor are together in the Japanese title-tournament list. The existing Turkish/Ukrainian source qualifications remain applicable.

Producer `/root/honinbo_controlled_research_luna`, source reviewer `/root/four_cwi_series_independent_sol`, binder `/root/honinbo_name_preimage_binder_sol`, and this reviewer are distinct. Candidate production at `14:04:47.386225Z`, source approval at `14:08:42.221194Z`, production capture at `14:35:14.736820Z`, and binding at `14:37:48.920492Z` are correctly ordered after source collection. Models are recorded configurations, not independently attested runtime identities.

A fresh production **REPEATABLE READ READ ONLY** transaction at `14:47:26.851911Z`, ended with `ROLLBACK`, reproduced catalog SHA-256 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`. It found no normalized event canonical/alias collision and no collision for the eleven displays across all four verified-name tables. No 本因坊戦 owner exists, supporting the eleven explicit null preimages at this snapshot. Capture SHA-256: `5faf8dff7f7ec769a6ebf9502604224f7d31bbde62b7bcb96b53138390779a81`, retained with SQL, summary, and PDF review material in the new protected `honinbo-name-final-review-astra/` directory. A later import still needs its own current-state checks.

## Minimal correction path

Have the producer create a **new version**: use `reviewed_text` for the English language determination, resolve the six production-time fields with authentic current production metadata, and preserve original capture times and old artifact references. Record the actual correcting producer; do not copy another agent's producer identity or invent historical completion times. Retained source bodies can be reused because their hashes and name evidence pass.

Recompute affected research/candidate hashes, obtain fresh independent source-candidate approval, and have a separate binder issue new pending copies referencing the revised source-reviewed candidate hashes. Then perform independent final review of the eleven bound copies. Preserve the four unaffected rows under their recorded hashes where applicable. Existing signed files stay immutable; the 1,617 identity links require their separate review throughout.

Reviewer: `/root/oza_ua_display_decision_astra`, parent-configured `gpt-6-astra` / max, without runtime attestation. This review authored only a new memo and protected review evidence; no candidate signature, existing artifact/document edit, database write, or commit was made.
