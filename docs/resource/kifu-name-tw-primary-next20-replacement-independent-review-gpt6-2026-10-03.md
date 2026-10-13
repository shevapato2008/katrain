# TW next20 replacement independent review

Independent reviewer: GPT-6, `/root/ja21_independent_review`; candidate author: Luna. Review of the [replacement memo](kifu-name-tw-primary-next20-candidate-corrections-luna-2026-10-03.md) and its protected packet.

**Candidate JSONL integrity: PASS. Source-name decisions: 11 PASS / 9 HOLD, unchanged. Correction memo literal Sina quote: HOLD.** The memo converts three words of its quoted Simplified Chinese source into Traditional Chinese. Use the retained literal quote `预赛对阵（2017年新初段标记为——新）： 李鑫怡（新） 胜 叶桂`, or label the Traditional rendering as a translation. The JSONL already contains the correct literal quote; no candidate-row repair is needed for this issue.

| Original | Reviewed Traditional name | Decision |
| --- | --- | --- |
| 邱峻 | 邱峻 | PASS |
| 彭荃 | 彭荃 | HOLD |
| 牛雨田 | 牛雨田 | PASS |
| 宋容慧 | 宋容慧 | PASS |
| 蔡竞 | 蔡競 | PASS |
| 王群 | 王群 | PASS |
| 梁伟棠 | 梁偉棠 | HOLD |
| 吴肇毅 | 吳肇毅 | HOLD |
| 廖桂永 | 廖桂永 | HOLD |
| 安冬旭 | 安冬旭 | PASS |
| 宋雪林 | 宋雪林 | HOLD |
| 佟禹林 | 佟禹林 | PASS |
| 潘非 | 潘非 | HOLD |
| 岳亮 | 岳亮 | HOLD |
| 陶然 | 陶然 | HOLD |
| 杨冬 | 楊冬 | PASS |
| 李鑫怡 | 李鑫怡 | PASS |
| 李豪杰 | 李豪傑 | PASS |
| 朱毅 | 朱毅 | PASS |
| 桂文波 | 桂文波 | HOLD |

## Verified evidence and corrections

All 20 rows bind to the matching original and prior independent-review **literal JSONL line hashes, excluding the newline**. These are not hashes of newly serialized canonical content. Both whole input files, both manifests, the prior review memo, the registered Haifong registry snapshot, both approved anchor files, and the frozen scope matched their declared hashes. Owners, names, proposed forms, statuses, anchor content and linkage fields other than the factual corroboration prose, per-name frozen context/slot declarations, and all false authorization flags remain unchanged. PASS rows retain 2,965 slot hints and HOLD rows retain 1,820: 4,785 total. Slot membership and person/FK applicability are not approved.

All **15/15 main excerpts** equal their corresponding prior independent passages byte for byte and occur literally in the retained HTML text. The reproducible text extraction decodes HTML character references, strips only the edges of each text node, and joins nonempty nodes with one ASCII space. It preserves internal glyphs, full-width layout spaces and nonbreaking spaces. All ten Haifong bodies match the original captures in both hash and bytes, and retain `zh-tw`. Four sourced HOLD rows remain coach/team-leader-only HOLD; five unsourced rows remain HOLD.

- **宋容慧:** the retained 2025 article reports 海峰棋院女子隊 `0:3負` 深圳豪傑自行車隊, then `宋容慧五段 持白中盤勝 盧鈺樺五段`. The replacement no longer assigns Song to Haifong; the corrected prose matches this passage.
- **安冬旭:** the retained 2023 article says `王元均九段 持黑中盤負 安冬旭六段`. The replacement correctly removes the former white/1¾-stone result.
- **李鑫怡:** the retained 2016 page says `李鑫怡 5段`; the replacement does not call this professional fifth dan. The additional 2017 Sina body defines its `(新)` marker as 2017 new 初段 and lists `李鑫怡（新）`. Its exact excerpt, body size and hash match. The older retained 2017 professional-entry corroboration body also matches the prior independent-review manifest. These support the bounded rank-kind correction; they do not establish database person or game ownership.

The inherited four coach/team-leader HOLD decisions and five no-source HOLD decisions have not been promoted by this review. The added Simplified Chinese Sina report supplies contextual corroboration; Haifong remains the Traditional name source. Upstream approved anchor contents were checked for integrity and preservation; this replacement review does not reopen or extend their original identity scope.

## Protected review packet

`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/tw-primary-next20-replacement-independent-review-gpt6/` contains the 20 per-name reviews, summary, exact input/output manifest, and reproducible local review script. Directory mode is `0700`; files are `0600`.

- Reviewed rows SHA-256: `3f16e3182d63ed9fa3581d877da668c67938ff3f54a0accbd382c15cd7c0cbd3`
- Review manifest SHA-256: `ca9587947e1b791c0279031c8beec5a5a89b2ed19bc6b6375dc783c1d6580485`
- Replacement JSONL SHA-256: `a1401e8edd81864dc2b4e864f2b362248e6cc0e3bd85934edf82401c89f4b73c`
- Replacement manifest SHA-256: `23164396cd8167a1b9cad0a504e2b88000df76596272a7123ac3bd42feccd549`

PASS means exact Traditional source-name evidence only. No localized display write, entity/person/QID/FK/SGF/album or database approval follows. No production database access, app-code changes or commit were performed.

## Follow-up: memo quote HOLD resolved — 2026-10-03

The author corrected only the Sina quote to `预赛对阵（2017年新初段标记为——新）： 李鑫怡（新） 胜 叶桂`. I independently checked this line against the unchanged controlled JSONL excerpt and the retained source body: **PASS; the memo literal-quote HOLD is resolved.** The corrected author memo SHA-256 is `4ea658dda9335a1e00651937d94fd1b8eb9cc8e3f2f452c7a7d3000c3efce3a8`. The JSONL remains `a1401e8edd81864dc2b4e864f2b362248e6cc0e3bd85934edf82401c89f4b73c`; the Sina body remains `e6c5d56b4213c233ebcafb4828be24b65b2793d8e4528d55bd2c40a498574d62`.

This append-only follow-up does not overwrite the original review packet, its input memo hash, original HOLD finding, or review/manifest hashes recorded above. The 11 PASS / 9 HOLD source-name decisions remain unchanged; no broader authorization follows.
