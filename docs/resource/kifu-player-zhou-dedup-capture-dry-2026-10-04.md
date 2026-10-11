# 周鹤洋目录归并 B/C：冻结与事务回滚演练

2026-10-04。依据 `kifu-player-canonical-dedup-independent-decision-astra-2026-10-04.{md,json}` 实现并演练，**未 apply、未提交数据修改**。

## 实现与范围

- 脚本：`scripts/kifu_player_zhou_exact_dedup.py`。
- 聚焦测试：`tests/test_kifu_player_zhou_exact_dedup.py`，14 项通过。
- TEST：1028、9988、9989 归并至 1048；仅 87152 白方和 148135 黑方迁移 FK；raw 10145、10148 仅改 `review_metadata.player_id`。
- TEST 1028 的完整目录行与五条名称原像归档在冻结计划的 `archive`；1048 五条名称原行及其 `review/legacy_unverified` 状态保留。
- PROD：4193 canonical 从“周鹤样”改为“周鹤洋”；87152 白方保留 4193；仅 148135 黑方 4194→4193、raw 10148 metadata 指向同步迁移。归档并删除空 4194。
- 本批不新增 `周鶴洋` alias；该准确繁体别名留给后续完整姓名归并。禁止建立 `周鹤样／周鹤羊` 全局错字 alias。

| 操作 | TEST | PROD |
|---|---:|---:|
| 棋局 FK 修改 | 2 | 1 |
| 精确槽位原 FK 保留 | 0 | 1 |
| raw metadata 指向修改 | 2 | 1 |
| canonical 改名 | 0 | 1 |
| 归档后删除旧名称 | 5 | 0 |
| 归档后删除重复目录 ID | 3 | 1 |
| 新增 alias | 0 | 0 |

## 冻结计划

以下为计划内 `sha256`，即去掉自身 `sha256` 字段后，按脚本标准 JSON 序列化得到的内容摘要；文件字节摘要另见同名 JSON 记录。

- TEST `kifu-player-zhou-dedup-TEST-plan-2026-10-04.json`：`b5d1f5cb1dc9fd6176bbfad64a7b1f2185565b124e6127205c9adf81163e37fe`。
- PROD `kifu-player-zhou-dedup-PROD-plan-2026-10-04.json`：`f4dc01fed501e645e65625a9f086f3725dff457201856d5c10b1ae8741192613`。
- 两计划均绑定脚本字节摘要 `91ff92c538ee9b16545ff674dcdade2175b792c7fbe49382e4b98bf316064818`。
- 独立裁决 JSON 字节摘要：`a2a444ceeb7895ab03ba7a912c823431adb30b9e84f5e73c0f2389024888d1ef`。

计划冻结完整 players、names、aliases、evidence、raw 行、两个棋局完整行（含 SGF）、来源关联及来源行，同时记录真实入向 FK 结构和规范化 canonical/alias 碰撞结果。SGF SHA、日期、执色、原名、对手、结果与手数须满足独立裁决。所有待删 ID 的其他棋局或 raw metadata 引用都会阻止捕获或执行。

## 事务边界与实测结果

执行时锁定相关表、重新读取并比较完整冻结前像。每个 UPDATE/DELETE 额外使用 `to_jsonb(整行)=完整旧JSON` 的 CAS，raw metadata 保留原 kind、inventory SHA、parsed_data、raw 文本及 pending 状态。删除旧名称之后、删除 player 之前，再查询数据库全部现有入向 FK 与 raw metadata 指向，要求全部归零；任何新增 FK 类型需重新审核。

两库 dry 均执行了真实事务内修改和删除，验证完整事务后像后 ROLLBACK，继而在新的只读事务中复读并确认完整前像复原：

- TEST `kifu-player-zhou-dedup-TEST-dry-2026-10-04.json`：`committed:false`、`rollback_preimage_unchanged:true`。
- PROD `kifu-player-zhou-dedup-PROD-dry-2026-10-04.json`：`committed:false`、`rollback_preimage_unchanged:true`。
- 两库删除前 albums 黑/白、player_names、player_aliases、name_research_evidence 五类入向 FK，以及 raw metadata 引用计数均为 0。
- 未创建行，无序列分配。没有调用 apply，也没有生成 apply 参数文件。

TEST 一次 SSH 握手超时、PROD 一次参数文件复制超时，均在对应数据库命令启动前发生；重试后成功。

测试命令：`python -m pytest --noconftest -q tests/test_kifu_player_zhou_exact_dedup.py`。覆盖 metadata 保留、完整 JSON 漂移、残余引用、SGF 漂移、同人对手、额外旧 ID 引用、计划篡改、跨环境误用及 apply 摘要门槛。

未关联周鹤洋 860 槽及其他写法、其他棋手的待关联槽位、五语审核升级和 jp/ko 名称争议均不属于本批。任何后续 apply 需要按冻结计划摘要独立核准；脚本代码或前像变化会拒绝执行。
