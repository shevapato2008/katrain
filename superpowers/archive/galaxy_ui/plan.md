# Galaxy Go UI - 详细实施计划 (Superpowers版)

> **项目目标**: 构建一个对标星阵围棋(19x19.com)的现代化围棋Web应用
> **设计理念**: 延续现有Zen Mode风格 + 渐进式功能扩展
> **技术栈**: React 19 + TypeScript + React Router v6 + Material-UI v7
> **相关文档**: [已确认需求](./confirmed_requirements.md) | [风险分析](./risk_analysis.md) | [待确认问题](./open_questions.md)
> **实施进度**: 同步自 `conductor/tracks/galaxy_ui_20260119/plan.md`

---

## 已确认的产品决策

| 决策项 | 结论 | 备注 |
|--------|------|------|
| 研究模式访问 | **需要登录** | AuthGuard 已实现 |
| AI定级系统 | **Human-like AI (20k-9D)** | 用于定级和升降对局 |
| 观战功能 | **P5一起实现** | WebSocket广播 |
| 新旧UI共存 | **并存，路由隔离** | `/galaxy/*` 前缀 |
| 道具系统 | **不限制使用次数** | 按星阵风格分类展示 |
| 对局类型 | **Free + Rated** | 升降战影响段位 |
| 计费系统 | **Credits预留** | 暂不收费，10000初始积分 |
| 好友系统 | **完整版** | 关注+好友列表 |
| 棋谱库 | **Cloud SGF + 社交** | 已实现 |
| 快捷键 | **保持KaTrain默认** | 后续按需调整 |

---

## 项目概览

### 功能范围

| 模块 | 优先级 | 状态 | 说明 |
|------|--------|------|------|
| 首页Dashboard | P0 | ✅ 完成 | 模块卡片展示 |
| 研究模式 | P0 | ✅ 完成 | 自由摆棋+AI分析+Cloud SGF (需登录) |
| 人机对弈 | P0 | ✅ 完成 | AI设置+对局 (后端完成，前端修复完成) |
| AI定级 | P0 | ✅ 完成 | Ranking系统后端完成 |
| 人人对弈 | P1 | ⬜ 待开发 | 匹配/房间/观战 |
| 报告模式 | P2 | ⬜ 灰色占位 | 暂不实现 |
| 直播模式 | P2 | ⬜ 灰色占位 | 暂不实现 |
| 其他模块 | P3 | ⬜ 灰色占位 | 死活题/特训/课程等 |

### 现有资产复用

| 组件 | 复用方式 | 状态 |
|------|----------|------|
| Board.tsx | 直接复用 | ✅ |
| AnalysisPanel.tsx | 直接复用 | ✅ |
| ScoreGraph.tsx | 直接复用 | ✅ |
| PlayerCard.tsx | 直接复用 | ✅ |
| ControlBar.tsx | 样式调整 | ✅ |
| MUI Theme | 提取为theme.ts | ✅ |
| API层 | 直接复用 | ✅ |
| i18n系统 | 直接复用 | ✅ |

### 路由架构 (已实现)

```text
# 原有UI (保持不变)
/                         → 现有 App.tsx (Zen Mode)

# Galaxy UI (新增，/galaxy 前缀)
/galaxy                   → Dashboard (首页) ✅
/galaxy/play              → PlayMenu (对弈模式选择) ✅
/galaxy/play/ai/setup     → AISetupPage (AI配置) ✅
/galaxy/play/ai/game      → GamePage (人机对弈) ✅
/galaxy/play/human        → HumanVsHumanLobby (人人对弈大厅) ⬜
/galaxy/play/human/room/:id → GameRoom (对弈房间) ⬜
/galaxy/research          → ResearchPage (研究模式，需登录) ✅
/galaxy/settings          → SettingsPage (设置页) ⬜
```

---

## Phase 1: 基础架构与设计系统 ✅ COMPLETE

**目标**: 建立路由、布局结构，复用现有设计系统
**状态**: 已完成
**Checkpoint**: p1_structure, p1_theme, p1_layout

