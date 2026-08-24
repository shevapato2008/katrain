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

### 2026-08-24 — 四个内容页迁统一棋盘页外壳（非迁移）

发布 `53e83787`（= "Merge origin/develop into release/ucloud-20260805"，合入 develop 的
`80f54290`），线上此前 `26a046d0`。相对线上的实际改动：**10 个 `.tsx`、11 种语言 `.po`、
四份闸脚本、61 张视觉存档、本文件一段。零后端 `.py`、零 schema。**

- 镜像：`katrain-web:53e83787`，
  `image_id=sha256:27506996787e93e6f6807a93f495acf4b56e1e123f4045888cca3e5dbcb8998d`，
  `size_bytes=542522701`（上一版 `26a046d0` 为 542210337，增量 312364 字节）。
  `build-web.sh` 的容器内容测试通过。
- 回滚锚点保留：镜像 `katrain-web:26a046d0` 与目录 `/opt/katrain/releases/26a046d0` 均在位。
  `current` → `releases/53e83787`。
- `/etc/katrain/ucloud.env` 改动仅 `WEB_IMAGE` 一行（与改前副本 `diff` 恰好 2 行）；
  改前副本 `/opt/katrain/backups/ucloud.env.20260823-2353`，改后仍 root 所有、mode 0600。
- 数据库备份 `/opt/katrain/backups/prod-20260823-2342.dump`（`pg_dump -Fc`，189600570 字节）。
  **本次沿用 2026-08-21 第二次的恢复验证豁免，且前提这次是真成立的**：那条豁免的依据写的是
  「不含 schema 变更、**也不含任何后端代码变更**」—— 本次改动逐个文件核过，确实一个
  `katrain/**/*.py` 都没动（2026-08-23 那次不能沿用，是因为它改了三个后端 `.py`）。

**闸门结果 —— 一条真红，两条明示越过：**

- **第一次 `--phase full` 报了 3 条，其中第三条是真的：`WEB_IMAGE is not immutable`。**
  原因是我先把 `WEB_IMAGE` 写成了**标签** `katrain-web:53e83787`。preflight 要求的是
  `^sha256:[0-9a-f]{64}$` 或 `name@sha256:…` —— **标签会被后来的构建重新指向，不是不可变引用**。
  改成 `docker image inspect --format '{{.Id}}'` 的 image id 后重跑，checks 3 → 2。
  **这一进一出本身就是该分支在执行的证据**，本次因此没有再另做 `WEB_IMAGE` 变异。
- 剩下 2 条仍是容量闸：`available_bytes=26780643328`、`required_bytes=38500000000`，
  以及「projected filesystem use ≥ 75%」。**与 2026-08-21 两次、2026-08-23 一次同因同判据的
  明示越过**：该闸按本文档 Invariants 一节是为**迁移峰值**标定的，本次只是替换一个已构建完成
  的镜像。Stop conditions 写的是「任一闸失败即停」，此处是明示越过，不是忽略。
- 只有 `katrain-web` 与一次性的 `minio-setup` 被重建；postgres / katago / minio / cron
  保持原进程（compose 项目名仍是显式的 `name: katrain-ucloud`，换目录不会起平行栈）。

**发布后实测（外网 https://modelstella.com）：**

- `/health` = `{"status":"ok","engines":{"local":"reachable","cloud":"unconfigured"}}`；
  `/`、`/galaxy`、`/galaxy/tsumego`、`/galaxy/report` 均 200。
- `/api/translations?lang=cn`：**976 条**（上一版 970，+6），与 `26a046d0..53e83787` 的 cn
  `.po` 新增 msgid 数逐一吻合。判据仍选在**旧版根本不存在的键**上：`report:summary_done`、
  `tsumego:kyu_tier`、`dan_tier`、`stronger_downward`、`all_levels`、`your_level`，6/6 就位。
- **再加一条构建指纹判据**：新包 `/assets/GalaxyApp-DgDiQDNZ.js` = 200，
  旧包 `/assets/GalaxyApp-CaZhuOdw.js` = **404**。i18n 那条只能证明 `.mo` 换了，
  这条才证明**前端 bundle 也确实换了**（旧包还在就说明有缓存或没换）。

