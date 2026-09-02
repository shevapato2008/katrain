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

### 2026-08-25 — 上一条留的三项收口（治根，不是再腾一次空间）

上一条清出 10G 靠的是删东西，源头一个没动。本次三项都是**堵源头**。

#### 1. 停掉一个跑了 21 天的失控采样进程（每年 24G）

`/var/log/kifu-telemetry.ndjson` 我上一条写成「没配日志轮转」，**定性错了**。真相：

```
PID 627940  /bin/bash ./telemetry-sample.sh
启动 Mon Aug  3 11:41:08 2026    停时已运行 22 天
cwd  /opt/smartbox-kifu/releases/20260803-gen2-rollout/kifu-platform/deploy
```

它的父进程链是一条 **Aug 3 卡死的交互式诊断命令**
（`sudo bash -c "... telemetry-sample.sh | head -1"` —— `head -1` 读完就走，
脚本里的 `while [ "$running" = 1 ]` 却没人叫停）。3 秒内 `wchar` 涨 9.8KB，
**一直在写**：1,583,543 行 / 1.3G / 21 天 = **64.9 MB/天 → 23.7 GB/年**，1.2 秒一条。

**所以 logrotate 是错药** —— 加轮转只是把没人看的垃圾定期切片，源头照长。
脚本自带 `trap 'running=0' INT TERM`，按 trap 停：

```bash
kill -TERM 627940          # 优雅退出，不硬杀
kill -TERM 627939 627937 627814   # 清掉已成孤儿的父链
```

停后观察 6 秒，文件**增长 0 字节**。

**判据（值得记）：`ps` 里 `ELAPSED` 以「天」计、`%CPU` 却是 0.0 的 bash，
十有八九是某次交互式排查留下的。** 找它们不看进程名，看 etime。

那 1.3G 数据**没删** —— 它是 smartbox-kifu 的东西，不是 katrain 的。
要不要留由那边定。`pgrep -af telemetry-sample` 会匹配到查询命令自己，别被它骗。

#### 2. 关闭 SSH 密码登录（原来的「上 fail2ban」建议排错了顺序）

`btmp` 里 570,629 条失败登录不是噪声，是**真暴露面**：

```
passwordauthentication yes       ← 开着
permitrootlogin without-password
passwd -S ubuntu → ubuntu P      ← ubuntu **有密码且未锁定**
```

而 715 次成功登录**全部是 `publickey`、全部是 `ubuntu`**，一次密码登录都没有。
有 shell 的真实用户也只有 `ubuntu` 一个 ⇒ **密码登录零收益**。
被撞最多的是 `root`（23594 次，被 `without-password` 挡着）和 **`ubuntu`（1240 次，
挡不住）**。

**先关密码登录，fail2ban 才是次要的**（关完之后它只剩「减少日志噪声」的作用）。

**坑：`PasswordAuthentication yes` 写在两个文件里**

```
/etc/ssh/sshd_config:58
/etc/ssh/sshd_config.d/50-cloud-init.conf:1
```

sshd 取**先读到的**值，而 `sshd_config.d/*` 是在主文件顶部 Include 的 ⇒
**cloud-init 那份赢**。只改 `sshd_config` 不生效。改完必须 `sshd -T` 回读。

**改远程 SSH 配置的安全姿势（本次用的）** —— 事前无法确认 UCloud VNC 兜底可用，
所以装了「死人开关」代替：

```bash
BK=/root/sshd-backup-$(date +%Y%m%d-%H%M%S); mkdir -p $BK
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.d/50-cloud-init.conf $BK/
# 180 秒后无条件还原并 reload，除非标记文件被删除
nohup sh -c "sleep 180; [ -f /root/.sshd-deadman-armed ] && { cp $BK/* 回原位; systemctl reload ssh; }" &
touch /root/.sshd-deadman-armed
# 改 → sshd -t（**reload 前必须过**）→ systemctl reload ssh（不是 restart）
# → 用**新连接**验证密钥仍可用 → rm /root/.sshd-deadman-armed
```

改后实测：

```
强制只用密码  → ubuntu@117.50.183.169: Permission denied (publickey).
密钥          → Accepted publickey for ubuntu from 120.245.64.242
sshd -T       → passwordauthentication no
```

备份留在 `/root/sshd-backup-20260825-114356/`。

#### 3. release 目录改用 `git clone --depth 1`（每次省 1.6G）

**先纠正上一条写错的数**：那里写「一份 release 目录可从 3.1G 降到约 1.1G」是错的
—— `.git` 不可能是 0。服务器上跑探针实测：

| | `.git` | 工作树 | 合计 |
|---|---|---|---|
| 现在（从上一个 release 目录本地 clone） | 2.0G | 1.1G | **3.1G** |
| `clone --depth 1 --branch <分支>` | **403M** | 1.1G | **1.5G** |

**省 1.6G/次，不是 2G。**

为什么本地 clone 这么大：源仓虽是 shallow，但 graft 点在 2611 个 commit 之外
（`git rev-list --count HEAD` = 2611），pack 里压着 KataGo 二进制与 b18 权重
（单 blob 97MB：`kata1-b18c384nbt-s9996604416`；`KataGo/katago-bs` 73MB），
而 `git clone` 从 shallow 源仓**无法硬链接复用对象** ⇒ 每次整份复制。

**没有脚本在建 release 目录**（`grep -rl "git clone" deploy/` 空，
`deploy/ucloud/scripts/*.sh` 里 `git` 一次都没出现）—— 这一步一直是手工的，
所以「改部署流程」= 改这里。**下次发布照抄：**

```bash
SHA=<release 分支尖端的 short sha>
sudo git clone --depth 1 --branch release/ucloud-20260805 \
     https://github.com/shevapato2008/katrain.git /opt/katrain/releases/$SHA
sudo git -C /opt/katrain/releases/$SHA rev-parse --short HEAD   # 核对 = $SHA
# 然后照旧：build-web.sh → preflight.sh → 切 current 软链 → docker compose up -d
```

