# 摄像头与棋盘拔插恢复发布回执 — 2026-11-08

## 软件与发布顺序

| 内容 | 已发布的软件提交 |
| --- | --- |
| KaTrain 功能分支与 develop | `49b7cf79c052591bcc5532bea4dbee36e521bf87` |
| smartbox-software main | `319cbbceb7ff0161f935168470028e35796e3a5e` |
| 父仓 vendor/katrain | `49b7cf79c052591bcc5532bea4dbee36e521bf87` |

已先追上 develop `954a374bd`，再依序推功能分支、推 develop、推父仓 gitlink，随后部署 TEST、PROD、RK3562。Git 集成无冲突、未 force push；父仓原工作区既有 submodule 修改保留。部署后的回执和计划状态以纯文档提交追加，不改变上述软件产物版本。

## 改动与验证

- 摄像头：可选 Linux processed-udev 事件触发已有恢复线程；匹配新设备可绕过一次重连冷却，缺失节点只做廉价检查，5秒定时兜底。保留单 reader/lease、旧线程退出保护和断开后的帧失效。
- 棋盘：区分 Board A Type-C 的 LINK 状态与 Board B USB 串口。保留2秒 LINK 检查，补充静默失联、节点返回重连、严格命令总超时和过期批次作废。恢复先清空并确认，再设置亮度，只重建当前有效非 strict 指示。
- 标定预览：失败后隐藏旧画面和叠加层，失败重试降为1秒，新帧成功后恢复正常频率。没有固件、USB Hub 复位、电源策略、身份、数据库或标定数据变更。
- writing-plans 的 Astra Max 独立计划审核恰好两轮后通过。按归属并行实现，独立规格审核和新的 Astra Max 完整代码/发布工具审核均通过。
- 控制器集成 **520 项 Python、91 项前端测试通过**，full/strict 构建通过。独立审核复跑产品161项 Python、61项 UI；最终发布操作器60项离线用例通过。详见[代码审核记录](../superpowers/reviews/2026-11-08-hardware-hotplug-code-astra-max.md)。不宣称全量 pytest 通过；独立 board-lifespan 夹具的17项 import 失败已单列记录。

云端基于各自现役不可变镜像，仅覆盖明确列出的六个 Python 文件和完整 full static；包括最新 develop 中前端所需的两个 preferences API/core 文件。RK 同样替换六个文件及两套完整静态目录，不进行父仓全量同步。

| 产物 | 数量 / SHA256 |
| --- | --- |
| full static | 494 文件；index `9467996d28111cca677a63b84684fc7a9b90c8a3a95ed893b99ea2118b621a02` |
| strict Kiosk | 387 文件；index `70f3269f0f3f72988bd5e7a5d545ed27954e13d01ace6f5b498896b954857c4e` |
| RK manifest | `41dbf3df6a3ea013eedd7354bf6fbf14b343029b05087674c8dc775c37fd1a22` |

## 云端结果

| 环境 | 不可变新镜像 | 验收 |
| --- | --- | --- |
| TEST / home-ubuntu | `sha256:d318683dd50028839ff79aa7735a8abe8941e4fc17fdd9f1f174a858fa274346` | running，restart0，HTTP health ok，225个非 Web 容器保持 |
| PROD / ucloud-v100 | `sha256:6b4b244a0fd25f4f0b64d089a4e6552c261ef7b27313df7a03890732c21cfe28` | healthy，restart0，HTTP health ok，71个非 Web 容器保持 |

每端16项公开 HTTP 检查通过：根与深链接、GET/HEAD、query、真实旧前缀404、缺失 API/资源404、入口 JS/CSS hash、health。两个根域名保持 Galaxy；真实浏览器已查看 Galaxy/Kiosk 页面和截图，任务浏览器已关闭。配置角色、网络、挂载、会员/计费环境保持；没有重启引擎、DB、Cron 或 MinIO。非 Web 配置的 Mounts 数组顺序差异已证明仅为排列变化。

切换前 TEST 无真人活动；PROD 3局均为机器人，真人、观众、入站连接为0。仅按固定 native helper 执行兼容平滑切换，未触发云端回滚。原备份容器保留：

- TEST：`katrain-web-membership-backup-5dc49f0f6547-45ab7a6c`，私有回执 `/tmp/hardware-hotplug-49b7cf79c052/private/`。
- PROD：`katrain-ucloud-katrain-web-1-membership-backup-3e3de07be1ea-3737ada0`，私有回执 `/var/tmp/hardware-hotplug-49b7cf79c052/private/`。

## RK3562 现场与限制

设备为 `rk3562-local` / `gzpeite`。发布前实际整机归档版本是父仓 `e668d94f9d23531b0da81e95fa8accdb7be46468`、KaTrain `954a374bd`，完整版本标记 SHA256 `60f34b2aee6a034599240e231d137bd8802f6d3a88c4af76b1ad0a9fc6290588`。本次保留该整机标记和先前 routing 标记，以独立 `.katrain-hardware-release.json` 记录已审核的887文件差量，不宣称整机目录等于49b提交。

