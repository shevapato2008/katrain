# 会员与 API 充值：最终周上限预览

2026-11-02。权威为[简单双上限设计](../../superpowers/specs/2026-11-02-membership-simple-final-design.md)，目录版本 `membership_20261102_v1`。Astra Max 两轮计划审核已通过，用户已授权决策后直接实施，不再等待逐页视觉确认。当前目录仍是隔离设计 Fixture，不能当作真实收费功能已部署。

本地静态服务：`python3 -m http.server 8876 --bind 127.0.0.1`。

- [Galaxy 会员 · 1440×900](http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?tab=plans&capture=1&revision=final-week)
- [Galaxy 用量](http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?tab=usage&capture=1&revision=final-week)
- [Galaxy API 充值](http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?tab=topup&capture=1&revision=final-week)
- [Kiosk 会员 · 1024×600](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=final-week#membership-plans)
- [Kiosk 用量](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=final-week#membership-usage)
- [Kiosk API 充值](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=final-week#membership-topup)

页面仅使用本页内存，不连接业务 API、数据库、GPU 或真实支付。TEST 标记常显，无真实付款码。旧 `index-v2.html`、`index-v3.html`、对应 README 和 contracts 保留历史值，不用于本轮产品实现。

| 会员 | 每30天价格 | 普通报告，每周最多约 | 本期参考 | 满额相对 API 约省 |
| --- | ---: | ---: | ---: | ---: |
| Plus | 39元 | 10盘 | 30盘 | 56.8% |
| Pro | 99元 | 30盘 | 90盘 | 63.5% |
| Max | 199元 | 80盘 | 240盘 | 72.5% |

按每盘300手、含初始局面共301位置估算，受本期剩余限制，高级约4倍。优惠按30天额度用满计算，实际随用量变化。Max默认暂未开放。只有本期和本周两项上限；自然周为北京时间周一00:00。无24小时限制、额度结转或逐周释放。

用量分别显示本期与本周剩余百分比，示例为65.6%和80.0%，预留已计入不可用。不合并两个不同分母的百分比，不显示内部请求量或会员等值积分。未知、加载失败或能力关闭显示待确认，不用0冒充确认后的余额。

API仍为1元＝1积分＝100个旧整数credits，充值10／30／100元到账同额积分，无赠送。普通500visits每位置0.01积分，高级2000visits为0.04积分；300手整盘准确费用3.01／12.04积分。旧余额和账本本金不缩放。

会员足够完成整次预算时使用会员，否则整次使用已有API积分。开始前显示服务端报价及本次最大回退积分，不混扣，不自动人民币购买。未知账户、权限或网络失败不作为钱包回退依据；两边不足时阻止分析并提供充值或等待恢复。

[contracts.json](contracts.json)记录本轮内部契约和隔离边界。真实客户端类型在[types.ts](../../../katrain/web/ui/src/features/membership/types.ts)，共享请求复用鉴权头与ApiError、同源cookie和no-store；严格盒端token=null仍可正常认证。`useMembership()`以AuthContext身份和服务器环境隔离快照，仅可见时15秒同步，消费／支付后、返回前台及倒计时归零重取。倒计时基于server_now和performance.now，归零不自行补额度。真实产品不得导入本docs的模拟数据。

本轮已在真实浏览器查看[Galaxy会员](../../../output/playwright/membership-final-20261102/galaxy-plans.png)与[Kiosk会员](../../../output/playwright/membership-final-20261102/kiosk-plans.png)。保留现有构图、字体与触控尺寸；每周长文案、优惠小数及199元价格均无裁切。与上一版同viewport的[Galaxy并排](../../../output/playwright/membership-final-20261102/galaxy-plans-side-by-side.png)、[叠加](../../../output/playwright/membership-final-20261102/galaxy-plans-overlay.png)及[Kiosk并排](../../../output/playwright/membership-final-20261102/kiosk-plans-side-by-side.png)、[叠加](../../../output/playwright/membership-final-20261102/kiosk-plans-overlay.png)用于核对。本轮差异集中在冻结后的周参考、价格与优惠，未增加页面结构。
