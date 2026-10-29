# 棋谱 prepared search 发布与回滚

本文件包含操作 runbook 和文末的实际执行记录。迁移、换包、准备和性能验收分别记录，不能据本地测试或换包成功宣称线上 ready/性能达标。原始 inspect、环境、数据库 URL、SSH key 和完整响应保存在私有证据目录，不进入 Git。

已批准的范围及语义见 [实施计划](../../superpowers/plans/2026-10-27-kifu-search-prepared-read-path.md)。本轮保留现有受信 DB owner/运维边界和业务 engine；不声称能防止持有 superuser/table-owner 身份的运维伪造派生行或关闭守卫。发现实际存在不应受信的调用方时，停止 enable 并报告具体权限事实。

本文保留早期准备窗口及验收失败经过；当前性能合同与停点以“TEST 正确性、负载和真实页面”和“实际交付记录”为准。2026-10-29 用户已将 1 QPS 20ms 改为诊断参考，并要求在实际线上 8 核机器受控验证 100 QPS 每请求完整响应 ≤200ms；旧“低过才高”和“PROD 不做 100 QPS”不再作为当前执行限制。历史失败不删除，资源配额不得静默改变。

## 固定边界与发布顺序

| 阶段 | 目标与必要结果 |
| --- | --- |
| 集成 | fetch 最新 `develop` → merge 到 feature、解冲突、聚焦验证、commit/push feature → merge/push `develop`，记录完整 SHA |
| 父仓库 | `smartbox-software/vendor/katrain` 指向已发布 `develop` SHA；仅 commit/push 父 `main` 的 submodule pointer，保留无关工作树改动 |
| TEST | `home-ubuntu`，现有 Web `katrain-web`、唯一 collector `katrain-cron`；显式迁移并确认 disabled → 新 Web / 唯一 cron 安全换包且核实 hook/signature → 有界实际 prepare → 其余验收后才 enable |
| TEST 验收 | 实际新旧语义差异 0、完整响应错误 0、1 QPS p95≤20ms、100 固定到达 QPS p95≤200ms，以及真实 Galaxy/kiosk 页面和正确棋盘 |
| 新 PROD | 仅 `ubuntu@117.50.177.254`，现有 Web `katrain-ucloud-katrain-web-1`；全部 TEST 门禁通过后，Web/receiver disabled 换版、准备/验证、原子 enable、小样本复验 |

不得连接旧 183 入口或复活退役 producer。不得以部署 feature 代替 merge `develop`，也不得以本地 fixture、SHA cache 命中、后台 proof 尚在运行或 disabled legacy 路径的结果宣称完成。保留现有三项搜索索引。PG、GPU/单 V100 双 engine、MinIO、SSO、网络、媒体挂载及 PROD 无关 cron 不重启、不改配置；不改设备模式、不重启 RK。

每次动作前 fresh inspect 实际容器、进程、engine、mounts、env、网络、命令和 wrapper 为准。旧文档、Compose 默认值和 BUILD_SHA 不能代替运行时事实。已有 [web-only operator](2026-10-27-kifu-search/operators/README.md) 仅用于 Web 阶段；它的“所有非 Web ID/image/StartedAt 不变”约束不覆盖后续必要的 TEST 唯一 cron 换版。不要用旧 `runtime_replay.py` 重放整套迁移。

## 预检和命令

准备 CLI 使用发布包中的 `scripts/kifu_prepare_search.py` 和目标现有数据库身份；显式 `--database-url` 放在子命令前，默认沿用 `settings.DATABASE_URL`。不得建立另一个 prepare engine/凭证再把业务和准备拆成两个事务。执行前只读记录当前 DB role 属性及有关表/守卫权限，隐藏凭证。

```sh
# 可选诊断；不要求重跑，不作为迁移、准备或 enable 的放行器。
python scripts/kifu_prepare_search.py plan --max-seconds 120 --sample-albums 1000
python scripts/kifu_prepare_search.py migrate --dry-run
python scripts/kifu_prepare_search.py migrate --apply
python scripts/kifu_prepare_search.py verify-schema
python scripts/kifu_prepare_search.py prepare --batch-size 500 --max-seconds 1800 --max-memory-mib 512 --resume
python scripts/kifu_prepare_search.py verify --all-coverage --compare-sample 24 --compare-queries /private/evidence/frozen-main-cases.json
python scripts/kifu_prepare_search.py enable --expected-policy-version 1
python scripts/kifu_prepare_search.py disable
```

