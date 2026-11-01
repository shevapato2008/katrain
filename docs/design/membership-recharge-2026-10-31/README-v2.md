# 会员、实时额度与按次充值：设计预览

> 后续方向已变更：用户要求取消24h、以积分充值和统一请求预算替代双资源额度。当前HTML是上一轮v2设计资料，不能用于确认或销售新的v3商品。最新[请求预算修订稿](../../superpowers/specs/2026-11-01-membership-points-and-request-budget-v3.md)采用300手参考、Plus周2107／30天9030标准单位；价格仍待讨论。本轮旧视觉确认请求已被新方案取代。

2026-11-01。按[已审实施计划](../../superpowers/plans/2026-11-01-membership-usage-and-payments.md)更新；本轮使用 `claude-design` 设计，再以 `ui-ux-pro-max` 优化信息层级、触控和状态文案。用户视觉确认待记录，不进入对应后端切片。

## 入口

Kiosk 加入现有[围棋统一设计合集](../kiosk-current-based-redesign-2026-10-14.html#membership-usage)，不另建一套盒端设计入口。Galaxy 使用[网页预览](index.html?surface=galaxy)。两者只是隔离 HTML Fixture，不操作数据库、不发业务 API、不生成分析任务、不收款；跨页内存演示也不是已验证的跨端云同步。

在仓库根目录运行 `python3 -m http.server 8876 --bind 127.0.0.1`，打开：

- [Kiosk 合集 · 用量](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html#membership-usage)
- [Kiosk 合集 · 订阅](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html#membership-plans)
- [Kiosk 合集 · 按次充值](http://127.0.0.1:8876/docs/design/kiosk-current-based-redesign-2026-10-14.html#membership-topup)
- [Galaxy · 会员与用量](http://127.0.0.1:8876/docs/design/membership-recharge-2026-10-31/index.html?surface=galaxy)

## 构图和设计约束

- 主界面用于查看用量，其次才是比较商品。采用“用量／订阅／按次充值”页签；“复盘报告／领地与支招”切换同一个资源区，每种资源分别展示 24h 和本周的剩余数、比例与恢复时间。
- Kiosk 画布为 1024×600，复用合集顶栏、圆润软键、文楷、IBM Plex Mono 数字和全局字号设置；正式文案沿用 18／22／28 px。使用二级页面空间，不把全部套餐与四条进度压到一屏。
- Galaxy 目标为 1440×900，保留网页导航和较宽信息区。两端共用额度语义，布局随设备调整。
- `ui-ux-pro-max` 的通用自动匹配出现了与已有产品不相符的营销构图、配色和字体，不采用；保留项目设计体系，采纳其 44×44 px 触控目标、8 px 间隔、键盘焦点、清晰对比和诚实反馈建议。
- 单一明确方向；本次是在已有产品规范内增加模块，不扩大为三套无关视觉方案。

## 契约及价格

[contracts.json](contracts.json) 是本轮预览的字段、计时和价格约定；服务端尚未实现。价格以整数分存储，额度按资源和周期分别计数，不把 credits 与报告份数相加。

- Plus／Pro／Max：29／99／299 元每 30 天，报告 24h／周分别 1／7、5／35、20／140，独立互动分别 10／70、50／350、200／1400。
- Free 每自然周 1 份普通报告，不送独立互动或通用点数；24h 恢复不等于新赠一份。生产领取仍受可信身份前置约束。
- 29 元包发 1000 credits：标准 500 visits 局面扣 10 credits，即 100 标准次、0.29 元／次；2000 visits 扣 4 标准单位。已购余额是一个通用 credits 池，“约可用多少次”只是当前余额估算。
- 整盘复盘采用批处理计价：500 visits 报告为 `max(10, ceil(N/2))` credits。250 手为 125 credits、3.625 元／盘，不能宣传为每手 0.29 元。
- 会员单次参考价只适用于用满 30 天、将整笔会费分摊给互动的假设；低频用户选按次包可能总支出更低。Max 是否正式可售须以后端容量验证结果为准。
- 切换显示与重复查看同一已成功 operation 免费；额度不足不自动扣钱包。跨档订阅须在付款前显示当前期限到期后的生效日。

## 时间和状态

Fixture 使用固定 UTC 起点 `2026-11-01T04:00:00Z` 与单调时钟增量演示秒级倒计时。每秒只刷新文字，15 秒可见同步为本地模拟，不访问余额接口。倒计时归零只等待重新取得快照，不本地发放额度。

预览需包含会员、Free、耗尽、未开始窗口、未包含互动、预留、离线旧数据、跨零刷新以及付款等待／失败／过期／模拟成功。演示工具放在产品画布外；正式收银区始终说明 TEST 模拟及不可真实付款。

## 验证与确认记录

已用真实 Chromium 检查 Galaxy 1440×900 与合集内 Kiosk 1024×600 画布。Kiosk 用量、订阅、充值和收银台的代表性页面没有内容越界，产品按钮均至少 44×44 px；最大默认字号下数量和恢复时间完整。Galaxy 主要用量区和两条恢复时间在首屏内，补充说明沿网页纵向滚动。

| 对照维度 | 本轮设计变化与核对 |
| --- | --- |
| 构图、层级 | 旧稿默认三张套餐卡；新稿默认用量监测，订阅、按次包分别进入页签。两资源共用切换区，不把四条进度和三张套餐卡同时塞入盒端。 |
| 几何、间距 | Kiosk 顶栏 56 px、二级内容 516 px、两侧 16 px；资源区与 300 px 账户侧栏分开。卡片与操作之间使用 12／16 px 间隔。 |
| 字体、颜色、材质 | 沿用文楷、IBM Plex 数字、青黛玉绿与合集软键；盒端正式文字 18／22／28 px。已修复通用合集标题和软键样式对会员页的覆盖，当前选中页签明确可见。 |
| 图标、素材 | 复用合集顶栏和同类线性 SVG；收银台为不可付款的占位区域，不生成真实二维码或第三方支付已接入标识。 |
| 文案、状态 | 去掉旧 10 元／1250 点；使用 29 元／1000 credits。Free 周报告与独立互动分开，预留从可用量扣除，离线标旧数据，加载／失败跨页显示未确认并禁止下单。 |

代表截图：[Kiosk 用量](../../../output/playwright/membership-20261101/kiosk-usage.png)、[订阅](../../../output/playwright/membership-20261101/kiosk-plans.png)、[按次包](../../../output/playwright/membership-20261101/kiosk-topup.png)、[TEST 收银台](../../../output/playwright/membership-20261101/kiosk-checkout.png)；[Galaxy 用量](../../../output/playwright/membership-20261101/galaxy-usage.png)、[订阅](../../../output/playwright/membership-20261101/galaxy-plans.png)、[按次包](../../../output/playwright/membership-20261101/galaxy-topup.png)、[TEST 收银台](../../../output/playwright/membership-20261101/galaxy-checkout.png)。

同尺寸旧参考／新 Fixture：[Kiosk 并排](../../../output/playwright/membership-20261101/kiosk-side-by-side.png)、[叠加](../../../output/playwright/membership-20261101/kiosk-overlay.png)、[差异](../../../output/playwright/membership-20261101/kiosk-diff.png)；[Galaxy 并排](../../../output/playwright/membership-20261101/galaxy-side-by-side.png)、[叠加](../../../output/playwright/membership-20261101/galaxy-overlay.png)、[差异](../../../output/playwright/membership-20261101/galaxy-diff.png)。旧参考从准备提交 `0d938a0b` 还原，保留其当时文案；差异是此次改版的有意变化，不是像素还原失败或已完成产品对齐的证明。当前截图为设计 Fixture 的浏览器渲染，尚无 React 产品实现截图。

聚焦交互检查：两端模拟按次包重放只增加 1000 点且已付不被失败覆盖；Galaxy 失败／过期可重建订单；Free 开通会员保留已用报告；先续费 Pro 再换档的生效日期为延长后的 12/31。两端加载／错误切到订阅及充值均显示待确认并禁用购买。两端跨零前后数量不变，等待新快照后才更新恢复时间；Galaxy 数字时间戳经 HTML 属性转字符串造成的 `NaN` 已改为 ISO 并复验。Kiosk 状态检查未发出业务 `/api/` 请求。内联 JS、会员 JS 语法及 JSON、`git diff --check` 已通过。

以上仅验证隔离设计交互，不验证数据库事务、云端同步、真实支付或 GPU。用户视觉确认仍待记录。历史三卡设计及已审计划都不能替代本轮视觉确认；新页面没有对应真实设备截图。

独立 [Astra Max Fixture 代码与视觉审核](../../superpowers/reviews/2026-11-01-membership-fixture-astra.md)已 Approved，发现的跨页未知账户状态和跨零时间解析问题均已修复并独立复核，无未解决问题。此结论仅覆盖设计切片。`claude-design` 构图自查为 0／10：未触发其模板装饰或错误页面类型项；采用现有视觉规范，不新增品牌样式。

## Fixture 删除条件与后续

目前所有演示都在 `docs/` 内，没有生产导入。视觉确认后再实施目录纯规则、schema、事务和云端 API，按用户旅程接入真实数据。该切片集成通过后，生产路径不得保留 Fixture、模拟余额或调试按钮；明确标注的 docs 设计资料可以保留。

阶段 A 的真实业务后端与隔离 TEST mock 支付仍待开发；阶段 B 的官方商户签约、凭据、真实验签／查单／支付退款、身份及容量验收待核实。本轮设计不证明这些工作已完成。
