# 微信 Native 会员与充值上线草稿 — 2026-11-08

**状态：实现与本地验证已完成，待授权上线；不是发布回执。** 已完成官方文档和运行状态核查、Native 实现、隔离 PostgreSQL/密码学/HTTP 测试及双端浏览器预览。本轮没有部署、重启远程服务、写生产配置、创建生产 secret、修改商户平台或调用真实商户 API，真实收款保持关闭。独立审核结论见[代码及视觉审核](../superpowers/reviews/2026-11-08-wechat-native-code-astra.md)。

本稿对应[实施计划](../superpowers/plans/2026-11-08-wechat-native.md)。只读原始记录在本地忽略目录 `output/wechat-native/runtime-audit-2026-11-08.md`，官方契约摘要在 `output/wechat-native/official-contract.md`；下文已保留发布决策所需的事实及官方直接链接，不依赖这两个文件随 Git 交付。

**本地源码候选：`4af8cb3ffd5599f22b6994b9306a0bd98e610081`**，分支 `feature/membership-recharge`。2026-11-08 约21:47用户恢复任务后，核实源码未晚于最终验证记录；仅复跑协议、国际化与编译聚焦检查，**80 passed**，没有重启隔离PG或重复整套回归。随后仅收尾文档；未推送、未合入develop、未更新父仓或发布。

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

两云公开 `/api/translations` 的 en/cn/tw/jp/ko/de/es/fr/ru/tr/ua 均返回 200，每种保留 328 个现有会员键。Web 及 smartbox-platform 的实际环境未发现微信支付配置键；Web 挂载未发现微信私钥/公钥专用目录。运行版本 Settings 仅支持 `disabled/mock`；候选代码已新增 `live` 和下表配置，但尚未在服务器应用。

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

下表配置已在候选代码实现，**不是服务器已应用的设置**。默认仍为 `PAYMENTS_MODE=disabled`；获批前不改为 `live`。发布代码与开放真实收款分别验收。现有 `MEMBERSHIP_MODE=paused` 等收费设置也不得在部署时顺带放开。仓库入口为 [.env.example](../../.env.example)，可选 Web 专用只读挂载见 [docker-compose.wechat-pay.yml](../../docker-compose.wechat-pay.yml)；不要把示例整份覆盖现有生产 `.env`。

| 配置项 | 拟议值/安全来源 |
| --- | --- |
| `PAYMENTS_MODE` | 默认 `disabled`；`live` 已实现，开启仍待授权 |
| `WECHAT_PAY_APP_ID` | `wxb83dd544397ac964`，需核对关联证据 |
| `WECHAT_PAY_MCH_ID` | `1003105536` |
| `WECHAT_PAY_MERCHANT_SERIAL` | 待安全提供；商户 API 证书序列号 |
| `WECHAT_PAY_PRIVATE_KEY_PATH` | `/run/secrets/wechat-pay/apiclient_key.pem` |
| `WECHAT_PAY_API_V3_KEY_PATH` | `/run/secrets/wechat-pay/api_v3_key`，恰好 32 字节，不含结尾换行 |
| `WECHAT_PAY_PUBLIC_KEY_ID` | 待安全提供实际 `PUB_KEY_ID_...`，不猜测 |
| `WECHAT_PAY_PUBLIC_KEY_PATH` | `/run/secrets/wechat-pay/wechatpay_public_key.pem` |
| `WECHAT_PAY_NOTIFY_URL` | PROD 候选 `https://modelstella.com/api/v1/payments/wechat/notify`；运行中路由在19:55核查时404，候选已实现，待部署及确认 |

容器 secret 目录约定为 `/run/secrets/wechat-pay`，只读挂载，只允许 Web 服务所需用户读取；不挂入前端、Cron、GPU 或实体盒。主机目录 `/etc/katrain/secrets/wechat-pay/` **仅为待确认示例**，不代表既有路径，本轮不得创建或写入。确认后按部署用户/容器 UID 设置目录 0700、秘密文件 0600及只读挂载，实际属主和容器可读性须在不输出内容的条件下验证。

TEST 候选通知地址为 `https://go.sailorvoyage.top/api/v1/payments/wechat/notify`，与 PROD 分开配置及验收。通知必须公网 HTTPS、完整路径、无 query、无登录校验、无跳转，反向代理保留原始正文和 `Wechatpay-*` 头。具体商户是否可用于 TEST、回调路由、出网和时钟同步均待核实；TEST 的模拟模式严格禁止指向 PROD 数据库。此处没有执行平台配置或写 secret 的命令。

Native 的 `notify_url` 在每张订单的下单请求里传入并冻结，不虚构需要填写的全局“Native 回调设置”页面。平台还需确认 Native 产品权限、AppID 关联和微信支付公钥模式迁移已完成；候选客户端只信任实际配置的公钥 ID，旧平台证书回调会被拒绝，不能在迁移未完成时直接开启收款。`readiness` 仅证明本地文件和格式可用，不能代替平台权限或配对证书的真实联调。

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

