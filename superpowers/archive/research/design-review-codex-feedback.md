## 总体评价
两级架构方向合理，但核心状态流和数据模型尚缺稳健性：L1 本地棋盘与 L2 服务器棋盘的同步/分支处理不完备，`useGameSession` 复用假设对弈场景，数据库与 API 迁移缺少兼容方案与权限约束，Phase 顺序也存在上线风险。需要先补齐这些基础安全网再推进实现。

## 关键问题（必须修复）
1. L1→L2 状态一致性风险 → 当前用 `moves[]` 序列化为 SGF，未覆盖“拖动改位、连续同色摆子、提前插手、让子先置”等非线性编辑；Legacy Board 期望合法顺序着法，可能在加载时丢手或复现错误。建议：序列化时支持 SGF `AB/AW/AE` 置子与 `PL` 标记，明确初始行棋方与让子；对拖动改位应转换为清除 + 置子；进入 L2 前做一次本地 SGF 解析-回放校验，失败则阻止进入分析。
2. L2→L1 回填 moves 可能不可靠 → `GameState` 在对弈模式常只保留最近窗口（受 max_moves、review buffer 等限制），且可能包含 engine 追加的虚拟结尾节点；直接提取可能丢历史或顺序错位。建议：为研究 session 请求全量历史或在 session 创建时显式禁用截断；若服务器仍截断，需同时返回完整 SGF 或 position hash 以便重建。
3. `useGameSession` 复用未验证 → Hook 里含有对弈特有逻辑（轮到谁走、自动推进、对局状态枚举、计时），研究模式需要自由摆子和分支，可能触发非法 turn 校验或自动发送落子事件。必须在接入前审查 hook，拆分出纯分析版或增加 feature flag，禁用对弈专属副作用（计时、对局结束判定、自动提交 actual move）。
4. 分支/盘面存储缺口 → `user_game_analysis` 以 `(game_id, move_number)` 唯一，无法表示用户在研究中从中途分支（不同变体共享 move_number），也不能保存盘面片段分析。需增加 `variation_id`（或 `position_hash`/`parent_move_id`）字段并调整唯一索引 `(game_id, variation_id, move_number)`；API 亦需接受/返回该标识。
5. 数据迁移与 rating 关联不明确 → 直接 `DROP games` 会破坏现有对弈/直播依赖；人人对弈生成两条 `user_games` 时，`rating_history.game_id` 指向哪一条未定义，可能导致积分双写或缺失。应先保留旧表只读、提供迁移脚本与回滚方案；为 rating 选择单一 canonical 记录（新增 `match_id` 共用，rating 指向 match 层）。
6. 访问控制未定义 → `/api/v1/user-games` 与分析接口未明确鉴权/授权策略；若漏检 user_id，用户可读写他人棋谱或分析数据。必须在 handler 层强制 `WHERE user_id = current_user.id`，删除和分析访问同样验证；公共棋谱需单独只读路径。
7. Session 生命周期与资源释放 → 设计只在“返回编辑”断开 WebSocket，若用户关闭标签/刷新，后端 session 可能泄漏，影响 KataGo 资源。需在 session 创建时设置超时 + 心跳，后端定期清理孤儿 session，前端在 `beforeunload`/`visibilitychange` 发送 `DELETE /sessions/{id}`。

## 改进建议（推荐但非必须）
1. 棋谱去重与元数据 → `user_games` 增加 `checksum`/`hash`, `event/date/round/tags`, `thumbnail` 字段，列表查询可用元数据而非全文 SGF，节省传输与存储重复。
2. 分析结果字段对齐 → 明确 `winrate` 以黑方为基准，并存储 `score_mean`, `score_stdev`, `visits`；Top moves 建议结构化列化为表（visits/wr/score/pv_len）以便筛选与排序。
3. API 批量与分页 → 列表 GET 需分页/排序参数，DELETE/GET 允许批量 id（限制上限）；分析 GET 可支持 `?moves=10,20,30` 批量拉取，减少往返。
4. UI 路由可加 query state → 仍保持单路由，但使用 `?mode=analyze` 并在 history state 写入，解决刷新/分享链接时恢复正确 Level；同时在进入分析后屏蔽浏览器返回键导致的空白页问题。
5. 工具栏状态机清晰化 → 对每个按钮定义可用条件和互斥关系（如移动/删除模式与连续摆子模式互斥），在 L2 中对会触发新分支的操作给出提示并生成新的 `variation_id`。
6. SGF 导入/保存健壮性 → 支持多变体、花子、含注释的 SGF；导入时对超大 SGF（>1k 手）警告，并校正规则/贴目与 SGF 元数据差异；保存时在前端先跑一次 `sgf -> moves -> sgf` round-trip 以确保可还原。

## 遗漏补充
1. 与直播/对弈的交互 → 若直播/对弈仍依赖旧 `games` 表或旧 API，需列出受影响模块与替换计划，避免上线后其他功能崩溃。
2. 并发/锁定场景 → 同一棋谱多人或多标签编辑时的冲突策略未定义；建议采用乐观锁（`updated_at` 比对）或版本号，保存冲突时提示用户另存为。
3. 前端性能与离线 → 大 SGF 的 LiveBoard 计算可能卡顿；可在 L1 使用 Web Worker 计算提子/合法性；同时考虑离线模式（本地存储）并在恢复时提示是否同步到服务器。
4. 测试计划缺失 → 需要列出关键用例：让子/贴目一致性、分支往返、超长对局、刷新恢复、权限绕过、session 泄漏。

## Phase 优化建议
- 调整顺序与切分：先做 Phase 0：`useGameSession` 审核与轻量 POC，验证 L1↔L2 SGF 往返和 session 生命周期；再做 Phase 1 数据迁移但保留旧表只读并 behind feature flag；Phase 3/4 可并行开发 UI 骨架，Phase 5 在 POC 通过后衔接；Phase 6（棋谱库）应在 API 与权限稳定后再启用；Phase 7/8 依赖迁移完成并完成回滚脚本。
- MVP 范围建议锁定：L1 编辑 + L2 分析（单分支）+ 手动导入/本地保存 + 基础分析展示；暂不持久化分析、不联动 rating，待稳定后再开启。
