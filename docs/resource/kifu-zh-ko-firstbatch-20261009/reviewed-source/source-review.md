# 首批 CN/EN 来源锚点独立审批

**8 个锚点 PASS。翁子瑜可进入最终候选审批；王宏伟的生成韩名暂缓。**

审批人：`/root/zh_ko_task2_review_astra`，模型 `gpt-6-astra`，实际审批时间 `2026-10-08T22:39:02Z`。这是来源锚点审批；没有签署生成候选、最终研究 hash、bundle 或生产发布。

| 环境 | Owner | 已核来源名称 | 来源批次 | 锚点决定 |
|---|---:|---|---:|---|
| PROD | 5498 | 王宏伟 / Wang Hongwei | 563 | CN、EN 均批准 |
| TEST | 11272 | 王宏伟 / Wang Hongwei | 563 | CN、EN 均批准 |
| PROD | 5739 | 翁子瑜 / Weng Ziyu | 555 | CN、EN 均批准 |
| TEST | 11508 | 翁子瑜 / Weng Ziyu | 555 | CN、EN 均批准 |

签名文件为 [PROD-approved-anchors.json](PROD-approved-anchors.json) 和 [TEST-approved-anchors.json](TEST-approved-anchors.json)。每个 `approval` 均绑定原有精确 `content_sha256`，保留实际 producer，并填写本审批人的 ID、模型、时间及 `approved_orthographic_original`。8 个完整签名均通过 `validate_primary_orthographic_anchor`。

已逐一比对 pending packet、原 595 只读快照，以及后补的 `*-first2-source-proof-readonly.json.gz`。8 份 source name/evidence 均与快照、创建日志 after-image 完全相同，创建日志 before-image 均为 null，来源批次为 applied，且批次 bundle、candidate membership 和 research hash 检查通过。我读取了根代理的只读捕获脚本并核对回执；本审批人没有执行 SQL 或云端操作。

另对 8 份不同的原始正文重新计算字节 hash，核对 URL、抓取时间、正文及摘要：CWA 名录、两人的 U-Go 搜索和人物页、Daum 人名表、TVBaduk 中国名录、NIKL 完整规则。CWA 的两条汉名和 U-Go 同人汉名/完整拉丁名/CHN 信息一致；六个有限音节及 `hong` 的组合推导与 NIKL 原表一致。U-Go 未标注“汉语拼音”，普通话拼音的分类是已刊完整读音在此大陆围棋语境下的独立语言判断。CN/EN 锚点自身只批准既有显示名称，不把任意英文列等同于拼音。

Daum 的两行是与输出一致的正面社区用例。TVBaduk 的 `not_found` 只限实际保存的索引正文。缺实际抓取时间的 KBA 材料继续省略，未作为缺名证据。文件、锚点内容、来源正文和回执的精确 hash 见 [review-manifest.json](review-manifest.json)。

## 最终候选的处置

- **翁子瑜（PROD 5739 / TEST 11508）：来源输入可进入最终候选审批。** 已刊 `Weng Ziyu`，边界 `[["weng"],["zi","yu"]]`，规则输出 `웡쯔위`。最终审批仍须绑定含这次正式锚点签名的研究内容和实际目标前像。
- **王宏伟（PROD 5498 / TEST 11272）：生成韩名 HOLD。** 当前已批准的 CN/EN 证据内部保留了同人 GOR `/ko/players/477.html` 的 `<h1>왕훙위에</h1>`，原记录正文 hash 为 `6f28f59f9cb6495d35d4e37f12ceb73ee7b478d1fc56662a7c044f256cf26e91`，旧 root 决定也明确暂缓 KO。新的 pending research 未显式处理这项已知差异，却填了 `unresolved_conflicts=[]`。本次未找到该旧临时正文文件，因此不声称重新核过它的原始字节；它作为现有审核证据里的已知反例仍须保留。不能仅凭新规则输出就断言 GOR 错误或由机器生成。建议先交付翁子瑜，待这一差异被明确解决后再审王宏伟。

以上 HOLD 不撤销王宏伟精确 CN/EN 锚点的审批；它只限制生成 KO 候选。
