# SGF literal game / round — 独立代码审核

**最终结论（第 2 轮）：PASS。第 1 轮唯一问题已修复，无剩余阻塞；可进入计划既定的发布及逐包 dry-run 流程。以下保留两轮记录。**

## 第 1 轮结论

**CHANGES_REQUESTED：1 项有限阻塞，收窄新增数字规则后复核。**

- Reviewer：`/root/ret77_ko_astra_decision`，委派配置 `gpt-6-astra / max`。
- 审核记录 UTC：`2026-10-07T21:02:59.985415+00:00`。
- 冻结 diff：`/tmp/kifu-literal-game-round-chunk1-20261008.diff`。
- 独立重算 diff SHA-256：`25926934dcda3aa3d33316f12e4c246102cf7f3ab917a40c5344a18f9baeb87a`，与委派值相同。
- 范围：一个生产模块及两份测试的实际 diff、现有 parser 数字规则、owner marker 与严格读端相关上下文。未修改代码、执行 SQL/Git、部署或扩展数据审计。

## 唯一修改要求

**P2 — `raw_event_translation.py:68` 的新 `_POSITIVE_NUMBER` 超出已批准的 parser 正整数范围。**

新增汉字分支 `[一二三四五六七八九十百千万]+` 接受任意符号排列；数字分支没有现有 parser 的位数限制，并额外接受它不会作为新增 game/round 数字部件产出的全角写法。审核实际运行纯函数，得到：

| 提交给 mixed validator 的部件 | 校验结果 | 现有 parser 实际结构 |
|---|---|---|
| `game: 一一局`，core `友情杯` | 接受 | core `友情杯一`，game `一局` |
| `round: 百百轮`，core `友情杯` | 接受 | 整串为 core，无 round |
| `game: １０００局`，core `友情杯` | 接受 | 整串为 core，无 game |

这不满足计划要求的“新增分支仅接受 parser 实际正整数写法”。owner 的原 parts 绑定仍存在；本发现不宣称上述合成输入已经绕过数据库绑定或实际影响已存棋局。

最小修改：只把新增数字常量收窄到现有 parser 支持的 ASCII 1–3 位数字且数值大于零（允许其原本可产出的前导零），以及现有汉字 1–99 写法。旧 `_ORDINAL` 分支、旧零值及纯 `sgf_chinese` 不变。不增加重新解析层、不改 parser。补 1–2 个非法汉字排列或超出 parser 范围的新增部件拒绝例；保持现有三个真实正例及零值兼容测试。

## 已确认符合范围的部分

- 新 game 与无「第」round 均受 mixed 条件限定；research 前置 kind 检查同步，无普通来源或纯 `sgf_chinese` 的 game 放行。
- 旧 `_ORDINAL` 与新增 round 分支以 OR 组合。独立纯函数实测旧 `第0轮` 在两个中文 profile 仍接受，新增 `0轮` 拒绝。
- raw 字符集、逐字拼接、单 core、kind 唯一、parts/hash 及 SGF 证据检查保持；没有改写原文或把 game 转成 round。
- 新测试使用真实 parser 输出，覆盖 owner prepare/inspect/apply、research、名称 dry-run/apply 与三条严格显示读取，并断言 parser 原像与 SGF 不变。
- 150 raw 上限、完整 scope、CAS、profile marker 与严格读取资格相关生产逻辑未改动。无需为本次变更扩建审核或测试框架。

## 验证与文件锚点

Producer 报告两份相关测试 `145 passed / 9.75s`、diff-check PASS，以及修改前 9 个针对规则的真实失败。审核未把这些报告冒称自己的执行结果；本轮已独立运行上述五个纯函数边界例，发现明确问题后未重复全套测试。

本轮审读文件 SHA-256：

- `katrain/web/kifu/raw_event_translation.py`：`846fb376665ab93c70bc853866dcad23bf51752eca25d1ac6015a988f0073ef6`。
- `tests/web_ui/test_kifu_raw_event_title_translation.py`：`9b063c76b3ee485433c8535e39000b8b96b3d1a9fa9a92da88809abcf625ed30`。
- `tests/web_ui/test_kifu_raw_event_title_owners.py`：`55a2b53e8937fae19c6c323263d9662b5f5bd1bbf7f92547b4124cf6f070a770`。

第 1 轮结束时约定：下一轮仅核对这项修正和相关测试结果；发布与实际数据应用不属于代码审核完成状态。

## 第 2 轮最终结论

**PASS — 数字边界已按计划收窄，未发现本次有限范围内的剩余阻塞。**

- 同一 reviewer 与配置：`/root/ret77_ko_astra_decision`，`gpt-6-astra / max`。
- 独立复核记录 UTC：`2026-10-07T21:05:41.544167+00:00`。
- 冻结 diff：`/tmp/kifu-literal-game-round-chunk1-round2-20261008.diff`。
- 独立重算 diff SHA-256：`7134e8a15ac1312d83e3d4e07643c893365565bc0aad1e312809131aabf6e55f`，与委派值相同。

本轮实际读取新 diff；修正限定于新增数字常量及对应边界测试。新常量只接受 parser 的 ASCII 1–3 位正整数（包含 `001`、`099`）与其汉字 1–99 结构；旧 `_ORDINAL`、mixed 限定、research 前置检查及原像/资格约束保持。没有新抽象或 parser 修改，150 raw 上限不变。

独立执行了 15 个纯函数边界例，所有断言通过：

- 使用实际 parser parts 的 `001局`、`099局`、`999轮`、`九十九局`、`第2局`：mixed 接受，纯 `sgf_chinese` 拒绝。
- `一一局`、`百百轮`、`1000局`、`１０００局`、`0轮`、`0局`、`第0局`、`００局`：新增规则均拒绝。
- 旧 `第0轮`、`第１２轮`：两个中文 profile 均保持接受。

Producer 报告新增 malformed 用例在修正前 4 failed，修正后两份相关 suite `152 passed / 9.94s`、diff-check PASS；此处如实记录为 producer 结果。审核者执行的是上述独立纯函数复核，未重复 suite、未执行 SQL/Git、未修改生产代码或部署。

第 2 轮独立重算文件 SHA-256：

- `katrain/web/kifu/raw_event_translation.py`：`e9122f7fe70260a97e813cb8be9529fe2759750a71311c437ae61474dcf19fc4`。
- `tests/web_ui/test_kifu_raw_event_title_translation.py`：`a18b3330d5e236d79bc9f42ad33c0de640bf15b5a4d34a33bcb612de851fb63f`。
- `tests/web_ui/test_kifu_raw_event_title_owners.py`：`55a2b53e8937fae19c6c323263d9662b5f5bd1bbf7f92547b4124cf6f070a770`。

本次两轮代码审核结束；不追加扩展审核。实际部署、TEST/PROD dry-run、应用和覆盖率仍由后续既定流程报告。
