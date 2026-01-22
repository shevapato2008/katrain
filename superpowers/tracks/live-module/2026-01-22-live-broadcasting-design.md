# KaTrain Galaxy 直播功能设计文档

**日期**: 2026-01-22
**状态**: 已确认，待实现

---

## 1. 功能概述

### 1.1 功能目标

为 KaTrain Galaxy Web UI 添加直播功能模块，支持：
- 实时观看职业围棋比赛（数据源：XingZhen 星阵围棋）
- 回顾近期重要比赛棋谱（数据源：中国围棋协会）
- 本地 KataGo 引擎实时分析，标注妙手/问题手
- 查看即将进行的赛事预告

### 1.2 核心特性

| 特性 | 说明 |
|------|------|
| 双数据源 | XingZhen（实时直播）+ weiqi.org.cn（近期棋谱） |
| 本地分析 | 使用 KaTrain KataGo 引擎，不依赖第三方分析 |
| PV 推演 | 悬停显示 AI 预测变化图（可配置步数/速度） |
| 妙手/问题手 | 基于目数变化自动标注，悬停显示原因 |
| 赛事预告 | 定期爬取整合多来源赛事信息 |
| 评论系统 | 直播时显示评论区，用户可登录发言 |

### 1.3 不包含（MVP 范围外）

- 棋友赛事/业余比赛
- 评论审核功能（后续实现）
- 棋手头像获取
- 发挥水准指标
- 停一手、研究、分享功能

---

## 2. 数据源 API

### 2.1 XingZhen 星阵围棋

**基础 URL**: `https://api.19x19.com/api/engine/golives`

| 端点 | 说明 |
|------|------|
| `GET /all` | 所有正在直播的比赛 |
| `GET /count` | 直播比赛数量 |
| `GET /history?page=0&size=10&live_type=TOP_LIVE` | 历史直播列表 |
| `GET /situation/{live_id}?no_cache=1` | 当前局面 + 着法 |
| `GET /winrates/{live_id}?begin_move_num=X` | 胜率历史 |
| `GET /base/{live_id}?begin_move_num=X&end_move_num=Y` | 详细分析 |

**关键数据字段**:
- `liveId`: 比赛唯一ID
- `liveStatus`: 0=直播中, 40=已结束
- `pb/pw`: 黑方/白方棋手名
- `moveNum`: 当前手数
- `winrate`: 黑方胜率 (0-1)

### 2.2 中国围棋协会

