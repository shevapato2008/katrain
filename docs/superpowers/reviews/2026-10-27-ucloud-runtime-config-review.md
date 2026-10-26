# UCloud runtime replay 独立审核

**Decision: Approved — 已恢复数据卷后的隔离服务重放及受门禁控制的激活工具。** 当前脚本没有必须修改项。此结论允许继续镜像导入、私有备份传输和隔离恢复准备；不代表最终数据、VPN、入口切换已获运行实证，也不授权将门禁模板直接改为全 true。

审核日期：2026-10-27。审核仅读取本地文件、执行离线 dry-run 和内存反例；没有连接服务器、Docker daemon、数据库或模型服务。唯一写入为本报告。

## 审核对象

- 公共脚本：`/private/tmp/ucloud-migration-runtime-replay-20261027.py`。
- 私有入口：`/Users/fan/.local/share/ucloud-migration/2026-10-26/runtime-replay/runtime_replay.py`；两份代码逐字节相同，SHA256：`1f863afc0e53b621832ca742713ed06c511b6ea421671bc2216d25f40d7af1df`。
- 同目录的 manifest、gate/媒体覆盖模板、exports、原网络快照；权威依据为私有原始 `docker-containers.private.json` 和 `runtime-inventory/old-runtime.private.json` 中的原始 network inspect。
- 本次只审实际运行配置与 operator，不扩展到业务源码、GUI 全状态或整站安全审计。未输出或复制秘密值。

## 已核对事实

- 20 个原始 inspect 中恰为 17 running、3 exited；manifest 恰含 17 个在线容器、16 个不可变 image ID、7 个网络、8 个卷、4 个仍需存在的 bind。三个 exited 初始化/导入任务明确排除，不能被选中或由依赖展开启动。
- 原始 source/network 快照完整性匹配；逐容器对比确认 Env 的完整顺序与字面值、命令、用户、工作目录、Healthcheck 等 Config 字段，以及 HostConfig 的挂载、资源、权限、GPU、最终 restart/ports 均保持原值。受控差异仅为固定 image ID、去除自动生成旧 hostname、去除活动 Compose ownership labels 和空 DNS/ContainerIDFile 字段。网络创建参数和 endpoint 字段与原始 inspect 一致。
- 两个 GPU engine 保留原来的同卡 `nvidia Count=1`；所有容器原 `Privileged=false`。没有增设 producer、LLM 或第二套同步任务。
- PortBindings 以实际 HostConfig 为准。staging 只移除 `10.8.0.3` 绑定并保留 loopback，restart 统一为 `no`；activate 恢复原绑定和各自原 restart，包括 Pitch 的 `no`。不存在 wildcard/public 扩张。
- MinIO 原值是 VPN `10.8.0.3:9000` 与 loopback `127.0.0.1:9001`。可选 patch 仅追加 `127.0.0.1:9000`；不会开放公网 9000 或改 bucket policy。三个媒体环境覆盖仅允许已约定的旧 preview URL/origin → modelstella 值，默认关闭。
- 私有根与 replay 目录均为 0700，replay 文件均为 0600。脚本输出仅含容器、镜像、端口、网络和操作元数据；Docker 错误正文与未处理异常详情不会输出。

## 离线验证

独立运行 **26 项检查，全部通过，退出码 0**。验证进程阻断 socket 与 subprocess，门禁检查中的 `ip` 结果仅用内存数据替代，没有实际 Docker 或主机查询。

覆盖：默认/activate/媒体 patch 的 dry-run 无 socket/process；拒绝 excluded 容器、staging cron/worker、未显式允许的 isolated web；拒绝 apply 缺 phase、缺显式 container、错误本机 hostname；拒绝全 false 模板、缺 gate、缺恢复证明、缺 isolated web/Pitch schema/Pitch alembic/media/最终切换门禁和 manifest 不匹配；17 份原始 inspect 按 staging 差异调整后通过既有容器检查，owner/spec/env/port 漂移均被拒绝。内存比对不是实际 Docker create/inspect/start 回读测试。

## 执行边界