### 1.1 项目结构重组 ✅

- [x] 创建Galaxy UI目录结构:
  ```
  katrain/web/ui/src/galaxy/
  ├── components/
  │   ├── layout/
  │   │   ├── MainLayout.tsx      # 主布局壳
  │   │   └── GalaxySidebar.tsx   # 新侧边栏
  │   ├── auth/
  │   │   └── LoginModal.tsx      # 登录弹窗
  │   ├── guards/
  │   │   └── AuthGuard.tsx       # 路由保护
  │   ├── research/
  │   │   └── CloudSGFPanel.tsx   # 云端棋谱面板
  │   └── game/
  │       └── RightSidebarPanel.tsx # 游戏右侧栏
  ├── context/
  │   └── AuthContext.tsx         # 认证状态
  ├── pages/
  │   ├── Dashboard.tsx           # 首页
  │   ├── PlayMenu.tsx            # 对弈选择
  │   ├── AiSetupPage.tsx         # AI配置
  │   ├── GamePage.tsx            # 对弈界面
  │   └── ResearchPage.tsx        # 研究模式
  ├── hooks/
  │   └── useGameSession.ts       # 游戏会话管理
  └── utils/
      └── (ranking utilities)     # 段位工具
  ```

- [x] 安装React Router v6

### 1.2 提取共享主题 ✅

- [x] 从App.tsx提取MUI主题到 `src/theme.ts`
- [x] 两套UI共享同一主题配置

### 1.3 路由配置 ✅

- [x] 创建 `GalaxyApp.tsx` 配置路由
- [x] 修改入口文件支持路由
- [x] 创建 `MainLayout.tsx` 布局壳

### 1.4 验收标准 ✅
- [x] 访问 `/galaxy` 显示Dashboard
- [x] 访问 `/` 显示原有Zen Mode UI
- [x] 两套UI共享相同的主题色彩

---

## Phase 1.5: 数据层 (PostgreSQL) ✅ COMPLETE

**目标**: 建立持久化数据存储
**状态**: 已完成
**Checkpoint**: p1_db_setup, p1_db_api (747d659)

### 1.5.1 数据库设计 ✅

- [x] PostgreSQL Docker配置 (`docker-compose.db.yml`)
- [x] 初始化脚本 (`katrain/postgres/init.sql`):
  ```sql
  -- users: 用户信息、段位、积分
  CREATE TABLE users (
      id SERIAL PRIMARY KEY,
      username VARCHAR(255) UNIQUE NOT NULL,
      hashed_password TEXT NOT NULL,
      rank VARCHAR(10) DEFAULT '20k',
      net_wins INTEGER DEFAULT 0,
      elo_points INTEGER DEFAULT 0,
      credits NUMERIC(15, 2) DEFAULT 10000.00,
      ...
  );

  -- games: 对局记录
  CREATE TABLE games (
      id SERIAL PRIMARY KEY,
      black_player_id INTEGER REFERENCES users(id),
      white_player_id INTEGER REFERENCES users(id),
      game_type VARCHAR(20) DEFAULT 'free', -- 'free' or 'rated'
      sgf_content TEXT,
      ...
  );

  -- relationships: 社交关系
  CREATE TABLE relationships (
      follower_id INTEGER REFERENCES users(id),
      following_id INTEGER REFERENCES users(id),
      ...
  );

  -- rating_history: 段位变动历史
  CREATE TABLE rating_history (...);
  ```

- [x] 后端API实现 (User Profile, Cloud SGF CRUD)

---

## Phase 2: 首页与认证系统 ✅ COMPLETE

**目标**: 完成Dashboard和用户登录/注册流程
**状态**: 已完成
**Checkpoint**: p2_auth (4a8b6b2), p2_sidebar (38e6428), p2_dashboard

### 2.1 GalaxySidebar ✅

- [x] 实现侧边栏结构
- [x] 模块导航列表:
  - 对弈 (可用)
  - 研究 (可用，需登录)
  - 报告 (灰色禁用)
  - 直播 (灰色禁用)