GitHub 本机实测直连可用（`git ls-remote` exit 0）。**不再从旧 release 目录 clone。**

改完之后 `current`（`c7f3eed7`）那份 2.0G 的 `.git` 就不再是必需的克隆源了，
**但本次没删** —— 这台机器有过连不上外部 registry 的前科，留一份本地兜底。
等 `--depth 1` 真正跑通一次发布之后再回收。

**盘面：** 71% → **72%（70G/97G，剩余 28G）**。本次三项都不是为了立刻腾空间，
是把「每年 24G」和「每次 +1.6G」两个源头堵上；SSH 那项与磁盘无关。

### 2026-08-25（夜）— 发布 `e9a7889e` + **把生产从 preview profile 切回 production**

两件分开做、分开验，为的是出事时能归因。

#### 第一步：补发代码 `e9a7889e`

`fix/test-fixture-isolation` 那两条（2026-08-23 做完一直没并）今天并进 develop 后补发。
只动后端与测试，不含前端。

**合并时 `server.py` 冲突了一处**，两边分别是：release 的 `PREVIEW_MODE` 守卫、
develop 把 `SessionLocal as _SL2` 换成可注入的 `session_factory()`。**两者都要**——
守卫决定跑不跑，`session_factory` 决定跑在哪个库上。解完复核：三处 `PREVIEW_MODE`
守卫俱在，无残留标记，相关 38 条测试通过。

- `git clone --depth 1` → `/opt/katrain/releases/e9a7889e` **1.5G**（第三次，稳定）。
- 镜像 `katrain-web:e9a7889e`，
  `image_id=sha256:53bfcb82ff9a163eb0b7849803aadc0bb264bba0a657cd655b14d5382c802f44`，
  `size_bytes=542526049`（上一版 542524873，+1176）。`build-web.sh` 容器内容测试全过。
- `--phase full` 仍只有那 2 条容量闸（`available_bytes=22352781312`），`checks=2`，同因越过。
- env 备份 `/opt/katrain/backups/ucloud.env.20260825-1614`，diff 恰好 2 行，root:root 0600。
- **回滚锚点：** 目录 `releases/a9b2485b` + 镜像 `katrain-web:a9b2485b`。

验证：镜像 id 逐字符相符、health 200、外网 `/`、`/galaxy`、`/galaxy/research` 全 200。

#### 第二步：切回 production profile（修上一条记的那个错位）

**先查清机制再动手。** 两个容器的 `config_files` 标签把事情说明白了：

```
katrain-cron : .../c7f3eed7/compose.yml,.../c7f3eed7/compose.production.yml   ← 用完整命令起的
katrain-web  : .../e9a7889e/compose.yml                                        ← 只用了短命令
```

所以不是有人决定让生产跑 preview，而是**后续每次「只发 web」都用了那条短命令，
把 web 的 production override 冲掉了**，cron 那半一直是对的。

**切之前先排掉三个风险，每一个都是量出来的，不是想出来的：**

1. **卷里会不会有东西丢**：preview 卷只有 `config.json`（+ 我今早的备份），20K；
   production 卷有 `.platform_salt` 和 `platform_credentials.db`。⇒ 切过去**不丢任何东西**。
2. **打开 billing 对账会不会动钱**：`reconcile_stale_reservations` 会退款 `status='reserved'`
   且超时的交易。生产库实测 **`credit_transactions` 表是空的** ⇒ 零影响。
3. **production 卷里的 engine 配置**：和 preview 卷今早修之前一模一样的病
   （`http_url=http://127.0.0.1:8000`、`http_has_human_model=False`）。**不修就切，
   引擎会立刻回到「连不上 → 回退本地 KataGo → status 127 死掉」。**
   先改（备份 `config.json.bak-20260825-081537`，带断言只许这两个键变），再切。

切换命令用 runbook 第 43 行那条（`-f compose.yml -f compose.production.yml --profile production`）。

**验证（逐条对着 `PREVIEW_MODE` 管的那三处）：**

| 项 | 切换前 | 切换后 |
|---|---|---|
| `KATRAIN_PREVIEW_MODE` | 1 | **0** |
| 挂载卷 | `katrain-state-preview` | **`katrain-state-production`** |
| `GET /api/v1/live/matches` | **503** `Live service not initialized` | **200** |
| 平台适配器 | 不初始化 | **OGS / Fox registered** |
| 调度器数量 | 1 | 1（invariant 要求恰好一个） |

引擎端到端实测：容器内现签一个 5 分钟 token 给已存在的 `qa_verify`（不新建账号、
不碰密码），开一个**内存会话**走一手，**AI 1 秒内回手**。会话不到终局 ⇒ 不落库，跑完即弃。

外网 `/`、`/galaxy`、`/galaxy/live` 全 200。盘面 77% → **79%（21G 可用）**。

**回滚**：`-f compose.yml up -d`（短命令）即切回 preview；env 备份在
`/opt/katrain/backups/ucloud.env.20260825-1614`；production 卷 config 备份见上。

**以后别再踩**：只发 web 时**也要用完整命令**。短命令会静默把 web 的 production
override 冲掉，而且**冲掉之后一切看起来都正常**——health 200、页面 200，只有直播那一格
503，而没人天天点它。判据：发布后查一次
`docker inspect katrain-ucloud-katrain-web-1 --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'`，
必须是**两个**文件。

#### 顺带修掉的：测试域名网关那两行（不同机器，同一天的故事）

`alicloud-ecs-gateway` 上 `go.sailorvoyage.top` 的 504 已治：新增
`/etc/nginx/conf.d/katrain-upstream.conf`（`map $http_upgrade $connection_upgrade` +
`upstream katrain_go { server 10.8.0.2:8001; keepalive 32; }`），站点里
`proxy_pass` 改指 upstream、`Connection` 改用 map 变量、`proxy_connect_timeout` **5s → 15s**。
备份 `/root/nginx-backup-20260825-1613/`。

