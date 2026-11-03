# 百分比、日均报告与积分回退：Astra 增量审核

日期：2026-11-02。结论：**Approved（仅限本次隔离设计 Fixture 增量）**。发现的一项移动端优惠说明遗漏已在同一轮修复并复核，无未解决的实现问题。用户视觉及候选价格确认仍待取得；本结论不表示后端回退、真实支付或商品开售已实现／获批。

## 范围

本次以[展示与回退修订](../specs/2026-11-02-membership-presentation-and-fallback-amendment.md)为权威，审核新展示、文案、算术和契约一致性，不重做原业务设计或成本评审。沿用已读的 AGENTS、`claude-design`、`ui-ux-pro-max` 与现有设计规则。

读取 [Galaxy HTML](../../design/membership-recharge-2026-10-31/index.html)、[Kiosk JS](../../design/kiosk-unified/membership.js)、[Kiosk CSS](../../design/kiosk-unified/membership.css)、[contracts.json](../../design/membership-recharge-2026-10-31/contracts.json)、[README](../../design/membership-recharge-2026-10-31/README.md)。使用 `view_image` 查看两端用量／会员四张桌面图及两张 Galaxy 375px 图。实际浏览器状态检查由主任务执行，本审核没有使用共享浏览器、修改实现或调用业务 API、数据库、GPU、生产服务。

## 唯一发现：已修复

Galaxy 满额优惠条件原先只在 `.matrix-caption` 内，而窄屏 CSS 隐藏该区域，导致手机会员卡片显示约省 57／73／76% 时缺少用满前提。现将「按 30 天额度用满计算；实际优惠随用量变化」放入常显的套餐页介绍段落。已读取修复代码，并实际查看新的 375px 会员截图，确认条件位于卡片之前；同一轮审核闭合。

## 核对结果

- 两端用量分别显示本期 74.2%、本周 78.6%，均扣除了预留；没有把不同分母的百分比合并成一个总剩余。原大数额改为来源状态，未显示内部请求整数或「标准单位」。内部期／周限额保留。
- 套餐行名为「普通报告」，日均参考为 1／4／13 盘。按每盘 300 手、包含初始局面及 30 天预算计算，数值一致；文案说明这是估算、不设每日上限，仍受本期和本周限制。
- 39／99／279 元候选价格对应满额优惠 56.810631%／72.591362%／76.233069%，显示约 57／73／76%；折数为 4.32／2.74／2.38。没有重新评估租金、容量或商业可持续性；Max 仍明确暂未开放且禁用。
- 来源策略与新修订一致：本期与本周必须同时足够覆盖完整分析，否则整次使用已有 API 积分，不拆分来源；开始处展示报价，没有新增独立钱包选择流程。不足时提供充值／等待，未承诺自动购买积分或自动扣人民币。
- 账号未确认、失败及离线文案不把旧数据当成已授权钱包消费；用量来源标为待确认，购买入口按状态禁用。上述结论来自代码与文案检查，真实事务授权和自动回退仍属后续后端工作。
- Kiosk 1024×600 新用量／套餐画面无可见截断或重叠；Galaxy 1440×900 及 375px 新布局可读，手机页面纵向排列，无可见横向溢出。TEST、候选价和本地示意边界保留。

## 实际查看的图片

| 尺寸 | 图片 |
| --- | --- |
| Kiosk 1024×600 | [用量](../../../output/playwright/membership-v31-20261102/kiosk-usage.png)、[会员](../../../output/playwright/membership-v31-20261102/kiosk-plans.png) |
| Galaxy 1440×900 | [用量](../../../output/playwright/membership-v31-20261102/galaxy-usage.png)、[会员](../../../output/playwright/membership-v31-20261102/galaxy-plans.png) |
| Galaxy 375px，完整纵向页面 | [用量](../../../output/playwright/membership-v31-20261102/galaxy-mobile-usage.png)、[会员](../../../output/playwright/membership-v31-20261102/galaxy-mobile-plans.png) |

本轮不以旧 v3 的通过记录代替新修订审核，也不以本记录代替用户视觉确认。主任务另负责同尺寸对比与聚焦浏览器验证记录。
