# 开局前标定：最终前后端集成审核

2026-10-12，独立审核，先核对用户旅程与契约，再审代码质量。已部署基线 `8382acbb540f35da2cb1d3aa872d44744109ecd9`，首轮候选 `4ffa441c0`，包含前端 `fd0f2087c`、后端 `b5e90a308` / `602ae0bbd` / `562fc975f`；最终复审候选 `c9d1799584f8c764fe98f92b43d09d7bae5a592d`。

依据：仓库 AGENTS.md、[实施计划](../../superpowers/plans/2026-10-12-local-calibration-before-start.md)、[前端审核](PRESTART-FRONTEND-REVIEW.md)、[后端审核](PRESTART-BACKEND-REVIEW.md)，以及完整候选产品差异、直接调用链和相关测试。本次只读产品代码，未操作浏览器、RK、云服务或用户当前三手局。

**最终结论：规格 GO、代码质量 GO。`c9d179958` 已关闭唯一阻塞 F1，无残留实质问题。** 首轮 NOT GO 的证据保留如下。既有前后端审核已关闭的问题不重开；不追加 GPU、视觉状态矩阵或无关测试设施。本结论覆盖代码集成，不代替真实设备旅程与发布验收。

## F1 · P1：首次 bind 已拒绝，服务端仍开始计时（首轮，已关闭）

- 主位置：`katrain/web/api/v1/endpoints/vision.py:305–315`。`controller.ready(...)` 先产生副作用，之后才在 `session.lock` 中做最终几何检查。
- 相关位置：`katrain/web/server.py:4623–4629` 只暂停已有 physical-ready controller；`katrain/web/core/local_confirmation.py:81–86` 的 `ready()` 会登记 physical 输入并调用 `start_clock()`。
- 真实交错：实体 19 路新局尚未首次 ready → bind 已读到 ready 几何及 reference → 几何降级回调发生在 `controller.ready()` 之前 → controller 尚未登记 physical，暂停回调直接返回 → worker 的异步几何命令尚未反映到 reference-ready → `ready()` 启动时钟 → 最终 phase 检查返回 409，却没有撤回已启动的时钟或设置几何暂停。
- 影响：前端正确进入恢复提示、禁止确认，后端仍给当前玩家扣时。用户在处理标定/恢复期间可耗尽用时，违反“实体识别未就绪不计时”的权威边界。已有后端回归把失效注入在 `ready()` **之后**，因而未覆盖首次 controller 尚未就绪的分支。
- 独立证据：临时 `/tmp/test_prestart_final_review.py` 使用既有隔离数据库 `TestClient` 夹具、真实 19 路 `/api/game/setup`、真实暂停回调与真实 `LocalConfirmationController.ready`，仅用既有 `WindowVision` 表示异步 worker 尚可见的旧 readiness。在调用原 `ready()` 前注入降级，得到 `(HTTP status, clock_started, local_geometry_paused, timer.paused) = (409, True, False, False)`；期望保持暂停的断言明确失败。新局初始 `clock_started=False` 已先断言。
- 最小修复方向：把 `ready()` 的登记/启动时钟副作用纳入与失效回调串行的同一个 session 提交边界，并在该副作用前复核当前几何、revision、reference 与失效 epoch；失败须保持未就绪或暂停。仅补首次 bind 这一确定交错，保留已通过的“ready 后失效”和 epoch 回归。

复现命令：

```sh
CI=true .venv/bin/python -m pytest -q -p tests.conftest --rootdir=/Users/fan/Repositories/katrain-kiosk-local-play /tmp/test_prestart_final_review.py
```

结果为 **1 FAIL**，1.56 s；失败是上述产品断言，不是环境错误。夹具启动时的本地引擎/直播数据库不可达日志不影响请求或断言，未为这些旁支排障。

## 其余规格与质量核对

