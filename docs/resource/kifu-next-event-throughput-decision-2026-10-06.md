# 下一批赛事翻译吞吐决策

日期：2026-10-06；独立决策：GPT-6 Astra。第二轮更新依据用户再次明确的“赛事名字直接翻译，年份轮次按结构拆解，不要求每一个原始带年份标题逐字找到网络来源”。

## 决定

**批准将国家队 13 项与两个高频单项合成一个标准包：15 raw / 486 历史盘数 / 75 个五语名称，按 SGF 原文字面翻译继续标准化。** 不再寻找逐字包含年份、冠名及整个 parser core 的网页。先前本文件把外部 exact-core 来源设为入包前提的要求撤销；该要求超出了用户本次授权的显示翻译需求。

原始 SGF 的首个 **GN** 与已有 raw owner 证明“待翻译的原文是什么”；网页可辅助解释赛事概念和术语。两者都不证明所有原文属于同一赛事实体。`2013职业棋手精英赛` 也允许直接翻译，明确记录没有外部赛事证实，不改为别的已知精英赛、不填写伪造来源。后续 TEST/PROD fresh capture 已各核对 15 raw / 486 盘：全部没有 EV，首个 GN 均精确等于 raw；两盘第二个 GN 的超时注释原样保留。此处纠正此前 EV 假设，代码审查见 `kifu-national15-code-review-2026-10-06.md`；数据仍须正常绑定、签署与入库，不因本决策自动成为 apply-ready。

候选原文集合 SHA-256：`a1c386f0d6b606f2ed588d8b98bfd39398cec584bba683ab07e0dc7f9dede77d`。486 是旧捕获的目标覆盖量；写入范围以新捕获为准。不要为了凑该数量排除异常 occurrence。

## 草稿实际状态

| 组 | 数量 | 实际 parser / 来源状况 | 排序 |
|---|---:|---|---|
| 2020 国家队积分大循环 | 13 / 213 | `core:2020中国国家队积分大循环` + `round:第N轮`；现有语法兼容。新增 Sina/Sohu 捕获支持“国家队积分大循环”概念；2020、中国及逐轮数字来自原文。 | 第一批，不继续 exact-core 检索 |
| 两个高频单项 | 2 / 273 | `2013职业棋手精英赛`（137）与 `2014日本国家队新浪网络训练赛`（136）分别为完整单 core；现有语法兼容。后者有 2013 年博客支持网训/Sina 平台概念；前者如实无外部佐证。 | 两项均并入第一批 |
| All-Japan Women's Championship | 16 / 151 | `edition:19th ` + exact English core 等；东京例外不覆盖它。草稿只有 owner 原文，无外部来源。 | 第二优先；需一个 core 来源及一次固定 16 raw 英文届次扩展 |
| remaining CMB | 草稿 13 / 23；实际余 11 / 21 | 两个第9届 round raw 已完成。余项有双 core、年份/阶段嵌在 core、来源正文写法与 exact core 不同；例如 source 为“亚洲电视围棋快棋赛”，raw 为“亚洲电视快棋赛”。仅有杯名来源不能满足这些完整 core。 | 暂缓，不为 21 盘先扩展多种语法 |
| 阿含本选 | 10 / 205 | 已有正式包，两库 name batch **106** verify 为 50 names / 205 unchanged albums。原目录草稿的 pending 状态已过时。 | 排除重复交付 |

CMB 已完成的两个 raw 为 `第9届招商银行杯第3轮`、`第9届招商银行杯第一轮`；两库 name batch **107** verify 为 10 names / 2 unchanged albums。上述完成状态来自本地保存的实际 verify 结果。

## 已有真实网页的证据作用

捕获记录及原始字节在 `/tmp/kifu-event-title-national15-20261006/source_research.json` 和同目录 `sources/`。三页都是 HTTP 200；它们是辅助文章/博客，不标为官方赛事身份证明。

