# 微信 Native 与会员分析开放回执 — 2026-11-10

用户已确认具体开放方案。已按 TEST 验收后 PROD 的顺序，将两云实际设置为 **`MEMBERSHIP_MODE=enabled / PAYMENTS_MODE=live`**，保留 billing=true、Free=0、Max 可售及现有微信凭据。网站现在可以由用户本人选择商品并微信扫码；尚未发生真实下单、付款、到账或消费验收。

本文件接续[凭据配置回执](wechat-native-config-release-2026-11-09.md)，优先于其中 paused/disabled 的历史状态。不开新钱包、不改价格或额度、不重新生成密钥，不把开闸、readiness 或按钮可用写成支付已成功。

## 发布与实际运行版本

- 会员提示修复：`9db75414c`，仅 Kiosk 一行条件及对应测试。
- 功能分支同步最新 develop 后，二者均发布 `caf97c03db089eb851170491da5c9d99ee0d3d21`。
- 父仓 main `59e0b697a10b81bf861f08a09c5725519a34aa4c`，vendor 指向 caf97c03；保留同期父仓及翻译收尾改动，没有重置原工作区。
- 联合软件包含另一会话已独立审核的 USB 改动；云端 `KATRAIN_USB_HUB_RECOVERY=false`、没有新增设备权限。后续板上 USB 修订属于独立发布，不以本次云端默认关闭状态冒充其物理异常恢复验收。

| 项目 | TEST | PROD |
| --- | --- | --- |
| Web | `katrain-web` | `katrain-ucloud-katrain-web-1` |
| 最终完整 ID | `8f36b26788b4ec7e6dd3252b77c180f9c0bce68fb5a0269e0e741343bf123c27` | `15f0c1a6f4f4e12a279c860bb7c0f83517215480180771be017c3cc4a18d58f8` |
| 不可变镜像 | `sha256:6e3bb20862409bffeb27db29db7419d81113b0b7260a380f6ec6d9b920f398e8` | `sha256:60fb49e9086171c4b9cd09c463c910bd67e99302d43184cfe9cbd2ef2375384a` |
| 实际软件 / OCI revision | `caf97c03db089eb851170491da5c9d99ee0d3d21` | 同左 |
| 实际商业配置 | enabled / live / enforced=true / Free=0 / Max=true | 同左 |
| 实际 Web 用户 | root | 10001:10001 |
| 检查 | health HTTP200、restart0 | health HTTP200、Docker healthy、restart0 |
| 其他运行容器 | 16 个，配置、网络、资源、身份及启动事实不变 | 18 个，同左 |

先在原 4235 软件上受控开放两个开关：TEST 新 ID 为 `6be1306a92fb0a532e1447496032e94ddba8641cf2f7629161f6073e4fdb98a2`，PROD 为 `eca97f22ed78dbb76e1b89c8d78980195cf38a8c34b2c57b53303290ebd32b24`。TEST 实页发现提示缺陷后，先发布 caf 并复核脚注，再在原 4235 上开放 PROD，随后 PROD 发布 caf，完整保留已启用模式。没有绕过固定 4235 激活器的基线检查。

## 最小修复及检查

TEST 真实收款 Kiosk 充值脚注原先仅根据 TEST 环境显示“模拟订单·不会真实收款”。现改为仅在 `payments_mode=mock` 显示此文案；live 使用现有 11 语“付款前核对订单金额”，TEST 环境徽标仍保留。Galaxy 原判断正确，无需改动。新增 live/mock 两种断言；该页面 17 项测试通过，独立 Astra 复验通过。

最终 caf 源码从锁文件安装依赖并完成普通与严格 Kiosk 构建；两份独立本机构建的完整 inventory 相同，build manifest SHA256 为 `44ec1d2263804c962b1fa6b01643ec00f2b7429d41b3ccce82850851e5445d2c`。联合云包 SHA256 为 `b396e031d0cb64ec9183d75b3dcc08a0896d15a3a84833a84d19ea6651108bdd`。两站候选和实际运行载荷均验证 967 个文件、445 个 Python 源文件语法及 11 套完整语言目录，各 345 个会员键。未升级服务依赖、重启 GPU/数据库/Cron/对象存储。最终两站公开 HTTPS OpenAPI 均保留微信通知 POST 路由、无模拟到账路由；这次没有重复发送通知探测。

两开关操作器 7 项聚焦测试及独立审核通过。代码发布复用另一会话已审核的 cloud `953eaba6…` 与 native `92769832…`，按实际完整 Config/HostConfig/Env、原 8 个微信字段及只读挂载、User、网络、资源作 fresh CAS。只改镜像、build SHA 和发布标签；完整保留当前商业配置。审核与视觉结论见[本轮 Astra 报告](../superpowers/reviews/2026-11-09-wechat-activation-astra.md)。未执行本机历史候选 forward wrapper。

