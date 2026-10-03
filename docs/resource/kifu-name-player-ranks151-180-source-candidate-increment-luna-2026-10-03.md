# Raw-player ranks 151–180: source candidate increment (pending)

Date: 2026-10-03. Source research only: no code, database, or production changes. This bounded increment covers exactly 30 owners (ranks 151–180) and 150 `cn / tw / jp / ko / en` matrix cells. It is a candidate packet for independent review; no name is approved.

## Scope and capture

The exact rank/raw/occurrence list is in the protected packet `rank-raw-occurrence-inventory.json`. It retains the existing frequency inventory scope used by the ranks 151–250 packet. Four-locale GoRatings profile captures were attempted for the 30 mapped IDs. There are 110 captured raw HTML pages out of 120 expected, each SHA-256 recorded in `capture-manifest.json`; the 10 uncaptured pages are explicitly enumerated there. The last requests encountered connection timeouts, so those cells remain unresolved. Captures are raw response bodies, not browser-rendered or normalized extracts.

The packet has 150 matrix rows: 4 `SOURCE_POSITIVE` carry-forward candidates and 146 `HOLD`. No new candidate was independently approved or promoted to PASS in this increment. `SOURCE_POSITIVE` means previously documented same-person Wikipedia display-name candidates were re-observed against this batch’s same-ID GoRatings captures; it does not mean approved. Those four cells are rank 151 in cn/jp/ko/en. The official identity anchor is KBA profile `pkey=10000276` (백홍석 / 白洪淅, DOB 1986-08-13), documented with the linked same-ID profile and corresponding Wikipedia articles in the existing ranks 151–250 packet.

Keep the Chinese GoRatings ID 315 profile DOB discrepancy visible: its zh page displays 1986-07-02 while KBA, English and Japanese sources give 1986-08-13. The source-positive cn proposal is the actual zh Wikipedia page title 白洪淅, cross-identified using the official KBA record and the Wikipedia interlanguage graph; the discrepant zh profile DOB is not used as identity evidence. `tw` remains HOLD because a separate zh-tw article was not established. This is not an absence claim.

All other 29 owners (ranks 152–180) remain HOLD in every target language: the increment captured GoRatings profile pages and their links as discovery leads, but did not capture/verify the target Wikipedia displayed names and independent official anchor contents for those owners. The 10 uncaptured profile pages are: ID 1275 zh/ja; ID 854 en/zh/ja/ko; ID 268 en/zh/ja/ko. Other available pages do not by themselves close that identity-plus-target-display-name requirement. These 29 owners are in scope and counted as HOLD, not reported as reviewed Wikipedia pages.

## Protected packet and hashes

Protected directory: `~/.local/share/kifu-name-audit/2026-10-03/player-ranks151-180-primary-five-pending-luna/` (mode 0700; packet files mode 0400). The matrix, scope inventory, and capture manifest hashes are recorded in `manifest.pending.json`:

- Matrix: 150 JSONL rows; SHA-256 `b220f54b15a49c837ed6bb2ef9327540642072ff2ea15bc7babe48fc3d77ef8a`.
- Scope inventory: 30 rows; SHA-256 `a11c6d18007562d6aec016902ac0801a1515bbf8f4ba2e7ef39efe47f73999aa`.
- Capture manifest: 110 page entries; SHA-256 `0295c41f60c9eaaa4fa1c096477a51d905cb6a4ef89c272ae9c12be1a890cf77`.

No source absence is asserted; no identity binding, approved-name preimage, production-write readiness, or database action is asserted.
