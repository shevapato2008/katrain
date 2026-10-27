# Kifu search: one-release web-only operator

`web-only.py` completed the first TEST release at `dc17489e2`; PROD is still on its
prior release while the TEST latency gate is unresolved. Run further updates only
after full Astra review and the required feature push → develop merge/push →
`smartbox-software` parent-main submodule-pointer push. Release TEST first, complete
its actual Galaxy/kiosk acceptance, then release the new PROD. Image construction,
index/data preparation, and application/page acceptance are separate controller work.

| Target | Host / Docker daemon | Web | Existing image user |
| --- | --- | --- | --- |
| TEST | `home-ubuntu`, hostname `ubuntu` | `katrain-web` | `root` |
| new PROD | `ubuntu@117.50.177.254`, hostname `10-60-162-188` | `katrain-ucloud-katrain-web-1` | `10001:10001` |

Do not connect to the old 183 host. Do not invoke the migration `runtime_replay.py`
for this update: it is an earlier migration operator, not this live web release.

The script runs on the target with access to its local `/var/run/docker.sock`
(TEST's Docker-capable user; `sudo -n python3` on PROD). It refuses remote Docker
contexts and checks both local hostname and daemon name. It does not SSH, build,
pull, run SQL/DDL, restart dependencies, delete containers, or retry mutations.

## Preflight and apply

Supply a **full immutable local image ID**, its full 40-character published release
SHA, and freshly inspected full old container ID/image ID. Candidate image OCI
`org.opencontainers.image.revision` must equal the release SHA; its image user and
platform must match the live image. TEST and PROD require their respective users.
The candidate must not introduce extra default env keys, ports, volumes,
healthchecks, or unreviewed labels through Docker image-default merging.

On the selected host, with the reviewed script already copied there:

```sh
python3 web-only.py --target test \
  --image sha256:<64-hex-candidate> --sha <40-hex-release> \
  --expected-id <64-hex-live-web-id> --expected-image sha256:<64-hex-live-image> \
  --output /var/tmp/kifu-search-test-preflight-<unique>
```

Default preflight reads runtime state and writes **only a new private evidence
directory**, never formal runtime configuration. Each invocation needs a new output
directory. Review the metadata receipt. To apply, invoke the same arguments with
`--apply` and a new output directory; this repeats the entire fresh preflight and
performs identity/config CAS immediately before replacement. On PROD use
`sudo -n python3` and `--target prod`. Keep the successful TEST apply directory: its
private override remains part of the running Compose ownership chain.

An error stops the operator. Inspect evidence and actual state before any further
action; do not rerun an interrupted apply blindly. Docker has no transactional
compare-and-swap API: the helper locks concurrent copies of itself, rechecks the
named web's exact identity/config immediately before mutation, and addresses PROD
mutations by its inspected full ID. Do not run another deployment concurrently.

## Preservation boundaries

TEST reads the live web's exact Compose `config_files` labels (eleven before the
first release, twelve before its measured proof follow-up), checks its
current `config --hash` against the running container's hash, and checks effective
env against live env. It adds one mode0600 JSON override containing only web image
and `KATRAIN_BUILD_SHA`. Full effective config before/after must differ only at those
two fields. Apply uses only:

```text
docker compose <same live files + private override> up -d --no-deps --no-build --pull never --force-recreate katrain-web
```

It does not revive any stopped Compose cron. The running `katrain-cron` collector
and every other running/stopped non-web container must retain the exact same full
ID, image, `StartedAt`, restart count, running flag and status. Compose replaces the
TEST web; it does not preserve that old web container as a backup.

PROD requires the exact seventeen running services observed for this release. It
reads the frozen mode0600 manifest at
`/var/lib/ucloud-migration-20261027/input/runtime-replay/runtime-manifest.private.json`
and checks its **file-byte SHA256**:

```text
0d8c789f371da95c619d1e72dd956f7431a3a13145cb51d03168a3eb04e0e2b6
```

That manifest is provenance only and is never modified. The new create payload
comes from fresh live inspect, preserving the full `HostConfig` (permissions,
mounts, ports, networks, resources/GPU, restart policy), ordered env, command,
entrypoint, user, healthcheck, and stable network aliases. Controlled differences
are immutable image ID, the existing `KATRAIN_BUILD_SHA` value, OCI/current-release
labels, and omission of an automatically generated old container hostname. Old
migration/overlay labels remain historical provenance; the new
`io.katrain.kifu-search.release` label identifies this release.

PROD stops the old web normally (exit 0, no OOM), renames it to the backup name in
the receipt, creates and starts the new web, and leaves the stopped old container
intact. No container is removed. Stop/rename must succeed before create/start.
The backup keeps the original image/config/mounts and has restart `unless-stopped`
or `no`. All sixteen non-web containers must retain exact ID/start/restart/state.

After replacement the script verifies config/ordered PROD env, full HostConfig,
mounts and aliases and waits at most 120 seconds for a declared healthcheck. TEST
has no container healthcheck, so it still needs controller HTTP/page acceptance.
The final receipt means runtime-preservation checks passed, not full user acceptance.

## Recovery and evidence

All raw inspect/config/env, Compose command stdout/stderr and create payloads are
written exclusively to a new mode0700 directory as mode0600 files. Stdout contains
metadata receipts only; error bodies, env values and command contents are suppressed.
Keep private artifacts off Git. Receipts record the frozen manifest hash without
overwriting it. No application log or response body is printed by this operator.

If PROD replacement fails, inspect the actual web and receipt backup IDs first.
Recovery is a separate deliberate operation: stop any new web, retain it under a
distinct failed name, rename the original stopped backup to the original web name,
and start that original full ID. Verify its HTTP health and all sixteen non-web
ID/start/restart values. The helper does not guess or automatically roll back.

Preparation validation: `py_compile` passed; in-memory comparison against the
2026-10-27 actual PROD inspect confirmed only the stated payload changes, exact
HostConfig/endpoints, rejection of added env drift, and non-web backup exclusion.
Read-only host checks confirmed the eleven TEST Compose paths/hash/environment,
different TEST/PROD users, seventeen PROD services and frozen manifest file hash.
No remote runtime mutation or DDL was performed during preparation.
