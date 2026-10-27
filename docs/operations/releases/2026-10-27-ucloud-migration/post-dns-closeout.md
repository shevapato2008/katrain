> 最终独立结论：[`can_retire_old=true`，未解决必修项0](post-dns-independent-review.md)。唯一证书装载缺口已修复并实证复核，旧资源仍由用户自行删除。

# DNS 后最终运营收尾

本页是迁移控制者的实际执行记录；独立审核报告另行保留，不冒称控制者结果已由审核者全部复核。UTC日期为2026-10-27（北京时间加8小时）。旧云资源未删除、退订或续费。

## 实际执行

| 边界 | 时间与证据 |
| --- | --- |
| DNS | Root于02:36:13.669在既有AliDNS主账号提交五A→117.50.177.254，TTL600，其余10记录未动。Root与controller分别经gateway TCP53真实权威AA/NOERROR核验十答案；更晚首次证明02:42:17.072462，TTL门禁02:52:17.072462。详见[dns-cutover](dns-cutover.md)。 |
| ACME | 02:52:43.701→02:53:49.650，原nginx/webroot/webroot三组配置一次LE staging dry-run全部成功，exit0；五域均完成模拟验证，三份live fullchain前后SHA完全相同。未force真实证书或运行deploy hook。 |
| 旧入口排空 | 02:55:24先核旧HTTPS连接0、到新active upstream0，直接nginx -s quit；02:55:27自然退出，MainPID0、80/443无监听、连接0，nginx inactive/disabled。原unit TimeoutStopSec5/KillMode mixed，未使用可能强制截止的systemctl stop、未强kill。保留全部旧配置/4PG/两个旧engine及资源。 |
| 旧信任撤除 | 02:56:15→16，将唯一三条临时real_ip指令文件00-old-edge-realip.conf原子移到root私有备份。原SHA9347f8e29ec7b53c5f8d1fd5cfadd635bfabd16e41a0f055eecadb1cf96110f7；nginx-t/reload均0，活跃配置无旧10.60.219.118信任。 |
| 续期唯一owner | 新certbot.service/timer解除mask，canonical timer active/enabled/waiting，下次计划22:30:37 CST。旧timer仍inactive/disabled；无新建重复定时器。live三证书SHA再次不变。 |
| Gateway关旧后 | 02:57:52普通DNS（无--resolve），五域health均200/remote_ip177/TLS0；Galaxy/kiosk棋谱页与公开列表size1为200，auth/me保持401。真实媒体Range206、1024 bytes，SHA68f53c831803a81cd42b6a09be11c09030c4ee07f7a2774028c6882081650ad4。 |
| WebSocket | 02:57:50普通DNS严格TLS直达177，/ws/lobby真实upgrade101，匿名连接按既有权限close1008 No token provided。未创建账号/棋局或使用私有token。 |
| RK关旧后 | 03:02:23–24普通DNS串行五域各一次，DNS及remote_ip全部177、HTTP200/TLS0、0timeout，各0.17–0.26秒。gateway/katrain/katago-api/kiosk/setup-wizard服务前后均active/running不变。NEW五个owned nonce各唯一200，客户IP脱敏；未导航、切模式或改登录。 |
| 真实IP防伪造 | 在临时信任撤除后，以伪造XFF/X-Real-IP访问公开health。NEW唯一nonce日志仍是受控gateway真实地址，非203.0.113.77/78，HTTP200；没有把其它客户日志作为证据输出。 |

## 独立审查发现且已修复的续期装载缺口

本轮fresh Astra实际核现装Certbot2.9发现：两个webroot renewal的installer=null，原全局/目录deploy/post hook为空；成功续磁盘证书后，没有保证nginx重新装载证书的路径。主域nginx installer不能保证随后其它证书及时载入。因此审核没有直接给退旧全绿，而提出这一项must-fix。

按Root与审核者共同确认的最小范围，只在NEW新增root:root0755成功deploy hook `/etc/letsencrypt/renewal-hooks/deploy/20-reload-nginx-webroot`，父目录不可由非root写。仅精确白名单`/etc/letsencrypt/live/pitch-api-staging.modelstella.com`和`/etc/letsencrypt/live/smartbox-platform`两条lineage，`set -eu`，依次`nginx -t`、`systemctl reload nginx`；测试失败不能reload，其它lineage不操作。保留原canonical timer及renewal配置，未改业务容器。

