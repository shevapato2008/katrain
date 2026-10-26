# UCloud 迁移与 TEST→PROD 独立只读审核

审核时间：2026-10-26 22:00–22:12 UTC（2026-10-27 06:00–06:12 上海）；最终写入时间见文末。
范围：旧/新 UCloud、TEST、gateway 的有限运行状态、数据库只读查询、原始证据文件和公开 GET。生产端未修改业务数据、控制行、锁、服务、网络或 DNS；未调用采集、导入、翻译、模型推理、报告创建或 native 重放。本报告仅写在本机。

**结论：有条件批准新后端继续承担生产；不能批准“整机迁移全部完成”或删除旧机。`can_retire_old=false`。**

未发现需要立即暂停新业务的新增问题。新机是当前业务写入权威，TEST 是原生小时采集的唯一生产者；旧机仍是公网 HTTPS 必需入口。必须保留这两个结论之间的区别。

## 独立实证

| 边界 | 本轮实际核验与结论 |
| --- | --- |
| 运行与版本 | 新 hostname `10-60-162-188`，17 个容器运行；已配置 healthcheck 的容器均 healthy。17 个实际 ImageID 全部匹配冻结 source inspect，共 16 个不可变 image，无重启计数、OOM 标志或公网全地址敏感端口绑定。未重建或升级业务源码。初次检查根盘约 35 GiB 空余。 |
| 旧 writer 隔离 | 旧 hostname `10-60-219-118`，11 个业务容器均退出，仅 4 PG＋2 GPU 留存。旧业务 restart policy 为 unless-stopped 或 no，没有 always。旧四 PG 逐一只读查询均为 0 其它 client、0 prepared transactions。旧 receiver authorized_keys 为 0 bytes/0 key，receiver process 为 0。旧 WG inactive/masked、certbot timer inactive/disabled。 |
| 新网络身份 | 新 WG active/enabled。gateway 实际 PROD SSH PID 1723160，以 StrictHostKeyChecking=yes 连 `ubuntu@10.8.0.3`，转发 `127.0.0.1:18011→127.0.0.1:8010`；health 200，返回 katrain/platform providers。TEST 原 PID 731204 仍 active，仍连 `fan@10.8.0.2`。新 WG 的 Legacy 8013/8014 readiness 均 200。 |
| 最终导入证据链 | 原 manifest、原 failed apply、原/新 fence、semantic proof、continuation verification、config copy、final receipt 的实际字节 SHA 与给定值一致；manifest→failed/proof→verification→config→final 引用匹配。13 restore exit=0；原失败回执仍为 failed_final_apply，未被伪改成功。 |
| 有限 schema 例外 | 4 库共 67 CHECK＋1 partial unique index，68 身份唯一。逐个实际 plan/catalogue 文件 SHA 与汇总匹配；68 个 source/target planned JSON 实际完全相同、Output 非空、literal/order 标志为真，其他 DDL exact-match。不是只检查汇总 Status。没有再执行 EXPLAIN 或恢复数据库。 |
| continuation 锁 | 保留证据显示独立 1800 秒窗口，verify 与 sign 均在该锁期限内；新 final receipt 明确 DatabaseRestoresRepeated=false，原失败状态保留。16 配置文件记录均 UID70/mode600；旧过期锁未被当成当前授权。此项是对历史原始证据的审核，不能称本轮重新观测了已结束的锁。 |
| 当前 PG | 新四 PG 实际版本 15.18、15.19、17.11、16.14；非 template DB 清单合计 13。四实例均 config_errors=0、pending_restart=0、prepared=0。历史 runtime receipt 各 19 项 GUC 匹配。17 份最终数据库/global 文件当前存在、bytes 与 manifest 相符、mode600。未重新全量哈希所有归档。 |
| 有限当前数据复核 | 对当前 PROD 与 TEST 分别开启 READ ONLY 事务，按原方法重新计算 5 谱、batch932/939、sources、10 条 rank snapshot 的整行 MD5及5张表计数；每个字段均与重放前/后原始快照完全相同。PROD 为 176884 albums、176896 sources、919 batches、54 snapshots、46 history；TEST batches 为 922，其余计数相同。 |
| 真实重放与幂等 | 原 12 份证据字节核验通过；PROD before/after 原 raw SHA 均 `0e3b0f866db43644c15876d1db908186369114f5493bbd3cadbd554781cebaa4`，TEST before/after 字节相同。native response batch932，原 publication key；API 证据 status verified，5 谱、25 个五语检查、5 张卡片。结合当前整行哈希，支持已有包幂等复用；不是新增 5 谱。本轮没有重新发送 native 包。 |
| TEST 实际目标 | 新 cron ID `aff8a325…`，image `9604d05e…`；原 Web ID `bbeef6a…`、image `85391af…`。新/旧 cron 全部 Env 的唯一差异是 SSH_HOST，实际为 `kifu-receiver@117.50.177.254`；原 stage/key/known_hosts mounts 相同。新 known_hosts fingerprint `31itMGe6aoHtgkfaQQXAt2iQ5S1Xn1R66LKam8o2qDU` 存在，容器实际挂载文件 hash 与 host 文件相同，read-only；stage lock 仍 device2081/inode203039078。 |
| 接收权限 | 新 receiver 1 个公钥，选项为 restrict＋固定 forced command。sudoers mode440，仅允许无参数 `/usr/local/sbin/kifu-incremental-receive-root`。未打印公钥正文、私钥、密码或任何 token。 |
| 调度恢复 | 本轮当前 NEW 与 TEST 的指定 8 个 control 行均 absent。心跳观测约 14 秒/24 秒。TEST kifu_ingest enabled=true、interval3600，running=0/advisory=0；NEW 无 native kifu_ingest 注册，但保留既有 fetch/poll/免费Wiki/分析。fetch/poll 在恢复后已有实际 success。TEST 两份 root 恢复回执的原样本地副本 SHA 亦匹配；本轮不越过 TEST 既有 sudo 限制。 |
| GPU | 新 8000/8002 GET /health 均 200、status ok、ready=true。本轮未推理；原真实推理成功与 warm 记录属于既有证据。 |
| 实际 HTTPS | 从 gateway 分别经当前公网 DNS 和 --resolve 直达 NEW，五域共 10 次 health 全 200/TLS verify0，各同域 body hash 相同。Galaxy/kiosk HTML 200；公开棋谱有界列表 200。媒体真实 Range 206、1024B，SHA `68f53c831803a81cd42b6a09be11c09030c4ee07f7a2774028c6882081650ad4` 精确匹配。 |
| 旧代理与真实 IP | 旧 nginx -T 有效，唯一 proxy_pass 为 `https://10.60.162.188`，CA/verify/SNI 均启用、proxy_ssl_session_reuse off，WS Upgrade/Connection 保留。新 nginx 有效，只信 `10.60.219.118` 的 X-Forwarded-For；新 upstream 未反向指旧机，实际容器 Env 无旧公网/私网 IP。既有伪造头测试记录已读，本轮未重复发送。 |
| DNS 与证书 | gateway 直接查询 dns27 与 dns28.hichina.com，五域均 AA/NOERROR，A 全为旧 `117.50.183.169`、TTL600。新 certbot masked/inactive；三组实际证书到期分别为 2027-01-02、01-03、01-17，当前 TLS 有效，续期接管尚未完成。 |

