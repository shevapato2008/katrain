> 最终执行结论（UTC2026-10-27 03:20）：[迁移与DNS/续期接管完成，独立运营审核通过，can_retire_old=true](../../operations/releases/2026-10-27-ucloud-migration/README.md)。下方原计划/早期执行补记保留历史时间与边界。旧资源未删除，实际删除由用户操作。

> 执行补记（UTC22:42）：保护/基础安装/17服务与13库最终恢复、VPN/receiver/TEST交接、旧写端隔离、同包原生幂等验收及独立审核已实际完成。下方复选项保留原审核计划，实际范围/证据以[发布记录](../../operations/releases/2026-10-27-ucloud-migration/README.md)和[最终独立审核](../../operations/releases/2026-10-27-ucloud-migration/final-independent-review.md)为准；并非所有拟议用户写入旅程均重放。DNS编辑权限缺失，五个A仍依赖旧机入口，`can_retire_old=false`；未删除或续费旧资源。最终DB与非PG离机副本均完整并核验通过。

# UCloud V100 全服务迁移执行计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 今晚将旧 117.50.183.169 的全部现役服务/数据迁至新 117.50.177.254（100GB），验证后完成 modelstella.com/www 和内部调用切换，保留旧机回滚，不删除或付费续订旧资源。

**Architecture:** 以实际 inspect 的不可变镜像、环境、卷、网络和入口为恢复权威，避免旧 checkout 重建退功能。先在线备份与新机隔离恢复，再在有界单写者维护窗口完成最终一致性同步；同一 VPN identity 不双活，PROD 接收器与分析任务也不双写。外部流量旧 DNS 缓存期由旧 host nginx 受控代理新站，避免两个独立数据库继续接受写入。pitch 内部 Caddy 仍只绑定127.0.0.1:8080。

**Tech Stack:** Ubuntu24.04、Docker/Compose、NVIDIA V100/driver/container toolkit、PostgreSQL15/16/17、MinIO、nginx/Certbot、pitch内部Caddy、现有 VPN/SSH forced receiver；没有业务 schema/代码升级。

## Chunk 1: 保护、盘点与恢复

### Task 1: 备份与真实容量（统筹＋只读盘点 agent）

**Files:** 公共脱敏回执 `docs/operations/releases/2026-10-27-ucloud-migration/README.md`；私有备份 `/Users/fan/.local/share/ucloud-migration/2026-10-26/`，目录700、文件600；远端私有操作目录 `/var/lib/ucloud-migration-20261027/`。

- [x] 明确旧 alias `ucloud-v100-old`→183.169，新 alias `ucloud-v100`→177.254；新机免密 ubuntu 和 `sudo -n` 已实测通过；新 hostkey 已经控制台精确验证。
- [ ] 保持根 session 已启动的主库 dump：只观察 partial 增长、stderr、最终 atomic rename 和 manifest SHA；不重复启动同一 dump，不将 partial 当成功。校验 custom archive TOC 可读，并在新机实际恢复验证。
- [ ] 独立记录20容器的 image IDs、各唯一镜像尺寸、mount/network/GPU/ports/restart、卷和bind实际容量；盘点全部4套PG、MinIO、平台/SSO/admin、旧kifu API、预约站及 host nginx/Certbot/TLS/VPN/systemd。3个 exited（minio-setup、smartbox-kifu-init、smartbox-kifu-importer）显式保持停止，排除通用compose depends_on自动重跑；缺失 importer image/旧setup脚本只记录，不用latest替代。
- [ ] 四套PG分别备份 globals＋所有非模板业务DB；在线备份只用于初始恢复，最终切换需再一致备份。备份与敏感inspect禁止提交Git或输出原文。
- [ ] 100GB仅迁运行依赖、当前image、必要models/data/config。总预算含解压/restore临时空间，恢复后目标至少15GiB可用；不足则停在可恢复状态报告具体缺口，不删旧卷/历史证据或擅自买盘。目前只读上界：镜像compressed+去重解包约39.952GB、卷12.414GB、bind0.279GB，另计OS/driver/finaldump；不在新盘暂存整份镜像tar。

### Task 2: 新机基础与私网传输（唯一新机写入者）

- [ ] 以官方文档确认 Ubuntu24/V100 驱动支持及 Docker/NVIDIA toolkit 安装；保留Ubuntu24，不盲升级系统。安装驱动如需reboot仅新机，重连后 `nvidia-smi`确认V100、容器GPU访问通过。
- [ ] 从新机实测旧 private10.60.219.118:22 可达。需要时生成一次性 migration SSH key，旧端授权限制 `from=10.60.162.188,restrict`，仅用于已审迁移；私钥仅新机600，迁移后删除该授权与临时密钥。不得复制Mac私钥或放宽hostkey。
- [ ] 用内网SSH流式迁必要 image（save/load，可压缩，避免新盘同时存全tar）；各PG使用匹配major的现有image恢复，PG物理目录不在线硬拷。MinIO/其它文件先在线copy，最后写维护内delta校验。大包不能经Mac5Mbps反复搬。
- [ ] 用实际inspect生成私有resolved部署配置，显式固定镜像、env、volume、network aliases、用户/权限、单GPU的两engine；不复制所有旧image/cache/release。路径替换需白名单映射并记录，没有秘密进入公共报告。
- [ ] 初始新站只loopback/受控测试可达；不启用PROD分析writer、receiver入口、平台/预约后台worker的业务写入，不上线旧VPN identity，也不向TEST广告新接收器。DB/GPU不额外暴露公网。

