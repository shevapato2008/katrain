**UCloud DNS 切换后最终独立运营审查 — 2026-10-27**

正式独立实测窗口：UTC 03:00:37–03:17:58（上海 11:00:37–11:17:58）。此前 02:48 仅阅读材料，未提前作通过判断。审查者仅执行只读 SSH、有限运行/配置/日志查询、公开 GET、匿名 WebSocket 握手及四个旧 PG 的只读活动计数；未实施生产修改，未调用采集、导入、模型、native 重放或用户/对局创建。生产修复由控制者执行。本报告仅写在 Mac。

**最终结论：在本次已盘点的迁移范围内，`can_retire_old=true`。当前未解决 must-fix 为 0。旧机已不再承担本轮验证的生产入口、续期、VPN、接收或 writer 依赖；旧资源仍保留，实际删除由用户另行操作。**

本轮发现过一个真实必修项：两个 webroot 证书成功续签后缺少 nginx 重载路径。该项经最小修复与实际 Certbot→hook→nginx 验证后关闭；不能将本轮写成“从未发现问题”。此结论不代表 Root Mac 新建公网连接已恢复，也不代表所有互联网客户端和业务旅程均已验证。

**唯一必修项及关闭证据**

初次现态中，`pitch-api-staging.modelstella.com` 与 `smartbox-platform` 使用 webroot authenticator，无 installer；三组 renewal、全局 cli.ini 和 hook 目录均无部署/后置钩子，canonical certbot.service 亦无 ExecStartPost。nginx 使用静态 fullchain 路径。唯一 nginx installer 属于 `modelstella.com`，其证书 2027-01-02 到期，另两组分别 01-03 和 01-17 到期，不能依赖前一组较早续期时的 reload 自动加载后来签发的两组证书。

现装 Certbot 2.9.0 的 `_internal/main.py` 1555 附近只在存在 installer 且非 dry-run 时调用 restart；`hooks.py` 明确提供成功续期后的 deploy hook。官方文档也区分 webroot 认证与证书安装，并说明 `--run-deploy-hooks` 在模拟续期成功后使用当前有效证书执行钩子。[Certbot 官方说明](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates)

控制者新增 `/etc/letsencrypt/renewal-hooks/deploy/20-reload-nginx-webroot`，SHA256 `bc570fd9d052c3b93d8ce240c978b7155ec3a46b0e85e4e57b055969eb2837b2`。本审查独立读取实际脚本，确认 root:root、0755，全部父目录 root 拥有且 group/other 不可写；`set -eu`、精确匹配上述两个 live lineage，依次执行 `nginx -t`、`systemctl reload nginx`，成功后才输出 marker。其它 lineage 无动作。未修改 renewal 配置或 timer 频率。

仅 `smartbox-platform` 的一次 `renew --dry-run --run-deploy-hooks` 于 UTC 03:15:04.642509–03:15:34.722244 完成。独立读取根原始回执与 stdout：ExitCode=0、该 lineage 模拟续期成功、deploy-hook 调用及成功 marker 各有实际证据；nginx journal 在同一窗口真实记录 Reloaded，没有失败记录；主 PID 前后均 366162，审查时仍 active/running。三组 fullchain SHA 在初始演练、修复演练和最终现态完全相同。03:17:58 再从 gateway 以普通 DNS 对 lobby 与 pitch 两组证书各做一次请求，均 200、remote_ip=117.50.177.254、TLS verify=0。

修复回执 SHA256 `dcb7f097e07d86a45b4c345dbe1a375ba62929e943d171feaf04ba63855b2948`；stdout SHA256 `d3d6f99ee974a241dd220ed820d7e79f1aa71afaab18a060f5e4377a1b99b327`。因此不是仅凭 Certbot 返回 0 关闭问题，也未强制签发或替换真实证书。

**本轮退旧边界的实际证据**

