# 研究模块重构设计文档

**日期**: 2026-02-01
**状态**: 待实现
**版本**: v2（已整合 Gemini / Codex 审核意见）
**参考**: 星阵围棋"研究"模块 (`superpowers/tracks/research/xingzhen-research-module.md`)

---

## 1. 功能概述

### 1.1 功能目标

重构 KaTrain Galaxy 的研究模块，实现类似星阵围棋的两级页面架构：

- **Level 1（研究准备）**：纯前端棋盘编辑，不涉及任何 KataGo 计算。用户可自由摆棋、导入 SGF、设置规则参数。
- **Level 2（AI 分析）**：在 Level 1 给定的棋局基础上启动 KataGo 分析，提供完整的 AI 推荐、胜率走势、妙手/问题手标注。

### 1.2 核心特性

| 特性 | 说明 |
|------|------|
| 两级页面 | 同一路由内通过状态切换，无页面跳转 |
| 多种摆子模式 | 黑白交替、连续摆黑、连续摆白 |
| 棋盘编辑工具 | 手数显示、停一手、移动棋子、删除棋子、清空棋盘 |
| 棋谱加载 | 本地 SGF 上传 + 棋谱库模态框（个人棋谱/个人盘面/公共棋谱） |
| 棋谱保存 | 保存到本地（SGF 下载）+ 保存到数据库（个人棋谱库） |
| 完整 AI 分析 | hints、ownership、eval、走势图、妙手/问题手 |
| 分析数据持久化 | `user_game_analysis` 表存储每步分析结果 |

### 1.3 不包含

- 计时收费功能
- 停止计算功能
- Policy 热力图
- 多变体分支分析（MVP 后考虑）

---

## 2. 页面架构

### 2.1 路由设计

单路由 `/galaxy/research`，通过 `isAnalyzing` 状态变量切换两个 Level。支持 query parameter 用于深度链接。

```
/galaxy/research                       → Level 1（空棋盘）
/galaxy/research?game_id=xxx           → Level 1（自动加载指定棋谱）
/galaxy/research?game_id=xxx&analyze=1 → 直接进入 Level 2 分析
```

使用 `history.replaceState` 在切换 Level 时更新 URL query，解决刷新/分享链接恢复问题。进入 L2 后 push 一个 history entry，防止浏览器返回键导致空白页。

```
ResearchPage (isAnalyzing: boolean)
├── isAnalyzing = false → Level 1（LiveBoard + 设置面板）
└── isAnalyzing = true  → Level 2（Legacy Board + 分析面板）
```

### 2.2 Level 1：研究准备

#### 布局

```
┌──────────────────────────────────┬──────────────────┐
│                                  │                  │
│       棋盘区域 (LiveBoard)        │  ① 对局信息      │
│                                  │    PB/PW 棋手名   │
│   19路棋盘，支持自由落子/编辑      │    提子数         │
│   点击空位 = 落子                 │                  │
│   支持多种摆子模式                │  ② 规则设置      │
│                                  │    棋盘大小       │
│                                  │    规则(中/日)    │
│                                  │    让子           │
│                                  │    贴目           │
│                                  │                  │
│                                  │  ③ 工具栏        │
│                                  │   (见下方详述)    │
│──────────────────────────────────│                  │
│  底部工具栏                       │                  │
│  [导航按钮] [手数 N/M]           │  ④ [开始研究]    │
│                                  │    (绿色,固定底部) │
└──────────────────────────────────┴──────────────────┘
```

#### 工具栏按钮（图标按钮网格，参考星阵布局）

第一行（摆子编辑）：

| 按钮 | 功能 | 互斥关系 |
|------|------|---------|
| 手数 | 切换棋盘上手数标记的显隐 | 无（toggle） |
| 停一手 | 在当前位置插入一个 pass | 无（即时动作） |
| 移动 | 进入移动模式，拖拽棋子到新位置 | 与删除、摆子模式互斥 |
| 删除 | 进入删除模式，点击棋子删除 | 与移动、摆子模式互斥 |
| 摆黑 | 切换为连续摆黑棋模式 | 与移动、删除互斥；摆黑/摆白/交替三选一 |
| 摆白 | 切换为连续摆白棋模式 | 同上 |
| 交替 | 切换为黑白交替模式（默认） | 同上 |

第二行（棋谱操作 + 分析开关）：

| 按钮 | 功能 | L1 状态 | L2 状态 |
|------|------|---------|---------|
| hints | 显示/隐藏 AI 推荐点 | 置灰 | 激活 |
| 领地 | 显示/隐藏 ownership | 置灰 | 激活 |
| 清空 | 清空棋盘所有棋子 | 激活 | 激活 |
| 打开▲ | 下拉菜单：从本地打开 / 从棋谱库打开 | 激活 | 激活 |
| 保存▲ | 下拉菜单：保存到本地 / 保存到棋谱库 | 激活 | 激活 |

