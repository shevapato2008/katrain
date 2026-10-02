# 小林光一, player 82: independent Spanish and French name review

Reviewer: `/root/kobayashi_es_fr_review_sol` (`gpt-6-sol`), 2026-10-02T04:26:54Z. Producer: `/root/kobayashi_es_fr_sol` (`gpt-6-sol`). This is a source-only approval of the exact `es` and `fr` conventional-name proposals; no owner, album-link, preimage, alias, or database write was reviewed or made.

## Decision

Approve **`Kobayashi Koichi`** as the pending conventional display spelling for both languages. The saved [Spanish Wikipedia revision 156714182](https://es.wikipedia.org/w/index.php?title=K%C5%8Dichi_Kobayashi&oldid=156714182) has that exact spelling in its infobox and biography lead, despite the `Kōichi Kobayashi` article title. The saved Spanish [Godokoro Go article](https://godokoro.es/fuseki-apertura-kobayashi) calls the Japanese 9P `Kobayashi Koichi` in prose. The saved [French Wikipedia revision 232852983](https://fr.wikipedia.org/w/index.php?title=K%C5%8Dichi_Kobayashi&oldid=232852983) heads its biography `Kōichi Kobayashi` and gives `Kobayashi Kōichi` in parentheses; both remain excluded display variants. The French-language Belgian Go federation [Belgo 80](https://www.gofed.be/files/gofed/belgo/Belgo080.pdf) repeatedly uses `Kobayashi Koichi`, including a passage identifying the Meijin winner over Cho Chi Kun. The saved [Nihon Ki-in profile](https://www.nihonkiin.or.jp/player/htm/ki000001.htm) independently matches `小林 光一`, `KOBAYASHI, Koichi`, birth date 1952-09-10 and 9 dan. The federation's exact professional Go usage supports the unaccented surname-first display in French despite Wikipedia's title.

I checked the archived HTML text and `lang` attributes (`es`, `fr`, `ja`), and extracted the PDF with `pdftotext -raw`. The French PDF has `Kobayashi Koichi` at extracted lines 1157, 1309 and 1326. Raw capture SHA-256 values: Spanish Wikipedia `a6dab2cbf279539eb5c55e4a65dd01db2f0b66c353b8e393c023ec5f9abc928c`; Godokoro `e5db3fd214ede4436b9df6725427d3aebc8209306d91d30ee4ed5497ec08e8fc`; French Wikipedia `5074b94c4f3afefe0c2268b8bcc9cdb83fe4ff1f3bcc6dcbfc77d40bb363499d`; Belgo 80 `520a01d86c3fb8311055aac6309a3ebb90f9c1c01492938c52e157803bc187a3`; Nihon Ki-in `c8fc10a734da7143d0c9bf5225f32a241556ca936a8e59311dc49ee90afa6e7d`.

## Exact artifact binding

Source registry `2026-10-02.3` has canonical SHA-256 `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. Both evidence rows passed `validate_research_record`; their candidate `research_sha256` values match their canonical evidence-row hashes. The source evidence JSONL SHA-256 is `d73c65dfa66f6eab0ee05d669a95b9143fda64dfb78d385690c5eceb4dfa6b2f` and the untouched producer candidate JSONL SHA-256 is `a3fde192c874253c69834e6d55e93f51d575f7e7ea561a426d9b3945e9817fb1`.

| Language | Evidence row SHA-256 | Original candidate row SHA-256 | Signed candidate row SHA-256 |
|---|---|---|---|
| `es` | `8e9e3af9431e31c331cac88318f1be55fd314d70c6227221f0aae39429a1eee7` | `a5fefc1638f032e2ddfc7d2d163f21c7eae06c1f23e49872c070ab9d8e172c5a` | `3961ec3d6d2121088f3b1fbb4078a5d8144e2a6499b28316e9c61886930fb2e7` |
| `fr` | `6e30bac28a4de9ea43e7df8aada0888987d77b7d43c116a74781ccdf7d9a8872` | `cb0bb0ea5b0ff1c85accf9a6277274471ca94cf3b5f2a5773cbe666275f37441` | `5e6f44791d0b2fc6691d49cb9460d7aeaf00eab6bf7b8814cf1784e527ab4ca9` |

The separate mode-`0600` reviewed copy is `/Users/fan/.local/share/kifu-name-audit/2026-10-02/kobayashi-koichi-11lang-captures/kobayashi-koichi-player-82-es-fr-reviewed-candidates.jsonl`, SHA-256 `f2bf98f421032167dc912e71579040c65a20283be8be465e8028f388f092131e`. It signs `review_status: approved`, reviewer ID/model/time, and language-specific conclusions while retaining all producer fields. The producer files remain unchanged.

This source-only signature is **not import-ready**. `validate_candidate` against the pinned production v2 inventory (`518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9`) rejects both rows with `entity ID/ref absent from pinned inventory and approved links`. Player 82 has zero album foreign-key links. An independently approved exact SGF identity/link scope and current preimage binding are required before any combined v2 import. No negative source-scope closure is claimed.
