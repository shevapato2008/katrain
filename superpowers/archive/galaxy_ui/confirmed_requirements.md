# Galaxy Go UI - 已确认需求

> 日期: 2026-01-20
> 状态: ✅ 已确认并实施中
> 相关文档: [风险分析](./risk_analysis.md) | [问题追踪](./open_questions.md)
> 实施进度: 同步自 `conductor/tracks/galaxy_ui_20260119/plan.md`

---

## 产品决策 (最新确认)

### 1. AI级别体系
- **决策**: 使用 **Human-like AI** (20k - 9D) 进行定级和升降对局。
- **说明**: 该AI拥有完善的级别体系 (20k...1D...9D)，适合作为标准参考。其他AI策略（如Ky/Dan等）作为娱乐模式保留。
- **影响**: RatingPage 和 Rated Game 必须调用 Human-like AI 引擎。
- **实现**: `katrain/web/core/ranking.py` ✅

### 2. 道具系统
- **决策**: **不限制使用次数**。
- **说明**: 优先保证功能可用性。UI上可以按照星阵风格分类展示（领地/支招/变化图），但不做扣费或次数限制逻辑。
- **实现**: 复用现有KaTrain功能 ✅

### 3. 对局类型
- **决策**: 区分 **Free (自由对局)** 和 **Rated (升降对局)**。
- **说明**:
  - **Rated**: 结果影响用户段位，用于定级，影响人人对弈匹配。
  - **Free**: 娱乐性质，不计分。
- **UI**: 需在对弈菜单中明确区分入口或选项。
- **实现**: `games.game_type` 字段 ✅

### 4. 积分/计费系统
- **决策**: **预留Credits系统**，暂不收费。
- **实现**:
  - UI显示积分余额 ✅
  - 初始给用户10000 Credits ✅
  - 后端: `users.credits` 字段 ✅

### 5. 棋谱库与社交
- **决策**: **完整版 (Cloud SGF + 社交)**。
- **实现**:
  - **Cloud SGF**: 用户可保存棋谱到云端 ✅ (P3)
  - **Social**: 好友列表、关注功能 ⬜ (P5)
  - **后端**: PostgreSQL表已设计 ✅

### 6. 快捷键
- **决策**: 保持 **KaTrain 默认配置**。
- **说明**: 暂不对齐星阵快捷键，后续视需求调整。
- **实现**: 复用现有 `useKeyboardShortcuts` hook ✅

---

## 现有功能继承

| 功能 | 决策 | 状态 |
|------|------|------|
| 研究模式访问 | **需要登录** | ✅ AuthGuard 已实现 |
| 新旧UI并存 | **并存** | ✅ `/galaxy/*` 路由前缀 |
| 观战功能 | **P5实现** | ⬜ WebSocket 广播待开发 |

---

## 数据库设计 (PostgreSQL) ✅ IMPLEMENTED

基于确认的决策，已实现以下数据表 (`katrain/postgres/init.sql`):

### users 表
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    rank VARCHAR(10) DEFAULT '20k',      -- 段位 (20k-9D)
    net_wins INTEGER DEFAULT 0,          -- 净胜场数
    elo_points INTEGER DEFAULT 0,        -- ELO积分
    credits NUMERIC(15, 2) DEFAULT 10000.00,  -- 积分
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### games 表
```sql
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    black_player_id INTEGER REFERENCES users(id),
    white_player_id INTEGER REFERENCES users(id),
    winner_id INTEGER REFERENCES users(id),
    sgf_content TEXT,                    -- SGF棋谱内容
    result VARCHAR(50),                  -- 对局结果
    game_type VARCHAR(20) DEFAULT 'free', -- 'free' or 'rated'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE
);
```

### relationships 表
```sql
CREATE TABLE relationships (
    follower_id INTEGER REFERENCES users(id),
    following_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, following_id)
);
```

### rating_history 表
```sql
CREATE TABLE rating_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    old_rank VARCHAR(10),
    new_rank VARCHAR(10),
    elo_change INTEGER DEFAULT 0,
    game_id INTEGER REFERENCES games(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 索引
```sql
CREATE INDEX idx_games_black ON games(black_player_id);
CREATE INDEX idx_games_white ON games(white_player_id);
CREATE INDEX idx_relationships_follower ON relationships(follower_id);
```

---

## 路由规划 ✅ IMPLEMENTED

```
# 原有UI
/                       → 现有 App.tsx (Zen Mode) ✅