1. **现在可先执行：** 按原不可变 ID 流式导入必要镜像、传输已完成并校验的私有备份及文件、创建恢复所需目录和卷。无需等待最终 cutover gate；不得把 partial dump 当成功，PG 不在线硬拷物理目录。
2. **初始逻辑恢复：** 当前 operator 在 PG create/start 前也要求 `RestoredVolumes`。新空 PG 卷需要单独受控的本机隔离 bootstrap/restore 步骤，按对应 major 启动、恢复 globals/全部业务 DB、核对 owner/sequence/数据后，再由 operator 接管。不能把空卷虚假填入 `RestoredVolumes`，也不能据本工具 Approved 推断该 bootstrap 已审或已执行。
3. **隔离服务：** 卷/bind 已实际恢复后，仅用明确 container 选择运行 staging。默认只允许 DB、MinIO、web GPU 启动。web/platform/API 另需 `--allow-isolated-web` 和真实隔离证明；Pitch API 还需验证 schema=head 且原 alembic 命令无变更。公网 ingress、receiver、背景 writer 和旧 VPN identity 必须仍禁用。gate 是操作者对事实的声明，代码不能替代事实验证。
4. **媒体 patch 一致性：** 若采用这次白名单 patch，应从相关容器第一次 staging create 起使用同一有效 manifest/flags，并将 gate digest 绑定有效 manifest。已按 base manifest 创建的 staged 容器会拒绝直接以 patched record 激活；这是配置漂移防护，不能手动伪造 spec label 绕过。新 host nginx `/media` 路由仍需另行审阅/验证，保留原匿名 bucket 权限。
5. **最终激活：** 必须先证明旧业务写者持久隔离、最终一致性数据恢复并验证、VPN 单一所有权完成迁移、入口切换获准，然后才用 activate 的显式选择。staged → final 必须使用 `recreate-final`，随后显式 start；不会因 recreate 自动启动。恢复原 VPN 绑定前会检查本机地址。旧端写栅栏、TEST receiver/hostkey、DNS/旧 nginx 转发与实际 HTTP/WS/媒体/数据/健康验收仍由控制者完成。

新机实际 Engine 1.54 的 create/inspect/start 回读、数据库恢复正确性、媒体 Range 与各服务健康尚未在本次离线审核中验证；执行阶段若遇到严格配置回读不一致，应停下核对具体字段，不放宽检查或自动覆盖已有容器。最终切换证据齐备前仍应维持 `can_retire_old=false`。

## 追加：实际 MinIO create 后的 OOM 字段规范化（2026-10-27）

**Decision: Approved。可使用修正版按既有 staging 门禁继续 MinIO start。** 本结论不改变前述最终激活门槛。

实际 Docker 29 create 成功后，原 `HostConfig.OomKillDisable=null` 被回读为 `false`，旧的逐字面比较因此拒绝 start。此次按控制者授权，仅通过既有 `new-direct` SSH Master 读取一次新机 `katrain-ucloud-minio-1` 的 Name、State.Status/Running、OomKillDisable 和三个 operator label；未读取 Env、修改文件或启动容器。独立观察为 `Status=created`、`Running=false`、`OomKillDisable=false`，owner=`2026-10-26`、phase=`staging`、spec=`9630045dd110e797215927a194136f4fca7fa2dc1d1e874684a062798faa1cac`。

修复仅在 `verify_existing` 的该字段比较中将两端各为 `None` 或 `False` 视为等价；使用 Python identity 限定，整数或字符串不会混入。`True` 仅能与原本也是 `True` 的记录精确匹配；本次原值为 null，因此观察到 `True` 仍拒绝。其它 HostConfig、Config、镜像、网络和 ownership/spec 校验保持原逻辑。

公共与私有脚本逐字节一致，修正版 SHA256 为 `c709bbd26692072c987136764fdb4ca33c9b34c238ab5b10b4371beacc9688a1`。将这唯一比较代码块逆替换为原块后，整份脚本 SHA256 精确还原为上节已审版本，确认没有其它变更。原 source/manifest/payload 仍保留 literal null，现有 created 容器的 spec 与有效媒体 patch 后 staging payload 一致，无须重写 manifest 或标签。

本次只执行 **12 项聚焦检查，全部通过，退出码 0**，未重复整套 26 项：None/False 四种配对、原 True 精确配对、null/True 与 True/False 拒绝、整数 0/1 和字符串拒绝、Privileged 漂移和 spec 漂移拒绝。implementer 另存的 `runtime-replay/oomkill-normalization-evidence.metadata.json` 记录完整真实 inspect 的 `verify_existing=PASS`；本审核独立核实的是上述真实白名单字段、标签与唯一代码差异。没有新机写入，也未代替控制者执行 start。

