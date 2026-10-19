# 棋谱翻译安全暂停检查点（2026-10-10）

用户要求安全暂停，修改 Codex 并行配置并重启后继续。子 agent 已中断；没有尚在执行的数据库写入。不要把未签名来源候选当成已入库名称。

## 已实际完成

- 当前分支 `feature/kiosk-go-kifu`。测试 `home-ubuntu`、正式 `ucloud-v100` 均实际 apply 和 verify 到 **634**。
- 625：补齐尾崎春美、祷阳子韩文，两人五语齐全。实际 ID 是625；准备文件名624不代表提交批号。
- 重复身份归并：626朴智恩、628赵惠莲、630朴鋕恩另一写法、632崔珪昞、634尹俊相。五对共421个棋手 FK 槽，原SGF、历史段位、来源关联保持。
- 正式库五语齐全棋手 **1,756/3,690（47.5881%）**，当前活跃棋手3,308。原3,695人基线仍为47.5237%。五语齐全赛事类型 **64/85（75.2941%）**。
- 固定宽口径 **120,314/173,025（69.5356%）**；严格完整卡片 **45,980/173,025（26.5742%）**。统计由原已核实基线加577盘有限前后差量推导，没有声称全库UI重扫。
- 当前报告：[HTML进度](kifu-five-language-progress-2026-10-05.html)。实际回执在 `kifu-incremental-applied-2026-10-05/`。

## 仍未写入

1. **Chinen Kaori（知念熏→知念薰）84槽**：两端实际634后 capture/check/rollback dry-run 已完成，尚未独立审签和 apply。目录 `/tmp/kifu-next-eight-duplicate-seven-20261010/{TEST,PROD}-chinen_kaori/`；索引 `chinen-kaori-actual634-unsigned-review-pins.json` SHA `524f7c2aa1bd0425e3f505265d5e57a37140b9362efd8aef1bf887809b328a28`。干跑635已回滚，下一实际ID不得预先硬编码。恢复时核对活跃前像与原生CAS，过期则重新捕获。
2. **Ueno Asami（上野爱笑美→83）79槽 HOLD**：第三 owner TEST338/PROD337 `上野愛咲美女流` 的五行名称均为 `review/legacy_unverified`，无证据、无关联棋局；既有执行器仍拒绝带名称历史的退役节点，不绕过碰撞检查、不删除记录。独立 Astra 决定 `ueno-external-collision-decision-astra.json` SHA `8fe4ca2c7139c9b9570ac26aeefb346a94d31165ea6d972af21723b865b8facf`。其他批次可继续，不为79盘扩三方合并系统。本轮最终若只完成另外六对，授权变化是505槽，不能宣称584槽全完成。
3. **20位棋手 × 五语来源候选**：`/tmp/kifu-next20-players-source-only-sol-20261010/next20-main5-source-only-unsigned.json` SHA `4535ae03b592b245802b6db7a87aebe7124cdc8de27950affcab6bf9f719a6f1`。原队列game计数合计1,389，尚不是去重物理棋局数。29个来源URL、实际正文和可见摘录已整理；4538/6190/4692潜在重复、5563身份读音未明均排除。尚未绑定当前目录、签名或SQL。只读capture helper已准备但尚未运行；`gotoeveryone.k2ss.info`的曹恒梃英文尚需现有支持来源等价证据，不伪造source ID。
4. **50个赛事标题五语草稿**：20条v3和剩余30条均来源准备，未入库。赞助商可保留原名作字面翻译；少数赛制疑点单列。
5. **11/4431缺格来源**：已核7格来源加3格补充候选，待真实目录绑定。柳/栁差异不能冒充自动繁简转换。

未入库来源检查点包 `kifu-pending-sources-checkpoint-2026-10-10.zip`，39个文件，包含20人候选及实际正文、50赛事草稿、上野HOLD决定和知念待审索引。SHA `3857526e3bf96799421c941f337e3c1038b38aa8a41c7e7272f0c0d2284c765c`。其中 manifest 保留原路径、字节长度和哈希；若 `/tmp` 丢失可按路径恢复来源，原生数据库前像应重新捕获。

## 恢复方式

在项目目录恢复原会话，并将子 agent 上限设为10：

```bash
codex resume --no-daemon -c 'agents.max_concurrent_threads_per_session=10'
```

该设置不含主窗口，不等于CPU核心配额。重启后先核对运行时实际名额；旧会话名额为4（含主窗口），不能热修改保证生效。[官方说明](https://learn.chatgpt.com/docs/agent-configuration/subagents#global-settings)

继续时根窗口唯一SQL写者；来源查询和翻译分配给多个廉价agent，不确定身份由Sol处理，需要决策或独立审核由Astra max处理。复用此前来源，不重复全库扫描。每20棋手汇总入库，每次更新仍报告当前棋手/赛事数和宽、严格两种棋局指标。

可复用 agent：`pdf_three_operational_prepare_sol`（只读前像/统计）、`mixed_event_three_rebase_sol`（来源/候选组装）、`next_high_frequency_sources_luna`（批量查询）、`next_four_name_review_astra`（独立审签/决策）。名称入库沿用已有原生执行器，无需重启服务。
