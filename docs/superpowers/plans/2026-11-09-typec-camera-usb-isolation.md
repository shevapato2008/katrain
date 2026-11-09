# Type-C 插拔影响摄像头：诊断与修复执行计划

> 本文保留现场诊断与人工恢复证据。用户随后批准的软件自动恢复方案、独立审核和实施记录见 [自动恢复计划](2026-11-09-usb-hub-auto-recovery.md)；初始硬件对照不再是发布前提。

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 找到 Board A↔Board B Type-C 插拔导致摄像头掉线的实际触发点，使棋盘插拔不影响摄像头持续出帧，同时保留真实的设备断连提示。

**Architecture:** 先按内核 USB → 摄像头 owner → 状态 API → 界面逐层定位，再用单变量物理对照确定供电、接地、连接器或 USB 信号链路中的故障点。只有证据指向软件时才修改对应 owner/状态代码；软件重试不能替代已无法枚举的设备恢复。当前交付仅为诊断和计划，不实施代码、硬件或部署变更。

**Tech Stack:** RK3562 Linux USB/UVC、Terminus USB Hub、ESP32-S3、Python CameraManager/CameraHub/LedService、React Kiosk。

**最新状态（16:53）：用户要求优先验证纯软件恢复，已成功找回摄像头并取得真实JPEG；详见文末。硬件变更不在当前范围。下方初始物理对照步骤保留为历史诊断思路，不能作为实施前置要求；自动 Hub 恢复尚未开发或审核。**

---

## Chunk 1: 已取得的证据与边界

### 现场结果（2026-11-09，设备本地时间 UTC+8）

| 时间 | 证据 | 能证明什么 |
| --- | --- | --- |
| 15:59–16:00 | 应用反复 grab/empty-frame 失败；内核记录摄像头 `1-1.4` disconnect 和重新枚举 | 取流失败伴随真实 USB 设备丢失，恢复线程确实尝试重开 |
| 16:00:04 | UVC probe control 多次 `-71` | USB 控制传输失败 |
| 16:01:24–35 | 摄像头 disconnect → 重枚举 → descriptor/config `-71` → `unable to enumerate USB device` | 故障已到 USB 枚举层；不是仅把前端状态显示错 |
| 16:04:09 | 截图与 API：camera=false、LED=true、LINK=UP、ACK=OK | 此时 LED 为 UP，摄像头不可用；单张快照不单独证明 LED 的恢复过程 |
| 16:11:36 | `lsusb` 无 `0ac8:0346`，`/dev/smartbox-cam` 不存在；ESP `303a:1001` 和 `/dev/smartbox-led` 仍在 | 当时连 Linux 都没有可供应用打开的摄像头节点 |
| 16:11:36 | `smartbox-katrain.service` active，PID=2812，自15:57:12启动 | 该过程没有应用服务重启 |

`dmesg -T` 是可读墙钟换算，不用它单独推断毫秒级先后；本次没有同步记录用户每一次手动拔插的精确时间。用户报告与故障时段吻合，但尚未完成受控复现。

本地原始证据（`output/` 不纳入 Git，包含真实屏幕，仅用于本次诊断）：

- [截图](../../../output/diagnostics/typec-camera-20261109/screen.png)
- [API 快照](../../../output/diagnostics/typec-camera-20261109/status.json)
- [内核、应用和 USB 拓扑](../../../output/diagnostics/typec-camera-20261109/usb-and-service.log)
- [Hub 描述符、设备规则和服务状态](../../../output/diagnostics/typec-camera-20261109/usb-rules-and-hub.log)

### 本地源码核对与现场硬件路径

- 摄像头 `1-1.4` 与 ESP `1-1.3` 同属 Hub `1-1`（`1a40:0101`）。该 Hub 描述符为 **ganged power switching / ganged overcurrent protection**；不能把它当作可独立安全断电的摄像头端口。
- `katrain/vision/device_events.py` 只接受匹配摄像头 alias/node 的 `video4linux` add/remove，metadata/其他设备不触发摄像头生命周期。`katrain/web/core/led_service.py` 没有调用摄像头关闭或 USB Hub 重置。
- `katrain/vision/worker_inprocess.py::_publish_status` 从摄像头自身的 `is_connected` 取值。`katrain/web/api/v1/endpoints/vision.py::vision_status` 单独取摄像头和 LED；`katrain/web/ui/src/kiosk/context/VisionContext.tsx` 和 `katrain/web/ui/src/kiosk/components/layout/GoConsoleRail.tsx` 也分别映射显示。
- 摄像头 udev 事件加速恢复，5秒定时兜底；重新打开有2秒对焦/曝光预热，界面每3秒刷新状态。几秒的显示延迟可能包含这些环节，但本次持续未连接是节点已经消失，不能靠加快轮询恢复。
- `CameraManager.open()` 完成预热并启动 reader 即返回成功；`_reconnect_locked()` 此时会打印 `reconnected`，尚不保证 reader 已交付有效新帧。API 的 `is_connected` 仍要求 `_latest_frame` 存在。因此日志里的“reconnected”不等于画面已经恢复，存在可独立修正的日志语义问题。
- Board A Type-C 不直接作为 Linux USB 设备枚举；主机通过 Board B `LINK` 每2秒读取 CC/ACK。固件 `smartbox-software/firmware/led-esp32s3/src/main.cpp` 的 ACK 来自 Board A F1 后的5V回传。USB串口存活与棋盘连接是两条状态。
- 旧硬件核查文档包含历史版本，不能直接当成现场整机的电源连接事实。共享 Hub 本身也不能证明两者由同一5V支路供电。必须核对现场 Board A/B 与 RK 板版本、线束和现行原理图。

