# 微信会员与收款开关聚焦审核（Astra Max）

初审日期：2026-11-09；运行与代表页面终验补充：2026-11-10。**规格符合性、代码与配置安全：Approved；最终配置开放、联合软件发布与代表性入口验收：Approved。** 本报告保留各步骤的精确历史版本，最终实际状态见末节；真实付款及到账不在该通过结论内。

用户已确认 `/Users/fan/cert/wechat-native-activation-plan.md`：先 TEST 开启并验收健康、登录后 catalog/usage 和新入口，再开启 PROD；用户本人选择商品并手机付款。Agent 不代下单、不代付款。初始两开关操作保持 `4235a58238e805530cb07ef0eb8041ba93df586f` 原软件和镜像；后续联合软件发布另按已审机制执行，不因纯文档提交重新构建。

## 精确审核版本

完整阅读 `output/wechat-native-activation-20261109/activate.py`、对应测试和 README，并核对复用的原 helper：

| 文件 | SHA-256 |
| --- | --- |
| `activate.py` | `04cba13645caf64ee53f45ce5db26cedaab584332cfdfaa9cac6d09dbc2ff8aa` |
| `test_activate.py` | `5332b6a7b44fddd7223f9f1a3f7c1b1908edb35f081c6b13436d8b44eb610b2e` |
| `native-release.py` | `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108` |

## 规格与安全结论

- Env 集合和顺序保持，唯一值变更为 `MEMBERSHIP_MODE=enabled`、`PAYMENTS_MODE=live`。原 8 个微信标识/路径 Env、只读秘密挂载、其他 Env、User、资源、角色、网络和不可变镜像完整保留；另沿用 helper 的操作标签与 Docker 自动默认 hostname 更新。billing=true、Free=0、Max sale=true 不变。
- 前置条件要求当前目标正是已配置微信凭据的 paused/disabled Web，并核对固定站点、daemon、软件 SHA、User、8 个微信 Env、路径和精确只读挂载。prepare 与 apply 绑定新鲜完整 ID、镜像及 fingerprint；manifest 同时校验 old/new hash、精确重建载荷和真实变更字段，私有证据为 0700/0600。
- beforeimage 是本次开放前的**已配置凭据、收款关闭状态**，不是早先尚无微信配置的容器。完整 Config/HostConfig/挂载/网络均留存；切换或后置检查失败恢复该容器，保留同一秘密挂载和后续已有订单验签、查单及履约所需配置。
- 恢复保留上一轮强化的 full-owned-new 检查：停止前、优雅停止回调及重命名前均核对操作归属和完整 Config、HostConfig、挂载与网络。发生漂移会拒绝操作并记录 `recovery-required`；没有退回仅核 label/image 的窄检查。
- 后置检查确认实际运行配置、health/restart、解析后的两个 Settings、其他运行容器 fingerprint，以及已停止保留的 configured beforeimage。成功原子写入私有 `active.private.json`，含实际 Web/image、开关与 beforeimage 路径/hash；失败恢复成功会移走 active 记录。
- 操作器没有秘密 staging、传输、安装或密钥正文读取路径，没有创建订单、商户 HTTP、设备变更或其他服务重启路径。两个开关开启后，用户或正常服务可能产生真实业务；操作器自身未下单的回执不能代替全站订单状态检查。

## 独立验证与验收边界

独立执行 `/Users/fan/Repositories/katrain/.venv/bin/python -B output/wechat-native-activation-20261109/test_activate.py -v`：**7 tests passed，退出码 0**。覆盖两开关增量与非法 patch/image 拒绝、已配置关闭基线、完整 owned-new 漂移拒绝、过期 fingerprint、完整 beforeimage/变更清单、后置失败恢复及原 helper 字节一致。三个 Python 文件 AST 解析通过，hash 与冻结版本一致。未重复上一轮秘密安装/传输测试或业务全量回归。

**审核者仅本地读取上述代码、测试、说明及用户确认方案；未执行 SSH、Docker、部署、下单或商户 API，未读取/输出密钥正文。** 本结论允许主代理按已确认计划核对远端精确字节、新鲜 CAS 后执行 TEST，再经实际验收开启 PROD；不代表两端已开启，也不代表真实扫码、签名通知、到账或扣费成功。这些必须由后续实际回执和用户亲自付款后的观察证明。

## RK 本地收费 guard 配置补充

**规格与配置安全：Approved。** 实机仍以 legacy/billing=false 启动时，云端 enabled 不会自动传播本地 guard。已发布代码具备拦截旧分析入口及清除私有 state 结果的逻辑，本次只补 `MEMBERSHIP_MODE=enabled / BILLING_ENFORCED=true / FREE_WEEKLY_REPORTS=0`；本地支付继续 disabled，不下发商户密钥，不新增商业规则。

