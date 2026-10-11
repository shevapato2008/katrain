# 高频中文三人精确槽：提交与复核

状态：独立 gpt-6-astra max 身份及修复后代码／计划审查 PASS，按协调授权 TEST → PROD 提交，两库直接复核均通过。执行计划与预演门禁见 [dry-run](kifu-player-highfreq-exact-dry-run-2026-10-04.md)。

| 环境 | 提交计划 SHA | 新增 FK | 保护 | hold | 提交后已关联槽 | NULL 槽 | 目录 ID | 报告 SHA |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| TEST | `33ae23a772f50da57f841d311db611f221fd4c05f7943bc6fe5edf349a60b0f9` | 3,805 | 5 | 2 | 273,695 / 346,050 | 72,355 | 3,848 | `e66cf2e8278b01cf934d31e49c3d9670ddaea0512cacf0d21e20ea2f0fee3a28` |
| PROD | `1a46ffefdbe0245bbd586fa51f7142247d898efe7ebcfa3c6e5ab40c51843c02` | 3,805 | 5 | 2 | 275,300 / 346,050 | 70,750 | 3,670 | `c1e97a9fff9ebd6854a3bb9a7e193f930771551c0c97ec3bf9c770e5fdae03d4` |

每库新增：小林光一 1,639、井山裕太 1,279、萧／蕭正浩 887；没有新建 ID、改 canonical、重指旧 FK 或搬迁译名／证据。5 个小林既有 FK 保持目标82，井山 album93943 黑白两个 hold 仍 NULL。称号旧 ID TEST339／PROD338「小林光一名誉」及相关 aliases、译名、evidence 与冻结前像完全相同。其他28个称号／混写原值未纳入。

提交后从当前数据库重新查询全部 exact raw 对应的 raw/date/source/FK 完整范围，逐项与计划加新增目标后的期望结果相等，保护和 hold 槽均匹配。10 个 staging metadata 指向正确目标和 review SHA，井山基本姓名保持 pending，held_album_ids=[93943]；其余九个 raw approved。两库分别全量读取 173,025 局，全部 PB／PW 与各自 post7 冻结 inventory 原文一致。目录数保持原值。

TEST 已关联槽269,890→273,695；PROD271,495→275,300。应用结果报告：[TEST](kifu-player-highfreq-exact-application-test-2026-10-04.json)、[PROD](kifu-player-highfreq-exact-application-prod-2026-10-04.json)。已提交计划不可重放。
