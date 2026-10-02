# Remaining 120 Chinese professional reading anchors: independent review

**119 PASS; 1 HOLD (严古韵琪).** This decision covers exact original names, CWA → GoRatings zh/en source correspondence, the published English spelling, and reviewed syllable words only. It does not approve target-language displays, database identities or QIDs, SGF/album slots or FKs, imports, or production writes.

The submitted candidate file SHA-256 is `426c03599195142a0f8a5ce04ebdc29f2d7ba5ac85e715ac7df6911fdcfdf514`; manifest SHA-256 is `399cd47693c625362e04b9dfec823ae70fd896958ffb2ea16d1e7399d79be190`. The reviewer independently rehashed **241 distinct retained bodies** (one CWA roster and 120 each GoRatings zh/en), confirmed **360/360 literal contiguous body excerpts**, and checked every role, observed language, exact H1/roster name, complete DOB, stable ID, URL, same-ID language link, CWA exact-name uniqueness, and source-link fields. The CWA roster has 1,062 rows. Every approved record was then submitted to the actual `validate_transliteration_anchor`; **119/119 passed**. The HOLD record was not signed or sent to the validator as an approved anchor.

The reviewer read the published English spelling and Han name for all 120, treating the candidate `pypinyin` partitions as proposals. The spellings and ordered per-character syllables agree for the 119 PASS records. In particular, `王子昂 / Wang Ziang` is reviewed as `wang | zi ang`: `Ziang` is the publisher's fused spelling; 子昂 supplies the two characters and `ziang` is not a single Pinyin syllable. This is a reading normalization decision, not a change to the published spelling.

`梁伟棠 / Liang Weitang` is PASS for the **source correspondence** with `1963-10-02`. The separate [DOB disposition](kifu-name-liang-weitang-dob-conflict-sol-2026-10-03.md), exact SHA-256 `c33a2653b28154bd830d097b9c64194e3897f400140c3940f4d25b21b21586fb`, specifically excludes the current Chinese Wikipedia `1963-06-02` field because its directly cited Taiwan Go Institute archive says October 2. It does not certify the person's physical DOB; the 1999 yearbook page remains unread. The candidate source-link basis explicitly binds that disposition.

**HOLD: `严古韵琪 / Yangu Yunqi` (CWA000867, GoRatings 2465).** The retained English page prints `Yangu Yunqi`, and the candidate partitions that as `yan gu | yun qi`. [广西日报's reporting](https://guangxi.china.com.cn/2022-07/20/content_42042132.html) identifies her father as 严剑刚 and mother as 古萍, supporting 严 as the surname and 古韵琪 as the given name. Thus the published word boundary does not establish a compound 严古 surname. The v2 validator requires source word count to match `reading_words`; the candidate cannot be signed as a verified surname/given-name boundary without an explicit exception or another sourced representation. The exact original name and English H1 remain observed facts, but no anchor for this row is approved here.

Protected packet: `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/secondary-six-remaining120-anchor-review-sol/` (directory `0700`, files `0600`). The reviewed JSONL carries a PASS/HOLD decision per candidate; the approved JSONL contains passing anchors only. Signatures are content-bound reviewer attestations, not cryptographic identity authentication.

| Artifact | SHA-256 |
| --- | --- |
| `anchors.approved.jsonl` (119) | `fe2371a7ce47894bee17cf150a7eeae92f83191d1cd0ee701b75bd1a90fc8e71` |
| `reviewed-120.jsonl` | `aea52d7cad5c2ea39a76847b552c5d04c6affc491b61f5ec07c2737bee42620c` |
| `source-body-hashes.jsonl` | `5e5dc22ee6a6191b337ecc1394cde1bc7957871c067a2786603aabb1c10050ea` |
| `holds.json` | `521e0830d247d5f8522bd4dc631e8002d1d2450c54687f97274887922dcd1d3c` |

The pending source packet is unchanged. No shared code, database, deployment, or commit was changed.
