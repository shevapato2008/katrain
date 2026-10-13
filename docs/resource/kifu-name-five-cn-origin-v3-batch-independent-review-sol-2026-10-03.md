# 五名中文原名 category/batch 独立复核：局部 PASS，最终 scope HOLD

独立审核 `/root/five_cn_v3_independent_review_sol`（GPT-6 运行时身份），2026-10-03。完整 producer manifest 索引文件 bytes/hash 均吻合；5 个已签 anchor、2 条 RU/UA 规则与此前独立批准记录原样一致。使用 pinned registry `2026-10-02.8`，而非当前默认 registry。

实际冻结 inventory 的 4,358 个精确槽与既有 scope 三元组完全相同，各槽人物 FK 为 NULL；五名数量858/864/911/868/857。五个 category=`readable_unlinked` 与 conservative parser 相同；occurrence_album_ids 与冻结库存全部实际出现及其 hash 相符。**5 个 owner category 独立批准**，保留 producer 内容、ID/model/time，只新增 reviewer 签署并更新 owner_set_sha256。分类批准不证明同一人物。

producer 的独立隔离 clone 只读 snapshot/preimage 文件已离线核对：inventory/catalog hash 一致，before/after counts 同一，写入0；真实 approved-name snapshot 为0行；五个目标 owner/category/name 前像均不存在。审核者未重新连接数据库。

六批 grammar、完整 signed anchor/rule hash、时间依赖、snapshot hash 与30个输出均相符。**6 个 batch 独立批准**，真实 `validate_transliteration` 通过。此批准针对当前已给的有限 batch 内容，不批准写库。

随后以仅本地内存的 candidate 签署继承 probe 运行真实 `validate_bundle`，明确得到 **ready=false / write_ready=false**：30 个 candidate 各报 `raw-player candidate has no signed display scope`；另5条为下游缺已批准显示决定。未交付任何已批准 candidate 或最终 bundle。

## 精确窄修正

五个 owner 声明缺 **raw_display_scope**。现有 `scope.pending.json` 为三元组库存清单，不能替代实际已签 scope record。

producer 应为每名构造 `content/approval` scope：content 包含 `inventory_sha256/raw_value/applicability_basis/slots`；slots 按 `(album_id, slot)` 排序，每项精确为 `album_id/slot/context`，context 包含 `duplicate_of_id/player_black/player_white/event/round_name/black_rank/white_rank/date_played/black_player_id/white_player_id/event_id`，来自冻结库存真实前像。先由独立 reviewer 按 `approved_raw_display_scope` 签署，再放入 owner.raw_display_scope。不得由审核者补造 producer 内容。

`raw_display_scope_sha256` 必须指向完整 signed scope record 的 canonical hash。目前 anchor/member/candidate 中该字段是三元组列表 hash，因此 scope 签署后须由 producer 修订 anchor 的该绑定及对应叙述、重算 content hash；独立重新签 anchor。随后 producer 更新 batch member 的完整 anchor/scope hashes、重算 batch content hash，以新的产出时间再独立签 batch；最后继承 batch signature 与最终完整 batch hash 构造 candidate，再跑 validator。既有来源姓名/DOB/读音、token、输出事实均无需重查。

受保护目录 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-v3-batch-independent-review-sol/`（0700，文件0400），仅交付5 category 与6 batch 局部批准、category-only/final probe validator结果和review record。manifest SHA-256 `b47d718637486dc6f3151b46ff98737b3779ca546490d382f1a7eb346d93b73e`。没有数据库连接/写入、人物 FK/alias、生产者文件或应用代码修改。
