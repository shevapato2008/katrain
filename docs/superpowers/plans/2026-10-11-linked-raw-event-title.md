# Linked SGF Literal Event Titles Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store and display the five reviewed full titles for 38 already linked historical event spellings, preserving their years, editions, SGF and existing event links.

**Architecture:** Add explicit `linked_sgf_literal_v1` / `sgf_english_linked_event` branches to the existing owner, evidence, batch and shared reader flow. Retain the old profiles unchanged. Freeze complete physical membership and exact legacy CN preimages; reuse existing signatures, locks, journals and rollback without DDL, a new template system or frontend changes.

**Tech Stack:** Existing Python, SQLAlchemy, PostgreSQL and pytest; current native importer and web deployment overlays.

**Approved design:** `docs/superpowers/specs/2026-10-11-linked-raw-event-title-design.md` (SHA-256 `d69c0e574a973073fc1ab55fcb179a09fd7589ba10c33529d6643b6b7915d19a`). The user delegates decisions to independent gpt-6-astra/max; plan review is limited to two rounds.

## Chunk 1: Focused implementation

### Files and ownership

| File | Change |
| --- | --- |
| `katrain/web/kifu/raw_event_translation.py` | Explicit new profile, exact core/edition/Oteai-year shapes, reviewed core references, persisted qualification. |
| `scripts/kifu_raw_event_title_owners.py` | Complete linked scope, physical edition column, SGF proof and legacy pending CN preimage. |
| `katrain/web/kifu/name_evidence.py` | New SGF basis source validation; preserve real source and independent approval requirements. |
| `katrain/web/kifu/name_candidates.py` | Bind new profile, owner, scope, references and research hash. |
| `katrain/web/kifu/name_batch.py` | Recheck full linked scope under existing transaction locks; upgrade exact existing CN row. |
| `katrain/web/kifu/identity.py` | Shared finite album eligibility for exact title display, search and strict coverage. |
| Existing four tests below | Focused representative acceptance and regression; no separate audit framework. |

Root owns SQL, deployment and Git integration. One fresh implementation agent works in `.worktrees/linked-raw-event-title`; source research and the current R21 player batch stay in the original checkout. Never change `models_db.py`, endpoints, parser, formal identities, album links, aliases, sources or SGF.

### Task 1: Explicit profile, complete scope and existing names

- [ ] Extend fixtures in `tests/web_ui/test_kifu_raw_event_title_owners.py` and `tests/web_ui/test_kifu_raw_event_title_translation.py`: linked `Oteai`, `Oteai 1973`, actual `28th Honinbo` (edition=`28th `, core=`Honinbo`), and `14th Judan`. A linked owner has an exact old CN `review/direct_translation` row with null evidence/revision, plus four empty locale preimages. Use actual existing parsed shapes, not a new parser.
- [ ] Run the new test selection before implementation; expect refusal by old linked-event/profile/name-empty gates. Command: `PYTHONPATH=. /Users/fan/Repositories/katrain-kiosk-go-kifu/.venv/bin/python -m pytest tests/web_ui/test_kifu_raw_event_title_owners.py tests/web_ui/test_kifu_raw_event_title_translation.py -q -k linked_sgf`.
- [ ] Add only the explicit new constants/branches. Keep `decision_kind="translated"`, `translation_method="literal_event_title"` and existing evidence version. Require matching basis/profile everywhere, exact existing parts roundtrip and correctly formatted ordinals/year.
- [ ] Freeze sorted unique full physical matching IDs, `game_total`, event/FKs, visibility/duplicate/selection status, source path, SGF byte hash and EV/GN arrays. Require one nonempty reviewed formal series ID; editions may be null or existing valid values and must remain unchanged. Reuse existing physical-column reflection for old ORM compatibility.
- [ ] Capture and hash the entire existing name set for owner approval. Accept only explicitly listed legacy CN rows in the new profile; old profiles continue requiring no names. Owner approval writes review metadata/status only.
- [ ] Require finite `reviewed_core_refs` with actual material hash, locator, supported core/language and persisted excerpt/decision. SGF witnesses the raw title; sources witness core names. Do not invent HTTP captures or require a published full phrase for every year/edition.
- [ ] Add focused rejection parameters for wrong profile, changed parts/year, missing core proof, scope membership drift, mixed series, hidden/duplicate/selection and EV/GN mismatch. Run both test files; old and new cases pass. Root records this checkpoint before integration.

### Task 2: Transactional names and consistent finite reader