`plan` 保持只读，不隐式创建六张表。小字段统计分别覆盖列表 visible albums 和所有详情可读 albums，包含 hidden/duplicate；另列 owner、raw、所有物理 name、alias 和语言数量。至多 1000 个 album 的相关 owner/raw 使用原 proof 做成本诊断，不 reimport、不请求 LLM/翻译。输出取样范围、估算行数、空间、RSS、时间和不确定项；它既不是覆盖证明，也不是资源验收，不以估算或缩小 sample 代替真实结果。

2026-10-28 主会话明确将只读 `plan` 采样窗口从原计划的 30 秒调整为有界 120 秒。原 30 秒窗口未通过：完成同一 1000 album、四域 6735 个物理名称的完整 proof，在一次仅作诊断的 180 秒上限进程中实际耗时 51.149 秒，进程峰值 399.95MiB。此诊断没有迁移、业务写入或 enable，也不算原 30 秒门禁通过。调整只涉及离线预检窗口；1000 样本、完整 proof、初始准备总计 1800 秒、512MiB、2GiB，以及 API 的 1 QPS p95≤20ms / 100 QPS p95≤200ms 均保持不变。历史批准计划保留原文，运行命令以本节的显式调整为准。

随后正式 120 秒采样也未通过：`e1d763a6` fresh 进程在 136.855 秒 wall 后以预算超时返回，未得到完整资源估算。主会话据实际成本正式采纳运营调整：forecast 仅作诊断，不继续把全库 proof-reference 扫描扩建成放行器；由始终 disabled、实际有界且可恢复的 TEST 准备结果验收资源和覆盖。原 30/120 秒预测门禁均不得记为通过。该取舍经独立 Astra CODE/OPS 核对，保留迁移、writer、资源、完整语义、API SLO 和 TEST→PROD 顺序。

成本模型保留原隔离 PostgreSQL 15.15 机械 canonical fixture 的行和索引成本基础。2026-10-28 另用现有已验证 fixture 经原 Core 生成的有限 primitive rows，在专属隔离库的自有 schema 中按每类 1000 行校准；该 schema 已删除，业务库未安装准备表。`pg_total_relation_size` 实测 raw member 的 black/white、event、selected_event 分别为 557.056、245.760、262.144 B/行，包含 heap 和全部索引。names/displays/dependencies 同次测量为 425.984、212.992、294.912 B/行；取较保守的既有基数，按实际 Text UTF-8 与该 Connection 的 JSON serializer（含 nullable JSON）宽度调整。fixture 仅校准结构成本，不能代表真实库密度。

诊断按原构造函数的 live member 主键、去重的 `(target,input)` 依赖和每 album 一份 display 依赖计量；完整 scope 与 1000 album 内的密度分开，不把已包含样本外成员的完整 scope 再按 album 倍数放大。保留明示余量，分列 proof、构造、display 和写入。PG `EXPLAIN ANALYZE` 与 Mac 客户端 process CPU 仅是有标签的校准估算；SSH wall 不冒充容器本地耗时。诊断失败和不确定项保留，实际六关系含索引总空间验收上限仍为 2GiB。

`migrate` 默认 dry-run。只有明确 `--apply` 安装独立 MetaData 的六张派生表、默认 disabled singleton 和普通 DML/TRUNCATE 失效守卫；重复执行保留既有 checkpoint/开关。显式迁移外，Web startup 和 plan/prepare/verify/enable 均不建表。先核对迁移计划、全部输入表和守卫定义，再检查 `verify-schema` 实际结果，不能仅看表名存在。

PostgreSQL `migrate --apply` 在同一迁移事务、首个 DDL 之前设置 `SET LOCAL lock_timeout='1000ms'`、`statement_timeout='30000ms'`。旧 collector 正在发布或源表锁忙时，迁移有限等待后整事务回滚，CLI 返回非零；不会留下半建表/守卫或半启用状态，也不 kill writer、自动重试。记录 busy 后保留现有服务，等待 writer 自然空闲，再显式重试迁移；不得把 DDL 无限排队当作 drain。首次安装仍默认 disabled，重复迁移失败保留此前已提交状态。

`prepare` 的 state.phase/cursor 与该批结果在同一 Connection/事务提交，每批至多 500，保留每 SQL statement 30 秒 timeout、lock timeout 1 秒和合作式耗时检查，不承诺 Python 构造或锁墙钟每批严格 30 秒释放。500 owner 的完整 finite closure 可能包含更多 album，不截断 proof。沿用名称 writer advisory lock `720220261002`，再取 publication lock `720220261003`，再锁源表、singleton 和目标；不得倒序或另开连接嵌套争锁。所有派生结果、cursor 与最终 reconcile 写完后，在该 Connection commit 前检查实际进程峰值、六关系含索引空间和截止时间；失败回滚本批，保留已提交 checkpoint。遇活跃 writer/锁超时立即让出，无自动重试或第二 collector。初次覆盖未完成时 writer 保留 dirty；覆盖完成后即使 disabled，正常 writer 仍维护派生结果，因此实际新包/hook 门禁不能省略。