完整审核 `rk_guard.py` 最终 SHA-256 `0cb5dac5f0a98cb4762ff84c39bd9a489e761f5e887b0c6bc7b33cb4d558093e`、`RK-GUARD.md` 及测试。原 RK helper 为 `14d9f72105379649a5ee1c8c7c369dcaea26220014d141f63766e13ba2bdc4c5`，字节一致；测试文件为 `764be94e56a1f1478477e07bd834bdf67593b3f80d62d942cb89cf4df36fcde7`。

- 固定 Go unit、实际 `/mnt/data/weiqi/weiqi-web.db` 和私有部署目录。prepare 保存完整 unit show/cat、原环境来源及有效配置，在无打开数据库 FD 时通过只读连接作一致 SQLite backup 并核对业务指纹。未写源数据库。
- apply 取得自己的维护锁，15 秒心跳并核验 owner/inode；要求所有模式和成员 inactive、Go PID 为 0、setup 保持 active、唯一原 launcher page 和原数据库/配置不变。复用的 `Runtime.capture()` 只 GET 现有页面列表，不发送 CDP 指令。
- 唯一配置写入为两个新 root0600 文件：三字段 Env 文件和固定 16 个 z 前缀的末尾 drop-in。拒绝已有目标或排序不在最后；旧文件内容/元数据、Exec/User、其他有效 Env 均严格比较。仅执行 daemon-reload，不启动/停止模式、导航页面、改变摄像头或恢复 SQLite。
- 失败仅在 Go 启动时间未变、仍 inactive 且 activation marker 不存在时，CAS 删除本次 owned 新配置并验证原配置。Go 已启动或 marker 已存在后，不自动退 legacy；只能在文件归属明确时保留下一次启动的 paused/billing=true/Free=0 配置，或记录 recovery-required。paused 文件不会追溯修改已运行进程，本地 paused 也不代表云端所有收费入口暂停。备份不是自动资金或用户数据回滚方案。

独立运行 **6 tests passed，退出码 0**，三个相关 Python 文件语法及 hash 核对通过。未复跑完整 RK 发布套件，未连接设备。后续由主代理通过正常 launcher 启动，并完成解析 Settings、app guard、代表旧分析拒绝/state 清理、登录云代理和正常 AI 落子的实际核验；本审核不代替这些运行验收。

### EnvironmentFiles 序列与私有诊断叶子修订

主代理报告首次 0cb apply 检查失败，已精确恢复到启动前状态：Go inactive/PID0、有效 Env 与 beforeimage 相同、两个新增文件不存在，未恢复数据库。由于当次未保存原始失败点，不能认定 systemd 换行分隔就是已证实的原因。

**最终增量 Approved：** `rk_guard.py` SHA-256 `f25289b743c3f531c46a5858c351974debab6b1fdc4fa27324ff27efb613eb1e`；测试文件 `620e722a35ae6e80716e08f94d18efe89cbf435cd7e2c9c480e9926ff112969e`。独立逐字节对比保留的已审 0cb 版本，变化仅为：EnvironmentFiles 从原始字符串拼接比较改为有序 `(path, ignore_errors)` 列表比较，以及新增 mode0600 的私有 after/阶段失败诊断。空白分隔差异不改变语义，重排、不同路径/optional 标志或未解析内容仍拒绝。

中间 b1f7 版本的失败诊断写入可能阻断原恢复，因此未放行；最终版本将该诊断 I/O 处理为 best-effort，保存失败仍继续原恢复分支。独立 **8 tests passed，退出码 0**，包含换行分隔、重排拒绝，以及 after/failure 双诊断 I/O 故障时仍删除 owned 新文件、daemon-reload 并完成启动前恢复的定向用例；语法与 hash 核对通过。原 helper、三字段范围、维护锁、启动/activation 后禁止 legacy 及禁止数据库恢复边界均未改变。

允许主代理使用新私有目录 b，经新鲜 prepare/CAS 后执行一次有诊断证据的 apply；不清除旧失败回执、不盲目重试或覆盖 SQLite。审核者未执行该远端操作，首次恢复状态来自主代理回执，后续结果仍需实际确认。

## TEST/live Kiosk 付款提示修复

**Approved。** 产品差分仅 `MembershipPage.tsx` 一行：模拟订单提示改由 `catalog.payments_mode === 'mock'` 决定，不再由 TEST 环境标识决定。TEST badge 保留；TEST/live 复用现有 11 语“付款前核对订单金额”文案。没有改金额、购买动作、支付状态或翻译目录。

