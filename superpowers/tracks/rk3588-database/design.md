# RK3588 Smart Board Database Architecture Design

> Date: 2026-02-09
> Status: v2 — 补充工程落地细节

## 1. Background

KaTrain 需要支持多台 RK3588 智能棋盘接入。每台棋盘运行 KaTrain Web 服务（FastAPI + React），需要访问数据库。远程服务器上已有一套完整的 PostgreSQL 数据库（15 张表，~120 MB 数据）。

### 核心需求

- **集中管理**：数据库 schema 统一变更，避免各设备之间表结构不一致
- **在线模式**：智能棋盘通过网络访问云端数据
- **离线模式**：断网时仍能下棋，数据暂存本地，联网后同步

---

## 2. 当前数据库表分类

### A. 全局共享内容（智能棋盘只读，~113 MB）

| Table | Rows | Size | Description |
|-------|------|------|-------------|
| `tsumego_problems` | 21K | 19 MB | 死活题库 |
| `kifu_albums` | 25K | 41 MB | 大赛棋谱 |
| `live_matches` | 71 | 312 KB | 职业比赛记录 |
| `live_analysis` | 14.8K | 53 MB | 直播对局 KataGo 分析 |
| `live_upcoming` | 16 | 56 KB | 赛事日程 |
| `player_translations` | 123 | 72 KB | 棋手名多语言翻译 |
| `tournament_translations` | 101 | 88 KB | 赛事名多语言翻译 |
| `system_config` | 0 | 8 KB | 运行时配置 |

### B. 用户账户数据

| Table | Description |
|-------|-------------|
| `users` | 账户、段位、积分 |
| `relationships` | 社交关注 |
| `rating_history` | 段位变动记录 |

### C. 用户生成内容（需同步）

| Table | Description |
|-------|-------------|
| `user_games` | 个人棋谱（对局、导入、研究） |
| `user_game_analysis` | 逐手分析结果 |
| `user_tsumego_progress` | 做题进度 |
| `live_comments` | 直播评论 |

---

## 3. 方案评估

### 3.1 方案 A：智能棋盘直连远程 PostgreSQL（不推荐）

将每台棋盘的 `DATABASE_URL` 指向远程 PostgreSQL。

| 维度 | 评估 |
|------|------|
| **安全性** | 差 — 5432 端口暴露到公网，每台棋盘持有 DB 完整读写凭据，任一设备被攻破 = 全库泄露 |
| **网络延迟** | 每次 DB 查询都走公网（20-100ms/次），浏览死活题、棋谱需要多次往返 |
| **离线支持** | 完全不可用 — 断网即崩溃（启动时 `lifespan()` 会查询 `users` 表） |
| **连接数** | PostgreSQL 默认上限 100 连接，每台棋盘占 ~5 个连接池，20 台即耗尽 |
| **Schema 耦合** | 高 — 代码加列后所有设备必须同时更新，否则崩溃（如 `uuid` 列缺失问题） |

### 3.2 方案 B：每台棋盘部署本地 PostgreSQL + 双向同步（不推荐）

每台 RK3588 运行 Docker PostgreSQL，定期与云端同步。

| 维度 | 评估 |
|------|------|
| **Schema 管理** | 噩梦 — 每台设备独立管理 migration 状态 |
| **资源开销** | PostgreSQL + Docker 在 ARM 开发板上占 ~50-100 MB 内存 |
| **冲突解决** | 复杂 — 双向同步的数据冲突（同一用户在多台棋盘下棋）难以处理 |

### 3.3 方案 C：API-First + 本地离线缓存（推荐）

智能棋盘通过 REST API 访问远程 KaTrain 服务器，离线时回退到本地 SQLite。

| 维度 | 评估 |
|------|------|
| **安全性** | 好 — 仅 HTTPS 443 端口暴露，JWT 认证 |
| **Schema 耦合** | 零 — 棋盘不接触数据库，API 接口稳定 |
| **离线支持** | 可降级 — 本地 SQLite 支持核心下棋功能 |
| **可扩展性** | 好 — 一个服务器 API 服务 N 台棋盘 |

---

## 4. 推荐方案详细设计

### 4.1 系统架构