- [ ] Add failing integration cases in the existing raw-title tests: full five-language apply, CN row ID/created-at retention, changed CN/owner/scope rejection before writes, idempotence and undo restoring old CN. Assert no album/FK/SGF/source writes.
- [ ] Extend evidence/candidate validation and existing locked batch guard for the explicit basis. Preserve exact name preimages, independent approval, collision policy and trusted bundle hash; `album_links=[]`. Recheck current complete scope inside the write transaction, not only at owner preparation.
- [ ] Extend the shared qualification path with per-album `(id, raw, event_id)` membership plus live edition, visibility, selection, source path and SGF hash. Linked proofs require explicit opt-in or a separate qualification function: default `eligible_literal_raw_name` calls continue refusing the new basis. This prevents `legacy_raw_events._eligible` from turning it into an unlimited unlinked raw mapping. Persist all proof needed at runtime; local research files and public web fetches must not be runtime dependencies.
- [ ] Give an eligible linked full title precedence over a generic formal series name and the old Oteai special case. Other formal, obscured, selection and unlinked behavior remains unchanged.
- [ ] Batch-read required fields for the page or finite search candidates. Avoid per-album deferred SGF reads and request-time whole-catalog scans. SQL search and Python display must share the same finite eligibility, including live drift checks.
- [ ] Extend `tests/web_ui/test_kifu_name_api.py` and `tests/web_ui/test_kifu_name_coverage.py` for list/detail/exact translated search/strict agreement, out-of-scope same-raw exclusion, evidence revocation and scope drift. Include old ORM without mapped edition/hidden attributes and a legacy-helper check that new same-raw albums or scope members with cleared FK never inherit linked proof. Actual R23 endpoint uses shared identity; no endpoint/legacy module leaf is needed.
- [ ] Run: `PYTHONPATH=. /Users/fan/Repositories/katrain-kiosk-go-kifu/.venv/bin/python -m pytest tests/web_ui/test_kifu_raw_event_title_owners.py tests/web_ui/test_kifu_raw_event_title_translation.py tests/web_ui/test_kifu_name_api.py tests/web_ui/test_kifu_name_coverage.py -q`. Expected: all pass; query assertion proves batch reads.
- [ ] Independent spec review, then code review of the six-file change and relevant tests. Fix material issues until approved; review only actual data integrity, reader consistency and deployment boundaries. Root commits only exact reviewed files and design/plan, then integrates into the feature branch.

## Chunk 2: Real data and deployment, root only

### Task 3: Capture and sign the finite 38-owner batch

- [ ] A preparation worker builds a read-only parameterized supplement for exactly the frozen 38 raws; root reads and runs it once per environment. Current post643 five-field capture is insufficient for edition/SGF/source proof. Capture complete owners/names/evidence and all physical matching album fields; do not scan SGF beyond this set or filter away conflicting records.
- [ ] Root cross-checks actual native/web baseline leaves and latest receipt. The R21 player batch and four separate brand updates may finish first; bind new event packets to the actual subsequent preimages rather than pretending post643 is still current.
- [ ] Build owner plans and five-language research/name packets with independent Astra approval for every finite member and complete title; reuse existing core evidence. Refused raws remain unapplied with a concrete reason. Name packets upgrade exact old CN and add empty other locales; no relationship changes.
- [ ] Freeze affected distinct album IDs and run current wide/strict before metrics once. Report 7,615 as potential affected scope, never automatic new coverage.

### Task 4: Test-first deployment and real write verification

- [ ] Publish only five reviewed shared modules to web, plus the owner script to the native importer/coverage runtime. Preserve actual images, Compose/env/static and the R23 endpoint/analysis handler. No full repo models swap or DDL. If module imports require any extra changed leaf, stop and review that dependency before deployment.
- [ ] Deploy TEST reader/importer first. Validate four representative shapes through actual list/detail/search and native dry-run using each environment's own IDs and old ORM. Health checks/import success alone are insufficient.
- [ ] Execute signed TEST owner approval, then dry/apply/verify names using existing guarded helpers. Verify exact receipts, unchanged FK/SGF/source and reader/search/strict qualification.
- [ ] Deploy PROD matching reader/importer leaves only after TEST passes. Repeat actual dry/apply/verify and representative public API checks. A deployment or write failure stops dependent writes; use existing batch undo and saved leaf rollback.
- [ ] Run after metrics on identical finite IDs. Inherit unaffected actual baseline explicitly; report both wide and strict deltas, P5 unchanged, formal event denominator unchanged, exact applied name count and any holds.
- [ ] Archive actual source/approval/owner/name/verify/deployment receipts, update the existing HTML and coverage decision document, targeted commit and push. Continue the next player/event batch; do not stop at a progress response.

## Verification budget

Reuse existing fixtures and immutable importer boundaries. Baseline the two owner/title suites once; the final gate is the four affected suites plus representative real TEST and PROD requests. Broaden checks only for an identified remaining regression risk. No frontend snapshots, full-catalog rescan, unrelated services or new evidence infrastructure.
