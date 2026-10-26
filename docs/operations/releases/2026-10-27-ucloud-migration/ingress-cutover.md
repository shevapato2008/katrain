# UCloud 入口切换验收（脱敏）

设备验收时间：2026-10-27T05:57:50.965264+08:00。本轮仅在 `rk3562-local` 执行只读 date、DNS、curl 和服务状态查询；未操作 GUI、导航、mode、认证或服务启停。

- RK DNS A / curl 连接 IP：`117.50.183.169`（旧入口）。
- 严格 TLS health：HTTP **200**，`status=ok`，TLS verify **0**，未使用 `-k`。
- 唯一 nonce：`rk3562_cutover_mvpss0b0_eswqol`。
- NEW nginx access log 唯一命中该 nonce，HTTP **200**，证明 **RK → 旧入口 proxy → NEW**；客户地址已脱敏，解析后的地址不是旧 private。
- RK 原有 `smartbox-gateway`、`smartbox-katrain`、`smartbox-katago-api`、`smartbox-kiosk`、`smartbox-setup-wizard` 均 active/running，查询前后完全一致；未启动任何服务。

```text
[client-redacted] - - [27/Oct/2026:05:57:50 +0800] "GET /api/v1/health?migration_probe=rk3562_cutover_mvpss0b0_eswqol HTTP/1.1" 200 89 "-" "curl/7.74.0"
```

已实际完成的入口证据：

| 域名 | 检查路径 | 结果 |
| --- | --- | --- |
| modelstella.com | /api/v1/health | 200 |
| www.modelstella.com | /api/v1/health | 200 |
| lobby.modelstella.com | /health | 200 |
| ranked.modelstella.com | /health | 200 |
| pitch-api-staging.modelstella.com | /api/v1/health | 200 |

五域已按 model → lobby → pitch → ranked → www 串行两轮通过，均经旧 `117.50.183.169`，TLS verify 0。旧 fallback 的跨 SNI 502 已通过仅关闭 upstream TLS session reuse 修复；证书 verify/CA/SNI 始终开启，修前配置及错误证据已保留。

- 真实 client IP：分别经旧 fallback 和直达新公网 `117.50.177.254` 发送伪造 XFF/X-Real-IP 的两次 health 请求，均 200；NEW 日志记录真实 gateway 地址，未采信伪造头。
- 代表性 HTTP：Galaxy `/galaxy` 与大厅 `/lobby/chess/` HTML 200；未登录 auth/me 401。大厅根、static、admin 与 ranked/ws 保持原 404 ACL。未创建交互式登录会话。
- 实际教程页图 Range：206，1024 字节，`Content-Range: bytes 0-1023/64338`，TLS 验证通过。
- Gateway → NEW WG `10.8.0.3` 的 Legacy 8013/8014 readiness 均 200；prod admin health 200，katrain/platform providers available。
- prod forward 仅更新 `10.8.0.3` 的已信任 ED25519 pin，服务运行；TEST pin 未变，forward 原 PID 731204 保持运行。OLD WG down/masked、NEW WG up 的实际切换由主控制器完成。
- NEW nginx active；NEW certbot masked/inactive，OLD certbot timer disabled/inactive。本 agent 未更改 DNS、cron/worker 或 RK 状态。

Gateway TCP53 直查两个权威 NS：`dns27.hichina.com`、`dns28.hichina.com`（NS TTL 86400），均 AA/NOERROR；五域 A 仍为旧 IP、TTL 600，无 AAAA/CNAME，负缓存 TTL 600。

剩余有限条件：取得 DNS 编辑权限后，将五域 A/AAAA 的最终路由指向 NEW，确认权威与公共解析并等待旧 TTL/旧连接排空；确认新端公网 80 与实际 ACME webroot/nginx challenge 路径后才恢复 NEW certbot timer。旧私网地址释放/可能重新分配前，删除 NEW 仅信任 `10.60.219.118` 的 real_ip 文件并 nginx -t/reload。上述条件完成前 **can_retire_old=false**。

私有证据：gateway `/var/lib/ucloud-migration-20261027/old-ingress-fallback/public-five-hosts.after.json`、`public-recovery.summary.json`；OLD 同目录 `initial-502-evidence.json` 与 `ssl-session-reuse-before.tar`。本报告不包含 cookie、token、账户 URL 或私有棋局。
