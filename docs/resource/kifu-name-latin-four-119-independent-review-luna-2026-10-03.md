# 独立审核：119 名中国棋手德／西／法／土来源拼写候选

**裁决：PASS，119/119 个姓名锚点、476/476 个显示值。** 本次仅批准有限的规则与显示拼写：四语候选逐字沿用各自已批准的 GoRatings 英文姓名；不代表四语均有经证实的当地惯用译名。本裁决不批准人物实体或 QID 绑定、FK、SGF／棋谱归属、数据库写入、导入或生产使用。

审核输入哈希均与请求一致：候选 `outputs.pending.jsonl` SHA-256 `0be0f58a747085e90de15f47dba0f5454e6f6c45259bbf08b561d11526b30742`；上游批准锚点 `anchors.approved.jsonl` SHA-256 `fe2371a7ce47894bee17cf150a7eeae92f83191d1cd0ee701b75bd1a90fc8e71`。逐条比对 owner、汉字原名、批准的英文 source reading、完整锚点规范哈希和四语显示字段；119 个英文 GoRatings 留存页的 `<h1>` 均与批准拼写完全一致。复核并实测上游 241 个来源 body 哈希，全部匹配。

每个显示值均保留英文来源中的姓／名空格、大小写与给定名内部连写；按批准的 syllable words 重组后与英文来源完全一致。de、es、fr、tr 各 119 值，经 NFKC、casefold、合并空白后仍各有 119 个唯一值。与先前 33 人四语批准显示无碰撞；与冻结目录 876 个 canonical name、23 个玩家 alias、22 个赛事 canonical name、8 个赛事 alias 无规范化碰撞。目录快照 SHA-256 `420ed4a10445a8d50c49d1132cd47ee8eee893b871dce2a968e8593775fa6105`，沿用[33 人独立规则复核](kifu-name-latin-four-33-independent-review-gpt6-2026-10-03.md)中的同一来源拼写回退规则；本次另复核了先前 33 人包的 67 个来源 body 哈希，全部匹配。

**范蔚菁 / Fan Weijing：四语均 PASS，保留 `Fan Weijing`。** 留存的 Wikidata Q24473 德、西、法标签均为 `Fan Wei Jing`，仅在 given name 内多一个空格；土语无精确标签。标签是发现线索，不能确立当地惯用异名，也不推翻本批“照录已审核英文来源拼写”的窄规则。本决定不批准 Q24473 与棋手实体的绑定。

受控签署审核包位于 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/latin-four-119-review-luna/`（目录 `0700`，文件 `0600`），含逐锚点裁决、已验来源 body 哈希清单、审核报告、签署 attestation 与 manifest。`reviewed.json` SHA-256 `aaa20f8c596f8abe53b0039580dcf390f4b1db75379ad3e8e1d361c36f47c67b`；`row-decisions.jsonl` SHA-256 `195bf782bf35f1d0490c566709da80ae2631d3ae7533bef1d615a66c4285fa0e`；`source-body-hashes-verified.jsonl` SHA-256 `2f3baf81bf818f1ddf17e34e9e893b9ee2f6328cf60d0ed27a58aa7b38fd9d7f`；`review-signature.json` SHA-256 `d18637c7d81a431e9c4d79d0f50a25704d93995c53a9109119748ccaa36452e6`。
