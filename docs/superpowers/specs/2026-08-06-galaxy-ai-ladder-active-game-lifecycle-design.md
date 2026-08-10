# Galaxy 升降级对弈未完成对局设计

> 日期：2026-08-06
> 状态：用户已确认方案 A
> 当前切片：`/galaxy/play/ai?mode=rated` 未完成对局占用、继续、等待与主动结束

## 1. 目标与边界

当同一账号已有一局未完成的升降级对局时，设置页直接在现有“本局挑战”区域切换为占用状态，不新增中转页：

- 本设备创建且仍可恢复的对局：允许“继续对局”或“结束该对局”；
- 另一设备创建的对局：允许“等待结算”或“结束该对局”；
- 已产生终局、正在结算的对局：只允许刷新结算状态，不重复提交认输。

用户已明确确认：另一设备即使仍在线，也允许当前设备立即结束该局。该动作按用户主动认输处理，计为本局负。

本切片先完成隔离 Fixture 驱动的 Galaxy 前端视觉与交互确认；用户确认后再冻结接口并进入后端实现。kiosk、跨设备续弈、设备管理和通用消息中心不在本切片内。

## 2. 页面与视觉结构

- 沿用已确认的 Galaxy 升降级设置页、`ContentPageHeader`、品牌、字体、颜色和连续旅程舞台。
- 不增加新页面、全屏遮罩或同权卡片；右侧“本局挑战”区域原位替换为未完成对局面板。
- 面板只显示理解当前状态所需的信息：状态标题、对手段位、己方执子、设备归属说明和操作。
- 不展示设备 ID、内部 rung、执行身份、会话密钥或其他设备的可路由 session。
- 同一屏最多一个实底主行动。危险操作“结束该对局”使用描边/文字危险按钮，必须二次确认。
- 1440×900 保持左右双区；430×880 按现有顺序纵向排列，内容区滚动，按钮完整可达且无横向滚动。

## 3. 状态与动作

| 权威状态 | 页面展示 | 主动作 | 次动作 |
|---|---|---|---|
| 无占用 | 现有段位、对手和固定条件 | 开始正式对局 | 无 |
| `active/current_device` | 当前设备有一局未完成对局 | 继续对局 | 结束该对局 |
| `active/current_device` 但会话不可恢复 | 对局占用仍在，本地会话暂不可用 | 刷新状态 | 结束该对局 |
| `active/other_device` | 另一设备有一局未完成对局 | 等待结算 | 结束该对局 |
| `pending_settlement` | 本局结果正在结算 | 刷新状态 | 无 |

动作语义：

- “继续对局”只在服务端明确返回当前设备可恢复的 `session_id` 时出现，并导航到
  `/galaxy/play/game/{session_id}?mode=rated`。
- “等待结算”和“刷新状态”都重新读取权威状态；前者不暗示后台一定会自动完成，也不创建轮询风暴。
- “结束该对局”弹出确认：`结束后将按你认输处理，并计为本局负。此操作不可撤销。`
- 用户确认后调用权威结束命令；执行期间两个动作都禁用，并在按钮内显示进度。
- 成功后进入 `pending_settlement` 或直接展示既有结算回执，再刷新状态。
- 请求失败时保留原占用信息，显示可理解的行内错误并允许重试；不得先在客户端清除占用。

## 4. 最小公开契约

现有 `pending_settlement: boolean` 保留一个兼容周期，但不能独立表达活动对局。`GET /api/v1/ai-ladder/status`
新增一个可空的 `blocking_game`：

```json
{
  "blocking_game": {
    "game_id": "opaque-game-id",
    "state": "active",
    "ownership": "current_device",
    "session_id": "local-restorable-session",
    "user_color": "B",
    "opponent_rank_name": "3段"
  }
}
```

约束：

- `state` 只能是 `active | pending_settlement`。
- `ownership` 只能是 `current_device | other_device`；`pending_settlement` 时仅作来源提示，不决定动作。
- `session_id` 只在 `active/current_device` 且本设备确实能恢复会话时返回；其他状态必须省略。
- `game_id` 是不透明幂等键；前端不得解析。
- 响应包含 `blocking_game` 时它是唯一真相；只有旧服务完全缺失该字段时，客户端才用
  `pending_settlement` 降级。迁移后删除重复布尔值。

新增权威命令：

```http
POST /api/v1/ai-ladder/games/{game_id}/end
Content-Type: application/json

{"reason":"user_resigned"}
```

成功与终局竞态统一返回判别联合：

```json
{"state":"pending_settlement","game_id":"opaque-game-id"}
```

或：

```json
{"state":"settled","game_id":"opaque-game-id","receipt":{"counted":true,"reason":null}}
```

