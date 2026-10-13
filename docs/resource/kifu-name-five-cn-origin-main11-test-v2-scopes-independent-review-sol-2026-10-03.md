# 五个最新 TEST v2 clone raw display scopes：独立 PASS

2026-10-03。Reviewer `/root/test_five_scope_review_sol`，GPT-6 运行时身份（无独立 subtype attestation）；Producer `/root/five_player_test_stage_preflight_sol`。实际 `reviewed_at=2026-10-03T08:25:02.737791+00:00`，晚于新 pending 包冻结及五 scope 的真实生产时间。**仅独立签五个有限 raw display scope；五项 category 保留并核对通过。**

输入 pending manifest 文件 SHA `bc0e99c9bc31df9efaac195efe82a40c01648544b012ceb365554cc22cfa9fa6` 的 35 文件、原始已签 manifest `819682d6faa96c67176960dfb68a9ea11786dc49122a208db83e5f33f8a66940` 的 19 文件、冻结 raw-display assessment manifest `f1efa529d5ca4c0d8e6502491394e907ffe0f432ef280643e3155d63ffc86e97` 的 6 文件，全部实际 byte/hash 校验通过。原始已审 25 项姓名来源正文 hash 同时复核通过；本轮不重审姓名输出或批准下游对象。

独立枚举新 format-4 inventory 全部 **173,025** 条 associations，五原串的所有黑白槽均为 NULL person FK，精确集合、排序、完整 11 字段 context 与 pending scope、原始已签 scope及冻结显示 assessment 逐槽一致，来源数组亦一致。五 scope content 相对原始签包仅变更 `inventory_sha256`。五 owner 的 occurrence ID 集、hash、create、ref、category review 与原签一致；保守 parser 五项均为 `readable_unlinked`，旧 category 独立 reviewer 与 producer 不同且真实时间顺序成立。历史 category_basis 中的 “Pending” 文案沿用冻结原记录，不影响已批准 status，也未被改写为新的类别签审记录。

总计 **4,358 slots／4,238 unique albums**。全部 **22 个既有 metadata 异常槽**原样保留：唐4、杨9、檀5、胡1、连3。日期、段位及赛事缺失不被修复或用于人物身份推断；`24170/black` 的杨鼎新日期保持 inventory 真值 **NULL**，未误用早期展示记录的空串。所有槽仍继承冻结 assessment 的 display PASS 与 person FK／alias HOLD 边界。

实际 `validate_raw_player_scope`：pending 五项均拒绝；新签五项 **5/5 PASS，HOLD 0**。

| raw | slots | 完整已签 scope canonical SHA-256 |
| --- | ---: | --- |
| 唐韦星 | 858 | `e48269773bd63dc3d7b5b3eaefe26bcfb29b768345da40b8fb3c4e8b24ae45bc` |
| 杨鼎新 | 864 | `34eaa2ec20ecc58e79fe9f11f9565214ea30f2a124b6aceac50d059246d7e1fd` |
| 檀啸 | 911 | `0aab22c60fa01d9ca63752ade5c00e33224b5c08f0ac60fae7613019f3a9e3d6` |
| 胡耀宇 | 868 | `db5147b25781912028c455fde53a97d939c98a6d2be27ee2127056195f04ddd3` |
| 连笑 | 857 | `565d202c506684542f6bc9d3b2e523de37ed711623ded4d0a045d4b5ad8ac9ad` |

新保护目录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-scopes-independent-review-sol/`，目录 0700、全部文件 0400。含 `raw-display-scopes.test-v2.approved.json`、`scope-bindings.approved.json`、`metadata-exceptions.preserved.json`、`review-decision.json`、可审计脚本及 `manifest.json`。manifest 文件 SHA **`9c266a0ba00410c6bd4599e6eda773dad0b3f3692673603061fd312d9a7344be`**。独立署名是 reviewer attestation 和内容 hash，不是密码学密钥签名。

目标实际 URL 为 **`postgresql+psycopg2://postgres@127.0.0.1:55445/katrain_db`**，inventory SHA `d5f376a980d12ec82ca18940b199295d6ce0f14b052261e9ce95afe58eb8af54`，base SHA `c765d95689b98c6944cdab88b5a37cfd9a6fb2c2419807a7d10c64f8f455a87b`。它是从 active TEST 导出的隔离 clone；active TEST 的受控来源标识为 `postgresql://katrain_user:***@host.docker.internal:5432/katrain_db`。不能改 URL 或把本签署当作 active TEST 审批。

源／恢复前／迁移后 19 表完整行指纹及 173,025 albums SGF/FK hash 在冻结回执中一致；dump 字节 hash、代码绑定、只读 capture 和停止回执复核通过。完整 base/catalog／表指纹属 producer 的保留 DB capture 和恢复证据，本 reviewer 未重新连接数据库计算，不扩大成独立 live DB 扫描或全库审计结论。

本次数据库连接／写入均为 **0**，未改原始包、pending 包或应用代码。未签 anchors、batches、candidates，未批准 FK、alias、active TEST／PROD、apply 或克隆写入演练。Producer 下一步使用上表**完整已签 record hash**重新生产并绑定 anchors，再进入相应独立审查。