```
┌──────────────────────────────────────────────┐
│            Remote Server (Cloud)              │
│                                              │
│   KaTrain Web Server (FastAPI)               │
│   ├── REST API (/api/v1/*)                   │
│   ├── WebSocket (/ws/*)                      │
│   └── Static Files (/galaxy)                 │
│         │                                    │
│         │ localhost only                     │
│         ▼                                    │
│   PostgreSQL (source of truth, all 15 tables)│
└──────────────────┬───────────────────────────┘
                   │ HTTPS + JWT
       ┌───────────┼───────────┐
       │           │           │
  ┌────▼───┐  ┌───▼────┐  ┌───▼────┐
  │Board #1│  │Board #2│  │Board #N│
  │(RK3588)│  │(RK3588)│  │(RK3588)│
  │        │  │        │  │        │
  │ Online │  │ Online │  │ Online │
  │ →远程API│  │ →远程API│  │ →远程API│
  │        │  │        │  │        │
  │Offline │  │Offline │  │Offline │
  │ →本地   │  │ →本地   │  │ →本地   │
  │  SQLite│  │  SQLite│  │  SQLite│
  └────────┘  └────────┘  └────────┘
```

### 4.2 部署模式定义

通过环境变量 `KATRAIN_MODE` 区分两种部署模式：

```
KATRAIN_MODE=server   →  远程服务器模式（默认，现有行为不变）
                          - PostgreSQL 数据库
                          - 全部 15 张表
                          - 提供 REST API + WebSocket 给棋盘端和 Web 用户
                          - 运行 live_service 爬虫

KATRAIN_MODE=board    →  智能棋盘模式
                          - 在线时：所有数据操作通过远程 API（不直接访问数据库）
                          - 离线时：回退到本地 SQLite（仅核心表）
                          - 需要配置 KATRAIN_REMOTE_URL
                          - 不运行 live_service
```

**配置项**（`katrain/web/core/config.py`）：

| 配置 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| `KATRAIN_MODE` | `KATRAIN_MODE` | `"server"` | `"server"` or `"board"` |
| `REMOTE_API_URL` | `KATRAIN_REMOTE_URL` | `""` | 远程服务器 URL，如 `https://katrain.example.com` |

### 4.3 在线模式 vs 离线模式

| Feature | Online (远程服务器) | Offline (本地 SQLite) |
|---------|--------------------|-----------------------|
| 对弈 AI | 远程 KataGo（GPU，强） | 本地 KataGo（CPU，弱） |
| 用户认证 | JWT via 远程 API | 本地 guest 模式 |
| 保存棋谱 | 直接写入云端 DB | 暂存本地 SQLite → 联网后同步 |
| 死活题 | 从远程 API 实时加载 | 不可用 |
| 棋谱库 | 从远程 API 实时检索 | 不可用 |
| 直播对局 | WebSocket 实时推送 | 不可用 |
| 人人对弈 | WebSocket 匹配 | 不可用 |

### 4.4 棋盘端本地 SQLite 表选择

离线模式仅创建支撑核心下棋功能的最小表集：

| 表 | 用途 | 数据来源 |
|----|------|----------|
| `users` (仅当前 guest) | 离线身份标识 | 本地创建 |
| `user_games` | 离线对局暂存 | 本地产生 |
| `user_game_analysis` | 离线分析暂存 | 本地 KataGo |
| `user_tsumego_progress` | 做题进度暂存 | 本地操作 |
| `sync_queue` (**新表**) | 待同步操作队列 | 离线操作记录 |

**不需要的表**：
- `tsumego_problems` — 在线时通过 API 加载，离线时不可用
- `kifu_albums` — 同上
- `live_matches` / `live_analysis` / `live_upcoming` — 需要网络
- `live_comments` — 需要网络
- `player_translations` / `tournament_translations` — 服务器端翻译
- `system_config` — 服务器端配置
- `relationships` / `rating_history` — 社交/排名功能需要网络

### 4.5 离线数据同步策略

#### 同步队列表设计

