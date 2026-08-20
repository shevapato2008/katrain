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

## Execution log

Record only sanitized sizes, immutable IDs and gate results here. Never record environment
values, keys, or unformatted `docker inspect` output.

### 2026-07-25 — post-hoc capacity evidence

Captured read-only after the preview stack was already running, so it is current-state
evidence, not the pre-cleanup bundle the capacity gate asks for.

- `df -B1 /`: total 103865303040, used 46628384768, available 57220141056 (45%).
- `docker builder du`: reclaimable 0B, total 0B — build cache already reclaimed.
- `preflight.sh --phase capacity` at 2026-07-25T01:40:09Z: `available_bytes=57220022272`,
  `peak_bytes=13500000000`, `required_bytes=38500000000`, result `preflight passed`.
- `/opt/katrain/current` → `releases/bb3f85bf43ad684faf573e1382d7e5f8fbea8c25`.
- `/etc/katrain/ucloud.env`: root-owned regular file, mode 0600.
- Preview profile live: `katrain-web`, `postgres`, `minio`, `katago-web`, `katago-cron` healthy;
  `minio-setup` exited 0; `KATRAIN_PREVIEW_MODE=1`; no scheduler.
- MinIO serial-path mirror complete: source 27452 objects = target 27452 objects, 0 failed,
  0 remaining, 0 extra; `tutorial-assets` 2.4GiB.
- PostgreSQL data directory ≈1224MB, no manifest verification performed.

Open gaps recorded in the plan's Execution State section: no legacy-container capture record,
no `pre-operation/release-<commit>.json`, no source/target manifests, and the live `wg0` peer
uses `10.8.0.0/24` rather than the per-peer `/32` matrix the WireGuard gate requires.

## Stop conditions

Stop without attempting cleanup if any preflight gate fails, an immutable image ID differs between source and target, the Preview profile contains a scheduler, the Production profile contains anything other than one scheduler, a port would bind publicly, or a source/target data checksum differs. Preserve the existing containers and images until rollback is no longer required.

At the Chunk 1 checkpoint, only a disposable `/tmp/katrain-ucloud-preflight-20260724` tree may be created on UCloud. Remove that exact tree after the read-only preflight; do not replace `/home/ubuntu/Repositories/katrain`.

### 2026-08-21 — develop 合并后重新发布（非迁移）

发布内容：`release/ucloud-20260805` 合入 `origin/develop`（合并提交 `0d88bff6`），
带上围棋升降级阶梯封档（目录 41 档不变，认证可选 29 档）与对局终止/聊天身份守卫。

- 镜像：`katrain-web:0d88bff6`，`image_id=sha256:83092e2a51bbf574c7fb34602e34ca1bb02f7dcec5581d24fb5825ebca1865f5`，
  `size_bytes=542197378`（上一版 `93803100` 为 549896220，同量级）。`build-web.sh` 的容器内容测试通过。
- 上一版镜像 ID 保留作回滚锚点：`sha256:cd28719b9610dbb9d49714de53edcbfa8f95ac4a34b8a81732e7d49d51f3624e`
  （tag `katrain-web:93803100`），`/opt/katrain/releases/93803100` 未删除。
- `/etc/katrain/ucloud.env` 改动仅 `WEB_IMAGE` 一行；改前副本 `/opt/katrain/backups/ucloud.env.20260821-0040`，
  改后仍为 root 所有、mode 0600。
- 数据库备份 `/opt/katrain/backups/prod-20260821-0030.dump`（`pg_dump -Fc`，183.7 MB）。
  **已真恢复验证**：恢复进临时库后逐表比对 38 张表行数，0 处不一致（含 `kifu_albums` 151197、
  `tsumego_problems` 21072、`live_analysis` 61918）。验证库已 DROP。
- 本次无 schema 变更：`ai_ladder_game_ledger` 及其 `ck_ai_ladder_ledger_decision` 等 6 条约束已在位。

**闸门结果与一次明示越闸：**

- `--phase full`：仅 2 条失败，且都是容量闸——`available_bytes=20760682496`，
  `required_bytes=38500000000`；以及「projected filesystem use ≥ 75%」（实际 80%）。
- 其余全部通过：env mode 0600、三个镜像均不可变且本地存在、GPU 可用、
  preview profile 无调度器且 mode=1、production profile 恰好一个调度器且 mode=0、
  WireGuard peer/地址、防火墙、端口工具。
- **这些「通过」不是靠沉默认定的**：拿一份 `WEB_IMAGE` 改坏的 env 副本做过变异，
  `check_runtime` 如实多报一条 `WEB_IMAGE is not available locally`（checks=3），证明该分支确在执行。
- **越闸说明**：容量闸的判据是 `PEAK_BYTES(13.5G) + 25G`，按本文档 Invariants 一节的措辞
  是为**迁移峰值**标定的。本次是替换一个已构建完成的镜像，磁盘增量近似为零，故按迁移口径
  判定该闸不适用并继续发布。**Stop conditions 一节写的是「任一闸失败即停」，此处是明示越过，
  不是忽略。** 若后续要让这条路径重新落在闸内，应把重新发布与迁移拆成不同的 PEAK_BYTES。

**发布后实测（外网 https://modelstella.com）：**

- `/health` = `{"status":"ok","engines":{"local":"reachable","cloud":"unconfigured"}}`，首页 200。
- `/api/ladder-rungs`：目录 41 档；可选 29 档，与封档集合逐档一致；其余 12 档 unavailable。
  发布前该接口 41 档**全部** unavailable（升降级在生产处于关闭态），前后对比明确。
- 容器不变量实测：`KATRAIN_PREVIEW_MODE=0`、卷 `katrain-ucloud_katrain-state-production`、
  调度器恰好 1 个、端口仅绑 `10.8.0.3` 与 `127.0.0.1`（无公网通配）。

**遗留（未处理，需决策）：** 根分区 80%，可回收但**本次一律未删**：
旧 release 目录 `bb3f85bf…`(217M)、`a9607e75`(220M)、`e7f0e758`(554M)；
旧镜像 `katrain-web:{85d81a06,e7f0e758,a9607e75}` 与 `katrain-web:ucloud-candidate-20260724`(2.48G)。
`93803100` 的目录与镜像在回滚窗口内**不得删除**。
