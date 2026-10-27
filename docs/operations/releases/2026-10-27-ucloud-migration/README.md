# UCloud V100 迁移记录 — 2026-10-27

**迁移完成：`can_retire_old=true`。全新独立Astra最终运营审查通过，未解决必修项0；旧云资源尚未删除，由用户自行操作。**

UTC03:20最终审核实况：新机17个原有服务容器正常运行，单张V100上的两个KataGo engine ready/warm；五A已切新177并过完整TTL，关旧后的gateway和RK普通DNS五域均200/TLS通过，媒体与真实WS通过。新certbot续期timer已接管，live证书字节不变，旧private临时real-IP信任已撤除。本轮审核发现并已修复两个webroot证书续签后缺nginx reload的漏项：精确两lineage成功deploy hook及一次聚焦staging实际调用/重载均通过。旧11个业务容器及receiver/WG均维持隔离，旧nginx inactive/disabled，只保留4PG与两个旧engine供对照，未删除旧资源。

本页为最新汇总；[DNS切换](dns-cutover.md)与[DNS后实际收尾](post-dns-closeout.md) · [最终独立运营审核](post-dns-independent-review.md)记录这次最终阶段。此前UTC22:00–22:12的Astra报告保持历史原文，不能把其当时DNS未切的结论误读为现状，也不把控制者新结果冒称为当时审核已证明的内容。

## 运行与数据

| 项目 | 实际结果 |
| --- | --- |
| 新机 | `ucloud-v100`，117.50.177.254 / 10.60.162.188，Ubuntu24.04，8CPU/64GB/V10016GB/100GB |
| 旧机 | `ucloud-v100-old`，117.50.183.169 / 10.60.219.118，保留，未删除/退订/续费 |
| 应用版本 | 原已发布 `e9b4d3ecce03b3269f12922a476fd6d6c6545547`；web实际image `sha256:f90b1526e8ec9375e3f0021a478b7a546fbf3026f6268b2b331adf97289b5355` |
| 镜像 | 17个原在线服务的16个不可变image逐ID迁入；未运行3个历史exited init/import任务 |
| 基础组件 | Docker29.5.2/containerd2.2.4/runc1.3.5/Compose5.1.4同旧；新专有NVIDIA580.178.04/NCT1.20.1 |
| 数据库 | PG15/15/16/17，13个非template库、4份globals全部离线逻辑恢复，owner/ACL/sequence/extensions/密码等价核对 |
| 非PG数据 | 4卷＋4bind最终checksum delta，两次完整dry-run均0；含MinIO全部metadata、平台静态资源、模型及审计状态 |
| 持久可写层 | 原14份教程备份、必要Kivy/Caddy配置已保留；当前新GPU同设备/驱动/配置的timing cache复用 |
| 重启核验 | 4PG配置16文件原bytes/UID70/mode复制；各19项GUC及全部库清单一致，配置错误与pending_restart均0 |
| 新机容量 | 此前独立审核实测约35GiB空余，满足保留至少15GiB的迁移门槛 |

运行权威是冻结的私有Engine manifest/operator，原历史Compose文件链不作为新机部署依据。所有image、volume、bind、网络、原GPU单卡双engine及权限按真实运行配置保留。新Docker增加WG启动顺序依赖，防VPN地址未就绪时原端口绑定失败。

## 最终导入的严格验证与续作

原最终窗口在旧11个writer正常SIGTERM退出、receiver授权/进程为0、PG无其它client/prepared后，导出并内网逐SHA核验13库。全部restore exit0。

原严格schema-dump hash门禁正确拒绝4个库并留下`failed_final_apply`。精确差异只有67个CHECK和1个partial unique-index的表达式重解析：varchar数组cast与AND分组。固定对象、literal字节/顺序、非表达式元数据及其它DDL逐行核对；PostgreSQL自身只读EXPLAIN无ANALYZE，真实Output和完整稳定计划全部一致，0额外差异。网络失败的两次部分证明均保留，并集覆盖68项，重复对象及catalogue逐字一致。

