# JP 原名展示独立代码审核

日期：2026-10-09。结论：**PASS**。实际差异中未发现需要修复的实质性正确性、导入或持久读取回归。

审核范围为当前未提交的五个文件：`katrain/web/kifu/name_evidence.py`、`name_orthographic.py`、`identity.py`、`name_batch.py`，以及 `tests/web_ui/test_kifu_name_orthographic.py`。对照 `docs/superpowers/plans/2026-10-09-kifu-japanese-original-display.md`，并沿现有快照、写锁、读取资格和覆盖统计调用链核对行为。

- 来源类型使用明确的 `jp/ja/Kanji` 描述，要求同 owner 的 conventional 名称及证据、相同 revision、完整 candidate/research 绑定和批准快照。原有 `cn/zh-Hans/Hans` 条件保持等价。统一汉字检查在输出和规范化之前完成。
- JP→CN 规则精确限定所有字段，直接保留原名码点；JP→TW 要求独立的有限逐字映射。member、anchor 和 rule 的来源类型及方向必须一致，生成 CN 不满足 conventional 来源条件，不能作为旧 CN→TW 分支的来源。
- 两个目标均要求 NULL 名称前镜像。现有 `_inspect` 在锁定事务中检查所有状态的实际目标行、当前批准快照、alias 快照及碰撞；新增分支没有引入绕过这些检查的写入路径。既有规范名、棋局 FK、SGF 和段位写入范围未扩大。
- `verified_source_live` 对 JP 复用精确名称/证据全镜像、已应用来源批次、来源 candidate/research 以及名称和证据日志检查；证据日志须为 NULL 前镜像的唯一创建记录。导入、重复应用和持久读取均经过相应检查。
- `identity.py` 仅扩大创建日志中识别的来源类型，查询条件和搜索集合语义未变。即使目标名称及证据被改成 conventional 并移除可变生成标记，创建日志仍会触发完整证明检查，阻止其重新取得显示及 conventional 覆盖计数资格。
- 新增测试覆盖两种目标的导入、读取、generated 计数、来源漂移、损坏日志、目标 REVIEW 及标记移除，并保留原 CN 分支测试。CN 原名与合格 JP 来源相同时仍可通过 JP 搜索命中棋局，与损坏 CN 不再显示或计数的要求一致。

本轮亲自完成实际差异和调用链静态检查，五个文件的 `git diff --check` 返回 0。实施者报告聚焦模块 **148 passed** 和 `py_compile` 通过；按本次比例约束未重复运行该模块或扩展测试。未执行 SQL、修改产品代码或提交 Git。此结论覆盖所审代码，云端发布和实际数据批次仍须按计划完成各自验收。

## 云端最小回植复核

同日结论：**PASS**，无修复项。本次仅复核 `/tmp/kifu-jp-display-cloud-20261009/{TEST,PROD}` 的实际补丁边界，未重复上述产品审核。

- TEST 四个文件为既有已审核部署上增加本次 JP 分支；`name_batch.py` 仅将错误消息改为通用来源措辞。
- PROD 三个文件保留原有 SQL 读取适配。`identity.py` 的四处来源判定同时识别 CN 和 JP，包含创建日志的原始类型识别以及当前 candidate/anchor 识别，继续接入同一持久证明检查。`name_orthographic.py` 保留 `_live_row_image` 和日志查询，在来源检查入口接纳 JP；两种目标的规则、NULL 前镜像和来源绑定与产品实现一致。
- 以 `docs/resource/kifu-verified-cn-display-deployment-2026-10-08.json.gz` 中归档的部署后代码为基线，独立重建差异：TEST 4/4、PROD 3/3 的 before/after SHA-256 均与本次 manifest 一致，重建结果与各自 `review.diff` 完全一致。七个实际文件的内存语法编译通过，前后 SQL 字符串逐项一致。

本复核未运行 SQL、执行部署、修改产品或临时补丁代码，也未提交 Git；结论为具体回植代码可继续发布验收，不代表云端已经部署或实际数据已导入。
