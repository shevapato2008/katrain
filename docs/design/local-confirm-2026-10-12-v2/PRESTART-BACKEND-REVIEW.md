# 本地对弈开局前标定：独立后端代码审核

2026-10-12，独立 GPT-6-astra / max，先规格后代码质量。审核基线 `cb19ebb0d`，首轮候选 `b5e90a3081d2e4094d021797b7812e1e97e073ab`。

依据：仓库 AGENTS.md、[实施计划](../../superpowers/plans/2026-10-12-local-calibration-before-start.md)、[计划审核](PRESTART-PLAN-REVIEW.md)，以及候选 diff、几何服务与摄像头调用链、vision bind / worker reference 状态、本地确认与权威时钟、Task 1 前端 API 契约。

**最终结论：规格 GO，代码质量 GO。候选 `562fc975fc8a5c57cfcce570f170d9bec6f098ef` 已关闭 F1 / F2 / F3，无残留实质阻塞。** 本结论覆盖本次后端实现与所审调用链；真实设备旅程和发布验收仍按实施计划执行。

首轮候选结论为 NOT GO，原始三项证据保留如下。

## 规格符合性阻塞

### F1 · P1：重复帧没有打断连续证据，可误放行或误写 board_moved

- 位置：`katrain/web/core/geometry_calibration_service.py:301–303`，计数在 `314–347`。
- 原因：旧/重复 seq 或 ts 只更新 reason 后 `continue`，没有清零 `stable_count` / `drift_count`。因此旧帧前后的有效样本被拼接成连续三帧。
- 独立复现：使用真实 `MotionFilter` 和 `GeometryDriftMonitor`，96×96 固定随机图、20 px cell spacing；返回 seq `[1, 2, 3, 3, 4]`，第 4 次同时复用旧 ts。第 1 张仅作运动基线，旧帧后只有 1 张有效证据。原图在第 5 次取帧即得到 `ready=True`；换成相对原参考平移 8 px 的图，在第 5 次取帧即得到 `reason=board_moved, phase=degraded`。
- 影响：摄像头短暂停滞会跨越证据缺口直接开局，或把不足连续证据的结果持久到本轮状态为棋盘移动，违反“坏帧不能拼接累计”和未知不能冒充移动的契约。
- 最小修法：无效 seq/ts 必须打断两条连续计数；后续仍需重新收集三张连续可信样本。补一条混合正常/重复帧序列的正反方向回归，不能只测所有帧都旧。

### F2 · P1：计算或 monitor 锁等待越过预算后仍可发布成功

- 位置：`katrain/web/core/geometry_calibration_service.py:314–347`；当前 deadline 只在取帧后 `286` 检查。
- 原因：`_monitor_update_lock` 无截止时间，`motion.is_stable` / `monitor.update` 完成后也不重新核对 deadline；第三张有效结果会直接把 reason 置空。末尾身份校验没有时间条件。
- 独立复现：将预算缩为 50 ms，并只让真实 monitor 的第 3 次 update 额外耗时 100 ms。候选返回 `ready=True, reason=None`，耗时约 `0.106 s`，已经超过该轮预算。缩短预算只为让同一个边界确定重现，生产 8 s 边界走同一分支。
- 影响：超过采样预算的旧结果仍能开启实体局；monitor 竞争又可额外增加无界等待。计划审核已明确要求实际取帧和计算后复核期限，超时样本不能发布成功。
- 最小修法：锁获取使用剩余预算，计算后以及发布前再次检查 deadline；到期不能置 ready，也不能用过期计算触发移动降级。补第三次计算跨期与锁等待耗尽预算的聚焦回归。

## 代码质量与并发阻塞

### F3 · P1：旧 bind 可以覆盖刚发生的几何暂停

- 位置：`katrain/web/api/v1/endpoints/vision.py:299–304`；暂停来源在 `katrain/web/server.py:917–934` / `4608–4630`，暂停 setter 在 `katrain/web/interface.py:1097–1109`。
- 原因：`controller.ready(...)` 的同局 reference 校验和 `set_local_geometry_paused(False)` 是两次分离的提交。后者只检查 game/node，没有校验失效代次、当前几何 phase/revision 或当前 reference ready。几何回调可在两者间给同一局置暂停，旧 bind 随后又清除。worker 的几何命令是异步队列，旧 ready 状态也存在滞后窗口。
- 独立复现：复用既有 `TestClient` / 隔离数据库夹具和 `WindowVision`，让原 `controller.ready` 正常返回，接着调用真实 `_set_bound_local_geometry_pause(app, True)` 并将 `vision.local_confirmation_ready=False`，再让 bind 继续。实际结果为 HTTP `200`、`local_geometry_paused=False`、reference readiness `False`；测试期待的冲突且保留暂停结果失败。
- 影响：同一原局在几何失效或人工标定期间重新计时；物理 pass 仅检查该暂停位，可能继续提交。game/node 不变是本次恢复的正常条件，不能用它识别新失效。
- 最小修法：把最终 reference / 原局 / 当前几何身份验证与暂停清除放在同一权威提交边界，并与失效回调串行；新的失效代次不得被旧 bind 清除。若使用当前 geometry revision/phase，应同时处理状态已 degraded 而回调尚未到达、worker readiness 尚未更新的交错，不能仅在清除前再增加一次无锁布尔检查。保留一个确定交错的回归即可。