| 边界 | 核验结果 |
| --- | --- |
| DNS 与 TTL | UTC 03:04:36–40 本审查经 gateway TCP/53 直查 dns27、dns28，各五域共十答均 AA/NOERROR、唯一 A=117.50.177.254、TTL600；gateway 默认 resolver 五答也均新 IP。晚于保守 TTL gate 02:52:17.072462。DNS UI 修改与其它十条记录保持不变属于 Root 既有操作证据，本审查未再操作控制台。 |
| 旧 edge 实际退出 | 旧根原始回执记录 02:55:24 无 HTTPS/active upstream 后执行 `nginx -s quit`，02:55:27.940 自然退出。独立现态 nginx inactive/disabled、Restart=no、MainPID0，无 nginx 进程、无 80/443 listener、HTTPS established=0；限定窗口 journal 为正常 Deactivated successfully，未见强制终止。旧配置和资源保留。 |
| 旧 writer/VPN/续期 | 旧机仅四 PG＋两 GPU 容器运行，原十一业务容器未复活。receiver authorized_keys=0 bytes、receiver process=0；旧 WG inactive/masked、certbot timer inactive/disabled。03:07:53 对四 PG 分别执行 READ ONLY 活动计数，其他 client=0、prepared=0；未扫描业务数据。 |
| 新入口与临时信任 | 独立 nginx -T 成功，活跃配置无旧公网/私网 IP 引用、无 real_ip 指令；原信任文件已移出配置目录，归档 SHA256 仍为 `9347f8e29ec7b53c5f8d1fd5cfadd635bfabd16e41a0f055eecadb1cf96110f7`。本审查自发 plain/伪造头双 nonce 在新机日志各唯一 200，记录 client 相同且均不是伪造值。 |
| 旧 edge 关闭后的公开功能 | 本审查由 gateway 使用普通 DNS、严格 TLS、无 --resolve：五域 health 均 200/新 IP/TLS0；Galaxy/kiosk HTML 与有界公开列表 200，匿名 auth/me 401。实际媒体 Range=206、1024 bytes、SHA256 `68f53c831803a81cd42b6a09be11c09030c4ee07f7a2774028c6882081650ad4`。匿名 `/ws/lobby` 严格 TLS 直达新 IP，upgrade101 后 close1008 “No token provided”，未创建用户或对局。 |
| RK 实际路径 | 核验旧 edge 关闭后 UTC03:02:23–24 的真实 RK 五域回执，五次普通 DNS/remote IP 均新 IP、HTTP200/TLS0、服务 before/after 全相同；报告字节 SHA256 `7dc3c579a9bb89c242d0cac04b689bdc995cc6138aeb9109adc9f5061627762d`。本审查另在新机实际日志独立查到这五个 nonce 各唯一 200；没有重新导航、登录或改设备模式。 |
| 续期 owner | 初始三配置 staging dry-run 于 02:52:43.701–02:53:49.650 全部成功，实际 stdout 三个 fullchain 均 success；三组 live SHA 始终不变。NEW canonical certbot.timer active/enabled/waiting，下一次为上海 2026-10-27 22:30:37；OLD timer 停用。两个 webroot 的部署缺口已按上文关闭。 |
| 新运行状态 | 实测 17 容器运行、16 个不同 ImageID；已配 healthcheck 的全部 healthy，restart count=0、OOM=0。实际 web image 为 `sha256:f90b1526e8ec9375e3f0021a478b7a546fbf3026f6268b2b331adf97289b5355`，与既有发布一致；运行容器 Env 扫描没有旧 IP 引用，仅输出判定，没有输出 Env 值。约 35 GiB 根盘可用。 |
| TEST 接收路径 | TEST 仅一个 cron 运行、迁移前 cron 停止，两者同一不可变镜像；Env 唯一差异为 SSH 目标，独立断言其为预期 NEW。stage/key/budget/known_hosts 配置未变，mount 按 destination 比较完全相同（数组顺序不同不算漂移）；known_hosts 只读挂载、host/container SHA 相同，新主机指纹31it存在；实际容器同步代码保留 StrictHostKeyChecking=yes。没有执行同步/重放。 |
| gateway/VPN | NEW WG active/enabled、地址10.8.0.3；gateway 的 PROD peer endpoint 为新公网且无旧公网 endpoint。PROD/TEST forward PID 分别1723160/731204保持，严格 host-key 检查仍启用，PROD pin匹配新机，TEST原目标保持；PROD admin health200。正确的 `/api/v1/kifu/readiness` 在 NEW VPN8013/8014 均200，generation与既有值相同。 |
| 最终离机备份 | Mac 两个最终 tar 实际存在，分别2473472000和3872061440 bytes、文件0600/父目录0700，均无 .partial。独立读取控制者已完成的完整 SHA 与33 payload校验回执：13库归档 SHA `fc53fba5b1080a93a534cbabc1e530438aef335533674e27e60161c0833a6740`；非PG归档 SHA `6ac730c0af7ea125b3db2d13e333d854af726b1bf40ed659973ef3a52a4defd3`。按限定 scope，本轮未重新全读6.3GB归档或重做恢复。 |

