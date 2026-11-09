# 微信 Native 收款资料准备

> **2026-11-10后续已开放：** 本文记录当时的配置/代码/准备状态；用户随后已确认TEST与PROD真实收款开放，最终软件、RK扣量保护及实际验收边界以[开放回执](wechat-native-activation-release-2026-11-10.md)为准，不再将历史paused/disabled理解为当前配置。

> **2026-11-09更新：** 本商户资料已准备完毕并获用户授权部署至TEST及PROD，文件readiness、健康及无扣款验收通过；仍paused/disabled，真实支付未验收。当前实际路径及结果见[配置回执](wechat-native-config-release-2026-11-09.md)。下文保留准备/换证指引，不要因重读本页而重新生成已设置的API v3密钥。

代码发布与开启收款分开执行。当前仍为 `MEMBERSHIP_MODE=paused / PAYMENTS_MODE=disabled`；本指南不包含开启收款或真实扣款操作。已知 AppID 为 `wxb83dd544397ac964`，商户号为 `1003105536`，商户简称为“智星盒智能设备”。Native 不需要 AppSecret，也不需要开发小程序界面。

## 在商户平台准备

请使用该独立商户的管理员账号登录微信支付商户平台，按当前平台提示操作：

1. **确认产品和关联。** 检查 Native 支付已开通，“智星盒” AppID 与上述商户号仍显示已关联。不要把 AppID 当作 AppSecret。
2. **商户 API 证书和私钥。** 在“账户中心 → API 安全”按官方流程申请/下载商户 API 证书，保留配对的 `apiclient_key.pem` 和证书。需要证书序列号及 RSA 私钥，本实现不支持用 SM2 私钥替代。不要将证书包或私钥发送到聊天。[官方证书指引](https://pay.wechatpay.cn/doc/v3/partner/4012081992)
3. **API v3 密钥。** 在同一 API 安全区域设置并安全保存由32个字母/数字组成的 API v3 密钥；设置后平台不能再次查看。若商户已有其他应用使用该密钥，先核实后再决定是否变更，避免破坏原应用解密。[官方密钥指引](https://pay.wechatpay.cn/doc/v3/merchant/4012072195)
4. **微信支付公钥。** 在“API 安全 → 微信支付公钥 → 管理公钥”下载公钥 PEM，记下完整 `PUB_KEY_ID_...`。下载公钥不等于已启用公钥模式；核实平台应用/迁移状态已完成。迁移期间仍可能有平台证书签名，本实现不会跳过未知序列号的验签。[官方公钥指引](https://pay.wechatpay.cn/doc/v3/merchant/4013038816)

## 安全放置文件

建议本机目录为 `/Users/fan/.local/share/stella-private/wechat-pay/`，放在所有 Git 仓库之外。目录权限 0700，秘密文件 0600，仅当前用户可读。准备以下文件：

| 文件 | 内容 | 后续容器配置 |
| --- | --- | --- |
| `apiclient_key.pem` | 配对商户证书的 RSA 私钥 | `WECHAT_PAY_PRIVATE_KEY_PATH` |
| `api_v3_key` | API v3 密钥，恰好 32 字节，无结尾换行 | `WECHAT_PAY_API_V3_KEY_PATH` |
| `wechatpay_public_key.pem` | 从商户平台取得的微信支付公钥 | `WECHAT_PAY_PUBLIC_KEY_PATH` |
| `apiclient_cert.pem` | 配对商户 API 证书，可供本机读取序列号 | 不需挂入应用 |

不要在终端命令行参数、聊天、截图、日志或 Git 中粘贴 API v3 密钥及私钥。请通过本机安全编辑器保存文件，或使用已有受保护目录；无需为了匹配建议路径而移动现有安全资料。

完成后只需提供**目录路径**，以及两个非秘密标识：商户 API 证书序列号、微信支付公钥 ID。开发会话只检查文件存在、格式、权限和配对关系，不输出秘密正文。

## 随后的受控配置和联调

配置声明见仓库 [.env.example](../../.env.example) 与 [只读挂载 overlay](../../docker-compose.wechat-pay.yml)。实际TEST主机目录为 `/home/fan/.config/katrain/secrets/wechat-pay/`，PROD为 `/etc/katrain/secrets/wechat-pay/`，容器均只读挂载到 `/run/secrets/wechat-pay/`；权限已按实际Web用户验证。配置只给云端 Web，不给 Cron、GPU、前端或实体盒发放支付秘密，不用示例 `.env` 覆盖运行配置。文件布局及后续轮换以最新配置回执为准。

通知地址分别为：

- TEST：`https://go.sailorvoyage.top/api/v1/payments/wechat/notify`
- PROD：`https://modelstella.com/api/v1/payments/wechat/notify`

Native 的通知地址在每张订单的下单请求中指定；无需虚构一个全局 Native 回调设置页。需要 HTTPS 可达、无登录和跳转、保留原始正文及 `Wechatpay-*` 头。代码部署已验证路由可达及无签名通知被拒绝；尚未验证来自真实微信的签名通知。

文件准备后，先展示实际配置差异、只读挂载和检查命令，请用户确认；配置检查仍保持关闭收款。真实 TEST 联调、金额上限、账户、权益保留/退款安排和 PROD 开放另行确认。TEST 不是微信支付沙箱，不能把模拟到账当作正式收款。

Native 需要手机微信扫描另一块屏幕。官网手机页面会提示跨屏操作；同一手机长按或相册识别不在官方 Native 支持范围，直接同机支付需要另外接入 H5/JSAPI。[官方调起支付说明](https://pay.weixin.qq.com/doc/v3/merchant/4012791878)