- 设置页只为实体 19 路发 POST preflight；通过后才 create/setup/writeActive/navigate。pending 防重复；失败和离页后的旧响应不会发布新局，未发布的本次新会话会清理。标定组件替换可见内容但保留设置组件状态，标定完成返回设置，仍需再次点击开始。屏幕局、非 19 路与实际无视觉设备的原路径保留。
- preflight 的 `{ready, reason, status}` 与前端解析一致；status 与普通状态接口共用 camera/model/recognition 能力口径。服务端复用原 lock/monitor，要求严格递增的新鲜帧、运动基线之后的三张连续可信稳定证据，重复/不可信帧断开连续计数；期限在计算、锁等待、清理和返回边界检查。正常通过不点灯、不写盘、不改 revision。
- 仅本地对局路由移除外层卸载守卫。GamePage/session/棋谱在恢复及用户主动空盘标定期间保留；恢复使用原 session bind 和权威 GET state，再核对 revision、几何和绑定后的视觉状态；旧 session/game/revision 与未 ready 状态不能解除界面封锁。
- 对已经 physical-ready 的原局，降级/人工标定回调设置独立几何暂停；计时、超时和物理确认提交门消费此状态，原手动暂停不被覆盖。恢复须真实 reference-ready bind 成功，游戏/node/epoch 检查阻止旧 bind 清除新的暂停。新局初始化会重置该暂停原因；其它模式与纯屏幕局不被几何回调选中。F1 是首次绑定尚未登记 physical 的遗漏边界。
- 改动沿用现有 API/context、标定组件、绑定与本地确认链路；没有新增产品 Fixture、识别替代实现或额外基础设施。本轮除此阻塞外未发现需要扩张范围的质量问题。

## 本轮验证与边界

- 独立执行 `git diff --check 8382acbb..4ffa441c0`：通过。
- 独立聚焦 Python：`tests/test_geometry_api.py tests/test_local_play_timeout.py tests/test_local_move_confirmation.py -k 'preflight or geometry_pause or geometry_callback or bind_does_not_clear_pause or real_bind_ready'`：**10 PASS / 49 deselected**，3.67 s。
- 独立聚焦 Vitest：`src/api/geometryApi.preflight.test.ts src/kiosk/pages/PvpLocalSetupPage.test.tsx src/kiosk/pages/GamePage.test.tsx -t 'preflight|recovery|three-move|calibration|preparation|original|earlier geometry'`：**24 PASS / 92 skipped**，3 文件通过，4.08 s。
- root 已报告候选全范围 Python 5 文件 181 PASS、Vitest 8 文件 142 PASS、TS/full/strict2D 构建通过，以及 Mac Chrome 1024×600 两旅程预览与独立视觉 GO。本审核未把这些结果冒称为自行重复执行，也未据此覆盖 F1 的独立失败证据。
- 当前 RK 三手局保持在本次审核操作范围之外；本结论不代表真实设备旅程、发布或用户局切换已经验收。

## 第 2 轮：定向关闭 F1，最终 GO

独立审核 `c9d1799584f8c764fe98f92b43d09d7bae5a592d` 的四文件窄修复，仅复核 F1 与直接相关的原局恢复、屏幕局隔离边界。

- `LocalConfirmationController.ready()` 的 `before_start` 在 `session.lock` 与游戏提交锁内、登记输入和 `start_clock()` 之前执行。bind 在此复核绑定身份、reference、几何 phase/revision 及原局/node/暂停 epoch；失败不会启动首次时钟。提交后的再次校验继续拒绝紧随 ready 发生的新失效。
- 暂停回调现在覆盖当前绑定的 19 路本地局首次 reference bootstrap，controller 尚不存在或未登记输入时也不会漏掉暂停。已登记为当前局 screen 的 controller、旧游戏 controller、非本地模式和非 19 路仍被排除；常规屏幕 ready 不使用本次新增回调。原手动暂停与原局身份机制未改。
- 原封不动独立重跑首轮 `/tmp/test_prestart_final_review.py`：**1 PASS**，1.80 s。原先失败的“ready 前降级后，拒绝绑定但必须保持计时暂停”断言现已通过。
- 独立执行 `tests/test_local_move_confirmation.py tests/test_local_play_timeout.py -k 'first_physical_bind or bind_does_not_clear_pause or geometry_callback or real_bind_ready'`：**6 PASS / 27 deselected**，4.26 s。包括首次失效保持 `clock_started=False` / `local_geometry_paused=True`、正常首次 bind 成功才起钟、ready 后失效和旧 epoch 不恢复、同局恢复、screen controller 不误暂停。
- `git diff --check 4ffa441c0..c9d1799584f8c764fe98f92b43d09d7bae5a592d`：通过。实现者另报告五目标 183 PASS、Black 通过；本轮未重复全范围测试或构建，前端没有变化，沿用既有视觉确认。

**F1 关闭，最终规格与质量均 GO。** 本审核只更新本文件，没有修改产品或测试，没有操作 RK 当前三手局、浏览器或云服务。
