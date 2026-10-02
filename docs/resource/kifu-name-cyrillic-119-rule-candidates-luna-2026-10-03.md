# RU/UA rule candidates for 119 newly approved Chinese readings

**Status:** pending independent review; no target-language display, production rule, person identity, database slot, or foreign-key approval.

## Scope and sources

The input is the 119-record source/reading-approved packet `secondary-six-remaining120-anchor-review-sol/anchors.approved.jsonl`, SHA-256 `fe2371a7ce47894bee17cf150a7eeae92f83191d1cd0ee701b75bd1a90fc8e71`. The source approval authorizes only original Han-name and published-reading correspondence. The 119 records are additional to the previously reviewed 33.

The combined finite vocabulary is 143 distinct Pinyin syllables: 60 retained from the earlier 33-name packet and 83 new tokens. The new 119 readings use 124 distinct tokens. Russian values were matched to the retained Palladius table body (SHA-256 `942c4f4b633939c1da9facfd29c00cfe4e04a549410bd3833f5681ed92a9b6ab`). Ukrainian values were matched to the retained 2019 academic transcription PDF body (SHA-256 `6ac441c5784986b9c127d8db94f83010e49807c0a8f177a6b2fa73391283c0ab`). Existing token decisions were carried forward from the reviewed 33-name packet, preserving its selected systems and holds.

## Candidate and collision counts

| Language | New records | Rule-only displays | HOLD records | Distinct rendered/proposed strings | Collisions in new cohort | Combined with prior 33 |
|---|---:|---:|---:|---:|---:|---|
| Russian | 119 | 117 | 2 | 117 | 0 | 149 distinct rendered strings; 0 collisions across 152 candidate rows |
| Ukrainian | 119 | 118 | 1 | 119 (one is a held academic-system proposal) | 0 | 152 distinct proposals; 0 collisions across 152 candidate rows |

Russian `hui` remains held because the retained Palladius entry offers `хуэй (хой)` without a selector; both new names containing that token have no rendered candidate. Ukrainian `jun` remains held because the selected 2019 academic table gives `цзюнь` while the alternate table gives `дзюнь`; the exact academic-system rendering is retained only as a pending proposal. No other token was missing or ambiguous in the selected source table.

The packet contains 119 candidate rows per language and explicit per-token decisions for all 143 union tokens. No database or code changes were made; actual production slot impact is zero. Slot/FK qualification and writes remain outside this packet's authority.

## Protected packet

`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/cyrillic-119-rule-candidates-luna/` is mode `0700`, with files mode `0600`. It contains per-language candidate JSON, JSONL display rows, and full token decision records, plus a manifest of input/source and artifact hashes. The packet is unsigned and requires independent review.
