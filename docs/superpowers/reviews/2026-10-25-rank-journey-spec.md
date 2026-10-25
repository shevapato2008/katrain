# 棋手等级冻结与小时回退：用户旅程规范审核

**Verdict: Spec Approved**

审核对象为最终 `01aa39cd0b16ef86bf4d13826eead1f43222e65a`：包含 API/验证 `d07aa9889`、有限纠正 CLI `79e752d75`、别名接口补丁 `730f0a7dc` 及 producer/native slice `01aa39cd0`。已阅读 `AGENTS.md`、`requesting-code-review`、批准计划 Chunk 2/3 与 R1/R2/R3 修正、当前运行手册，并检查实际实现。本报告是部署前的独立规范审核；不重复已批准 foundation，也不代替后续独立代码质量或线上实际效果审核。

没有本范围内的 must-fix。

## 实际实现与规格对应

- **源值、身份与冻结**：`ranks.py` 保留明确源段位优先，包括 `9d` 的 amateur 语义；不以人物职业证据改成 `9p`。缺失时只接受已绑定 canonical owner 的合格库内事实，不能证明则固定 unknown。原 SGF、raw ranks、source metadata/fingerprint 不改写。完整事实在 manifest 中按内容 SHA 去重；快照绑定准确来源 ID、SGF SHA、slot、canonical、policy 和固定时间。source observation 与该盘显示选择分开保存，不会因 fallback 路径漏掉明确新谱观察。
- **准备顺序与重试**：`orchestration.prepare_staged_games` 在付费名称调用前冻结两侧结果，包含 unknown；`Stage` 使用独立、完整校验且不覆盖的文件保存决定。相同请求的重试先读冻结文件，已冻结成员不重新读取今日 current；后续晋段不漂移原包。rank 路径没有外部 profile 请求、爬虫或新模型入口，没有放宽来源窗口、429/7004 策略、历史滚动或原有发布协作预算。
- **原生事务与可移植性**：`catalog._apply_manifest_ranks` 在既有 publication guard/write transaction 内校验当地 album side FK/canonical、精确 SGF 与规范事实，锁人物行，提交 history/current 与两侧 snapshot；包内无当地 player/album 裸 ID。正常路径复用既有身份索引，rank-only 路径只构建一次有限 raw token 索引。别名经唯一 owner 解析，不能用同名或翻译文本发现人物。
- **v1/v2 与有限预算**：v2 明确使用新格式；有限完整事实、快照和观察引用均受 manifest SHA 覆盖，并拒绝缺事实、错 owner/slot/raw、未引用事实等情况。manifest 为 12 MiB 上限内预留 envelope 空间，报告上限 4 MiB，发送及接收总 envelope 保持 16 MiB。known source receipts、native artifact、replay、undo 与依赖判断同时识别两版；旧名称 proof/hash 的输入未加入新表，v1 checkpoint 算法保持原值。
- **重放与撤销**：正常 replay 核对不可变事实、原来源和每盘快照并返回原 receipt，不重新应用 current。rank journal 支持 DATE 的 ISO 往返；undo 在补偿写入前统一核对 journal after-image、后来 snapshot FK 及后来 applied receipt 的事实/快照依赖。后来晋段或后续引用会整批拒绝；不会删掉后来数据或倒退人物 current。
- **三盘纠正**：CLI 固定 `91694911`、`91638738`、`91637528` 与各自原始 manifest/SGF SHA，默认 dry-run 只读；输出以 fsync 后不覆盖链接冻结。已有文件重用先走独立验证，不开数据库、不重查晋段。TEST apply 必须显式 `--apply --target test --expected-sha256`；PROD 继续使用同一个冻结包和已有 verified receiver。native rank-only 分支校验原始完整包权威、source/SGF/raw metadata/canonical 和旧 snapshot CAS，跳过 SGF 全库预热、全库去重与姓名续审；不新增 album、不改源 link、原 receipt 或 `StateStore` 的 `prod_synced` 进度。成功重放跳过首次 CAS，返回原纠正 receipt。
- **API 与发布资格**：API 保持 raw rank 字段原值，每页一次批量读取 snapshots；列表、详情和 preview 共用固定决定，不查 current、不逐卡 HTTP。unknown 为空。v2 使用新 rank-aware checkpoint/report 算法，保留完整五语姓名/赛事/SGF/来源、raw/display rank、两侧快照 SHA/origin/provenance 及中文公开列表卡片摘要。sender 与 receiver 共用严格验证；不能以只含 album/lang 计数的旧报告批准 v2。当前范围无前端改写，已有隐藏未知段位的 UI 变更留给实际设备验收。

## 本轮实际验证

在最终 HEAD 上使用仓库既有 Python 环境执行 **16 passed in 4.06s**：

- `tests/web_ui/test_kifu_rank_publication.py` 全部 7 项：跨库不同 local ID、source history/snapshot 与 DATE journal、7p→8p 后旧包 replay、唯一别名、后来 snapshot 依赖、仅后来 receipt 的依赖、纠正快速路径/CAS/原 receipt 保持。
- CLI 实际 native publisher 应用与重放 1 项；付费名称失败后冻结重试 1 项；API 每页一次 snapshot 查询与 preview 复用 1 项。
- v2 报告的 count-only、缺语言、缺公开卡片、缺侧、错 source hash 拒绝 5 项；新 checkpoint 算法及 rank evidence 重核 1 项。

另做两项不改仓库代码的本地定向检查，均退出 0：

1. 以合法合成 v2 manifest 的正确 SHA 加旧式 count-only 报告，实际调用 `sync.send_verified_manifest` 与 `orchestration receive`；两端均在数据库/SSH 工作前拒绝。
2. 临时 SQLite 中先发布 7p、再发布较新 8p，撤销第一包因 current after-image 改变被拒绝；比较全部原生表和两张 rank 表前后像，零修改。

## 批准边界

本轮只读取代码、计划和测试文件，并运行合成数据/临时数据库检查；未读取全库 SGF、`data/kifu-album/` 文件、模型服务或真实写接口，未修改业务代码或真实数据库、状态与服务。

真实 PostgreSQL 004 迁移/约束及并发仍未实测；真实新谱 TEST→同包 PROD、三盘实际纠正与双端重放、五语及公开列表真实 API、1024×600 页面和同版本 RK 验收仍由发布控制者按运行手册补齐。发布须先 schema/兼容 receiver/API，再 producer。这些是部署阶段的未完成证据，不是本部署前代码切片的规范失败；本报告不宣称它们已经完成。
