# v3 积分与会员 Fixture：Astra 代码及视觉审核

日期：2026-11-02。结论：**Approved（仅限当前隔离设计 Fixture）**。本次发现的一处按钮文案问题已在同一轮修复，无遗留阻塞项。用户视觉确认仍待取得；本结论不代表后端、真实支付、可售目录或发布获批。

## 范围与方法

- 对当前 v3 做一次相称的独立代码与视觉审核，重点是「API 充值／会员」两种选择、每手积分、会员相对 API 的优惠、可见状态及 Fixture 可操作性。没有重做已通过的两轮 v3 业务设计审核。
- 读取用户／仓库 AGENTS 指令、`claude-design`、`ui-ux-pro-max` 和现有 Kiosk 统一改版规则；沿用既有色彩、字体、软键及 Compare／Monitor 构图。
- 检查 [Kiosk JS](../../design/kiosk-unified/membership.js)、[Kiosk CSS](../../design/kiosk-unified/membership.css)、[Galaxy HTML](../../design/membership-recharge-2026-10-31/index.html)、[契约示意](../../design/membership-recharge-2026-10-31/contracts.json)、[README](../../design/membership-recharge-2026-10-31/README.md) 与[原设计合集入口](../../design/kiosk-current-based-redesign-2026-10-14.html)。
- 使用 `view_image` 实际查看下列八张截图。浏览器交互验证由主任务执行；本审核没有操作共享浏览器会话，没有调用生产、GPU、账单或数据库。

## 发现及处理

1. **已修复：Kiosk 当前会员续费按钮写死 Pro。** 原 `membership.js:95` 在 Free → Plus 模拟开通后仍显示「续费 Pro」，但实际选择的是 Plus。现已改为 `续费 + p.name`；已读取修复后的代码确认标签与套餐一致。
2. **主任务发现的 TEST 控件遮挡已检查修复。** Galaxy 页面外演示栏现为 `z-index:150`，高于弹窗遮罩的 `100`；`inert` 只作用于产品画布，演示栏在画布之外。代码检查确认该修复保留了弹窗内产品操作的隔离。

没有新增未解决问题。

## 核对结果

- API 显示 1 元 = 1 积分、普通约 0.01／高级约 0.04 积分每手；300 手示例包含 301 个局面，为 3.01／12.04 积分。
- Plus／Pro／Max 价格、期／周标准单位、300 手参考盘数与契约一致；独立计算得到优惠 67.884828%／72.591362%／74.529347%，页面取约 68%／73%／75%。优惠用满前提与估算限制可见，移动卡片也在优惠行写明「用满后」。Max 明确暂未开放且禁用。
- 不显示会员内部等值积分，不保留 24h 或报告／互动独立资源；当前可用按期／周剩余较小值，默认示例为 6,622。TEST、候选价格、内存示意与无真实收款表达明确。
- 代码中的加载、错误和离线状态会阻止创建购买预览；Kiosk Free 升级保留已用 301 个周单位，新期已用为 0；Galaxy 会员成功仅记录 TEST 订单，不宣称正式履约。
- Kiosk 三页在 1024×600 内完整呈现，18／22／28px 层级、至少 44px 产品触控目标及软键材质符合现有规则；未见截断、重叠或越界。Galaxy 桌面与 375px 窄屏主信息可读，窄屏按纵向卡片布局，无可见横向溢出；桌面允许纵向滚动。
- `claude-design` 构图诊断为 0/10：未发现其列出的通用 Hero、装饰图标卡片或错误页面构图问题。

## 实际查看的图片

| 目标 | 图片 |
| --- | --- |
| Kiosk 1024×600 | [API 充值](../../../output/playwright/membership-v3-20261101/kiosk-topup.png)、[会员](../../../output/playwright/membership-v3-20261101/kiosk-plans.png)、[用量](../../../output/playwright/membership-v3-20261101/kiosk-usage.png) |
| Galaxy 1440×900 | [API 充值](../../../output/playwright/membership-v3-20261101/galaxy-topup.png)、[会员](../../../output/playwright/membership-v3-20261101/galaxy-plans.png)、[用量](../../../output/playwright/membership-v3-20261101/galaxy-usage.png) |
| Galaxy 375px，完整纵向页面 | [API 充值](../../../output/playwright/membership-v3-20261101/galaxy-mobile-topup.png)、[会员](../../../output/playwright/membership-v3-20261101/galaxy-mobile-plans.png) |

旧 v2 截图的同尺寸对比及最终验证记录由主任务负责；本记录不把旧 v2 审核、代码检查或截图检查代替用户视觉确认。
