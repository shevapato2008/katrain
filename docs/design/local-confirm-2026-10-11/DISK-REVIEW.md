# RK3562 冗余文件只读检查

2026-10-12。用户要求检查可删除的冗余文件；本轮**没有删除历史文件**。当前 rootfs 约 13GiB、95% 已用，剩余约 660–680MiB；独立 `/mnt/data` 约 24GiB 空闲。本次发布候选和回滚副本已放数据盘。

## 可优先清理的约 166MiB

独立 Astra max 检查当前进程 cwd/exe/fd/maps、有效 systemd/cron/init 配置和活跃树 symlink，没有发现下列旧发布候选被引用。

| 具体范围 | 预计实际回收 | 依据 |
| --- | ---: | --- |
| 以下三个 payload 中各自的 `static.tar.gz` 和 `static-kiosk-2d.tar.gz`，共 6 个文件 | 约 114MiB | 与保留的 `katrain-release-3802866d/payload/` 两文件 SHA256 完全相同 |
| `/root/katrain-deploy-0e2d02fc/stage/` | 46.1MiB | 无活跃引用、可再生成的旧候选；同目录 `backup/` 保留 |
| `/root/.cache/pip/` | 6.0MiB | 可再下载的 pip 缓存 |

重复 payload 的三个目录为：

- `/root/katrain-release/kifu-7b61b1ec-20261011/payload/`
- `/root/katrain-release-62f69125/payload/`
- `/root/katrain-release-7ecc9b55/payload/`

单个 full 压缩包为 28,520,224 bytes，SHA256 `d8d34cde75650384d286f4bbd44e863826df6e46008ed5c488f6089ff42fb100`；单个 strict 压缩包为 11,304,786 bytes，SHA256 `8b345977bfee70f64342faac58024c08dfaff395a9c396a434a0de076e4d782a`。三对合计 119,475,030 bytes。各版本 source 包、验收记录及数据库副本不能随整个 release 目录一起删。

## 保留和迁移候选

保留本次 `/mnt/data/.../backup/`、旧 `katrain-deploy-0e2d02fc/backup/`、数据库、模型、身份和硬件状态。`/root/deploy-backups/`、`/root/smartbox-software/.deploy-backups/`、`/root/smartbox-deploy-backups/` 可考虑校验后转存数据盘再移除根盘副本；本轮没有迁移历史备份。

不能直接相加 `du` 的目录大小：显示约 1.4GiB 的 `katrain.before-retry-20261009-020257/` 与其它树共享大量硬链接，单删它仅实际释放约 2.7MiB。`/root/deploy-backups/` 单独删除实际约释放 625MiB，远小于单独 `du` 显示的约 1.94GiB。journal 约 222MiB 属于日志留存，应先确定保留策略，不列为无条件删除。