验证：`nginx -t` 通过、reload 后 `/`、`/galaxy`、`/api/v1/health` 全 200、
**重复请求 `connect` 降到 ~1ms**（连接复用生效）、**WS 升级仍是 `101`**（这是改
`Connection` 头的主要风险，专门验了两次）。

> 中途出现过一次 `502`，**不是这个改动**：那一刻测试机容器 08:13:17 才启动，探针
> 08:13:28 打进去，差 11 秒应用还没起来。判据是容器 `StartedAt`，不是「改完就红所以是改的」。

**遗留（未处理）：** 根分区 79%（21G）。`releases/` 下有 7 份，其中 5 份已无引用
（`3d65e536` / `772ee97a` / `c5b8c4eb` / `c7f3eed7` / `fc1e73c3`，合计约 8.3G）。
保留 `e9a7889e`（线上）与 `a9b2485b`（回滚锚点）。**未删，等授权**——容量闸那条老规矩
仍然成立：它要 38.5G 是按迁移峰值标定的，清盘也不会变绿，别为了让它绿去删该留的东西。

---

### 2026-08-25（傍晚）— 发布 `a9b2485b`：研究/复盘页的 WS 凭据（同族最后一处）

下午发的 `c5b8c4eb` 修的是**对局** WS。之后普查了全仓 6 个 `new WebSocket()` 调用点与
后端 3 条 WS 路由，找到同族的最后一处：`useResearchSession` 压根不收 token，往
`useSessionBase` 递进去的是 `undefined`。测试机原始 close 帧实测（同一 research session）：

```
不带 token → CLOSE code=1008 reason='Invalid token'
带  token  → 收到 game_update
```

后果与对局那条同形：研究页 `onMove` 只发 HTTP、状态全靠推送 ⇒ 摆子「点了没反应」、
分析永不刷新。两个 ResearchPage 手里本来就有 `token`（都写了 `useAuth()`），只是没往下传。

**闸也一并改了，因为上一版的闸量错了对象。** 它检查 `websocketUrl()` 收没收到第二个参数，
而 `useSessionBase` 一直老实把自己的 `token` 递进去 —— **参数在**，闸全绿。缺的是更外面一层。
新一组落在真正的操作数上：谁调用这三个 hook，谁就得在选项里显式写出 `token`。
变异验证（真跑）：把 `galaxy/pages/ResearchPage.tsx` 改回 `useResearchSession()` ⇒ 新增两条转红。

**发布数据：**

- `git clone --depth 1` 第二次实战：`/opt/katrain/releases/a9b2485b` **1.5G**（与首次同）。
- 镜像 `katrain-web:a9b2485b`，
  `image_id=sha256:01b14b65429f10e020f9c9f443bd63f067443a22de921a1d09b780c9df603a34`，
  `size_bytes=542524873`（上一版 `c5b8c4eb` 为 542524786，**+87 字节**）。`build-web.sh` 容器内容测试全过。
- `/etc/katrain/ucloud.env` 只改 `WEB_IMAGE` 一行（与备份 `diff` 恰好 2 行），仍 root:root / 0600；
  备份 `/opt/katrain/backups/ucloud.env.20260825-1536`。
- **回滚锚点：** 目录 `releases/c5b8c4eb` + 镜像 `katrain-web:c5b8c4eb`
  （`sha256:50f9a56f48d1…`），均已复查在位。`current` → `releases/a9b2485b`。
- 盘面 74% → **77%（24G 可用）**。

**闸门：** `--phase full` 仍只有那 2 条容量闸（`available_bytes=24921931776`、
`required_bytes=38500000000`、projected ≥ 75%），`checks=2`，与历次同因同判据明示越过。
**这次没有重做变异验证**，理由是查过 `preflight.sh` 自 `661b7cc7`（2026-07-24）起一字未改，
而 2026-08-24 那次变异正是对这同一份脚本做的 —— 重复做不增加信息。

**验证（不靠 health 200 一条撑着）：**

- 新旧镜像的前端产物逐文件比对：**16 个 chunk 换了哈希、255 个不变**。换的正是这次动到的
  （`GalaxyApp` / `KioskApp` / `useReportDetail` / `Undo` / `index` 等）。
- 外网指纹对照：新 `/assets/index-CJo6Tllh.js` = **200**，旧 `/assets/index-BBvEhq70.js` = **404**。
- `https://modelstella.com` 的 `/api/v1/health`、`/`、`/galaxy`、`/galaxy/research`、`/galaxy/kifu` 全 200。
- 容器内 `katago-web:8000/health` → `status=ok, has_human_model=True`。
- 卷里那份今早修好的 engine 配置**没被这次重建冲掉**：`http_url=http://katago-web:8000`、
  `http_has_human_model=True`。

#### 本次发现的一件**既有**配置错位（未处理，需要决定）

**生产的 web 容器跑在 preview profile 上**，而 cron 是 production profile 起的：

```
KATRAIN_PREVIEW_MODE=1
挂载 katrain-ucloud_katrain-state-preview -> /home/katrain/.katrain
config_files = /opt/katrain/current/deploy/ucloud/compose.yml    ← 没有 compose.production.yml
katrain-ucloud-katrain-cron-1  Up 19 hours (healthy)             ← 却是 production profile 的
```

这违反本 runbook 开头的 Invariants（production 应为 `PREVIEW_MODE=0` + `katrain-state-production` 卷）。
`PREVIEW_MODE` 在 `server.py` 里管三处，都是「**不**做」：

1. `server.py:210` — 崩溃后的 billing 预留对账不跑；
2. `server.py:282` — **直播服务不启动**。实测 `GET /api/v1/live/matches` → **503
   `{"detail":"Live service not initialized"}`**；
