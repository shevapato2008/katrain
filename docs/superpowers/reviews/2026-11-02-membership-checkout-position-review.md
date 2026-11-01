# Task 5 / Task 8 独立分包审核

日期：2026-11-02。审核者为独立只读 reviewer；被审基线 HEAD `0da56f0ef1ec0f7136492c3c5238d93f0f39175c` 加当前未提交实现。此报告不是整个会员功能的最终 Astra 审核。

范围：Task 5 的 checkout / usage / TEST payment 路由与三组测试；Task 8 的 paid position / 旧计算入口 / 私有分析出口 / kiosk 身份桥及两组测试。没有修改产品、运行生产或 GPU、读取默认业务库或输出秘密；真实 PG 仅使用已验证 loopback 专库内随机 schema。

**最终分包结论：Task 5 Spec 通过 → Quality 通过；Task 8 Spec 通过 → Quality 通过。未解决 0 Critical / 0 Important / 0 Minor。** 下文保留首轮发现与复现，修复和独立关闭证据见末节。只对本轮两个包负责，不代替 Task 9 / 全功能终审或发布批准。

## 第一轮 Spec 结论

- Task 5：**需修改**，1 Important（I1）。金额/钱包 grant、同 owner key、15 分钟订单、真实 TEST DB 与管理员/HMAC、一次事务履约/退款、provider transaction 唯一、迟到失败与漏通知恢复、owner/no-store 与 legacy settle 隔离均已检查；会员冻结权益仍未贯穿。
- Task 8：**需修改**，1 Important（I2）。固定 profile/合法 SGF、reserve commit 后锁外 HTTP、模型/深度验证、generation fencing、按来源退款、owner HTTP 收据/重放/24 小时过期、enabled/paused 旧 API 阻断、state/WS/诊断日志隔离及 kiosk 身份桥均已检查；SGF 导出仍可交付内部分析。
- Quality 最终通过须等对应 Spec 修复通过后再给出；以下先记录已确认缺陷和验证结果，不把测试通过等同规格通过。

## I1 · Important · 冻结会员快照尚受当前目录影响

位置：`katrain/web/core/payments.py:167`、`core/membership.py:125` / `:219`、`core/billing_operations.py:61` / `:403`。

支付履约仍进入 `create_term_in_transaction` 的当前 `PLANS[plan_id]["sellable"]` 检查；已经合法创建的待付订单在停售后会抛 `ValueError("plan_not_sellable")`，不能履约。虽然 `sku_snapshot` 已冻结 `week_units`，usage、来源选择和周桶 allowance 仍读取当前 `PLANS`，已付权益随目录变化。

真实 PG、`autoflush=False` 最小复现：创建 Plus pending 并提交，内存把当前 Plus `sellable=False`，同一已绑定 paid event 在 15 分钟内履约，得到 `ValueError plan_not_sellable`。恢复 sellable 并支付成功，再把当前目录 `week_units=1`，订单快照仍为 `3010`，`usage_snapshot()["week"]["limit"]` 实际变成 `1`。所有内存目录变更均在脚本 finally 恢复；schema 随脚本销毁。

最低修复：合法已创单履约与已购 term 周量从关联订单冻结快照读取；停售只挡新建。无需新建价格平台或扩 schema。

## I2 · Important · SGF 保存可旁路私有分析结果闸

位置：`katrain/web/interface.py:2090`（特别是 `save_analysis` / `save_feedback` / `save_marks`）、`katrain/web/server.py:1595`。

`get_state` 已清除内部 AI 分析，但 `get_sgf` 仍尊重可配置的 `trainer.save_analysis`，`GET /api/sgf/save` 直接输出它。内部 node 缓存可作为 KT 压缩属性导出并完整解码，绕过已 committed、本人、完整 scope/profile 的结果授权边界；保存到用户棋谱的其他 `get_sgf` 调用也应使用同一安全输出。

实际挂载、无 GPU 最小复现：`enabled` 的 `create_app(enable_engine=False)`，本人 session，内存 `trainer.save_analysis=True`，根 node 设置 completed 内部结果（visits 500 / scoreLead 3 / winrate 0.9、361 点 ownership）。`runtime.get_state()["analysis"]` 是 `None`；`GET /api/sgf/save?session_id=...` 返回 200 且含 `KT[...]`。使用 `class Parser(SGF): _NODE_CLASS=GameNode` 解析后 `load_analysis()` 恢复相同 root 和 361 点 ownership。仅改内存，没有保存用户配置。

最低修复：在统一 `get_sgf` 输出中按现有 sticky membership guard 关闭分析、派生反馈与分析标记，保留真实手顺、必要棋谱属性和人工文本。

## Minor

