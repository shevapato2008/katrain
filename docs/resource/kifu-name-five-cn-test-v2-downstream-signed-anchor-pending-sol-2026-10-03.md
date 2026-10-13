# 五位中国棋手 TEST v2：已签 anchor 下游 pending 包

已机械生成 **25 primary research、6 secondary batches（30 members）、55 candidates**。五个 anchor 与五个 raw scopes 的独立签名原样复用；本次不添加研究、batch 或 candidate 审批。

生产人 `/root/players_101_150_candidates_sol`，模型 `GPT-6 (runtime identity; no independent subtype attestation)`。生产时间 `2026-10-03T08:40:57.320954+00:00`，严格晚于 anchor review `2026-10-03T08:38:55.750750+00:00`。

- anchor 审核输入 manifest：`eb07a5041a0f8ba5cf0456549472d452e99a1c4ea8704a0d85c6b940206e7243`。
- 上游 pending 输入 manifest：`917ca1e848218ba506165047aba4a8e58c29e1a948f639dc49e13d5a8d9348e6`。
- 新包：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-downstream-signed-anchor-pending-sol/`。
- 新 manifest SHA：`c66f605fb442791313c236ff9eff2f2cfcaee1bc1f726d0118ec0cb3c612bf64`。
- bundle canonical SHA：`0919248441330ba045f6840019da0dcf55bd14eef87a6d4260b6696ebec09c93`。

55 显示值、25 份 source checks、既有 rules、owners/category 与 scope 均保留。只重绑五个完整 signed anchor SHA、research SHA、batch SHA，并记录实际新生产人/时间。25 个 research 通过现有 pending validator，5 个复用 anchor 通过 anchor validator；bundle `ready=false / write_ready=false / approved=0`。其余错误是未签 batch/member、未批准显示决定所形成的预期闸门。报告中的 pending=25 是当前通过结构验证的 primary 候选数，包内全部55行仍 pending。

当前绑定仅为冻结 clone `postgresql+psycopg2://postgres@127.0.0.1:55445/katrain_db`，inventory SHA `d5f376a980d12ec82ca18940b199295d6ce0f14b052261e9ce95afe58eb8af54`；clone 据上游已停止，本轮未连接。旧 capture 明确命名 `preimage-capture.historical-input-only.json`，fresh capture、candidate preimage binding、新审批、DB 连接/写入均为 **0**。

冻结配置离线重放一次：**22 个文件及 manifest 逐字节一致**；protected replay receipt 为包的同级 `five-cn-origin-main11-test-v2-downstream-signed-anchor-pending-sol-replay.actual.json`。包目录 0700、文件 0400。复放命令：`.venv/bin/python <包>/build.py --output <不存在的输出目录>`。

下一闸门：由不同 reviewer 独立审核/签25 primary research 与6 secondary batches。producer 随后使用实际批准 SHA 重新绑定候选，并捕获真实 fresh clone preimage；最后独立审核55候选。该包不批准 active TEST/PROD、apply、FK 或 alias。
