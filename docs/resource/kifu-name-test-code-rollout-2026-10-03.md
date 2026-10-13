# 棋谱名称：测试环境兼容代码发布

2026-10-03。仅更新 `home-ubuntu` 的现役 TEST 棋谱 schema 和 `katrain-web`；未导入名称候选，未改正式库。源码从已追上 `develop` 的功能分支提交 `ce8f81ce` 隔离检出，专用镜像 `katrain-web:kifu-name-ce8f81ce` 的 ID 为 `sha256:d43960ac5259c57dc36a21a3b596c5368a2f53777795107def089e11056d3949`。本地同一代码的 280 项棋谱名称聚焦后端测试与前端构建通过；镜像内前端和管理端构建完成。

迁移前从现役 `katrain_db` 以 `pg_dump --serializable-deferrable -Fc` 备份 `public.kifu_*`，文件位于测试机 `/home/fan/kifu-name-test-deploy-20261003/kifu-before-migration.dump`，权限 `0600`，98,381,388 字节，SHA-256 `4026e00c6b3658b3dbdc3bb114039bc04fea5c3c8d7622a25860a`。容器内 `pg_restore --list` 可读，目录含 `kifu_albums`。此前同一批 173,025 盘的 TEST 只读快照已在隔离克隆完成迁移及 19 张表前后哈希核对；本次没有重复恢复新备份。

新镜像通过原有两个 compose 文件及仅覆盖 Web 镜像的 `kifu-web-only-ce8f81ce.override.yml` 执行 `migrate_catalog --validate`，返回 `Kifu catalog schema ready; foreign keys validated`。新增的 `kifu_album_event_selections` 和 `kifu_event_selection_batches` 均为零行。迁移后旧 Web 仍返回健康接口 200，棋谱总数保持 173,025。

随后只执行 `up -d --no-deps --no-build katrain-web`。新 Web 的 `KATRAIN_BUILD_SHA=ce8f81ce`、`KIFU_STRICT_NAMES=0`；cron、KataGo、PostgreSQL 和 MinIO 未重启。健康、棋谱列表、ID 24171 详情及 `吴清源` / `Go Seigen` 搜索均返回 200；中、俄、乌语言列表各为 173,016 条可见记录（9 条原有重复记录不列出），近五分钟 Web 日志匹配 `Traceback|Exception|ERROR` 为 0。

旧镜像 `katrain-web:kifu-name-2e4fcef5` 与其专用 override 保留，可仅切回 Web。兼容 schema 可由旧 Web 读取；不应把旧数据库备份直接覆盖有并发写入的共享测试库。五位棋手 55 个名称的隔离克隆演练已通过，但**现役 TEST 名称仍未导入**：它们须绑定现役库迁移后的新 inventory、catalog 和名称前像并独立审核。严格名称模式继续关闭，因此普通列表不会提前显示部分 raw-player 名称。
