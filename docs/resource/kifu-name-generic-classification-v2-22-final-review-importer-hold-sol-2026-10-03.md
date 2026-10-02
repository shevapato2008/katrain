# classification-v2 22 格：最终签署通过，importer dry-run HOLD

审核者 `/root/generic_v2_22_source_review_sol`；运行时标识 GPT-6，任务名 sol 不认证具体子型号。对 [最终 pending 绑定包](kifu-name-generic-classification-v2-22-final-pending-binder-sol-2026-10-03.md) 独立复算全部 46 个文件 hash，确认 source/binder/capture 链、22 条前像及时序、两个 create refs、901/638 完整 contexts 和既有类别/模板签署。审核时 binder 记录的三个实现文件 hash 与当前文件相同。

**22/22 最终候选已独立签署；离线 validator `ready=true/write_ready=true`，但 importer dry-run 在写入前拒绝，整批交付仍 HOLD。** 已签包规范 SHA-256：`2693cf83586d7ddc76d0c6f20f3f56506e49fb60e792be3f3767024be96c2f5d`。这不是已导入或线上覆盖证明。

独立仅连接 `127.0.0.1:55433/kifu_raw31_clone_20261003`，使用 `REPEATABLE READ READ ONLY` 再查现状，inventory/catalog 与 binder 一致，两个精确 raw_event owner 仍不存在，22 条新 owner 名称前像均 NULL。两组共 1,539 盘、全部十一语签署，仍零 event owner/alias/album link 提案。实际执行显示/搜索/批准覆盖的入库前检查，范围内全部事件审批为零；尚未取得入库后的显示增益。

精确阻塞来自 `name_batch.py:353` 的 `_check_owner_manifest`：新 raw 的 `create` 必须恰含 `raw_value`、`category`。本包两个 owner 的 `create` 额外携带 `parser_version: classification-v2`，因此真实 dry-run 抛出 **`BatchError: new raw create fields not allowlisted`**。离线候选 validator 未拒绝这个字段，不能将其 `write_ready=true` 代替 importer 门槛。

本轮未执行 apply/replay/undo，数据库写入 0，实际审批展示增益 0；没有生产或现役测试库操作。clone 在 finally 中停止，停止收据确认 `Running=false`。原 binder 需移除两个不受支持的 `create.parser_version`，重算 owner/bundle hashes；随后重新独立签署修正工件并完成隔离演练。候选的 `generation_rule_version=classification-v2` 和精确文字继续保留，不扩张 importer allowlist。

冻结目录：`~/.local/share/kifu-name-audit/2026-10-03/generic-classification-v2-22-final-review-rehearsal-sol/`，目录0700、文件0400，包含已签 bundle、离线校验、独立 clone preflight、入库前十一语运行时检查、原始失败 traceback、HOLD 结果及停止收据。manifest 字节 SHA-256：`961d424176b6039fa0b94e06f8ec2dc02536bbd6e5005bec0dec360d19462ec4`。后续修正包在固定 classification-v2 已提交版本的独立 worktree 演练，以免并行 Hoensha 开发改变运行代码。正式入库仍须实际目标的 fresh inventory/catalog/name 前像；克隆结果不认证未来线上状态。
