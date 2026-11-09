# 微信配置部署与会员计划复核 — 2026-11-09

> **2026-11-10后续已开放：** 本文记录当时的配置/代码/准备状态；用户随后已确认TEST与PROD真实收款开放，最终软件、RK扣量保护及实际验收边界以[开放回执](wechat-native-activation-release-2026-11-10.md)为准，不再将历史paused/disabled理解为当前配置。

**当前状态：TEST、PROD凭据配置及独立实际验收均完成；真实收款和新的私人分析授权仍暂停。** 本文件续接[代码发布回执](wechat-native-release-2026-11-09.md)。配置成功、真实微信支付成功和正式开放分别验收，不能相互替代。没有创建真实订单、调用商户HTTP API或扣款。

## 计划复核：规则不变，更新阶段和范围说明

权威业务规则依次为[简单最终设计](../superpowers/specs/2026-11-02-membership-simple-final-design.md)、[简单实施计划](../superpowers/plans/2026-11-02-membership-simple-implementation.md)，以及后续[Max开放修订](../superpowers/plans/2026-11-02-membership-max-and-clarity.md)。旧展示修订中不冲突的百分比、会员优先及报价上限仍有效；旧候选价格、日均展示、Max停售和“尚未开发”仅作历史。

不改价格39/99/199元、30天普通报告参考30/90/240盘、周最多约10/30/80盘，高级分析约四倍消耗。不增加每日限制、额度结转、混合扣费或新的钱包。

### 统一扣减已覆盖的范围

| 场景 | 已实现的边界 |
| --- | --- |
| 个人棋谱普通/高级复盘报告 | 服务端报价、完整报告预算预留、完整成功后结算；失败退原来源，不交付失败前缀 |
| 用户主动请求的私有局面分析 | 领地、支招共用一次授权结果，不分别扣两笔；新局面/深度按新授权处理 |
| Galaxy、云Kiosk与实体盒 | 盒端捕获云端身份并代理到同一云账务，不在盒内发会员或扣本地钱包 |
| 旧直接分析、state/WS结果出口 | 已封闭绕过授权的入口及结果泄露；不能因旧API存在便免费触发云GPU |
| 合法已有结果重看 | 已拥有结果仍可用时不重新消费；短分析24小时只是结果缓存保留，不是每日用量上限 |
| 正常AI对手落子、公共职业报告读取 | 保留既定非私人付费分析边界；不是四棋所有引擎计算一律收费 |
| ranked等禁止辅助的场景 | 保留原权限规则，不能用钱包回退绕过 |

这次只读复核的是已发布`4235a5823`实现及既有通过测试，没有重跑整套功能回归或改动计费代码。来源为`billing_operations.py:_source`、`reports.py`、`paid_analysis.py`、`test_membership_operations_pg.py`和`test_paid_analysis_guards.py`。

**会员优先的精确语义：** 本期和本周都足够覆盖整次分析时使用会员；任一不足，整次使用现有API积分，会员零散余额保留。比如整份报告需要约一盘会员量，而本周只剩半盘，这份报告整次用API，半盘会员量仍可用于之后较小请求。不是先把会员扣到零再由API补差价。钱包回退受用户已接受的报价上限约束，未知账号、权限失败或断网不能视为会员用尽；两边不足则拒绝，不自动扣人民币充值。

目前两云仍为`MEMBERSHIP_MODE=paused / PAYMENTS_MODE=disabled`，新私人分析授权暂停，不能将“计费链已实现”写成“正式消费已经开放”。已有授权结果与合法在途支付处理保持原保护。

## 资料与平台状态

用户通过商户平台申请证书并在本机准备文件。已验证商户证书与RSA私钥配对、商户号匹配、证书当前有效，API v3文件恰好32字节且为ASCII字母/数字，微信支付公钥为RSA2048。实际应用客户端的本地配置readiness对TEST/PROD通知地址均通过；没有调用真实微信API。

- AppID：`wxb83dd544397ac964`；商户号：`1003105536`。
- 商户证书序列号：`1FD2E977A9D81EA9192DB6FCDAB95A574E4233EF`。
- 微信公钥ID：`PUB_KEY_ID_0117525274632026110900111829000011`，用户平台截图明确显示“已启用”，标识经两种本机OCR逐字一致核对。
- 本机文件位于仓库外`/Users/fan/cert/`；目录0700，证书包、密钥、公钥文件0600。秘密不进入Git、聊天、日志或前端；本文件仅记录非秘密标识。