**基础 URL**: `https://wqapi.cwql.org.cn`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/playerInfo/battle/list` | POST | 获取对局列表 |
| `/playerInfo/battle/{battleNo}` | GET | 获取对局详情 + SGF |

**请求示例**:
```json
POST /playerInfo/battle/list
{
  "pageNum": 1,
  "pageSize": 20,
  "gameKifu": 1
}
```

**响应关键字段**:
- `battleNo`: 对局ID
- `gameKifuSgf`: 完整 SGF 数据
- `gameFullName`: 赛事全称
- `battleResultComment`: 比赛结果

---

## 3. 页面结构

### 3.1 一级页面：直播首页 (`/galaxy/live`)

```
┌────────────┬─────────────────────────────────┬──────────────────┐
│  Sidebar   │            主内容区              │      右边栏       │
│            │                                 │                  │
│            │  ┌───────────────────────────┐  │  [顶尖大赛][预告]  │
│            │  │                           │  │                  │
│            │  │         棋 盘              │  │  ┌────────────┐  │
│            │  │   (最重要的实时/最新比赛)    │  │  │ 正在直播    │  │
│            │  │                           │  │  │ 井山 vs 余  │  │
│            │  └───────────────────────────┘  │  │ 91.9% 130手 │  │
│            │                                 │  └────────────┘  │
│            │  ┌───────────────────────────┐  │  ┌────────────┐  │
│            │  │  ⏮ ⏪ ⏯ ⏩ ⏭  313/313手   │  │  │ 历史直播    │  │
│            │  └───────────────────────────┘  │  │ 上野 vs ... │  │
│            │                                 │  └────────────┘  │
│            │        [ 进入直播 ] 按钮         │       ...        │
└────────────┴─────────────────────────────────┴──────────────────┘
```

**右边栏 TAB**:
- **顶尖大赛**（默认）：实时 + 近期比赛卡片列表，按时间倒序
- **赛事预告**：即将进行的重要比赛列表

**主内容区逻辑**:
- 有实时直播 → 显示最重要的实时比赛
- 无实时直播 → 显示最新一场已结束比赛

### 3.2 二级页面：对局详情页 (`/galaxy/live/{match_id}`)

```
┌────────────┬────────────────────┬────────────────────────────────┐
│  Sidebar   │      主内容区       │           右边栏 (加宽)         │
│            │                    │                                │
│            │  ┌──────────────┐  │  ┌────────────────────────────┐│
│            │  │              │  │  │ 第29期日本女流棋圣战...     ││
│            │  │              │  │  │ 上野梨纱 ●━━━━━ 96.2% 上野爱││
│            │  │              │  │  └────────────────────────────┘│
│            │  │              │  │  ┌────────────────────────────┐│
│            │  │     棋 盘     │  │  │ 推荐着法         [▲][▼]   ││
│            │  │              │  │  │ H3  29%  4.7目  96.2%     ││
│            │  │              │  │  │ S7  17%  5.7目  95.8%     ││
│            │  │              │  │  │ G9  16%  4.4目  96.6%     ││
│            │  │              │  │  │ P18 15%  4.5目  96.2%     ││
│            │  └──────────────┘  │  └────────────────────────────┘│
│            │                    │  ┌────────────────────────────┐│
│            │                    │  │[走势图][妙手][问题手]        ││
│            │                    │  │   📈 胜率/目数曲线          ││
│            │                    │  └────────────────────────────┘│
│            │                    │  ┌────────────────────────────┐│
│            │                    │  │ 试下  领地  手数            ││
│            │                    │  └────────────────────────────┘│
│            │                    │  ┌────────────────────────────┐│
│            │                    │  │ 💬 评论区 (仅直播时显示)     ││
│            │                    │  │  user1: 这手棋厉害         ││
│            │                    │  │  user2: 黑棋形势不妙       ││
│            │                    │  │  [输入评论...]    [发送]   ││
│            │                    │  └────────────────────────────┘│
│            │                    │  ⏮ ⏪ ⏯ ⏩ ⏭  297/313手       │
└────────────┴────────────────────┴────────────────────────────────┘
```

**右边栏模块（从上到下）**:
1. **对局信息**：赛事名称、日期、棋手信息、胜率条
2. **AI 推荐着法**：最多显示 4 手，带滑动条可查看更多
3. **走势图 TAB**：走势图 / 妙手列表 / 问题手列表
4. **功能按钮**：试下、领地、手数
5. **评论区**：仅直播比赛显示，固定区域，可发言
6. **播放控制栏**：进度控制 + 手数显示

---

## 4. 后端架构

### 4.1 数据流

```
┌─────────────────────────────────────────────────────────────────────┐
│                           KaTrain 后端                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │ LivePoller  │    │ LiveCache   │    │     KataGo Engine       │ │
│  │ (定时任务)   │───▶│ (Redis/内存) │───▶│     (本地分析)          │ │
│  └─────────────┘    └─────────────┘    └─────────────────────────┘ │
│         │                  │                       │               │
│         ▼                  ▼                       ▼               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │ XingZhen    │    │ weiqi.org   │    │   分析结果存储           │ │
│  │ API Client  │    │ API Client  │    │   (SGF + 分析数据)       │ │
│  └─────────────┘    └─────────────┘    └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
         │                   │                       │
         ▼                   ▼                       ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐
