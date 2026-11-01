# 会员与积分充值：双端真实运行时规格／视觉审核

2026-11-02。范围为当前 worktree 的 Galaxy / Kiosk React 页面、共享客户端契约和隔离浏览器预览。先按最终设计检查规格，再检查运行时质量；本报告不把浏览器 mock 当作真实业务 API、账务或正式支付验收。

## 规格审核

基线为[最终简单双上限设计](../specs/2026-11-02-membership-simple-final-design.md)及[Astra Max 最终计划审核](2026-11-02-membership-simple-plan-astra-r2.md)。本次未重开已冻结的产品决策。

- 目录驱动价格为每30天39／99／199元，普通报告周参考10／30／80盘，本期参考30／90／240盘。双端方案主行及邻近说明保留300手估算、受本期剩余限制、高级约4倍与满额优惠条件；Max始终显示暂未开放、购买控件禁用。
- 用量显示本期65.6%和本周80.0%两项独立剩余比例，预留包含在“已用及分析中”。两页和说明没有向用户显示内部标准单位、会员积分或日均量。
- 普通／高级 API 每位置0.01／0.04积分；300手报告包含初始局面，示例分别为3.01／12.04积分。钱包初始10.00积分，1元＝1积分。说明表达会员优先、任一窗口不足时整次使用已有API积分，不拆分来源、不自动充值。
- Galaxy购买确认解释顺延、不清零现有额度，实际日期以服务端付款回执为准。TEST模拟订单明确不真实收款；页面没有模拟成功或自行发放权益按钮。
- 付款测试先由POST得到pending，再由GET订单轮询返回paid；页面随后重新GET usage，最终显示20.00积分。断言创建仅一次，provider为mock；没有用普通用户按钮直接把订单设成paid。

**规格结论：在本次UI范围内通过。** 真正的PG账务、权限／并发、真实报价与消费链路仍须由后端与全功能终审独立验证。

## 运行时与证据

新增[浏览器用例](../../../katrain/web/ui/tests/membership-recharge.spec.ts)，仅3个代表场景：Galaxy1440×900、Kiosk1024×600、Galaxy375×812。mock全在该spec内，载荷按共享types/API形状构造；生产页面没有导入测试数据。语言cn，登录token仅为浏览器fixture。外壳静态图片／翻译复用现有helper，auth、health、vision、geometry与billing由浏览器拦截；未启动完整后端、读取数据库／env、调用GPU或支付渠道。

命令（在`katrain/web/ui`）：

```sh
KATRAIN_PW_VISUAL_PORT=5189 KATRAIN_PW_VISUAL_CHROME=1 npx playwright test --config=playwright.visual.config.ts tests/membership-recharge.spec.ts
```

使用现有visual config，以strict port启动本worktree Vite，不复用其他服务。最近完整运行：**3 passed，15.7s**。Kiosk检查无新增Dock、可见操作均至少44px、说明／订单弹层位于`.kiosk-screen`内且没有越出600px画布；用量底部说明由真实鼠标滚轮到达。375px方案页上端与滚到Max后均无横向溢出。浏览器没有pageerror；现有React Router future flag控制台提示不影响此次预览。

图片位于`output/playwright/membership-runtime-20261102/`。每组保留同尺寸reference／implementation／side-by-side／overlay／diff，已经通过`view_image`实际看过实现、并排和叠加／差异；像素差异不作为通过分数。

| 视图 | 实现 | 同尺寸并排 | 叠加 |
| --- | --- | --- | --- |
| Galaxy方案1440 | [实现](../../../output/playwright/membership-runtime-20261102/galaxy-plans-1440.png) | [并排](../../../output/playwright/membership-runtime-20261102/galaxy-plans-side-by-side-1440.png) | [叠加](../../../output/playwright/membership-runtime-20261102/galaxy-plans-overlay-1440.png) |
| Galaxy用量1440 | [实现](../../../output/playwright/membership-runtime-20261102/galaxy-usage-1440.png) | [并排](../../../output/playwright/membership-runtime-20261102/galaxy-usage-side-by-side-1440.png) | [叠加](../../../output/playwright/membership-runtime-20261102/galaxy-usage-overlay-1440.png) |
| Kiosk方案1024 | [实现](../../../output/playwright/membership-runtime-20261102/kiosk-plans-1024.png) | [并排](../../../output/playwright/membership-runtime-20261102/kiosk-plans-side-by-side-1024.png) | [叠加](../../../output/playwright/membership-runtime-20261102/kiosk-plans-overlay-1024.png) |
| Kiosk用量1024 | [实现](../../../output/playwright/membership-runtime-20261102/kiosk-usage-1024.png) | [并排](../../../output/playwright/membership-runtime-20261102/kiosk-usage-side-by-side-1024.png) | [叠加](../../../output/playwright/membership-runtime-20261102/kiosk-usage-overlay-1024.png) |
| Galaxy方案375 | [实现](../../../output/playwright/membership-runtime-20261102/galaxy-plans-375.png) | [并排](../../../output/playwright/membership-runtime-20261102/galaxy-plans-side-by-side-375.png) | [叠加](../../../output/playwright/membership-runtime-20261102/galaxy-plans-overlay-375.png) |

