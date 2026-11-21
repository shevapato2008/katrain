# 棋谱段位规范与小时采集运维

## 关闭原因及证据边界

2026-11-03 只读核对保留容器和任务记录：

- 10 月 29 日旧 TEST Cron 的 collector、LLM 均开启，每日本地预算为 100000 tokens。
- 北京时间 11 月 1 日 04:09:44 创建的 `58a5475b70a6…` 已缺采集环境变量、stage/受限发布挂载；Compose 记录只有主文件与 override，缺采集专用 overlay。程序因此使用默认 `false / false / 0`。
- 后续部署继承了该配置；最近一次发布不是最早缺失点。
- 旧待发布批次明确报过 `preparation memory budget exceeded`；没有找到供应商余额用尽的记录。本地预算 0 不是阿里云余额 0。
- 未找到首次遗漏配置的原始命令或操作人。不能把部署技能中存在的裸 Compose 命令当成已证实的历史操作。

用户已明确授权恢复并升级服务，使用原每日 100000 tokens 预算；下述步骤由实际发布记录验证后才算完成。

## 数据契约

原始 SGF、原 rank、source owner、旧 manifest/receipt 不重写。规范层使用现有 `kifu_album_rank_snapshots`：职业 `Np`、业余 `Nd`、级位 `Nk`、类别待核 `N段`。两页面共用中文格式化，棋谱中文显示统一为“九段”，保留职业/业余数据库类别。

新 v3 决策与历史工具共用同一策略：精确人物和原始来源；不晚于目标局的可靠原始证据；不传播 inferred snapshot；保留来源日期，不能伪造升段日。内嵌段位也属于原始来源。部分/占位/已知上传式日期、系统冲突、较近数字矛盾和职业降段疑点保留待核。

首次应用在已有写锁、表锁后复核 material cohort；已应用重放验证原 journal，不按今日资料重算。后续谱引用的原始依据会阻止其父发布被撤销。

## TEST 与 PROD 历史段位盘点

先分别在 TEST 和 PROD 的实际主机上核对数据库身份、部署版本和受控连接。两边各用一个私有目录，在进程设置中读取 DSN。为两边使用同一个带时区的 UTC 记录时间 `freeze_utc`，保存实际运行时间与环境身份。PostgreSQL 在只读的可重复读事务中扫描当时可见的数据，回看截止日取每局原谱里可信的对局日期。

在每个环境运行全库盘点，分别保留可审定修复的清单和已受保护的 v3 复核证据。

```bash
umask 077
python scripts/repair_historical_kifu_ranks.py \
  --matched-at "$freeze_utc" --output "$private_dir/rank-repair.json" \
  > "$private_dir/rank-prepare-summary.json"
python scripts/repair_historical_kifu_ranks.py --audit-existing-v3 \
  --matched-at "$freeze_utc" --output "$private_dir/rank-v3-audit.json" \
  > "$private_dir/rank-v3-summary.json"
```

可写清单的 `census` 覆盖全库。逐库核对身份、范围、来源、段位分类和拒绝原因，区分可靠补齐、真实原值及待核。用各库本地 album ID 抽查可补齐、保留原值和无法补齐的实际棋谱。核对 PROD 的 `179180` 原谱日期和双方来源。来源展示日期可能来自上传时间，缺少可信原谱日期时，按 `untrusted_target_date` 留待核。

v3 私有证据逐槽记录本地 album ID、侧、冻结快照摘要、原发布引用及新判定。用以下字段解释各侧结果。

| v3 审计结果 | 处理 |
| --- | --- |
| `consistent_slots` | 有依据且显示段位、数值与类别一致 |
| `refused_slots` | 按所列原因保留当前冻结状态，等可靠证据 |
| `supported_difference_slots` | 复核原快照、拟结果、实际原始依据、本地绑定和受影响发布 |
| `resource_deferred_slots` | 缩小核对范围并复跑，记录尚未完成的槽位 |
| `integrity_failure_slots` | 核查冻结快照、原谱、原发布、精确 journal 或本地绑定 |

隐藏棋谱和重复棋谱的受保护槽位也参与复核。证据记录当前可见性，`excluded_from_repair_slots` 另外统计这些槽位。

