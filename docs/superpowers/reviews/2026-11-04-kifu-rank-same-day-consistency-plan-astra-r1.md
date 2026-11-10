# Same-day rank consistency — independent Astra plan review, round 1

**Verdict: one blocking plan clarification (R1).** The proposed resolver/first-write consistency fix is otherwise appropriately scoped.

Reviewed `docs/superpowers/plans/2026-11-04-kifu-rank-same-day-consistency.md`, `_qualification`, preparation and incoming first-write validation, and the historical repair preparation/apply eligibility rules. The reported live part-150 failure and 149 committed parts are controller evidence; this reviewer performed no live query or operation.

## R1 — A normal fresh census cannot re-evaluate or correct the already-applied v3 rows

`historical_rank_repair.prepare_manifest` counts and then skips existing v3 snapshots at lines 331–337. `_replaceable` at line 116 accepts missing rows and the explicitly supported legacy formats, not v3. Therefore including already-applied HOME rows in the ordinary census will neither re-evaluate the 16,667 committed slots nor make them eligible for correction through the existing finite apply operator. The plan currently promises that result without an executable path.

Minimal clarification: enumerate the exact committed targets from the confirmed 149 receipts and immutable journals, then separately re-run the new resolver read-only against their original source facts and full eligible cohorts, comparing the stored inference semantics. Preserve unchanged accepted rows. If any committed inference differs, stop new data application and separately specify/review a finite correction operation with exact old-v3 row, original applied journal/afterimage, new beforeimage and reverse-dependency checks. Do not broaden global `_replaceable`, overwrite old journals, relabel old manifest hashes, or undo unrelated accepted work. If no committed differences exist, retain those results and proceed with fresh manifests for the still-eligible scope. This need not expand the immediate resolver implementation into a speculative correction framework.

## Scope and sufficient verification

The same-target-day bare mismatch must disqualify historical inference across the entire stored cohort, irrespective of which targets share a prepared part. Earlier compatible progression, equal same-day grades, future exclusion and explicit typed source ranks must remain intact. Incoming originals should be an additional negative check only; they must not become positive historical basis or propagate inferred snapshots. Sharing a pure compatibility predicate is acceptable if it retains the existing strict first-write requirements.

The listed stored/incoming 6p → same-day bare 7/9 regression, reverse order, earlier progression, equal-day and future/missing counterexamples are the minimum relevant cases. Verify the resulting prepared source/unknown decisions can pass first-write checks after persistence, and retain existing resource/source/binding and native replay tests. Old applied receipts must remain frozen; changing resolver bytes requires new manifests, not changes to prior authority.

No additional schema, general correction abstraction, backend unrelated tests or visual work is needed for this plan clarification. Only this review document was written.
