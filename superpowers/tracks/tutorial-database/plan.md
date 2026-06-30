# 教程媒体存储方案设计文档 (Tutorial Media Storage)

> **For agentic workers:** REQUIRED SUB-SKILL — 用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 逐任务实施。步骤使用 `- [ ]` 复选框追踪。本文件先作为**设计文档 / 调研结论**；实施前请确认 §决策记录 中的待定项。

**状态:** 阶段 1 完成并上线生产 home-ubuntu (2026-06-28) · 存储抽象 + S3/MinIO 合并入 `develop`；MinIO 上线 + 全量迁移 27452 对象；**应用已切 `s3` 后端**——`/assets` 经 302 跳到 `https://go.sailorvoyage.top/media/`（nginx → MinIO over WireGuard `10.8.0.2:9000`，匿名只读 + Referer 防盗链）。HTTP 链路全验证（302 + 206 Range + 字节一致 854796 + 外站 Referer 403）。浏览器实机播放待人工眼检（本服务器无头 chromium 沙箱受限）。**阶段 2（阿里云 OSS+CDN）待办。**
>
> **阶段 3 后端完成（2026-06-30）** · K1（RemoteAPIClient tutorial 只读方法）+ K2（`/board/tutorials/*` 代理 + assets 302）+ K3（源站目录 `Cache-Control`+弱 ETag/304 中间件）+ K4（确认复用 `KATRAIN_REMOTE_URL`，零新配置）全部 TDD 落地并提交（K1/K2/K3 共 15 测试 + 回归 31 passed）。**K5 前端**（`tutorialApi.ts` 接 board 前缀）属前端 track `sbc-tutorial-parity`，本计划不实施。**K6 部署 + 浏览器实机眼检待人工**（docker compose 起源站 + board 实例 + curl 验证）。

---

## 0. 一句话目标

把教程模块生成的**视频 / 音频 / 页面图片**从"裸文件系统 + FastAPI 流式吐字节"迁移到**S3 兼容对象存储**抽象层：**阶段 1 自托管 MinIO**（home-ubuntu，零云费用），**阶段 2 上线前切换阿里云 OSS + CDN**（仅改配置，零业务代码改动）。数据库（PostgreSQL）只存对象 key + 元数据，**视频字节永不进数据库**。远端 web 与 SBC（始终在线）客户端通过 Range + 缓存头 + CDN 边缘缓存实现流畅播放。

---

## 1. 背景与调研结论 (Research)

### 1.1 核心结论：视频不进数据库

工业界几乎不把视频字节存进关系型/文档数据库（BLOB-in-DB 是公认反模式）：

- 数据库体积爆炸 → 备份/恢复/复制变慢且昂贵
- 流式传输会占满连接池与 worker，挤压正常业务查询
- 无法直接利用 HTTP Range、CDN、边缘缓存
- 对象存储的单 GB 成本远低于数据库存储

**标准三层分工**（本方案遵循）：

| 层 | 职责 | 本项目对应 |
|---|---|---|
| 数据库 | 元数据 + 对象 key/URL | PostgreSQL `tutorial_figures.video_asset` / `audio_asset` |
| 对象存储 (S3 API) | 真正的字节 | 阶段1 MinIO → 阶段2 阿里云 OSS |
| CDN / 缓存 | 就近分发、边缘缓存 | 阶段2 阿里云 CDN（阶段1 暂用 nginx + 浏览器缓存） |

棋谱 / SGF（`board_payload` JSON）放在 PostgreSQL 是**正确的**，保持不动 —— 它是结构化小数据，需要查询/编辑/审计（已有 `board_payload_history`）。

### 1.2 实测现状 (2026-06-27)

数据位于 `~/Repositories/katrain/data/tutorial_assets/`（注意：在 sibling repo，非本 repo）。

| 类型 | 数量 | 体积 | 备注 |
|---|---|---|---|
| 视频 MP4 | 651 | **1.39 GB** | 均值 2.1 MB · p50 1.2 MB · p90 4.6 MB · max 52 MB |
| 音频 MP3 | 1902 | 199 MB | |
| 页面图片 jpg/png | 24893 | 918 MB | OCR 页面截图 |
| **合计** | | **2.6 GB** | 9 本书里**仅 3 本**已生成视频 |

### 1.3 规模预估 (10×)

- 直接 10× 现有视频 → ~14 GB 视频 / ~26 GB 总量。
- 若把现有 9 本全部补齐视频再扩到 ~90 本书 → 仍为**几十 GB 量级**（medium tier）。
- **结论：存储成本可忽略**（OSS ≈ ¥0.12/GB/月 → 26 GB ≈ ¥3/月）。真正要解决的是**架构正确性 + 播放流畅度 + 平滑迁云**，不是省钱。
- 视频均为 2 MB 级**短片** → **不需要 HLS/DASH 自适应流**（那是给长视频/多码率准备的，对此场景过度设计）。渐进式 MP4 + Range + CDN 足矣。

### 1.4 现有代码事实（实施依据）

- `katrain/web/api/v1/endpoints/tutorials.py:37` `ASSET_BASE = Path("data")`；`:258` `/assets/{asset_path:path}` 手写 Range（206）逻辑，**字节穿过 FastAPI**。
- `katrain/web/core/models_db.py:357-358` `audio_asset` / `video_asset` 均为 `String(512)`，**已存的是相对 `data/` 的路径（≈ 对象 key）**，无需改表结构。
- 前端唯一出口：`katrain/web/ui/src/galaxy/api/tutorialApi.ts:80` `assetUrl(rel) => '/api/v1/tutorials/assets/' + rel`。**单点**，迁移友好。
- `katrain/web/core/config.py` pydantic `Settings`，`__init__` 内用 `os.getenv` 覆盖 → 在此加存储配置。
- `scripts/generate_video.py:731` 主合成已带 `-movflags +faststart`（起播关键，已具备）。
- `docker-compose.yml:23` 现挂载 `./data/tutorial_assets:/app/data/tutorial_assets`。

---

## 2. 目标架构 (Target Architecture)

引入 **`StorageBackend` 抽象**，两个实现共用一套接口：

```
                       ┌─────────────────────────────┐
  generate_video.py ──▶│  StorageBackend (interface)  │
  generate_voice.py    │   .put(key, file)            │
  /assets endpoint ────│   .get_range(key, start,end) │
                       │   .public_url(key) -> str     │
                       │   .exists(key) -> bool        │
                       └──────────┬──────────┬─────────┘
                                  │          │
                    ┌─────────────▼──┐   ┌───▼──────────────────┐
                    │ LocalStorage   │   │ S3Storage (boto3)    │
                    │ (现行为/开发)   │   │ MinIO ≡ 阿里云 OSS    │
                    └────────────────┘   └──────────────────────┘
```