按 `evidence_omitted` 检查导出是否达到 128 MiB 限额。控制台仍有本次范围的总数。用汇总中的 `first_omitted_album_id` 作为 `--audit-from-album-id` 的包含性起点，写入另一个新私有文件。起点棋谱可能部分重叠，证据按环境、album ID 与侧对账。也可用 `--album-id` 聚焦一局或数局。补跑读取的是该次连接中可见的数据，保留每次输出，发生变化时重新核对。命令失败时保存现场并重跑到新的输出路径，使用完整 JSON 文件作为证据。

现有写入入口仅能补当前无快照的槽位或更正允许替换的旧快照。v3 支持差异记录直接归属发布，并以 `retained_receipts_require_review` 标记仍需核对后续依赖。批准任何更正前，另行按环境、album ID、侧和冻结摘要分批定位保留该快照或原始依据的后续发布，核对其回执与重放。v3 支持差异保持验收未完成，直到独立审核的安全更正路径通过验证，能保留原生回执、重放和精确补偿。缺证据的槽位按实际拒绝原因登记。资源延后和校验失败分别跟踪至有结论。

## 审定与分批写入

每库单独审定实际数据库身份、批准范围、完整 `census`、拒绝原因和 `manifest_sha256`。每个 part 最多 100 局、200 槽。即使使用一个 `--part`，CLI 也会读取整个 JSON 清单，单文件读取上限为 128 MiB。写入前使用与 CLI 相同的读取及校验路径确认整份清单可重新读取，并核对准备命令返回的规范化 JSON 摘要。

```bash
python - "$private_dir" <<'PYCODE'
import json
import sys
from pathlib import Path

from scripts.repair_historical_kifu_ranks import _read
from katrain.web.kifu.historical_rank_repair import manifest_sha256, validate_manifest

root = Path(sys.argv[1])
summary = json.loads((root / "rank-prepare-summary.json").read_text(encoding="utf-8"))
manifest = validate_manifest(_read(root / "rank-repair.json"))
if summary["status"] != "prepared" or manifest_sha256(manifest) != summary["manifest_sha256"]:
    raise SystemExit("Rank manifest SHA verification failed")
print(summary["manifest_sha256"])
PYCODE
```

`--expected-sha256` 取上述 `manifest_sha256`。若全库清单超过上限，保留全库只读盘点，再按已审定的本地 album ID 用重复的 `--album-id` 分片冻结，分别复查完整清单、批准范围及各自 SHA。

先在 TEST 的真实受控连接上按审定顺序执行，每部分独立提交。每次保存命令输出和私有回执。记录已改、未变化和拒绝的数量及原因，以及失败位置和恢复入口。

```bash
python scripts/repair_historical_kifu_ranks.py --apply \
  --manifest "$private_dir/rank-repair.json" --expected-sha256 "$reviewed_manifest_sha256" \
  --part "$part_number" --audit-output "$private_dir/apply-part-$part_number.json"
```

失败时核对 `completed_parts` 与 `commit_outcome_unknown_part`。对提交结果未知的部分，使用相同清单、SHA 和 part 重试，用持久化 CAS journal 确认结果。回执文件使用新路径。需要精确补偿时，对已提交部分按反序执行各自的 `--undo`，保存对应回执。

```bash
python scripts/repair_historical_kifu_ranks.py --undo \
  --manifest "$private_dir/rank-repair.json" --expected-sha256 "$reviewed_manifest_sha256" \
  --part "$part_number" --audit-output "$private_dir/undo-part-$part_number.json"
```

TEST 验收后才用 PROD 自己的清单、身份和 SHA 执行。两边均复查代表性修复，验证真实小时新谱的双方段位、来源、待核原因以及 TEST→PROD 的 rank 对账和原发布重放。私有清单和证据记录留在受控存储。

## 单一采集者与发布配置

TEST 是唯一采集者；PROD 仅接收同一验证包，不另开采集。

| TEST 配置 | 恢复值 |
| --- | --- |
| collector / LLM | true / true |
| 每日本地 tokens 上限 | 100000，保留原 ledger |
| 间隔 / 每批局数 / 新名字上限 | 3600 秒 / 100 / 20 |
| stage | 原持久目录，禁止重置或复制新空目录 |
| TEST API | http://host.docker.internal:8001 |
| PROD API | https://modelstella.com |
| 原生 SSH | kifu-receiver@117.50.177.254 |
| ES sync | enabled，受限 writer key |

原资源：