#### 棋谱库模态框

点击"从棋谱库打开"时弹出全屏模态框：

```
┌────────────────────────────────────────────────┐
│  棋谱库                                    [X]  │
│                                                 │
│  [上传棋谱]    ┌──────────────────────────────┐ │
│                │ 搜索框                       │ │
│  ▸ 我的棋谱    ├──────────────────────────────┤ │
│  ▸ 我的盘面    │ 棋谱列表                     │ │
│  ▾ 公共棋谱    │ 赛事|手数|规则  黑方 结果 白方│ │
│    大赛棋谱    │ ...                          │ │
│                │                              │ │
│                │ 分页: 1 2 3 ... N            │ │
│                └──────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

左侧分类树：
- **我的棋谱** → `user_games` 表，`category = "game"`
- **我的盘面** → `user_games` 表，`category = "position"`
- **公共棋谱 > 大赛棋谱** → 现有 `kifu_albums` API

#### Board 技术方案

使用 `LiveBoard` 组件（客户端模式）：
- 维护本地 `moves: string[]` 数组
- 浏览器端 `buildBoardState()` 计算棋盘状态（含提子逻辑）
- 不创建后端 session，不连接 WebSocket，不启动 KataGo

### 2.3 Level 2：AI 分析

#### 布局

```
┌──────────────────────────────────┬──────────────────┐
│  "研究模式"            [返回编辑] │                  │
│                     (棋盘右上角)  │  ① 对局信息+胜率条│
│                                  │    黑白胜率进度条  │
│       棋盘区域 (Legacy Board)     │                  │
│                                  │  ② 工具栏        │
│   占满左侧全部空间               │    (与 L1 一致)   │
│   显示 KataGo 分析结果：          │                  │
│   - AI 推荐点（hints）           │  ③ 分析面板       │
│   - ownership 领地               │   (AnalysisPanel) │
│   - eval 评价点                  │    Top moves 列表 │
│                                  │    详细变化文字   │
│   用户可继续落子 + 编辑棋盘       │                  │
│                                  │  ④ 走势图区域     │
│                                  │   [走势图][妙手]  │
│                                  │   [问题手] Tab    │
│                                  │                  │
│                                  │  ⑤ 导航栏        │
│                                  │  ⏮⏪⏩⏭ N/M手   │
└──────────────────────────────────┴──────────────────┘
```

#### 棋盘区域

- 左侧纯粹只放棋盘，不放底部工具栏或走势图，最大化棋盘尺寸
- 棋盘右上角显示"返回编辑"按钮（参考对弈模块的"退出"按钮位置）
- 左上角显示"研究模式"标题

#### 右侧面板

从上到下：

1. **对局信息 + 胜率条**：黑白棋手信息、胜率进度条、胜率百分比
2. **工具栏**：与 Level 1 完全一致的按钮网格（同一个组件），L1 中 `[hints]` `[领地]` 置灰，L2 中激活
3. **分析面板** (AnalysisPanel)：Top moves 列表（坐标、推荐度、子差、胜率）+ 详细变化文字
4. **走势图区域**：三个 Tab 切换
   - 走势图：胜率/目数双轴曲线，可点击跳转
   - 妙手：妙手列表，标注等级，点击跳转
   - 问题手：问题手列表，附胜率变化，点击跳转
5. **导航栏**：⏮ ⏪ ⏩ ⏭ + 手数显示 N/M

#### Board 技术方案

使用 Legacy `Board` 组件 + `useResearchSession` hook（见 2.5 节）：
- 从服务端接收 `GameState`（含完整分析数据）
- WebSocket 实时推送 KataGo 分析结果
- 支持 `analysisToggles`：`hints`, `ownership`, `eval`, `coords`, `numbers`
- 不支持 `policy`（已排除）

### 2.4 状态转换

#### L1 → L2（点击"开始研究"）

```
1. 前端将棋盘状态序列化为 SGF 字符串（见 2.6 节 SGF 序列化策略）
2. 在本地做一次 SGF 解析-回放校验，失败则阻止进入并提示错误
3. 冻结 L1 的 moves[] 快照（保存到 frozenMoves 状态中）
4. 调用 POST /api/v1/sessions，传入 SGF + mode="research"
5. 设置 isAnalyzing = true，更新 URL query
6. useResearchSession hook 连接 WebSocket
7. 后端创建 research session，加载 SGF，开始分析
8. 棋盘从 LiveBoard 切换到 Legacy Board
9. 右侧面板从设置模式切换到分析模式
```

#### L2 → L1（点击"返回编辑"）

```
1. 断开 WebSocket 连接
2. 前端发送 DELETE /api/v1/sessions/{id} 释放后端资源
3. 设置 isAnalyzing = false，更新 URL query
4. 从 frozenMoves 快照恢复 LiveBoard 状态（不从 GameState 反推）
5. 棋盘从 Legacy Board 切换回 LiveBoard
6. 右侧面板从分析模式切换回设置模式
```

**关键决策**：L2 返回 L1 时，恢复进入 L2 前的 L1 快照，而不是从 GameState 反向提取 moves。原因：
- GameState 可能不包含完整的编辑历史（移动、删除等非线性操作）
- GameState 可能受 max_moves 截断或包含虚拟节点
- 用户在 L2 的任何落子/编辑都是临时的分析行为，如需保留应使用"保存"功能

### 2.5 useResearchSession hook（新增）

`useGameSession` 为对弈设计，包含 turn 校验、计时、对局结束判定等对弈专有逻辑，不适合直接复用。需新建 `useResearchSession` hook。

**与 `useGameSession` 的区别**：

| 功能 | useGameSession | useResearchSession |
|------|---------------|-------------------|
| Turn 校验 | 严格轮流 | 禁用，允许自由落子 |
| 计时 | 支持 | 不支持 |
| 对局结束判定 | 支持 | 不支持 |
| 自动 AI 落子 | 支持 | 不支持 |
| 棋盘编辑指令 | 不支持 | 支持（set_stones, remove_stones） |
| Session 模式 | mode="play" | mode="research" |

**实现策略**：从 `useGameSession` 提取公共部分（WebSocket 连接、GameState 管理、导航）到 `useSessionBase`，然后分别扩展：

```
useSessionBase（公共：WS 连接、state 管理、导航）
├── useGameSession（对弈专有：turn、timer、game end）
└── useResearchSession（研究专有：自由编辑、无 turn 限制）
```

**后端对应变更**：session 创建时接受 `mode` 参数。`mode="research"` 的 session 禁用 turn 校验和对局结束判定，允许 `set_stones` / `remove_stones` 指令。

### 2.6 SGF 序列化策略

L1 的棋盘状态可能包含非线性编辑（连续同色、移动、删除），不能简单地将 `moves[]` 拼接为顺序着法。

**序列化规则**：

1. **标准交替落子**：直接生成 `;B[xx];W[yy]` 序列
2. **连续同色落子**：使用 SGF `AB[xx][yy]` / `AW[xx][yy]` 置子语法
3. **让子/初始布局**：生成 `AB[...]` 节点 + `PL[W]` 标记先行方
4. **移动棋子**：转换为 `AE[原位]` + `AB/AW[新位]`（清除 + 置子）
5. **删除棋子**：生成 `AE[xx]`

**校验流程**：进入 L2 前，在前端做一次 `SGF → buildBoardState → 比对当前棋盘` 的 round-trip 校验。不一致则阻止进入分析并提示用户。

### 2.7 Session 生命周期管理

KataGo session 是重量级资源，必须确保可靠释放：

| 触发 | 动作 |
|------|------|
| 点击"返回编辑" | 前端 DELETE session + 断开 WS |
| 关闭/刷新页面 | `beforeunload` 事件发送 `navigator.sendBeacon(DELETE session)` |
| 页面不可见 5 分钟 | `visibilitychange` 事件触发释放（可选） |
| 后端心跳超时 | 后端定期检查 WS 心跳，超时 60s 无心跳自动释放 session |
| 后端启动时 | 清理所有孤儿 session（status=running 但无 WS 连接） |

---

## 3. 数据库设计

### 3.1 概述

删除旧的 `games` 表，新建 `user_games` + `user_game_analysis` 两张表。`rating_history` 的 `game_id` FK 改为指向 `user_games`。

### 3.2 `user_games` 表

统一的个人棋谱库，承载对弈记录、导入棋谱、研究盘面。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| user_id | INT | FK → users.id, NOT NULL | 所有者 |
| title | VARCHAR(255) | | 棋谱标题 |
| sgf_content | TEXT | | 完整 SGF 内容 |
| player_black | VARCHAR(100) | | 黑方名称（字符串） |
| player_white | VARCHAR(100) | | 白方名称（字符串） |
| result | VARCHAR(50) | NULLABLE | 对局结果 |
| board_size | INT | DEFAULT 19 | 棋盘大小 |
| rules | VARCHAR(20) | DEFAULT 'chinese' | 规则：chinese / japanese / ... |
| komi | FLOAT | DEFAULT 7.5 | 贴目 |
| move_count | INT | DEFAULT 0 | 手数 |
| source | VARCHAR(50) | NOT NULL | 来源：play_ai / play_human / import / research |
| category | VARCHAR(50) | DEFAULT 'game' | 分类：game / position |
| game_type | VARCHAR(50) | NULLABLE | 对弈类型：free / rated / null(非对弈) |
| sgf_hash | VARCHAR(64) | NULLABLE | SGF 内容 SHA-256，用于去重检测 |
| event | VARCHAR(255) | NULLABLE | 赛事名称（从 SGF EV 字段提取） |
| game_date | DATE | NULLABLE | 对局日期（从 SGF DT 字段提取） |
| created_at | TIMESTAMP | DEFAULT now() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT now() | 更新时间 |

**索引**：
- `user_id` (查询用户棋谱)
- `(user_id, category)` (按分类筛选)
- `(user_id, source)` (按来源筛选)
- `created_at` (时间排序)
- `sgf_hash` (去重检测)

### 3.3 `user_game_analysis` 表

逐手分析数据，结构与 `live_analysis` 对齐。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO | 主键 |
| game_id | UUID | FK → user_games.id, NOT NULL | 关联棋谱 |
| move_number | INT | NOT NULL | 手数（0=空盘） |
| status | VARCHAR(16) | DEFAULT 'pending' | pending / running / success / failed |
| priority | INT | DEFAULT 10 | 优先级 |
| winrate | FLOAT | NULLABLE | 黑方胜率 0-1 |
| score_lead | FLOAT | NULLABLE | 黑方领先目数 |
| visits | INT | NULLABLE | KataGo 搜索次数 |
| top_moves | JSON | NULLABLE | [{move, visits, winrate, score_lead, prior, pv}, ...] |
| ownership | JSON | NULLABLE | 领地数据 |
| actual_move | VARCHAR(8) | NULLABLE | 实战着手 |
| actual_player | VARCHAR(1) | NULLABLE | B / W |
| delta_score | FLOAT | NULLABLE | 目数变化 |
| delta_winrate | FLOAT | NULLABLE | 胜率变化 |
| is_brilliant | BOOLEAN | DEFAULT false | 妙手 |
| is_mistake | BOOLEAN | DEFAULT false | 问题手 |
| is_questionable | BOOLEAN | DEFAULT false | 疑问手 |
| error_message | TEXT | NULLABLE | 失败原因 |
| created_at | TIMESTAMP | DEFAULT now() | |
| updated_at | TIMESTAMP | DEFAULT now() | |

**索引**：
- `(game_id, move_number)` UNIQUE（每步只有一条分析，MVP 阶段不支持多变体）
- `(status, priority)` (任务队列查询)

**关于 `live_analysis` 与 `user_game_analysis` 合并**：两位审核者均建议合并为通用分析表。考虑到：
- `live_analysis` 已在生产运行且与 cron job/poller 深度耦合
- 合并需要同时改动直播和研究两个模块
- 测试阶段优先降低改动范围

**决策**：MVP 阶段保持分开，后续在直播模块重构时统一合并为 `game_analysis` 表（通过 `source_type` + `source_id` 多态关联）。

### 3.4 `rating_history` 表变更

人人对弈产生两条 `user_games` 记录时，rating 只指向发起者（黑方）的那条记录：

```python
# 对弈结束时
black_game = create_user_game(user_id=black_player_id, ...)
white_game = create_user_game(user_id=white_player_id, ...)

