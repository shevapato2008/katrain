# UCloud migration: TEST publisher and RK client dependencies

只读审计，2026-10-27 CST。未修改代码、配置、数据库、锁、调度、DNS、设备模式；未运行 receiver、采集、翻译或 job；未导航 RK；未进入文件系统 `data/kifu-album/`。以下为实时配置和运行态取证，切换步骤只是建议，没有执行。

**最先需要处理的实际依赖：TEST 发布仍直连旧公网，与 Mac alias 无关。**

| 环节 | 实际取证结果 | 切换影响 |
|---|---|---|
| Mac `ucloud-v100-old` | `ubuntu@117.50.183.169:22` | 旧管理目标，网关复用连接可达；Mac 直连两次超时 |
| Mac `ucloud-v100` | `ubuntu@117.50.177.254:22` | 仅 Mac 管理别名已换新；本次直连超时，未证明新 receiver 存在 |
| Mac `home-ubuntu` | `fan@127.0.0.1:2222`，ProxyJump `alicloud-ecs-gateway` | 测试机管理入口；不是发布时 receiver 的入口 |
| TEST producer | `home-ubuntu` 的 `katrain-cron`；`CRON_KIFU_INGEST_ENABLED=true`，interval `3600` | 保留为唯一小时 producer，不在新机启用第二套 |
| TEST 实际 SSH target | `CRON_KIFU_INGEST_SSH_HOST=kifu-receiver@117.50.183.169`；cron 内 `ssh -G` 确认为旧 IP、user `kifu-receiver`、port `22`、无 proxyjump | 显式旧公网依赖，DNS/Mac alias 切换都不会更新 |
| TEST PROD 验证 URL | `CRON_KIFU_INGEST_PROD_API_URL=https://modelstella.com` | 跟随域名 DNS；与 SSH 发布通道相互独立 |
| TEST 本机 API / DB | `http://host.docker.internal:8001`；`KATRAIN_DATABASE_URL` 非秘密部分为 `katrain_user@host.docker.internal:5432/katrain_db` | 保留现有 TEST DB 与本机发布链 |
| 持久 stage | `/mnt/disk1/fan/kifu-hourly-incremental-20261019/ingest-stage` → `/app/data/kifu_ingest`，RW | 不搬空、不重建、不更改旧包/receipt/`prod_synced` |
| 发布配置来源 | `/mnt/disk1/fan/kifu-hourly-incremental-20261019/cron-kifu.override.yml:14` PROD URL、`:15` SSH target；当前 Docker compose config_files 仍包括该文件和后续镜像 override | 最终受控切换要改 TEST 的持久 override 并核对真实容器 env；不是只改 Mac |
| 专用私钥 | TEST `/home/fan/.local/share/kifu-hourly-incremental/ssh/id_ed25519` → `/run/secrets/kifu_ingest_key:ro` | 保持在 TEST；新 receiver 只需要对应公钥 |
| 主机信任文件 | TEST `/home/fan/.local/share/kifu-hourly-incremental/ssh/known_hosts` → `/run/secrets/kifu_ingest_known_hosts:ro`；当前仅旧 IP 主机条目 | 切换必须加入从可信管理会话取得的新主机公钥，保留旧条目用于回滚；不得关闭严格校验 |

TEST 运行镜像为 `katrain-rank-release:kifu-ranks-e9b4d3ecce03-cron`。实测预算为 LLM `true`、每日 `MAX_TOKENS=100000`、`MAX_GAMES=100`、`MAX_NEW_NAMES=20`。运行版本代码的轮次总预算默认 `3300s`、source `<=600s`、recovery `<=300s`；这些预算和 stage/writer 机制不属于端点迁移改动。本次不触碰其状态，不触发额外轮次。

**PROD 原生 receiver 的真实执行链**

