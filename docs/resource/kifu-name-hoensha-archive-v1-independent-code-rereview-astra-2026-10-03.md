# Hoensha archive-description-v1 独立代码复审（2026-10-03）

**PASS：首轮 1 项 P1、1 项 P2 均已修复，本轮范围内无剩余 P0/P1/P2。** 本结论取代[首轮报告](kifu-name-hoensha-archive-v1-independent-code-review-astra-2026-10-03.md)对实现的 HOLD；首轮缺陷和复现记录保留不改。

复审任务：`/root/hoensha_archive_code_review_astra`。公开运行时标识为 GPT-6；名称中的 astra 不作为具体子型号认证。本轮仅复查两项修复及必要的旧入口兼容边界，未修改实现、业务数据库、克隆库或提交。测试使用 pytest 的临时数据库。

| 首轮问题 | 复审结果与依据 |
|---|---|
| P1：旧格式或省略类别的 manifest 将 archive 说明变成全局 conventional 名称 | 已关闭。`name_batch.py:417` 从数据库真实 owner 读取 `category` / `parser_version`，只准专用 decision 和精确 v1 版本。无 manifest 的 `bundle_format=1` 以及省略 category/parser 的 `bundle_format=2` 均不能绕过。两个参数化复现均验证 dry-run/apply 拒绝，名称/证据前像和行数保持不变。 |
| P1 的运行时旁路 | 已关闭。`identity.py:285` 在进入普通全局 raw 分支前排除 archive owner 上的不相容 decision。将已存 name/evidence 同时改成 conventional 的复现中，范围内行和未审同文行均显示待核实；译文搜索、slot approval 和 coverage 同步拒绝。 |
| P2：name/evidence 同为未知版本仍借用 v1 candidate | 已关闭。`identity.py:300` 强制 candidate、name、evidence 三方 decision 等于 `archive_description`，三方 version 等于 `archive-description-v1`。将两列同时改为 `archive-description-v999` 后，显示待核实、搜索无结果、事件 slot approval 为 `None`、coverage 不计批准；恢复原版本后有限范围的搜索和覆盖恢复。 |

四个新增复现实例为 `test_archive_owner_rejects_conventional_replacement_without_category_manifest[1/2]` 与 `test_archive_runtime_rejects_incompatible_persisted_decision_or_version[conventional/unknown_version]`。本轮独立执行其修复后的结果；没有回退实现重演 RED 阶段，也不将实现者的 RED 记录当作本轮独立执行结果。

修复仅约束新 archive 类别/规则。`name_candidates.py` 及其测试文件与首轮 SHA-256 相同；冻结的 v1 hash、v2 精确模板和十一语门槛继续通过。普通旧格式 apply、幂等和 SGF 保留、conventional evidence/collision、旧 v2 raw owner 的 apply/undo 也通过。正常 archive 十一语的有限显示/搜索/coverage、来源证据损坏后拒绝，以及 event/event alias/event_id 零新增和 undo 仍由本轮执行的已有集成测试验证。

独立执行结果：

```text
.venv/bin/python -m pytest tests/web_ui/test_kifu_name_candidates.py tests/web_ui/test_kifu_name_batch.py -q -k 'archive or classification'
59 passed, 128 deselected in 1.72s

.venv/bin/python -m pytest \
  tests/web_ui/test_kifu_name_batch.py::test_apply_is_atomic_audited_idempotent_and_preserves_sgf \
  tests/web_ui/test_kifu_name_batch.py::test_conventional_name_evidence_matches_verified_row_and_collision_is_blocked \
  tests/web_ui/test_kifu_name_batch.py::test_v2_new_raw_owner_fixture_dry_run_apply_and_undo -q
3 passed in 0.41s

git diff --check
通过，无输出
```

本轮检查到的基线为 `HEAD=3e4a331b7db7d2cc73f7bfa739b6849f9cfff2ea`，实现仍为未提交改动。已审文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `katrain/web/kifu/name_candidates.py` | `5b998dd4ac7d4b7feff8a5692b96e677c4a69885cdc818176f7a6bbb377aaab9` |
| `katrain/web/kifu/name_batch.py` | `1527bbfda18533d5c1fe90be86cd4a970d0656e8121932296569a6996eb8b3dd` |
| `katrain/web/kifu/identity.py` | `78c2a6dba601271aa6c92f39cfe74f83913f28dfa85713576b4996b837065691` |
| `tests/web_ui/test_kifu_name_candidates.py` | `7f9d65c4b5cbee74068254acc2c6196ee3d6748d54fdf6bb1c7c14e994f5e36d` |
| `tests/web_ui/test_kifu_name_batch.py` | `5457c5d7f5c64990ed5f29163bafa8a6082a7448d15159e63b84d1e0baf1e0d7` |

PASS 的范围是此版本实现及上述回归边界；实际候选包的来源语义、目标库存/前像绑定、独立最终签署和真实导入结果仍由该包的既有审批流程确认。
