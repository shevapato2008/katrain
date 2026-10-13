# r4 reader backport 独立审核（2026-10-09）

**结论：PASS；无必须修正项。允许主任务以本报告绑定的冻结内容构建 TEST、PROD r4 镜像，随后执行已有发布验证。**

审核目录：`/tmp/kifu-reader-r4-root-20261009`。源提交：`2a2f016f5c3ca1deef2d0f041c4622730f61edfe`。本轮仅核对 backport；请求内复用和英文 literal 的源代码审核分别见 [复用审核](kifu-request-reuse-code-review-20261009.md)、[英文 literal 审核](kifu-english-literal-code-review-20261009.md)。未重新扩展功能或重复全量回归。

- **PROD web 兼容适配通过。** 保留原有 raw SQL 查询；每次调用重新读取当前批次行，按批次 id 比较 `status`、`bundle_sha256`、`reviewed_artifact`。仅 `applied` 且三项一致时复用成功上下文；不一致时先移除旧值并重验，失败不缓存，保存快照使用 `deepcopy`。`new`、`dirty`、`deleted` 任一非空时绕过缓存读写。
- **实时名称校验保留。** 原名称和 evidence 查询、creation ledger 判别、逐名 `persisted_name_eligible()`、当前 source name/evidence/batch/creation journal 校验和 positive JA/KO 路径均保留。另读取本地 r3 捕获的 PROD web `name_orthographic.py`，SHA 与保护表的 `9216531e…` 一致；其 `persisted_batch_bindings()` 仅依赖上述三项批次内容，`persisted_name_eligible()` 仍逐名调用 `verified_source_live()`。复用没有扩展到这些实时检查。
- **路由传递通过。** PROD web 列表为每次请求建立一个字典，传入 exact/partial `matching_entity_ids()` 和 `display_maps()`；函数新增参数默认 `None`。TEST web 与两个 importer 的 native 搜索、显示传参均为已批准 hunk。PROD importer 的唯一插入位于实际 dispatcher 提前返回之后、首个本地查询之前；缺少较新 locale 赋值不影响字典生命周期和两个消费者。
- **旧业务路径保留。** 对 PROD web 两个模块独立移除明确的 adapter 新增节点后，整个模块 AST 与捕获 before 一致；原 SQL 字符串和其他函数完整保留，反向行差异逐 byte 恢复 before。没有以现代模块整文件覆盖旧 reader，也没有改动 ORM/schema、`name_evidence.py` 或 `name_orthographic.py`。
- **其余补丁与已审源一致。** 独立读取 Git 中 `e334482a → 7499f4ac` 和 `7499f4ac → 2a2f016f` 的 `-U0` 补丁，核验 10 个非 adapter 模块的每个 old/new hunk、位置和 SHA，正向重建 after，逆向恢复 before。两个 importer 新增的 owner 脚本与已审 tracked 文件逐 byte 相同；两个 web 中该文件继续缺席。

本地聚焦验证：运行冻结 `verify-prod-web-adapter.py` 一次，通过成功复用、artifact/status 失效和 pending Session 绕过，得到 **5 次 fresh batch reads、4 次 bindings、5 次逐名检查**。另完成 12 个冻结模块的内存语法编译、capture/manifest/before/after/差异哈希核对，以及两个归档内每个文件与冻结目录的逐 byte 核对。验证导入产生的本地 `__pycache__` 不在归档和 Docker COPY 清单中。

`build-r4.py` 的 r3 image id、原文件和保护模块哈希检查完整；Dockerfile 仅 COPY manifest 指定的三个模块及 importer owner 脚本，构建后再次核验。`deploy-r4.py` 绑定原容器/id、检查实际环境变量与 Compose/image 合并结果相同，使用 `up -d --no-deps --no-build katrain-web`，并核验其他运行容器 id 未变。审核限于这些发布边界原则，未执行构建、部署、真实数据库访问或 Git mutation；真实镜像检查、健康状态及延迟由主任务在后续步骤确认。

冻结文件的 SHA-256：

