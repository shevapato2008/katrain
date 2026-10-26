# Seven interval control operator — 2026-10-27

Public executable source: `/private/tmp/ucloud-migration-control-batch-20261027.py` (0644).
SHA-256: `abb0964c9bb43e9eb7edd38b07ec8320f39529a69f0187369fe25b43d0a1cf02`.
A matching copy is on the new host at `/tmp/ucloud-migration-control-batch-20261027.py`.

## Scope and authority

Fixed jobs only: `fetch_list`, `poll_moves`, `poll_pandanet`, `translate`, `fetch_upcoming`, `cleanup`, `tutorial_backup`.
`kifu_ingest` is excluded; its 1800-second guard remains a separate controller responsibility. Loop workers are not paused by these rows. This operator does not start containers, run jobs, enqueue commands, or write business tables.

Fixed role/hostname/container mapping:

| CLI role | Actual host hostname | Explicit container |
| --- | --- | --- |
| `old-prod` | `10-60-219-118` | `katrain-ucloud-katrain-cron-1` |
| `new-stage` | `10-60-162-188` | `katrain-ucloud-katrain-web-1` |
| `new-prod` | `10-60-162-188` | `katrain-ucloud-katrain-web-1` |
| `test` | `ubuntu` | `katrain-cron` |

Run the host wrapper as root (`sudo -n python3 ...`); Docker worker runs as root in the named existing container. Connection discovery inside that container uses existing `CRON_DATABASE_URL`, then `KATRAIN_DATABASE_URL`, then the existing cron config. Credentials do not enter CLI arguments or public output. `--expected-database` is required and must match the actual logical database name. Only the new staged target was contacted for this task; OLD and TEST were not written.

## State and CAS behavior

`prepare` reads DB state and persists the complete seven-row before image and exact planned paused image to the host **before any DB mutation**. The private parent directory must be owned by the invoking user and mode 0700; state and lock files must be owned and 0600. It uses exclusive creation for the first plan, fsync for file and directory, and an exclusive local operation lock. Before each mutation it durably records intent and re-reads the saved plan. A lost commit reply therefore leaves the complete recovery images on the host.

`pause` and `restore` require `--go APPROVED:WINDOW_ID`. Both lock existing seven rows with `FOR UPDATE`, compare the entire current image, and perform all mutations in one transaction. Missing-row inserts use `ON CONFLICT DO NOTHING` and require one inserted row, refusing a concurrent insertion. Existing rows are updated. All paused rows use the exact same preplanned UTC microsecond timestamp, reason, and owner. Restore compares current rows to this window's paused image; original missing rows are deleted and original existing rows have all fields restored, including `changed_at`. Any changed row rejects the whole operation. Status prints only counts, hashes, deadline and comparison booleans.

The default mode is read-only `status`; `prepare` also never writes the DB. `pause` refuses after deadline. There is **no automatic restore** on timeout, exceptions, process exit, or a changed authority. A deliberate expired-window restore additionally requires `--ack-expired`; it still runs the full CAS.

The prepare `plan_sha256` is a stable digest of `{before, paused}`. It is the value used in `ControlStateSHA256`; it is not the mutable state file's byte hash.

## Verified staged round trip

Window: `stage-control-roundtrip-20261027-023943`.
Owner: `migration-control-validator`.
Target database: `katrain_prod_20260725` on new host `10-60-162-188`, through `katrain-ucloud-katrain-web-1`.
Deadline: `2026-10-26T18:54:43.000000Z` (2026-10-27 local Asia/Shanghai).
Private state on new host: `/var/tmp/ucloud-control-stage-20261027-023943/controls.json`.
Confirmed ownership/modes: directory `root 700`, state `root 600`.

Observed real sequence:

1. `prepare`: before present count 0; all seven rows absent.
2. `pause`: committed all seven paused rows.
3. `status`: present count 7, paused count 7, `matches_window_paused=true`.
4. `restore`: committed exact original image.
5. Final read-only `status`: present count 0, paused count 0, `matches_before=true`.

Before/restored SHA-256: `a414c79353025fb66703381a2f69cc1d4dd9db47d8a678baf6df1c4139e715c4`.
Paused SHA-256: `6138151a809cbe6bd492712a3458d86363757a14fc7cc99ab6a9020a8db774a4`.
Plan SHA-256: `4e2822a39b15864814e5828bd5223a27c356b1241d591774e966e2641227df8a`.

Real DB verification covered the initially absent-row insert/delete path. The existing-row update/full timestamp restore path is implemented, but was not exercised by adding artificial source control rows.

Offline third-party change refusal passed (1 test): `/private/tmp/ucloud-migration-control-batch-offline-20261027.py`. It changes one expected job image to another actor's row and verifies the actual shared CAS gate raises `control_changed_by_other_actor`. Python compilation passed. No extra schema, queue, or test platform was created.

## Exact commands used on new staged host

The script was copied using the supplied SSH key and strict host checking. The following commands were executed on the new host under `sudo -n`:

