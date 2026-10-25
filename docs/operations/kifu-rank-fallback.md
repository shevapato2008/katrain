# 棋谱段位冻结与三盘有限修正

状态：开发中，尚未部署。本文的命令是待执行步骤，不是线上验收记录。当前本地仅使用临时 SQLite 和合成棋谱验证；真实 PostgreSQL 迁移、TEST → PROD、设备预览的证据由发布控制者补齐。

## 来源、显示与时间含义

每盘、每侧冻结一次段位决策：原谱明确段位优先；原谱为空时使用已精确绑定到本地棋手 FK 的、证据合格的资料库当前段位；没有合格资料则保持未知。原始 `BR`/`WR`、数据库 `black_rank`/`white_rank`、姓名、来源链接和 SGF 均不改写。两侧分别决策，未知不会显示虚构段位。

`source_as_of` 是来源所能证明的日期，`valid_from` 在升段日期不明时为 null。资料库当前段位表示“目前资料中最新已知”，不证明比赛当时段位。冻结的 `matched_at`、完整事实和快照 SHA 随包重用；重试不读取新晋段位重新计算。专业身份只复用已有审核来源捕获，有限修正不联网、不翻译、不调用模型。

当前调查发现的六个参考事实如下，仅用于核对来源；工具从当前数据库及已有合格证据读取，不把此表硬编码成段位。

| 棋手 | 最新已知段位 | 已有来源棋谱 | 来源日期 |
| --- | --- | --- | --- |
| 藤泽里菜 | 7p | 91664767 | 2026-10-19 |
| 上野梨纱 | 4p | 91284570 | 2026-10-15 |
| 高星 | 5p | 89651576 | 2026-09-16 |
| 王爽 | 5p | 88955900 | 2026-09-05 |
| 唐奕 | 5p | 91116424 | 2026-10-11 |
| 周泓余 | 7p | 90521040 | 2026-10-01 |

## 发布顺序与边界

先按仓库正式发布流程集成并记录提交，再发布 receiver/API，最后发布 producer/cron。两个数据库均需显式应用 `katrain/cron/migrations/004_kifu_player_ranks.sql`，并检查两张 rank 表、唯一 current 索引及外键。应用启动不自动创建这两张表。迁移文件具备事务和 `IF NOT EXISTS`；由受控数据库连接执行，保留执行与 schema 检查回执，不打印 DSN。当前环境未演练 PostgreSQL 迁移，发布前需补齐这一项。

保留现有发布锁、数据库写锁、固定 receiver SSH 命令、已知主机校验、环境变量、stage 挂载、GPU、数据库和 MinIO 配置。不要重建数据卷或借本次发布放宽 HTTP、SGF、模型 token、来源窗口等预算。旧 cron 不识别新约束时先停止旧写入者；不得在尚未结束的发布线程旁启动第二个发布者。

小时来源窗口、头部页数、复查上限沿用现有策略；这次不做历史全库补齐。既有 3300 秒是协作预算，同步数据库工作、已有 SGF 缓存预热或原生发布线程仍可能超出，取消 await 不等于取消写线程。

## 只允许这三盘

所有来源为 `19x19`，原始黑白段位均为空。下列原始包摘要与完整源 SGF 摘要是可移植权威；TEST/PROD 本地 album ID 只出现在各自原生回执中，绝不写入共享修正包。

| 来源 ID | 原始包 basename | 原始 manifest SHA-256 | 源 SGF SHA-256 |
| --- | --- | --- | --- |
| 91694911 | `91694911-0dbd77cb3a429076.json` | `0dbd77cb3a4290768ad9955542a51a8dc85cc6517231a0778faf06b42417d8fb` | `b044277aaac3223d3304fee2b958358418a83624d8c817fedb850c1994d845c2` |
| 91638738 | `91638738-2608c873a1f62fad.json` | `2608c873a1f62fade6f3e5b5964befb69e43d32009920c3a7793c3c198920e1e` | `0da65da0d6d75d9839585fdeac0f3860929e019ca03d7445c42887324a9bfd8f` |
| 91637528 | `91634842-c14e011c14dbca75.json` | `c14e011c14dbca7511ae472e0c70c0f3fda4f0cb3ef2ba42e7dbe348de924824` | `97edeb6666a08122e24940c7d4e303f7c1a2f4f4dfb8c94b2dc7b7ef762557d8` |

第三个原始包包含多盘，只选择其中的 `91637528`，同时校验整个原始包摘要。工具只读取明确给定的三个包；不得列举、glob 或读取 `data/kifu-album/`。需要诊断时仅使用数据库 SGF 或已知 stage 的 `sgf/ID.sgf`、`metadata/ID.json`。

