# 微信 Native 配置部署聚焦审核（Astra Max）

日期：2026-11-09。**规格符合性：Approved。代码质量与配置安全：Approved。** 未发现阻塞下列精确版本按 TEST→PROD 顺序继续配置的剩余问题。该结论批准配置机制，不代表远程配置已完成或真实微信支付已验收。

## 审核版本与范围

运行软件保持 `4235a58238e805530cb07ef0eb8041ba93df586f`。完整阅读本次一次性操作器、对应测试、README、其复用的原 native helper，以及[配置部署与计划复核](../../operations/wechat-native-config-release-2026-11-09.md)。审核文件位于 Git 忽略目录 `output/wechat-native-config-20261109/`：

| 文件 | 独立核对的 SHA-256 |
| --- | --- |
| `configure.py` | `9d15cfbe9a0039085ab89581cd8ef3d69b4372428f770fd84424769cd883d068` |
| `test_configure.py` | `7bcd1f5273ecbc985b752476cdb4c9692337819c6e524aadfa81f56eb0aa612d` |
| `native-release.py` | `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108` |

原 helper 字节未改。本审核未扩大支付产品设计、计费实现或测试体系；仅覆盖本次秘密传输、安装、Web 配置替换、状态记录与恢复边界。

## 规格符合性

- 固定 TEST/PROD 主机、daemon 与目标 Web。新配置复用实际完整 Config、HostConfig、原挂载及稳定网络配置，保持同一不可变镜像、软件 SHA、Config.User、其他 Env、资源与角色设置。只增加 8 个微信公开标识/文件路径 Env、1 个固定只读 bind，并更新原 helper 的操作标签。manifest 的 `changed_fields` 已准确列出该增量，并重新计算供 apply 核对的字节 hash。
- 现有 `MEMBERSHIP_MODE=paused / PAYMENTS_MODE=disabled / BILLING_ENFORCED=true / FREE_WEEKLY_REPORTS=0 / MEMBERSHIP_MAX_SALE_ENABLED=true` 均是明确前置条件，配置不改变这些值。不存在开启收款、改价、重建镜像、数据库迁移或其他角色重启路径。
- TEST 使用 fan 自有的 `/home/fan/.config/katrain/secrets/wechat-pay`，不请求 sudo 或运行特权安装容器；现有 Web 的 0:0 保持不变。PROD 经既有 sudo-root 权限安装到 `/etc/katrain/secrets/wechat-pay`，归属 10001:10001。两端只读目标均为 `/run/secrets/wechat-pay`，通知 URL 按站点固定。
- prepare 只写私有 beforeimage、计划和其他服务指纹，不安装主机秘密或替换 Web。apply 在安装前及切换前核对完整旧容器 ID、不可变镜像和配置 fingerprint，并绑定审核后的计划/manifest hash；原 helper 自身由固定 SHA-256 加载。远端仍须核对本次操作器的精确上传字节。
- 计划复核保留 39/99/199 元及 term/week 规则。对 `billing_operations.py:_source` 的聚焦只读检查确认：本期与本周都足够覆盖整次操作才选 membership，否则选 wallet；本次没有修改该业务代码。

## 代码质量与安全

- 三个标准文件仅在内存中打包后作为 SSH stdin 传输，使用已知主机检查；秘密不进入 argv、Docker Env、标准输出或公开回执。接收端只接受固定的四个普通文件名（含公开 identifiers），拒绝路径逃逸、链接、重复项及超限归档。私有 staging、证据及主机秘密使用 0700/0600。
- 安装拒绝已有非空目标，不覆盖既有秘密。安装前先写 exclusive、fsynced 的私有尝试回执；部分安装或离线探针失败记录当前文件名、`cutover_started=false` 和禁止重试状态。失败材料留存供检查，不假称服务已切换或秘密已自动清理。
- 离线探针使用原不可变镜像、真实 Web UID/GID、`--network none`、只读根与只读秘密挂载，仅调用现有客户端的本地文件 readiness；不启动应用或调用商户 API。切换后的检查核对完整运行配置、健康/restart 状态、文件 hash/权限、实际本地 readiness 和其他运行容器指纹。
- 同镜像、无迁移的操作明确使用完整 beforeimage 恢复。恢复前以及停止/改名前均验证 owned-new 的完整 Config、HostConfig、网络与只读挂载；配置漂移时拒绝停止/重命名并记录 `recovery-required`，不将标签或镜像相同当成充分归属证明。
- 成功后以 fsync 和原子 rename 写入持久私有 `active.private.json`，记录已核验的 Web/image、公开配置、paused/disabled 状态及 beforeimage 路径/hash。恢复成功会移走该 active 记录；秘密文件仍私有保留，原 Web 不挂载它们。该记录描述最近核验的配置，后续仍须以实际运行状态验收。

