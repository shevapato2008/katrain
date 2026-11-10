# 微信 Native 会员与充值实施计划

> **2026-11-10开放状态：** 后续用户明确确认开闸，TEST→PROD现已enabled/live，保留11语；RK guard配置已启动。软件和实际未完成的手机扫码/到账/消费边界见[开放回执](../../operations/wechat-native-activation-release-2026-11-10.md)。本初版要求的默认关闭不撤销后续明确授权。

> **2026-11-09配置完成：** 用户在代码三端发布后准备好本机证书、API v3密钥和微信公钥，平台截图显示公钥启用，并明确授权TEST和PROD配置；现两站配置及独立实际验收已通过。仍保持会员paused/支付disabled，没有调用真实商户HTTP API、扣款或开放收款。具体增量、实际新Web和余项见[后续回执](../../operations/wechat-native-config-release-2026-11-09.md)，下文初始“禁止部署/配置待授权”为当时历史，不撤销后续用户授权。

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** 复用现有订单、权益与账本，实现网站 Galaxy、云 Kiosk 与实体盒代理的微信 Native 支付；本轮只做实现、本地验证与上线方案，真实收款默认关闭。

**Architecture:** 独立、无数据库依赖的微信 API v3 客户端负责签名、验签、解密与网络调用。订单服务在事务外执行网络操作，在用户→订单锁序内验证冻结绑定并原子发放。双端复用二维码内容与状态逻辑，保留现有外观、身份隔离和 11 语目录。

**Tech Stack:** FastAPI / SQLAlchemy / PostgreSQL，httpx / cryptography，React / MUI / Kiosk CSS，现有 qrcode / gettext / Vitest / Playwright。

## 授权与实时基线

- 读取了 `docs/operations/membership-i18n-release-2026-11-04.md`。本工作树已快进到实际已发布 `49b7cf79c052591bcc5532bea4dbee36e521bf87`，不新建 worktree，不重做旧会员设计。
- 两云 paused / disabled / billing enforced=true，11 语各 328 会员键；当前网站会员入口 `/membership`，Kiosk `/kiosk/membership`。拟议通知地址尚 404。
- 实体 RK 可达，1024×600，8081、Box SSO、云 modelstella.com。实体已有后续升级；9 语 PO 有会员键而 MO 缺失，需在获批盒端发布时重新编译全部 11 语。
- 用户提供非秘密标识：AppID `wxb83dd544397ac964`，商户号 `1003105536`，商户简称“智星盒智能设备”。仅写示例/运维资料，不自行改服务器配置。
- 禁止本轮部署、修改生产配置、启用收款、真实下单/关单/扣款或提交平台设置；必须先展示具体方案并取得用户确认。仅隔离本地数据和模拟传输用于自动化。

## 产品与安全契约

