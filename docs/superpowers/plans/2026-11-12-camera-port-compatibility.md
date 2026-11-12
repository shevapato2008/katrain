# Board B 摄像头按端口识别 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Board B唯一外露摄像头口支持新旧批次的兼容UVC摄像头，不再因VID/PID改变而显示未连接，并部署到当前RK3562。

**Architecture:** 在拥有该规则的smartbox-software父仓库修改udev映射，以稳定物理路径、uvcvideo采集能力和主视频节点绑定 `/dev/smartbox-cam`。同时修正KaTrain USB恢复适配器中对摄像头旧VID/PID的限定，以同一固定口的真实UVC主采集节点验证代替。应用继续用原入口和现有取帧/重连生命周期；不在udev中试拍、不修改棋盘识别算法。

**Tech Stack:** Linux udev / V4L2，systemd，pytest，Git跨仓库发布。

---

## 范围和证据

- 用户已批准按此思路优先开发、独立审核后执行四步部署；之前两份复盘计划保持暂缓。
- 本计划和USB恢复适配器修复位于KaTrain feature；设备入口规则修复位于父仓库，不修改无关算法或复盘功能。
- 子仓工作树：`/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/camera-port-20261112`，基线 `8c02b98d7`。
- 父仓工作树：`/Users/fan/.config/superpowers/worktrees/smartbox-software/camera-port-20261112`，基线 `038fe9ab`。原父仓认证WIP不动。
- 现场新机 `0bdc:2710`，旧机 `0ac8:0346`；两者都在USB位置 `1-1.4`。新机有 `/dev/video0`、uvcvideo、Video Capture/Streaming和MJPG1080p30，已独立读取一帧。
- 现场新机的 `ID_PATH=platform-fed00000.usb-usb-0:1.4:1.0`，`ID_V4L_CAPABILITIES=:capture:`；原规则只匹配旧VID/PID，新机缺少alias。
- 安装前规则SHA256为 `dc7bf30abfd7d5abcb83c543570f1a8ee3734e12512a9b605b5105e8f7f5b43b`。部署前重新核对，若改变先查差异，不覆盖其他会话改动。
- 新发现第二处独立限定：`katrain/web/core/linux_usb_hub.py:LinuxUsbHub.TARGETS` 将port4固定为旧 `0ac8:0346`；现场启动日志已有 `topology could not be verified`。仅修udev会保留这条恢复缺口，故本计划纳入同一兼容修复。

## Chunk 1: 实施与聚焦验证

计划状态：独立Astra Max两轮审核通过，用户已授权本需求开发和部署。测试使用现有解释器 `/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python`（系统python未安装pytest）；基线子仓103项、父仓24项已通过。

### Task 1: 改规则与既有测试

**Files (parent repo):**
- Modify: `provisioning/configs/99-smartbox-cam.rules`
- Modify: `provisioning/tests/test_vision_led_provisioning.py`
- Modify: `provisioning/provision.sh`（只改安装成功日志中的旧型号描述）

- [ ] 先扩展现有规则契约测试，使旧VID/PID绑定规则失败；不新建一套仿造udev的解析器。
- [ ] 规则不再匹配厂商、产品或序列号，限定已核实的物理口 `ENV{ID_PATH}=="platform-fed00000.usb-usb-0:1.4:*"`，允许该口的接口编号变化。
- [ ] 同时保留 `SUBSYSTEM=="video4linux"`、`ATTR{index}=="0"`，增加uvcvideo驱动和 `ENV{ID_V4L_CAPABILITIES}=="*:capture:*"` 约束，排除metadata、音频、其他口设备；不添加全局video0兜底。
- [ ] 继续提供 `SYMLINK+="smartbox-cam"`、video组和0660权限。保留既有 `exposure_auto_priority=0,exposure_auto=3` 初始化；其RUN失败不作为alias准入判断，应用继续按实际取帧/控制读回判定就绪。不引入udev阻塞试拍或轮询/Hub反复复位。
- [ ] 只将provision安装日志改成Board B指定口的UVC摄像头，规则注释清楚说明端口依据及能力范围。
- [ ] 测试确认：非注释规则行有端口/驱动/采集/index守卫且没有VID/PID/name/serial绑定；保留曝光与安装/trigger契约。
- [ ] 运行既有聚焦suite，记录red→green后提交父仓feature。此配置变更无需前端构建、引擎或全量系统回归。

Run (parent worktree):
```sh
/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest provisioning/tests/test_vision_led_provisioning.py -q
bash -n provisioning/provision.sh
```

### Task 1b: USB恢复适配器的型号无关校验

**Files (child repo):**
- Modify: `katrain/web/core/linux_usb_hub.py`
- Modify: `tests/test_linux_usb_hub.py`