3. `server.py:298` — 跨平台对弈的 `PlatformManager` 不初始化。

**本次刻意没有切过去**，理由不是怕麻烦而是有具体风险：production 卷里的
`config.json` 是 **2026-07-25** 的，切过去等于换掉 `/home/katrain/.katrain` ——
今早那份修好的 engine 配置在 **preview** 卷里，一切就又回到「引擎不可用」。
要切得先把 production 卷里的 config 也修好并验过，那是一次独立的变更。

**顺带澄清一件不是应用缺陷的事**：同日测试域名 `go.sailorvoyage.top` 上点「对局」报 504，
根因在**网关**不在应用 —— `acme_error.log` 写的是 `upstream timed out (110) while
**connecting** to upstream`，即 TCP 都没连上，应用日志那一秒一片空白。该站点是
阿里云 nginx → WireGuard → 家宽上的 home-ubuntu，网关 `proxy_connect_timeout` 只有 **5s**，
且全局无 `upstream{keepalive}`（每个请求都要重新握手）。生产是 `proxy_pass http://127.0.0.1:8001`
同机直连，结构上不会发生。历史上该站点共 9 次 504，其余 8 次全在 8 月 16 日那次停服里。

---

### 2026-08-25（下午）— 发布 `c5b8c4eb`：自由对弈无法落子的修复

发布内容：对局 WebSocket 从来不带凭据，AI 走的每一手都推不到浏览器
（详见 commit `dc55f32e` 与 `katrain/web/ui/src/utils/websocketUrl.test.ts` 的头注）。
`c751e8dd`（2026-08-04）把 `/ws/{session_id}` 的鉴权从「只在 strict box 模式下检查」
改成无条件，而前端三处对局 WS 一处都不带凭据 ⇒ **两个线上环境已断三周**。

**只换 web，没换 cron**：`Dockerfile.cron` 只 `COPY katrain/cron/`，
且 `katrain/cron/models.py` 明写「zero imports from katrain.web」，本次改动碰不到它。
命令用第 37 行那条（不带 `--profile production`），cron 容器保持 16 小时前那个不动。

**`--depth 1` 首次实战（上一条刚定的新步骤）：**

```
git clone --depth 1 --branch release/ucloud-20260805 … /opt/katrain/releases/c5b8c4eb
→ 合计 1.5G（.git 403M）   对照 c7f3eed7 的 3.1G
```

**与预测一致，省 1.6G。** 新旧目录并排摆着就是证据：

```
3.1G  releases/c7f3eed7     ← 旧法（从上一个 release 本地 clone）
1.5G  releases/c5b8c4eb     ← 新法（GitHub --depth 1）
```

**preflight 仍是那 2 条容量闸失败后继续** —— `available_bytes=27119853568`、
`required_bytes=38500000000`、「projected ≥ 75%」。与 2026-07-31 / 08-14 / 08-23 / 08-24
历次完全同形，那道闸是按**迁移**量级设的，不是按换一次 web 镜像。

**验证：** 6/6 healthy、`/api/v1/health` 200、容器镜像 id 与构建产物逐字符相符、
bundle 里含 `?token=${encodeURIComponent`、WS 握手 `101` 且持续收到 `game_update`
（修复前此处是 `CLOSE 1008 'Invalid token'`）。盘面 72% → 74%（26G 可用）。

**回滚锚点：** 目录 `releases/c7f3eed7` + 镜像 `katrain-web:fc1e73c3`
（`sha256:f1fa474eeabd…`）+ env 备份 `/etc/katrain/ucloud.env.bak-20260825`。

---

#### 本次顺带查出的一件**既有**故障（未修，需要决定）

**生产上拟人 AI 走不出手** —— 与上面这个 WS 修复无关，是另一条链。实测可复现：
落一手之后 `player_to_move` 停在 W，日志只有一行
`[HumanStyleStrategy] Engine does not have a human model loaded. Falling back to PolicyStrategy.`
而 PolicyStrategy 同样走不出手。

根因是 **`/home/katrain/.katrain` 挂的那个迁移期遗留卷
`katrain-ucloud_katrain-state-preview`**，里面那份持久化 config 写着：

```
http_url             = http://127.0.0.1:8000     ← 容器内这个地址指向容器自己
http_has_human_model = False
```

于是启动时 `Checking HTTP engine status at http://127.0.0.1:8000/health` → `Connection refused`
→ `Falling back to local engine` → 本地 KataGo 因镜像里没有 `fusermount` 直接
`status 127` 死掉 ⇒ **整个会话没有可用引擎**。

**证据它不是本次发布带来的**：三个镜像里的仓库默认 config 完全一样
（`fc1e73c3`＝换之前跑的那个、`3d65e536`、`c5b8c4eb`），且那份生效的 config 根本
不在镜像里、在卷里。**测试机 home-ubuntu 没有这个卷**
（`/home/katrain/.katrain/config.json` 不存在，用镜像默认值），所以测试机是好的
—— 这也是同一份代码两个环境表现不同的全部原因。

**线路本身是通的**：容器内 `curl http://katago-web:8000/health` → 200 且
`has_human_ment=true`；compose 也已经把 `LOCAL_KATAGO_URL: http://katago-web:8000`
传进去了。`server.py:248-253` 本该用它同步 `engine/http_url` 并落盘，
但容器日志里**没有** `Syncing KataGo URL` 这一行 —— 那条分支为什么没执行，本次没查到底。

**修法（未执行，等授权）**：把卷里 config 的 `engine.http_url` 改成
`http://katago-web:8000`、`engine.http_has_human_model` 改成 `true`，重启 web。
改前先备份该文件。**不要**顺手删那个卷 —— 里面还有别的持久化状态。

