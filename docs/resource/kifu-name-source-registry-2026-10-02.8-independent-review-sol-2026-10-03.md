# `.8` 来源 registry 独立审核

2026-10-03；独立审核者 `/root/source_registry_08_review_sol`，与生产者 `/root/source_registry_08_luna` 分离。结论：**PASS（仅固定 registry 元数据）**。候选 JSON 与[生产者说明](kifu-name-source-registry-2026-10-02.8-candidate-memo-luna-2026-10-03.md)一致，无阻塞修复；此结论不批准抓取、姓名、人物主键、负面检索或数据库导入。

对照已审 `.7`、[41–60 补证独立审核](kifu-name-five-primary-frequency-41-60-cn-tw-ko-followup-independent-review-sol-2026-10-03.md)，重新读取相关留存 HTML、正文、metadata，并打开来源页面。仅版本、说明及末尾两条来源变化：原49条来源逐对象、顺序完全相同，11个 `language_tags`、11个 `language_scopes` 及实际调用 `source_plan` 得到的11个搜索计划完全相同；所有 `complete_for_negative_claims` 仍为 false。没有新增重复 FoxWQ/Cyberoro，也没有放宽负面结论门槛。

| 新 ID | 核对结果 | 结论 |
| --- | --- | --- |
| `ttplus-go` | [实际文章](https://www.ttplus.cn/publish/app/data/2022/01/03/407019/os_news.html)署名体坛周报全媒体记者谢锐，作者简介说明棋牌首席记者/编辑，平台介绍说明体坛传媒集团旗下体坛周报及体育杂志。`reference`、`zh-Hans`、`https://www.ttplus.cn/`准确；原 HTML `lang=zh`，简中判定来自正文。没有把媒体登记为协会官方名录。 | PASS |
| `hk2-go` | [首页](https://hk2.com/)标题为妙手棋院/围棋专业培训；历史留存正文有沙田地址，支持香港专业围棋培训出版方归属。[人物页](https://hk2.com/personages.htm)为繁中围棋人物资料。`language_go`、`zh-Hant-HK`、`https://hk2.com/`准确；未改标台湾。原 HTML 无语言声明、声明 Big5，CP950 解码确实得到相关人物正文。条目明确保留作者/更新时间不清、陈旧/重复材料、逐人独立职业记录核对限制，没有整页质量或原创性批准。 | PASS |

相关留存来自 `~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/` 下既有补证目录。体坛和HK2人物页各自 raw HTML、正文及metadata共6个文件的 SHA-256均与 `sources.manifest.json` 相符。体坛原 HTML hash为 `ca41001aa01f471808052be5f70018af0fb2456468549b9e51becf5bfd5bf3b8`；HK2人物页为 `549ad27fe67a5a91985c0405e8317ef0ef72a4ea93ba3386b37e07469b0b1f0d`。HK2历史首页原字节 hash为 `6c4e8df8a1a06d165b64ac7140b072611f83c6b0a4570aef9ed1e0b44de43857`，与先前审核一致；本报告没有把历史留存声称为新固定捕获。线上HK2首页工具解析有编码问题，出版方文字核对采用原字节CP950解码。

实际以 `.venv/bin/python` 调用 `load_registry`：`.8`载入成功，51个唯一 ID。逐项断言原49条、恰好新增 `ttplus-go`/`hk2-go`、tags/scopes/search plans不变、负面标志全false，以及两份实际文章URL通过对应来源host匹配，全部通过。未追加无关回归测试。

| 工件 | 独立重算 SHA-256 |
| --- | --- |
| 默认 registry 原始文件 | `9a3b3bd517e85f6822d2edd55bc06816bd202919c72214d91a8b7f8a1fd7b7f5` |
| `.7` 原始文件 | `e6ece1699371d54d719e8333cec2fa571c5fc6bb913f71815f0139399b2b591f` |
| `.8` 原始文件 | `2cfd665b215d1e8651ec9313953504d7c9ac0536d02548bfb8b8f80210593911` |
| `.8` 规范内容（`registry_sha256`） | `b1a43187a9694e8098697d0eb57ab97bcf0bea1042d16613d0361c36e9c54082` |

候选说明的全部hash一致。来源登记只提供出版方研究起点；现有host匹配不强制语言路径，也不代替实际正文语言、署名、身份或捕获审核。

后续研究记录仍须完成既有修复：显式绑定所选`.8`版本及规范hash；旧补证包仍绑定`.2`且pending，不能自动视为已更新。复用已有 `foxwq-cn`/`cyberoro`，HK2和Cyberoro记录使用 `language_basis: reviewed_text`并分别保留 `zh-Hant-HK`/`ko`；江维杰tw显示选择继续HOLD。登记的新增两项不解除这些限制，也不增加数据库写入批准数。

本轮仅新增此独立审核报告；未修改候选JSON、候选说明、默认registry、代码、受控原文或数据库，无提交。
