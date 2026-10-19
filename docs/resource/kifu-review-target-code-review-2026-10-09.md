# REVIEW 目标字形修复独立代码审查

2026-10-09，第 1 轮。按[范围决策](kifu-next20-review-target-decision-2026-10-09.md)及[实施计划](../superpowers/plans/2026-10-09-kifu-review-name-orthography.md)，先审规格、后审代码质量。范围仅为 `name_orthographic.py` 与其聚焦测试的未提交改动；未发现需要修复的实质问题。

**规格：PASS。** 非 NULL 例外仅进入 `verified_chinese_display` 的 CN→TW 分支；JP 分支仍要求 NULL。目标前像必须具备完整且无多余的 `KifuPlayerName` 字段、正整数物理 ID、相同 player/语言、`status=review`、`evidence_id=None`，整行哈希必须等于候选及 member 的已批准前像哈希。其他旧字段随完整行绑定；无需把旧行的文字相同视为豁免，也未扩大到带证据的目标。

**代码质量：PASS。** 已逐段核对以下链路：

- member 的 `preimage_binding_sha256` 签住包括 `target_name_preimage` 在内的整个 binding，完整成员批准及 freeze 条件继续生效。
- `persisted_batch_bindings()` 经 `validate_orthographic()` 调用同一候选校验，读取时不会遗漏新增目标证明；持久 evidence candidate 还须等于已核对的 artifact candidate。
- `apply_bundle()` 锁内复用完整真实行 CAS；`_apply_candidate()` 更新原物理行并保存完整 before/after 和新证据，现有 undo 可恢复原行。
- 合格 conventional CN 来源、来源证据及创建日志核验、已合格目标保护、有限字形规则和碰撞条件保持原有约束。未发现新增例外可绕过上述边界的具体路径。

新增测试覆盖一次真实 SQLite apply→严格读取/搜索→undo，核对原行 ID 和完整旧行日志；另覆盖缺失/不完整前像、status/evidence/owner/lang/ID/hash 错误、绑定后真实行漂移及 JP 拒绝。根代理报告已观察改动前失败、改动后 orthographic **162 passed** 与 importer preimage **14 passed**；本轮核对测试内容和调用链，未重复执行测试或进行数据库操作。

审查文件 SHA-256：

- `katrain/web/kifu/name_orthographic.py`：`d210965d365b766498d520df50294ee5622b827d07324813f6c4f79adff7af91`
- `tests/web_ui/test_kifu_name_orthographic.py`：`c3d2b06053e1e8fdf9ad788057be6587c97a36a1a95b16efbf1fd71ba0c25b3f`

本 PASS 是实现审查结论。七行最终实时前像绑定和两环境 web/importer 单模块回植仍按计划执行；PROD legacy SQL adapter 须保留。本轮只新增此审查记录，未修改实现、提交 Git 或部署。

## PROD web 兼容回植补充审查

2026-10-09，第 2 轮，**PASS**。根代理部署预检发现 PROD web 的旧 ORM 仅列出 9 个名称字段，而真实表、当前 importer 与原生实现使用 13 个字段；直接复用 ORM 字段集会错误拒绝完整目标证明。采用仅在 PROD web 新增 guard 中写明原生 13 字段集合的最小兼容替换，不修改旧 ORM 或 identity，也不改变原生模块/importer。

已检查冻结的 `/tmp/kifu-review-target-root-20261009/PROD/web-patch.diff`、前后模块及 manifest，并执行只读的精确比对：字面集合与当前原生 `KifuPlayerName` 的 13 个字段完全相同；除字段集合表达式外，新增 guard 的 AST 与已审原生 guard 相同；逆转 3 个批准 hunk 后，整个文件逐字节恢复为 PROD 原模块。`_live_row_image()`、`verified_source_live()` 及后续模块正文逐字节保留，既有完整 SQL 读取适配未丢失。未发现新增放宽路径。

- PROD web before SHA-256：`ac08ba320266be89cc1e76f16ad8aadc7bd4d9a13e340547412b13989570e458`
- PROD web approved backport SHA-256：`9216531ea227f66098663c8c0b29e664873beeb071bea4d44c2c2f7f86130c14`
- 原生/importer 模块仍为：`d210965d365b766498d520df50294ee5622b827d07324813f6c4f79adff7af91`

本补充结论仅覆盖冻结回植内容；根代理继续原计划的镜像导入、运行模块哈希及实际七条证明验证。本轮未操作数据库、运行时、实现文件或 Git。
