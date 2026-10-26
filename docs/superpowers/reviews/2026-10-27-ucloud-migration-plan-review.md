# UCloud 整机迁移计划安全审核

日期：2026-10-27。范围：一次聚焦的计划与本地现有证据审核；未登录或修改任一服务器，未触发采集、导入或翻译，未审核业务代码。

**结论：Approved。** 已定位核对统筹落实的 3 项最小修正，当前没有额外计划阻塞项。新机基础安装和隔离恢复可立即继续；本结论不是“已满足切换实测门槛”或“旧机可删除”的证明。容量、GPU、数据库清单由已分配的只读任务补证，不重复调查，不再启动一轮完整计划审核。

## 已关闭的最小修正

1. **真实入口已更正为 host nginx/Certbot。** 私有运行证据显示公网 80/443 实际由 nginx 提供，`pitch-booking-caddy-1` 只绑定 `127.0.0.1:8080`。计划现已区分两者，并补充最终 dump 前停止旧 web/直接写者、验证旧 forced receiver 拒绝的持续写入封锁，不依赖 TEST 暂停 TTL。执行时在新端首次接受业务写入前验证封锁生效；代理上游固定新端，避免经同名 DNS 回到旧入口形成循环，保留旧 IP 携正确 Host 的实际请求证据。

2. **3 个已退出的一次性容器已明确保持停用。** inspect 为 20 个容器、17 running、3 exited；退出者是 `katrain-ucloud-minio-setup-1`、`smartbox-kifu-init-1`、`smartbox-kifu-importer-1`。计划 Task 1 已排除依赖自动重跑，不以 latest 替换缺失旧镜像。执行时新机隔离启动和最终恢复后确认它们未运行，PROD cron 仍仅承担原有报告分析职责。

3. **所有已发现服务域名已纳入切换门槛。** nginx 除 `modelstella.com` / `www.modelstella.com`，还配置 `pitch-api-staging.modelstella.com`、`lobby.modelstella.com`、`ranked.modelstella.com`。计划 Task 5 已加入其 A/AAAA/CNAME 核实，未脱离旧 IP 则禁止认定可退役。执行时连同 TLS、后端和新旧入口留证；随 apex 切换的 CNAME 无需重复修改，直接指旧地址的记录才改，旧缓存入口覆盖这些现役域名。

## 已具备的安全边界与执行门槛

- 计划正确区分初始在线备份与最终停写备份，要求四套 PostgreSQL 的 globals、全部非模板业务库、权限/owner/sequence 及媒体/state；匹配原 major，不在线硬拷 PG 数据目录。最终原始文件复制应在对应服务停止修改后完成，包含对象存储元数据，不能只冻结数据库。
- 全站最终备份前必须实际完成 writer 表及停写命令：TEST 唯一 producer/SSH receiver、旧 PROD 分析、平台/预约后台与 HTTP 写入口、对象媒体写者；确认在途工作及锁安全释放。不能把“当前无活跃事务”单独当作持续停写。最终恢复、校验完成前新端仍隔离。
- 既有 TEST 地址为专用公网 SSH receiver；新 known_hosts 需可信核对，不能通过关闭主机校验绕过。RK 域名消费者的正常切换不需要改设备模式。VPN `10.8.0.3` 必须旧停后新启；隔离恢复阶段移除该尚未接管地址的发布绑定，使用 loopback 测试即可。
- 容量批准必须依据峰值预算，包含镜像解压、PG restore/WAL、最终 dump 与文件 delta 的临时空间，并满足计划中的恢复后至少 15 GiB 余量。镜像流式传输可先分批执行，不能在容量证据不足时一次铺满 100 GB。Ubuntu 24/V100 官方兼容性和真实容器 GPU 验证是服务上线门槛。
- 维护开始前填入唯一 owner、明确 deadline、控制前像和失败恢复命令。现有回滚规则正确：新端产生业务写入后，禁止直接回到陈旧旧库；先冻结，再修复新端或从新权威状态一致回迁。容量、网络或上下文中断不能遗留无人负责的暂停状态。
- 公网只开放实际所需入口；恢复 inspect 端口时不将旧 loopback/VPN 绑定扩大为 `0.0.0.0`。私有部署配置、数据库备份、密钥、证书及认证状态仅存受限目录，不进入 Git 或公开回执。

## 现在可先执行

Approved：继续观察既有 dump、只读盘点和容量核算；补做其他数据库的初始备份；新机基础包安装与经确认的 GPU 配置；在可用空间预算内分批流式迁移必要镜像/文件、隔离恢复和私有功能验证。以上不依赖生产切换批准，不得重复启动同一主库 dump。

本次观察时本地已出现 `katrain-prod.pgcustom`（1,091,146,291 bytes）及备份清单，未见同目录 partial；这仅说明文件状态已变化，**不等于确认备份成功或最终一致性**。原执行者仍须核对完整退出结果、归档可读性及真实恢复；不另起重复任务。

不得仅因本报告便越过门槛开启新端业务 writer、转移 VPN identity、切 TEST receiver/DNS，或宣布旧机可删除；须按修正后的计划完成已有实测门槛。三项修正已关闭，无须为基础安装再等待批准。旧机删除、退订或购买资源始终不在本次 agent 执行范围。

证据来源：审核时的迁移计划；本地私有 Docker inspect 的服务名/状态/绑定白名单；运行盘点中 nginx 的监听与域名声明、四套 PG 采集成功标志；本地备份清单的文件名和字节数。未将环境变量、凭据或认证摘要写入本报告。

## 追加：旧 cron 当前免费 Wiki 翻译项的正常停止边界