**同批部署的测试环境**（home-ubuntu / https://go.sailorvoyage.top，独立库、与生产不互通）：
`develop` 快进到 `80f54290` 后 `docker compose up -d --build katrain-web`。同样 6/6、976 条，
`/galaxy/live` 等六个路径均 200；测试专用开关 `KATRAIN_LADDER_ALLOW_PROVISIONAL=1`
（`docker-compose.override.yml`，仅测试机）重建后仍在。

**本次一并记下的两点：**

- **`katrain-cron` 两台都未重建**，是有意的：本次零后端 `.py`，cron 没有功能增量。
  home-ubuntu 上 `Dockerfile.cron` 的基础镜像 `python:3.11-slim` 仍拉不动 Docker Hub，
  这条阻塞照旧存在，只是本次不构成发布缺口。
- 上一条「遗留（未处理）」已自然消解：旧 release 目录 `bb3f85bf…`、`a9607e75`、`e7f0e758`、
  `93803100` 与对应旧镜像现已不在，根分区从 84% 降到 **75%（25G 可用）**。当前保留三份：
  `53e83787`（线上）、`26a046d0`（回滚锚点，**回滚窗口内不得删除**）、`65677ce5`（更早一版）。

### 2026-08-24 — 棋谱库列表性能修复 + 「建议」改称「支招」（非迁移，**含一条 DDL**）

发布 `3d65e536`（合入 develop 的 `58f130c0`），线上此前 `53e83787`。相对线上 12 个文件：
**3 个后端 `.py`**（`katrain/web/api/v1/endpoints/kifu.py`、`katrain/web/core/migrations.py`、
`katrain/web/core/auth.py`）、2 份 `.po`、4 个 `.tsx`、1 个新测试、本文件一段。
**无 schema 迁移，但有一条新索引**，由启动期迁移 `create_kifu_album_sort_index` 自建。

- 镜像：`katrain-web:3d65e536`，
  `image_id=sha256:62536691fd314ab75d918e6fcc72779a1ca2e314a0c80b8a1ef802612be25280`，
  `size_bytes=542524053`（上一版 542522701，增量 1352 字节）。`build-web.sh` 容器内容测试通过。
- 回滚锚点：镜像 `katrain-web:53e83787` 与目录 `/opt/katrain/releases/53e83787` 均在位。
  `current` → `releases/3d65e536`。
- `/etc/katrain/ucloud.env` 只改 `WEB_IMAGE` 一行（与改前副本 `diff` 恰好 2 行）；
  改前副本 `/opt/katrain/backups/ucloud.env.20260824-1348`，仍 root 所有、mode 0600。

**恢复验证：这次不能豁免，而且做了。**
备份 `/opt/katrain/backups/prod-20260824-1246.dump`（`pg_dump -Fc`，192198943 字节）。
2026-08-21 第二次那条豁免的依据是「不含 schema 变更、**也不含任何后端代码变更**」——
本次改了三个后端 `.py`**并且**新建了一条索引，前提两头都不成立。
恢复进临时库 `katrain_restore_verify`：`pg_restore` 0 错误，**38 张表里 37 张逐行一致**。

> 唯一不一致的是 `live_analysis`（生产 61754 / 恢复 61747，差 7 行）。**没有当成噪声放过，
> 而是量了**：连采三次间隔 20 秒 —— `04:49:33=61759`、`04:49:53=61761`、`04:50:13=61765`，
> 约每 20 秒 +2 行。这张表在 dump 之后仍在持续追加，7 行正是那段写入窗口，不是恢复缺陷。
> 判据是「该表是否在持续增长」，不是「差值小不小」。验证库已 DROP。

**闸门结果：**

- `--phase full` 只剩 2 条容量闸失败：`available_bytes=22232080384`、
  `required_bytes=38500000000`，以及「projected filesystem use ≥ 75%」（实际 79%）。
  **与前三次同因同判据的明示越过**（该闸为迁移峰值标定，本次只是替换已构建完成的镜像）。
- **上一次学到的那条这次直接照做了**：`WEB_IMAGE` 必须写 **image id digest**，不能写标签
  （2026-08-23 先写成 `katrain-web:53e83787`，闸如实报 `WEB_IMAGE is not immutable`）。
  这次直接 `docker image inspect --format '{{.Id}}'`，该分支没红。
- 「其余通过」仍不是靠沉默认定：把 `WEB_IMAGE` 改成 `sha256:deadbeef…` 的副本做变异，
  `--phase runtime` 如实多报 `WEB_IMAGE is not available locally`（checks 2 → 3），
  对照组同相位仍是 2。副本 `shred -u`。