桌面和实体盒可供手机扫描。本次没有生成真实商户付款二维码、没有改变实体当前页面，也未识别到可自动操作的手机微信设备。实际 iOS/Android 扫码、账单商户简称、返回后的会员/API 充值到账和网络恢复须在用户批准真实联调后验收；本地模拟、1024×600 浏览器和二维码解码只能证明各自覆盖的范围。

## 实现与本地验证记录

| 交付项 | 当前状态/后续记录 |
| --- | --- |
| Native 客户端及配置校验 | 完成；临时 RSA/AES、MockTransport 验证请求、响应含204、通知、公钥选择、±300秒、无效签名/密文拒绝、慢速流预算及三种官方 QR 链接原文 |
| 订单冻结、查单/关单及原子到账 | 完成；独占 loopback PG16、独立 TEST marker、每例随机 schema。会员/充值、并发重复、跨单交易号、回滚、迟到成功、同秒时间精度、冻结配置恢复、网络跨到期和 80 秒创建余量均有覆盖 |
| 网站/Galaxy、Kiosk、盒端代理 | 本地 HTTP/浏览器及代理身份边界通过；真实客户端→模拟微信传输→实际隔离 PG→验签解密回调→原子发放贯通。实体新功能未安装，未进行真实微信付款 |
| 11 语与构建 | 原328键未改，新增17键×11语=187译文，每语345会员键。实际11套MO含es核对通过；普通和严格Kiosk构建通过；Docker改为无归一化编译全部11语 |
| 视觉与主要交互 | 1440px桌面、375px中英文手机、1024×600中/德Kiosk真实浏览器预览；QR截图独立解码等于原始code_url；下单前跨屏说明、长文、关闭/取消和44px操作已验证 |
| 候选版本与发布产物 | 本地源码候选 `4af8cb3ffd5599f22b6994b9306a0bd98e610081`；未推功能分支、未合develop、未更新父仓vendor、未构建或部署候选服务器镜像。后续从获批的精确Git提交重新构建，不复用工作区静态包 |
| TEST/PROD/实体上线 | 未执行；待用户审核并授权具体方案 |
| 真实支付/通知/退款 | 未执行；无真实付款成功或退款成功的证据 |

最终组合验证：Python **213 passed**（10条既有 `auth.datetime.utcnow` 弃用提醒）、前端 **80 passed / 11 files**、Playwright **6 passed**。普通构建通过；`build:smartbox-kiosk-2d` 验证没有 Galaxy/三维模块或旧 localStorage token 读写。旧 `i18n.py` 仍因既有全局缺键 exit2；已撤其无关改写，使用 `compile_gettext_catalogs.py` 实际编译11语。本轮没有修复或冒称全项目历史 i18n 检查通过。

证据保留在本地 `output/wechat-native/{python-final.log,ui-final.log,build-normal.log,build-kiosk-strict.log,i18n-catalog-verification.json,qr-decode.txt}`；[预览截图](../../output/playwright/wechat-native-20261108/)均是隔离订单，不是正式收款。未执行完整 Docker 镜像构建、真实微信扫码、生产回调、商户结算或自动退款验收。

### 各端完整旅程与验收边界

- **网站/Galaxy：** 登录→选择会员或API充值→确认商品与人民币金额→“微信支付”→本地二维码→手机微信扫一扫→服务端通知或查单确认→原子发放→页面自动刷新。浏览器验证了充值入账、关闭后从历史恢复；组件/HTTP验证会员、账号切换、失败和到期。关闭新收款后仍能查看历史与在途订单。
- **云 Kiosk：** 选择会员/充值→确认→微信支付→1024×600二维码及状态区→付款后回执、用量/余额刷新。浏览器验证充值取消及会员付款后真实用量快照变为Plus；取消与返回分开，长文不遮挡操作。
- **实体盒：** 本地Box SSO身份→绑定云用户的订单代理→云端同一支付/账务→本地轮询回执。代码及代理测试通过；仅只读确认现有设备1024×600/8081可达，未升级或切换当前设备页面。需获批设备发布后核验身份、11语及实际屏幕二维码，再以手机真实扫码完成终验。
- **手机：** 375px中英预览已验证下单前跨屏提示。未识别到可自动操作的实际iOS/Android微信设备；不把浏览器模拟尺寸当手机微信付款通过。同机直接支付不属于本轮Native范围。

付款结果不明时保持确认中，不以404、倒计时、关弹窗或未验签错误判付款失败。每用户至多一个未确认真实订单，同SKU恢复并永久绑定幂等键；取消/到期后不再创建，不足80秒不再重下，以避免微信最短1分钟钳制延长截止。签名SUCCESS仍优先到账。Native文档中仅付款码返回的异常状态不当作Native终态，记录供审查；REFUND不在本轮自动回扣权益，需商户退款与账务人工协调。