文件格式/readiness和用户平台截图不能替代真实微信响应或通知的验签联调，也不能证明用户在平台保存的API v3值与本机一定相同；实际联调仍待后续授权。

## 已授权配置的精确增量

用户在语音中明确要求“在测试环境和正式环境都部署一下”。执行顺序TEST→PROD，仅配置Web，原软件和镜像保持不变，会员paused、支付disabled、billing=true、Free=0继续保持。不安装新软件，不改Cron/GPU/数据库或实体设备。

| 配置/路径 | TEST | PROD |
| --- | --- | --- |
| Web | `katrain-web` | `katrain-ucloud-katrain-web-1` |
| 实际Web UID/GID | 0/0 | 10001/10001 |
| 主机秘密目录 | `/home/fan/.config/katrain/secrets/wechat-pay/` | `/etc/katrain/secrets/wechat-pay/` |
| 容器只读目标 | `/run/secrets/wechat-pay/` | 同左 |
| 通知URL | `https://go.sailorvoyage.top/api/v1/payments/wechat/notify` | `https://modelstella.com/api/v1/payments/wechat/notify` |

TEST的SSH部署用户没有免密sudo，因此选用其自有0700私有目录，不索要密码、不提升权限、不为安装秘密启动特权容器。其Web本来以root运行，需用实际只读探针验证可读性；PROD经既有sudo权限安装，目录和文件归Web的10001用户读取。该主机路径选择不改变容器路径、收款开关或其他角色的配置。

仅新增8个`WECHAT_PAY_*`环境变量：APP_ID、MCH_ID、MERCHANT_SERIAL、PUBLIC_KEY_ID、NOTIFY_URL、PRIVATE_KEY_PATH、API_V3_KEY_PATH、PUBLIC_KEY_PATH。三份容器文件固定为`apiclient_key.pem`、`api_v3_key`、`wechatpay_public_key.pem`，仅通过SSH私有通道传输，0700/0600，并只读挂载给Web。

复用已审核native替换机制；先私有保存实际完整Config/HostConfig/网络/挂载和不可变镜像，按完整容器ID与fingerprint做CAS。配置适配只允许上述8变量、1个固定只读bind及原helper操作标签，其余Env、用户、资源、角色设置及网络原样保留；容器默认Hostname仅随新容器ID正常变化，定制Hostname保留。未用裸Compose重建，未将secret值放入环境变量。机制已获[独立Astra审核](../superpowers/reviews/2026-11-09-wechat-config-astra.md)；失败按同镜像、无迁移的配置恢复路径恢复实际旧Web及完整beforeimage。

## 部署前实际核对

2026-11-09 15:58北京时间：两云仍为`4235a58238e805530cb07ef0eb8041ba93df586f`，实际Web均running/restart0，PROD为healthy。尚无WECHAT_PAY环境变量或微信专用秘密挂载。

| 项目 | TEST | PROD |
| --- | --- | --- |
| 旧Web ID前缀 | `695669c2d7f9` | `163933b6fe6b` |
| orders / terms | 0 / 0 | 0 / 0 |
| credit_transactions / users / system_config | 14 / 19 / 2 | 9 / 12 / 3 |
| 在途Native订单 | 0 | 0 |
| 钱包总整数credits | 140000 | 90000 |

完整beforeimage私有保存在各主机，未导出秘密：TEST `/tmp/wechat-config-preflight-20261109-89xz_rcd/`，PROD `/var/tmp/wechat-config-preflight-20261109-psv7abzp/`。最终prepare/apply仍需新鲜CAS，不能套用本表替代。

## TEST先行、PROD随后：实际结果

| 项目 | TEST | PROD |
| --- | --- | --- |
| 新Web完整ID | `d2b2e967f826d4d7c689332336561845956ca226762a9cc7c52da8a0f30ceff9` | `92df49f9c35c19e52ddc1c21bc052d5a50811e432f190e568abde3d7f0203044` |
| 不可变镜像（与配置前一致） | `sha256:165a6b2d8ac948be403f9e55e2477a71ef34d0a54dc370bebf970f7a2a4b6383` | `sha256:0356ac1ae1de4b1a47a7d7d76d4337ab41a273d79e15881aca07da56d7504995` |
| 实际软件 | `4235a58238e805530cb07ef0eb8041ba93df586f` | 同左 |
| 独立检查时间（北京时间） | 2026-11-09 16:23起 | 2026-11-09 16:29起 |
| 健康 | HTTP200/status ok、restart0 | HTTP200/status ok、Docker healthy、restart0 |
| 实际文件readiness | true，内容匹配原件 | 同左 |
| 商业开关 | paused / disabled / billing=true / Free=0 / Max sale=true | 同左 |
| 其他运行容器 | 16个，身份/配置/资源/挂载/网络/启动与重启次数均不变 | 18个，同左 |
| 财务前后 | 本文基线各计数、钱包总额不变，在途Native0 | 同左 |

