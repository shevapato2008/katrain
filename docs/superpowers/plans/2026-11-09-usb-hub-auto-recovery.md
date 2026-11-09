# 共享USB Hub受限自动恢复 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 纯软件找回仍连接却无法枚举的camera或ESP，每次故障最多一次恢复，保持当前页面、登录与权威局面。

**Architecture:** Linux适配器验证Hub及全部端口，协调器复用CameraHub现有5秒恢复线程；小型admission gate与视觉循环边界ACK隔离采集和业务提交。持久episode与跨进程锁防循环。仅显式启用的RK board模式运行；前端只修正瞬断导致的卸载/误开标定，不作视觉重构。

**Tech Stack:** Linux USBDEVFS/Hub class、Python标准库/Pytest、CameraHub/LedService/InProcessAdapter、React/Vite。

**Spec:** [用户批准的设计](../specs/2026-11-09-usb-hub-recovery-design.md)。原诊断及16:52实机成功试验在控制器 `docs/superpowers/plans/2026-11-09-typec-camera-usb-isolation.md`，不再以硬件调整为前提。基线develop c34ed5a89；现有owner四组151项测试通过。

---

## Chunk 1: 冻结契约与并行开发

### 共享契约（并行前冻结）

1. A创建 `katrain/vision/hardware_recovery_gate.py`：`HardwareRecoveryGate.active: bool`、`generation: int`；`try_use()`返回使用令牌或None，`try_recovery()`仅在无使用者时原子返回独占令牌并增加generation。令牌支持上下文与幂等`close()`，只释放自身归属。计数锁不跨IO/await持有，使用令牌涵盖完整异步业务。
2. A创建 `LinuxUsbHub(hub_path='1-1', camera_port=4, led_port=3)`，`snapshot()`返回Hub身份及全部4端口/child状态；USB位与reset operation对象仅A内部解析。`UsbHubRecovery(adapter, camera, led, vision, gate, state_path, *, clock=time.monotonic, wall_clock=time.time)`公开`tick()`、`stop(timeout=2.0)->bool`、静态`startup_allowed(state_path)->bool`。constructor不启动线程。stop=False明确表示旧操作仍在运行；startup检查受控operation flock，锁忙或锁无法验证则拒绝open。若锁已核实空闲，即使episode JSON损坏/latched/inflight旧记录未清也可正常open，但自动reset继续禁用/锁存；不能仅因限流JSON损坏拖垮正常设备。
3. B给两设备owner提供 `begin_usb_recovery(timeout=2.0)->bool`、`end_usb_recovery()`、`set_usb_startup_check(callback)`。每次首次/重连open前检查callback；False保留低频重试但不open。CameraHub提供`set_device_recovery(recovery)`，在现有循环释放生命周期锁后tick，即使camera正常也调用以覆盖ESP异常。
4. C给VisionService/InProcessAdapter提供同名begin/end USB暂停，不支持ACK的worker返回False。VisionService可注入共享gate；请求开始立即禁止旧业务消费/新local窗口。ACK位于当前推理结束后的循环边界，暂停monitor/local confirmation等全部帧处理，不覆盖已有hint/UI暂停。
5. 固定次序：稳定候选→取得业务独占gate和operation flock→持久锁存episode/inflight→Vision ACK并清旧队列/窗口→两设备owner静默→固定child新鲜复核全部身份/端口→一次reset→真正退出后释放设备owner让正常重连运行→真实新帧/LED恢复后解除视觉/业务gate。设备仍不可用时继续轻量观察，不再次reset；未退出操作不释放owner。正常业务已结束或scope改变时不恢复旧窗口。
6. child继承operation flock直到真正退出；parent超时不等于复位取消。新服务在camera/LED首次open之前检查旧操作锁。明确已退出失败与仍inflight两种结果；stop后不得启动新reset。
7. A/B/C/D只编辑所属文件，不并行操作共享Git index；报告改动/测试后由控制器顺序commit。接口调整先同步控制器与其他实现者。
8. 设备连接状态与业务就绪分开：USB暂停期间仍可从owner发布camera/LED各自真实连接状态，不能因另一侧未恢复而把已恢复侧显示断开；recognition/物理输入在新帧屏障完成前保持不可用。reset已退出后允许两个owner正常重连；正常新帧与需要的transport可用才恢复对应业务，真实Type-C LINK DOWN不冒充USB失败，也不能让camera状态永远等待棋盘UP。业务失败继续由原就绪条件阻止，不伪报全局成功。