# rating 统一指向黑方记录
create_rating_history(game_id=black_game.id, user_id=black_player_id, ...)
create_rating_history(game_id=black_game.id, user_id=white_player_id, ...)
```

```sql
ALTER TABLE rating_history
  DROP CONSTRAINT rating_history_game_id_fkey,
  ADD CONSTRAINT rating_history_game_id_fkey
    FOREIGN KEY (game_id) REFERENCES user_games(id);
```

### 3.5 删除 `games` 表

测试阶段无历史数据需要保留，直接删除：

```sql
DROP TABLE games;
```

**受影响模块排查**：

| 模块 | 依赖 `games` 表？ | 迁移方案 |
|------|------------------|---------|
| 对弈 (server.py game end) | 是，写入 games | 改写入 user_games |
| CloudSGFPanel | 是，读取 /api/v1/games/ | 改用 /api/v1/user-games |
| RatingHistory | 是，FK 到 games.id | FK 改指向 user_games.id |
| 直播模块 | 否 | 无影响 |
| 棋谱库 (kifu_albums) | 否 | 无影响 |

### 3.6 所有权模型

| 场景 | user_games 记录数 | 说明 |
|------|-------------------|------|
| 人机对弈 | 1 条 | user_id = 玩家 |
| 人人对弈 | 2 条 | 双方各一条，SGF 相同，user_id 不同 |
| 研究模块导入 SGF | 1 条 | user_id = 导入者，source = "import" |
| 研究模块保存 | 1 条 | user_id = 用户，source = "research" |
| 从棋谱库加载研究 | 不新增 | 直接引用原记录，用户主动"另存为"时才新增 |

**关于 SGF 冗余存储**：人人对弈时 SGF 存两份确实冗余，但测试阶段数据量极小，SGF 文本压缩后通常 < 10KB。范式化（拆分为 game_records + user_library_entries 两张表）增加复杂度，收益不大。如未来用户量增长导致存储问题，再做范式化重构。

---

## 4. API 设计

### 4.1 个人棋谱 API（新增）

所有端点需要 JWT 认证，handler 层强制 `WHERE user_id = current_user.id`。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/user-games` | GET | 列表查询（分页、排序、按 category/source 筛选、关键词搜索） |
| `/api/v1/user-games` | POST | 保存棋谱 |
| `/api/v1/user-games/{id}` | GET | 获取详情（含 SGF） |
| `/api/v1/user-games/{id}` | PUT | 更新（重命名、覆盖保存），使用乐观锁（比对 updated_at） |
| `/api/v1/user-games/{id}` | DELETE | 删除 |

