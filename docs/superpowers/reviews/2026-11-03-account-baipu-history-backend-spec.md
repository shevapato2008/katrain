# Account baipu history — H1/H2 independent spec review

**Verdict: SPEC COMPLIANT — S1 and S2 are closed after focused re-review.**

Reviewed the actual H1/H2 working tree on `feature/baipu-physical-history-20261103` against baseline `9e83f1ad5`, the approved account-history plan, and its approved ASTRA/MAX round-2 review. This is a backend specification review, not the final independent code-quality review or frontend/physical-replay acceptance.

## Closed findings from the initial review

### S1 — Board-mode 409 current snapshots can claim authoritative `this_node`

**Owner: H2, with the router boundary adjusted only if needed.**

- `katrain/web/core/baipu_history_sync.py:185` calls the repository save without decorating a raised conflict's `current` snapshot. The stale resolve checks at lines 197–203 likewise raise conflicts with an undecorated repository row.
- `katrain/web/api/v1/endpoints/baipu_history.py:121` serializes that row through `public_record(current)` with its default authority.
- `katrain/web/api/v1/endpoints/baipu_history.py:67` defaults a clean `synced` row without an authority field to `this_node`.

Thus a stale save against a clean board cache can return `409` with `current.authority == 'this_node'`, although successful board reads identify that same durable row as `local_cache`. The frozen response contract requires honest authority, including any current snapshot attached to a cursor conflict.

Carry the service's board authority into error snapshots. Retain authoritative server-mode `this_node` and the bounded browser shape. A focused regression should assert the board stale-CAS response's authority and absence of owner/writer bookkeeping; cover a pre-fetch stale resolve snapshot through the same boundary if it uses a separate path.

**Closed:** `web/core/baipu_history_sync.py:127` now decorates conflict snapshots through `_conflict`. Save and all relevant resolve conflict paths use it, including the repository CAS after the awaited cloud fetch. The new parameterized `test_stale_api_conflicts_keep_truthful_authority_and_bounded_current` exercises save/resolve in board/server mode through the real router `invoke` boundary; the existing concurrent-resolution regression also asserts `local_cache`. Actual code and assertions confirm honest authority with the bounded public shape preserved.

### S2 — `keep_local` clears conflict evidence before its pending write settles

**Owner: H1.**

- `katrain/web/core/baipu_history.py:462` constructs every resolution with `conflict_remote=None` (line 470).
- `katrain/web/core/baipu_history.py:480` then leaves `keep_local` in `pending`, based on the freshly fetched cloud revision. Its new writer has not yet received cloud acceptance.
- `katrain/web/core/baipu_history.py:357` already has the precise current-writer/current-sequence acknowledgement guard, but the settling update at line 364 does not clear conflict evidence there.

The approved resolution contract retains the other snapshot until resolution completes. Clearing it before the explicit `keep_local` write is accepted loses the cloud cursor/evidence while that resolution may still be offline or conflict again.

Retain the validated remote conflict evidence in the existing JSON field while the explicit resolution write is pending. Clear it when the guarded current-writer/current-sequence acknowledgement settles that branch. `use_cloud` may clear it on successful local adoption. Assert evidence survives a late old-writer receipt and an intermediate receipt for an older local sequence, then disappears on the matching acknowledgement. No new audit table or infrastructure is needed.

**Closed:** `web/core/baipu_history.py:462` no longer clears evidence in the common resolution values; only `use_cloud` clears it immediately at line 477. The `keep_local` branch preserves the existing conflict evidence while pending. The precise acknowledgement guard at lines 357–364 clears it together with the transition to `synced`. New `test_keep_local_retains_conflict_evidence_until_current_sequence_receipt` verifies preservation after resolution, a rotated old-writer receipt and an older-sequence intermediate receipt, then verifies clearing on the exact current acknowledgement while retaining the correct cursor and dirty base.

## Contracts verified in the implementation

