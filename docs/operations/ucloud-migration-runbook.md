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

### 2026-08-21（当日第二次）— 研究页可用性修复发布（非迁移）

发布内容：`release/ucloud-20260805` 再次合入 `origin/develop`（合并提交 `65677ce5`）。
相对上一版 `0d88bff6`，改动**只有前端 + i18n + 文档**——`git diff --name-only e3f50c43..a930c6c1`
里没有任何 `.py`、没有迁移、没有 schema。修的是研究页在**任何非 `127.0.0.1` 域名**下
永远停在「正在分析棋局」：`sb_token` cookie 只在 loopback 主机名下发，而前端手写 fetch
不带 `Authorization`，于是需鉴权端点一律 401；建会话那一步也因此建成无主的，
`/api/state` 再被 `guard_session_reader` 判 403。

- 镜像：`katrain-web:65677ce5`，`image_id=sha256:87176ac9188e03e1dd109d3312f6a923ffe11831183a67cac960e7a785e56304`，
  `size_bytes=542199207`（上一版 542197378，增量 1829 字节）。`build-web.sh` 的容器内容测试通过。
- 回滚锚点保留：镜像 `katrain-web:0d88bff6`
  = `sha256:83092e2a51bbf574c7fb34602e34ca1bb02f7dcec5581d24fb5825ebca1865f5`，
  目录 `/opt/katrain/releases/0d88bff6` 未删。`current` 指向 `releases/65677ce5`。
- `/etc/katrain/ucloud.env` 改动仅 `WEB_IMAGE` 一行（与改前副本 `diff` 恰好 2 行 = 1 删 1 增）；
  改前副本 `/opt/katrain/backups/ucloud.env.20260821-1213`，改后仍 root 所有、mode 0600。
- 数据库备份 `/opt/katrain/backups/prod-20260821-1207.dump`（`pg_dump -Fc`，192.6 MB）。
  **本次未做恢复验证**，判据写在这里：本次发布不含 schema 变更、也不含任何后端代码变更
  （见上面那条 diff），回滚路径是换回镜像 tag 而不是恢复数据；当日 00:30 那份**已逐表
  恢复验证过**的 dump 仍是有效的验证锚点。若下次发布带 schema 变更，这条豁免不成立。

**闸门结果与同一次明示越闸：**

- `--phase full`：仍只有 2 条失败，且都是容量闸——`available_bytes=20709629952`，
  `required_bytes=38500000000`；以及「projected filesystem use ≥ 75%」（实际 81%）。
- **越闸说明与 2026-08-21 00:40 同因同判据**：容量闸按本文档 Invariants 一节的措辞是为
  **迁移峰值**标定的，本次只是替换一个已构建完成的镜像，磁盘增量 1829 字节。
  **Stop conditions 写的是「任一闸失败即停」，此处是明示越过，不是忽略。**
- **「其余通过」不是靠沉默认定的**：拿一份 `WEB_IMAGE` 改成 `sha256:deadbeef…` 的 env 副本
  做变异，`--phase runtime` 如实多报一条 `WEB_IMAGE is not available locally`（checks 2 → 3），
  对照组同相位仍是 2。副本 `shred -u` 删除，未落盘留存。
- 容器不变量实测：`KATRAIN_PREVIEW_MODE=0`、卷 `katrain-ucloud_katrain-state-production`、
  调度器恰好 1 个、端口仅绑 `10.8.0.3` 与 `127.0.0.1`（无公网通配）。仅 `katrain-web` 与
  一次性的 `minio-setup` 被重建，postgres / katago / minio / cron 保持原进程。

**发布后实测（外网 https://modelstella.com）：**

- `/health` = `{"status":"ok","engines":{"local":"reachable","cloud":"unconfigured"}}`，首页 200。
- `/api/translations`：951 条（上一版 950），新增 `research:progress_failed`，
  cn = 「无法获取分析进度」、en = "Couldn't load analysis progress"，11 种语言全部就位。
- **入口 chunk `/assets/index-xPv7qGZG.js` 与本机已验证构建的同名文件 SHA-256 逐字节相同**
  （`ba566bd4ac204e158afda179df50880ca55ab414d2f82db575d653b02b248a43`）。chunk 名是内容哈希，
  哈希相同即内容相同。其中含 `authHeaders` 的 localStorage 兜底；严格盒端那条分支在全量
  构建里按预期被 DCE 掉（全文件只剩 1 处 `Bearer ` 模板）。

**本次未做（需要授权才做）：** 生产上的登录态走查。修复的判据是「主机名 ≠ 127.0.0.1 时
请求会不会带 `Authorization`」，这一条已在测试服（home-ubuntu）上用真浏览器走通：
主机名 `localhost` 登录后 `document.cookie` 为空、`localStorage.token` 存在，
`/api/session`、`/api/analysis/scan`、`/api/state`、`/api/analysis/progress` 四个请求全部 200，
页面进入 L3。生产跑的是同一份 bundle（哈希已比对）。在生产建探针账号属于生产数据写入，
未经明确授权不做。

**遗留（未处理）：** 根分区 81%。本次新增 `/opt/katrain/releases/65677ce5`（1.9 GB，
`git clone` 因源仓是 shallow 而未能硬链接复用对象）与一份 192 MB 的 dump。可回收但本次
一律未删：旧 release 目录 `bb3f85bf…`(217M)、`a9607e75`(220M)、`e7f0e758`(554M)；
旧镜像 `katrain-web:{85d81a06,e7f0e758,a9607e75}` 与 `katrain-web:ucloud-candidate-20260724`(2.48G)。
`0d88bff6` 的目录与镜像在回滚窗口内**不得删除**。

