# English-form SGF 原始标题：Astra 独立决定（2026-10-09）

**决定：先实施最小 `sgf_english` 扩展，沿用现有 raw-title owner/name 流程。** 当前 591 player SQL 和已具备条件的中文批次继续执行。依据 next212 source-only 的 13 个 core、五语名字及现有 validator/owner 代码，180 个无内部显示碰撞的标题值得处理：保存快照为 900 个语言单元、1,606 盘；这些数字不是实时准入或已完成覆盖。

1. **准入字段。** 冻结 manifest 的 `profile="sgf_english"`；research 保持 `source_basis="sgf_literal_v1"`、`scope_status="translated_from_original"`、`translation_method="literal_event_title"`，设置 `original_language="en"`、`original_language_basis="reviewed_sgf_gn"`、`source_checks=[]`。这里的 en 指所翻译的英文形式 SGF 标题，可含罗马字专名，不声称赛事历史原名为英语。`owner` 必须是现有 raw ID；`original_name` 等于唯一 core；`raw_parts` 取该 owner 实际保存的 parser parts，逐字拼回 raw。五语 `cn/tw/jp/ko/en` 均提供完整标题。保留既有 producer/reviewer、registry、name preimage、scope、parts hash 和 CAS 字段；无需逐个赞助商查网，`translation_support=[]` 可接受。

2. **有限语法。** 仅 ASCII 字母、数字、空格、直撇号、连字符、逗号和 `#`，至少一个字母；仅接受唯一 core，以及可选的唯一 edition。覆盖现有四形：core-only、`1st Core`、`26thCore`、`Core,10th`；edition 范围与现有 parser 一致（1–999，正确 st/nd/rd/th），原空格和逗号必须保留。无需新增 year/round/game 语法，也不改 parser。原 `sgf_chinese` / `sgf_chinese_mixed` 的汉字与中文序数门槛保持原样；profile 与 original_language 交叉冒用必须拒绝。

3. **最小代码及验证。** 仅改 `katrain/web/kifu/raw_event_translation.py`（新 profile/validator、research 序数与语言分支、owner marker 匹配）和 `scripts/kifu_raw_event_title_owners.py`（共同 profile 集合、显式 validator 分派、manifest/CLI 接入）。复用 `test_kifu_raw_event_title_translation.py`、`test_kifu_raw_event_title_owners.py`：覆盖四种实际 parts、五语 apply/严格读取、错误 profile/语言、parts/hash 篡改及一个 scope/CAS 漂移；运行这两份既有测试以守住中文回归。不增 schema、pipeline、UI 或身份归并。

4. **数据边界。** 每批最多 150 owner；以 fresh TEST/PROD 完整 scope、现有 owner/name preimage 和正式库显示碰撞检查为准。`sgf_literal_evidence.owner_profile="sgf_english"`，保留 captured_at、scope_file/rows/hash、raw_parts_sha256。`original_sgf_refs` 必须逐份解析实际 SGF，保存实际全部 GN 值，确认第一 GN 恰等于 raw 且 EV 为空；不得根据 raw 拼造 refs。现有 validator 只核捕获 refs 与 scope/hash 的一致性，此实读检查须在本批现有 capture 步骤完成。沿用独立签名与 TEST→PROD 流程；SGF、FK、hidden、album/raw IDs、原文与 parser data 均不变。

5. **通用标题可准入。** `Hoensha game` 可作为原始棋局标签加入本批，采用包内 `Hoensha棋局 / Hoensha棋局 / Hoenshaの対局 / Hoensha 대국 / Hoensha game`；保留 Hoensha 专名，不推断机构中文名、不补成正式赛事。现有 `unclassified_pending` 分类和不批准身份/链接的 review 语义已足够。若 fresh scope 合格，合计 **181 标题、905 个语言单元、保存快照 2,201 盘**，分两批即可。另 32 个显示碰撞 variants（保存快照 58 盘）继续 hold；不为本次字面翻译合并 raw owner 或改造碰撞规则。

本决定批准实施方向和有限准入，不代替随后实际数据包的独立签名。已检查所选 181 行的保存 parts/字符/序数及五语字段，均符合上述形状；本轮未运行 SQL、修改产品代码、部署或执行 Git。