```sql
CREATE TABLE sync_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    operation   TEXT NOT NULL,   -- "create_user_game" / "update_tsumego_progress"
    endpoint    TEXT NOT NULL,   -- 对应的远程 API 路径
    method      TEXT NOT NULL,   -- "POST" / "PUT"
    payload     JSON NOT NULL,   -- 序列化的请求参数
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at   DATETIME,        -- NULL = 未同步
    retry_count INTEGER DEFAULT 0,
    error       TEXT              -- 最后一次失败的错误信息
);
```

#### 同步触发时机

1. `ConnectivityManager` 检测到网络恢复（连续 2 次 health check 成功）
2. 按 `created_at` 顺序逐条处理
3. 每条记录最多 retry 3 次，超过后标记 error 并跳过
4. 同步成功后设置 `synced_at`

#### 支持的离线操作

| Operation | 远程 API | 冲突策略 |
|-----------|----------|----------|
| `create_user_game` | `POST /api/v1/user-games/` | UUID 主键，服务器端 append-only，无冲突 |
| `update_tsumego_progress` | `POST /api/v1/tsumego/progress/{id}` | 服务器端 upsert，取 attempts 最大值 |

**无冲突风险**的关键原因：
- `user_games.id` 使用 UUID（`uuid4().hex`），本地生成 + 远程插入不会重复
- `user_tsumego_progress` 是 `(user_id, problem_id)` 复合主键，upsert 语义天然幂等

### 4.6 连接检测机制

```
ConnectivityManager
├── 仅在 KATRAIN_MODE=board 时启动
├── 后台 asyncio task，每 10s 调用远程 /health
├── 判断逻辑：
│   ├── 连续 3 次 health check 失败 → 切换为 offline
│   └── 连续 2 次 health check 成功 → 切换为 online → 触发同步
├── 对外暴露 is_online 属性
└── 状态变化时触发回调（切换 Repository 实现）
```

网络抖动防护：不因单次超时就切换模式，需连续多次确认。

### 4.7 远程 API 客户端

棋盘端需要一个 HTTP 客户端封装对远程服务器 API 的调用。

**关键设计**：

```
RemoteAPIClient
├── base_url: str              # KATRAIN_REMOTE_URL
├── _token: Optional[str]      # JWT token，登录后缓存
├── _client: httpx.AsyncClient  # 复用连接池
│
├── Auth
│   ├── login(username, password) → str (token)
│   └── register(username, password) → dict
│
├── Tsumego (只读)
│   ├── get_levels() → list
│   ├── get_problems(level, category, offset, limit) → list
│   ├── get_problem(problem_id) → dict
│   └── update_progress(problem_id, data) → dict
│
├── Kifu (只读)
│   ├── search(q, page, page_size) → dict
│   └── get(album_id) → dict
│
├── User Games (CRUD)
│   ├── list(**params) → dict
│   ├── create(data) → dict
│   └── get(game_id) → dict
│
├── Live (只读)
│   └── get_matches(**params) → dict
│
└── Health
    └── check() → bool
```

所有请求自动附加 `Authorization: Bearer <token>` header。Token 过期时自动尝试 refresh。

### 4.8 Repository 抽象层

**当前问题**：API endpoint 直接通过 `Depends(get_db)` 操作 SQLAlchemy。在棋盘模式下，这些 endpoint 需要改为调用远程 API 而非本地数据库。

**解决方案**：引入 Repository Protocol，按部署模式注入不同实现。

```
                    ┌─────────────────────┐
                    │ TsumegoRepository   │ ← Protocol (接口)
                    │   get_levels()      │
                    │   get_problems()    │
                    │   get_problem()     │
                    └────┬──────────┬─────┘
                         │          │
          ┌──────────────▼┐   ┌────▼──────────────┐
          │ LocalTsumego  │   │ RemoteTsumego     │
          │ Repository    │   │ Repository        │
          │               │   │                   │
          │ SQLAlchemy DB │   │ RemoteAPIClient   │
          │ (server mode) │   │ (board mode)      │
          └───────────────┘   └───────────────────┘
```

**渐进式改造策略**：不一次性重构所有 endpoint。优先改造 3 组：

1. **Tsumego** — 离线时不可用，在线时走远程。改造简单，只读接口
2. **Kifu** — 同上
3. **User Games** — 离线时写本地 SQLite + sync_queue，在线时走远程

其余 endpoint（live、users、analysis 等）保持不变，棋盘模式下按需降级。

