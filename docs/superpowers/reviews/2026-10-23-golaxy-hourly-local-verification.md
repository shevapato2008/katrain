# 星阵小时同步：本地修复验证

范围：本地隔离 worktree；未推送、合并、部署、执行生产队列迁移、真实导入/发布或付费模型。基线 `0ac3190d8`；最终验证和独立审核代码 `22fff109ea98f495c36cd527c0a28e941b5cb0c9`。后续提交仅收录计划进度、审核报告与恢复说明，不改变业务代码。

## 实际验证

```sh
/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest \
  tests/test_kifu_incremental_source.py \
  tests/test_kifu_incremental_staging.py \
  tests/test_kifu_incremental_state.py \
  tests/test_kifu_incremental_cli.py \
  tests/test_kifu_incremental_preparation.py \
  tests/test_kifu_recent.py \
  tests/test_kifu_maintenance.py \
  tests/test_kifu_api_verification.py \
  tests/cron/test_kifu_ingest.py \
  tests/cron/test_kifu_hourly_orchestration.py \
  tests/web_ui/test_kifu_incremental_catalog.py -q
```

最终亲自复跑结果：**295 passed in 14.76s**，exit 0。此前版本为 294 passed，补齐缺失 Stage 原始基线的冻结包守卫后增加一项。`git diff --check` exit 0；Black 对全部 16 个变化 Python 文件检查通过。新调度测试使用真实临时 Stage、StaticPool SQLite 状态日志和禁止真实 HTTP 的 mock；发布契约回归使用临时 SQLite。没有用生产数据写入来证明修复。

## 验收映射

| 场景 | 主要实际回归 |
| --- | --- |
| 七条 2021 坏项不挡最新页；小时不走 rolling | `test_legacy_seven_failures_never_block_head_and_later_page_new` |
| 北京时间窗口、午夜、延迟上传、超窗排除与 ID 去重 | `test_window_boundaries_timezone_midnight_delayed_upload_unknown_and_dedup` |
| 7004/无效 SGF 终止；临时错误冷却限次；429 整源退避 | `test_terminal_7004_and_invalid_sgf_not_retried_next_round`、`test_cooldown_three_round_limit_does_not_block_other_games`、`test_429_defers_entire_source_without_bad_item_attempt` |
| 页、HTTP、SGF、时长有界；跨轮公平续检 | `test_real_source_http_ceiling_is_shared_by_head_and_sgf`、`test_persistent_absent_last_checked_rotates_across_rounds` |
| 同 ID 变化下载前留证；已发布状态/原件不覆盖 | `test_same_id_change_retains_original_success_and_both_evidence`、`test_metadata_change_is_saved_before_sgf_failure_or_budget_deferral` |
| 429/预算中断不把未知发布状态当未发布；待办复核后继续 | `test_partial_head_never_treats_unresolved_published_item_as_unpublished`、`test_existing_unpublished_raw_waits_for_current_successful_recheck` |
| 列表暂时超时有限恢复、同轮列表复用仍逐卡核验 | `test_transient_list_timeout_retries_once_and_uses_finite_default`、`test_list_cache_reuses_exact_page_but_checks_each_albums_card` |
| 全部五语、SGF、姓名、来源与审核译名；不完整/绑定变更/过期证据不能跳验 | `test_last_language_still_requires_sgf_original_names_source_and_reviewed_displays`、`test_half_album_has_no_checkpoint_credit`、`test_checkpoint_binding_changes_cannot_skip_verification` |
| 完整逐盘检查点跨轮续验且不刷新旧时间 | `test_complete_albums_resume_across_two_bounded_calls`、`test_completed_at_is_not_refreshed_when_another_album_completes` |
| 新谱先于旧包验证；重复轮次不重译/重导；姓名冲突单条隔离 | `test_recent_pipeline_precedes_failed_old_verification_and_does_not_repeat` |
| 近期 TEST 冻结包继续 PROD；变化/未复核版本不发布 | `test_recent_frozen_test_receipt_continues_to_prod_without_prepare`、`test_unverified_source_version_never_publishes_frozen_test_package` |
| 已发布 receipt 只续验，失败不能成为 prod_synced；尾段共享预算 | `test_prod_published_receipt_resumes_only_verification_and_failure_does_not_advance`、`test_historical_test_receipt_verifies_only_and_shared_tail_deadline` |
| 发布超预算等写者结束；不启动第二个并发写者 | `test_publication_overrun_finishes_writer_and_stops_next_package` |
| 精确七项迁移默认预览、审计与摘要保护回滚 | `test_finite_migration_default_dry_run_apply_preserves_and_digest_rollback`、`test_rollback_refuses_concurrent_manifest_or_backup_change` |

## 审核与剩余验证边界

计划由独立 Astra Max 第 1 轮通过；采集、API 验证和调度各自的规范与质量审核均通过，具体发现和修复 SHA 保留在各自报告。另一位独立 Astra Max 对整体最终代码裁定 **Approved／无必须修复项**，独立复跑同一套件 **295 passed in 15.13s**。

最终 Astra 另用真实状态机和验证函数、临时 SQLite、MockTransport、逻辑时钟，模拟 2／32／44 共 78 盘原生 PROD 回执恢复：每轮共享 300 逻辑秒、每请求 8 逻辑秒，12 轮完成，11 次中断保留 `retry_wait/resume_phase=prod_published`，最终检查数 10／160／220，424 次 mock HTTP、3 个检查点、**0 次发布调用**。这不是线上性能测量；完整说明见 [最终 Astra 报告](2026-10-23-golaxy-hourly-final-astra-review.md)。

没有运行 GPU、设备/UI 回归或全库审计；本改动不涉及这些路径。没有在真实 TEST/PROD 执行完整发布旅程，线上恢复须在后续授权部署后核对实际一轮。旧 API 的底层名称证据耗时仍存在；本修复减少重复读取并允许有限续验，未声称消除全部服务端慢路径。3300 秒全轮仍为协作预算，首次 SGF cache warm-up/同步发布可以超时；同轮复用既有 cache，且不会以取消 await 冒充取消写线程。
