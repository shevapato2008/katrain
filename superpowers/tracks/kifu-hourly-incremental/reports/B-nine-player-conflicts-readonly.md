# 首轮 B 九条 player metadata 冲突：只读诊断

范围：仅 `/app/data/kifu_ingest` 下指定九条 manifest/metadata/sgf 文件，以及 `kifu_ingest_items` 对应九行。未实例化 Stage 或 StateStore，未读 data/kifu-album，未调用任务/API/模型或修改状态。

九条暂存原始 SGF SHA 均匹配；manifest metadata、metadata sidecar 与 StateStore source_metadata 完全一致。读取时均为 Stage failed、journal quarantined、resume_phase downloaded、publication_key null。

| source ID | SGF PB / PW | metadata black / white | 结论 |
|---|---|---|---|
| 91088511 | 马靖原 / 李思璇 | 李思璇 / 马靖原 | 相同棋手集合，黑白执色互换 |
| 91284564 | 中根直行 / 崔珪昞]BR[九段 | 中根直行 / 崔珪昞 | SGF 姓名含损坏属性片段，不是可剥离段位 |
| 91284563 | 金灿佑 / 尹炫晳 | 金灿佑 / 尹炫皙 | 姓名用字差异；需数据级确认，不能直接视为等价 |
| 91141733 | 郑载想 / 许一笛 | 许一笛 / 郑载想 | 相同棋手集合，黑白执色互换 |
| 91195300 | 向井千瑛 / 李奈炫 | 李奈炫 / 向井千瑛 | 相同棋手集合，黑白执色互换 |
| 91192869 | 周泓余 / 唐嘉雯 | 唐嘉雯 / 周泓余 | 相同棋手集合，黑白执色互换 |
| 91392988 | 福风航太朗 / 邱禹然 | 福冈航太朗 / 邱禹然 | 姓名用字差异；需数据级确认，不能直接视为等价 |
| 91366815 | 赵奕斐 / 郑有珍 | 郑有珍 / 赵奕斐 | 相同棋手集合，黑白执色互换 |
| 91363310 | 李赫 / 陈品桦 | 陈品桦 / 李赫 | 相同棋手集合，黑白执色互换 |

## 结论与最小范围

没有干净 rank/空格差异。`derive_metadata` 已用实际 `parse_player(...).name` 比较，现有规则本来允许无歧义内嵌段位差异；这九条均不能由该规则消去冲突。91284564 的损坏姓名另被原生 parser 判为 corrupt_pending / sgf_property_fragment，即使略过比较也会在后续姓名有效性检查拒绝。

因此本次不需要代码修复或自动恢复：六条执色冲突须核对原始来源权威，两条字形差异须确认是否同一人，一条须修正或重新获取受审原 SGF。确认前保留现有隔离，不扩大通用名称归一化、不忽略来源冲突、不翻转原 SGF 或覆盖原暂存证据。任何后续恢复仅限经确认的这些条目，保留原始证据，并由 root 协调运行结束后的有条件恢复。

完整原文、字段 ranks、原生 parser 输出、Stage/StateStore 快照及原暂存 SGF见 `B-nine-player-conflicts-readonly.json`。