**关键设计点：**

1. **后端选择由配置驱动**：`STORAGE_BACKEND=local|s3`。`s3` 实现对 MinIO 与 OSS **完全同构**（都是 S3 API），切换只改 endpoint/credentials/bucket/public-base-url。
2. **`public_url(key)` 是迁移的枢纽**：
   - `local` → `/api/v1/tutorials/assets/{key}`（FastAPI Range，现状）
   - `s3 + MinIO`（阶段1） → 经 nginx 反代的公开 URL，如 `https://media.<domain>/tutorial-assets/{key}`（或 presigned URL）
   - `s3 + OSS`（阶段2） → CDN 域名 `https://cdn.<domain>/{key}`（可选私有桶 + 签名 URL）
3. **`/assets/{path}` 端点保持存在**以向后兼容：`local` 走现有 Range；`s3` 则 **302 重定向**到 `public_url(key)`，把带宽从 app 卸载到对象存储/CDN。前端 `assetUrl()` 无需改动。
4. **DB 几乎零改动**：`video_asset`/`audio_asset` 直接当作 key 复用（规范化去掉前导 `/` 与 `data/` 前缀，bucket 名不入库）。

---

## 3. 文件结构 (File Structure)

| 动作 | 路径 | 职责 |
|---|---|---|
| **新建** | `katrain/web/core/storage/__init__.py` | 导出 `get_storage_backend()` 工厂 |
| **新建** | `katrain/web/core/storage/base.py` | `StorageBackend` 抽象基类 + `normalize_key()` |
| **新建** | `katrain/web/core/storage/local.py` | `LocalStorageBackend`（封装现有 `data/` + Range 逻辑） |
| **新建** | `katrain/web/core/storage/s3.py` | `S3StorageBackend`（boto3，兼容 MinIO/OSS） |
| **修改** | `katrain/web/core/config.py` | 加 `STORAGE_*` 配置（env 覆盖） |
| **修改** | `katrain/web/api/v1/endpoints/tutorials.py` | `/assets` 经后端解析：local→Range，s3→302；§1.4 的 has_video 检查改走 `backend.exists()` |
| **修改** | `scripts/generate_video.py` | 生成后 `backend.put()` 上传（local 后端为 no-op/原地） |
| **修改** | `scripts/generate_voice.py` | 同上，音频上传 |
| **新建** | `scripts/migrate_assets_to_minio.py` | 一次性迁移：filesystem → 对象存储，幂等 + 计数校验 |
| **修改** | `docker-compose.yml` | 加 `minio` 服务 + 卷；加 `mc` bootstrap（建桶/策略） |
| **新建** | `deploy/minio/bootstrap.sh` | 建桶 `tutorial-assets`、设匿名只读或生成 service account |
| **修改** | `requirements-web.txt` / `pyproject` | 加 `boto3` |
| **新建** | `tests/test_storage_backend.py` | 抽象层契约测试（local + 用 moto/MinIO 测 s3） |
| **修改** | 本文件 | 实施中勾选进度 |

**新增 deps:** `boto3`（+ 测试用 `moto` 或起一个 MinIO 容器）。

---

## 4. 配置项 (Config — `config.py`)

```python
# Storage
STORAGE_BACKEND: str = "local"          # local | s3
S3_ENDPOINT_URL: str = ""               # MinIO: http://minio:9000 ; OSS: https://oss-cn-<region>.aliyuncs.com
S3_REGION: str = ""                     # OSS: cn-hangzhou 等；MinIO 可留空
S3_BUCKET: str = "tutorial-assets"
S3_ACCESS_KEY: str = ""
S3_SECRET_KEY: str = ""
S3_PUBLIC_BASE_URL: str = ""            # 客户端可达的公开前缀：阶段1 nginx 反代域名；阶段2 CDN 域名
S3_USE_PRESIGNED: bool = False          # 私有桶时 True → public_url() 返回签名 URL
S3_PRESIGN_TTL_SEC: int = 3600
```

对应 env（`__init__` 内 `setdefault(os.getenv(...))`）：
`KATRAIN_STORAGE_BACKEND` / `KATRAIN_S3_ENDPOINT_URL` / `KATRAIN_S3_REGION` / `KATRAIN_S3_BUCKET` / `KATRAIN_S3_ACCESS_KEY` / `KATRAIN_S3_SECRET_KEY` / `KATRAIN_S3_PUBLIC_BASE_URL` / `KATRAIN_S3_USE_PRESIGNED`.

---

## 阶段 1 — 自托管 MinIO（现在）

> 目标：把"S3 这条路"在自家服务器**完整跑通并验证**，新生成的资产直接落对象存储，迁云风险提前暴露。

### Task 0：分支 + 前置确认
- [ ] 从 `feature/tutorial-database` 切分支 `feat/tutorial-media-storage`。
- [ ] 确认 §决策记录 待定项已定（public URL 走法、桶访问策略）。
- [ ] 确认 sibling repo `~/Repositories/katrain/data/tutorial_assets` 为权威数据源，备份一份再动。

### Task 1：存储抽象层 + Local 实现（TDD，行为不变）
**先写测试**（`tests/test_storage_backend.py`）：契约 = `put / exists / size / read / read_range / public_url / normalize_key`。
- [x] `base.py`：`StorageBackend` ABC；`normalize_key()` 去前导 `/`、去 `data/` 前缀、折叠反斜杠、禁止 `..`（替代现 `_safe_asset_path` 的防穿越）。
- [x] `local.py`：`LocalStorageBackend(base_dir="data")` 实现全部方法；`is_remote=False`；`public_url` 返回 `/api/v1/tutorials/assets/{key}`；`read_range` 复用 seek/read。
- [x] `__init__.py`：`get_storage_backend()` 按 `settings.STORAGE_BACKEND` 返回 memoized 单例；s3 后端 lazy import（boto3 仅 s3 时需要）。
- [x] `config.py`：加 `STORAGE_*` 配置 + env 覆盖（提前于 Task 2 落地，集中管理）。
- [x] **测试**：22 passed（契约 + 工厂 + 防穿越）。`STORAGE_BACKEND=local` 行为与现状一致。
- [x] **验收**：生产服务器端点接入后手动验证逐字节一致（live local 206 + MinIO 匿名 206，同为 854796 字节，content-type/cache-control 一致）。

