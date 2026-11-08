# 微信 Native 会员与充值上线草稿 — 2026-11-08

**状态：供审核的运维草稿，不是发布回执。** 已完成官方文档核实及云端、实体盒只读基线核查；微信 Native 实现、自动化测试和本地旅程结果均待后续填写。本轮没有部署、重启、写生产配置、创建生产 secret、修改商户平台或调用真实商户 API，真实收款保持关闭。

本稿对应[实施计划](../superpowers/plans/2026-11-08-wechat-native.md)。只读原始记录在本地忽略目录 `output/wechat-native/runtime-audit-2026-11-08.md`，官方契约摘要在 `output/wechat-native/official-contract.md`；下文已保留发布决策所需的事实及官方直接链接，不依赖这两个文件随 Git 交付。

## 已知商户与待补资料

用户提供 AppID `wxb83dd544397ac964`、商户号 `1003105536`，商户简称“智星盒智能设备”，并说明 AppID 已关联商户号。这些标识不是秘密；本轮未登录微信商户平台独立确认 Native 产品权限、绑定和回调配置，不据此宣称已具备真实收款条件。

仍需安全提供并核对：商户 API 证书序列号及配对私钥、32 字节 APIv3 密钥、微信支付公钥及其实际 `PUB_KEY_ID`、secret 的真实主机路径/属主/读取权限、TEST 与 PROD 的通知地址和平台配置。不得使用官方示例标识，不把私钥或 APIv3 密钥发到聊天、Git、日志或前端。Native 不需要 AppSecret 或支付者 openid 来创建订单。

## 2026-11-08 实际运行基线

核查开始时间为北京时间 19:55。以下是运行中的容器和进程事实；不是候选微信功能的版本。2026-11-04 国际化回执的 `959800a467...` 以及较早的根路径发布回执不能代替本次实时版本核查。

| 项目 | TEST `home-ubuntu` | 新 PROD `ucloud-v100`（117.50.177.254） |
| --- | --- | --- |
| Web 容器 | `katrain-web` | `katrain-ucloud-katrain-web-1` |
| 实际 `KATRAIN_BUILD_SHA` | `49b7cf79c052591bcc5532bea4dbee36e521bf87` | `49b7cf79c052591bcc5532bea4dbee36e521bf87` |
| 不可变镜像 | `sha256:d318683dd50028839ff79aa7735a8abe8941e4fc17fdd9f1f174a858fa274346` | `sha256:6b4b244a0fd25f4f0b64d089a4e6552c261ef7b27313df7a03890732c21cfe28` |
| 实际 Settings 环境/角色 | `test / server` | `production / server` |
| 会员/支付 | `MEMBERSHIP_MODE=paused`、`PAYMENTS_MODE=disabled` | 同 TEST |
| 其他收费开关 | `BILLING_ENFORCED=true`、`FREE_WEEKLY_REPORTS=0`、`MEMBERSHIP_MAX_SALE_ENABLED=true` | 同 TEST |
| 健康 | HTTP 200 / status ok，restart 0；无 Docker health 字段 | HTTP 200 / status ok，Docker healthy，restart 0 |

两云公开 `/api/translations` 的 en/cn/tw/jp/ko/de/es/fr/ru/tr/ua 均返回 200，每种保留 328 个现有会员键。Web 及 smartbox-platform 的实际环境未发现微信支付配置键；Web 挂载未发现微信私钥/公钥专用目录。本地现有 Settings 仅支持 `disabled/mock`，尚无下表微信配置字段，不能把本稿中的配置约定当成已实现能力。

两云实际 OpenAPI 只有既有 `/api/v1/billing/orders` 和 `/api/v1/billing/orders/{order_id}` 等订单接口，没有微信 Native 通知/专用接口，也没有 TEST 模拟到账入口。拟议路径 `/api/v1/payments/wechat/notify` 当前在两云均为 404。公开 HTTPS 的证书链及主机名校验通过，只能证明当前域名 HTTPS 可达，不能证明支付回调已接通。

