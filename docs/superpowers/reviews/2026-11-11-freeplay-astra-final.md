# 自由对弈付费分析 A：Astra Max 独立最终审核

**结论：Approved。未发现阻塞合入的 Critical 或 Important 问题，代表性视觉审核通过。**

审核对象为 `feature/membership-recharge` 上基线 `c6a48d2d7da4d350f4bc0bd82c2f695e58266ce2` 之后的当前未提交 A 切片，包含新增 `usePaidPlayPosition.ts` 及测试。依据为 [计划 Chunk 1、3](../plans/2026-11-11-phone-signup-and-freeplay-analysis.md)、[R2 计划批准](2026-11-11-phone-freeplay-plan-astra-r2.md) 与 [规格审核](2026-11-11-freeplay-spec-review.md)。B 手机号验证、短信及注册赠额保持独立外部依赖，不作为本次 A 的缺失。

## 代码审核

- **局面与执行授权一致。** `interface.py:584` 在实际落子、导航共用的 `ai_ladder_commit_lock` 内生成盘面与 key；`core/paid_analysis.py:79` 按 session → runtime 顺序校验参与者、模式、强度及 key，并捕获不可变完整路径 SGF。quote/execute 在这一步之后才进入账务或云端转发，未持运行时锁跨数据库工作或 await。已核对 `update_timer` 的 RLock 重入及广播调用链，未发现本次引入的锁顺序反转。
- **强度、计费与拒绝边界正确。** play 只允许 normal；目录的 normal 为 500 visits，实际执行继续绑定模型并验证最低 visits。research advanced 保持。缺失、过期或不支持的局面 key 在 reservation/GPU 前返回 `position_changed`；前端对此清报价及视图，等待再次点击。会员本期与本周都足够才走会员，否则整次钱包的现有 `_source`、报价上限、幂等、owned 复用及原来源退款均未改写。
- **结果保持私有。** 新 helper 只构造当前 React 的 GameState 投影，不写共享 `setGameState`、服务端节点或 WS；支招、领地、评估使用一个 receipt。scope 覆盖身份、会话、局面 key、节点、完整历史及棋盘条件；换手与旧响应丢弃机制保留。Kiosk 节点变化自动分析 effect 已删除，报价和执行只由主动操作触发。
- **限制保留。** legacy 免费 API guard、共享 state stripping、participant/owner、ranked/未结算 ranked、大厅 bot 与反作弊 lease 均继续生效；无主或他人会话的最终权限由服务端决定。普通 AI 对手生成落子的路径未被替换。
- **投影方向已独立复核。** ownership 反向取行与既有 `var_to_grid` 的底部原点一致；非对称 A19 黑、T1 白测试通过，黑方评估未随待落子颜色错误反转，输入和共享历史保持不变。此前 A-SPEC-01 可维持关闭。
- **文案范围适当。** 新增 `membership:error_position_changed` 已在 11 语 PO 中提供非空翻译，批量字典同步；未扩张到无关注册或账务实现。

## 非阻塞发现

**Minor A-FINAL-01 — Galaxy 的不可用状态缺少原因提示。** `galaxy/components/game/RightSidebarPanel.tsx:157–161` 的 `analysisUnavailable` 会禁用三个分析键，但 tooltip 目前只处理 `analysisRequiresLogin`。已登录用户遇到缺 key 或分析不允许的局面时只见灰键。可在后续小修中复用已有 `membership:error_position_unavailable` 提示；正常可分析旅程、计费与权限不受影响，不阻塞 A。

## 代表性视觉结论

独立查看以下六张实际浏览器截图，按现有页面视觉核对，无需扩大截图矩阵：

| 页面与目标尺寸 | 证据 | 结论 |
|---|---|---|
| Galaxy 1440×900 | [主页面](../../../output/playwright/freeplay-2026-11-11/galaxy-1440x900-main.png)、[报价](../../../output/playwright/freeplay-2026-11-11/galaxy-1440x900-quote.png)、[结果](../../../output/playwright/freeplay-2026-11-11/galaxy-1440x900-result.png) | 原分析按钮的位置、层级及点击状态保留；报价标题、会员优先策略、来源和最高 0.01 积分清晰，取消/确认完整可见。结果的候选点与当前黑方胜率、目差可辨认，未填造历史评估；没有裁切或布局阻塞。 |
| Kiosk 1024×600 | [主页面](../../../output/playwright/freeplay-2026-11-11/kiosk-1024x600-main.png)、[报价](../../../output/playwright/freeplay-2026-11-11/kiosk-1024x600-quote.png)、[修正后角点领地](../../../output/playwright/freeplay-2026-11-11/kiosk-1024x600-ownership-corners-corrected.png) | 棋盘、玩家卡、棋谱和触控按钮完整落在视口内；报价文本与操作按钮无溢出，层级明确。最终方向证据中左上 A19 为黑格、右下 T1 为白格，另两角中性。 |

领地方向以修正后的角点截图与当前 helper 测试为准；早期 Galaxy 结果图仅用于页面构图和结果呈现审核。

## 实际验证及限度

本审核亲自执行：

- `npx vitest run src/features/analysis/usePaidPlayPosition.test.ts src/features/analysis/usePaidPosition.test.tsx`：**2 文件、11 passed**，覆盖私有投影、同局面复用、过期局面不自动重报价、身份/游标失效及重试。
- `git diff --check c6a48d2d7da4d350f4bc0bd82c2f695e58266ce2`：通过。
- 当前 diff、相关完整调用链和新增测试源码检查；11 语新增 key 检查；上述六图目视审核。

交接记录另提供前端 9 文件 281 passed、普通及 strict Kiosk 构建通过、隔离 PostgreSQL position 用例 15 passed、guards 26 passed。本审核阅读了对应关键测试和账务实现，未重复执行这些较大检查，以上数量按交接记录引用。

截图来自本机隔离 Fixture，证明浏览器展示与状态表达；不代表真实云扣费、GPU、支付或实体设备验收。本次付费支招路径展示屏幕私有回执，且显式不宣称白灯闪烁；物理灯输出衔接及动态效果须在明日设备范围单独确认。审核未连接真实数据库、GPU、支付或 RK3562，未 SSH、部署或修改产品代码。此批准可用于继续 A 的既定集成发布流程，生产健康与发布版本仍由发布步骤验证。