409 也返回同一结构和已经生效的终局结果。重复提交必须返回同一终局决定，不得重复保存棋谱、重复写
`user_games`、重复写 ledger 或重复改变段位。

新增按局查询接口，供原设备轮询以及落子/保存前校验：

```http
GET /api/v1/ai-ladder/games/{game_id}/status
```

它统一返回 `{"state":"active","game_id":"..."}`、上面的 `pending_settlement` 结构，或上面的
`settled + receipt` 结构。接口必须验证该局属于当前登录账号；不存在或不属于当前账号均不泄露对局详情。
前端不能通过总览 status 中 `blocking_game` 消失来推断某一局已经结算。

## 5. 权威边界与竞态

- “同一账号最多一局活动/待结算升降级对局”的唯一约束必须由账号级权威服务保障；权威占用保存
  `user_id`、`game_id`、服务端认可的 `origin_device_id` 和生命周期。设备本地
  `ai_ladder_pending_games` 只能作为耐久镜像，不能据此声称实现跨设备互斥。
- status 由服务端比较认证设备身份与 `origin_device_id`，只返回 `ownership` 结论；客户端提交的
  ownership 不参与任何授权。结束接口必须同时校验登录账号、占用归属和当前生命周期。
- 开局先取得账号级占用，再创建本地会话；失败必须按协议释放或过期，不允许产生第二局。
- 所有终局入口必须调用同一个权威原子操作，对占用执行
  `active → terminal(result, reason, decided_at)` 的 CAS。原设备正常终局与另一设备主动结束并发时，
  第一份成功转换获胜；失败者读取并重放已有终局。棋谱保存、ledger 和 outbox 都只能消费该决定，不得自行判定结果。
- 用户主动结束的规范结果是当前用户 `loss`，不是“取消”“无效局”或仅释放占用。
- 原设备的升降级游戏页每 5 秒调用 `GET /api/v1/ai-ladder/games/{game_id}/status`，并在每次提交落子
  和保存前调用同一接口校验；收到
  `pending_settlement` 或 `settled` 后立即禁用落子、停止引擎并进入同一结算反馈。
- 当前 `_recover_pending` 不能因为本节点找不到活动 session 就清除账号级占用；只能按权威状态对账。
- 当前设备占用成功但本地会话创建失败或丢失时，不显示“继续对局”；显示“刷新状态 + 结束该对局”。
  设备不得自行超时清除账号级占用，恢复/清理由权威服务的占用协议决定。

## 6. 数据一致性

- 对局仍只保存到共享 `user_games`，沿用 `source=play_ai`、`game_type=ai_ladder_ranked`；不建立升降级专属历史表。
- `game_id` 在占用、`user_games`、结算 ledger 与同步 outbox 中保持一致。
- `AiLadderGameLedger.game_id` 唯一约束继续承担结算幂等；结束命令不得绕过现有结算服务直接改段位。
- 若主动结束时尚无可保存棋谱，服务端仍需生成带冻结开局快照和认输结果的最小合法对局记录，保证对局首页进入复盘后能找到该局。

## 7. 加载、错误、隐私与可访问性

- 状态加载保留现有舞台几何；旧状态不可伪装成刷新成功。
- 401/403 引导重新登录；404 表示占用已消失，刷新整个 status；409 表示终局竞态，读取并展示既有结果；网络/5xx 保留状态并允许重试。
- 确认框初始焦点放在“取消”，支持键盘与 Escape；危险按钮有明确文本，不只依赖红色。
- 对另一设备只显示“另一设备”，不返回设备名称、IP、硬件编号或 session。

## 8. 前端 Fixture 与视觉验收

Playwright Fixture 只拦截 status 与结束命令，不进入生产 bundle。至少覆盖三个可见状态：

1. `active/current_device`：继续对局 + 结束该对局；
2. `active/other_device`：等待结算 + 结束该对局；
3. `pending_settlement`：刷新状态，无结束按钮。

第一轮输出 1440×900 与 430×880 的实现截图；核对页面构图、右侧层级、按钮可达性、危险语义、字体和
移动滚动。用户明确确认视觉后才实现后端。生产接口接通后删除业务组件中的临时注入入口；测试目录中的
确定性网络 Fixture 作为视觉回归输入保留。

## 9. 最小验收

- 组件测试：四种权威状态对应正确动作，另一设备不泄露 session，结算中不能再次结束。
- 后端测试：同账号互斥、立即认输、重复结束幂等、正常终局与远端结束竞态只结算一次、共享
  `user_games` 只写一行。
- 集成验收：设备 A 开局，设备 B 看到占用并立即结束；A 停止对局；两端最终显示同一负局与同一段位状态。
- 不扩展到无关安全审计、全站视觉重构或 kiosk 回归矩阵。