**旁证**：`user_games` 近 21 天只有 1 局（2026-08-25 03:11，**3 手后黑方中盘认输**），
上一局远在 2026-06-23。3 手意味着白棋当时确实走了；「下三手就认输」正是
「看不见 AI 还手」的形状。

#### 2026-08-25（承上）— 那件既有故障已修：改卷里的持久化 engine 配置

上一条留的「未修，需要决定」已授权执行。

**改了什么**（`/var/lib/docker/volumes/katrain-ucloud_katrain-state-preview/_data/config.json`，
文件 mtime 原为 **Jul 24 20:49** —— 迁移期遗留无疑）：

```
engine.http_url             : http://127.0.0.1:8000  →  http://katago-web:8000
engine.http_has_human_model : False                  →  True
```

**手法**：先 `cp -a` 备份成 `config.json.bak-20260825-134012`（仍在位），
然后用 **json 解析改写而不是 sed**，并在脚本里断言
「engine 段里发生变化的键必须是且只是这两个」—— 不满足就 assert 失败、不落盘。
文件属主 `10001:10001` 未变（`open(p,"w")` 保留 inode）。
**注意**：整个文件被重新序列化成 `indent=2`，字节数 6900 → 5392，
**内容等价、排版变了**；要逐字节对照请用那份备份。

**卷没有删**（里面还有别的持久化状态），只改了这一个文件里的两项。

**改后重启 `katrain-web`，启动日志的变化就是判据：**

```
改前: Checking HTTP engine status at http://127.0.0.1:8000/health
      ERROR Could not connect to HTTP engine: ... Connection refused. Falling back to local engine.
      ERROR 引擎意外终止且未发送输出:  status 127        ← 本地 KataGo 缺 fusermount
改后: Syncing KataGo URL to http://katago-web:8000 from environment
      （上面三条一条不剩）
```

**端到端验证（与测试机同一个探针）：**

```
握手 HTTP/1.1 101 Switching Protocols
game_update 推送 6 次
手数 3   该谁走 B          ← AI 还手了
探针期间 AI/引擎错误日志：无
```

对照修复前同一探针在生产上的结果：`手数 2 / 该谁走 W`（AI 不还手）。

**至此生产的自由对弈两条链都通了**：WS 凭据（本次发布 `c5b8c4eb`）+ 引擎地址（本条）。
6/6 healthy、`/api/v1/health` 200、`current -> releases/c5b8c4eb`、盘面 74%（26G 可用）。

**仍未查清的一点**：`server.py:248-253` 那条 `Syncing KataGo URL` 分支，
在改配置**之前**（`http_url` 与 `LOCAL_KATAGO_URL` 明明不同、`backend` 也确是 `http`）
日志里**没有**出现，改完之后反而出现了。条件看起来该成立却没走，本次没查到底 ——
如果它当初正常执行，这个故障根本不会存在。**下一个碰这块的人从这里接。**

---

### 2026-08-27 — 发布 `7c268569`：未登录游客可下自由对弈（非迁移，无 DDL）

发布内容：`release/ucloud-20260805` 合入 `origin/develop`（`6a3f605d`）。**自动合并零冲突**
—— 两边在 `server.py` 的改动分处首尾（release 的 `PREVIEW_MODE` 守卫在 lifespan 段
220–310 行，develop 的归属闸在 725 与 1274 之后）。合并后逐项复核：三处 `PREVIEW_MODE`
守卫俱在；`git diff origin/develop HEAD -- katrain/web/server.py` 的**全部**差异就是那段
lifespan 守卫，说明 develop 上跑过的全量测试覆盖的就是这份代码。

功能面（用户可见）：
- 未登录游客可以走完自由对弈（此前卡在 `POST /api/new-game` 的必需鉴权上，屏上是一串裸
  `Request failed 401: {"detail":"Not authenticated"}`）。
- 升降级对弈仍要登录，但给出原因与登录入口，不再复用「登录已失效」那句假话。
- **无主会话不交付分析**（`analysis_delivered=false`）：堵掉「开一个不带凭据的窗口就能读到
  引擎最佳点」这条绕过升降级反作弊的路。三个分析键在前端置灰并说明「登录后可用」。
- 四个会话级写端点（`/api/config`、`/api/config/bulk`、`/api/player`、`/api/player/swap`）
  补上归属闸；`GET /api/config` 另加可读键白名单（此前不鉴权可读 `server/database_url`
  与 `contribute/*`）。

**无 schema 变更**：本次改动不含任何 migration / DDL，未取新的 `pg_dump`（与 `e9a7889e`
同口径）。

- `git clone --depth 1` → `/opt/katrain/releases/7c268569`，**1.5G**（第四次，稳定）。
- 镜像 `katrain-web:7c268569`，
  `image_id=sha256:1490683a54380cc4f1f03fca091262c29a3b7bb9f4aa627bc90bd05ceaecd7d9`，
  `size_bytes=542544116`（上一版 542526049，+18067）。`build-web.sh` 容器内容测试全过 ——
  其中 `find /app/katrain/i18n/locales -name katrain.mo` 那条正是本次新增 11 个 i18n 键的闸：
  **生产的 .mo 由 `Dockerfile.web` 的 source-pruner 阶段编译**，不需要在主机上跑 `i18n.py`
  （测试机需要，见下）。
- `CRON_IMAGE` **未动**：`Dockerfile.cron` 只 `COPY katrain/cron/`，本次改动全在 `katrain/web/`。
- `--phase full` 仍只有那 2 条容量闸（`available_bytes=28438618112`，`required_bytes=38500000000`），
  `checks=2`，**同因明示越过**（容量闸按迁移峰值标定；本次是替换一个已构建完的镜像，磁盘增量近似为零）。
- env 备份 `/opt/katrain/backups/ucloud.env.20260827-1753`，diff 恰好 2 行（只有 `WEB_IMAGE`），
  root:root 0600。
