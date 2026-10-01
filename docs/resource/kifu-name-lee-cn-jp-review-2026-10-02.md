# Independent source review: Lee Chang-ho, Chinese and Japanese

Reviewer: `/root/lee_cn_jp_source_review_luna` (`gpt-6-luna`), reviewed 2026-10-02. Scope: source-only review of the pending `cn` and `jp` conventional-name candidates for existing player ID 143. This review does not sign the candidate rows, bind a database preimage, or authorize a write.

## Decisions

| Language | Candidate | Decision | Review conclusion |
|---|---|---|---|
| `cn` | `李昌镐` | **PASS** | The National Sports Administration article is a Simplified Chinese Go report and its visible body names Lee Chang-ho as `李昌镐` in a match account. The Korean Baduk Association profile independently pairs `이창호` with Hanja `李昌鎬`, birth date 1975-07-29, Korean affiliation, and 9-dan. The candidate contains only the name. |
| `jp` | `李昌鎬` | **PASS** | The Nihon Ki-in Fujitsu Cup page is Japanese and its visible tournament body lists `李昌鎬九段` for Korea. The Korean Baduk Association profile matches the Hanja/name identity, birth date, Korean affiliation, and Go rank. The Japanese Ki-in archive also gives `李昌鎬九段`, reading `イ・チャンホ`, romanization `Lee Chang Ho`, and the same birth date. The candidate contains only the name; `九段` is rank context. |

## Independent source and artifact checks

I fetched each recorded URL over verified HTTPS. All returned HTTP 200, and each raw response SHA-256 matches the captured body hash in the evidence record and producer memo. The Chinese report and the Japanese tournament page directly support their respective target-language names. The Korean profile corroborates identity across the Korean name, Hanja, birth date, affiliation, and Go-player context. For the older Japanese archive, the response declares Shift_JIS; decoding the independently fetched bytes as CP932 exposes the recorded reading and birth-date passage, and the raw byte hash matches.

| Source | Raw response SHA-256 |
|---|---|
| [National Sports Administration report](https://www.sport.gov.cn/n20001280/n20745751/n20767274/c22079082/content.html) | `b955994190dfc2aca6e9a9d42d444c159ec6ddf0c2f68a5b2b4160be91904674` |
| [Nihon Ki-in Fujitsu Cup page](https://www.nihonkiin.or.jp/match/fujitsu/016.htm) | `1e99d71bbc5f73f80c92785257d7ab8808d90a33f4bef56b5e44c430a1fddc47` |
| [Nihon Ki-in archive player profile](https://archive.nihonkiin.or.jp/event/toyota/toyota002/korea-profile.htm) | `979f6a73c71647b47d8461ec581e35848659f9823f2a0c420cf58f9a868617a6` |
| [Korean Baduk Association profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001) | `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6` |

The two research records pass `validate_research_record` with source registry `2026-10-02.3`; the canonical registry SHA-256 is `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. The registered `china-sport`, `nihon-kiin`, and `baduk-mobile` sources match the three main evidence URLs. Each candidate's `research_sha256` equals its corresponding canonical research-row hash. Candidate canonical row hashes and controlled file hashes match the producer memo.

| Language | Research row SHA-256 | Candidate row SHA-256 |
|---|---|---|
| `cn` | `15a15ce58c90da00fc3ce625e40ffdde8dd7fc2810e8cb45f9c14b6662d5c77b` | `f4ed4fce8a497bb887a5bf06f3aae0bfa6073f56a58acbff7bfc13f56933a715` |
| `jp` | `7e6782b653f884c3538cc540f1a16efc5e25190a4e7e457245bb4b017277b9f8` | `a86f226bd45ea3f5ae9a00146a0d1677aca8ba99315549975b1ebe5c97c675e6` |

| Controlled artifact | SHA-256 |
|---|---|
| `lee-player-143-cn-jp-evidence.jsonl` | `1f0dbcd8ed8d36b6114641e5b1847aaaebf91055728591e57c4ac288b257e1e4` |
| `lee-player-143-cn-jp-candidates.jsonl` | `ad405a961ed7baa210d0fb0ca14ca4e8d4c3d041c2ffce0fcaabec07161f86e5` |

Both controlled JSONL files and the four captured response bodies remain mode `0600`; no candidate or evidence file was changed. The Japanese archive host is outside the registry's exact `www.nihonkiin.or.jp` host match, so I treat it as supplemental reading evidence only. Direct Japanese-context name support comes from the registered Nihon Ki-in Fujitsu Cup page. These findings approve only the source evidence for the exact pending rows; they do not complete either language's search scope or any database-write gate.
