# 星阵小时同步修复：Astra 独立最终审核

**结论：Approved／无必须修复项。**

本结论针对本地分支 `fix/golaxy-hourly-sync-20261023`，审核基线为 `0ac3190d8a114403f35d37ffd76c34caaa31825b`，代码 HEAD 为 `22fff109ea98f495c36cd527c0a28e941b5cb0c9`。已独立阅读真实 diff、完整新增测试及相关既有状态机、发布和调度边界，并在该 HEAD 重新执行验证；没有以分阶段 Approved 或实施者的测试报告代替最终审核。

这只是本地修复审核，**尚未上线，生产恢复仍待后续授权**。没有执行生产 SSH、DB/API 访问、模型调用、真实导入/发布、部署、push 或读取、列举 `data/kifu-album`。唯一新增仓库文件为本报告，未提交。

## 审核范围与依据

按最终用户策略核对近期比赛窗口、有限头部分页、持久观察差异、来源错误隔离、原生回执恢复和验证检查点。入口为 `docs/superpowers/plans/2026-10-23-golaxy-hourly-sync-fix.md`；原调查、慢因诊断、三个分阶段审核及待发布 runbook 仅作为需求和证据背景。先检查实际实现，再交叉核对阶段报告中的修复。

业务 diff 限于 `cron/config.py`、`cron/jobs/kifu_ingest.py`、`kifu_ingest/{source_19x19,staging,recent,maintenance,exclusions,sync,verification}.py`。没有大厅、本地续开、UI、KataGo 或底层 Web API/索引改动。

## 关键场景核对

| 场景 | 实际检查与结论 |
| --- | --- |
| 七个 2021 年 7004 坏项与合法新谱并存 | `discover_recent` 先读有限 page 0 起的列表，不进入历史 rolling；七个旧待办不能消耗小时 SGF 尝试。测试让第一页为旧比赛、第二页为新比赛，仍取得新谱，游标 1786 保持不变。 |
| 窗口、跨天、未知时间及覆盖诚实性 | 完整 `playTime.date/time` 按产品约定解释为北京时间，比较带时区的闭区间；7 天默认、14 天硬上限。未使用 createTime/analyzeTime 作为更新时间，也不遇旧记录停止。跨午夜、边界、迟到窗内比赛、超窗比赛、重叠 ID 与未知时间均有针对性断言。页边界、未知时间、尝试/请求/时间触顶计入 coverage，没有全库完整声明。 |
| 预算、公平与延期 | 5 页默认/10 页上限，每页最多 20 行；100 次 SGF 尝试、160 次默认/240 次硬 HTTP 上限含重试；离开头部的近期重检最多 20 条并共享预算。未观察且未发布的候选优先，其后用持久 last_checked 排序。跨轮预算延期和 absent 重检轮换测试通过。 |
| 7004、临时错误、429、无效 SGF | 仅 shared SGF 的 7004 不可重试并保留代码/消息；普通错误逐条冷却，累计三轮终止，不因连续五条失败挡住其他合法项。429 立即停止整源、持久 Retry-After，不消耗普通坏项计数。无效 SGF 与严格黑白姓名冲突单条隔离。 |
| 发布权威与不重复处理 | 候选集合的 catalog/provenance 和原生 receipt 查询区别于 StateStore 已见记录；隐藏已发布行仍算已发布。发布权威未完成或本轮 SGF 未成功检查时不能取得准备资格。已发布无源指纹者只建观察基线；不变已发布条目不重译、不重入，未发布且预算延期的条目后续仍可继续。 |
| 同 ID 元信息或 SGF 变化 | 元信息差异在 SGF 请求和预算判断之前持久留证，`raw_status=not_fetched` 不伪造内容证据；SGF 差异保留新旧指纹及变体。原 metadata、原 SGF 和成功状态不被覆盖；后续小时不重复拉取已隔离版本。 |
| 新谱、冻结 TEST 包与历史回执顺序 | 源扫描前只读取/校验本地冻结包并收集 packaged IDs；旧包 DB 恢复与网络验证在扫描及新候选处理之后。近期冻结 TEST 包只有本轮 checked、仍在窗口，且 manifest／原 Stage／当前 observation 的非空 raw SHA 一致才能继续 PROD。changed、unchecked、不同/缺失原始基线测试均禁止发布并保留 receipt。 |
| 已发布包失败与尾段边界 | 原生 PROD receipt 直接续 PROD 验证；测试确认失败不变成 prod_synced，也不调用 TEST 发布、PROD sync 或翻译。历史 TEST receipt 最多续 TEST 验证，不开启历史 PROD；所有尾段共享 `min(round deadline, now + 300s)`，prod_synced/quarantined 包跳过。 |
| 五语、内容与公开卡片检查 | 对照旧实现逐项核对，五语详情、canonical SGF、原黑白名/赛事、source membership、存在的审核译名以及中文公开列表卡片均保留。成功列表缓存只限同次调用的完整 target/query/lang/page/page_size，并仍逐盘比较卡片。非 200/语义错误不重试；瞬时网络/超时最多重试一次。 |
| 检查点绑定及 TTL | 绑定完整 manifest、完整 receipt、规范化目标、algorithm version 和 languages。只保存五语加公开卡片全部通过的单盘证据；partial 无进度信用，invalid/corrupt/symlink 拒绝，绑定变化重验，24 小时到期不复用。追加后续单盘不会刷新先前 completed_at；返回前要求全部 `5 × games` 检查覆盖。 |
| 真网络截止与写者 | Source HTTP 使用剩余 source deadline 的 wait_for；验证每次 GET 同时限制 httpx timeout、30 秒墙钟和整体验证剩余时间。真实短 sleep/cancellation 测试覆盖挂起请求及重试耗尽。发布调用不受外层 wait_for 取消；发布超出协作预算时先保留完成回执，再停止后续 phase/包。PG session lock 和 Stage file lock 包围整轮，Stage 在取得锁后构造。外围 RunRecorder 直接 await job，APScheduler 设置 max_instances=1。 |
| 有限维护与证据保留 | 固定七 ID + 精确旧错误匹配，默认 dry-run；apply 前持有兼容 writer lock，保存原像、pre/post digest 与审计；回滚拒绝覆盖已变动 postimage。人工历史入口要求独立 staging root 和有限参数，不调用模型或发布。没有清空 stage、删证据或假标成功的路径。 |