### 4.9 启动逻辑分支

`server.py` 的 `lifespan()` 需要根据模式分支：

```
lifespan():
  if KATRAIN_MODE == "board":
    ├── 创建 RemoteAPIClient(KATRAIN_REMOTE_URL)
    ├── 启动 ConnectivityManager
    ├── 注入 Remote Repository 到 app.state
    ├── 本地 SQLite 仅 create_all() 核心 5 张表
    ├── 不启动 live_service（棋盘不需要爬虫）
    └── 不创建 default admin 用户（用远程账户体系）
  else:  # "server"
    └── 现有逻辑完全不变
```

### 4.10 对 Web 端用户的影响

**零影响。** Web 端用户的链路是 `浏览器 → 远程服务器 → PostgreSQL`，与智能棋盘的本地架构完全无关。所有调整仅发生在 RK3588 设备端。服务器端代码的唯一变更是在 config.py 增加了两个配置项（默认值保持现有行为）。

---

## 5. 棋盘端用户认证流程

```
┌──────────┐       ┌───────────────┐       ┌──────────────┐
│  棋盘 UI  │       │ Board FastAPI │       │ Remote Server│
│ (React)  │       │  (本地 8001)   │       │ (Cloud API)  │
└────┬─────┘       └──────┬────────┘       └──────┬───────┘
     │   POST /api/v1/auth/login              │               │
     │──────────────────────────>│                              │
     │                          │  POST /api/v1/auth/login     │
     │                          │─────────────────────────────>│
     │                          │  { token: "eyJ..." }         │
     │                          │<─────────────────────────────│
     │   { token: "eyJ..." }    │                              │
     │<─────────────────────────│                              │
     │                          │  token 缓存到内存            │
     │                          │  后续请求自动附加 Bearer      │
```

离线时：
- 用户以 guest 身份使用
- 本地 SQLite 中创建一个 guest 用户记录
- 联网后可选择绑定到远程账户

---

## 6. 不做的事情（避免过度设计）

| 明确不做 | 原因 |
|----------|------|
| 本地缓存全部死活题/棋谱 | 数据量 60+ MB，首期保持简单。离线时这些功能不可用 |
| 双向冲突解决机制 | UUID 主键 + append-only 策略天然无冲突，不需要 CRDT |
| Alembic migration 管理本地 SQLite | 本地 SQLite 视为可丢弃缓存，`create_all()` 即可 |
| WebSocket 远程代理 | 离线时不需要直播/匹配；在线时浏览器直连远程 WebSocket |
| 本地用户密码体系 | guest 模式不需要密码，认证走远程 API |

---

## 7. FAQ

### Q1: 本地 SQLite 关机后数据会丢失吗？

**不会。** SQLite 是一个普通磁盘文件（如 `db.sqlite3`），和任何文件一样持久化。关机重启后数据完好无损。

首次启动时 `Base.metadata.create_all()` 根据当前代码创建表；之后再启动，发现表已存在则跳过，不会丢弃已有数据。

### Q2: 更新客户端版本时，本地 SQLite 的 schema 怎么办？

这是本地数据库的核心痛点。如果新版本代码给某张表加了一列，旧的本地 SQLite 没有这列 → 查询会崩溃。

**推荐做法：将本地 SQLite 视为可丢弃的缓存。**

更新流程：

1. 联网 → 自动同步离线数据到云端（sync_queue 清空）
2. 更新客户端代码
3. 删除旧 SQLite（`rm db.sqlite3`）
4. 启动 → `create_all()` 用新 schema 创建空表
5. 下次离线时自动使用新表结构

这之所以可行，是因为本地 SQLite 中不存储任何**唯一且不可恢复**的数据——它只是云端的镜像 + 离线暂存区。

### Q3: 为什么 SQLite 不会遇到 PostgreSQL 的 schema 不一致问题？

**本质上会遇到同样的问题。**

`create_all()` 的行为是：根据 ORM 模型创建**不存在的表**，对**已存在的表不做任何修改**。

- 本地 SQLite 看起来"没问题"，只是因为它通常是首次创建（表结构和代码同步）
- 如果本地 SQLite 已有旧表 + 代码更新加了新列 → 同样会报 `column does not exist`

