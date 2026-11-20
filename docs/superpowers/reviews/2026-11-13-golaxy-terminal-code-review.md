# Golaxy labels, self rank and terminal vision: final code review

Product commits: bd39bad41, 263bb0825, 317db9beb; corrective commits: 5f7ab2a70, 72f44cf66.

Independent reviewer: gpt-6-astra, max effort. User requires notification before RK3562 deployment; no device or cloud deployment in this release handoff.

## 2026-11-13 修复复核（当前结论）

**Approved。上述 R1、R2、R3 已解决；终局规格 M1（规格报告中的 R1）也已通过。** 本节取代上方历史阻塞结论，保留原发现与复现记录。

复核范围仅为修复提交 `5f7ab2a701e66978f891bd72c9b0b7ead8006724`、`72f44cf6670bc75b490074053f47bd313890d272`，当前 HEAD 为后者。核对原复现路径及修法直接影响的边界，未重做其余产品变更的全量审核。

| 项目 | 修复复核结果 |
| --- | --- |
| R1：新登录开始期间旧身份回写 | `clear_username()` 立即推进身份代次，`get_account_identity()` 在发布缓存前校验代次和 token；`connect()` 进入时置未连接，三种成功登录统一经 `set_tokens()` 发布凭据。原先“先放行旧身份、后返回新 token”的密码、短信、扫码三条离线路径全部通过：旧查询降级为未知，新账号新局取得新人的 4 段；资料已在途时新登录开始的边界也通过。3 秒总预算未改变。 |
| R2：终局误阻独立 monitor/setup | 两种 worker 以 `_game_active = bound and not game_over` 选择对局处理来源；monitor/setup 可继续更新，独立事件标记为 `sessionless`。orchestrator 仅将 `game_over` 从 generic pause 聚合中剔除，其 tick 仍暂停，其他 pause 原因仍有效。已运行两个真实 processing loop：终局 binding 保持结束，setup 产生 `setup_complete`，随后 monitor 产生 `move_confirmed`；没有通过恢复终局对局或关闭共享相机实现。 |
| R3：旧 pending/ambiguous 跨绑定 | 两种 worker 的 dict 生产统一经 `_emit_event()` 附绑定 epoch；service 拒绝旧 epoch 与未标记的绑定对局候选，再附当前 session/game。前端按当前 session/game 拒收旧事件，绑定页面不接收 sessionless monitor 事件。离线验证原未标记 pending／旧 epoch ambiguous 均被丢弃，生产 pending 保留绑定身份；同 session 换 game 后迟到 WS 事件不再回填，`useVisionSync(null)` 仍接收独立 monitor 事件。 |
| M1：恢复清理终局条件不一致 | `_apply_game_state()` 和 `_release_recovery_on_game_end()` 复用 `_game_is_over()`。只有 `terminal_result` 的历史节点会清除 engine error、移除上下文和灯；`awaiting_count=True` 时保留恢复上下文。原来通向窄移除 tick 的过期上下文已被清掉。 |

本轮独立执行的定向验证：

```text
pytest：test_new_login_rejects_old_identity_before_new_token_arrives（三参数）
        test_engine_self_rank_discards_profile_if_new_login_starts_before_token_changes
        → 4 passed in 0.06s

pytest：test_terminal_game_does_not_block_real_monitor_setup_completion
        test_unstamped_or_old_binding_game_events_do_not_cross_a_new_bind
        test_production_pending_event_keeps_its_binding_identity_through_service
        test_terminal_history_releases_recovery_but_counting_keeps_it
        → 4 passed in 0.98s

Vitest：useVisionSync.test.tsx，仅迟到旧 game 与 sessionless 路由用例
        → 3 passed，2 条非本次选择的用例 skipped
```

未发现上述修复引入的新阻塞。其余已独立审过的名称、公开名、等级管线、相机 idle/fresh wake 和 Chip timer 结论沿用；未重复全套测试、构建或视觉预览。本轮只追加审核文档，未修改产品代码、未 SSH、未操作设备、未 push 或部署。本结论为代码审核与 M1 规格通过，不等同设备验收；发布仍须遵守代码整合/push 后先通知用户、RK 与云均不部署的当前门禁。


## Platform nickname addendum

# 星阵昵称追加独立代码审核

审核日期：2026-11-13。审核对象：`f548cbca5..db5dec650` 的 11 个文件，仅对应已批准计划 Chunk 6。先核对修订规格与两轮计划审核，再检查实现、调用链和定向回归；不重复旧终局、反光或黑屏审核。

**结论：Approved。未发现需阻塞此次昵称追加的正确性或规格问题。**

- 本人来源正确：`GolaxyAdapter.get_player_profile()` 本人分支只取原始 `nickname`，其他用户仍保留 `followAlias or nickname`。REST 层校验响应 `userCode`；engine 层再确认 `is_self is True` 与 caller 一致，没有采用登录 principal、手机号或盒内公开名。
- 身份与预算正确：`_get_engine_self_profile()` 保留整次 3 秒上限及读取前后的 connected、identity revision、token 检查。昵称随本次返回值传递，没有跨请求昵称缓存；凭据切换或资料失败时同时丢弃结果。未知等级仍能保留已验证昵称。正常开局及 AI 首手保持既有降级路径。
- 传递正确：默认 `None` 的 `PlatformGameSession.my_username` 不改变其他构造路径；manager 根据真人执色设置既有玩家名字，真实 Session/GameState 验证了两种执色。前端移除了盒内公开名覆盖，直接使用席位名字；旧 `Me`／空名回落“星阵用户”。机器人名称、等级及非 engine 名字规则未改变。
- 范围适当：没有新增网络请求、公共接口、GameState 字段或轮询；未发现此次改动需要扩展资料架构或增加额外状态。

**本次独立验证**（均在本地、网络 mock 下运行）：

```text
python -m pytest -q tests/platforms/test_golaxy_engine_adapter.py \
  -k 'self or nickname or follow_alias or new_login or credential or identity_read'
32 passed, 37 deselected

python -m pytest -q tests/platforms/test_engine_manager.py -k 'nickname'
4 passed, 17 deselected

python -m pytest -q tests/web_ui/test_golaxy_lobby.py \
  -k 'player_profile or self_profile or profile_read'
5 passed, 91 deselected

npm run test -- src/kiosk/utils/playerName.test.ts \
  src/kiosk/__tests__/GamePageEngine.test.tsx \
  -t '星阵.*名称|星阵.*显示名|星阵引擎局席位名称'
20 passed, 67 skipped

git diff --check f548cbca5..db5dec650
通过
```

另外直接调用真实 adapter，验证 `nickname` 为 `None`、空串、纯空白、数字且存在有效 `followAlias` 的 4 种情况：均未采用备注，正常创建对局，每次仅读取一次资料。

以上数量仅为本审核者实际运行结果，未把实施者报告的整组通过数作为本次独立执行证据。按任务边界未重复全套测试、构建或浏览器预览；计划要求的最终构建与一次 1024×600 真实卡片预览由主代理统一完成。本审核未修改产品、操作设备、SSH、推送或部署；自动生成的 `engine_game_state.json` 不作为产品改动审查。