实际准备只在独立的一次性纯 CLI 容器中运行：不可变已发布镜像、512MiB 生效的 Docker memory 限制、memory-swap 等于 memory（无额外 swap）、无自动 restart、不启动 Web/cron/collector。不得在常驻 Web/cron 容器里执行这次准备。原累计 1800 秒窗口已失败，后续累计 3600 秒窗口又在未全覆盖时触发2GiB门禁；本次必要新policy重建按下述明确批准的累计10800秒上限执行，每次 CLI 仍至多1800秒，跨 `--resume` 扣除全部既有耗时，不能通过重启重置预算。OOM、截止终止、连接丢失或未知 COMMIT 均算失败、不 enable。若终止发生在 COMMIT 附近，本批可能已完整提交；恢复只能读 DB durable phase/cursor，并确认自有后端事务和锁已释放，不能凭最后客户端日志重放。只终止自己的准备容器/连接，不触碰既有任务。

2026-10-29（北京时间）主会话针对实际进展明确批准一次额外有界 1800 秒离线准备窗口，并经同一独立 Astra OPS 增量审核 Approved。原窗口实际累计 1802.618804684 秒，保持失败记录；累计上限修正为 3600 秒，旧耗时保留，余额 1797.381195316 秒。继续同 `c83ec948` policy 的原 `--resume --batch-size 500`（已进入 raw_event，仍至多500），不重建或改写 signature/cursor，不减数据或完整 proof。首次续跑 CLI/外部截止采用1792秒，为监督及停止保守预留约5秒；后续显式续跑只从累计余额扣取，不能再填1792或1800重置。预留不是清理时长保证，实际停止/事务释放仍如实计账，超过3600仍失败。512MiB/no-swap/no-restart、2GiB观测/完成门禁、原锁、statement30秒/lock1秒、disabled及TEST先于PROD全部保持。最终RSS未观察、覆盖/语义/SLO未通过的状态保留，不能把此运营窗口修正称为原1800秒门禁通过。

500批续跑实际7批提交后触发合作式30秒限制，非OOM，峰值RSS279945216B；新增实际154.966459037秒计入，累计1957.585263721秒，余额1642.414736279秒。主会话明确授权同policy从durable cursor70023（实际19800/52229 raw_event owners）以200批继续；仅若200再次遇同一种合作式30秒错误，且无OOM/新异常、自有事务锁已释放，授权一次缩到100续跑。每次仍扣除全部实际用时和监督余量，没有无限自动重试；其它新风险先停止。

200批实际171批提交后因六表物理空间2148065280B超过2GiB而停止，非OOM；已完整准备names303783/members811286，但display仅8000行、1600/176907个album。依赖5548474行占1581629440B，是本次已实证的主要空间成本。该次实际991.467373604秒计入，累计2949.052637325秒；空间/全覆盖门禁未通过，不启用、不推进PROD。

主会话据上述事实保持2GiB/512MiB，授权两个最小存储收敛：全部非generic名称/alias输入按(kind,owner_id)取完整UNION，存于obsolete删除、upsert并重读current后仍存在的最小prepared_name.id；display只删除已由同owner watch覆盖的逐source_name附边，其余source/selection/album/negative inputs完整保留。代表行的立即invalid数量不再等于整个受影响cohort数量，HTTP仍由ready/dirty总闸阻断，完整owner重证后才能ready。没有新schema/targetkind、reader分支或弱化proof/hash。

新policy必须按原guard完整重建。主会话为此必要重建再明确授权一次有界3600秒窗口，累计上限7200秒；旧2949.052637325秒完整保留，重建前余额4250.947362675秒，每次CLI仍≤1800秒，实际reclaim/停止/监督耗时也计账。普通相同合作式30秒原因的100/200参数选择只在原≤500范围基于事实处理，不无限重试。512MiB/no-swap/no-restart/2GiB、完整语义/writer/API SLO和TEST→PROD门禁均不变；本轮CODE/OPS增量审核通过后才执行。

