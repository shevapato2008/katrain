# 赛事字面翻译提速补充决定：先补既有 game / round 资格

日期：2026-10-08。独立决策配置：`gpt-6-astra / max`。本次仅读取现有代码与冻结 RO 数据，并运行内存统计；未实施代码、SQL、签名或 Git 操作。

## 决定

**先扩充现有 `sgf_chinese_mixed` 的有限部件校验。** 接受 parser 已保存的 `game`：`第N局` / `N局`；接受已保存的 `round`：`N轮`，保留既有 `第N轮`。数字限现有 parser 可识别的正整数写法，逐字锚定；不改 raw、parts、parser 或 SGF，也不将 `game` 改成 `round`。此次不新增英文 profile，不同时扩展年度、首届、多段 core、标点或 season 规则。

## 同一真实快照上的量化结果

输入为 PROD `discovery-readonly.json`，捕获时间 `2026-10-07T20:28:20.150043+00:00`。其含 `parsed_data` 的待审行共 **15,235 raw / 23,667 games**。以下数字直接使用原有 parts，不重新解析。

| 准入范围 | raw | games |
|---|---:|---:|
| 当前混合校验函数实际通过 | 3,565 | 4,620 |
| 仅增加上述 game，新增加 | 3,702 | 3,822 |
| 仅增加无「第」的 round，新增加 | 627 | 1,653 |
| 两项合计新增，互不重叠 | **4,329** | **5,475** |
| 两项实施后的结构候选总数 | 7,894 | 10,095 |
| 对比：三个既有英文序数 grammar 的候选池 | 1,354 | 4,656 |

英文池是 `english_ordinal_edition / suffix / joined` 的总量，尚未证明都可满足一个新的英文 SGF literal profile。它还需要原语言、字符集、序数格式及 profile 分支的新增准入，因此此次优先补已有中文路径。

任务给出的 binder 数字为 3,557 / 4,440；本次直接调用当前 `validate_chinese_mixed_literal_parts` 的结构结果多 8 raw / 180 games。未将未核明的筛选差异归因为某个具体原因，也不把纯结构通过量替代 binder 最终可选量。

**5,475 是新增结构候选所对应的真实快照棋局数，不是已入库覆盖增量。** 新候选分布于 1,161 个精确 core；仍需逐包确认完整 GN/EV、SGF、成员范围、翻译与冲突资格。没有两名棋手的交集统计，不能推算 full-five 卡片增幅。

## 最小实施范围

1. 在 `raw_event_translation.py` 内为 **SGF mixed 路径**增加上述两种部件准入；`validate_raw_title_research` 与 owner 校验使用相同规则，避免一个接受、另一个仍拒绝。保持单一非空 core、部件 kind 唯一、逐字拼回 raw、原字符集和已有 year/edition 限制。普通网页来源、旧固定 profile 的范围不顺带放宽。
2. `scripts/kifu_raw_event_title_owners.py` 已通过共享 validator 取得 marker；复用现有 prepare / dry-run / apply 与每包最多 150 raw 的流程。保持 `parsed_data`、`parser_version`、raw、SGF、EV/GN、album/source/FK 原像；owner 仅改审核状态及 metadata，五语仅写入经审核的显示名。`sgf_literal_v1` 不建立正式赛事身份或链接。
3. 保留完整 scope/hash、原 parts hash、manifest/hash、独立真实 producer/reviewer 与时间、TEST/PROD 环境绑定、锁内原像/CAS、重放幂等、after-image 及严格读端资格检查。源字段变化就重新冻结；不能为通过校验删「局」、补写原 raw 的「第」，或缩小成员范围。

## 可立即承接的首包

代码交付后可重新冻结 **145 raw / 211 games**：

- 已有 BC8：`2016惠山古镇杯中国围乙`，8 raw / 74 games，现有 held packet 明确卡在 `N轮`；改用新的 mixed manifest，旧冻结件保留。
- `韩国GG拍卖杯绅士淑女擂台赛`，137 raw / 137 games，实际例子为 `18届韩国GG拍卖杯绅士淑女擂台赛2局`；137 条均有无异常的既有结构。

此首包是快照候选，尚未替代 fresh 完整 SGF capture 或 dry-run。当前清晰的 150 raw / 155 games 包继续推进。后续同一规则还覆盖 `正官庄杯三国擂台赛` 的 79 raw / 79 games。

## 风险与最低充分验收

主要风险是把局数当轮次、丢失数字/三番棋等 core 信息，或只放宽生产者而严格读端仍拒绝。用真实 `N轮`、`第N局`、`N局` 三类例子贯通既有 owner 与 translation 测试；补一个部件被改写或 kind 错配的拒绝例。复用现有 stale-scope/hash/CAS、跨 profile、重放测试，不新建通用框架。首次数据包须在 TEST/PROD 分别 dry-run 核对精确数量，再按既有流程应用与核验；不宣称正式赛事官方名称。

## 输入锚点

- Selection proposal：`/tmp/kifu-event-title-mixednext-20261008/selection-proposal-v1.json`，SHA-256 `2a25aa5ff367de8fd6b92e36ba646b94d61344ef59db319193b5fd93dfe4481c`。
- PROD discovery：`/tmp/kifu-event-title-mixednext-20261008/PROD/discovery-readonly.json`，SHA-256 `cc3589c646dbf3c562d1080bec339797260f31cab16da02f4b4f7ae360254cf9`。
- BC8 held summary：`/tmp/kifu-event-title-chinese8bc-20261007/held-summary.json`，SHA-256 `c46d7849e11acdbf258dbb39cb931fd455b954e09101b9a0f1195f96afbc486b`。
- `raw_event_translation.py` 审读 SHA-256：`616796e1b51b9f5afed877a3365d24e5c53d1a48abcc4100254cd41f2dafd70d`。
- `kifu_raw_event_title_owners.py` 审读 SHA-256：`b9660d75f6e0e0c5b334567b1ae3b1d7c00104ab319fd4e538b6b8b8f15c0d36`。
- `name_structure.py` 审读 SHA-256：`8923cc5c2c8370b3aa189dd0312657962daa26b4d4d662efbd85347579ac071b`。