## 本轮独立验证

- `CI=true .venv/bin/python -m pytest -q tests/test_geometry_calibration_service.py tests/test_geometry_api.py tests/test_geometry_drift.py tests/test_local_play_timeout.py tests/test_local_move_confirmation.py`：**171 PASS**，19.84 s。仅既有 passlib/crypt 弃用 warning。
- F1 / F2 使用一次性 Python 最小复现，真实运动过滤与漂移计算；得到上述失败行为。
- F3 的一次性 `/tmp/test_prestart_backend_review.py` 使用既有夹具，经 `pytest -p tests.conftest --rootdir=...` 执行：**1 FAIL**，明确输出 `late bind overwrote pause: (200, False, False)`。该临时复现不进入产品代码。
- `git diff --check cb19ebb0d..b5e90a3081d2e4094d021797b7812e1e97e073ab`：通过。

已核对 preflight 复用原 monitor/reference、0.10 cell / response 0.05 门、首帧基线、能力门与 `asyncio.to_thread`、正常成功路径无点灯/持久化/revision 修改，以及绑定局过滤、原手动暂停保留、暂停时结算与丢弃时间、物理提交/超时入口。三项阻塞外不扩展状态矩阵或测试设施。未操作 RK、浏览器或云服务，未运行全量 GPU 测试，未修改产品代码。

## 第 2 轮：定向复审 `602ae0bbd5abad6ab0e86d702e2dda68397b2dcc`

**F1 已关闭。** 无效 seq/ts 会同时清零稳定与漂移连续计数。独立重跑首轮 seq `[1, 2, 3, 3, 4]` 复现：原图和平移图都得到 `ready=False, reason=stale_frame, phase=ready`，不再放行或误降级。

**F3 已关闭。** bind 在 `session.lock` 下复核 reference、几何 phase/revision，并通过暂停 epoch 条件清除；失效回调持有同一 session 锁，setter 在局提交锁内对比 epoch。失效发生在 bind 之前/过程中不会被旧 bind 覆盖；发生在恢复提交之后的回调继续置暂停。首轮完全相同的真实 `TestClient` 最小复现独立重跑为 **1 PASS**（1.75 s）。新增回归还覆盖 phase/reference 状态滞后但失效 epoch 已增加的分支。

**F2 原计算与采样锁问题已修复，最终清理还有一个残留。** motion/update 后有 deadline 检查，monitor 获取锁使用剩余预算；首轮慢第三次 update 复现现在为 `ready=False, reason=timeout`（约 0.105 s）。新增加的 `finally` 清理仍会在成功后等待 monitor 锁至 deadline，而当前最后一次时间检查位于清理之前。

唯一残留阻塞位置：`katrain/web/core/geometry_calibration_service.py:382–400`。独立使用真实 `threading.Lock` / `Event`：三张可信样本已计算成功，在最终 camera readiness 检查处让竞争线程获得 monitor 锁，随后进入 `finally`。50 ms 预算实得 `ready=True, reason=None, elapsed≈0.052 s, pending_reset=True`。成功结果跨过清理锁的超时期，仍直接发布。

最小修法：在 `finally` 和最终 status 读取之后、返回之前再次核对 deadline；清理锁等待耗尽预算时不能保留成功。只需一个该交错的定向回归，不重开 F1 / F3。

本轮独立新增回归命令选择 duplicate frame、slow monitor、monitor lock wait、bind invalidation：**9 PASS / 132 deselected**（2.54 s）；另独立重跑首轮 F1/F2 Python 复现与 F3 TestClient 复现。未重复全量测试，未修改产品代码，未操作设备/浏览器/云。

## 第 3 轮：关闭 F2，最终 GO

定向审核候选 `562fc975fc8a5c57cfcce570f170d9bec6f098ef` 相对 `602ae0bbd5abad6ab0e86d702e2dda68397b2dcc` 的窄修复：产品改动仅在 `preflight` 的 `finally` 清理与最终 status 读取后，再次检查 deadline，然后返回结果；配套增加一个真实 Lock/Event 清理竞争回归。

- 独立重跑前轮相同 Lock/Event 交错：`ready=False, reason=timeout, phase=ready, elapsed≈0.055 s, pending_reset=True`。清理等待耗尽预算后不再发布成功。
- 独立使用真实平移图和 monitor，在第三次 update 跨过截止时间，并监视 `_apply_drift` 调用：`ready=False, reason=timeout, phase=ready, apply_drift_calls=0`。超时计算不会触发移动降级。
- 聚焦 preflight 连续帧、慢计算、monitor 锁与 cleanup 相关用例：**9 PASS / 110 deselected**（0.60 s）。`git diff --check 602ae0bbd5abad6ab0e86d702e2dda68397b2dcc..562fc975fc8a5c57cfcce570f170d9bec6f098ef` 通过。

**F2 已关闭；沿用第 2 轮已关闭的 F1 / F3，最终规格与代码质量均 GO。** 未重开其它状态矩阵，未重复全量测试，未修改产品代码，未操作设备/浏览器/云。文中各轮测试数字均为该轮独立实际执行结果，不将实现者报告的扩展测试冒称为审核员执行。
