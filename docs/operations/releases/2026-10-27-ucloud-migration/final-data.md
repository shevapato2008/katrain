# 最终数据执行结果

13库恢复和独立continuation已实际完成，16份配置复制通过，新运行服务已接管。原严格schema-hash失败记录保留；67个CHECK＋1个partial index的有限语义等价证明和新验证回执见[当前总记录](README.md)。下文保留各阶段操作说明和当时状态，不能把早期“prepared”文字当作当前执行状态。

# Final data handoff completed — runtime activation pending controller

Final data work finished at approximately **2026-10-26 21:05 UTC / 2026-10-27 05:05 Shanghai**. The controller now owns PG/service reconstruction, VPN, health checks and traffic activation. This report does not claim the overall migration is activated or that the old host can be deleted.

- Final offline export: 13 custom database archives, four globals, all four PG configuration sets. All TOCs/majors passed. Source/target immutable versions: main 15.18, lobby 15.19, kifu 16.14, pitch 17.11.
- VPC-only transfer: **2,473,019,285 archive/global bytes**, all payload SHA256/byte checks passed. Manifest SHA256: `3b8d2b9da4ebab869c8a0b5745aa749eda95fa428d09a478f3cef78e983a8a9e`.
- Four original non-PG volumes and four exact bind paths synchronized with owner/ACL/xattr/hardlink preservation and target-only deletion. MinIO included `.minio.sys`. There were 69 itemized changes; two full checksum dry-runs reported **0 / 0**. GPU model bind was unchanged.
- All **13 final pg_restore commands exited 0**. No database restore was repeated.
- The original final verification correctly failed on four schema text hashes. Exact investigation found **67 CHECK expressions and one partial unique-index predicate**, limited to varchar-array-to-text cast placement and AND parenthesization. All literals and ordering were unchanged. PostgreSQL read-only `EXPLAIN … LIMIT 0`, with non-pruned Output and controlled planning settings, proved all 68 equivalent on the same target types/collations. Constraint/index metadata and all other DDL matched exactly.
- A separately approved continuation used a fresh actual TEST flock, current physical fences and distinct verify/sign/copy live probes. Fresh source fingerprints still matched the original final manifest; target differed only in those four proven schema text hashes. Password equivalence passed in memory.
- All four original target PGs were normally stopped by `SIGTERM`, timeout `-1`, at **21:05:27 UTC**, with actual `exited`, Running=false and PID 0. No kill, recreation or volume deletion was performed by this data operator.
- **16 configuration files** were copied only while PGs were stopped. Exact source bytes, UID/GID 70 and original file modes were verified. No business service, VPN, DNS or ingress was started or changed by the data operator.

The original expired fence, original manifest, original failed receipt and archives were preserved. In particular, the original apply receipt remains `failed_final_apply`; the new independent continuation receipt does not overwrite or rename it.

| Evidence | SHA256 |
|---|---|
| Original failed apply receipt | `dfd303bb81b153252c1d48298632bd4dfa80b35a7ca4eed1cf656b245a797aeb` |
| Finite 67-CHECK / one-index backend proof | `38aeaa7ee70560f0c76d2d8ad27285b52fe0c2aa7b6bcf52b58e89f3a14b98eb` |
| Approved continuation verifier | `6cbfa7ab68f67a360f1a5dd5dec32699e7a80c7972bf301d6830fd8b60f90076` |
| New continuation fence | `8d683994238cae351f2a9da4bf2b42a511fc35269f2e8191245cf53bff653a93` |
| Signed continuation verification | `95e202b8b59fcb7deae8d8962356df3e7ec32558e81d8a08ba3e20a1cac624f5` |
| Stopped-PG configuration-copy receipt | `3bb0fe92dc2cdbbb0e9e39973764e5256d9b4dccd3fb913090cca331d75ad7a0` |
| **Final data receipt** | **`836ffa4e4a0c234a1f3647814c975649bfd281b7edf428d9cfebacdfb64c8ebe`** |

Root-private handoff files on new (0600) are under `/var/lib/ucloud-migration-20261027/continuation-migrate-continue-20261027-0420/`: `verification.private.json`, `normal-pg-stop.private.json`, `config-copy.private.json`, and `final-data-receipt.private.json`. Final status is `verified_final_data_under_continuation_pending_controller_runtime_activation`.

The original preparation instructions below are retained as historical procedure. Their earlier “not executed” wording refers to preparation time, not the completed data handoff above.

---

# Final PostgreSQL data operator — prepared, not executed

