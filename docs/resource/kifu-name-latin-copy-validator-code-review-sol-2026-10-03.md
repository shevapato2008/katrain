# Latin-copy 来源语言校验独立代码审查

日期：2026-10-03。审查范围为当前未提交的 `name_evidence.py`、`name_transliteration.py`、`test_kifu_name_transliteration.py` 改动；仅审查代码和测试，未修改生产代码、未提交、未操作数据库。

## 结论

**PASS。未发现 P0/P1，补充测试后无未处理 P2。** 当前改动没有扩大批量转写的目标语言权限，也没有把英文规则来源当作五种主语言名称证明。无需为了当前交付进一步收窄生产代码。

本次允许 `copy_roman_words_v1` 的规则来源正文诚实标为 `en/de/es/fr/tr`，符合已审核 Latin-copy fallback 需要使用 LOC 英文及 RAE 西语出处的背景。它只改变规则说明的出处语言，不改变原名/读音的证据要求、批准结论或候选集合。

## 权限与数据完整性检查

- `name_transliteration.py:131–154` 先要求 copy operation 的目标仅为 `de/es/fr/tr`，再传来源语言集合。`ru/ua` 不能通过改 operation 绕过目标限制；五主语也仍在规则和候选层被排除。
- `allowed_languages=None` 保留原目标语言语义。其他规则操作、普通原名/读音锚点和双出版社锚点的调用均未传宽化参数；`ua` 来源仍按 `uk` 校验。
- 每一份规则来源都单独通过语言、HTTPS、成功状态、hash 格式、正文摘录、来源依据及时间检查；不是只要求来源列表中任意一份符合语言。因此加入日语或未知来源标签不能被英文来源掩盖。
- 规则内容的批准 hash 在来源检查前验证。规则 hash 继续约束批次及每个成员，批次 hash 继续约束候选；任何来源修改都必须重新批准并更新依赖。
- 来源读音锚点、完整签署成员集合、机械输出重算、同语碰撞和已批准 conventional 名称保护未变。跨语言规则出处不会直接批准新人物、FK、棋谱归属或生产写入。

允许原本四种拉丁目标语言相互作为规则说明语言，比只允许 `目标语 + en/es` 更通用，但没有改变可执行 operation：仍只能按签署的读音词组作同一机械 copy。独立审核仍须确认具体出处支持该有限规则；validator 不自动把任意英文、西语正文解释为适用于全部语言的规范。当前代码不需要加入来源域名白名单或另一个规则操作。

## P2 测试建议及处理

初始新增测试证明英文来源可用于四种 copy 目标，并证明 `ru` 的 syllable map 不能使用英文出处；但没有直接固定「同为拉丁目标的 syllable map 仍严格」及乌语路径。提出非阻塞 P2：补 `de` 与 `ua` 的英文来源反例。

主代理已将反例改为参数化 `de/ru/ua` 的 `test_english_rule_source_does_not_authorize_syllable_transliteration`（`test_kifu_name_transliteration.py:521`），并对每项要求来源语言校验错误。建议已处理，无需再增测试层。

## 验证和限制

审查者在补充测试后独立执行 `.venv/bin/python -m pytest -q tests/web_ui/test_kifu_name_transliteration.py`，结果 **85 passed in 0.10s**，退出码 0。父任务所报更广聚焦测试结果不作为本审查者独立执行的证据。

此 validator 检查 source body hash 的格式，并验证包含它的已批准内容和依赖 hash；它不读取源正文文件重算真实 body hash，这是原有职责。真实捕获正文 hash 和摘录是否准确仍须在来源审核包中核验。本审查确认本改动未削弱这条边界，不代替具体规则来源及 132 个显示值的内容批准，也不批准数据库写入或生产使用。