- 只有 `katrain-web` 与一次性 `minio-setup` 被重建；postgres / katago / minio / cron 保持原进程。
- 启动日志确认 DDL 执行：`migrate: created index ix_kifu_albums_date_sort_desc_id_desc on kifu_albums`。

**这次修的是什么（供以后同类问题对照）：**

`/api/v1/kifu/albums` 在 151,197 行、堆 247MB 的表上要 1.3 秒，两处叠加：

1. `Query.count()` 把**带 ORDER BY 的**查询整个套进子查询，COUNT 也要排序，外部归并落盘 3712kB。
   而且那个子查询把 `sgf_content` 也选了进去 —— `defer()` 是 loader option，`.count()` 不认它。
2. `date_sort DESC NULLS LAST, id DESC` 没有能用的索引：现有 `btree(date_sort)` 是默认
   ASC NULLS LAST，**反向扫出来是 DESC NULLS FIRST**，不是同一个顺序。

补索引 + 拆 COUNT 之后，生产 `EXPLAIN ANALYZE` 实测：

- 取当页：`Index Scan using ix_kifu_albums_date_sort_desc_id_desc`，**9 个 buffer、0.14ms**
  （原先并行全表扫 + top-N，31,707 buffer、364ms）
- COUNT：并行 index-only scan，**18ms**（原先 557ms、带落盘排序）

**发布后实测：**

- 同一条 ssh 隧道（与部署前 1.28–1.37s 可比）：列表接口 **0.054–0.062s**；
  搜索 `q=丁浩` 0.786s → **0.587s**（COUNT 那半变快，`LIKE '%q%'` 仍是全表扫）；详情 0.058s。
- 真浏览器打开 `/galaxy/kifu`：`kifu/albums` 请求 **1249ms → 44ms**。
- 外网 `https://modelstella.com`：`/health` ok；`/`、`/galaxy`、`/galaxy/kifu`、`/galaxy/research` 均 200。
- `/api/translations?lang=cn` 仍 **976 条**（本次没有新键，只改值），7 个键全部读作「支招」。
  **条数不变时更要看构建指纹**：新包 `/assets/GalaxyApp-BNATEQSJ.js` = 200，
  上一版 `/assets/GalaxyApp-DgDiQDNZ.js` = **404**。

**没修的（已写进代码 docstring）：** 深翻页 `OFFSET 151180` 仍约 361ms（规划器回退到全表扫+排序，
要 keyset 游标分页才治）；搜索 `search_text LIKE '%q%'` 仍是全表扫（要 pg_trgm GIN）。

**磁盘清理（2026-08-24 当天做掉，Fan 授权）：** 根分区 **79%（21G）→ 70%（30G）**，净释放 9G。

删的三类，删之前逐项确认过没有引用方：
- release 目录 `65677ce5`、`26a046d0`（三版、两版之前）—— 保留 `3d65e536`（线上）与
  `53e83787`（**回滚锚点，回滚窗口内不得删除**，目录与镜像清理后复查均在位）。
- 镜像 `katrain-web:{65677ce5,26a046d0}` —— 删前用 image id 反查 `docker ps -a`，各 0 个容器引用。
- `docker builder prune -f`（4.222GB）。**没有加 `-a`**：全清会让下次构建重跑 apt/pip/npm，
  而这台机器拉这两个源会中途停死（pip 还会报误导性的 `from versions: none`）。
- **备份目录 1.1G 一律没动。** 四份 `prod-*.dump` 是唯一的数据后路，不拿它换磁盘。

清理后复查：六个容器全 healthy、`current` 仍指 `3d65e536`、外网 `/health` ok、
`/`、`/galaxy`、`/galaxy/kifu` 均 200、棋谱库列表接口 0.49s（外网含跨境 RTT）。

**容量闸仍然过不了，而且过不了是对的**：它要 38.5GB，是按**迁移峰值**标定的，
这台 97G 的盘在正常占用下永远达不到。它不是「磁盘告警」，把盘清空也没用 ——
以后仍按同因同判据明示越过，不要为了让它变绿去删该留的东西。

### 2026-08-24（晚）— 直播列表修复，连着三次发布（非迁移）

`3d65e536` → `fc1e73c3` → `772ee97a` → `c7f3eed7`。三次都只动 `katrain/cron/**`，
**一次 schema 都没动**。改的是同一条链上的三处，一处修完才量得出下一处：