修正包为 `kifu-incremental-manifest-v2`、`mode=rank_only`、空 `decisions`；保留完整原始 game 字段，新增去重 `rank_facts`、两侧快照、观察引用和 `rank_correction`。后者只包含原始 manifest 摘要及每侧已有完整快照摘要/null CAS。原始批次、原始回执、album ID、来源链接、raw ranks 以及 Stage/StateStore 进度保持不变；修正有独立 publication key、原生 batch、journal 和 receipt。

## 冻结、TEST、同包 PROD、重放

以下命令在 **TEST 数据库已正确配置的受控容器** 内执行。先只读预览，省略 `--output` 不建目录、不写 stage、不发布：

```sh
python scripts/kifu_rank_correction.py build \
  --original /app/data/kifu_ingest/packages/91694911-0dbd77cb3a429076.json \
  --original /app/data/kifu_ingest/packages/91638738-2608c873a1f62fad.json \
  --original /app/data/kifu_ingest/packages/91634842-c14e011c14dbca75.json
```

确认三盘来源、原始包、各侧实际 FK/canonical identity、raw rank、段位出处与旧快照 CAS 后，在独立且已存在的维护目录冻结一次。在上面的命令增加：

```sh
  --output /app/data/kifu_ingest/rank-corrections/three-games-v1.json
```

保存输出的 `manifest_sha256`。完整临时文件 fsync 后以不覆盖链接落盘；同一路径再次 `build --output PATH` 只验证并重用冻结文件，不开数据库、不查晋段、不重算快照。意外不同文件或摘要必须停下调查，不能覆盖后继续。没有模型或名称处理入口。

将下面的 `EXACT_MANIFEST_SHA256` 替换为冻结输出的完整摘要，仅通过共享 `catalog.publish_manifest` 在 TEST 原生应用：

```sh
python scripts/kifu_rank_correction.py apply-existing \
  --manifest /app/data/kifu_ingest/rank-corrections/three-games-v1.json \
  --expected-sha256 EXACT_MANIFEST_SHA256 --apply --target test \
  > /app/data/kifu_ingest/rank-corrections/test-apply.json
```

读取该 JSON 的 `receipt`，调用共享 `sync.verify_album_api(client, TEST_API_URL, manifest, receipt)`，必须传入完整 v2 manifest。为返回报告加入同一个 `manifest_sha256`，保存报告并调用 `sync.validate_test_verification`。验收包括三盘的 `cn/tw/jp/ko/en` 详情、完整 SGF、原始元信息、两侧段位/出处/快照摘要，以及真实中文公开列表卡片。旧 v1 检查点或只验证姓名的报告不能批准 v2。

随后将磁盘上**同一个冻结 manifest**、相同摘要和通过的 v2 TEST 报告交给 `sync.send_verified_manifest(manifest, digest, test_report, host=..., key_path=..., known_hosts=...)`。沿用现有固定 receiver；不创建独立 PROD publisher、不在 PROD 重新采集/冻结、不绕过 TEST 验证。保存返回的 PROD 原生 `receipt`，对 PROD 实际 API 再执行同一个全五语及中文公开列表验证。操作控制者负责具体连接参数及回执存档。

在两端重放相同包：返回相同原生回执，行数不增，原始数据与进度不变。重放直接进入原生 replay guard；不能用旧 null CAS 在它之前拒绝已经成功写入的非 null 快照。首次应用的任一 SGF、来源、FK、原始批次、metadata 或快照 CAS 不匹配时，整批零写入，保留冻结包并调查。

## 撤销与代码回退

使用共享原生 `catalog.undo_publication(engine, correction_batch_id)` 撤销本次独立修正，保留撤销回执。原生 guard 会核对 journal/postimage 和后续依赖；已有后来使用这些事实/快照的发布时应拒绝撤销，不得强删事实、快照或原始批次。

代码回退必须保留 rank 表和历史数据。若旧 API 不理解快照，先停止 producer，再协调显示回退；不得通过删表恢复旧版。原始源谱空段位在回退期间可能重新显示未知，不能用覆写 raw rank 掩盖。

## 待补的真实证据

| 验收项 | 证据/结果 |
| --- | --- |
| 集成、父仓库 submodule、两端发布提交 | 待发布控制者填写 |
| 两端 PostgreSQL schema 应用与校验 | 待填写；本地未演练 PostgreSQL |
| 真正新发现且原谱段位空白的合法源谱完整 TEST → PROD | 待填写来源 ID、摘要、双端回执和 v2 报告 |
| 三盘修正的冻结包与 manifest 摘要 | 待填写 |
| 三盘 TEST / PROD 全五语及中文公开卡片 | 待填写报告路径 |
| 相同包双端重放与不变原始字段/进度 | 待填写 |
| 未知段位、1024×600 真实 UI | 待填写截图与实际来源 |
| RK 与相同已发布源谱验收 | 待填写设备/版本/截图；不把其他库的样本冒充同一源谱 |

完成上述证据前，不将本地测试、有限修正或部署动作写成线上全部验收通过。
