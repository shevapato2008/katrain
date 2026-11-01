# 会员发布预检：实际 TEST / 新 PROD

核查时间：2026-11-02 02:35 Asia/Shanghai。本次仅远端只读核查；未部署、构建镜像、DDL、改 env、停服务、调用付费分析或读取/输出凭据值。数据库 URL 仅在容器进程内用于只读连接。未访问旧 `117.50.183.169`，未进入另一 ES worktree，未操作并发 ES 容器。

本文件是发布前置事实与后续执行边界，不是已发布回执。最终后端/UI 审核、已发布 develop SHA 和实际服务切换均由主任务完成。用户已授权 feature → develop → smartbox 父 main → TEST 后新 PROD 的顺序，不新增批准流程。

## 当前实际运行基线

| 项目 | TEST | 新 PROD |
| --- | --- | --- |
| SSH | `home-ubuntu`，hostname `ubuntu`，用户 fan | `ucloud-v100` = `ubuntu@117.50.177.254:22`，hostname `10-60-162-188`；Docker 用 `sudo -n` |
| Web | `katrain-web` | `katrain-ucloud-katrain-web-1` |
| Web full ID | `5e2d2c06d0390620cd2f1bd76e4c88fd3c8095eb453abc4db7136766d81d61f4` | `76722693c9cf2a25de5b68126987ea89a906595682b36eca0db68f3672514cd7` |
| Web image | `sha256:45345474b0cca6cce5a541f005d5ad27129a6684d938668ce30ef39788931050` | `sha256:9806b186286f271ccaf5f6bfc859da126b34f09b0e4014eee34c7ca400bed8a5` |
| Web tag | `katrain-kifu-es:f43b673d-test` | `katrain-kifu-es:f43b673d-prod` |
| Web build / OCI revision | `f43b673d71ba9bc7a65344dd5c587ff9f4c1436b` | 同 TEST |
| Web StartedAt / restart | `2026-10-31T20:09:03.199569912Z` / 0 | `2026-10-31T19:29:11.857573562Z` / 0 |
| Web user / health | `root`；无 container healthcheck | `10001:10001`；healthy |
| Web restart / limits | `no`；无 CPU/memory quota | `unless-stopped`；4 CPU、4 GiB memory、8 GiB MemorySwap |
| Web host ports | `8001`，HostIp 空 | `127.0.0.1:8001`、`10.8.0.3:8001` |
| Docker API | 1.55 | 1.54 |
| Cron | `katrain-cron`，ID `58a5475b70a6c905f558250be9ef37441a7ca4aa2b793dfdbd41624440253bc0` | `katrain-ucloud-katrain-cron-1`，ID `b265082475b807680ef55cab2eb2e619fbd08292b345e1e7f8a5bd6ab71b9702` |
| Cron image | `sha256:70b6c280d4f1b3c963a2886573e9e7c234dcc207d07ea9d38f4cba78f31c5b16` | `sha256:9b28e8be9b77deb63f99cac2b076aac9df584a521f9b00989d6cc2bc920adb79` |
| Cron build identity | env `unknown`，无 OCI revision，不能据此声称新包 | env `56f53fa4d29ee041faa39f00d5b27a12613ee0e5` |

两端 Web/Cron 当前都没有显式 `KATRAIN_ENVIRONMENT`、`MEMBERSHIP_MODE`、`PAYMENTS_MODE`、`BILLING_ENFORCED`、`FREE_WEEKLY_REPORTS`；都有非空显式 `KATRAIN_DATABASE_URL`。两端 Web 的 paid `CLOUD_KATAGO_URL` 都为空/未设，不能把既有非空 `LOCAL_KATAGO_URL` 当作 paid 路由已经配置。未输出这些 URL。

TEST host checkout 是 `/home/fan/Repositories/katrain` 的 develop，但不是 running identity。本次早期任务提供的 HEAD 为 `43d916099e2f9aa3ecd00902f438cbd179c78332`，fresh 核查已推进到 `6bb4e7bf795dd8ac38b25bd9f1e4214b8ecc993e`，Web 仍为 f43；存在并发推进，不能拿 checkout HEAD 代替容器包版本。tracked 只有无关 `.dockerignore` 改动，untracked 计数 6692；包括私有 `docker-compose.override.yml` 的既有文件全部保留。PROD `/home/ubuntu/katrain-transformer` 存在但没有 `.git`，不是可直接 git pull 的发布 checkout。

