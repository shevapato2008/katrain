# 李昌镐 ID 143：五槽位 v2 待审关联草案

本记录说明有限 v2 待审包的生成与边界。它不是独立身份审核，不授权生产写入或部署。五个关联仍为 `pending`；没有生成任何最终身份审核签名。

## 包含范围

仅包含 Astra 有限身份裁决 [`4de8d3f6`](kifu-name-lee-143-finite-link-scope-review-2026-10-02.md) 核准的五个精确槽位：`40212/black`、`64489/black`、`83228/black`、`97368/white`、`98003/black`。其完整生产关联上下文、关联行哈希和生产 SGF 前像哈希均在私有包中。除此五槽位以外，没有棋局链接。

当次完整原文 `李昌镐` 的 2,140 个黑白槽位哈希仍为 `43b19733404467dbe5300258627767d32ecd13138de7ac81d26a5a720acac9ec`；五个入选项和 2,135 个 HOLD 项沿用 Astra 裁决中的集合划分，HOLD 集合哈希为 `7afade75df6fd0383c613fbb7b686624ba865363b7b1400b68847140472715c0`。包内 `raw_scope_sha256` 绑定完整 2,140 项原文范围，不是五项子集哈希。

## 当前生产前像

2026-10-02 进行了一次生产 `katrain_prod_20260725` 的 `REPEATABLE READ READ ONLY` 捕获。完整 album/source inventory 哈希由 173,025 条 album 记录和 173,034 条 source link 记录重算为 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`，与受控 inventory 文件的内部哈希完全相同。因而该 inventory 的关联内容得到当前生产快照的全量哈希复核；不以行数相同代替内容复核。

完整 catalog supplement 按导入器当前顺序读取 `kifu_players`、`kifu_events`、两张 alias 表和两张 raw value 表，SHA-256 为 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`。表行数依次为 876、22、23、8、0、0。player 143 的完整行前像为 ID `143`、canonical `李昌镐`、创建时间 `2026-09-30T19:33:17.795037+00:00`；没有该 ID 的 alias，当前 canonical 精确唯一。

当前实际 `name_preimages.json` 文件 SHA-256 为 `5e7ed4b44ea81707ce10384e31afc5219021cfd0a896157042b3575c438bb220`。其五个已存在名称行哈希在 live 表中逐行复核相同：`cn`、`en`、`jp`、`ko`、`tw`；`de`、`es`、`fr`、`ru`、`tr`、`ua` 六行当前仍缺失。候选绑定只引用这些真实前像，不为缺失行伪造值，也不改变目录成员资格。

五份生产 `sgf_content` 均在同一只读捕获中取回并计算 UTF-8 SHA-256，与 Astra memo 一致：

| Album／slot | 生产 SGF SHA-256 |
|---|---|
| `40212 / black` | `fc5f85221c020b5f9dfe5d0335819573176431daca8bb6574c14753090eea61f` |
| `64489 / black` | `258ef4e12adc36f5a78c189a5a97631c1588bccfaeaef354ec36305fc863e92c` |
| `83228 / black` | `e4046bc777ac563e5185edff1d460896e5465597840e2939c9154a1042252ecd` |
| `97368 / white` | `381dbd9b4353604cd6a0c0193a5e69e0f41e134d61a94dfdf93b10ae06dc5f30` |
| `98003 / black` | `bc8f87d0d83b589dabc147bd6351e4ec7d6fd5447ba647240383795d972103c6` |

## 十一语名称与签名边界

包含 `en cn tw jp ko de es fr ru tr ua` 十一语。十个名称候选沿用 [`fca78c69`](kifu-name-lee-player-143-source-approvals-2026-10-02.md) 的实际来源审核行；`ru` 使用 [`ea84b54f`](kifu-name-lee-player-143-ru-corrected-v2-independent-review-2026-10-02.md) 审核的修订二候选 `Ли Чханхо`。十一条研究记录均按候选的 `research_sha256` 原值抽取，来源生产者、来源审核者、结论及行哈希保存在受控来源候选副本和 provenance 文件中。

来源候选审核早于本次真实名称前像绑定：十语审核时间为 `2026-10-02T04:09:17Z`，俄语修订二审核时间为 `04:28:11Z`，提供的前像捕获时间为 `04:42:14Z`。所以包中的新绑定候选均设为 `pending` 并移除其顶层审核签名；不把旧签名挪用到修改后的候选行。私有 `source-reviewed-candidates.jsonl` 保留原先十一条实际签过的候选行，`source-provenance.json` 绑定各签名行哈希、候选文件哈希及研究行哈希。完成新前像绑定后的候选行需要再由独立审核者复核。

每条链接的 `identity_review.status` 也为 `pending`，只有真实 producer 元数据和范围输入，没有 `reviewer_id`、`reviewer_model`、`reviewed_at` 或审核结论。草案已记录五项固定成员、完整 `raw_scope_sha256`、冻结时间及其范围哈希 `221bb5180b81db45b44ea4f70bd56a5e052312b4713dddc5d4baa936c1b1668b`；该哈希不是批准签名。源检查使用独立捕获的日本棋院富士通杯成绩页 `https://www.nihonkiin.or.jp/match/fujitsu/016.htm`，响应体 SHA-256 为 `1e99d71bbc5f73f80c92785257d7ab8808d90a33f4bef56b5e44c430a1fddc47`，摘录具体绑定第 22 届（2009）和第 23 届（2010）比赛记录。

## 受控文件与验证

未签 payload 与证据位于 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-v2-pending/`；目录权限为 `0700`，所有文件权限为 `0600`。

| 文件 | SHA-256 |
|---|---|
| `bundle.json` | `7652d7a20b76e9f677651d0ea081acde64acf8449cd232ece6a242b08e87d00c` |
| `inventory-prod-v2-20261002.json.gz` | `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9` |
| `research.jsonl` | `0050a61c3f3cddeee2379469ccebe3473551a5e740d4a0f9aceb66e5ef751d58` |
| `sgf-preimages.jsonl` | `2b30b9c4961f9a41c17af97dfe2b5defae6200b140d36c1db06dfa6cf8539899` |
| `source-reviewed-candidates.jsonl` | `19fcf4397fe6f298e754cf2de2369d2094ac48934999b64260ca78f58b6d1dfe` |
| `source-provenance.json` | `7c7a2327ca45de977e5a1ba8d52bc0d4f4e69161348d64398782386e8abccd61` |
| `capture-summary.json` | `ee4c344486a5397a3a0bb3a4037e1ec71133f14885e923358ffc2f94582aa8e0` |

Ran the current offline validator against this bundle, registry `2026-10-02.3`, pinned inventory and eleven evidence rows. It returned `ready: false` with the expected five `link needs approved identity-mapping review` errors. Since the target ID is absent from the current album foreign-key inventory until those links are signed, dependent member/candidate checks also report the ID absent from approved links. `write_errors` was empty, confirming the bound-name preimage fields are structurally complete; this does not make the bundle ready.

No production rows were written, no deployment occurred, and no application code changed. A separate reviewer must inspect the final exact bundle hash, approve the five-link identity scope and eleven post-binding name rows, and then follow existing isolated rehearsal/release gates. Any changed production snapshot requires a new inventory/catalog capture and re-freeze.
