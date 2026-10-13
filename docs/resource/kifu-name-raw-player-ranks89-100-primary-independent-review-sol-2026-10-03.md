# Ranks 89–100：主五语来源姓名独立审核

2026-10-03，独立审核员 `/root/freq41_60_95_review_sol`。审核 [Luna 来源提案](kifu-name-raw-player-ranks89-100-primary-source-candidates-luna-2026-10-03.md)；输入 `capture-manifest.json` SHA-256 `92c6bba3aa5f781bd3f94508caff5513409d1de4835db1b94a04fb73c6fb7c1d`。

**21/60 来源格 PASS、39 HOLD。** cn 7/5、tw 1/11、jp 2/10、ko 11/1、en 0/12（PASS/HOLD）。只批准来源姓名与来源人物档案对应；不批准任何 raw 棋谱槽适用性、人物身份/FK、别名或库写入。producer 的原始出现次数未作为已审核槽集合使用。

| 精确原名 | cn | tw | jp | ko | en |
| --- | --- | --- | --- | --- | --- |
| 彭立尧 | 彭立尧 | HOLD | HOLD | 펑리야오 | HOLD |
| 吴侑珍 | HOLD | HOLD | HOLD | 오유진 | HOLD |
| 辜梓豪 | 辜梓豪 | HOLD | HOLD | 구쯔하오 | HOLD |
| 林书阳 | HOLD | 林書陽 | HOLD | 린수양 | HOLD |
| 刘小光 | 刘小光 | HOLD | HOLD | HOLD | HOLD |
| 余正麒 | HOLD | HOLD | 余　正麒 | 위정치 | HOLD |
| 李钦诚 | 李钦诚 | HOLD | HOLD | 리친청 | HOLD |
| 刘星 | 刘星 | HOLD | HOLD | 류싱 | HOLD |
| 赵善津 | HOLD | HOLD | 趙　善津 | 조선진 | HOLD |
| 古灵益 | 古灵益 | HOLD | HOLD | 구링이 | HOLD |
| 李赫 | 李赫 | HOLD | HOLD | 리허 | HOLD |
| 睦镇硕 | HOLD | HOLD | HOLD | 목진석 | HOLD |

## 复核依据与限制

- **35 个 manifest 条目全部核对原字节 hash/长度**，其中实际为 **34 份 HTTP 留存正文 + 1 份派生 CWA 七人摘要**，不是 35 份独立来源正文。派生摘要逐字段匹配完整官方 API 的 1,062 条名册；cn 七格以 API 原文为依据。CWA 前端 JS 确实记录该官方接口路径；空 SPA 页面没有被当成姓名使用证据。
- **21 格实际姓名、所在语言、身份上下文均通过。** KBA 十一格来自 `html lang=ko` 的真实韩文档案，逐格从姓名标题抽出 Hangul，剥离括号中的汉字及后续 `단` 段位，不把段位或导航当人名。海峰林書陽来自 `zh-tw` 的直接职业档案；日文两格来自 `ja` 的关西棋院、日本棋院档案，保留原姓名内 U+3000 空格。页内假名与拉丁姓名不计为新增英文使用证据。
- **12 个来源人物 crosswalk 全部对应。** GoRatings 的 profile URL/ID、实际 H1、DOB 与 CWA/KBA及台日职业档案核对；姓名、汉字副标、组织语境相符。重点排除了把吴侑珍当成其他吴姓韩国棋手、把刘星/李赫同名字面当作另一人物的情况。吴侑珍对应 KBA `10000736` / GoRatings `1315` / `1998-06-11`；赵善津对应 KBA `20000056` / GoRatings `95` / `1970-04-18`。这只链接来源档案，不能把全部同名原谱绑定到该人物。
- **39 格及其 HOLD 理由原样保留。** 未借 GoRatings 的本地化名填充本次限定的官方/职业出版物来源空格；未将韩日汉字当 tw/cn 证据，也未用普通转换或拼音补英文。

来源中的履历问题单独留存，未给升段/年份事实签署：赵善津 KBA 的九段日期 `1991.01.01` 与日本棋院 `1998年九段` 不同；余正麒 KBA `2026.09.11` 与关西棋院 `令和7年11月九段`（2025-11）不同；海峰林書陽履历含 `20011年七段` 笔误。上述来源姓名、DOB 和组织对应仍一致，故姓名格 PASS，履历差异不被擅自改写或用于 raw 身份外推。

## 受控记录

新目录 `~/.local/share/kifu-name-audit/2026-10-03/raw-player-ranks89-100-primary-independent-review-sol/`（0700，文件 0400）含：完整 60 格 `cells.reviewed.json`、12 条 `identity-profile-crosswalk.reviewed.json`、35 个留存文件、原 capture manifest、独立正文提取、来源差异/限制、review record 与 manifest。每格绑定原提案内容 hash、URL、正文 hash、实际 span 与独立审核时间；39 HOLD 不签正面来源结论。

- 来源格集合 canonical SHA-256：`a7990bc007b98611e1683ce06164644dea2e897e3e45e496449638a591808295`。
- review-record SHA-256：`2d49bb64c614327275707d28d9c66104e83e22728a6fd91d094ac2b9e2a8cf7b`。
- manifest SHA-256：`e72e98353161d6e0fcb9b9114758c088485f45d1a63be8f8677db47a025c8fe3`。

本轮未获取新页面、连接数据库、改代码/生产者文件或提交。独立署名与内容 hash 是来源事实审核记录，不是密码学签名或应用批准。
