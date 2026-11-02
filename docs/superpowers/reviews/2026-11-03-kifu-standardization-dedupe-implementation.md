# 棋谱标准化 M3 实施与只读修复包

2026-11-03。已实现审定同局展示去重、精确来源重导入兼容和默认 dry-run 的组合修复工具。**两套线上数据库均未应用修复，也未部署、提交或推送代码。**

## 最终双库只读结果

| 项目 | ucloud-v100 / PROD | home-ubuntu |
| --- | ---: | ---: |
| 全量棋谱 / 公开棋谱 | 176,949 / 176,690 | 176,949 / 176,690 |
| 完整操作候选组 | 1,885 | 1,885 |
| 审定合格两行组 / 拟隐藏行 | 187 / 187 | 187 / 187 |
| 保留原有隐藏行 | 259 | 259 |
| CWI 泛指 dan → 系统未指定 | 5,550 槽 | 5,550 槽 |
| 同局历史职业证据细化 | 21 槽 | 21 槽 |
| 其中审定 Yoda 目标槽 | 2 | 2 |
| 原有 rank snapshots（保留） | 184 | 184 |

187 组包含调查冻结的 186 组和显式审定的 `25055 → 140858`；目标黑白身份为 `[57, 1]`。按精确来源组合计数为星阵↔星阵 98 组、CWI↔星阵 86 组、CWI↔CWI 3 组。

1,702 个完整操作候选组仍含未获自动合并许可的成员，其中 4 组同时含合格两行子组，因此不能把组数简单相减。10 行未满足完整操作解析守卫，35 行属于短谱或含分支的保守排除；它们和其余未证明成员均保留。去重不删除棋谱、不改原 SGF、不转移分析、赛事、段位或历史引用。

两套环境的合格 **SGF SHA 对集合一致**，但有 **9 对实际 album ID 不同**；已分别查询、冻结每套数据库的精确 ID、来源行和前像，未复用另一套环境的 ID。完整差异见下面的精简证据 JSON。

## 守卫与来源契约

- `catalog_standardization.py` 使用棋盘尺寸、展开的 AB/AW/AE、PL、有色落子与 pass 构建完整操作指纹；完整单局解析、精确日期、同色批准身份、原始 SGF 与标量元数据一致、无显式贴目/让子/结果/规则冲突后才合格。人物只用已有 FK、唯一 canonical、已登记 alias 和有引用来源的 verified 名称；Yoda 是固定原始 SHA/来源/官方历史证据的单个例外。
- Manifest 绑定两端原 SGF、元数据、来源定义、原来源行 ID、指针及精确前像。规范主记录优先原始星阵来源，再稳定 ID。复用 `KifuDedupBatch/Change`，仅写 duplicate 指针及新增 `reviewed_same_game` 聚合来源，原来源行 ID 保持不变。
- 原生发布重试仍返回原 receipt 和原 source-specific album ID。聚合到主记录的来源不能冒充另一个 SGF 的精确拥有者；隐藏原始记录只有经完整 journal 验证后才能继续发布、重试和回放。新来源同样在原记录保留精确来源，并在主记录聚合审定来源。
- HTTP 回放分别核对原始详情的存储字节 SHA、manifest 的完整规范化 SGF、有限 journal 证明以及实际公开主卡片。包含“存储 SGF 多一个换行、后续规范化重导入”的真实原生回归用例。未修改分析端点或分析库的精确 SGF 安全规则。
- 保留名称证据范围只投影已验证 journal 的原指针前像；任意隐藏、未记账指针、来源或原始元数据漂移不会获得资格。
- 组合工具先写 rank、再写 dedup，撤销顺序相反；使用现有原生写入锁顺序、事务/savepoint、前像复核、不可变审计证据与现有 `maintain_after_write`。同一包重复应用幂等；后续独立修改使撤销整批拒绝。

首次全量 live dry-run 发现未带引用的 verified 展示名称被误当身份索引，得到 195 组。该包未应用，已排除；聚焦回归 RED→GREEN 后恢复到上述 187 组，和冻结证据一致。最终证据仅指向纠正后的 manifest。

## 审计产物

完整私有产物在仓库忽略目录 `output/kifu-standardization/2026-11-03/`：

- `prod.manifest.json`、`home.manifest.json`：完整精确前像、源 SGF、审定证据、拟写入及撤销输入；各有 `.sha256` 和压缩副本。
- `summary.json`：计数、环境实际 ID 差异、代码 SHA、只读状态和已部署兼容性检查。
- `candidate-code/`：生成包时的三个纯策略模块副本；`operation-cache.json.gz` 仅含 SHA 绑定的操作计算结果，不含全库 SGF dump。
- `prepare_live.py`、`build_operation_cache.py` 和每环境日志：只读生成过程。

可进入版本管理的精简证据：[`evidence/2026-11-03-kifu-standardization-manifests.json`](evidence/2026-11-03-kifu-standardization-manifests.json)。完整私有棋谱数据不加入版本管理。

Manifest 的 canonical JSON SHA-256：

- PROD：`8af6346f74815843ff51294df90e53273eb39dfd433dfaec1f31354f54f984f6`
- HOME：`db5d53d30689b6ae4bdc17b22d2b6028a025f51ece0a3f260f29b5000f59133f`

两个查询都在 `REPEATABLE READ, READ ONLY` 事务中生成并确认 `transaction_read_only=on`，读取全库实际 SGF、来源、身份和快照。临时内存模块只用于只读准备，未替换线上文件。操作计算缓存由当前代码对完整既有快照计算，复用时先核对每份 live SGF SHA，未命中重新解析；最终包另由本地**未安装缓存补丁的纯代码**重新验证。实际 apply 仍在锁内重新解析、核对当前数据库前像，缓存不参与 apply。

## 工具入口与发布状态

默认只读：

```bash
.venv/bin/python scripts/standardize_kifu_catalog.py --database-url '<目标DSN>' --output '<新manifest.json>'
```

写入入口要求冻结 manifest、精确 SHA、已验证的持久 beforeimage 副本和匹配本包的部署兼容性前置检查。两环境实际部署版本均为 `7f2ff0c65381250e41a9dc959d8cac9201c3a86b`；原生原记录重试、HTTP 审定去重回放和 v2 段位读模型三个检查均为 false，状态为 **incompatible**。因此当前交付止于代码与审定修复包，生产 APPLY 明确待兼容运行时发布和新鲜前像复核之后进行；不把候选代码测试通过当作线上兼容。

## 验证

聚焦测试覆盖原生实际 publication → dedup → exact retry → 新来源重导入、CWI/星阵旧导入与 backfill、实际详情/列表 HTTP 回放、原 SGF 字节与规范化内容差别、未审指针拒绝、SGF 元数据/日期/身份与原来源行 ID 漂移、canonical 选择、组合事务回滚、幂等及受保护撤销。PostgreSQL 使用本机临时 schema，结束后删除该 schema；未使用生产写入连接。

最终相关 Python 套件 **227 passed, 1 skipped（22.36 秒）**，其中 M3 PostgreSQL apply/undo 用例已启用并通过，另一个可选 PostgreSQL 用例未设置其专属环境变量而跳过。测试文件为 `tests/web_ui/test_kifu_catalog_standardization.py`，并联跑 source rank normalization/repair、原生 incremental catalog、旧 import history、catalog schema 和 cron ingest。两套真实 UI 的隔离运行时验收由 Controller 记录在 `2026-11-03-kifu-standardization-runtime.md`。