# Galaxy UI
/galaxy                 → Dashboard ✅
/galaxy/play            → PlayMenu (选择 AI/Human, Free/Rated) ✅
/galaxy/play/ai/setup   → AiSetupPage (AI配置) ✅
/galaxy/play/ai/game    → GamePage (对弈) ✅
/galaxy/play/human      → HumanVsHumanLobby (人人大厅) ⬜
/galaxy/research        → ResearchPage (云端棋谱/本地SGF) ✅
/galaxy/profile         → UserProfile (积分/好友/历史棋谱) ⬜
```

---

## 已实现的组件/文件

### 前端 (katrain/web/ui/src/galaxy/)

| 路径 | 描述 | 状态 |
|------|------|------|
| `components/layout/MainLayout.tsx` | 主布局壳 | ✅ |
| `components/layout/GalaxySidebar.tsx` | 侧边栏导航 | ✅ |
| `components/auth/LoginModal.tsx` | 登录弹窗 | ✅ |
| `components/guards/AuthGuard.tsx` | 路由保护 | ✅ |
| `components/research/CloudSGFPanel.tsx` | 云端棋谱面板 | ✅ |
| `components/game/RightSidebarPanel.tsx` | 游戏右侧栏 | ✅ |
| `context/AuthContext.tsx` | 认证状态管理 | ✅ |
| `pages/Dashboard.tsx` | 首页 | ✅ |
| `pages/PlayMenu.tsx` | 对弈模式选择 | ✅ |
| `pages/AiSetupPage.tsx` | AI配置页 | ✅ |
| `pages/GamePage.tsx` | 对弈界面 | ✅ |
| `pages/ResearchPage.tsx` | 研究模式 | ✅ |
| `hooks/useGameSession.ts` | 游戏会话管理 | ✅ |

### 后端 (katrain/web/)

| 路径 | 描述 | 状态 |
|------|------|------|
| `core/ranking.py` | 排名系统 | ✅ |
| `core/game_repo.py` | 对局数据访问 | ✅ |
| `core/models_db.py` | 数据库模型 | ✅ |
| `api/v1/endpoints/games.py` | 对局API | ✅ |

### 数据库

| 路径 | 描述 | 状态 |
|------|------|------|
| `katrain/postgres/init.sql` | 数据库初始化 | ✅ |

---

## P4 待修复Bug清单 🐛

### Bug #1: 缺少规则集选择
| 项目 | 内容 |
|------|------|
| 位置 | `AiSetupPage.tsx` |
| 当前行为 | 只有贴目(Komi)选择，无规则类型选项 |
| 期望行为 | 添加 Rules 下拉框 |
| 支持规则 | Japanese, Chinese, Korean, AGA, Tromp-Taylor, New Zealand, Ancient Chinese |
| 参考 | KaTrain桌面版截图 |
| 优先级 | **高** |

### Bug #2: 让子(Handicap)未生效
| 项目 | 内容 |
|------|------|
| 位置 | `AiSetupPage.tsx` → `GamePage.tsx` |
| 当前行为 | 设置Handicap=2，进入游戏棋盘空白 |
| 期望行为 | 棋盘上预置让子石（星位） |
| 技术要求 | 前端传递handicap参数，后端game初始化时放置让子 |
| 参考 | KaTrain桌面版让子逻辑 |
| 优先级 | **高** |

### Bug #3: 计时器显示错误
| 项目 | 内容 |
|------|------|
| 位置 | `PlayerCard.tsx` / `GamePage.tsx` |
| 当前行为 | 显示 `600:00` (原始秒数，格式混乱) |
| 期望行为 | 分三行显示: |
|  | - Main Time: `10:00` (分:秒) |
|  | - Byo-yomi: `30s` |
|  | - Periods: `5` (剩余读秒次数) |
| 优先级 | **高** |

### Bug #4: AI段位显示为内部数值
| 项目 | 内容 |
|------|------|
| 位置 | `PlayerCard.tsx` |
| 当前行为 | 显示 `(-19)`, `(-9)`, `(10)` |
| 期望行为 | 显示人类可读段位 |
| 映射规则 | `-19` → `20k`, `-9` → `10k`, `0` → `1d`, `9` → `9d` |
| 中文显示 | `20k (20级)`, `9d (9段)` |
| 需要 | 创建 `rankToLabel()` 工具函数 |
| 优先级 | **高** |

### 影响范围
- Free Play Setup (`/galaxy/play/ai/setup`)
- Free Play Game (`/galaxy/play/ai/game`)
- Rated Game vs AI (相同页面)

---

## 新增需求: Rules选择器

### 支持的规则类型

| 规则名称 | 内部值 | 说明 |
|----------|--------|------|
| Japanese | `japanese` | 日本规则 (默认) |
| Chinese | `chinese` | 中国规则 |
| Korean | `korean` | 韩国规则 |
| AGA | `aga` | 美国围棋协会规则 |
| Tromp-Taylor | `tromp-taylor` | 逻辑规则 |
| New Zealand | `new-zealand` | 新西兰规则 |
| Ancient Chinese | `stone-scoring` | 古代中国规则 |

### UI设计
```
Board & Opponent
├── Board Size: [19x19 (Standard) ▼]
├── Your Color: [Black (First) ▼]
├── AI Strategy: [ai:human ▼]
├── Rules: [Japanese ▼]        ← 新增
├── Difficulty: [slider 20k ←→ 9d]
├── Handicap: [slider 0-9]
└── Komi: [slider 0.5-9.5]
```

---

## 新增需求: 段位映射工具

### 映射函数规格

```typescript
// galaxy/utils/rankUtils.ts

