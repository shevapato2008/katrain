# Galaxy Go UI - 已确认需求

> 日期: 2026-01-20
> 状态: 已确认
> 相关文档: [风险分析](./risk_analysis.md)

---

## 产品决策 (最新确认)

### 1. AI级别体系
- **决策**: 使用 **Human-like AI** (20k - 9D) 进行定级和升降对局。
- **说明**: 该AI拥有完善的级别体系 (20k...1D...9D)，适合作为标准参考。其他AI策略（如Ky/Dan等）作为娱乐模式保留。
- **影响**: RatingPage 和 Rated Game 必须调用 Human-like AI 引擎。

### 2. 道具系统
- **决策**: **不限制使用次数**。
- **说明**: 优先保证功能可用性。UI上可以按照星阵风格分类展示（领地/支招/变化图），但不做扣费或次数限制逻辑。

### 3. 对局类型
- **决策**: 区分 **Free (自由对局)** 和 **Rated (升降对局)**。
- **说明**: 
  - **Rated**: 结果影响用户段位，用于定级，影响人人对弈匹配。
  - **Free**: 娱乐性质，不计分。
- **UI**: 需在对弈菜单中明确区分入口或选项。

### 4. 积分/计费系统
- **决策**: **预留Credits系统**，暂不收费。
- **实现**:
  - UI显示积分余额。
  - 初始给用户无限或大额Credits。
  - **后端**: 需基于 PostgreSQL 设计 `user_credits` 表。

### 5. 棋谱库与社交
- **决策**: **完整版 (Cloud SGF + 社交)**。
- **实现**:
  - **Cloud SGF**: 用户可保存棋谱到云端（数据库）。
  - **Social**: 好友列表、关注功能。
  - **后端**: 需基于 PostgreSQL 设计 `games`, `sgf_records`, `relationships` 等表。

### 6. 快捷键
- **决策**: 保持 **KaTrain 默认配置**。
- **说明**: 暂不对齐星阵快捷键，后续视需求调整。

---

## 现有功能继承

| 功能 | 决策 | 备注 |
|------|------|------|
| 研究模式访问 | **需要登录** | AuthGuard 保护 |
| 新旧UI并存 | **并存** | `/galaxy/*` 路由前缀 |
| 观战功能 | **P5实现** | WebSocket 广播 |

---

## 数据库需求 (PostgreSQL)

基于确认的决策，需要设计以下数据表支持：

1.  **Users**: 基础信息, 当前段位 (rank), 积分 (credits).
2.  **Games**: 对局记录 (player_black, player_white, result, type: free/rated, sgf_content).
3.  **Relationships**: 社交关系 (follower_id, following_id).
4.  **RatingHistory**: 段位变动历史.

---

## 路由规划

```
# 原有UI
/                   → 现有 App.tsx (Zen Mode)

# Galaxy UI
/galaxy             → Dashboard
/galaxy/play        → PlayMenu (选择 AI/Human, Free/Rated)
/galaxy/play/setup  → GameSetup (AI配置/匹配设置)
/galaxy/play/room/:id → GameRoom (对弈)
/galaxy/research    → ResearchPage (云端棋谱/本地SGF)
/galaxy/profile     → UserProfile (积分/好友/历史棋谱)
```