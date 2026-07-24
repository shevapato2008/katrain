# UCloud migration runbook

## Invariants

- Start only when available disk is at least the measured migration peak plus 25 GB. The current estimate is 13.5 GB + 25 GB = 38.5 GB (operationally 39 GB).
- `/etc/katrain/ucloud.env` must be root-owned and mode `0600`. Never print or copy its values into logs.
- No service port binds to a public wildcard address. Application ports bind only to `127.0.0.1` and the UCloud WireGuard address.
- Preview uses `KATRAIN_PREVIEW_MODE=1`, the `katrain-state-preview` volume, and no `katrain-cron` scheduler.
- Production uses `KATRAIN_PREVIEW_MODE=0`, the separate `katrain-state-production` volume, and exactly one scheduler.
- Before the later install/cutover phases, do not transfer production data, create volumes, change WireGuard/firewall/Nginx/DNS, stop services, or prune Docker storage.

## Preflight

Capacity and Compose structure, with no secret file:

```bash
deploy/ucloud/scripts/preflight.sh --structural
```

Runtime after the immutable images and root-only environment exist:

```bash
sudo deploy/ucloud/scripts/preflight.sh --phase runtime --env-file /etc/katrain/ucloud.env
```

Full network gate before starting a profile:

```bash
sudo deploy/ucloud/scripts/preflight.sh --phase full --env-file /etc/katrain/ucloud.env
```

## Profile commands

Preview:

```bash
sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml up -d
```

Production:

```bash
sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d
```

## Stop conditions

Stop without attempting cleanup if any preflight gate fails, an immutable image ID differs between source and target, the Preview profile contains a scheduler, the Production profile contains anything other than one scheduler, a port would bind publicly, or a source/target data checksum differs. Preserve the existing containers and images until rollback is no longer required.

At the Chunk 1 checkpoint, only a disposable `/tmp/katrain-ucloud-preflight-20260724` tree may be created on UCloud. Remove that exact tree after the read-only preflight; do not replace `/home/ubuntu/Repositories/katrain`.
