# Owner-only helper code review — PASS

Reviewed 2026-10-09. Scope: `owner_inner.py`, `owner_run.py`, the unsigned owner review/execution request and their actual captured manifest/matrix bindings. Compared the helpers with the previously reviewed 593/594 helpers and inspected the unchanged native owner CLI. No SQL, database connection, cloud action, Git mutation, approval signature or deployment was performed by this review.

**PASS for the bounded owner-only prepare, dry-run, apply and verify code. No remaining Essential or Important code blocker.** This report is not an owner approval or approval of future exact execution plans.

## Reviewed bytes

| File | SHA-256 |
| --- | --- |
| `owner_inner.py` | `55bf5864a117cfe06da9774357e4a17ef617ba2227c8e4cf2ccae1dbefb55068` |
| `owner_run.py` | `9e3226d10ec62d3e28522905147641c3208754f3550ffcf497af102a2169fb5e` |
| Existing `scripts/kifu_raw_event_title_owners.py` | `7c152e11172052e0de1c1adadf586b3930fed7946df09aa5eadef15171bd23ca` |

The native CLI SHA matches both saved r6 build receipts. The importer pins are TEST `82124209ad6425190d587fec10b06eb7cab8b80067cd345cc523bd9a760523c4` and PROD `6eb7597b5b478c082fe91405c0223531a46380bf53b9d7dc33e8e74cfb642b02`; the existing web image pins remain separate. The runner checks the exact importer ID, existing web ID and patched raw-event module hash before running a phase. `/work` is mounted read-only and the DB URL travels through stdin.

## Scope and binding

- Independently recomputed the actual request, manifest, matrix and compressed capture hashes. TEST and PROD each contain **150** unique pending/unclassified raw owners, **174** distinct current albums, zero captured rejections and zero normalized external-name collisions. The **750** proposed name cells are collision inputs for a later phase, not owner-phase writes.
- Owner IDs/preimages, parser-part scope, album IDs, complete scope rows/hashes and SGF references agree across the current capture and manifest. Original references retain the exact first GN and no EV. The current source packet, selection, matrix and capture identities are bound explicitly; archived numeric IDs remain hints.
- The helper rechecks exact live raw-owner identity, owner preimages before prepare/dry-run, empty name/evidence preimages, all 174 full physical album images and SGF hashes, formal event/edition NULLs, duplicates, hidden state, event selections and the 750-name normalized collision boundary. The narrow physical hidden-column mapping leaves native inventory columns fixed and performs no DDL.

## Write boundary and recovery

- Prepare/dry-run/verify use read-only connections. Prepare requires a separate root owner approval bound to the request/manifest/matrix. Apply additionally requires root execution approval with exact environment, image, manifest and plan hashes, matching prepare/dry-run receipts and a ready 150-owner/174-album/zero-name/zero-FK report. The templates and proposed execution manifest remain unsigned.
- Apply enters the original native lock before the complete physical/scope guard, then calls unchanged `apply_plan` on the same locked connection. Native `inspect_plan` checks the complete current owner preimage, fixed owner set, inventory/catalog, parser parts and signed scope; the only owner field delta is `review_status` and `review_metadata`. Registry, batch and change journal bookkeeping remain the original implementation. No name, album, FK or SGF write path was added.
- **Resolved finding:** the first adaptation required the pending owner preimage before native `already_applied` recovery could run. The final wrapper calls `scoped_guard(..., before=False)` inside the original lock, preserving all album/name/selection checks while allowing native first-apply before-image validation or exact applied-plan/after-image recovery to select the correct branch. Prepare/dry-run retain full preimage equality. The wrapper restores the lock function and disposes its engine in `finally`.
- Verify checks every exact owner after-image, the applied batch's exact plan, a 150-row owner-only journal, unchanged scoped physical guard and unchanged native inventory hash. Existing journal/undo behavior is reused unchanged.

Verification was proportional: helper syntax compilation, exact-file/hash and actual packet/count checks, complete diff against the prior reviewed helpers, and final inspection of the repaired lock/recovery call and unchanged native branch. No database or full-suite run was needed for this code review.

`postowner_name_bind.py`, name application, actual root owner approval and exact TEST/PROD prepared-plan approval are outside this code approval. No batch ID, applied owner count or name publication is asserted here.