The operator is on the new host at `/var/lib/ucloud-migration-20261027/final-data/final-data-operator.py` (root:root, 0700). Its working directory, receipts, manifests and logs are root-private (directories 0700, files 0600). No final export, restore, configuration copy, writer fence, controller GO marker or service-state change was performed while preparing it.

## Read-only checks completed

- Python syntax passed. The role/membership and database/object/sequence metadata SQL ran successfully against the actual new PostgreSQL 15 and 17 instances. The bounded native contract query returned batches 931/932 and six protected rank snapshots.
- Current `preflight` returns `prepared_not_executed` and blocks final apply because non-PG/GPU application containers are still running. This is expected before the controller's window; it is not a final-ready marker.
- Source configuration path discovery was read-only. All four instances currently use `/var/lib/postgresql/data/{postgresql.conf,pg_hba.conf,pg_ident.conf}`, with SSL off and no discovered external included configuration files. Kifu 16 also explicitly includes `postgresql.auto.conf`. Final export rediscovers and captures these files after fencing; this preparation did not copy their contents.
- No final window/fence/GO authority file has been created by this operator. The source-fence file remains the controller's responsibility.

## Authority and prerequisites

Every mutating data/configuration action requires all of:

- `--window-id WINDOW`, `--go APPROVED:WINDOW`, and `--fence-sha` equal to the SHA256 of the actual controller-produced fence file.
- Fixed fence pathname `/var/lib/ucloud-migration-20261027/source-fence-WINDOW.private.json`, root-owned, regular, 0600, on the host where the action runs. The copied new-host fence must be byte-identical to the source file.
- Fence Schema 1, Owner `migration-controller`, matching WindowID/hostnames, `OldWritersFenced=true`, the 11 exact SourceContainers, zero receiver/prepared/writable-transaction fields, a control-plan SHA256, and the controller's TestWriterGate fields with an unexpired ExpiresUnix. The operator validates but never creates or refreshes this authority.

The source independently inspects all 11 containers and compares their actual ContainerID, ImageID, exited/Running=false/PID=0 and FinishedAt against the pinned fence. Only the four PostgreSQL and two GPU containers may be running. All four PGs must use the original immutable images/volumes and have zero prepared transactions and zero other client sessions. Receiver active keys at `/home/kifu-receiver/.ssh/authorized_keys` must exist with zero bytes. Receiver-process matching requires an argv token whose basename is exactly `kifu_incremental.py` and a separate `receive` token.

The target independently requires all non-PG/GPU applications stopped, no receiver process/active key, no `10.8.0.3` address, inactive systemd nginx, and no public listeners on 80/443 (or stage 18080/18443; loopback is allowed). It rechecks the source fence over the pinned new→old VPC SSH path before and after apply. Source/target fence actions, TEST authority, production queue pause, normal PG stop/rebuild/start, DNS/VPN and ingress changes belong to the controller.

## Exact usage — run only after controller GO

The following are commands for the controller on the **new host as root**. Substitute the controller's actual values; these assignments do not produce authority files.

```bash
final_op=/var/lib/ucloud-migration-20261027/final-data/final-data-operator.py
final_window=CONTROLLER_WINDOW_ID
final_fence=/var/lib/ucloud-migration-20261027/source-fence-${final_window}.private.json
final_sha=CONTROLLER_PINNED_FENCE_SHA256
```

Safe current-stage read-only preflight, requiring no GO:

```bash
python3 "$final_op" preflight
```

### 1. Export a fresh final source snapshot

Only after the controller has actually fenced old writers, stopped the 11 old business containers and receiver, and written the genuine old fence file:

```bash
ssh -i /var/lib/ucloud-migration-20261027/transfer_key \
  -oIdentitiesOnly=yes -oBatchMode=yes -oStrictHostKeyChecking=yes \
  -oUserKnownHostsFile=/var/lib/ucloud-migration-20261027/transfer_known_hosts \
  ubuntu@10.60.219.118 sudo -n python3 - source-export \
  --window-id "$final_window" --fence-file "$final_fence" \
  --fence-sha "$final_sha" --go "APPROVED:$final_window" < "$final_op"
```

This streams the operator code to old Python; it does not install a source-side operator. It refuses an existing `/var/lib/ucloud-migration-20261027/final-db-WINDOW` directory and never overwrites initial backups. It exports 13 non-template databases and four globals, verifies each TOC/major, records SHA256/bytes, and performs independent source-fence checks before and after. `manifest.json` must finish with `Status=verified_final_export` and `Phase=final_offline_after_writer_fence`.

