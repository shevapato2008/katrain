# 棋谱 prepared search 发布与回滚

本文件是操作候选 runbook，不是执行记录。尚未据此执行远端迁移、准备、enable 或压测，不能据本地测试宣称线上 ready/性能达标。最终记录补在文末，原始 inspect、环境、数据库 URL、SSH key 和完整响应保存在私有证据目录，不进入 Git。

已批准的范围及语义见 [实施计划](../../superpowers/plans/2026-10-27-kifu-search-prepared-read-path.md)。本轮保留现有受信 DB owner/运维边界和业务 engine；不声称能防止持有 superuser/table-owner 身份的运维伪造派生行或关闭守卫。发现实际存在不应受信的调用方时，停止 enable 并报告具体权限事实。

## 固定边界与发布顺序

| 阶段 | 目标与必要结果 |
| --- | --- |
| 集成 | fetch 最新 `develop` → merge 到 feature、解冲突、聚焦验证、commit/push feature → merge/push `develop`，记录完整 SHA |
| 父仓库 | `smartbox-software/vendor/katrain` 指向已发布 `develop` SHA；仅 commit/push 父 `main` 的 submodule pointer，保留无关工作树改动 |
| TEST | `home-ubuntu`，现有 Web `katrain-web`、唯一 collector `katrain-cron`；Web disabled 换版、显式迁移、有界准备、唯一 cron 安全换版及真实 hook 验证后才 enable |
| TEST 验收 | 实际新旧语义差异 0、完整响应错误 0、1 QPS p95≤20ms、100 固定到达 QPS p95≤200ms，以及真实 Galaxy/kiosk 页面和正确棋盘 |
| 新 PROD | 仅 `ubuntu@117.50.177.254`，现有 Web `katrain-ucloud-katrain-web-1`；全部 TEST 门禁通过后，Web/receiver disabled 换版、准备/验证、原子 enable、小样本复验 |

不得连接旧 183 入口或复活退役 producer。不得以部署 feature 代替 merge `develop`，也不得以本地 fixture、SHA cache 命中、后台 proof 尚在运行或 disabled legacy 路径的结果宣称完成。保留现有三项搜索索引。PG、GPU/单 V100 双 engine、MinIO、SSO、网络、媒体挂载及 PROD 无关 cron 不重启、不改配置；不改设备模式、不重启 RK。

每次动作前 fresh inspect 实际容器、进程、engine、mounts、env、网络、命令和 wrapper 为准。旧文档、Compose 默认值和 BUILD_SHA 不能代替运行时事实。已有 [web-only operator](2026-10-27-kifu-search/operators/README.md) 仅用于 Web 阶段；它的“所有非 Web ID/image/StartedAt 不变”约束不覆盖后续必要的 TEST 唯一 cron 换版。不要用旧 `runtime_replay.py` 重放整套迁移。

## 预检和命令

准备 CLI 使用发布包中的 `scripts/kifu_prepare_search.py` 和目标现有数据库身份；显式 `--database-url` 放在子命令前，默认沿用 `settings.DATABASE_URL`。不得建立另一个 prepare engine/凭证再把业务和准备拆成两个事务。执行前只读记录当前 DB role 属性及有关表/守卫权限，隐藏凭证。

```sh
python scripts/kifu_prepare_search.py plan --max-seconds 30 --sample-albums 1000
python scripts/kifu_prepare_search.py migrate --dry-run
python scripts/kifu_prepare_search.py migrate --apply
python scripts/kifu_prepare_search.py verify-schema
python scripts/kifu_prepare_search.py prepare --batch-size 500 --max-seconds 1800 --max-memory-mib 512 --resume
python scripts/kifu_prepare_search.py verify --all-coverage --compare-sample 24 --compare-queries /private/evidence/frozen-main-cases.json
python scripts/kifu_prepare_search.py enable --expected-policy-version 1
python scripts/kifu_prepare_search.py disable
```

`plan` 在 migrate 前保持只读，不隐式创建六张表。小字段统计分别覆盖列表 visible albums 和所有详情可读 albums，包含 hidden/duplicate；另列 owner、raw、所有物理 name、alias 和语言数量。至多 1000 个 album 的相关 owner/raw 使用原 proof 做实际成本取样；只读相关有限证明，不遍历全库 artifact/SGF，不 reimport，不请求 LLM/翻译。输出取样范围、有限成员上界、预计六表行数、空间、RSS、时间和估算依据；未观察的 closure 必须明确标出，不能把估算当覆盖证明。估计超过 1800 秒、六张新关系合计 2GiB 或进程 512MiB 时返回非零并报告，不放宽预算。取样失败或成本无法可靠估计时也停止；不以缩小 sample 掩盖超预算。

