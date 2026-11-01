# API 充值与会员：百分比与日均报告预览

2026-11-02，v3.1。按用户最新截图反馈修订，当前权威入口是[展示与自动回退修订](../../superpowers/specs/2026-11-02-membership-presentation-and-fallback-amendment.md)，与原 v3 冲突的展示、来源策略和候选价格以此为准。其余已审事务、权限、隔离要求不变。

## 预览

本地静态服务仍为 `python3 -m http.server 8876 --bind 127.0.0.1`，Kiosk 继续使用原围棋设计合集：

- [Galaxy · 用量](http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?tab=usage&revision=percent-daily)
- [Galaxy · 会员](http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?tab=plans&revision=percent-daily)
- [Galaxy · API充值](http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?tab=topup&revision=percent-daily)
- [Kiosk · 用量](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=percent-daily#membership-usage)
- [Kiosk · 会员](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=percent-daily#membership-plans)
- [Kiosk · API充值](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=percent-daily#membership-topup)

页面只有隔离内存示意，无业务 API、数据库、GPU、真实支付或跨端云同步。TEST 与候选价仍明确标注。前轮资料保留在 `index-v3.html`、`membership-v3.js/css`、[README-v3](README-v3.md) 与 [contracts-v3](contracts-v3.json)，不能用其旧文案替代本轮。

## 本轮变化

采用 claude-design 的 Monitor／Compare 构图和 ui-ux-pro-max 的可读性与触控约束，保留字体、色彩、导航和软键。Kiosk 1024×600，正式文字 18／22／28px、触控至少44px；Galaxy 1440×900及375px窄屏。

- 用户界面全部移除“标准单位”及内部整数数量，含用量、套餐、说明及 TEST 订单。用量分别显示本期／本周剩余百分比，不合并不同分母；预留计入不可用。示例为74.2%和78.6%。
- 顶部大数字改成当前来源说明；会员优先，会员不足时整次使用已有 API 积分；积分也不足时提示充值或等待恢复，不自动购买积分。
- 套餐行名为“普通报告”，只用日均约1／4／13盘帮助比较，不再铺开本期／周请求量。按300手估算，日均由30天预算换算，不新增每日限制，仍受本期与本周剩余限制，高级报告消耗约4倍。

| 候选会员 | 每30天价格 | 普通报告 | 满额相对API约省 | 折数 |
| --- | ---: | ---: | ---: | ---: |
| Plus | 39元 | 日均约1盘 | 57% | 4.32折 |
| Pro | 99元 | 日均约4盘 | 73% | 2.74折 |
| Max | 279元 | 日均约13盘 | 76% | 2.38折 |

价格和展示是本轮候选，待用户确认；Max暂未开放。优惠基于30天额度用满，实际随用量变化。API仍为1元1积分、普通约0.01／高级约0.04积分每手；300手含初始局面，准确费用3.01／12.04积分。底层权益量没有减少，也没有把会员等值积分发入钱包。

## 来源与集成边界

[contracts.json](contracts.json)记录内部整数契约与显示规则，不会加载到产品画面。底层仍由服务器校验用户、环境、完整棋谱、模型／深度及 term/week，不能按客户端百分比授权。

开始分析前，在已有报价／开始操作处显示会员优先及不足时的本次积分费用；事务内重检后全额选择一个来源，不混扣。并发变化的积分扣款必须仍处于该次已展示的回退报价范围内，超出则更新报价。未知账号、失败或离线不能作为跳过会员校验扣钱包的理由；钱包不足不发起自动人民币充值。Free资格及原幂等、退款、旁路、迟到worker与TEST隔离边界不变。

本轮只是展示与规则的隔离预览，尚未实现真实后端自动回退。用户视觉确认后才进入对应后端切片，不能把设计文案当作真实计费功能已上线。

## 本轮核对

本轮真实浏览器检查和独立 [Astra Max 增量代码与视觉复核](../../superpowers/reviews/2026-11-02-membership-percent-daily-fixture-astra.md)已通过，无遗留实现问题；用户视觉与候选价格确认仍待取得。

- 已查看 Kiosk 1024×600、Galaxy 1440×900 的用量／会员四张主图，及 Galaxy 375px 用量／会员。Kiosk 无越界，正式文字仅18／22／28px，产品触控目标均至少44px；375px无横向溢出。保留既有字体、色彩、软键、顶栏与图标。
- 用量构图保留两条进度，将内部整数换为独立百分比；顶部改成扣费来源提示。套餐表删除内部额度和期／周盘数，保留日均普通报告、价格与优惠，增加留白。原标准单位在规则、API说明及购买确认也不显示。
- 复核发现的移动端满额优惠条件遗漏已修复：现在方案顶部常显“按30天额度用满计算；实际优惠随用量变化”。桌面主图已更新。
- 实际浏览器路径验证：两端会员耗尽时提示接续API积分；离线时来源待确认并阻断购买。规则说明含整次选来源，Galaxy39元Plus确认显示日均约1盘且无标准单位。此轮业务API请求0。两端JS语法、契约JSON、准确优惠与日均计算、git差异检查通过。

截图：[Galaxy用量](../../../output/playwright/membership-v31-20261102/galaxy-usage.png)、[会员](../../../output/playwright/membership-v31-20261102/galaxy-plans.png)；[Kiosk用量](../../../output/playwright/membership-v31-20261102/kiosk-usage.png)、[会员](../../../output/playwright/membership-v31-20261102/kiosk-plans.png)；[手机用量](../../../output/playwright/membership-v31-20261102/galaxy-mobile-usage.png)、[手机会员](../../../output/playwright/membership-v31-20261102/galaxy-mobile-plans.png)。

四张主图均保存同viewport的v3参考、新稿、并排、叠加及差异图，位于同一截图目录。代表核对：[Galaxy用量并排](../../../output/playwright/membership-v31-20261102/galaxy-usage-side-by-side.png)、[叠加](../../../output/playwright/membership-v31-20261102/galaxy-usage-overlay.png)；[Kiosk会员并排](../../../output/playwright/membership-v31-20261102/kiosk-plans-side-by-side.png)、[叠加](../../../output/playwright/membership-v31-20261102/kiosk-plans-overlay.png)。构图、数据语义与价格的差异是本轮用户要求，不作为旧稿像素还原；当前仍没有对应生产实现或会员实机截图。

以上未验证后端账务、GPU、生产数据库或真实支付；前轮v3审核及测试记录只作历史，见[旧截图与核对](README-v3.md)。
