# Name helper code review — PASS

Reviewed 2026-10-09: `postowner_name_bind.py`, `assemble_name_approval.py`, `name_inner.py` and `name_run.py`, using the actual saved TEST/PROD post-owner captures and pending artifacts. Review was limited to the name-phase changes and execution boundary, building on the completed native/capture/owner reviews. No SSH, SQL, database connection, deployment, Git operation or approval signature was performed.

**PASS. No remaining Essential or Important helper-code blocker.** This review does not approve name semantics or authorize a future exact bundle application; those remain separate root decisions.

## Reviewed bytes

| File | SHA-256 |
| --- | --- |
| `postowner_name_bind.py` | `b31c9716c305efc85d27d0e2111ad602de7330e2a927a7d830f12498c2a676de` |
| `assemble_name_approval.py` | `d69168d9a0803b8a32fc145e9fb823c3183748a2f19d328b0d73cfde211af8d7` |
| `name_inner.py` | `5eb31e7945bc81cb93f01e357f4f2a94036c7f7732385142a0e7b2233337e804` |
| `name_run.py` | `eb8b9a53c7dd08571b20331a8c25664ad881437ac9a669e3b20247f01a25bb78` |

## Binding and native compatibility

- Independently rebuilt both pending artifacts in memory from the saved post-owner captures. Their canonical hashes match TEST `c367fc4092344ee821f19b982ef35f8d4f28877d506a7b1b56704881778bdc2f` and PROD `289e5413e29f426f6b7668978185e7c51880c6e3e722f6ae4fb06c84e512aa46`.
- Each environment contains **150** existing owners, **174** distinct games, **750** unique owner/language cells and no album links. Candidate research hashes, member/owner set hashes, original SGF references, scope bindings and null target preimages reproduce exactly. Pending state was retained; no approval was synthesized.
- The post-owner capture, pre-owner capture identity, owner manifest, matrix, selection, source packet, inventory/base/selection supplement and current catalog are bound before execution. The helper accepts only the exact approval-only transformation of the reviewed pending artifact, so an approved file cannot silently replace names, research, owner scope or CAS values.
- Independently ran all **750 research records per environment** through the actual patched native raw-title validator; all **1,500** passed. The profile remains `sgf_chinese_mixed`, original language `zh-Hans`, bundle format 2 and inventory format 4. No newer ORM or generalized importer is copied.
- The runner uses the reviewed TEST `82124209…523c4` / PROD `6eb7597b…42b02` administrative image pins, separate stable web image pins and exact `0aab89aa…6b1f` raw-event module pin. The physical hidden-column mapping preserves native `ALBUM_COLUMNS` and performs no DDL.

## Write boundary and idempotency

- Assembly needs an independent root name approval tied to the exact request and pending hashes, with chronology checked against binding time. It changes only candidate review fields and artifact approval/status. Apply additionally pins the complete approved artifact, request, exact bundle and environment image and requires the matching ready dry-run receipt.
- Apply enters the original native write lock before checking exact approved owner images, every physical column and full SGF hash of all 174 albums, global inventory/selection/catalog hashes and the required hidden count of **250**. First apply also requires empty name/evidence preimages. Native bundle validation, null-name CAS, collision checks, journal and rollback remain active on that same connection. The helper adds no SGF, rank, hidden-field, owner or album-FK update.
- **Resolved Important finding:** the original wrapper rejected an already committed name batch before native retry handling and accepted only a first-apply receipt. The final wrapper retains the scope guard inside the lock, checks null targets when no prior batch exists, and calls `verify_names` when an exact prior batch exists. This recovery check binds the stored bundle and research hashes, requires exactly **1,500** creation journal rows limited to name/evidence tables, and compares every current row to its full journal after-image. It also checks all **750** exact candidates and qualified literal names. The helper accepts `applied` with 1,500 changes or `already_applied` with zero changes; verify accepts either receipt. This explicit audit is needed because the native format-2 already-applied branch does not provide the stronger format-4/transliteration after-image checks.
- Dry-run and verify use read-only engines. Verify repeats unchanged owner/album/global guards, checks the exact applied bundle and full ledger after-images, and confirms the 750 qualified names. The wrapper restores the native lock function and disposes its engine in `finally`; existing output files are not overwritten.

Validation was proportional: complete helper diffs against the previous reviewed name helpers, actual artifact reconstruction and hash/count checks, the 1,500 native pure research validations, syntax compilation of all four helpers, and a directed static recheck of the repaired first-apply/retry branches. No full suite or new test infrastructure was introduced.

Actual root name approval, approved bundle dry-runs, execution approval, SQL application and live display/search verification are not asserted by this code review.
