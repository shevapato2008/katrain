# 会员与充值：隔离设计预览

2026-10-31。对应[设计讨论稿](../../superpowers/specs/2026-10-31-membership-recharge-design-draft.md)修订2。

本预览用于确认Galaxy/Kiosk套餐和收银台设计。它不是已集成业务模块，不会真实收款、操作数据库或生成分析任务。

## 打开方式

- [本地Galaxy预览](http://127.0.0.1:8766/docs/design/membership-recharge-2026-10-31/index.html?surface=galaxy)
- [本地Kiosk预览](http://127.0.0.1:8766/docs/design/membership-recharge-2026-10-31/index.html?surface=kiosk)
- 服务停止后，可在仓库根目录执行 `python3 -m http.server 8766 --bind 127.0.0.1`。
- `capture=1`隐藏预览控制，以目标尺寸检查产品构图；常规打开保留模拟按钮。

## 设计依据

- 复用现有kiosk-shell本地字体，使用现有围棋的slate/panel/jade颜色；不安装或复制字体/依赖。
- 用`ui-ux-pro-max`检查支付反馈、触控尺寸和间距；采用44px最小触控目标、至少8px按钮间距。
- Galaxy以1440×900检查，Kiosk以1024×600检查。新页面Artifact尚待用户确认；并非与既有正式会员页面的对齐验收。
- 三档建议价29/99/299元，每24小时1/5/20份、每周7/35/140份；无5小时限制。深度报告4份和Plus需额外购买深度的限制在付款前可见。
- 所有价格、账号和权益都是设计Fixture。页面内存仅演示“同页切换两端”的共用状态，不代表两个真实客户端已通过云端同步。

## 已做的聚焦检查

- 内联JavaScript经`node --check`通过。
- Chromium/Playwright实际点击检查：失败提示、过期重建、选择支付宝、模拟会员到账、离线付款不冒充已确认到账、恢复后显示到账、重复通知不重复增加1250点、切换两端保留同一份演示权益、离线禁止创建订单。
- 本次点击链无页面脚本异常，没有向业务/支付`/api/`发请求。以上只证明Fixture行为，不证明真实验签、数据库事务或并发账务正确。
- 1024×600：frame实测1024×600、无横向溢出；可见产品按钮均≥44px，底部按钮在600px以内。
- 已逐张查看以下真实截图，套餐和弹窗文字未截断：
  - [Kiosk套餐](../../../output/playwright/membership-20261031/kiosk.png)
  - [Kiosk收银台](../../../output/playwright/membership-20261031/kiosk-checkout.png)
  - [Galaxy套餐](../../../output/playwright/membership-20261031/galaxy.png)

## 尚未完成与下一切片

确认视觉和价格后，先实现TEST-only模拟支付渠道与真实云端订单/权益事务、24小时/周份数预留和失败归还，再接Kiosk云端账务。正式配置必须拒绝mock，不允许仅靠隐藏调试按钮。

商户审批后另做微信/支付宝真实适配器、签名和商户/金额校验、查单、退款及小额实测。官方审批时间与工程预留详见讨论稿。既有真实支付、余额和数据库没有改动。

Fixture退出条件：真实后端接入并通过该切片验收后，生产路径不保留模拟业务数据；此独立docs目录可作为明确标注的设计资料保留。