- [ ] 先写失败测试：旧机、新机和一个不同VID/PID但同能力的UVC主节点在port4均可获得valid snapshot；同口非UVC/未绑定uvcvideo/仅metadata或无主采集节点拒绝。
- [ ] 保持Hub精确 `1a40:0101`、class09、4端口、固定1-1拓扑，LED port3仍精确 `303a:1001`，端口1/2意外设备、过流、reset、掉电、usbfs地址及alias跨设备指向等原守卫不变。
- [ ] 只有port4已枚举子设备的身份准入改为可证明的UVC主视频节点：查该USB child下的video-class接口、uvcvideo绑定和index0主视频节点；存在alias时仍必须指向该child的真实字符设备。metadata不能单独成为证明；若现有sysfs信息不能证明capture则用只读V4L2 QUERYCAP，绝不通过STREAMON/试拍证明恢复权限。
- [ ] 所有证明必须限定在准确child祖先下；枚举中/证据不完整时fail closed，不拿名字/新VID白名单替代校验；没有已枚举child时保留原故障candidate语义。
- [ ] `PortSnapshot.child_identity`仍记录实际VID/PID，parent/locked-child最终重查、稳定candidate mask、操作锁及唯一reset ioctl入口不变；不做任何真实Hub复位来跑测试。
- [ ] 运行现有适配器、协调器和server wiring聚焦测试；在单元fixture中补真实所需sysfs/能力证据，不将验证函数整体mock为True；记录red→green后提交子仓feature。

Run (child worktree):
```sh
CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest tests/test_linux_usb_hub.py tests/test_usb_hub_recovery.py tests/web_ui/test_usb_hub_recovery_wiring.py -q
```

### Task 2: 并行准备现场安装与验收

**Files:** 只在本地ignored output保存一次性安装/验收材料；不增通用部署框架。

- [ ] Task1与Task1b分属不同仓库/文件，可由两个子代理并行；主代理准备精简安装步骤，所有远端操作统一由主代理执行，禁止多个代理同时控制设备。
- [ ] 部署前确认仍是目标RK，摄像头仍在指定口，app没有活动绑定；保存原规则、SHA和服务PID，不读凭据，不改变用户棋谱/登录/标定数据。
- [ ] 将审核后的规则和单个 `linux_usb_hub.py` 先传暂存，核对源/目标SHA并备份；规则原子安装0644，child源码同样只替换这个拥有修复的文件，保留其余设备覆盖层。仅reload udev并对已验证摄像头video节点重放add事件、等待settle；不对所有USB设备trigger、不复位Hub。
- [ ] 真实检查alias解析到指定口的capture节点；由现有应用自动重连，并确认camera_connected/camera_ready及新帧/预览，不能仅以软链接存在声称摄像头可用。
- [ ] 因USB恢复模块在启动时导入且本次已修child源码，再次确认unbound/无活动对局后只重启KaTrain一个服务使其生效；保留其他源文件、diagnostic overlay、模式和其他服务，不做整机重启。启动确认USB恢复拓扑valid，不再因为新型号被禁用；只读snapshot，不执行reset。
- [ ] 若规则/源码安装、alias映射或服务恢复不符合预期，按本批备份和写后SHA比较恢复两个文件并reload/恢复服务，记录失败；不得覆盖期间变化的文件或删除不属于本次安装的链接。
- [ ] 新摄像头已经在场，现场验证其恢复和一段有界的新帧可用性；旧机/未来批次的VID无关性由规则契约检查支撑。没有实际换回旧机或冷启动就如实标为待现场补验，不伪称已做物理插拔/重启验收。

## Chunk 2: 审核、四步发布与回报

- [ ] 先让独立 Astra模型、Max effort 审计划，至多两轮修订；用户已授权执行，不再重复索要同一实施许可。
- [ ] 用subagent-driven-development执行：一个代理拥有父仓规则/测试/安装日志；另一个拥有子仓USB适配器/对应测试。主代理整合部署材料；规格核对和最终质量审核顺序不变。
- [ ] 规格核对通过后，由全新独立 Astra Max 审父子仓diff（含USB适配器与测试）及两个文件的实际安装步骤，修复并复审直至无阻塞。不要省略真实udev验收，也不要扩成无关全站审核。
- [ ] 第一步：子仓fetch develop并合到本feature，解决冲突；提交推USB适配器修复/测试与计划（若develop另有更新，核对不会带入待批复盘功能）。
- [ ] 第二步：将该feature合入并推远端develop，报告真实commit；不创建虚假的KaTrain算法修复。
- [ ] 第三步：父仓feature追最新main，合入设备规则修复并将vendor/katrain指向已发布develop；复验后推父仓main，原工作树WIP保持不变。
- [ ] 第四步：只对RK3562安装上述已发布两个文件补丁并验收，不部署无关云端或替换整套旧设备checkout。设备部署回执准确写规则来源父仓commit、child修复commit、两个SHA和实际安装内容，不把旧checkout冒称整体已更新。
- [ ] 当前镜头变化后需要正常重新标定；不恢复旧镜头geometry来伪造ready。不为本修复自动结束对局或抹掉校准。
- [ ] 完成后在当前session用文字通知用户：实际修复位置、已发布commits、设备恢复/取帧证据和未完成的物理换机验收；然后再回到复盘计划待执行事项。
