# Legacy Duplicate GN Event Selection Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the real event description for the 1,160 reviewed `19x19` albums whose stored event is `GNUGo3.8`, without changing the original album fields or SGF, and keep search, display, and eleven-language coverage consistent.

**Architecture:** A small per-album selection table records the reviewed root SGF property/value and the SHA-256 of the SGF it came from. A finite, reversible import verifies every album and source preimage before inserting selections. The strict API and coverage resolver use a valid selection as the effective event; the search query includes selected raw values. Until a selection and its name are approved, the event remains a gap.

**Tech Stack:** SQLAlchemy/PostgreSQL/SQLite, FastAPI, pytest, existing SGF parser and name review tooling.

**Decision basis:** [independent remedy decision](../../resource/kifu-name-duplicate-gn-remedy-decision-2026-10-02.md), [data audit](../../resource/kifu-name-duplicate-gn-data-audit-2026-10-02.md), [focused guard](../../resource/kifu-name-duplicate-gn-import-review-2026-10-02.md). The existing [full localization plan](2026-10-02-kifu-full-name-localization.md) still sets the 100% release gate. This slice does not change generic first values such as `段位赛`.

## File map

| File | Responsibility |
| --- | --- |
| `katrain/web/core/models_db.py`, `katrain/web/core/migrations.py`, `katrain/web/kifu/migrate_catalog.py` | Add `kifu_album_event_selections` (one row per album, exact selected raw value, SGF SHA-256, property/index, optional event ID, reviewed provenance, batch ID) and `kifu_event_selection_batches`; protect schema during normal startup. |
| `katrain/web/kifu/event_selection.py`, `scripts/kifu_event_selection.py` | Shared exact SGF predicate and finite `validate/dry-run/apply/undo/status` over reviewed member file; one atomic batch, row-level preimage checks, conditional undo. |
| `katrain/web/kifu/name_inventory.py`, `katrain/web/kifu/name_candidates.py`, `katrain/web/kifu/name_batch.py` | Add a versioned, hashed selection supplement to future inventory and allow reviewed raw-event names whose only occurrence is a valid selected `GN[1]`; recheck that scope under the name-batch lock. Existing v2 artifacts retain their original hash semantics and cannot approve a newly selected event. |
| `katrain/web/kifu/identity.py`, `katrain/web/api/v1/endpoints/kifu.py` | Batched approved selections for a page, strict effective-event resolution, and exact/partial search over approved selected raw event and later linked event ID. |
| `katrain/web/kifu/name_coverage.py` | Count a selected event only if its approved row still matches the live SGF SHA-256; missing selection, changed SGF, or unapproved display remains a gap. |
| `tests/web_ui/test_kifu_event_selection.py`, existing name API/coverage/migration tests | Finite predicate, preimage failure, retry/undo, page and search equivalence, frozen coverage. |
| `docs/resource/kifu-name-duplicate-gn-selection-rehearsal-2026-10-02.md` | Reviewed member SHA, clone dry-run/apply/undo and residual gaps. |

## Chunk 1: Selection schema and finite importer

### Task 1: Schema

- [ ] Write failing migration tests for an old catalog and a fresh one. Require one selection per album, FK to album/event/batch, nonempty selected raw, 64-character lowercase SGF SHA, `status` limited to `approved`, and a unique batch hash. Existing albums, SGF, `event`, sources, and old name rows remain byte-for-byte unchanged.
- [ ] Run `uv run pytest -q tests/web_ui/test_kifu_name_schema.py tests/web_ui/test_migrations.py` and confirm the new test fails before implementation.
- [ ] Add models, protected table list, explicit `migrate_catalog` create/verify path. Do not migrate by rebuilding `kifu_albums`.
- [ ] Rerun those focused tests and commit the schema slice.

### Task 2: Safe reviewed batch

- [ ] Write failing tests with a two-GN `19x19` SGF and counterexamples: EV present, extra GN, wrong SO, second program/fragment, mismatching GC, changed SGF hash, changed old event/FK/source/date/round, already selected album, duplicate member, reviewer equal to producer, and conditional undo after another edit. Snapshot test and dry-run must be read-only.
- [ ] Reuse the exact source predicate from `scripts/import_kifu.py` in one shared pure function; assert the imported value equals the reviewed `GN[1]` byte-for-byte. A member pins `album_id`, `old_event`, `old_event_id`, source/path/date/round, full SGF SHA-256, `GN` index 1/value and rule version. The signed scope records actual producer/reviewer IDs and models, production/freeze/review timestamps in order, explicit evidence scope and review conclusion. Its member-set hash and batch hash are deterministic. Do not accept a raw boolean from the controlled list as proof.
- [ ] `apply` uses one transaction/lock and rechecks every live preimage, inserts only selection and batch rows, records before/after images. A retry of the same applied hash is read-only. `undo` removes only unchanged rows from that batch and marks it undone; later edits refuse or skip according to explicit test semantics. No original metadata update.
- [ ] Run `uv run pytest -q tests/web_ui/test_kifu_event_selection.py`, verify pass, commit importer/CLI.

