# Honinbo v3: production preflight and isolated clone rehearsal

**PASS for this finite rehearsal.** The [independently approved v3 bundle](kifu-name-honinbo-374-candidates-v3-final-review-astra-2026-10-03.md) passed fresh production inventory/catalog/preimage checks, then isolated-clone dry-run, apply, exact repeat, strict display eligibility, conditional undo and restoration. The clone is restored; batch **5** remains `undone`. Production `katrain_prod_20260725` and live test `katrain_db` were not written. No deployment, service-code replacement or strict-mode activation occurred.

## Pinned inputs and fresh production state

Protected local directory: `~/.local/share/kifu-name-audit/2026-10-03/honinbo-v3-clone-rehearsal-sol/` (`0700`, artifacts `0600`). The copied final bundle has byte SHA-256 `80628846722928263fbe64971c11e492293fe95243f79e42a289c07ce9bf26a8`, canonical SHA-256 `c142e9a5c81335c1fe82f9118c5add3059ff432b9cef4d2e561f67813b5bb3c8`. The explicit protected registry `.5` remains canonical SHA-256 `d64180400bfdd95fa558e04dada00a7b4e0a31a6b361b2a8845ebd49e43bb88f`; evidence byte SHA-256 remains `a000df1ad82b01a00945c3384ba3c299fc443f2f0fa4fa17d0cd4d784f9c4470`. Repository-default registry `.2` was not used.

One production `REPEATABLE READ READ ONLY` transaction, ending in `ROLLBACK`, captured **all 173,025 albums and 173,034 source associations**, six catalog tables, all name rows, and exact cohort SGF hashes. Start/end: `2026-10-02T18:37:44.957401+00:00` / `18:39:25.796251+00:00`; unchanged snapshot `1604157:1604157:`. Recomputing the importer's complete ordered album/source hash matched the frozen inventory exactly:

- Full inventory SHA-256: `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`.
- Catalog SHA-256: `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`.
- Capture byte SHA-256: `1a354f089782d7e8b42b3adaa56197ce7051a49693e10cd525cd41d67a41bc00`.
- Full-inventory receipt SHA-256: `cc7cd59b16df416468d9cc43b409b725ecd21a5b837edab237c4d337349964b0`.
- Catalog/cohort/preimage analysis SHA-256: `b7975daa036b5352c8fd695b9609acaf729caebad22bd17af114b71573d8ee6d`.

The exact 34 raw groups / 1,617 links, original compared fields and SGF hashes match. All target event IDs are null; the proposed series and 34 raw owners are absent, supporting **385 null name preimages**. Verified-name and canonical/alias collision checks found zero conflicts. Production has no `kifu_album_event_selections` table, so this legacy v2 inventory has no selection supplement. Required production schema migration/preflight remains a separate gate before any current-importer production action.

## Isolation, backup and execution

Target: `home-ubuntu`, **`kifu_name_rehearsal_20261002`**. Read-only preflight found no other connection, batches 1–4 all `undone`, no selection rows, and matching full inventory/catalog hashes. Every phase checks `current_database()` before accessing the target. Only the inventory copy's connection identifier is adapted; its signed inventory hash is unchanged. Credentials remain in process memory.

The first backup streamed over SSH exceeded 180 seconds and was retained as `.incomplete`; no clone write followed that attempt. One explicitly authorized retry saved a host-local `pg_dump -Fc -Z1` of `public.kifu_*` in **5 seconds**. `pg_restore --list` returned zero; the validated **100,232,793-byte** backup remains at `home-ubuntu:/tmp/kifu-honinbo-v3-rehearsal-20261003-ZzYOPG/clone-kifu-before.dump`, SHA-256 `b1b7626c950c6ea4b57a5ff6d7904167a658015a5a40c928654f40e0de369a46`. The host had 294,018,576 KiB available. The backup directory/files use `0700`/`0600`.

To avoid per-row SSH round trips, 318 exact Python files from checkout `e6085b316d4388869791ae4bb24edf66f93f2a4a` and pinned inputs were copied into the web container's separate `/tmp/kifu-honinbo-v3-rehearsal-20261003-ZzYOPG/` directory. The helper verifies every code/input hash and the canonical bundle/registry hashes before each phase; it imports that copied code, rather than service-installed code. `name_batch.py` SHA-256 is `80c5af9dd76c29959a7cea2a8dc990bd6932c7775a8ac81898bb332db89df3e9`; helper SHA-256 is `7936bab4bd2d78c133015a85807fb89d8daaab73700d206fdf94d9ce6b98e9c2`. Phases ran sequentially using the existing importer APIs.

| Phase | Result | Seconds | Receipt byte SHA-256 |
| --- | --- | ---: | --- |
| Clone preflight | Full inventory/catalog match; 1,617 null event IDs | 4.709 | `6db8bfdc53c1b8bba28c9c67744bb5096b2b6677fa697197034cd2a8817d14da` |
| Dry-run | 385 approved; ready/write-ready; 1,617 affected albums; zero errors | 11.477 | `b1513a78f7ac59ca5c893eaf49f8c9d0a06e78f7db6181d13d3aac193664a810` |
| Apply | Batch 5; event 24; 34 raw owners; 2,422 ledger changes | 24.265 | `d8cf596668f6f0230c1c43bdf44c562ef06f80ceb5292a1a3e072592d347da79` |
| Exact repeat | Same batch; already applied; zero changes | 2.339 | `ebc31989f0b2e0f03db33ff1dcae98b07d99ac563ceaef9bf5059f3a6d474d0d` |
| Applied verification | 17,787/17,787 composed event slots; exact display maps; raw fields/SGF unchanged | 7.773 | `dbc6080a814bbbf977680a3b32681d185aa295ea6dc8f6fdf8bdae6f8cb7734b` |
| Conditional undo | Undone; 2,422 reverted; zero skipped/already reverted | 40.360 | `c6ed6ebe47a2236c50c66f87298ae2bc8030b8e351066c31f5887e0f6fa1588b` |
| Restoration | Full inventory/catalog and data counts restored; all 1,617 complete album images match | 5.080 | `c851553612b0cdf7c025125c3803513f6a7ccce7a9a91ade41072b3ef0d01407` |

Applied verification used the shared strict display maps and slot approvals: **1,617 composed event slots in each of eleven locales**. Complete cohort album-image preimage hashes are retained in `clone-before.json`, SHA-256 `934a197ab174a6cb7958011a3bab86d15334da7e818b0475baab2827ee870744`. Restoration checks include every original album column, original SGF, owner/name/evidence counts, full source associations and catalog. Audit receipts remain; no backup restoration was needed.

Protected `rehearsal-manifest.json` SHA-256: `f2e39c62b43aa22954d820dee38b622c8d82b4a3421b69fd1df95d025234bf1f`. It pins inputs, code, helpers, production capture and every receipt. This result covers the finite Honinbo event slice only; both player slots, full eleven-language coverage, production migration and production-release authorization remain outstanding.