1. 新订单真实 provider 使用 `wechat`，payments mode 使用 `live`；保留 mock 严格 TEST 隔离。兼容类型原有 live 占位，但不新增其他真实渠道。
2. 点击“微信支付”先创建服务端 SKU 快照订单，再请求 Native，展示原样 code_url 本地生成的黑白二维码。订单号不超过 32 ASCII 字符，旧订单不重写。新单时限 15 分钟，Native 请求显式 time_expire=本地 expires_at。完整 Native 下单参数随单冻结，同参数同单号恢复，不重新计算时间或描述。
3. 不使用 AppSecret/openid。配置 AppID/商户号、商户证书序列号、私钥文件、32 字节 API v3 密钥文件、微信支付公钥 ID/公钥文件及 HTTPS notify URL。固定官方 API origin，TLS 验证、限时、无重定向；公钥固定信任，明确发送 Wechatpay-Serial 选择已配公钥，未知 ID 拒绝，轮换需受控配置。秘密不进 Git、日志、聊天或前端。
4. 请求 RSA-SHA256；所有 2xx 响应包括 204 空正文均按原始字节验签；不能把未验签响应当付款事实。非 2xx 不假定一定有签名；有签名则验证，无签名只作为不可置信诊断/暂时失败，不能据此判 SUCCESS/CLOSED。通知按原始正文验签，响应与通知均校验 ±5 分钟时间窗口，合法重复通知幂等返回 204，再 AES-256-GCM 解密，校验事件、资源类型、商户/AppID、订单、NATIVE、整数 total/CNY、交易号与成功时间。拒绝测试签名探测，安全错误不泄露正文/密钥。
5. 冻结微信商户/AppID/支付元数据，不随运行配置或价格变化。新加 nullable `payment_details` JSON 列和 `payment_next_check_at` 时间列，历史数据保持原样。账务始终使用本地金额和 SKU，绝不信任前端金额。
6. 创建超时保持 pending/确认中，复用同一幂等键和商户单号恢复，不直接判失败后创建第二单。取消请求持久化 cancel_requested，取消/过期后严禁再次 create；旧 create 晚完成仍须查单/关单，404/ORDER_NOT_EXIST 绝不证明 CLOSED。创建中/关单中不确定均保留可重试确认状态。每用户最多一个未确认真实订单；同 SKU 可恢复、不同 SKU 引导先处理旧单，防止新幂等键绕过未知结果。浏览器网络错误允许使用原尝试安全重试，并可从订单记录恢复。
7. 成功事实经同一原子发放服务处理：用户→订单锁，唯一交易号/订单权益/账本 ref，会员或充值与订单终态同提交；重复通知/查单不重复到账。迟到成功不能被失败、取消、过期降级；不因本地超时丢弃真实已付事实。
8. 关闭弹窗仅隐藏。独立“取消订单”走查单/关单；付款抢先成功则到账；结果未知继续确认。到时隐藏 QR、提示确认，服务端查单并关单确认后才终结。时间截止不是微信已关单的证明。
9. 网站/双端轮询本地订单；服务端每单节流微信查单，后台使用独立短事务/每笔失败隔离，网络不占用户锁。新增 payment_next_check_at 可索引时间字段，due 优先/更新后轮转的有界公平扫描，避免前 100 笔未知订单永久饿死后续单。通知缺失可查单补偿，关闭新收款后仍处理已存在真实订单的查单/通知。不得让旧同事务扫描循环把外部网络放进锁内。
10. 盒端仅按云身份代理创建/查单/取消；无本地钱包发放、无离线付款队列、无私钥落盒；退出/切换身份丢弃迟到响应。
11. Native 只支持手机微信“扫一扫”扫描另一屏幕，不承诺长按/相册/同手机直接付款；手机网站给出跨屏指引。H5/JSAPI/小程序界面不在本轮。
12. 所有新文案 11 语完整，切语言不重下单。金额 CNY，数字显示与原始值分离，二维码不使用外部生成服务。

## Chunk 1: 协议与实施审核

### Task 1: 官方文档、方案审核与局部视觉

Files: 本计划；`output/wechat-native/official-contract.md`；`docs/superpowers/reviews/2026-11-08-wechat-native-plan-astra.md`。

- [x] 读取项目、发布回执、代码，核实云端/实体/配置 presence，保留 11 语。
- [x] 官方 Native 创建/查询/关闭/通知与安全文档核实，记录直接链接。
- [x] 独立 Astra Max 计划审核两轮，修复阻塞问题，最终 Approved。
- [x] 使用 ui-ux-pro-max 在既有结账弹窗中设计二维码/确认中/终态；1024×600 Kiosk、网站桌面和 375px 手机预览，保持现有设计系统。

## Chunk 2: 共享支付基础

### Task 2: 无状态 API v3 客户端（独立任务）

Files: create `katrain/web/core/wechat_native.py`, `tests/web_ui/test_wechat_native.py`; modify `katrain/web/core/config.py`, dependency declaration if required。

