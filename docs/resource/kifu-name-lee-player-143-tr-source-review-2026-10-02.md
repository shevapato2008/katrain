# Lee Chang-ho player 143: Turkish source review

Source-only review, 2026-10-02. Reviewed independently from producer `/root/lee_ru_tr_sources_luna`. Scope: Turkish (`tr`) conventional candidate only. No candidate approval or database/preimage work was performed.

## Result: PASS for positive Turkish source evidence

The candidate `Lee Chang-ho` is supported by two Turkish-language sources. I independently fetched each recorded URL; both returned HTTP 200 and their exact response-byte SHA-256 values match the controlled evidence. The revisioned Turkish Wikipedia API response is pinned to revision `28972733`. Its Turkish biography states that Lee Chang-ho (born 29 July 1975) is a South Korean 9-dan professional Go player and identifies Cho Hun-hyeon as his teacher. Turkish Go School's article `Go oyuncuları ve akış` names `Cho Hun-hyun ve Lee Chang-ho` in its passage about the Korean flow. The spelling and hyphenation in both sources support the proposed display form.

The independent official Hanguk Kiwon profile returned HTTP 200 and matches the identity: `9단 이창호 (李昌鎬)`, born 1975-07-29, Korean affiliation, and Cho Hun-hyeon as teacher, with professional Go records. Rank is corroborating identity context only; the display candidate contains no rank.

| Evidence | HTTP | Independently fetched SHA-256 | Result |
|---|---:|---|---|
| Turkish Wikipedia revision 28972733 | 200 | `a5c3d6ef4e64bf070ca70c7b5bfd4c39797c1b9774b36125c206c7e1eb1e8ca8` | Target-language biography supports `Lee Chang-ho` and identity |
| Turkish Go School, `Go oyuncuları ve akış` | 200 | `b0447606605c3097445e3c7fca580645d1eb91e695540ab6eb4abb5fdbecf2ae` | Target-language Go article independently uses `Lee Chang-ho` |
| Hanguk Kiwon official profile | 200 | `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6` | Independently corroborates Korean identity and biographical details |

The evidence JSONL and candidate JSONL are both mode `0600`. Their exact file hashes match the producer memo: evidence `1dc41022502cd8d99d2dcb7ad2110968b5878ea5f67604202ea9a41d9f0710c6`; candidates `c527d070237324dcdee9faebda0f32d598020e4e5f23a0f06f8ff2bb53bc79eb`. Candidate `research_sha256` `195e695dd6e339b62478f03b6219cc8a4523ea733d736c1f884defd184265279` equals the canonical sorted-JSON SHA-256 of its Turkish research record. That record passes `validate_research_record` against registry `2026-10-02.3`, whose canonical SHA-256 is `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. The registered source IDs match the cited URLs: `wikipedia-tr`, `go-school-tr`, and `baduk-mobile`.

The research row correctly remains `pending` with `scope_status: found`. TGOD comprehensive search and Wikidata Turkish labels/aliases remain incomplete, so this review makes no claim that the Turkish source scope is closed or that no other conventional spelling exists. This is a source-only PASS for the positive candidate evidence; it is not a candidate approval.
