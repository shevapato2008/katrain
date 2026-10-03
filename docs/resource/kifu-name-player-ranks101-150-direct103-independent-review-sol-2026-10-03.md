# Ranks101–150：103 direct-source 独立审核

2026-10-03；reviewer `/root/player103_candidate_review_sol`，运行时模型标识 GPT-6（未把任务名中的 Sol 后缀作为模型证明）。**来源姓名 PASS 103 / HOLD 0；历史冻结范围候选批准 103 / HOLD 0；现役 TEST/PROD 写入闸门 HOLD。** 本次没有数据库连接、读写、canonical player ID/FK 批准、部署或 producer 包修改。

新受保护签包：`~/.local/share/kifu-name-audit/2026-10-03/player-ranks101-150-direct103-independent-source-review-sol-v1/`，目录 0700、140 文件 0400（含 manifest）。审核时间 `2026-10-03T08:58:22.973484+00:00`。

| 对象 | SHA-256 |
| --- | --- |
| producer 输入 manifest | `ec3b5ec5a001719c60db7ab966516cee182e2a98e5000e784de6a733f7344104` |
| 独立 identity/reading 输入 manifest | `dc034fd59cc13fea4d146854e114eab22e59e18574444c4fffba908a48f9670c` |
| 独立 raw30 scope 输入 manifest | `bcdf46e05579da96ecfe4241d64ba44baab94d7e8589557d8302484779acc1b1` |
| 新独立审核 manifest | `bc9232609f962781137048b731df4f91dc1a58fe42f1f1cea45ba786810f0fe2` |
| 103 approved candidate JSONL 字节 | `da6cad6a61f9ee07de3469f9ac09159f6dfce38cdce636e224eb7227337b0fa3` |
| 新 approved bundle canonical | `4333b88d9e55afe70056a25e860eaf3e3963e62035a904e491af40444660dc9a` |

逐格事实在 `checks103.actual.json`；候选文件为 `candidates.direct103.historical-frozen-scope.approved.jsonl`。签名结论明确限定为 `approved_conventional_display_for_exact_frozen_raw_scope_and_null_preimage_only`；每条签名绑定输入候选 hash、独立来源检查行 hash 和历史 capture 时间。姓名、producer 身份、research、原 signed scope 与 anchor 内容均保留。

73 条 GoRatings 完整 HTML 的姓名精确等于 `<h1>`，语言、同一 profile ID、官方资料链接和完整生日均与已签外部身份/reading anchors 对齐。20 个 cn 页面真实 HTML 标注为 `zh`，记录中保留该事实；简体 UI 正文及实际中文姓名支持 cn 使用，字形中性的姓名不被冒称为独有的简体拼写。没有把 generic zh 用作 tw。

17 条 tw、7 条 jp 的文本 capture 均回溯原冻结 HTML 并核验 HTML/text hashes、正文首段净名及 QID/sitelink/DOB。真实内容语言分别为 `zh-Hant-TW` 和 `ja`；原 HTML 的 parser-cache comment 直接写明每条 revision ID，tw 同时写明 `canonical!zh-tw`。另 6 条 fr/es 完整 HTML 直接核验 `<h1>`、实际语言、`wgRevisionId` 和 `wgWikibaseItemId`。公开 revision-pinned API 额外复查通过 17/24；7 次超时/429 原样保留为重抓可用性限制，不降低已有冻结原字节的证明，也没有继续重试。

童夢成 jp 修订 `78393770` 的生日为 `1996-04-01`；官方资料、已签身份及 Wikidata 为 `1996-04-26`。同一 QID、原中文姓名和明确围棋生涯支持姓名身份，生日冲突继续保留，本轮未裁定生日。韩国棋院作为资料发布者不代表人的原语言；日籍棋手采用已签 ja，中文棋手采用已签 zh-Hans，仅安祚永和洪性志采用 ko。

20 个 owner 声明与独立已签 scope 原对象逐字相同；11,318 个实际 display slots 的完整 context 与冻结 inventory 一致且 player FK 全部 NULL。原 26 个 context exclusions 保留，其中属于这 20 位的 13 个槽位均未进入签署范围。既有签名、依赖 hash 与 producer→reviewer 时间顺序全部核验。

历史姓名碰撞单独保留在 `legacy-name-matches70.actual.json`：**70/103 格对应 86 条旧 name rows，全部 `status=review / evidence_id=null / reference_kind=legacy_unverified`**。不是已核 canonical 身份证明。其中 13 格涉及多个旧 player ID，精确 owner/lang 对如下：

| raw owner ref | lang | 历史 player IDs |
| --- | --- | --- |
| `raw_ranks101_150_102_20261003` 彦坂直人 | cn、jp、ko | 465、489 |
| `raw_ranks101_150_116_20261003` 丁浩 | cn、en、tw | 36、62、390 |
| 同上 | jp | 62、390 |
| 同上 | ko | 36、390 |
| `raw_ranks101_150_126_20261003` 谢科 | cn、en、tw、jp | 250、335 |
| `raw_ranks101_150_136_20261003` 濑户大树 | cn | 613、643 |

本包内部没有同语规范化姓名对应不同 raw owners。`validate_bundle` 的碰撞规则只比较当前包 approved decisions；`name_batch._check_cross_bundle_collisions` 只读现役 `verified` names。冻结 catalog 的全部 owner name tables 中 30 条 verified names 与这 103 格的规范化比较匹配数为 0，因此当前历史匹配不会触发该 apply 碰撞规则。将来 legacy 名称变为 verified 或同时导入 raw/person owners 时须重新审查；本轮没有签署 `distinct_people_confirmed`，没有由同名猜测 FK 或合并身份。

103 个 null name preimages 精确绑定原 PROD read-only repeatable-read 事务 `2026-10-03T07:36:56.499701+00:00`；核验原 capture/sql hashes、整张 raw value/name 表为空、catalog hash 和 inventory hash。审核时该事务约 81.4 分钟旧；现有校验器没有最大年龄规则。签名只认可这个历史事务的冻结前像，没有断言现役目标库仍相同。

从落盘文件重新核验全部 139 个 manifest 内容文件、签名审计行 hash 和 bundle canonical，再运行现有 `validate_bundle`：`approved=103 / pending=0 / errors=[] / write_errors=[] / ready=true / write_ready=true`。这两个 true 是**给定冻结文件的离线校验结论**；不构成 TEST/PROD 写入批准。新增 signed-source 指针由本次独立审核验证，conventional importer 本身不会自动强制它们，后续必须携带本审核 manifest 的精确依赖。

**下一闸门：授权的 importer 审核对真实目标库重新核验 inventory/catalog/name preimages、verified 姓名碰撞和 runtime/schema，随后审批精确 dry-run/apply。** 冻结生产仍记录缺少 `kifu_album_event_selections`；本次未检测现役状态。canonical person ID、棋局 FK、10 HOLD anchors、5 mappings、余 52 direct cells 和 secondary172 均未被本签审批准。
