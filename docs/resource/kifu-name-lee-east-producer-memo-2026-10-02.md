# Lee Chang-ho East language producer memo

Producer: `/root/lee_east_evidence_luna` (`gpt-6-luna`), research fetched 2026-10-01 UTC. Scope: product languages `en`, `tw`, `ko`, plus explicit gaps for `cn` and `jp`. Owner is existing player ID 143. Records remain pending and contain no review signatures, database preimages, or write bindings.

Controlled mode-600 evidence and candidate JSONL are under `/Users/fan/.local/share/kifu-name-audit/2026-10-02/`:

- `lee-chang-ho-en-tw-ko-evidence.jsonl`: 3 registry-valid found records. Canonical record SHA-256 by language: en `f219fb27b00c1b31c8701016eddd5e6114fcb04a2d850ed1a6212bcee8f89633`; tw `27d680c38d6efb7db7a3d7d4c247d9b060f89e4ecfb11e8ad18a1aac037b32f7`; ko `a5933a3e3dc1e6a1eed9ba4708340e8deeab79a67dc2d1a4f3d6e744361e8e81`.
- `lee-chang-ho-en-tw-ko-candidates.jsonl`: 3 pending conventional candidates. Canonical row SHA-256: en `76c9971a22acf3d4d89e9eddadfbb7bc000eed6360865b912677f80386cbe089`; tw `a60af195d5eb704e0ac475cd9d8f10d1686dcd8ad3ba978711af1d6b58614e76`; ko `451d4d5aab4e10ed22f0d8fd2bc1601708d48b9d8bbc95f237d76ddc07de8415`.

| Language | Proposed display | Target-language source; raw response SHA-256 | Independent identity source |
|---|---|---|---|
| en | `Lee Chang-ho` | [English Wikipedia revision 1373361912](https://en.wikipedia.org/w/index.php?title=Lee_Chang-ho&oldid=1373361912); `4c24672fb2f23a5f009e38581b512ec6d00bc3ace97f78a9fb92eb6c231b7188` | [Korean Baduk Association profile](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001); `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6` |
| tw | `李昌鎬` | [Haifong Go Institute report](https://www.haifong.org/news/content/15EE67D3992682B5D3F462451173543C); `a32305a1fb13039e3dc7a02b314052a89554d8f9feac502ad53b62baff9fe8d2` | Korean Baduk Association profile above; `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6` |
| ko | `이창호` | [Cyberoro report](https://www.cyberoro.com/news/N_news_view.oro?num=514050); `1c33f24fac60d9dbca179e7173afbb4e5ce1693817805e3632f65b6d344c1a2f` | Korean Baduk Association profile above; `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6` |

All three source checks were freshly fetched with HTTP 200; response body hashes and timestamps are in the records. Identity evidence separates birth date, rank, association, and pupil history from the proposed display strings; rank is not part of any candidate. Research hashes bind each pending candidate to its evidence record. The English Wikipedia passage and KBA profile satisfy the schema's revisioned article plus independent corroboration requirements. Traditional Chinese Haifong and Korean Cyberoro uses are independently cross-checked against the KBA profile.

## Pending gaps

- `cn`: Do not submit a candidate yet. The China Weiqi Association URL in the matrix failed normal TLS certificate verification on the one live fetch; no certificate bypass was used. The previous matrix capture's `5f970691af7b6ea130cccbfdca05c7a939e62448a83959a4e8a50fe4e0652481` is a lead, not a new producer capture. Re-fetch over verified TLS and capture fresh target-language body/revision and exact passage before writing a record.
- `jp`: Do not submit a candidate yet. The Kotobank page in the matrix currently fetched, but Kotobank is not a registered source host in registry `2026-10-02.3`; its live raw-body hash was `642b1bb0d2a588f84e034b1e1b1056be4abdc3c4fdcdf6d0ee5024616a4f80`, different from the matrix's rendered-body capture hash. Obtain an allowed registered Nihon Ki-in or revisioned Japanese Wikipedia capture, with independent identity match and exact reading evidence.

All five target-language URLs and the profile are positive-name leads; this memo does not claim full source-scope completion or absence. No approval signatures, preimage binding, or database writes were made.
