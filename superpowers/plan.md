# Galaxy Go UI - 详细实施计划 (Superpowers版)

> **项目目标**: 构建一个对标星阵围棋(19x19.com)的现代化围棋Web应用
> **设计理念**: 延续现有Zen Mode风格 + 渐进式功能扩展
> **技术栈**: React 19 + TypeScript + React Router v6 + Material-UI v7
> **相关文档**: [已确认需求](./confirmed_requirements.md) | [风险分析](./risk_analysis.md) | [待确认问题](./open_questions.md)

---

## 已确认的产品决策

| 决策项 | 结论 | 备注 |
|--------|------|------|
| 研究模式访问 | **需要登录** | 与星阵一致 |
| AI定级系统 | **简化版: 3盘定级** | 自动计算初始段位 |
| 观战功能 | **P5一起实现** | WebSocket广播 |
| 新旧UI共存 | **并存，路由隔离** | `/galaxy/*` 前缀 |

## 待确认决策 (影响P4/P5)

| 决策项 | 选项 | 详见 |
|--------|------|------|
| AI级别体系 | 保持KaTrain现有 / 31级映射 / 简化5-10级 | open_questions.md #1 |
| 道具系统 | 不引入 / 人人对弈限次 / 保留但不限制 | open_questions.md #2 |
| 对局类型 | 统一处理 / 自由战+升降战 | open_questions.md #6 |

---

## 项目概览

### 功能范围

| 模块 | 优先级 | 状态 | 说明 |
|------|--------|------|------|
| 首页Dashboard | P0 | 待开发 | 模块卡片展示 |
| 研究模式 | P0 | 待开发 | 自由摆棋+AI分析 (需登录) |
| 人机对弈 | P0 | 待开发 | AI设置+对局 |
| AI定级 | P0 | **新增** | 3盘定级系统 |
| 人人对弈 | P1 | 待开发 | 匹配/房间/观战 |
| 报告模式 | P2 | 灰色占位 | 暂不实现 |
| 直播模式 | P2 | 灰色占位 | 暂不实现 |
| 其他模块 | P3 | 灰色占位 | 死活题/特训/课程等 |

### 现有资产复用

| 组件 | 复用方式 | 修改量 |
|------|----------|--------|
| Board.tsx | 直接复用 | 无 |
| AnalysisPanel.tsx | 直接复用 | 无 |
| ScoreGraph.tsx | 直接复用 | 无 |
| PlayerCard.tsx | 直接复用 | 无 |
| ControlBar.tsx | 样式调整 | 小 |
| MUI Theme | 提取为theme.ts | 小 |
| API层 | 直接复用 | 无 |
| i18n系统 | 直接复用 | 无 |

### 路由架构 (新旧并存)

```text
# 原有UI (保持不变)
/                         → 现有 App.tsx (Zen Mode)

# Galaxy UI (新增，/galaxy 前缀)
/galaxy                   → Dashboard (首页)
/galaxy/play              → PlayMenu (对弈模式选择)
/galaxy/play/ai           → HumanVsAI (人机对弈)
/galaxy/play/ai/setup     → AISetupPage (AI配置)
/galaxy/play/human        → HumanVsHumanLobby (人人对弈大厅)
/galaxy/play/human/room/:id → GameRoom (对弈房间)
/galaxy/research          → ResearchPage (研究模式，需登录)
/galaxy/rating            → RatingPage (AI定级)
/galaxy/settings          → SettingsPage (设置页)
```

---

## Phase 1: 基础架构与设计系统

**目标**: 建立路由、布局结构，复用现有设计系统

### 1.1 项目结构重组 [checkpoint: p1_structure]

- [ ] 创建Galaxy UI目录结构:
  ```
  katrain/web/ui/src/galaxy/
  ├── components/
  │   ├── layout/
  │   │   ├── MainLayout.tsx      # 主布局壳
  │   │   └── GalaxySidebar.tsx   # 新侧边栏
  │   ├── ui/
  │   │   ├── ModuleCard.tsx      # 首页模块卡片
  │   │   ├── LanguagePicker.tsx  # 语言选择器
  │   │   └── AuthSection.tsx     # 认证区域
  │   └── guards/
  │       └── AuthGuard.tsx       # 路由保护
  ├── context/
  │   ├── AuthContext.tsx         # 认证状态
  │   └── GameContext.tsx         # 游戏状态
  ├── pages/
  │   ├── Dashboard.tsx
  │   ├── PlayMenu.tsx
  │   ├── AISetupPage.tsx
  │   ├── HumanVsAI.tsx
  │   ├── HumanVsHumanLobby.tsx
  │   ├── GameRoom.tsx
  │   └── ResearchPage.tsx
  └── AppRouter.tsx               # 路由配置
  ```

