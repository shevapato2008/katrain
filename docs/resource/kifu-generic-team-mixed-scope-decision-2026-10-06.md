# 团体赛有限 mixed-scope 决定 — Astra，2026-10-06

**决定：先交付其余 49 raw / 557 局；允许随后为固定“团体赛”建立单独的小范围例外。** 该例外保留 30 局现有赛事关联，仅为符合现有 NULL-event/public/nonduplicate/no-selection 条件的 294 局提供 raw 译名。不因此开放其他 mixed raw，也不修改赛事身份。

已检查 `/tmp/kifu-event-title-generic50-20261006/{TEST,PROD}/scope-capture.json` 及现有 owner/name/reader 路径。两份捕获一致：

| 范围 | 全部 occurrence | 可展示/可计新增 | 已关联排除 |
|---|---:|---:|---:|
| 团体赛，既有 raw owner 73686 | 324 | 294 | 30 |
| 其余 49 raw | 557 | 557 | 0 |
| 合计 50 raw | 881 | 851 | 30 |

49 raw 的固定 sorted-raw-array canonical SHA-256：`17b041004df08a99aa9845060e0d6009f103e612110673e48a6260e2bd1395ab`。团体赛单一 raw-set SHA：`6fac391a238c31cdff80bad25d6f2452e9d30f898301a0815af4b3c556cdebfa`。

## 现有协议应怎样记录

`name_candidates._v2_scope` 要求 raw owner 的 `occurrence_album_ids` 与 inventory 的**所有**该 raw 出现位置严格相等。因此团体赛 declaration 必须填写全 324 个有序 ID，并对这 324 个 ID 计算 `occurrence_sha256`；填 294 会违反协议，不能为方便而改变该字段含义。其 owner `preimage` 仍为完整当前镜像。

`bundle.members` 是名称成员，仍只有该 owner 的 cn/tw/jp/ko/en 五项；它不是棋局 ID 清单。`album_links=[]`，沿用 format 2 / inventory 4。`name_batch._affected_albums` 会返回全 324 的审计涉及范围，这个值不能被当作新增显示覆盖。

在该有限 manifest/owner review 和执行收据中另行明确记录 `eligible_album_ids`（294）及 `excluded_linked_album_ids`（30），各自计数/hash；两者不交叠、合并后恰为 all-occurrence 324。实际新增覆盖最多 294，最终用五语言 strict/legacy 读取结果确认；原有 30 局即使本来已有赛事显示，也不算本次新增。

## 团体赛单独实施的最小边界

1. **补齐全量冻结证据。** 当前 capture 的 `occurrence_album_ids` 实际只有 294 个 eligible ID；另外 30 局仅有数量，没有 ID/原 event_id/字段镜像。它尚不足以批准全 324 的冻结计划。由 root 补一次只读捕获，保存全部 324 的原 event_id、原 EV、SGF hash、日期/轮次/段位/来源及可见性字段，连同完整 owner 前镜像与 inventory/catalog pins。
2. **只加团体赛固定 profile。** 固定 raw/owner、324 全量、294 eligible、30 linked；其他 profiles 保留现有全部无关联要求。owner 工具针对该 profile 容许上述精确 30 项的原 event_id 非空，其余仍全部要求公开、非重复、无 selected scope。全 324 的 `scope_rows` 与 SHA 留在原有审核单/metadata，不能只冻结 294 或只比较两个数量。
3. **名称写入仅复用这一已审核例外。** `_check_raw_owner` 的纯无关联门禁仅对该 raw/owner 且具有已批准有限 mixed-scope 证据的情形分支；在写锁内重新核对全 324 的冻结字段 hash、294/30 的精确分区及已关联 event_id。任何 excluded 行从一个非空 event_id 换到另一个非空 event_id，也必须拒绝原计划。不能简单删除 `all(event_id is None)`，也不能只加 `raw == 团体赛` 的无证据豁免。
4. **保持现有写入和读取边界。** 只写 owner review_status/review_metadata，随后只写 names/evidence/ledger；不更新任何 album、FK、SGF、alias 或 parser 字段。两种 reader 已按当前 `event_id IS NULL` 等条件排除已关联棋局，无需新 reader 机制。此决定遵循现有“当前字段条件决定显示资格”的语义，不增加永久 album 排除名单协议。

这些约束允许继续使用现有全 occurrence validator、名称 bundle、签名、锁、前后镜像账本和条件撤销。无需新的范围描述框架，也无需把 30 个 linked 局塞入身份链接审核。

最小聚焦验收：一个正常混合样本证明名称只作用于 eligible 子集且 linked FK/内容逐项不变；一个 excluded linked 字段变更证明 CAS 拒绝。正常批次撤销沿用原机制。不重做整个 raw-title 功能回归。

**执行顺序仍为 49 / 557 先交付，团体赛 1 / 294 单独补齐证据和小补丁后交付。** 这样当前可写的 245 个五语言名称不等待 mixed-scope 扩展；39 个“中国围棋段位赛”/294 局的地理限定语决定属于另一个已明确范围，继续独立推进。

本次仅作有限决策和本地读取，没有代码、数据库、SSH 或部署操作。