- [Sina 用户文章](https://k.sina.com.cn/article_7060223011_1a4d2742300100uxg7.html)：真实文字 `国家队国家队积分大循环第五轮`，重复“国家队”照实保留。SHA `defb26ffbcc949136ce40eb665e97222d1ef6a86211ec8ad380ea77a20506bcb`。
- [Sohu 回顾](https://www.sohu.com/a/443127195_120051921)：真实文字 `国家队积分大循环`。SHA `f24760c6fa009966b5af6e6675758e3e042cda1a59bcbdc9ba06bda1388c473b`。
- [新浪博客](https://blog.sina.com.cn/s/blog_4da014140101hzcb.html)：真实文字 `日本国家队网络训练赛`、`新浪对弈转换大厅`。SHA `4eebfc45db6d6e8a51beb6720ce27facf8f0aee9cead86dcf97486241f4b9d26`。2013 年页面只解释概念及平台，不能写成证明 2014 年那批对局。

## 最小代码调整与执行范围

1. **保留真实 parts，不改年份语法。** 国家队仍是上表两段，两个 singleton 仍是完整单 core；年份在 core 内不妨碍离线生成完整译文。研究说明可指出原文开头的 `2020`/`2013`/`2014` 是年份，不能伪造 `raw_parts.text = 2020年`。无需改 parser、parsed_data、裸年份正则或创建通用 qualifiers。
2. **增加一个显式 SGF 字面证据分支，仅允许本文件固定 15 raw。** 例如 `source_basis=sgf_literal_v1`，仍用 existing raw_event、`translated_from_original`、`literal_event_title` 和现有 raw generation rule。研究内保存原文语言依据与原始范围引用：exact owner/raw、实际 capture 时间、owner 审核采用的完整 `scope_sha256`、可追溯的 album/source_path/SGF hash 引用。复用已归档 owner plan 的 scope rows，不另建证据库；本批核对真实 `ev_values=[]`、`gn_values[0] == raw`，保留全部后续 GN 值及原始 SGF hash，不改写超时注释。外部 `source_checks=[]` 可诚实为空，`original_language_basis_url` 可缺省；三页实文进入 `translation_support`，不填写假 HTTP/URL、假 `found` 或拼接 exact-core excerpt。其他 raw 与 entity/player 不得进入这个分支。
3. **同步修改两个实际闸门。** `raw_event_translation.validate_raw_title_research` 对该显式分支保留 owner/raw、完整唯一 core、lossless parts、原文语种、五主语言和 provenance 检查，替换“必须有外部 HTTPS exact-core source”这一项。`name_evidence.validate_research_record` 也须针对同一分支调整其前置 URL 要求、非空 checks 及 `candidate_name == original_name` 的重复门禁；只改 pure 文件会继续被外层拒绝。旧无 marker 的外部来源分支及原 `event`/人物规则保持原样。
4. **沿用现有绑定，补最小一致性检查。** `name_candidates._validate_candidate` 可从既有 owner declaration 的批准前镜像核对研究 scope hash；`eligible_literal_raw_name` 核对同一 hash 等于实际 raw owner 的 `review_metadata.scope_sha256`。原文范围必须绑定本批现有 owner，不能只接受一个任意格式正确的 SHA。原始捕获及实际用到的辅助捕获时间都不得晚于独立审核时间；candidate→research hash、producer/reviewer、raw/lang/display/version 的检查保留。现有 writer 的 owner preimage、inventory/CAS、锁、ledger/undo 继续复用，不增加新的审批阶段。
5. **一个 `national15` profile，一次有限代码审查。** 固定上述 raw-set SHA 与 fresh 实际总量；补覆盖三个标题形态、范围外 raw/玩家或实体误用、raw/scope/hash 或签名不匹配、旧来源分支的聚焦检查即可。共享 pure 模块需同步到实际双 reader 运行时；无需改 reader 查询、schema、身份碰撞或 FK 规则。

## 第一批数据准备

1. 生成标准 pending research，补 registry/producer/owner 绑定等正常字段。国家队草稿 TW 的 `第N轮` 改为 `第N輪`；JP 的 `第N回` 明确译为 `第Nラウンド`。保留“中国”“日本”“新浪”等原文含义；不用“官方译名”“已核实同一赛事”等措辞。
2. 目前旧 capture 只有 owner/names；inventory 成员不是完整当前 scope。两库应一次捕获这 15 个 raw 的**全部 occurrence**、公开/duplicate/selection/FK 状态、完整 owner/name preimages、SGF/rank/source 等既有 scope 字段和名称/实体/alias 碰撞；正常路径要求全部 public、NULL event、无 duplicate/selection。刷新原有 inventory/catalog pins 后，沿用 TEST→PROD 的 owner→name dry-run/apply/verify。若出现真实范围或身份碰撞，按已有规则处理；不以补找外网 exact 字符串代替范围核对。

## 来源链接持久保存

后续标准包在计算 research hash、绑定 candidate 和签署之前，将**实际用于翻译的 supplementary captures** 放进 research 的 `translation_support`，随现有整条 research 保存到 `research_payload.research.translation_support`。每项保留 source ID、URL、实际 excerpt、body SHA、抓取时间/状态/语种、用途及归档文件引用；原响应文件继续归档。旧 external-core 分支的 primary `source_checks` 保持原规则；本批 SGF 分支将原文证据与概念辅助依据如实分开，不把另一语种或另一年份的辅助页冒充 exact 原始标题来源。

Tokyo 的 CWI primary URL/excerpt/SHA 已在 DB research；Kifudepot supplementary URL 目前在 immutable manifest/归档。该事实不要求重写已签研究：**禁止直接补改旧 research JSON 或 DB payload 破坏既有 hash**。新包从签署前就完整保存辅助依据，减少后续再次寻找主页。

本次只读摘要、实际 parser parts、来源字段、本地 verify/capture 及现有计划/验证代码；未联网逐项查证，未运行测试、改实现、签署或访问数据库。本文件更新本批来源策略，原始用户授权与数据完整性边界优先于此前过严的 exact-core 实现假设。