│ api.19x19.com   │  │ wqapi.cwql.org  │  │    PostgreSQL DB        │
│ (着法/赛事信息)  │  │ (棋谱/SGF)      │  │ (用户/评论/历史分析)     │
└─────────────────┘  └─────────────────┘  └─────────────────────────┘
```

### 4.2 后端模块结构

```
katrain/web/
├── live/                       # 新增：直播模块
│   ├── __init__.py
│   ├── poller.py              # 定时轮询任务
│   ├── cache.py               # 直播数据缓存
│   ├── clients/
│   │   ├── xingzhen.py        # XingZhen API 客户端
│   │   └── weiqi_org.py       # weiqi.org.cn API 客户端
│   ├── analyzer.py            # KataGo 分析调度
│   └── models.py              # 直播相关数据模型
├── api/v1/endpoints/
│   └── live.py                # 新增：直播 API 端点
```

### 4.3 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/live/matches` | GET | 获取比赛列表（直播+近期） |
| `/api/v1/live/matches/{id}` | GET | 获取比赛详情（含着法、分析） |
| `/api/v1/live/matches/{id}/analysis` | GET | 获取指定手数的分析数据 |
| `/api/v1/live/upcoming` | GET | 获取赛事预告列表 |
| `/api/v1/live/matches/{id}/comments` | GET | 获取评论列表 |
| `/api/v1/live/matches/{id}/comments` | POST | 发表评论（需登录） |

### 4.4 数据模型

```python
# 比赛信息
class LiveMatch:
    id: str                    # 内部ID
    source: str                # "xingzhen" | "weiqi_org"
    source_id: str             # 原始数据源ID
    tournament: str            # 赛事名称
    date: datetime             # 比赛日期
    player_black: str          # 黑方棋手
    player_white: str          # 白方棋手
    status: str                # "live" | "finished"
    result: str | None         # 比赛结果
    move_count: int            # 当前手数
    current_winrate: float     # 当前黑方胜率
    sgf: str | None            # SGF 数据

# 分析数据
class MoveAnalysis:
    match_id: str
    move_number: int
    winrate: float             # 黑方胜率
    score_lead: float          # 黑方领先目数
    top_moves: list            # AI 推荐着法
    is_brilliant: bool         # 妙手标记
    is_mistake: bool           # 问题手标记
    is_questionable: bool      # 疑问手标记
    delta_score: float         # 目数变化
    delta_winrate: float       # 胜率变化
```

---

## 5. 前端组件

### 5.1 文件结构

```
katrain/web/ui/src/galaxy/
├── pages/
│   └── live/
│       ├── LivePage.tsx           # 一级页面：直播首页
│       └── LiveMatchPage.tsx      # 二级页面：对局详情
├── components/
│   └── live/
│       ├── MatchCard.tsx          # 比赛卡片（列表项）
│       ├── MatchList.tsx          # 比赛列表
│       ├── UpcomingList.tsx       # 赛事预告列表
│       ├── MatchInfo.tsx          # 对局信息面板
│       ├── AiAnalysis.tsx         # AI 推荐着法面板
│       ├── TrendChart.tsx         # 走势图（复用/改造现有）
│       ├── BrilliantMoves.tsx     # 妙手列表
│       ├── MistakeMoves.tsx       # 问题手列表
│       ├── LiveControls.tsx       # 功能按钮组
│       ├── CommentSection.tsx     # 评论区
│       ├── PlaybackBar.tsx        # 播放控制栏
│       └── PvOverlay.tsx          # PV 推演覆盖层
├── hooks/
│   └── live/
│       ├── useLiveMatches.ts      # 比赛列表数据 hook
│       ├── useLiveMatch.ts        # 单场比赛数据 hook
│       ├── useAnalysis.ts         # 分析数据 hook
│       └── useComments.ts         # 评论数据 hook
└── context/
    └── LiveContext.tsx            # 直播状态管理
```