- [x] 先写 MockTransport/临时 RSA/AES 密钥测试，证明错误签名/序列号/重放/密文失败拒绝。
- [x] 文件配置校验与 readiness，默认无配置不发任何网络请求。对外错误只稳定代码。
- [x] 实现 Native create/query/close 与 webhook decode；查询必须精确编码，签名 canonical URL 与发送 URL 一致。
- [x] 测试包含 204 空正文、合法/非法响应、网络未知结果、参数检查，原始签名字节保留。
- [x] `python -m pytest tests/web_ui/test_wechat_native.py -q` 通过后自审。

### Task 3: 订单与真实渠道原子集成（Task 2 接口稳定后）

Files: `payments.py`, new `wechat_payments.py`, `models_db.py`, `migrations.py`, `billing_environment.py` as needed; `api/v1/endpoints/billing.py`, new `payment_wechat.py`, router registration; `server.py`; `remote_client.py`, `repository.py`。

- [x] 隔离 PostgreSQL 写先失败测试，涵盖会员与充值、并发重复通知/查询、金额/商户/AppID/交易号冲突和事务回滚。
- [x] additive payment_details migration；新 provider、冻结绑定、32 字符以内单号、创建双阶段；外部请求不在账务锁/DB事务内。
- [x] 保留 mock require_mock_database；抽取共享发放，不使 mock 可写生产。成功通知在 disabled/paused 时可处理既有单。
- [x] webhook 原始正文限长、先验签解密再查本地订单，成功提交后 204，失败非 2xx；无登录、只在云有效，no-store，不信任客户端。
- [x] 按订单节流查询与关单竞态；结果未知保留 pending，成功不可降级，后台单笔隔离。公开状态至少 pending/paid/expired/failed/cancelled/refunded。
- [x] owner-only cancel API 与设备云身份代理；列表避免同步批量网络查单。
- [x] 测试 paused/disabled、新单拒绝、既有到账、迟到通知、取消与成功竞态、回调重复、超时恢复与后台单笔失败；复跑原有 mock 边界和盒端代理测试。

## Chunk 3: 双端、国际化与验证

### Task 4: 双端二维码和订单恢复（可与 Task 2 并行）

Files: new `features/membership/WechatNativePayment.tsx` (+ CSS/test); `types.ts`, `api/membershipApi.ts`; Galaxy MembershipPage/checkout hook；Kiosk MembershipPage/order hook；聚焦现有测试。

- [x] 先组件/Hook 测试 pending QR→paid/failed/expired/cancelled、查询失败、身份切换和同键重试。
- [x] live capability 为服务端权威，按钮“微信支付”；mock 提示继续明确区分。用现有 qrcode 生成原样 code_url，验证协议，不使用外链或 raw HTML。
- [x] 真实倒计时只管显示，零点不自行宣告账务终态。取消与返回分别表意；支付成功刷新用量/钱包。
- [x] 焦点、可读状态、触控与 1024×600 可滚动布局；375px 显示另一屏幕扫码指引。
- [x] 保留现有语义键，提供新键清单交翻译；切换语言不改订单、幂等键或轮询身份。

### Task 5: 11 语与完整本地旅程

Files: `scripts/wechat_native_translations.json` (或现有 membership JSON), `scripts/batch_translate_galaxy.py`, 11 PO/MO；`tests/test_membership_i18n.py`, focused Playwright spec。

- [x] 新键精确覆盖 11 语，placeholder parity；重新编译所有 11 MO，既有 328 键不得丢失。避免 i18n.py 既有缺键造成无关目录归一化。
- [x] 后端密码学→模拟微信传输→真实隔离 DB→HTTP→前端完整会员/充值旅程；模拟仅测试层，无生产假数据或假收款按钮。
- [x] 网站/Galaxy（同一应用不同入口）与 Kiosk 分别记录流程。真实盒只读现状，不安装候选代码；本地 1024×600 验证不是盒端实机支付通过。
- [x] 运行普通前端构建、严格 Kiosk 构建、聚焦前后端/国际化测试；检查真实二维码解码原文与长文布局。
- [x] 独立 Astra Max 代码/安全/翻译/视觉审核，修复到通过；检查秘密与非预期改动。

## Chunk 4: 可审核上线方案（本轮交付终点）

