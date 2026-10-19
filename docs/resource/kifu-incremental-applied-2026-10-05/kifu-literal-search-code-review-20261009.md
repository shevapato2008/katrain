# 已审赛事直译标题搜索：有限代码审核

**PASS。没有阻塞项。** 这组精确代码及两份环境 proposal 可进入 root 的既有 TEST-first guarded R16 发布流程；不宣称已上线。

审核人 `/root/durable_rule12_review_astra`；实际 UTC `2026-10-09T11:53:56.788357+00:00`；配置 `gpt-6-astra / max`，依据 `source.parent_spawn`，不声明 serving variant。审核者未执行 DB、SSH、部署、重启或 Git 修改。

## 精确字节

| 文件 | SHA-256 |
|---|---|
| repo legacy_raw_events.py | `16ab7a0185d8c9de96907f742bb4853e23e98e0e2d7bfa6969a40341135fb2b6` |
| tests/web_ui/test_kifu_raw_event_title_translation.py | `5d4408dc7413ba8965a84aef6962acaf35ea9d73cd387ffe54a7e94c156ecc3b` |
| 两环境实际旧运行时 helper proposal | `dc2e133edfe372c6415f1f169367329c78f8017d927fa111a17fefd10fb57617` |
| PROD endpoint proposal | `1dbb2367aa5fa574f21b357ee552af678e01ad003b727041f0ed9b44e8cc5272` |
| TEST endpoint proposal | `dc4a61f2a88fae541ab6016ef0b252dde0a1ecf73269c53a59a34bd7782ed652` |
| PROD proposal-manifest.json | `005bf8d70369feb73e167570d7737cf7648f40c1473007329c0694b6d37848f5` |
| TEST-proposal-manifest.json | `e77790fba6c5f785ff69ffdad0eab27d9dac7713b1608e8c4339bb6390e163bb` |
| repository-implementation.diff | `0846eba2f136af725df57c7725b3abd7965151b740f721662f81913138d3306e` |

## 已核行为

1. 新 helper 先复用 `_approved_rows` / `_eligible` / `eligible_literal_raw_name`，保留当前姓名/证据/owner 状态、revision、完整 candidate/research、实际审批者/时间、规则和正面 SGF 源检查。仅接受完整已批准 literal 标题，保留 `_other_exact_name_exists` 的冲突拒绝；不运行翻译或扩大为中文子串搜索。
2. 针对已命中的 evidence IDs 作一次有界 SQL 查询，要求唯一创建 ledger、before_image 为 null、创建后像的 owner/lang/revision/approved/payload/source_registry 与当前一致，以及 batch 实际 applied、完整 bundle canonical SHA、唯一 exact candidate、research hash 成员关系。审核 scope 从该 bundle 唯一 owner declaration 的非空无重复正整数 IDs 和 occurrence SHA 取得。缺失或不匹配时不给新 clause。
3. 实际返回 clause 同时限定已审 occurrence IDs、原始 event 值、event_id null、非重复、公开、无 selected-event 记录。没有删除旧 raw/alias/rank/排序/分页/显示行为；新增 scope 与原 needle OR 后同时用于列表与 count，保持两者一致。
4. 独立逐字节检查：每环境 endpoint 移除新增的精确五行后，完整恢复各自真实旧原文（PROD f97bc5cd…；TEST 200ee2c3…）。TEST 既有 identity_display_compat 导入及全部其他字节保留；工作区现有 endpoint 未被覆盖。两环境 helper proposal 相同；与 repo helper 的唯一差别是既有 pure `legacy_raw_event_rules` 导入适配，未改模型/表结构。

## 已有验证与本次核对

实施者 `focused-tests.txt` SHA `93a11418c48b4251ea0bd0c312b7b78f67411897848664fa9b3a30dac93af759`：27 focused tests passed，覆盖五语、同译名多 raw owner、冲突、审批/证据、batch/hash/candidate/research/ledger失效、旧 ORM 和已审/公开/未链接/未选择范围。审核者已读测试差异，没有重复整组或扩大回归。

真实 `PROD-live-preview-readonly.json` SHA `0be9e2589fa5b8dd602957d3e245e5849c23bb1ec5a4a1249fc3446caf877d37`：独立进程内存执行 proposed modules，DB READ ONLY；CN/TW 精确标题 0→65，raw 65→65，子串及无关查询 0→0；65-ID 集合 SHA `46e4cd4a5d33fd3ed15d2ced22c60a1726e9449797e3fa04c063c0eecc5c8a4d`。我核实际 preview 脚本内嵌的两模块正是被冻结的 proposed 字节，前后 deployed source 校验为原 SHA，没有写服务源。额外仅核全部冻结文件 SHA、上述五行可逆字节差分、proposal/helper对应关系和编译。

本报告范围是新 literal 精确搜索分支及已给定的两个实际旧 endpoint；不宣称所有未来 dispatcher/运行时已经应用，不审批新的赛事语义、owner/FK 或 DB 名称写入。发布后真实服务操作及验证由 root 按现有流程完成。