/**
 * 将KataGo内部段位值转换为人类可读标签
 * @param internalRank - KataGo内部段位值 (-19 到 9)
 * @param locale - 语言 ('en' | 'zh')
 * @returns 人类可读的段位标签
 *
 * 映射规则:
 *   -19 → "20k" (en) / "20k (20级)" (zh)
 *   -18 → "19k" (en) / "19k (19级)" (zh)
 *   ...
 *   -1  → "2k"  (en) / "2k (2级)" (zh)
 *   0   → "1d"  (en) / "1d (初段)" (zh)
 *   1   → "2d"  (en) / "2d (2段)" (zh)
 *   ...
 *   8   → "9d"  (en) / "9d (9段)" (zh)
 */
export function rankToLabel(internalRank: number, locale?: string): string;
```

---

## 新增需求: Timer显示重构

### PlayerCard布局更新

```
┌─────────────────────────────────┐
│ ● Black          [Rank Badge]   │
│ player:human                    │
│ ─────────────────────────────── │
│ Main Time:     10:00            │
│ Byo-yomi:      30s              │
│ Periods:       5                │
│ ─────────────────────────────── │
│ Captures: 0                     │
└─────────────────────────────────┘
```

### 时间格式规范

| 组件 | 格式 | 示例 |
|------|------|------|
| Main Time | `mm:ss` | `10:00`, `05:32` |
| Byo-yomi | `Ns` | `30s`, `60s` |
| Periods | 整数 | `5`, `3` |

---

## 开发进度总览

| 阶段 | 描述 | 状态 | 关键Commit |
|------|------|------|------------|
| P1 | 基础架构 | ✅ COMPLETE | - |
| P1.5 | 数据库设计 | ✅ COMPLETE | 747d659 |
| P2 | 首页+认证 | ✅ COMPLETE | 4a8b6b2, 38e6428 |
| P3 | 研究模式 | ✅ COMPLETE | 681814f, 64b83a4 |
| P4 | 人机对弈 | 🔄 IN PROGRESS (4 Bugs) | - |
| P5 | 人人对弈 | ⬜ NOT STARTED | - |
| P6 | i18n+优化 | ⬜ NOT STARTED | - |

---

## 下一步

1. **P4 Bug修复**:
   - [ ] Bug #1: 添加Rules选择器到AiSetupPage
   - [ ] Bug #2: 修复Handicap让子初始化逻辑
   - [ ] Bug #3: 重构PlayerCard计时器显示
   - [ ] Bug #4: 实现rankToLabel()段位映射
2. **P5开始**: 人人对弈大厅、匹配、房间系统
3. **持续**: 单元测试覆盖