### Task 6: 文档、缺项与待确认发布步骤

Files: `docs/operations/wechat-native-rollout-2026-11-08.md`；相关操作指引链接。

- [x] 记录最终提交、测试/未测试、截图、各端旅程、默认关闭证据和回滚限制。
- [x] 提供配置示例：AppID/商户号；容器 `/run/secrets/wechat-pay/` 文件只读挂载与主机私有 0700/0600；微信支付公钥 ID、商户证书序列号和 API v3 密钥/私钥需用户安全填写，不要在聊天传秘密。
- [x] callback 计划 `https://modelstella.com/api/v1/payments/wechat/notify`，HTTPS/反向代理原始请求头正文/无登录/无重定向、持久 DB、时钟、出网核实清单；平台关联、Native 产品权限及商户通知已切微信支付公钥模式须上线前确认；迁移中旧证书回调不会被未知序列号绕过，应先完成平台切换或另行配置受信证书。
- [x] 按现有四步集成：同步 develop/功能分支推送→develop→父 vendor→先 TEST 后 PROD；本轮不执行发布，不改生产。先关闭新收款发布代码、验证配置/通知，再单独明确授权开启 live 与 membership enabled。
- [x] 单独列真实小额充值/会员、手机微信扫桌面/盒屏、断网恢复/通知重试/重复到账检查及退款恢复方案；每项在用户确认具体方案后执行。不能把本地模拟当正式收款。

## 官方依据

- Native 产品介绍：https://pay.wechatpay.cn/doc/v3/merchant/4012791874
- 其余 Native/API v3 安全直接文档见 `output/wechat-native/official-contract.md`，完成研究后复制必要链接至上线说明。

## 本轮收尾

源码候选 `4af8cb3ffd5599f22b6994b9306a0bd98e610081` 已本地提交，Astra Max最终审核Approved。暂停后用户恢复，仅补文档和聚焦核验（80 passed），源码不变。完整结果213 Python / 80前端 / 6浏览器、普通与严格构建通过。此计划到“可审核上线方案”已完成；四步发布、生产配置、真实收款及实体升级仍明确待用户授权，没有执行。独占本地测试PG保持停止。

## 用户随后授权的代码发布

上述收尾为用户要求部署前的历史记录。用户随后明确“微信支付需要部署啊”，授权四步集成及代码部署，真实收款仍保持关闭。

- 已发布功能分支 `47c56913a`，合并 develop 为 `4235a58238e805530cb07ef0eb8041ba93df586f`；组合聚焦检查96项Python及80项前端通过。
- 父仓 main `fd7bc6bc922d43cf4da51e72f6d1cde511addf1c` 保留已在设备运行的前端历史，并将 vendor 指向上述 develop；RK发布链由五语扩为十一语，经独立审核及106项发布测试验证。
- 按 TEST→新PROD→协调后的实体窗口执行；实际版本、配置保留、备份及验收/未验收边界见[2026-11-09回执](../../operations/wechat-native-release-2026-11-09.md)。未准备的秘密和真实微信联调仍需后续确认。

## 后续凭据配置阶段（2026-11-09）

- [x] 用户已准备证书/API v3密钥/微信公钥，完成本机配对、格式、应用readiness及非秘密公钥ID核对；截图显示公钥已启用。
- [x] 用户明确授权TEST、PROD配置；有界配置操作器通过独立Astra规格和安全审核，保持同镜像、原用户和完整配置，仅Env8+只读bind+操作标签增量。
- [x] TEST先配置、独立实际验收通过，再配置PROD并验收通过；均paused/disabled，11语和账务/其他服务保留，真实商户HTTP与扣款为0。完整回执见[配置部署与计划复核](../../operations/wechat-native-config-release-2026-11-09.md)。
- [ ] 真实微信接口/手机跨屏扫码/会员及充值到账与消费联调：确定账户、金额上限、权益保留或退款安排，单独获批后执行。
- [ ] 正式开放会员和真实收款，以及实体支付终验：分别确认，不随凭据配置自动开启。
