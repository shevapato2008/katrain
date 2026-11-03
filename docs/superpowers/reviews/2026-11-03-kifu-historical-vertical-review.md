# Historical rank vertical slice independent review

Date: 2026-11-03. Scope: Task 2 native freeze/publication/API and Task 3 standalone historical repair. Initial Task 2 review used `5889b0955f7b52c79d60434a1d688d343227bbac`; Task 3 used `8c51e43d29e2f596e96b3f1367bcd1d40dd69dbd`, including the approved foundation and `5d24dfb82` compatibility fix. Task 4 was concurrently unfinished and excluded from that review; the initial catalog assessment used the fixed Task 2 commit. The committed P2 follow-up is scoped separately below.

**Current spec verdict: APPROVED. Current quality verdict: APPROVED for this Task 2/Task 3 review and the original P2 follow-up.** The sole independently reproduced finding below is fixed. The follow-up first confirmed the spec correction and then checked its code quality. Later retained-receipt contracts and the full integrated release have a separate fresh Astra review; they were not reopened or approved by this narrow follow-up.

## Follow-up verification — original P2 resolved

Follow-up inspected committed `500484e3c` (shared foundation budget/cache), `a475954c9` (repair integration), and native resource propagation from `a3bd8359c`/`2221199f0`. Verification HEAD was `2221199f0e7843233a909e86df179a06122906e2`, containing `3572aa4a4`. This follow-up deliberately rechecked only the original cumulative-fetch finding and its two public regressions.

Spec stage: `EvidenceBudget` now gives the operation a finite content cache and cumulative byte allowance. Repair preparation shares the resource with binding; each repair preflight shares it across all target bindings and fresh initial qualification. Native initial verification, artifact binding and applied replay receive the publication's same resource. A new body reserves its complete size before SQL materialization, so individually valid frozen decisions cannot evade the aggregate allowance by combining them in a larger reviewed part.

Independently ran exactly these two public repair cases:

```text
PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_kifu_historical_rank_repair.py::test_public_apply_shares_large_original_body_across_all_slots_and_verification tests/web_ui/test_kifu_historical_rank_repair.py::test_public_apply_rejects_combined_reviewed_unique_evidence_over_part_budget
```

Result: **2 passed in 20.68s**. The original 99-change/131,142-byte scenario now observes exactly one full evidence-body SELECT in each public apply, already-applied replay and undo. The 34-unique/250,000-byte scenario refuses before exceeding 8 MiB and before creating either snapshots or a batch. Both regressions inspect real SQL body fetches rather than mocking the budget counter. **Spec: APPROVED.**

Quality stage followed that passing spec check. Inspected reservation-before-fetch, operation-local cache lifetime, exact live text/length equality before cached reuse, expected source SHA validation on a new fetch, unchanged default row locks, and explicit native propagation rather than a process/global cache. The two tests cover reuse and aggregate overflow at the public transaction boundary, including the no-write assertion. No further blocker was found within the original P2 scope. **Quality: APPROVED.** No broader test run or PostgreSQL rerun was added by this reviewer; controller PG evidence remains separately attributed.

The initial finding and initial verification below are retained as review history; their failure observations refer to the original Task 2/Task 3 commits.

## Resolved spec finding — P2: Per-slot binding repeats evidence reads beyond the shared batch body ceiling

Locations: `historical_ranks.py:923–947` resets `used` for every `bind_rank_decision` call; `historical_rank_repair.py:511–533` calls it separately for every changed slot, then runs fresh preparation; fixed Task 2 `catalog.py:1519–1531` and `1689–1728` do the same for native artifact binding and applied replay.

The plan's shared ceiling is 8 MiB of cumulatively fetched evidence/candidate SGFs per batch. The prepare adapter caches a chosen original body across slots, but the apply/replay binding adapter has neither an operation-wide cache nor an aggregate byte budget. A legal frozen part with many slots sharing one original therefore refetches that same body once per slot, resetting the budget each time. Initial qualification adds another evidence-body fetch. This is an actual public-interface execution, not a theoretical oversized malformed manifest.

Independent in-memory SQLite reproduction used the existing repair test helpers, 100 public empty-rank target games, and one original `8p` evidence game with a legal root comment making its SGF 131,142 bytes (below 256 KiB). Preparation emits two bounded parts. Applying the first part through `apply_in_transaction` succeeds with 99 changes while an SQL execution listener observes 100 full evidence-body SELECTs: **13,114,200 fetched evidence bytes**, exceeding **8,388,608**. Target bodies and other reads are additional. No persistent data or product files were changed by the reproduction.

Minimum correction: share a finite body cache and byte budget across all binding/initial-verification calls in one repair/native apply or replay operation; reuse a previously validated exact original body rather than fetching it again per slot. Preserve default row locking, exact SHA/owner/source binding and first-apply qualification. Enforce the aggregate ceiling before fetching additional bodies and fail/refuse honestly if it cannot fit. A focused regression should exercise multiple slots sharing a large original through the public repair helper and at least the native shared binding boundary. Avoid a new cache service or a global corpus cache.

## Spec coverage checked

- New staged decisions freeze v3 before paid name work, prefer the exact legacy checkpoint key, keep old checkpoint bytes, and preserve old fact/receipt contracts. Historical inference is absent from original `rank_facts`/`rank_observations`.
- Portable decisions omit local IDs; native/standalone artifacts retain local `basis_bindings`. First application checks fresh historical qualification under writer/table locks; applied replay validates frozen journals/bindings without resolving newer ranks.
- Standalone preparation counts every album/side, limits writes to public eligible targets, reports refused/unknown targets, emits finite 100-game/200-change parts, omits SGF bodies from exports, binds DB/code/policy/hash, and retains complete beforeimages. The CLI defaults to read-only prepare, commits selected parts independently, stops after failure, and labels uncertain commit outcomes without claiming rollback.
- Snapshot correction uses a new CAS journal and preserves the old journal. Replay/undo fail on current afterimage drift. The real native A → standalone B → undo A refusal → undo B → undo A path is present and passes the independent focused run.
- API list/preview/detail share the same renderer and batch loader; v3 validates target raw/name/date/FK/source/SHA, row hash, applied batch discriminator and exact journal afterimage. The loader selects small artifact authority fields and journal data, with no full-manifest or per-card basis lookup. Invalid overlays fall back to source semantics.
- The compatibility checks allow deterministic embedded-name rank derivation when root rank is empty, preserve a source-only date without historical inference, and keep `bind_rank_decision(lock=True)` as the default.

## Independent verification

Fresh command:

```text
PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_kifu_historical_rank_native.py tests/web_ui/test_kifu_historical_rank_repair.py tests/test_kifu_rank_freeze.py tests/test_kifu_incremental_decision_resume.py tests/web_ui/test_kifu_rank_snapshots_api.py
```

Result: **75 passed, 1 skipped in 10.55s**. The skipped case is the opt-in PostgreSQL repair test. PostgreSQL verification reported by the controller is separate evidence; this reviewer did not independently run PG or read/print a DSN. The cumulative-body reproduction above was run after these tests and is not covered by them.

Only this review document is owned/modified by this reviewer. No product/test/config/data edits, deployment, cron activation, paid call, or filesystem access/listing/traversal under `data/kifu-album/` was performed. Paths inside synthetic SGF/source metadata are strings, not filesystem reads. Production data preparation/application and unfinished Task 4/release work are outside this slice's approval scope.