### Task 3: 隔离恢复与功能对齐

- [ ] 依赖序恢复：四套数据库→对象存储/持久文件→GPU engines→主web/平台/旧kifuAPI/admin/预约API/内部Caddy/host nginx；定时写者保持停用。按原env还原 local/S3/publicURL，不将媒体字节误当PG内容。
- [ ] 新机数据库按有限关键表 counts/约束/manifest&receipt/sourceSGF/名称rank历史摘要与初始备份一致；角色扩展/sequence/owner保留；数据和state权限按实际用户还原。
- [ ] 私有Host/`--resolve`核实每个原站域名的TLS/静态/健康/WS、Galaxy/kiosk/SSO/平台/报告/教程媒体Range/admin/旧kifu/预约。GPU两容器共享同一V100，分别健康且一次有界真实分析成功；没有第二套抓取/翻译。
- [ ] TEST→PROD固定SSH/user/key/known_hosts/forced receiver/container/DB链及RK实际域名/旧IP/VPN依赖形成精确表；不导航RK、切模式或改盘面。记录所有需替换地址和受信新hostkey渠道。

## Chunk 2: 最终一致性、切换与回滚

### Task 4: 受控最终写窗口（统筹独占；独立审核通过后执行）

- [ ] 切换前列出每个写者和健康回滚命令，私有备份当前所有控制前像、运行状态、nginx/DNS记录及TTL。设置明确owner、deadline和失败恢复；任何维护启动后不得无交接退出。不得强kill尚有写线程的run。
- [ ] 先按现有小时维护入口暂停TEST未来触发，等待真实source/receiver writer及同一stage lock安全释放；保留3300协作预算事实，不能cancel await后留下旧线程。旧PROD分析、平台/预约worker和公网写请求进入可恢复只读/短维护，所有DB确认无未完成业务写者。
- [ ] 对所有业务DB做最终逻辑dump和最终媒体/state delta并存离旧机备份，验证完整退出码、SHA/TOC；新机停止对应服务，按major恢复最终DB和owner/sequence，校验关键计数/摘要与最终旧库一致。不能将初始在线dump当最终一致性证明。
- [ ] VPN peer10.8.0.3只在旧端停用并确认之后转到新端；验证route/上游peer owner。若可改用现有域名/新受控端点，必须覆盖所有消费者而非同时冒用身份。
- [ ] 更新TEST精确receiver目标和只读known_hosts（经可信渠道核对新指纹），恢复PROD唯一receiver和原分析任务；RK仅改确有旧IP的持久依赖，域名消费者随DNS；保留现有SSO身份、授权/密钥、队列和预算。
- [ ] 旧接收 wrapper 通过旧web容器执行；在最终dump前停旧web及所有直接业务写者并验证旧 forced receiver拒绝，形成不依赖TEST暂停TTL的持久旧端写栅栏。旧nginx仅代理新机；不允许维护自动恢复后仍向旧库成功发布。TEST恢复前固定新端点和hostkey，并核对实际容器env而非只改Mac alias。
- [ ] 在切DNS前做一次现存冻结原生包的安全幂等/读取验证，保证TEST/PROD原生权威与进度一致；禁止为了演示重译/重导/伪造新谱。受限只读receiver验证不写新DB记录。

### Task 5: DNS/入口与真实验收

- [ ] 使用已有授权DNS API/控制台修改 modelstella.com/www 所需记录183.169→177.254，记录provider、旧新值/TTL/时间。host nginx另有 pitch-api-staging、lobby、ranked.modelstella.com；逐一核实其A/AAAA/CNAME实际指向与迁移依赖，给root精确现有记录和必要动作，未脱离旧IP则不能can_retire_old=true。没有权限则立即向root提供具体动作并继续其它恢复，不读Google密码文档或绕身份验证。
- [ ] 旧入口停止直接服务旧DB，保留host nginx代理新站处理DNS缓存流量；验证代理不会循环、Host/forwarded headers/WS/TLS正确，旧地址不能继续写旧库。旧数据库保持停写保留备份，不能有两个独立接受写入的PROD。
- [ ] 公开DNS多resolver确认新IP，实际 HTTPS/WS/AI/SSO/Galaxy棋谱/报告/媒体/管理/平台/旧kifu/预约路径逐项验收；TEST真实receiver目标及新hostkey生效，小时调度/预算/队列控制前像恢复，RK只读请求确认仍可用。
- [ ] 独立只读最终审核检查真实数据、所有服务、端点/防火墙与writer，无旧IP/VPN隐藏依赖；记录已验/未验和 `can_retire_old=true/false`。旧机删除/退订仅用户明早另行操作。

### 回滚规则

- [ ] 新机对外写入前任一失败：停止新机写者/新VPN，恢复旧入口/worker/TEST控制前像，保留新机供排查，DNS不切。
- [ ] 新机开始接受写入后任一失败：先封闭所有写入口与双端worker，不直接把DNS/TEST指回陈旧旧库；从新权威数据库及媒体一致导出回旧端或修复新端，核对后才恢复单一写者。保留所有原包/receipt和审计，不删除迁移数据。
- [ ] 无论成功或失败，维护必须由当前owner核实控制行/锁/正在运行任务并恢复或明确移交，任何容量/网络/model中断不允许静默遗留暂停。

**完成标准：** 所有原现役功能和数据已恢复、唯一写者和TEST/RK依赖切换有实证、公开域名实际到新机、离旧机最终备份完整、旧机无业务依赖；任何一项未证则 `can_retire_old=false` 并列明确剩余步骤。