**非阻塞事项与证据边界**

- Root Mac 新建公网 TCP 路径仍未证明恢复。Root 会话工具输出报告：02:57:46 三个新公网 URL 普通 DNS 已解析177，但 connect15秒超时；随后 NEW22/443、OLD22、gateway22 各约4秒超时，Aliyun443约29ms成功，已有 SSH control master 仍可用。未保存原 raw 文件；本审查仅读取明确标为 Root-reported 的注记，未把它当独立复测。精确网络根因未知，不能归责某一个应用，也不能宣称所有互联网或 Root Mac 通路已正常。独立 gateway 与实际 RK 的成功证明本轮已验证路径不依赖旧入口。
- 初始 ACME 启动遗漏 --no-block，使 Mac SSH 等待超时；独立 unit 继续并成功完成，没有取消、重启或重放原三组。两次验证 transient unit 均已正常被 systemd 回收，当前 LoadState=not-found；不能用此时 systemctl 默认的 Result=success 证明历史运行。结论使用原始 finish/stdout 与实际 journal。第二次聚焦验证的启动已正确使用 --no-block。
- TEST 保留的旧 stopped cron 与现役 cron 共用 Compose 标签，当前未造成双 writer；后续常规 Compose 维护应避免误复活旧 collector。此为原审核已记录的维护项，不是本轮新增阻塞。
- 尚未等到未来 canonical timer 的真实签发周期；本轮证明的是 ACME staging 验证、实际 deploy hook、nginx reload与现有有效证书完整性。没有签发真实替换证书，也不能保证未来 CA、网络或人工配置永不变化。
- 本轮未重审数据库恢复/68项 schema 证明、全库或全 SGF 内容、原生新增包/付费整理，也未新建用户、登录、对局、预约或报告。数据与既有幂等链路结论沿用之前完整迁移审核及控制者已核验记录，不冒称本轮再次全量证明。RK为健康请求与服务状态验证，没有完整屏幕/SSO交互验收。
- 新机是后续写入权威；旧 PG 是停写快照。即使旧资源尚未删除，也不可直接启旧 writer 作为无损回滚。真正回滚仍需保护新写入并受控反向同步。

**原始证据定位及历史保留**

NEW `/var/lib/ucloud-migration-20261027/dns-cutover/`：初始 ACME finish SHA `d73930415a60d1b6ce1a78e97a4b7a057823aee384f79482b095080ea00c3bfe`、stdout `a70ed812cdf2d603bdc0ee90f24197dc795253c5d3945630c51edb7002ec01e4`、trust/timer handoff `8bf9ff659914615d7528dda56b2d25596cd9541dad80dedfe739a3a58ffa3af2`，以及上述 webroot 修复证据。

OLD 根 `dns-cutover-old-edge-retired.private.json` SHA `35fd49dd40ccc9b762c893068d417838eceebe93fe09c273db2e5cf02a42a36f`。Mac `dns-cutover/raw-new/`、`raw-old/` 已核对应根原字节；旧 compact JSON 副本经独立比较内容相同，但 SHA 不同，未冒称逐字相同。Mac 路径限制注记为 `root-reported-mac-path-limit.private.json`，其证据级别明确低于原始工具 raw。

原 `final-independent-review.md` 的 UTC22:00–22:12 条件批准/不可退旧结论保留原文，本报告仅在后续 DNS、旧 edge、信任、备份与续期部署缺口完成后给出新时点结论。没有改写历史失败回执，也没有删除任何旧资源。

报告写入UTC：2026-10-27T03:20:41.789798+00:00