## 已核实的实际发布机制

当前 f43 的实际历史入口是：

- TEST：`/tmp/kifu-es-f43b/swap_home.py`，SHA256 `92dde8dc6a264ceda429c0e22ab8d9b485d800841803609d56e9c392b6a23250`。
- PROD：`/var/tmp/kifu-es-3ec/swap_release_f43b.py`，SHA256 `985c7a6f2efac7e18f69fe028c1a0c0c026327c461e6a45a031d1e51bc56cb92`。

二者通过本机 Docker socket，fresh inspect live Web，复制 `Config`、完整 `HostConfig` 与稳定 network endpoints，正常 stop → rename 原容器为 backup → create/start 新 Web。PROD f43 脚本固定 old image `e869041f…`；现场保留的 `katrain-ucloud-katrain-web-1-backup-add72afbd1e4` 正是该 image、旧 SHA `5435aa5e…`。TEST 保留 `katrain-web-backup-92d920e4ede2`，旧 SHA `07d1ddce…`。当前运行 f43 的 inspect 是最新版本事实；目录内没有本次 f43 的结构化 applied receipt，不能冒称已有完整发布回执。

**这些历史脚本不能直接重跑本次发布。** 它们硬编码旧 tag/SHA（PROD 还固定旧 image），无只读 preflight 入口，且错误处理会删除新失败容器。只读取脚本源码，未调用它们。已有较完整的受控骨架是 [web-only operator](releases/2026-10-27-kifu-search/operators/web-only.py) 及其 [说明](releases/2026-10-27-kifu-search/operators/README.md)：full ID/image CAS、私有证据、配置比较、保留其它容器。它也不能原样运行会员发布：TEST 仅允许 11/12 个 compose 文件、只允许 image/build SHA 变更，PROD 也只允许原 env 中 SHA 变化；本次要加入模式和独立 TEST DB 等明确 delta。

TEST Web 仍带 `com.docker.compose.project=katrain` 和 **20 文件历史链** labels，working_dir 是 `/mnt/disk1/fan/kifu-hourly-incremental-20261019`；最后两层为 `/mnt/disk1/fan/kp29-web-489-apply/release.override.private.json` 与 `/mnt/disk1/fan/kp29-web-07d-apply/release.override.private.json`。f43 已通过 native Engine swap，旧 labels 被复制保留，不能据此断言 compose 的 effective env 等于 live env。TEST Cron 的 ownership 才指向 `/home/fan/Repositories/katrain/docker-compose.yml` 加私有 override。PROD Web/Cron 没有 compose working_dir/config_files labels。**本地 compose 新增透传不会自动进入这些 native 容器**；不得用通用 `docker compose up -d --build` 覆盖实际现场。

最小后续入口是复用已存在 operator 的 fresh inspect/CAS/compare 逻辑，为这次已发布 immutable image 与下述 env 白名单做一次有限适配；TEST 与 PROD 均按实际 native Engine 配置保留。不要造新部署平台，也不要直接复用旧 migration `runtime_replay.py`。已另行在本机 `/tmp` 准备下节 helper，尚待主任务独立审核及实际只读 prepare；没有远端执行。

### 本次本地 helper（待审核，未部署）

文件：`/tmp/membership-native-release-20261102.py`；SHA256 `a26d7c83c1b302c5f042d5e4f5a1fe7426446ecac174f0ebeb12cc55c1ceaa39`。单文件、仅 Python 标准库；只接受两端明确的四个 Web/Cron 名称，绑定实际 hostname/daemon ID，不读取 stale compose 链，不 build/pull、不访问 SQL、不修改 DB URL 或 mock secret。未 commit 此 `/tmp` 工具。

