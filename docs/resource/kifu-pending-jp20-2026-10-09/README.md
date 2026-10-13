# Pending mixed 20-player display packet

20 distinct players per environment: 19 qualified conventional JP names preserved verbatim for missing CN cells, plus PROD 4340 / TEST 10134 qualified CN 安东阳向 converted by a finite rule to TW 安東陽向. This packet does not claim a new Taiwanese publication or 20 complete players.

Pinned JP importer source gates and actual source-name/evidence/applied-batch/creation-journal checks passed for all 40 environment-specific anchors. The source names and target NULL preimages were captured read only. Linked scopes agree across both environments: 1,918 player-game slots / 1,869 unique albums, including SGF UTF8 SHA256, side, original names, ranks, dates and results.

`unsigned-anchor-review-requests.json`, `unsigned-jp-rule-request.json`, and `unsigned-tw-rule-request.json` are frozen for root review. The two per-environment unsigned member packets deliberately reference unsigned anchor-content hashes; full signed anchor/rule hashes, actual preimage bindings, inner batches and outer execution approval remain pending root.

JP → CN preserves exact codepoints. The TW rule covers only 安东阳向: Taiwan MOE PDF physical page 5 东－東 and page 7 阳－陽; 安 remains unchanged, and 向 retains the established person-name suffix. Unihan lists multiple variants for 向, so this is a finite full-name decision rather than a general unique-variant mapping. Original MOE PDF and Unicode 17 archive hashes match the preceding TW packet.

Root confirmed preceding batch 588 applied in both databases. Global qualification context was refreshed using the same pinned importer: PROD 2026-10-08 18:11:08 UTC (63,959 qualified names), TEST 18:12:18 UTC (63,954 qualified names). The actual unchanged inventory was reused. Four unsigned inner batch review requests are now frozen: `PROD/TEST-jp-to-cn-batch-review-request.json` (19 members each) and `PROD/TEST-cn-to-tw-batch-review-request.json` (one member each). Sources/rules were signed by root; inner and outer approvals remain root-owned. `finalize-unsigned-bundles.py` will validate and assemble the two 20-player outer bundles after root supplies the four signed inner batches.

No approval signatures, SQL writes, shared locks, product changes or Git operations were performed by this producer.