1. `katrain/web/api/v1/endpoints/billing.py:359`：quote 未执行中央 `guard_user_has_no_pending_ranked_game`。真实 PG/HTTP 中 pending-ranked 用户的 raw SGF position quote 为 200，同 token 执行为 403。执行闸有效，没有复现 GPU/扣费绕过，但与显式 quote 中央闸规格不一致，应在代理/输入处理前统一拒绝。
2. `tests/web_ui/test_paid_analysis.py:42`：fixture 的 sessionmaker 未显式 `autoflush=False`，与运行时不同。用临时内存 `partial(sessionmaker, autoflush=False)` 复跑既有 12 项均通过；建议 fixture 显式对齐，避免后续变更只在隐式 flush 下通过。

## 本轮验证

- 指定五个文件合并运行：**54 passed**，仅现有 `datetime.utcnow` deprecation warning；包含 Task 5 32 项、Task 8 22 项。
- Task 8 既有 position 12 项以运行时 `autoflush=False` 临时重跑：**12 passed**。
- I1 / I2 / quote gap 均由临时内存脚本及实际 HTTP/随机专库复现，不新增产品测试层。
- 保留 AI 选步和实际终局判定所需内部计算；没有将必要最终对局结果误报为中途 ownership/hint/PV 交付。

## 修复复核与最终结论

实现作者修改产品及既有测试，reviewer 仅重读和运行复核；未替实现作者改代码。

1. **Task 5 Spec 通过。** `_order_entitlement` 读取关联本人订单快照校验冻结事实；会员履约不再因当前停售失效，term 起止/总量/catalog 由快照建立；`term_week_units` 贯穿 usage、quote/source 判断和最终预留周桶。当前目录不再覆盖已购周量；只对无版本、无快照的既有行保留有界兼容。独立复跑以下三项 **3 passed in 1.93s**：停售后履约冻结权益；当前目录周量/总量变化后 usage 及 quote 保持冻结权益；pending ranked 报价在输入解析和 board 派发前拒绝。I1 与 quote Minor 关闭。
2. **随后 Task 5 Quality 通过。** 重读冻结 helper 与 payment 边界，没有新 schema、价格平台或 service commit；金额校验、owner 绑定、既有锁序及单事务支付/退款保持。未发现新增 Critical / Important / Minor。
3. **Task 8 Spec 通过。** `get_sgf` 使用 sticky guard，在脱离运行中棋树的副本上清 analysis / KT / shortcut 后序列化。该做法同时阻断 KT 与“人工 note 导致 GameNode 自动追加分析反馈”的路径，保留手顺、metadata、终局结果、人工 notes，并且不改变内部 AI 树。sessionmaker 已显式 `autoflush=False`，默认 commit expiration 也与运行时一致。独立复跑 positions + guards **25 passed in 8.62s**，包含 enabled / paused / hot-legacy 三种实际 SGF HTTP 导出回归。I2 与 fixture Minor 关闭。
4. **随后 Task 8 Quality 通过。** 对修复树的复制/分支连接、分析清理、共用输出边界，以及原授权/结算/结果路径再次检查，未发现新增 Critical / Important / Minor。没有增加 GPU 调用或修改内部选步分析。

复核针对上述工作区文件内容；HEAD 仍是前述基线，未提交变更不是新 commit。关键复核内容 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `core/payments.py` | `0c14d6b5331ab9902317f0534abee27d85932f62aa93fc93e59a1ce4344c15a9` |
| `core/payment_mock.py` | `4723c45360b02172e6f2ac1eaa08e413cc4080bde707ca6ff75a83e31c922444` |
| `core/membership.py` | `a46d3936d81423fc59c4894ff150dc659b4c33a7ca769e7de39a16a4afe6c189` |
| `core/billing_operations.py` | `4eb900e5410a8639a63b7f710d2a3179b2f299b10675742583bd822f9c272cff` |
| `api/v1/endpoints/billing.py` | `9253eef311154b401d1e1e2680ee1f02aa9111f38096a543dbb581e5b63aec40` |
| `api/v1/endpoints/payment_test.py` | `61a4f7bedd9e29403f0e2cd86c870faf423f7e95393b9596a87c9209d57d108f` |
| `core/paid_analysis.py` | `01ccfc1ff6fc509b66d16968a17814a0ef6dbe8bedfcaee822ec395bf196033b` |
| `api/v1/endpoints/paid_analysis.py` | `dc925c6de5a73fb232529de58670895d14eaef9fc19d25681a89a3b7d59b3d5e` |
| `interface.py` | `92e0fb59db690735ac36b030ef17d285b8af4dcd597b62ef932dded239387a18` |
| `server.py` | `344264e8bf804fd78373e84671612e389d3cc7b4a4272c037dc048bf2d62cc39` |
| `session.py` | `71f4a395bb653e068b2be0ae2cfcd331b13154e593a88ce4fe1b2e614930af05` |

以上路径均相对 `katrain/web/`。后续共享文件修改须由整合者按实际变更补充验收。