`prepare` 仅 GET fresh Docker inspect/image/info，并向已存在的当前执行用户 mode0700 私有目录新建一个 mode0600 manifest；其中保存旧 inspect、新 create payload 和 hashes。stdout 只列 image/ID/SHA、变更字段名和 manifest byte SHA，不打印 env 值。允许的 env 只有 build SHA、明确环境/会员/支付/收费/Free/Max、paid engine URL，以及三个实际 queue/lease 配置；本次主服务强制 paused/disabled/enforced/free0/maxfalse。禁止 DB URL 与 mock event secret delta。

`apply` 必须显式提供 reviewed manifest byte SHA、fresh expected full old ID/image digest；每步针对完整 ID 核对配置和名称，保留 Config/完整 HostConfig、ordered env、mounts 与稳定 endpoints。仅 image、白名单 env、OCI revision 和唯一 operation ownership label 可变化；后者用于未知 create 响应时识别本次资产。正常停止采用 Engine `stop?t=-1`（[Docker 官方说明](https://docs.docker.com/reference/cli/docker/container/stop/#stop-container-with-timeout--t---timeout)明确不升级 SIGKILL），客户端等待有界；超时可能仍有 daemon stop pending，拒绝盲重试/强杀，保留现场并明确 forward-fix。

默认 `safeFailurePolicy=stop;oldBackupRetained`：candidate 失败后只在 full ID/name/operation ownership 仍匹配时正常停止并保留为 failed 名称，旧容器保留 stopped backup，**不启动不懂 v3 的 f43 旧镜像**。不删除任何容器/镜像，不清 activation、不改 legacy。只有操作者已证明旧镜像支持会员 activation/v3，且 prepare/apply 两次都显式 `--rollback-compatible`、manifest 绑定该事实时，才允许恢复兼容旧软件；本次首次财务发布不传此参数。外部并发变化或安全恢复不完整时拒绝进一步动作并保留 private receipt。

本机验证：`py_compile`、CLI help 通过；5 个小 fake inspect 用例验证配置/网络保留与危险 env 拒绝、stale ID/配置 CAS 拒绝且无 mutation、首次财务失败无旧镜像 start 且无 DELETE，以及小写强杀信号拒绝、Healthcheck.Test=['NONE'] 不等待 healthy；另一次完整 fake prepare 证明 Docker mutation=0、manifest mode0600、stdout 无 dummy secret，默认失败策略正确。这些不等于实际 Docker/runtime 已验收，实际只读 prepare 与独立审核由主任务在执行前完成。

在选定目标机完成文件传输/审核、候选 image 已构建、原服务已取得自然安全窗口后，可用下面的占位符命令。private env JSON 与 manifest/receipt 目录必须分别为执行用户拥有的 mode0600 / mode0700；PROD 由 root 拥有并用 `sudo -n python3`。示例不含凭据：

```sh
python3 /tmp/membership-native-release-20261102.py prepare \
  --container katrain-web \
  --image sha256:CANDIDATE_64_HEX --sha PUBLISHED_40_HEX \
  --env-json /var/tmp/membership-release-RELEASE/web-env.private.json \
  --manifest /var/tmp/membership-release-RELEASE/web-manifest.private.json

python3 /tmp/membership-native-release-20261102.py apply \
  --manifest /var/tmp/membership-release-RELEASE/web-manifest.private.json \
  --manifest-sha256 REVIEWED_MANIFEST_64_HEX \
  --expected-old-id FRESH_OLD_CONTAINER_64_HEX \
  --expected-old-image sha256:FRESH_OLD_IMAGE_64_HEX \
  --receipt /var/tmp/membership-release-RELEASE/web-apply.receipt.jsonl
```

PROD 对应 `--container katrain-ucloud-katrain-web-1`；Cron 分别为 `katrain-cron` / `katrain-ucloud-katrain-cron-1`，每个服务独立 prepare/manifest/CAS，不自动展开其它服务。无 healthcheck 的 TEST 与 Cron 仍需主任务做启动后真实 HTTP/任务检查；有 healthcheck 的 PROD 也仍需实际页面/业务验收。原 collector drain/单实例前置由执行者先建立，helper 不改调度行或伪造该前置。

Cron 找到的较近期受控换包证据是 TEST `/mnt/disk1/fan/kp29-cron-fd62f743-v7c/final.receipt.json`：status `cutover-verified`，SHA `fd62f743ccc95d5fffcc3048ebe71517450441a2`，当时新 ID `a59875bbc2950de8bedf25c3e4c87d38f6e8999e4a1543da70d3d5653be541f3`。它与当前 10-31 的 `58a5475b…` 不同。已知 release 目录 `/mnt/disk1/fan/kifu-prepared-20261028-a3ebeeb9` 顶层未发现 cron operator `.py`；本仓库 10-20 的 [deploy-cron-test.py](../../superpowers/tracks/kifu-hourly-incremental/operations/release_e23_20261020/deploy-cron-test.py) 固定旧 ID、旧 image、旧 pause 事实，仅作历史背景。没有找到可直接用于当前 Web/Cron 版本和会员模式的近期完成版 cron runner；不能重跑旧脚本或把旧 receipt 当当前状态。现有 10-27 prepared-search runbook 的自然 drain/单实例/配置 CAS 边界仍可沿用，无须扩建调度平台。

## 必须保留的运行配置

- 两端原 ordered env 的所有非本次 delta、启动 command/entrypoint/user/healthcheck、完整 HostConfig、网络/aliases、端口、restart、资源、labels/host pin。原 SSO、媒体、ES key、DB 凭据只在进程内复制，原值不进 stdout/Git。
- TEST Web：`/home/fan/Repositories/katrain/data/tutorial_assets` → `/app/data/tutorial_assets` rw；`/home/fan/deploy-es/certs/ca.crt` → `/etc/ssl/certs/kifu-es-ca.crt` ro；`katrain_default` 网络；`host.docker.internal:host-gateway`。TEST Cron 原 backups bind 和 engine/调度/预算也保留。
- PROD Web：named volume `katrain-ucloud_katrain-state-production` → `/home/katrain/.katrain` rw；host CA `/home/ubuntu/deploy-es/certs/ca.crt` → `/etc/ssl/certs/kifu-ca.crt` ro；`katrain-ucloud_app` 与 `katrain-ucloud_backend` 网络。
- `/etc/katrain/ucloud.env` 是私密运维配置，仅保留路径与现有 owner/mode，不 cat 或从新 compose 默认值重建。冻结 migration manifest `/var/lib/ucloud-migration-20261027/input/runtime-replay/runtime-manifest.private.json` mode0600，file-byte SHA256 仍为 `0d8c789f371da95c619d1e72dd956f7431a3a13145cb51d03168a3eb04e0e2b6`；保留，不修改、不重放。
- PostgreSQL、MinIO、两 KataGo、admin、其它业务服务及并发 ES 容器保持原 full ID/image/StartedAt/restart。仅在本功能确需的 Web/Cron 自然安全边界换包；不重启整个项目、不启动第二 collector、不 kill 在途任务。

本次观察 Web HostConfig canonical SHA256：TEST `0e4f8c6fc9bc8f86f843925310ca36313ed69df84a58d21064f63184dc2bcc47`；PROD `a3cdc75237002bcd6e69ef60c3820ffc405da940bddf7cedcaa3da70b0ba09c8`。这些是本次快照，执行时必须重新取 fresh 值，不将旧快照当作后来授权。

## TEST mock 的实际数据库前置

在 TEST `katrain-web` 内使用 `os.environ['KATRAIN_DATABASE_URL']`、psycopg2 与 `default_transaction_read_only=on`，statement timeout 5s / lock timeout 1s，只输出以下事实：

```json
{"database_name":"katrain_db","role_superuser":true,"marker_exists":false,"marker_test":false}
```

所以当前 TEST PG **未满足 mock 前置**。不能给该现有 superuser 库加 env 或用应用自建 marker，把它自称独立 TEST。启动 guard 也会拒绝缺 marker 的 mock；guard 在 startup DDL 前核对 explicit URL 数据库名与实际 `current_database()`，每次 mock 写入前再次核对。

最小准备方案是由 bootstrap 管理身份建立专用 TEST database、专用非 superuser login app role 和独立 NOLOGIN control owner；或复用已有且确有独立身份的 TEST DB。专用 app role 不具有 SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS，也不是 control owner 的成员。业务 schema 只给本库启动迁移所需的最小权限；control schema 则只能 USAGE/SELECT，不能 CREATE、INSERT、UPDATE、DELETE、TRUNCATE 或通过所有权改表。不要为此改生产数据库的全局 PUBLIC grants。凭据用既有私密渠道配置，不写进命令记录。

由独立 bootstrap owner 在**新专用 TEST DB** 中执行的 control schema 形状如下（仅建议，未执行；角色名需由执行者绑定实际创建结果）：

```sql
CREATE SCHEMA billing_test_identity AUTHORIZATION membership_test_identity_owner;
SET ROLE membership_test_identity_owner;
CREATE TABLE billing_test_identity.environment (
    database_name text PRIMARY KEY,
    environment text NOT NULL CHECK (environment = 'TEST')
);
INSERT INTO billing_test_identity.environment VALUES (current_database(), 'TEST');
REVOKE ALL ON SCHEMA billing_test_identity FROM PUBLIC;
REVOKE ALL ON billing_test_identity.environment FROM PUBLIC;
GRANT USAGE ON SCHEMA billing_test_identity TO membership_test_app;
GRANT SELECT ON billing_test_identity.environment TO membership_test_app;
RESET ROLE;
```

应用不执行上述 provisioning。验收前同一只读探针必须证明：实际 DB 是选定专用库、app 非 superuser、marker 精确匹配该库且为 TEST、app 对 control schema 无 CREATE、对 marker 无 DML/DDL 权限，并核对本库 owner/角色成员关系。不能拿本地 `membership_validation*` mock 测试成功替代远端事实。

主 TEST 保留现有数据与 ES 配置，软件先采用 paused/disabled；受控 mock 验收使用专用 DB/role，必要时以同版应用在临时独立端口运行。该临时进程只服务本旅程，不启动第二 collector，不复制生产凭据或把 mock 写进现有 `katrain_db`。这是有限验收运行，不是新部署平台。当前并发 ES 工作尚在进行，本预检没有切其 Web/Cron/DB 或改变现有任务目标。

## 支付、Free 与本次运行模式

源码只实现隔离 mock provider；`real_adapter=false`。未验证商户真实回调验签、真实退款、真实试付，也未查询任何商户凭据内容。Free 的 `get_trusted_free_eligibility()` 固定返回 False；尚无可信手机号事实提供者与本站注册限流落地。`billing_catalog.PLANS.max.sellable=false`，不能宣称 Max 已可售。

因此软件可以按下列诚实配置发到 PROD，但不能称为正式收款上线：

```text
KATRAIN_ENVIRONMENT=production
MEMBERSHIP_MODE=paused
BILLING_ENFORCED=true
PAYMENTS_MODE=disabled
FREE_WEEKLY_REPORTS=0
MEMBERSHIP_MAX_SALE_ENABLED=false
```

PROD 不需要建立 TEST control marker，且 production+mock 必须拒绝。主 TEST 同样使用 paused/disabled 保留既有数据库（环境标识可为 test）；专用 TEST mock 实例仅在上节独立数据库/role 成立后使用 `KATRAIN_ENVIRONMENT=test`、`MEMBERSHIP_MODE=enabled`、`BILLING_ENFORCED=true`、`PAYMENTS_MODE=mock`、`FREE_WEEKLY_REPORTS=0`、Max false，并通过私密渠道提供 mock event secret 与显式专用 DB URL。paid 引擎实际 URL 也必须按该主机原网络验证后显式透传；当前未配置，不能宣称 paid 实际调用已验收。

暂停后已有 v3 reserved/running operation 仍按原版本结算/退还；不能切回 legacy 规避，也不能用只更新 Web、Cron 仍旧包的状态宣称报告旅程可部署。当前 Cron 的真实身份如上，需发布同版 report worker 并验证其独立 ORM/严格 engine 合同。会员激活会留下持久事实，旧 pre-feature backup 不是有 v3 任务后的通用安全回滚方案；优先用当前 v3 capable 软件的 paused/disabled 模式与保留账务事实恢复。

## 准确的后续执行顺序与检查命令

1. 完成当前功能 review 与必要验证后，feature fetch/merge 最新 develop、解决冲突、验证、commit/push；merge/push develop；再将 `smartbox-software/vendor/katrain` 指向该已发布 develop，commit/push 父 main。保留两个仓库所有无关改动，记录三个 published SHA。
2. 用已发布 SHA 的完整软件及对应前端产物构建候选 immutable image，保留 TEST root / PROD 10001:10001 的实际运行 user；不从 home 正在并发变动的 checkout 盲目打包。构建本次 Web 与 Cron 必需的包，不重建 KataGo。候选 metadata 与实际包/前端必须一致。
3. 主 TEST 保留既有 DB/ES，以 paused/disabled 软件配置发布；另补齐上节专用 mock DB/role。沿用现有 Engine operator 骨架加入本次明确 env delta 与 fresh full ID/image CAS。preflight 只在私有 mode0700/0600 证据目录保存原 inspect/create payload；不在 stdout 输出原 env。比较除 image、build identity、明确模式/paid 路由外，其它主服务配置一致；专用 mock 实例的专用 DB/secret/独立端口明确另记。当前不具备安全窗口则保持服务原态，不能跳过 TEST mock 前置。
4. TEST 先更换本功能必要 Web/Cron，正常 drain、单实例、原调度/预算不变；主 TEST 验证 paused 真实页面，专用 mock 实例验证登录的 Galaxy/Kiosk 会员/充值/报告旅程、TEST 明显标识、mock 支付核对、报告提交/完整交付/结算。仅做当前旅程所需有限数据与引擎请求，不压测、不碰无关 kifu 数据。
5. TEST 通过后，新 PROD 仅以 paused/disabled 模式发布同版必要服务；无商户/P3/paid 实际前置时保留上述模式。fresh 记录实际 ID/image/SHA、健康及代表性真实 Galaxy/Kiosk 页面，不用仅 shell env 或 HTTP 200 代替 UI 行为验证。

以下命令可在执行前重取非敏感 identity；它们不打印 env 或 credential 文件：

```sh
ssh -G ucloud-v100 | rg '^(hostname|user|port) '
ssh home-ubuntu 'docker inspect katrain-web --format "{{.Id}} {{.Image}} {{.State.Status}} {{.State.StartedAt}} {{.RestartCount}}"'
ssh ucloud-v100 'sudo -n docker inspect katrain-ucloud-katrain-web-1 --format "{{.Id}} {{.Image}} {{.State.Status}} {{.State.Health.Status}} {{.State.StartedAt}} {{.RestartCount}}"'
ssh home-ubuntu 'curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8001/api/v1/health'
ssh ucloud-v100 'curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8001/api/v1/health'
```

本地 helper 经独立审核与实际只读 prepare 后，才按上述 immutable image、published SHA、fresh expected identity 和私有 manifest 进入 apply。本预检没有运行 helper 的远端 prepare/apply，也没有运行已知硬编码旧目标的历史 swap 脚本。

## 当前具体阻塞

- TEST 实际 `katrain_db` + superuser + 无 TEST marker，不能直接开启 mock；专用隔离数据库/role 尚未 provision。这阻塞 mock 验收，不阻塞主 TEST paused/disabled 软件换版。
- 本地最小 native helper 已准备，但独立审核与真实只读 prepare 尚未完成；旧通用 compose 路径不适用，不扩大部署平台。
- 正在收尾的产品审核/发布 SHA、必要 Web/Cron 同版产物、远端真实旅程尚未完成，本文件不将它们标为通过。
- 正式商户、可信 Free 身份/注册限流与 Max 容量前置未完成；PROD 只能诚实 paused/disabled 软件发布，不能称正式收款/Free/Max 上线。

本次只新增此预检文档；没有写远端文件、改配置或改变任何服务状态。