现场在原 Go 模式、同一个 Chromium page 上维护。首次只读预检因实际 `chromium-bin` 程序名被拒绝，修订为 kernel exe 与 kiosk cgroup 的精确检查并经 Astra 复审后才继续。候选源、静态及服务已更新，后续标定页面验收遇到明确的登录门禁，安全检查拒绝停止不明弹窗页面，原失败回执和维护锁当时保留。

受限恢复工具及输入也经独立 Astra 审核，69项联合离线用例通过。该工具只运行了只读预检；此时页面已被外部操作转到盒子登录入口，因此拒绝继续，**未执行恢复 apply、认证操作、手动解锁或第二次服务重启**。

用户要求安全暂停后，没有部署/回滚进程继续执行。恢复工作时，新读取到设备已在新 page `CF944F631BB90C79993A679184E6996F` 的 `http://127.0.0.1:8080/launcher`，Go/KaTrain/Hermes inactive，维护锁不存在。没有沿用暂停前的页面或锁信息，也没有强行恢复旧摆谱 URL。再次逐文件核验887个已安装文件，全部匹配发布 manifest，hardware marker仍指向49b/319c。

随后将 RK 独占交接给 session `01a1b6fc-f640-7de3-8ad2-7571dd683858` 的四棋类翻译发布任务；本 session 不再启动 RK 部署或切换模式。对方确认发布来源父仓 `a0d0cb1a`、vendor `fda461efc` 已包含49b热插拔修复，避免后续同步覆盖。旧 `result.json` 是保留的历史失败记录，不代表当前仍有在途回滚；恢复后的只读核验在 `rk/resumed-state.json`、`rk/resumed-file-verification.json`。

接管方最终确认 release `translation-completeness-20261108T134804Z-a0d0cb1a` 为 verified：父源码 `a0d0cb1a5a81c3a31e1a5619fe36468a40f3c28d`、vendor `fda461efcb29b713342bde3a2edc0ab11c0c4e05`，原 launcher/同一页 CF944 已恢复，维护锁释放，无在途更新/恢复；五套实际 MO API 已逐项匹配。设备窗口已释放，登录后的内页和物理验证仍待用户，登录由接管 session 单点跟进。

注意版本边界：父 main 仍为本任务的 `319cbbce`；接管方新增的三棋前端与 MO 发布脚本位于 `origin/feat/frontend-redesign` 的 `a0d0cb1a`，尚未合入父 main。后续整包重建需先纳入该来源，不能仅从旧 main 重建并覆盖设备。这里不把功能分支部署写成已合入 main。

新服务 PID79038 的观察：`udevadm` 子进程79188约932 KiB RSS，5秒 CPU ticks 增量0；摄像头节点缺失时没有 OpenCV 打开失败或重连尝试日志。另一次只读候选监听探测约17ms完成订阅；这不是物理重连或出帧延迟的测量。

摄像头仍在 Linux USB 枚举层缺失，内核曾记录 `-71` / unable to enumerate。尚未确定线材、接口、供电、相机或 Hub 的具体原因。共用 Hub 为 ganged power，未执行可能影响 ESP 的重置。事件监听不能让未成功枚举的硬件产生有效帧。

物理摄像头/Type-C/Board B USB 拔插，以及登录后的真实画面恢复，仍待用户现场验证。其他棋类独立 readiness API 没有纳入本次修改。

## 证据与现场检查

发布工具、全部 hash、模拟故障用例、云端 HTTP/runtime 回执、RK 原失败及恢复材料保存在 `output/releases/hardware-hotplug-20261108/`；截图在 `output/playwright/hardware-hotplug-20261108/`。板端现场目录为 `/var/lib/smartbox/deployments/hardware-hotplug-49b7cf79c052591bcc5532bea4dbee36e521bf87-attempt1/`。为给下一发布腾空间，接管 session 完整离机核验后，仅清理了本任务的 `payload.tar.gz` 和 `backup/` 历史副本；metadata、脚本、日志、stage及已安装源、marker、用户状态保留。

完整归档：`/Users/fan/Backups/smartbox/rk3562-20261108-translation-completeness/hotplug-complete.tar.gz`，189,961,933 bytes，SHA256 `667b5fc926227c78fcd1798aa51225331012677102a8dc04613fa0ad0a68ebad`。接管方核对928项内容/权限/数值UIDGID/符号链接与前后源一致，控制器也独立复核了归档大小和SHA256。恢复旧备份时应先核验该归档，不能假设远端backup仍在。

用户现场按顺序检查：

1. 登录后进入标定页，拔插摄像头 USB；内核识别回来后，连接状态和新画面应自动恢复，无需重启服务。
2. 拔插 Board A Type-C，确认 LED 状态由断开回到 UP，当前有效灯光恢复，旧采集图案不重放。
3. 拔插 Board B USB，确认握手和棋盘状态自动恢复；过程中不应出现意外落子或过期灯光。

如摄像头节点仍未出现，应继续检查 USB 连接/线材/供电；不能据此把软件模拟测试记成硬件通过。
