# 棋谱名称本地化：测试环境兼容发布记录

2026-10-02 05:18–05:20 CST。目标仅为 `home-ubuntu` 的现役 `katrain-web` 和 `katrain_db`；本次没有部署正式环境，也没有导入候选译名或关联棋手、赛事。

## 版本与隔离准备

- 发布代码：`ff573f0b628c0af670c3fd1ecaac94f07029f514`，已合并当时的 `develop`；专用镜像 `katrain-web:kifu-name-ff573f0b`，镜像 ID `sha256:70d471aedd818043dab369df74aca0de532832e5d4778772a9864e3edc0460f0`。前端和管理端静态构建成功。
- 旧 Web 镜像 ID `sha256:0b337c7f5f0952f4d0e59cd075fd66c51fe81a440d6449205419c4b1c198329b`，保留为 `katrain-web:kifu-name-prev-20261002`。隔离构建源目录 `/home/fan/kifu-name-test-deploy-20261002/source`，未切换测试机原有 `feature/admin-console` 工作树，也未覆盖其 `katrain-web:local` 标签。
- 现役测试库完整备份 `/home/fan/kifu-name-test-deploy-20261002/katrain_db_pre_kifu_names.dump`（仅该机可读，mode `0600`），SHA-256 `00300f807e97f63340cc8f6d3435722ef2f37f42900fe25c572d87058d19a3e7`。恢复到独立库 `kifu_name_live_test_rehearsal_20261002` 后核对 `kifu_albums=173025`。
- 在恢复副本上用新镜像执行 `python3 -m katrain.web.kifu.migrate_catalog --validate`，返回 `Kifu catalog schema ready; foreign keys validated`。新 Web 和旧 Web 分别连接该副本启动，均返回健康状态。确认旧镜像可读取迁移后的数据库后，停止两个副本 Web 容器。
- 随后对现役测试库执行相同的显式迁移和外键校验，再用三个 compose 文件仅重建 `katrain-web`：原 `docker-compose.yml`、测试机原 `docker-compose.override.yml`、专用 `kifu-web-only.override.yml`。命令使用 `up -d --no-deps --no-build katrain-web`；cron、admin、KataGo、Postgres、MinIO 均未重启。新容器实测 `KATRAIN_BUILD_SHA=ff573f0b`、`KIFU_STRICT_NAMES=0`、`KATRAIN_DATABASE_URL` 指向 `host.docker.internal/katrain_db`，媒体后端仍为 `s3`；其余 compose 环境值与旧容器逐键核对无差异。

## 聚焦验收与限制

| 检查 | 实测 |
|---|---|
| `/api/v1/health` | 200，服务与本地引擎可用 |
| `GET /api/v1/kifu/albums/24171?lang=cn` | 200，SGF 内容 1417 字符，显示黑白棋手 |
| 棋谱列表 | 200，可见 173016 盘；库中原有 173025 行，其中 9 行已有 `duplicate_of_id`，新列表按设计隐藏这 9 行 |
| `吴清源` / `Go Seigen` | 中文与英文查询均返回 1059 盘，同一首条 ID `140859` |
| `Го Сэйгэн` | 俄语查询返回 **0**；严格模式关闭且全量译名尚未入库，此项是明确缺口，不算多语言验收通过 |
| `/galaxy/kifu` 与无会话 `/api/v1/auth/me` | 分别为 200 和预期的 401；未使用真实账号执行登录 |
| 现有教程视频路径 | API 返回 302，跳转主机仍为 `go.sailorvoyage.top`；未验证目标媒体字节下载 |
| 启动日志与数据库 | 近五分钟无 `traceback/error/exception/failed`；现役测试库仍为 173025 棋谱、9 个重复标记、黑/白/赛事已连接槽位 1166/1816/575、旧姓名行 5437/108、新证据行 0 |

这只是代码与旧数据的兼容发布，不是十一语言全量交付。正式库截至本次审计仍有 5,678,904 个槽位缺少合格显示决定；正式环境 Web、严格开关和候选姓名数据均未变更。

## 回滚点

测试机已保留 `kifu-web-rollback.override.yml`，只把 Web 镜像改回 `katrain-web:kifu-name-prev-20261002`，并继续令 `KIFU_STRICT_NAMES=0`。如需回滚，在 `/home/fan/Repositories/katrain` 使用原 compose 文件、原测试机 override 和此回滚 override，以 `up -d --no-deps --no-build katrain-web` 只替换 Web。副本已证明旧 Web 可读新增的兼容 schema；不要直接用备份覆盖有并发新写入的共享测试库。
