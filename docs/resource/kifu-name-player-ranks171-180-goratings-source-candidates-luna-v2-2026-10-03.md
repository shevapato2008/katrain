# Raw-player ranks 171–180: GoRatings cross-language candidates (pending v2)

Date: 2026-10-03. Source-only follow-up to the 171–200 packet; no code, database, or production changes. Actual model: `gpt-6-luna`. This packet uses one source family, GoRatings, for the first ten owners only. These are source candidates for independent review, not approvals. They are not Wikipedia article names.

## Captures and identity linkage

The source is the local GoRatings cross-language capture at `~/.local/share/kifu-name-audit/2026-10-03/goratings-crosslang-index/`. Its index maps numeric player IDs to names visible on separately language-labeled `zh`, `ja`, `ko`, and `en` ranking pages. The v2 packet preserves the exact bytes of the four `*-current.html` pages and `index.json`, along with SHA-256, byte length, source URL, and capture time. For each of the ten IDs, a direct English GoRatings player profile body was fetched and retained with response URL, exact-byte SHA-256, length, heading/title, and date of birth when parsed from the profile. The same numeric player ID joins each candidate to the profile; identity remains pending independent review.

The index uses actual language label `zh`. It does not distinguish `zh-CN` from `zh-TW`; accordingly, no `cn` versus `tw` assertion is made from those rows. Japanese, Korean, and English source labels are `ja`, `ko`, and `en` respectively. A GoRatings-listed name is evidence of that site's language-specific rendering, not proof of Wikipedia usage or universal local convention.

## Results

| Rank | Raw name | Occurrences | GoRatings ID | zh / ja / ko / en |
|---:|---|---:|---:|---|
| 171 | 上野爱咲美 | 426 | 1754 | SOURCE_CANDIDATE × 4 |
| 172 | 陆敏全 | 425 | 1592 | SOURCE_CANDIDATE × 4 |
| 173 | 王昊洋 | 424 | 379 | SOURCE_CANDIDATE × 4 |
| 174 | 唐奕 | 423 | 434 | SOURCE_CANDIDATE × 4 |
| 175 | 蔡丞韦 | 423 | 1693 | HOLD × 4 |
| 176 | 志田达哉 | 422 | 1069 | SOURCE_CANDIDATE × 4 |
| 177 | 本木克弥 | 422 | 1269 | SOURCE_CANDIDATE × 4 |
| 178 | 范胤 | 421 | 1275 | SOURCE_CANDIDATE × 4 |
| 179 | 藤泽朋斋 | 421 | 854 | HOLD × 4 |
| 180 | 林至涵 | 420 | 268 | HOLD × 4 |

Total: **28 SOURCE_CANDIDATE, 12 HOLD**. HOLD means the selected current cross-language index did not yield one unique row for that player ID; no page absence is implied. Rank 179/180 names were visible in other dated GoRatings index captures, but are intentionally held because this bounded v2 used only the current index rows. Rank 175 did not have a unique row in the current captures.

## Protected packet

`~/.local/share/kifu-name-audit/2026-10-03/player-ranks171-180-goratings-v2/` (directory mode 0700; files mode 0400) contains `candidates.pending.jsonl`, `manifest.json`, the exact current ranking-page bytes, index bytes, and ten direct profile response bodies. Candidate JSONL SHA-256: `4388585033346952946a496152e47953c7fd20234e62a9fa1ce50f585735b275`.

The prior ranks 171–200 memo remains the full-scope report; this v2 addendum is restricted to ranks 171–180 and does not change ranks 181–200. No approval, production-write readiness, or database action is asserted.
