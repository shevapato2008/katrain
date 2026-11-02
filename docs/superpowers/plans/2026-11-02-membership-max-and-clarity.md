# Max 开放与会员提示修订实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. 本轮为现有功能的小范围修订，不重建 worktree，不重新核算成本。

**Goal:** 根据用户最新授权开放 Max，并补清已确认的30天总量与 API 钱包扣费提示。

**Architecture:** 沿用现有目录、报价、订单事务和两端页面。Max 使用199元、72240／24080原整数请求预算及30天期限；配置开关同时控制目录与下单，不能绕过整体会员模式、支付环境或隔离 TEST 限制。界面只增加已有字段的说明和确认文案，不新增额度或扣费规则。

**Tech Stack:** FastAPI／SQLAlchemy／PostgreSQL，React／MUI／Kiosk现有组件，pytest／Vitest／代表性浏览器预览。

## 用户决定与不变边界

- 用户已明确“Max也开放”并要求直接开发；不再计算510元或新租金情景。保留既有3500–4500元参考，不将利润或容量说成新实测结论。
- 现行价格39／99／199、30天参考30／90／240盘、每周最多10／30／80盘、高级4倍均不变。
- 主 TEST／PROD 保持 paused／payments disabled／billing enforced／Free关闭；仅取消 Max 独立停售。不能把目录开放说成正式收款已接通。
- 不改变已付订单冻结快照、幂等履约、预留／退款、整次会员→钱包来源策略、报价上限、模型深度或历史余额。

## Chunk 1：并行实现

### Task A：Max 目录与订单可售能力

**Files:** `katrain/web/core/{billing_catalog,config,payments}.py`、`katrain/web/api/v1/endpoints/billing.py`、`docker-compose.yml`；对应 `tests/web_ui/test_membership_{catalog,usage_api,orders_pg,environment}.py`。

- [x] 先在现有测试补 Max目录、19900分下单、72240／24080冻结权益、重复履约仅一次，以及配置关闭／paused／支付disabled仍拒新订单的行为断言，先红后绿。
- [x] 目录 Max 默认可售；`MEMBERSHIP_MAX_SALE_ENABLED` 默认true并在目录与新订单使用同一可售判定，允许操作者显式关闭。Compose透传该开关。旧订单读取／履约不受后来开关影响。
- [x] 只运行相关目录／环境／HTTP／订单PG检查，不重复全功能回归。

### Task B：双端权益与消费确认说明

**Files:** 两端 `pages/membership/MembershipPage.tsx`、共享 `features/membership/presentation.ts`／`ConsumptionQuoteDialog.tsx` 及对应既有测试；必要的会员 Playwright 预览用例。

- [x] 套餐卡在周盘数附近直接展示服务端 `term_report_reference`：“30天共约30／90／240盘”，保留300手、高级4倍和本期限制说明，隐藏内部单位。
- [x] 当前报价预计走钱包时，确认按钮直接写明“使用API积分，最多扣{报价积分}”；会员、免费、已拥有结果保持准确来源提示，处理中禁止重复提交。只使用签名报价给定上限，不自行推算或改扣费。
- [x] 现有 Max不可售夹具保留为关闭分支，增加或切换代表性可售 Max场景；两端使用相同服务端目录，不在前端硬编码开放。
- [x] 聚焦 Vitest，Galaxy与严格 Kiosk 构建；复用现有预览链路，各端一个代表性套餐与钱包确认截图，目视检查新增文字不溢出。不重拍全部状态。

## Chunk 2：独立审核、集成与发布

- [x] 独立 Astra Max 对本计划一次定向审核 Approved、无重要缺口；A/B 已按文件所有权并行。
- [x] 独立 Astra Max 顺序检查规格、实现质量与代表性视觉；资金相关只覆盖本次开关与历史快照边界，修复至无未解决重要问题。
- [x] 文档注明本修订优先于旧 Max停售决策。同步并推功能分支→合并推develop→更新并推父 main submodule；保留无关工作区变化。
- [x] 基于实际已运行镜像做必要换包：本轮只更换 Web，Cron 报告合同未改且保持原进程。native发布仅将Max开关改true，保留主环境paused／disabled等其余边界；先TEST后新PROD，核对真实catalog／版本／健康及双端页面，记录回执。
- [x] 停止本轮临时PG／预览进程；如正式支付前置仍缺，明确报告，不能用模拟履约替代正式收款。

**开发检查点：** 两个任务已完成，独立 Astra Max 规格／质量／四图视觉审核 Approved，无未解决重要问题。根代理69项后端检查通过，前端36项及两个真实Vite代表用例通过；普通／严格Kiosk构建通过。没有重新核算成本。集成与实际发布待下方执行回执。

**完成状态（2026-11-02，约 11:54）：** feature `f23b013055aa6580e8494037416df4e91efff4b1`、develop/实际新 Web 软件 `7f2ff0c65381250e41a9dc959d8cac9201c3a86b`、父 main `daef1180ddfeb4780782ec7db0f4fd278897a6c1` 已发布。先 TEST 后新 PROD Web-only 换版、Max true 与全局 paused/disabled 边界已核对，Cron 未改；真实 TEST Galaxy / PROD Kiosk paused 页面与本轮清理已确认，钱包确认仅由隔离 Vite 预览验收，无真实消费。阶段 A 本修订完成；见[本轮回执](../../operations/membership-max-release-2026-11-02.md)，真实收款仍属阶段 B 未完成，后续 docs 提交不改变实际镜像软件 SHA。