Linux 官方文档说明，`EPROTO` 可对应协议/响应错误，常见于设备（包括固件）或线缆问题，单个错误码不能区分具体电气原因：[USB Error codes](https://docs.kernel.org/driver-api/usb/error-codes.html)。RK 上的 `-71` 对应 `EPROTO`。

**当前结论：** 故障边界已定位到真实的摄像头 USB 链路掉线/枚举失败。Type-C 操作是否通过供电瞬变、地线/屏蔽耦合、机械牵动或其他路径触发，仍需以下对照；目前不能宣称已确定“电压跌落”或“回灌”。

## Chunk 2: 受控定位与最小修复

### Task 1: 同步复现并保留稳定基线

**Files:** 原始结果追加到 `output/diagnostics/typec-camera-20261109/`；结论更新本计划。此任务不修改产品文件。

- [ ] **Step 1:** 与现场人员约定短观察窗口；无对局/标定动作时记录设备版本、线束、当前 camera/LED 状态和供电，并核对当前应用部署提交/受影响文件哈希、固件版本与这里审查的源码。摄像头目前不枚举，先记录原状态，再由现场人员只重插摄像头一次恢复基线，不重启整机或 Hub；若仍不能枚举，直接进入 Task 2 的线缆/端口对照。
- [ ] **Step 2:** 在操作者会话开启两个只读流：`ssh rk3562-local 'journalctl -k -f -o short-iso --since now'` 和 `ssh rk3562-local 'journalctl -u smartbox-katrain.service -f -o short-iso --since now'`。本地分别保存文件，结束后 Ctrl-C。记录初始 `lsusb -t`、`/dev/smartbox-cam`、`systemctl show smartbox-katrain.service -p MainPID`。
- [ ] **Step 3:** 当前 `/kiosk/play` 是棋盘示意图，不能用它验证视频。真实帧通过既有 `GET /api/v1/geometry/snapshot?view=raw&scale=2` 观察：`geometry.py::geometry_snapshot` → `CaptureService.read_frame()` → 同一个 CameraHub，不增加采集进程。操作者侧以最多每秒1次、无并发请求查看并保存返回JPEG和时刻；例如单次取证命令为 `ssh rk3562-local 'curl --max-time 2 -fsS "http://127.0.0.1:8081/api/v1/geometry/snapshot?view=raw&scale=2"' > output/diagnostics/typec-camera-20261109/frame-baseline.jpg`，失败文件不当作有效图。配合画面内移动的秒表/测试卡验证内容更新，不能用连续HTTP200或JPEG哈希不同单独证明新帧。API `vision/status`、`led/status` 分别读取连接状态，503时记失败并清除观察窗口的旧画面，不启动标定。按同一设备时钟标记拔/插时间；Type-C 拔出至少5秒、插回等待稳定，重复3次。固定摄像头线与RK接口，记录 LED DOWN/UP、camera false/true、首次观察到的新帧和USB node变化。若不能观察真实帧，该项记为未完成。
- [ ] **Step 4:** 对照同样时间长度但不动线的基线。预期可明确区分：USB真实消失；USB在但UVC取流失败；API与实际帧不一致。若未复现，保留结果继续现场单变量检查，不以“刚好恢复”验收。

### Task 2: 定位物理耦合路径

**Files:** 现场板版本/原理图以 `/Users/fan/Repositories/smartbox-hardware-design/` 中匹配版本的设计与网表为依据；初次记录参考 `debug/整机bring-up实测报告-BoardB_v7-2026-09-02.md`。不直接修改历史设计文件。

- [ ] **Step 1:** 只更换摄像头为已知正常的短 USB 线，其余接线不变，重复 Task 1 三次。若消失，再换回原线复验，区分偶然恢复和线/接头问题。
- [ ] **Step 2:** 如现场存在经过确认的独立 USB root-port 路径，把摄像头接到该路径，再以 `lsusb -t` 确认确实不经过原 Hub。只换路径，重复三次。若没有独立端口，记录此限制，不把同 Hub 另一孔误当隔离。
- [ ] **Step 3:** 需要供电对照时，只使用已确认无 VBUS 反向供电的测试配置；不得直接并联供电。由熟悉原理图的现场人员测量 Type-C 插拔时摄像头 VBUS、RK USB 供电、Board B/A 电源与地参考变化，使用有足够时间分辨率的仪器捕获瞬变；普通万用表的稳定读数不能排除瞬态问题。
- [ ] **Step 4:** 以单变量、可恢复的实验确定最小修复：线/接头问题更换对应件；供电瞬变问题按实测处理供电裕量、限浪涌或支路；接地/屏蔽问题按现行设计纠正。修改电路前记录具体测点、波形和版本，不凭 `-71` 指定电容值或擅改电源保护。

初始只读阶段不执行 Hub/controller reset、`authorized` 切换、驱动卸载或未经确认的端口电源切换，因为会影响同 Hub 的 ESP/LED。用户随后明确授权纯软件找回验证，才执行文末记录的一次单端口复位、一次共享Hub总线复位；不据此批准无限自动复位。原始日志里的 `attempt power cycle` 是内核自身尝试。

### Task 3: 按定位结果决定软件范围

**可能涉及的文件（不是预授权全部修改）：**

- `katrain/vision/camera.py`：仅在确认需要时，修正打开成功/首帧就绪日志；不改变真实连接判据，不保留断开前旧帧冒充实时画面。
- `katrain/vision/device_events.py`、`katrain/web/core/camera_hub.py`：仅当证据显示节点已返回而恢复未被唤醒/重试失效，修正该条路径；维持单 owner、单 reader、现有廉价兜底与重试冷却/频率限制。
- `tests/test_vision/test_camera_recovery.py`、`tests/test_vision/test_device_events.py`、`tests/test_camera_hub.py`：只为被证实的软件问题补充最小回归测试。

- [ ] **Step 1:** 若 Task 1/2 确认电气/线缆故障且现有软件能在节点恢复后恢复新帧，则主修硬件，不为该故障增加扫描线程、前端快速轮询或全局重置。
- [ ] **Step 2:** 日志语义修正可单独成小任务：现有 reconnect 成功日志改成“设备已打开，等待新帧”；首次有效帧到达再在 owner 内记录 ready。先补一条“open成功但reader空帧不得宣称ready”的聚焦测试，再修改、验证、独立提交。不增加新的公开状态机或界面设计。
- [ ] **Step 3:** 若查到恢复路径缺陷，先用原事件序列/假 capture 写失败用例，再作最小修复。运行相关用例；仅修改摄像头代码时使用 `.venv/bin/python -m pytest tests/test_vision/test_camera_recovery.py tests/test_vision/test_device_events.py tests/test_camera_hub.py -q`。按实际改动补跑直接依赖的状态用例，不重跑无关全量套件。
- [ ] **Step 4:** Type-C 小于2秒的完整拔插可能被 LINK 采样漏掉，这是另一项固件需求。若要求完整捕获，另写固件事件/锁存断连代次与主机读取的契约及计划，不把轮询盲区混作这次摄像头掉线的解释。

### Task 4: 验收、审核与发布

- [ ] **Step 1:** 在原使用方式下 Type-C 拔插至少10次，含LED灭灯和有正常指示两种负载。按 Task 1 的真实帧观察方式，结合连续内核日志验收摄像头始终枚举、持续交付内容更新的新帧、画面无冻结、API不错误掉线；LED正确DOWN/UP，服务PID稳定，无过期灯命令或误落子。仅状态变绿不算画面通过。另做一次真正摄像头拔插，确认仍诚实断连并在设备恢复后恢复画面。
- [ ] **Step 2:** 保存最小对照结果及最终改动。任何无法完成的物理验证明确列出，不把模拟用例通过称为整机通过。
- [ ] **Step 3:** 遵循用户既定流程：本计划由独立 Astra Max 审核，最多两轮；有代码时按 @superpowers:subagent-driven-development 实施，只并行互不依赖的已定范围；最终新的独立 Astra Max 审核，修正直至通过。硬件定位是串行依赖，不为并行而提前猜测代码修复。
- [ ] **Step 4:** 后续若实施产品代码并获准发布，按既定四步：追 develop/解决冲突/验证并推当前分支 → 合入develop并推送 → 更新smartbox-software的vendor/katrain并推main → 部署测试 `home-ubuntu`、正式 `ucloud-v100` 和RK3562，验证实际页面与板上行为，报告各仓发布提交与部署版本。若只改硬件或本计划文档，则不进行无意义的云端发布。

## 初次只读排查的操作记录

- 截取现有 `/kiosk/play` 页面，没有导航、切模式、改变登录状态或开第二个摄像头进程。
- 读取日志、状态API、sysfs/USB信息和udev规则；没有服务重启、USB复位、固件烧录、产品代码修改或部署。
- 16:10曾查询不存在的 `katrain-board` unit；随后通过 `/proc/2812/cgroup` 确认实际服务为 `smartbox-katrain.service`，原始设备状态日志已用正确unit重新采集；诊断只采用实际服务结果。
- 16:12前后已向同设备的另一工作会话释放只读观察窗口；之后不把其他会话的新操作误归因于本次采样。

## 独立计划审核

2026-11-09，独立 `gpt-6-astra` / `max` 共两轮审核：第1轮要求补足真实帧观察路径，已修正；第2轮最终 **Approved**，无剩余实质阻塞。批准范围仅为诊断和后续执行计划，不代表物理触发机制已经验证或故障已经修复。

## 用户授权后的纯软件恢复验证（16:45–16:53）

用户明确提出硬件来不及调整，要求先验证能否在不碰线的情况下重新发现摄像头。已与另一设备会话取得独占窗口；当时Go PID11786、vision unbound、geometry required，无进行中的物理对局绑定或标定。

1. **16:48:23只读 Hub GET_STATUS：** 摄像头port4为 `0x501`：connected=true、powered=true、enabled=false，无当前过流标志；ESP port3为 `0x103`，连接且启用。物理连接仍能由Hub端口看到，之前仅查看设备节点的轮询不足以看见此状态。
2. **16:49:01单端口总线复位：** 向已校验身份的 `1a40:0101` Hub 发送 `SET_FEATURE(PORT_RESET)`，目标仅port4。端口变为 `0x503`（enabled=true），ESP不变，但14秒观察中没有重新枚举摄像头。Linux5.10 `hub.c::port_event` 在单独RESET change、无已注册child时不会仅凭该事件强制走新连接枚举，和本次观测一致。
3. **16:52:25共享Hub总线复位：** 对 `/dev/bus/usb/001/002` 执行一次 `USBDEVFS_RESET`，没有断电、改线、重启应用/系统或改部署。此步骤确实使ESP断开后重新枚举，不能称作“只复位摄像头”或“另一侧完全不受影响”。
4. **16:52:26–30：** 摄像头 `0ac8:0346` 重新枚举为device16，alias返回，现有owner在16:52:27自动open、29完成预热；30的状态采样camera_connected=true。即重新枚举约1秒、可用状态首次采样约5秒。
5. **16:52:40：** LED LINK UP再次采样为true；34日志serial opened，中途有一次handshake失败。当前仅能报告约15秒内观察到棋盘恢复，不能把它写成确定上限。
6. **16:53:53：** PID仍11786，camera与LED均true；通过既有snapshot接口取得并查看真实棋盘JPEG。验证了一次真实故障现场的恢复，不代表所有插拔场景或连续运行已验收。

证据：[单端口复位](../../../output/diagnostics/typec-camera-20261109/port4-reset-experiment.log)、[Hub复位](../../../output/diagnostics/typec-camera-20261109/hub-reset-experiment.log)、[恢复后状态](../../../output/diagnostics/typec-camera-20261109/recovered-status.log)、[恢复后的真实画面](../../../output/diagnostics/typec-camera-20261109/recovered-camera.jpg)。

**软件方案下一步（尚未实施/独立审核）：** 由现有单一设备owner统一协调恢复，不另起竞争的摄像头/串口进程。普通断连仍用事件与低频重试；若Hub端口connected而摄像头持续无节点，则经宽限期、互斥和冷却，按已确认Hub身份/拓扑触发有次数限制的整Hub恢复。恢复前暂停物理输入与LED任务、作废旧命令；恢复后分别验证camera新帧、LED握手和实际LINK，不直接报全局就绪。必须区分“设备确实拔掉”与“已插入但枚举失败”，并明确活动对局/标定的暂停与恢复策略；不能把每次棋盘Type-C变化都当成复位理由。共享Hub复位会短暂影响另一侧，这是当前已证实路径的代价。

后续自动化实现需更新为独立可执行软件计划，按用户既定Astra Max最多两轮计划审核、SDD开发、新独立Astra代码审核与四步发布流程执行；上方原始审核不覆盖新自动复位实现。
