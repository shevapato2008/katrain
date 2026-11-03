# Authoritative Rank Supersession Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax. This task prepares the plan only. The controller sends it for independent Astra max review, at most two rounds, before implementation; do not independently start additional review or implementation agents.

**Goal:** Let an immutable native publication replay and its current API verification recognize one exact, applied historical-rank repair without accepting arbitrary later corrections or changing the original receipt, manifest, or publication key.

**Architecture:** Add one bounded DB authority resolver beside the existing native rank replay helpers. It accepts either the unchanged original rank or a single historical-repair journal whose complete beforeimage is the original native afterimage and whose complete afterimage is the current row. A separate current-API verification context is derived by this resolver locally or through one fixed, authenticated SSH read operation; it never authorizes writes or replaces the original publication receipt/report.

**Tech Stack:** Existing Python, SQLAlchemy/PostgreSQL, native manifest V2/V1 rank snapshots, historical repair V1/V3 snapshots, fixed SSH receiver, HTTP API verifier/checkpoints, pytest. No new service, signature/key system, table, general journal-chain engine, provider call, or source filesystem access.

---

## Evidence and fixed scope

Worktree: `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/kifu-rank-hourly-20261103`. Every implementation/test command runs from this directory. Preserve unrelated changes. This plan does not cover the separate `0ef`/`08b` receiver failures, collector configuration, search projection, hourly scheduling, duplicate cleanup, or the paused 1934-record investigation.

The finite read-only diagnosis is `output/kifu-rank-hourly-20261103/hourly-run-99352/cfd-root-cause-and-safe-design.md`, SHA256 `087a2f3d673d5c2fed714eab8708b5970548dd785760bf52294b49d57ae7d08a`. Its evidence shows:

- Original key `19x19-batch-cfd82ce9add2e3080d5155da`, manifest `e7358ebe588ed69c53608fede048d611e9665d90bc6fdc991ab93955eb46fa5f`, TEST native batch1433, unchanged receipt SHA `bb5537088a6ad55da9c7d0ca382a2879b37452f1c7906aaf12e1270fe8474207`.
- Five inserted public albums180554–180558, source items91931760/91931761/91931767/91931768/91931769; no canonical/original alias remap. Ten snapshot IDs8530–8539 were replaced in place by approved HOME repair batch2998, part1410, SHA `ca687092c1d99cd7e441d7c07df13c2c97f6081c52d95d007f2a15fa77dce59f`, index SHA `911a981a7ca041d75a9b2ed70b80540c0b33f8cf6f16a74e8d2c6517a0d020b4`.
- Every native original afterimage equals the repair beforeimage and frozen part beforeimage; every current row equals the repair afterimage and frozen part result. Original immutable facts, owners, raw ranks, numeric grades and source SGF hashes remain unchanged. This is authoritative supersession, not unexplained drift.
- Current snapshots are V3/source, `target_date=null`, `refusal_reason=untrusted_target_date`; all five original SGF roots lack DT although source metadata supplies2026-10-28. Wu Yiming's two slots and Sekiyama Toshimichi's black slot change `professional_dan` to `dan_unspecified`; all ten displays change from Chinese-number raw values to canonical numeric bare-dan values. The full machine provenance also changes.
- The saved TEST report still validates against the original M/receipt:25 detail checks and5 cards, report SHA `e9cbea6dc4282205dbdc0fa39276c8563bf5daa88c9224370b04f9e2427d55f6`. Stage is `retry_wait`/`resume_phase=test_verified`, PROD receipt null. At this phase TEST is replayed for existing search recovery, then the original saved report is transported; TEST is not re-GET-verified.
- At diagnosis time PROD has neither these five exact source links nor a native batch for M. Its original first publication therefore legitimately creates original V1 ranks; a later finite V3 repair is a separate operation below, not a changed ingestion request.

These are diagnostic identities, not constants to bake into product code. Live operations must freshly confirm them before acting.

## File map and reuse

Modify only these product files as needed for this journey; no new product module is necessary:

