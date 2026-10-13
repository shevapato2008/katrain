# Independent Honinbo source-candidate review (2026-10-02)

## Decision

**PASS for all 11 exact `conventional` candidate rows at source-candidate level.** The candidate display strings match the corresponding validated research rows and the [independently reviewed retained source bodies](kifu-name-honinbo-controlled-research-independent-review-2026-10-02.md). All rows target only the Japanese professional 本因坊戦 event reference `honinbo-series-2026-10-02`. The Turkish and Ukrainian decisions retain the source-level qualifications in that review: Turkish `Honinbo Turnuvası` is observed event wording within a school article, and Ukrainian `Турнір на звання Хон'імбо` is observed wording in an uncited article. Neither is claimed to be a federation-endorsed or dominant local convention.

I saved a **separate** source-reviewed JSONL copy at `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-controlled-research/honinbo-series-2026-10-02-candidates.source-reviewed.jsonl` (mode `0600`, SHA-256 `c9698402c05fa9863cc024c11f53b30229cd435c132620b4acf4775086bb9001`). Each row preserves its original producer fields and adds only the independent review status/signature. The original pending candidate and research files remain unchanged. This source approval does not create an event catalog ID, approve 1,617 album links, supply a production name preimage binding, form a write-ready bundle, or authorize a database write.

## Row-by-row check

I loaded immutable registry `2026-10-02.5`, canonical SHA-256 `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`. The [producer candidate memo](kifu-name-honinbo-controlled-candidates-2026-10-02.md) was SHA-256 `9410d88fbbe7effd1b651a095135eea36c8ac162c8139a3442bb2e659600ac43`; pending candidate JSONL SHA-256 was `8b15057a48aea12a47720a22769229d5fc46b3af95cb650a42afb79ea546f113`, and matching research JSONL SHA-256 was `21b96c75b47036781a03c14f3240345eba65898514d84535bb64b9955be30aa1`. The prior independent source review was SHA-256 `9bad1836c1cb84d3a4affa93409fef5c95339fe80c290d16c6321da9a45186de`.

The hashes below are independently recomputed `canonical_sha256` values over each parsed JSON object, with UTF-8, sorted keys, compact separators, and unescaped Unicode. The candidate's stored `research_sha256` equaled the first hash in every row. All eleven rows contain a single `found` source check for the exact candidate string and **zero conflicting found-name checks**; each has `decision_kind: conventional`, `generation_rule_version: none`, and `name_preimage_sha256: null`.