- stage：`/mnt/disk1/fan/kifu-hourly-incremental-20261019/ingest-stage` → `/app/data/kifu_ingest`，rw。
- key / known_hosts：`/home/fan/.local/share/kifu-hourly-incremental/ssh/` 下原文件 → `/run/secrets/kifu_ingest_key`、`/run/secrets/kifu_ingest_known_hosts`，ro。
- TEST CA：`/home/fan/deploy-es/certs/ca.crt` → `/etc/ssl/certs/kifu-es-ca.crt`，ro。
- TEST Cron 加入现有 `kifu-search-private`，容器 ES URL 为 `https://elasticsearch:9200`、alias 为 `kifu-search`。
- writer 仅从各主机受保护的 `deploy-es/secrets/es_api_keys.env` 提取指定 writer key；不把 admin/read 全文件作为 Cron 的 service env_file，也不能照搬宿主机 loopback URL。
- 千问沿用现有 `DASHSCOPE_API_KEY`，不输出、不换钥、不重置当日计费 ledger。

原私钥、公钥授权及 known_hosts pin 已只读核对匹配。PROD 保留 `restrict` + forced-command + 仅 root wrapper 的 sudoers，接收器仍在实际 Web 容器运行；为其明确开启 ES sync，不能改成任意 shell 通道。

`docker-compose.kifu-ingest.yml` 是 TEST 专用、默认关闭的 opt-in overlay，含必须的持久挂载和 writer 网络。真实恢复时提供受保护的运行参数；PROD 不加载 TEST collector 角色。发布时遵守更新后的 server-deploy 第 0 步，比较实际 Config/Env/Mounts/Networks 和完整文件链。不能以裸 Compose 重建覆盖活跃采集者。

## 恢复顺序

1. 代码经独立 Astra 审核后按 feature → develop → Smartbox gitlink 发布；先部署两端兼容 reader/receiver，再考虑数据或调度。
2. 保存 fresh 实际配置和备份；保留所有无关开关、会员、身份、GPU、数据库、MinIO。只应用审定的采集角色 delta。
3. 核对 stage、预算 ledger、单写者锁、受限 SSH/pin、实际数据库身份、writer 网络/CA/alias 与 ES ready。
4. 保留并检查原五个 unfinished 批次，按其已有 checkpoint/原 publication key 恢复；不重新翻译冻结结果、不另建进度冒充完成。
5. 最后开启 TEST collector/LLM，保持原每日预算。配置预检须早于 Stage/StateStore、模型调用和 PG 写入；发布参数缺失不能默默降级为无索引写入。
6. 使用实际新/恢复批次验证 TEST → PROD、同包重放、API 与索引可见性，并查看下一次计划运行和 heartbeat。只看到 healthy 容器不算采集恢复。
7. 再核对 Galaxy/RK Kiosk 的规范职业段位、可补缺失、明确业余及待核反例。摄像头离线与实体盘实物验收单独如实记录。

## 增量成本与索引

每批发布沿用 pending → PG commit → 有限 projection/bulk → refresh → ready。失败保留原操作待恢复；不每小时重建索引。纯 rank overlay 由 API 从 PG 批量读取，不需全库 ES 重建。

本轮新 rank/exact/semantic 候选证据共享 8 MiB 操作预算；同证据缓存复用仍检查新鲜元数据和原文相等。候选数量/大小超限整 cohort 延后，不能截断后错误判定。此限额不冒称已有审计 afterimage、特殊名称证明和提交后 ES 投影的任意原文都只读取一次；保留这些既有校验，记录实际阶段成本。

结构日志分别记录 projection、bulk（含打包/客户端）、refresh/ready、action 数与 outcome。旧整轮约 24–43 分钟包含准备/名称/验证/发布，不能算作 ES 增量耗时；实际当前数值以授权运行的日志和发布记录为准。

## 生产投影内存

实际恢复时，PROD 已提交批次 967 的 18 局在后续投影触及旧 Web 4 GiB cgroup 上限，11:25:10Z 被内核终止；原 pending gate 保持关闭，没有撤销或另建 publication key。相同工作负载 TEST 峰值 4,987,953,152 bytes。经独立运维审核，在确认主机约 44.9 GB 可用后，仅在线调整 PROD Web 为 8 GiB memory / 12 GiB memory+swap，无重启；完整前后像及明确策略位于该主机 release-fb970e488/private-memory。后续 native clone 或完整 Compose 角色配置必须保留该资源上限，不能重新落回 4 GiB。使用现有 recover_pending 恢复原已提交操作，禁止清 gate 或新 key 重导。
