# 共享USB Hub异常后的受限软件恢复

用户已在2026-11-09语音中批准：优先纯软件恢复，不改硬件；保留轻量状态检查；只有“端口仍物理连接但设备持续无法枚举”才执行一次Hub复位；正常拔线不复位；不因自身复位事件循环触发；保持页面、语言、登录、布局。按 writing-plans → 独立Astra Max最多两轮计划审核 → SDD并行 → 独立规格与新的Astra Max代码审核通过 → 四步发布执行，无需再次请求相同设计授权。

## 已验证的基础

RK3562内核5.10.209，Hub1-1为1a40:0101；port3 ESP303a:1001，port4 camera0ac8:0346。16:48 Hub GET_STATUS证明camera connected+powered但disabled、无设备节点。单端口PORT_RESET只启用端口未重枚举；16:52 USBDEVFS_RESET共享Hub后摄像头约1秒重新枚举、约5秒状态可用；ESP也重新枚举，约15秒内LINK恢复。PID11786不变，16:53通过现有共享snapshot取得真实JPEG。此为一次现场验证，不能保证所有场景时延。原始证据在控制器 `/Users/fan/Repositories/katrain-kiosk-debug/output/diagnostics/typec-camera-20261109/`。

## 最小实现与边界

- 仅RK board模式显式配置启用，默认及云端关闭。显式限定Hub拓扑、端口及VID/PID；读取sysfs动态busnum/devnum，不固定USB地址；未知同Hub设备/拓扑变化/身份不符/当前过流均禁止复位。
- 复用CameraHub恢复线程的5秒轻量检查与现有udev唤醒；保留LED每2秒LINK。不因为LINK DOWN而复位：Type-C不产生Linux USB枚举，真实棋盘拔线与USB异常分开。
- 目标physical=false视为真正拔除，绝不复位。自动候选收窄为已验证的失败终态：connected+powered+disabled、无reset/过流、child缺失且稳定10秒；enabled无child继续观察，不打断正常枚举。已有child但服务失败交原owner重试。
- 单个异常episode最多一次整体Hub复位，最小冷却60秒。持久schema包含latched、last_attempt、inflight、attempt_id，破坏性静默前原子锁存；静默失败亦消费episode。只有操作退出、settle后核实Hub的新鲜外部0→1，或双端USB及实际服务健康30秒，才持久解除锁存；读取失败/Hub暂失不是0，冷却始终有效。时间异常、损坏、无权限均禁用自动恢复；部署/回滚不覆盖记录。
- 两个现有owner协同暂停：camera禁止返回缓存帧并停止旧reader；LED在自己的worker关闭串口、作废旧批次和灯光意图，停止新业务提交。无法在预算内静默则取消复位。不能在HTTP线程、udev回调或持有CameraHub生命周期锁时等待另一owner。
- 共享Hub复位不可完全无感：两个USB设备会短暂离线。界面保持原页与登录，不刷新、不新增弹窗/动效、不虚报连接；摄像头与LED分别按实际状态恢复。
- 一个小共享admission gate覆盖完整标定/preflight/relocate事务和已接受的物理落子提交；无使用者才原子进入恢复，新业务被拒绝，不持锁等待IO。in-process worker独立USB请求在推理循环边界ACK，暂停monitor/local confirmation等全部帧处理；服务/worker/WS旧队列与旧local-window token失效。保留绑定/权威棋盘，不覆盖hint/UI暂停。
- 固定reset子进程继承跨进程operation flock直到真正退出；8秒期限后终止并有界收割。仍未退出则保留inflight、owner静默与业务gate，tick只观察旧操作，禁止新操作。新进程在camera/LED首次open前检查旧操作锁。stop禁止迟到reset；最终全部端口/身份复核紧邻ioctl。
- 已进入实体页面在geometry仍有效、仅camera/recognition瞬断时保持挂载并停止物理输入；初次进入/真几何失效仍用原校验。不自动因瞬断打开完整标定弹窗。允许最小前端逻辑与full/strict static更新，不作视觉重构，不伪报ready。
- 无远程reset API，无sudo-shell或任意路径执行，无端口断电、authorized切换、驱动卸载、Hub/controller复位循环。

## 验收

真实拔掉任一/两个USB设备、单独Type-C拔插均不触发无故Hub复位；模拟/重现connected但child缺失异常可一次找回。并发/重复/自身事件不重复复位；失败停止，冷却和重启限流有效。单owner/reader保持，旧帧与灯光批次不重放，正常API不阻塞，stop后无延迟重置。板上新帧、LED握手及LINK分别确认，页面/登录/语言保持。未完成的物理插拔验证明确报告。
