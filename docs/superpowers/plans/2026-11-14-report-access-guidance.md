# Report access guidance Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** kiosk复盘普通/深度报告因额度或免费资格被拒绝时，立即显示与既有弹窗同样式的原因说明和账户入口。

**Architecture:** 只改前端。复用服务端错误码和现有membershipErrorCode映射，在用户主动生成/重试失败时显示提示；复用ConsumptionQuoteDialog的cdlg结构、字体和按钮，不新增设计系统。正常报价确认、创建和进度管线保持原样，账户入口只导航到现有/kiosk/membership。

**Tech Stack:** React、TypeScript、Vitest、现有十一语PO目录、1024×600本地浏览器预览、既有RK应用发布脚本。

## Chunk 1: 范围、证据及设计

- 基线最新origin/develop：a1987ca13。分支fix/report-access-guidance-20261114，独立worktree；不依赖原工作目录的旧fix/kiosk-ui-debug分支。
- 现场：RK报价POST两次403；auth/me200；报告列表空；usage无会员、余额0、免费资格verification_required。两台云端运行容器的get_trusted_free_eligibility固定False。证据在主工作树output/diagnostics/report-click-20261114。
- 用户授权写计划后直接实施、计划仅独立Astra Max审核一轮；开发用SDD并行，最终独立Astra Max代码审核至通过，随后四步部署。优先最小修复，不开展计费后端重构或完整报告恢复开发。
- 沿用既有kiosk cdlg/cdlg__box/cdlg__acts、ghost/main按钮、dialog-typography.css：标题28px、正文22px、触控按钮至少48px；不新增CSS主题或多状态截图矩阵。ui-ux-pro-max采用现有设计系统，重点可读性、触控和明确反馈。

### 弹窗内容

1. insufficient：标题“报告额度不足”；正文“当前可用额度不足，报告尚未开始。你可以查看会员权益或充值积分。”；主按钮“会员与充值”，次按钮“取消”。
2. verification_required（实际403）：标题“免费报告暂不可用”；正文“免费报告资格暂不可用，报告尚未开始。你可以在账户页查看会员和积分状态。”；主按钮“查看账户与额度”，次按钮“取消”。不暗示再次登录或充值能修复服务端验证缺失。
3. 401及其它网络/服务/未知错误继续原有提示，不伪装成积分不足、不自动弹购买引导。成功请求仍显示真实报价确认与任务进度。

两个弹窗的主按钮仅清理当前提示并navigate('/kiosk/membership')，不创建订单、不POST报告、不自动重试或扣费。取消返回原报告列表，可再次主动点击。弹窗不能在账号切换后被旧请求迟到错误重新打开。

## Chunk 2: 两个不冲突的并行实施任务

### Task A: 错误分类与本地化

**Files:** Create `katrain/web/ui/src/features/report/reportAccessIssue.ts`、`reportAccessIssue.test.ts`；Modify `katrain/i18n/locales/{cn,tw,en,jp,ko,de,es,fr,ru,tr,ua}/LC_MESSAGES/katrain.po`，不提交生成MO。

冻结契约：
```ts
export type ReportAccessIssue = 'insufficient' | 'verification_required';
export function reportAccessIssueFor(error: unknown): ReportAccessIssue | null;
```
复用membershipErrorCode(error,'quote_failed')，明确status401返回null；只返回这两种已知业务原因，不读错误文案、不按前端余额推断。为Dialog提供六个键：membership:report_insufficient_title/body、membership:report_verification_title/body、membership:report_view_membership、membership:report_view_account；取消复用membership:cancel。

- [x] 写红测：402/insufficient_credits、403/verification_required；401、503、未知错误均null。
- [x] 最小实现并绿测，添加六键的十一语译文，PO可解析；不改现有全局错误映射或报价接口。
- [x] 显式只提交本人文件，报告测试。

### Task B: 弹窗与页面贯通

**Files:** Create `katrain/web/ui/src/kiosk/components/report/ReportAccessDialog.tsx`及`.test.tsx`；Modify `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx`、既有`ReportsPage.test.tsx`。

冻结props：`issue: ReportAccessIssue | null`、`onClose: () => void`、`onAccount: () => void`。使用useMembershipI18n和上述键，英文fallback；issue为null不渲染。

- [x] 先写红测：真实页面生成普通/深度和失败任务重试收到这两种错误后弹窗可见；取消不创建/重试/下单；主按钮只导航现有会员页。
- [x] 为用户主动报告菜单的create/retry Promise添加一个局部失败处理，使用Task A分类；普通后台列表刷新不弹窗。有效身份下由弹窗接管这两类错误时，先clearTasksError()再打开弹窗，取消后不留下误导登录提示；其它错误仍保留原错误状态。保留正常报价/创建逻辑，不改共享hook或Galaxy页面。
- [x] 请求开始记录当前identityKey/auth status，失败回调仅在仍同身份时打开弹窗；身份变化清理弹窗。复用现有ref/effect写法，不新增请求生命周期框架。
- [x] 用同样式cdlg实现弹窗，给标题/正文正确aria关联；不增加自定义CSS。覆盖401/503不误弹、正常报价仍可确认、账号切换晚到失败不弹。
- [x] 显式只提交本人文件，报告聚焦测试。Task A独占helper/locale，Task B独占Dialog/Page，禁止共享文件并行改动。

## Chunk 3: 最小验证、审核及发布

- [x] 主代理先核对规格，再由全新独立Astra Max对本次整体代码审核，修正实质问题直至通过；不重复旧识别/计费架构审核。计划审核仅一轮，建议若必要在同次反馈中收敛。
- [x] 聚焦检查：`npm run test -- src/features/report/reportAccessIssue.test.ts src/kiosk/components/report/ReportAccessDialog.test.tsx src/kiosk/pages/ReportsPage.test.tsx`；保留原成功报价和两秒进度轮询测试，不额外建测试层。
- [x] 运行`npm run build:smartbox-kiosk-2d`。主代理一次1024×600真实弹窗组件预览，对照既有消费确认框的样式，检查正文、两个按钮和触控尺寸；这是沿用既有设计的局部前端任务，没有本次后端实施阶段或新的视觉审批门。
- [ ] fetch并合并最新develop到feature，解决冲突、复验、推feature；合入并推develop。
- [ ] 隔离smartbox-software工作树，更新vendor/katrain到发布develop，推main；保留其它WIP。
- [ ] 确认无其它部署进程、设备不在对局/标定，使用已发布准确源码及标准app发布事务部署rk3562-local；复用已验证构建，空间不足按用户已有授权清理过期发布产物，保留活动数据和当前资源。
- [ ] 恢复当前页面，验收版本、服务和实际页面。设备存在实际报告错误时可在不创建任务/订单的前提下查看已有错误；不代用户支付或绕过资格校验。说明仍未接入的免费资格来源不属于本次修复。
