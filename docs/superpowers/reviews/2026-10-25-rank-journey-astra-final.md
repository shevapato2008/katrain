# 棋手段位用户旅程：独立代码质量与数据完整性终审

**代码结论：Approved；当前没有未关闭的 must-fix。** 本轮发现的三项必须修复问题均已由实施负责人修复，并经本审核独立复核。批准对象为部署前代码，不表示 PostgreSQL、真实三盘纠正或设备验收已完成。

审核基线为 `2e7640d892e311f3fc8ed70d4dc5a32e470d2ddf`，首次审核代码为 `01aa39cd0b16ef86bf4d13826eead1f43222e65a`，其后的 `98883b8de` 仅增加规范审核报告。最终批准代码为 **`727fecb978eb3cf6066b1ad0bdb1ce605ea7b8e6`**，包含修复 `8a4f8a451`、`1db5bf7b0` 和 `727fecb97`。本审核为 fresh、独立的 Astra Max 审核；读取了实际代码、适用 AGENTS、requesting/receiving-code-review 和 verification-before-completion 技能，以及批准计划和运行手册，没有以既有审核结论代替检查。

## 必须修复的问题及关闭依据

### 1. P1：同日明确类型与未定类型的异值观察，冲突结果依赖到达顺序 — 已关闭

原位置：`katrain/web/kifu/player_ranks.py:709`、`:723`。

在临时 SQLite 中使用现有 `source_fact` / `apply` 测试辅助函数，以同一人物、同一 `2026-10-01` 依据日期分别应用 `8p`、`九段`：

- `8p → 九段` 得到 current `8p/qualified`，下一次库内回退仍可用。
- `九段 → 8p` 得到 current `8p/conflict`，下一次回退为未知。

原因是明确类型的 current 遇到 `dan_unspecified` 时设置 `active=False`，但 inactive 分支只检查跨系统或职业降段，漏掉同依据日异值。它违反同日矛盾应阻止继续回退的约束。

修复 `8a4f8a451b8e4cc342696b2db574ea2e33eb8493` 只补充 retained current 的同依据日异值冲突条件，保留事实、原段位和依据日期。独立检查了 diff，并运行 `professional_dan` / `amateur_dan`、两种到达顺序、同日 / 均无日期及 sticky conflict 的 8 项回归，另运行不同日期的明确类型优先 8 项回归。全部通过；没有把不同日期的未定类型观察误作职业降段。

### 2. P1：相同事实的不同观察时间使缓存与新成员的重试包永久失败 — 已关闭

原位置：`katrain/kifu_ingest/orchestration.py:267`、`katrain/kifu_ingest/ranks.py:400`。

事实 SHA 有意排除 `observed_at`，但 manifest 以该 SHA 合并完整事实时覆盖其中的观察时间，随后验证要求每个快照的观察时间与单一事实代表相等。

实际调用 `prepare_staged_games` 和 `Stage` 的最小合成复现：先以 T1 发现库内事实并冻结 A，不写 history；然后以 T2 发现相同事实，准备 `[缓存 A, 新 B]`。所有人物和赛事均已 qualified，名称调用为 0。第二次准备失败：`PublicationError: rank snapshot fact decision mismatch`。两个成员此时均已冻结，之后重复准备仍无法自行恢复。

修复 `727fecb97` 将不可变事实与观察元数据区分：共享 `merge_rank_facts` 校验完整事实后，按最早有效观察时间选择 manifest 代表；`1db5bf7b0` 让 correction CLI 使用同一规则。每个已冻结 snapshot 继续保留自己的观察 / 匹配时间、hash 和带时区校验，不再强行等于共享事实代表的观察时间。grade / owner / 来源 / 依据日期 / proof 的完整比较仍在。

最终 HEAD 的独立回归证明：缓存 T1 与新成员 T2 在两种输入顺序下均可准备；反向重试无需查当前等级；两个 stage 文件的字节和旧 snapshot 不变；native 中已有更早 T0 时保留 first-observed、保存各盘原快照，并返回相同重放 receipt。