### 网站、Kiosk 与实体入口

网站就是 Galaxy，当前入口是根路径应用，会员页为 `/membership`，无需再区分“网站”和“Galaxy”两套支付实现。

| 场景 | 当前入口 | 接入与验收边界 |
| --- | --- | --- |
| TEST 网站/Galaxy | `https://go.sailorvoyage.top/membership` | 使用隔离 TEST 身份及数据库；获批后才联调真实商户 |
| PROD 网站/Galaxy | `https://modelstella.com/membership` | 当前 200 HTML；正式新收款保持 disabled |
| 云 Kiosk | 两域名下 `/kiosk/membership` | 同一云端订单、账务与通知权威 |
| 实体智星盒 | `http://127.0.0.1:8081/kiosk/membership` | 本地页面代理云端身份与订单，不在盒内放密钥或发放权益 |

当前 `/galaxy`、`/galaxy/`、`/galaxy/membership` 返回 404，不能复用[旧国际化回执](membership-i18n-release-2026-11-04.md)的前缀链接。根路径历史变更见[根路径发布回执](galaxy-root-routing-release-2026-11-08.md)，本次运行基线优先于历史回执。

实体 `rk3562-local`（hostname `gzpeite`）可达，`smartbox-katrain.service` active；屏幕为 1024×600，Chromium 当前页面是 `http://127.0.0.1:8081/kiosk/vision/setup`。本地 health 200，会员页面 200 HTML。实际进程 `KATRAIN_BUILD_SHA=4691484225b47fca7c6c7f8c8faa6edf6426a23d`；磁盘部署 stamp 为父仓 `e668d94f9d23531b0da81e95fa8accdb7be46468`、vendor `954a374bdd0cf5661a9e7e556af7f699928edfbe`。设备目录不是 Git checkout，stamp 与进程 build 来源不同，不能合并成一个“当前整机 SHA”。

盒端实际 Settings 为 `board / production`、Box SSO 开启、`REMOTE_API_URL=https://modelstella.com`、`MEMBERSHIP_MODE=legacy`、`PAYMENTS_MODE=disabled`、`BILLING_ENFORCED=false`、`FREE_WEEKLY_REPORTS=1`。这些本地默认值不代表云端授权或账务事实；付款确认及权益发放必须由云端完成。

**实体 9 语编译包仍缺会员键。** 盒端 11 套 PO 均有 328 个会员键，但真实 MO 和 `/api/translations` 仅 en/cn 含这些键，tw/jp/ko/de/es/fr/ru/tr/ua 为 0 个会员键，仍有旧全局翻译。说明源码翻译已送达、编译产物未补齐；下次获批盒端升级需重新编译并校验全部 11 套 MO，不能把云端 11 语已发布等同于实体已完整发布。

## 拟议配置约定

下表是待实现、待校验的配置契约，**不是服务器已应用的设置**。默认必须为 `PAYMENTS_MODE=disabled`；实现完成且获批前不改为 `live`。发布代码与开放真实收款分别验收。现有 `MEMBERSHIP_MODE=paused` 等收费设置也不得在部署时顺带放开。

| 配置项 | 拟议值/安全来源 |
| --- | --- |
| `PAYMENTS_MODE` | 默认 `disabled`；真实模式待实现、测试和授权 |
| `WECHAT_PAY_APP_ID` | `wxb83dd544397ac964`，需核对关联证据 |
| `WECHAT_PAY_MCH_ID` | `1003105536` |
| `WECHAT_PAY_MERCHANT_SERIAL` | 待安全提供；商户 API 证书序列号 |
| `WECHAT_PAY_PRIVATE_KEY_PATH` | `/run/secrets/wechat-pay/apiclient_key.pem` |
| `WECHAT_PAY_API_V3_KEY_PATH` | `/run/secrets/wechat-pay/api_v3_key`，内容为实际 32 字节密钥 |
| `WECHAT_PAY_PUBLIC_KEY_ID` | 待安全提供实际 `PUB_KEY_ID_...`，不猜测 |
| `WECHAT_PAY_PUBLIC_KEY_PATH` | `/run/secrets/wechat-pay/wechatpay_public_key.pem` |
| `WECHAT_PAY_NOTIFY_URL` | PROD 候选 `https://modelstella.com/api/v1/payments/wechat/notify`；路由当前 404，待实现及确认 |

