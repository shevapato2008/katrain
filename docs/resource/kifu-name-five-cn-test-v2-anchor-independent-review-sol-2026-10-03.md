# 五位中国棋手 TEST v2 anchor 独立审核

结论：**5 PASS / 0 HOLD，仅签五个 source anchors**。时间：2026-10-03T08:38:55.750750+00:00。审核人 `/root/players_101_150_candidates_sol`，模型 `GPT-6 (runtime identity; no independent subtype attestation)`。

- 输入 pending manifest：`917ca1e848218ba506165047aba4a8e58c29e1a948f639dc49e13d5a8d9348e6`。
- 最新 scope 审核 manifest：`9c266a0ba00410c6bd4599e6eda773dad0b3f3692673603061fd312d9a7344be`。
- 逐人重核官方棋协原名、完整生日及 GoRatings 同 ID 的中文桥接页和英文读音，15 个 source role 全部与保留原文 SHA 相符；胡耀宇 locator 保留 `data.Z08[10]`。25 份 retained source checks 与旧已审源逐项一致，仅检查保留性，未重新签 research。
- 新 anchor content 与旧已审 anchor 的差异仅为 finite scope hash 及三处对应 scope 说明；原始身份、读音、分词、来源和 locator 保留。新签名不更改 producer/time/content。
- 五个最新 signed scope 经现有 validator 对冻结 inventory 的 exact unlinked context 核对；唐韦星 858、杨鼎新 864、檀啸 911、胡耀宇 868、连笑 857，共 **4,358 slots / 4,238 albums**。

唯一数据库标识为冻结 clone `postgresql+psycopg2://postgres@127.0.0.1:55445/katrain_db`，inventory SHA `d5f376a980d12ec82ca18940b199295d6ce0f14b052261e9ce95afe58eb8af54`。这份签名不能改标为 active TEST 或 PROD。本轮数据库连接和 SQL 写入均为 0，未改 producer 原包。

受保护输出：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-anchors-independent-review-sol/`，目录 0700、文件 0400。

- manifest SHA：`eb07a5041a0f8ba5cf0456549472d452e99a1c4ea8704a0d85c6b940206e7243`。
- `anchors.test-v2-signed-scope.approved.json` SHA：`4a4de6ea27658b8b1f3a596e6f1e9138a1e4f623f9c4ab18461a86cba14e7a38`。
- 27 个 manifest 文件和所有本轮使用的 source bodies 验证通过；五个已签 anchor 通过 `validate_transliteration_anchor`，五个 scope 通过 `validate_raw_player_scope`。包内包含审核脚本、输入依赖 SHA、source 重核结果与 signed record crosswalk。

下一步由 producer 使用本次五个完整 signed anchor SHA 重新生成 25 research、6 batches 和 55 candidates。三类新审批均为 0；55 个真实 preimage 仍须重新捕获/绑定后再独立 final review。此结论不批准 final readiness、数据库 apply、FK 或 alias。