预审发现的安装前阶段缺少失败回执、恢复仅核 label/image 两项已在上述精确版本修复；辅助变更清单也已更正。不再保留未解决的阻塞项。

## 独立验证与执行边界

独立执行 `/Users/fan/Repositories/katrain/.venv/bin/python -B output/wechat-native-config-20261109/test_configure.py -v`：**16 tests passed，退出码 0**。三个 Python 文件 AST 语法解析通过，文件 hash 与冻结版本相符。测试使用合成数据、一次性 RSA 密钥和模拟 Engine/subprocess，覆盖精确增量、只读/资源漂移、staging/stdin、权限、CAS、部分失败回执、拒绝盲重试、恢复归属及 active 私有持久化。没有重复支付功能全量回归、11 语或设备测试。

**审核者未执行 SSH、Docker、部署、真实凭据 staging 或商户 API，也未读取/输出 `/Users/fan/cert/` 中的密钥正文。** 真实凭据既有配对/格式检查由主代理负责，不能由本次合成测试代替。

可由主代理继续新鲜远端 prepare/CAS，先完成 TEST 配置及实际健康、readiness、11 语/代表页面、收费开关、账务和其他服务保留核验，再执行 PROD。同意配置不包含真实订单、扣款、到账或正式开放；这些仍须独立授权与真实验收，不能以本地 readiness 或本审核通过代替。

## 后续 PROD SSH alias 修复快审

主代理随后报告：TEST 已使用上述 `9d15cfbe9a0039085ab89581cd8ef3d69b4372428f770fd84424769cd883d068` 操作器完成 apply 及独立实际验收；PROD 的 send 在 SSH 身份认证阶段失败，未安装秘密、未切换 Web。主代理核对既有 `ucloud-v100` SSH alias 的登录用户为 ubuntu，原显式 `fan@ucloud-v100` 覆盖了该配置。

**修复规格与代码快审：Approved。** PROD 候选操作器 SHA-256 为 `3e529a8fa0b0603c57f8ada5b963159dacc3f632f95c0c549e33b7e7489cd8cf`，测试文件为 `9f8eeca2d8039adc7e2975e8015c2a40666c947896597e89ce74a81233d69c1b`。独立核对保留的 `configure-test-applied.py` 仍为已审 9d15 版本，并通过完整字节替换断言确认：源代码唯一差异是 `SSH_HOSTS["prod"]` 从 `fan@ucloud-v100` 改为 `ucloud-v100`。接收端、prepare、apply、恢复、固定主机/daemon 核验及完整 ID/image CAS 均未改；TEST endpoint 未改。

独立执行新增实际 send argv endpoint 测试及既有 stdin 传输、站点执行身份测试：**3 tests passed，退出码 0**；三个 Python 文件语法解析通过，原 native helper hash 仍一致。无需重跑其余部署机制或产品测试。可仅向 PROD 上传该精确修订版本，复用既有 SSH alias 后仍以 `sudo -n` 执行。TEST 保持已完成的 9d15 配置，不因本次传输修复重做。

本节 TEST 实际结果与 PROD 认证失败状态来自主代理回执；审核者仍未执行 SSH、远程写入或读取真实密钥。新 PROD 配置是否完成，仍由后续实际部署回执证明。
