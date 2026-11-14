# Report access guidance — 最终代码审核

**结论：Approved。** 本次改动符合已修订计划，未发现需要修复后才能合入的代码问题。

审核范围：`a1987ca13b507a97f7984e2642cf4ad833d044df..18d20c1adfaf2f4f07977763e45c403b3e3f6d68`；产品提交为 `f050a308d`、`18d20c1ad`。先核对 `docs/superpowers/plans/2026-11-14-report-access-guidance.md` 和单次计划审核记录，再检查本次代码、相关共享 hook、错误映射和既有弹窗样式。

## 规格核对

- `reportAccessIssue.ts:5` 复用既有业务码映射，仅输出两种访问问题，明确排除 401；503、未知错误和普通错误文案不触发引导。未按余额或登录 token 猜测资格。
- `ReportsPage.tsx:143` 只处理主动菜单生成与失败任务重试的 Promise；后台列表错误未接入弹窗。普通和深度报告复用同一入口。
- `ReportsPage.tsx:147` 在处理迟到失败前核对当前认证及请求身份/status；身份、status 或认证状态变化会清除已打开的弹窗。
- `ReportsPage.tsx:150` 对本次接管的两类错误先调用 `clearTasksError()`，再打开弹窗，落实计划审核唯一 P2 修订；取消后不残留原“请先完成登录验证后重试”提示。
- `ReportAccessDialog.tsx:10` 复用 `cdlg`、`cdlg__box`、`cdlg__acts`、ghost/main 和现有字体/触控样式，标题与正文有正确的 aria 关联。六个新文案键覆盖现有十一语目录，403 文案不暗示重新登录或付费能修复资格来源缺失。
- `ReportsPage.tsx:595` 的取消仅关闭弹窗，主按钮仅关闭并导航 `/kiosk/membership`；没有新增 POST、自动重试、订单、余额或计费后端改动。原报价确认、创建和进度逻辑保持不变。

## 代码质量与验证

实现规模与本次局部问题相称：错误分类、展示与页面事件处理职责清楚，没有新增请求生命周期框架或修改共享错误语义。没有阻塞项，也没有需要扩大本次范围处理的建议。

审核者独立运行：

```text
npm run test -- src/features/report/reportAccessIssue.test.ts src/kiosk/components/report/ReportAccessDialog.test.tsx src/kiosk/pages/ReportsPage.test.tsx
Test Files  3 passed (3)
Tests       83 passed (83)
```

`git diff --check a1987ca13..HEAD` 通过。聚焦用例覆盖两类拒收、取消与账户导航不重复请求、旧行内提示清理、401/503 不误弹、正常报价确认、身份切换及旧请求迟到失败。

构建与 1024×600 真实组件视觉预览由主代理执行，本审核不重复；未修改产品代码、连接设备、支付、推送或部署。此结论为本次代码审核通过，不代表已完成发布或已恢复免费报告资格。
