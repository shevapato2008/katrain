# Kifu rank / hourly plan independent review — Astra R1

Date: 2026-11-03. Review round: 1 of at most 2. Reviewer: independent Astra max agent.

**Verdict: BLOCKING — address the three items below before implementation.** The overall architecture is viable: a portable v3 snapshot in the existing table, unchanged legacy bytes, a separate historical CAS repair, and finite semantic dedup within the existing native publication / ES gate. No new service, table, current-profile crawler, or full-index rebuild is needed.

Reviewed plan: `docs/superpowers/plans/2026-11-03-kifu-rank-and-hourly-consistency.md`, baseline `bc248574d9b49ffecf641d08945938ca1c1e79aa`. This was a plan and targeted code inspection. The reported investigation counts and 80 passing baseline tests were not independently rerun. No product code, configuration, production data, or deployment was changed; no access/listing/traversal under `data/kifu-album/` was performed. The pending scheduling choice remains pending.

## B1 — Initial apply must validate the historical qualification context, not only the chosen SGF

**Plan locations:** lines 51, 62–66, 82–83, 104. **Existing precedent:** `source_rank_repair.py:_live_preflight` (lines 490–568) locks the relevant tables under READ COMMITTED and rechecks the frozen historical cohort specifically because row locks cannot protect the absence of a competing observation.

An unchanged selected source does not prove that it is still the latest qualified observation, that its day is conflict-free, or that no typed boundary exists between it and the target. For example, TEST can freeze a March missing rank from January `9p`, while PROD already contains a February `9d`, or such a row can be inserted after historical `prepare`. All selected path/owner/raw/SHA checks in the current plan still pass. This would violate the stated refusal policy and can yield different safety decisions in the two databases.

**Minimum change:** explicitly freeze the bounded qualification scope / material cohort evidence for inferred decisions, including owner, target day, relevant date/rank/system boundaries, and the applicable date-exclusion policy. On **first apply / first receiver publication**, recheck that qualification after the existing writer/table locks and before writes. New conflicting or otherwise disqualifying evidence must reject the frozen decision; the receiver must not silently choose replacement evidence. Reuse the existing READ COMMITTED / cohort-recheck approach. Keep this separate from already-applied replay, which validates the original receipt/journal and never re-resolves a decision against new observations. The 2002-11-30 exclusion must be the same versioned policy in the shared resolver and receiver, not only an optional historical CLI parameter.

**Required cases:** prepare→apply inserted nearer typed conflict; conflict present only in receiving DB; conflict hidden beyond the SGF shortlist; future-dated observation does not affect an earlier target; successful applied replay stays frozen after later evidence arrives.

## B2 — Protect v3 basis dependencies when undoing an earlier native publication

**Plan locations:** lines 66, 102–104, 123. **Current code:** `catalog.py:_check_retained_rank_dependencies` (1262–1297) recognizes `rank_fact_id` and native `rank_bindings`; `_check_retained_publication_receipts` (1231–1260) recognizes the later publication's own source receipt. Neither recognizes a later snapshot's new portable `basis` references.

Batch A can insert an original source SGF; a later batch B can infer a rank from A's SGF. B's own receipt references B's target, and a v3 basis has no existing FK that necessarily protects A's album/source link. Undoing A could therefore remove the original evidence while B remains applied and its canonical rank remains visible. A target-row CAS check does not detect this reverse dependency.

**Minimum change:** add an explicit retained-v3-basis check to native compensation before the first child/parent compensation write. Resolve the portable basis refs to the exact local original album/source-link/owner bindings already stored in the applied journal, and refuse compensation that would remove or invalidate evidence still used by another applied v3 decision. Cover standalone historical repair artifacts as well as native publications; do not limit the scan to V2 native receipts. Preserve the no-new-table design by using the existing immutable artifacts / snapshot JSON. Record and validate dedup-child hashes and membership before any compensation, then undo children before checking/restoring their parent's intermediate afterimages, as the plan already proposes.

**Required case:** publish evidence A → publish or repair target B using A → undo A refuses atomically with B unchanged → undo B then undo A succeeds. Include a later historical-repair dependency whose artifact is not a native publication.

## B3 — Give hourly candidate work an explicit resource ceiling and overflow outcome