### 5.2 状态管理

```typescript
interface LiveState {
  // 比赛列表
  matches: LiveMatch[];
  upcomingMatches: UpcomingMatch[];

  // 当前比赛
  currentMatch: LiveMatch | null;
  currentMoveNumber: number;
  isLive: boolean;

  // 分析数据
  analysisData: Map<number, MoveAnalysis>;

  // PV 显示
  hoveredMove: string | null;
  pvMoves: string[];
  pvAnimationIndex: number;

  // 轮询控制
  isPolling: boolean;
}
```

---

## 6. 配置结构

```json
{
  "live": {
    "sources": {
      "xingzhen": {
        "enabled": true,
        "api_base": "https://api.19x19.com/api/engine/golives",
        "endpoints": {
          "live_list": "/all",
          "history": "/history",
          "situation": "/situation/{live_id}",
          "winrates": "/winrates/{live_id}"
        }
      },
      "weiqi_org": {
        "enabled": true,
        "api_base": "https://wqapi.cwql.org.cn",
        "endpoints": {
          "battle_list": "/playerInfo/battle/list",
          "battle_detail": "/playerInfo/battle/{battle_no}"
        },
        "web_url": "https://www.weiqi.org.cn/competition/battle"
      }
    },
    "polling": {
      "list_interval": 60,
      "moves_interval": 3,
      "analysis_interval": 5
    },
    "analysis": {
      "max_visits": 500,
      "use_local_katago": true
    },
    "display": {
      "pv_moves": 10,
      "pv_anim_time": 0.3,
      "brilliant_threshold": 2.0,
      "mistake_threshold": -3.0,
      "questionable_threshold": -1.5
    }
  }
}
```

---

## 7. 实现阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **Phase 1** | 后端 API 客户端（XingZhen + weiqi.org） | 无 |
| **Phase 2** | 后端轮询 + 缓存 + API 端点 | Phase 1 |
| **Phase 3** | 前端一级页面（直播首页） | Phase 2 |
| **Phase 4** | 前端二级页面（对局详情） | Phase 3 |
| **Phase 5** | KataGo 本地分析集成 | Phase 2 |
| **Phase 6** | PV 推演显示 | Phase 4, 5 |
| **Phase 7** | 评论系统 | Phase 4 |
| **Phase 8** | 赛事预告爬取 | Phase 2 |

---

## 8. 后续待办（MVP 之后）

- [ ] 评论审核功能
- [ ] 棋手头像批量获取
- [ ] 棋手名字中英翻译
- [ ] 停一手、研究、分享功能
- [ ] 棋友赛事支持
- [ ] 更多数据源（日本棋院、韩国棋院）

---

## 9. PV 推演显示参考

参考 KaTrain 桌面版实现 (`katrain/gui/badukpan.py`):

- **显示方式**: `draw_pv()` 方法，半透明棋子 + 序号标签
- **触发方式**: 鼠标悬停在推荐招法上
- **动画配置**: `general/anim_pv_time` (默认 0.5 秒)
- **数据来源**: KataGo `analysis.json["moveInfos"][0]["pv"]`

---

## 10. 妙手/问题手标注

| 标注类型 | 阈值 | 说明 |
|----------|------|------|
| 问题手 🔴 | delta < -3.0 目 | 明显失误 |
| 疑问手 🟡 | delta < -1.5 目 | 小失误 |
| 妙手 🟢 | delta > +2.0 目 | 扭转局势的好棋 |

**悬停显示原因**: 目数变化（如 "-5.2目"）、胜率变化（如 "-12.3%"）

---

# 专家评审 (2026-01-22)

作为一名兼具围棋背景和计算机专业的开发者，我对这份设计文档的评价是：**架构清晰、功能切中痛点，但存在几个关键的“隐形地雷”（风险点）需要我们在实现时格外注意。**