| File | Responsibility |
| --- | --- |
| `katrain/kifu_ingest/catalog.py` | Shared finite authority proof, strict replay integration, bounded read-only context entry point. Reuse `_check_source_receipts`, `_rank_local_owners`, `_rank_source_context`, `_assert_retained_rank_row`, old fact checks and shared `EvidenceBudget`; make lock behavior explicit only where this read path needs it. |
| `katrain/kifu_ingest/sync.py` | Fixed SSH context client, trusted loader integration, exact current display/origin/source expectations, separate current-report validation and context-bound checkpoints. |
| `katrain/kifu_ingest/orchestration.py` | Strict, bounded read-only receiver operation before the existing publish branch. |
| `katrain/cron/jobs/kifu_ingest.py` | Supply local TEST and fixed remote PROD context loaders to current API verification. Preserve existing resume phases, key/M, native receipts and saved original verification. |

Extend the existing focused tests:

- `tests/web_ui/test_kifu_historical_rank_native.py`: real native→historical-repair authority and unchanged refusal paths.
- `tests/test_kifu_api_verification.py`: exact current API detail/card expectations and checkpoint binding.
- `tests/test_kifu_incremental_cli.py`: strict read operation/SSH contract, real read-only DB behavior and no writer/provider/search calls.
- `tests/cron/test_kifu_hourly_orchestration.py`: existing frozen-package replay/transport and trusted loader wiring.

Reuse `historical_rank_repair._validate_part`, `_artifact`, `manifest_sha256`, `_database_identity` and `historical_ranks.bind_rank_decision(lock=False)`/resource helpers. Do not modify `historical_ranks.py`, `historical_rank_repair.py`, their policy or code-hash rules: approved repair code SHA remains `b009f59cb7160689a2ee48ebc1ac328ebbffe3fdb1ccb0217b42183e977d7300`. Do not rerun initial historical qualification on already-applied replay. Existing `AlbumCheckpoint(..., algorithm=...)` supports adding context identity without changing `verification.py` or the old checkpoint namespace.

## Contracts that implementation must preserve

### 1. Exact single-hop authority

The new proof is a narrow alternative to the current `row == frozen snapshot` assertion, not a replacement for ordinary validation. Use the original-equality path unchanged. In the alternative path require all of the following in the existing writer transaction before replay returns:

1. Original native batch is applied and its format/key/M, source receipts, receipt SHA, source-to-album mapping, original manifest snapshot/binding and original rank fact are valid. Find exactly one original rank journal row for the bound snapshot ID and require its full afterimage to match the frozen native binding. Do not synthesize a predecessor from the incoming snapshot alone.
2. Current snapshot has the same ID, album and side and belongs to one applied `kifu-historical-rank-repair-v1` batch with key `historical-rank:<partSHA>`. Reject native `rank_only`, source-rank repair, arbitrary corrected rows, unknown formats, pending/failed/undone batches, missing/ambiguous journals and multiple hops.
3. Load and validate the exact existing repair artifact/part: manifest SHA equals batch bundle SHA equals canonical part SHA; artifact equals `_artifact(part)`; `_validate_part(part)` enforces existing shape/policy/code/caps. Its database identity equals this DB. Exactly one part change and binding cover the requested slot.
4. Repair journal **complete beforeimage** equals original native journal **complete afterimage** (including snapshot ID, fact binding, publication key and native batch ID). It also equals part `snapshot_before`. Repair journal complete afterimage equals the current complete row and agrees with part `snapshot_after`, hash, publication key, batch and fact-null rules. No lookup of an earlier acceptable link through another correction.
5. Current source path/link/owner FK/raw name/raw rank/metadata and original SGF remain exact. Validate target root/source metadata and SHA using existing source checks, then compare fresh `bind_rank_decision` with the part's exact frozen binding; validate any frozen original basis similarly. Do not accept an unrelated applied V3 snapshot merely because its own hash is valid.
6. Under replay's existing writer/relevant-table/row locks, recheck the current afterimage before returning. Continue the existing **original immutable legacy fact** validation after successful supersession; do not `continue` past it. Keep all other source/name/catalog/receipt guards and exact-original strict tests.

