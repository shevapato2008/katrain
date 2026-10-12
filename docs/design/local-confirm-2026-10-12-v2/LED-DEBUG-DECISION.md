# LED 标定未亮：独立故障决策

2026-10-12，用户授权的独立 `gpt-6-astra / max` 决策。依据本地当前源码、既有测试及主代理取得的设备日志/状态；只读分析，未改应用代码、未部署、未操作设备局。

## 结论

**确认存在曝光控制尚未完成就被标定服务判失败的竞争条件，允许先离线修复等待与取消边界。它解释当前标定为何在闪灯前退出，但不能证明曝光最终一定成功，也不能排除 LED 实际出光故障。**

调查开始时设备的用户 AI 局仍在运行，因此没有授权自行结束该局或重启。**用户随后已明确该局不用保留、可以应用修复**，这项特定阻塞已解除；该授权不适用于以后新开的局。曝光阶段展示的追加决定见末节。

## 因果与证据边界

1. `GeometryCalibrationService._run()` 先执行 `_converge_exposure()`，返回后才构造并调用 LED calibrator。当前 `manual exposure lock readback failed`、进度 `0/13` 和标定期间只有清灯的 `submit 0` 相符：失败发生在闪灯循环之前。
2. `CameraManager.request_controls()` 排队新请求，并将 `controls_effective` 置为 `None`。相机读线程执行 `_apply_pending_controls()` 时，如 `lock_exposure=True`、没有固定曝光值、请求原生 manual 模式且没有显式 exposure，会进入 hardware auto-then-lock：最多 90 帧收敛、3 帧交接稳定、6 帧验证。此期间直接调用 `cap.read()`，不更新普通消费者看到的 `_latest_frame/_frame_seq/_frame_ts`。
3. geometry 只等待 `EXPOSURE_CONTROL_VERIFY_MAX_FRAMES=3` 次 `grab_fresh()`。相机的 `grab_fresh()` 默认每次最多等 2 秒，超时可返回同一旧帧。三次调用并不代表控制过程完成，也不一定是三帧新图。若此时结果仍为 `None`，服务抛出 readback failed，随后在 `finally` 排入恢复请求，增加 controls generation。
4. 主代理记录 14:05:21 标定已失败清灯，14:05:37 相机线程才报告 `brightness changed after locking hardware AE`；后来还有 `hardware AE did not reach the target brightness band`。这个先后关系符合抢跑，但较晚的日志本身也是**真实失败证据**，不是可忽略的等待噪声。消除早退之后，正确结果仍可能是“曝光锁定失败”，而不是进入点灯。
5. runtime 的 `lock_exposure=True` 来自持久化的 `hardware_auto_then_lock` profile，主代理已核实。它不同于 `--vision-auto-exposure off`：后者是视觉 worker 的软件 AE 开关。`CameraManager` 构造默认值为 false，不能把默认值当作本机有效设置。
6. 空盘 JPEG 的 median 157、clip 0 只描述那个采样时刻；不能证明之后的原始帧序列持续带内，或切 manual 后保持亮度。不能以单张截图替代模式读回和锁后验证。

LED 的 `transport=true`、缓存 `LINK UP / ack OK`、入队成功及无串口错误，只证明已观测到的传输/板端确认。`board_status=null` 表示当前没有有效的新鲜缓存，不能直接读作连接故障。主代理追加的中心点低亮度测试确实提交了点灯命令，但画面未能明确确认出光；**没有排除灯珠、映射、亮度或其他物理链路问题**。先解决已确认的前置软件失败，不能因此宣称 LED 硬件正常。

## 最小正确修复方向

- 将“最多三次取帧”改为**基于 monotonic 截止时间、可取消的控制结果等待**。复用已有曝光等待量级（例如当前 30 秒墙钟预算），而不是随意扩大帧次数；把总时限写清并在测试中缩短。`None` 是等待中，`False` 是已明确失败，`True` 才能继续，真实 manual 模式读回仍需满足原生值校验。始终未知到达时限时应诚实报告 pending/timeout，不能标成功。
- 等待不应靠反复测旧图来推进，也不能忙轮询。控制完成后再读取相机提供的新图，既有锁后亮度验证和 calibrator 曝光闸继续工作。保留原生模式 `1/3`、亮度带、稳定帧与 clip 规则，不回放不可靠的 `exposure_absolute`，不绕过检查让 LED 先闪。
- 在等待前、等待中和进入 calibrator 前处理取消；取消不得变成普通 readback failed，不进入闪灯、不持久化新几何。已取消时不要再启动一次不必要的 manual 收敛尝试。外层恢复仍负责回到开始前的模式，LED 清除及状态收尾保持。
- 恢复流程也有同样的三帧缺陷，须使用有界的结果等待；**恢复不能被已经置位的用户 cancel 直接跳过**。只有当前恢复请求得到确认才可声称已恢复；超时/拒绝保留诊断，不能用上一代结果当作本次结果。
- 相机仍由原读线程独占。先在 geometry 等待/取消层完成最小修复，沿用现有串行控制队列和 generation 保护，不另开相机、不跨线程直接设置 UVC、不建立新任务框架。若针对性的交错测试证明旧请求会覆盖新的恢复结果，再把 generation 检查限定补到相机控制的发布/取消处；不要为假设中的泛化场景重构采集架构。