### Task A: Linux适配器、gate与恢复策略

**Files:** Create `katrain/web/core/linux_usb_hub.py`, `katrain/web/core/usb_hub_recovery.py`, `katrain/vision/hardware_recovery_gate.py`; Test `tests/test_linux_usb_hub.py`, `tests/test_usb_hub_recovery.py`。

- [ ] **Step 1:** 用假sysfs/usbfs、假时钟和假owner写失败用例，确认缺实现导致失败再实现。
- [ ] **Step 2:** 固定1-1、Hub1a40:0101、恰为4端口；camera port4=0ac8:0346、ESP port3=303a:1001。Hub路径严格解析；验证class/descriptor、全部4端口connection/power/enable/reset/过流。未配置端口connected即拒绝，即使无child；已有camera/serial alias必须匹配预期USB child。动态取busnum/devnum，open后fstat与新鲜sysfs复核防地址重用。GET_STATUS=class/other 0xa3、length4、timeout1000ms，按ctypes native ABI计算ioctl；不写POWER/authorized，不卸驱动。
- [ ] **Step 3:** 自动候选只限已验证终态：connected+powered+disabled、无reset/过流、缺child且状态稳定10秒。enabled缺child只观察；child已存在的取流/握手失败交原owner。双端正常廉价检查；Type-C LINK DOWN、任一/两者真physical=0不reset。
- [ ] **Step 4:** 持久schema明确latched、last_attempt、inflight、attempt_id，跨进程flock保护、受控owner/mode，拒绝symlink/异常类型，原子落盘。任何破坏性静默前锁存；静默失败/取消亦消费episode，避免每5秒关相机/清灯。时间异常、坏JSON、无权限/写入失败禁用。部署/回滚不覆盖运行时state。
- [ ] **Step 5:** 固定child入口/参数，无shell或公开reset API。8秒期限后kill并有界收割；仍未退出则保留flock/inflight、静默/gate，tick只poll旧操作。真正退出才恢复owner。stop关闭新提交、取消未开始操作、有界等待，不持CameraHub生命周期锁join、不假报完成。child紧邻ioctl复核全部端口/身份，child已出现则取消，避免重置已恢复设备。
- [ ] **Step 6:** 最小全局冷却60秒，episode跨重启锁存。操作结束后20秒settle内忽略自产变化，读取失败/Hub暂失不算physical=0。仅settle后同一核实Hub有效外部0→1，或双端USB+真实服务健康30秒，才持久解除latched；冷却始终有效。成功必须camera新帧、LED transport/LINK，不能以ioctl成功代替。
- [ ] **Step 7:** 测试正常/真拔线/Type-C正常0次、两目标disabled缺child各1次、enabled缺child0次；枚举竞争、全部端口/alias/身份/过流拒绝；并发与跨进程互斥、静默/ACK失败、超时仍inflight/已退出失败、stop、坏state/时间、跨重启episode/冷却、首次open闸门与自产事件。Run: `PYTHONPATH=. /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest tests/test_linux_usb_hub.py tests/test_usb_hub_recovery.py -q`。自审后报告，由控制器commit。

### Task B: camera/LED owner静默

**Files:** Modify `katrain/web/core/camera_hub.py`, `katrain/web/core/led_service.py`; Test `tests/test_camera_hub.py`, `tests/test_led_service.py`。