成本模型的基础系数来自隔离 PostgreSQL 15.15 上 1000 album 的机械 canonical fixture：5000 display 行含索引 925696B、9030 个共享 album dependency 含索引 2236416B、2942 name 行（含固定 generic 资产）1908736B，六表合计约 5.14MB。当前 plan 再按目标库头/中/尾样本实际 UTF-8 宽度和有限成员密度调整，显示 metadata、dependency/member 密度保留明示余量。这个 fixture 没有 raw members，不代表真实 176k 库预测或性能证明；Mac→PG 的往返耗时也不是容器本机准备耗时。若目标全库实际存在某 name family 而本次样本完全未见，返回非零/成本未充分观察；全库本不存在的 family 不成为阻塞条件。真实 TEST plan 和 actual 六关系 2GiB guard 始终必需。

`migrate` 默认 dry-run。只有明确 `--apply` 安装独立 MetaData 的六张派生表、默认 disabled singleton 和普通 DML/TRUNCATE 失效守卫；重复执行保留既有 checkpoint/开关。显式迁移外，Web startup 和 plan/prepare/verify/enable 均不建表。先核对迁移计划、全部输入表和守卫定义，再检查 `verify-schema` 实际结果，不能仅看表名存在。

`prepare` 的 state.phase/cursor 与该批结果在同一 Connection/事务提交，每批至多 500，单批最多 30 秒 statement timeout、1 秒 lock timeout；命令总截止 1800 秒不因换批重置。沿用名称 writer advisory lock `720220261002`，再取 publication lock `720220261003`，再锁源表、singleton 和目标；不得倒序或在已有 Session 内另开连接取锁。遇活跃 writer/锁超时立即让出并返回非零，保留最后成功 checkpoint，下次显式 `--resume`；没有后台自动重试、跨全库长快照或第二 collector。超时当前批回滚，已提交批保留。初次覆盖未完成时正常 writer 保留 dirty，最终闭包统一核对；不得半准备 enable。

普通增量准备遇到 `input_key='*'`（如 TRUNCATE）的 collection invalidation 必须拒绝完成，操作入口是显式完整重建：

```sh
python scripts/kifu_prepare_search.py disable
python scripts/kifu_prepare_search.py prepare --full --batch-size 500 --max-seconds 1800 --max-memory-mib 512
# 如中断，只继续 checkpoint，不再传 --full：
python scripts/kifu_prepare_search.py prepare --resume --batch-size 500 --max-seconds 1800 --max-memory-mib 512
python scripts/kifu_prepare_search.py verify --all-coverage --compare-sample 24 --compare-queries /private/evidence/frozen-main-cases.json
python scripts/kifu_prepare_search.py enable --expected-policy-version 1
```

`--full` 与 `--resume` 互斥；enabled 时 `--full` 拒绝，绝不暗中关闭开关。第一批在既有 writer 锁、同一事务中将启动时已有的 `*` dirty 转为持久的完整重建义务，保留普通旧 dirty，关闭 ready/initial coverage、重置 phase/cursor，再写入该批结果；只有整批 commit 后才算开始。中断用 `--resume` 不重复 reset，预算不变。重建期间新业务变更保留 dirty，在完整扫描后处理实际闭包；若期间又出现新 `*`，拒绝 complete，须再次显式 `--full` 重新开始，不能静默清除/无限自动重跑。没有新增表、业务审批改写或预算扩张。

`verify --all-coverage` 读取一致快照，检查全部详情 album×五语、所有物理名称（包括不合资格的否定记录）、aliases、有限成员/当前 scope、当前 policy 和 dirty；不把 `ready=true` 当自证。`--compare-queries` 直接使用负载工具的 `{version:1,cases:[{id,category,params,expected,...}]}` casefile，比较其前 `--compare-sample 24` 个有效 case；控制器冻结真实 params/expected，不能自动生成空 query。缺 manifest/不足 24/格式无效时 `observed=false`、非零。比较在同一个 PostgreSQL REPEATABLE READ READ ONLY Connection/Session 中先核验全覆盖/policy/dirty，再分别调用实际 `_read_prepared_album_page()` 与原 `read_album_page_legacy()`；前者只绕过 enabled 开关，确保 disabled 时仍是真 prepared 对照，绝非 legacy 对 legacy。比较完整 public `model_dump` 的 JSON、ID 顺序、total、展示/来源、分页、rank/report/preview SGF，只记录 opaque case id/category、equivalent 和两侧 SHA256，不输出姓名/SGF。存在差异返回非零；真正运行完这 24 个实际 case 前，不能称发布语义门禁通过。

