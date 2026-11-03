# Canonical display coverage — independent spec review

Date: 2026-11-03. Reviewed commit: `e9d18fb3f414aefae9093050b074ce59d20fff7d`. Requirement: Task 1 of `docs/superpowers/plans/2026-11-03-kifu-hourly-live-recovery.md`, approved by the independent Astra round-one plan review.

**SPEC: APPROVED.** No blocking requirement gap or scope expansion found in this commit. This is a spec review of the coverage correction only; it is not the subsequent independent Astra quality/final review, production recovery approval, or evidence that the active hourly round has completed.

## Requirement coverage

- `_coverage` resolves a duplicate only through the existing `verified_display_duplicate` helper. That helper still checks the complete immutable dedup manifest/journal ancestry, current members and original source links. The commit does not change its proof rules or fabricate name evidence.
- For proved aliases, coverage collects the actual canonical IDs, explicitly loads only public, nonduplicate canonical albums, requires exact membership, and deduplicates them with already requested public albums. All five existing `strict_slot_approvals` checks then run against those displayed albums. The canonical album must have all three approved slots in every language.
- The public native regression creates real previously signed finite raw-player scopes, applies the reviewed display dedup afterwards, establishes the alias's white approval is unavailable while the canonical remains approved, and successfully publishes a new game whose preflight includes the old scope. It also checks same-package replay and both original receipts, retained evidence/source rows, old SGF bodies, and the alias pointer. No old proof is rewritten or broadened.
- A genuinely missing canonical Korean approval still rejects the public native publish with the existing coverage error and leaves the complete captured database state unchanged. This is not a bypass for unapproved canonical names.
- Malformed journal, cyclic pointer and nonpublic canonical cases cannot place the claimed target in the approval set. The existing behavior of ignoring an unproved hidden alias inside coverage is preserved; `_require_source_publication` still rejects that alias as a requested source. The commit does not relax original source ownership, source receipt membership, SGF/rank binding or compensation checks.
- Product changes are confined to `_coverage`; the only other committed file is the focused regression suite. No migration, queue/state reset, cron role change, token accounting change, paid-call path or publication-key change is introduced.

## Independent verification and limits

Read the complete approved live-recovery plan and its review, the exact commit diff, relevant native call sites/source-publication guard, the unchanged duplicate-proof helper, and all six new cases. Independently ran:

```text
PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_kifu_canonical_display_coverage.py
```

Result: **6 passed in 5.13s**. This verifies the requested narrow native/coverage behavior; the controller's larger 138-pass/1-skip run and the worker's earlier RED result are separate evidence, not independently rerun here.

The actual read-only `6086 → 907` observations and active restored cron status were supplied by the controller. This reviewer made no live database query and did not touch the running round, live data, services, paid providers, source filesystem, product, tests or configuration. Only this spec-review document was written. The index, historical audit coordinator and combined operational release remain outside this commit's spec verdict.