重点代码边界为 `recent.py:253,315,380,407,427`，`jobs/kifu_ingest.py:392,457,508,523,564,663,839`，`sync.py:169,223`，`verification.py:49,85`。这些结论基于实现和测试断言逐项检查，不仅是测试数量。

## 本次独立验证

在审核 worktree 执行：

```sh
/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest \
  tests/test_kifu_incremental_source.py \
  tests/test_kifu_incremental_staging.py \
  tests/test_kifu_incremental_state.py \
  tests/test_kifu_incremental_cli.py \
  tests/test_kifu_incremental_preparation.py \
  tests/test_kifu_recent.py \
  tests/test_kifu_maintenance.py \
  tests/test_kifu_api_verification.py \
  tests/cron/test_kifu_ingest.py \
  tests/cron/test_kifu_hourly_orchestration.py \
  tests/web_ui/test_kifu_incremental_catalog.py -q
```

实际结果：**295 passed in 15.13s，exit 0**。

```sh
git diff --check 0ac3190d8a114403f35d37ffd76c34caaa31825b..22fff109ea98f495c36cd527c0a28e941b5cb0c9
git diff --check
```

两项均 exit 0、无输出。审核结束时确认代码 HEAD 仍为上述 SHA。

另外执行了一次合成 78 盘的交叉场景脚本，使用现有 `tests/test_kifu_api_verification.py` 的 `AlbumAPI/Clock`、临时 SQLite StateStore、临时 checkpoint 目录和 MockTransport。按 2/32/44 分包预置原生 PROD 回执；每个 HTTP 调用消耗 8 个逻辑秒，每轮尾段共享 300 个逻辑秒，轮间 wall clock 前进一小时；调用真实 `process_package_queue → resume_batch → verify_album_api`。TEST 发布、TEST 验证和 PROD sync 回调全部设置为若被调用则失败。

实际结果：12 个有界逻辑轮次，11 次预算中断，失败阶段均保留 `retry_wait/resume_phase=prod_published`；最终三个包均 `prod_synced`，检查数分别为 **10、160、220**，424 次 mock HTTP、3 个检查点、**0 次发布调用**，原 PROD receipt 保留。此项证明跨包共享预算与逐盘续验的组合行为；逻辑时钟模拟不冒充真实线上性能测量。真实墙钟取消由上述测试套件中的短时挂起 transport 场景验证。

## 结论边界

- 3300 秒仍是用户已接受的协作预算。同步 DB、首次全库 SGF cache warm-up 和同步发布线程仍可能超出；本次没有将它们重构为可取消操作，也没有声称硬性全轮截止。
- 头部分页和近期比赛窗口只提供有限覆盖；古老比赛新上传、超过窗口的停机遗漏、未知时间都不由小时任务自动补全。
- 检查点 TTL 在复用时判断，旧完成时间不会刷新；这不构成最终返回时刻的全包原子快照。
- 底层 Web 名称证据计算和缺少匹配索引的慢路径仍存在。本次有限重试、同轮列表缓存、逐盘续验降低重复工作，没有声称消除服务端慢因。
- 未验证真实 TEST → PROD 发布旅程、线上 78 盘恢复或部署效果；须在后续获准发布后按 runbook 执行。审核结论不授权部署、迁移或生产补跑。

**最终裁定：本地修复 Approved，无必须修复项；尚未上线，生产恢复仍待后续授权。**
