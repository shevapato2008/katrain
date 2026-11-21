# 星阵棋谱深度报告与段位修复 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal**　自动分析小时任务新收录的职业棋谱，并以现行证据规则完成历史段位修复和后续新谱验收。

**Architecture**　TEST 小时发布和 PROD 固定接收器分别在本地发布事务里准入，现有 worker 独立消费。重用同一历史段位规则和分批修复工具。

**Tech Stack**　Python、SQLAlchemy、PostgreSQL、KataGo、pytest、Docker Compose。

需求见 `docs/superpowers/specs/2026-11-21-kifu-hourly-deep-reports-and-ranks.md`。测试以基线 `3c4a4c261` 为起点。Astra Max 计划审核最多两轮，每轮处理意见后记录修改。第一轮审核增加了引擎恢复、压缩摆子、模型一致性、v3 复核和清单读取限制。第二轮审核增加了回执归属标记、完整棋盘尺寸校验和摘要来源。发布准入、worker 恢复和段位审计可以并行，文件范围互不重叠。各自验证后提交，合并审查由独立 Astra Max 负责，修订至通过。

## Chunk 1　小时发布准入深度报告

### Task 1　为新入库的本地职业棋谱建持久任务

- [ ] 加入 `tests/web_ui/test_kifu_incremental_catalog.py` 的真实发布用例。使用带有效 `RU/KM` 的合格星阵 SGF，断言启用时新增一个 `pending` job，报告所需 visits、模型、SGF 摘要和总手数准确，分析局面表为空；重复发布的回执与任务数量相同。复用原始来源、非 `19x19`、rank-only、开关关闭不新增。加一条缺参数或无法忠实复盘的用例，证明发布成功、失败原因可追踪，worker 不会拾取。运行 `python -m pytest -q tests/web_ui/test_kifu_incremental_catalog.py -k 'deep_analysis'`，确认因缺少自动准入失败。
- [ ] 在 `katrain/kifu_ingest/catalog.py` 新增可选的 `deep_analysis_model` 服务端参数，默认 `None`。仅在首次发布、完成目录修复、即将写入 `applied` 的同一事务中，根据本地 `results` 的 `(source_key, action, album_id)` 挑选 `19x19` 且 `inserted` 的规范棋谱。剔除后来标为重复的行。通过 `katrain/kifu_ingest/analysis_admission.py` 在同一连接插入 job，复用 Web 的 `KifuAnalysisJob` 表、`parse_game`、`resolve_parameters`。按 `album_id + SGF SHA + model SHA + visits` 检查现有任务。有效任务写 `pending`，已知不可分析原因写 `failed` 与错误码/概要，不排计算；报告和个人配额继续由原代码处理。现有同身份 job 保留。目录接受的单盘数据异常与数据库故障分开处理，后者仍使事务回滚，避免无记录遗漏。
- [ ] 在 `undo_publication` 已有的下游依赖检查处，明确识别仍引用待删除 album 的分析任务。撤销返回已有 `PublicationError` 路径，由现有受控维护流程先处置引用后再重试；不批量清除报告和局面。增加测试确认拒绝无部分改动。
- [ ] 在 `katrain/cron/jobs/kifu_ingest.py` 的本地 `publish` 闭包及 `katrain/kifu_ingest/orchestration.py` 验证过 TEST 回执的原生 `receive` 发布路径，按新服务端开关 `CRON_KIFU_AUTO_ANALYSIS_ENABLED` 传入准入模型。TEST 仅给启用后由小时任务首次发布、会携带原生 v3 回执的批次写入持久标记 `hourly_deep_analysis: true`，纳入原生回执、验证报告和既有哈希，旧回执重放不能补标。PROD 仅从已通过校验的原生 TEST 回执读取该标记，并同时要求本地首次插入。测试旧回执延迟送达、手工验证包、伪造顶层标记、标记真实包。`run-once`、旧回执和 rank-only 不准入。测试 `tests/test_kifu_incremental_cli.py` 和 `tests/cron/test_kifu_ingest.py` 或 `tests/cron/test_kifu_hourly_orchestration.py`，覆盖两端进入参数的权威边界。Prod 接收器使用本地 album ID，未从 TEST 读取任务 ID 或 SGF 变体。
- [ ] 更新 `katrain/cron/config.py` 和 `docker-compose.yml`。将默认关闭的分析消费者开关透传至 cron、准入开关透传至本地 collector 及 Web 固定接收器所在服务，配置固定模型 SHA，并确认候选设置与 API 的 2,000 visits 模型相同。开关关闭时旧路径行为一致。在 `katrain/cron/kifu_parameters.py` 共享职业报告模型和 visits 常量，Web 读取与准入复用；本地 collector 在预检、固定接收器在首次发布前校验准入开关和实际模型 pin，缺少或不一致时显式报错，避免悄悄漏入队。设计仍使用现有调度器。
- [ ] 在新准入中检查完整 `SZ` 声明。普通 `19`、合法的 `19:19` 及项目原有缺省 19 路径可用，矩形如 `19:13` 或其它棋盘尺寸记待核。覆盖 `B[aa]` 在矩形盘被错误包装成 A19 的回归。
- [ ] 完成发布准入对应测试后提交。