### Task 2：S3 实现（boto3）
- [x] `s3.py`：boto3 client（path-style + s3v4，兼容 MinIO/OSS）；`is_remote=True`。
- [x] `put(key, bytes|fileobj, content_type)`：带 `ContentType`（显式或按扩展名推断）与 `CacheControl: public, max-age=31536000, immutable`。
- [x] `public_url(key)`：`use_presigned` → `generate_presigned_url`；否则 `f"{S3_PUBLIC_BASE_URL}/{key}"`。
- [x] `exists` / `size` / `read` / `read_range`（缺失映射为 `FileNotFoundError`，与 local 一致）。
- [x] **测试**：moto 模拟，`tests/test_storage_s3.py`，含公开/预签名两路；**37 passed**（含 local）。
- [x] `boto3>=1.34.0` 加入 `requirements-web.txt`；已装 boto3 1.43 + moto 5.2 到 py311_katago。

### Task 3：接入 `/assets` 端点
- [x] `tutorials.py` 用 `get_storage_backend()`；`get_asset`：`is_remote`→302 到 `public_url`；`local`→Range/FileResponse（`backend.fspath`，大文件不进内存）。
- [x] `get_sections` 的 `has_video` 改为 `backend.exists(...)`。
- [x] 删除 dead `_safe_asset_path` / `ASSET_BASE` / 未用 `Path` 导入（防穿越收敛到 `normalize_key`）。
- [x] `base.py` 加 `fspath()` 钩子（local 返回 Path，remote 返回 None）。
- [x] **测试**：`tests/test_tutorial_assets_endpoint.py`（httpx AsyncClient，local 200/206/404/防穿越 + remote 302/404）；**43 passed**（全套）。
- [x] **galaxy 端到端**：前端 `assetUrl()` 不改；`s3` 后端下 `/assets` → 302 → `…/media/…` → 206（HTTP 全验证）。浏览器/SBC kiosk 实机眼检待人工（服务器无头 chromium 受限）。

### Task 4：MinIO 服务上线
- [x] `docker-compose.yml` 加 `minio` 服务（9000/9001 **仅绑 127.0.0.1**，命名卷 `minio-data`，healthcheck）+ `minio-setup` 一次性服务跑 bootstrap；`katrain-web` 加 `STORAGE_*` env 并 `depends_on minio`。
- [x] `deploy/minio/bootstrap.sh`：`mc` 建桶 + `mc anonymous set download`（D7），幂等。**实测**：本地起 MinIO 跑通，bucket 创建 + 匿名只读生效。
- [x] `deploy/minio/nginx-media.conf`：`https://media.<domain>` 反代 `127.0.0.1:9000`，Referer/域名白名单防盗链，Range 透传，TLS 占位（D6）。
- [x] app env 模板就位（compose 内 `KATRAIN_STORAGE_BACKEND=s3` 等，phase2 改值即切 OSS）。
- [x] **生产 MinIO 部署完成**：`docker compose up -d minio minio-setup` 跑通（minio healthy + 桶 `tutorial-assets` + 匿名只读），生产 `.env` 就位（`KATRAIN_STORAGE_BACKEND=local` + 强 MinIO 凭据）。`media.<domain>` 证书+nginx + 跳板机 :9000 反代留待 Stage B。

### Task 5：历史数据迁移
- [x] `scripts/migrate_assets_to_minio.py`：遍历 `data/tutorial_assets/**`，幂等上传（exists+size 匹配则跳过）+ 结尾计数校验；`--book/--force/--dry-run`；拒绝对 local 后端运行；**非破坏（D8）只读本地**。
- [x] **实测**（本地 MinIO，7 文件真实样本）：dry-run ✓、真实迁移 7 上传+校验通过 ✓、重跑 7 全 skip（幂等）✓。
- [x] **抽样播放校验**（curl 匿名）：mp4 200 + Range 206 + `video/mp4` + `Cache-Control: max-age=86400`，mp3 `audio/mpeg`，缺失 404。
- [x] **服务器全量迁移完成**：27452 对象（651 视频 / 1902 音频 / 24893 图片）经 `migrate_assets_to_minio.py` 上传，计数校验通过（bucket==local==27452，0 失败）；本地未删（D8）。

### Task 6：生成即上传 (write-through)
- [x] `storage/__init__.py` 加 `upload_file(key, path)`：**仅 remote 后端上传**（local 后端是磁盘本身→no-op），失败仅告警不中断批量（可由迁移脚本补齐）。
- [x] 接入 4 个产出点：`generate_video.py`（figure 视频+poster、section 视频+poster）、`generate_voice.py`（音频）、`services.generate_figure_audio`（API 路径音频）。
- [x] **本地永久保留**（D8）：生成始终写本地（权威镜像），再上传分发层；不删本地。
- [x] 测试：`upload_file` 三例（local no-op / remote 上传 / 缺失源吞错），全套 46 passed。

### Task 7：播放流畅度 & 缓存
- [x] faststart 核查：主合成（:731）+ section 拼接（:1060）均已带 `+faststart`。
- [x] 缓存：抽出共享常量 `MEDIA_CACHE_CONTROL = "public, max-age=86400"`，**一致**应用于 S3 上传 + local 端点（206/FileResponse）。**未用 immutable**——内容仍在按稳定 key 重生成，1 天 TTL 可自愈脏缓存；静态化后可上调 immutable + 版本化 key（见注）。
- [x] **实测**缓存头随对象返回（curl 验证）。
- [ ] 前端预取（可选，未做）：kiosk 翻页预取下一 figure 视频；SBC 始终在线，无需离线包。

### 阶段 1 验收标准
- [x] **代码层**：`STORAGE_BACKEND=s3` 切换、s3 后端 put/get/range/public_url、端点 302/Range、写入即上传——全部单测 + 真实 MinIO 集成验证通过。
- [x] 资产字节不再穿过 FastAPI（s3 路径为 302）。
- [x] 迁移脚本幂等 + 计数校验 + 匿名 Range 播放——真实样本跑通。
- [x] **服务器端到端**：生产 MinIO 部署 + 全量迁移（27452）+ 翻 `s3` 后端；走 WireGuard 路径 `nginx /media/ → 10.8.0.2:9000`（非 `media.<domain>` 子域名，复用现有证书，零 DNS）。HTTP 链路全验证通过。浏览器/kiosk 实机眼检待人工。

---

## 阶段 2 — 阿里云 OSS + CDN（上线前）

> 因 MinIO 与 OSS 同为 S3 API，本阶段**理想情况零业务代码改动**，主要是开通云资源 + 数据搬迁 + 配置切换 + 合规。