**关键区别不是 SQLite vs PostgreSQL，而是"新空库"vs"已有旧表的库"。**

这也是 API-First 架构的核心优势之一：schema migration 只需要在**一个地方（服务器）**执行一次，所有智能棋盘通过 API 访问，完全不关心数据库 schema 版本。

### Q4: 已有的 API endpoint 够用吗？

当前 REST API 覆盖度已经很好，棋盘端所需的全部读写操作都有对应 endpoint：

| 功能 | Endpoint | 状态 |
|------|----------|------|
| 用户登录 | `POST /api/v1/auth/login` | 已有 |
| 用户注册 | `POST /api/v1/auth/register` | 已有 |
| 死活题列表 | `GET /api/v1/tsumego/levels` | 已有 |
| 死活题详情 | `GET /api/v1/tsumego/problems/{id}` | 已有 |
| 做题进度 | `GET/POST /api/v1/tsumego/progress` | 已有 |
| 棋谱搜索 | `GET /api/v1/kifu/albums` | 已有 |
| 棋谱详情 | `GET /api/v1/kifu/albums/{id}` | 已有 |
| 保存对局 | `POST /api/v1/user-games/` | 已有 |
| 对局列表 | `GET /api/v1/user-games/` | 已有 |
| 直播列表 | `GET /api/v1/live/matches` | 已有 |
| 健康检查 | `GET /health` | 已有 |

无需新增 endpoint，棋盘端是这些 API 的消费者。

### Q5: 在线模式下，棋盘端本地还需要运行 FastAPI 吗？

**需要。** 棋盘端的 FastAPI 承担两个角色：

1. **API 代理**（在线时）：前端 React 仍然调用 `localhost:8001/api/v1/*`，本地 FastAPI 将请求转发到远程服务器
2. **离线服务**（离线时）：本地 FastAPI 直接操作 SQLite，提供降级功能

这样前端代码完全不需要修改——它始终调用同一个 URL，由后端决定数据来源。

---

## 8. 实施路线图

### Phase 1：立即可做（零代码改动）

```bash
# 棋盘端：不需要本地 PostgreSQL，停掉 Docker 容器
docker compose -f docker-compose.db.yml down

# 确保 config.json 中没有 database_url 配置
# KaTrain 会自动回退到 SQLite（现有代码已支持）

# 启动
python -m katrain --ui web
```

此时棋盘端完全独立运行，使用本地 SQLite + 本地 KataGo。无在线功能。

### Phase 2：添加部署模式配置

| 改动 | 文件 | 影响 |
|------|------|------|
| 添加 `KATRAIN_MODE` + `REMOTE_API_URL` | `config.py` | 纯增量，默认值保持现有行为 |

### Phase 3：实现远程 API 客户端

| 改动 | 文件 | 影响 |
|------|------|------|
| 新建 `RemoteAPIClient` | `remote_client.py` (新文件) | 不影响现有代码 |

### Phase 4：实现连接检测 + 同步队列

| 改动 | 文件 | 影响 |
|------|------|------|
| 新建 `ConnectivityManager` | `connectivity.py` (新文件) | 不影响现有代码 |
| 新建 `SyncQueueEntry` 模型 | `models_db.py` | 仅新增表 |

### Phase 5：Repository 抽象 + 启动逻辑分支

| 改动 | 文件 | 影响 |
|------|------|------|
| Repository Protocol + 实现 | `repository.py` (新文件) | 不影响现有代码 |
| `lifespan()` 增加 board 分支 | `server.py` | 仅在 board 模式生效 |
| Endpoint 注入 Repository | `tsumego.py`, `kifu.py`, `user_games.py` | 渐进改造 |

### 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| Repository 抽象改造影响现有 server 模式 | 中 | 默认走原有 SQLAlchemy 路径，仅 board 模式使用 Remote |
| 远程 API 缺少某些 endpoint | 低 | 当前 API 覆盖度已经很好（见 Q4） |
| 离线对局数据丢失 | 低 | SQLite 持久化 + sync_queue 有 retry |
| 网络抖动导致频繁模式切换 | 中 | 连续 3 次失败才切离线，连续 2 次成功才切在线 |