```text
TEST katrain-cron
  ssh BatchMode=yes StrictHostKeyChecking=yes
      UserKnownHostsFile=/run/secrets/kifu_ingest_known_hosts
      -i /run/secrets/kifu_ingest_key
      kifu-receiver@117.50.183.169 kifu-incremental-receive
  -> /home/kifu-receiver/.ssh/authorized_keys
     restrict,command="sudo -n /usr/local/sbin/kifu-incremental-receive-root"
  -> /etc/sudoers.d/kifu-incremental-receiver
     kifu-receiver ALL=(root) NOPASSWD: /usr/local/sbin/kifu-incremental-receive-root ""
  -> root wrapper /usr/local/sbin/kifu-incremental-receive-root
  -> docker exec -i katrain-ucloud-katrain-web-1 /bin/sh -c
     'KIFU_INGEST_DATABASE_URL="$KATRAIN_DATABASE_URL" exec python3 /app/scripts/kifu_incremental.py receive'
  -> container's KATRAIN_DATABASE_URL
     user katrain_user / host postgres / port 5432 / DB katrain_prod_20260725
```

wrapper 为 `0755`，SHA-256 `6970924370b31ee4776473283e0608295060568cb3a0e0e602a677ac81953a0c`；authorized_keys 为 `0600`。公钥 fingerprint 为 `SHA256:fR0z2USlsVSX6QGXNPNwu+BI3l13xLzNV4WoSWMlaGY`。`kifu-receiver` 的 shell 为 `/bin/sh`。真正的会话限制来自公钥的 `restrict` 和固定 sudoers 无参数规则；sshd 全局本身 `ForceCommand none`、`AllowTcpForwarding yes`、`PermitTTY yes`、`PasswordAuthentication no`。新机不得仅创建同名用户并授予常规 Docker/root shell 权限。

旧 Web 运行镜像为 `katrain-rank-release:kifu-ranks-e9b4d3ecce03-web`，compose 工作目录 `/home/ubuntu/kifu-hourly-incremental-20261019`。配置链以 `web-base.private.json` 开始并包含发布 overlay；未打印其中私有值。新 receiver 必须绑定新实例上确认过的实际 Web 容器/DB，不得因默认库名 `katrain_db` 而写错库。

旧 SSH 主机公钥：ED25519 `SHA256:WAumc5GpcL4qnXO+MiXdtjxKUtdi9SFzp+9x3B+/IKI`；ECDSA `SHA256:+H40s2FzGDMVfzT7JjnD82UZRoNjlJLCEsc8rGESLok`；RSA `SHA256:Cbje60ykRY0BsmGDaCaSYdT9vN/wN+g7eTJoXkNBAvQ`。以上来自已认证的旧机管理通道。TEST known_hosts 条目的 fingerprint 相等性和新机 fingerprint 尚未在本子审计完成验证，不能以 `ssh-keyscan` 网络结果单独代替可信核对。

**RK3562：实际运行与持久依赖**