- [x] 底部语言选择器
- [x] 底部登录/用户区域 (显示Credits/Rank)

### 2.2 AuthContext ✅

- [x] 创建认证状态Context
- [x] 集成现有 `/api/v1/auth/*` 端点
- [x] 支持token持久化 (localStorage)
- [x] 连接后端User Profile API (获取Credits/Rank)

### 2.3 LoginModal组件 ✅

- [x] 登录/注册表单
- [x] 已登录: 用户名+段位+积分显示

### 2.4 Dashboard首页 ✅

- [x] 模块卡片布局
- [x] 卡片状态: 可点击/灰色禁用
- [x] 点击跳转到对应路由

### 2.5 验收标准 ✅
- [x] 侧边栏导航完整
- [x] 登录/注册流程可用
- [x] Dashboard可访问，模块卡片显示正确

---

## Phase 3: 研究模式 ✅ COMPLETE

**目标**: 实现自由摆棋+AI分析功能
**状态**: 已完成
**Checkpoint**: p3_page, p3_cloud_sgf (681814f), 64b83a4

### 3.1 AuthGuard实现 ✅

- [x] 创建AuthGuard组件
- [x] 未登录时显示LoginReminder
- [x] 包裹ResearchPage路由

### 3.2 ResearchPage布局 ✅

- [x] 复用现有Board组件
- [x] 复用现有AnalysisPanel组件
- [x] 复用现有ScoreGraph组件
- [x] 配置选项面板

### 3.3 Cloud SGF集成 ✅

- [x] CloudSGFPanel组件
- [x] "My Games" 侧边面板 (从数据库获取)
- [x] "Save to Cloud" 功能
- [x] 加载SGF文件
- [x] 保存SGF文件
- [x] 棋谱导航

### 3.4 验收标准 ✅
- [x] 未登录访问/galaxy/research显示登录提示
- [x] 登录后可自由落子
- [x] AI分析正常显示
- [x] Cloud SGF加载/保存功能完整

---

## Phase 4: 人机对弈 ✅ COMPLETE

**目标**: 完整的人机对弈设置和游戏流程
**状态**: 已完成
**Checkpoint**: p4_backend ✅, p4_setup ✅, p4_game_ui ✅

### 4.1 Backend Ranking System ✅

- [x] 排名系统后端 (`katrain/web/core/ranking.py`)
- [x] 段位计算逻辑

### 4.2 PlayMenu页面 ✅

- [x] 人机对弈入口
- [x] 人人对弈入口 (跳转时检查定级)

### 4.3 AISetupPage - Bug修复 ✅

**已完成**:
- [x] 获取AI常量 `/api/v1/ai-constants`
- [x] AI策略/级别选择
- [x] 贴目 (Komi) 选择
- [x] 让子 (Handicap) 滑块UI
- [x] **Bug #1: 缺少规则集选择** 🐛
    - 添加规则集下拉框，支持 Japanese/Chinese/Korean/AGA/Tromp-Taylor/New Zealand/Ancient Chinese
- [x] **Bug #2: 让子未生效** 🐛
    - 修复Handicap让子初始化逻辑，后端在game初始化时正确放置让子石

### 4.4 GamePage - Bug修复 ✅

**已完成**:
- [x] 复用Board组件
- [x] 复用PlayerCard组件
- [x] 游戏控制栏
- [x] ITEMS面板 (Territory/Advice/Graph/Policy)
- [x] **Bug #3: 计时器显示错误** 🐛
    - 正确显示 Main Time, Byo-yomi, 和 Periods
- [x] **Bug #4: AI段位显示为内部数值** 🐛
    - 实现 `rankToLabel()` 段位映射工具

### 4.5 验收标准 ✅

**Setup页面**:
- [x] 可选择规则集 (Japanese/Chinese/Korean/AGA等)
- [x] Handicap设置后进入游戏能正确显示让子

**Game页面**:
- [x] PlayerCard正确显示: Main Time + Byo-yomi + Periods
- [x] AI段位显示为 `20k`/`10k`/`1d`/`9d` 而非内部数值
- [x] 人机对弈全流程正常
- [x] 对局可以正常结束