The read-only context route performs the same proof in one bounded coherent READ ONLY transaction, using `lock=False` for body/basis/target reads; it never invokes publish, `_lock_writer`, `FOR UPDATE`, repair apply/undo, a search writer or providers. Snapshot consistency is read evidence, not a claim that DB rows cannot later change. A later API/current-row mismatch must fail, not select a new expectation silently.

### 2. Trusted current-API context, distinct from publication outcome

Use one internal resolver and a small versioned context. The exact schema is allowlisted; it contains no SGF body, full artifact/part/journal, secret or arbitrary SQL. At minimum:

```text
version = kifu-rank-publication-context-v1
manifest_sha256, receipt_sha256, database_identity, source_mapping_sha256
slots[] = {
  source_key, source_item_id, album_id, side, snapshot_id,
  original_snapshot_sha256, current_snapshot_sha256,
  repair_part_sha256, repair_batch_id, predecessor_after_sha256,
  successor_before_sha256, successor_after_sha256,
  expected = {rank, rank_origin, rank_source}
}
content_sha256
```

`slots` contains only proven superseded slots, with unique complete membership within the bound receipt. Unchanged slots continue existing frozen snapshot/rank_outcome expectations. All proof/expected values are generated from the resolver's DB reads and standard `display_rank_for_game_slot`; neither caller nor API output can provide them. `rank_source` comparison includes policy, snapshot SHA, source reference/SHA, system/category, evidence/as-of date, origin and refusal, not just the visible 九段 text. Existing V3 `rank_outcomes` remains unchanged; this context does not masquerade as an outcome for a legacy request.

A canonical hash detects altered bytes; it is **not** authorization. The trusted local code calls the DB resolver. The remote loader consumes only the response to its own authenticated fixed SSH call, validates its exact request binding, DB/target mapping and schema/hash, and never accepts a caller-supplied context argument at an external boundary. Persisted context JSON must be freshly resolved/compared before reuse as current authority. The receiver independently derives its own local context; TEST's successor JSON cannot authorize any PROD rank write.

Keep the old native receipt and old saved TEST verification byte-for-byte. A new current report is a distinct versioned supplement bound to original M/receipt SHA, actual target/DB identity and context SHA, plus the usual actual five-language/detail/card evidence. It does not overwrite an already-saved original report or become a standalone substitute for original TEST authorization at receive. A legacy package lacking its required original verification remains refused rather than manufacturing historical verification from current API output.

For the current supplement, validate the context against its freshly returned trusted-loader result before accepting any API evidence; schema/hash alone is not sufficient. Do not route a caller-supplied supplement through the original `validate_test_verification` acceptance path.

Bind new current verification checkpoints to `CURRENT_RANK_ALGORITHM + ':' + contextSHA` using the existing algorithm parameter. Old non-context checkpoints/reports stay in their original namespace and remain valid as original historical evidence. A changed authority/context gets a different checkpoint; old V1 evidence cannot satisfy current API checks. Default verification without a supersession context retains its exact existing behavior and output. Load this compatibility context only for legacy V1-request verification; ordinary new V3 publication/verification adds no SSH call or context namespace. An empty proven context continues the old algorithm/output. Same-source V3-to-V3 corrections and canonical-alias reuse are not generalized by this plan.

### 3. Fixed SSH read operation and bounded work

Request schema is exactly:

```json
{"operation":"read-rank-publication-context-v1","manifest_sha256":"<64 lowercase hex>","receipt_sha256":"<64 lowercase hex>"}
```

Reject unknown keys, malformed strings, oversized request (>1KiB) and caller rank/snapshot/correction/batch/path/SQL fields **before opening the DB**. Reuse `_receiver_command` and the existing forced receiver; do not add a general query endpoint, alternate command or dynamic target. Read the one applied native batch by indexed M, pin its exact original receipt hash, and obtain source membership from its immutable artifact. Reconstruct/check M from its frozen logical manifest plus exactly bound DB bodies where needed; do not accept a caller's reconstructed rank data. The actual database/DSN is selected only by existing role configuration. No manifest enumeration or library discovery.

