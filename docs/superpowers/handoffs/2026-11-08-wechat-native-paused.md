# 微信 Native 安全暂停交接

**恢复记录：** 2026-11-08约21:47用户明确“继续”，已恢复并完成本地收尾；下文保留暂停瞬间快照。源码已提交为 `4af8cb3ffd5599f22b6994b9306a0bd98e610081`，恢复聚焦检查80项通过，最终审核仍Approved。没有推送、部署或真实支付授权。当前仅待用户审核[上线方案](../../operations/wechat-native-rollout-2026-11-08.md)并补齐安全配置；本地PG继续停止。后续如有发布授权，先同步另一个会话正在申请的RK3562发布窗口和最新main/设备版本。

2026-11-08：用户明确“安全暂停一下，我准备回家了”。已停止开发、提交、发布与自动继续；仅保存本交接并关闭本轮独占的本地测试 PostgreSQL。所有本轮 agent 均已完成，无运行中的子任务。不因回家或等待自动恢复，需用户明确继续。

## 已完成但尚未提交的实现

- 工作区 `/Users/fan/Repositories/katrain-membership-recharge`，分支 `feature/membership-recharge`。
- 开始时干净；已从 origin/develop 快进到实际已发布 `49b7cf79c052591bcc5532bea4dbee36e521bf87`。本地 HEAD 为计划提交 `899811aa5`；没有推送。本轮实现、最终审核及收尾文档仍为未提交/未跟踪文件，全部保留，不 reset/clean。
- Native 客户端、文件配置、冻结请求、原子会员/充值到账、查单/关单/通知、盒端云身份代理和双端二维码均实现。默认 disabled，未改价格、额度或旧 mock 的独立 TEST 隔离。
- 新17键×11语，原328键不变，每语345会员键。实际全部MO含es编译验证；新 `compile_gettext_catalogs.py` 及 Docker入口避免跳过es。9语MO在Git忽略中，未来精确源码打包必须重新编译，不能仅复制Git跟踪的中英文MO。
- 计划经独立 Astra Max 两轮批准；最终代码、安全、翻译、视觉审核 Approved，无剩余阻塞。[最终审核](../reviews/2026-11-08-wechat-native-code-astra.md)。
- 主代理最终验证：Python **213 passed**（10条既有auth时间弃用提醒）、前端 **80 passed/11 files**、Playwright **6 passed**；普通构建、严格Box SSO/Kiosk2D构建通过。工作树最后的80秒余量和paused历史恢复修改均已覆盖。新代码此后未改动。
- 实际浏览器QR由OpenCV解码，原文与测试code_url完全一致。预览位于 `output/playwright/wechat-native-20261108/`，含1440桌面、375中英文手机、1024×600中德Kiosk；都是隔离订单。

## 安全边界和当前实况

- 没有真实微信 API 下单/查单/关单、扣款、生产数据库写、生产配置写、商户平台更改、远程部署或实体升级。
- 19:55只读核查：两云实际49b7cf79c、paused/disabled、健康，11语各328键。网站/Galaxy入口现在是 `/membership`，旧 `/galaxy/membership` 404；Kiosk `/kiosk/membership`。拟议通知路径尚404，HTTPS本身有效。
- 实体RK已在之前更新，1024×600、8081、BoxSSO、云modelstella.com；英文/简中MO含会员键，其余9语仅PO含会员键，MO尚缺失。这个已存在的设备发布问题本轮没有上线修复。实际进程与部署stamp SHA不同，详见运维方案。
- 用户已提供非秘密 AppID `wxb83dd544397ac964`、商户号 `1003105536`、简称“智星盒智能设备”；仅文档记录，没有自行写服务器。仍缺商户证书序列号、配对私钥文件、32字节APIv3文件、微信公钥ID及公钥文件，需用户安全填写；绝不在聊天/日志/Git收秘密。
- 只支持Native跨屏微信扫一扫。实际手机微信、真实通知、付款/结算/退款及实体候选均未验收。不支持相册/长按或同手机直接支付，不开发小程序界面。

## 本地环境已安全关闭

- 独占容器 `wechat-native-pg-test-20261108`（postgres:16-alpine，loopback55439，DB membership_validation_wechat_20261108）已正常停止，容器保留供续做；55439无监听。
- 未停止其他数据库、Docker Desktop、线上服务或设备服务。
- 私有测试env仍保留0700目录/0600文件，只含本地随机测试凭据；路径元数据 `output/wechat-native/pg-path.json`。不要输出文件内容。续做测试需先用户恢复任务、再启动此独占容器。
- 复现runner `python3 output/wechat-native/run-tests.py ...`，会安全加载专用loopback测试环境，不打印URL。每例随机schema已清理。日志在 `output/wechat-native/{python-final.log,ui-final.log,build-normal.log,build-kiosk-strict.log}`。
- Playwright自动管理的预览已结束；核查5196无监听。无本轮SSH隧道、商户会话或支付后台进程。

## 用户继续后剩余事项

1. 先确认用户是恢复开发收尾还是批准上线；不得将“继续”自动解释为生产/真实扣款授权。
2. 不重做已通过计划/整套回归。核对工作树无新增外部改动及最终审核，补齐计划最后复选框、运维方案候选提交信息和暂停恢复记录，做本地候选提交（尚未执行）。
3. [上线方案](../../operations/wechat-native-rollout-2026-11-08.md)已含具体配置位置、真实基线、各端旅程、测试证据、缺项、分段审批与四步发布。审核后只余提交编号/最终交付信息收尾；不需要继续开发其他功能。
4. 先向用户交付改动/测试/缺少配置及下一步，再等明确批准发布/配置：功能分支→develop→父vendor→TEST→新PROD，代码发布先保持paused/disabled。每一步保留真实服务完整配置；不得用裸Compose覆盖当前角色链。
5. 真实TEST支付不是微信沙箱；提案会员Plus39元+充值10元各一笔，上限49元，另未付款取消/超时检查，需单独明确用户确认。默认保留测试权益；本轮没有真实退款接口，不承诺自动退款。PROD开放、盒端升级和实际手机扫码也分别待授权。

注意：旧 `i18n.py` 全局缺键仍exit2，已撤无关归一化；不能报告全项目i18n历史检查通过。完整Docker镜像未构建，未来从获批精确Git提交构建，不复用脏工作区静态目录。
