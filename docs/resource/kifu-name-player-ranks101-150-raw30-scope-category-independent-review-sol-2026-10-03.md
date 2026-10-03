# Ranks 101–150 raw30：有限 scope/category 独立审批 PASS

2026-10-03。Reviewer：`/root/five_player_test_stage_preflight_sol`，真实运行模型 GPT-6（未另行声称 subtype）；Producer：`/root/players_101_150_candidates_sol`。实际签审时间 `2026-10-03T08:00:21.727132+00:00`，晚于 producer 冻结／前像绑定。**仅批准 30 个 `readable_unlinked` 类别和 30 个精确 raw display scopes；候选译名审批、person ID／album FK／alias 审批均 0。**

## 冻结输入及逐项核对

输入为 [fresh direct155 v2 producer 记录](kifu-name-player-ranks101-150-fresh-bulk155-pending-sol-2026-10-03.md) 所指受控包，manifest SHA `36de195a01a1d9863f13c14adff8ac2d4e6c7bd09917c62338edc8ee8351f894`。独立复验全部 176 文件、15 外部依赖及 4 validator 模块绑定，未修改 producer 原包。

从 frozen PROD capture 原始 173,025 条 A／173,034 条 S 向量重算 inventory SHA，逐条重建 album association/source-link 投影；再重算六 catalog 表 hash，与 fresh inventory 和前像文件一致。该 capture 来自 `ucloud-v100 / katrain-ucloud-postgres-1 / katrain_prod_20260725`，`07:36:56.499701–07:38:29.824952 UTC`、同一 snapshot `1647002:1647002:`、`REPEATABLE READ READ ONLY`；本 reviewer 未连接数据库。

- 全部 raw 原始槽位 **16,551 = 黑 8,207 + 白 8,344**，覆盖 **15,880 albums**；30 个 raw 的黑／白频次、完整 occurrence ID/hash、全部 11-field context 和 scope content/hash 均逐项一致。
- 批准显示子集 **16,525 槽／15,856 albums**，未扩大任何槽位集合。所有匹配 player FK 为 NULL，source links 齐全，同名双边局为 0；类别解析正确，无原始拼写改写。
- **26 槽仍 HOLD 且未签入显示范围**：6 个 `1900-01-01` sentinel、16 个 `invalid_explicit_rank`、两个 duplicate albums 的 4 槽。例外由 fresh context 独立重算，完整 ID／slot／原因与 producer 清单一致；有效完整日期未发现早于来源生日的游戏。
- Frozen capture 的整个 raw-player value/name 表为空。30 个新 raw owner／name 前像均为空；不声称后来生产状态仍未变化。

## 签审产物

目录：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/raw-player-ranks101-150-raw30-scope-independent-review-sol-v2/`，`0700`；全部 9 文件冻结为 `0400`。30 scope content／slot 数组、owner create／occurrence 和原 category basis 保持原值，独立签署字段仅新增在 scope approval 与 category review。实际 `validate_raw_player_scope` 对全部 30 个 signed scopes 通过。

| 文件／对象 | SHA-256 |
| --- | --- |
| reviewer `manifest.json` 文件字节 | `bcdf46e05579da96ecfe4241d64ba44baab94d7e8589557d8302484779acc1b1` |
| `owners.raw30.reviewed.json` 文件字节 | `8418f8b96b2846a5c9f5abb88f791a70653efe710d44e0c9e1856bfe9ad9f1a7` |
| `scopes.raw30.approved.json` 文件字节 | `22635aa5f0e443129e8c6ecc2aa13b1bc548391b5f3509e39634317ab4d75911` |
| `scope-bindings.approved.json` 文件字节 | `53eb3114e4fe34b4b90bd8d9be3113424c9601912cfe8dfa763487b16c6466d7` |
| `review-record.json` 文件字节 | `7d2a48361094fbec407986e6ce1c359935e1a42d8ad71c9eda9b525af994efff` |
| frozen PROD capture gzip 文件字节 | `457959f10c94a38e87c1a90b19ffb8fbcbe9de9f507bfcba9f7fe229e9ab0bed` |
| fresh format2 inventory | `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3` |
| frozen catalog | `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09` |

`owner-audit.actual.json` 保存每位的黑白频次、全部／批准／HOLD 数、scope/occurrence hash、26例外和现有 canonical ID 线索；`scope-bindings.approved.json` 保存 pending → 完整 signed scope hash，供 producer 真实重绑 research/candidate。本审没有批准 155 个候选显示决定或最终 preimage binding；之后仍需独立 candidate 审批及实际目标 freshness/dry-run 闸门。

## 人物唯一 ID 与后续集成边界

**26/30 raw 在现有 `kifu_players` 中有精确同名 canonical 记录；这些 ID 仅为同名线索，不证明游戏人物身份或授权 album FK。** Exact alias 匹配为 0。全部 30 个值保留在 `identity-link-queue.unsigned.json`，后续仍须完成唯一人物 ID 与有限 album-slot 关联审核；签 raw scope 不等于身份归一完成。

运行时 `identity.py` 的 `strict_slot_approvals` 和 `resolve_strict_display` 在 `black/white_player_id` 有值时只取实体名称，raw-player 名称仅在相应 FK 为 NULL 时使用。未来签署并导入人物 FK 时，必须同时确保实体十一语已审名称已集成，否则 UI 可能失去已有 raw 显示。这 30 个 raw scopes 是当前阶段的有限展示审批，不是最终人物 ID 交付。

本轮没有线上数据库连接／写入、迁移、apply、重启、应用代码修改或 Git 提交；未审候选译名。