**结论：有条件 Approved。** 可在其它业务完成排空后，用 `docker stop --signal SIGTERM --timeout -1` 正常停止旧 cron，允许当前尚未完成的免费 Wiki 项被取消、下次按原规则重新尝试。无需等待整轮免费预取自然结束或缺翻译计数归零。该结论只放宽当前 `translate` 的结束条件，不放宽 TEST collector、报告/直播分析、预约业务或其它 interval 的排空要求，也不宣称此次翻译整轮成功。

本次独立从旧运行容器读取真实源码和已安装库源码；未用本地 checkout 替代。运行库为 Python 3.11.15、SQLAlchemy 2.0.54、APScheduler 3.11.3、httpx 0.28.1；再次只输出配置布尔值，付费 LLM 配置确为关闭。未查询玩家/赛事名字、用户棋局或输出配置值，未写服务器、控制行或数据库。

### 源码判断

- `jobs/translate.py:25-45` 顺序 await 玩家与赛事处理，`finally` 同步执行 `db.close()`；此 Python 的 `CancelledError` 不属于 `Exception`，不会被这些 `except Exception` 吞掉。`translator.py` 的 Wikipedia 请求为 `httpx.AsyncClient` 的异步 GET，搜索/语言链接捕获同样仅为 `Exception`；该业务路径没有 `to_thread`、独立 worker 或后台写入任务。`translator.py:239-241` 在付费配置缺失时直接返回，不能发出 LLM 请求。
- `jobs/translate.py:85/140` await 返回前，当前项尚未进入 ORM 写入段；返回后的赋值/添加到 `db.commit()`（111/165 行）之间没有 await，使用同步 SQLAlchemy。正常 SIGTERM 由事件循环处理，不会向同步 commit 中间注入任务取消。已经完成的单项 commit 保留；当前尚未完成的网络结果可以丢弃并免费重取。实际变更仅为翻译表，不涉及原生发布包、receipt 或 `prod_synced`。
- `db.py` 的 Session 为 `autocommit=False, autoflush=False`。直接核对已安装 SQLAlchemy：`Session.close → Session._close_impl → SessionTransaction.close → RootTransaction._close_impl → Connection._rollback_impl` 会结束当前事务并 rollback 活跃未提交事务，不会隐式 commit。故取消期间当前查询事务得到释放，已提交项不被回滚。若同步数据库调用或关闭卡住，`--timeout -1` 必须继续等待，不能通过有限超时强杀跨过它。
- `__main__.py:28-31` 的 SIGTERM handler 调度 `scheduler.shutdown()`；`scheduler.py:164-178` 停 APScheduler 并取消任务。实际 `AsyncIOExecutor.shutdown` 会取消 pending future；Python runner 在退出时取消并 gather 剩余任务，随后等待默认 executor 关闭。此路径允许中断当前异步 Wiki 请求，不是等待整轮自然完成。
- **保留真实的取消元数据。** `run_recorder.py:150-166` 捕获取消后重新抛出，并明确跳过 `_finish_rows`，因此最终旧快照中这条 translate run/status 仍可能显示 `running`、finished 为空。这是预期历史记录，不应改成 success、伪填结束时间或删行。新权威 cron 的 `register/_register_rows:103-129` 会按原逻辑将前进程遗留 running 标为 failed/previous process exited。恢复后应确认这一正常恢复结果；不能再以该旧 running 行要求等待已经退出的旧进程。
- 整个 cron 仍有控制/健康 `to_thread` 和诊断 daemon，不能笼统称为无线程。核对源码，控制线程更新任务命令/暂停状态，健康和 error collector 写诊断元数据；它们不是翻译业务或付费请求线程。取消外层 await 仍不能代表这些线程已结束，因此最终证据必须是实际进程退出与旧数据库连接/事务消失。正常退出不保证所有未持久化诊断缓冲都已刷新；本批准保证已提交业务数据及真实 run 历史不被伪改，不作超出源码的诊断完整性承诺。

### 执行必要条件

1. 先封住旧端所有新的业务写请求（含内部/VPN/管理入口），新端继续隔离；暂停全部 7 个 future interval 并确认 poller 已实际读取。禁止新提交 run-now。复查付费配置仍为关闭；若容器源码/配置与本次不同，本例外不直接适用。
2. 除 translate 外，其余 interval 已自然收尾；报告、直播等业务队列和 in-flight 为零，已有 HTTP/WS 持久化完成；Pitch 仍符合其单独的 eligible/claimed 空闲门槛。只允许取消本次已确认的免费异步预取，不允许把“进程最终会退出”用于中断其它业务。
3. 正常发送 SIGTERM 并无限等待，记录真实退出状态/退出码/OOM 信息；不使用 SIGKILL、SIGSTOP、有限 stop 超时或改状态行来制造排空。若进程未退出，保持写入封锁，由已有 owner/deadline 机制明确继续等待或恢复原单一权威端，不能开始最终快照。
4. 仅在旧 cron 容器实际 exited、无残余旧业务进程且旧数据库连接/事务已结束后，执行最终 PG dump 和文件复制；同样等其它应用 writer/MinIO 各自达到原门槛。旧 cron 可写层的教程历史备份在退出后复制。保存停止前 translate run 身份及最终真实状态到私有证据，随最终数据库迁移，不手工修业务进度。
5. TEST 小时任务仍严格沿用现有 1800 秒 guard、相同 staging flock、真实远程 receiver 排空；绝不取消其 `to_thread` 或用本结论代替锁验证。只有新端最终恢复核验、唯一 writer 和目标 hostkey/receiver 生效后恢复控制前像；免费未完成项由原有后续调度处理，不主动重导或重译已发布包。

此新增判断已完成一次源码聚焦核对，无需整轮重审；只改变上述免费 translate 项的允许停止边界。DNS 未切或仍依赖旧 nginx 时，`can_retire_old` 继续为 false。