`enable` 在原 writer 锁下消费最终 dirty closure，复核完整覆盖、policy version/signature、有效 schema/guard，然后仅在同一事务末置 enabled。任一失败不提交 enable。`disable` 只改 existing singleton 的 enabled，不删除业务、proof、派生结果或守卫；即使派生索引/guard 的 schema 验证不通过，仍允许用既有 singleton 关闭读取开关。

## 实际 writer 和策略包门禁

| Writer | 必须保留的 engine/入口 | 换版及验收证据 |
| --- | --- | --- |
| TEST 唯一小时 collector | `cron/jobs/kifu_ingest.py` 启动时 import `catalog.publish_manifest`；使用 `katrain.cron.db.engine` / 原 `KATRAIN_DATABASE_URL` | 实际新 cron 包已加载 commit 前准备 hook；保留 stage、SSH key、日 token/budget、host pin、collector session lock、stage `.writer.lock` 和单实例 |
| 新 PROD receiver | 受限 SSH `kifu-incremental-receive` → `/usr/local/sbin/kifu-incremental-receive-root` → 实际 `docker exec` 的 `/app/scripts/kifu_incremental.py receive` | fresh 查看 root wrapper 目标；必须 exec 新 Web 的发布包/实际 pin；原 `KIFU_INGEST_DATABASE_URL` 指向同一原目标库，业务与准备同 Connection commit |
| 人工 name / event-selection apply、undo | 发布包 `scripts/kifu_name_batch.py`、`scripts/kifu_event_selection.py`，原显式 URL | 提交前调用库内 hook；不能先 commit 再外置补 prepare |
| 人工 player merge、undo / SGF import | 发布包 `scripts/kifu_player_duplicate.py`、`scripts/import_kifu.py`，原 engine | survivor/retired/token/raw/历史 slots 闭包与业务原子提交；仍在使用的旧 repair/direct SQL 只能强制失效，不冒充已适配 |

新 Web、实际新 cron、receiver 入口和 prepare CLI 必须分别输出并比对 `current_policy_signature()`，只记公开 hash。该签名包含 `web/kifu/*.py`、`data/*`、strict 设置、policy version/五语，并在进程内缓存。BUILD_SHA/镜像标签相同不足以通过：runtime-base overlay 残留额外旧 `.py`、缺失打包 asset 或 strict 环境差异都会产生不同签名。发现差异时保持 disabled、修复包内容/实际环境，再重新启动并核对；不得放松/改写签名绕过。`Dockerfile.cron` 应包含整个 kifu 包。

可在已核对的包/环境中用以下只读命令获取文件对应的签名：

```sh
python -c 'from katrain.web.kifu.prepared_read import current_policy_signature; print(current_policy_signature())'
```

此 fresh exec 仅证明该入口此刻文件/环境的签名，不能单独证明旧常驻进程已重新 import hook。Web/cron 还需受控启动后的实际进程/入口证据；receiver 要经真实受限 wrapper 的新 exec 路径验证。若无法观察实际加载的新 hook/签名，不 enable。

## TEST 唯一 cron 的自然空闲换版

2026-10-28 的 fresh 观察表明 TEST cron 不是隔离 collector：除 `KIFU_ANALYZE=false` 外，其它 interval 和 analyze/report 常驻 loop 均启用。08:33 UTC 时旧 `kifu_ingest` run `82639` 自 08:17 UTC 仍活动；当时 analyze/report 的 in-flight=0 不能证明整进程已 drain。必须重新观察，不能沿用这个历史快照。

旧 scheduler 的 `shutdown(wait=False)` 会取消 interval task 和 loop，不能对活动 job 直接 stop/SIGTERM 后假称完成。采用以下有限操作；任一安全条件无法满足就报告实际 blocker，保留旧 writer/disabled，不 force-kill、不启动第二 collector。

