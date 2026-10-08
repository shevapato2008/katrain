# Existing review-name orthography implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Root alone signs research, writes SQL, commits and deploys.

**Goal:** Allow seven existing, unqualified TW review rows to receive independently approved orthographic displays derived from their qualified conventional Chinese names.

**Architecture:** Keep the existing source proof, finite directional character mappings, owner/language scope, collision review and importer transaction. For the Chinese-to-TW branch only, accept a non-null target preimage when the signed candidate binding includes the exact complete physical row, its hash matches, and its status is `review` with no evidence. Existing qualified targets and Japanese-display non-null targets remain rejected. The current importer checks the live whole-row preimage under lock before updates and journals the change.

**Tech Stack:** Existing Python validators, SQLAlchemy importer and pytest fixtures; no schema or frontend changes.

## Task 1 — Focused implementation

Files: `katrain/web/kifu/name_orthographic.py`, `tests/web_ui/test_kifu_name_orthographic.py`.

- [ ] Add a real SQLite-backed fixture for an existing legacy TW review row. Bind its complete before-image in the already signed candidate `preimage_binding`; observe the current NULL-only rejection.
- [ ] Add the smallest validation for this before-image: exact positive physical ID, player ID and language match, status `review`, evidence absent, whole-row hash equals the member/candidate preimage hash. All source and complete-name review hashes remain required.
- [ ] Verify approved/evidence-bearing targets, wrong owner/language/hash, missing before-image and stale live CAS reject; verify NULL behavior and Japanese original display remain unchanged.
- [ ] Verify one actual apply/read-qualification/undo roundtrip using the existing importer fixture, including correct physical row restoration.
- [ ] Independent Astra spec review, then code review; fix material findings. Run the orthographic tests and existing preimage importer tests once.

## Task 2 — Deploy and resume the prepared batch

- [ ] Commit only the reviewed module, focused tests and this plan/review evidence. Preserve unrelated workspace files.
- [ ] Patch that one module onto each current web/importer image; retain PROD legacy SQL adapter and compare runtime file hashes. Restart only each web service using existing production deployment procedure and unchanged environment.
- [ ] Independently review actual next20 sources/rules, refresh context after batch590/page synchronization, then bind the seven exact live target rows. Reject changes after binding.
- [ ] Root dry-run TEST, apply and verify TEST; then PROD. Check representative actual language/search results, update real coverage HTML and archive receipts before beginning another SQL batch.

**Decision:** Delegated to independent `gpt-6-astra`, max effort, as explicitly authorized by the user. No NULL row deletion, unverified source relabeling, identity merge, rank/FK/SGF changes or guessed name conversion.