## Chunk 2: Same effective event in API, search, and coverage

### Task 3: Selection-aware name inventory and approval

- [ ] Write failing inventory/candidate/batch tests with an event name that occurs **only** in a reviewed selection, never in `kifu_albums.event`. Its approved raw-event candidate must validate and import; the same candidate must fail if the selection is missing, changed, unapproved, or its SGF hash no longer matches. The old inventory v2 hash and signed Wu/Lee fixture semantics stay stable before any selection exists.
- [ ] Add a versioned selection supplement: sorted `(album_id, selected_raw, sgf_sha256, review/batch identity)` rows with a deterministic digest inside the inventory's own hashed snapshot. Keep original album `event` unchanged. Extend `_inventory_values`, `_occurrence_indexes`, scope hashing and the batch transaction's live snapshot check to use only approved, SGF-matching selections. A v2 bundle cannot claim selected-event scope. The supplement does not turn every selected description into a formal event entity.
- [ ] Run `uv run pytest -q tests/web_ui/test_kifu_name_inventory.py tests/web_ui/test_kifu_name_candidates.py tests/web_ui/test_kifu_name_batch.py`, commit.

### Task 4: Display and search

- [ ] Write failing API tests: a selected real second GN with an approved raw event name renders that translation in list and detail; without approved name it renders localized unverified text; original `event` response and SGF remain unchanged. Program-only GN may still hide if separately approved. Chinese/English/raw second GN search reaches the same selected albums only when the alias is approved and unambiguous. Query count stays bounded by the page, not album N+1.
- [ ] Add an approved selection map to the current strict batched resolver. Choose effective raw event from the selection; if absent, keep current source guard. Search and `total` use a subquery/exists with the **same live SGF SHA check** as display/coverage; after an SGF edit, the former selected name returns no album. PostgreSQL has built-in `sha256(bytea)`; for SQLite test/development, register an equivalent deterministic connection function or a narrowly scoped fallback and assert query/count parity. Use the selection's event ID only after its identity has passed the existing evidence gate. Avoid changing non-strict public behavior before the strict release gate.
- [ ] Include a test that changes SGF after selection: old event-name search has zero result and zero `total`, while direct detail remains a visible gap. Assert the `q` count and page use identical validity filters.
- [ ] Run focused API tests and commit.

### Task 5: Reproducible coverage

- [ ] Write failing coverage tests: a global approved `GNUGo3.8` hidden row never completes a selected real event; a valid selection plus approved effective event name can count; modifying the SGF after selection while leaving album metadata unchanged produces a missing event and a drift flag, never `complete=true`. An unselected real second GN remains missing. Repeat with two batch sizes and compare missing digests.
- [ ] For the bounded selected/`GNUGo3.8` set, read live SGF in one page query and compare to the row's pinned SHA. Resolve effective raw event through the same helper as the API; report a specific `event_selection_drift` count and make any drift fail completion. Keep the original inventory hash for album metadata and include a deterministic selection/SGF digest in the report, so two reports cannot silently claim the same input snapshot after SGF change.
- [ ] Run `uv run pytest -q tests/web_ui/test_kifu_name_coverage.py tests/web_ui/test_kifu_name_api.py tests/web_ui/test_kifu_event_selection.py`, commit.

## Chunk 3: Finite reviewed repair and release gate

### Task 6: Freeze and rehearse 1,160 members

- [ ] Read the 1,160 IDs from the controlled clone JSONL, then fetch each current `sgf_content` from the isolated production backup. Compare each to its pinned SHA **before** reparsing it. Require the exact predicate and produce a minimal finite member file with full preimages. Independently review/sign its exact hash and scope; any changed or excluded row stays unresolved. The 559 second-GN strings are descriptions to classify, not assumed 559 event entities.
- [ ] On a production backup clone with the same code SHA, run CLI `validate`, `dry-run`, `apply`, then check 1,160 selections, original `event`/SGF hash invariance, list/detail/search/coverage examples, and conditional `undo`. Record batch/member hashes and counts; no production data write in this task.
- [ ] Obtain independent code review of schema/importer/API/coverage; fix Critical/Important findings and rerun focused checks. Production import and strict-mode activation remain under the full-plan 100% gate and explicit deployment runbook.

## Parallel ownership

Implement schema/importer before page resolver. A separate agent may research and independently review the finite member evidence while code proceeds; neither agent writes the current production database. Shared `identity.py`, endpoint and coverage files are one code-owner slice. Frontend changes are unnecessary because the strict API already has `display_event`.
