# 曝光标定与本地确认：最终代码审核

2026-10-12。独立审核在 root 正式 Task 3 DONE、工作区稳定后进行。Task 3 基线为 `60a8b67c096102eaa93f0207606c266fa84aef23`，对象为三个生产文件 `ipc.py`、`worker_inprocess.py`、`local_confirmation.py` 及两个对应测试文件的未提交差异。随后检查了 `90e89e8fd` 起的完整改动及相关调用边界。先核对规格，再审核代码质量；不追加计划审核。

| 审核 | 结论 |
| --- | --- |
| Task 3 spec compliance | **GO** |
| Task 3 code quality | **GO** |
| 整体最终 code review | **GO** |

**没有剩余阻塞项。** 可以提交、合并并准备发布该源码。这个结论是代码审核通过，实际 RK 标定、首手确认和部署健康仍由后续验收确认。

## Task 3 规格

- `LocalWindowObservation.exposure` 默认 `None`，保留原字段和 IPC 兼容路径。确认窗口在同一张新鲜 raw board warp 上、average/CLAHE/模型推理之前测量，AE 关闭时也执行；复用 `check_frame_exposure` 的 245 / 0.35 / 20 严重阈值，没有把 AE 目标带 120–170 当成报警线。
- 连续证据属于 worker 的 `_LocalWindow`：同方向至少三张不同新鲜帧，camera 时间跨度至少一秒。正常、运动、缺帧、重复/迟到 seq 或 ts、方向改变、warp 失败和真实 controls pending 都在原始分支复位。生产 CameraManager/CameraHub 的控制接口在 `controls_effective=None` 时保守等待；终态 `False` 不会被当成 pending。
- 首张严重帧立即清 candidate、原始候选参考及累计投票，重新对齐 move detector 到权威 expected，发送 `board=[]` 的诚实光照事件。它不伪造盘面，不进入推理或普通候选提交。正常帧继续原有 motion、投票、denial、reference、置信度和规则链。
- controller 在原 token、当前局、camera identity 检查之后、board shape 和盘面差异之前处理严重光照。未 confirmed 的严重帧清普通错误 streak 和 points 并继续等，不会被前三张快速坏帧提前判成 no_stone。满足三帧/一秒才返回明确过亮或过暗，无点标记、无 SGF、无落子音，关闭窗口并恢复同方计时；原八秒边界保持。
- 真正 BIND 后，仅在当前 local mode 已绑定、真实 bootstrap/reference、geometry 和 camera 齐备时完成既有 pose/sync 转换。service 的 session/game/generation 核验保留；新局、旧 generation、geometry 丢失和相机断开不能对外维持可用状态。窗口外仍不推理、不喂自动 sync、不发自动落子事件。
- 首手回归明确使用 `pose_locked=False`，没有借 helper 预设锁定：真实参考就绪后 locked/synced，一次确认只提交一手、换方、发一次音效，关闭窗口后停止推理。首子早放时拒建假参考；拿回棋子、显式 false→true 重试后才建立真正空盘参考。
- physical `ready()` 只有在当前局及权威物理就绪校验成功后，才清除遗留的 idle/unavailable。并发确认的提前返回、失败校验和其他 reason 保持原行为。

## 质量及整体核对

实现局限于既有窗口状态、可选事件元数据和现有 readiness 发布点，没有增加常驻监控、替代识别链或新的重试服务。直接检查了真实 worker→service→controller/API 回归，覆盖从第一张严重帧开始的拒绝过程，并非只给 controller 填造好的 confirmed metadata。

Task 1、Task 2 的既有 GO 证据继续有效；整体代码复核确认：

- 控制完成使用 monotonic 30 秒预算；None 等待，终态仍需实际 manual 模式读回。取消在取帧前后及发布边界检查，恢复有独立预算且不被已置位的 cancel 跳过，不回写不可信绝对曝光值。
- 早期控制失败保留原 manual 错误；只有共享 probe 的三张请求后、严格 seq/ts 递增新帧才可附加严重光照证据。缓存、超时、pending、缺帧不能生成环境光警告。LED 差分、锚点拟合及阈值未变。
- 服务状态与持久化提交边界保留；失败/取消同锁保存 stopped_phase，ready/start/reuse 清除。全量搜索确认现有活动 phase 消费者均包含 converging_exposure。
- 所有实体标定入口复用共享五步屏。对局重新标定等原局、新 revision、实际 bind 成功后再处理；本地局不额外 RESET_SYNC 销毁新参考，非本地局保留原局限定的一次 reset。
- 严重提示需要权威原因及相应可信证据；本地复用同一 voice 实例，几何 revision/reason 与 local game/node/reason 去重保留。首手引导等待实际准备和 pose，就绪失败有独立 bind 重试。沿用 Task 2 的 1024×600 视觉 GO、两条 Tingting MP3 实际播放完成及听辨限制记录；本轮后端改动无需重复截图。

顺带只读检查了 ignored `output/rk-exposure-release/rk_release.py` 与 `cloud/cloud_release.py` 的发布修改边界，未发现阻塞：RK 先核验源码 hash、唯一原生 launcher、unbound 和无活动应用连接，二次空闲核验后只停 KaTrain；同目录临时文件加 replace 避免改写 hardlink，assets 先于 index，失败恢复本轮写入文件。云端固定 live base、新镜像单独 tag，保存 compose/env，验证转义及运行环境，只对 web 执行 `--no-deps`，保留 sibling 容器与卷，切换前再次核验零用户活动。此时最终 manifest/context 尚未生成，本报告不把 helper 源码检查视为候选 hash 或生产发布验收，也不声称增量后端成为全量同 SHA 源码。

## 验证证据及边界

- root 对稳定源码执行六个直接相关 Python 文件：`CI=true .venv/bin/python -m pytest tests/test_geometry_calibration_service.py tests/test_geometry_api.py tests/test_vision/test_local_confirmation_window.py tests/test_local_move_confirmation.py tests/test_led_geometry_calibrator.py tests/test_vision/test_worker_commands.py -q --tb=short`，**278 passed，16.16s，exit 0**，仅既有 passlib/crypt 弃用警告。审核者读取了 `output/rk-exposure-release/verification.json`；按比例原则未再重复该组合。实现者另有 Task 3 **17 RED → 149 passed** 记录。
- 前端沿用 root 的相关十二文件 **204 passed**、最终短文案相关 **92 passed**；`tsc -b` 和主要生产源文件 targeted ESLint exit 0，GamePage 七条既有 hook warnings 及 api.ts 既有 lint 基线已在 Task 2 报告说明，未宣称全仓 lint 干净。
- 审核者读取 full 与 strict build 日志：两者构建完成；strict 的 Box SSO、无 three.js / Galaxy / live API 边界检查通过。
- 审核者执行 `git diff 90e89e8fd --check`，exit 0；核对稳定 Task 3 只有上述五个文件。未跑 GPU、全量 Python 或无关回归，未编辑产品代码。

本次审核未操作设备、浏览器或用户当前棋局。发布必须继续遵守已批准的空闲切换和实际验收步骤；代码 GO 不授权中断后来仍在使用的对局。