Configuration export captures only the explicitly discovered config/hba/ident/sourcefiles/auto.conf and necessary SSL file paths, never the entire PGDATA. File contents and metadata stay private. `pg_file_settings` discovery selects distinct source paths, not settings values. A small separate non-secret pg_settings whitelist baseline is saved privately for the controller's restart comparison. Parse errors or pending-restart settings fail closed. External referenced files are explicitly listed; an SSL CRL directory requires controller handling rather than recursive copying.

### 2. Controller transfers and verifies final files

The controller must transfer the fresh directory from old to the same new-host pathname, preserve private ownership/permissions, and independently verify every listed file SHA256 and byte count. The operator does not perform this transfer or invent its successful receipt.

After actual verified transfer, the controller supplies a root-owned 0600 JSON transfer receipt via `--transfer-receipt`. Required fields are:

- `WindowID`: the exact window.
- `Status`: `verified_final_archives`.
- `SourceFenceSHA256`: the exact pinned fence SHA256.
- `ManifestSHA256`: SHA256 of the transferred final manifest.

### 3. Apply in the four existing actual target PG containers

After the controller has stopped all new business applications and receiver while leaving the four actual PG containers running:

```bash
python3 "$final_op" target-apply \
  --window-id "$final_window" --fence-file "$final_fence" \
  --fence-sha "$final_sha" --go "APPROVED:$final_window" \
  --transfer-receipt /ABSOLUTE/CONTROLLER_VERIFIED_TRANSFER_RECEIPT.private.json
```

Before the first database write, all four target role/database inventories are checked for compatibility with the final source. Extra target roles/databases, missing expected source-role CREATE statements, unexpected tablespaces, active target clients or failed source fencing block apply. Only exact CREATE ROLE statements for already-existing **source** roles are filtered; every ALTER/password/grant remains. Globals use `ON_ERROR_STOP` and a single transaction.

Archives stream directly from the sole host-side final copy into the existing actual PG containers. There is no volume creation/deletion, container recreation, archive bind or extra archive copy. Because streaming archives are not seekable, this version uses `pg_restore --jobs=1` (within the requested <=4 limit), with `--exit-on-error --clean --if-exists --create`, connected to template1 and preserving owner/ACL/sequence/extensions.

Verification compares exact selected table counts, schema dumps normalized only for random psql restrict tokens, role attributes/membership/configuration, database/object owners and ACLs, sequence metadata/current values, extensions, both full native artifacts from **kifu_name_batches**, and the six rank snapshots. A fresh source recheck confirms the source fingerprint stayed unchanged. Actual role-password hashes are compared through a fresh nonce-bound proof in process memory; they are not printed or persisted in comparison receipts. No SGF-body scan is performed.

The separate result is `/var/lib/ucloud-migration-20261027/final-data/apply-WINDOW/receipt.private.json`, with `Status=verified_final_logical_data` only after all 13 restore exits and source/target checks pass. It explicitly leaves configuration status pending; it never renames or modifies the initial restore receipt.

### 4. Copy final configs only after normal controller PG stop

The controller must first normally stop all four new PG containers. Other business writers remain stopped and the source remains fenced. Then:

```bash
python3 "$final_op" target-copy-configs \
  --window-id "$final_window" --fence-file "$final_fence" \
  --fence-sha "$final_sha" --go "APPROVED:$final_window"
```

The action refuses running PGs and wrong PG_VERSION, requires verified logical-data receipt, and copies only the explicit config files into the original four named volumes with UID/GID 70 and source file modes. It verifies copied bytes and rejects path escapes. External config references block before copying and remain listed in the private config-copy receipt for explicit controller resolution.

Success produces `/var/lib/ucloud-migration-20261027/final-data/config-copy-WINDOW.private.json` with `Status=copied_configs_while_pg_stopped_pending_controller_restart_validation`. This is **not** final runtime approval. The controller then rebuilds/starts with the old exact immutable images and original private runtime Env/mounts, checks real authentication/health and the saved per-instance `configs[container].paths.settings_whitelist`, and writes its own final runtime validation receipt.

## Failure and resource handling

Any failed command or gate stops that action. There is no automatic rerun/resume, swallowed restore error, global-volume cleanup or rollback claim. A partially restored new target remains for controller diagnosis while the old source stays authoritative and fenced. Existing `apply-WINDOW` or config-copy receipt paths block another attempt until explicit controller review.

