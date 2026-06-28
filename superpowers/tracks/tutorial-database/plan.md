# 教程媒体存储方案设计文档 (Tutorial Media Storage)

> **For agentic workers:** REQUIRED SUB-SKILL — 用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 逐任务实施。步骤使用 `- [ ]` 复选框追踪。本文件先作为**设计文档 / 调研结论**；实施前请确认 §决策记录 中的待定项。

**状态:** 阶段 1 完成并上线生产 home-ubuntu (2026-06-28) · 存储抽象 + S3/MinIO 合并入 `develop`；MinIO 上线 + 全量迁移 27452 对象；**应用已切 `s3` 后端**——`/assets` 经 302 跳到 `https://go.sailorvoyage.top/media/`（nginx → MinIO over WireGuard `10.8.0.2:9000`，匿名只读 + Referer 防盗链）。HTTP 链路全验证（302 + 206 Range + 字节一致 854796 + 外站 Referer 403）。浏览器实机播放待人工眼检（本服务器无头 chromium 沙箱受限）。**阶段 2（阿里云 OSS+CDN）待办。**

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