- **回滚锚点：** 目录 `releases/e9a7889e` + 镜像
  `sha256:53bfcb82ff9a163eb0b7849803aadc0bb264bba0a657cd655b14d5382c802f44`。

**四条不变量逐条实测（发布后）：**

| 项 | 值 |
|---|---|
| `Config.Image` | `sha256:1490683a…d9`（与 build 输出逐字符相符） |
| `config_files` 标签 | **两个**文件（compose.yml + compose.production.yml —— 08-25 记的那个坑没再踩） |
| `KATRAIN_PREVIEW_MODE` | `0` |
| 挂载卷 | `katrain-ucloud_katrain-state-production` |

**功能实测**（容器内 `127.0.0.1:8001` + 外网 `https://modelstella.com` 各一遍）：
匿名建会话 → `new-game` 200 → `move` 200 → `state.analysis_delivered=false` 且 `analysis=null`；
`/api/v1/ai-ladder/start` 401；`GET /api/config?setting=server/database_url` **403**、
`setting=ai/ai:human` 200；`/api/v1/live/matches` 200（production profile 的活性判据）；
五个新 i18n 键 cn 全部返回中文。探针会话跑完即 `DELETE`，不到终局 ⇒ 不落库。
外网 `/`、`/galaxy`、`/galaxy/play/ai?mode=free`、`/api/v1/health` 全 200。

盘面：71% → **72%（28G 可用）**。

**同日测试机（home-ubuntu / go.sailorvoyage.top）另走一条路**：它用的是 develop 上那份
单阶段 `Dockerfile.web`（`COPY . /app`），**不编译 .mo**，所以 `.mo` 必须先在**构建主机**上
生成。该机 `python3` 受 PEP 668 管控且无 `polib`、无 `msgfmt`，用一次性 `python3 -m venv
/tmp/i18nvenv` + `pip install polib` 跑 `i18n.py`（`.po` 零改动，只产出 `.mo`）。
顺带发现：该机 `.mo` 停在 8-21，而 `.po` 8-24 就更新过 —— **三天里测试机的新文案一直没上线**。
判据留给下一个人：`ls -la katrain/i18n/locales/cn/LC_MESSAGES/` 比一下两个文件的时间。

**遗留（未处理）：** `releases/` 下现有 3 份（`a9b2485b` / `e9a7889e` / `7c268569`）。
`a9b2485b` 已无引用可删（约 1.5G），`e9a7889e` 是回滚锚点、`7c268569` 是线上，**都不动**。

### 2026-08-29 — develop 合并后重新发布（非迁移）

发布内容：`release/ucloud-20260805` 合入 `origin/develop`（合并提交 `72024fcc`），
带上着手评价七档改造 —— 妙手从单边的目数损失轴挪到难度轴、新增「发挥水准」直方图、
妙手/问题手列表每方前 5 并加阶段/棋手筛选。

- 镜像（均为不可变 ID）：
  `WEB_IMAGE=sha256:187662fc70b9bd6efa14d474db98698b3f5b82175a4e0c9932b7058be031841e`
  （tag `katrain-web:72024fcc`，`size_bytes=542672203`；上一版 542197378，同量级），
  `CRON_IMAGE=sha256:3aca246d00c5f23ddaee3375a9f3cd623e33687970d0f0b528fd31a2a9782d61`
  （tag `katrain-cron:72024fcc`）。`build-web.sh` 的容器内容测试通过。
  **本次 cron 镜像也重建了** —— 改动涉及 `katrain/cron/`，而 compose 里 `CRON_IMAGE`
  是独立变量，只换 `WEB_IMAGE` 会让 cron 继续跑旧代码。
- 上一版镜像 ID 保留作回滚锚点：web `sha256:1490683a5438…`（tag `katrain-web:7c268569`）、
  cron `sha256:0c75181ec14c…`（tag `katrain-cron:c7f3eed7`）；
  `/opt/katrain/releases/7c268569` 未删除。
- `/etc/katrain/ucloud.env` 改动仅 `WEB_IMAGE` 与 `CRON_IMAGE` 两行；
  改前副本 `/opt/katrain/backups/ucloud.env.20260829-1800`，改后仍 root 所有、mode 0600。
- 数据库备份 `/opt/katrain/backups/prod-20260829-1747.dump`（`pg_dump -Fc`，196.2 MB）。
  **已真恢复验证**：恢复进临时库 `pg_restore` 退出码 0、零 error，逐表比对 38 张表
  的 `count(*)`，0 处不一致（含 `kifu_albums` 151197、`tsumego_problems` 21072、
  `live_analysis` 63954、`report_task_moves` 2317）。验证库已 DROP。

**本次有 schema 变更**（与 2026-08-21 那次不同）：`report_task_moves` 新增 7 列
`grade` / `points_lost` / `points_lost_source` / `is_top_move` / `top_prior` /
`brilliance` / `root_visits`，全部 nullable。仓里没有 Alembic，靠
`katrain/web/core/migrations.py::add_missing_columns` 在 `init_db` 时自动
`ALTER TABLE ADD COLUMN`。**这条路径先在测试环境（home-ubuntu）的真 PostgreSQL 上
跑通后才上生产**；生产发布后实测 7 列全部就位，`report_task_moves` 仍为 2317 行。

**闸门结果与一次明示越闸：**

- `--phase full`：**仅 2 条失败，且都是容量闸** —— `available_bytes=20711616512`，
  `required_bytes=38500000000`；以及「projected filesystem use ≥ 75%」（实际 77%）。
  与 2026-08-21 那次同形（当时 20760682496）。错误文案本身写的是
  “**migration** requires at least …”，即一次性迁移的峰值要求，不是发布要求；
  本次为非迁移发布，`peak_bytes=13500000000` 远低于可用空间。
