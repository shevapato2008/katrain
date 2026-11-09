# 微信 Native 代码发布回执 — 2026-11-09

> **后续配置完成：** 用户准备商户资料并授权后，TEST和PROD配置及独立实际验收均已通过，新的实际Web容器/配置和计费计划复核见[后续回执](wechat-native-config-release-2026-11-09.md)。本文旧容器及“资料未准备/配置待确认”为代码发布完成时的历史状态；软件仍4235，真实收款关闭，真实扫码和到账尚未验收。

**代码已发布至 TEST、新 PROD 和实体智星盒，11 语保留；真实收款仍关闭。** 本次从用户“微信支付需要部署啊”的明确授权继续四步集成；不包含支付秘密安装、商户平台变更、启用收款或真实扣款。实体登录后页面和手机真实扫码仍待终验。

## 精确发布来源

| 项目 | 提交/产物 |
| --- | --- |
| 已发布功能分支 | `47c56913a` |
| 已发布 develop / 两云运行软件 | `4235a58238e805530cb07ef0eb8041ba93df586f` |
| 本次运行载荷的父仓 main 来源 | `fd7bc6bc922d43cf4da51e72f6d1cde511addf1c` |
| 父仓 `vendor/katrain` | `4235a58238e805530cb07ef0eb8041ba93df586f` |
| 两云共同部署包 SHA-256 | `4ae612190e5325ba3218070794dfb387d7b848cae92bc56bfadc792ef3744143` |

先合并当前 develop，解决五套完整目录冲突，保留既有五语围棋翻译、热插拔修复和全部 11 语会员键，再推功能分支、合入并推 develop。父仓合入已在设备运行的 `a0d0cb1a...` 前端历史及后续文档，避免从旧 main 覆盖其他会话的三棋修复。独立父仓工作树完成 gitlink 发布，原父仓的无关工作树变化保留。

两云从精确 Git archive 生成同一软件载荷，分别基于各自实际旧镜像构建；不覆盖可变 `katrain/config.json`、模型及其他资源。445 个运行源码文件加 22 个 PO/MO、497 个普通 Web 静态文件经清单验证。文档收尾提交不代表运行镜像另有变化。

发布完成后的本回执、配置指南和审核说明作为纯文档尾提交再次经功能分支、develop及父仓gitlink发布；不为纯文档变化重复部署。上表固定记录实际运行载荷，不把后续文档HEAD冒充云端或实体运行版本。

## TEST 先行、PROD 随后

| 项目 | TEST `home-ubuntu` | 新 PROD `ucloud-v100`（117.50.177.254） |
| --- | --- | --- |
| Web | `katrain-web` | `katrain-ucloud-katrain-web-1` |
| 新容器 ID 前缀 | `695669c2d7f9` | `163933b6fe6b` |
| 不可变镜像 | `sha256:165a6b2d8ac948be403f9e55e2477a71ef34d0a54dc370bebf970f7a2a4b6383` | `sha256:0356ac1ae1de4b1a47a7d7d76d4337ab41a273d79e15881aca07da56d7504995` |
| 实际 build/OCI revision | `4235a58238e805530cb07ef0eb8041ba93df586f` | 同左 |
| 健康 | HTTP 200、restart 0 | HTTP 200、Docker healthy、restart 0 |
| 实际解析设置 | `paused / disabled / enforced=true / Free=0 / Max sale=true` | 同左 |
| 其他运行容器 | 17 个，配置/挂载/网络/启动时间及身份不变 | 18 个，同左 |

仅替换 Web，保留各自完整实际 Config、HostConfig、角色 Env、网络、资源限制和挂载，除构建标识/必要镜像标签外没有配置差异。未添加任何微信 Env 或秘密挂载；未重启 Cron、GPU、Postgres 或 MinIO。旧 Web 容器正常停止后保留为备份，旧镜像及私有 beforeimage 留存。未访问已退役的旧 PROD。

数据库仅新增 nullable JSON `payment_details`、nullable `timestamptz` `payment_next_check_at` 和对应 BTREE 索引。只读核对迁移前后账务规模一致：

| 表 | TEST | PROD |
| --- | ---: | ---: |
| `recharge_orders` | 0 | 0 |
| `membership_terms` | 0 | 0 |
| `credit_transactions` | 14 | 9 |
| `users` | 19 | 12 |
| `system_config` | 2 | 3 |