### 4.6 影响范围

以上Bug同时影响:
- `/galaxy/play/ai/setup` (Free Play Setup)
- Rated Game vs AI (如有单独页面)

---

## Phase 5: 人人对弈 (UI原型) ⬜ NOT STARTED

**目标**: 构建人人对弈界面原型
**状态**: 待开发

### 5.1 HumanVsHumanLobby

- [ ] 进行中对局列表 (观战入口)
- [ ] 在线玩家列表
- [ ] 快速匹配按钮

### 5.2 快速匹配流程

- [ ] 匹配等待动画
- [ ] 匹配成功跳转
- [ ] 取消匹配

### 5.3 房间系统UI

- [ ] 创建房间
- [ ] 加入房间
- [ ] 房间等待页面

### 5.4 GameRoom对弈界面

- [ ] 复用Board组件
- [ ] 对手信息显示
- [ ] 观战者数量显示
- [ ] 聊天区域 (可选)

### 5.5 观战模式

- [ ] 观战入口
- [ ] 只读棋盘显示
- [ ] 实时更新 (WebSocket)

### 5.6 验收标准
- [ ] 大厅UI可交互
- [ ] 房间系统UI完整
- [ ] (如后端就绪) 真实匹配和对弈

---

## Phase 6: 国际化与优化 ⬜ NOT STARTED

**目标**: 完善多语言支持和交互体验
**状态**: 待开发

### 6.1 i18n完善

- [ ] 收集所有新增文本
- [ ] 添加到i18n系统
- [ ] 验证9种语言显示

### 6.2 微交互优化

- [ ] 按钮悬停效果
- [ ] 页面切换过渡
- [ ] 加载状态动画

### 6.3 响应式适配

- [ ] 平板适配
- [ ] 侧边栏折叠
- [ ] 棋盘缩放

### 6.4 验收标准
- [ ] 所有文本支持多语言
- [ ] 交互流畅无明显卡顿
- [ ] 不同屏幕尺寸可用

---

## 里程碑

| 阶段 | 里程碑 | 状态 | Commit |
|------|--------|------|--------|
| P1 | 基础架构完成 | ✅ COMPLETE | - |
| P1.5 | 数据库设计 | ✅ COMPLETE | 747d659 |
| P2 | 首页上线 | ✅ COMPLETE | 4a8b6b2, 38e6428 |
| P3 | 研究模式可用 | ✅ COMPLETE | 681814f, 64b83a4 |
| P4 | 人机对弈完整 | ✅ COMPLETE | b1aeae7 |
| P5 | 人人对弈原型 | ⬜ NOT STARTED | - |
| P6 | 产品打磨 | ⬜ NOT STARTED | - |

---

## 已实现的文件清单

```
katrain/web/ui/src/galaxy/
├── components/
│   ├── layout/
│   │   ├── MainLayout.tsx
│   │   ├── GalaxySidebar.tsx
│   │   └── GalaxySidebar.test.tsx
│   ├── auth/
│   │   └── LoginModal.tsx
│   ├── guards/
│   │   └── AuthGuard.tsx
│   ├── research/
│   │   ├── CloudSGFPanel.tsx
│   │   └── CloudSGFPanel.test.tsx
│   └── game/
│       └── RightSidebarPanel.tsx
├── context/
│   ├── AuthContext.tsx
│   └── AuthContext.test.tsx
├── pages/
│   ├── Dashboard.tsx
│   ├── PlayMenu.tsx
│   ├── AiSetupPage.tsx
│   ├── GamePage.tsx
│   ├── ResearchPage.tsx
│   └── ResearchPage.test.tsx
├── hooks/
│   └── useGameSession.ts
└── utils/
    └── (pending)

katrain/postgres/
└── init.sql              # 数据库初始化脚本

katrain/web/core/
└── ranking.py            # 排名系统后端
```

---

## 下一步行动

1. **P4完成**: 修复AI Setup和Timer UI
2. **P5开始**: 人人对弈大厅和房间系统
3. **持续**: 单元测试覆盖