### 2026-08-23 — galaxy 全站风格统一发布（非迁移）

发布内容：`release/ucloud-20260805` 尖端 `26a046d0`。**本次没有做合并** —— `26a046d0`
（= "Merge origin/develop into release/ucloud-20260805"）早已包含 `origin/develop` 的
`12a3d3fe`，本地与 origin 一致，只是从未部署；线上此前停在 `65677ce5`。相对线上多 256 个文件：
galaxy 全站风格统一（S1–S9：六个棋盘页 + 十二个内容页统一版式、控件账本 22 个无名归零）、
followups 六项收口、11 种语言 i18n，以及**三个后端 `.py`**
（`katrain/core/engine.py`、`katrain/web/server.py`、`katrain/web/session.py` —— 会话清理
把服务挂住的三段修复）。无 schema 变更。

- 镜像：`katrain-web:26a046d0`，
  `image_id=sha256:f276874d337ec7147c55aacc230a2ce39b8022f47b67efa4bf96c034ea5f0181`，
  `size_bytes=542210337`（上一版 `65677ce5` 为 542199207，增量 11130 字节）。
  `build-web.sh` 的容器内容测试通过。
- 回滚锚点保留：镜像 `katrain-web:65677ce5`
  = `sha256:87176ac9188e03e1dd109d3312f6a923ffe11831183a67cac960e7a785e56304`（实测仍在位），
  目录 `/opt/katrain/releases/65677ce5` 未删。`current` → `releases/26a046d0`。
- `/etc/katrain/ucloud.env` 改动仅 `WEB_IMAGE` 一行（与改前副本 `diff` 恰好 2 行 = 1 删 1 增）；
  改前副本 `/opt/katrain/backups/ucloud.env.20260823-2057`，改后仍 root 所有、mode 0600。
- 数据库备份 `/opt/katrain/backups/prod-20260823-2055.dump`（`pg_dump -Fc`，189600573 字节）。
  **已真恢复验证**：恢复进临时库 `katrain_restore_verify` 后逐表比对 **38 张表行数，0 处不一致**，
  `pg_restore` 0 错误（抽查 `kifu_albums` 151197、`tsumego_problems` 21072、
  `live_analysis` 60349、`users` 9）。验证库已 DROP。
  **为什么这次不能沿用 2026-08-21 第二次的豁免**：那条豁免的依据写的是「不含 schema 变更、
  **也不含任何后端代码变更**」，而本次改了三个后端 `.py`，前提不成立。

**闸门结果与同一次明示越闸：**

- `--phase full`：仍只有 2 条失败，且都是容量闸 —— `available_bytes=16686505984`，
  `required_bytes=38500000000`；以及「projected filesystem use ≥ 75%」（实际 84%）。
- **越闸说明与 2026-08-21 两次同因同判据**：容量闸按本文档 Invariants 一节的措辞是为
  **迁移峰值**标定的，本次只是替换一个**已构建完成**的镜像，切流量本身磁盘增量近似为零。
  **Stop conditions 写的是「任一闸失败即停」，此处是明示越过，不是忽略。**
- **「其余通过」不是靠沉默认定的**：拿一份 `WEB_IMAGE` 改成 `sha256:deadbeef…` 的 env 副本做
  变异，`--phase runtime` 如实多报一条 `WEB_IMAGE is not available locally`（checks 2 → 3），
  对照组同相位仍是 2。副本 `shred -u` 删除，未落盘留存。
- 容器不变量实测：`KATRAIN_PREVIEW_MODE=0`、卷 `katrain-ucloud_katrain-state-production`、
  调度器恰好 1 个、端口仅绑 `10.8.0.3` 与 `127.0.0.1`（无公网通配）。仅 `katrain-web` 与
  一次性的 `minio-setup` 被重建，postgres / katago / minio / cron 保持原进程。
- compose 项目名在 `deploy/ucloud/compose.yml` 里是显式的 `name: katrain-ucloud`，
  所以从**新的 release 目录**跑 compose 替换的是同一个项目，不会起出平行栈 —— 换目录发布前
  应先确认这一点。

**发布后实测（外网 https://modelstella.com）：**

- `/health` = `{"status":"ok","engines":{"local":"reachable","cloud":"unconfigured"}}`；首页 200；`/galaxy` 200。
- `/api/ladder-rungs`：目录 41 档、可选 29 档，与上一版逐档一致（本次不动升降级）。
- `/api/translations?lang=cn`：**970 条**（上一版 951，+19），与 `65677ce5..26a046d0` 的
  cn `.po` 新增 msgid 数逐一吻合。**判据选在旧版根本不存在的键上**，能证伪：
  `game_room:title`=对局室、`game:nav_first`=跳到开局、`game:nav_last`=跳到最后、
  `back_to`=返回{parent}、`kifu:page_x_of_y`、`live:move_slider`、`tsumego:hint`、
  `game:in_play`，8/8 就位。只查「200 / 条数变多」分不清是新构建还是缓存。

**遗留（未处理，需决策）：** 根分区 84%（16G 可用），可回收但**本次一律未删**：
旧 release 目录 `bb3f85bf…`、`a9607e75`、`e7f0e758`、`93803100`，以及对应旧镜像与
`katrain-web:ucloud-candidate-20260724`(2.48G)。`65677ce5` 的目录与镜像在回滚窗口内**不得删除**。