| 环境 / 类型 | 文件 | SHA-256 |
| --- | --- | --- |
| TEST web | `katrain/web/kifu/identity.py` | `36d817a93ac2fb3a53395963730e2ed07a96447b5bf63e7f4f659e0456d2516b` |
| TEST web | `katrain/web/api/v1/endpoints/kifu.py` | `743d215d919bfe9fc52cad40ba40954ae468246c6dccc1e1ac742c148e1f9fc3` |
| TEST web | `katrain/web/kifu/raw_event_translation.py` | `5806eddd74484a1ecae40c81f8e67a13120b28d3afb30e2b793b27e87d423507` |
| TEST importer | `katrain/web/kifu/identity.py` | `4095e932bacd5cf7ffb932131a23cc585dd66d48a2b8e84900940b372e8b02b8` |
| TEST importer | `katrain/web/api/v1/endpoints/kifu.py` | `6079a64d0d7a955c9fc0cde0e964601b70119dcc10186a2bb1ccd175e9d1bdd7` |
| TEST importer | `katrain/web/kifu/raw_event_translation.py` | `d97e8e88a4e484b684106e0b06296b372066645961b79647425154b5c5102499` |
| PROD web | `katrain/web/kifu/identity.py` | `0c4503e93f3ee62488058ba1e46f995dc6566063089a9ec6240789d27be0ecab` |
| PROD web | `katrain/web/api/v1/endpoints/kifu.py` | `50b4cb005946fd974de852fb74c345dd6066796a2f46998f4f62c3db4d7d3fe7` |
| PROD web | `katrain/web/kifu/raw_event_translation.py` | `5806eddd74484a1ecae40c81f8e67a13120b28d3afb30e2b793b27e87d423507` |
| PROD importer | `katrain/web/kifu/identity.py` | `4095e932bacd5cf7ffb932131a23cc585dd66d48a2b8e84900940b372e8b02b8` |
| PROD importer | `katrain/web/api/v1/endpoints/kifu.py` | `82e72c189c425db0045105ca9e2a0d45f6bdffe17605b380b6af727efe31a048` |
| PROD importer | `katrain/web/kifu/raw_event_translation.py` | `d97e8e88a4e484b684106e0b06296b372066645961b79647425154b5c5102499` |
| TEST、PROD importer | `scripts/kifu_raw_event_title_owners.py` | `7c152e11172052e0de1c1adadf586b3930fed7946df09aa5eadef15171bd23ca` |

冻结元数据、保护清单与分发包的 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `TEST/manifest.json` | `9e165b7b5f4d7d1478feded6f9c5132b45ae6c9629359cb26538740673c3473a` |
| `PROD/manifest.json` | `1824cdb16f9982ad37593ceca98289b90b39245ea241c7fe870c21fcabcd7520` |
| `TEST/capture-metadata.json` | `e797fc1b35122f548fd87b11afb4efddeec7673890213a23c011c2aee73fb0f1` |
| `PROD/capture-metadata.json` | `6ace90a108272e92559cc6d4c18bb50a3310c79db7887f92e99bd10ec407d8d3` |
| `TEST/r3-protected-hashes.json` | `7c890fa45f301723346769ad82ab9513cf79fa6ab577b76813c6ee2a8cf69846` |
| `PROD/r3-protected-hashes.json` | `5134f081dd199834b35e6d37885d903b7d4610f4bf3d054b1ffad940c88d5cd9` |
| `TEST-r4-overlay.tar.gz` | `0a215ff2313fc6835db4b0e0ebc5a5be2efd1b90456674a8624de91f1abfc706` |
| `PROD-r4-overlay.tar.gz` | `0b572a69e2ccbd31e6b80409c732024ce8ee403600f3bbca2086adf414a5ace9` |
| `build-r4.py` | `65c3e9817ca6d6d5547ea79fe6eb91cc47aaaf6501a95c3a6576844f0074f530` |
| `deploy-r4.py` | `af988123382a07860e9ddb030e8901a57c953da92d3f83dfe872caf60a2db03c` |
| `verify-prod-web-adapter.py` | `1a6d3bf54dd830c2d1f2c4ade77019707538cf5dadd10ff60d7a9a43a5a350cc` |
