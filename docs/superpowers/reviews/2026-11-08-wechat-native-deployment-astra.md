# 微信 Native 发布封装聚焦审核（Astra Max）

日期：2026-11-08。结论：**Approved；未发现阻塞本次已授权代码部署的实际风险。** 本审核限精确载荷、配置保留及 11 语发布事务链，不重做已通过的支付功能审核。

审核版本：已发布 KaTrain `develop` `4235a58238e805530cb07ef0eb8041ba93df586f`，两云实际基线 `49b7cf79c052591bcc5532bea4dbee36e521bf87`。前者与已验证功能分支 `47c56913a` 内容一致，包含当前 develop 的完整围棋五语目录及热插拔改动；原会员目录与本轮 17 键保留。主代理已报告合并后的 96 项 Python 和 80 项前端检查通过。

## 云端载荷与配置

已审 `output/wechat-native-deploy-20261108/release.py`、`test_release.py` 和其调用的已审核 `native-release.py`。依据 `server-deploy` 技能的实际配置保留要求检查；本轮原 native helper 字节未改变，SHA-256 仍为 `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108`。

- 包装器要求完整提交 SHA、等于本地已抓取的 published `origin/develop`、实际基线为祖先，并核对 Git archive 内嵌提交。构建不使用工作树或忽略文件，清除继承的 Vite 开关，生成普通 Web 完整静态包。
- 独立将本次精确提交与实际基线送入载荷选择/覆盖检查：**445 个运行文件、146 个提交差异全部分类覆盖**，Native 客户端、账务、配置、迁移、模型、路由、server 及代理所需 Python 均在载荷内。未知运行文件改动或运行代码删除会拒绝，不静默漏发。
- 只清空并替换 Web static；运行代码定向覆盖。原 `katrain/config.json`、模型、KataGo、字体、声音和其他资产不被源码默认值覆盖。候选从实际旧镜像构建，离线构建/只读无网络探针不启动应用或数据库。
- 全部 11 套 PO 来自精确提交并重新编译 MO，校验 345 个会员键及完整目录 hash，目录不缩回旧五语或仅 Git 跟踪的中英文 MO。包清单、模式和文件 hash 核对，并拒绝归档路径逃逸、链接及多余 static 文件。
- 私有 beforeimage 和清单经 full container ID/image/fingerprint CAS 绑定，固定主机/daemon/目标 Web。新容器克隆现有 Config、HostConfig、挂载和网络；环境集合必须一致，除构建 SHA 外不允许值变化。仍为 `paused / disabled / enforced=true / free=0`，不注入微信秘密或额外挂载，不替换 Cron、GPU、Postgres 或其他服务。
- 包装器不含 apply 子命令。实际切换调用原 helper 时仍须使用已审核清单 hash 和旧完整 ID/image。当前 `rollback_compatible=false` 的失败策略是停止并保留原容器及失败候选，**不是自动恢复旧版**；原数据与完整 beforeimage 留存供明确恢复决策。切换后仍应完成健康、实际解析配置、逐文件/11语及代表性页面验收。

独立本地执行云包装器测试：**12 tests passed**。仅本地临时文件及模拟 Engine，未接触 Docker/远端。

## RK 11 语事务链

审核父仓隔离工作树 `smartbox-software/.worktrees/membership-wechat-release-20261108` 中三个文件的稳定差异：`scripts/rk3562_deploy.py`、对应测试和 `docs/rk3562-deployment-storage.md`。生产变化仅将语言元组由五语扩为十一语及说明更新；未另建安装路径或绕开原发布流程。

精确 gitlink PO → MO → manifest 的 PO/MO 双 hash → 维护/停服前校验 → 原应用目录传输 → 逐文件备份 → 原位回滚的链路覆盖所有 11 语。缺少新增语言源、缺 manifest 记录、PO/MO 缺失或篡改会在维护和运行变更前拒绝。旧版无语言字段 manifest 保留既有兼容行为；带语言字段但只有五语的候选须重新导出，文档已明确。回滚恢复全部 11 个 MO 及匹配源码、静态、manifest 和原数据库，未在 manifest 后手工补产物。

独立执行新增目录边界与完整文件回滚的聚焦测试：**15 passed / 91 deselected**；主代理/实现者另已完成该部署测试文件 **106 passed**。无需重复全套功能或设备流程。

## 授权与验收边界