**列表查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| page | INT | 页码，默认 1 |
| page_size | INT | 每页条数，默认 20，最大 100 |
| category | STRING | 筛选分类：game / position |
| source | STRING | 筛选来源：play_ai / play_human / import / research |
| sort | STRING | 排序：created_at_desc (默认) / created_at_asc / move_count_desc |
| q | STRING | 关键词搜索（匹配 title、player_black、player_white、event） |

**列表响应不包含 sgf_content**（节省传输），仅在 GET detail 时返回。

### 4.2 分析数据 API（新增）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/user-games/{id}/analysis` | GET | 获取分析数据（支持分页：`?start_move=0&limit=50`） |
| `/api/v1/user-games/{id}/analysis/{move}` | GET | 获取指定手数的分析 |

**权限**：同样强制校验 `user_games.user_id = current_user.id`。

### 4.3 现有 API 变更

| 端点 | 变更 |
|------|------|
| `/api/v1/games/` | 废弃，前端改用 `/api/v1/user-games` |
| Session 创建 API | 增加 `mode` 参数（"play" / "research"） |

---

## 5. 前端组件设计

### 5.1 文件结构

```
katrain/web/ui/src/galaxy/
├── pages/
│   └── ResearchPage.tsx              # 重构：两级页面主组件
├── components/
│   └── research/
│       ├── ResearchToolbar.tsx        # 工具栏（L1/L2 共用）
│       ├── ResearchSetupPanel.tsx     # L1 右侧面板（对局信息+规则+工具栏+开始按钮）
│       ├── ResearchAnalysisPanel.tsx  # L2 右侧面板（信息+工具栏+分析+走势图+导航）
│       ├── GameLibraryModal.tsx       # 棋谱库全屏模态框
│       ├── SaveGameDialog.tsx         # 保存棋谱对话框
│       └── CloudSGFPanel.tsx          # 废弃，功能并入 GameLibraryModal
├── hooks/
│   ├── useSessionBase.ts             # 公共：WS 连接、GameState、导航
│   ├── useGameSession.ts             # 重构：继承 useSessionBase，对弈专有逻辑
│   ├── useResearchSession.ts         # 新增：继承 useSessionBase，研究专有逻辑
│   └── useResearchBoard.ts           # L1 本地棋盘状态管理 hook
├── utils/
│   └── sgfSerializer.ts              # 新增：moves[] ↔ SGF 双向转换 + 校验
```

