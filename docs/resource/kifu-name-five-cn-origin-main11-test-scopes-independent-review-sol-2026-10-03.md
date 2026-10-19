# 五位 CN-origin 棋手 TEST-restored display scopes：独立 PASS

日期：2026-10-03。Reviewer `/root/freq41_60_95_review_sol`，真实模型 `GPT-6`（未声称另有 subtype attestation）；Producer `/root/five_player_test_rebind_producer`。**五 scope PASS，HOLD 0。仅签有限 raw-name 显示 membership，不签下游 anchors/batches/candidates、TEST 激活或 person FK/alias。**

输入远端冻结 manifest `b87d500a97b4075f4ed1fca7d2086eaa9be7e6e18e3e2c5291869239ce88b55c` 的 372 文件 byte/hash 全通过。对比已签 all11 bundle canonical `64e399b7c5f010012448b0e6ba189593f390da43d005825dcf9bd3fe031bfbfa`：每个 slots 数组（含排序、11 context 字段）、occurrence_album_ids/hash、owner 其余字段与旧签逐字一致；scope **content 唯一变化为 inventory_sha256**，producer/审批元数据按新记录正常变化。

从 TEST inventory 的全部 173,025 album associations 独立枚举五 raw spelling 的 unlinked black/white slots：集合与五 scope 精确相等，未遗漏或添加，context 逐字相等。总计 **4,358 slots / 4,238 unique albums**。签后实际 `validate_raw_player_scope` 五项全通过；输入 pending 门禁仍拒绝。实际 reviewed_at **`2026-10-03T04:16:36.927975+00:00`** 晚于 producer scopes/record 与冻结 `2026-10-03T04:11:26.309843+00:00`，真实独立 reviewer 与 producer 不同。

| raw | slots | status | 完整已签 scope canonical SHA-256 |
| --- | ---: | --- | --- |
| 唐韦星 | 858 | PASS | `e6227dcb0178aad46d8b57170dbd4a82ec362e4f1f1ee6545fd2643fff7c1867` |
| 杨鼎新 | 864 | PASS | `1295ed490bc0c47e73e3c8e743d50bd45a1a98f011fabd115cb620a83ad571a5` |
| 檀啸 | 911 | PASS | `d420e0beb518cb933746475d88c40fa79c3a800c0ab651ab627ce37b01abe830` |
| 胡耀宇 | 868 | PASS | `f1091155ec7c38f505648e4d2ca2233cd2e383c0a0404157f41e5329632e97cb` |
| 连笑 | 857 | PASS | `b2872b0becf2239ece6ff8d21424c0c9faa6907385331fe857f8cfdc24a0612f` |

新 TEST inventory SHA `d5f376a980d12ec82ca18940b199295d6ce0f14b052261e9ce95afe58eb8af54`，base SHA `c765d95689b98c6944cdab88b5a37cfd9a6fb2c2419807a7d10c64f8f455a87b`，实际 captured_at `2026-10-03T04:10:58.330005+00:00`。catalog supplement 从保留的全部六表原始 rows 独立重新 canonical 计算为 `3d4625b37b57c49f8fbf594a15f2bdb51525067df1cf2e7a5612dc5622f8fa79`，与 capture/迁移前后/producer一致。TEST catalog 有 1,088 players、22 events、23 player aliases、7 event aliases；这与旧clone catalog不同，scope批准未断言两者相同或继承旧 collision/final审批。五 owner/all11 name前像为空，approved-name snapshot为空。

隔离证据：唯一定向 DB `kifu_five_test_rebind_20261003` / container `kifu-five-test-rebind-db-20261003`，专属 network `kifu-five-test-rebind-net-20261003`；脚本硬编码该 clone，读取以 REPEATABLE READ / READ ONLY 执行。仅在恢复clone创建两张空 selection 表；2 CREATE、business row writes 0；迁移前后全部album fields+SGF基线hash一致。捕获/backup/停止回执和代码审查支持该producer步骤 active TEST SQL writes 0、prod connections 0、无active runtime restart；clone已停止。审阅者没有任何 DB连接或写入。

证据边界：全inventory数据库hash沿用真实 producer readonly capture/保留manifest及迁移前后证明，本次未重启远端clone独立扫描DB；外部 207,214,538-byte TEST pg_dump SHA `2fb2f147c543c82fb4a6cc7a3bea4682317e37a426678d65c08d630bcc103113` 由已保留远端hash/0400回执绑定，本次未下载备份。精确slot/context/occurrence与完整catalog数据已独立检查；不扩大为对其他操作者或时段的无写入证明。

受控目录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-scopes-independent-review-sol`（0700，文件0400）。

- `raw-display-scopes.test.approved.json` byte SHA `b831861ae84ec9f2a9a42c357a21cbea86c64cae3c38695fcdb23d655d64985f`。
- `scope-bindings.approved.json` byte SHA `b96c6be54084b5e9037c37add961260dfc2dc056631003bfa399646177695ea1`；含五个旧、新完整record和member/occurrence hashes。
- `review-decision.json` byte SHA `474b4a775b29e2a2e39dc243946f337301413ce94581fbfa451944818e4bd934`。
- `manifest.json` byte SHA `d88aec6da6fd6b9fa5989fc1d0e82288ccc38a9fda8a019f1354b2a19c75d745`。

下游只能使用以上 **完整已签 scope record SHA** 重绑新anchors，再逐阶段独立审查；旧anchors/batches/候选及旧55绑定不能自动获得新TEST scope资格。最终fresh preimages、ready/write_ready、clone演练与TEST上线仍未由本scope审查批准。没有修改producer/旧签包/应用代码，没有Git commit。
