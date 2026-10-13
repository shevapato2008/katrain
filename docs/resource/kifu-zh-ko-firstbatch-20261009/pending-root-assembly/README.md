# First two Chinese-to-Korean names: pending review packet

This packet contains producer research for 王宏伟 → 왕훙웨이 and 翁子瑜 → 웡쯔위 in both current environments. It has **no independent anchor or candidate approval** and is not an import bundle.

- `PROD-pending.json`: owners 5498 and 5739.
- `TEST-pending.json`: owners 11272 and 11508, bound to the corresponding PROD identities.
- `registry-proposal.json`: the same current TEST/PROD registry plus one CWA professional-roster source needed for the captured original Han row. It is a proposal, not a signed batch registry.
- `manifest.json`: SHA-256 hashes of those three files.

Each item's `research_pending_with_unsigned_anchors` includes the original UTF-8 response bodies for the CWA Han row, U-Go profile and exact Latin query, Daum's positive Korean/Han community row, and a bounded literal scan of the saved TVBaduk China index. The NIKL rule capture is pinned to its original body hash and Table 5 locators. KBA's person-specific response was omitted because only its filesystem modification time was retained, not an actual fetch time. U-Go does not explicitly label its Latin spelling Hanyu Pinyin; the Mandarin reading classification is the recorded reviewer determination.

The separate `research_structural_draft_without_anchors` passes the pure research validator to check capture shape. The anchored pending version intentionally fails validation because all four CN/EN anchors have `approval.status=pending` and no reviewer signature. The anchor content binds exact current name/evidence after-images and source batch IDs/hashes from the captured read-only snapshots. The snapshots contain 15 physical albums and 15 game slots, no KO target for these owners, and no exact KO collision at capture time.

To finalize, an independent reviewer must approve each exact anchor content after checking the current source rows and creation ledgers. Replace only its pending approval with an actual reviewer ID/model/time and `approved_orthographic_original` conclusion; then revalidate the fully anchored research and recompute its hash. A separate independent generated-name review must bind that final research, the six frozen entries, the published reading and boundaries, and the output. Refresh target preimages, source status, inventory and collision checks immediately before import. The legacy TEST/PROD adapters still need the Task 3 ZH proof and source-live read gate.
