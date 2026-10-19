# Independent review: Lee Chang-ho, East language candidates

Reviewer: `/root/lee_east_review_luna` (`gpt-6-luna`), reviewed 2026-10-01 20:54:43 UTC. Scope: existing player ID 143, product languages `en`, `tw`, and `ko`. This is a source and candidate review only. The controlled candidate file remains pending; this memo does not bind a database preimage, authorize an import, or record a database write.

## Decisions

| Language | Candidate | Decision | Review conclusion |
|---|---|---|---|
| en | `Lee Chang-ho` | Approve conventional name | Fixed English Wikipedia revision 1373361912 has title `Lee Chang-ho` and the exact name in its English article body. The article identifies the Korean name 이창호, birth date 1975-07-29, and 9-dan rank. The separately published Korean Baduk Association player profile independently identifies 이창호 / 李昌鎬, birth date 1975-07-29, Korean affiliation, 9-dan, and pupil history under Cho Hun-hyeon. The rank is evidence only and is not part of the display string. |
| tw | `李昌鎬` | Approve conventional name | Haifong Go Institute's Traditional Chinese report uses the exact string `李昌鎬` in its body in references to the opponent Lee Chang-ho in the 2017 LG Cup. The Korean Baduk Association profile independently matches the person's Korean name, Hanja, birth date, affiliation, rank, and pupil history. The candidate is a personal name only. |
| ko | `이창호` | Approve conventional name | Cyberoro's Korean report uses the exact string `이창호` in its body and describes the same professional Go player. The Korean Baduk Association profile independently matches the Korean name and the same identity through Hanja, birth date, affiliation, rank, and pupil history. The candidate is a personal name only. |

The reviewer independently fetched the exact four recorded source URLs on review. HTTP status was 200 for each; the raw response SHA-256 values matched the evidence captures byte-for-byte. The English article is pinned to the recorded revision. The browser page extractor could not render the Cyberoro URL, so I fetched it directly over verified HTTPS; this succeeded with the exact recorded response hash and the target-language body excerpt. The registry check confirms `wikipedia-en` is the registered revisioned article source, `haifong` is registered for `zh-Hant`, `cyberoro` is registered for Korean Go sources, and `baduk-mobile` is the registered official Korean profile source. All three research records pass `validate_research_record` under registry 2026-10-02.3; their stored registry hash is its canonical SHA-256. Each candidate's `research_sha256` points to its matching record, and the candidate row hashes match the producer memo.

These approvals are limited to the exact pending rows below. They do not assert completeness of the language search scope. No `cn` or `jp` candidate was reviewed or created.

## Reviewer signature by row

Reviewer ID: `/root/lee_east_review_luna`  
Reviewer model: `gpt-6-luna`  
Reviewed at: `2026-10-01T20:54:43Z`  
Conclusion: `approved_conventional_name`

| Language | Owner | Display name | Research record SHA-256 | Canonical candidate row SHA-256 |
|---|---|---|---|---|
| en | `player:143` | `Lee Chang-ho` | `f219fb27b00c1b31c8701016eddd5e6114fcb04a2d850ed1a6212bcee8f89633` | `76c9971a22acf3d4d89e9eddadfbb7bc000eed6360865b912677f80386cbe089` |
| tw | `player:143` | `李昌鎬` | `27d680c38d6efb7db7a3d7d4c247d9b060f89e4ecfb11e8ad18a1aac037b32f7` | `a60af195d5eb704e0ac475cd9d8f10d1686dcd8ad3ba978711af1d6b58614e76` |
| ko | `player:143` | `이창호` | `a5933a3e3dc1e6a1eed9ba4708340e8deeab79a67dc2d1a4f3d6e744361e8e81` | `451d4d5aab4e10ed22f0d8fd2bc1601708d48b9d8bbc95f237d76ddc07de8415` |

## Controlled inputs and capture hashes

| File | SHA-256 |
|---|---|
| `docs/resource/kifu-name-source-registry-2026-10-02.3.json` (raw file) | `9e2016ac9675c44aa0bbdb304f8c5e1134a4a020d4d577c1c37890a813e0821b` |
| Registry 2026-10-02.3 (canonical JSON used by records) | `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61` |
| `docs/resource/kifu-name-review-runbook.md` | `a74df74e87c318fab2c43c10358a29646f1bba7ed71a0f4eb960550aec65c8ba` |
| `docs/resource/kifu-name-lee-east-producer-memo-2026-10-02.md` | `e7ca2c49efef749efa5c302b94f2a0c36b631f4896940e27b68928d5c2828807` |
| Controlled `lee-chang-ho-en-tw-ko-evidence.jsonl` raw file | `e9fd6eadae9bed84b193ab17541c60b91fc555abca52ec4596e8fb082549e08e` |
| Controlled `lee-chang-ho-en-tw-ko-candidates.jsonl` raw file | `a388fe5ab857acdb1096122a43fd1e121bc987c209ece71ce4d8223febb8378c` |

### Independently fetched source response hashes

| Source | URL | HTTP | Raw response SHA-256 |
|---|---|---:|---|
| English Wikipedia revision 1373361912 | `https://en.wikipedia.org/w/index.php?title=Lee_Chang-ho&oldid=1373361912` | 200 | `4c24672fb2f23a5f009e38581b512ec6d00bc3ace97f78a9fb92eb6c231b7188` |
| Haifong Go Institute | `https://www.haifong.org/news/content/15EE67D3992682B5D3F462451173543C` | 200 | `a32305a1fb13039e3dc7a02b314052a89554d8f9feac502ad53b62baff9fe8d2` |
| Cyberoro | `https://www.cyberoro.com/news/N_news_view.oro?num=514050` | 200 | `1c33f24fac60d9dbca179e7173afbb4e5ce1693817805e3632f65b6d344c1a2f` |
| Korean Baduk Association player profile | `https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001` | 200 | `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6` |
