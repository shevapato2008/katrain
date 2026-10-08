# 先交付 16 人，下一步增加有限中文人名转韩文规则

2026-10-09。决策及规划文件；未实现代码、签具体候选或执行 SQL。

**本批立即交付已通过原生门的 16 人。** 每 20 人是减少更新次数的工作偏好，不是必须凑满的准入条件。已做两轮补源仍无合格替补，继续等待四人对用户没有相称价值。沿现有 TEST→PROD、前像及撤销流程执行，不改 conventional 来源等级要求。

- 本批 16：`6366、5349、5952、6322、6550、4593、6571、5915、6367、6278、5912、5350、4031、5034、5296、5036`。
- 保留 source-only：`4071 华伟荣、6329 陈惠民、5495 王学传、4331 孟繁雄`。Daum 完整韩汉行仍是有效的身份/姓名用例，但其 `reference` 等级不能单独满足当前 `conventional` 门。不得重标为官方或专业语言站。
- 先前 [20 人来源判断](astra-pragmatic-identity-decision.md) 只证明身份桥及姓名来源可研究采用；原生入库资格以本次 16/4 决定为准。统计只增加真实写入且读端合格的数量。

## 已查代码：尚无可直接使用的中文→韩文正面 profile

| 现有位置 | 可复用部分与边界 |
|---|---|
| `katrain/web/kifu/name_evidence.py:31,180,446` | 已有 `pinyin-syllables-v1`、保留 ü 的拼音规范化、`reading_words` 音节、来源正文及哈希、原名/读音 anchor。来源拼音不是根据汉字自动猜出的读音。 |
| `name_evidence.py:1041` 及 `name_candidates.py:616` | 正面生成仅有 `normative_ja_ko_v1` / `nikl-ja-ko-personal-name-v1`，严格限已有 player、ja→ko、本人完整假名。普通 generated 旧路仍要求完整负面查询；不能伪造 negative closure 绕过。 |
| `name_transliteration.py:114,286` | 有限音节映射及完整批次证据可作实现参考，但目标只允许六种辅助语言，当前不能承载 ko。 |
| `name_orthographic.py` | 简繁字形、已核日文原文或官方 Hanja 保留；不是中文读音转韩文规则。 |
| `name_batch.py:761,942`、`identity.py:113`、`name_evidence.py:1623` | 已有正面方法的 applied batch / 精确研究与候选哈希重验；新方法必须接入同一显示、搜索、覆盖资格流程。 |

当前源码树未找到 `raw_player_translation` 模块/规则；实际是 `raw_event_translation.py` 和 `name_raw_player_scope.py`。不能假定已有名字转换入口。

## 批准的最小下一步

**新增一个独立命名、范围固定的正面规范分支：**建议 `source_basis=normative_zh_ko_v1`、`generation_rule_version=nikl-zh-ko-personal-name-v1`、`decision_kind=generated`、`scope_status=generated_from_original`。沿用现有研究、候选、签名和批次表；不扩展 conventional 门、不新增人物表、服务或通用音译架构。