## 用户审批后的发布顺序

本轮授权边界只覆盖实现、本地验证与可审核方案；以下均是**待用户确认后**的操作，当前不得执行。

1. 获取最新 `develop` 并合入功能分支，保留无关改动，解决冲突，验证组合结果，提交并推功能分支。先补齐上节实际实现/测试/候选产物，再提交具体发布方案供用户批准。
2. 获批后将功能分支合入并推送 `develop`。
3. 更新 `smartbox-software/vendor/katrain` 到已发布 develop 提交，提交并推送父仓 gitlink，保留父仓其他工作区改动。
4. 按已批准方案先 TEST `home-ubuntu`，再新 PROD `ucloud-v100`；先保持 `PAYMENTS_MODE=disabled` 发布/验证代码与配置，不自动开启会员或真实新收款。分别检查实际软件 SHA、health、代表性的 `/membership` 与 `/kiosk/membership`、语言和通知路由。TEST 未通过不进入 PROD；旧 PROD/未知设备不在范围内。

四步集成不等同于真实收款启用。用户需另行确认真实小额金额、订单类型（会员/API 充值）、商户/通知配置、操作主体及退款处理方案，才可在批准环境开启联调/收款；回执分别记录“软件已部署”和“真实支付已验收”。不得把 TEST 名称当成微信支付沙箱，也不得把 mock 到账当作真实微信凭证。

建议分段确认：①精确候选的四步集成及先TEST后PROD代码发布，保持paused/disabled，原有服务完整配置、挂载、网络和资源保持，仅Web/语言包和两列及索引的可加迁移；迁移前留存订单/账本/会员备份与实际配置，核对表规模和锁等待；②用户安全放置所需文件并批准只给Web注入标识/只读挂载，验证HTTPS通知路径、时钟、出网和公钥模式，仍不下单；③另行批准真实TEST联调，使用用户指定测试账户，会员Plus39元与API充值10元各一笔，**最多49元真实支付**，另各一张未付款取消/超时订单，禁止擅改SKU价格或增加扣款次数；④TEST回执及账务通过后，单独批准PROD开放 `MEMBERSHIP_MODE=enabled / PAYMENTS_MODE=live` 及实际盒升级。若用户要更小金额或其他组合，先改批准方案，不临时更改生产价格。

本轮没有真实退款接口；上述49元方案默认保留对应测试权益，不承诺自动退款。若要退款，需用户先确认商户平台退款及与之匹配的账务/会员处理方案，再执行，不能只退钱不处理权益或反向操作。只读/无扣款验证与真实支付步骤分别记录。

实体盒升级另需用户明确授权具体候选和窗口。升级前核对实际进程、当前模式/页面、持久数据和可恢复备份；本次只规划有界 KaTrain/静态包及 11 套 MO 更新，不顺带全量覆盖整机或改本地钱包。打包前从精确源码运行 `python scripts/compile_gettext_catalogs.py`，将11套真实产物随盒包安装，逐语检查345会员键，不能只复制Git跟踪的中英文MO。升级后在实际1024×600设备检查 `/kiosk/membership`、云身份绑定、11语和真实跨屏扫码（后者仍以真实支付授权为前提），完成后恢复约定模式/页面并报告实际版本。不能用磁盘stamp或本地浏览器代替设备进程验收。

真实联调最小验收范围：会员与 API 充值各一笔获批金额；扫码另一屏幕、成功通知与查单一致；重复通知/查询只到账一次；中断网络后能恢复原订单；取消/超时与已付款竞态不丢权益、不重复付款；按已批准方案完成退款及对应权益处理。每项保留非秘密订单关联、金额、时间、最终状态及环境，真实用户身份/支付凭据不进公开回执。

停止新收款时先关闭新订单入口；既有真实订单的通知、查单与对账继续受理。出现资金一致性或身份串线问题立即暂停新收款并保留证据。每端发布前私有保存当时实际容器Config/HostConfig、网络、挂载与不可变镜像，正常停止并保留旧Web备份。新Web健康或代表页面失败时，仅停止候选并恢复该实际备份及完整配置，不重启GPU/Cron/数据库，不回滚已到账账务数据、不删除新增nullable列。

回退到没有微信通知/订单能力的旧版本前，必须先确认没有在途真实单，或保留能验签、查单及履约的服务路径，不能仅替换镜像便宣称资金回滚完成。本文两端镜像是19:55核查基线，部署前必须重新捕获；确切新旧镜像、备份容器和受控替换命令随获批的精确产物填写，不能套用历史容器ID。

设备发布协调：会话 `01a1b6fc-f640-7de3-8ad2-7571dd683858` 正申请四棋类漏译修复的RK3562窗口（其报告源码 `a0d0cb1a`、Go `fda461efc`）。本会话已明确未占用、不会现在部署，后续设备发布须等待其完成通知并重新同步最新main/vendor和实机基线；上述19:55设备信息不作为未来覆盖依据。