两站实际只有预期8个Env、1个固定只读bind及操作标签变化；实际Web用户、原有完整Config/HostConfig/其他挂载和稳定网络均通过独立比对。主机目录0700、文件0600且归属正确，容器内仅输出文件内容匹配的布尔结果，未输出秘密或摘要。原容器正常停止后保留，恢复资料和实际配置持续私有保存。

持久状态位于TEST `/home/fan/.local/state/katrain/wechat-native-config/wx20261109a/`，PROD `/var/lib/katrain/wechat-native-config/wx20261109a/`，包括完整beforeimage的`manifest.private.json`、安装/切换回执及原子`active.private.json`。各自实际执行的`configure.py`和未改的`native-release.py`也经hash核对、以0600保存在此目录，恢复不依赖临时目录是否仍在。实际Env/bind同时持久在Docker配置，未来替换须从实际配置完整保留；不能以裸主Compose覆盖。

本次配置恢复建立在尚无真实订单、paused/disabled的基线上。后续开放并存在真实单时，不得直接移除支付配置；必须先确认在途订单及继续验签、查单和履约的路径，不能把恢复旧Web等同于资金回滚完成。

网站/Galaxy `/membership` 与云Kiosk `/kiosk/membership` 的真实HTTPS页面均200，健康接口正常。11语实际翻译接口各345会员键，逐语匹配既有已审核部署产物；未改静态包或重做无关视觉回归。两站各一笔空正文无签名回调探测均返回400 `invalid_payment_notification`，财务再查不变，OpenAPI无mock到账路由。出网只完成官方商户域名TLS握手、验证CA/主机名，没有发送HTTP或商户凭据；这不是商户签名联调成功。

配置操作器本地17项机制测试通过，Astra独立原16项及SSH叶子修复的3项聚焦测试通过。TEST精确执行版SHA256 `9d15cfbe9a0039085ab89581cd8ef3d69b4372428f770fd84424769cd883d068`；PROD执行版为`3e529a8fa0b0603c57f8ada5b963159dacc3f632f95c0c549e33b7e7489cd8cf`。唯一代码差异是PROD沿用既有SSH别名，其实际登录用户为ubuntu；最初误指定fan的传输在身份认证阶段拒绝，未安装PROD秘密或切换服务。修复经独立快审，prepare/apply/恢复逻辑未变。原native helper SHA256仍为`98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108`。

本机证据目录`output/wechat-native-config-20261109/`保存prepared/applied公共回执、独立`postcheck-public.test.json`/`postcheck-public.prod.json`及TEST单独回调财务复核。TEST首次公网读取瞬时失败后做了一次合理重验，全部通过；未因此更改产品配置或反复触发回调。原始完整配置及stage只在各机私有目录，未入Git。

配置后没有更改或部署实体盒，密钥未下发盒端。其他设备会话报告fan已正常登录`/kiosk/play`并继续语言/页面验收；本会话未将其报告当作会员支付实机终验，也未抢占RK窗口。

本轮提交只更新运行回执、计划状态及历史优先级说明，不改变任何计费代码、价格或额度。文档按功能分支→develop→父仓vendor/main收尾，纯文档尾提交不重复部署，实际软件仍为上表4235版本。

## 当前闭环与余项

- [x] 配置操作器针对性验证及独立Astra审核。
- [x] TEST配置、健康、实际readiness、11语与代表页面、收费开关及账务/其他服务保留核验。
- [x] TEST通过后PROD同项配置与验收，记录新容器和恢复资料。
- [ ] 真实微信API、手机扫另一屏幕、会员与充值到账、取消/超时及恢复：另行确定账户、真实金额上限、权益/退款安排并获批。
- [ ] 正式开放会员/真实收款：单独确认；不随本次配置开启。
- [ ] 实体正常登录后内页与云身份、摄像头及真实扫码：由协调后的设备验收继续，不把云页面或文件检查当成实机全验收。