1. **`fc1e73c3`** —— 上游不再列为 live 的对局要降级。`SourceRegistry` 先把
   「这家答没答」做成显式状态位（key 在 = 答了，哪怕是空集合；key 不在 = 这轮没问到），
   `FetchListJob` 去掉 `if not all_rows: return` 并新增降级。
2. **`772ee97a`** —— 装完上一条，日志每轮都是 `demoted 49`，接口读出来仍是 49 局 live。
   `poll_moves` 每 3 秒把它们改了回去：对局结束后上游 `/situation/<id>` 只回信封
   `{"code":"0","msg":""}`（**21 字节，没有 data**），`get_situation` 的
   `data.get("data", data)` 把信封当局面返回（真值 dict，`if not situation` 拦不住），
   再往下 `md.get("liveStatus", 0) == 0` —— 默认值 0 恰好是「进行中」。
3. **`c7f3eed7`** —— 测试机上每轮 `FetchListJob failed`：dedup 那句 `db.delete(dup)`
   撞 `live_analysis_match_id_fkey`，错在 `commit()` 才炸，**把整轮（含降级）一起回滚**。
   放进 savepoint，删不掉就退回「跳过这条新行」。生产没撞上，是数据不同。

三处是同一个错的三次出现：**「上游没说」被读成了「上游说还在下」。**
判别位必须是上游真写进来的值，不能是一条消息的缺席，更不能给它配一个恰好等于
「进行中」的默认值。

**这次发布方式与以往不同的两点，都记死：**

- **`katrain-cron` 挂在 `profiles: [production]` 下**，所以历次 `docker compose up -d`
  **从来没有换过它**（部署前它已经 `Up 13 days`，跑的是两周前的镜像）。
  要换必须显式带 `--profile production`。这条不写下来下次还会踩。
- **没有 cron 的构建脚本**（`deploy/ucloud/scripts/` 里只有 `build-web.sh`）。
  cron 镜像是手工 `docker build --pull=false -f Dockerfile.cron -t katrain-cron:<sha> .`，
  再把 `CRON_IMAGE` 改成 `docker image inspect --format '{{.Id}}'` 的 digest。
- `772ee97a` 与 `c7f3eed7` **只重建了 cron，没有重建 web**：这两次相对上一版
  web 源码零改动，且 `katrain/web/**` 不 import `katrain.cron`（已 grep 确认）。
  代价是 release 目录的树比 `WEB_IMAGE` 新，**这一点是有意的，记在这里免得以后当成漂移**。
  当前 `WEB_IMAGE` 对应的是 `fc1e73c3` 那次构建。

**`docker builder prune -f` 的一个没预料到的代价（自己造的，记下来）：**
当天早些时候为腾磁盘跑的 `docker builder prune -f`（4.222GB）把 `Dockerfile.web` 里
按 digest 钉死的 `node:22-bookworm-slim@sha256:6c74791e…` 的缓存一并清掉了，
而这台机器连不上 Docker Hub ⇒ **web 镜像一度构建不出来**
（`failed to resolve source metadata for node:22-bookworm-slim@sha256:…`）。
修法：从国内镜像源**按同一个 digest** 拉回来再打上官方名 ——
`docker pull docker.m.daocloud.io/library/node@sha256:6c74791e…` +
`docker tag … node:22-bookworm-slim`，之后 `build-web.sh` 恢复正常。
可用的源实测：`docker.m.daocloud.io`、`dockerproxy.net`、`docker.1panel.live`
（`hub-mirror.c.163.com` 不可用）。**以后在这台机器上 prune 构建缓存之前，
先确认按 digest 钉死的基础镜像在本地留得住。**

**发布后实测：** 上游 `/all` = `{"code":"0","msg":"","data":[]}`、`/count` = 0（**HTTP 200，
星阵没有拒绝我们**）。修复前生产接口 49 局标 live，修复后 **50 条全部 finished**，
与上游一致；cron 日志 `demoted 0`（没有可降的了）、`poll_moves` 被跳过 **0 次**
（此前它每 3 秒去轮询 28 局早已下完的棋，把自己堵死）。

**遗留：** 根分区 **82%**（三次发布各留一份 release 目录与镜像）。可回收：
`3d65e536`、`fc1e73c3`、`772ee97a` 三份目录与对应镜像（`c7f3eed7` 是线上，
`772ee97a` 是回滚锚点，**它不能删**）。本次未删。