## 最低充分验证

主代理正在新增的“控制结果超过三次旧帧才到达”回归是正确起点。聚焦证明：

- 延迟结果最终为 true 时，旧实现确实早退，修复后只在真结果到达后进入 calibrator；缓存帧的次数不决定成功。
- 延迟或立即返回 false，以及一直 pending 到截止时间，仍失败且不闪灯、不发布几何。
- 等待期间取消，不进入 calibrator、不持久化，取消语义保留；恢复结果即使较晚到达也被正确等待，旧控制结果不能冒充恢复成功。
- 既有曝光失败、恢复与相机单线程/generation 测试保持通过。无需重复 v2 前端视觉、云页面或整套 AI 回归。

离线通过只能证明软件竞争条件修复。安全空闲后再在设备进行一次实际标定，区分“控制 pending”“相机明确锁定失败”“已开始 LED 闪灯但未检出锚点”三类结果。若真实锁定仍失败，保留这一事实并按那次原始帧/模式证据继续定位；不同时乱调阈值、曝光值、LED 亮度或重装硬件。物理出光尚未得到证实时，仍须保留相应验收限制。

源码依据：[geometry 服务](../../../katrain/web/core/geometry_calibration_service.py)、[相机控制与读线程](../../../katrain/vision/camera.py)、[相机初始化](../../../katrain/web/server.py)、[LED 校准器](../../../katrain/vision/led_geometry_calibrator.py)、[LED 状态](../../../katrain/web/core/led_service.py)、[geometry 测试](../../../tests/test_geometry_calibration_service.py)、[控制读回/generation 测试](../../../tests/test_vision/test_auto_exposure.py)。

## 用户追加：曝光作为可见标定步骤

用户明确要求“曝光收敛也做成标定的一步”。**设计 GO：沿用现有标定页面，在准备空盘之后插入“曝光收敛并锁定”，不另起全套 Artifact 或视觉探索。**

| 顺序 | 页面步骤 | 真实阶段 |
| --- | --- | --- |
| 1 | 准备空盘标定 | 原准备/等待状态 |
| 2 | 曝光收敛并锁定 | `converging_exposure` |
| 3 | 定位棋盘四角 | `flashing_corners` |
| 4 | 定位九个星位 | `verifying` |
| 5 | 生成空盘基线 | `building_baseline` |

`_run` 挂起识别 worker 后、进入 `_converge_exposure` 前真实发布新 phase。直到曝光工作通过且校准器进入下一步才推进，不让计时器或前端自行推断完成。原 `progress.total=13` 只表示锚点，不增加曝光百分比或改成 14。旧的 `dark_reference` 兼容值不另画为独立步骤，因为每个锚点本来都交替拍暗/亮帧。

新增可选 `stopped_phase`：失败/取消切换为终态**之前**在同一锁内记录最后实际活动阶段；恢复曝光过程不能覆盖它，新开始和成功须清空。UI 优先按该字段标记失败/取消所在步骤；旧响应缺字段时保留兼容处理，不把未知阶段伪造为已证实。曝光错误不能因检测到 0 个锚点而被画到“四角失败”。五步的运行映射、失败映射、基线质量行、完成标签及相关注释/测试都要同步更新。

所有已有 ACTIVE 判据须包含新 phase，至少覆盖服务、geometry API 的预览节流/旧几何保护、API 类型、`GeometryContext`、`BaipuSessionRoute`、`GeometryCalibrationScreen`。曝光期间保持运行态：只能取消，不可继续、沿用旧几何、重新开始或挂起摆谱的点灯流程；服务端仍以运行线程互斥为准。

文案保持短而真实：运行提示可为“正在稳定画面亮度并锁定曝光”；真实拒绝显示“曝光未能锁定”，等待超时显示“曝光调整超时”。保留重试与取消语义，不宣称 LED 故障已修好；原始错误 detail 留给诊断。UI 只增加一行并沿用现有滚动/样式，做一次 1024×600 实际预览，核对运行/曝光失败显示及底部按钮可达；由同一独立代理复核真实代码和代表画面，无需新增审核代理或重跑 v2 全部视觉。

主代理已取得更强的串口测试证据：固件 STATUS 正常、LINK UP/ack OK，以及 BRIGHT/SETI/SHOW/CLEAR 的真实响应；仍需真实画面或用户观察证明实际发光。该证据没有取消曝光真实性要求。

完成等待、取消、真实 false、超时和 manual 模式读回的聚焦验证与代码复核后，只应用本次围棋服务/对应静态修复；不因此重启其他棋种或云服务。继续使用数据盘备份与同目录临时文件替换，保留硬件配置和历史状态。最终报告区分“软件等待/阶段显示通过”“串口命令通过”和“物理出光/完整标定实际结果”。
