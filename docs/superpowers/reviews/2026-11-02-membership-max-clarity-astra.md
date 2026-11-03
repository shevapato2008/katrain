# Max 开放与提示修订：独立 Astra Max 审核

结论：**Approved，0 未解决 Critical / Important。** 本轮只审已批准的小范围 diff，不替代正式商户支付验收。

- 规格基准：[修订计划](../plans/2026-11-02-membership-max-and-clarity.md)，已由另一独立 Astra Max 一轮审核通过。
- 实现基线：`e2d492bbe2c0e28446a7042be90231f86bc0cf29`。独立 reviewer 查看稳定工作树、现有行为与四张代表图；实现者未参与独立裁定。
- 源码／测试／compose diff SHA256：`afd8635a7da04758a46836ed83a3d444dfe1913170795973bc854fcb006eb133`（不含文档）。最终发布 SHA 在发布回执记录。

## Spec → Quality

Max 默认开放且可显式关闭，19900分／30天／72240本期与24080周预算不变，其他档39／99价格不变。目录与新订单共用可售判定；历史幂等读取先于停售检查，已付履约继续使用冻结快照。真实支付未启用，主环境 paused／disabled、TEST 独立数据库与 production 禁 mock 边界未放宽。

两端直接使用服务端 term_days／term_report_reference 显示本期普通报告总量。钱包确认按钮使用签名报价给出的最高积分，不自行计算或改变消费来源。

发布 helper 原件 SHA256 为 `5ed0a19c737804dcad0357a25447a90c2e87bb32625eec8afbbd000826006a53`；本轮副本只将强制 Max false 改为显式 true／false，paused／disabled／enforced／free0 与其它保护保持。报告 worker 合同不变，本轮只需更换 Web，不重启 Cron。

## 视觉与验证

独立 reviewer 查看 `output/playwright/membership-max-clarity-20261102/` 四张 Galaxy／Kiosk 套餐及钱包确认截图，对照旧同尺寸套餐图：月总量、周盘数、最高扣费清楚；Kiosk 1024×600 无裁切，按钮位于画布内。

- 实现者前端：4个聚焦 Vitest 文件36通过；真实 Vite 两个代表性 Playwright 用例通过。
- 根代理后端：目录／环境／真实PG订单／HTTP／mock边界及4个完整API旅程，69通过；16个既有UTC弃用告警。
- reviewer 独立复验：catalog／environment 23通过，3个相关前端文件32通过，diff格式检查通过。
- root operator限定检查：Max布尔两种值通过，5种不合法／越界配置拒绝，Docker mutation=0。

未新增成本计算、生产容量压测、真实支付请求或全量回归。软件发布仍须先 TEST 后新 PROD 并核对真实配置、版本与页面。