其他代表交互截图：[Kiosk画布内额度说明](../../../output/playwright/membership-runtime-20261102/kiosk-quota-dialog-1024.png)、[Kiosk充值](../../../output/playwright/membership-runtime-20261102/kiosk-recharge-1024.png)、[Galaxy充值](../../../output/playwright/membership-runtime-20261102/galaxy-recharge-1440.png)、[Galaxy待付款](../../../output/playwright/membership-runtime-20261102/galaxy-order-pending-1440.png)。reference来自当前最终Artifact：Galaxy直接按相同viewport捕获；Kiosk合集只捕获原生1024×600的`#stage`，未把合集侧栏或工作台当产品。

## 视觉质量审核

| 项目 | 实际观察与差异判断 |
| --- | --- |
| 构图／几何 | Galaxy真实外壳保留顶部品牌、完整导航与移动底栏，区别于Artifact简化壳；1440由矩阵改为三个等宽方案卡，但价格、优惠、普通报告、购买操作层级相同，信息无裁切。375为单列，底栏固定，后续方案可滚动到达。Kiosk保持56px顶栏、全宽页控／三分段、三列方案、两栏用量；没有新增Dock。 |
| 间距／层级 | Galaxy文字与卡片比Artifact更疏，1440规则需下滚；375单卡更高。Kiosk方案卡上缘相差约6px，主要由真实分组标题尺寸造成，底部购买操作仍44px且可见。Kiosk用量下方重复查看说明进入局部滚动区，有真实滚轮通路，不假装内容已完整同屏。 |
| 字体／色彩／材质 | 使用真实应用既有主题与字体，Galaxy为深灰底／文楷式显示、Kiosk为实际serif与Plex数字；Artifact深绿与更圆字体不机械复制。Kiosk玉绿强调、软键质感及18／22／28px层级保持。Galaxy可用按钮原低对比度问题已要求局部修正，详见下表。 |
| 图标／素材 | 品牌图、导航与Kiosk Phosphor复用真实资源；无碎图或新增装饰图。Kiosk订单历史使用现有页级图标按钮，原受本页通用padding挤压，详见下表。 |
| 文案／状态语义 | 移除了设计工作台、示例身份与“当前数据仅在本页内存”说明；真实页面的已同步来自mock API确认，订单paid来自服务端轮询。价格与比例均不依客户端按钮自行授权；Max禁用、TEST无真实收款提示诚实。 |

### 发现与修复闭环

| 严重性 | 位置与复现 | 处理 |
| --- | --- | --- |
| Important I1（已关闭） | `src/galaxy/pages/membership/MembershipPage.tsx`的可用outlined/text操作及选中Tab原沿用深绿`#4a6b5c`，在`#252525`卡片／`#0f0f0f`页底分别约2.59:1／3.24:1。充值cream示例框的h3还受到`global.css:54`标题浅白色影响。 | 实现者在该页L66为可用text/outlined按钮增加浅玉绿`#b7d9c2`（对卡片10.01:1），disabled明确排除；L1045／L1046同样提亮选中Tab及indicator，L846令示例总价显式继承深字色。最终完整3例再次通过，并实际查看1440／375方案及充值截图，确认三处文字清楚、Max仍禁用。 |
| Minor M1（已关闭） | Kiosk `src/kiosk/pages/membership/membership.css:19`通用button横向16px padding原覆盖44px宽`.kiosk-pagebar__iconbtn`，将右上订单记录图标挤至约8px。 | 实现者在该页CSS L46只为iconbtn将padding归零，保持44px触控框。最后Kiosk代表截图与叠加已实际查看，订单记录图标恢复可辨，触控尺寸断言仍通过。 |

**质量结论：Approved。未解决问题：0 Critical／0 Important／0 Minor。** 两项视觉问题均由相应实现者局部修正，本审核包只写测试、截图与本报告，未修改产品代码、未commit。最终完整运行3 passed（15.7s），全部对照图已刷新至修复后的实现。完整业务API和正式收款不在本次UI预览验收范围，仍须后续真实集成与Astra Max终审。
