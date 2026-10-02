# Independent review: Russian and Ukrainian 119-name rule packet

**Reviewer:** independent Sol agent, 2026-10-03 (Asia/Shanghai). **Decision scope:** finite syllable values and mechanically composed displays for the 119 source-approved readings. PASS means agreement with the selected table and stated composition rule only. It grants no conventional personal-name, entity, album/SGF slot, foreign-key, production-rule, or database-write approval.

## Evidence and decision

The 119 approved original-name/readings are bound to `anchors.approved.jsonl` SHA-256 `fe2371a7ce47894bee17cf150a7eeae92f83191d1cd0ee701b75bd1a90fc8e71`. All six producer files match their manifest byte counts and SHA-256 values; producer manifest SHA-256 is `24d42d0ce97bb09747a3bb02f35af53885f11947acf8990b56ad5afff366287d`. I compared all 83 added tokens and the 60 inherited tokens with the retained [Russian Palladius table](https://cidian.ru/palladius) HTML body (`942c4f4b633939c1da9facfd29c00cfe4e04a549410bd3833f5681ed92a9b6ab`) and [2019 Ukrainian academic transcription system](https://chinese-studies.com.ua/pinyin_to_ukrainian_26.06.2019.pdf) PDF body (`6ac441c5784986b9c127d8db94f83010e49807c0a8f177a6b2fa73391283c0ab`). The inherited proposals and holds match the [prior 33-name independent review](kifu-name-cyrillic-33-rule-independent-review-sol-2026-10-03.md).

The 119 readings contain 124 distinct tokens; their union with the prior 33 contains 143, including 83 newly needed tokens. Candidate IDs, source names, published readings, and component boundaries match all 119 approved anchors in both languages. Every proposed display matches the producer's mechanical rule.

| Language | Token decisions, union 143 | New display decisions, 119 | New plus prior 33 normalized proposals | Frozen catalog collisions |
|---|---:|---:|---:|---:|
| Russian | 142 PASS, `hui` HOLD | 117 PASS, 2 HOLD | 149 distinct; 0 collisions | 0 |
| Ukrainian | 142 PASS, `jun` HOLD | 118 PASS, 1 HOLD | 152 distinct; 0 collisions | 0 |

Russian `hui` remains HOLD: the retained table gives `хуэй (хой)` without selecting a form. The two affected new displays, **樊麾 / Fan Hui** and **回敬辰 / Hui Jingchen**, have no Russian proposal. Ukrainian `jun` remains HOLD because the selected academic table gives `цзюнь` while the alternate Ukrainian table considered in the prior review gives `дзюнь`. **李君凯 / Li Junkai** retains `Лі Цзюнькай` only as an unsigned academic-system proposal.

I also checked the one new Ukrainian within-name vowel boundary, **王子昂 / Wang Ziang**, segmented `zi + ang`. The PDF's apostrophe condition is ambiguous syllable division; the selected table gives `цзиан` only the `zi + ang` division, so `Ван Цзиан` passes this bounded rule check. This is a table and orthography decision, not conventional-name evidence.

The collision check used NFKC, case folding, and whitespace collapse against the 33 reviewed prior proposals and the frozen six-table catalog capture `catalog-recheck.jsonl` SHA-256 `420ed4a10445a8d50c49d1132cd47ee8eee893b871dce2a968e8593775fa6105` (1,059 player/event canonical, alias, and name rows). The catalog capture is from 2026-10-02; this is not a current production preflight.

## Protected reviewed packet

`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/cyrillic-119-rule-independent-review-sol/` contains `ru.reviewed.json` and `uk.reviewed.json` with every token and display decision, `manifest.json` with source/artifact hashes and counts, and reproducible `review.py`. Directory mode is `0700`; file modes are `0600`. The reviewed JSON SHA-256 values are `16b3cba7ba2874f11cdfed5c9973a52b1ace9684ca25859230965c944998b99c` (Russian) and `3cb4696c77f03b7575c61698678ddab6537e46a29abccb725154f4dd7e937c06` (Ukrainian). No shared code, commit, or database content changed.