新continuation使用独立1800秒锁和verify/sign/copy各自新鲜live证据，绑定原manifest、失败回执、旧fence、完整13库exit0与当前物理fence。新receipt独立签发，**没有修改旧失败回执、放宽成忽略所有schema hash、重导13库或伪造旧过期锁有效**。

关键哈希：

- 原manifest：`3b8d2b9da4ebab869c8a0b5745aa749eda95fa428d09a478f3cef78e983a8a9e`
- 68项真实语义证明：`38aeaa7ee70560f0c76d2d8ad27285b52fe0c2aa7b6bcf52b58e89f3a14b98eb`
- 新最终数据回执：`836ffa4e4a0c234a1f3647814c975649bfd281b7edf428d9cfebacdfb64c8ebe`
- 配置复制回执：`3bb0fe92dc2cdbbb0e9e39973764e5256d9b4dccd3fb913090cca331d75ad7a0`

## 真实TEST→PROD与调度恢复

TEST原stage、密钥、预算、模型与数据库保持原值。持久override仅将接收SSH目标改为`kifu-receiver@117.50.177.254`，专用known_hosts加入已由用户控制台核实的新ED25519 key；StrictHostKeyChecking未关闭。新cron同原9604镜像，原Web同8539镜像/容器恢复。

原冻结包`rank-only-current-page-tail-20261026-v1`的5谱在标准stage writer flock下完成真实原生重放：TEST939→新PROD932，manifest前缀`133dc7ae`，返回原receipt逐字段相同。25项五语详情/SGF/姓名/rank及5张公开卡片全部通过。包JSON、这5谱及相关来源/快照/批次记录的前后哈希完全相同；PROD总量保持176884 albums、919 batches、176896 sources、54 rank snapshots、46 rank history。**这是已有包幂等验收，新增谱0、翻译0、重复入库0**；未修改stage/prod_synced。

- 新PROD7个interval控制于UTC21:45:43完整CAS恢复为原先全部absent；仅新机恢复。心跳新鲜，fetch/poll任务已真实success，native `kifu_ingest`不注册。
- TEST8个控制于UTC21:55:24完整CAS恢复为原先全部absent。唯一collector enabled、interval3600、目标新IP，running/advisory/receiver均空闲。恢复操作也持同inode标准writer锁，完成后释放。
- 恢复后的自然小时轮79033于UTC22:20:17成功完成，176.7秒/error0；head5页100项/46请求/41SGF检查，55超窗过滤、预算未耗尽；本轮无新包/模型调用，详细coverage见收尾补记。
- 两个1800秒纯维护锁均按各自期限自然结束；真实重放与恢复分别由实际操作进程持标准writer锁直到完成。没有超时取消SSH/同步写线程，也没有自动延长旧锁。

PROD仍保留原有live fetch、免费Wiki和分析功能；本次未把旧默认任务误说为全部关闭。原生小时采集/付费整理仍只有TEST，既有3300秒为协作预算，不能当可强杀截止。

## 入口、VPN与设备

新WG唯一接管10.8.0.3，旧WG停并mask。gateway仅替换PROD的10.8.0.3 host pin并重连，TEST原pin/PID未改；PROD admin health200/providers available，Legacy A/B通过新WG readiness200。

新nginx五SNI证书验证通过。过渡期旧入口曾只代理新private HTTPS，CA/hostname/SNI验证始终开启；现旧proxy已正常退出。实际发现跨SNI复用TLS会话造成3域502，已仅关闭旧上游session reuse；指定五域两轮串行health全200/TLS0。过渡期新nginx曾仅临时信旧private；最终已撤除该三条real-IP指令并重新核对伪造XFF/X-Real-IP未被采信。

Galaxy、lobby/chess HTML、未登录认证拒绝边界、原路由ACL、媒体Range206/字节哈希均通过。未新建测试用户或改用户登录状态。RK仅执行严格TLS health请求，唯一nonce在新机日志命中，实证RK→旧proxy→新机；设备验收前后服务状态相同，未改Chat/Go模式、导航、SSO或标定。