1. 私有保存全部既有 `cron_job_controls` interval 行的原像（含不存在的行）、命令队列及容器/进程配置。用现有 interval pause control 临时暂停启用的 interval jobs，按完整原像 CAS 写入；遇外部改动立即停止，不覆盖。记录临时变更的精确 postimage，恢复时仅在仍等于本次 postimage 时还原原行/删除本次新增行，保留此前已暂停状态。暂停不取消当前 run，也不暂停常驻 loop。
2. 等待 controls poll 已实际观察暂停，所有既有 interval run 自然结束，fresh 检查 `cron_job_runs` 无活动 run、`cron_job_commands` 无待领取命令，结合进程/数据库活动确认没有尚存发布线程或事务。不要改 run 状态/receipt/heartbeat 来制造空闲；不手工终止旧 run `82639` 或后来实际活动 run。
3. 在旧 run 自然释放后，从实际目标库、实际 stage 取得原 collector PostgreSQL session advisory lock（`kifu_ingest.LOCK_KEY`）及原 stage `staging_writer_lock`，由同一个维护进程持有到旧进程退出及新配置就绪。锁不可用则有限退出。它们防止新的 ingest/人工 stage writer，不能作为 analyze/report loop 的 fence。
4. 对两个常驻 loop 观察真实、短暂的全部 idle 窗口：fresh heartbeat/process identity、in-flight=0，相关 analyze/report/live 队列无 queued/pending/running，数据库无在途 claim/写事务，确认窗口仍持续再正常停止旧进程。此组合是可信正常调用方下的实际空闲边界，不是阻止恶意或未来生产者新 claim 的完整 fence。若队列仍在流入、存在未观测 producer 或无法可靠保持窗口，则停止换版并报告，不能把一次零计数当保证。
5. 不要为了 drain 对 loop 队列表持 `SHARE` 等阻塞写锁。旧 async loop 会同步执行 SQL，阻塞的 UPDATE 可能卡住事件循环，反而使 SIGTERM 无法完成。若正常停止未及时完成，保留现场、报告实际阻塞；不追加 SIGKILL、不取消活动写事务。
6. fresh CAS 核对旧容器/进程精确 identity、env、mounts、stage/key/host pin/预算和完整配置，只将唯一 cron 切到已发布不可变新 image/代码 pin。保留原启动/调度设置，确认旧进程确实退出且无遗留写线程；新进程不得与旧 collector 并存。按新包实际启动需要有序释放维护锁，确认新进程沿用原锁且只有一个 collector，所有 interval 原控制行按 CAS 恢复；不得留下长期临时暂停或静默覆盖管理员新改动。
7. 核对新进程实际加载的 hook、policy signature 和原 DB/连接边界，记录旧/新 ID/image/StartedAt/代码 SHA，以及确实保持的配置。不能把只更新 Web、只检查磁盘 SHA 或新 subprocess 导入成功视为常驻 collector 已换版。保留自然下一轮运行、心跳与唯一实例证据。

具体 idle 边界和有限维护操作需经本轮最小 operational review 后执行；本 runbook 不声称已取得安全窗口。若现有 loop/队列状态无法让上述条件成立，主会话需报告真实阻塞，不能自行扩大成全站调度平台改造。

## TEST 正确性、负载和真实页面

保持新包 disabled，完成显式 migrate、实际预算 plan 和分批初始准备。经真实新 cron/人工 CLI 入口，使用隔离或已明确批准的小范围 TEST 包验证正常发布、幂等 replay、undo/恢复，业务 receipts/images/hash 语义不变，dirty 同事务消费、ready 持续正确。不得为验收撤销无关现有数据，不新增模型请求，不全库重导入。验证实际下一次 writer 仍使用新包后才 enable。

冻结至少 24 个实际主查询、至少 12 个不同棋手，包含王/柯/张涛/一力辽的实际记录、姓名 q、原 `player_id`、合法别名、同名授权、未归并 raw、五语和页2。每个姓名保留完整同名/raw/碰撞结果，不能以 ID 快分支代替自由 q。主到达分布固定 50% 唯一姓名、25% player_id、15% 别名/同名、10% 含 raw 结果的姓名；兼容赛事/日期/模糊/无条件页/无结果另列结果/耗时，不稀释主 SLO。缺实际类别时报告缺口，不用捏造 fixture 冒充生产语义。

在一个一致快照对照实际 legacy/prepared 完整 JSON，语义差异必须为 0。启用后重启一次 TEST Web，记录 ready 时间；不预热目标棋手，至少 12 个不同棋手先完成首次查询再重复。主低负载 120 次、1 QPS，p95≤20ms；通过正确性和低负载后只做一次有限 ramp：10/50 QPS 各 5 秒、100 固定到达 QPS 30 秒。高负载 p95≤200ms、完整响应错误率 0，按类别保留首次样本和尾延迟。