### 待办（上线前执行，当前不实施，仅记录 runbook）
- [ ] **提前启动**：自有域名 **ICP 备案**（中国大陆挂 CDN 必需，走流程耗时，最早启动）。
- [ ] 开通阿里云 OSS，建桶 `tutorial-assets`（区域就近用户，如 `cn-hangzhou`/`cn-shanghai`）。
- [ ] 开通阿里云 CDN，源站指向 OSS bucket，绑定 CDN 加速域名 `cdn.<domain>`。
- [ ] 数据搬迁：`mc mirror minio/tutorial-assets oss/tutorial-assets`（或 OSS ossutil / ossimport）。计数校验。
- [ ] 配置切换（**仅改 env，无需改代码**）：
      `KATRAIN_S3_ENDPOINT_URL=https://oss-cn-<region>.aliyuncs.com`、`KATRAIN_S3_REGION`、OSS RAM 子账号 keys、`KATRAIN_S3_PUBLIC_BASE_URL=https://cdn.<domain>`。
- [ ] 访问控制：**公开只读桶 + CDN Referer/域名防盗链**（D7，`S3_USE_PRESIGNED=false`，与阶段1 同策略，CDN 命中率最高）。
- [ ] CDN 缓存规则：mp4/mp3/图片长 TTL；校验 Range 回源正常（OSS + CDN 原生支持）。
- [ ] 灰度：先切一部分流量/一本书验证，再全量。
- [ ] 成本监控：OSS 存储 + CDN 流量看板。

### 注意（boto3 连 OSS 的坑）
- OSS 兼容 S3 API 但**非 100%**；boto3 基本可用（put/get/list/presign）。如遇兼容问题，备选 OSS 官方 SDK `oss2`，在 `s3.py` 旁加 `oss.py` 实现同一 `StorageBackend` 接口即可（抽象层价值正在于此）。

---

## 5. 决策记录 (Decisions & Open Questions)

| # | 决策 | 状态 |
|---|---|---|
| D1 | 阶段1 用 MinIO（非纯文件系统抽象） | ✅ 已定（用户） |
| D2 | 阶段2 云厂商 = 阿里云 OSS | ✅ 已定（用户） |
| D3 | 用户始终在线，**不做离线包** | ✅ 已定 |
| D4 | 视频字节不进数据库；DB 只存 key | ✅ 已定（行业标准） |
| D5 | 短片不上 HLS/DASH，用渐进式 MP4 + Range | ✅ 已定（规模决定） |
| D6 | MinIO 对外可达 = **nginx 反代公开 URL**（`https://media.<domain>` → `minio:9000`），不裸暴露 :9000/:9001 | ✅ 已定（用户） |
| D7 | 桶访问策略 = **公开只读 + Referer/域名防盗链**（CDN 命中率最高、实现最简，教程内容非敏感）→ `S3_USE_PRESIGNED=false` | ✅ 已定（用户） |
| D8 | **本地永久保留完整副本**：对象存储仅作分发层，本地为权威镜像；生成走 write-through（写本地 + 上传），**从不删本地** | ✅ 已定（用户） |

---

## 6. 风险 (Risks)

- **MinIO 对外暴露**：必须经 nginx 反代 + 限制，勿直接裸暴露 `:9000`/`:9001`。
- **缓存脏数据**：内容更新若复用同 key + 长 TTL → 客户端看旧视频。对策：更新即换 key 或加版本参数 + CDN 刷新。
- **OSS 非完全 S3 兼容**：见 §阶段2 注意；抽象层已预留 `oss2` 后备实现位。
- **迁移期数据双写/漂移**：迁移脚本幂等 + 计数校验 + 校验通过前不删本地。
- **ICP 备案阻塞**：纯流程性但耗时，阶段2 最早启动。

---

## 7. 不做什么 (Out of Scope)

- HLS/DASH 自适应流、转码流水线（短片不需要）。
- 离线下载 / SBC 本地预置包（用户始终在线）。
- `board_payload`/SGF 存储改动（已正确在 PostgreSQL）。
- 视频生成算法本身的改动（仅加"生成后上传"一步）。


---

## 阶段 3 — Kiosk 教程车队访问（board-proxy + 目录缓存 + CDN 就绪）

> 补充于 2026-06-29。承接前端 track `sbc-tutorial-parity`（kiosk 只读教程模块）的远端数据需求。
>
> **背景**：棋智盒终端以 `KATRAIN_MODE=board` 运行（瘦客户端，本地 SQLite 无教程数据）；教程目录 + 媒体只存在于远端（PostgreSQL + MinIO/OSS）。目标是让成千上万终端就近、低成本读取远端教程，且家用服务器 → 阿里云/UCloud 迁移零终端改动。
>
> **架构决策（D9）：复用既有 board-proxy 模式**（与 `/api/v1/board/live/*` 同构），**不给后端加 CORS**。理由：与现有架构一致；浏览器 → 本机 board katrain 为**同源**（无 CORS/预检）；写端点不暴露跨域；迁云只改 `KATRAIN_REMOTE_URL`。此决策取代早期「加 CORS 直连」的设想。

### 3.1 现有代码事实（实施依据，2026-06-29 核对）

- `server.py:460` `app = FastAPI(lifespan=lifespan)`，`:461` `include_router(api_router, prefix="/api/v1")`，**无任何中间件 / 无 CORS**。`:464` `KATRAIN_MODE=="board"` 时服务 `static-kiosk-2d`，并在 `app.state.remote_client` 挂 `RemoteAPIClient`。
- board-proxy 范式：`api/v1/endpoints/board.py` 下 `/board/live/*` 用 `_get_remote_client(request)` + `_proxy(call, what)` 把只读请求转发到远端。前端 kiosk 走 `/api/v1/board/live`（`ui/src/api/live.ts:17`：`__KIOSK_2D_ONLY__ ? '/api/v1/board/live' : '/api/v1/live'`）。
- `RemoteAPIClient`（`core/remote_client.py`）：`:31` `self.base_url`；`:100` 通用 `_request(method, path, *, json, params, auth=True)`；已有 `get_live_*` 等域方法，**尚无 tutorial 方法**。
- 远端教程只读端点（`tutorials.py`，server mode，公开 GET，无鉴权依赖）：`/categories`(`:45`)、`/categories/{category}/books`(`:56`)、`/books/{id}`(`:67`)、`/books/{id}/chapters`(`:85`)、`/chapters/{id}/sections`(`:98`)、`/sections/{id}`(`:118`)、`/figures/{id}`(`:131`)；`/assets/{path:path}`(`:252`) 已 302→公开媒体并带 `MEDIA_CACHE_CONTROL`。注意 `GET /books/{id}`(`:79`) 返回的 `TutorialBookDetailOut` **已内嵌 `chapters`**，故 `/books/{id}/chapters` 仅为完整性代理，kiosk 主导航可只用 book detail。
- 目录 JSON 端点**无 `Cache-Control`/`ETag`** → 当前不可边缘缓存（车队规模下必须补，否则每终端每次都击穿源站 + DB）。
- `config.py`：board 模式已有 `REMOTE_API_URL`（env `KATRAIN_REMOTE_URL`），tutorial 代理**复用**它，无需新增。