| 消费者 | 配置/代码来源 | 观测值与迁移结论 |
|---|---|---|
| KaTrain remote API | 初次 `/proc/<MainPID>/environ`；`/etc/systemd/system/smartbox-katrain.service.d/override.conf:3`；`/etc/smartbox/identity.env` | `KATRAIN_REMOTE_URL=https://modelstella.com`，随 DNS；不应改成新公网裸 IP |
| 身份账号权威 | setup-wizard 现役 env；`/etc/smartbox/identity.env`；`setup-wizard/app/config.py:46-47` | `BOX_IDENTITY_REMOTE_URL=https://modelstella.com`；login/register/me/refresh 都由 `services/identity.py` 派生 |
| 中央 lobby | setup-wizard env；`/etc/smartbox/cloud-endpoints.env` | `SMARTBOX_LOBBY_ORIGIN=https://lobby.sailorvoyage.top`，是独立域名，不因本次 modelstella 迁移自动改写 |
| ranked | 同上 | `SMARTBOX_RANKED_ORIGIN=https://ranked.sailorvoyage.top`，同样单独保持 |
| RK Chromium | 运行进程参数 | `http://127.0.0.1:8080/launcher`；本次没有导航、模式切换或 renderer 操作 |
| 本地 DB / engine | 初次 KaTrain env | `sqlite:////mnt/data/weiqi/weiqi-web.db`；engine 配置 `http://127.0.0.1:8000`，不迁到公网 |
| strict Box SSO | `smartbox-katrain.service:15-16` | `KATRAIN_BOX_SSO=1`，本地 bridge key 文件路径存在；保留 RK 本地身份和桥接材料 |
| WebSocket | `katrain/web/core/pvp_box_bridge.py:201-211` | 由 `remote.base_url` 派生 `wss://modelstella.com/...`，Origin 同域，Bearer 仅后端 header；浏览器本地 WS 仍在本地同源，DNS切换后新连接跟随域名，旧长连接不会被DNS自动迁移 |
| 系统代理 | `/etc/environment`、systemd manager env、现役进程 env、Chromium flags、gsettings | 未见 proxy env/Chromium proxy flag；`org.gnome.system.proxy mode='none'`；两类 HTTP client 代码均 `trust_env=False` |
| resolver | `/etc/resolv.conf`、`/etc/hosts` | DNS 为 `223.5.5.5/223.6.6.6`；未见 modelstella hosts 覆盖；实测解析 `117.50.183.169`，初次存在旧公网443长连接 |
| settings / siteURL | `/var/lib/smartbox/settings.json`、运行配置和源代码有界检索 | settings 只有 volume/brightness/language；未找到活跃 `siteURL/siteUrl/site_url` 配置消费者；没有可据此擅改的新字段 |
| OTA | `/etc/rauc`、`/etc/swupdate`、`/etc/mender`、smartbox unit/bin 名称及相关源代码 | 未找到在用 OTA endpoint/unit；这只是已检查范围内的阴性结论，不等于全设备/未来版本不存在 OTA |

设备 SSH 为 `root@192.168.0.104:22`、alias `rk3562-local`、专用 `~/.ssh/id_ed25519`。SSH alias 现有 `StrictHostKeyChecking=false` 属管理链现状；与产品 HTTPS/TLS、TEST receiver 的严格 host pin 分开，不据此改动任何配置。

RK 采样期间发生独立状态变化：初次 KaTrain PID `906542` 正常运行，随后 `smartbox-katrain.service` 在 **2026-10-27 00:45:47 CST** 变为 inactive/dead，`ExecMainStatus=0`、`NRestarts=0`；setup-wizard PID `904570` 与 kiosk PID `2014` 仍 active。原因未调查，本子任务没有执行 stop/start/restart，且没有自动恢复设备模式。当前 KaTrain 停止不能写成迁移验收通过。

RK 实机代码扫描覆盖 setup-wizard/app、provisioning、firmware、scripts、KaTrain web/core/server/ui/src 共 **626** 个有界源文件；排除了 data、kifu-album、node_modules、git、静态构建和测试。旧公网 `117.50.183.169` 与 VPN `10.8.0.3` 的代码硬编码均 **0**。`modelstella.com` 的 13 处包括 config 默认值、provisioning 默认写入、提示文字、注释和 ICP 展示；实际网络消费者由上表 env 派生。阴性结论不覆盖未扫描的其他应用、浏览器持久化内容或未启用配置。

**外层 gateway / WireGuard / 统一 admin（追加实时取证）**

网关管理 alias `alicloud-ecs-gateway` 实际为 `root@8.130.171.106:22`，本机专用管理 key 路径 `~/.ssh/sailorvoyage-ecs-gateway.pem`。直连曾间歇超时；复用旧机已建立管理 master，以 SSH `-W` 通道到同一 gateway 管理端点完成只读取证，没有修改代理/路由。Nginx active；Caddy inactive。核对了 Nginx master 的实际命令（默认 `/usr/sbin/nginx`，无自定义 `-c`），`nginx -T` 成功共12个有效配置文件。

