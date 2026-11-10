# Kifu Elasticsearch 计划独立评审，第 2 轮（最后一轮）

日期：2026-10-30。评审者：同一独立 Astra Max。结论：**Approved（实施计划层面）**。最终未解决 Critical：0；Important：0。

对象是 docs/superpowers/plans/2026-10-30-kifu-elasticsearch-search.md 的第二轮最终文本，包含 Root 在本轮收到反馈后完成的定点修订。这些修订在本轮内复核，不构成第三轮。本轮只复查第一轮 I1–I5 及新增内容的内部一致性；未部署、建索引、运行旧 prepared、操作业务数据或修改产品代码。唯一写入是本评审文件。

## 第一轮问题的关闭情况

| 原问题 | 第二轮最终判断 |
|---|---|
| I1：资格/类型驱动查询，不按 hits 分类 | 已关闭。typed term/public-player 元数据、exact 零盘、公开身份边界、原分支规范化、有限 scope、越末页空结果及任意非空页 preview 均已明确。所有业务计数过滤 doc_kind=album。 |
| I2：投影权威来源和复用边界 | 已关闭到可实施的计划程度。来源表及 build_projection_context/project_album_batch 两个入口足够；按唯一 owner/name/batch 复用既有资格，有限 scope 单独适用，不依赖待删六表。实际批处理成本留待样本验证。 |
| I3：本页 SGF 与报告/段位绑定 | 已关闭。Task 4.3 如实保留当前页必要 SGF、source_path 和原判定；响应仍只含首盘预览，ES 不存 SGF。 |
| I4：真实 affected IDs 与 undo 删除 | 已关闭。现有 guard/journal/owner 关联集合、当前 PG upsert/delete、分类撤销及实际 writer 表均已补齐，没有扩张为新删除/更名产品。 |
| I5：全量、提交、恢复、可见性闭环 | 本轮新增反馈落实后已关闭，具体见下。 |

## 第二轮发现并在本轮关闭的三项问题

**1. 请求开头的 ready 检查存在并发窗口。** 原修订仅在 _mget 时检查 ready，不能阻止随后发生的 writer 造成旧分类、新 ES 结果和新 PG 数据混读。最终 Task 4.7/5.3 使用同一具体索引的单调 epoch，写入进入 pending 时递增、恢复 ready 不回退；请求在 ES 查询和 PG 补齐后再次确认 ready 且 epoch 相同，包括空结果和越末页。Task 5.8 覆盖跨请求写入及 ready→pending→ready 的 ABA。该方案使用现有一个状态文档，不增加读锁服务或新事务平台。两次状态读取成本计入完整 HTTP；_mget 逐项错误不会被当作无词条转入 generic。

**2. PROD verify 的修复原先缺少合法远端入口。** 最终 Task 5.6 不再要求 TEST 调用任意 PROD sync-batch 命令，而是复用 send_verified_manifest 和原验证材料，经原受限 native receiver 对同 manifest 幂等重放，让 PROD 本地 publisher 修复 ES，再进入原验证阶段。TEST 只在本机做本地修复；SSH forced command、host pin、签名 receipt 和数据库目标边界保持。相关文件范围明确为有限接线，不扩协议。

**3. pre-PG pending 的恢复原先可能没有 batch/journal 可定位。** 最终 Task 5.3 及恢复段明确：publication 使用 manifest digest/publication key，新 apply 使用写前已知的 bundle digest，undo 使用原 batch ID。恢复必须先取得原 writer 锁确认上次操作结束，按 digest 查询提交事实；仅对全部变更属于原子事务且确认未提交/回滚的操作恢复 ready。已提交重投当前 PG；未知结果保留 pending 并报告。无 journal 的人工 import 在 pending 之前原子写入小型 0600 输入摘要/source_path 记录，operation_ref 可定位，恢复只处理该有限集合，不假称原导入命令已成功。这足以作为一期恢复边界，不需要新 outbox、PG 表或常驻队列。

锁描述也已纠正：外层 _PUBLICATION_LOCK_KEY=0x4B49465550554231 的独立 Connection 保持原样；只在业务 Connection 上延长 720220261002、720220261003 两个内层 key 的 session 持有至有限 ES 尝试结束。空锁事务结束后才写 pending，再进入原业务事务，避免重复获取外层锁造成自锁；解锁结果未知则 invalidate 物理连接。有限崩溃恢复检查已覆盖 pending 成功但 journal 尚未创建，以及无 receipt 人工 import。

## 其余已核对的修订

- Task 3.6 与六步首次上线顺序已统一：先准备/审查包，后暂停准入、等待发布结束、TEST 旧包 disable，再部署 bootstrap 包并构建；成功确认新 hook 后才恢复 collector。失败保持 legacy，恢复本次控制状态并清理无引用候选。
- 最终负载判定使用完整 HTTP max≤200ms、全部 3000 样本、0 错误/差异及真实到达率；不复用旧 ASGI p95 或 low20ms 作为最终通过证据。
- 两端磁盘独立计量，含分类文档的整个索引 store2GiB 观测阈值、10GiB 首次额外峰值、15GiB 宿主剩余线及 GC/应用/Docker 日志和 dump 策略已落到计划。预算没有被写成实测承诺。
- 旧 prepared 的 disable、实际 reader/writer 和四进程退役、40 个 guard 与六表的 RESTRICT 删除顺序，以及共享镜像/真实 runtime 的保护仍保持正确。

## 用户批准时必须看见的实际取舍

计划现在明确：**性能的 100QPS、每请求≤200ms、0 错误验收针对稳定 ready 的可读窗口；正常发布或恢复期间 pending 会使 ES 搜索短时返回 503，并阻止后续正式同步成功，下载/翻译可继续。** 发布窗口的显式 503 和恢复另行验收，不能被稳定窗口的压测结果掩盖，也不能宣称已经满足全时段零错误。该取舍已写入 Task 6.3 和验收清单，应在提交用户批准计划时如实说明。

## 实施时验证，不是本轮尚缺的设计

固定镜像版本/digest、批量资格投影实际成本、分类元数据大小、全量构建时间、1GiB heap 深页开销、实际磁盘峰值、共享 8CPU 下完整 HTTP 100QPS、Galaxy/RK 页面表现仍须在获准实施后测量。

本轮 Approved 只表示计划已具体到可以实施和验证，不表示性能/存储已达标，不表示实现代码已完成审查，也不构成用户部署授权。两轮计划评审至此结束，不追加第三轮。