用户已授权四步集成和代码部署，本审核允许在该范围继续；真实收款、商户秘密安装/配置、真实微信 API 和扣款不在授权内。审核者未执行 apply、远程变更或商户请求，未输出秘密。这里只批准部署机制和候选载荷，不把准备、发布 Git 提交或本地测试当作两云/实体已完成部署验收；最终回执需列实际运行版本与验收结果。

## 设备现场门禁补充

聚焦复核 `output/wechat-native-deploy-20261108/device-mode-coherence.py` 与已部署 helper 的 `Runtime.start/capture` 和 launcher 锁协议，结论 **Approved**。修复只允许在 Hermes target 为 inactive、实际 Wants 精确等于固定 WebUI/STT/voice 三服务白名单、配置成员为该集合的子集、三服务全部 active 且 PID 非零、Requires 已 active、实际 Conflicts 全 inactive/failed、其他四模式无活动或过渡服务、唯一现有 page 仍为精确 launcher URL 时执行。唯一运行状态写入为 `systemctl start` Hermes target；没有停止服务、账户操作或页面导航。完成后验证三个成员 PID、setup PID、其他模式状态和原 page 的 ID/URL/WebSocket 地址不变。首次尝试因现场配置仅登记 WebUI、而 target Wants 包含三个服务，在 start 前拒绝并释放自己的锁；第二次只修正该已核实的成员集合差异，不允许未知单位。

补查 live Conflicts 后，避免仅凭配置中的其他模式推断 systemd 的停服集合。命令单次最多 15 秒，总预算 90 秒；前置失败和成功仅按 inode 与 owner 释放本脚本创建的锁。start 已尝试后的失败保留锁供操作员立即诊断，不静默停止或回退。既有 launcher 在 180 秒后可回收 stale lock，因此保留锁不是永久隔离；脚本和本回执均不作该保证。本地仅做源码审核及语法解析，未执行设备操作。

完整读过 `output/wechat-native/rk-prepare-fd7bc6bc/archive_translation_release.py`，**离机归档机制 Approved，清理须等真实验证完成**。旧 `translation-completeness-20261108T134804Z-a0d0cb1a` 整棵 release 被视为恢复资料，流式保存至新建的私有 0700 本地目录，文件 0600。校验覆盖完整 entry 集合、文件 SHA/size/mode/uid/gid、软链接及硬链接内容、gzip 完整性；源树在前后两次清单中必须不变，且无打开 FD、后代挂载或跨文件系统条目。脚本不含设备删除或服务写入。

仅在最终 verified proof 落盘、清理前再次匹配 source-after 并复查 FD/挂载后，才可释放该旧 release 的两个精确顶层目录 `files/` 与 `static/`。其 metadata、DB、Rime 和 live pointers 留存，不把旧回滚副本称作垃圾；离机归档保留恢复所需的完整内容与权限/归属。清理后必须重跑真实容量预算并保留 1 GiB，不能用估算代替实际可用空间。本审核未声称归档传输、清理或设备发布已完成。

随后已读取真实 `archive-proof-public.json`：5,393 entries 验证通过，源树前后不变、两次 FD 为零，私有归档为 482,693,619 字节，SHA-256 `4aa2ebc27b36d3da02a7670078264390e5a27ea048b588821317082d23db7203`。此回执确认归档阶段完成，状态仍为 `verified-no-cleanup-performed`；不替代清理时的 source CAS 与实际预算。

已完整审核独立 operator `output/wechat-native/rk-prepare-fd7bc6bc/cleanup_translation_backups.py`，SHA-256 `0eafd47dba199c3065039c5ce9bf6685a5aeaf0565433e7645cf9189f9638858`，结论 **Approved，可执行该精确版本**。它在 `--execute` 后复核本机归档、proof、source-after、已审清单工具的固定 hash 与私有权限；原子发布完整 JSON 锁并每 15 秒刷新，锁内再次完成 canonical CAS、FD、挂载和活动指针检查。先写入并 fsync 离机恢复指示，再以 release 根目录的 dir_fd 锚定，仅删除两个已验证 inode 的 `files/`、`static/`；随后逐 entry 核对 metadata、DB、Rime 等所有保留资料，仅豁免根目录因增删子项自然变化的字段。锁清理受自身 token 与 inode 约束，无服务、模式、页面或身份操作。独立只做本地及嵌入远端代码的语法解析，没有执行 operator 或 SSH；实际清理回执和清后容量预算由执行者确认。