| 外层真实消费者 | 路由/状态 | 迁移边界 |
|---|---|---|
| api-go.sailorvoyage.top `/api/v1/kifu/` | `/etc/nginx/sites-enabled/api-go.sailorvoyage.top:8` → `http://10.8.0.3:8013` | 真实旧VPN消费者，须纳入新机8013验收；不是主Web8001 |
| api-go其余路径 | → `10.8.0.2:8000` | 仍属TEST，不改 |
| go.sailorvoyage.top | `/etc/nginx/conf.d/katrain-upstream.conf:20` → `10.8.0.2:8001`；`/media/`→`10.8.0.2:9000/tutorial-assets/` | 仍属TEST，不联动改 |
| lobby/ranked.sailorvoyage.top | → `10.8.0.2:8090`，各自限制的路由白名单 | 与此次PROD搬迁分开保持 |
| v100-preview.sailorvoyage.top | 系统解析失败；`dig` 明确 **NXDOMAIN**；不在有效 Nginx includes | 现有旧基线已失效，不能复制URL后宣称媒体可用 |
| preview历史配置 | `/etc/nginx/sites-available/v100-preview.sailorvoyage.top` 未启用；`/media/`→`10.8.0.3:9000/tutorial-assets/`，其余→`10.8.0.3:8001` | 仅为历史配置；本次不启用、不加DNS |
| gateway PROD admin隧道 | `smartbox-admin-forward@prod.service` active；`127.0.0.1:18011` → SSH `ubuntu@10.8.0.3:22` → 目标`127.0.0.1:8010` | 真实活动依赖；经该隧道 GET `/api/admin/health` 为 **200** |
| gateway TEST admin隧道 | 独立 `smartbox-admin-forward@test.service` active；`127.0.0.1:18012` → SSH `fan@10.8.0.2:22` → 目标`127.0.0.1:8012` | 保持TEST，不替换成PROD |

PROD admin持久来源 `/etc/smartbox-admin/ssh/prod.env` 与 `/etc/systemd/system/smartbox-admin-forward@.service`。有效SSH参数（已独立`ssh -G -F /dev/null`核对）：

```text
bind source 10.8.0.1; user ubuntu; hostname 10.8.0.3; port 22
IdentityFile /etc/smartbox-admin/ssh/prod_ed25519
IdentitiesOnly yes; StrictHostKeyChecking yes
UserKnownHostsFile /etc/smartbox-admin/ssh/known_hosts
GlobalKnownHostsFile /dev/null
HostKeyAlias unset; 使用目标主机名10.8.0.3查pin
ExitOnForwardFailure yes; GatewayPorts no
-L 127.0.0.1:18011:127.0.0.1:8010
```

该隧道客户端公钥 `/etc/smartbox-admin/ssh/prod_ed25519.pub` fingerprint：`SHA256:+k7/XSoYEnpIS5VRyrAL/eptSyRFFpSo78D5zWgssZE`。专用 known_hosts 为0640，当前10.8.0.3 pin为旧ED25519 `SHA256:WAumc5GpcL4qnXO+MiXdtjxKUtdi9SFzp+9x3B+/IKI`，另有TEST10.8.0.2条目。**新机接管10.8.0.3但换了host key时，该隧道仍会严格拒绝；必须只把此旧pin安全替换为经控制台/可信管理链验证的新host公钥，保留TEST条目，不关闭校验。**

旧 `/home/ubuntu/.ssh/authorized_keys` 中与上述 gateway PROD 公钥 fingerprint **唯一匹配**的一整行已只保存到指定私有目录，未复制其他授权：

`/Users/fan/.local/share/ucloud-migration/2026-10-26/client-dependencies/old-ubuntu-authorized-key-gateway-prod.line`

该文件0600，SHA-256 `b25a6c059d68bb62a99db618bca22bd3b358eed5f234959ef04132faa8085ccc`；完整公钥blob不出现在本脱敏报告。原restrictions为：`restrict,port-forwarding,from="10.8.0.1",permitopen="127.0.0.1:8010",permitlisten="127.0.0.1:65535",command="/bin/false"`。后续应将**这条完整原授权**精确追加到新ubuntu，保留新机已有Mac管理公钥；不要复制旧authorized_keys整文件，不搬gateway私钥。未实际追加。

