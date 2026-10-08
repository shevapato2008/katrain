# JP 原名展示实施计划审查

日期：2026-10-09。第 1 轮结论：**CHANGES REQUIRED**，仅需以下两处修订。

审查对象为 `docs/superpowers/plans/2026-10-09-kifu-japanese-original-display.md`，对照当前 `name_evidence.py`、`name_orthographic.py`、`name_batch.py`、现有 orthographic 测试，以及这些路径实际调用的 `identity.py`。本轮为静态计划审查，未改产品代码，未运行测试或执行 SQL。

1. **补上持久读取的创建日志识别，避免生成记录被当作 conventional。** 计划 Task 2 的文件清单（第 31 行）遗漏 `katrain/web/kifu/identity.py`。该文件第 143–147 行仅把创建日志中的 `verified_chinese_display` 记录纳入强制 orthographic 复核。新 JP 记录若只扩展计划当前列出的文件，在名称、证据及 payload 中的 decision/version 被改为 conventional/none、`primary_orthographic` 被移除后，会绕过来源及批次资格检查，并计入 conventional。现有 `test_verified_chinese_display_reader_rejects_damaged_proof` 的 `masked_target` 案例已经覆盖旧分支的这个实际边界。最小修订：把这一个创建日志判定扩为同时识别 CN、JP 两种 reference kind，保持现有 SQL 不变；复用并参数化 `masked_target`，验证新 JP→CN 与 JP→TW 在这种漂移后均不能进入展示、搜索或任何 approved/conventional/generated 覆盖计数。把该 Python 判断纳入云端最小回补文件清单。

2. **移除失效 `/tmp` 决策文件的权威依赖。** 第 13 行引用的 `/tmp/kifu-jp-original-cn-tw-fallback-decision-astra-20261008.md` 实际不存在，Task 3 第 43 行仍要求依其审核。应明确历史文件已不可用，将本次会话已接受的边界在计划内作为可审查依据：同 owner、已合格 conventional JP、精确已应用批次及日志；CN 保留原码点且标为 generated；TW 直接使用同一 JP 来源及有限官方人名规则；仅 NULL 目标；2–16 个 CJK Unified 字符；不改 alias、身份合并或 schema。不得声称本轮已读到或验证过历史决策全文。

其余设计与既定边界相符：原来源绑定及写锁流程可以复用；CN 保留和 TW 转换已明确分开；目标占用、碰撞、来源漂移、生成计数和实际部署回读均有相应验收项。无需扩大到其他架构、全站测试或重复研究流程。修订上述两项后，第 2 轮仅核对这两处即可。

## 第 2 轮（最终）

日期：2026-10-09。结论：**PASS**，计划可进入实施，无待修改项。

仅复核上一轮两项：Task 2 已纳入 `identity.py` 的创建日志 reference-kind 判定，并要求 CN、TW 两个目标复用 `masked_target` 验证持久资格及 conventional 计数；计划已记录会话接受的完整边界，明确临时决策文件不可用，Task 3 改为依据计划中记录的决定审查。两项均满足要求。

本结论批准实施计划，不代表代码、云端发布或具体数据批次已经通过验收。本轮仅更新此审查文档，未修改产品或执行 SQL。
