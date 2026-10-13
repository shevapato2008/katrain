# Hoensha archive-description-v1 独立代码审核（2026-10-03）

结论：**HOLD，发现 1 项 P1、1 项 P2；修复并复审后才能批准第二阶段导入。** 无 P0。

审核任务：`/root/hoensha_archive_code_review_astra`。运行时公开标识为 GPT-6；任务名及文件名中的 astra 不作为具体子型号认证。依据 [三原文协议决策的第二阶段](kifu-name-generic-three-event-protocol-decision-astra-2026-10-03.md)，审核当前未提交的 `name_candidates.py`、`name_batch.py`、`identity.py` 和两个已有测试文件。本次没有修改实现、业务数据库、克隆库或提交；额外复现仅使用独立内存 SQLite，测试使用 pytest 的临时数据库。

## P1：省略 archive manifest 后，旧格式导入可把有限档案说明升级为全局名称

位置：`name_candidates.py:511–514`、`name_batch.py:400–423`、`identity.py:306–307`。

新加入的“该 owner 只能使用 archive_description”约束仅检查候选包 manifest 中的 `category`。`bundle_format=1` 没有 manifest；既有 owner 的导入检查 `_check_raw_owner` 只核对 ID、raw 拼写和真实出现行，未按数据库中的 `archive_source_description` / `archive-description-v1` 收紧 decision。一个拥有独立署名、正确前像和常规 research 形状的 `conventional` 候选因而能覆盖该 owner 的单语名称。运行时又依据名称的 decision 分流，把它作为 `composition=None` 返回，从而进入 `result[raw]` 全局映射。

这违反第二阶段“所有该 owner 的候选只能使用 archive_description”，并使未经档案来源审核的同文新行获得档案译文。问题需要一个经旧入口提交的候选包，不需要直接改数据库记录来绕过导入器。

最小复现使用现有测试 helper：

1. 按 `test_archive_description_finite_scope_display_search_coverage_evidence_and_undo` 建立两条 CWI Hoensha 行 12、13，正常导入十一语 archive bundle。
2. 增加同为 `event='Hoensha game'`、`event_id=NULL` 的行 14，来源为 `unreviewed.sgf`。俄语严格显示此时为 `Название турнира не проверено`。
3. 为已创建的 raw owner 构造 `bundle_format=1 / inventory_format=4` 包，只含俄语 `decision_kind='conventional'`、`generation_rule_version='none'`、文字 `Историческая партия из архива Хоэнся`。可从 `player_bundle` 的 conventional research fixture 改为相同 raw owner/raw 拼写；重新计算 research/member hash，真实读取俄语 `name_preimage_sha256` 并重新绑定。所有常规署名仍为测试 fixture 署名。
4. 当前 `dry_run_bundle(...)["ready"]` 返回 `True`，`apply_bundle` 返回 `applied`。
5. 行 14 的严格显示变成 `Историческая партия из архива Хоэнся`；raw owner 的类别仍是 `archive_source_description`。

必要修复边界：在现有 importer 的真实 raw owner 检查中强制 archive 类别/规则仅允许专用 decision 和专用版本，覆盖无 manifest 的旧格式以及省略类别字段的既有 owner manifest。运行时同样不得把 archive owner 上的其他 decision 放回全局 raw 映射。约束只针对新 archive 类别/版本，不改变旧 v1/v2 owner 的原有合法性。

最低回归断言：上述替换包的 dry-run/apply 均拒绝，原名称/证据无写入变化；省略既有 owner manifest 的 category/parser 字段也不能绕过；人为存在不相容 decision 的 archive owner 时，严格显示、搜索和 coverage 均不能扩大至行 14。

## P2：持久化版本与签署候选版本不同，仍显示并计为批准

位置：`identity.py:291–300`，以及 `_approved_names` 中只比较 name/evidence 两列相等的版本条件。

运行时专用 validator 核对 JSON 中 candidate 的 `generation_rule_version`，却没有将它与持久化 name/evidence 的 `generation_rule_version` 相连。name 和 evidence 两列即使同时成为未知规则版本，仍能借用保留的 v1 candidate/scope 通过批准。这是未知版本和损坏证据应拒绝的实际缺口。

