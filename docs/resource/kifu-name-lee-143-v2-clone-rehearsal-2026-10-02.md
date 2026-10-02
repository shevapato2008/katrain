# 李昌镐 ID 143 五槽位：隔离库导入与撤销演练

2026-10-02 05:23–05:30 UTC，在 `home-ubuntu` 的独立备份恢复库 `kifu_name_rehearsal_20261002` 演练[已签署的五槽位工件](kifu-name-lee-143-five-link-v2-independent-review-2026-10-02.md)。现役测试库和正式库均未写入。审核范围仍只有棋局 `40212/黑`、`64489/黑`、`83228/黑`、`97368/白`、`98003/黑`；其余 2,135 个同名槽位保留待审。

隔离执行目录为 `/home/fan/kifu-name-rehearsal-20261002/lee-143-v2-run/`，目录及文件分别限制为 `0700`、`0600`。`bundle-reviewed.json` 文件 SHA-256 为 `6d7b9f5fdbe16cea483f071cf58f61b4a53067cd1af548411f7cb0749e4de99a`，导入器计算的规范 bundle 哈希为 `cb0bb519a39583120b8872322ead962cd52faeed8975527c0d6a864ffb583c39`。克隆清单仅把 `database_identifier` 改为隔离库地址，内部数据快照哈希仍为 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`；克隆清单文件 SHA-256 为 `7c0b6d8153fa1d3bf3d0b585a38c643378fbde8c14ca11b8cf71723b66c58e8c`。

首次 dry-run 暴露导入器比较缺陷：前像中的 `created_at` 是审核工件的 ISO 文本，SQLAlchemy 读取为时间对象，直接比较导致 `owner catalog preimage differs: player:143`。提交 `ce8cba3e` 改用现有 `_image` 规范化读取值，先写的聚焦测试红灯，再修复为绿灯；`tests/web_ui/test_kifu_name_batch.py` 共 **36 passed**。隔离容器实际挂载的 `name_batch.py` SHA-256 为 `19e6ae6dc34f2cd5e4dae00c5697315f791abd9e75e0f5480f2ca511c499042a`，`name_candidates.py` 为 `5f25ac03ceacad4ab6f821d510abbd922727816644a063196a99b7d4bf849a31`。此修复正在独立代码复核。

使用同一已签署工件重跑 dry-run：`ready=true`、`write_ready=true`、11 个姓名、五个指定棋局、`estimated_undo_rows=27`，零错误。隔离库 `apply` 返回 `batch_id=3`、`change_count=27`；只读 SQL 核对五个指定棋局槽位均指向棋手 143，`kifu_player_names` 中该棋手的十一语 `cn,de,en,es,fr,jp,ko,ru,tr,tw,ua` 齐全。随后对批次 3 执行条件 `undo`，返回 `reverted=27`、`skipped=0`。撤销后五个槽位均不再指向 143，名称行恢复为原有五条 `cn,en,jp,ko,tw`，批次状态为 `undone`。

本演练证明有限工件可在此备份副本上写入并完整撤销，不授权将五个关联写入正式库，更不代表全库十一语言已完成。正式入库仍受全库覆盖率、其余同名槽位消歧及最终发布门槛约束。隔离目录中的数据库连接信息仅供本次测试，应在证据核对后删除；不进入 Git。