100 QPS 稳态计划到达 3000 次，必须在这 30 秒内实际发出并被入口接收≥2970（≥99 QPS）；未发出/超时/失败/缺响应计入失败，不能丢弃慢请求。最多 32 in-flight，积压计排队；最多额外 2 秒排空不算窗口内 achieved QPS。分别记录调度→发出、入口→last-body、完整 JSON 收取 wall time、ASGI/server total、错误及语义核对。只测 handler 或 HTTP200 的快样本无效。错误/排队急升或 writer 健康异常即止测，保留已观察结果，不扩大样本寻找好数字。

记录实际 CPU/RSS、workers、DB pool/等待/连接、磁盘/网络、响应 bytes/压缩和 bytes×achieved QPS 带宽；本机持久连接、公网、浏览器分列，不把本机数字称全球网络体验。最终在真实 Galaxy/kiosk 搜索、翻页、切语种、打开一盘正确棋盘，核对 SGF、黑白、赛事、轮次、来源、rank/report。只有 API 快、棋盘错误不通过。若仍未达标，记录剩余成本和未通过门禁；不自动增加 Redis/全卡片投影/资源或保留在线 proof 掩盖。

## 新 PROD 推广与回滚

全部 TEST 门禁通过后才推广新 177。按 fresh Engine inspect/web-only operator 更新 Web，保持 disabled，保留冻结迁移 manifest 及实际 mounts/env/network/资源。旧 PROD 基线 `e9b4d3ecc` 不等于 TEST 的 `06d8e732`；新六表迁移不会补旧黑/白 player ID 等三项搜索索引。两端均先运行已有 `python -m scripts.kifu_search_indexes --check`，核对实际 definition/valid/ready 和缺失计划。TEST 已有正确索引只核验、不重复重建；PROD 必要时显式 `python -m scripts.kifu_search_indexes --apply`，沿用工具的 autocommit/CONCURRENTLY 及有限锁/时间预算，再 `--check`。不另造索引工具、不在 Web startup 执行 DDL，不自动删除/重建发现的 invalid 或定义不符索引。准备仍用原目标 DB/身份、有界批次和全覆盖。

在无在途 receive/事务的自然边界检查受限 SSH/root wrapper、实际 exec 容器和 package pin。若指当前 Web，则新 Web 后的新 receive 应加载新包；若固定旧包，只更新该实际 pin，不另起 receiver 服务、不重启 PROD 无关 cron。原 `KIFU_INGEST_DATABASE_URL`、同连接写入、SSH/sudoers、producer 新 177 host pin 保持。使用合法已有包的幂等 replay 验证真实 receiver 新 hook、同签名、dirty/ready/receipt；正常发布及 undo 路径已由 TEST 同包验证，生产不随意撤销数据。观察自然下一轮合法发布；实际 writer 仍旧或无法验证时拒绝 enable。

最终在 writer 锁下全覆盖/guard/dirty/policy 校验并原子 enable。PROD 仅做少量代表性正确性、读延迟、真实页面/正确棋盘复验，不重跑 100 QPS 压测。任一失败先 disable，明确恢复原完整 proof/慢延迟；再在相同自然空闲边界回退 collector/receiver pin 和 Web。绝不可先退旧 writer 而留下 enabled prepared reader。保留六表、守卫、checkpoint 和准备/负载证据，不急卸迁移、不修改审批事实或旧 receipts。若 Web 切换本身失败，结合 operator receipt 的真实旧/新 full ID 做受控恢复，不盲重跑 apply。

## 实际交付记录（待执行填写）

| 证据 | 实际结果 |
| --- | --- |
| feature / develop / 父 main 发布 SHA | 未执行 |
| TEST/PROD Web、TEST 唯一 cron、PROD receiver 实际 package/image/container/pin | 未执行 |
| 四入口实际 policy signature、strict、schema/guard/角色事实 | 未执行 |
| plan 估算/实际 RSS、耗时、六表 bytes、phase/cursor、覆盖/dirty | 未执行 |
| cron 原控制行/CAS 恢复、自然 drain/原锁、旧新实例证据 | 未执行 |
| 实际发布/replay/undo 与新旧完整 JSON 对照 | 未执行 |
| 1 QPS/100 QPS 完整响应、到达率、各类分位、错误/语义差异、资源 | 未执行 |
| TEST/PROD 实际 Galaxy/kiosk 正确棋盘与公网复验 | 未执行 |
| 回滚开关与残留阻塞 | prepared 尚未启用；无本 runbook 远端执行 |
