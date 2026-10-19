# 五名 raw display scope 内容 PASS，签署 HOLD

独立审核 `/root/five_cn_v3_independent_review_sol`，2026-10-03。输入 producer manifest SHA-256 `8f74d3eb95166a1e426ff842f192121b52e99863a7a0241f3fc38ec2aed97f5e`，逐文件 bytes/hash 相符。

五个 scope content 的 canonical hash 与 producer 逐名声明相同；全部4,358槽的11个 context 字段逐一与完整冻结 inventory 相符，精确原名且对应人物 FK 为 NULL，成员集合与全部 eligible 槽完全一致，排序和唯一性通过。逐名858/864/911/868/857，内容事实 **5/5 PASS**。

正式签署 **HOLD**：记录只有 content/content_sha256/owner/slot_count，没有 producer metadata 或 approval wrapper；manifest.created_at 无法代替实际 producer produced_at。审核者不补造实际生产者身份及时间。

唯一修正：producer 保持五份 content/hash 不变，在实际 record 添加 pending approval，包含真实 `producer_id/producer_model/produced_at`（时区）、`content_sha256`（当前相同）、`status=pending`、`conclusion/reviewer_id/reviewer_model/reviewed_at=null`。独立 reviewer 随后签 `status=approved`、`conclusion=approved_raw_display_scope` 和真实 reviewer 字段，再运行 `validate_raw_player_scope`；完整 signed record hash 只能在签署后生成。

冻结目录 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-v3-raw-scope-content-independent-review-sol/`（0700、文件0400），manifest SHA-256 `201385b0873323e1316af500ef5e41991ca4381f4e5cf11d71de6e77a1385848`。本轮没有正式签 scope、没有数据库连接/写入、生产者或应用代码修改。