新增 live/mock 两个参数化断言同时核对 TEST badge、脚注与没有自动创建订单。独立执行该页面测试文件：**17 tests passed，退出码 0**。无需为此重做布局设计或全状态视觉回归；部署后仅需核对代表性真实 TEST/live 页面文案。实际修复提交为 `9db75414c`。

## 联合云发布采用已有独立审核

主代理与 USB 功能负责人已协调共同云发布。最终源码会包含已独立审核的 USB 改动（云端默认关闭）及上述会员提示修复；会员产品增量仍只有这一行。发布机制沿用[共享 USB Hub 代码与发布工具审核](2026-11-09-usb-hub-code-astra-max.md)的 Approved 结论，本轮不重复审核该产品或工具：

- `cloud-release.py`：`953eaba6e467f01949774dcdd17aa074f22e6ab51e32c0fdab4801ab8fa8f179`。
- 该会话的 `native-release.py`：`92769832dc735ceacb73eba79337bf3d6a066d429e0d8ae2e3594738feb5881c`。

该独立审核明确覆盖 code-only 构建 SHA 变更、实际商业模式、微信参数与只读挂载保留，并已复核其相对原 native98 的精确差分。由主代理核对最终 published develop、工具精确字节及新鲜实际配置，单点执行部署；本报告不将该独立审核冒充本审核者重新执行的验证。

本目录 `forward-release.py`（`e817d9c27bfb18c94dd66263ad5c278d8978dbc2a92429332480f3657ac9ff1c`）仅为未执行的本机历史候选，已停止审核，不作为此次发布依据。原 `activate.py` 04cba 仍固定 4235 软件基线；若先发布联合软件版本，再开启 PROD，必须对激活目标 SHA 作精确适配和字节复核，不能绕过原 baseline 校验。开启与代码发布的实际结果仍由最终运行回执说明。

## 2026-11-10 实际回执与代表页面终验

**Approved，可收尾本次配置开放、联合软件发布与代表性入口验收。** 本节仅复核已有实际证据，不重新执行部署、浏览器流程或测试矩阵。

已读取本机 `joint-verified-test.public.json`、`joint-verified-prod.public.json` 及 PROD 开闸/发布后只读账务回执。两云实际软件均为 `caf97c03db089eb851170491da5c9d99ee0d3d21`，`enabled/live / BILLING_ENFORCED=true / FREE_WEEKLY_REPORTS=0 / Max=true`；USB 自动恢复保持 false。两站 HTTP health 200、restart0、实际完整配置匹配 manifest，967 个载荷文件、445 个 Python 源文件及 11 套语言目录各 345 个会员键核验通过，其他运行容器分别为 TEST 16 个、PROD 18 个且保持不变。具体完整容器/镜像及恢复资料见[开放回执](../../operations/wechat-native-activation-release-2026-11-10.md)；本次核对的最终 Web 分别为 TEST `8f36b26788b4…`、PROD `15f0c1a6f4f4…`。

仅目视指定的三张实际图片，未要求重拍或扩大状态矩阵：

- `test-kiosk-topup-after-fix.png`（1024×600）：TEST 徽标保留；“模拟订单／不会真实收款”误导已消失；选中 ¥10、`充值 ¥10` 按钮及“付款前核对订单金额”清楚完整。
- `prod-galaxy-plans.png`：Plus/Pro/Max 的 39/99/199 元及三个选择按钮清楚可见，没有 TEST 或模拟收款误导。
- `prod-kiosk-topup.png`（1024×600）：显示“云端已同步”；10/30/100 元选项、选中 ¥10、充值按钮和核对金额脚注完整，没有 TEST/mock 文案。

上述图片位于 `output/playwright/wechat-native-activation-20261109/`，由运行验收代理采集；本审核者仅读取图片和公开回执，没有连接远端、导航页面或点击购买。已对[开放回执](../../operations/wechat-native-activation-release-2026-11-10.md)的核心事实与范围作聚焦复核。

RK 状态依据主代理实际回执：既有 4235 软件已追加三项 guard 配置并启动，activation marker 存在，本地支付仍 disabled、无商户密钥；真实屏幕仍处于 launcher 登录页。**未将其写成 fan 登录后的云代理、旧 API 409/state 边界、手机扫码或消费动态旅程已验收。** 截至所读账务回执没有真实订单，不能据此宣称下单响应、通知验签、到账幂等或真实收款成功；这些仍须用户本人付款后的实际观察。
