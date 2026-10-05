# Independent code review — 2026-10-06

**Final verdict: APPROVE at `443f898c385f6f823c707b47b0ab128174975717`.** All three original Important findings are resolved. The review rounds below preserve their evidence and disposition.

Reviewed `74d5d25ee1120d4db29d4daefbf89050daf9dabd` against `92e49539` in `/Users/fan/Repositories/katrain-kiosk-go-kifu/.worktrees/kifu-raw-event-title-translation`. Scope: literal raw event title translation, the first 24 owner approvals, shared persisted eligibility, strict/legacy readers, collisions, and existing ledger/undo. Applied the requesting-code-review skill proportionately. Approved design decisions were not reopened.

## R1 — Important: the legacy bridge accesses a column absent from the production ORM

**Code:** `katrain/web/kifu/legacy_raw_events.py:170–171` and `:206–207`.

`reviewed_raw_event_hints` reads `album.list_hidden_reason`; exact search constructs `KifuAlbum.list_hidden_reason.is_(None)`. The captured PROD endpoint at `/tmp/kifu-raw-event-title-live-20261006/PROD/katrain/web/api/v1/endpoints/kifu.py:185–188` explicitly retains the old ORM and therefore reads this database column through SQL text. The overlay does not replace the model.

Any public, unlinked album with a nonempty event reaches the new attribute access during listing, including existing generic/archive descriptions. A legacy-shaped album reproduced `AttributeError: ... has no attribute 'list_hidden_reason'` before a database call. Exact translated search encounters the equivalent class attribute failure.

**Minimal fix:** check hidden state through a bounded SQL query for current page IDs, and use the existing SQL-text hidden predicate for legacy search. Retain the explicit NULL condition; defaulting a missing attribute to `None` would bypass it. Add one representative legacy-model compatibility check.

## R2 — Important: persisted eligibility accepts incomplete source evidence

**Code:** `katrain/web/kifu/raw_event_translation.py:62–69`, `:129–144`; used by both readers and `name_batch.py:526–530`.

The persisted guard verifies a self-contained research hash and then calls only the lossless-parts/core helper. That helper does not validate the required original-language and source-capture schema. Starting from the valid `literal()` fixture, deleting each of `original_language`, source `identity_basis`, source `source_id`, or source `http_status` and recomputing `candidate.research_sha256` still returns `True` from `eligible_literal_raw_name`. The normal importer rejects all four variants. The same incomplete records consequently remain eligible for display/search and the cross-batch collision exemption. Nonempty signature field validation also currently differs between the strict helper and the legacy wrapper.

**Minimal fix:** enforce the required stored research/source and signature schema in the shared pure eligibility path, including original-language consistency and capture checks. Reuse the import validation rules or factor their required pure subset; no source refetch or broader research is needed. Add a focused malformed-proof parity case.

## R3 — Important: legacy exact expansion loses identity ambiguity

**Code:** `katrain/web/kifu/legacy_raw_events.py:198–203`; integration in `scripts/build_kifu_raw2134_overlay.py:75–78`.

The legacy helper permits a translated raw-title group without considering qualifying identity/raw-player names. Its caller assumes empty `player_ids` and `event_ids` means no matching identity. However, captured PROD `identity.py:134–139` deliberately returns empty sets for multiple approved matching identity names with no aliases. The endpoint then replaces its ordinary fuzzy predicate with the raw-title union. Strict matching correctly refuses that expansion.

A pure mocked reproduction supplied two approved player names and two translated raw titles with the same display text: the captured matcher returned `(set(), set())`, the legacy bridge returned a raw union, and `strict_matching_names` returned four empty sets for the same recognized rows. Such query ambiguity can cross locales; the write-time collision check is locale-specific.

**Minimal fix:** for translated raw-title expansion, distinguish no identity matches from ambiguous matches. A bounded SQL existence check against qualifying player/event/raw-player names, or an explicit ambiguity signal from the caller, can preserve the existing fuzzy behavior while keeping the new group exception limited to raw descriptions.

## Other review results and verification

The finite owner tool restricts the 24 exact raw values and 271/222 group totals, requires pending unclassified owners without names, checks complete owner preimages plus inventory/catalog hashes, and writes only review status/metadata. Its apply uses the existing advisory and physical table locks, and records before/after images for conditional undo. No additional blocking defect was found in these inspected paths or the format-2/inventory-4/no-link boundary.

Verification was limited to reading the actual source/tests/captured runtime and two small in-process probes. They exercised persisted-proof corruption, a legacy-shaped album, and ambiguous-name routing without database writes. The parent-reported 48 focused plus 237 existing passing tests were not repeated; their passing result does not cover the reproduced cases. No repository code, SSH session, database, or deployment was changed. This report does not claim that either runtime has been updated.

## Round 2 — 2026-10-06

Reviewed follow-up `e70f4ce2984508f5dc25a8028b870d6590ee6511` against `74d5d25ee1120d4db29d4daefbf89050daf9dabd`, limited to the three fixes and their immediate regressions.

**Verdict: CHANGES REQUIRED — one remaining part of R2.**

- **R1 resolved.** The legacy helper now queries public IDs through bounded SQL and uses an explicit SQL-text NULL predicate for search. The new legacy-shaped model test covers the missing ORM attribute.
- **R3 resolved.** Translated raw exact expansion now checks aliases and qualifying identity/raw-player rows independently, so multiple matching identities cannot disappear into empty matcher results. The tests cover two identities, a raw player, and removal of their approval.
- **R2 source-schema cases resolved; signature parity remains.** At `raw_event_translation.py:191–201`, reviewer ID/model are compared only for equality against the stored evidence, and the conclusion is tested only for truthiness. Setting both candidate/evidence `reviewer_id` or `reviewer_model` to `""`, or setting candidate `review_conclusion` to spaces, still yields `True` from the shared persisted helper. The legacy wrapper's `_check_signature` rejects all three. This is the nonempty signature mismatch already identified in R2.

**Minimal remaining fix:** require `_text` for candidate producer/reviewer IDs and models plus review conclusion before comparison, and apply the same nonblank text requirement to the owner-review signature/conclusion/category-basis fields. One focused signature-parity test is sufficient.

I independently reproduced the remaining three signature cases with a pure in-process probe; the valid control returned `True`. Source inspection and `git diff --check` found no other blocking regression in this follow-up. The parent-reported 161 focused passing tests were not repeated. No code or database was changed during review.

## Round 3 — 2026-10-06 — final approval

Reviewed `443f898c385f6f823c707b47b0ab128174975717` against `e70f4ce2984508f5dc25a8028b870d6590ee6511`, restricted to the outstanding nonblank signature checks.

**Verdict: APPROVE. R1, R2, and R3 are resolved.** The shared persisted gate now requires nonblank producer/reviewer IDs and models plus the review conclusion. Owner approval uses the same nonblank checks for its signature, conclusion, and category basis. No further changes are requested by this review.

Independent verification: the valid control was accepted; the three previously reported candidate/evidence cases and all six owner-review blank-field cases were rejected in a pure in-process probe. `git diff --check` passed, and the working tree was clean. Inspected the five added tamper regression cases; the parent reports 31 focused tests passing, which were not repeated. No repository code, database, or deployment was mutated by the reviewer. This approval covers the reviewed code; runtime rollout and first-24 data application remain the root agent's pending work.