### 3.2 目标

1. kiosk 经 `/api/v1/board/tutorials/*`（本机 board katrain，**同源**）读取远端教程目录 → 无需 CORS、与 live 一致。
2. 视频按需流式（前端 `<video preload="none">`），仅播放当前小节，**不在 2GB 终端落盘**（媒体字节也不经 board katrain）。
3. 远端目录端点可缓存（`Cache-Control` + `ETag`/304）→ 车队规模下源站不被击穿；阶段 2 CDN 命中率高。

### Task K1：RemoteAPIClient 加 tutorial 只读方法

**Files:**
- Modify: `katrain/web/core/remote_client.py`（紧随 `get_live_*`，约 `:259` 之后）
- Test: `tests/web_ui/test_remote_tutorial_methods.py`（新建）

**Interfaces:**
- Consumes（均已存在）：`RemoteAPIClient._request(method, path, *, json=None, params=None, auth=True) -> httpx.Response`（`:100`）；`self.base_url`（`:31`）。构造签名 `RemoteAPIClient(base_url: str, device_id: str, ...)`（`:24`）。
- Produces（供 K2 调用，签名/返回类型固定）：
  - `get_tutorial_categories() -> Any`
  - `get_tutorial_books(category: str) -> Any`
  - `get_tutorial_book(book_id: int) -> Any`
  - `get_tutorial_chapters(book_id: int) -> Any`
  - `get_tutorial_sections(chapter_id: int) -> Any`
  - `get_tutorial_section(section_id: int) -> Any`
  - `get_tutorial_figure(figure_id: int) -> Any`

> 教程是公开内容 → 全部 `auth=False`（不绑定 board 登录），镜像 `get_live_match` 的 `_request → raise_for_status → json()` 三段式。`get_tutorial_chapters` 覆盖源站 `GET /books/{id}/chapters`（`tutorials.py:85`）；`GET /books/{id}` 已内嵌 `chapters`（`tutorials.py:79`），故该方法是为对齐源站全部只读端点的**完整性补全**，kiosk 主导航可只用 book detail。

- [x] **Step 1: 写失败测试** `tests/web_ui/test_remote_tutorial_methods.py`

```python
"""K1: RemoteAPIClient tutorial read-only methods forward to the right paths, auth=False."""
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote

import pytest

from katrain.web.core.remote_client import RemoteAPIClient


def _client_with_capture():
    c = RemoteAPIClient(base_url="http://up", device_id="test-dev")
    captured = {}

    async def fake_request(method, path, *, json=None, params=None, auth=True):
        captured.update(method=method, path=path, auth=auth)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"ok": True})
        return resp

    c._request = AsyncMock(side_effect=fake_request)
    return c, captured


@pytest.mark.asyncio
async def test_categories_path_and_public():
    c, cap = _client_with_capture()
    assert await c.get_tutorial_categories() == {"ok": True}
    assert (cap["method"], cap["path"], cap["auth"]) == ("GET", "/api/v1/tutorials/categories", False)


@pytest.mark.asyncio
async def test_books_url_encodes_category():
    c, cap = _client_with_capture()
    await c.get_tutorial_books("围棋 入门")
    assert cap["path"] == f"/api/v1/tutorials/categories/{quote('围棋 入门')}/books"
    assert cap["auth"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call, expected_path",
    [
        (lambda c: c.get_tutorial_book(7), "/api/v1/tutorials/books/7"),
        (lambda c: c.get_tutorial_chapters(7), "/api/v1/tutorials/books/7/chapters"),
        (lambda c: c.get_tutorial_sections(12), "/api/v1/tutorials/chapters/12/sections"),
        (lambda c: c.get_tutorial_section(34), "/api/v1/tutorials/sections/34"),
        (lambda c: c.get_tutorial_figure(56), "/api/v1/tutorials/figures/56"),
    ],
)
async def test_id_based_paths(call, expected_path):
    c, cap = _client_with_capture()
    await call(c)
    assert cap["path"] == expected_path
    assert cap["auth"] is False
```

- [x] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/web_ui/test_remote_tutorial_methods.py -v`
Expected: FAIL — `AttributeError: 'RemoteAPIClient' object has no attribute 'get_tutorial_categories'`.

- [x] **Step 3: 实现 7 个方法**（紧随 `get_live_translations` 之后）

```python
# ── Tutorial (read-only, public) ──
async def get_tutorial_categories(self) -> Any:
    resp = await self._request("GET", "/api/v1/tutorials/categories", auth=False)
    resp.raise_for_status()
    return resp.json()

async def get_tutorial_books(self, category: str) -> Any:
    from urllib.parse import quote
    resp = await self._request("GET", f"/api/v1/tutorials/categories/{quote(category)}/books", auth=False)
    resp.raise_for_status()
    return resp.json()

async def get_tutorial_book(self, book_id: int) -> Any:
    resp = await self._request("GET", f"/api/v1/tutorials/books/{book_id}", auth=False)
    resp.raise_for_status()
    return resp.json()

async def get_tutorial_chapters(self, book_id: int) -> Any:
    resp = await self._request("GET", f"/api/v1/tutorials/books/{book_id}/chapters", auth=False)
    resp.raise_for_status()
    return resp.json()

async def get_tutorial_sections(self, chapter_id: int) -> Any:
    resp = await self._request("GET", f"/api/v1/tutorials/chapters/{chapter_id}/sections", auth=False)
    resp.raise_for_status()
    return resp.json()

async def get_tutorial_section(self, section_id: int) -> Any:
    resp = await self._request("GET", f"/api/v1/tutorials/sections/{section_id}", auth=False)
    resp.raise_for_status()
    return resp.json()

async def get_tutorial_figure(self, figure_id: int) -> Any:
    resp = await self._request("GET", f"/api/v1/tutorials/figures/{figure_id}", auth=False)
    resp.raise_for_status()
    return resp.json()
