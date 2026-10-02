# 小林光一, player 82: independent review of eight language candidates

Reviewer: `/root/kobayashi_eight_review` (GPT-6), 2026-10-02. Research producer: `/root/kobayashi_11lang_luna` (`gpt-6-luna`). This is a source and name-form review only. Spanish and French were reviewed separately; Ukrainian has no candidate. No album identity, link, preimage, alias, or database write is approved here.

## Decisions

| Language | Decision | Candidate | Review basis |
|---|---|---|---|
| `en` | **PASS** | `Koichi Kobayashi` | The captured English Wikipedia revision identifies a Japanese Go player born 1952, gives native name `小林光一`, and uses the candidate as full name. The official Nihon Ki-in profile independently matches `小林 光一`, `KOBAYASHI, Koichi`, birth date, and 9 dan. English given-name-first order is directly observed. |
| `cn` | **PASS** | `小林光一` | China Sports Administration's Simplified Chinese report calls him a Japanese Go player and identifies him in the 2019 Nie Weiping Cup final against Nie Weiping. The official profile confirms the same Japanese professional. The observed Simplified Chinese form is the exact candidate. |
| `tw` | **PASS** | `小林光一` | The Haifong Go Institute's Traditional Chinese Go article includes this name among the Japanese professionals of the China-Japan match era and discusses his Fujitsu Cup win. The official profile independently confirms identity. The Traditional Chinese page directly prints the candidate characters. |
| `jp` | **PASS** | `小林光一` | The official Nihon Ki-in tournament page lists `小林光一名誉碁聖`; removing the honorific/title leaves the exact name. The separate official player profile supplies kana `コバヤシ コウイチ`, romanization, birth date, and 9 dan. The honorific and rank are not part of the proposed display name. |
| `ko` | **PASS** | `고바야시 고이치` | The Korean Baduk Association's player game archive uses the exact Hangul form in result rows, including a 2026 senior match against Yuchanghyuk. Its player-specific record context and the official Japanese profile support identity. The candidate contains the name only, not a rank. |
| `de` | **PASS** | `Koichi Kobayashi` | The captured German-language biography of Kitani Minoru says his daughter married `Koichi Kobayashi`, one of Kitani's best students. The Go-family relationship and the official Nihon Ki-in profile identify the same professional. The German page directly prints the exact candidate, though this is an incidental biography mention rather than a dedicated Kobayashi page. |
| `ru` | **PASS** | `Кобаяси Коити` | RusGoLib's Russian player page gives `Кобаяси Коити (Kobayashi Koichi)`, birth date 10.09.1952, Japan, Nihon Ki-in, and 9 p. The official profile independently confirms the identity. Rank is contextual evidence and is absent from the candidate. |
| `tr` | **PASS** | `Kobayashi Koichi` | The captured Turkish Go-opening article says the opening is named for `Kobayashi Koichi`, linking the exact form to Go usage. The official Japanese profile independently confirms the person. No rank is included in the display candidate. |

The identity anchor saved in the capture set is the Nihon Ki-in profile: `小林 光一 （コバヤシ コウイチ / KOBAYASHI, Koichi）`, born 1952-09-10, Japanese association, 9 dan, and honorary Kisei/Meijin/Gosei titles. The language-specific source forms and professional context align with that person. Ranks and honorary titles are used only as identity evidence and are not appended to any candidate.

## Artifact and validation checks

I reviewed the exact saved bodies and confirmed their raw-file SHA-256 values against the evidence rows and capture manifest. The eight rows use registered source IDs and target-language tags under registry `2026-10-02.3`, whose SHA-256 is `dd6e5f62895bfe8dc42e2ea08d4624fc420f6bb0b7d313bb022ca6e73e6e0a61`. Validation with that explicit registry succeeded for all ten research rows; the eight in-scope rows returned `scope_status: found` and remain `review_status: pending` in the producer artifacts. Candidate `research_sha256` values match the canonical SHA-256 of their exact evidence rows.

| Artifact | SHA-256 |
|---|---|
| Evidence JSONL | `1eb1a5b71c9791206dca0c7663052b6d26b2b6202114ca14b7fdce946e0c4f69` |
| Candidate JSONL | `754eb5fe84a2bd309616fbe6539ce8cc7ca8fdf0a682def4c9325739d15a7ba2` |
| Capture manifest | `89b9df664c62c841f19217b248e0729919b576aa8fe20abba5560ca912515308` |

The source body hashes checked for `en`, `cn`, `tw`, `jp`, `ko`, `de`, `ru`, and `tr`, in that order, are `48110cf8201925b484cc501c1c3446888c141ca73813fbec28c574e3316f27a9`, `d16805312c7255014c8492c125f0644d7d313ac78b551f02585c04ee1ce3aa9f`, `743e90c89ec7bace32663d465f0983cf17f456274832bc9f2d79ec2520772ff0`, `06b4493cc267de3ce953d7c8a470281b41b081ad8020b7aac4c7125c91d800c2`, `7e634e844df07f01ea9ddaf1e06390ab2d8742b63586bc885583abc8f075cdc8`, `155c77044542d919e242ac2bd6b856d61d10024d58354b7c59a6fbeb4ddb569a`, `d38ee64e3cf53014bd9e1aacba4c0c1f21d94a9748306e11aa6d10c0d6bfb7e2`, and `a41fbf7e63d2cedd4062c9cb56162a3826ff9734b63e66a30916c711ca7b7f0c`. The shared official identity-profile body hash is `c8fc10a734da7143d0c9bf5225f32a241556ca936a8e59311dc49ee90afa6e7d`.

The producer evidence and candidate artifacts are unchanged. This review does not make the candidates import-ready: the research packet reports that player ID 82 has zero album foreign-key links and candidate validation against the pinned production inventory rejects the absent association. Exact SGF identity/link scope and preimage binding still require independent approval before any combined import. No alias or negative language-scope conclusion is added.
