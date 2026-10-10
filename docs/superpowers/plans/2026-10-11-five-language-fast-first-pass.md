# Five-language fast first pass implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Store every safe missing player and event display name in five languages before the morning, with explicit generated provenance and working list/search readers.

**Architecture:** Add one opt-in `user_authorized_first_pass_v1` generated profile to the existing candidate, evidence, transaction and reader paths. Reuse existing identities, authoritative links, exact preimages, journals and rollback. Preserve approved names. Split frozen whole-catalog work into parallel translation shards and transactions of at most 200 owners; independently check each batch once.

**Tech Stack:** Existing Python/SQLAlchemy/PostgreSQL kifu pipeline; no schema or UI redesign.

**Decision:** `/tmp/kifu-fast-first-pass-decision-astra-20261011/decision.md` SHA-256 `407de435948e0c6329a91c2a82108b5b6045a3c13e8af3806d37602aa7efadfd`. Latest user explicitly permits direct translation when published names are unavailable, requires speed, and forbids excessive reviews.

## Chunk 1: Implement and verify the minimal profile

### Task 1: Generated profile, import and read qualification

Files: create `katrain/web/kifu/name_first_pass.py`; modify `name_evidence.py`, `name_candidates.py`, `name_batch.py`, `identity.py`; add a focused `tests/web_ui/test_kifu_name_first_pass.py`.

- [ ] Add failing examples for generated input without external search, preserving existing approved slots, source/target CAS, real persisted read qualification and exact raw-event scope.
- [ ] Run `PYTHONPATH=. /Users/fan/Repositories/katrain-kiosk-go-kifu/.venv/bin/python -m pytest tests/web_ui/test_kifu_name_first_pass.py -q`; confirm meaningful failures.
- [ ] Add the single explicit generated profile described in the decision; retain old paths and independent signature, collisions, transactions and journals. Mark `verification_level=generated_first_pass`; do not invent source URLs or published readings.
- [ ] Use precise `(album_id, raw, event_id)` scopes for raw titles and existing approved selections; never globally inherit a generated title across different event identities.
- [ ] Re-run the focused file plus the affected existing candidate/batch/identity tests. Record unrelated existing query-budget failures without expanding this task.
- [ ] Perform one independent focused code review, fix actual failures, and freeze exact changed files for root integration.

## Chunk 2: Parallel generation, actual database delivery

### Task 2: Fill the frozen missing pool

Files: `/tmp/kifu-full-firstpass-pool-sol-20261011/*`; per-agent generated JSON chunks; existing name-batch runner and progress documents.

- [ ] Capture TEST and PROD once in read-only snapshots after the actual batch644 receipt; reuse structure artifacts for names-only batches.
- [ ] Assign disjoint frequency-balanced player shards and event core/title shards to available Luna workers. Skip every existing `status=verified` row and every evidence-backed row; write only absent or evidence-free review slots. Supply missing five-language names and truthful method tags, write chunks every 20 entities. No repeated web search or negative-evidence gate.
- [ ] Bind actual TEST/PROD IDs and original rows, check all generated proposed names for obvious mistakes and owner collisions once, and sign exact batches once. Hold only genuinely conflicting identities or damaged data.
- [ ] Before the first new-profile write, root deploys the same approved reader/importer profile to TEST/PROD and RK3562; verify representative read qualification. Root then executes TEST dry/apply/readback and PROD for each at most 200-owner transaction. Preserve journals and prior source URLs; prepared files do not count as uploaded.
- [ ] Report actual completed entities and affected games after each commit; use bounded before/after deltas for fixed wide coverage and strict complete-card coverage. Reserve full-catalog coverage sweeps for the first representative validation and final report. Distinguish generated first pass from sourced names.
- [ ] Archive exact receipts/data, commit and push the authorized branch, and verify language switching/search with representative real API results.

### Completion criteria

All safe missing five-language slots are stored and usable by list/detail/search; report actual remaining identity collisions or damaged/hidden records separately. Other six UI languages fall back to English. A generated first pass is complete for display but is not claimed as an authoritative published translation.