最小复现：在上述正常 archive 导入后，仅对英语的 `KifuRawEventName.generation_rule_version` 与其 `KifuNameResearchEvidence.generation_rule_version` 同时赋值 `archive-description-v999`；保留 candidate、scope 和其 hash 为原始 v1。当前结果：

```text
baseline_display: Hoensha archive game
damaged_version_display: Hoensha archive game
damaged_version_approval: ('archive_description', 1)
```

必要修复边界：archive 的运行时资格检查应要求签署候选、name 与 evidence 的 decision/version 一致，并为本协议保留精确 `archive-description-v1`。不需要重读来源文件或联网。

最低回归断言：这两列同时改为未知版本后，显示为待核实、译文搜索无结果、`strict_slot_approvals` 返回 `None`、coverage 不计 `archive_description`；恢复原版本后三入口恢复原结果。

## 其余已核对项目与验证范围

- 十一语固定完整字符串符合协议；默认 `parse_event('Hoensha game')` 保持 `unclassified_pending`。专用候选分支核对精确 raw/category/parser version，拒绝普通 owner、大小写变体和错误规则版本。
- 档案依据绑定 inventory、完整出现行及其 hash、同一 occurrence ID 集合、CWI 来源路径、固定 registry 中的来源 ID/URL host、抓取时间/正文 hash 和独立分类审核。离线校验读取留存正文，运行时不读取文件或联网。
- 新 owner 导入白名单仅为精确 archive 三元组增加 `parser_version`；同拼写既有 owner 不会被新建重复或静默改类。专用 archive 包要求无 album links、无 player/event owner，十一语均批准。
- 专用路径保留 candidate 和完整 archive scope。正常有限显示、搜索、coverage 共用资格检查；同文新增行、改 raw、非空 event_id、selected event 映射以及撤销/单点损坏的档案依据均被现有聚焦测试覆盖。以上两项发现指出的是这些测试尚未覆盖的旁路。
- `archive_description` 未加入 player/event 共用的 `_DECISIONS`；`name_evidence.py` 的一般研究规则未修改；v1/v2 模板与 fallback 的既有含义未改。此次 diff 没有新增 SGF 或 event FK 写入，已有集成测试验证零 event/event alias/album event_id 变更以及 undo 删除 archive 名称和证据。

实际执行：

```text
.venv/bin/python -m pytest tests/web_ui/test_kifu_name_candidates.py tests/web_ui/test_kifu_name_batch.py -q -k 'archive_description or classification_v1_template_hashes_remain_frozen'
27 passed, 156 deselected in 0.77s
```

另执行一次纯内存 SQLite 复现，得到以上两项缺陷输出；未把复现脚本加入仓库。父任务此前报告的 260 个相关测试通过属于父任务证据，本次没有重复执行或将其冒充独立结果。通过的现有测试不足以覆盖这两项批准边界。

审核基线：`HEAD=5b887f155dde7314503fc03ed3f4e6b1998ac32e`，以下为本轮已审文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `katrain/web/kifu/name_candidates.py` | `5b998dd4ac7d4b7feff8a5692b96e677c4a69885cdc818176f7a6bbb377aaab9` |
| `katrain/web/kifu/name_batch.py` | `02ab3fc15bc3b5d0089f3059833b348652844bbc9d9be917ec7db6648e0a69aa` |
| `katrain/web/kifu/identity.py` | `98c89b953258c19352398ef33399e3dc64c415358ea06e2522035345e025f823` |
| `tests/web_ui/test_kifu_name_candidates.py` | `7f9d65c4b5cbee74068254acc2c6196ee3d6748d54fdf6bb1c7c14e994f5e36d` |
| `tests/web_ui/test_kifu_name_batch.py` | `b1c47cbc2474a534108d4c31a3729123200325848f4a5b6322b3fbea5f181db7` |

此报告不批准实际候选包、来源语义署名或数据库导入；修复后应只围绕以上两个问题及受影响的 v1/v2 兼容入口复审。