Return only the bounded context JSON (`status=resolved` or a fixed safe unavailable error); no raw exception, SQL, environment, DSN, body or artifact. Authenticate with the existing fixed SSH key/host policy, not a new key/signature service. A read request must dispatch before any normal publication/search/provider setup. Neither the read request nor its response changes stage/publication state.

Ceilings per resolver operation:

- At most100 receipt games /200 slots /200 owners; at most one native authority plus200 unique successor batches and400 selected slot-journal rows. Deduplicate selected artifacts per batch in an operation-local cache.
- Scalars and authority JSON together ≤32MiB, measured with counts/UTF-8 lengths **before** body/JSON fetch. Each repair part remains ≤4MiB and200changes under the existing validator. A native authority artifact must also fit the cumulative ceiling. Reject a whole proof on overflow; never truncate and accept a subset.
- Source/basis SGFs ≤256KiB each, cumulative8MiB with one shared `EvidenceBudget` across source receipts, proof and bindings. Count already provided bodies once and reuse exact cached bodies while freshly checking scalar/root/source/FK/hash. No phase-local resets.
- Bounded relevant queries ≤5s with the existing timeout helper restoring parent settings. Fixed remote read timeout30s, constrained by the caller's remaining verification deadline; no automatic publication/replay fallback on timeout.
- Context response ≤1MiB; context plus current report/evidence still fits the existing4MiB verification ceiling. Keep existing16MiB publication envelope and other original limits unchanged.

## Chunk 1: Generic compatibility and current verification

### Task 1: Prove the single supported successor, preserving rejection

**Files:** `catalog.py`; `tests/web_ui/test_kifu_historical_rank_native.py`.

- [ ] Write a synthetic native V1 publication followed by **real existing** `historical_rank_repair.prepare_manifest(album_ids=[...])` and `apply_in_transaction`; include the actual cfd semantics (bare source rank, metadata-only date, old professional category → current unspecified). Capture original M/key/receipt, facts/raw columns and native journal before repair. The new expected result is successful native replay returning the exact original receipt with no further row writes.
- [ ] Add focused parameterized negative mutations: wrong/missing original journal; wrong predecessor or successor; altered part/hash/binding/source/owner/raw/SHA; pending/undone repair; unrelated generic `rank_only`; second hop. Rehash forged JSON in at least one case so a self-consistent hash alone cannot pass. Assert rejection and unchanged state. Keep `test_replay_rejects_changed_journal_or_later_cas_without_writing` unchanged and passing.
- [ ] RED command (new positive test must fail at the existing frozen-snapshot guard):

```sh
PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_kifu_historical_rank_native.py -k 'supersession or replay_rejects_changed_journal_or_later_cas'
```

- [ ] Implement the finite proof in `catalog.py`, reusing source/binding/repair validators. Make lock/read behavior explicit, share EvidenceBudget, and keep unchanged-original and legacy-fact checks strict. Do not run historical initial resolution or mutate the original artifact/receipt. Tests must prove that tampering the old fact still rejects even after the successor proof is valid.
- [ ] GREEN the command, then run `test_kifu_rank_publication.py` plus the native suite once to catch prior snapshot/undo/rank-only behavior. Commit only the task files with `allow exact applied historical rank successors on replay`.

### Task 2: Resolve a bounded current context locally and through fixed SSH

**Files:** `catalog.py`, `orchestration.py`, `sync.py`; `tests/test_kifu_incremental_cli.py` and the native authority tests.

- [ ] Add failing real-fixture tests for `{operation,M,receiptSHA}` returning only DB-derived current expectations, plus invalid extra rank/path/query fields rejected before `_engine`. Use a fixture where the requested legacy publication was legitimately repaired; verify the original receipt and all DB tables remain exact before/after the read.
- [ ] Add guards proving no publish/apply/undo/writer-lock/ES/provider function is called. Count source body returns, assert shared8MiB caching across repeated slots, and test authority-JSON/body overflow rejection before excess fetch. Reuse current resource helpers/fixture instrumentation rather than adding a new framework.
- [ ] RED command:

```sh
PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_kifu_incremental_cli.py -k 'rank_publication_context'
```