MinIO保持原内部网络。容器重建后必须运行`sudo /usr/local/sbin/refresh-minio-upstream.py`再reload nginx；公开媒体Env修为同域`https://modelstella.com/media`，修复原preview域名不可解析的实际问题，未改bucket权限或开放数据库/GPU/MinIO公网端口。

## 旧机退役与回滚

五个现有A（主域、www、lobby、ranked、pitch-api-staging）已于UTC02:36:13改为117.50.177.254，TTL600、其余10记录未动；两独立gateway TCP53权威AA/NOERROR核验通过，采用02:42:17的较晚首次证明，02:52:17完整TTL后才收口。此前OSS API身份403及原生窗口故障是历史阶段阻塞，Root已用既有登录主账号完成实际修改，没有申请新凭据或扩权。

新机三组原ACME配置一次staging模拟全部成功，live三证书SHA不变，canonical certbot.timer active/enabled，旧timer仍停。旧edge在0连接/0active upstream时直接QUIT自然退出，无强kill；新机不再信任旧private10.60.219.118。[本轮独立运营审查](post-dns-independent-review.md)已确认在已盘点迁移范围内`can_retire_old=true`、未解决must-fix0；尚未执行云资源删除/退订/续费。

已实际验证的外部路径是gateway与同LAN RK：旧proxy关闭后五域普通DNS均直达新177/TLS通过。Root Mac新建TCP同时对新机、旧机和gateway超时，而其它互联网目标可达；具体根因未证，本轮不确认该Mac路径恢复，不泛称所有互联网客户端均已验证，也没有盲改云防火墙或本地网络。用户另确认实际浏览器已能打开新机页面，该项仅为user-reported。

新后端已接收正常业务，旧PG只是停写快照，**不能直接启旧writer当无损回滚**。若需回滚，须先停新写入并保护新权威数据，执行受控反向数据同步/验证及网络单writer交接。旧nginx配置保留，可单独start恢复代理能力；这不意味着允许陈旧旧库重新接写。

## 备份与记录

Mac初始完整主库备份1,091,146,291 bytes及配置/14教程历史备份已离机。最终13DB tar 2,473,472,000 bytes已完整到Mac，内含13库＋4globals＋16配置共33个payload重新逐尺寸/SHA核验通过。最终非PG冷快照3,872,061,440 bytes已完整离机到Mac，下载流校验及本地独立全文件重读SHA均匹配`6ac730c0af7ea125b3db2d13e333d854af726b1bf40ed659973ef3a52a4defd3`，已原子rename且.partial不存在。所有env、密码/role hash、私钥、SQL/媒体备份均仅在目录700/文件600私有位置，不在Git。

[计划](../../../superpowers/plans/2026-10-27-ucloud-v100-migration.md) · [计划安全审](../../../superpowers/reviews/2026-10-27-ucloud-migration-plan-review.md) · [运行配置审](../../../superpowers/reviews/2026-10-27-ucloud-runtime-config-review.md) · [continuation安全审](../../../superpowers/reviews/2026-10-27-ucloud-continuation-plan-review.md)

[运行盘点](runtime-inventory.md) · [客户端依赖](client-dependencies.md) · [基础安装](foundation.md) · [初始恢复](database-initial-restore.md) · [入口准备](host-edge.md) · [GPU验收](gpu-preflight.md) · [隔离功能预检](services-preflight.md) · [DNS权限](dns-access.md) · [writer边界](writer-drain.md) · [控制CAS](control-batch.md)

[最终导入执行记录](final-data.md) · [实际入口与RK验收](ingress-cutover.md) · [首次Astra流程审核（历史）](final-independent-review.md) · [首次审核后收尾](closeout.md) · [DNS切换](dns-cutover.md) · [DNS后实际收尾](post-dns-closeout.md) · [最终独立运营审核](post-dns-independent-review.md)

附：迁移临时SSH授权已从旧机精确撤销，其他授权原字节保留，新机临时private key已删除；常规Mac管理key经新机VPC代理访问旧机仍可严格host-key登录/sudo。TEST旧stopped cron保留作回滚证据，Compose标签存在后续维护歧义，独立审核列为非阻塞；再次常规Compose部署前须明确唯一实例，不可误启动旧collector。