## 退旧前必须完成

1. **DNS 与入口依赖未解除。** 获得已授权的编辑权限，将五个现有 A 指向 `117.50.177.254`，核对两权威及实际 resolver，等待 TTL 和旧连接排空，验证新公网直接 TLS/代表功能。当前删除旧机会中断全部五个域名入口；不能因新后端健康而删除旧机。
2. **完成证书续期接管及临时信任清理。** DNS/挑战路由就绪后恢复新 certbot 续期，并在旧 private IP 释放/可能重分配前撤掉新 nginx 对 `10.60.219.118` 的 real_ip 信任，验证配置和入口。旧 certbot 保持停用，避免双 owner。
3. **完成并核验最终离机副本。** 本轮 Mac 观测：初始主库备份 1,091,146,291B 存在；final-all13-databases.tar 2,473,472,000B 已为最终文件，但本轮未再验完整 SHA；final-nonpg-and-binds.tar 仍为 .partial。保留旧机及新机冷归档，完成 final offsite 的尺寸/哈希核验后再执行不可逆删除，不能把 .partial 当成功备份。
4. **保持单 writer 和正确回滚语义。** 新机已接收正常写入，旧 PG 是停写快照；不可直接启动旧 writer 或把业务指回旧数据库当作无损回滚。当前未发现双 writer，此项是退旧/后续操作的必要约束。

## 非阻塞项与明确未证明的范围

- TEST 自然小时轮次尚未在恢复后完成：本轮 kifu_ingest.last_success_at 仍为 UTC18:43:55，原生固定包链路已另行证明。后续只需观察既有调度的下一轮；不应为补证据手动触发新采集/付费处理。
- NEW translate 有 1 次历史 consecutive_failure；只读判断 last_error 正是“前一个 cron 进程退出”的记录，last_finished 为启动时21:16:59，新一轮已于21:47运行。没有证据表明新增迁移故障；不把该历史项隐去，也不扩展为无关重试或修复。
- TEST 保留的旧 stopped cron 与新 cron 使用同一 Compose project/service 标签；当前只有新容器运行，未构成双 writer，但后续常规 Compose 操作需明确实际容器与唯一运行定义，避免误复活旧实例。
- 本轮未全库逐行 checksum、未全量 SGF 扫描、未重放所有用户写入旅程，未新建账户/登录/对局/预约/报告；亦未复测真实屏幕 UI、SSO 用户会话、所有历史语言内容或长时间 GPU 负载。13库完整性结论依赖已冻结的 restore/metadata/transfer 证据链，加上本轮有限现态复核；不是数学意义的全库逐行相等证明。
- RK 设备链路以既有独立 nonce 日志记录为证据，本轮未操作设备或导航；本轮独立公开入口检查来自 gateway。
- 所有当前状态均是上述观测时点，不能替代 DNS 切换完成后的最终验收。报告没有授权或执行退旧。

关键原始证据：NEW `/var/lib/ucloud-migration-20261027/`；本地受限目录 `/Users/fan/.local/share/ucloud-migration/2026-10-26/test-endpoint/`。公开文档 README 已更新到 UTC22:00 当前状态，历史阶段报告仍应按其明确时间/作用范围阅读。

报告写入UTC：2026-10-26T22:12:10.061218+00:00
