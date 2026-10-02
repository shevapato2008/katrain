# Honinbo finite v2 bundle: isolated clone rehearsal (2026-10-02 UTC)

The exact [independently reviewed bundle](kifu-name-honinbo-corrected-final-candidates-independent-review-astra-2026-10-02.md) passed validate, database dry-run, apply, idempotent repeat apply, conditional undo, and restoration checks **only** in `home-ubuntu` database `kifu_name_rehearsal_20261002`. Production `katrain_prod_20260725` and live test `katrain_db` were not written. The clone has been restored; batch 4 remains as an `undone` audit receipt.

## Inputs and preflight

Protected execution directory: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-clone-rehearsal-sol/` (`0700`, files `0600`). The reviewed bundle was copied byte-for-byte as `bundle-reviewed.json`, SHA-256 `7650b57fde346dadf8a7b71ae5a36f2d31e7b66f04bbd8f5302cd23d4942b34d`; canonical SHA-256 `91ff30ea2b7326ee21a8573ca3d582dbc7dbf47f2cb6bb03193407fadef939a4`. Registry `.5` copy SHA-256 is `2ebd1c462887632717f0b281ed983db41de7065d9e5f7c4332a4fef8a5624511`. The exact eleven research records (seven corrected plus four original) are in `evidence-exact11.jsonl`, SHA-256 `a000df1ad82b01a00945c3384ba3c299fc443f2f0fa4fa17d0cd4d784f9c4470`; each canonical row hash equals its reviewed candidate's `research_sha256`.

The clone inventory copy changes only `database_identifier` to the local SSH tunnel address used by this run; its file SHA-256 is `718d50eda4a0d878ee4d2735079a2c82b69c720d88e9eff9a466abf65bb0391a`, while its internal inventory SHA-256 remains `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`. The connection helper obtained credentials in process memory from the active web container, replaced the URL's database with the isolated clone, and required `current_database() = kifu_name_rehearsal_20261002`; no secret was saved in an artifact. The SSH tunnel was closed after the rehearsal. The import used the local reviewed importer code, not the different code image in the running web container. Local `name_batch.py` SHA-256 was `ff5ae5085acca4561ed5d42d1d965f115979cd29de69cc148e007e13e79104b1`.

A `REPEATABLE READ READ ONLY` clone transaction at `2026-10-02T15:44:11.959626Z` matched the full inventory and six-table catalog hashes exactly (`catalog_sha256 = 37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`). It found 1,617 exact Honinbo rows, all with null `event_id`, 34 raw groups, no `本因坊戦` canonical/alias collision, 22 events and 108 event names. Clone batches 1–3 were all `undone`; no prior record had this bundle hash. Remote free disk was 281 GB. Preflight receipt SHA-256: `c609b7fd785e92d88051062cd7dd5122869bb14950127dd343515839ca0562c1`.

## Commands and receipts

Offline validation used `python scripts/kifu_name_batch.py validate` with the four protected bundle, registry, inventory, and evidence paths; it returned `approved=11`, `ready=true`, `write_ready=true`, and no errors. The database phases used `python /Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-clone-rehearsal-sol/run_phase.py <phase>` with `dry-run`, `apply`, `apply-again`, then `undo`. The helper pinned the canonical reviewed bundle SHA-256 for importer dry-run/apply and checked the clone database name before each phase; helper SHA-256 is `427cddf11e5e5148de5ef8ec4872fc3eae791b4138f0fb8d56200536285e14f8`.

| Phase | Result | Receipt SHA-256 |
|---|---|---|
| Database dry-run | `ready=true`, `write_ready=true`, exactly 1,617 affected album IDs, `estimated_undo_rows=1640` | `f93a811baff275f61b9c5e59e6514a5724aee78264c1a915a6501c806589ef7b` |
| Apply | batch `4`, `status=applied`, `change_count=1640`, new event ID `23` | `436e7af826f47e9ae1e093a06e432f6e04cdbab1c1a4cb9d0beba3e87df1e169` |
| Repeat apply | same batch `4`, `status=already_applied`, `change_count=0` | `99bd86190a00da9d4d55a16f1a86c7c88f6e220a12c869605299e14e6672869d` |
| Conditional undo | batch `4`, `status=undone`, `reverted=1640`, `already_reverted=0`, `skipped=0` | `f0035babb50d43e92c070a1f67669fd917380afb59d8bd97d5440e2a090b1eaa` |

The dry-run finished at about `15:50:57Z`; apply at `16:01:03Z`, repeat apply at `16:02:14Z`, and undo at `16:07:37Z`. Apply and undo were slow because the local importer made per-row round trips over the SSH tunnel; PostgreSQL reported active transactions without lock waits. No concurrent retry or alternate apply was started.

After apply, read-only checks found exactly one new event `id=23, canonical_name=本因坊戦`, all 1,617 selected albums linked to it, and the exact eleven reviewed language names as `verified` with evidence IDs. There were 1,640 ledger changes. The saved raw-field/SGF-hash preimage for all 1,617 rows has SHA-256 `b4231efb80b43e4adb082cdaacddcaf409435ac8b7b87dcb6e6f39e255051e2c`; every compared raw field and SGF SHA-256 stayed unchanged during apply. Applied verification receipt SHA-256: `73dafb71fb647314b9d05be17a0e9ad11f54d094ae77e36c15722bf39985c3e4`.

After undo, all 1,617 target event IDs were null again; the new event and its names were gone; counts returned to 22 events and 108 event names. All cohort raw fields and SGF hashes matched their preimages. A final read-only full inventory hash and catalog hash returned to the exact preflight values above; 173,034 source links remained. Restoration receipt SHA-256: `5393c807be162c810daa856428ed95dc45dcba95e1d7138b76c70f96f6f3b603`.

This finite bundle proves only a reversible isolated import for **one series identity and its eleven base names**. It does **not** provide the 34 exact raw-event values × eleven approved edition displays, or player-name coverage, needed for strict display across these games. It does not authorize a production apply. No repository code, production database, live test database, or SGF was changed.
