# 会员与充值 11 语言发布回执

2026-11-04（北京时间约 01:55）：已完成开发、独立 Astra Max 审核、四步集成，以及先 TEST 后新 PROD 的 Web 发布和实际页面验收。

## 发布内容

- Galaxy / Kiosk 的会员、用量、API 充值、订单、额度说明、分析扣费确认和相关登录/错误提示，共 328 个键、3608 条译文。
- 全部 11 种语言：英语、简体中文、繁体中文、日语、韩语、德语、西班牙语、法语、俄语、土耳其语、乌克兰语。
- 打开的确认页、回执和错误信息随语言切换更新，不创建新订单、不重置额度或身份。显示数字与进度条原始数值分开；时间仍为北京时间，金额仍为人民币，非中文币种标识避免与日元混淆。
- 修复手机端长文本/页签/充值金额及 Kiosk 长文本卡片布局。保留现有套餐、额度、计价、账务和支付边界。

## 已发布软件版本

- 功能分支软件：`48450b4c4`（主要实现 `8ca3166e6`，随后仅格式整理）。
- 已发布 develop / 两端实际 Web 软件：`959800a4679447b871c7ad6ef89d062e93cd15bb`。
- smartbox-software 父 main：`58372bd892e59eea716aedd504b54d9a34519b17`，vendor/katrain 指向上述 develop。
- 后续回执/计划收尾为文档提交，不改变实际运行的软件版本。完整源码构建来自上述已发布提交的隔离 Git archive，未复用脏工作区静态包。

| 环境 | 实际新 Web container ID | immutable image ID |
| --- | --- | --- |
| TEST home-ubuntu | `ffe7a86e66ff8560164de8ab361a863ad1c6e408fdcb117078ff48639d3bd1dc` | `sha256:3a605ec2b74f87262a8c3856443b90b68755ce647bc9bf87d7e3e57b58a5e57f` |
| 新 PROD 117.50.177.254 | `8ac6c90df11644be49713798509cdbd6808d51f0fb37144f68f11c20041e66b5` | `sha256:9ddc30868e2249eb3925b7e4eb02e5ff1e947a94a6856e63e5252ccf8bb07319` |

两端 HTTP 200、restart 0；PROD healthy。仅替换 Web 的静态包及 11 套 PO/MO；每端实际校验 493 个文件（471 个 static、22 个 PO/MO），11 个真实 `/api/translations` 响应逐项核对全部 328 个键。公开域名首页字节与发布包一致、英文全部键匹配；实际 fan 登录页无 route mock、无账务 POST。

TEST 其余 13 个、PROD 其余 18 个运行容器的配置、身份、启动及重启事实未变，Cron/GPU/数据库/MinIO 未重启。PROD Web 保留 8 GiB 内存、12 GiB memory+swap、4 CPU；两端保留现有网络、挂载、完整环境与角色配置。旧 Web 已正常停止并保留为备份。

## 审核和验证

- [计划审核](../superpowers/reviews/2026-11-04-membership-i18n-plan-astra-r1.md)：初审后仅针对数值/显示分离做第二次核对，Approved。
- [独立代码、翻译和视觉审核](../superpowers/reviews/2026-11-04-membership-i18n-final-astra.md)：Approved，无未解决重大问题。
- 聚焦 UI：14 个文件、190 项通过；Python 目录/gettext：14 项通过；普通前端及最终严格 Kiosk 构建通过。发布包另用 `npm ci` 从精确提交重新构建。
- 浏览器 7 项覆盖通过：11 语言 × 三页签 × 两端、德语进度条数值、打开订单/回执/错误时切换语言，以及 375px 和 1024×600 的可用性。最终新增布局/币种修改后复跑受影响用例；未重复无关全量回归。
- PO 只追加本次会员键，既有目录内容保留。按 skill 执行 `i18n.py` 时出现既有全局缺键/默认目录问题（exit 2）；已撤回其无关归一化，直接重新编译并实际验证全部 11 套 MO。该历史问题不冒充为全项目翻译检查通过。
- [截图](../../output/playwright/membership-i18n-20261104/)含隔离状态预览及 `test-live-*` / `prod-live-*` 实际服务器页面；隔离订单状态不代表正式收款。

本地运维回执位于 `output/releases/membership-i18n-20261104/`。部署包 SHA256 `418b70649cf402ec6e6c9b0c1e29b552e1055148ad6e9ce3938a565c95177f4f`；复用 native helper `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108`。私有 manifest/备份证据保存在 TEST `/tmp/membership-i18n-private-959800a467`、PROD `/var/tmp/membership-i18n-private-959800a467`，未把凭据放进 Git 或公开回执。

本轮专用浏览器已关闭，两条 SSH 隧道已关闭，临时验证凭据与隔离构建的 node_modules 已删除；发布包、截图和回执保留供验收。

## 验收入口与边界

- TEST：[Galaxy](https://go.sailorvoyage.top/galaxy/membership)、[Kiosk](https://go.sailorvoyage.top/kiosk/membership)。
- PROD：[Galaxy](https://modelstella.com/galaxy/membership)、[Kiosk](https://modelstella.com/kiosk/membership)。
- 登录后切换语言，检查用量、会员和 API 充值；重点看德语/俄语长文本、手机页签和 Kiosk 滚动区，金额应保持人民币。
- 正式服务仍为 membership paused、payments disabled、billing enforced=true、Free=0、Max 独立 gate=true；不开放真实支付，不新增模拟支付入口。正式商户接入及真实支付/退款验收继续按原阶段 B 办理。
- 本次完成云端 Web 和浏览器 Kiosk 发布、父仓库指针更新及严格设备构建；未执行实体盒子升级或实机验收。
