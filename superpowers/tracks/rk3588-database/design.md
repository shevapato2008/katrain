# RK3588 Smart Board Database Architecture Design

> Date: 2026-02-09
> Status: v4 — 补充基础设施部署拓扑（家庭服务器 → 云端集群迁移路径）

## 1. Background

KaTrain 需要支持多台 RK3588 智能棋盘接入。每台棋盘运行 KaTrain Web 服务（FastAPI + React），需要访问数据库。远程服务器上已有一套完整的 PostgreSQL 数据库（15 张表，~120 MB 数据）。

### 当前部署拓扑

项目当前采用**家庭服务器 + 阿里云 ECS 反向代理**的部署方式：

- **家庭服务器**：运行 KaTrain Web Server（FastAPI）、PostgreSQL、KataGo（GPU）
- **阿里云 ECS**：运行 Nginx 反向代理，通过 WireGuard 隧道连接家庭服务器
- **RK3588 棋盘**：通过 HTTPS 访问阿里云 ECS 公网 IP，流量经 Nginx 转发至家庭服务器

未来计划迁移至**阿里云服务器集群**：KataGo GPU 实例 + KaTrain ECS 实例 + RDS PostgreSQL，各组件独立扩展。

本文档的 API-First 架构（方案 C）天然支持这一拓扑迁移——棋盘端代码和服务器端代码均无需修改，仅变更服务端配置（`DATABASE_URL`、KataGo 地址）。详见 [Section 4.18 基础设施部署拓扑](#418-基础设施部署拓扑)。

### 核心需求

- **集中管理**：数据库 schema 统一变更，避免各设备之间表结构不一致
- **在线模式**：智能棋盘通过网络访问云端数据
- **离线模式**：断网时仍能下棋，数据暂存本地，联网后同步

### 设计约束

- **单用户设备**：每台 RK3588 棋盘视为单用户设备。同一时间只有一个用户使用。本地缓存和同步队列不需要多用户隔离（但 `user_id` 字段保留以备未来扩展）
- **最长离线容忍期**：90 天。超过此期限认证凭据过期，需重新登录。本地数据在此期间保持安全

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

**拓扑说明**：图中 "Remote Server (Cloud)" 是一个**逻辑概念**，不限定物理部署方式。它可以是：

- **单机部署**：KaTrain + PostgreSQL + KataGo 运行在同一台服务器上（当前家庭服务器方案）
- **分离部署**：KaTrain ECS 实例、RDS PostgreSQL、KataGo GPU 实例各自独立（未来云端集群方案）

无论哪种拓扑，棋盘端的链路始终是 `RK3588 → HTTPS → KaTrain API`，完全相同。KataGo 引擎路由（参见 CLAUDE.md 中的 Dual-Engine Routing）也可独立部署为内网服务，对棋盘端透明。

详细的拓扑架构图和迁移路径见 [Section 4.18](#418-基础设施部署拓扑)。

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
| `DEVICE_ID` | `KATRAIN_DEVICE_ID` | 自动生成 UUID | 设备唯一标识，用于审计和监控 |

### 4.3 在线模式 vs 离线模式

| Feature | Online (远程服务器) | Offline (本地 SQLite) |
|---------|--------------------|-----------------------|
| 对弈 AI | 远程 KataGo（GPU，强） | 本地 KataGo（CPU，弱） |
| 用户认证 | JWT via 远程 API | 本地 guest 模式 |
| 保存棋谱 | 直接写入云端 DB | 暂存本地 SQLite → 联网后同步 |
| 死活题 | 从远程 API 实时加载 | 不可用（显示"需要网络连接"提示） |
| 棋谱库 | 从远程 API 实时检索 | 不可用（显示"需要网络连接"提示） |
| 直播对局 | WebSocket via 本地代理 | 不可用（显示"需要网络连接"提示） |
| 人人对弈 | WebSocket via 本地代理 | 不可用（显示"需要网络连接"提示） |

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

#### 4.5.1 同步队列表设计

```sql
CREATE TABLE sync_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL UNIQUE,  -- 客户端生成的操作唯一标识（UUID）
    operation       TEXT NOT NULL,         -- "create_user_game" / "update_tsumego_progress"
    endpoint        TEXT NOT NULL,         -- 对应的远程 API 路径
    method          TEXT NOT NULL,         -- "POST" / "PUT"
    payload         JSON NOT NULL,         -- 序列化的请求参数
    status          TEXT NOT NULL DEFAULT 'pending',  -- 见状态机
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at       DATETIME,             -- 租约开始时间（防并发）
    synced_at       DATETIME,             -- 同步成功时间
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 5,
    next_retry_at   DATETIME,             -- 下次重试时间（指数退避）
    last_http_status INTEGER,             -- 最后一次响应 HTTP 状态码
    last_error      TEXT,                 -- 最后一次失败的错误信息
    user_id         TEXT,                 -- 关联用户（审计用）
    device_id       TEXT                  -- 设备标识（审计用）
);
```

#### 4.5.2 同步状态机

```
                    ┌─────────────────────────────┐
                    │                             │
                    ▼                             │
  pending ──→ in_progress ──→ completed          │
                  │                              │
                  ├──→ pending (retry)  ──────────┘
                  │    retry_count < max_retries
                  │    next_retry_at = now + backoff
                  │
                  └──→ failed (dead letter)
                       retry_count >= max_retries
                       或 4xx 业务错误（不可重试）
```

**状态定义**：

| 状态 | 含义 |
|------|------|
| `pending` | 等待同步或等待下次重试 |
| `in_progress` | 正在执行同步请求 |
| `completed` | 同步成功 |
| `failed` | 永久失败（进入 dead letter） |

**指数退避策略**：`next_retry_at = now + min(2^retry_count × 10, 300) 秒`

即：10s → 20s → 40s → 80s → 160s（上限 5 分钟）

#### 4.5.3 Dead Letter 处理

同步永久失败的条目**不会被静默丢弃**：

1. 状态标记为 `failed`，保留完整错误上下文（`last_http_status`、`last_error`）
2. 棋盘端本地 API 暴露 `GET /api/v1/board/sync-status`，返回队列状态摘要
3. 前端 UI 显示黄色警告徽标（"N 条数据同步失败"）
4. 点击可查看失败详情，提供"重试"按钮（将 `status` 重置为 `pending`，`retry_count` 清零）
5. 服务端设备监控（见 4.15）会检测到积压的失败队列并告警

**4xx vs 5xx 区分**：
- `5xx` / 网络超时：可重试，按退避策略继续
- `409 Conflict`：幂等重复，直接标记 `completed`
- 其他 `4xx`（400/403/404）：业务错误，不可重试，直接标记 `failed`

#### 4.5.4 幂等设计

**问题**：网络抖动导致请求重试时可能产生重复写入。

**解决方案**：每个同步操作在创建时生成 `idempotency_key`（UUID），服务端据此去重。

| 操作 | 幂等策略 |
|------|----------|
| `create_user_game` | 客户端在 payload 中包含 `id`（UUID）。服务端 `POST /api/v1/user-games/` 需改造：若 `id` 已存在则返回 `200`（非 `409`），不重复创建 |
| `update_tsumego_progress` | 天然幂等：`(user_id, problem_id)` 复合主键 + merge 规则（见 4.12） |

**服务端需新增**：
- `user_games.create()` 支持客户端传入 `id`，若已存在返回已有记录
- 可选：通用 `idempotency_key` 缓存表（TTL 24h），用于跨操作去重

#### 4.5.5 并发控制

**问题**：网络抖动可能导致 `ConnectivityManager` 在旧同步未完成时再次触发同步。

**解决方案**：进程级 `asyncio.Lock` + 行级租约。

```python
class SyncWorker:
    _sync_lock: asyncio.Lock  # 进程级，确保只有一个同步 worker 运行

    async def run_sync(self):
        if self._sync_lock.locked():
            return  # 已有同步在运行，跳过

        async with self._sync_lock:
            items = await self._fetch_pending()  # status='pending' AND (next_retry_at IS NULL OR <= now)
            for item in items:
                await self._mark_in_progress(item)  # status='in_progress', locked_at=now
                try:
                    await self._execute(item)
                    await self._mark_completed(item)
                except RetryableError:
                    await self._schedule_retry(item)
                except PermanentError:
                    await self._mark_failed(item)
```

**租约超时**：若 `locked_at` 超过 5 分钟仍为 `in_progress`，视为 worker 崩溃，重置为 `pending`。

#### 4.5.6 同步触发时机

1. `ConnectivityManager` 检测到网络恢复（连续 2 次 health check 成功）
2. `SyncWorker.run_sync()` 被调用（受 `_sync_lock` 保护）
3. 按 `created_at` 顺序逐条处理
4. 同步成功后设置 `synced_at`、`status = 'completed'`
5. 应用启动时检查是否有残留的 `in_progress` 条目（租约超时恢复）

#### 4.5.7 支持的离线操作

| Operation | 远程 API | 冲突策略 |
|-----------|----------|----------|
| `create_user_game` | `POST /api/v1/user-games/` | 客户端传 UUID 主键 + 服务端幂等去重 |
| `update_tsumego_progress` | `POST /api/v1/tsumego/progress/{id}` | 服务端 merge 规则（见 4.12） |

**冲突避免策略**（非"完全无冲突"，而是有意的设计选择）：
- `user_games`：客户端生成 UUID（`uuid4().hex`）作为主键，服务端 append-only。重试时通过幂等键去重，不会产生重复记录
- `user_tsumego_progress`：`(user_id, problem_id)` 复合主键，服务端按字段级 merge 规则合并（见 4.12）。这是 "last write wins on field level" 的有意设计

### 4.6 连接检测机制

```
ConnectivityManager
├── 仅在 KATRAIN_MODE=board 时启动
├── 后台 asyncio task，每 10s 调用远程 /health
├── 判断逻辑（含 RTT 阈值）：
│   ├── 连续 3 次 health check 失败或 RTT > 5s → 切换为 offline
│   └── 连续 2 次 health check 成功且 RTT < 5s → 切换为 online
├── 对外暴露 is_online: bool 属性
├── 状态变化回调：
│   ├── online → offline：通知 RepositoryDispatcher 切换到 Local
│   └── offline → online：通知 RepositoryDispatcher 切换到 Remote + 触发 SyncWorker
└── SyncWorker 引用（通过 _sync_lock 防止并发同步）
```

**网络抖动防护**：
- 不因单次超时就切换模式，需连续多次确认
- 增加 RTT 阈值（> 5s 视为不可用），避免弱网下频繁抖动
- 在线→离线切换时，等待当前 in-flight 请求完成（最长 10s timeout）后再切换

### 4.7 远程 API 客户端

棋盘端需要一个 HTTP 客户端封装对远程服务器 API 的调用。

**关键设计**：

```
RemoteAPIClient
├── base_url: str                  # KATRAIN_REMOTE_URL
├── _access_token: Optional[str]   # 短期 access token（内存中）
├── _refresh_token: Optional[str]  # 长期 refresh token（加密持久化）
├── _device_id: str                # 设备唯一标识
├── _client: httpx.AsyncClient     # 复用连接池
│
├── Auth
│   ├── login(username, password) → { access_token, refresh_token }
│   ├── refresh_token() → { access_token }           # 需服务端新增
│   ├── device_auth(device_id, device_secret) → token # 设备级认证（备选）
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
│   ├── create(data) → dict      # 支持客户端传 id
│   └── get(game_id) → dict
│
├── Live (只读)
│   └── get_matches(**params) → dict
│
├── Board (设备管理)
│   └── heartbeat(device_id, queue_depth, oldest_unsynced_age) → dict
│
└── Health
    └── check() → { ok: bool, rtt_ms: int }
```

#### 4.7.1 认证生命周期

**问题**：当前后端只有 login/register/me/logout，无 refresh endpoint；token 默认 7 天有效期。设备离线超过 7 天后重连，sync_queue 无法处理。

**解决方案**：双 token 机制。

| Token | 有效期 | 存储位置 | 用途 |
|-------|--------|----------|------|
| `access_token` | 1 小时 | 进程内存 | API 请求认证 |
| `refresh_token` | 90 天 | 加密文件 `~/.katrain/board_credentials` | 续期 access_token |

**认证流程**：

```
请求 API
  ├── 成功 → 正常返回
  └── 401 Unauthorized
       ├── 尝试 refresh_token → POST /api/v1/auth/refresh
       │   ├── 成功 → 获取新 access_token，重试原请求
       │   └── 失败（refresh_token 也过期）
       │        └── 标记 auth_required 状态
       │             ├── sync_queue 暂停处理
       │             ├── UI 显示"请重新登录"提示
       │             └── 用户登录后恢复 sync_queue
       └── （无 refresh_token）→ 同上
```

**服务端需新增**：
- `POST /api/v1/auth/refresh`：接收 refresh_token，返回新 access_token
- `POST /api/v1/auth/login` 响应增加 `refresh_token` 字段

### 4.8 Repository 抽象层

**当前问题**：API endpoint 直接通过 `Depends(get_db)` 操作 SQLAlchemy。在棋盘模式下，这些 endpoint 需要改为调用远程 API 而非本地数据库。v2 设计在启动时注入固定 Repository，但无法处理运行时网络切换。

**解决方案**：RepositoryDispatcher 模式 — 在每次请求时根据当前连接状态动态路由。

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
          └──────┬────────┘   └────────┬──────────┘
                 │                     │
          ┌──────▼─────────────────────▼──────┐
          │      RepositoryDispatcher         │
          │                                   │
          │  启动时实例化 Local + Remote 两者  │
          │                                   │
          │  每次方法调用时：                   │
          │  if connectivity.is_online:        │
          │      return remote.method()        │
          │  else:                             │
          │      result = local.method()       │
          │      if is_write:                  │
          │          enqueue_to_sync_queue()   │
          │      return result                 │
          └───────────────────────────────────┘
```

**关键改变**（vs v2）：
- 不在启动时一次性决定用哪个 Repository
- RepositoryDispatcher 同时持有 Local 和 Remote 两个实现
- 每次方法调用时，根据 `ConnectivityManager.is_online` 动态路由
- 写操作离线时同时写入本地 + sync_queue

**server 模式不受影响**：`KATRAIN_MODE=server` 时直接注入 LocalRepository（SQLAlchemy），不经过 Dispatcher。

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
    ├── 生成或读取 DEVICE_ID
    ├── 本地 SQLite 仅 create_all() 核心 5 张表
    ├── 创建 RemoteAPIClient(KATRAIN_REMOTE_URL)
    ├── 创建 RepositoryDispatcher(local=SQLAlchemy, remote=RemoteAPIClient)
    ├── 启动 ConnectivityManager（引用 SyncWorker）
    ├── 恢复 sync_queue 中残留的 in_progress 条目（租约超时恢复）
    ├── 尝试从加密文件恢复 refresh_token
    ├── 不启动 live_service（棋盘不需要爬虫）
    └── 不创建 default admin 用户（用远程账户体系）
  else:  # "server"
    └── 现有逻辑完全不变
```

### 4.10 对 Web 端用户的影响

**零影响。** Web 端用户的链路是 `浏览器 → 远程服务器 → PostgreSQL`，与智能棋盘的本地架构完全无关。所有调整仅发生在 RK3588 设备端。

服务器端代码的变更清单：
- `config.py`：增加 `KATRAIN_MODE`、`REMOTE_API_URL`、`DEVICE_ID` 配置项（默认值保持现有行为）
- `auth.py`：新增 `POST /api/v1/auth/refresh` endpoint
- `user_games.py`：`create()` 支持客户端传入 `id`
- `tsumego.py`：`update_progress()` 实现字段级 merge 规则
- `models_db.py`：可选新增 `device_heartbeats` 表

### 4.11 设备安全

**威胁场景**：RK3588 棋盘是可触摸的物理设备，存在被盗、非授权物理访问、调试接口暴露等风险。

#### 4.11.1 凭据存储

| 数据 | 存储方式 | 说明 |
|------|----------|------|
| `access_token` | 进程内存 | 短期有效（1h），进程退出即丢失 |
| `refresh_token` | 加密文件 `~/.katrain/board_credentials` | AES-256 加密，密钥派生自 `DEVICE_ID` + 设备 MAC 地址 |
| 用户密码 | **不存储** | 仅在登录时传输，不在本地保留 |

#### 4.11.2 本地数据库加密

本地 SQLite 使用 SQLCipher 加密（AES-256-CBC），密钥同上。

**依赖**：`pip install sqlcipher3-binary`（预编译 ARM64 wheel 需确认可用性）

**降级方案**：若 SQLCipher 在 RK3588 ARM 平台上不可用，则：
- 本地 SQLite 不加密，但仅存储可丢弃的缓存数据
- 通过文件系统权限（`chmod 600`）限制访问
- 在威胁模型中标注此为已知风险

#### 4.11.3 Token 失效

设备被盗后的缓解措施：
- 管理员通过服务端 API 撤销该设备的 refresh_token
- 服务端 token 黑名单机制（可选，按需实现）
- `refresh_token` 绑定 `device_id`，不可跨设备使用

### 4.12 冲突解决策略

v2 文档声称"无冲突风险"，这不准确。正确表述：本方案采用**冲突避免 + 字段级 merge 规则**的有意设计，非"完全无冲突"。

#### 4.12.1 `user_games`：无冲突

- 每条棋谱使用客户端生成的 UUID 作为主键
- 服务端 append-only，不存在同一主键被不同设备写入的情况
- 网络重试通过幂等键去重
- **结论**：真正无冲突

#### 4.12.2 `user_tsumego_progress`：字段级 Merge

同一用户可能在不同设备离线做题后同步。服务端 upsert 需按以下规则 merge：

| 字段 | Merge 规则 | 说明 |
|------|-----------|------|
| `attempts` | `max(existing, incoming)` | 取更大值，反映实际练习量 |
| `completed` | `existing OR incoming` | 只要任一设备完成即为完成 |
| `first_completed_at` | `min_non_null(existing, incoming)` | 取最早完成时间 |
| `last_attempt_at` | `max(existing, incoming)` | 取最近尝试时间 |

**服务端实现**（`tsumego.py` 的 `update_progress`）：

```python
# 伪代码
existing = db.get(user_id, problem_id)
if existing:
    existing.attempts = max(existing.attempts, incoming.attempts)
    existing.completed = existing.completed or incoming.completed
    existing.first_completed_at = min_non_null(existing.first_completed_at, incoming.first_completed_at)
    existing.last_attempt_at = max(existing.last_attempt_at, incoming.last_attempt_at)
else:
    db.insert(incoming)
```

**这是"字段级 last-write-wins"策略的有意设计选择**，而非"完全无冲突"。

### 4.13 Guest-to-User 数据绑定流程

**场景**：用户离线时以 guest 身份下棋，联网后登录远程账户，需要将本地 guest 数据关联到真实账户。

#### 4.13.1 流程设计

```
用户首次联网并登录
    │
    ▼
棋盘检测到本地存在 guest 数据
（user_games 和 user_tsumego_progress 中 user_id = guest_xxx）
    │
    ▼
弹出绑定确认对话框：
"检测到 N 条离线棋谱和做题记录，是否关联到当前账户？"
    │
    ├── [是] → 执行绑定
    │   ├── 1. 本地 SQLite 中：UPDATE user_games SET user_id = real_user_id WHERE user_id = guest_xxx
    │   ├── 2. 本地 SQLite 中：UPDATE user_tsumego_progress SET user_id = real_user_id WHERE ...
    │   ├── 3. sync_queue 中所有 pending 条目：更新 payload 中的 user_id
    │   ├── 4. 触发 SyncWorker 同步
    │   └── 5. 删除本地 guest 用户记录
    │
    └── [否] → 保留 guest 数据在本地（不同步）
         └── 后续可在设置中再次触发绑定
```

#### 4.13.2 边界条件

- 绑定操作是本地事务（SQLite），不依赖网络
- 绑定只修改 `user_id` 引用，不修改棋谱内容
- 同一设备多次登录不同账户：每次仅绑定当前 guest 数据，已绑定的数据不可改绑

### 4.14 WebSocket 策略

**问题**：v2 文档写"在线时浏览器直连远程 WebSocket"，但前端当前固定连接 `window.location.host/ws/...`（即本地 FastAPI）。两者矛盾。

**决策：本地 FastAPI 代理 WebSocket。**

理由：
1. 前端代码无需修改（始终连 localhost）
2. 本地代理可统一处理认证 token 注入
3. 离线时代理返回错误码，前端统一处理

```
棋盘 React UI
    │  ws://localhost:8001/ws/...
    ▼
Board FastAPI (本地)
    │  检查 is_online
    ├── online → 代理到 Remote Server ws://remote/ws/...
    │           （附加 Bearer token）
    └── offline → 返回 1001 关闭码 + "offline" reason
                  前端显示"需要网络连接"
```

**影响范围**：
- `server.py` 新增 WebSocket 代理路由（仅 board 模式）
- 使用 `websockets` 或 `httpx-ws` 做后端 WS 客户端
- 前端代码**零修改**

### 4.15 设备监控与可观测性

**问题**：若棋盘长期离线且有未同步数据，管理员无法感知。

#### 4.15.1 设备心跳

棋盘端在 online 状态下，每 5 分钟向服务端发送心跳：

```json
POST /api/v1/board/heartbeat
{
    "device_id": "rk3588-001",
    "queue_depth": 3,              // sync_queue 中 pending + failed 条目数
    "oldest_unsynced_age_sec": 7200,  // 最久未同步条目的年龄（秒）
    "failed_count": 1,             // failed 状态条目数
    "last_sync_at": "2026-02-09T10:00:00Z"
}
```

#### 4.15.2 服务端设备表

```sql
-- 服务端 PostgreSQL 新增表
CREATE TABLE device_heartbeats (
    device_id       TEXT PRIMARY KEY,
    last_seen       TIMESTAMP NOT NULL,
    queue_depth     INTEGER DEFAULT 0,
    failed_count    INTEGER DEFAULT 0,
    oldest_unsynced_age_sec INTEGER DEFAULT 0,
    last_sync_at    TIMESTAMP,
    ip_address      TEXT,
    app_version     TEXT
);
```

#### 4.15.3 告警规则

| 条件 | 告警等级 | 说明 |
|------|---------|------|
| `last_seen` > 7 天 | 警告 | 设备可能永久离线 |
| `failed_count` > 0 | 警告 | 有同步失败的数据 |
| `queue_depth` > 50 | 错误 | 大量数据积压 |
| `last_seen` > 30 天 | 严重 | 设备可能丢失 |

**实现方式**：服务端后台定时任务（每小时检查一次），通过日志或 webhook 通知管理员。

### 4.16 离线 UX 降级

离线时用户尝试访问在线功能时的 UI 行为：

| 功能 | 离线表现 | UI 组件 |
|------|----------|---------|
| 死活题 | 页面显示"需要网络连接才能加载题库" + 网络状态图标 | `OfflineNotice` |
| 棋谱库 | 同上 | `OfflineNotice` |
| 直播 | 同上 | `OfflineNotice` |
| 人人对弈 | 同上 | `OfflineNotice` |
| AI 对弈 | **正常可用**（本地 KataGo），右上角显示"离线模式"标签 | `OfflineBadge` |
| 保存棋谱 | **正常可用**（自动暂存本地），显示"联网后自动同步"提示 | `SyncPendingBadge` |

**全局状态栏**：
- 在线：绿色 dot + "已连接"
- 离线：灰色 dot + "离线模式"
- 同步中：蓝色旋转 + "正在同步 (3/7)"
- 同步失败：黄色警告 + "N 条同步失败"

### 4.17 本地数据生命周期

**问题**：本地 SQLite 无限增长会耗尽设备存储。

**清理策略**：

| 数据 | 保留策略 | 清理时机 |
|------|---------|---------|
| `sync_queue` status=`completed` | 同步成功后保留 7 天 | 每次应用启动时清理 |
| `sync_queue` status=`failed` | 保留直到手动处理 | 不自动清理 |
| `user_games` 已同步 | 同步成功后保留 30 天 | 每次应用启动时清理 |
| `user_tsumego_progress` 已同步 | 同步成功后保留 30 天 | 每次应用启动时清理 |

**磁盘水位检查**：
- 启动时检查 SQLite 文件大小
- 超过 100 MB 时日志警告
- 超过 500 MB 时强制清理所有已同步数据 + VACUUM

### 4.18 基础设施部署拓扑

本节描述 KaTrain 服务器端的物理部署方式。这些拓扑变化**不影响任何应用代码**——棋盘端始终通过 HTTPS 调用 KaTrain API，服务器端始终通过 `DATABASE_URL` 和 KataGo 地址连接后端服务。

#### 4.18.1 拓扑 A：家庭服务器 + 云端反向代理（当前）

```
┌─────────────────────────────────────────────────┐
│              Home Server (家庭服务器)              │
│                                                 │
│   KaTrain Web Server (FastAPI)                  │
│   PostgreSQL (localhost:5432)                    │
│   KataGo (localhost, GPU)                       │
│                                                 │
└──────────────────┬──────────────────────────────┘
                   │ WireGuard Tunnel (内网互联)
                   │
┌──────────────────▼──────────────────────────────┐
│           Alibaba Cloud ECS (反向代理)            │
│                                                 │
│   Nginx (443 → WireGuard Peer → Home:8001)     │
│   Let's Encrypt TLS 证书                        │
│                                                 │
└──────────────────┬──────────────────────────────┘
                   │ HTTPS (公网)
       ┌───────────┼───────────┐
       │           │           │
  ┌────▼───┐  ┌───▼────┐  ┌───▼────┐
  │Board #1│  │Board #2│  │Board #N│
  │(RK3588)│  │(RK3588)│  │(RK3588)│
  └────────┘  └────────┘  └────────┘
```

**特点**：
- 成本低：仅需一台低配 ECS（反向代理无计算负担）
- 家庭网络带宽和稳定性为瓶颈
- 所有服务单机运行，无法独立扩展

**配置**：
- `DATABASE_URL=postgresql://localhost:5432/katrain`
- KataGo: `localhost`（本地 GPU）

#### 4.18.2 拓扑 B：云端集群 + RDS（未来）

```
┌─────────────────────────────────────────────────────────┐
│                  Alibaba Cloud VPC                       │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────────────┐     │
│  │ KataGo GPU 实例   │  │ KaTrain ECS 实例 (×N)    │     │
│  │ (ecs.gn6i 系列)   │  │                          │     │
│  │                  │  │ FastAPI + Uvicorn         │     │
│  │ 内网 LB 地址      │◀─│                          │     │
│  └──────────────────┘  └────────────┬─────────────┘     │
│                                     │ 内网                │
│                        ┌────────────▼─────────────┐     │
│                        │ RDS PostgreSQL            │     │
│                        │ (高可用版，自动备份)        │     │
│                        └──────────────────────────┘     │
│                                                         │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS (SLB / 公网)
             ┌───────────┼───────────┐
             │           │           │
        ┌────▼───┐  ┌───▼────┐  ┌───▼────┐
        │Board #1│  │Board #2│  │Board #N│
        │(RK3588)│  │(RK3588)│  │(RK3588)│
        └────────┘  └────────┘  └────────┘
```

**特点**：
- 各组件独立扩展：KataGo GPU 按需增减，KaTrain ECS 水平扩展
- RDS 提供自动备份、主从高可用、免运维
- VPC 内网通信，延迟 < 1ms
- 成本高于拓扑 A（GPU 实例按需/包年）

**配置**：
- `DATABASE_URL=postgresql://user:pass@rm-xxx.pg.rds.aliyuncs.com:5432/katrain`（RDS 内网地址）
- KataGo: `http://katago-lb.vpc.internal:8000`（内网 LB 地址）

#### 4.18.3 迁移路径（拓扑 A → 拓扑 B）

迁移是纯运维操作，**不涉及任何代码修改**：

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1. 准备 | `pg_dump` 导出家庭服务器数据 → `pg_restore` 导入 RDS | 全量迁移约 120 MB，耗时 < 5 分钟 |
| 2. 验证 | 在 ECS 实例上部署 KaTrain，运行测试套件 `CI=true uv run pytest tests` | 确认 API 功能正常 |
| 3. 切换 | 修改 Nginx 上游地址：从 WireGuard Peer 指向 ECS 内网 IP（或 SLB） | 棋盘端无感知，DNS/IP 不变 |
| 4. 清理 | 观察 1-2 周后下线家庭服务器 | 保留旧数据库备份 |

**关键保证**：
- **棋盘端代码零修改**：始终调用同一个 HTTPS 域名
- **服务器端代码零修改**：仅 `DATABASE_URL` 和 KataGo 地址变化（环境变量）
- **数据完整性**：`pg_dump/pg_restore` 是 PostgreSQL 官方全量迁移工具

#### 4.18.4 其他拓扑变体

API-First 架构支持更多部署变体，均仅需修改服务端配置：

| 变体 | 场景 | 配置变化 |
|------|------|---------|
| 多区域 KaTrain | 低延迟覆盖不同地理区域 | SLB 按地域路由，各区域 ECS 共享同一 RDS |
| 读写分离 | 高并发读取（如棋谱检索） | RDS 只读实例 + 应用层路由 |
| 本地开发环境 | 开发者本机测试 | `DATABASE_URL=sqlite:///dev.db`，无需云资源 |
| 混合部署 | 部分服务云端、部分本地 | KaTrain 云端 + KataGo 本地（Dual-Engine Routing 已支持） |

所有变体对棋盘端**完全透明**——棋盘只认识一个 HTTPS 入口地址。

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
     │                          │  { access_token, refresh_token }
     │                          │<─────────────────────────────│
     │   { access_token }       │                              │
     │<─────────────────────────│                              │
     │                          │  access_token → 内存缓存     │
     │                          │  refresh_token → 加密文件    │
     │                          │  后续请求自动附加 Bearer      │
```

**Token 续期**（静默，用户无感知）：

```
     │  请求 API → 401          │                              │
     │                          │  POST /api/v1/auth/refresh   │
     │                          │  { refresh_token: "xxx" }    │
     │                          │─────────────────────────────>│
     │                          │  { access_token: "new..." }  │
     │                          │<─────────────────────────────│
     │                          │  重试原请求                   │
```

离线时：
- 用户以 guest 身份使用
- 本地 SQLite 中创建一个 guest 用户记录（`user_id = "guest_{uuid}"`）
- 联网后弹出绑定提示（见 4.13）

---

## 6. 不做的事情（避免过度设计）

| 明确不做 | 原因 |
|----------|------|
| 本地缓存全部死活题/棋谱 | 数据量 60+ MB，首期保持简单。离线时这些功能不可用 |
| CRDT 双向冲突解决 | UUID 主键 + append-only + 字段级 merge 规则已足够，不需要 CRDT |
| Alembic migration 管理本地 SQLite | 本地 SQLite 视为可丢弃缓存，`create_all()` 即可 |
| 本地用户密码体系 | guest 模式不需要密码，认证走远程 API |
| 多用户支持 | 棋盘为单用户设备，首期不考虑多用户切换 |
| 通用 API Gateway | 棋盘端 FastAPI 只代理自己需要的 endpoint，不做通用网关 |

---

## 7. FAQ

### Q1: 本地 SQLite 关机后数据会丢失吗？

**不会。** SQLite 是一个普通磁盘文件（如 `db.sqlite3`），和任何文件一样持久化。关机重启后数据完好无损。

首次启动时 `Base.metadata.create_all()` 根据当前代码创建表；之后再启动，发现表已存在则跳过，不会丢弃已有数据。

### Q2: 更新客户端版本时，本地 SQLite 的 schema 怎么办？

这是本地数据库的核心痛点。如果新版本代码给某张表加了一列，旧的本地 SQLite 没有这列 → 查询会崩溃。

**推荐做法：将本地 SQLite 视为可丢弃的缓存。**

**自动化更新流程**（由更新脚本 `scripts/board_upgrade.sh` 执行）：

```bash
#!/bin/bash
# 1. 检查网络连接
curl -sf https://katrain.example.com/health || { echo "无网络，请联网后再更新"; exit 1; }

# 2. 触发强制同步，等待队列清空
curl -X POST http://localhost:8001/api/v1/board/force-sync
while [ "$(curl -s http://localhost:8001/api/v1/board/sync-status | jq .pending)" != "0" ]; do
    sleep 2
done

# 3. 确认无 failed 条目
FAILED=$(curl -s http://localhost:8001/api/v1/board/sync-status | jq .failed)
if [ "$FAILED" != "0" ]; then
    echo "警告：有 $FAILED 条同步失败记录，请先处理"
    exit 1
fi

# 4. 停止应用
systemctl stop katrain

# 5. 备份旧数据库（以防万一）
cp db.sqlite3 "db.sqlite3.bak.$(date +%Y%m%d)"

# 6. 删除旧数据库
rm db.sqlite3

# 7. 更新代码
git pull

# 8. 启动（create_all 创建新表）
systemctl start katrain
```

这之所以可行，是因为本地 SQLite 中不存储任何**唯一且不可恢复**的数据——它只是云端的镜像 + 离线暂存区。

### Q3: 为什么 SQLite 不会遇到 PostgreSQL 的 schema 不一致问题？

**本质上会遇到同样的问题。**

`create_all()` 的行为是：根据 ORM 模型创建**不存在的表**，对**已存在的表不做任何修改**。

- 本地 SQLite 看起来"没问题"，只是因为它通常是首次创建（表结构和代码同步）
- 如果本地 SQLite 已有旧表 + 代码更新加了新列 → 同样会报 `column does not exist`

**关键区别不是 SQLite vs PostgreSQL，而是"新空库"vs"已有旧表的库"。**

这也是 API-First 架构的核心优势之一：schema migration 只需要在**一个地方（服务器）**执行一次，所有智能棋盘通过 API 访问，完全不关心数据库 schema 版本。

### Q4: 已有的 API endpoint 够用吗？

当前 REST API 覆盖度已经很好，棋盘端所需的大部分操作都有对应 endpoint：

| 功能 | Endpoint | 状态 |
|------|----------|------|
| 用户登录 | `POST /api/v1/auth/login` | 已有 |
| 用户注册 | `POST /api/v1/auth/register` | 已有 |
| Token 续期 | `POST /api/v1/auth/refresh` | **需新增** |
| 死活题列表 | `GET /api/v1/tsumego/levels` | 已有 |
| 死活题详情 | `GET /api/v1/tsumego/problems/{id}` | 已有 |
| 做题进度 | `GET/POST /api/v1/tsumego/progress` | 已有（需改造 merge 规则） |
| 棋谱搜索 | `GET /api/v1/kifu/albums` | 已有 |
| 棋谱详情 | `GET /api/v1/kifu/albums/{id}` | 已有 |
| 保存对局 | `POST /api/v1/user-games/` | 已有（需支持客户端传 id） |
| 对局列表 | `GET /api/v1/user-games/` | 已有 |
| 直播列表 | `GET /api/v1/live/matches` | 已有 |
| 设备心跳 | `POST /api/v1/board/heartbeat` | **需新增** |
| 健康检查 | `GET /health` | 已有 |

### Q5: 在线模式下，棋盘端本地还需要运行 FastAPI 吗？

**需要。** 棋盘端的 FastAPI 承担两个角色：

1. **API 代理**（在线时）：前端 React 仍然调用 `localhost:8001/api/v1/*`，本地 FastAPI 通过 RepositoryDispatcher 将请求路由到远程服务器
2. **离线服务**（离线时）：本地 FastAPI 直接操作 SQLite，提供降级功能

这样前端代码完全不需要修改——它始终调用同一个 URL，由后端决定数据来源。

### Q6: 同步操作永久失败后怎么办？

失败条目进入 dead letter 状态（`status = 'failed'`），处理流程：

1. **用户侧**：UI 显示黄色警告"N 条数据同步失败"，点击可查看详情和重试
2. **管理员侧**：设备心跳上报 `failed_count`，服务端告警通知管理员
3. **自动恢复**：用户手动点击"重试"后，`status` 重置为 `pending`，`retry_count` 清零
4. **最终兜底**：本地 SQLite 保留完整数据，不会丢失。即使同步失败，棋谱仍可在本地查看

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

### Phase 2：认证闭环 + 幂等契约（数据安全基础）

> **调整说明**：将认证和幂等能力提前到 Repository 抽象之前。这些是"最难回滚的数据一致性能力"，应优先落地。

| 改动 | 文件 | 影响 |
|------|------|------|
| 添加 `KATRAIN_MODE` + `REMOTE_API_URL` + `DEVICE_ID` | `config.py` | 纯增量 |
| 新增 `POST /api/v1/auth/refresh` | `auth.py` | 服务端新增 endpoint |
| `create_user_game()` 支持客户端传 `id` | `user_games.py` | 幂等改造 |
| `update_progress()` 实现字段级 merge | `tsumego.py` | 冲突解决改造 |

### Phase 3：远程 API 客户端 + 同步队列

| 改动 | 文件 | 影响 |
|------|------|------|
| 新建 `RemoteAPIClient`（含 refresh token） | `remote_client.py` (新) | 不影响现有代码 |
| 新建 `SyncQueueEntry` 模型（含完整状态机字段） | `models_db.py` | 仅新增表 |
| 新建 `SyncWorker`（含 asyncio.Lock + 租约） | `sync_worker.py` (新) | 不影响现有代码 |
| 新建 `ConnectivityManager` | `connectivity.py` (新) | 不影响现有代码 |

### Phase 4：Repository 抽象 + 启动逻辑分支

| 改动 | 文件 | 影响 |
|------|------|------|
| Repository Protocol + RepositoryDispatcher | `repository.py` (新) | 不影响现有代码 |
| `lifespan()` 增加 board 分支 | `server.py` | 仅在 board 模式生效 |
| Endpoint 注入 Repository | `tsumego.py`, `kifu.py`, `user_games.py` | 渐进改造 |

### Phase 5：可观测性 + UX + 安全加固

| 改动 | 文件 | 影响 |
|------|------|------|
| 设备心跳 endpoint | `board.py` (新) | 服务端新增 |
| `device_heartbeats` 表 | `models_db.py` | 仅新增表 |
| 离线 UX 组件（OfflineNotice 等） | React 前端 | 纯增量 |
| Guest-to-User 绑定 UI | React 前端 | 纯增量 |
| WebSocket 代理（board 模式） | `server.py` | 仅在 board 模式生效 |
| 凭据加密存储 | `credentials.py` (新) | 不影响现有代码 |
| 自动化升级脚本 | `scripts/board_upgrade.sh` (新) | 运维工具 |

### Phase 6：可选增强

| 改动 | 说明 |
|------|------|
| SQLCipher 本地数据库加密 | 依赖 ARM64 平台可用性验证 |
| 离线内容包（预置 200-500 题） | 提升离线体验 |
| 服务端告警 webhook | 设备监控通知 |

### 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| Repository 抽象改造影响现有 server 模式 | 中 | 默认走原有 SQLAlchemy 路径，仅 board 模式使用 Dispatcher |
| 远程 API 缺少某些 endpoint | 低 | 当前 API 覆盖度已经很好（见 Q4），Phase 2 补齐缺口 |
| 离线对局数据丢失 | 低 | SQLite 持久化 + sync_queue dead letter + 设备监控告警 |
| 网络抖动导致频繁模式切换 | 中 | 连续 3 次失败才切离线 + RTT 阈值 + in-flight 请求等待 |
| 同步重复写入 | 低 | idempotency_key + 服务端幂等去重 |
| Token 过期导致同步卡死 | 低 | refresh_token（90 天）+ auth_required 状态暂停队列 |
| 设备被盗数据泄露 | 中 | 凭据加密 + 远程撤销 + SQLCipher（可选） |

### 基础设施迁移（与 Phase 1-6 正交）

云端基础设施迁移（从家庭服务器迁移至阿里云集群）是**独立的运维操作**，不属于软件开发路线图。API-First 架构确保迁移不依赖任何代码变更。

| 时机 | 可行性 | 建议 |
|------|--------|------|
| Phase 1 完成后 | 可行 — 服务器已在运行 | 最低依赖，但无可观测性 |
| Phase 2-4 完成后 | 可行 — 棋盘端已在线运行 | 可在迁移后立即验证棋盘端功能 |
| **Phase 5 完成后** | **推荐** — 设备监控和告警已就绪 | 迁移后可通过心跳和日志确认所有棋盘正常连接 |
| Phase 6 完成后 | 可行 — 全部功能就绪 | 非必要等待 |

详细迁移步骤见 [Section 4.18.3 迁移路径](#4183-迁移路径拓扑-a--拓扑-b)。

---

## 9. 威胁模型

| 威胁 | 攻击面 | 缓解措施 | 残余风险 |
|------|--------|---------|---------|
| 设备被盗 | 物理访问 SQLite + 凭据文件 | refresh_token 加密存储 + 远程撤销 + SQLCipher（可选） | SQLCipher 不可用时本地数据可读 |
| 离线暴力读取 | 拆机读取 eMMC/SD 卡 | SQLCipher 加密（可选）+ 本地仅存缓存数据 | 无 PII 敏感数据（仅棋谱和做题记录） |
| 调试接口访问 | ADB/串口/SSH | 生产环境禁用 ADB、关闭 SSH 密码登录、禁用串口调试 | 供应链阶段需验证 |
| Token 泄露 | 内存 dump 或文件系统读取 | access_token 短期（1h）+ refresh_token 加密 + 绑定 device_id | 若 device_id 也泄露则可伪造 |
| 中间人攻击 | 网络嗅探 | 强制 HTTPS + 证书验证 | 需确保设备系统时间正确 |
| Replay 攻击 | 截获并重放 API 请求 | idempotency_key 去重 + 短期 access_token | - |