```

- [x] **Step 4: 跑测试确认通过**

Run: `CI=true uv run pytest tests/web_ui/test_remote_tutorial_methods.py -v`
Expected: PASS（7 个用例）。

- [x] **Step 5: commit**

```bash
git add katrain/web/core/remote_client.py tests/web_ui/test_remote_tutorial_methods.py
git commit -m "feat(board): RemoteAPIClient tutorial read-only proxy methods (K1)"
```

### Task K2：board.py 加 `/board/tutorials/*` 只读代理

**Files:**
- Modify: `katrain/web/api/v1/endpoints/board.py`（镜像 `/board/live/*`，约 `:139` 路由区；顶部 `:7-19` import 区加 `RedirectResponse`）
- Test: `tests/web_ui/test_board_tutorial_proxy.py`（新建，镜像 `tests/web_ui/test_board_live_proxy.py`）

**Interfaces:**
- Consumes: K1 的 `get_tutorial_*` 方法（名字/签名必须逐字对齐 K1 Produces）；已存在的 `_get_remote_client(request)`（`:110`）、`_proxy(call, what)`（`:118`，上游 4xx 透传、连接错误→502、非 board→503）、`self.base_url`（remote client）。
- Produces: 7 个只读路由 `/api/v1/board/tutorials/*`（6 JSON + 1 assets 302），供 K5 前端 kiosk 调用。

> 各前缀互不冲突（无 live 那种 featured-vs-`{id}` 顺序坑）：`/books/{id}` 与 `/books/{id}/chapters` 是不同段，FastAPI 不会相互 shadow。

- [x] **Step 1: 写失败测试** `tests/web_ui/test_board_tutorial_proxy.py`

```python
"""K2: board-mode tutorial proxy forwards reads to RemoteAPIClient; assets → 302; errors map."""
import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.server import create_app


def _http_status_error(code: int, text: str = "") -> httpx.HTTPStatusError:
    resp = MagicMock(); resp.status_code = code; resp.text = text
    return httpx.HTTPStatusError(f"{code}", request=MagicMock(), response=resp)


@pytest.fixture
def board_app():
    db_path = "test_board_tutorial_proxy.db"
    os.environ["KATRAIN_DATABASE_PATH"] = db_path
    if os.path.exists(db_path):
        os.remove(db_path)
    app = create_app(enable_engine=False)
    client = MagicMock()
    client.base_url = "http://up"
    client.get_tutorial_categories = AsyncMock(return_value=[{"category": "joseki", "book_count": 3}])
    client.get_tutorial_books = AsyncMock(return_value=[{"id": 1}])
    client.get_tutorial_book = AsyncMock(return_value={"id": 1, "chapters": []})
    client.get_tutorial_chapters = AsyncMock(return_value=[{"id": 9}])
    client.get_tutorial_sections = AsyncMock(return_value=[{"id": 5}])
    client.get_tutorial_section = AsyncMock(return_value={"id": 5, "figures": []})
    client.get_tutorial_figure = AsyncMock(return_value={"id": 7})
    app.state.remote_client = client
    yield app
    if os.path.exists(db_path):
        os.remove(db_path)


async def _get(app, path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get(path, follow_redirects=False)


@pytest.mark.asyncio
async def test_all_json_proxies_reachable(board_app):
    assert (await _get(board_app, "/api/v1/board/tutorials/categories")).json()[0]["book_count"] == 3
    assert (await _get(board_app, "/api/v1/board/tutorials/categories/joseki/books")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/tutorials/books/1")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/tutorials/books/1/chapters")).json()[0]["id"] == 9
    assert (await _get(board_app, "/api/v1/board/tutorials/chapters/9/sections")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/tutorials/sections/5")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/tutorials/figures/7")).status_code == 200
    board_app.state.remote_client.get_tutorial_books.assert_awaited_once_with("joseki")
    board_app.state.remote_client.get_tutorial_chapters.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_asset_redirects_to_remote_gateway(board_app):
    resp = await _get(board_app, "/api/v1/board/tutorials/assets/book/video/section_5.mp4")
    assert resp.status_code == 302
    assert resp.headers["location"] == "http://up/api/v1/tutorials/assets/book/video/section_5.mp4"


@pytest.mark.asyncio
async def test_upstream_404_passes_through(board_app):
    board_app.state.remote_client.get_tutorial_section.side_effect = _http_status_error(404, "not found")
    assert (await _get(board_app, "/api/v1/board/tutorials/sections/999")).status_code == 404


@pytest.mark.asyncio
async def test_upstream_unreachable_maps_502(board_app):
    board_app.state.remote_client.get_tutorial_categories.side_effect = httpx.ConnectError("refused")
    assert (await _get(board_app, "/api/v1/board/tutorials/categories")).status_code == 502


@pytest.mark.asyncio
async def test_not_board_mode_503():
    os.environ["KATRAIN_DATABASE_PATH"] = "test_board_tutorial_proxy_nb.db"
    app = create_app(enable_engine=False)  # no remote_client on app.state
    resp = await _get(app, "/api/v1/board/tutorials/categories")
    assert resp.status_code == 503
```

- [x] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/web_ui/test_board_tutorial_proxy.py -v`
Expected: FAIL — 路由未注册（404 而非预期状态码）。

- [x] **Step 3a: 加 import**（`board.py` 顶部 import 区）

```python
from fastapi.responses import RedirectResponse
```

- [x] **Step 3b: 加路由**（紧随 `/board/live/*` 路由区之后）

```python
# ── Tutorial Proxy (board mode only) ──
@router.get("/tutorials/categories")
async def proxy_tutorial_categories(request: Request):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_categories(), "Tutorial categories")

@router.get("/tutorials/categories/{category}/books")
async def proxy_tutorial_books(request: Request, category: str):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_books(category), "Tutorial books")

@router.get("/tutorials/books/{book_id}")
async def proxy_tutorial_book(request: Request, book_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_book(book_id), "Tutorial book")

@router.get("/tutorials/books/{book_id}/chapters")
async def proxy_tutorial_chapters(request: Request, book_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_chapters(book_id), "Tutorial chapters")

@router.get("/tutorials/chapters/{chapter_id}/sections")
async def proxy_tutorial_sections(request: Request, chapter_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_sections(chapter_id), "Tutorial sections")

@router.get("/tutorials/sections/{section_id}")
async def proxy_tutorial_section(request: Request, section_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_section(section_id), "Tutorial section")

@router.get("/tutorials/figures/{figure_id}")
async def proxy_tutorial_figure(request: Request, figure_id: int):
    c = _get_remote_client(request)
    return await _proxy(lambda: c.get_tutorial_figure(figure_id), "Tutorial figure")

# Media: redirect to the remote asset gateway (which itself 302s to the public
# media domain). Bytes never traverse the board katrain; the browser follows the
# redirect chain and streams from media.<domain>.
@router.get("/tutorials/assets/{asset_path:path}")
async def proxy_tutorial_asset(request: Request, asset_path: str):
    c = _get_remote_client(request)
    return RedirectResponse(f"{c.base_url}/api/v1/tutorials/assets/{asset_path}", status_code=302)
```

- [x] **Step 4: 跑测试确认通过**

Run: `CI=true uv run pytest tests/web_ui/test_board_tutorial_proxy.py -v`
Expected: PASS（含 503 / 404 / 502 / 302 全路径）。

- [x] **Step 5: commit**

```bash
git add katrain/web/api/v1/endpoints/board.py tests/web_ui/test_board_tutorial_proxy.py
git commit -m "feat(board): /board/tutorials/* read-only proxy + asset 302 (K2)"
```

### Task K3：远端目录端点加缓存（源站，server mode）

**Files:**
- Create: `katrain/web/core/catalog_cache.py`（集中实现的目录缓存中间件 + 常量）
- Modify: `katrain/web/server.py`（`create_app` 内 `include_router` 之后注册中间件，约 `:461` 后）
- Test: `tests/web_ui/test_catalog_cache.py`（新建）

**Interfaces:**
- Produces: `CATALOG_CACHE_CONTROL: str`；`add_catalog_cache_middleware(app: FastAPI) -> None`。
- 作用范围：仅 `GET /api/v1/tutorials/*` 且**排除** `/assets/*`（媒体已自带 `MEDIA_CACHE_CONTROL` + 302，见 `tutorials.py:271/295/301`）；只对 `200` 响应加头。写端点（PUT/POST）天然不命中（非 GET）。

> 集中到一个 `@app.middleware("http")` 而非逐端点改签名：目录 JSON 小、可安全缓冲整段算弱 ETag。**已知局限（不在本任务范围）**：board 侧 `_proxy()` 当前不转发 `If-None-Match`，故 v1 的 304 只服务于「源站 ↔ 阶段 2 CDN / 浏览器直连」，车队→board→源站 的逐跳 304 依赖阶段 2 CDN 边缘缓存（+ 可选 K4 内存缓存）。

- [x] **Step 1: 写失败测试** `tests/web_ui/test_catalog_cache.py`

```python
"""K3: catalog GETs get Cache-Control + weak ETag; If-None-Match → 304; /assets untouched."""
import pytest
from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient

from katrain.web.core.catalog_cache import CATALOG_CACHE_CONTROL, add_catalog_cache_middleware


def _stub_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/tutorials/categories")
    async def categories():
        return [{"category": "joseki"}]

    @app.get("/api/v1/tutorials/assets/{p:path}")
    async def asset(p: str):
        return Response(content=b"\x00\x01", media_type="video/mp4")

    add_catalog_cache_middleware(app)
    return app


async def _get(app, path, headers=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        return await ac.get(path, headers=headers or {})


@pytest.mark.asyncio
async def test_catalog_gets_cache_control_and_weak_etag():
    resp = await _get(_stub_app(), "/api/v1/tutorials/categories")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == CATALOG_CACHE_CONTROL
    assert resp.headers["etag"].startswith('W/"')
    assert resp.json() == [{"category": "joseki"}]


@pytest.mark.asyncio
async def test_if_none_match_returns_304():
    app = _stub_app()
    etag = (await _get(app, "/api/v1/tutorials/categories")).headers["etag"]
    again = await _get(app, "/api/v1/tutorials/categories", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["etag"] == etag
    assert again.content == b""


@pytest.mark.asyncio
async def test_assets_path_not_touched():
    resp = await _get(_stub_app(), "/api/v1/tutorials/assets/x/y.mp4")
    assert "etag" not in {k.lower() for k in resp.headers}
```

- [x] **Step 2: 跑测试确认失败**

Run: `CI=true uv run pytest tests/web_ui/test_catalog_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: katrain.web.core.catalog_cache`.

- [x] **Step 3a: 写中间件模块** `katrain/web/core/catalog_cache.py`

```python
"""Source-station caching for tutorial *catalog* (read-only JSON) endpoints.

Adds `Cache-Control` + a weak `ETag` to `GET /api/v1/tutorials/*` JSON responses
(excludes `/assets/*`, which already carry their own long TTL + 302) and answers
`If-None-Match` with 304. Lets an edge/CDN cache the catalog so a large fleet does
not hammer the source DB. Media keeps its own immutable-leaning long TTL.
"""
import hashlib
import os

from fastapi import FastAPI, Request, Response

# Catalog changes rarely; short TTL + SWR lets edges serve stale while revalidating.
_MAX_AGE = int(os.getenv("KATRAIN_TUTORIAL_CATALOG_MAX_AGE", "300"))
CATALOG_CACHE_CONTROL = f"public, max-age={_MAX_AGE}, stale-while-revalidate=86400"


def _is_catalog(request: Request) -> bool:
    p = request.url.path
    return request.method == "GET" and p.startswith("/api/v1/tutorials/") and "/assets/" not in p


def add_catalog_cache_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def _catalog_cache(request: Request, call_next):
        response = await call_next(request)
        if not (_is_catalog(request) and response.status_code == 200):
            return response
        # Buffer the (small) JSON body to compute a weak validator.
        body = b"".join([chunk async for chunk in response.body_iterator])
        etag = 'W/"' + hashlib.sha256(body).hexdigest()[:32] + '"'
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": CATALOG_CACHE_CONTROL},
            )
        headers = dict(response.headers)
        headers["ETag"] = etag
        headers["Cache-Control"] = CATALOG_CACHE_CONTROL
        headers.pop("content-length", None)  # re-sent below; let Starlette recompute
        return Response(content=body, status_code=200, headers=headers, media_type=response.media_type)
```

- [x] **Step 3b: 注册中间件**（`katrain/web/server.py`，`app.include_router(api_router, prefix="/api/v1")` 之后）

```python
from katrain.web.core.catalog_cache import add_catalog_cache_middleware  # top of file
# ...
add_catalog_cache_middleware(app)
```

- [x] **Step 4: 跑测试确认通过**

Run: `CI=true uv run pytest tests/web_ui/test_catalog_cache.py -v`
Expected: PASS（3 用例）。

- [x] **Step 5: 回归 + commit**

```bash
CI=true uv run pytest tests/web_ui/test_board_live_proxy.py tests/web_ui/test_catalog_cache.py -q
git add katrain/web/core/catalog_cache.py katrain/web/server.py tests/web_ui/test_catalog_cache.py
git commit -m "feat(tutorial): source-station catalog Cache-Control + weak ETag/304 (K3)"
```

### Task K4：配置（无新代码，确认复用）

> 本任务**不写代码**——board 模式 tutorial 代理与 live 共用既有配置；目录 TTL env 已在 K3 的 `catalog_cache.py` 内 `os.getenv` 落地。此处仅做确认 + 记录，无独立 commit。

**Files:** 仅阅读 `katrain/web/core/config.py`（确认 `REMOTE_API_URL` / env `KATRAIN_REMOTE_URL` 已存在）。

- [x] 确认 `REMOTE_API_URL`（env `KATRAIN_REMOTE_URL`）已存在并被 board 模式 `RemoteAPIClient` 使用；tutorial 代理**复用**它，**不新增任何配置项**。
- [x] 确认 `KATRAIN_TUTORIAL_CATALOG_MAX_AGE`（默认 300）已由 K3 `catalog_cache.py` 读取（按车队规模调 TTL 的旋钮，无需改 `config.py`）。
- [ ] **（可选 / 阶段 2 前不做）** 车队极大时：board katrain 侧对目录响应做短期内存缓存进一步降远端压力。**当前 out-of-scope**——初版依赖源站 `Cache-Control`（K3）+ 阶段 2 CDN 边缘缓存；如需实施另开任务，勿塞入本计划。

Run: `grep -n "REMOTE_API_URL\|KATRAIN_REMOTE_URL" katrain/web/core/config.py`
Expected: 命中既有定义（无需改动）。

### Task K5：前端 kiosk API（契约，由前端 track `sbc-tutorial-parity` 执行）

> **不在本计划执行** —— 仅锁定后端必须满足的前端契约，供前端 track 实施。后端 K1–K3 落地后此契约即可用。

**契约（前端实现时遵循）：**
- 范式对齐 `katrain/web/ui/src/api/live.ts:17`：`const API_BASE = __KIOSK_2D_ONLY__ ? '/api/v1/board/live' : '/api/v1/live'`。
- kiosk 教程 API 走**共享territory** `src/api/tutorialApi.ts`（非 `src/galaxy/api/tutorialApi.ts`，后者为 galaxy 专用，保持 `BASE='/api/v1/tutorials'` 不变）：`BASE = __KIOSK_2D_ONLY__ ? '/api/v1/board/tutorials' : '/api/v1/tutorials'`。
- `assetUrl(rel)` 同样按 `BASE` 拼接 → kiosk 命中 K2 的 `/board/tutorials/assets/*` 302。
- 路径与 K2 路由逐一对应：`/categories`、`/categories/{cat}/books`、`/books/{id}`、`/books/{id}/chapters`、`/chapters/{id}/sections`、`/sections/{id}`、`/figures/{id}`。

- [ ] （前端 track）`src/api/tutorialApi.ts` 按上契约接 board 前缀；galaxy 专用文件不动。
- [ ] （前端 track）双构建 `npm run build` + `npm run build:kiosk-2d` + `npm run verify:kiosk-2d` 全绿（遵守 `CLAUDE.md` SBC 构建边界契约）。

### Task K6：集成验证 + 部署

**Files:** 无代码改动（部署 + 端到端验证）。

- [x] **Step 1: 全套测试绿**

Run: `CI=true uv run pytest tests/web_ui -q`
Expected: PASS（含 K1/K2/K3 新增 + 既有 board live/auth 回归不破）。
**实测（2026-06-30）**：K1/K2/K3 新增 15 测试全绿；board live 回归 7 绿；tutorial assets 端点回归绿（合计 31 passed）。
全套 `tests/web_ui` 另有 **15 failed + 22 errors 属预存问题**（`test_ai_*`/`test_interface`/`test_billing`/`test_social`/`test_settings_snapshot` 等无关子系统；22 errors = `httpx TestClient(app=...)` 版本不兼容）——已用「将本任务 3 个源文件回退到 caf2dfd5 再跑同一批」证明：回退后这 15 failed 依旧，**与 Stage 3 无关**，留待单独修复。

- [ ] **Step 2: 部署源站**（home-ubuntu，server mode；加载 K3 中间件）

Run: `docker compose up -d --build katrain-web`（或 `server-deploy` skill）

- [ ] **Step 3: 验证源站目录缓存**

```bash
curl -sI https://go.sailorvoyage.top/api/v1/tutorials/categories   # 期望含 Cache-Control + ETag
ETAG=$(curl -sI https://go.sailorvoyage.top/api/v1/tutorials/categories | awk -F': ' 'tolower($1)=="etag"{print $2}' | tr -d '\r')
curl -s -o /dev/null -w '%{http_code}\n' -H "If-None-Match: $ETAG" https://go.sailorvoyage.top/api/v1/tutorials/categories  # 期望 304
```
Expected: 第一条见 `Cache-Control: public, max-age=300, stale-while-revalidate=86400` + `ETag: W/"…"`；第三条 `304`。

- [ ] **Step 4: 验证 board 代理**（起 board-mode 实例：`KATRAIN_MODE=board`、`KATRAIN_REMOTE_URL=https://go.sailorvoyage.top`、服务 `static-kiosk-2d`）

```bash
curl -s http://localhost:<port>/api/v1/board/tutorials/categories          # 期望远端真实书目，book_count 非 0
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:<port>/api/v1/board/tutorials/assets/<book>/video/section_<id>.mp4  # 期望 302
```
Expected: 目录返回远端真实数据；assets 返回 `302`（Location → `https://go.sailorvoyage.top/api/v1/tutorials/assets/…`）。

- [ ] **Step 5: kiosk 浏览器实机眼检**：进「教程」→ 远端书目可见 → 进某小节 → 视频经远端公开 URL（`media`/CDN）流式播放；暂无视频的小节优雅降级（不报错）。

### 决策记录（追加 D9–D11）
| # | 决策 | 状态 |
|---|---|---|
| D9 | kiosk 取远端教程 = **board-proxy**（`/api/v1/board/tutorials/*`，复用 live 范式），**不开 CORS**。浏览器→本机 board katrain 同源；写端点不跨域暴露；迁云只改 `KATRAIN_REMOTE_URL`。取代早期「CORS 直连」设想。 | ✅ 已定（用户，2026-06-29） |
| D10 | 远端目录端点可缓存（`Cache-Control` 短 TTL + `ETag`/304）；媒体已长 TTL。车队规模下源站不被击穿，阶段 2 CDN 命中率高。 | ✅ 已定（用户，2026-06-29） |
| D11 | 媒体：kiosk 经 board assets 代理 **302** 跳远端公开媒体（→ `media.<domain>`），字节不经 board katrain；按需流式、终端不落盘（合 D3）。 | ✅ 已定（用户，2026-06-29） |

### 与阶段 2（OSS+CDN）衔接
- 媒体与目录同上 CDN：媒体长 TTL（已 immutable-ready），目录短 TTL + ETag。CDN 源站 = OSS（媒体）+ 教程 API（目录，或 API 网关缓存）。
- 迁云 = DNS / `KATRAIN_REMOTE_URL` 改向；board 终端与 kiosk 构建零改动。

### 不做（追加）
- 不开后端 CORS（被 board-proxy 取代）。
- 不在 SBC 落盘缓存视频（按需流式；合 D3 始终在线）。