- [ ] **Step 1:** 先写失败用例：静默无缓存帧/新批次、阻塞reader/serial不能假ACK、timeout无晚到未归属暂停、stop/end幂等、startup检查在首次open前。
- [ ] **Step 2:** CameraHub循环释放锁后tick；暂停期read/grab/is_connected均不可用，旧reader确退出才ACK，保留lease，不建第二reader。end只解除自身USB暂停并唤醒正常恢复，不改geometry/session。旧operation仍inflight时持续拒绝open；stop先协调器后owner，不能锁内join。
- [ ] **Step 3:** LED请求即拒绝新业务，由worker确认静默并关闭串口、失效旧generation/strict批次/灯光意图，唤醒等待者，不跨线程close。end按原CLEAR/SHOW/BRIGHT握手，不重放旧指示。timeout/stop保护暂停归属。
- [ ] **Step 4:** Run: `PYTHONPATH=. /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest tests/test_camera_hub.py tests/test_led_service.py tests/test_vision/test_camera_recovery.py tests/test_vision/test_device_events.py -q`。基线151通过，报告新增结果，由控制器commit。

### Task C: board装配、标定/物理提交/WS原子边界

**Files:** Modify `katrain/web/core/config.py`, `katrain/web/server.py`, `katrain/vision/service.py`, `katrain/vision/worker_inprocess.py`, `katrain/web/core/geometry_calibration_service.py`, `katrain/web/core/local_confirmation.py`；必要WS边界 `katrain/web/api/v1/endpoints/vision.py`。Test新增 `tests/web_ui/test_usb_hub_recovery_wiring.py`, `tests/test_vision/test_usb_recovery_barrier.py`，及现有geometry/local-confirmation聚焦用例。

- [ ] **Step 1:** 默认 `KATRAIN_USB_HUB_RECOVERY=False`，仅显式启用+Linux+board+完整camera/LED owner+精确拓扑有效才装配。state路径 `/var/lib/smartbox/usb-hub-recovery/state.json`。cloud误开启也不运行。camera/LED首次open前安装startup check；初始化结束创建协调器交给现有线程。部分启动/关闭清理，不新增HTTP控制面。
- [ ] **Step 2:** geometry start完整worker事务、preflight、relocate/confirm等采集发布持gate use令牌，thread.start失败/finally释放。恢复与新采集原子互斥，busy复用CalibrationBusy，不以phase快照代替。
- [ ] **Step 3:** `_vision_move_poller`在取move前取得use令牌，覆盖`_handle_confirmed_move`全部await/实际提交；`LocalConfirmationController._run`每次取候选到真实play/forward结束持令牌，不给整个长期任务持令牌。已接受动作未完成则延后reset；恢复中拒绝新physical提交，不扩大封锁触屏业务。
- [ ] **Step 4:** Vision USB请求独立于hint/UI pause。请求开始即禁止get_confirmed_move/get_local_window_observation/poll_events/open_local_window；worker当前推理结束后循环ACK，暂停所有帧处理。ACK后清worker/service旧队列、失效旧local-window token、重置暂存识别累积，保留expected与绑定。不支持ACK则不reset。
- [ ] **Step 5:** asyncio线程清WS旧队列，内部项带gate generation，sender发送前校验，防已取出旧项晚发；公开WS payload不变。新帧就绪再解除USB门禁，失败保持真实不可用，不复活旧token。
- [ ] **Step 6:** 聚焦验证cloud/default无reset、startup-before-open、stop；推理延迟ACK、既有UI pause、旧move/window/WS丢弃；标定与reset竞争、已取出move正在await时reset延后；新帧/新窗口恢复。已有board-lifespan夹具17项import失败若遇到单列，不篡改全局stub。报告，由控制器commit。

### Task D: 最小页面保留

**Files:** `katrain/web/ui/src/kiosk/components/vision/PhysicalBoardGuard.tsx`, `katrain/web/ui/src/kiosk/pages/GamePage.tsx`及对应聚焦测试。无新布局、弹窗、文案或依赖。