- `--structural`：**Compose preview 与 production profile 均渲染通过**、**GPU 可用**。
- 注意：preflight 在容量闸上**快速失败**，不会继续报告其余检查项，
  所以本次没有取得 env mode / 镜像不可变 / WireGuard / 防火墙 等项的**正向**证据
  （只有 `--structural` 那两条）。镜像不可变性是手工保证的：两个 `*_IMAGE`
  都写成 `sha256:` ID 而非 tag。
- 未按 runbook 的 stop condition 停止，属**明示越闸**，理由如上，
  回滚锚点（旧镜像 ID、旧 release 目录、env 副本、已验证的库备份）齐备。

**发布后验证：** 6 个 katrain-ucloud 容器全部 healthy；`/api/v1/health` 返回
`{"status":"ok","engines":{"local":"reachable"}}`；前端产物含 `grade:performance`；
`/api/translations?lang=cn` 下发 21 条 `grade:*` 文案；cron 的 `poll_moves` /
`fetch_list` 正常执行。

### 2026-09-01 — 发布 `f8f3582d`：galaxy 右栏 / 报告改版 + 撤人类倾向（非迁移，无 DDL）

> **这条是 2026-09-02 事后补的。** 当天发布完没有留条目，本文件在 `f8f3582d` 上
> 最后一条还停在 08-29。补的依据有两处，逐条标了出处:
> **[机]** = 事后在生产机上还查得到的状态（镜像/目录/备份文件的时间戳与 ID）；
> **[录]** = 当天那次会话自己的工具输出（本仓 transcript）。
> 没有出处的项一律写「无记录」，**不补写、不追认**。

发布内容：`release/ucloud-20260805` 合入 develop（`2b6b44c8`），合并提交 `f8f3582d`。
galaxy 十个棋盘页右栏统一 20px 内边距 + 宽度改由实测式子决定 + 字号切两档、
复盘五个分析 tab 改版、直播列表点开一盘棋的加载态、撤掉人类倾向。
`git diff 683b71ab..f8f3582d` 共 **50 个文件**，其中含 `katrain/cron/config.py`
（这就是 cron 镜像那次也重建的原因），无 models / 迁移文件 ⇒ **无 DDL**。

- 镜像 **[机][录]**：`WEB_IMAGE=sha256:79b94765a8fdf5a351f67141b4ee5523e3a67d24ba4b2bf0766f0c4eb091b291`
  （tag `katrain-web:f8f3582d`，`size_bytes=542720405`，建于 2026-09-01T21:07:46+08:00），
  `CRON_IMAGE=sha256:8d3f0735f98ce06018ede612328748fcc753a3953b30330614f6489b3e32144f`
  （tag `katrain-cron:f8f3582d`，68M，建于 21:10:30）。**两个都重建了**，因为改动落进了 `katrain/cron/`。
- release 目录 **[机]**：`/opt/katrain/releases/f8f3582d`，`git clone --depth 1` 于 2026-09-01 21:04:09。
- 回滚锚点 **[录]**：`katrain-web:683b71ab` / `katrain-cron:683b71ab` 未删除。
- env 副本 **[机][录]**：`/opt/katrain/backups/ucloud.env.20260901T211058.bak`。
  （这类副本的**文件名带备份时刻、mtime 带被备份文件自己的修改时刻**——`cp -p` 保原时间。
  所以这份的 mtime 是 08-31 14:50，指的是上一版 `683b71ab` 写进去的那一刻，不是备份时刻。
  拿 `ls` 的时间列当备份时间会读反一整代。）
- 预检 **[录]**：`available_bytes=22133936128`、`peak_bytes=13500000000`、`required_bytes=38500000000`，
  **2 条红且都是容量闸**（同历次）。
  当天**另做了一次变异**：把 `WEB_IMAGE` 指向一个不存在的镜像 ⇒ 多报一条
  `ERROR WEB_IMAGE is not available locally`、`checks=3` ——
  证明容量闸之外的分支**确实在跑**，不是被快速失败跳过了。
  （这一格 08-29 和 09-02 两次都没做到，是这次补记里唯一比它们强的一处。）
- `up -d`：**无 dry-run 记录**。事后看结果是对的——`katrain-web` 与 `katrain-cron` 两个重建，
  KataGo（`Up 30 hours`）与 postgres（`Up 5 weeks`）uptime 未断 **[录]**。
  但「结果没出事」不等于「事前知道会动谁」，这一步 09-02 那次补上了。

**⚠️ 一处偏离常规前置（如实记，不追认）：这次发布没有取数据库备份。**
`/opt/katrain/backups/` 里 `f8f3582d` 之前最近的一份是 `prod-20260831-1410.dump`（08-31 14:08，
属上一版 `683b71ab`），09-01 一份都没有 **[机]**；当天那次会话的发布表里也没有这一行 **[录]**。
本次改动确无 DDL，事后也没有出问题，但**「无 DDL」不是免掉备份的理由**——
备份是回滚锚点，不是迁移专用件。09-02 那次已按前置补回（含真恢复验证）。

**发布后验证 [录]：** 6 个容器全部起来（web/cron `health: starting` → 随后 healthy）；
`docker inspect` 确认 web/cron 跑的就是上面两个 ID；`/api/v1/health` 200；
公网 `https://modelstella.com/` 200；`current -> /opt/katrain/releases/f8f3582d`。
**发布前后同一组三探针**（这是当天做得好的一处，值得抄）：

| 探针 | 前 | 后 |
|---|---|---|
| bundle 含 `min-width:560px` | 无 | `rankUtils-Bq-lsBox.js` |
| `/api/translations` 的 `live:loading_match` | 缺失 | 正在加载棋局… |
| cron 环境变量 `HUMAN_SL_PROFILE` | `'rank_5d'` | `''` |

生产真浏览器实测（2000×1050）：右栏 762、标题左内距 20px、标题 26px、棋盘 978 未变 **[录]**。

### 2026-09-02 — 发布 `7a6069aa`：kiosk 屏 20 复盘五个分析 tab（非迁移，**无 DDL**）

