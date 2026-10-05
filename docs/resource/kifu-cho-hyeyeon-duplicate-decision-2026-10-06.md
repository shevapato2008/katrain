# 赵惠莲／赵惠连重复 ID 有限决策 — 2026-10-06

**决定：选择 B。CG 替换赵惠莲这一名成员，保留其余四人继续交付；将此对登记为已确认同人、待合并。当前不向重复 ID 写入第二套名称，不使用“同名异人”声明绕过碰撞。**

## 身份与两库映射

已读取 CG 的两库 `current.json`、source-map、保存的 KBA/GoRatings 文本，以及已应用 AJ 的两库归档。

| 环境 | 重复待退役 ID／目录名 | 已完成五语的保留 ID／目录名 | 后续合并方向 |
|---|---|---|---|
| PROD | 5961／赵惠莲 | 5962／赵惠连 | 5961 → 5962 |
| TEST | 11730／赵惠莲 | **895**／赵惠连 | 11730 → 895 |

TEST 保留 ID 895 来自 AJ 实际 bundle 与核验收据，不能按 PROD 相邻 ID 推算为 11731。

两包指向同一官方 KBA `pkey=10000146` 和 GoRatings 100，韩文原名均为 `조혜연`、生日为 **1985-06-07**。AJ 保存的原文身份片段也包含韩文／汉字姓名和该生日；CG 五语候选与 AJ 已写入名称一致。AJ 两库 batch 59 的收据均为 applied，并核验了保留 ID 的五种名称。因此这是同一职业棋手的目录重复，不能计为新增已完成棋手。

CG 最新捕获中，待退役 ID 在两库均有 **126 linked slots**，names 为空、五个 name preimage 均为 null。该捕获足以识别本次重复及停止重复名称写入，但未包含合并工具所需的双方完整引用／raw metadata／alias／审计前像。

证据位置：

- `/tmp/kifu-player-next5cg-20261006/{TEST,PROD}/current.json`、`source-map.json`、`sources/chohyeyeon-official.txt`、`sources/chohyeyeon-gr-en.txt`。
- `docs/resource/kifu-incremental-applied-2026-10-05/kifu-player-next5aj-20261005-{TEST,PROD}.json.gz` 中对应 owner、evidence、apply/verify receipts。

## 为什么当前不能直接复用合并器

`katrain/web/kifu/player_duplicate.py` 是固定 **朴文垚／朴文尧**、**李喆／李哲** 两对的执行适配器。`PAIRS` 只含 `piao`、`li`；`pair_key()` 明确拒绝其他 ID 对。

其 `_validate()` 还绑定每对的双方 canonical names、移动／保留 slot 数、唯一 raw ID、恰好一次 raw metadata.player_id 迁移、一次别名插入，以及待退役 owner 没有既有审核／名称／别名历史等条件。`capture()` 要求精确 FK/列集合和多表完整前像。当前不能仅换 JSON 的 ID 或重用旧 review；支持赵惠连这一对需要新增固定 pair 和独立的两人引用捕获、计划校验，这超出本轮“不新增工具／例外、快速五人交付”的范围。

## CG 的最小处理

1. 从尚未签署的 CG 候选／research/member 列表移除 PROD 5961、TEST 11730 对应五项，保留原来源及本同人结论供后续去重使用。
2. 保留其余已核对的四人：金主镐（6798／12567）、金仑映（6096／11864）、李瑟娥（5061／10843）、韩友赈（6800／12569），括号内为 PROD／TEST ID。
3. producer 从下一批已就绪、未重复保留的人选中补入一位，协调该人的批次归属，避免同时进入 CG 与后续包。仅对新成员与已完成／已保留记录作官方 profile ID 和人物对应核对，无需重审其他四人的来源或全库。
4. 重新生成五人／25 名称的有限 bundle 与 members/hash，绑定当前 inventory/catalog/name 前像后，按原独立签署、dry-run、TEST→PROD 流程交付。原 CG 是 pending，无需撤销数据库写入。
5. 状态明确记录 `same_person_duplicate_pending_merge` 及上述方向。此次重复不增加完整棋手人数，也不把这 126 slots 算作本批新完成覆盖。后续真实合并后，再按实际数据库重算去重人数与显示覆盖；不得提前宣称合并完成。

## 留给后续单对去重的既有接口

既有脚本为 `scripts/kifu_player_duplicate.py`；下面是其接口说明，**当前代码尚不接受此 ID 对**：

```text
check / dry-run:
  --plan <plan.json> --preimage <full-preimage.json.gz>
  --plan-sha256 <canonical-plan-sha256>

apply additionally requires:
  --review <review.json> --review-file-sha256 <exact-file-bytes-sha256>
  --actor-id <actual-applying-actor>

verify / undo:
  --batch-id <actual-batch-id>
```

后续单独处理此对时，复用该锁/CAS/账本/undo 路径，先捕获这两个真实 owner 的完整引用和 126 移动 slots，确认实际保留 scope、metadata/alias 情况与自我对局冲突，再适配固定 pair。保留 AJ 的名称、证据、源页面和审核历史；原始棋手文本、SGF 与段位不因 ID 归并改变。本轮不新增适配、不生成或签署合并审批，也不执行该脚本。

本次只读本地代码与证据、写本决策文档；无数据库或 SSH 操作。
