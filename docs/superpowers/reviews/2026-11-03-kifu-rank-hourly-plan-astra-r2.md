# Kifu rank / hourly plan independent review — Astra R2

Date: 2026-11-03. Review round: 2 of at most 2. Reviewer: independent Astra max agent.

**Verdict: APPROVED for implementation.** The three R1 blocking findings are addressed. No remaining plan-level blocker was found in the revised scope. This approves the implementation plan; it is not a claim that the unwritten implementation or any live data change has passed review.

Reviewed plan: `docs/superpowers/plans/2026-11-03-kifu-rank-and-hourly-consistency.md`. Confirmed worktree HEAD: `bc248574d9b49ffecf641d08945938ca1c1e79aa`. Review consisted of the revised plan, the R1 findings, and targeted inspection of the existing cohort preflight, native publication/compensation, stage checkpoint, source normalization, and semantic-dedup code. The reported investigation counts and baseline test results were not independently rerun.

## R1 blocker disposition

| Finding | Disposition | Sufficient plan commitment |
| --- | --- | --- |
| B1: Chosen-source checks do not establish current historical qualification | Resolved | Lines 68–86 require a hashed material `qualification`, first-apply/first-receiver revalidation after writer/table locks using a fresh READ COMMITTED view, complete bounded scalar-cohort checks, refusal of new disqualifying evidence, and separate frozen replay behavior. Lines 37 and 102–104 cover the shared date-exclusion policy and the required conflict/future/replay cases. This fits the existing `source_rank_repair._live_preflight` approach without a new locking subsystem. |
| B2: Native compensation can remove another v3 decision's original evidence | Resolved | Lines 78, 86 and 106 require exact local `basis_bindings`, binding hashes, and a retained-basis check before any compensation write, covering both native and standalone historical-repair artifacts. The evidence-A/target-B refusal and ordered-undo cases are explicit. Lines 127 and 146 connect repair artifacts and child hash/membership validation to that lifecycle. |
| B3: A finite predicate does not bound rows or SGF memory | Resolved | Line 88 fixes the row, scalar-byte, per-body, cumulative-body and query-time ceilings before implementation splits; requires scalar/length checks before body fetch; and defers an overflowing whole cohort instead of accepting a truncated result. Original ownership checks remain mandatory and fail publication if they cannot complete. Lines 144–145 apply bounded candidate work to the noncanonical exact fallback and semantic dedup. |

## Compatibility and scope

The revised plan also closes the R1 compatibility clarifications: source-aware `d/dan` semantics and embedded-name handling; preservation of explicit ranks despite unreliable dates; refusal of conflicting source grades; portable evidence tie-breaking; shared `matched_at` for full snapshot hash parity; legacy checkpoint lookup and mixed-version dispatch; preservation of original observations/facts; a census of every slot with an explicit writable subset; and an FF4/`B+`/source-attribution regression.

The hourly scope is now implementable without a second rank-repair child lifecycle: incoming original slots receive frozen v3 decisions, semantic dedup is the sole new child, and corrections to existing snapshots use the separate historical CAS repair. Child compensation precedes parent intermediate-afterimage restoration, while dependency and artifact checks precede the first compensation write. The existing ES pending/commit/bulk/refresh/ready lifecycle remains the publication authority.

One nonblocking editorial cleanup: add `qualification` directly to the displayed field list at lines 54–57, so it matches the explicit required-field statement at line 86. The requirement is already unambiguous; no further plan-review round is needed for that edit.

Proceed with the shared contracts first, followed by the disjoint workers and the focused transaction/compatibility tests already specified. The requested independent final code/data-integrity review remains appropriate before live writes. No additional platform, research, test campaign, or plan-review round is requested.

Only this review document was written. No product code, production configuration, data, collector state, or deployment was changed. No access, listing, or traversal under `data/kifu-album/` was performed. The unanswered scheduling choice remains pending; this approval does not authorize enabling collectors or paid calls.
