# 吴清源西语和乌克兰语候选：隔离库演练

2026-10-02 在 `home-ubuntu` 的独立数据库 `kifu_name_rehearsal_20261002` 演练；该库从正式库的受控备份还原，测试环境现役数据库和正式数据库均未写入这两条候选。正式库备份、恢复和迁移记录见 [迁移记录](kifu-name-migration-record-2026-10-02.md)。正式服务的 `KIFU_STRICT_NAMES` 仍关闭。

- 受控候选 `wu-v4-prod-bound-v3-candidates.jsonl` 经独立审核，文件 SHA-256：`5aab0e1dc3c0e0e8428d08ae8674461ec271a9eb803ef6f41acde83e73c094ae`。来源、审核和真实 `null` 前像核查见 [审核备忘录](kifu-name-wu-es-ua-v4-review.md)。
- 有限批次 `wu-v4-prod-bound-v3-bundle.json` SHA-256：`78608644d0044d02dabde91ba13e38441a09a5bf6dc949d1452986ccf947bf1a`。本地离线校验为 `approved=2, ready=true, write_ready=true, errors=[], write_errors=[]`。
- `inventory_format=2` 正式数据快照的内容 SHA-256：`66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`。演练用清单仅将连接标识改为隔离库的 `host.docker.internal` URL；数据快照和候选绑定的内容哈希不变。演练清单文件 SHA-256：`a2f2bb7f73672958a6d6b742ea39d0545a666e2b94272e75ae168250c440872b`。
- 使用审过的代码（含提交 `444bddd1` 的前像绑定门禁）在隔离库运行 `dry-run`，结果 `approved=2, ready=true, write_ready=true`，预计撤销 4 行。实际 `apply` 返回 `batch_id=1, status=applied`，收据登记 `change_count=4`、上述批次和清单哈希；查询两条姓名为 `es: Go Seigen`、`ua: Ґо Сейґен`，`decision_kind=conventional, revision=1`。
- 对该批次执行条件 `undo` 返回 `status=undone, reverted=4, skipped=0`。撤销后隔离库这两条姓名行数为 0。

该演练证明此有限批次的写入和回滚机制；不能代替其他九种吴清源译名的复核，也不能代表全库十一语言覆盖完成。全库严格展示和发布仍受覆盖门禁限制。