**Plan locations:** lines 51, 66, 121–122, 127. **Current code:** `catalog_standardization.py:prepare_dedup_manifest` (282–402) retains complete candidate SGFs; the existing publication path also parses all original SGFs (`catalog.py` 1902–1903, 1973–1986). A date/ordered-owner predicate reduces scope, but 100 incoming games / 200 owners does not bound the number or cumulative size of historical matches in one cohort.

The plan correctly removes the full-library Python warm/parse. It must also prevent a large upload-date cohort from recreating the observed memory-budget failure inside the new finite path.

**Minimum change:** state that the shared implementation fixes candidate-row, per-SGF, cumulative-SGF-byte, and query-time limits before workers split. Apply them to semantic dedup and the noncanonical exact-match fallback, as well as historical proof bodies. Fetch length/scalar information before bodies. An oversized or ambiguous cohort is explicitly deferred (or publication is rejected where original-source integrity requires it); never silently truncate a cohort and accept a deduction from the remainder. Authoritative original receipt / original-path owner checks remain mandatory and cannot be skipped by the candidate cap. Reuse existing rank byte limits where suitable; no global hash-index project is required.

**Required case:** a cohort exceeds the selected row/byte cap; no partial dedup/rank inference is applied, its outcome is reported, and the known original source owner remains unchanged. Keep the existing same-day scalar conflict aggregate independent of the bounded SGF shortlist.

## Compatibility details to pin while making the above amendments

These are small contract clarifications, not requests for another subsystem or review campaign:

- Make the source-aware rank matrix explicit. `normalize_source_rank` currently treats `19x19` `9d` as amateur, non-19x19 bare `9d/dan` as unspecified, `9p` as professional, and explicit amateur syntax as amateur. “Preserve explicit p/d/k” must preserve this distinction, including equivalent embedded-name ranks. An untrusted/partial date blocks inference, not preservation of an explicit source rank. Conflicting root-vs-name grades must refuse inference rather than choose one silently.
- Keep an existing staged checkpoint discoverable when adding the v3 policy. `Stage._rank_decision_path` hashes `rank_decision_request`, including its policy string (`staging.py` 110–168; `ranks.py` 80–93). Preserve the old request namespace or explicitly load the old key before selecting a new one. Test an old frozen checkpoint and a new v3 item in the same preparation batch; only the new item resolves. Per-snapshot dispatch must cover validation, fact reference collection, reporting, API verification, publish and replay. `rank_observations` / `rank_facts` should remain original observations; historical inferred results must not become new original facts.
- Define deterministic portable evidence tie-breaking by source/path/SHA rather than local album ID. Independent TEST/PROD historical prepares need one supplied `matched_at` if full snapshot SHA parity is required; otherwise compare a clearly defined logical projection and report that full snapshot hashes differ. The native frozen package must retain byte/hash parity as planned.
- Freeze the resolver / in-transaction repair interfaces and the child-artifact shape before assigning the disjoint workers. The current named files and sequencing are otherwise reasonable. Add one existing-pipeline regression showing FF4 / `B+` / source attribution survive the hourly path; no parser redesign or UI layout work is needed.
- The full-library prepare should report a census of every album/source slot, including excluded/hidden scope, and state which subset is eligible for writes. The 175 Go candidates are only examples. Persist canonical decisions in PG; raw SGFs/columns remain evidence, as the plan correctly states.

## Recommended scope reduction

For this slice, hourly publication can write v3 decisions only for incoming original slots and run bounded semantic dedup. Existing frozen snapshots can always be reported as deferred correction candidates and corrected by the separately reviewed historical CAS manifest. This satisfies canonical treatment of newly collected games and the requested historical cleanup while avoiding a second rank-repair child lifecycle inside every hourly transaction. The semantic-dedup child still needs native replay/undo and ES-scope integration. If automatic correction of already-published snapshots is retained, it needs the same explicit beforeimage and dependency rules as the historical tool; it is not necessary to make the core hourly path work.

The ES design is otherwise sound: one writer lock spans pending gate, real PostgreSQL commit, scoped projection/bulk, refresh and ready; uncertain or failed postcommit work retains the original pending operation for recovery. Pure snapshot-only rank repair does not require a full index rebuild. The plan correctly distinguishes historical whole-run timing from currently unavailable ES-stage measurements and does not claim that a configured one-hour interval means the collectors are running.

After the three blocking amendments, one second plan review is sufficient. Implementation validation should remain focused on these contracts and the already-listed integration suites.
