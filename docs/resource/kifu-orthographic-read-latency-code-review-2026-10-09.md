# Orthographic 读取索引优化独立代码审核

日期：2026-10-09。最终结论：**PASS**，无未解决的产品代码阻塞项。范围为 `HEAD 2df7e729` 上 `name_orthographic.py` 与 `tests/web_ui/test_kifu_name_orthographic.py` 的实际未提交差异，以及对应 TEST/PROD JP 回植产物；参考 `kifu-orthographic-read-latency-2026-10-09.md`。最终本地模块 SHA-256 为 `b3e5e39870e63d04c9f2a3ce82bee20ce365021766e549e1b8e0b05255147da3`。

## 已解决的审查项

**P2 已解决：缺少 `lang` 的快照行继续拒绝。** 初审索引使用 `row.get("lang")`，可能忽略缺字段行；旧成员扫描会因 `existing["lang"]` 抛出 `KeyError` 而拒绝。最终修改为 `owner_key(row.get("owner"), row["lang"])`，恢复原拒绝语义，没有扩大其他语言类型限制。新增 `missing_language` 回归例检查外层 `validate_bundle()` 返回 `write_ready=False` 和语言错误。

亲自在纯内存中用归档 TEST 包核实：原始 63,934 行快照、20 个成员在最终代码中继续通过；追加一条有效 owner/名称/批准状态、但缺少 `lang` 的行并刷新既有快照与批次内容哈希后，最终代码与旧实现均抛出 `KeyError('lang')`。外层 `validate_bundle()` 捕获该错误并返回不可写报告。没有执行 SQL，也没有改写归档数据。

## 其余代码边界

- owner/language 索引保留完整行列表；来源名称、conventional 状态、批准状态、名称哈希及证据哈希仍须在同一行同时成立，重复行不能拼接来源证明。
- `owner_key()` 要求精确 owner 字段、正整数 ID 或有限 symbolic ref；对于已验证的 CN/TW 成员，索引键保持原 owner 与语言比较语义。目标保护继续拒绝现有 conventional 目标，并对 verified display 与 Hanja retention 拒绝任何现有批准目标。
- 名称索引按语言及原 `_normalize()` 函数建立，每个规范化名称保留全部 owner；外 owner 即使在快照末尾也不会被覆盖。批内输出碰撞与 alias 检查保持原实现。
- 索引仅存在于本次 `validate_orthographic()` 调用；没有进程缓存。整份快照校验及哈希、anchor/rule/member/候选绑定、时间与独立审批、前镜像、持久来源及日志验证未删减。
- 新增的末尾碰撞、拆分来源证明和缺少语言用例覆盖实际风险；已有规模测试增加非空快照并约束规范化次数。实施者报告其余 150 个用例通过；修正后的三个快照用例正在聚焦复跑，本结论不声称最终整模块 151 项已全部通过。本轮未重复运行整个模块。

## 云端回植边界

已确认主代理采用本次差异补丁回植到先前已审核的 JP 模块。最终 TEST web、TEST importer 和 PROD importer 模块 SHA-256 均为上述 `b3e5e398…`；PROD web 为 `ac08ba320266be89cc1e76f16ad8aadc7bd4d9a13e340547412b13989570e458`。四份实际文件的 `validate_orthographic()` AST 与本地一致，内存语法编译通过。

PROD 与本地模块的差异仅为先前已有的 SQL 读取适配；`_live_row_image()` AST 和 SQL 字符串与原 PROD `.orig` 一致。对最终本地和 PROD 实际文件只反转上述一行修复，所得 SHA-256 分别精确等于初审的 `63c5e10e…` 和 `a91e4a5c…`，确认复核之间没有夹带其他代码修改。

本轮亲自完成静态差异、上述内存比较和 `git diff --check`；未修改产品代码、执行 SQL、部署或提交 Git。延迟文档中的约 30% 改善是已有组件测量，本审核未复测 HTTP 延迟。

Root verification: after correcting the outer validation assertion, the three targeted snapshot regressions passed (3 passed, 148 deselected, 0.30 s). The preceding module run passed the other 150 cases; only the test assertion was corrected afterward.
