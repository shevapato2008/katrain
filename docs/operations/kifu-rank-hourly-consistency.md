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

原始 SGF、原 rank、source owner、旧 manifest/receipt 不重写。规范层使用现有 `kifu_album_rank_snapshots`：职业 `Np`、业余 `Nd`、级位 `Nk`、类别待核 `N段`。两页面共用中文格式化，职业显示“职业九段”。

新 v3 决策与历史工具共用同一策略：精确人物和原始来源；不晚于目标局的可靠原始证据；不传播 inferred snapshot；保留来源日期，不能伪造升段日。内嵌段位也属于原始来源。部分/占位/已知上传式日期、系统冲突、较近数字矛盾和职业降段疑点保留待核。

首次应用在已有写锁、表锁后复核 material cohort；已应用重放验证原 journal，不按今日资料重算。后续谱引用的原始依据会阻止其父发布被撤销。

历史工具默认只读：

```bash
python scripts/repair_historical_kifu_ranks.py \
  --matched-at <固定UTC时间> --output <私有manifest路径>
```

DSN 来自进程内 settings，不放命令行。逐库冻结、审查 census/变更/拒绝原因，再使用显式 `--apply` 或 `--undo`、manifest 与 SHA。每个 part 最多 100 局/200 槽，独立事务；失败停止并记录已提交范围，不能宣称整个 envelope 原子回滚。保留私有前像与精确补偿凭据。

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