### 优点
1.  **架构清晰**: 明确了 "LivePoller" (轮询) 和 "LiveCache" (缓存) 的设计，这对于保证 UI 流畅性和避免频繁请求 API 至关重要。
2.  **API 调研深入**: 提供了 19x19 和 cwql 的具体 API 端点，大大减少了开发前期的调研成本。
3.  **功能完整**: 涵盖了直播、历史回顾、本地 AI 分析、PV 推演等围棋用户最关心的核心功能。

### 缺陷与风险分析

#### 1. 技术风险：API 的非官方性质 (最高风险)
*   **问题**: 我们依赖的 `api.19x19.com` 和 `cwql.org.cn` 并非官方开放平台，而是通过逆向工程获取的。
*   **风险**:
    *   **反爬虫/限流**: 如果我们的客户端轮询频率过高（比如几千个用户同时在线），可能会触发对方的 WAF 防火墙，导致 IP 被封禁。
    *   **接口变动**: 对方一旦更新前端代码或修改 JSON 结构，我们的“直播”功能就会立即瘫痪，必须发布新版本修复。
*   **建议**: 在 `LivePoller` 中必须实现**指数退避 (Exponential Backoff)** 策略。如果请求失败，不要死循环重试，而是降低频率。同时，缓存策略要尽可能激进，减少对源站的请求。

#### 2. 产品逻辑：本地分析的“算力陷阱”
*   **问题**: 规划中提到利用本地 KataGo 实时分析并标注“妙手/问题手”。
*   **风险**:
    *   **性能滞后**: 职业比赛快棋阶段，一手棋可能只有 30 秒。如果用户的显卡较弱（如集成显卡），KataGo 可能还没算出上一手的胜率，下一手棋已经来了。这会导致“妙手”标注出现严重的延迟或漏标。
    *   **准确性**: 快速分析（低 Visits）下的胜率波动很大。AI 可能会在低算力下把一步正常棋误判为“问题手”（胜率跳水），这会误导用户。
*   **建议**: 默认配置中，直播模式下的 `max_visits` 应该设置得比复盘模式更低（例如 200-500 visits），优先保证跟上直播速度，而不是追求极致准确。

#### 3. UX 交互：“试下”模式的状态同步
*   **问题**: 用户点击“试下” (Try) 后，会从直播流分叉出一个本地分支。
*   **风险**: 当用户在“试下”时，直播流仍在继续。当用户点击“返回直播”时，如何处理？
    *   如果直接跳回最新手，用户可能会感到突兀，错过了中间的进程。
    *   如果不仅跳回，还要保留刚才的“试下”图作为变化图，逻辑会非常复杂。
*   **建议**: MVP 阶段简化处理：点击“返回直播”直接清空当前分支，强制同步到服务器最新手。

#### 4. 法律/版权风险：评论与棋谱
*   **问题**: 棋谱（SGF Moves）通常被视为事实数据，版权风险较小。但**解说评论**（Text Commentary）是具有独创性的文本，受版权保护。
*   **风险**: 直接抓取并展示星阵或弈城的解说文字，存在法律灰色地带。
*   **建议**: 仅作为“个人学习/研究”工具使用尚可，如果发布为商业软件或大规模推广，建议默认关闭评论抓取，或仅抓取不含版权的纯技术统计数据。

#### 5. 数据源缺失：赛事预告
*   **问题**: 规划中提到的“赛事预告”目前没有现成的 API (`Likely scraping weiqi.org`)。
*   **风险**: 网页结构化数据抓取（HTML Scraping）极不稳定。一旦官网改版，解析代码就会失效。且 `weiqi.org` 的更新频率和准确性不可控。
*   **建议**: 这一块建议作为 `Nice-to-have`，或者考虑硬编码一些已知的世界大赛日程（如果不需频繁更新），不要在这个功能上投入过多精力去写复杂的爬虫。