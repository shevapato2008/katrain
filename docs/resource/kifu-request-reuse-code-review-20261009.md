# 棋谱列表请求内正交批次复用：独立代码审核

日期：2026-10-09。基线：`feature/kiosk-go-kifu` / `e334482a`。范围仅为相对 HEAD 未提交的 `identity.py`、列表端点 `kifu.py`、`test_kifu_name_orthographic.py`。依据：[实施计划](../superpowers/plans/2026-10-09-kifu-request-orthography-reuse.md)、[计划审核](kifu-language-latency-plan-review-20261009.md)。按 `requesting-code-review` 技能进行先规格、后代码质量的聚焦审核。

**最终结论：PASS。业务实现与代码质量通过；首轮唯一测试验收缺口已由新增跨请求用例补齐，独立聚焦复核通过，无剩余必须修正项。**

## 第一阶段：规格符合性

实现满足以下约束：

- 列表调用内部建立同一个空字典，并传入搜索与展示；玩家实体和 raw player 分支均接入，事件分支不扩展，未建立 Session、全局或跨请求缓存。
- [`identity.py:173`](../../katrain/web/kifu/identity.py#L173) 在读取批次前检查 `new`、`dirty`、`deleted`。有待提交改动时跳过缓存读写与刷新；正常复用路径在首次读取、空缓存、命中与失配时统一 `populate_existing()`。
- 批次 id 对应成功上下文及独立保存的 `status`、`bundle_sha256`、`reviewed_artifact` 旧值。状态必须为 `applied` 且三项一致才复用；失配先移除，再完整验证，失败不缓存。`deepcopy(snapshot)` 避免旧值随 ORM 刷新或 JSON 对象修改而改变。
- 名称/证据查询、creation ledger 检查及每名 `persisted_name_eligible()` 保留；后者仍调用 `verified_source_live()`，来源名称、来源证据、来源批次和 creation journal 校验未纳入复用。
- 新增参数默认 `None`，旧调用方式兼容；`name_orthographic.py` 未改动。

### 首轮必须修正，现已解决：跨请求用例未覆盖新请求首次读取旧 ORM 对象

位置：[`test_kifu_name_orthographic.py:1055`](../../tests/web_ui/test_kifu_name_orthographic.py#L1055)，重点为第 1079–1084 行。

现有用例在第一次请求的搜索验证中由独立事务修改批次，随后该请求的展示阶段已经刷新 `held_batch` 到修改后的值。第二次请求虽然重建空缓存，但其 Session 中的强引用已经不是旧值，因此不能检出计划明确要求防止的“仅缓存命中时刷新”回归。

独立验证：仅在审核 Python 进程内将 `if use_contexts:` 刷新条件临时替换为 `if use_contexts and any(key in orthographic_batch_contexts for key in batch_ids):`；三个新增测试函数（5 个 case）仍全部通过。未修改磁盘业务文件。该变体违反首次/miss 新鲜读取要求，证实当前用例缺少相应保护。

最小修正：保留现有请求内失效用例，另加或调整一个跨请求 case。先在同一个 Session 成功执行一次列表；持有批次 ORM 强引用；在两次请求之间由独立事务将状态改为 `undone`；明确断言读 Session 中强引用仍为 `applied`；第二次列表必须返回 `total == 0`，并使强引用更新为 `undone`。无需再次参数化全部字段或新增测试框架。

## 第二阶段：代码质量

**PASS，无另需修正的问题。** 改动集中在必要传参和现有批次查询位置；失败时沿用原验证，未改变权限与名称判定算法。缓存存储与失效条件直接，旧 API 调用可用，未扩大到其他语言机制或数据库结构。

性能收益仍需按计划通过一次代表性 TEST 只读请求计时确认。实现仍有 JSON 读取、深复制、内容比较及逐名来源校验成本；本审核不宣称已获得特定毫秒收益或已经上线。

## 验证记录

- 当前实现：新增三个测试函数，**5 passed / 162 deselected**，0.46 秒。
- 仅进程内“只在缓存命中时刷新”变体：相同用例，**5 passed / 162 deselected**，0.40 秒；用于证明上述测试缺口。
- 三个文件 `git diff --check` 通过。
- 主任务提供的已有结果：正交模块 167 PASS；列表 14 PASS / 1 skip；列表与名称 API 合计 77 PASS / 1 skip，另有 3 个 SQL 上限失败，已在归档 HEAD 基线复现相同的 `9 > 7`、`27 > 18`。本审核不将这些已证基线失败归因于本次改动，也未重复全量运行。

仅运行本地临时 SQLite fixture；未访问 TEST/PROD 数据库，未操作线上服务、部署或写入 Git，未修改业务实现。

## 最终聚焦复核

新增 [`test_list_refreshes_orthographic_batch_on_new_request_with_held_orm`](../../tests/web_ui/test_kifu_name_orthographic.py#L1089) 在第一次成功列表请求后保持原批次 ORM 强引用，由独立 writer 事务撤销批次，并在第二次请求前明确断言读 Session 中的旧状态仍为 `applied`。第二次列表自行建立空字典，必须返回 `total == 0`，同时强引用更新为 `undone`。该用例直接覆盖首轮指出的首次/miss 刷新边界；原有三种请求内失效 case 保留。业务代码未改变。

本轮独立验证只运行上述新增用例：**1 passed in 0.19s**。实施方另提供：原实现该用例 PASS；仅命中刷新错误变体下第二次列表 `total == 1`，用例按预期 FAIL；完整正交模块 **168 passed in 10.29s**。本轮未重复完整模块或 API 回归。

最终审核文件 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `katrain/web/kifu/identity.py` | `4095e932bacd5cf7ffb932131a23cc585dd66d48a2b8e84900940b372e8b02b8` |
| `katrain/web/api/v1/endpoints/kifu.py` | `f577e70a90e7cf8d6a2b9f7f37f8c1b38ed88526a9aef94ee270ddbb56db4897` |
| `tests/web_ui/test_kifu_name_orthographic.py` | `a13708d3643486aa35a8a11a33ee845f64eb1ac63a7e80f4a45aa3b01a25256d` |

**规格与代码质量最终均 PASS。** 该结论为代码审核通过，实际 TEST 性能计时及发布仍按主任务计划执行。
