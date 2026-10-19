# 七个 raw-player 高收益姓名：stage1 独立审核 PASS

审核者 `/root/raw7_stage1_review_astra`；运行时标识 GPT-6，具体子型号未独立暴露。真实签署时间 `2026-10-02T23:52:11.876665+00:00`，与生产者 `/root/raw7_high_yield_binder_sol` 独立。固定 committed HEAD `3e6325699506197ad373fb02b6e61c00ca4a9123`，使用独立干净 worktree `.worktrees/raw7-stage1-review-3e632569`。

批准[生产者受控包](kifu-name-raw-player-next7-high-yield-fresh-clone-bound-pending-sol-2026-10-03.md)的 **7 个精确 raw 展示 scope、7 个 `readable_unlinked` 分类和 2 个有限 RU/UA 规则**。四条既有 de/es/fr/tr 签署记录原样保留。所有 scope/rule 内容与被审输入完全相同，只新增真实独立审核字段；没有签署锚点、研究、六语批次或 77 个候选。

逐字节复核全部 **93 个输入文件**。重新扫描冻结 inventory 的 173,025 条 album association，得到 **1,575 个全局出现槽 = 1,568 个十一语 PASS 槽 + 7 个 HOLD 槽**。owner 全局 occurrence 声明完整；有限 scope 精确等于 raw31 独立审核 PASS 集合，没有扩大。全部 1,575 个全局槽的上下文和来源注册与冻结 production preview 对应，目标人物 FK 仍为 NULL。

| 原名 | 全局出现 | 有限 PASS 槽 | 排除 HOLD |
| --- | ---: | ---: | ---: |
| 牛雨田 | 480 | 478 | 2 |
| 吴肇毅 | 223 | 223 | 0 |
| 安冬旭 | 208 | 208 | 0 |
| 廖桂永 | 208 | 208 | 0 |
| 宋雪林 | 197 | 195 | 2 |
| 佟禹林 | 154 | 154 | 0 |
| 岳亮 | 105 | 102 | 3 |

排除槽为：牛雨田 `119719/white`、`119723/white`（段位上下文异常）；宋雪林 `111594/white`、`133518/black`（孤立较晚老将上下文）；岳亮 `13287/black`、`13298/white`、`21001/black`（孤立较晚上下文）。既有 HOLD 理由保留，没有把来源人物对应转成人物归属批准。

七个旧 source anchor 的协会编号、唯一原姓名册项、完整生日、GoRatings ID、英文发表拼法与分词均匹配原批准记录。重新读取协会 1,062 人完整名册、28 个 GoRatings 本地化页面和台湾报道正文，**35 个 primary 显示值**的字形、实际语言正文、H1/生日或繁中报道字面上下文均通过。`吴肇毅 / 吳肇毅 / 呉肇毅` 分属 cn/tw/jp 的来源字形，韩文值按各页面保留。本次仅核对这些值，原 pending raw anchors/research/candidates 不获得新签署。

仅四条 Latin `copy_roman_words_v1` 规则可原样复用；旧 RU/UA 丁波规则确实仅含 `ding/bo`。两个新规则均严格限于七人所需的同一 **18-token union**，共 36 个映射。审核从保留俄文 HTML 与乌克兰学术 PDF 原字节重新提取表项，并与既有独立 33 人音节/显示审核及 31×6 草案逐项对应。36/36 通过；已知 held 音节 `hui`、`jun` 均未进入本规则。乌克兰语采用同一 2019 学术表，没有混用其他系统。

原 **186 个 31×6 输出**和本批 **42 个输出**均重新机械生成且完全一致。七人和冻结 31 人矩阵在全部十一语中均无归一化显示碰撞。这是有限冻结矩阵核对，未认证当前生产目录碰撞或时效。

受控审核目录：`~/.local/share/kifu-name-audit/2026-10-03/raw-player-next7-stage1-independent-review-astra/`（0700，冻结文件0400）。正式结果为 `scope-set.approved.json`、`owners.stage1.approved.json`、`category-reviews.approved.json`、`rules.approved.json`；`signed-dependency-hashes.json` 给出每个新依赖 hash，`verification.actual.json` 保存逐槽、来源、逐 token 与输出检查。

签后 scope 集规范 hash `ab02e1962ccb4612b2530dcad010f4a8df4a50a50c7b655472e1dddcdaf582d4`；owner 集 `8c75d11a91f7abead18d10cb81c052f264fc702c8dc399ed813352701967ac90`；六规则集 `2cded60d67d669806c143c8cc6489d279e9fefbd1d5e1ff26a28bf3e2baeb07a`。

| 新签规则 | 签后完整 record 规范 SHA-256 |
| --- | --- |
| ru | `bb061665a9e97f76eb3cef1cd9c1bd993e7434aa5ecf52ebbf00f388b6575e26` |
| ua | `d7f92ad760c5580ea7b411f0f8b6c39acd1f667ee0b9123de28bb5178ca1fdac` |

正式 `_v2_scope` 对七个签后声明通过，规则 validator 已通过规则段并到达原 pending batch gate。签后 scope/rule record hashes 已改变：后续须以晚于本次审核的真实时间重产 raw anchors/research，再按各依赖签署时间重产批次和候选。锚点旧文本仍称 segmentation/normalization pending，重产时应准确记录既有 reading 批准及此次有限 raw 范围；不得继承旧 pending 依赖 hash/生产日期。新规则来源字段的 unsigned 描述是保留的生产时状态，实际批准记录以本次 reviewer 字段为准。

本阶段没有数据库连接、没有访问或启动 clone、没有 Git commit，未更改生产者工件。冻结 inventory 来自旧 production dump 的 clone 捕获，生产时效仍 stale/unknown。阶段一无剩余阻塞；锚点、批次和候选的重产及独立审批、实际目标 fresh 前像/schema 核实和已授权演练仍需完成。当前数据库写入、人物 FK 和实际显示收益增量均为 0。