发布内容：`release/ucloud-20260805` 合入 `origin/develop`（合并提交 `7a6069aa`，
develop 侧 `30071a5d`）。把 galaxy 的着手评价五个 tab（走势 / 妙手 / 失误 /
发挥水准 / AI吻合度）搬上 kiosk 屏 20，右栏两块折叠改成单开手风琴，
AI 推荐表与研究页收敛成同一个组件。

**先测试环境后生产**（Fan 2026-08-31 的裁定）：home-ubuntu / go.sailorvoyage.top
先发 `30071a5d` 并验过（web 重建 healthy、产物含 `ai-recommend-row` 与 `grade:tabs`、
`/kiosk/report/1` 200、公网 200），再上生产。

- 镜像（不可变 ID）：`WEB_IMAGE=sha256:1433d03c7b96faabcedc9b84b9ad046f2f195a3697cba37758bc538e3b1c72e8`
  （tag `katrain-web:7a6069aa`，`size_bytes=542725705`；上一版 542672203，同量级）。
  `build-web.sh` 的容器内容测试通过。
- **CRON_IMAGE 不动**，仍 `sha256:8d3f0735f98ce06018ede612328748fcc753a3953b30330614f6489b3e32144f`。
  08-29 那条记的是反面（改了 cron 却只换 WEB_IMAGE ⇒ cron 跑旧代码）；这次是正面，
  所以**要拿证据不是拿印象**：`git diff --name-only f8f3582d 7a6069aa` 共 24 个文件，
  **全部在 `katrain/web/ui/` 下**，`katrain/cron/` 与 `Dockerfile.cron` 各 0 处。
- 回滚锚点：web `sha256:79b94765a8fd…`（tag `katrain-web:f8f3582d`），
  `/opt/katrain/releases/f8f3582d` 未删除。
- `/etc/katrain/ucloud.env` 只改 `WEB_IMAGE` 一行（`diff` 2 行 = 一去一来）；
  改前副本 `/opt/katrain/backups/ucloud.env.20260902T175723.bak`，改后仍 root:root、mode 0600。
- 数据库备份 `/opt/katrain/backups/prod-20260902-1752.dump`（`pg_dump -Fc`，194 MB）。
  **已真恢复验证**：恢复进临时库 `katrain_restore_check`，`pg_restore` 退出码 0、
  **stderr 零行**，逐表比对 38 张表的 `count(*)`，**0 处不一致**
  （`report_task_moves` 2938、`user_games` 24）。验证库已 DROP。
  ⚠️ 首次写比对脚本时嵌套引号被 shell 吃掉，`pg_tables` 查询报错 ⇒ 表清单为空，
  而循环体一次都没进，脚本照样打印「不一致的表: 0」—— **什么都没量却报绿**。
  重写时加了 `[ -s /tmp/t.prod ] || exit 2` 这一格。
  （`pg_dump -U katrain` 会失败：这台的角色是 `katrain_user`，`postgres` 角色也不存在。）

**本次无 schema 变更** —— 24 个改动文件全是 `.tsx` / `.css` / `.json` / 测试，
`add_missing_columns` 这一趟是空跑。

**闸门结果与一次明示越闸：**

- `--structural`：**仅 2 条失败，且都是容量闸** —— `available_bytes=18748497920`、
  `required_bytes=38500000000`，以及「projected filesystem use ≥ 75%」（实际 82%）。
  与 2026-08-21 / 08-29 同形。错误文案写的是 “**migration** requires at least …”，
  是一次性迁移的峰值口径；本次非迁移，`peak_bytes=13500000000` < 可用 18.7G。
- `--structural` 的正向证据：**Compose preview 与 production profile 均渲染通过**、**GPU 可用**。
- 单跑 `--phase runtime` 想补 08-29 缺的那几项正向证据，**没成功**：容量闸在 runtime 相
  之前就快速失败。⇒ 那两项仍是手工核的：`stat -c "%U:%G %a"` 得 `root:root 600`；
  三个 `*_IMAGE` 全写成 `sha256:` ID 而非 tag。
- 属**明示越闸**，理由如上，回滚锚点齐备。

**`up -d` 前先 `--dry-run`**（2026-08-30 那条教训：`up -d` 会连带重建依赖链上的服务，
KataGo 一重建就是 15 分钟 TensorRT 预热、期间 `katrain-web` 卡在 `Created`）。
本次 dry-run 只列出 `katrain-web` 与 `minio-setup` 两个 Recreate ——
`minio-setup` 是一次性建桶容器（跑完 exit 0，幂等）。发布后 KataGo 两个容器的
`STATUS` 仍是 `Up 2 days` / `Up 3 days`，postgres `Up 5 weeks`，cron `Up 21 hours`
—— **没被动过**，这是事后的证据，不是 dry-run 的承诺。

**发布后验证：** 6 个 katrain-ucloud 容器全部 healthy；
`docker inspect` 确认 web 跑的就是 `sha256:1433d03c…`；
`/api/v1/health` 返回 `{"status":"ok","engines":{"local":"reachable","cloud":"unconfigured"}}`；
前端产物含 `ai-recommend-row` 与 `grade:tabs`；
公网 `https://modelstella.com/` 200、`/kiosk/report/1` 200；
`/api/translations?lang=cn` 下发 48 条不同的 `grade:*` 文案；
cron 的 `poll_moves` 仍在 3 秒周期正常执行。发布后根分区 82%。

**一处欠账（不是本次造成的，已还）：** 上一次发布 `f8f3582d`（galaxy 右栏/报告改版）
当时没有留 runbook 条目。**2026-09-02 已照实补回**，见上一节 —— 依据是生产机上还查得到的
状态与那次会话自己的工具输出，逐条标了 **[机]** / **[录]** 出处，取不到的写「无记录」。
补的过程里查出那次**没有取数据库备份**，也一并如实记在那一节里。