## 追加：第二个 GPU HTTP 服务的 staging 资格（2026-10-27）

**Decision: Approved。** `STAGE_START` 仅增加精确名称 `katrain-ucloud-katago-cron-1`，用于业务切换前验证原单 V100 上两个 GPU HTTP 服务。manifest 确认该容器的命令为 `python3 -m realtime_api.main`，原镜像为 `sha256:b242fd2a379b28b7dda5cf965e41230324bc825e7d23cd4aa1c0c81f7a16798e`，原 `nvidia Count=1` 保持不变；它与业务 writer `katrain-ucloud-katrain-cron-1` 是不同容器。本节将前述 staging GPU 范围从仅 web engine 补齐为原有两个 engine。

公共与私有脚本一致，最新 SHA256 为 `0003abe81a98a85c060535ec86d3a06874bd3c8f6a40a2fe28121a7c770a6f6e`。逆替换这一行后，整份脚本精确还原为上节已审 `c709bbd2…` 版本，确认门禁、资源、manifest/spec 校验和其它行为均未变。

独立执行 **3 个离线 CLI 资格用例，全部通过**：`katago-cron` staging start dry-run 退出 0；业务 `katrain-cron` 和 `pitch-booking-worker-1` 均拒绝、退出 2。测试期间 socket/process 入口阻断，未连接或修改 host/Docker，也未重跑之前的完整检查。实际 apply 仍须满足原 staging 门禁、数据/bind 恢复、明确容器选择与既有配置校验。

## 追加：immutable image 继承 Compose 标签（2026-10-27）

**Decision: Approved。可按精确 guard 重建三个 Created/stopped 容器后继续隔离启动。** 此审核只覆盖标签继承修复，没有放松启动或最终切换门禁。

实际 roundtrip 中，`pitch-booking-api-1`、`smartbox-kifu-api-1`、`smartbox-kifu-api-b-1` 继承了源镜像内的 `com.docker.compose.project/service/version`，因此整张 Labels 严格比较拒绝启动。其余五个应用标签与 spec 相同，控制者已单独启动；不得将它们纳入重建。独立读取原始 image inspect，确认仅三个精确在线 image ID 内嵌这三个 Compose key：Pitch API 的 `28f423c0…`、尚未启动的 Pitch worker 的 `47181877…`、Kifu API 共用的 `9760261d…`，完整 ID 已固定在脚本中。

修复仅对这三个精确 image ID 的 payload 显式设三个标签值为 `""`，阻止 Docker 补回旧 project/service/version 值。键仍存在，旧 Compose ownership 值为空；没有删除或忽略整张 Labels，也没有接受未知 image 默认标签。覆盖先于正常 spec 计算，因此受影响的旧 created spec 不会被自动放行。原 source/manifest 未改；owner/phase/spec/image、完整 Config.Labels 比较和所有门禁均未改。

最新公共/私有脚本逐字节相同，SHA256 为 `4f4e07fdff8a5b363f09e361e0275789f018ad047ed49af6d55b77a4d7557173`。移除新增的精确 image/key 常量、payload 覆盖两行及说明后，整份脚本精确还原为前次已审 `0003abe8…` 版本。独立验证 **8 项聚焦用例通过**：三个待重建容器的 image-default merge 模拟通过；未知 label、旧 project 值、缺少空值 key、旧 spec、伪造 owner 均拒绝。另核对 13 个不受影响容器 payload 完全相同，四个受影响 payload 只改变这三个标签及正常重算的 spec；Pitch worker 的 staging 禁止资格不变。未重复原完整检查或连接服务器。

`runtime-replay/labels-created-recreate-guards.metadata.json` 中仅列上述三个 Created/stopped 容器，名称、具体 container ID、精确 image、旧/新 spec 已与对应 payload 核对。控制者删除前须重新读取并确认 ID、image、owner、phase、旧 spec、`Status=created`、`Running=false` 全部匹配，且只允许 `v=false&force=false`。任何字段改变即停止；不得删除卷、五个已运行应用、四套 PG、MinIO 或两个 GPU engine。重建后的实际 Labels 回读及启动健康由控制者继续验证，审核本身没有执行删除、创建或启动。