Each major command checks >=15 GiB root free space. Export additionally watches its own archive-writing subprocess and aborts it if the margin is lost. The controller should continue its independent disk watchdog throughout the window, particularly during restore/WAL growth. The operator never stops/kills business containers, receiver processes, services or VPN/DNS/ingress.

The currently installed operator and documentation are prepared artifacts, not evidence that any final operation has run.

## Durable controller launch and VPC-only transfer

Additional root-private prepared files on new:

- `final-data/final-stage-runner.py` (0700).
- `final-data/launch-final-stage.sh` (0700).

The launcher verifies the actual root-private fence/window/SHA/GO before creating a durable new-host systemd unit. Source export is additionally installed as a root-private window-specific operator and launched in its own old-host systemd unit, after independent live source-fence verification. These units survive a Mac SSH disconnect. No unit or source-side export script is launched merely by installation/preflight.

After genuine controller GO, from new root:

```bash
final_launch=/var/lib/ucloud-migration-20261027/final-data/launch-final-stage.sh
"$final_launch" watch-capacity "$final_window" "$final_sha" "APPROVED:$final_window"
"$final_launch" source-export "$final_window" "$final_sha" "APPROVED:$final_window"
```

Wait for `source-export-WINDOW.private.json` to report verified final export. Then run the following data stages **sequentially**, waiting for each success:

```bash
"$final_launch" transfer "$final_window" "$final_sha" "APPROVED:$final_window"
"$final_launch" files-delta "$final_window" "$final_sha" "APPROVED:$final_window"
"$final_launch" target-apply "$final_window" "$final_sha" "APPROVED:$final_window"
```

The transfer is new-root rsync directly over the pinned VPC SSH path to `10.60.219.118`, never through the Mac. It preserves private modes and independently rehashes all final manifest payloads, pins the complete manifest SHA before/after transfer, and rechecks the actual source fence. Only then does it create `transfer-WINDOW.private.json` with `Status=verified_final_archives`. An interrupted transfer can resume only against its own matching partial receipt; completed or unknown directories are refused.

After the controller normally stops the four target PG containers:

```bash
"$final_launch" target-copy-configs "$final_window" "$final_sha" "APPROVED:$final_window"
"$final_launch" assemble-receipt "$final_window" "$final_sha" "APPROVED:$final_window"
```

The aggregate is `final-data/final-data-receipt-WINDOW.private.json`, `Status=verified_final_data_pending_controller_runtime_activation`. It requires the 13 restore exits, verified transfer, all eight file mappings with two zero-change checksum dry-runs, and stopped-PG config-copy evidence for the same fence/window. It references and hashes the private change/dry-run logs. It does not authorize runtime activation or replace the controller's restart/health/settings checks.

Inspect durable stages with `systemctl status ucloud-final-STAGE-WINDOW` / `journalctl -u ucloud-final-STAGE-WINDOW`. Source export unit is `ucloud-final-source-export-WINDOW` on old. The capacity watcher records both root free-space values every 10 seconds to `capacity-WINDOW.private.jsonl` for up to 1800 seconds, with a below-15-GiB flag. It never stops services or kills production processes. Overall 30-minute window decisions remain with the controller.

## Final non-PG delta scope

`files-delta` independently requires the same actual old source fence and stopped new business writers. It uses existing target volumes only and derives the original mapping from private inspect, checked against the exact eight-path allowlist:

- Volumes: `katrain-ucloud_katrain-state-production`, `smartbox-admin_admin-audit`, `katrain-ucloud_minio-data`, `smartbox-kifu_kifu_work`.
- Binds: `/home/ubuntu/smartbox-platform/ui/lobby`, `/home/ubuntu/smartbox-platform/ui/shared`, `/home/ubuntu/katrain-transformer/models/kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz`, `/opt/pitch-booking/releases/3010f042179fd8ecef5c1eab0e17457552a9019b/deploy/Caddyfile`.

It runs `rsync -aHAX --numeric-ids --checksum --delete` only into those existing target paths, preserving owners, ACLs, xattrs, hardlinks and all MinIO content including `.minio.sys`. Source files and other target/PG volumes are never deletion destinations. Single-file binds target that exact file, never their parent directories.

After the checksum delta, **two complete checksum dry-runs** must both report zero itemized changes before the final-files receipt becomes verified. Itemized file changes stay in 0600 logs. If the model-file bind changes, the receipt explicitly marks `ControllerGPUModelReloadRequired`; a running GPU may still hold its prior bound inode/model and the controller must reload it before runtime acceptance.

No capacity watcher, final export unit, final transfer, final file delta, restore or configuration copy was started during this preparation.