- [ ] 安装React Router v6:
  ```bash
  cd katrain/web/ui && npm install react-router-dom@6
  ```

### 1.2 提取共享主题 [checkpoint: p1_theme]

- [ ] 从App.tsx提取MUI主题到 `src/theme.ts`
- [ ] 确保两套UI共享同一主题配置:
  ```typescript
  // src/theme.ts
  export const zenTheme = createTheme({
    palette: {
      mode: 'dark',
      primary: { main: '#4a6b5c' },
      background: { default: '#0f0f0f', paper: '#252525' },
      text: { primary: '#f5f3f0', secondary: '#b8b5b0' },
    },
    typography: { fontFamily: "'Manrope', sans-serif" },
    // ... 其他配置
  });
  ```

### 1.3 路由配置 [checkpoint: p1_routing]

- [ ] 创建 `AppRouter.tsx` 配置路由
- [ ] 修改入口文件支持路由
- [ ] 创建 `MainLayout.tsx` 布局壳

### 1.4 验收标准
- [ ] 访问 `/galaxy` 显示空白页面但路由正常
- [ ] 访问 `/` 显示原有Zen Mode UI
- [ ] 两套UI共享相同的主题色彩

---

## Phase 2: 首页与认证系统

**目标**: 完成Dashboard和用户登录/注册流程

### 2.1 GalaxySidebar [checkpoint: p2_sidebar]

- [ ] 实现侧边栏结构 (复用现有Sidebar样式)
- [ ] 模块导航列表:
  - 对弈 (可用)
  - 研究 (可用，需登录)
  - 报告 (灰色禁用)
  - 直播 (灰色禁用)
  - 更多模块占位...
- [ ] 底部语言选择器
- [ ] 底部登录/用户区域

### 2.2 AuthContext [checkpoint: p2_auth_context]

- [ ] 创建认证状态Context
- [ ] 集成现有 `/api/v1/auth/*` 端点
- [ ] 支持token持久化 (localStorage)

### 2.3 AuthSection组件 [checkpoint: p2_auth_ui]

- [ ] 未登录: 登录/注册按钮 (触发对话框)
- [ ] 已登录: 用户名+头像+下拉菜单

### 2.4 Dashboard首页 [checkpoint: p2_dashboard]

- [ ] 模块卡片布局 (2x3或响应式)
- [ ] 卡片状态: 可点击/灰色禁用
- [ ] 点击跳转到对应路由

### 2.5 验收标准
- [ ] 侧边栏导航完整
- [ ] 登录/注册流程可用
- [ ] Dashboard可访问，模块卡片显示正确

---

## Phase 3: 研究模式

**目标**: 实现自由摆棋+AI分析功能

### 3.1 AuthGuard实现 [checkpoint: p3_guard]

- [ ] 创建AuthGuard组件
- [ ] 未登录时显示LoginReminder (提示登录)
- [ ] 包裹ResearchPage路由

### 3.2 ResearchPage布局 [checkpoint: p3_layout]

- [ ] 复用现有Board组件
- [ ] 复用现有AnalysisPanel组件
- [ ] 复用现有ScoreGraph组件
- [ ] 配置选项面板 (贴目、规则等)

### 3.3 SGF操作 [checkpoint: p3_sgf]

- [ ] 加载SGF文件
- [ ] 保存SGF文件
- [ ] 棋谱导航 (复用ControlBar)

### 3.4 验收标准
- [ ] 未登录访问/galaxy/research显示登录提示
- [ ] 登录后可自由落子
- [ ] AI分析正常显示
- [ ] SGF加载/保存功能完整

---

## Phase 4: 人机对弈

**目标**: 完整的人机对弈设置和游戏流程

### 4.1 PlayMenu页面 [checkpoint: p4_menu]

- [ ] 人机对弈入口
- [ ] 人人对弈入口 (跳转时检查定级)

### 4.2 AISetupPage [checkpoint: p4_ai_setup]

- [ ] 获取AI常量 `/api/v1/ai-constants`
- [ ] AI策略/级别选择 (待确认：沿用KaTrain或新体系)
- [ ] 规则设置 (棋盘大小、贴目)
- [ ] 时间设置 (复用TimeSettingsDialog逻辑)
- [ ] 开始游戏按钮