- [ ] Add the strict read operation and fixed SSH client. The local entry point takes only engine/M/receiptSHA, starts a coherent read-only transaction and calls the same proof helper with locks disabled; it derives and returns the context above. Do not return giant journals/parts or let the caller choose DB, source list, snapshot or expected rank. Missing authority uses one fixed safe error and exit status2.
- [ ] Add one opt-in disposable PostgreSQL case using `KIFU_STANDARDIZATION_TEST_PG_DSN` and a UUID schema, reusing existing schema-fixture conventions: actual `SET TRANSACTION READ ONLY`, no `FOR UPDATE`/DML/DDL on this path, timeout restored, context matches SQLite semantics. Without env skip; do not find/print credentials or touch public schema. The controller supplies the DSN in memory. This case is necessary because SQLite cannot enforce PostgreSQL read-only/locking behavior.
- [ ] GREEN the focused tests and CLI suite. Commit these files with `resolve current rank authority through a bounded read operation`.

### Task 3: Verify current API ranks using trusted authority, not receipt mutation

**Files:** `sync.py`; `tests/test_kifu_api_verification.py`.

- [ ] Add a failing real-format mock API case: the original V1 receipt/manifest remains unchanged, API returns repaired V3 display/origin/full source provenance, and the verifier obtains its expectations from the trusted context loader. Verify all five languages and the public card, and retain the original saved report separately.
- [ ] Negative cases change only system/category, evidence/as-of date, source SHA/policy/refusal or snapshot SHA while leaving visible 九段 text equal; each must fail. Reject a caller-forged context, a response for another M/receipt/DB/target/mapping, duplicated/missing slot, and over-budget payload. An old V1 checkpoint must cause fresh current GETs, not a false hit; a valid context-bound checkpoint may resume normally.
- [ ] RED command:

```sh
PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/test_kifu_api_verification.py -k 'supersession or current_rank_context'
```

- [ ] Wire a trusted **loader**, not a public bare-rank override, into current verification. Derive expected triplets only from the resolver response; run original raw metadata/SGF/name/source checks unchanged. Add the distinct current-supplement algorithm/report validator and use `AlbumCheckpoint`'s existing algorithm parameter to bind context SHA. Keep the original report transport validator's legacy behavior; a current supplement cannot stand in for required original TEST evidence or change receiver rank inputs.
- [ ] GREEN focused cases and the existing API verification suite once. Commit with `verify superseded ranks against trusted current authority`.

### Task 4: Close the frozen hourly journey without refreezing

**Files:** `cron/jobs/kifu_ingest.py`; `tests/cron/test_kifu_hourly_orchestration.py`; extend the preceding suites only for one end-to-end fixture.

- [ ] Write a failing synthetic5game/10slot journey mirroring cfd: TEST original publication/report; official historical repair; stage at test_verified; natural resume replays successfully; exact old report/M/key is sent; independent PROD with no five originals publishes original V1 once; repeated resume returns original receipts without writes. No current context may be sent as a replacement rank payload or alter expected TEST/PROD rank outcomes.
- [ ] Supply TEST's local DB and PROD's fixed SSH authority loaders to current API verification only. Keep stages and old saved evidence unchanged. A context load failure blocks that verification; it never starts a publisher, alternate key, reset, skip or repair. Assert generic `rank_only` supersession still fails replay. Check original publication still uses the existing ES protocol; the new read operation never enters it.
- [ ] RED/GREEN command:

```sh
PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/cron/test_kifu_hourly_orchestration.py -k 'supersession or frozen'
```

- [ ] Run the final focused set once after code stabilizes:

```sh
PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_kifu_historical_rank_native.py tests/web_ui/test_kifu_rank_publication.py tests/test_kifu_api_verification.py tests/test_kifu_incremental_cli.py tests/cron/test_kifu_hourly_orchestration.py
```

Expected: all pass; opt-in PostgreSQL runs only with the controller-supplied test DSN. Record focused counts/PG result, `git diff --check`, changed files and commit SHA. No full GPU/UI suite or new all-library audit is needed for this backend compatibility change.

