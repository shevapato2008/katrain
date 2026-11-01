# Task 7 报告审查（Astra，2026-11-02）

范围：报告创建/retry、worker fencing、终态结算、分析读取/诊断、删除/requeue，以及关联测试。只读产品代码；不审消费 UI、已独立审过的账务基础实现或生产部署。

## Spec：通过（修复后定向复核）

当前未解决问题：Critical 0 / Important 0 / Minor 0。初轮两项 Important 均已修复，修复代码与对应真实 PostgreSQL 回归已定向复核通过。以下保留原问题与关闭依据。

### 已关闭 Important 1：owned 报告不能经旧失败任务的 retry 复用

- 位置：`katrain/web/api/v1/endpoints/reports.py:698`，`if op.task_id` 无条件返回 `report_attempt_superseded`。
- 复现：报告 A 失败并全额退款；同一 SGF/profile 用新 key 创建报告 B，B 完整成功并 committed；再取得 owned 报价，以新 key 调用 `POST /reports/{A}/retry`。
- 实际：HTTP 409 `report_attempt_superseded`；两份 task、两笔原 operation，余额 97。无重复消费，但服务端已确认拥有的报告无法完成重试旅程。
- 应有：与 create 的 owned 分支一致，通过 `resolve_owned_operation` 返回 B 和 owned alias receipt；A 保留原失败绑定，不创建新 task、不给 GPU 新工作、不重复扣费。HTTP 重放返回同一 alias。
- 修复复核：`reports.py:409` 的 `_existing_report_for_operation` 由 create 与 retry 共用，解析 owned receipt 后再次核实 committed 报告的完整可读性；retry 的 `:707` 分支返回 B 与独立 alias，保留 A 的 failed/原退款绑定。新增用例核实重放响应相同、2 task / 3 receipt、余额 97。

### 已关闭 Important 2：排位中的私有分析可以经报告入口绕过中央保护

- 位置：`katrain/web/api/v1/endpoints/reports.py:469`（create）、`:648`（retry）、`:806`（moves）；三个入口均缺少已有的 `guard_user_has_no_pending_ranked_game`。
- 实际复现使用完整生产 `api_router` 挂载、真实 `AiLadderRankedRepository` 和隔离 PG 中的 pending ranked 行；仅认证主体和 KataGo 响应是受控测试输入。
- 顺序：排位开始前取合法 report/raw-SGF quote；持有 pending ranked 时将同一当前两手棋谱用新 ID 导入个人库；用尚有效的报价启动报告；实际 worker claim/process 在 mock KataGo 下完成 0、1、2 全部位置；读取该报告 moves。
- 实际状态：先前 quote 200；pending 下导入 200；新 quote 403；paid position 403；report create 200；report moves 200，返回末局面推荐 `C3`；相同游戏的兼容 analysis 接口 403。
- 影响：报价层新加入的检查不能替代执行与读取门禁。有效旧报价、先排队后开始排位，以及旧任务 retry 都仍能走未保护的报告链路。
- 应有：create/retry 与私有 moves 在 dispatcher 之前沿用中央 pending-ranked guard；进度元数据不必扩张限制。应覆盖开始排位之前已获报价/已排队的情况。
- 历史边界：HEAD 的 reports 也缺这个 guard；这是原路径漏洞被本次 paid 报告保留。原 `user_games` analysis/save 与新 paid-position 已明确禁止 pending 用户取得辅助，故此处没有增设业务规则。
- 修复复核：`reports.py:476`、`:656`、`:817` 分别在 create/retry/moves 的 dispatcher 前执行中央 guard。真实 pending 行与完整 `api_router` 用例证明先报价再进入排位时 create/retry 均 403，已 committed 报告 moves 403、status 200；拒绝请求不新增 operation、不改变余额。

## 已核对的符合项

- 新报告从服务端 SGF 计算普通 N+1 / 高级 4×(N+1)，operation 与 task 原子提交；失败完整退款后完整重授权。
- worker 在 claim 提交前复制 generation/operation ID，再传入 coroutine；每次写入及终态校验代际、绑定和 running，拒绝迟到 worker。
- 全部 0..N 位置与实际 root visits 门禁；冻结 model SHA 显式传给真实 KataGo client；不依靠全局配置或 analyzed_moves 代替完成证明。
- persisted 账务版本控制结算；锁顺序为 admission → user → operation → task，重试退款/再授权保持 admission 锁。
- 完整 committed 才开放报告/兼容分析；诊断先 reconcile/read gate，再按游戏去重；不让坏的新尝试遮住旧合法报告。
- 活跃/未结算报告阻止删棋谱；终态删除保留 receipt；legacy requeue/reaper 不改 paid task。
- 四路报告读取及 create/retry 转发传 expected_user_id；关联测试覆盖身份切换与离线不回退本地。

## 验证

- 初轮 reviewer 执行 `tests/web_ui/test_membership_reports_pg.py`：28 passed，19.60s。
- 修复后 reviewer 定向执行两个新用例及原 create/owned replay 用例：4 passed，26 deselected，3.00s。原作者交包另报告完整 30 PG 与 37 项 report/board 回归通过；本轮未重复运行全套。
- 聚焦 `git diff --check` 通过。
- PostgreSQL 使用既有专用 TEST 实例及随机 schema；`autoflush=False`、默认 `expire_on_commit=True`。
- 两个补充复现均用同一隔离 schema helper，执行后自动清理本次 schema。没有访问生产/default DB、没有 GPU 调用，没有停止共享 PostgreSQL。
- 不重复作者已完成的全套回归，不展开已知无关 cron import 历史失败。

## Quality：通过

在 Spec 通过后完成 Quality 审查，未发现需修复的 Critical / Important / Minor：

- owned 解析共用小型 helper，原 task 授权与 alias receipt 身份清晰；异常沿原请求事务回滚，不引入第二次提交窗口。
- 权限检查复用既有中央规则，置于云转发之前，保留纯进度读取；无需新增状态或权限系统。
- worker 保持 cron/web 边界，账务结算集中在 web；完整性、结果门禁与固定锁序在各消费路径复用，未发现本次修改引入的反向锁序或陈旧代写入。
- 新回归覆盖实际失败行为、幂等资产和真实 pending-ranked 数据；测试成本与两个高风险边界相称。

Task 7 可以进入下一阶段。本结论仅覆盖本报告范围，整功能代码/视觉统审另行进行。
