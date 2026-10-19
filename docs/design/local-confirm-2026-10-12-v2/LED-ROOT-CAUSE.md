# RK 标定曝光故障：调查结论

2026-10-12，用户报告 LED 已连接但标定不亮。实际 geometry/status 为 failed、0/13，错误 `manual exposure lock readback failed`；日志每次只 submit0 清灯，未进入锚点闪灯。

camera.py、geometry_calibration_service.py、led_service.py 的设备文件 hash 与当前仓库相同，此次 v2 静态发布未改它们。相机14:04 USB断线重连，随后多次标定失败。

已复现的代码缺陷：CameraManager 的持久化 hardware_auto_then_lock 策略在相机读线程执行90帧收敛、3帧settle、最多6帧锁定验证。期间不更新公共帧序号；grab_fresh可超时返回旧图。标定只调用最多3次便将 controls_effective=None（尚待完成）视为失败，finally再排入恢复，覆盖请求generation。回归在延迟5次旧图时稳定RED；有界等待草稿后GREEN。CLI vision-auto-exposure off 是软件AE开关，与 owner lock_exposure 不是同义。

不能把失败直接解释为环境太亮：当前空盘JPEG median约157、clip0；释放camera owner后的实际模式3→1测试，写入及读回成功，3帧自动收敛、3帧手动settle和3帧验证均median163、clip0，0.834s完成。历史14:05:37确有brightness changed after locking、随后target未达标，当前无法复现其物理诱因；保留真实失败与阈值，修正等待后再走真实标定验收，不伪称所有历史现象只由时序造成。

LED实际满亮度单点测量：BRIGHT255、SETI90白255、SHOW均ACK OK；相机看到中心灯实际发光，lit-dark最大增量213、791像素增量>30。LINK为UP、ackOK，证明此次测试灯板具有出光能力；早先guidance_scale0.08低亮度照片不能用来否定它。测试后CLEAR/SHOW并恢复原围棋服务，未更改持久化标定、模型、固件或配置。

用户明确允许当前AI局不保留、可应用修复。尚未发布任何故障修复源码；此前等待及五步UI是新流程指令前的未提交草稿，已冻结。按最新要求，先正式writing-plans、独立Astra max计划审核最多2轮，再subagent-driven-development，最后Astra代码审核至通过。

原始JPEG/串口与曝光probe回执在 ignored `output/rk-led-debug-20261012/`；设备对应 `/mnt/data/smartbox-deployments/rk-exposure-debug-20261012/`。未将测试信号当作正式棋局落子。

## 2026-10-12 发布后的实机确认

正式计划两轮审核、实现与独立最终代码审核通过后，`754c24b2e` 已部署两云和 RK。RK 真实呈现曝光第 2/5 步，手动模式读回 1，随后 13 个 LED 点全部定位、空盘基线成功，geometry ready；RMS 0.991 px。确认此次等待修复能完成真实标定，不将无法复现的历史物理亮度失稳一并归因。保存棋谱和报告均保留，详见 [EXPOSURE-RELEASE.md](EXPOSURE-RELEASE.md)。