UTC03:15:04.642→03:15:34.722，仅smartbox-platform一次额外聚焦staging `--dry-run --run-deploy-hooks`实际调用该hook。除Certbot exit0，还独立要求并取得：stdout成功marker、真实nginx Reloaded journal、masterPID366162前后不变/active、live三证书SHA完全不变。Certbot对deploy hook失败不一定返回renew失败，因此没有只依赖exit0。本次未真实签发/替换live证书，也未重跑其它两组或数据库/采集验收。随后同位Astra实际复核脚本/根原始回执/重载journal，并于03:17:58经gateway普通DNS分别核lobby和pitch 200/TLS0，关闭唯一must-fix。

- 实际hook SHA256：`bc570fd9d052c3b93d8ce240c978b7155ec3a46b0e85e4e57b055969eb2837b2`
- 根原始验证回执：`dcb7f097e07d86a45b4c345dbe1a375ba62929e943d171feaf04ba63855b2948`
- 根原始stdout：`d3d6f99ee974a241dd220ed820d7e79f1aa71afaab18a060f5e4377a1b99b327`

本轮启动命令漏了systemd-run的--no-block，Mac SSH调用端等待40秒超时；durable oneshot独立继续运行并按上述时间完成，未取消或重启。根原始finish/stdout、三pem success及journal证明完成。unit随后可被systemd正常回收，不能把回收后show的默认Result=success当作当前unit仍存在或完成的证据。

## 实际原始证据

根原始文件与本地重新序列化摘要分开：NEW根回执原bytes另存Mac私有dns-cutover/raw-new，OLD另存raw-old，逐SHA验证；未把不同JSON排版称为相同bytes。

| 原始文件 | SHA256 |
| --- | --- |
| ACME finish | d73930415a60d1b6ce1a78e97a4b7a057823aee384f79482b095080ea00c3bfe |
| ACME stdout | a70ed812cdf2d603bdc0ee90f24197dc795253c5d3945630c51edb7002ec01e4 |
| 新trust/timer回执 | 8bf9ff659914615d7528dda56b2d25596cd9541dad80dedfe739a3a58ffa3af2 |
| 旧edge自然退出回执 | 35fd49dd40ccc9b762c893068d417838eceebe93fe09c273db2e5cf02a42a36f |
| RK关旧后五域证据 | 7dc3c579a9bb89c242d0cac04b689bdc995cc6138aeb9109adc9f5061627762d |

私有证据根：/Users/fan/.local/share/ucloud-migration/2026-10-26/dns-cutover；NEW /var/lib/ucloud-migration-20261027/dns-cutover。公开Git中无env/口令/rolehash/私钥/业务备份。ACME原实际runner证据副本见[operators](operators/README.md)。

## 验收边界与回滚

Mac诊断来自Root本会话原工具输出转述，无另存原raw文件；明确以Root-reported注记保存，与gateway/RK独立证据分开。Root Mac的新建TCP在同一有界诊断中，对NEW177:22/443、OLD183:22及gateway8.130:22均超时，而www.aliyun.com:443约29ms，既有SSH master仍可用。本轮不能确认该Mac路径恢复，也没有据此修改云防火墙、代理或本地网络；具体根因未证明。Gateway与同LAN RK的真实外部请求均在旧proxy关闭后直达NEW并成功，证据只覆盖这些路径，不能泛称所有互联网客户端均验证。用户随后确认自己的实际浏览器已打开新机KaTrain页面；这是user-reported结果，不冒称Root或审核者独立浏览器复测。

本轮没有重新恢复数据库、部署业务/RK、改变调度/预算/stage/原包/prod_synced、创建用户/对局/预约/报告或调用模型。数据恢复、同冻结包原生TEST939→新PROD932幂等及自然小时79033的既有实证见[迁移入口](README.md)与[此前收尾](closeout.md)；保留3300秒协作预算、源缺可靠updated_at和列表慢路径等既有边界，不把本次DNS迁移说成这些问题的修复。

新机持续是唯一权威写端。旧PG只是停写快照，不能直接启动旧writer作为无损回滚；如需数据回迁，先隔离新写入并保护新权威数据，核对后反向同步。当前旧nginx只需start即可恢复代理能力，但DNS/TEST仍指新端，不恢复旧数据库写入。旧资源删除由用户自行操作，最终可退旧结论以本轮独立运营审查为准。