### 5.2 状态管理

```typescript
// ResearchPage 顶层状态
interface ResearchPageState {
  // 模式切换
  isAnalyzing: boolean;

  // Level 1 状态（本地棋盘）
  moves: string[];           // 着法序列
  currentMove: number;       // 当前浏览位置
  placeMode: 'alternate' | 'black' | 'white';  // 摆子模式
  editMode: 'place' | 'move' | 'delete' | null; // 编辑模式
  frozenMoves: string[] | null;  // 进入 L2 时的快照，用于 L2→L1 恢复

  // 规则参数
  boardSize: number;
  rules: string;             // 'chinese' | 'japanese'
  komi: number;
  handicap: number;

  // 对局信息
  playerBlack: string;
  playerWhite: string;

  // Level 2 状态（复用 useResearchSession）
  sessionId: string | null;
  gameState: GameState | null;

  // 分析 toggles
  analysisToggles: {
    hints: boolean;
    ownership: boolean;
    eval: boolean;
    coords: boolean;
    numbers: boolean;
  };
}
```

### 5.3 组件层级

```
ResearchPage
├── [L1] LiveBoard + ResearchSetupPanel
│   ├── PlayerInfo
│   ├── RulesConfig
│   ├── ResearchToolbar（共用组件）
│   └── StartResearchButton
│
└── [L2] Board (Legacy) + ResearchAnalysisPanel
    ├── "返回编辑" button (棋盘右上角)
    ├── PlayerInfo + WinrateBar
    ├── ResearchToolbar（同一组件，分析按钮激活）
    ├── AnalysisPanel (Legacy)
    ├── TrendTabs（走势图 / 妙手 / 问题手）
    └── NavigationBar
```