两端在途 Native 单均为 0。TEST 的会员相关 PG dump 已用 `pg_restore` 解码校验；PROD 的 `pg_dump` 一次失败后，使用 READ ONLY / REPEATABLE READ 一致快照及 schema 留存，**该 JSON 快照不能直接用 pg_restore 恢复**。备份、容器配置与数据库内容仅保存在各机 0700/0600 私有目录，没有写入 Git/聊天。

## 实际网站、Galaxy、云 Kiosk 验收

网站与 Galaxy 是同一应用，正式会员入口为 [modelstella.com/membership](https://modelstella.com/membership)，云 Kiosk 为 [modelstella.com/kiosk/membership](https://modelstella.com/kiosk/membership)。TEST 为 [Galaxy](https://go.sailorvoyage.top/membership) 和 [Kiosk](https://go.sailorvoyage.top/kiosk/membership)。旧 `/galaxy/membership` 不是当前入口。

- 两端真实页面 HTTP 200；登录后实际 auth、catalog、usage、orders GET 均为 200，没有 route mock、账户/账务写入或分析请求。
- 分别检查 Galaxy 1440px 德语、375px 英语，Kiosk 1024×600 简中及德语：没有水平溢出或页面错误，购买控件按真实 paused/disabled 状态禁用，订单历史仍可读取。短时隔离浏览器身份及存储已清理，专用会话与 SSH 隧道已关闭。
- en/cn/tw/jp/ko/de/es/fr/ru/tr/ua 实际 HTTPS 翻译接口每种 **345 个会员键**，逐语 hash 匹配精确部署产物；既有 328 键保留并增加 17 个微信状态/说明键。
- HTTPS 通知路由已在两端 OpenAPI 注册 POST。各发送一次空正文无签名 POST，均返回 400 `invalid_payment_notification`；之后账务计数不变。GET 因既有 static catch-all 为 404，不能据此判断 POST 未部署。没有模拟到账路由、真实商户调用或真实支付通知。

本地已贯通“选择会员/充值 → 微信按钮 → QR → 验签通知/查单 → 同事务发放 → 自动刷新”，使用模拟微信传输和实际隔离 PG。部署后的真实服务保持关闭收款，因此不冒称实际微信扫码、真实到账或结算已验收。

## 实体智星盒

实际设备为 `rk3562-local`（192.168.0.104，hostname `gzpeite`），1024×600。`app` 事务 release 为 **`wechat-native-20261108T1602Z-fd7bc6bc`**，于北京时间 **2026-11-09 00:11:57** 返回 `verified`；父来源 `fd7bc6bc922d43cf4da51e72f6d1cde511addf1c`、围棋软件 `4235a58238e805530cb07ef0eb8041ba93df586f`。不是全盘镜像升级，没有安装或升级 Python 依赖、写支付秘密或改真实用户账号。

- canonical 事务从精确提交重建四棋前端及普通/严格 Kiosk，生成全部11套PO/MO后进入同一manifest、传输、备份、安装和回滚链。安装后逐语 PO/MO hash 匹配发布 manifest，每套实际 MO 含345会员键；7个支付/代理/服务运行文件逐一匹配精确源码。
- 保存5份实际数据库一致备份，完成迁移及业务数据守卫、五模式 readiness、Rime及浏览器输入法检查，保留源文件、静态包和数据库回滚资料。Go/五子棋摄像头均离线，使用已批准的 app-only `allow_offline_camera` 跳过摄像头就绪检查，**不称摄像头健康或识别验收通过**。
- Hermes 原模式、setup服务和唯一原 Chromium page ID `701DDACA3AFFA4968753F69AD8CD8291` 恢复，URL仍为 `http://127.0.0.1:8080/launcher`；其他棋类模式按原状态停止，维护锁释放，成功后的可再生成 incoming 已移除。最终根分区可用1,744,764,928字节，仍高于1GiB保留量。
- 保留前一会话已发布的 `a0d0cb1a...` 父仓及 `fda461ef...` 围棋运行修复，两者分别是当前父/vendor提交的祖先。设备窗口与该会话协调交还，登录和内页验收由其继续；不重复索取登录、不用临时账户替换设备用户。

发布前曾因rootfs预算差约471MiB而停止，没有绕过1GiB门禁。先将旧 `translation-completeness-20261108T134804Z-a0d0cb1a` **完整**回滚目录流式归档到 Mac 私有目录 `/Users/fan/Backups/smartbox/rk3562-20261108-wechat-native/`，验证5393 entries、内容/权限/数值属主/链接、gzip及源树前后一致。归档482,693,619字节，SHA-256 `4aa2ebc27b36d3da02a7670078264390e5a27ea048b588821317082d23db7203`。经Astra批准的清理器锁内再次校验，只移走该旧release的顶层 `files/`、`static/`，其余38项metadata/DB/Rime资料逐项保留，并先落盘离机恢复指示；不是删除不可恢复备份。清后真实预算2,342,010,880可用 / 2,274,185,216必需（含1GiB）通过，之后才发布。

原设备存在Hermes成员active而target inactive的模式不一致。经独立审查的有界修复只启动该已有target，在成员/冲突/页面严格前置条件下验证3个成员PID、setup和原page不变，再进入canonical事务。其私有前后记录位于设备 `/var/lib/smartbox/deployments/wechat-native-hermes-coherence-4235a5823-2/`。

设备 Go 在事务中完成后端就绪检查后即停止并恢复Hermes。本次未捕获完整逐语HTTP采样窗口，不将文件校验冒充实体翻译API或登录后的屏幕验收；实体正常登录、会员页面/云身份及实际手机扫码继续留待终验。原进程旧 `KATRAIN_BUILD_SHA` 不能替代此次安装来源，以上版本以精确发布manifest、文件hash及成功事务为依据。

## 验证与审核

已通过的实施验证为 Python **213 passed**、前端 **80 passed**、Playwright **6 passed**，普通及严格 Box SSO/Kiosk2D 构建通过；二维码截图独立解码与原始 `code_url` 一致。与当前 develop 合并后的聚焦检查为 Python **96 passed**、前端 **80 passed**。云发布包装器 **12 passed**，父仓 RK 发布测试 **106 passed**；独立 Astra Max 另复核 15 个目录/回滚边界测试。

[支付代码、安全及视觉终审](../superpowers/reviews/2026-11-08-wechat-native-code-astra.md)和[部署封装/11语事务链审核](../superpowers/reviews/2026-11-08-wechat-native-deployment-astra.md)均 **Approved**。既有全局 `i18n.py` 缺键不在本次修复范围；实际使用专用编译器/发布 manifest 校验全部 11 语，未声称历史全项目国际化检查通过。

本地忽略目录 `output/wechat-native-deploy-20261108/` 留存两云 prepared/verified/postcheck、浏览器验收及清理报告；`output/playwright/wechat-native-release-20261108/` 留存实际页面截图。这些是本机证据，核心事实已在本文及 Git 审核报告记录。

## 尚未完成：真实收款配置与手机终验

用户已说明资料尚未准备。[操作指引](wechat-native-credentials.md)包含商户 API 证书/私钥、API v3 密钥、微信公钥/ID的获取方法及建议私有目录。只提供目录路径、证书序列号与公钥 ID；不向聊天、Git 或日志发送秘密内容。现有正确 AppID/商户号只记录在文档，未擅自写入运行配置。

后续依次是：用户安全准备文件 → 展示实际 Web 配置/挂载差异并获批 → 保持关闭状态做配置核验 → 明确账户、金额、权益/退款安排并获批 TEST 真支付 → 真实手机扫网站/盒屏，验证会员和充值各自到账、取消/超时与恢复 → 再单独获批 PROD 开放。TEST 不是微信支付沙箱，没有自动退款功能，不承诺审批等待天数或把模拟支付等同正式收款。

手机 Native 必须扫描另一屏幕；同机长按、相册识别或直接支付不属于已实现范围。尚未进行 iOS/Android 微信真实扫码、商户账单、生产签名通知和结算终验。[官方说明](https://pay.weixin.qq.com/doc/v3/merchant/4012791878)

## 恢复边界

当前没有真实订单，恢复仍须先查在途单。云 helper 的 `rollback_compatible=false` 意味失败时停止候选并保留实际备份供受控恢复，不能写成自动恢复成功。不要回滚已到账账务或删除 additive 列；一旦有真实单，旧版本不具备通知/查单能力，必须保留正确验签及履约路径。设备另由 canonical app 事务统一备份/迁移/回滚及恢复模式，不能只回退源码忽略数据库或语言包。
