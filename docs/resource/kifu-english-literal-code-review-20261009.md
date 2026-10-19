# English-form SGF literal 扩展独立代码审核（2026-10-09）

**结论：PASS。** 按 `requesting-code-review` 先审核规范符合性，再审核代码质量。未发现必须修正的问题；本次最小代码扩展可进入后续真实 capture 与独立数据包审核。

审核基线为委派任务指定的 `7499f4ac`，对象为以下四个文件的未提交差异。规范依据 `docs/resource/kifu-event-latin-literal-astra-decision-20261009.md`，实施计划为 `docs/superpowers/plans/2026-10-09-kifu-english-sgf-literal.md`。

## 规范审核

- `raw_event_translation.py:148` 新增专用英文 validator：允许的 ASCII 字符、至少一个字母、唯一 core、最多一个 edition，以及 parts 逐字拼回 raw 均有检查。四种实际 parser 形态（core-only、空格前缀、连写前缀、逗号后缀）均通过；edition 限 1–999 并校验正确的 st/nd/rd/th，包括 11/12/13 的例外。未增加 year/round/game parser 规则。
- `raw_event_translation.py:243` 和 `:270` 按 SGF profile 进入英文序数和语言分支；`sgf_english` 必须为 `original_language=en`，两个中文 profile 仍要求 `zh-Hans`，汉字和原中文序数检查保留。未知 profile、跨 profile 和错误语言不能借新分支获得准入。
- `raw_event_translation.py:289`、`:380` 保留 parts hash、owner marker、scope hash 和独立 owner review 的绑定。现有 candidate 路径仍以 `check_parser=True` 比较实际保存 parts，严格 reader 仍重新检查当前 owner、候选与 research。`original_name` 仍必须等于唯一 core。
- `scripts/kifu_raw_event_title_owners.py:30` 使用共同 profile 集合和显式 validator 分派；英文 manifest 必须明确标记 `sgf_english`，单批 1–150 owner，冻结 raw 集合、完整 member scope、现有 owner/name preimage、registry、inventory/catalog 和 plan hash 条件保留。英文 raw 在取得实际保存 parts 后校验，未伪造整段 core 代替 parser parts。
- owner apply 仍只写 review status/metadata 并复用现有 journal/undo；name apply 复用既有路径。没有新增 schema、pipeline、身份归并或 SGF/FK/hidden/raw ID/parser data 写入。Hoensha 的五语显示保持棋局标签语义。

## 质量与聚焦验证

改动集中在两个既有产品文件，复用了已存在的 owner/name 审核机制；没有引入本次需求之外的抽象。新增测试覆盖四种实际 parts、正确与错误序数、语言/profile 互冒用、parts/hash 篡改、scope 漂移、owner apply/undo，以及五语 name apply/严格读取。原中文和既有 title 测试一起执行。

独立执行：

```text
.venv/bin/python -m pytest -q tests/web_ui/test_kifu_raw_event_title_translation.py tests/web_ui/test_kifu_raw_event_title_owners.py
198 passed in 11.09s
```

四个目标文件的 `git diff --check` 通过。无 Critical/Important 发现；没有额外要求扩大测试或重构。

## 审核边界

本报告批准代码扩展，不代替实际数据包签名。181 个标题、905 个语言单元及 2,201 盘是保存快照数据，不表示本轮实时准入或完成覆盖。后续每个批次仍须读取实际每份 SGF，保存全部实际 GN，核对第一 GN 精确等于 raw 且 EV 为空；现有 validator 只验证已捕获 refs 与 scope/hash 的一致性。必须继续 fresh TEST/PROD scope、正式显示碰撞检查和独立签名，32 个碰撞 variants 继续 hold。

本审核只做本地文件读取、只读 diff、两份本地测试和本报告写入，没有执行真实数据库操作、capture、Git mutation 或部署。

## 被审核文件 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| `katrain/web/kifu/raw_event_translation.py` | `5806eddd74484a1ecae40c81f8e67a13120b28d3afb30e2b793b27e87d423507` |
| `scripts/kifu_raw_event_title_owners.py` | `7c152e11172052e0de1c1adadf586b3930fed7946df09aa5eadef15171bd23ca` |
| `tests/web_ui/test_kifu_raw_event_title_translation.py` | `5a4418a2bfc91be97cd658318d8b06ae2ae23143519d4ccb21883df48bc4a668` |
| `tests/web_ui/test_kifu_raw_event_title_owners.py` | `5dfe80fbf295c4e1638fdcea810c52d5650fc66a2b5f9761e0cc32c8489ad0b0` |