内网 admin HTTPS 外层仅发现准备配置 `/etc/smartbox-admin/nginx.conf`：`admin.internal.modelstella.com`/`admin-test.internal.modelstella.com` 在10.8.0.254:443分别proxy18011/18012，allow10.8.0.4/denyall。**该文件未被现役默认Nginx加载，TLS目录为空，renew timer disabled；不能宣称该外层HTTPS健康。** `smartbox-admin-dns.service` 的 dnsmasq活跃，`/etc/smartbox-admin/dnsmasq.conf` 为两个内网域名返回10.8.0.254。`SB_ADMIN_INPUT`有效规则仅允许来自wg0的10.8.0.4到10.8.0.254的DNS/443，再drop其余到该地址流量，保留此隔离边界。

gateway WireGuard持久文件 `/etc/wireguard/wg0.conf`：interface `10.8.0.1/24,10.8.0.254/32`，UDP51820；旧PROD peer公钥 `kDnaM1I1OxDdk2m82Gl6mogxU22Ci32Gu0kGGm6B6nk=` 对应 `AllowedIPs=10.8.0.3/32`、keepalive25，持久文件**没有Endpoint**。运行态该peer endpoint=`117.50.183.169:36353`，handshake **2026-10-27 00:53:21 CST**。旧机down、新机up并继承经授权的peer身份后，server可动态学习177的新公网端点；若更换peer身份，应受控替换该peer公钥而非创建同AllowedIPs并行peer。私钥仅记录key名`PrivateKey`存在和来源，未读取输出或保存私钥值。

gateway已检查的现役公网证书renewal为webroot/nginx authenticator，无DNS-provider凭据路径；`/etc/smartbox-admin/acme-state/account.conf`只有`CERT_HOME`/`UPGRADE_HASH`/`DEFAULT_ACME_SERVER`存在，certs目录为空，未发现其中DNS-provider token/key项。此结论只覆盖检查过的配置，不代表云账号没有DNS凭据；未输出任何token。

**旧PROD教程媒体真实基线（只读、单条）**

旧Web实际 `KATRAIN_STORAGE_BACKEND=s3`、`KATRAIN_S3_ENDPOINT_URL=http://minio:9000`、bucket=`tutorial-assets`、`KATRAIN_S3_PUBLIC_BASE_URL=https://v100-preview.sailorvoyage.top/media`、presigned=`false`。因此该public URL是当前活动消费，不是local backend下的无效遗留env。

在`BEGIN TRANSACTION READ ONLY`且`default_transaction_read_only=on`的有限SQL中，只取`tutorial_figures`按ID第一条非空公开图片路径（figure1），随后ROLLBACK。对现役公开API `/api/v1/tutorials/assets/tutorial_assets/曹薰铉布局技巧-上册-曹薰铉-1997/pages/page_011.png` 做 `GET Range: bytes=0-1023`：**302**到preview/media下同路径；对Location做HEAD：**DNS失败 `[Errno -2] Name or service not known`**，总共读取素材0字节。没有检查私有棋局、没有扫描对象桶、没有修改任何媒体。

迁移验收必须把“媒体重定向仍如旧配置”与“素材真实可下载”分开记录。前者可用于证明没有引入新差异，后者当前旧基线本身失败；不能把既有媒体DNS故障归因于新迁移，也不能据此宣称新媒体已通过。修复其DNS/路由或改public URL属于后续另行授权的具体变更，本审计没有执行。

**认证、TLS、网络与秘密边界**

