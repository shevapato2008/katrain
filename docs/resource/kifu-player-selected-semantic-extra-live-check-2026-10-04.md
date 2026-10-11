# 98 个语义误收原文的双库只读复核（2026-10-04）

范围：`kifu-player-selected-semantic-rollback-extra-2026-10-04.json` 的 98 个精确原文、203 个黑白棋手槽位；只读事务逐原文检查 `kifu_albums`、`kifu_raw_player_values` 与同名 `kifu_players`。

| 环境 | 原文 | 实际槽位 | 非 NULL 棋手 FK | 原文审核行 | 需要解除的 FK |
| --- | ---: | ---: | ---: | --- | ---: |
| PROD | 98 | 203 | 0 | 98 行均 `readable_unlinked` / `pending` | 0 |
| TEST | 98 | 203 | 0 | 98 行均 `readable_unlinked` / `pending` | 0 |

每个原文的实际槽位数均与冻结清单一致。AI 程序名 3 组/10 槽、双人连写 20 组/50 槽、学校/队名/地名前缀 45 组/58 槽均未关联；其余带棋品、称号或学生后缀的 30 组/85 槽亦未关联。没有任何当前 FK ID 可进一步追查同 ID 的其他对局引用；精确回滚的执行集合为空，不能无条件按旧清单执行 UPDATE。

目录核对：PROD 未找到与这 98 项 `canonical_name` 完全相等的棋手目录行；TEST 有 `kifu_players.id=1074`、`canonical_name=丁浩周泓余`，当前 0 个棋谱 FK、0 个别名。它是孤立目录行，需另行判断是否删除；本次不修改数据库。

若后续再次出现关联，应按 **原文 + 黑/白侧 + 当前 FK ID** 重新制作条件更新；真实姓名边界仍须人工审核。
