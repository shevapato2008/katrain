# 已核中文显示名转繁体：审核记录

**结论：PASS。** 第 2 轮仅核上一轮两项必要修订，均已落实；计划审核结束，没有剩余计划阻塞。

审阅时间：2026-10-08T09:54:59.460707+00:00。计划：`/Users/fan/Repositories/katrain-kiosk-go-kifu/docs/superpowers/plans/2026-10-08-kifu-verified-chinese-display-orthography.md`；SHA-256 `b6908d20dfaebf77d91f5bfff8eb8d7b7502577b678efc423afb80627e1a9d44`。独立任务配置 `gpt-6-astra / max`，无另一个可核实的运行时型号标识。

1. Task 1 已把源限定写成强制条件：只接受同 owner 当前合格的 conventional CN，name/evidence 的 decision、revision、display 与资格证据一致；明确拒绝生成、转写、正字法递归输入。第一项关闭。
2. Task 2 明确修改 identity.py、复用创建日志识别原始方法，并测试 name/evidence/candidate 标记和 primary_orthographic payload 被协同移除仍拒绝降级。第二项关闭。

范围仍为四个清洁姓名的 CN→TW generated 缺格显示；5410 留在实际 TW conventional 队列。完整源前像、目标缺格 CAS、旧门槛隔离和既有持久化证明均保留，没有扩张新服务或全库审核。可以按计划实现并完成其中约定的聚焦验证、独立代码审核及真实 TEST→PROD 验收，无需第 3 轮计划审核。

PASS 仅表示计划通过，不是产品代码审核、具体候选签署或实际入库/上线收据。本次只读计划并写本报告，未改产品、SQL、Git 或共享锁。

---

# Verified Chinese display orthography — focused re-review

结论：**PASS。首轮唯一阻塞已关闭，无剩余 spec 阻塞。**

本轮仅复核“目标 TW 必须缺失”修正和对应测试，未扩张范围。

- `katrain/web/kifu/name_orthographic.py:263` 仅对 `verified_chinese_display` 强制已签 member 的 `name_preimage_sha256 is None`。
- 同文件 `:374` 将 candidate 与 member 全字段绑定，`:408` 再核对目标前像；不能通过给 candidate 或重新签署的 member 填入现有 TW hash 绕过。
- `katrain/web/kifu/name_batch.py:277` 的既有锁内实时前像比较将该 NULL 限定落实为目标不存在 CAS；目标后填仍被拒绝。
- `tests/web_ui/test_kifu_name_orthographic.py:289` 新用例创建真实既有 review TW 行，捕获非空 hash，同时刷新 candidate/binder/member，验证候选不可写、apply 拒绝且原值保留。`:312` 的原 target_filled 漂移情形保留。

父任务已报告聚焦 orthography 测试 **86 PASS**。本轮独立完成源码与测试路径复核；遵照只读约束未重复运行数据库测试，未执行 SQL、Git、网络、锁或产品修改。

首轮其余检查结论继续适用；本补充将首轮 BLOCKED 更新为 PASS。

---

# Verified Chinese display orthography: code review

**Result: PASS.** No Critical or Important correctness issue found in the five uncommitted files.

Reviewed the complete focused `git diff` for `name_evidence.py`, `name_orthographic.py`, `name_batch.py`, `identity.py`, and `test_kifu_name_orthographic.py`, against `docs/superpowers/plans/2026-10-08-kifu-verified-chinese-display-orthography.md` and the second spec review. `git diff --check` passed. I did not repeat the reported 86 passing orthographic tests.

Checks:

- `name_evidence.py:1405-1461` rejects unknown subtypes and requires an exact same-player approved conventional CN row and evidence, consistent revision, complete research payload, and a creation batch digest. The old Chinese-original and Hanja branches retain their field gates.
- `name_orthographic.py:237-280, 292-340, 372-408` binds the new subtype to CN→TW, the qualified approved-name snapshot, a missing TW preimage, finite full-name mapping, and collision exclusions. The signed candidate and member are compared field for field.
- `name_batch.py:278-287, 618-622, 981-987` checks the source row, evidence, applied batch, and journal inside the write transaction, including idempotent reapply. Existing target preimage CAS checks still enforce TW absence.
- `identity.py:121-159, 206-223` uses the evidence creation journal to retain the new method even if mutable name, evidence, and candidate markers are removed. Such a row cannot fall through as conventional; `name_orthographic.py:446-507` checks the exact source rows and creation proof before display or search inclusion.
- Query work is scoped to name rows already returned by the caller; page display limits owner IDs to that page, and exact search constrains the matching names. The new source check adds a fixed set of point lookups per matching verified display row. This is proportionate to the initial four names; no cache is justified here.

**Minor observation, no change requested:** the existing creation-ledger lookup in `identity.py:128-131` uses `target_table` plus `target_row_id`, while the visible table definition indexes journal changes by `batch_id` first. This query predates the change and is reused rather than added. A production query plan is the right evidence if latency later becomes an issue; it is not a correctness gate for this focused diff.

I did not access a database, network, lock, or product file, and did not run the full suite. The separate reported orthographic test result is 86 PASS; this review directly verified source and test paths plus whitespace integrity.

## 测试及上线边界

实施代理先观察新用例按预期失败，修复后实际 `.venv/bin/python -m pytest tests/web_ui/test_kifu_name_orthographic.py -q` 为86 passed；新增非空TW前像重签拒绝例也完成red/green。Root读取完整审核报告并检查 diff --check。旧转写集成12个俄语期待失败源于HEAD已有ru→en政策，未扩大本次修改；不声称全套通过。当前提交只表示代码审查通过，真实首批导入与云端上线仍待执行。