容器 secret 目录约定为 `/run/secrets/wechat-pay`，只读挂载，只允许 Web 服务所需用户读取；不挂入前端、Cron、GPU 或实体盒。主机目录 `/etc/katrain/secrets/wechat-pay/` **仅为待确认示例**，不代表既有路径，本轮不得创建或写入。确认后按部署用户/容器 UID 设置目录 0700、秘密文件 0600及只读挂载，实际属主和容器可读性须在不输出内容的条件下验证。

TEST 候选通知地址为 `https://go.sailorvoyage.top/api/v1/payments/wechat/notify`，与 PROD 分开配置及验收。通知必须公网 HTTPS、完整路径、无 query、无登录校验、无跳转，反向代理保留原始正文和 `Wechatpay-*` 头。具体商户是否可用于 TEST、回调路由、出网和时钟同步均待核实；TEST 的模拟模式严格禁止指向 PROD 数据库。此处没有执行平台配置或写 secret 的命令。

## 已核实的官方接口与资金边界

来源限微信支付官方商户文档；`pay.wechatpay.cn` 页面本次跳转到同属官方的 `pay.weixin.qq.com`。

| 操作 | 官方 API v3 契约 | 直接文档 |
| --- | --- | --- |
| Native 下单 | `POST /v3/pay/transactions/native`，成功 200 返回 `code_url` | [下单](https://pay.weixin.qq.com/doc/v3/merchant/4012791877) |
| 商户单号查单 | `GET /v3/pay/transactions/out-trade-no/{out_trade_no}?mchid=...` | [查单](https://pay.weixin.qq.com/doc/v3/merchant/4012791880) |
| 微信交易号查单 | `GET /v3/pay/transactions/id/{transaction_id}?mchid=...` | [交易号查单](https://pay.weixin.qq.com/doc/v3/merchant/4013070354) |
| 关单 | `POST /v3/pay/transactions/out-trade-no/{out_trade_no}/close`，JSON `mchid`，成功 204 空正文 | [关单](https://pay.weixin.qq.com/doc/v3/merchant/4012791881) |
| 支付通知 | POST 到下单时 `notify_url`；成功事件 `TRANSACTION.SUCCESS` | [通知](https://pay.weixin.qq.com/doc/v3/merchant/4012791882) |

API 域名固定官方 `https://api.mch.weixin.qq.com`，保持 TLS 校验，不向客户端输入的地址发送商户凭据。订单金额由服务器冻结为整数分、币种 CNY；AppID 与商户号需绑定，不使用前端价格决定到账。

请求用商户 API 私钥做 RSA-SHA256 签名，签名串包含 method、实际 path/query、秒时间戳、nonce、原始 body，并以换行结束。Authorization 的 `serial_no` 是**商户证书序列号**；请求 `Wechatpay-Serial` 是**微信支付公钥 ID**，二者不能混用。公钥模式按配置的完整 ID 选择可信公钥；迁移期间回调可能使用平台证书或公钥，不能跳过未知 Serial 的验签。[签名总述](https://pay.weixin.qq.com/doc/v3/merchant/4012365342)、[请求正文签名](https://pay.weixin.qq.com/doc/v3/merchant/4012365336)、[查询参数签名](https://pay.weixin.qq.com/doc/v3/merchant/4012365337)、[公钥迁移规则](https://pay.weixin.qq.com/doc/v3/merchant/4012154180)。

成功应答和回调使用 `Wechatpay-Timestamp/Nonce/Signature/Serial` 验证原始正文；**关单 204 空正文同样需要验签**。时间偏差按官方建议限制为最多 5 分钟，拒绝重放/未来越界；以 HTTP 签名时间戳判断，不能拿业务发生时间代替。拒绝 `WECHATPAY/SIGNTEST/` 探测签名。[公钥验签](https://pay.weixin.qq.com/doc/v3/merchant/4013053249)、[平台证书验签及时间窗口](https://pay.weixin.qq.com/doc/v3/merchant/4013053420)。

官方通用文字要求验证应答，但当前 Native 示例仅在 2xx 分支验签，非 2xx 转 API 错误；没有核实到“所有错误/网关响应一定带验签头”的保证。实现需保留有界错误码、HTTP 状态及 Request-ID 供诊断，不能把未经验证的错误文字当作付款成功或 CLOSED 的证据；成功签名缺失/失败一律不接受，未知结果通过可信查单恢复。[下单示例](https://pay.weixin.qq.com/doc/v3/merchant/4012791877)、[HTTP 状态处理](https://pay.weixin.qq.com/doc/v3/merchant/4012081717)。

回调先验签，再按 `resource_type=encrypt-resource`、`original_type=transaction`、`algorithm=AEAD_AES_256_GCM` 解密；使用 APIv3 密钥、resource nonce、associated_data（可空）和 Base64 密文/GCM tag。成功发放还需比对本地订单的 mchid、appid、out_trade_no、NATIVE、SUCCESS、transaction_id、整数 total/CNY；`payer_total` 可能因优惠券低于 total，不能拿它代替订单总额。未知事件、金额冲突、解密失败不发放。[回调结构](https://pay.weixin.qq.com/doc/v3/merchant/4012791882)、[解密规则](https://pay.weixin.qq.com/doc/v3/merchant/4012071382)。

回调要求 5 秒内应答；持久接受/完成幂等处理后回 200/204，验签失败回 4xx/5xx。重复通知、前端查单、后台查单必须共用一次原子发放，订单与权益/账本同提交。禁用新收款后仍需处理已存在真实订单的合法通知与查单，不能让关闭开关造成已付款丢单。[回调规则](https://pay.weixin.qq.com/doc/v3/merchant/4012075420)、[回调与查单指引](https://pay.weixin.qq.com/doc/v3/merchant/4012075249)。

`code_url` 有效 2 小时，`time_expire` 只是最晚付款截止时间，**不等于已关单**。本地倒计时到零、取消界面或网络超时均不能证明付款失败。查单/关单与用户付款可能并发：结果不确定保持确认中，以可信成功事实原子到账；不得被旧查询结果或本地过期降级，不在旧订单结果不明时创建第二张可付款订单。SYSTEM_ERROR 按原参数重试，429 降频；不把旧 API v2 错误码列表套进当前 v3 关单。[Native 开发指引](https://pay.weixin.qq.com/doc/v3/merchant/4012791891)、[关单及错误表](https://pay.weixin.qq.com/doc/v3/merchant/4012791881)。

### 手机、另一屏幕与真实扫码

Native 需要手机微信“扫一扫”扫描另一屏幕上的二维码。官方明确不支持相册识别或长按识别；因此本轮手机网站需诚实提示跨屏支付，不承诺在同一手机保存截图、长按或点击 `code_url` 就能付款。H5/JSAPI/小程序支付属于另行接入范围。[Native 开发指引 §2.2](https://pay.weixin.qq.com/doc/v3/merchant/4012791891)、[调起支付](https://pay.weixin.qq.com/doc/v3/merchant/4012791878)。

桌面和实体盒可供手机扫描。本次没有生成付款二维码、没有改变实体当前页面，也未识别到可自动操作的手机微信设备。实际 iOS/Android 扫码、账单商户简称、返回后的会员/API 充值到账和网络恢复须在用户批准真实联调后验收；本地模拟、1024×600 浏览器和二维码解码只能证明各自覆盖的范围。

## 实现与验证记录：待后填

| 交付项 | 当前状态/后续记录 |
| --- | --- |
| Native 客户端及配置校验 | 未完成；待填实现提交、无效配置拒绝规则、请求/响应密码学测试 |
| 订单冻结、查单/关单及原子到账 | 未完成；待填 PostgreSQL 并发/重复/回滚、迟到成功和关闭新收款后的恢复验证 |
| 网站/Galaxy、Kiosk、盒端代理 | 未完成；待填真实本地 HTTP 旅程、身份切换、取消、超时恢复和二维码原文检查 |
| 11 语与构建 | 未完成；待填新增翻译、占位符校验、全部 MO、普通及严格 Kiosk 构建 |
| 视觉与主要交互 | 未完成；待填桌面、375px 手机、1024×600 Kiosk 代表性预览及审核结果 |
| 候选版本与发布产物 | 待填 feature/develop/父仓提交、可复现产物 hash 和回滚候选 |
| TEST/PROD/实体上线 | 未执行；待用户审核并授权具体方案 |
| 真实支付/通知/退款 | 未执行；无真实付款成功或退款成功的证据 |

本节空缺未填前，不得将本稿改称“接入完成”“测试通过”或“已经上线”。

## 用户审批后的发布顺序

本轮授权边界只覆盖实现、本地验证与可审核方案；以下均是**待用户确认后**的操作，当前不得执行。

1. 获取最新 `develop` 并合入功能分支，保留无关改动，解决冲突，验证组合结果，提交并推功能分支。先补齐上节实际实现/测试/候选产物，再提交具体发布方案供用户批准。
2. 获批后将功能分支合入并推送 `develop`。
3. 更新 `smartbox-software/vendor/katrain` 到已发布 develop 提交，提交并推送父仓 gitlink，保留父仓其他工作区改动。
4. 按已批准方案先 TEST `home-ubuntu`，再新 PROD `ucloud-v100`；先保持 `PAYMENTS_MODE=disabled` 发布/验证代码与配置，不自动开启会员或真实新收款。分别检查实际软件 SHA、health、代表性的 `/membership` 与 `/kiosk/membership`、语言和通知路由。TEST 未通过不进入 PROD；旧 PROD/未知设备不在范围内。

四步集成不等同于真实收款启用。用户需另行确认真实小额金额、订单类型（会员/API 充值）、商户/通知配置、操作主体及退款处理方案，才可在批准环境开启联调/收款；回执分别记录“软件已部署”和“真实支付已验收”。不得把 TEST 名称当成微信支付沙箱，也不得把 mock 到账当作真实微信凭证。

实体盒升级另需用户明确授权具体候选和窗口。升级前核对实际进程、当前模式/页面、持久数据和可恢复备份；本次只规划有界 KaTrain/静态包及 11 套 MO 更新，不顺带全量覆盖整机或改本地钱包。升级后在实际 1024×600 设备检查 `/kiosk/membership`、云身份绑定、11 语和真实跨屏扫码（后者仍以真实支付授权为前提），完成后恢复约定模式/页面并报告实际版本。不能用磁盘 stamp 或本地浏览器代替设备进程验收。

真实联调最小验收范围：会员与 API 充值各一笔获批金额；扫码另一屏幕、成功通知与查单一致；重复通知/查询只到账一次；中断网络后能恢复原订单；取消/超时与已付款竞态不丢权益、不重复付款；按已批准方案完成退款及对应权益处理。每项保留非秘密订单关联、金额、时间、最终状态及环境，真实用户身份/支付凭据不进公开回执。

停止新收款时先关闭新订单入口；既有真实订单的通知、查单与对账继续受理。出现资金一致性或身份串线问题立即暂停新收款并保留证据。回退到没有微信通知/订单能力的旧版本前，必须确认未终结真实订单的处理路径，不能仅替换镜像便宣称资金回滚完成。具体回滚命令、镜像和数据兼容检查待候选实现完成后填写，本稿不提供未经验证的生产操作命令。
