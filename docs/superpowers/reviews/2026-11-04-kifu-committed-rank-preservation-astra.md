# Committed HOME rank decisions: independent preservation review

**Verdict: APPROVED PRESERVE.** No mandatory correction is supported by the reviewed differences. Preserve the accepted 149 parts, their 16,667 snapshots, journals and receipts without rewriting hashes, refusal metadata or category labels. This closes the old-149 correctness gate; fresh audit acceptance and the existing code/database/hash, backup, ES-ready and per-part CAS requirements remain in force.

Scope: independent offline review of the five fixed read-only evidence artifacts below and the relevant resolver/freeze contracts at release `8cc4b6dcdd236bd8339643043f176708ff499503`. The local repair/resolver code digest independently matches the report: `b009f59cb7160689a2ee48ebc1ac328ebbffe3fdb1ccb0217b42183e977d7300`. No live database recheck, writes, provider calls or product changes were performed in this review.

The evidence covers exactly original parts 1–149 and 16,667 slots, with original afterimages and bindings reported verified. Its 1,374 initial differences are covered by the finite 15-part reference result. Of those, 1,287 equal the old complete decisions after reference resolution; unresolved decisions and bulk-replay drift are both zero. The 197 old historical decisions in that reference scope have zero differences. Together with the 2,722 historical decisions unchanged in the original pass, the reports account for all 2,919 accepted historical decisions without an identified incorrect inference.

I independently checked all 87 remaining unique `(part, album_id, side)` differences, their aggregate groups and cross-file hashes. Every old decision is `source` / `dan_unspecified`; **no numeric rank changes**.

- 84 originally record `resource_deferred`. The reference can now classify the reason more specifically in 77 cases, while retaining their source grade and origin. The other 7 could refine an existing source number to a professional category: 14829 white; 15229 black/white; 15238 black; 15244 white; 15245 black; 15246 white. Their existing 5段/9段 values are present and honest; an unspecified system does not assert amateur or professional status. These are optional refinements, not missing-number repairs or corrections of a false profession.
- 3 retain the same source rank, category and origin but change refusal precedence from `typed_boundary` to `incompatible_bare_observation`: 10696 black, 14598 white, 14607 black. Full old/new qualification pairs in parts 99/138 differ only in `incompatible_bare_ranks`. The old amateur boundary, date and grade remain identical and real. The old refusal was therefore conservative and truthful; it does not become fabricated merely because the revised predicate finds an additional earlier-priority reason to refuse.

This preservation follows the existing contract, not a new exception: `historical_ranks.py:985–993` requires source decisions to match the original grade and carry no inference; `historical_ranks.py:1018–1044` explicitly freezes source/unknown decisions without requiring later upgrades, while historical decisions receive fresh qualification. Ordinary repair still skips v3 at `historical_rank_repair.py:331–337`. The plan's conditional correction gate has now been reviewed against the exact finite differences: there are **zero identified slots requiring correction**. No generic v3 replacement, unrelated undo, old-manifest relabelling or metadata-only rewrite is warranted.

Evidence precision: the original run records RR view `6515728:6515728:`, and the reference run records `6516708:6516708:`. They are separate snapshots. The reference's recorded bulk replay has zero drift; do not describe both executions as sharing one exported snapshot. The original timestamp remains `2026-11-03T10:35:55+00:00`. This review independently validates artifact consistency and the preservation decision; the live afterimage/cohort observations are supplied read-only audit evidence, not queries repeated by the reviewer.

All five SHA-256 checks, result/summary cross-hashes, part coverage/counts, unique difference membership, group arithmetic, optional-refinement membership and all three complete qualification comparisons passed local assertions. No unrelated regression suite was rerun. Existing evidence files remain immutable, including their pre-review `candidate_only` / `rank_apply_blocked` flags; this review supplies the decision that those flags were awaiting.

| Evidence under `output/kifu-rank-hourly-20261103/rejudge-ro-evidence/` | SHA-256 |
| --- | --- |
| `original-result.json` | `057057a13c67f2249d3bf0f095c48c4fb3d797a62fc441f11a20bb5442ddfc5f` |
| `reference-result.json` | `a332cbccd78eaa7afc38a995c88fc698d2b18561cace4e54d70cc6b3564ec568` |
| `reference-summary.json` | `58ce37a210cf5978fb74f2f2e31d192c8312819dd59db58fd417cc3a5009f272` |
| `reference-part-000099.json` | `25fa3f8251b1353738872bb204ad69fb6f5b5bab7e2f0e7c80aac2794299ed91` |
| `reference-part-000138.json` | `f330c61b9ff56adb6966f78faae34928e12c70ca7c21f37f65cd93ef18ffe730` |