### 3. P1：省略 rank metadata 可绕过原生 source-first 检查并提交错误 overlay — 已关闭

原位置：`katrain/kifu_ingest/catalog.py:295`、`katrain/kifu_ingest/ranks.py:92`、`:323`。

原生 manifest 校验只比较 metadata 中实际存在的键，而 rank 决策从 metadata 判断原等级是否缺失。最小合成复现：已有可验证 `7p` 库内事实；新源 SGF 明确 `BR[9p]`，删除 `metadata.black_rank`，重新冻结为库内 `7p` 并计算正确摘要。实际 `publish_manifest` 成功提交了 raw rank `9p` 和 `library_current/7p/raw=""` 的快照，数据库前后像确实发生变化。

API 的原值优先和后续 TEST API 验证会阻止错误 overlay 显示 / 继续发布，但不能替代 native 事务写入前的拒绝。修复 `727fecb97` 在 v2 manifest 校验阶段，对两侧 rank metadata 与确定性 SGF / source derivation 逐项比较。条件仅作用于 v2，v1 原语义保持。最终 HEAD 的独立 4 项回归覆盖原始等级来自 SGF / source metadata，以及省略 / null 两种篡改，均在写入前拒绝，全部模型表前后像一致。

同一边界的相邻检查已独立证明有效：对于有可靠 owner 的真实 `9p` 源观察，删除 observation / facts、清除快照 fact/proof/date 引用并重算 SHA，native 会报 `bound source rank observation missing`；原生表和 rank 表均零变化。该检查已有实现，无需扩大改动。

## 已检查且未发现其他必须修复项的边界

- 两张表独立于原 player / album 字段；显式 004 SQL 和模型包括覆盖 conflict 状态的唯一 current 约束、每盘每侧唯一快照以及事实 RESTRICT 外键。启动路径不创建或修复 rank schema。真实 PostgreSQL 执行仍待部署阶段证明。
- 明确源 rank / 嵌入 rank 优先；`3002` 不转为段位；中文裸段保持未定类型。回退只使用可靠既有 owner 的固定事实。职业证明复用精确同 owner 的已审核官方捕获，不引入外部 HTTP、爬虫或名称模型调用。
- 依据日期、未知升段日期、观察时间和匹配时间分别保存；grade、owner、slot、完整 SGF、来源及职业证据均可在 native 侧重验。无 DT 的 grade 来源明确使用 `album_date_sort` 并重验，不能伪称升段日期。
- Native 发布复用既有 publication guard / write transaction。history、current、snapshot 及有限 journal 一起提交；DATE 前后像可往返。正常重放校验固定事实 / 快照并返回原 receipt，不把 current 晋段回退。撤销先检查后来 snapshot 外键、保留 receipt 和当前 after-image，拒绝时零修改。
- rank-only 分支位于全库 SGF 预热、去重和姓名续审之前。CLI 固定三个原始包摘要 / SGF 摘要和来源 ID，默认只读，冻结文件不覆盖；已有冻结文件不重新查当前等级。Native 首次应用核对原始权威、raw metadata、canonical / FK 和快照 CAS，重放保持原始 receipt / album / source link / StateStore 进度。
- v2 检验完整有限的五语详情和中文公开卡片，重核 source / side / SGF / snapshot / origin / raw / display / provenance；sender 和 receiver 不接受 v1 count-only 报告冒充 v2。v2 checkpoint 算法独立，v1 路径保留。API 每页一次 snapshot 批读，list / detail / preview 使用固定决定，不查当前人物等级。
- 来源窗口、HTTP / SGF 上限、历史队列、7004 / 429 策略和模型预算不在本改动中放宽。原有 3300 秒仅为协作预算，普通首次发布的全 SGF 缓存冷路径仍是已知限制；rank-only 路径绕开它。

## 本轮独立验证证据

在 `8a4f8a451` 上使用 `/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q` 运行选定 63 项：**63 passed in 5.05s**，退出码 0。范围为：