### Task 1b　续算暂态引擎故障

- [ ] 在 `tests/web_ui/test_kifu_analysis.py` 先复现 worker 遇到超过三次临时错误后无法续算。在 `katrain/cron/jobs/kifu_analyze.py` 区分 httpx 网络/超时、429 和 5xx 等暂态故障与请求、深度、参数/模型等确定性错误。暂态失败保留已算局面，让同一个 job 回到 `pending`，用单 worker 的有界退避冷却 KataGo 请求。恢复后从连续前缀继续。确定性错误保留原失败上限，手工任务及非本次入口原有职能继续可用。保留已有优先级和唯一在途限制。
- [ ] 测试真实入库可接收但 `parse_game` 无法忠实处理的压缩摆子，例如 `AB[aa:bb]`。准入解析在无法忠实代表此开局时写明待核原因；如复用共享 SGF 解析正确展开，验收四颗初始黑子同时进 KataGo 查询。空谱、错误手数和无效转换均不伪装成有效报告。
- [ ] 运行 `python -m pytest -q tests/web_ui/test_kifu_incremental_catalog.py tests/test_kifu_incremental_cli.py tests/cron/test_kifu_ingest.py tests/web_ui/test_kifu_analysis.py` 和 `git diff --check`。报告真实回滚/重放覆盖与可用数据库环境，提交实现。

## Chunk 2　历史与小时增量段位验收

### Task 2　利用现行规则修复，并补齐一致性验证

