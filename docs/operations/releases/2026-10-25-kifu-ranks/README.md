# 棋手段位：小时采集、同包发布与 RK 验收

发布开始于北京时间 2026-10-25，实际验收完成于 10-26 凌晨。代码已经部署；本目录记录真实动作，不把本地测试当作线上恢复。部署后独立审核见 [Astra 报告](astra-deployed-flow-audit.md)。

## 已发布版本与范围

| 项目 | 版本 |
| --- | --- |
| feature / `origin/develop` | `93f2038a0020d43b3090b1a71c8877980580f740` |
| Smartbox 已发布 main / gitlink | `51825c0e00a7f58544193ea6d584489252c6887e` / 上述 KaTrain commit |
| TEST Web image | `sha256:e5b77e0a6165617132900d22104bc7fbfe91b760b81ade7822f63fb345a2281f` |
| TEST cron image | `sha256:d67fcb72cbb31470b8cbbc24745ff0826fc7111e8594b64dbfecfaa98a46dc44` |
| PROD Web image | `sha256:dd83ae55fdb2549844be8d4d8f518b24f671990471a4b7d3f2b876555863ce2e` |
| RK 实际 source / 验收 PID | `93f2038a0020d43b3090b1a71c8877980580f740` / `658469` |

两云通过各自当前不可变镜像的 COPY overlay 发布，保留已上线大厅 API、Compose/env/mount、GPU、Postgres、MinIO。只替换两端 Web 和 TEST producer；PROD 原分析 cron 未变成采集器。显式执行精确 `004_kifu_player_ranks.sql` 前，已在真实 PostgreSQL 用临时父表/影子表演练约束；没有伪造 public 业务行，没有自动 GRANT 或启动时 DDL。

RK 仅更新 vendor/KaTrain 的 393 个运行 Python、1 个内容 policy 和 797 个 full/strict 构建资源，1191 个文件均核对。Smartbox main 是已发布 gitlink 上下文，**不是本次把整个 parent 工作文件部署到设备的声明**；首页、其他棋类、配置、棋局和硬件资料没有随本次复制。动态读取的 462 个保护文件 hash 不变。运行入口 `index-BL-M4qBg.js`，SHA256 `19e60d9e3d65f3b5167785f7562a9b3fd479abaaa3cc1af9baaf0f78d2dd4719`。

## 段位保存规则

原谱明确的 rank 优先。原谱缺失时，只针对可靠唯一实体查询库内最新已知明确等级；专业/业余/级别必须有相应证据，不能把 `3002`、同姓、模糊姓名或当前账号等级当棋手段位。新增代码没有外部人物爬虫、逐卡 HTTP 或额外 LLM。职业身份利用已有精确 owner 的已审核官方捕获；没有可靠类型/身份的资料继续为空，单条不会阻塞合法棋谱。

`kifu_player_rank_history` 追加事实并在同一原生事务维护唯一 current；`kifu_album_rank_snapshots` 保存每盘每侧的冻结决定、来源、事实 hash、匹配时间。`source_as_of` 是等级证据日期，`observed_at` 是本系统观察时间，`matched_at` 是本盘匹配时间。当前六条 `valid_from` 都为空，**不知道真实升段日**，不会把导入时间伪装成升段日。

例如以后得到同一棋手 2026 年八段的可靠新事实，会追加 history 并把 current 从七段切到八段；新缺值棋谱可以使用八段。先前以七段冻结的棋谱和发布包继续保持七段。重试读取冻结结果，不查询今天的 current 来改写旧包。不同库按逻辑人物引用核对并映射当地 ID，不携带跨库裸 ID。

真实原值优先例见 [source-priority-example.json](cloud/source-priority-example.json)：TEST `178908` 上野梨纱原谱/原字段“三段”，即使库内 current 为职业四段，API 仍显示“三段”，origin 为 source。升段/冲突/冻结后重放的数据完整性由已通过的代码终审及聚焦测试覆盖；没有为了演示晋段而改真实棋手资料。

## 真实三盘有限纠正