- `modelstella.com` 旧 Nginx 从 `/etc/nginx/sites-enabled/modelstella.com` 反代到 `127.0.0.1:8001`，保留 Host/X-Forwarded-* 与 WS Upgrade/Connection，读超时3600秒。证书来自 `/etc/letsencrypt/live/modelstella.com/fullchain.pem`，SAN 为 modelstella.com/www.modelstella.com，有效至 **2027-01-02 11:35:28 GMT**。保持域名/SNI/完整证书链；裸 IP 作为显式 SSH target 本身并不不安全，HTTPS 用户端则仍须证书名称匹配。
- 旧 Docker：PostgreSQL无 published ports；Web8001仅127.0.0.1/10.8.0.3；KataGo8000和8002仅127.0.0.1/10.8.0.3；MinIO9000仅10.8.0.3，console9001仅127.0.0.1。不为迁移开放DB/GPU公网。旧机 ufw 不存在，iptables/ip6tables INPUT 默认ACCEPT；不能把主机防火墙当现有强限制，须核对云安全组并保持私网绑定。
- `10.8.0.3` 是旧机 Docker bind 的真实消费者，和 TEST 发布/上述 RK 调用不同。旧、新同时上线同一 VPN IP 会冲突；只有受控 VPN 切换时才把该地址交给新机。新私网10.60.162.188与旧10.60.219.118也不可混同VPN地址。
- 旧 Web 实际存在 `KATRAIN_SECRET_KEY`、`KATRAIN_S3_ACCESS_KEY`、`KATRAIN_S3_SECRET_KEY`（来源 Docker Config.Env，仅记录存在性）。保留生产身份签名材料与对应生产身份数据契约，避免新实例自行生成不同签名材料造成现有账号/令牌失效。没有读取或输出真实值。
- RK `/etc/smartbox/identity.env`、`cloud-endpoints.env`、`device.json`、各 bridge key 文件均0600；device_secret存在。box-sso/lobby-sso/rated-chess/xiangqi-ranked bridge key及gomoku secret文件存在，仅核对路径/权限，不读取值。RK身份持久目录为 `/var/lib/smartbox/identity`，由工厂 device secret 派生密钥；不解密、不复制到新云。

**最小受控切换顺序（本次未执行）**

1. 保留TEST唯一producer及其持久stage/预算/旧receipt。先确认旧receiver没有仍在完成的writer；不得用杀SSH、抢锁、清stage或更改`prod_synced`解决切换。
2. 在新机准备真实Web/正确生产DB、固定receiver wrapper、相同受限client公钥、`restrict,command=...`选项和无参数sudoers。新机只复制receiver公钥信任，不复制TEST私钥；不得借机启动第二个producer。
3. 从可信的新机管理会话取得host公钥，写入TEST专用known_hosts的新IP条目并独立核对fingerprint。保留旧IP条目。准备仅含SSH target变化的TEST持久override；key/stage/budget/API域名保持。先完成可审查变更，再在受控窗口实际切换，不临时运行receiver试写。
4. 单独完成VPN旧新互斥交接，再核对新机私网绑定与网关消费者（尤其api-go的10.8.0.3:8013）；给新ubuntu精确追加上文保存的受限gateway公钥授权，受控更新gateway专用known_hosts中10.8.0.3的host pin，并确认PROD admin隧道健康。DNS切换前验证新站点SNI证书、健康及WS反代配置。RK现有modelstella域名/SSO配置无需替换，lobby/ranked独立域名不得联动乱改。
5. 将TEST目标受控改为`kifu-receiver@117.50.177.254`并核对真实容器env；将域名解析受控指向新实例。确保SSH发布目标与域名验证目标是同一生产数据快照/后续同一权威，避免一边旧库发布一边新库验收。之后等待既有小时轮次，观察原生receipt与真实验证状态，不手动job。

**回滚条件与限制**

- 新host公钥不匹配、receiver限制不完整、容器/DBtarget不符、TLS/WS错误、身份拒绝、私网bind丢失或出现重复writer/producer时，不切换或停止继续推进；保持准确未完成状态。
- 新库尚无新增权威写入时，可将DNS与TEST SSH target作为同一窗口回退旧实例，并维持VPN互斥，继续使用原stage/原receipt。
- 新库已有新增写入后，不可直接把DNS指回旧快照；先隔离写入、核对原生receipt和数据差异，按确定的数据一致性方案回迁。不得改旧包、强置prod_synced或开启第二writer来掩盖差异。

本报告未作新receiver可用性、云安全组完整性、GPU能力、媒体恢复或RK当前页面验收结论；这些需要对应迁移执行/验收证据。脱敏结构化记录保存在指定私有目录，未保存秘密原值。