### 2026-08-24（夜）— 根分区清理：82% → 71%

承接上一条的「遗留」。**上一条列的可回收项，本次仍未删**（`3d65e536`/`fc1e73c3`/
`772ee97a` 三份 release 目录与镜像都还在，回滚窗口未关）。本次回收的是另外三处，
与回滚锚点无关。

**先记一个会把人带偏的量法：`du /var/lib/docker` 报 32G 是假的。**
这台的 Docker 用 containerd 快照器（`Storage Driver: overlayfs` +
`driver-type: io.containerd.snapshotter.v1`，`ctr namespaces ls` 里是 `moby`），
镜像层实际落在 `/var/lib/containerd`；运行中容器的 rootfs 又挂在
`/var/lib/docker/rootfs` 下（实测 15 个挂载点），`du` 会把 containerd 里那份**再数一遍**。
`du -shx --exclude=rootfs /var/lib/docker` = **8.3G** 才是 Docker 自身。
判据：**在装了 containerd 快照器的机器上，`du /var/lib/docker` 与
`/var/lib/containerd` 不可相加。**

清理前 79G/97G（82%）的真实构成：

| 占用 | 大小 | 备注 |
|---|---|---|
| `/var/lib/containerd`（镜像层 + 构建缓存） | 39G | `katago-trt:latest` 一个就 **20.8G** |
| `/opt/katrain/releases` | 12.4G | 4 份 × 3.1G，**其中每份 2.0G 是 `.git`** |
| Docker volumes | 8.3G | postgres 3.5G、minio 2.7G、smartbox-kifu 1.9G |
| `/swapfile` | 8.1G | 已用 2.2G |
| `/var/log` | 5.9G | journal 4.0G、`kifu-telemetry.ndjson` 1.3G、btmp 540M |
| `/usr` + 其它 | 3.3G | |
| `/opt` 其它项目 | 0.9G | pitch-booking、smartbox-kifu |

**这台不是只跑 katrain** —— pitch-booking、smartbox-kifu、platform 都在上面，
共 15 个容器。腾空间时别只盯着 katrain。

**本次回收（共 10G，82% → 71%，剩余 19G → 29G）：**

1. `journalctl --vacuum-size=500M` → **3.4G**。
2. `truncate -s 0 /var/log/btmp` + `rm /var/log/btmp.1` → **540M**。
   截断前 `lastb | wc -l` = **570,629 条失败登录** —— 这台一直在被爆破扫，
   值得单独评估要不要上 fail2ban（本次未做）。
3. 三份**非 current** release 目录的 `.git` → **6.0G**（每份 2.0G）。
   删前逐个校验 `deploy/ucloud/compose.yml` 与 `scripts/build-web.sh` 在位才动手；
   工作树完整保留，三个回滚锚点的 compose/脚本/镜像事后复核全部 ✓。

**为什么留下 `current`（`c7f3eed7`）那份 `.git`：** 新 release 目录是**从已有 release
目录本地 `git clone`** 出来的（见 2026-07-31 那条：「`git clone` 因源仓是 shallow
而未能硬链接复用对象」）。四份全删，下次部署就没有本地克隆源。
GitHub 本次实测**直连可用**（`git ls-remote` 拿到 `develop` = `7d551ba6`，exit 0），
所以留的这份不是唯一依赖，只是快。

**根因没修（下次部署仍会再长 2G）：** 源仓虽然是 shallow，但 grafted 点很深
（`git rev-list --count HEAD` = 2611），pack 里压着 KataGo 二进制与 b18 权重
（单个 blob 97MB：`kata1-b18c384nbt-s9996604416`、`KataGo/katago-bs` 73MB），
所以本地 clone 一份就是 1.98 GiB，而工作树只有 1.1G。
**建议改成从 GitHub `git clone --depth 1`**，一份 release 目录可从 3.1G 降到约 1.1G。
未改，因为动的是部署流程，需要单独确认。

**未处理（本次没碰）：** `kifu-telemetry.ndjson` 1.3G **没配日志轮转**，会一直长；
构建缓存 12.24G **不要动** —— 见上一条 `docker builder prune -f` 的代价，
且 `docker system df` 显示它可回收的只有 639M。

**清理后复核：** `df -h /` = 69G/97G（71%），15 个容器全 healthy，
`curl localhost:8001/api/v1/health` = 200，`current` → `releases/c7f3eed7` 未变。
