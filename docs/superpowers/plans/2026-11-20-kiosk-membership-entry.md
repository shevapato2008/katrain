# 围棋 Kiosk 设置会员入口 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 围棋设置左侧首屏可见“会员与用量”，点击进入现有 `/kiosk/membership`，保留右上角用户名入口。

**Architecture:** 只在真实渲染的 `SettingsPage` 左侧导航顶部增加一个页面跳转项。会员页面、鉴权、积分和用量查询、微信支付均复用现有逻辑；不接回已无人挂载的 `AccountSection`，不扩展其他棋类或盒子公共主页。

**Tech Stack:** React / TypeScript / React Router；现有 Kiosk 导航与 gettext 十一语词条。

## Chunk 1: 一个入口的闭环

### 已确认需求和设计

- 用户在本会话明确确认设置左侧增加“会员与用量”，并要求继续计划、独立审核及开发。
- 1024×600 七英寸布局；复用 `kiosk-navitem` 和已有 SVG `user-circle`，触控高度至少 44px。
- 导航顶部使用 `t('membership:auth_label', '会员与用量')`，该键已具备全部十一语。长译文应正常换行并保持可点击，不缩小全局字体、不改变外壳尺寸。
- 新项是跳转，不加入右侧设置分组和滚动锚点，不谎报当前分组选中态。
- 访客也能发现入口；后续权限由 `/kiosk/membership` 现有访问保护处理。设置页不新增会员请求，不预读余额。
- 已登录会员页沿用“返回设置”；访客权限提示沿用既有“返回对弈”，不改权限流。
- 本切片无后端改动、无业务 Fixture。一个真实前端预览即可；基线与实现使用相同1024×600，并排和叠加图仅检查左栏新增入口及其余布局稳定。现有文字方案已获用户确认，若预览发现必须改变已确认设计，先展示具体变化再确认。

### Task 1: 实现和聚焦验证

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`
- Adjust existing test: `katrain/web/ui/tests/kiosk-shell-scroll.spec.ts:493`（分组导航计数）
- Existing contracts: `src/kiosk/components/layout/KioskLayout.tsx`、`src/kiosk/pages/membership/MembershipPage.tsx`、`src/components/auth/accessPolicy.ts`（不修改）

- [x] 独立 Astra Max 审核本计划，最多两轮；按用户比例原则，不扩张为账务或跨棋类工程。
- [x] 子 agent 在真实 `SettingsPage` 中增加独立导航按钮：

```tsx
<button type="button" className="kiosk-navitem" onClick={() => navigate('/kiosk/membership')}>
  <Icon name="user-circle" />{t('membership:auth_label', '会员与用量')}
</button>
```

  放在现有 `groups.map` 之前。仅必要时局部处理长文本，不改共享导航样式或新增图标资源。
- [x] 在既有真实页面测试里覆盖普通构建与 strict box 构建：按钮可见，点击调用 `navigate('/kiosk/membership')`。这是此前孤立组件测试未发现漏接的直接回归点；不增加独立测试框架。
- [x] 修正已有真实页面单测及 `kiosk-shell-scroll.spec.ts` 的“导航数等于右侧分组数”断言：只统计 `[aria-current]` 分组锚点，新增独立跳转按钮不计入。更新相邻注释，保留原滚动高亮、296/680几何和分组词一一对应的验证。
- [x] Run: `npm run test -- src/kiosk/__tests__/SettingsPage.test.tsx`；全部通过。
- [x] 使用已有浏览器运行时定向运行 `tests/kiosk-shell-scroll.spec.ts` 中“设置:滚到「落子与提示」那一组时,导航高亮的正是它”，不运行无关全量浏览器用例。
- [x] 读取十一份 PO，确认复用键非空；不运行会重写无关目录的全局翻译脚本。
- [x] 本机真实运行前端，1024×600 下保留前后截图，检查中文入口首屏可见、点击到现有页面及返回；用一种最长译文检查触控区、换行与溢出。预览可复用已有本地 fixture 工具，但不得把模拟账户/余额带入生产代码。
- [x] 运行 `npm run build`、`npm run build:smartbox-kiosk-2d`；独立做规格核对，随后独立 Astra Max 代码审核，修复实际问题直至通过。

### Task 2: 集成和发布

- [ ] 提交聚焦修改；记录审核和测试结果，避免新增多层审计工具。
- [ ] 获取最新 `develop`，合并到功能分支，保护并保留其他会话的新改动；将成果并入当前 `feature/membership-recharge`，推送功能分支及 `develop`。
- [ ] 在隔离、干净的 `smartbox-software` checkout 更新 `vendor/katrain` 至发布的 develop，保留父仓其他改动，推送 `main`。
- [ ] 按既有 `server-deploy` 流程发布 TEST / PROD 的 Web UI，保留实际容器配置；验证代表性 Galaxy/Kiosk 页面。只变应用前端，不重启数据库、GPU 或无关服务。
- [ ] RK3562 使用 `rk3562-local`；先确认正在部署的其他会话/上传进程、维护锁和实际已发布版本。忙时等待，不并发部署，不覆盖较新父仓。按已提交的原生 app 发布流程保留模式、会话和用户数据；空间不足时报告具体预算，不降低现有保护、不自作主张清理数据。
- [ ] 验收实际围棋设置：新增入口首屏可见、触控可用、进入会员页及返回正常；核对发布版本。读取当前合法账号的会员、API积分、用量状态，不创建订单、不发送短信、不触发真实支付。

### 完成边界

代码通过不等于发布完成；分别记录服务器与RK3562真实结果。设备离线或另有发布阻塞时明确报告，不把本地预览写成实机验收。白屏排查已由用户取消，不在本切片重启该调查。