实际短期 fan 身份只用于读取 catalog/usage/orders 列表及检查本地确认框，不点击“微信支付”。TEST Galaxy 及 Kiosk 商品按钮、39/99/199 元会员和 10/30/100 元充值已核实；补丁后的 1024×600 Kiosk 实图确认真实金额提示、10 元按钮及无模拟收款误导。PROD Galaxy 与 Kiosk 双端首验也已通过：同一真实 fan 账号、catalog/usage/orders 列表 HTTP200，会员与充值金额、购买按钮和本地确认框的微信支付按钮可用，没有 TEST/mock 误导。两站均为0业务POST、0订单创建、0页面或console产品错误；最终3张代表实图及运行回执已获独立 Astra 聚焦验收 Approved。专用浏览器会话、数据和临时认证文件已清理，没有调用 logout 或改变真实账号。无真实二维码、手机扫码、商户签名 HTTP 或付款成功证据。

两云开闸检查和代码发布后只读账务聚合：TEST orders=0、terms=0、credit_transactions=14、users=19、总 credits=140000；PROD 为 0、0、9、12、90000。没有因验证创建订单或消费。用户之后的合法付款可以改变这些值，不据此自动回退或删单。

## RK3562：部署与扣量保护

实体既有功能软件仍为 `4235a58238e805530cb07ef0eb8041ba93df586f`，父来源 `fd7bc6bc922d43cf4da51e72f6d1cde511addf1c`；不是未安装微信模块。此次没有为云端 TEST 文案重装实体软件，实体仍使用生产云身份和账务。此前 MO 已覆盖 11 语，每语 345 个会员键。

实际检查发现本地原为 legacy/billing=false/Free1，云开闸不会自动封闭盒端旧分析入口。因此只给 `smartbox-katrain.service` 追加三项有效环境配置：enabled、billing=true、Free0；本地支付仍解析为 disabled，不安装微信密钥。

- Env 文件：`/etc/smartbox/katrain-membership-guard.env`，root0600，SHA256 `2b7e58a86349e32caea497b78a88685e50b3e7b44e3cf5757c451600c0c11505`。
- 末尾 drop-in：`/etc/systemd/system/smartbox-katrain.service.d/zzzzzzzzzzzzzzzz-wechat-membership-guard.conf`，root0600，SHA256 `17abe8c431baeac7acac632af68041429037604508de08b24dfc60340733736d`。
- 使用实际有序 EnvironmentFiles 解析器；旧 Env、身份 token、Exec/User、来源文件及页面均私有比对保留。
- 在所有模式 inactive 时，以只读 SQLite backup API 一致备份实际 `/mnt/data/weiqi/weiqi-web.db`；私有目录 `/var/lib/smartbox/deployments/membership-guard-20261109b/` 保存完整配置、备份和回执，禁止盲目覆盖活动库。
- 最终配置操作器 `f25289b7…` 经 Astra 批准、8 项聚焦测试通过。首次校验失败曾完整恢复启动前原配置且未启动/恢复数据库；后续修正 EnvironmentFiles 分隔符比较，使用新目录和 fresh CAS 成功。原失败点不能从恢复态直接确认，保留历史证据，没有盲重试。
- 原 launcher 页已有 Hermes 成员 active 而 target inactive；仅在维护锁下优雅停该孤儿成员，原单页未变。配置完成后通过已有 launcher 服务的 `switch_to('go')` 启动，返回 ui_ready=true；实际 Go 进程 PID54476，三项进程环境符合预期，数据库 `membership_activated_v1` 已存在。启动后不得恢复 legacy 或覆盖备份库。
- 实体 `/api/v1/health` HTTP200、正常落子引擎 reachable，`/kiosk/membership` HTTP200；未登录 catalog 返回401。原屏幕仍为 1024×600 launcher 登录页、原 page ID `64D0181DB6BCE1E89A66295983BF0C5B`，未创建访客或替用户重登。

因此实体收费保护已配置并启动，但**真实 fan 登录后的云代理、旧 API 的实际409/state交付边界、手机扫码及消费尚待用户登录后的设备验收**。配置与已审源码证明保护已启用，不能替代该完整动态旅程。未使用模拟身份冒充实机用户，也未声称摄像头/LED故障已由本轮修复。

## 用户验收入口和资金边界

- PROD 网站/Galaxy：<https://modelstella.com/membership>；云 Kiosk：<https://modelstella.com/kiosk/membership>。
- TEST：<https://go.sailorvoyage.top/membership> 及 `/kiosk/membership`；TEST 此次也是真实微信收款，权益与 PROD 独立。
- 实体：本人在 launcher 登录后进入围棋 → 会员与用量，订单由生产云处理，盒内不存支付密钥、不本地发权益。
- 自行选择充值或会员，核对金额，再点击微信支付并用手机微信扫一扫另一屏幕的订单码。Native 同手机付款不作承诺；手机网页需另一块显示屏。
- 会员优先仍是整次操作单来源：本期和本周都够才用会员，否则整次用现有 API 积分；不足或网络/身份未知不自动扣人民币、不拆分两来源。报告和私有局面分析纳入计费，正常 AI 对手落子等既定边界保持。
- 运行侧必需支付配置已齐，真实商户下单和通知仍待实单；Native 下单响应、验签解密、到账幂等、取消/超时/失败同步及真实消费仍需实际订单观察。用户亲自支付后再查对应单与账务，不把目前0单、readiness和自动化传输测试称为正式收款成功。

本机公开验收在 `output/wechat-native-activation-20261109/`，代表图片在 `output/playwright/wechat-native-activation-20261109/`。完整 beforeimage 和秘密仅留主机私有目录；未来部署必须保留实际已开放配置，不能拿历史 paused/disabled 示例覆盖。
