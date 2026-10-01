# 棋谱名称兼容迁移记录（2026-10-02）

本记录只覆盖新名称表和旧译名表的兼容性迁移；没有导入候选译名、开启 `KIFU_STRICT_NAMES`、替换 Web 镜像或完成十一语言全库验收。

## 固定输入和备份

- 正式数据库：`ucloud-v100` 的 `katrain-ucloud-postgres-1`，`katrain_prod_20260725`。在现役 Web 容器内读取连接串的非秘密部分，确认也是这个数据库；`KIFU_STRICT_NAMES` 未设置。
- 迁移 Python 代码：已独立代码审核的提交 `4de9e9f30090`；打包的 Python 文件归档 SHA-256 为 `36b9c7250ef976e9c64c81bcb09be143b9bd50bc41bbf2758d2142866758555e`。测试与正式容器内均从归档的独立 `/tmp/kifu-name-reviewed` 目录运行，现役 `/app` 代码未替换。
- 正式迁移前完整 `pg_dump -Fc --no-owner --no-acl`：`/opt/katrain/backups/kifu-name-pre-migration-20261002.dump`，权限 `0600`，SHA-256 `ea8c1ae9e6ddb8038ac8b0ce91a012031c4b10bb3d39b6a4192316d2e0fbd990`，大小 204,876,970 字节。`pg_restore --list` 成功。相同 SHA 的副本传至测试机 `/home/fan/kifu-name-rehearsal-20261002/prod.dump`，权限 `0600`。

## 隔离恢复与迁移演练

- 在 `home-ubuntu` 的 PostgreSQL 容器内新建独立数据库 `kifu_name_rehearsal_20261002`，从上述正式备份恢复；恢复后有 173,025 条 `kifu_albums`。
- 以原 Web 容器的数据库连接配置仅改数据库名，运行固定代码的 `python -m katrain.web.kifu.migrate_catalog --validate` 两次；两次均输出 `Kifu catalog schema ready; foreign keys validated`。连接设置 `lock_timeout=5s`、`statement_timeout=120s`。
- 迁移后的四个新姓名字段均存在：`decision_kind`、`generation_rule_version`、`revision`、`evidence_id`。在旧版 `/app` 代码下直接查询隔离库仍能读出 173,025 盘及吴清源旧译名。

## 正式迁移及不变性核验

隔离库迁移前、迁移后、正式库迁移前、正式库迁移后的四组摘要完全一致。摘要算法为按 `id` 排序后，对每行 `row_to_json` 的 MD5 拼接再取 MD5；姓名表只选取迁移前已有列。

| 表 | 行数 | 旧数据摘要 |
| --- | ---: | --- |
| `kifu_albums` | 173,025 | `2651c12a6aac2bb2e49083f4ffb3e2ac` |
| `kifu_album_sources` | 173,034 | `f85acfa0c173d09862130a3c727fed5d` |
| `kifu_player_names` | 4,377 | `4fca9c78e1bb78dfe9276c054a30900e` |
| `kifu_event_names` | 108 | `4b16757706b576221cd42a3e97744db1` |

正式库使用同一代码和超时设置运行 `migrate_catalog --validate`，成功输出 `Kifu catalog schema ready; foreign keys validated`；四个新列存在。现役 Web 的 `/api/v1/health` 返回 `status: ok`，旧版 `/app` 代码仍可读取 173,025 盘及原有姓名行。未执行批次导入。

## 后续门槛

迁移后只读采集吴清源 ID 1 的十一语言姓名行真实前像，受控文件为 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/wu-name-preimages-prod-20261002.json`，SHA-256 `b1008149c2163938e31822119e38f5e5425b973517073a6aeb4a4f1ba605ea7b`。它只用于生成新的生产绑定候选；原始候选的旧审批不自动覆盖新前像，须独立复核。正式数据导入仍需同哈希隔离演练、全库十一语言 100% 覆盖和零未经审核回退。
