# JP 原名展示规格审查

日期：2026-10-09。结论：**PASS**，无实质性规格修复项。

对照已批准的 `docs/superpowers/plans/2026-10-09-kifu-japanese-original-display.md`，本轮静态审查实际 Git diff 中的五个文件：`name_evidence.py`、`name_orthographic.py`、`identity.py`、`name_batch.py` 和 `test_kifu_name_orthographic.py`。

- 来源分支将 JP 精确限定为 `jp/ja/Kanji`，复用相同 owner、conventional、approved、revision、candidate/research hash、来源已应用批次及创建日志约束。2–16 个 CJK Unified 码点检查发生在任何规范化之前，旧 CN 来源约束未放宽。
- JP→CN 规则要求精确字段和值，输出直接等于 JP 原名；JP→TW 直接读取同一来源类型，沿用逐字单值映射、官方规则元数据、人名适用声明及既有例外排除。规则、member 和 anchor 的 reference kind 必须一致，生成 CN 无法成为旧 conventional CN→TW 来源。
- 两个目标均要求 NULL 前镜像；冻结快照和现有写锁流程阻止覆盖已占用目标。原有名称、alias 和同批碰撞检查继续生效。
- 实时来源检查已经覆盖 JP，继续核对当前 name/evidence 全镜像、已应用 batch、源 candidate/research 及两类日志。`identity.py` 的创建日志识别已加入 JP，使移除可变 proof/version、把 generated 改成 conventional 的目标仍需通过持久资格检查。
- 新增测试覆盖导入、读取、generated 覆盖计数、canonical/FK/SGF/rank 保留，以及两种目标的来源漂移、目标 REVIEW、缺失或不符日志和 `masked_target`。CN 与 JP 同字时仍可通过合格 JP 来源搜索到棋局，测试同时要求损坏 CN 名称不能继续显示或计数，符合既有搜索集合语义。

验证依据：实施者已报告聚焦模块 **148 passed**，并完成 `py_compile` 和差异格式检查；本审查按授权未重复执行测试。未修改产品、执行 SQL 或提交。本结论仅覆盖当前代码规格，云端发布及实际数据批次仍依计划验收。