| Language | Exact display form | Decision | Research row SHA-256 | Original pending candidate SHA-256 | Signed source-reviewed candidate SHA-256 |
|---|---|---|---|---|---|
| `en` | `Honinbo` | PASS | `ac03e34c0e16b137fae06038c224e93b8a7944f5b4518e092f0760a764f68f30` | `0eca7fcb385291197334c314240c63360e1458861e0a49c70d083d2eadd0a90f` | `36e851a93f5a6f2d48a68e8dad6e1b9ab68f7abc39f359bfba367924413de014` |
| `cn` | `本因坊战` | PASS | `b002d022603f4f828155ee12752eb88ef853e41c062096c30d7a656ad10deec3` | `92b550899dc3c8a5327952deca3a69f4c5628faa5e05144fb69a7e8fc9096e29` | `bb70b883b9b818e30ea674fb8fc7917689d3bdd8440aa58c1840a092c4ffb2db` |
| `tw` | `本因坊戰` | PASS | `93c8ec7475e8e6c43eade0e2b2c7062bcf84ec451f0c9ea803530fd629969de5` | `8af2fa58d089f06030bcddfd651bb153b3c061ac94b2170b0a02071a4cb50a8f` | `07a194921958e6a61ed13d21868829175b8584c46d13dcb4718325bc5bccff17` |
| `jp` | `本因坊戦` | PASS | `d32df0d604bcacd96c359929f038e3e611508e1db3d6890e2c1c82ce0c5e5e93` | `f84a19033d8dd08330d2283f6e0142cdecdbfd5fe63b260195e354152c3cda2d` | `7bb6f8c5de58beefe5c905c27c8a62c1146af93876ab5118fe3ab2f7c0a061b6` |
| `ko` | `본인방전` | PASS | `205f6e09d3242af3c3b60f1b3d746b05489044c61723be2914409ad8cf909b55` | `ff746096a426b4651ea8408e31d3810bdde6bbd48263045e464c4d0293c6b618` | `c61f39b7f558e736a44b91e1ef36de893e3ec11a82f34f4e945885e9f421513c` |
| `de` | `Hon’inbō` | PASS | `af8730e258fab3def6cab58293a5586300dd2bd5fe34320cee9074e1ee344a5d` | `181b2ba7af3c41451ee580a46f514d32188e2f9bed1287f59f9e023206f2f2e2` | `cd8aef11cb55823c4d726c9d30a1d64f483be4f19f58478cb42eaf55ef011a65` |
| `es` | `Torneo Hon'inbō` | PASS | `2ca7fb0e0d594937f231e5f296380e8cff400bd63d269e80957060ff447c76a4` | `2681d2f26852140d048bdf8963f6a0f2969db8e3e38ab2b880aa923561dfd9ea` | `e139e4e8d9ef2ac9b71941667719de7475e085e8a284553911c27c994eb9eb87` |
| `fr` | `Tournoi Hon'inbō` | PASS | `02ebd464e9518142ab75376f82a899c4050d801393bcbb69faa3848766a7611e` | `46eaa7ac88ae993c4142785a439ae490351263c7ad8af6a05af8d62ce3a7339c` | `a6ae7dc3f768a2b7b5136539435d0f0f321612306036f68635298ff565688573` |
| `ru` | `Турнир Хонинбо` | PASS | `86b7a80f0b9c9fdaf563717d70774d437e866b62d7238f1ef0e435fc4baaa427` | `9c2715b47fe0d109c1f485abea73537ff38c484934bb4aefb7aaf67fe87b3025` | `ce2fa207a1d6fc161187fa77687c54bf5b8b43cf94a3f2fe4d6ad3726d1d6e19` |
| `tr` | `Honinbo Turnuvası` | PASS, qualified | `cb0797a8e5e358d80d6831c001867489086759d4573d799b1c64a301213a780a` | `fa3fdc112372823f7b250e6b2a0ccb857ce35e8bf8b2b254f1dd7f4a55490c47` | `b2cc1eaeb3b1b9b6822a00d1c7587f83bb25d6be3dd4ae70fede56c1bed3ab5a` |
| `ua` | `Турнір на звання Хон'імбо` | PASS, qualified | `7439b086543da2d7c690cfdb0ad7535de975ce9b2ff3701a2d56251da798b40a` | `7f0cdd95c0627440759e1f50e16a2d182187f2e17f5e73738619e589bae32e2b` | `7cc6eca568b4bb8bb01e5d417b7d31ee48b84de1e439c6991532af0f95d6b54c` |

The owner, language, display name, and producer ID/model matched the corresponding research record in every case; each research record's registry version/hash matched loaded registry `.5`. The producer is `/root/honinbo_controlled_research_luna` with `producer_model: gpt-6-luna`. No duplicate product language, alternate found display string, `excluded_candidates`, or conflict adjudication is present in this finite eleven-row batch.

## Signature and focused validation

The independently reviewed copy has `review_status: approved`, `reviewer_id: /root/four_cwi_series_independent_sol`, `reviewer_model: gpt-6-sol`, `reviewed_at: 2026-10-02T14:08:42.221194Z`, and `review_conclusion: approved_conventional_name` on every row. The parent confirmed this agent's configured model override as `gpt-6-sol`, reasoning `high`; the runtime did not independently expose a model identifier. The review time follows the candidate production time and all saved source capture times. The reviewer differs from the source/candidate producer.

I ran `_validate_candidate` on each original and each signed row with its matching research row, registry `.5`, an empty player/event inventory value set, and a **finite temporary link-target set containing only** `event:@honinbo-series-2026-10-02`. All 22 checks passed. A field-by-field comparison confirmed the signed copy retains every original producer field, changes `review_status` only as intended, and adds only the four signature fields. The signed copy has no `preimage_binding`; the original pending research rows remain pending. This focused validation proves candidate/research consistency for this ref only. It is not a full v2 bundle, catalog/link, production preimage, or write-readiness check.

No original pending file, existing document, code, database, or SGF was edited; no commit was made.
