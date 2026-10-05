# Finite raw-title profile code review — 2026-10-06

**Verdict: APPROVE.** No Important or Critical finding in `cdb0aebd61f7c360d9edd130b5e2466a32cb5b39` against parent `443f898c385f6f823c707b47b0ab128174975717`.

Reviewed only the owner-profile diff, its focused tests, and the necessary adjacent validation/apply paths against the approved continuation decision and plan.

- Only `first24`, `agon10`, and `cmb2` are selectable. Their exact raw-set hashes, owner counts, and game totals are fixed in code. I independently recomputed the raw-set hashes from the approved drafts/first24 values; all match (24/493, 10/205, 2/2).
- `first24` remains the API/CLI default. Its prepared plan omits the new profile field, preserving the prior artifact shape and both 271/222 group checks. Missing profile in an existing plan still resolves to first24.
- Explicit profile agreement is checked for inspect/apply, including before the existing replay path. New profile selection cannot authorize arbitrary raw values; inspect rechecks the allowlisted hash/count and current exact scope.
- Complete owner preimages, pending/unclassified/no-name requirements, public/nonduplicate/NULL-event/no-selection scope, inventory/catalog pins, external manifest/plan hashes, and independent signatures remain intact. Writes still run through the existing advisory/physical locks, modify only review status/metadata, and journal complete before/after images for existing conditional undo.

Verification: source/test inspection; an independent read-only probe of exact profile hashes, default arguments and unknown-profile rejection; `git diff --check` passed and the worktree was clean. The implementer's five reported passing focused tests cover both new profiles, scope drift, wrong values/counts/totals, and apply/undo; I did not repeat database fixtures.

No code, database, SSH session, or deployment was changed by this review. Approval covers this finite code extension. Fresh TEST/PROD member/preimage binding, independent candidate approval, and actual data application remain execution steps.
