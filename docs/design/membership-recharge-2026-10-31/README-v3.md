# API 充值与会员：v3 设计预览

2026-11-01～02。按用户最新要求，把购买选择明确为「API 充值」和「会员」：充值说明平均每手积分，会员说明相对充值的优惠。业务口径来自[已审 v3 设计](../../superpowers/specs/2026-11-01-membership-points-and-request-budget-v3.md)。本轮仅更新隔离 HTML Fixture，用户视觉确认仍待取得，未进入后端。

## 预览入口

Kiosk 继续放在原围棋设计合集，无新建平行合集。复用本地静态预览服务 `python3 -m http.server 8876 --bind 127.0.0.1`：

- [Kiosk · API 充值](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=points-v3#membership-topup)
- [Kiosk · 会员对比](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=points-v3#membership-plans)
- [Kiosk · 用量](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html?design=points-v3#membership-usage)
- [Galaxy · API 充值](http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?tab=topup)
- [Galaxy · 会员对比](http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?tab=plans)

页面中的账号、余额、价格与支付状态均为设计示意。没有业务 API、数据库、GPU、真实付款码或正式收款；两端内存独立，不把演示称为已实现云端同步。旧稿保留为 [Galaxy v2](index-v2.html)、[旧说明](README-v2.md)、[旧契约](contracts-v2.json) 及 Kiosk 的 `membership-v2.js/css`，其旧价格与 24h 规则不再适用。

## 设计决定

使用 `claude-design` 的 Compare 构图设计购买选择，用 Monitor 构图展示用量；再按 `ui-ux-pro-max` 校正层级、可读性、触控、焦点和状态。通用搜索给出的活泼营销页与配色不符合现有产品，沿用项目墨绿、玉绿、中文字体与 Plex 数字，不引入新品牌风格或营销 Hero。

Kiosk 保持 1024×600、18／22／28px、最小 44px 触控及圆润软键；Galaxy 目标 1440×900，并提供窄屏纵向布局。导航是「用量／API 充值／会员」。充值以每手成本为主信息，会员以价格、同单位优惠和期／周请求量对齐比较。

## 价格与文案口径

当前候选价格仅用于设计比较，尚非获批开售的服务端目录。

| 方式 | 价格与额度 | 页面重点 |
| --- | --- | --- |
| API 充值 | 1 元 = 1 积分；10／30／100 元同额到账 | 普通 500 visits 约 0.01 积分／手；高级 2000 visits 约 0.04 积分／手 |
| Plus | 29 元／30 天；期 9030、周 2107 标准单位 | 相对 API 约省 68%；300 手普通报告预算约 30／7 盘 |
| Pro | 99 元／30 天；期 36120、周 8428 标准单位 | 相对 API 约省 73%；约 120／28 盘 |
| Max | 299 元／30 天；期 117390、周 27391 标准单位 | 相对 API 约省 75%；约 390／91 盘；暂未开放 |

优惠按 `1 - 会费 / (30天标准单位 × 0.01元)` 计算，未四舍五入分别为 67.8848%、72.5914%、74.5293%。页面必须紧邻说明「按30天额度用满计算；实际优惠随用量变化」，不能把它写成任何使用量都能获得的固定折扣。会员不显示内部等值积分，不将其发入购买余额。

每个标准局面扣 0.01 积分，高级扣 0.04。整盘 N 手含初始局面，共 N+1 个位置，所以 300 手普通／高级准确示例是 3.01／12.04 积分；每手价格用「约」或「平均」表述，不把整盘说成恰好 3／12 积分。领地与支招共用同一结果，切换、重复查看不双扣。

盘数是按 300 手换算的预算参考，受本期和本周剩余共同限制，不承诺所有续费排期都能做满该盘数；高级消耗 4 倍。取消 24h 和报告／互动独立资源；当前可用是本期与本周剩余的最小值，不相加。

## 状态与集成边界

[contracts.json](contracts.json) 记录本轮候选目录、折扣算法、统一 term/week 示例与状态语义，不是后端已实现契约。仅显示购买余额 `credits / 100`，原整数账本、旧订单与旧计价快照不得改写。

保留加载／失败／离线、预留、Free 与 TEST 确认的最小可用演示。账号未知禁止购买；离线明确标旧数据；会员不足不自动扣积分；Free 的每周一份报告资格不能显示为通用单位。周倒计时结束等待新快照，不能本地补量；本期结束表示到期，不表示恢复。正式接入须由服务端提供账号、目录可售状态、余额、term/week、预留、时间与订单确认。

## 验证与确认

真实 Chromium 已核对 Kiosk 1024×600 与 Galaxy 1440×900，并检查 Galaxy 375px 窄屏。独立 [Astra Max 代码与视觉审核](../../superpowers/reviews/2026-11-02-membership-points-fixture-astra.md)已通过，无遗留问题；这只覆盖隔离设计 Fixture，用户视觉确认仍待取得。

| 核对维度 | 本轮结果 |
| --- | --- |
| 构图与层级 | API 页把单手费用、整盘试算与充值选择放在主要位置；会员按同一单位对齐价格、优惠、期／周请求量。移除旧 24h 与双资源。 |
| 几何与间距 | Kiosk 固定画布内无越界，所有产品按钮至少 44px；已调整会员卡与脚注的独立留白。Galaxy 可纵向滚动，窄屏无横向溢出。 |
| 字体、色彩与材质 | 保留既有墨绿、玉绿、中文字体、Plex 数字与盒端软键。盒端正式文字仅 18／22／28px；修复 Galaxy 未闭合 small 导致的嵌套缩字，桌面重要说明至少 14px。 |
| 图标与素材 | 沿用现有顶栏及线性 SVG，未增加装饰图或真实付款码。Galaxy 的浅色试算区用于突出准确报告价格。 |
| 文案与状态 | 每手 0.01／0.04 积分和 300 手 3.01／12.04 对应；会员优惠及满额条件可见；Max 禁用，未知账号／离线禁止下单；无自动钱包兜底。 |

新截图：[Kiosk API](../../../output/playwright/membership-v3-20261101/kiosk-topup.png)、[会员](../../../output/playwright/membership-v3-20261101/kiosk-plans.png)、[用量](../../../output/playwright/membership-v3-20261101/kiosk-usage.png)；[Galaxy API](../../../output/playwright/membership-v3-20261101/galaxy-topup.png)、[会员](../../../output/playwright/membership-v3-20261101/galaxy-plans.png)、[用量](../../../output/playwright/membership-v3-20261101/galaxy-usage.png)；[375px API](../../../output/playwright/membership-v3-20261101/galaxy-mobile-topup.png)、[375px 会员](../../../output/playwright/membership-v3-20261101/galaxy-mobile-plans.png)。

同尺寸 v2 参考／v3 新稿对照已生成于同一截图目录，文件以 `reference-设备-页面-v2.png`、`设备-页面-side-by-side.png`、`设备-页面-overlay.png` 和 `设备-页面-diff.png` 命名。代表核对：[Kiosk 会员并排](../../../output/playwright/membership-v3-20261101/kiosk-plans-side-by-side.png)／[叠加](../../../output/playwright/membership-v3-20261101/kiosk-plans-overlay.png)，[Galaxy API 并排](../../../output/playwright/membership-v3-20261101/galaxy-topup-side-by-side.png)／[叠加](../../../output/playwright/membership-v3-20261101/galaxy-topup-overlay.png)。这是有意改版对照，不是把旧稿作为 v3 像素还原目标；目前尚无对应 React 产品实现或会员实机截图。

聚焦浏览器交互已通过：两端 10 元 TEST 充值确认后示意余额从 10.00 变 20.00，重复模拟确认不再增加；Galaxy 高级试算 12.04；加载中跨 API／会员页面均阻断购买，离线阻断，Max 始终禁用。Kiosk Free → Plus 后本期已用为 0、本周已用保留 301，续费按钮正确显示 Plus。两端此轮路径均无业务 `/api/` 请求。JSON、准确优惠计算、301 局面换算、JS 语法与 `git diff --check` 通过。Claude-design 构图自查未发现其十项模板化问题。

独立审核所指出的 Kiosk 当前套餐续费名称已修复；根代理发现的 Galaxy 弹窗遮挡页面外 TEST 控件已修复并以实际点击通过。未进行生产、数据库、支付渠道、GPU 或发布验收；不将这些 Fixture 检查扩写为业务已完成。

## Fixture 删除条件

当前文件只在 docs 内，无生产导入。视觉确认后按对应用户旅程接入真实服务；上线验收时生产路径不得保留模拟余额、Fixture 或调试控制。标明历史的 docs 可以保留。真实支付与发布仍按已审计划单独实施，不将 TEST 模拟当作正式收款。
