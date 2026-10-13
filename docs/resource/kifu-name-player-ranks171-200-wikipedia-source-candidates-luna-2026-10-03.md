# Raw-player ranks 171–200: Wikipedia source candidates (pending)

Date: 2026-10-03. Research status: source-only partial packet; no code, database, or production changes. Actual model: `gpt-6-luna`. This work does not approve identities or names.

## Frozen scope

The 30 owners come from the frozen historical clone `~/.local/share/kifu-name-audit/2026-10-03/raw-player-next7-phase4-signed-batch-binding-sol/inventory.historical-clone.json.gz` (snapshot `2026-10-02T23:25:59.957753Z`, gzip SHA-256 `e320eaf300bbbeffa4fdb1fca006b2d516ccb041653c58e192cd1a483490597e`). I independently recounted nonempty black/white association slots and sorted by descending occurrence count, then raw string. Scope: ranks 171–200, 12,271 total occurrences. Rank 171 is 上野爱咲美 (426); rank 200 is Iwamoto Kaoru (384). No overlap with ranks 101–170.

## Source status

The pending JSONL contains 150 rows (30 owners × `cn/tw/jp/ko/en`). All 150 are `HOLD`: this increment did not capture target-page heading, revision ID, and matching identity evidence together. For ranks 171–180, GoRatings profile IDs and URLs were available in the prior 151–180 source inventory; those URLs are discovery anchors only. A read-only check found Wikipedia links on several GoRatings pages (including pages for 王昊洋, 唐奕, 志田达哉, 藤泽朋斋, and 林至涵), but the target article captures could not be completed under the available request path (Wikipedia returned bot-policy 403s/timeouts). These links therefore remain leads, not PASS candidates. Ranks 181–200 have no GoRatings ID in the reused inventory. No page absence is claimed. No official roster/profile source was captured in this increment.

| Status | Cells |
|---|---:|
| PASS | 0 |
| HOLD | 150 |

## Protected packet

Packet: `~/.local/share/kifu-name-audit/2026-10-03/player-ranks171-200-source-candidates-luna/` (directory mode 0700; files mode 0400). Files: `rank-raw-occurrence-inventory.json` and `ranks171-200-five-language-candidates.pending.jsonl`. Candidate JSONL SHA-256: `3409e2d78b46ebeaa837b5f036b7d83af996522f20cc79d46a7750670370ce04`. The inventory records the frozen source and hash. No approval, production-write readiness, or database action is asserted.

Next useful step: retry this exact bounded cohort through a compliant Wikipedia/API capture path, preserving page language/variant, displayed heading, revision ID, and identity linkage before changing any HOLD to PASS. `zh` alone must not be represented as a `zh-tw` article.