由于DELETE不缩物理页，重建前允许一次明确的TEST派生缓存reclaim：仅在disabled、未完成覆盖、自有CLI已停且持既有name+publication锁及有限SQL/lock timeout时，在同一Connection事务对members/dependencies/displays/names明确各写 `ONLY`，以 `CONTINUE IDENTITY RESTRICT` 截断四表。四表必须全部在明确列表中以满足内部FK；不用CASCADE/RESTART IDENTITY，不含继承子表，不动business、receipts、sources或schema。随后调用现有 `begin_full_prepare`，由原full协议转移已知collection `*`义务并记录consumed count，普通dirty全字段hash守恒；不手写signature/cursor。记录精确before/after，失败回滚，未知COMMIT先读durable状态和自有backend，不盲重跑。按[PostgreSQL 15官方语义](https://www.postgresql.org/docs/15/sql-truncate.html)，该操作可随事务回滚、会取目标表排他锁且不是MVCC-safe；不能声称旧prepared快照继续可读。它仅用于从未启用、原reader仍disabled的未验收派生缓存，不能称为清除超限后原算法已经达标。

2026-10-29（北京时间）`381a0439` 的完整实际准备已完成：176907 albums、303783 names、811286 members、884535 五语 displays、3820974 dependencies，dirty0；六关系含全部索引1824768000B，完整覆盖校验通过。成功尾段进程1251.284330769秒、峰值RSS200044544B，前一段1800秒截止的最终RSS仍未观测；所有准备进程均受512MiB/no-swap约束，未发生OOM。累计实际6006.474458434秒，旧1800/3600失败记录全部保留。中间一次续跑遗漏既有host-gateway映射，connect阶段即失败、未提交，2.128119637秒也计入；恢复原参数后继续，不修改数据库URL、DNS或服务配置。

同版既有 native publish/replay/undo 测试在独立PG owned schema实际通过，原receipt/artifact SHA和ready断言保留，schema已删除。24组真实业务完整JSON在同一只读RR快照全部相等：前12个不同棋手、五语、页2、4个实际ID及合法alias；张涛总488条且含27条实际可见raw。随后CLI全覆盖校验、原子enable及一次同image Web自然exit0冷重启通过。但正式1QPS/120次完整响应未达标：错误及语义差异0，入口120/120，ASGI p95/p99=513.011/538.935ms，HTTP完整body p95/p99=515.809/542.295ms。低负载失败，未执行ramp/100QPS，PROD未部署。初次采样器因Python3.10缺少asyncio.timeout、0请求发出，单列工具失败；仅在独立采样进程使用已安装的async_timeout5.0.1兼容shim（成功/超时/取消三断言及Astra CODE/OPS通过）。实际Kivy日志formatter吞掉首个JSON冒号，离线仅恢复该固定前缀；原日志及两份SHA保留，所有metric数值/request id原样，未替换计时口径。

实际只读SQL/EXPLAIN定位到三个无关candidate扫描及finite raw/canonical OR计数全表扫描。最小reader修复只增加既有alias kind索引前缀、空physical selected_raw的EXISTS返回、未消费generic延迟求值，以及只针对有限canonical+raw OR的COUNT去重UNION；page/order/preview/report/rank不动，无新索引/schema/cache。实际相同快照朴廷桓完整1587条COUNT从375ms降至2.504ms，张涛完整488条从383ms降至1.181ms，稳定page相同；这些是SQL诊断，不是修复后API SLO通过。

主会话明确条件授权本次必要新policy重建再加3600秒，累计上限10800秒，旧6006.474458434秒保留、重建前余4793.525541566秒；每CLI仍≤1800、512MiB/no-swap/no-restart/2GiB及全部正确性/主SLO不减。该缓存曾启用并已complete，不能复用“从未启用”的旧reclaim前提：先显式disable（实际postcommit观测UTC2026-10-29T00:05:58.696286+00:00），自然排空所有此前事务；同原writer锁/Connection中检查全session可见权限、track_activities=on且无disabled session，清当前统计snapshot后确认business DB所有xact_start不晚于post-disable时点的非self事务为0。存在旧RR/事务即拒绝，不kill、不自动重试。其后才允许同样ONLY四派生表CONTINUE IDENTITY RESTRICT及现有begin_full_prepare协议，普通dirty hash守恒、known*正规移交、旧signature留存，绝不手改signature/cursor。disable后新HTTP快照只走legacy，不会新增旧prepared读；此边界已获本轮独立Astra OPS增量Approved，私有脚本SHA256为fae25ea4fa986e3526b841daea0a984551be427dfe80f47ea4432a6a21581377；执行前仍fresh核对实际前提。新Web/唯一新cron实际同policy后按原guard全重建，重新完整覆盖/24语义/冷低负载，低过才高。

执行前 fresh 核对 PG 数据与 WAL 所在磁盘的充分余量、六关系现状及 reader disabled。512MiB 容器限制不涵盖 PG/WAL；2GiB 是执行中的观测停止阈值和完成/enable 验收上限，不是物理配额。回滚不会自动缩掉 relation EOF 残页；失败后仍按真实 `pg_total_relation_size` 和剩余磁盘记录，超限继续保持失败/disabled，不自动清理、重试或放宽。只有真实资源、完整覆盖、24 个实际语义比较和新 writer 验证通过，才进入既定 enable/API 验收流程。

普通增量准备遇到 `input_key='*'`（如 TRUNCATE）的 collection invalidation 必须拒绝完成，操作入口是显式完整重建：

```sh
python scripts/kifu_prepare_search.py disable
python scripts/kifu_prepare_search.py prepare --full --batch-size 500 --max-seconds 1800 --max-memory-mib 512
# 如中断，只继续 checkpoint，不再传 --full：
python scripts/kifu_prepare_search.py prepare --resume --batch-size 500 --max-seconds "$remaining_seconds" --max-memory-mib 512
python scripts/kifu_prepare_search.py verify --all-coverage --compare-sample 24 --compare-queries /private/evidence/frozen-main-cases.json
python scripts/kifu_prepare_search.py enable --expected-policy-version 1
```

`remaining_seconds` 必须由该次验收私有证据中累计实际 wall 扣除得到，非正则停止，不能在 resume 时重新填 1800。`--full` 与 `--resume` 互斥；enabled 时 `--full` 拒绝，绝不暗中关闭开关。第一批在既有 writer 锁、同一事务中将启动时已有的 `*` dirty 转为持久的完整重建义务，保留普通旧 dirty，关闭 ready/initial coverage、重置 phase/cursor，再写入该批结果；只有整批 commit 后才算开始。中断用 `--resume` 不重复 reset，预算不变。重建期间新业务变更保留 dirty，在完整扫描后处理实际闭包；若期间又出现新 `*`，拒绝 complete，须再次显式 `--full` 重新开始，不能静默清除/无限自动重跑。没有新增表、业务审批改写或预算扩张。

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

旧 scheduler 的 `shutdown(wait=False)` 会取消 interval task 和 loop，不能对活动 job 直接 stop/SIGTERM 后假称完成。TEST 采用自然全 idle 的短窗口作为观测维护边界，不扩建计费/Web admission gate，不持阻塞队列写入的锁。它不承诺防止未来恶意调用或持续 submit。采用以下有限操作；任一条件无法满足就报告实际 blocker，保留旧 writer/disabled，不 force-kill、不启动第二 collector。

1. 私有保存全部既有 `cron_job_controls` interval 行的原像（含不存在的行）、命令队列及容器/进程配置。用现有 interval pause control 临时暂停启用的 interval jobs，按完整原像 CAS 写入；遇外部改动立即停止，不覆盖。记录临时变更的精确 postimage，恢复时仅在仍等于本次 postimage 时还原原行/删除本次新增行，保留此前已暂停状态。暂停不取消当前 run，也不暂停常驻 loop。
2. 等待 controls poll 已实际观察暂停，旧 ingest 和所有既有 interval run 自然结束，fresh 检查 interval running=0、`cron_job_runs` 无活动 run、`cron_job_commands` 无待领取命令，结合进程/数据库活动确认没有尚存发布线程或事务。不要改 run 状态/receipt/heartbeat 来制造空闲；不手工终止旧 run `82639` 或后来实际活动 run。
3. 对两个常驻 loop 观察真实、短暂的全部 idle 窗口：至少两轮新鲜 heartbeat 的 process identity 一致且 in-flight=0，相关 analyze/report/live 队列的 queued/pending/running/authorizing 均为 0，interval running 仍为 0，数据库无在途 claim/写事务。记录旧 cron full container ID、StartedAt 和各轮计数；一次零计数不构成窗口。出现新任务即放弃本次候选，不强停。
4. 在旧 run 自然释放后，从实际目标库、实际 stage 取得原 collector PostgreSQL session advisory lock（`kifu_ingest.LOCK_KEY`）及原 stage `staging_writer_lock`，由同一个维护进程持有到旧进程退出及新配置就绪；锁不可用则有限退出。持锁后，在同一次远端操作中立即复核上述全部计数与旧 cron full ID/StartedAt，任一变化即放弃候选。仍满足窗口才仅向核对过的旧实例发送 SIGTERM，等待自然 exit 0 并确认没有遗留写线程；不用 `docker stop` 的默认超时 KILL 路径，不追加 SIGKILL。若退出未完成，保留现场、报告具体阻塞，不以超时升级信号。这两个原锁保护 ingest/stage writer，不能当作 loop 或未来 submit 的完整 fence。
5. 不要为了 drain 对 loop 队列表持 `SHARE` 等阻塞写锁。旧 async loop 会同步执行 SQL，阻塞的 UPDATE 可能卡住事件循环，反而使 SIGTERM 无法完成。持续流入或无法可靠保持自然窗口时停止换版，不扩建产品准入 gate，也不取消活动写事务。
6. 只有旧实例自然 exit 0 后，fresh CAS 核对原 env、mounts、stage/key/host pin/预算和完整配置，只将唯一 cron 切到已发布不可变新 image/代码 pin。保留原启动/调度设置，新进程不得与旧 collector 并存。按新包实际启动需要有序释放维护锁，确认新进程沿用原锁且只有一个 collector；核对业务任务无新增 cancel/fail/retry 异常。原配置及所有 interval 控制行前像按 CAS 精确恢复，不留下临时暂停，不覆盖管理员新改动。新 cron 原有 startup 首轮任务照实记录，预算保持原值，不额外发 run-now。
7. 核对新进程实际加载的 hook、policy signature 和原 DB/连接边界，记录旧/新 ID/image/StartedAt/代码 SHA，以及确实保持的配置。不能把只更新 Web、只检查磁盘 SHA 或新 subprocess 导入成功视为常驻 collector 已换版。保留自然下一轮运行、心跳与唯一实例证据。

本 runbook 不声称已取得安全窗口。主体代码完成后，最后一轮 Astra 整体 diff 审核包含本节 runbook，不为此增加产品 gate；若持续没有安全窗口或 Astra 拒绝该操作边界，主会话报告具体 blocker，保持 disabled，不伪称已建立完整 fence，也不自行扩大成全站调度平台改造。

## TEST 正确性、负载和真实页面

先显式 migrate 并确认 disabled，再安全换包新 Web / 唯一 cron 并核实实际 hook/signature，然后分批初始准备和真实资源验收。经真实新 cron/人工 CLI 入口，使用隔离或已明确批准的小范围 TEST 包验证正常发布、幂等 replay、undo/恢复，业务 receipts/images/hash 语义不变，dirty 同事务消费、ready 持续正确。不得为验收撤销无关现有数据，不新增模型请求，不全库重导入。验证实际下一次 writer 仍使用新包后才 enable。

冻结至少 24 个实际主查询、至少 12 个不同棋手，包含王/柯/张涛/一力辽的实际记录、姓名 q、原 `player_id`、合法别名、同名授权、未归并 raw、五语和页2。每个姓名保留完整同名/raw/碰撞结果，不能以 ID 快分支代替自由 q。主到达分布固定 50% 唯一姓名、25% player_id、15% 别名/同名、10% 含 raw 结果的姓名；兼容赛事/日期/模糊/无条件页/无结果另列结果/耗时，不稀释主 SLO。缺实际类别时报告缺口，不用捏造 fixture 冒充生产语义。

在一个一致快照对照实际 legacy/prepared 完整 JSON，语义差异必须为 0。启用后重启一次 TEST Web，记录 ready 时间；不预热目标棋手，至少 12 个不同棋手先完成首次查询再重复。2026-10-29 用户明确更新合同：1 QPS 的 20ms 仅作诊断，不再拦截高负载/发布；保留既有 120 次低负载样本，不为此重复测量。正确性成立后，有限 ramp 10/50 QPS 各 5 秒、100 固定到达 QPS 30 秒。硬目标为实际线上 8 核机器（或明确认可的等效配置）本轮每个完整响应均 ≤200ms，错误率/语义差异 0；必须报告 p95/p99/max、>200ms 数、超时和所有慢样本，不能仅凭 p95 放行。

100 QPS 稳态计划到达 3000 次，必须在这 30 秒内实际发出并被入口接收≥2970（≥99 QPS）；未发出/超时/失败/缺响应计入失败，不能丢弃慢请求。最多 32 in-flight，积压计排队；最多额外 2 秒排空不算窗口内 achieved QPS。分别记录调度→发出、入口→last-body、完整 JSON 收取 wall time、ASGI/server total、错误及语义核对。只测 handler 或 HTTP200 的快样本无效。错误/排队急升或 writer 健康异常即止测，保留已观察结果，不扩大样本寻找好数字。

2026-10-29 的实际 fd62 ramp 证明单 Web Python 进程在 50 QPS 下饱和，因此局部增加固定 4 个 spawn 读进程，只服务默认 server/PostgreSQL 的 Kifu list。每个子进程自建同角色 Engine/Session、pool_size=1、max_overflow=0；执行原 `read_album_page`、只读 RR 及完整 report/rank/当前页 SGF 绑定，返回完整 JSON bytes。主 Web 仍唯一管理对局、lobby、matchmaker、engine，不改全应用 worker 数。总 admission 32，取消的 HTTP waiter 不会提前归还仍在运行的底层任务额度；满额/坏池明确 503，不切换到隐式慢路径。启动时四进程完成静态 mapper/policy 握手后才 ready，不预热目标查询；自然 shutdown 等待只读任务、释放自有连接。日志记录实际 reader pool 边界/PID，不能把父 Engine 的空池或边界采样当峰值/精确等待。

该执行器、端点接缝及计时文件位于 `web/kifu` 之外；若实际 policy、writer 和 assets 字节不变，不重复准备数据或重启 TEST collector。本次所有旧失败与资源账保留。TEST 当前为 x86_64/amd64、192 逻辑 CPU，无 Web/PG quota；它仅作功能/吞吐定位，不能代表新 PROD。新 177 实际 8 CPU/64G，现有 Web 2 CPU/4GiB、PG 0.75 CPU/2GiB；四个读进程仍共享 Web 2 CPU。此处只记录事实，不修改配额或宣称达标。TEST 通过后再依据实际 CPU/队列证据，提交短时受控 8 核验收与必要资源 delta 给同一 OPS 审核；不得静默改 quota。

记录实际 CPU/RSS、workers、DB pool/等待/连接、磁盘/网络、响应 bytes/压缩和 bytes×achieved QPS 带宽；本机持久连接、公网、浏览器分列，不把本机数字称全球网络体验。最终在真实 Galaxy/kiosk 搜索、翻页、切语种、打开一盘正确棋盘，核对 SGF、黑白、赛事、轮次、来源、rank/report。只有 API 快、棋盘错误不通过。若仍未达标，记录剩余成本和未通过门禁；不自动增加 Redis/全卡片投影/资源或保留在线 proof 掩盖。

## 新 PROD 推广与回滚

全部 TEST 门禁通过后才推广新 177。按 fresh Engine inspect/web-only operator 更新 Web，保持 disabled，保留冻结迁移 manifest 及实际 mounts/env/network/资源。旧 PROD 基线 `e9b4d3ecc` 不等于 TEST 的 `06d8e732`；新六表迁移不会补旧黑/白 player ID 等三项搜索索引。两端均先运行已有 `python -m scripts.kifu_search_indexes --check`，核对实际 definition/valid/ready 和缺失计划。TEST 已有正确索引只核验、不重复重建；PROD 必要时显式 `python -m scripts.kifu_search_indexes --apply`，沿用工具的 autocommit/CONCURRENTLY 及有限锁/时间预算，再 `--check`。不另造索引工具、不在 Web startup 执行 DDL，不自动删除/重建发现的 invalid 或定义不符索引。准备仍用原目标 DB/身份、有界批次和全覆盖。

在无在途 receive/事务的自然边界检查受限 SSH/root wrapper、实际 exec 容器和 package pin。若指当前 Web，则新 Web 后的新 receive 应加载新包；若固定旧包，只更新该实际 pin，不另起 receiver 服务、不重启 PROD 无关 cron。原 `KIFU_INGEST_DATABASE_URL`、同连接写入、SSH/sudoers、producer 新 177 host pin 保持。使用合法已有包的幂等 replay 验证真实 receiver 新 hook、同签名、dirty/ready/receipt；正常发布及 undo 路径已由 TEST 同包验证，生产不随意撤销数据。观察自然下一轮合法发布；实际 writer 仍旧或无法验证时拒绝 enable。

最终在 writer 锁下全覆盖/guard/dirty/policy 校验并原子 enable，先做少量代表性正确性、读延迟、真实页面/正确棋盘复验。原“PROD 不做 100 QPS”保守边界已由 2026-10-29 用户的实际 8 核目标更新：只在 TEST 通过、同轮聚焦 OPS 审核实际资源/停止条件后执行短时受控验证；不盲直接压、不新购资源，公网 RTT/5Mbps 带宽另列。任一数据/readiness/writer 失败先 disable，再按自然安全边界回退相应 receiver/Web；单纯性能未过则保留真实结果并停止推广，不自动改资源。绝不可先退旧 writer 而留下 enabled prepared reader。保留六表、守卫、checkpoint 和证据，不急卸迁移、不修改审批事实或旧 receipts。Web 切换失败按 receipt 的真实旧/新 full ID 受控恢复，不盲重跑 apply。

## 实际交付记录（持续更新，尚未完成）

| 证据 | 实际结果 |
| --- | --- |
| feature / develop / 父 main 发布 SHA | 已发布 `4045a1534550f28a7c47783decc21f74c2a4f034` / `fd62f743ccc95d5fffcc3048ebe71517450441a2` / `e318c315c35f43130d60d0a440f8285882258f22`。四读进程实现 `a997a381f` 已本地提交、30聚焦检查通过，CODE/SPEC/QUALITY Approved，OPS/集成/部署仍待完成，不能称已发布 |
| TEST/PROD Web、TEST 唯一 cron、PROD receiver 实际 package/image/container/pin | TEST Web code fd62、image d1ede6437ac4、container 3d4b5a5d931d；同容器冷重启08:24:34Z、natural exit0/restart0。唯一cron code fd62、image132f07fd8d92、container a59875bbc295。Web14/14、cron13/13 Git runtime assets实际SHA一致。新PROD仍e9b4d3ecc/f90b1526/17运行服务，无部署 |
| 实际 policy、strict、schema/guard/角色事实 | TEST Web HTTP进程、cron startup和CLI实际signature `8ac2a746a86db0c0634adf0709227356f4ceafa24196c48853ae78f908d701f8`、strict=false，保留原受信DB owner。新executor不改此目录/资产。PROD PG15.18、六表不存在、receiver仍实际exec当前命名Web、原URL来源不改 |
| plan 诊断、实际资源、覆盖/dirty | 原30/120预测及早期1800/3600窗口失败保留。fd62最终原Core完整闭包在授权单次300s窗口内133.182s完成（之前30/60s失败均回滚）；源176949、names303848/members811506/display884745、dirty0、ready/coverage true，六表1904730112B，最终进程RSS195129344B、nonOOM，仍受512MiB/noSwap约束。累计9347.50081090536/10800s，余1452.49918909464；未重置。准备后已正常enable |
| cron 控制/CAS恢复、自然drain/原锁、唯一实例 | v7c实际cutover-verified：旧8dd08自然exit0→唯一a59875；实际startup fd62/8ac、两个同process新鲜heartbeat、完整配置和8个controls恢复，helper exit0/pending0/new_bad=[]。前v7/v7b无STOP安全拒绝并恢复；旧84397自然status errors含source91879992 quarantine，不漂白基线健康。新executor不要求重复换cron |
| 实际发布/replay/undo与完整JSON | 381既有native publish/replay/undo隔离PG通过70.139s，receipt/artifact SHA及ready原断言保留、schema已drop；后续writer/preparer核心字节未变。fd62原24查询在RO RR快照完整JSON全等；高负载前再次同快照刷新，24/24全等，manifest9c774ffd82d01cba4d098add10092c6cfbcbf6ff6a1965465561e52c25a3486b。期望/SGF私有保存，未删字段/替换查询 |
| 低负载及ramp实际结果 | 旧381低120 ASGI p95513.011ms的原合同失败完整保留。fd62低120入口120/完整JSON120、0错误/差异；ASGI p95/p9954.903/76.740ms、HTTP61.316/80.224，按新合同作诊断。fd62 ramp10QPS50次ASGI max52.560ms；50QPS250次ASGI p95/p99/max1039.627/1242.025/1298.088ms、>200=221，HTTP1252.662/1333.270/1346.904ms、>200=227。共300完整/0错差、10s实际入口264/发出278，maxinflight32，队列急升后未启动100QPS |
| TEST/PROD 实际 Galaxy/kiosk 正确棋盘与公网复验 | 主SLO未过，尚未进行最终页面/公网验收；Chrome DevTools和TEST只读本地转发已就绪，未预热目标 |
| 回滚开关与残留阻塞 | TEST当前enabled且覆盖正确，PROD未变。当前瓶颈为单Web进程并发/GIL：ramp Web持续114–129% CPU、PG74–98%，pool边界checkedout max28<60，非限额throttle。四进程实现待OPS/发布/实际验收，不能称100QPS已过。PROD现Web2CPU/PG0.75CPU限制保持不变；必要资源delta另审。TEST10800账与条件授权PROD首次准备独立3600s分账，512MiB/2GiB不减；最新硬性能合同见上节 |