- [ ] 查 `katrain/kifu_ingest/ranks.py`、`orchestration.py` 与 `katrain/web/kifu/historical_ranks.py`。小时 v3 冻结、发布和在库历史工具已经调用共同 `prepare_rank_decisions`。检查既有 `tests/web_ui/test_kifu_historical_ranks.py`、`tests/web_ui/test_kifu_historical_rank_native.py` 与 `tests/web_ui/test_kifu_hourly_retained_ranks.py` 是否覆盖同一身份原谱缺段位、有可靠既往证据、以及不可信对局日期的 TEST/PROD 结果。找出一个缺口时在这组现有测试中增加针对性验证；若行为偏离需求，先复现，再最小修复，勿放宽证据准入。
- [ ] 给 `scripts/repair_historical_kifu_ranks.py` 增加独立只读 `--audit-existing-v3` 入口，对已有 v3 逐批按相同原始证据规则复评。实现放在 `katrain/web/kifu/historical_rank_audit.py`，保留 `historical_rank_repair.py` 和 `historical_ranks.py` 的代码摘要，因已应用旧批次重放仍验证原摘要。使用键集分页、既有 100 局/200 槽、查询和原谱字节预算，避免按槽重复加载原谱。分别计数 v3 一致、仍待核、可证实的段位/分类差异、资源延后或校验失败；输出供受控再核对的 album ID、侧、原快照摘要、拟结果与证据分类，无写入。用有合规晚新增的既往证据、缺日期、已准确的快照和受保护来源补充聚焦测试。
- [ ] 测试/生产的 v3 审计若发现可证实差异，列明证据、绑定和受影响发布。本次验收保持未完成，直到独立审核的原生日志安全更正路径能保留旧回执、发布重放及补偿；当前旧脚本只允许 v1 一跳更正，不能用它覆盖 v3。计数为零或仍缺证据时，按实际拒绝原因结束本项。
- [ ] 在 `docs/operations/kifu-rank-hourly-consistency.md` 补充本次作业步骤。用 `scripts/repair_historical_kifu_ranks.py --matched-at <共同 UTC 截止点> --output <每库私有新清单>` 全库只读准备。在两库各自核对身份、批准范围、census、原因和 SHA。使用原脚本的 `--apply --manifest … --expected-sha256 … --part …` 顺序提交独立事务，TEST 验收后再对 PROD 应用。保存真实报告、失败位置、继续入口和对应 `--undo` 回执。清单是单一 JSON，CLI 即使只应用 `--part` 也会读取全部，单清单读取上限 128 MiB。冻结后、写入前验证准备命令返回的 `manifest_sha256` 和文件可重新读取。`--expected-sha256` 取规范化 JSON 的 `manifest_sha256`，无需使用落盘文件字节 SHA；超过上限才按审定 album ID 分片分别冻结，先保留完整只读 census。批量写只有真实主机与受控连接可进行。
- [ ] 统计并核对实际缺段位案例，包括 `179180`。现行规则要求可信原谱对局日期，来源的展示日期有可能是上传日期。生产无此证据的槽位留待核；与可确认修复数量分别报告。验证可补齐、有来源原值、无法补齐三类实例来自真实库。保留 TEST→PROD rank 对账和已有发布重放。
- [ ] 运行 `python -m pytest -q tests/web_ui/test_kifu_historical_ranks.py tests/web_ui/test_kifu_historical_rank_repair.py tests/web_ui/test_kifu_historical_rank_native.py tests/web_ui/test_kifu_hourly_retained_ranks.py` 和 `git diff --check`。提交验证和运维文档，不纳入真实库私有清单。

## Chunk 3　集成、发布和实际验收

### Task 3　验收后依序发版

- [ ] 用独立 Astra Max 审核两部分的完整 diff、部署设置和故障边界。修改、复测并复审直至通过。使用 `git fetch origin develop fix/kiosk-ui-debug`，核对远端当前分支仍为本地工作历史的祖先；合入最新 `develop` 并验证，推送当前分支。再将已验收分支合入 `develop` 并推送，复查两个远端引用。
- [ ] 在 `smartbox-software` 的 `main` 将 `vendor/katrain` 指针设为已发布 `develop`，保留无关改动，提交、推送并核对 gitlink。
- [ ] 按 `server-deploy` 检查两端实际服务的 Compose 链、数据库身份、接收器、collector 和 transformer 模型。确认 Web schema 已有分析表、当前生产消费者实际状态、固定模型等于 Web 报告模型、磁盘可用空间和公开 API。先暂停 TEST collector 入口以避免部署间隙漏排，再发布兼容接收器和消费者，确认两边开关都就绪后恢复 TEST collector，沿用原 stage 及重复保护。按队列年龄、剩余局面、实际每小时入库和消费速率及磁盘观察积压。优先保护在线用户报告，必要时停消费并保留已排工作。保留既有受限 SSH 通道、KataGo 进程和集群配置。
- [ ] 执行 Task 2 的真实 TEST→PROD 修复。用新真实收录的同一盘谱在两边分别验证任务、每局面至少 2,000 root visits、完整报告、Galaxy 页面入口及服务端 Kiosk 页面。正式历史样本 `24171` 继续可用。报告发布提交、已部署 SHA、修复计数及未解决原因。无需给盒端发布版本。