```bash
sudo -n python3 /tmp/ucloud-migration-control-batch-20261027.py prepare \
  --state /var/tmp/ucloud-control-stage-20261027-023943/controls.json \
  --window-id stage-control-roundtrip-20261027-023943 --owner migration-control-validator \
  --expected-hostname 10-60-162-188 --env-role new-stage \
  --container katrain-ucloud-katrain-web-1 --expected-database katrain_prod_20260725 \
  --deadline 2026-10-26T18:54:43Z

sudo -n python3 /tmp/ucloud-migration-control-batch-20261027.py pause \
  --state /var/tmp/ucloud-control-stage-20261027-023943/controls.json \
  --window-id stage-control-roundtrip-20261027-023943 --owner migration-control-validator \
  --expected-hostname 10-60-162-188 --env-role new-stage \
  --container katrain-ucloud-katrain-web-1 --expected-database katrain_prod_20260725 \
  --go APPROVED:stage-control-roundtrip-20261027-023943

sudo -n python3 /tmp/ucloud-migration-control-batch-20261027.py status \
  --state /var/tmp/ucloud-control-stage-20261027-023943/controls.json \
  --window-id stage-control-roundtrip-20261027-023943 --owner migration-control-validator \
  --expected-hostname 10-60-162-188 --env-role new-stage \
  --container katrain-ucloud-katrain-web-1 --expected-database katrain_prod_20260725

sudo -n python3 /tmp/ucloud-migration-control-batch-20261027.py restore \
  --state /var/tmp/ucloud-control-stage-20261027-023943/controls.json \
  --window-id stage-control-roundtrip-20261027-023943 --owner migration-control-validator \
  --expected-hostname 10-60-162-188 --env-role new-stage \
  --container katrain-ucloud-katrain-web-1 --expected-database katrain_prod_20260725 \
  --go APPROVED:stage-control-roundtrip-20261027-023943
```

The original `prepare` must not be rerun over the existing state. A later rehearsal needs a fresh private path, window ID, and future explicit deadline. Final `status` above remains safe to run after deadline.

## Controller execution templates (not executed)

Set `control_window_id`, `control_deadline_utc`, and `control_expected_database` explicitly from the approved maintenance window/config. They are identifiers, not credentials. Copy the reviewed public source to each named host before invoking it.

On OLD, prepare before any pause; preserve that state for final new-PROD restoration:

```bash
sudo -n python3 /tmp/ucloud-migration-control-batch-20261027.py prepare \
  --state /var/lib/ucloud-control-old-20261027/controls.private.json \
  --window-id "$control_window_id" --owner migration-controller \
  --expected-hostname 10-60-219-118 --env-role old-prod \
  --container katrain-ucloud-katrain-cron-1 --expected-database "$control_expected_database" \
  --deadline "$control_deadline_utc"

sudo -n python3 /tmp/ucloud-migration-control-batch-20261027.py pause \
  --state /var/lib/ucloud-control-old-20261027/controls.private.json \
  --window-id "$control_window_id" --owner migration-controller \
  --expected-hostname 10-60-219-118 --env-role old-prod \
  --container katrain-ucloud-katrain-cron-1 --expected-database "$control_expected_database" \
  --go "APPROVED:$control_window_id"
```

On TEST, use the same command forms with a separate private state directory, `--env-role test --expected-hostname ubuntu --container katrain-cron`, and the TEST database's explicit name. Its original control image may be restored only on the same TEST authority. This operator does not itself perform the requested separate ingest guard.

After OLD writers are truly fenced and final logical restoration is verified, copy OLD state bytes privately to the NEW host at `/var/lib/ucloud-control-old-copy-20261027/controls.private.json`, owned root, file 0600, parent 0700. Do not display raw state while transferring. Controller exclusively creates the NEW host marker `/var/lib/ucloud-migration-20261027/cutover-authority.private.json`, owned root and 0600, with exactly matching values:

```json
{
  "Schema": 1,
  "WindowID": "APPROVED_WINDOW_ID",
  "OldHostname": "10-60-219-118",
  "NewHostname": "10-60-162-188",
  "OldWritersFenced": true,
  "FinalDataVerified": true,
  "ControlStateSHA256": "OLD_PREPARE_PLAN_SHA256",
  "OldFenceReceiptSHA256": "64_LOWERCASE_HEX_DIGEST",
  "FinalRestoreReceiptSHA256": "64_LOWERCASE_HEX_DIGEST",
  "OldDatabaseName": "EXACT_OLD_LOGICAL_DATABASE_NAME",
  "NewDatabaseName": "EXACT_NEW_LOGICAL_DATABASE_NAME"
}
```

This task did not create that marker or assert either production condition. It must reflect verified controller receipts. The file records authority; `restore` still refuses unless all seven NEW current rows equal the OLD paused image imported by the final restore.

On NEW after the marker exists:

```bash
sudo -n python3 /tmp/ucloud-migration-control-batch-20261027.py restore \
  --state /var/lib/ucloud-control-old-copy-20261027/controls.private.json \
  --window-id "$control_window_id" --owner migration-controller \
  --expected-hostname 10-60-162-188 --env-role new-prod \
  --container katrain-ucloud-katrain-web-1 --expected-database "$control_expected_database" \
  --allow-restore-target-change --go "APPROVED:$control_window_id"
```

If the original window deadline has elapsed, the controller must add `--ack-expired` intentionally. This never weakens CAS or marker checks. Use `status` against NEW with the copied OLD state and explicit NEW target arguments to verify `matches_before=true`; status reports `matches_origin_authority=false` as expected. Leave OLD paused after successful cutover.
