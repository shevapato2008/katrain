# Name helper review — PASS

Reviewer: `/root/event_owner_helper_review`; date: 2026-10-09. **PASS for the exact helper versions below and the pinned 610-name packet; no blocking issue found.** Review was limited to static code and finite local artifact checks. No SQL, cloud operation, Git operation, translation research or new test infrastructure was used.

| File | Reviewed SHA-256 |
| --- | --- |
| `name_inner.py` | `d2da8dffb6f043299081096acc8947bb9d14eb3e4da9c46d229e6c86f4b8b0b2` |
| `name_run.py` | `901c6480c5deebb8a2c8612a0cfe0f81f6250bed24ff4c6835dad4795d8c7107` |
| `assemble_name_approval.py` | `d814f6ee801bb7bc9dcf8681972cd679d2d14446a34c1a2ec3f386363b218c4d` |

The inner helper already had the above bytes when this review began; the earlier `9f067dae…` handoff hash is not the reviewed version.

- **Approval and source binding:** the unsigned request recomputes to `a4f25eebdae53307c2b2a147981c57a53e6f244be9f8c00ebde1c4936b55f536`. Its source matrix, owner manifest, both pending artifacts and both actual post-owner capture hashes match local files. Assembly requires a separate `/root` approval, reviewer fields and valid chronology, then changes only candidate review fields and artifact approval/status. It preserves the reviewed names, research and null-name CAS values. Apply additionally pins the complete approved artifact, exact bundle, request and current image for the selected environment, and requires a successful matching dry-run.
- **Exact finite write set:** both pending bundles have 122 existing `raw_event` owners, 610 unique owner/language candidates, 938 distinct albums and zero album links or owner creations. All candidate values equal the already-reviewed source matrix; research hashes, SGF references, scope hashes and null preimage bindings match the actual capture. Both format-4 inventories retain all 173,025 associations and match the captured full/base/selection hashes. This review did not reopen the 13-core translation decisions.
- **Locked preconditions:** the apply wrapper enters the original `_locked_write`, checks every physical column of all 938 albums using the capture's SGF-inclusive hashes, compares all 122 complete approved owner images, and requires no existing name/evidence rows. It also recomputes global inventory and catalog hashes before yielding the same connection to original `apply_bundle`. The original name CAS, owner/snapshot validation and cross-bundle collision checks remain active. The reviewed input causes only 610 raw-event names and 610 evidence rows plus batch/registry bookkeeping; it adds no owner, SGF, rank or album-FK write.
- **Readback and runtime boundary:** verify repeats the complete physical/owner/global guards, requires an applied batch with the exact bundle SHA, checks 1,220 journal rows restricted to the raw-event-name and evidence tables, and checks all 610 names against their exact approved candidate and `eligible_literal_raw_name`. Dry-run/verify engines are read only. Both helpers pin TEST image `61ffcb3f…5df1f1` and PROD image `6ffe9b6d…ab3c5`; deployment correctness was the supplied prerequisite, not rechecked remotely here.
- **Credentials and focused checks:** the runner passes the database URL through stdin, keeps Docker inspection output internal, and redacts ordinary PostgreSQL URLs on stderr. A dummy URL redaction check, all three syntax compilations and optimized-Python rejection checks passed. No credential output was added.

At review time the name root approval, execution approval and approved artifacts were not present locally. This PASS covers the helpers and pending packet; root still supplies and checks the actual approval/signature and performs the documented dry-run, apply and verify steps.