### 4.3 HumanVsAI游戏界面 [checkpoint: p4_game]

- [ ] 复用Board组件
- [ ] 复用PlayerCard组件
- [ ] 游戏控制栏 (Pass, Resign, Undo)
- [ ] 对局结束处理 (显示结果，跳转报告)

### 4.4 AI定级流程 [checkpoint: p4_rating]

- [ ] RatingPage入口
- [ ] 3盘定级引导UI
- [ ] 定级结果显示
- [ ] 后端API对接 (如已实现)

### 4.5 验收标准
- [ ] 人机对弈全流程正常
- [ ] 对局可以正常结束
- [ ] 定级流程UI完整 (后端可Mock)

---

## Phase 5: 人人对弈 (UI原型)

**目标**: 构建人人对弈界面原型

### 5.1 HumanVsHumanLobby [checkpoint: p5_lobby]

- [ ] 进行中对局列表 (观战入口)
- [ ] 在线玩家列表 (Mock数据)
- [ ] 快速匹配按钮

### 5.2 快速匹配流程 [checkpoint: p5_match]

- [ ] 匹配等待动画
- [ ] 匹配成功跳转
- [ ] 取消匹配

### 5.3 房间系统UI [checkpoint: p5_room]

- [ ] 创建房间
- [ ] 加入房间 (输入房间号)
- [ ] 房间等待页面

### 5.4 GameRoom对弈界面 [checkpoint: p5_game_room]

- [ ] 复用Board组件
- [ ] 对手信息显示
- [ ] 观战者数量显示
- [ ] 聊天区域 (可选)

### 5.5 观战模式 [checkpoint: p5_spectate]

- [ ] 观战入口 (从大厅列表)
- [ ] 只读棋盘显示
- [ ] 实时更新 (WebSocket)

### 5.6 验收标准
- [ ] 大厅UI可交互 (Mock数据)
- [ ] 房间系统UI完整
- [ ] (如后端就绪) 真实匹配和对弈

---

## Phase 6: 国际化与优化

**目标**: 完善多语言支持和交互体验

### 6.1 i18n完善 [checkpoint: p6_i18n]

- [ ] 收集所有新增文本
- [ ] 添加到i18n系统
- [ ] 验证9种语言显示

### 6.2 微交互优化 [checkpoint: p6_micro]

- [ ] 按钮悬停效果
- [ ] 页面切换过渡
- [ ] 加载状态动画

### 6.3 响应式适配 [checkpoint: p6_responsive]

- [ ] 平板适配
- [ ] 侧边栏折叠
- [ ] 棋盘缩放

### 6.4 验收标准
- [ ] 所有文本支持多语言
- [ ] 交互流畅无明显卡顿
- [ ] 不同屏幕尺寸可用

---

## 里程碑

| 阶段 | 里程碑 | 验收标准 |
|------|--------|----------|
| P1 | 基础架构完成 | 路由可用、风格一致、主题提取 |
| P2 | 首页上线 | Dashboard+登录+侧边栏 |
| P3 | 研究模式可用 | 自由摆棋+AI分析+AuthGuard |
| P4 | 人机对弈完整 | 完整对局流程+定级UI |
| P5 | 人人对弈原型 | UI可交互(Mock或真实) |
| P6 | 产品打磨 | 多语言、响应式、微交互 |

---

## 依赖与阻塞分析

```
P1 基础架构
├── React Router v6 安装 [阻塞]
├── 主题提取 [阻塞P2]
└── 入口文件改造 [阻塞]

P2 首页+认证
├── AuthContext [阻塞P3]
├── GalaxySidebar [非阻塞]
└── Dashboard [非阻塞]

P3 研究模式
├── AuthGuard [阻塞，依赖AuthContext]
├── Board组件复用 [低风险]
└── SGF功能 [低风险]

P4 人机对弈
├── AI常量API [已有]
├── AI级别体系 [待确认，open_questions.md #1]
└── 定级API [需后端，可Mock]

P5 人人对弈
├── 大厅API [需后端，可Mock]
├── WebSocket房间 [需后端，可Mock]
├── 观战广播 [需后端，可Mock]
└── 道具系统 [待确认，open_questions.md #2]
```

---

## 下一步行动

1. **产品确认**: 请回答 `open_questions.md` 中的8个问题
2. **P1开始**: 安装React Router，创建目录结构
3. **技术验证**: P1阶段验证路由隔离和状态共享