| source ID | 比赛日 | TEST ID | PROD ID | 冻结黑 / 白 |
| --- | --- | --- | --- | --- |
| 91694911 | 2026-10-25 | 179093 | 178757 | 7p / 4p |
| 91638738 | 2026-10-24 | 179085 | 178749 | 5p / 5p |
| 91637528 | 2026-10-24 | 179084 | 178748 | 5p / 7p |

这些值是**导入时库内最新已知资料补充**，不是声称比赛当时段位。冻结依据分别为藤泽里菜 10-19 七段、上野梨纱 10-15 四段、高星 9-16 五段、王爽 9-5 五段、唐奕 10-11 五段、周泓余 10-1 七段；grade 来源 SGF 与职业身份证据分开绑定。

同一 `rank_only` v2 包：

- publication_key：`rank-only-19x19-91637528-91638738-91694911-v1`
- canonical manifest SHA256：`1db149a53968f4a4b6c524624034ce876afc9d351434ef32e2e4114cd61675f2`
- 原文件 bytes SHA256：`d69ce9788ca34009af508e05b87b35e92cefee62cd7a0dbdda6c3f64891bb283`
- TEST 原生 batch `927`，完整 15 项五语详情 + 3 个公开卡片通过；API 验证约 7.75 秒。
- 将同一已验证包发 PROD，原生 batch `920`；同样全部验证通过，约 32.61 秒。
- 两端精确重放约 7.63 秒，返回原 receipt，batch/album 不变。

[冻结包摘要](cloud/frozen-manifest-summary.json)、[TEST receipt](cloud/test-apply.json)、[PROD receipt](cloud/prod-receipt.json)、[TEST API 验证](cloud/test-verification.json)、[PROD API 验证](cloud/prod-verification.json)、[双端重放](cloud/replay-result.json)。完整冻结原包留在持久 stage 的精确路径 `/app/data/kifu_ingest/rank-corrections/three-games-v1.json`，不复制整个原始源响应到证据 Git。

两库棋谱总数始终 `176876`，history `0→6`、snapshot `0→6`。原始 SGF hash、raw rank（六侧仍 null）、棋谱 ID/字段、source link、原始 native batch/receipt 均未改；TEST 原三个包、Stage manifest、StateStore `prod_synced`/publication_key/进度保持。没有重导旧谱、重译、删除原包或手改成功状态。见 [TEST 完整性](test/three-test-integrity.filtered.json) 和 [PROD 完整性](prod/three-prod-integrity.filtered.json) 及对应前后摘要。

## 小时采集与调度真实验收

一次真实有界轮完成于 228.43 秒。北京时间运行窗口是 `2026-10-19T00:43:16+08:00` 至 `2026-10-26T00:43:16+08:00`，不是固定调查日期：5 个 head 页/100 ID，60 次源 HTTP、55 次 SGF 尝试，39 个超窗过滤、19 个终止条目。固定七条 2021 坏项尝试次数不变，legacy rolling cursor `1786` 没有推进；没有历史深页扫描。见 [source-round-result.json](cloud/source-round-result.json)。

page cap 为 true、boundary_in_window 为 false，表示有限 head 覆盖，**不保证七天所有源记录都已枚举**。没有可靠源 updated_at；通过小时轮询和内容指纹发现可见近期变更，不假称按源站“最近一小时更新时间”精确筛选。保留 source7004 终止/审计、逐条隔离、429/Retry-After 整源退避、暂时错误退避和既有模型预算。

维护期间持有同一 stage writer lock（原 inode/owner/mode 未改），等待旧 writer 真正结束后才切换。第一维护 holder 到 TTL 后保留暂停，明确恢复原控制行再退役；第二 holder 在真实双端验证与重放成功后收到 bounded_passed，恢复原本不存在的 control row。没有取消 await 遗留同步写线程。首轮 cron 切换被 settings hash guard 拒绝并自动回滚，核实/刷新真实 baseline 后同一 candidate 通过，未放宽 guard；保留两个部署回执说明经过。

