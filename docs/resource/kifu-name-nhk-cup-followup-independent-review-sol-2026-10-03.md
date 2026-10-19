# NHK Cup follow-up：紧凑韩文来源与有限结构独立审核

2026-10-03，审核 `/root/freq41_60_95_review_sol`。核对 [follow-up memo](kifu-name-nhk-cup-followup-evidence-2026-10-03.md)及提交 `081115864a5dea2d23f44a14538e3a10327e97b9`；当前正文与该提交完全相同。

| 对象 | 结论 | 批准边界 |
| --- | --- | --- |
| ko `NHK배` | **PASS 来源事实** | KBA 真实韩文职业履历，明确第44届胜者，而非另一赛事的用时比较 |
| ko `NHK배 TV 바둑 토너먼트` | **HOLD** | 紧凑用名不能扩展为完整标题；本轮无对应职业来源 |
| 海峰刊载 `第65回NHK杯優勝` | **PASS 刊载事实** | 台湾专业棋院页面中的实际日文履历 |
| 原生 tw `NHK杯` 及扩展全名 | **HOLD** | 页面 `zh-tw` 不改变引用段落的日文属性 |
| de/es/fr/ru/tr/ua 六语结构约束 | **PASS 结构事实** | 保留 canonical token `NHK Cup`、届数整数、可空轮次；不批准翻译或显示字符串 |

## 正文与有限范围复验

两份新正文的字节数/hash、HTTP200、UTC metadata 均符合 manifest。KBA pkey `20000028` 正文实际为日本所属 `왕리청(王立誠)` 职业档案，记载 **`1997년 : 제44기 NHK배 우승`**；原日本棋院 NHK 历史表也列第44届、1997、王立诚，CWI 同届记录列 `O Rissei`。因此 `NHK배` 是该日本 NHK 围棋赛事的直接韩文职业使用证据。未批准展开标题、个人 FK 或全部棋谱的赛事归属。

海峰正文实际出现 **`第65回NHK杯優勝`**，相邻同一履历含 `第56期十段戦優勝`、`第73期本因坊戦優勝` 等日文。新捕获与此前留存正文 hash 相同；不把宿主页面语言当作该段的原生繁体中文语言。

从原冻结 gzip 逐原串复算 **115 个 explicit raw 字符串、合计 647 个 affected 计数**；逐项的届数/轮次/单位/计数与此前签署范围完全对应。另一个 `日本第43期NHK杯快棋赛` 为 single fragment，1 原串/1 affected 计数，继续 **HOLD**。

- 届数精确为 **3、6–9、11–30、32–33、35–45、47–59、63–67**，共56值；不扩大到未观察届数，也不从年份推届数。
- 轮次仅 **1、2、3**（分别43、41、23个原串）；**8 原串/61 affected 计数没有轮次**，保留 NULL。
- 74届日本官方页确实分别列 `1回戦`、`2回戦`、`3回戦`、`準々決勝`、`準決勝`、`決勝`。原串中的1/2/3轮不能自动映射后三种阶段。
- 六语仅保存 English-source-backed canonical token `NHK Cup` 与两个数字字段（ua 的语言标签为 uk）。不翻译 Cup/Go/round、不转写 NHK、不选择词序/变格、不拼接显示串、不宣称六语已有本地译名。

**647 是聚合分组计数，不是已经核实的647个精确 album槽集合。** 原分组没有 album IDs、SGF 或目标赛事前像；仅签115个精确原串及结构研究边界，未新增 event identity/FK、alias、owner、album link或十一语显示批准。

## 受控交付

`~/.local/share/kifu-name-audit/2026-10-03/nhk-core-followup-independent-review-sol/`（0700，文件0400）保留两份新正文、三份相关既有 JP/EN 正文、精确115条结构记录、fragment HOLD、六语结构约束、原签署依赖与独立review record/manifest。

- 新 KBA 正文 SHA-256：`bac30ee44b619b6d65c1f676be649d8b1875371abbd4cdde0b734cf8850a6fc3`。
- 海峰正文 SHA-256：`9e454d67519d93b5d8f2b1d6001099e6684a5d0ad77499c3682de38f8604617f`。
- 115条结构记录 canonical SHA-256：`16f9bb6ce58b9b3bd077c4dcaefdc4f66c3893c91c1da574f464b41802530846`。
- review-record SHA-256：`ed7f4c54221888076f83883b2b4812fd2a00594a9edcbe4f6c491b1936c1cd79`。
- manifest SHA-256：`c80a29da0e4a73503713144bf793ed507c841b6705975dff7687167a3f876558`。

原 grouping gzip SHA-256 `ae483b833c73879cf9b5544060d3857f1898806fddb76c93c2e6e0bda6716d05`；内容 `2cad3eb47908cc585c1090cd79e9209e8815b7025fef9724b0cedf2ca8b0b8d9`；底层库存 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`。本轮未联网扩展来源、连接/写入数据库、改代码/生产者文件或 Git 提交；署名为有限事实审核记录，不是密码学签名或应用许可。