| Area | Evidence and assessment |
| --- | --- |
| Exact immutable replay identity | `core/baipu_identity.py:5` and `web/core/baipu_history.py:88` derive schema-2 identity/hash/total from exact UTF-8 SGF; owner and presentation labels do not enter identity. Only supported, usable 19×19 replays are accepted. |
| Dedicated durable storage | `web/core/models_db.py:106` supplies the composite owner key, unique replay identity, bounded checks, revisions, durable writer, and row outbox. `web/core/migrations.py:71` protects it from startup rebuild; `api/v1/endpoints/auth.py:270` includes it in the guest-pristine guard. No `user_games` or generic queue storage was repurposed. |
| Auth and public shapes | `api/v1/endpoints/baipu_history.py:94` uses non-guest authenticated ownership and the canonical expected-identity precondition. All six planned routes exist with forbidden extra request fields. Owner/bookkeeping fields are excluded from browser summaries, details, and conflict snapshots; sync transport is separate. List responses omit SGF bodies and enforce a bounded limit. |
| Persistence and local CAS | `web/core/baipu_history.py:180` preserves existing progress on open. Save at line 214 enforces cursor bounds, last-mutation retry semantics and expected local revision; completion, undo, and restart remain durable. Authoritative saves advance both revisions and rotate the writer; board writes retain their durable writer and original dirty base. |
| Atomic cloud acceptance | `web/core/baipu_history.py:141` combines row locking with conditional updates; acceptance at line 263 implements causal sequence handling, exact retry checks, competing-writer revision checks, and protected insertion. Source/name differences do not produce immutable-content conflicts; existing cloud labels win. |
| Safe reads and resolution CAS | `web/core/baipu_history_sync.py:127` discovers cloud progress before creating local zero. Clean adoption at `web/core/baipu_history.py:402` is conditional, monotonic, race-safe, preserves the device writer and returns the actual winner. Dirty rows are not rebased. Resolve at lines 447–484 rechecks expected local revision, pre-fetch writer and conflict/refused state, increments local revision and rotates the writer. |
| Strict bound-owner transport | `web/core/remote_client.py:100` rejects absent or mismatching binding. The history helper checks ownership/session generation before HTTP, after HTTP, across refresh/retry and before exposing a response. Old responses after an account switch, including a switch away and back, are discarded. |
| Row outbox and worker integration | `web/core/baipu_history_sync.py:219` captures copied payloads, filters the active owner before the batch limit, preserves pending on transient failures, and stops automatic sends on validated conflict/refusal. Receipts preserve newer local cursors, dirty bases and conflicts, and ignore rotated writers. `web/core/sync_worker.py:88` invokes the focused callback under its existing lock; generic queue policy is unchanged. Both lifespans use injected factories and preserve an injected history service. |

## Independent verification

Ran:

```text
CI=true BAIPU_TEST_POSTGRES_URL=<disposable local PostgreSQL DSN> .venv/bin/python -m pytest tests/web_ui/test_baipu_history.py tests/web_ui/test_baipu_history_api.py tests/web_ui/test_baipu_history_sync.py tests/web_ui/test_box_sso.py -k 'baipu or history' -q
```

**Result: 60 passed, 49 deselected, no skips, in 12.97 seconds.** This includes the PostgreSQL atomic concurrent-writer check against only `127.0.0.1:15439/baipu_history_test`, isolated SQLite repository/API/transport tests, and the focused guest-owned-row guard. The tests meaningfully exercise delayed GET adoption, in-flight newer progress, retry after lost receipt/reopen, owner changes during request/refresh/response, undo, competing writers, conflict resolution CAS, writer rotation, differing labels and owner batch starvation. Existing `datetime.utcnow()` deprecation warnings remain.

At the initial review, these tests did not assert S1 or the pending evidence lifecycle in S2. After inspecting only the two fixes and their regressions, independently ran:

```text
CI=true .venv/bin/python -m pytest tests/web_ui/test_baipu_history.py::test_keep_local_retains_conflict_evidence_until_current_sequence_receipt tests/web_ui/test_baipu_history_sync.py::test_stale_api_conflicts_keep_truthful_authority_and_bounded_current tests/web_ui/test_baipu_history_sync.py::test_resolve_fetch_cas_does_not_discard_a_concurrent_local_step -q
```

**Focused re-review result: 6 passed in 1.67 seconds.** Both findings are closed; no unrelated review expansion was performed. The unrelated pre-existing pristine-guest bootstrap/credits mismatch is outside this review and remains separately identified.

## Integration boundary

The shared identity foundation is version 2, while `core/baipu.py` still has the earlier strict physical interpreter at this review point. That is the acknowledged dependency on the separate approved physical-replay work, not a claim that full physical replay has shipped and not an additional H1/H2 finding. Frontend H3, whole-journey runtime acceptance and final ASTRA/MAX code review remain separate.

Only this report was written by the reviewer. No product edits, production database operations, device actions, commits or sub-agents were performed. Root approved the narrow S1/S2 fixes; the implementation owners completed them, and this focused re-review confirms closure. Final independent code-quality review and integrated feature acceptance remain separate.
