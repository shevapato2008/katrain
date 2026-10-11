# 大手合剩余 exact type-only 关联执行记录

2026-10-04 独立审核通过并协调写入后，按冻结计划先执行 TEST、再执行 PROD。每库只更新 1,532 盘的 `event_id`，对应 131 个 exact raw；没有创建赛事、别名或届次。TEST 既有大手合 ID 为 1，PROD 为 22。

批准范围来自 [独立裁决](kifu-oteai-remaining-independent-decision-2026-10-04.md)，allowlist SHA-256 为 `edd2640dfb81619fe836cb88290f5a2c5442764bb2d69ff80e3fdfc572c43772`。实时两库的全部获准原值集合均为同一批 1,532 个 album ID，没有额外或缺失 ID。

| 环境 | 冻结计划 SHA-256 | 写入数 | 赛事 ID |
| --- | --- | ---: | ---: |
| TEST | `4aa59c839ff269ea5a9db585707d7ca4edb04e54b574596d615f8c82aab0e862` | 1,532 | 1 |
| PROD | `dfdce8dd0297750f687c520407d963480e345dfa1c6e86f710b6258402e83042` | 1,532 | 22 |

[执行脚本](../../scripts/apply_kifu_oteai_exact_type_only.py)在事务内验证目标事件身份和逐盘原始 EV、日期及两个 NULL FK，使用精确 CAS 只填 `event_id`。事务内及提交后均逐盘复查 1,532 盘的 EV/日期不变、赛事 ID 正确、届次 FK 仍为空；132 盘保留集合的全部冻结字段不变。源数据、玩家 FK、赛事别名和既有届次未被更新。聚焦测试 2 passed。写前 dry-run 是只读范围、目标实体和前像验证，没有执行 UPDATE。

[提交后执行日志和覆盖统计](kifu-oteai-remaining-apply-record-2026-10-04.json)：两库总盘数均 173,025、届次关联均 78,650、赛事类型均 73；TEST 类型关联 83,458，PROD 类型关联 83,940。TEST 验证时间为 UTC 05:19:18.823547，PROD 为 UTC 05:19:21.714159。
