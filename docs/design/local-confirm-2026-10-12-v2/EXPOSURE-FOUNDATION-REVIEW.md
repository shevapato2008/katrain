# 曝光共享后端基础审核

日期：2026-10-12。审核对象：批准计划 `docs/superpowers/plans/2026-10-12-rk-exposure-calibration.md` 的 Task 1，以及为该任务提前完成的共享 fresh-frame probe。基线：`524aee1ce79a2f1d70d1d7de36d98004a721a3f4`；审核在实现方正式 DONE、源码稳定后结束。

范围为六个未提交文件：`geometry_calibration_service.py`、`geometry.py`、`led_geometry_calibrator.py` 及对应三个测试文件。前端草稿和后续确认窗口逻辑由各自切片审核。

## Spec compliance：GO

- `GeometryCalibrationService._wait_for_exposure_controls` 使用独立的 monotonic 30 秒预算；缓存帧不再耗尽三次机会，`None` 继续等待，终态再校验 `controls_effective is True` 与有限、匹配原生 manual 1 的模式读回。超过期限的返回不会放行标定。
- 取帧前后、等待唤醒后均保留取消检查，收敛返回后还有进入 calibrator 前的检查。失败和取消保持旧几何与原持久化发布边界；恢复使用独立预算并忽略已置位的取消事件，只恢复可信模式，不回写绝对曝光 shadow，恢复异常仅记录 warning。
- `converging_exposure` 在 suspend 之后、收敛之前发布，进度仍为 0/13。服务及预览节流的活动阶段集合已包含它，期间不能沿用旧锁。失败或取消在同锁下保存 `stopped_phase`；start、ready、operator reuse 清空，恢复流程不修改它。
- 控制终态失败或模式读回不符时保留原 manual 错误，并且只有 camera 可用、控制非 pending、共享 probe 获得请求之后三张不同且 seq/ts 递增的新鲜帧、严格曝光 gate 拒绝时，才追加包含统计、reason 和 confirmed 的诊断。超时、缓存、普通画面、不足三帧、取消不生成该告警。
- `probe_frame_exposure` 最多取三次，三张必须全部新鲜；不足返回 `None`，标定报告 `no_frames`。取消不会继续 probe 或闪灯。245 / 0.35 / 20 阈值、LED 差分与拟合保持原行为。
- `/calibrate` 的 auto/manual trigger 均调用同一 `start → _run → _converge_exposure`，没有仅对 `pvp_local` 生效的分支；实体场景入口的前端接线由后续集成继续核对。

## Code quality：GO

未发现 Critical 或 Important 问题。控制等待和诊断使用小范围共享函数，取帧新鲜性规则只有一处；新字段沿用现有状态锁和发布流程，原错误不会被补充诊断或恢复失败覆盖。测试覆盖延迟缓存、真实失败、错误/非有限模式、超时、取消、延迟恢复、阶段和告警证据，范围与改动相称。

验证证据：root 转交实现方最终 `CI=true .venv/bin/python -m pytest tests/test_geometry_calibration_service.py tests/test_geometry_api.py tests/test_led_geometry_calibrator.py -q` 为 **167 passed，5.18s**。审核方重新读取稳定后的六文件差异并执行对应 `git diff --check`，通过；未重复全量回归。

结论：Task 1 审核通过，可进入下一切片。真实设备、全部实体入口与发布验收继续按后续 Task 2–5 执行；本报告不把单元测试视为实机标定成功证据。