- 上述同依据日冲突及不同日期明确类型优先，共 16 项。
- `tests/web_ui/test_kifu_rank_publication.py` 的 source history / 跨数据库 ID / 旧包重放 / alias / snapshot 依赖 / retained receipt / 旧 current 状态 journal / rank-only CAS。
- correction CLI 的实际 native 应用重放、冻结输出复用，以及错误 preimage 的零写入拒绝。
- 职业捕获与当地 owner 核对、缺 DT 的日期锚定、alias 歧义拒绝。
- v2 完整报告覆盖和错误证据拒绝、新 checkpoint 重核；API 五语固定回退、源 / 嵌入等级优先与每页一次 snapshot 读取。

另执行了上述三个最小反例及相邻 source-observation 删除检查，均使用临时目录、合成数据和临时 SQLite，不连接真实数据库，不调用模型 / 采集器。

在最终 HEAD `727fecb97` 上独立执行修复相关 12 项：**12 passed in 2.70s**，退出码 0。包含混合冻结时间的两种顺序、native T0 / 每盘快照重放、SGF / source metadata 省略 / null 的四项零写入拒绝，以及原冻结重试、correction CLI 实际 native 应用重放 / 文件复用、rank-only CAS 和 v2 checkpoint。没有再次运行完整 foundation、392 项广集、全 GPU 或全 UI 回归。

最终检查命令：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q \
  tests/test_kifu_rank_freeze.py::test_cached_and_new_games_share_fact_without_rewriting_observation_times \
  tests/web_ui/test_kifu_rank_publication.py::test_shared_fact_keeps_earlier_native_observation_and_each_snapshot_on_replay \
  tests/web_ui/test_kifu_rank_publication.py::test_v2_original_rank_cannot_be_omitted_or_null_to_publish_fallback \
  tests/test_kifu_rank_freeze.py::test_prepare_freezes_before_name_failure_and_retry_skips_today_profile \
  tests/test_kifu_rank_correction_cli.py::test_frozen_cli_pack_applies_and_replays_through_actual_native_publisher \
  tests/test_kifu_rank_correction_cli.py::test_frozen_output_retry_does_not_recompute_after_promotion \
  tests/web_ui/test_kifu_rank_publication.py::test_rank_only_correction_has_finite_fast_path_and_preserves_original_receipt \
  tests/test_kifu_api_verification.py::test_v2_checkpoint_uses_new_algorithm_and_revalidates_rank_evidence
```

目视检查了相同 UI patch 的 `before-after-reports.png`（每侧 1024×600），并读取同目录 `measurements.json`：未知节点已隐藏，明确的职业九段 / 业余6段 / 6级保留，记录字号 18px、卡片 624×74、无页面溢出。它是 patch preview，**不是最终线上或 RK 验收**。

## 代码批准之后仍须完成的真实部署门

1. 两端 PostgreSQL 迁移及约束检查。受控临时 schema 演练可先验证 current 唯一、RESTRICT 和事务回滚；随后执行精确 004 SQL 并记录 public schema 实况。当前未将 SQLite 结果当作 PostgreSQL 迁移 / 并发证据。
2. 正式 feature → develop → Smartbox gitlink 发布，先两端 schema / 兼容 receiver / API，再 TEST producer。保留现有挂载、环境、GPU、DB、MinIO、stage、预算和锁；PROD 分析 cron 不变成采集器。
3. 固定三 ID 的实际 dry-run、同一冻结包 TEST 应用 / 五语及公开卡片验证 → PROD 同包应用 / 验证，以及双端精确重放。记录 raw SGF / rank / source / 原 receipt / `prod_synced` 进度未改变，不增重复谱，不重译。
4. 最终发布版本的 1024×600 实际页面和 RK 证据。真正合法的新空 rank 源谱完整插入链路须等实际新来源；三盘既有谱纠正和合成测试不能替代它，也不应为凑证据放宽隔离或恢复旧队列。

本审核未读取、枚举或 glob `data/kifu-album/`，未修改产品代码、真实数据、服务、迁移状态、队列或锁；只写本报告。补丁由实施负责人完成，本报告只独立复核。
