独立 Astra 计划审查，第 1 轮：**Issues Found，修改后送第 2 轮；本轮不批准进入产品实现。**

审查对象为 `docs/superpowers/plans/2026-10-24-kiosk-player-card-spacing-ranks.md`，基线 `09ee7f59faf40e4908e70d6c201aebd25257d33c`。已纳入本轮中途对 `WebKaTrain.user_id` 的更正：它是引擎 UUID，计划改从 SessionManager 的真实账号参数注入独立 `account_user_id`，方向正确。这里只审计划及必要源码，未修改产品代码、未运行产品测试或部署；不构成后续代码或视觉验收。

必须修正：

1. **P1 — 不得把大厅/观战 `rank_label: null` 统一解释为“尚未定级”。** 计划等级合同及 Task 3 目前存在这一规则。`katrain/web/api/v1/endpoints/games.py:52`、`:74` 和 `katrain/web/api/pvp_spectator.py:72`、`:81` 都用 `labels.get(rung)`；该字典来自 `pvp_lobby_bots.py:26` 的 `playable_rungs()`，只含有 recipe、certified 且 available 的档位。已定级用户的档位不在这个集合、机器人元数据缺失等情况也会得到 null。最小修正是采用按来源明确的语义：大厅/观战的空、缺失、null label 均为“等级未知”；仅明确的 AI-ladder `placement_state.phase === 'placement'` 等有证据的未定级状态可显示“尚未定级”。不要为这件事新增中央发布依赖或用 rung/default/profile 猜标签。增加一个“非 null rung + null label → 未知”的聚焦用例，并覆盖空白 label。

2. **P1 — `rank_owner` 资格必须随真实棋局来源变化，不能只依赖账号、mode 和当前 Player 配置。** 最新 Task 2 已修正账号 ID，但仍有实际未覆盖路径：`interface.py:1258` 的 `_do_load_sgf` 调用 `_do_new_game(move_tree=...)`；后者默认设为 free、保留现有玩家类型，`server.py:1576` 的加载入口没有将原 play 会话改成 research。因此已登录的单真人 AI 会话加载别人的 SGF 后仍满足计划的 owner 条件，会误贴当前账号等级。另 `session.py:120` 的 `create_research_session` 在 `create_session` 已启动并生成 `last_state` 后才改 mode；若仅事后修改新属性，初始响应可能仍携带旧 owner。要求计划明确：资格在首次状态生成前确定；所有 SGF/研究来源清除资格及已缓存的 owner；新的真实私有 AI 开局才能重新建立资格；`create_multiplayer_session` 不继承私有 AI 资格，不能靠暂时的玩家类型碰巧排除；匿名后续管理认领继续不赋资格。测试至少覆盖 play→load_sgf、research 首个返回的 last_state、多人/平台排除、有效私有 AI 的黑/白席位。复用现有模式/来源信息或极小的单局标志即可，无需通用身份框架。

已核实可行的部分：

- 几何公式正确。直线段为 `xL=232.5-y/6`、`xR=22.5-y/6`，差值 210；两卡宽 C、组宽 G 时，水平路径间隔确为 `G-(74/39)C`。25%/50%/75% 高度均落在直线段内。原 AI 的 G=460、C=238 得约 8.4103px，采用 8.4px 目标合理。描边后的 6.9px 只是近似，依实际宽度缩放与截图测量验收；无需 ResizeObserver。
- 复用共享 SVG、仅统一几何、保留各页面黑白顺序/高度/时钟来源的方案与当前需求相称。星阵观战从 97px 到 104px 的局部调整需在已有视觉验收内检查剩余内容高度，不需要新测试基础设施。
- 邀请/大厅复用现有 active-games 接口可行，strict box 的 `rewrite_active_games` 确实为本人重写 local session_id；不必新增中央端点。
- 独立平台 B/W 等级字段及 SGF BR/WR 透传是合理的小型契约补充；平台等级必须从已验证棋局席位取得，默认 15、AI level fallback、姓名匹配均不可作为真人依据。

非阻塞建议，建议本次修订一并写清：

- 大厅的 8 秒截止、前台不快于每 30 秒、单请求及旧响应丢弃足够。账号 AI-ladder 等级也应明确相同的截止/取消规则，以及进入页面、身份/棋局/席位变更、恢复可见、权威结算后如何刷新；不要因每次 gameState 更新请求。现有 `useAiLadderStatus` 为阻塞页设计，含 15 秒后台复查且失败保留旧数据，直接复用不符合本计划“错误为未知”的合同。优先一个小 hook 调既有 `getAiLadderStatus`，不要建立新的缓存或轮询框架。
- 新 owner 状态必须在渲染时按身份与棋局 scope 校验，不能只在 effect 中清空，否则身份切换可能短暂显示前一个人的等级。平台恢复同一棋局时，即使着数没有变化，也要按最新验证结果更新或清空等级。
- 平台验收明确覆盖 OGS 新建及 `_restore_ogs_snapshot`，以及独立的 `start_engine_game` 星阵路径。星阵仅真实 `level_row.level_name` 能成为 AI 等级；既有 `AI-{level}` 名称回落即使在 AI 席也不能当作已知等级。
- Task 2/3 最终列出实际采用的测试文件与命令即可，例如既有 `tests/test_baipu_load.py`、`tests/web_ui/test_ogs_platform_game_bridge.py` 及对应页面/面板 Vitest；不需要把所有实现代码写进计划，也不需要全仓测试。SGF、平台、账号内部数值应按来源分别解释，不修改共享 `rankUtils` 而意外改变 Galaxy。

上述两项属于真实数据语义与归属边界，需在计划层闭合。其余范围和分工可继续保持现有规模。第 2 轮只需核查修订及其相关影响，不重复扩张审核范围。