---

## 6. 后端模块变更

### 6.1 文件结构

```
katrain/web/
├── core/
│   ├── models_db.py          # 修改：删除 Game，新增 UserGame + UserGameAnalysis
│   ├── game_repo.py          # 重构：改为操作 user_games 表
│   └── ranking.py            # 不变
├── api/v1/endpoints/
│   ├── games.py              # 废弃或重构为 user_games.py
│   └── user_games.py         # 新增：个人棋谱 CRUD + 分析数据 API
├── session.py                # 修改：支持 mode="research" 的 session 创建
```

### 6.2 后端 research session

在 session 创建时接受 `mode` 参数：

```python
# mode="research" 时：
# - 禁用 turn 校验（允许任意颜色落子）
# - 禁用对局结束判定
# - 禁用计时器
# - 允许 set_stones / remove_stones 指令
# - 请求 KataGo 分析时返回全量历史（不截断）
```

### 6.3 对弈模块联动

对弈结束时（`server.py` 中的 game end handler）：
- 写入 `user_games`（source = "play_ai" 或 "play_human"）
- 人人对弈：为双方各创建一条记录
- rated 对弈：同时写入 `rating_history`（`game_id` 统一指向黑方的 user_games 记录）

---

## 7. 错误处理

| 场景 | 处理方式 |
|------|---------|
| SGF 序列化校验失败 | 阻止进入 L2，显示错误提示 toast |
| Session 创建失败 | 保持 L1 状态，显示错误提示 |
| WebSocket 断线 | UI 显示"连接已断开"状态条 + 自动重连（3次，指数退避） |
| 保存到数据库失败 | 显示错误提示，提供"保存到本地"作为 fallback |
| 保存冲突（乐观锁） | 提示用户"棋谱已被修改"，提供"覆盖"/"另存为"选项 |
| 权限不足 | 返回 403，前端提示"无权访问该棋谱" |
| SGF 导入格式错误 | 显示解析错误详情，不加载到棋盘 |

---

## 8. 实现阶段

### Phase 0：POC 验证（前置） ✅ 完成

验证核心技术风险：
1. ✅ 审查 `useGameSession` hook，确认可拆分为 `useSessionBase` + 对弈/研究两个扩展
2. ✅ 验证 L1→L2 的 SGF 序列化-回放 round-trip（含连续同色、移动、删除等非线性编辑）
3. ✅ 验证后端 session 支持 mode="research"（禁用 turn 校验）
4. ✅ 验证 session 生命周期管理（心跳、超时清理）

### Phase 3：前端 Level 1 ✅ 完成

LiveBoard + 摆子工具栏 + 规则设置 + SGF 序列化 + 开始研究按钮

### Phase 4：前端 Level 2 ✅ 完成

- ✅ Legacy Board + useResearchSession + 导航栏
- ✅ 分析优化（见 8.1 节补充）
- ✅ 分析面板数据集成（AI推荐表、走势图、妙手/问题手）
- ✅ 分析进度条（batched scan + progress polling + gated L2 view）
- ✅ 自动播放（1s/手）+ 落子音效
- ✅ 全主线 history（导航后不丢失总手数）
- ✅ 关闭 eval 圆点（研究模式默认不显示）

### Phase 5：L1↔L2 状态转换 ✅ 完成

frozenMoves 快照、session 创建/释放、Board 切换、深度链接（kifu_id）

### Phase 1-8：完整进度

| 阶段 | 内容 | 依赖 | 状态 |
|------|------|------|------|
| **Phase 0** | POC 验证 | - | ✅ 完成 |
| **Phase 1** | 数据库迁移：新建 user_games + user_game_analysis，删除 games，修改 rating_history FK | Phase 0 | ✅ 完成 |
| **Phase 2** | 后端 API：user_games CRUD（含权限校验、乐观锁、分页）+ 分析数据端点 | Phase 1 | ✅ 完成 |
| **Phase 3** | 前端 Level 1：LiveBoard + 摆子工具栏 + 规则设置 + SGF 序列化 + 开始研究按钮 | Phase 0 | ✅ 完成 |
| **Phase 4** | 前端 Level 2：Legacy Board + useResearchSession + 分析面板 + 走势图/妙手/问题手 + 导航栏 + 进度条 + 自动播放 + 音效 | Phase 0, 3 | ✅ 完成 |
| **Phase 5** | L1↔L2 状态转换：frozenMoves 快照、session 创建/释放、Board 切换、深度链接 | Phase 3, 4 | ✅ 完成 |
| **Phase 6** | 棋谱库模态框 + 保存功能（本地下载 + 剪贴板复制）；云端保存/加载推迟 | Phase 2, 3 | ✅ MVP 完成 |
| **Phase 7** | 对弈模块联动：game end 写入 user_games，废弃旧 games 表和 API | Phase 2 | ✅ 完成 |
| **Phase 8** | 分析数据持久化：研究过程中将分析结果写入 user_game_analysis | Phase 2, 4 | ⏳ 待开始 |