- [ ] **Step 1:** 先写失败用例：已放行页面、geometry有效但camera/recognition瞬失，children不卸载；首次进入不就绪或真geometry失效仍原守卫。放行记忆按route/session scope重置，不跨新游戏绕过初始校验。
- [ ] **Step 2:** readiness真实。GamePage区别真正geometry失效与camera-only瞬断，后者停物理输入、保留页面，不自动强开完整标定；恢复用新local窗口/当前有效参考重建就绪，不复活旧token。失败/真几何失效保留原恢复入口。
- [ ] **Step 3:** 跑两组件与直接依赖用例；full/strict各构建一次。同目标viewport检查一个代表性活动页：页面/登录保持、无刷新跳页、物理输入不就绪时关闭。不做视觉重构/全状态重拍。报告，由控制器commit。

## Chunk 2: 审核、发布与交付

### Task E: 独立审核与集成

- [ ] **Step 1:** spec+plan交独立Astra Max最多两轮，未通过不开产品实现。第1轮指出持久episode、inflight、业务门禁、全部端口/枚举竞争、UI卸载、共享契约，本版已定稿；第2轮验证闭合。用户已批准目标与实施，不重复授权。
- [ ] **Step 2:** 用 @superpowers:subagent-driven-development 并行A/B/C/D、严格文件归属；先独立规格核对，再用新的独立Astra Max审核完整代码/测试/发布操作器，修到通过。只读发布准备可并行，远程部署串行。
- [ ] **Step 3:** 集成聚焦Python/UI及full/strict构建，用 @superpowers:verification-before-completion 验证后顺序commit；将 `impl/usb-hub-recovery-20261109` 成果merge进实际 `fix/kiosk-ui-debug`，不能只部署临时分支。保留原诊断文档和其他dirty。

### Task F: 常规四步发布及实机验收

**工具范围:** 独立 `output/releases/usb-hub-recovery-20261109/`。云复用近期支付release/native-release工具但fresh核对配置；RK差量工具需离线测试与最终独立审核。只替换精确Python、完整full/strict static及唯一drop-in，保留11语/账号/DB/标定/完整整包标记，另写delta版本。attempt state由程序初始化；部署/回滚不覆盖、删除、倒退已有记录。

- [ ] **Step 1:** 再fetch develop，merge进当前功能分支、解决冲突、验证、push当前分支；再merge/push develop。
- [ ] **Step 2:** 父仓独立工作树基于fresh main，vendor/katrain指发布develop，commit/push main；原父仓vendor dirty保留，不顺带合无关功能/文档。
- [ ] **Step 3:** TEST home-ubuntu先验收，再PROD ucloud-v100；fresh运行镜像/Config/HostConfig/Mounts/Networks不可变部署。保留8项WECHAT_PAY_*、只读secret bind、会员/计费开关和非Web容器；cloud USB关闭、无USB权限。不重启engine/DB/Cron/MinIO，验health及代表Galaxy/kiosk页面。
- [ ] **Step 4:** 协调RK独占窗口，fresh无写入中对局/标定，保留renderer/URL/登录/模式/语言外观。Go范围停启；manifest before-hash/absent CAS、备份、原子替换/回滚。唯一配置增量 `/etc/systemd/system/smartbox-katrain.service.d/35-usb-hub-recovery.conf` 启用 `Environment=KATRAIN_USB_HUB_RECOVERY=true`。保留fd7/4235整包标记，另写delta哈希。旧operator六文件/runtime hash/仅标定页门禁已过时，不原样用。
- [ ] **Step 5:** 验RK候选代码/启用、正常0复位、新JPEG、LED transport/LINK、页面/登录/语言。受控且可回滚地验证一次自动异常恢复，不反复制造USB故障；不能完成的现场物理拔插明确待验，不以人工试验代替自动交付。完成恢复原页，释放本任务锁。
- [ ] **Step 6:** session文字报告各仓commit、两云镜像、RK差量版本、测试/审核、真实恢复结果和待用户物理验证项。