随后自然小时轮也真实成功：UTC `17:13:19→17:16:59`，约 220 秒、error_count 0。当前 enabled=true、interval=3600、consecutive_failures=0、control=[]，见 [最后调度与实际账本](test/final-schedule-ledger.filtered.json)。预算保持 window7（硬14）、head5（硬10）、HTTP160（硬240）、SGF100、source600秒、旧包恢复300秒、total3300秒协作预算、token100000，没有提高金额/模型权限。3300 秒不是不可取消同步发布线程的硬截止，单 writer 仍覆盖实际工作结束。

**账本证据纠正：** 原 operator 前后脚本把 YYYYMMDD 写成 YYYY-MM-DD，因此其 `ledger_sha256:null` 和 `token_ledger_unchanged:true` 不能证明真实付费账本前后不变，完整性结果中该错误 ledger 文件项亦不用于该主张。另行只读核了真实 `qwen-usage-20261025.json`：最后调用/mtime 都为 UTC 08:59:56（本次发布之前），发布窗口 UTC15:00 以后审计调用 0。最终证据记录真实路径/hash/调用时间，不隐藏原无效 null 证据，也不为补前像重跑付费任务。

## RK 实际展示和原上下文恢复

[1024×600 实屏](rk/page1-after.png)、[页面/API/DOM](rk/page1-browser-verification.json)、[运行文件与保护项](rk/runtime-verification.json)。前三卡对应上表，显示“职业七段/四段、职业五段/五段、职业五段/七段”，字号 18px，结果中心差 0。第 4–6 张未知记录不生成 rank 节点，不显示“未记录”或横线。此前第 5 页的原有资料段位继续保留，没有误作最新第一页。

重启后 401 经正常盒子主页→Go tile→现有 SSO 恢复至 200，没有提取 token。验后已恢复原列表第 5 页和原 Chat 路由；正常 Hermes tile 自动使 Go 回到原先 inactive/MainPID0。没有读 Chat 内容、发送消息或调用模型。见 [原上下文恢复](rk/entry-restored.filtered.json)。因此最后空闲时 Go inactive 是恢复用户原状态，不是部署健康失败；上述实际运行 PID/相机/引擎健康在切回前验证。

## 已证实范围与保留限制

真实证明了三盘源 rank 空的既有棋谱经精确库内匹配→冻结快照→TEST 原生验证→同包 PROD 原生验证→RK 列表，以及双端重放不重复入库/翻译。新增 producer 已部署并真实完成手工和自然有界轮。

这两轮没有出现合法且尚未入库的新源谱，故**尚未实证一盘全新插入的空 rank 棋谱**；不能把三盘 correction 或合成测试说成该证据。下一条自然出现且通过既有身份校验的近期新谱，将继续正常预处理/必要名称翻译/TEST 全部验证/同包 PROD 发布，不为示范解除冲突隔离或制造数据。

当前资料只随可靠新事实推进，不承诺主动发现每位棋手真实升段；没有新增 profile 定时爬取。超出近期窗口/有限覆盖的历史补录独立安排。普通首次入库仍有现存全 SGF 缓存冷路径（此前实测约二十分钟），本次 rank-only 早分支避开该路径，未扩为全库索引工程。原旧 78 盘的已有发布回执不重发，本次未改它们此前恢复后的状态。

## 可复核位置

TEST 发布目录 `/mnt/disk1/fan/kifu-rank-fallback-93f2038a0-20261025`；PROD `/home/ubuntu/kifu-rank-fallback-93f2038a0-20261025`；RK `/mnt/data/smartbox-deployments/20261025-kifu-rank-fallback-93f2038a0`。仅本地保存过滤回执、公开样本摘要和操作脚本 hash；不提交私有控制备份、env、凭据、完整私有日志或真实 SQLite 备份。

代码终审 Approved 和聚焦验证记录保留在已发布 source 的 `docs/superpowers/reviews/2026-10-25-rank-journey-astra-final.md`。本目录是独立证据分支，纯记录不移动已部署 source revision。