### 8.1 分析优化（计划外补充，2026-02-02 实施）

原计划未考虑的性能问题：加载 100+ 手棋局后点击"开始研究"，后端 `Game.__init__()` → `analyze_all_nodes()` 会同时发送所有节点的分析请求，导致 KataGo 超时。

**已实施的优化策略**：

1. **`skip_initial_analysis` 标志**（`katrain/core/game.py`）：`Game.__init__()` 新增参数，research session 加载 SGF 时跳过批量分析
2. **参数透传链路**：`_do_load_sgf()` → `_do_new_game()` → `WebGame()` → `Game()` 全链路传递 `skip_initial_analysis`
3. **`/api/sgf/load` 端点**（`katrain/web/server.py`）：新增 `skip_analysis` 请求参数
4. **批量分析 + 进度条**（最终方案，替代了早期的"低 visits 后台扫描 + 按需深度分析"方案）：
   - **`/api/analysis/scan` 端点**：以 `batch_size=10` 分批分析主线所有节点，每批 500 visits，等待一批完成后再发送下一批，避免引擎过载
   - **`/api/analysis/progress` 端点**（GET）：返回 `{analyzed, total}` 统计主线节点分析进度
   - **前端进度条**：L2 入口为全屏加载页（"正在分析棋局"），每 1s 轮询 progress，显示 `已完成 X / Y 步` + 百分比进度条
   - **分析完成门控**：仅当 `analyzed >= total` 时才显示 L2 分析界面，确保用户首次看到的所有 AI 推荐都是准确的
5. **全主线 history**（`interface.py get_state()`）：history 始终返回完整主线（root → 最深第一子节点），`current_node_index` 标记当前位置，解决导航后滑块/走势图数据丢失问题
6. **自动播放 + 音效**（`ResearchAnalysisPanel.tsx`）：1s/手的 autoplay interval + 每次导航播放 `stone1.wav`
7. **关闭 eval 圆点**（`ResearchPage.tsx`）：`analysisToggles.eval = false`，研究模式默认不显示棋子上的评价圆点

**涉及文件**：

| 文件 | 变更 |
|------|------|
| `katrain/core/game.py` | `Game.__init__()` 增加 `skip_initial_analysis` 参数 |
| `katrain/web/interface.py` | `_do_new_game()`、`_do_load_sgf()` 透传参数；新增 `_do_analysis_scan()`（批量分批扫描）；新增 `_do_analysis_progress()`（主线进度统计）；`get_state()` 返回全主线 history |
| `katrain/web/server.py` | `/api/sgf/load` 增加 `skip_analysis`；新增 `/api/analysis/scan` 和 `/api/analysis/progress` 端点 |
| `katrain/web/models.py` | `LoadSGFRequest` 增加 `skip_analysis`；新增 `AnalysisScanRequest` |
| `katrain/web/ui/src/api.ts` | 新增 `analysisScan()`、`analysisProgress()` |
| `katrain/web/ui/src/galaxy/hooks/useResearchSession.ts` | `createSession()` 增加 `skipAnalysis`/`initialMove` 选项 |
| `katrain/web/ui/src/galaxy/pages/ResearchPage.tsx` | 三态 L2 渲染（进度条 → 完成 → L1）；进度轮询；分析完成门控 |
| `katrain/web/ui/src/galaxy/components/research/ResearchAnalysisPanel.tsx` | 自动播放 interval + 导航音效 |

**性能数据**（HTTP KataGo 引擎，500 visits/node，batch_size=10）：

| 棋局规模 | 预估耗时 |
|---------|---------|
| 10 手 | ~25s |
| 100 手 | ~3 min |
| 200 手 | ~6 min |
| 250 手 | ~7.5 min |

### 8.2 Phase 7 对弈模块联动（2026-02-02 实施）

删除旧 `Game` 模型和 `GameType` 枚举，将多人对弈记录迁移至 `UserGame` 模型。

**已完成的变更**：

1. **删除 `Game` 模型**（`models_db.py`）：移除旧 games 表模型和 `GameType` 枚举
2. **更新 `RatingHistory.game_id`**：从 `Integer FK(games.id)` 改为 `String(32) FK(user_games.id)`
3. **重写 `GameRepository`**（`game_repo.py`）：新增 `record_multiplayer_game()` 方法，为黑白双方各创建一条 `UserGame` 记录，并处理 rated 对局的段位计算
4. **更新 server.py**：resign/timeout/leave 端点改用 `record_multiplayer_game()`
5. **更新 `auth.py`**：`count_completed_rated_games()` 改查 `UserGame` 表
6. **精简 `games.py`**：只保留 `GET /active/multiplayer`（活跃对局列表），移除旧 CRUD 端点
7. **数据库自动迁移**：`init_db()` 检测到旧 `games` 表时自动 DROP 并重建 `rating_history`
8. **剪贴板复制**（Phase 6 补充）：研究模块工具栏"保存"菜单新增"复制 SGF 到剪贴板"功能

