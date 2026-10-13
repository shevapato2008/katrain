# Legacy exact 查询请求内复用：独立代码审核

日期：2026-10-09。主任务指定基线：`2a2f016f`。范围为本轮 `identity.py`、列表端点 `kifu.py`、`test_kifu_name_orthographic.py` 和延迟说明的改动，以及 `/tmp/kifu-reader-r4-root-20261009` 冻结 r4 内容的回补位置核对。

**结论：PASS；无必须修正项。** 新 exact alias 查询安全复用同一请求内已验证的 orthographic batch context，资格与实时来源检查保持不变。

- 列表调用把已有请求局部字典传给 non-strict `matching_entity_ids(..., exact=True)`；新增可选参数再传入原 `_qualified_name_rows`，未引入新的缓存生命周期。默认 `None` 保留已有调用和详情行为；partial alias、event 查询未新增复用。
- `_qualified_name_rows` 的保护逻辑与冻结 native r4 内容一致：Session 有 `new`、`dirty` 或 `deleted` 时跳过复用；正常路径每次 `populate_existing()`；仅 `applied` 且 `status`、`bundle_sha256`、`reviewed_artifact` 与独立快照一致才命中。失配仍重新完整验证，失败不缓存。每名 `persisted_name_eligible` 和 `verified_source_live` 仍执行。
- 新测试使用真实 native Japanese-source fixture 的 non-strict TW 列表路径，断言返回“加納一夫”，并精确要求 **1 次 batch bindings、3 次 live source 检查**。状态、bundle hash、artifact 在请求内改变的测试现同时覆盖 strict/non-strict；跨请求持有旧 ORM 与 pending change 用例保留。
- `/tmp/kifu-reader-r4-profile-actual-20261009.txt` 的实测记录为 `7.407 s`，batch 588 bindings 两次（`0.801 s`、`0.823 s`）。源码调用顺序支持延迟说明中的归因：第二次来自 legacy exact search；native fallback `display_maps` 不调用生成名称 proof gate。本地通过不等于发布后的延迟测量结果。

回补核对：冻结 **PROD web 无需此次产品代码 hunk**。它已在请求内创建字典，并传入 exact/partial `matching_entity_ids`；exact 再传到 `_normative_player_name_rows`，展示也传到 `display_maps`。**TEST web、TEST importer、PROD importer** 的 native 版本仍缺少这次接线，只需应用 `matching_entity_ids` 可选参数、内部 `_qualified_name_rows` keyword、列表 exact call keyword 这三处最小 hunk。各冻结端点有现存差异（包括报告/preview），不应以仓库整文件覆盖；PROD web legacy adapter 也不应替换为 native 文件。本审核未生成或修改回补归档。

独立验证仅运行一次：

```text
python -m pytest tests/web_ui/test_kifu_name_orthographic.py -q -k 'list_reuses_orthographic_batch or non_strict_list_reuses_orthographic_batch or list_refreshes_orthographic_batch or list_preserves_pending_orthographic_batch'
10 passed, 162 deselected in 0.73s
```

使用本地内存 SQLite fixture；未访问 TEST/PROD 数据库，未运行 Git、构建或部署。未修改业务实现。审核绑定文件 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `katrain/web/kifu/identity.py` | `0d73f2bbee561962eb5f7ed76711a01e10da6407723547e88352ad3375cdc883` |
| `katrain/web/api/v1/endpoints/kifu.py` | `3328da9a22a97501bf7e294293f7a8b7c7a6e894e140b143c74eb209cbcf8790` |
| `tests/web_ui/test_kifu_name_orthographic.py` | `1cb9a9601154a78a73bfc1147e442fe32ca817fa5b622aadd8d9c014961df7d8` |
| `docs/resource/kifu-orthographic-read-latency-2026-10-09.md` | `63f8831a4a4d6cdbb7369a090241f84021cb834ec5540fe9edf4cc33c257310b` |
