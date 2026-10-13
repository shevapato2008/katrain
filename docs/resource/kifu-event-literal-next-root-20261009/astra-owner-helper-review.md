# Owner helper review — PASS

Reviewer: `/root/event_owner_helper_review`; date: 2026-10-09. Scope: local static review and finite packet checks only. No database connection, SQL execution, cloud operation, Git operation, or deployment was performed.

**PASS for the current read-only prepare / dry-run / verify helpers. No remaining blocking issue was found.** This review is not `owner-root-approval.json`, a plan signature, or approval to apply a batch. The documented player-batch closure and separate root review/signature remain the existing execution gates.

Reviewed exact helper bytes:

| File | SHA-256 |
| --- | --- |
| `owner_inner.py` | `1501ba76d3f461544495527b1f1cb23004dfdf0b80d929940cc6007ab6599ef7` |
| `owner_run.py` | `2d06f07e0809df18b1cb3beca750d621fe092eb6a979957ffb4ee9dd4db74b56` |
| Existing `scripts/kifu_raw_event_title_owners.py` | `7c152e11172052e0de1c1adadf586b3930fed7946df09aa5eadef15171bd23ca` |

- **Read-only boundary:** the runner exposes only three read modes, pins immutable native image IDs, mounts `/work` read only, and supplies the database URL through stdin. Every helper connection uses PostgreSQL `default_transaction_read_only=on`; explicit read transactions cover direct queries. `prepare_plan` and `inspect_plan` use that same engine. There is no helper apply path. Adding `list_hidden_reason` to the ORM is an in-memory mapping after physical `VARCHAR(64)` inspection; it performs no DDL and leaves `ALBUM_COLUMNS` fixed.
- **Source and ownership:** locally checked both pinned captures against the manifest and matrix: each environment has exactly 122 owners and 938 distinct albums. All 122 saved English parser-part sets pass the existing pure validator. Owner IDs/preimages, pending/unclassified state, empty name/evidence preimages, exact album membership, scope hashes and source/SGF references match. Every accepted reference has the raw title as its first GN and no EV. Both physical extra columns are present and null. The 610 proposed cells match both captures. All 28 exclusions remain outside the manifest: 25 first-GN/empty-EV failures and three normalized-name collisions.
- **Approval binding:** the request canonical SHA is `41c9c85ea1c2c0916f24c07835de30f7de8e8af895165847acc5bc7835c95ec1`; manifest, matrix and both capture file SHA pins recompute correctly. Prepare requires a separate `/root` approval tied to these exact request/manifest/matrix hashes, distinct from producer `/root/event_literal_fresh_binding`. The established plan builder checks the actual review identity fields and chronology. Dry-run revalidates the manifest and plan; apply still requires the separately reviewed exact plan SHA.
- **Preservation:** `scoped_guard` reads every physical album column, hashes each complete SGF, checks event/edition/duplicate/hidden/selection boundaries and rescans verified-name collisions. Dry-run and verify require its exact equality to the prepare guard. Verify checks all 122 owner afterimages, the applied batch's exact plan, a 122-row owner-only journal and the unchanged native inventory hash. The reviewed product apply implementation updates only raw-owner `review_status` / `review_metadata`, plus its registry/batch/journal bookkeeping; it has no ordinary-name, album-FK or SGF write. The complete physical guard covers the 938 scoped albums, while the helper's database read-only setting covers all tables.
- **Resolved finding:** the original stderr URL regex was overescaped. The current runner uses `STDERR_URL = re.compile(r'\w+://\S+')`. A local dummy PostgreSQL URL is fully replaced by `[redacted URL]`; the env-file terminator is an actual newline. Both helper files compile successfully.

`binding-report.json` and `README.md` accurately describe the finite unsigned packet and later separate name-binding phase. Native-image deployment and live prepare/dry-run/verify results were not rechecked in this review; the already-reviewed deployed CLI SHA was the supplied execution prerequisite.

## Apply addendum — PASS

Reviewed the new apply hunks against the original helpers in `owner-reviewed-transport.tar.gz`. Current helpers include the separately gated apply mode below; the preceding section reviewed the archived read-only versions. No remaining code blocker was found.

| Current file | SHA-256 |
| --- | --- |
| `owner_inner.py` | `6230061bfc79ef802fff82f9feee74cb4944fa0cafe034f9b5acdac074018ea2` |
| `owner_run.py` | `f531f2b1932d794f4d99bf8276e112e15ec77c2041272866a2b2b1cd40c83124` |

- Apply requires a separate `/root` execution approval with `allow_apply: true`, actual reviewer fields and per-environment exact plan, manifest and native-image pins. Prepare/dry-run identity, canonical plan hash, captured inventory, successful 122-owner/938-album/zero-name/zero-FK report and matching physical guard are checked before opening the write engine.
- The native hidden-column mapping is inspected in a read-only transaction before importing the existing owner CLI. The new context manager enters the original `_locked_write` first, compares the unchanged complete `scoped_guard` while its table locks are held, then yields that same connection to unchanged `apply_plan`. First apply therefore still requires the original pending owner status, complete before-image and allowed review-field delta inside the lock. A prior batch is accepted only through the existing exact-plan/after-image idempotency checks. No new ordinary-name, FK or SGF write was added.
- The wrapper restores the imported lock function and disposes the engine in `finally`. Its receipt includes environment, phase, batch ID, status/count and plan/manifest/physical-guard hashes; existing receipt files prevent overwrite. A committed run without a saved receipt can use the original `already_applied` result. Credentials still travel through stdin and existing stderr URL redaction; the apply branch adds no credential output. The separate post-apply verify mode remains required for its full unchanged-data checks.

Focused local checks passed: exact hashes, syntax compilation, rejection under optimized Python, unchanged AST for the existing physical guard/capture/approval/ORM functions, and unchanged product CLI SHA `7c152e11172052e0de1c1adadf586b3930fed7946df09aa5eadef15171bd23ca`. No SQL or cloud execution occurred. Actual environment prepare/dry-run artifacts and the execution approval were absent locally, so this addendum reviews the code and does not sign those future execution pins.

Documentation follow-up: `README.md` line 64 still said the runner has no apply mode when reviewed; update that sentence to describe the separate execution-approval gate.