- [ ] Commit wiring with `preserve frozen hourly evidence across authoritative rank repair`. Request the controller's fresh independent code/security review before normal integration/deployment. Follow existing feature→develop→parent-pointer→two-server release workflow; preserve foreign changes and current role configuration. This plan-writing task authorizes none of those operations.

## Chunk 2: Separate cfd operations after reviewed code deployment

This is not an automatic branch in the new resolver and is not authorized by plan preparation. The controller approves exact command/pins after review. Do not reuse an original-receipt compatibility proof to write a replacement rank.

### Task 5: Let the unchanged original package complete naturally

**Files:** no product files; retain small private operational evidence under `output/kifu-rank-hourly-20261103/` and existing private server audit paths.

- [ ] After reviewed deployment, freshly confirm actual runtime/backend bytes and cfd original key/M/TEST receipt/report hashes, exact5game membership, current single-hop HOME repair authority and PROD absence/current state. If state differs from diagnosis, stop for review; do not recreate the diagnosed conditions.
- [ ] Observe the existing hourly scheduler retrying the original package through its existing phases. Do not manually publish/replay, edit a receipt/report/stage, change key/M, synthesize a verification or force an offset. Failure remains a failure with safe guard evidence.
- [ ] Verify exact original TEST receipt/report preserved; PROD original receipt records original M and5game source mapping; actual PROD APIs match its own current/original authority. Record the original PROD native batch and ten original snapshot bindings for the next finite repair. Do not claim these original V1 ranks already equal HOME V3.

### Task 6: Independently audit/apply exactly those five PROD originals with the existing repair

**Files:** no new product implementation, migration or corrector. Reuse `scripts/repair_historical_kifu_ranks.py` (`--album-id` repeated five times) and `historical_rank_repair.prepare_manifest(..., album_ids=[exact five IDs])`/public transaction apply. The existing option limits candidates/body reads/writes, **not the streamed all-album scalar census**; retain and report that distinction instead of claiming target-only SQL or changing the b009 repair module. This does not rerun SGF resolution for unrelated targets.

- [ ] Once original PROD publication is confirmed, run a **new read-only audit with exactly five original candidate albums /ten slots** using existing ordinary repair APIs and their normal streamed scalar census, source-aware policy, fresh DB/code identity and one explicitly pinned matched_at. Resolve via PROD's own existing original evidence, not by copying HOME target IDs/bindings or setting the desired answer. Preserve the old full-audit/index and all old journals.
- [ ] Freeze the exact finite part, original/after snapshots, fresh local bindings, code/DB/part hashes, census and refusal reasons. Compare the ten portable results with the diagnosed HOME outcomes; any difference is reviewed as a difference, never overwritten to force parity. Missing DT must continue to block inference; source numeric grades must remain unchanged.
- [ ] Obtain independent review of this concrete five-album/ten-slot candidate and fresh backup/ES/writer/CAS/runtime pins under the existing operational protocol. If fewer/more slots qualify or a target changed, stop for a revised exact review. Do not piggyback unrelated pending sources or another full-library repair.
- [ ] Only after the controller's explicit approval, apply through the existing public historical-repair transaction helper and writer/ES protocol, with exact expected part SHA and complete beforeimages. This creates a new ordinary applied repair batch/journal; it never fabricates or overwrites old native snapshots' **original evidence**, native receipt, manifest or ingestion key. On failure retain committed/unknown evidence; no skip/offset/automatic undo/reset.
- [ ] Verify the ten current afterimages/journals/bindings and actual API display/origin/full machine source using each environment's trusted current context. Verify replay of each original native publication still returns its original receipt while proving its own exact successor. Record paired logical parity or reviewed differences; no source filesystem read, provider call, data deletion or new publication key.

## Completion and review boundary

Plan delivery is the sole authorized action now. The controller owns at most two plan-review rounds. Implementation requires approved plan, RED→GREEN evidence, preserved strict-negative tests and fresh independent final review. Live deployment and the finite PROD audit/apply require their own concrete approved pins/commands. Until then: no product edits, PostgreSQL writes, stage mutations, replay, publisher/context execution or changes to the `0ef`/`08b` systems.
