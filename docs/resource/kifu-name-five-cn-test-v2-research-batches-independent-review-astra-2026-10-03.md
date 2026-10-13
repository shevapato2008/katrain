# 五位中国棋手 TEST v2：研究与六批次独立审核

结论：**25 primary research 来源审批 PASS / HOLD 0；6 secondary batches PASS / HOLD 0，共 30 members。55 candidate/preimage 审批为 0，整体 write_ready=false。**

Reviewer `/root/raw30_anchor_review_astra`；模型如实记录为 `GPT-6; requested gpt-6-astra/max; runtime subtype unverified`。真实审批时间 `2026-10-03T08:52:33.554004+00:00`。本轮无数据库连接、SQL 写入、迁移、重启、FK/alias 审批；producer 原包及旧审核包未改。

## 输入与独立核对

- 本次 producer manifest：`c66f605fb442791313c236ff9eff2f2cfcaee1bc1f726d0118ec0cb3c612bf64`，22 个受控文件完整性通过。
- 五个已签 anchor manifest：`eb07a5041a0f8ba5cf0456549472d452e99a1c4ea8704a0d85c6b940206e7243`，本轮实际包内 7 文件通过；五 anchor 复制字节及完整 canonical SHA 均保持原签。
- 比较基准为旧 TEST 独立审核 manifest `31380564a30752dc7fb09b22e304c955aae06b812595ab84503ffeb8ea78c6fa`；其 14 文件及本次 producer 的 72 条外部依赖均通过 hash 核对。
- 25 research 相对旧已审研究只改变 `producer_id`、`produced_at`、signed anchor SHA、signed scope SHA。原名、25 source checks、显示值及 registry 不变。重新读 19 份原始 UTF-8 正文，核实 24 个 exact name span 和 1 个 Wikipedia passage；未进行换行或姓名规范化。唐 jp 为无空格 `唐韋星`，revision `103506819`；杨 jp 为 `楊鼎新`；胡耀宇官方 locator 为真实 `data.Z08[10]`。五个 CWA 姓名/ID/完整生日与各自 anchor 对应。
- 六个规则及 30 个旧显示值/成员不变；batch content 仅重新绑定成员的 signed scope/anchor SHA。重新 render 30 项均一致，五 owner × 六 locale 键集合完整，无同语碰撞。真实 production time `08:40:57.320954 UTC` 晚于五 anchor 审批 `08:38:55.750750 UTC`，也晚于规则审批。
- 实际 `validate_research_record` 25 PASS、`validate_transliteration_anchor` 5 PASS、完整六 batch 的 `validate_transliteration` PASS。批次 validator 使用从五 anchor × 六 locale 构建的最小键集合；未调用 candidate、preimage 或 bundle validator。

## 受控产物

目录：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-research-batches-independent-review-astra/`，目录 `0700`、文件 `0400`。

**Manifest SHA：`874cd34418ef65b4aaf7d487898c6905efd28c14703e540e220990a5a470f49b`。**

| 文件 | 用途 |
| --- | --- |
| `research.primary-five.producer-preserved.json` | 25 原始研究逐字节保留 |
| `research-reviews25.approved.json` | 25 条独立来源/依赖审批，签精确 research canonical SHA |
| `research-record-bindings.approved.json` | research、独立 review、signed anchor/scope 的完整 hash 对照 |
| `transliteration-batches.approved.json` | 六个完整已签批次 |
| `transliteration-section.approved.json` | 原样规则与已签六批次 |
| `batch-record-bindings.approved.json` | 六个完整 signed batch canonical SHA，供 producer 引用 |
| `source-research25.actual.json`、`rendered-members30.actual.json`、`validation.actual.json` | 实际逐项核对与 validator 结果 |

研究 schema 明确要求 `research.review_status=pending` 并禁止内联 reviewer 字段，因此本次采用独立 review envelope。后续 candidate 的 `research_sha256` 仍指向**原始研究对象**，不能改指 review envelope。批次依赖必须使用本包**完整已签 batch SHA**，不能引用 pending 或 content-only SHA。

下一闸门：producer 据本包重新绑定 55 candidate 并取得真实 fresh clone preimage，再独立 final review。新 `bound_at` 若晚于本次 batch 审批，最终阶段须以真实更晚时间重新审批六个完整批次并更新其完整 SHA，不得沿用旧时间绕过 chronology。本包只引用已停止 clone 的冻结上下文与历史空 name snapshot，不证明 active TEST/PROD 新鲜度或批准导入。
