# 待执行赛事批次：top20 棋手回填后的独立精确 rebase

**结论：PASS，仅接受已提交 top20 决定造成的 29 个棋手 FK 变化。数据库写入为 0；赛事批准仍为 1,209 盘，HOLD 仍为 476 盘，旧 HOLD 4,292 盘全部保留。**

本审查以原赛事决定和 top20 棋手决定的固定 SHA 为依据，分别在 TEST、PROD 新建 `REPEATABLE READ READ ONLY` 事务，通过独立 SQL 获取完整前像后显式 ROLLBACK。没有调用赛事或棋手写入执行器。

|环境|数据库 UTC 快照时间|完整候选 / 实际列|棋手关联：前 → 后|赛事 / 届次关联（不变）|
|---|---|---|---|---|
|TEST|2026-10-04T13:03:30.923653+00:00|1,685 / 26|308,337 → 310,270|103,046 / 79,661|
|PROD|2026-10-04T13:03:30.764500+00:00|1,685 / 26|309,942 → 311,875|103,528 / 79,661|

两库总盘数均为 173,025；棋手关联各增加 1,933。逐盘比较确认仅有下列 29 个已批准棋手槽位由 NULL 变为固定目标 ID；29 盘均与 top20 执行计划及原赛事决定中的完整前像吻合。其余 1,656 盘的 26 列逐值相同；29 盘其余 25 列也逐值相同。

|专辑 ID|棋手槽|原名|TEST NULL → ID|PROD NULL → ID|原赛事决定|
|---:|---|---|---:|---:|---|
|12087|white_player_id|张涛|247|246|HOLD|
|12116|white_player_id|张涛|247|246|HOLD|
|12128|black_player_id|张涛|247|246|HOLD|
|12218|white_player_id|张涛|247|246|HOLD|
|13123|black_player_id|张涛|247|246|批准|
|13155|black_player_id|张涛|247|246|批准|
|19527|black_player_id|韩钟振|167|166|HOLD|
|25415|black_player_id|张涛|247|246|批准|
|25497|black_player_id|张涛|247|246|批准|
|25541|white_player_id|张涛|247|246|批准|
|26510|white_player_id|张涛|247|246|批准|
|68321|white_player_id|周鹤洋|1048|4193|批准|
|70884|white_player_id|韩钟振|167|166|批准|
|70896|black_player_id|韩钟振|167|166|批准|
|70908|white_player_id|韩钟振|167|166|批准|
|70949|white_player_id|韩钟振|167|166|批准|
|70951|black_player_id|韩钟振|167|166|批准|
|70957|black_player_id|韩钟振|167|166|批准|
|70962|black_player_id|韩钟振|167|166|批准|
|71110|black_player_id|韩钟振|167|166|批准|
|79363|black_player_id|张涛|247|246|批准|
|79466|black_player_id|黄宰渊|216|215|批准|
|79467|black_player_id|黄宰渊|216|215|批准|
|96072|black_player_id|张涛|247|246|批准|
|106320|black_player_id|张涛|247|246|批准|
|112399|white_player_id|张涛|247|246|批准|
|116703|white_player_id|张涛|247|246|批准|
|136719|black_player_id|周鹤洋|1048|4193|批准|
|147595|white_player_id|张涛|247|246|批准|

其中 24 盘属于赛事批准集，5 盘（12087、12116、12128、12218、19527）仍属赛事 HOLD。棋手回填不解除赛事 HOLD。top20 自身 HOLD 与赛事候选交集为 2301/white、7563/white，两槽仍为 NULL，整盘前像完全相同。

1,685 份 SGF 字节、1,685 条完整来源关系、2 个来源目录、82 个赛事类型、95／96 个赛事别名、1,535 个届次均与原像精确一致；保留全部原始时间戳。4,292 条旧 HOLD 与 476 条本次 HOLD 的 event_id / event_edition_id 均为 NULL。合计 4,768 条 HOLD 未释放。

原有 TEST 578／PROD 579 条引用棋手完整记录均未变化。为了守卫新引用，额外纳入已存在的韩钟振、黄宰渊、张涛三条记录：TEST 167、216、247；PROD 166、215、246。引用棋手守卫扩为 581／582 条，恰好覆盖当前全部候选 FK。新增守卫记录逐字等于 top20 已固定的原目录记录；没有新建或修改任何棋手。

原赛事范围、逐盘审批、赛事类型名和届次策略不变：仍只允许原批准集 1,209 个 event_id 更新及原定 3 个赛事类型创建。若随后仅提交原赛事决定，赛事关联应为 TEST 104,255／PROD 104,737；赛事类型数 85，届次关联仍为 79,661。当前 rebase 本身不执行这些写入。

JSON 包含两库 29 条逐槽变更及各完整行前后 SHA、源关系和 SGF SHA、棋手决定记录 SHA、完整守卫计数及 SHA、原始/新增引用棋手 ID、全局计数和精确重建结果。数据库一致性结论覆盖上述候选、目录、引用棋手、HOLD 守卫及全库统计；完整全库其他专辑字段不在本次采集范围。

|固定文件|SHA-256|
|---|---|
|`kifu-event-after-korean-two-next-post-top20-independent-exact-rebase-2026-10-04.json`|`54deecc86c3cf2db41760b7be7af654f262008d35dd76fa34bbbd3c2ee09e926`|
|`kifu-event-after-korean-two-next-independent-decision-astra-2026-10-04.json`|`264606394e2ad40dfec332ae660f8b281372cd4b6d30e6e8d646962ed487289b`|
|`kifu-player-exact-anchor-top20-independent-decision-astra-2026-10-04.json`|`6d53699a34bbcc4006020b9089977d4ca44eb4e192cd70db6021edb21dc5f39b`|
|`kifu-player-anchor-top20-applied-2026-10-04.md`|`8a6ca945d4d7f09316f69da00f299d25ae2a3103281e77efd890eccbd0b42695`|
|`kifu-event-after-korean-two-next-post-top20-independent-readonly-capture-2026-10-04.py`|`286360f5fe44ea06df40bf628d2a69edc927c823d2247367950b424e151e3eb3`|
|`kifu-event-after-korean-two-next-TEST-independent-full-preimage-astra-2026-10-04.json.gz`|`1c7eea811ecf6122e3ebb6cd565d7ba92647eb87302aff75362fe69c92ccbb6d`|
|`kifu-player-anchor-top20-TEST-captured-plan-2026-10-04.json.gz`|`f900cde8311614122ea3527d70f5786560621fb2c60a8c8660c61b38f5f784de`|
|`kifu-event-after-korean-two-next-TEST-post-top20-independent-full-preimage-2026-10-04.json.gz`|`35c812de4a131b5a7e57367f64184c0d483f67075b96a518d79e155708831ea5`|
|`kifu-event-after-korean-two-next-PROD-independent-full-preimage-astra-2026-10-04.json.gz`|`1ca0670bf2c336e750f06478a7732ec2d30f504f02fa53176db0c1f9fe50253b`|
|`kifu-player-anchor-top20-PROD-captured-plan-2026-10-04.json.gz`|`17ea7cb99b2fccb56a74f87f9fe6c2f5d7beef370348fc67177e83a4eb31eb91`|
|`kifu-event-after-korean-two-next-PROD-post-top20-independent-full-preimage-2026-10-04.json.gz`|`a74d2c192c36889da965d2f1765326fc478b8e6279b713f76267038bb61ffa53`|

所有新文件附独立 `.sha256` 旁车；原已冻结文件未覆盖。