1. **复用已核身份与读音。**首版自动范围限定现代中国大陆棋手、已有 player ID、确认为普通话本名的 `zh-Hans/zh-Hant` 及已有真实汉语拼音依据；CN 字形显示本身不证明中文原语言。允许复用已审 CN/EN 证据及同人双语专业资料完整行，记录各自 URL、来源角色、定位、正文及 hash，绑定 exact owner。华裔姓名的中文译名、韩日汉字姓名、其他本人实际读音不能据此转普通话。无需重查出生、段位或全部棋谱；不强迫套用现有要求 CWA ID/生日的 two-publisher anchor 格式。姓名两端已独立核实且同人桥明确即可。
2. **英文列只在确属普通话拼音时承担读音依据。**保存原始已刊拼写与姓/名、逐音节边界，再核规范化。台湾旧式罗马字、英文别名、`Chun/Chung`、拼写不能唯一切分者，不因字母看似合法就标为汉语拼音。`Huang Bi/Ben`、`Xuezhuan/Xuechuan` 等真实分歧逐人解决，暂缓该人即可。汉字拼音库或模型猜音不成为证据。
3. **冻结一个有限规则包并复用。**直接采用下方已完整实捕的 NIKL 原始正文、URL、时间、内容 hash 及具体条文/表格位置，不再抓同一规范。只收录当前批实际用到、已核准的拼音音节及对应韩文；不支持的音节拒绝，不设猜测回退。明确现代中文人名适用范围；古代人物、非普通话原读音另留待后续。保存姓/名边界；首版输出采用与当前中国棋手名一致的连写，这是项目显示格式选择，不宣称 NIKL 另有中国姓名强制空格条款，也不继承 JA 分支强制一个空格的校验。
4. **只做有限且真实的相反用名检查。**查原名/已核拼音的围棋身份及候选韩名的围棋用例，检查所有已知相反姓名。现有 KBA/TVBaduk/Daum 完整捕获可共用，逐人保存实际检索形式、范围、命中/未命中和定位；不重新下载同一名录，也不要求三个站点的全球负面闭环。必要的定向搜索保存真实响应。403/timeout 记 unavailable；只声称“本轮已查范围未取得可采用的通行名”。找到可靠已刊韩名仍优先走 conventional。社区形式可作为一致性/冲突线索，不能伪装成 native target-found。
5. **输出可重算、分类诚实。**每名保存原名、已刊读音、音节序列、所用规则条目、完整韩文输出及理由；独立核完整输出和跨 owner 名称碰撞，复用 `generated_review` 精确绑定。已核韩文名不被生成值覆盖。规则批准可跨批复用；无需每个名字重新审核规范全文。
6. **同一资格门验证并做一个正常批次。**在现有 evidence/candidate、batch proof、ORM 与实际部署 SQL reader 增加这个窄分支。不要让新方法退回普通 generated 的宽松读取；当前 `is_positive_ja_ko` 也会识别通用 `generated_from_original/positive_generation` 标记，分发必须明确区分两个 profile。只做相关阳性、错误读音/规则、篡改 proof、碰撞、未 applied 和旧 JA 分支回归，再验证一个真实小批次显示/搜索。完成后继续约 20 人一批，有少量 hold 就先交付其余，不为凑数扩张研究。

先关闭当前 16 人 conventional 批次，再实施这一分支。首个转换批优先选择已存在同页中文+明确拼音、仅缺 KO 的现代大陆高频 owner。社区四人的资料仍可复用为研究线索，但台湾两人不在首版自动范围，四人也不是必须凑齐的条件。目标是让多数普通名字沿相同有限规则继续处理，不为下一千人分别建生平档案。

## 本次 NIKL 核查范围

已复核 [Luna 规则事实包](../kifu-nikl-cn-ko-research-20261009/rule-findings.md)及其 5 份原始 HTML，5 个原始字节 hash 全部匹配索引。主源[国立国语院完整规范](https://korean.go.kr/kornorms/m/m_regltn.do?regltn_code=0003)为 HTTP 200、456,809 字节，SHA-256 `92977a7c4e2d255aa62d91011372bea1a198f5c3ee6f92db5b02fa6366fb9d9b`；完整正文已在该包 `captures/foreign-regulation-full.html`，不用再绕过本代理遇到的其他网址 403/404。

实际条文包括现代/历史人名区分、表 5 拼音/注音对应表、中文细则不标声调及特定声母后的元音调整。`wang (uang)→왕` 是表内明确项；`黄→황、陈→천、谢→셰、赵→자오、徐→쉬` 在已核普通话读音成立时是声韵表组合推导，不能说表格已经逐字逐人背书。这些规则事实足够作为有限 profile 的输入，尚不等于任何候选已批准。

[2026 年华侨姓名答复](https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=&pageIndex=1&qna_seq=328375)要求考虑本人实际使用语言和发音，因此首版明确排除仅有中文译名的自动普通话化。[简繁字答复](https://www.korean.go.kr/front/onlineQna/onlineQnaView.do?mn_id=261&pageIndex=1&qna_seq=325065)没有设定简繁硬性规范，不能拿它证明人物原语言。

补正事实包的一处范围：所摘“原文分写可连写”位于完整规范第 3 章第 1 节**英语**表记的复合词条款，本方案不将其冒充中国姓名专属空格规则。原始捕获及每条 URL/时间/hash 详见该包 `capture-index.json`，实施仅需冻结适用条目和当前批输出，无需再建规则档案。