| 文件 | 变更 |
|------|------|
| `katrain/web/core/models_db.py` | 删除 `Game` 模型和 `GameType` 枚举；`RatingHistory.game_id` 改为 String(32) FK user_games |
| `katrain/web/core/game_repo.py` | 重写为 `record_multiplayer_game()` + `count_completed_rated_games()` |
| `katrain/web/core/auth.py` | `count_completed_rated_games()` 改查 UserGame；`init_db()` 自动迁移旧表 |
| `katrain/web/server.py` | resign/timeout/leave 改用 `record_multiplayer_game()` |
| `katrain/web/api/v1/endpoints/games.py` | 仅保留 `GET /active/multiplayer` |
| `katrain/web/ui/src/galaxy/hooks/useResearchBoard.ts` | 新增 `copyToClipboard()` |
| `katrain/web/ui/src/galaxy/components/research/ResearchToolbar.tsx` | "复制 SGF 到剪贴板"菜单项连线 |

### MVP 范围

**MVP = Phase 0 ~ 7 已全部完成**。剩余 Phase 8（分析数据持久化）为 MVP 后续工作。

MVP 完成范围：
- Phase 0-5: 核心研究流程（L1 摆棋 → L2 分析 → 返回编辑）
- Phase 6: 本地 SGF 打开/下载/剪贴板复制（云端保存/加载推迟）
- Phase 7: 对弈模块联动（game end 写入 user_games）
- Phase 8 分析持久化：MVP 后实施，当前分析为会话级别，关闭即丢失

### 并行开发

```
Track 1 (后端): Phase 0 → Phase 1 → Phase 2 → Phase 7
Track 2 (前端): Phase 0 → Phase 3 → Phase 4 → Phase 5 → Phase 6
                         (可用 Mock API 并行)
```

---

## 9. 审核意见处理记录

| # | 来源 | 问题 | 处理 |
|---|------|------|------|
| 1 | Gemini/Codex | L2→L1 状态恢复数据丢失风险 | 采纳：使用 frozenMoves 快照恢复，不从 GameState 反推（2.4 节） |
| 2 | Gemini/Codex | useGameSession 复用兼容性 | 采纳：新建 useResearchSession hook + useSessionBase 公共层（2.5 节） |
| 3 | Codex | L1→L2 SGF 序列化未覆盖非线性编辑 | 采纳：定义完整序列化规则 + round-trip 校验（2.6 节） |
| 4 | Codex | Session 生命周期泄漏 | 采纳：心跳 + beforeunload + 孤儿清理（2.7 节） |
| 5 | Codex | 访问控制未定义 | 采纳：所有 API 强制 user_id 校验（4.1 节） |
| 6 | Gemini | 深度链接 | 采纳：支持 query parameter（2.1 节） |
| 7 | Codex | 分支/盘面存储缺口 | 延迟：MVP 不支持多变体，后续增加 variation_id |
| 8 | Gemini | user_games 所有权冗余 | 延迟：测试阶段数据量小，暂不范式化（3.6 节说明） |
| 9 | Gemini | live_analysis 与 user_game_analysis 合并 | 延迟：MVP 保持分开，直播重构时统一（3.3 节说明） |
| 10 | Gemini | 分析 API 分页 | 采纳：增加 start_move + limit 参数（4.2 节） |
| 11 | Codex | rating_history 双写 | 采纳：统一指向黑方记录（3.4 节） |
| 12 | Codex | 数据迁移风险 | 采纳：列出受影响模块（3.5 节） |
| 13 | Codex | 工具栏互斥关系 | 采纳：定义按钮互斥规则（2.2 节工具栏表格） |
| 14 | Gemini/Codex | Phase 优化 | 采纳：增加 Phase 0 POC + 定义 MVP 范围（8 节） |
| 15 | Codex | 棋谱去重 | 采纳：增加 sgf_hash 字段（3.2 节） |
| 16 | Codex | 分析结果增加 visits | 采纳：增加 visits 字段（3.3 节） |
| 17 | Gemini/Codex | 错误处理 | 采纳：新增第 7 节错误处理 |
| 18 | Codex | 保存冲突 | 采纳：乐观锁 + updated_at 比对（4.1 节） |
| 19 | Codex | 元数据字段 | 采纳：增加 event、game_date 字段（3.2 节） |
