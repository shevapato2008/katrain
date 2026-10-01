# Independent source review: Lee Chang-ho, Spanish and French

Reviewer: `/root/lee_es_fr_source_review_sol` (`gpt-6.1-sol`), 2026-10-01 21:12 UTC (2026-10-02 Shanghai). Producer: `/root/lee_es_fr_gap_luna`. Scope: source-only conventional names for `player:143`; no database write or production preimage review.

## Decision

| Language | Source review | Conventional display name | Remaining gate |
|---|---|---|---|
| `es` | **PASS** | `Lee Chang-ho` | Candidate is still pending and has no production preimage binding. AEGO, Godokoro and Wikidata checks remain incomplete; no negative-closure claim. |
| `fr` | **PASS** | `Lee Chang-ho` | Candidate is still pending and has no production preimage binding. FFG and Wikidata checks remain incomplete; no negative-closure claim. |

I independently fetched the pinned [Spanish revision 166117165](https://es.wikipedia.org/w/index.php?title=Lee_Chang-ho&oldid=166117165) and [French revision 221272547](https://fr.wikipedia.org/w/index.php?title=Lee_Chang-ho&oldid=221272547) through their recorded `action=parse` API URLs. Both returned HTTP 200 and the recorded revision IDs. Each API `title` and target-language `displaytitle` says `Lee Chang-ho`; the rendered article root carries `lang="es"` or `lang="fr"`. The Spanish and French body passages identify `이창호` as a Korean professional Go player, with the 29 July 1975 birth date and Cho Hunhyun connection. The recorded passage SHA-256 values match the stored passages, and the passages occur in the independently fetched visible text. French nonbreaking spaces normalize to the ordinary spaces in the stored excerpt.

I independently fetched the [Hanguk Kiwon player profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001). The visible Korean body pairs `이창호 (李昌鎬)` with birth date `1975년 07월 29일`, professional Go rank and records, and Cho Hunhyun as teacher. This corroborates identity across the sources. The `9-dan` / `9e dan` / `9단` rank appears only in context; neither proposed display name includes it.

| Independently fetched raw response | SHA-256, matching recorded value |
|---|---|
| Spanish revision API response | `1ef44422fa8992fbc27c8e031d626b0c7fc6d7cfea81673abd3d6f8e9da1d1ca` |
| French revision API response | `681f1759e1155c22ecd650e6655932bb29736c4ff3a7b76cf0cdae244950f730` |
| Hanguk Kiwon profile response | `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6` |

Both controlled research rows pass `validate_research_record` against immutable registry `2026-10-02.3` (canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`). Each pending candidate's `research_sha256` exactly equals its corresponding canonical research-row hash. Controlled files are mode `0600` and were not changed.

| Controlled artifact | SHA-256 |
|---|---|
| Evidence JSONL raw file, `lee-player-143-es-fr-source-followup.jsonl` | `4eccde81c9c26c505cb6e550227dec1b1c76b9dbcd4335fdafff870ff5b7393b` |
| Candidate JSONL raw file, `lee-player-143-es-fr-candidates.jsonl` | `1a8fb765a0075f27629098b054afb08d6b41fc19eb8df9b57009dd199b0cb831` |
| Spanish research row / candidate `research_sha256` | `feb333dde2674d4d88230597af615af85f74415987f7a499784376ff566f9b84` |
| French research row / candidate `research_sha256` | `882b74ef7d09c31ae976fbf5980fbebf7ccb889db61403e5f528146b8187a916` |
| Spanish candidate canonical JSON row | `9945f14b060b14c52fc6c2494148c6f45147aa1a571b45a705edf52cc4e63288` |
| French candidate canonical JSON row | `d99773ad7dcfd96aee1aa214504c21cb288d5dace951dc12d62f82b630f35b03` |

Conclusion for these exact controlled rows: `approved_conventional_name` for `es` and `fr` source evidence. This memo is the independent source review; it does not alter the pending candidates or satisfy production write gates.
