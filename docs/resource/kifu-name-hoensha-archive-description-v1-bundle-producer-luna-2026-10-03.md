# Hoensha archive-description-v1 候选包生产记录（2026-10-03）

状态：**PENDING；未签署、未导入。** 生产者为 `/root/hoensha_11_bundle_producer_luna`，运行时标识 GPT-6（无独立子型号认证）。基线工作树为提交 `cf22621dfeaa497330c1e40dd7dfa3ba972d66d0`，其中实现提交 `137b021c` 为祖先。此记录冻结来源与候选，不批准数据库写入。

## 候选包与前像

受控 packet：`/Users/fan/.local/share/kifu-name-audit/2026-10-03/hoensha-archive-description-v1-producer/`。候选文件 `hoensha-595-archive-description-v1.pending.json` 的 SHA-256 为 `c64379e014a2c7d3958812d29e7133ad6642fc3c810101101df46d2f32b45076`。它含精确 `raw_event=Hoensha game`、category `archive_source_description`、parser/rule `archive-description-v1` 和完整十一语候选；分类审批、十一份模板审核与独立前像绑定均为 PENDING。十一语 member/candidate 均齐全。`album_links=[]`；没有 event owner、alias 或 event ID 链接。

只读捕获使用容器 `kifu-raw31-clone-20261003`、数据库 `kifu_raw31_clone_20261003`，事务为 `REPEATABLE READ READ ONLY`，完成后容器已停止。副本源自昨晚正式库副本；此结果只描述该副本，不能当作当前生产库。库存格式 4 snapshot 为 `2026-10-02T23:32:24.168545Z`，inventory SHA-256 `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`；catalog SHA-256 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`。二者与留存副本的既有快照一致。该副本没有精确 `Hoensha game` raw_event owner 或 raw_event name；十一语 name 前像均不存在。binder 尚未签署捕获绑定。

## 595 条来源范围及 17 条路径差异

精确范围为 595 条 inventory association：每条 `event=Hoensha game`、`event_id=NULL`、一个 `CWI` 来源链接；只读查询的数据库 `sgf_content` 全部含原始属性 `EV[Hoensha game]`。详情文件 `occurrence-source-contexts.595.json` 固定 595 个 album ID、日期、source path/link、原始 EV、内容字节数及以数据库 SGF 内容 UTF-8 编码计算的 SHA-256。该哈希不声称是另行下载的 CWI 文件字节哈希。

| 路径组 | 数量 | 范围结果 |
|---|---:|---|
| `CWI_History_Full/Hoensha/<file>.sgf` | 578 | 符合当前 archive scope 路径模式 |
| `CWI_History_Full/ancient/Honinbo_Shuho/<file>.sgf` | 17 | 均有同一 CWI source key、`event_id=NULL` 及 `EV[Hoensha game]`；路径须由独立审核者裁定是否属于本次同一说明范围 |

以下 17 条均保存于 `scope-difference.17.json`，并在 `occurrence-source-contexts.595.json` 中有完整来源链接和 SGF 负载 SHA-256。它们的原始 `EV` 均为 `EV[Hoensha game]`：

| Album ID | 日期 | CWI source path | SGF 负载 SHA-256 |
|---:|---|---|---|
| 154830 | 1879-06-08 | `ancient/Honinbo_Shuho/206.sgf` | `10823e866c4a50b37eb7c8daef1f97d69a4e6d1724cec30b7dd77a27829941ec` |
| 154831 | 1879-08-17 | `ancient/Honinbo_Shuho/208.sgf` | `0388ecf4cb6acc16c45ac19d42ab61f485a833b985da256a2b3bea84408be312` |
| 154833 | 1879-11-16 | `ancient/Honinbo_Shuho/211.sgf` | `a0f5ae17b89fc3c981a1347b8996f166a459ebfbc62e1af24d2227e455372e89` |
| 154834 | 1879-12-14 | `ancient/Honinbo_Shuho/212.sgf` | `59a07879e5cadf5885bfb236988d73a59858f1ee1683d368c5f629427becbc75` |
| 154835 | 1880-01-18 | `ancient/Honinbo_Shuho/214.sgf` | `e45797c2e9260514ec0b0d3cef870026ab3a6a730967c32fc1661e9c5a6e8f0d` |
| 154836 | 1880-02-15 | `ancient/Honinbo_Shuho/215.sgf` | `d8882dbc75d761ba4480145b3c61383bb55b035a215f416f702081e5e3a7bd50` |
| 154838 | 1880-04-18 | `ancient/Honinbo_Shuho/218.sgf` | `d3c3aedbc1f238ab8fafaa1c71ad94f1e60d9756481f446ef07f563003c48b47` |
| 154839 | 1880-05-16 | `ancient/Honinbo_Shuho/219.sgf` | `1a8818132be4d0bc4e57f1798669880fb34a73f99457b4443dc9ee93ae927fef` |
| 154842 | 1880-06-20 | `ancient/Honinbo_Shuho/221.sgf` | `9c704dcc8998f4faa7af8c5da9f8bb1ac8c1820b45c0aaaff6759f722a810265` |
| 154843 | 1880-07-18 | `ancient/Honinbo_Shuho/222.sgf` | `7127c57e3e4331ce27d329391ff5ff47d6480bc11e793e5f01b597e4919abbbd` |
| 154844 | 1880-08-15 | `ancient/Honinbo_Shuho/223.sgf` | `933ca9e846db97e2e10c20abe3c7f09b58e96f96bfc8eeb27f27a99e7267ae1c` |
| 154848 | 1881-04-17 | `ancient/Honinbo_Shuho/238.sgf` | `a09ce996570ee9b27a3594d4689cd2f5f271ea9281dc4046b4ec64ae3182e6fd` |
| 154851 | 1881-12-10,11,1882-04-20 | `ancient/Honinbo_Shuho/252.sgf` | `98c8657fe7a69ea8adf3b2ff94811668d3892b96863827226344b5eb678525d7` |
| 154860 | 1882-11-19 | `ancient/Honinbo_Shuho/275.sgf` | `e6c2214cd6cf47cdb93a324b0673b47e733fa9dc9b39cea0f22f6bea1202a8e5` |
| 154862 | 1883-05-20 | `ancient/Honinbo_Shuho/283.sgf` | `8dd2a8e5536600c11547a73cf7778de49c76da21712c5084f01990c312659ede` |
| 154868 | 1884-03-16 | `ancient/Honinbo_Shuho/300.sgf` | `4aecb1a0c4c0dcc4cabd71937c6fe25a30c191478e3b74d41238d1d0ff0b89ca` |
| 154882 | 1885-05-17 | `ancient/Honinbo_Shuho/328.sgf` | `b7caba7ed237917147611a439c0c515bc88c4f5576624864258bf3ac4fb4c4e5` |

No source path was rewritten and no occurrence was omitted. The code path predicate in `katrain/web/kifu/name_candidates.py:283-286` currently requires exactly `CWI_History_Full/Hoensha/<file>.sgf`; it will reject the 17 nested paths with `archive description occurrence is outside reviewed CWI Hoensha source context` after category approval is supplied. The current validation stops earlier because the category review is pending.

## Retained history sources and validator

Source registry `.7` is used with registered IDs `cwi-go` and `nihon-kiin-archive-jp`. Retained response bodies were copied from the earlier producer packet, not freshly fetched: CWI SHA-256 `abeb516b8b69c606d1bf246191416aa6ef4a1db14b5b171aac505cafd22c417e`, captured `2026-10-02T22:17:04.723999Z`; Nihon Ki-in SHA-256 `813b6092377b2808f5dc91574fee2ea2c38673f84351ca72dd3c83fd9b74289f`, captured `2026-10-02T22:17:04.511616Z`. Their passages support Hoensha historical organizational and game-record context; they do not prove an individual event identity or official localized names.

The actual `validate_bundle` result is in `validator.pending.actual.json`: `ready=false`, `write_ready=false`, zero approved decisions. Reported blockers are:

- `owner[0]: archive description requires independent category approval`;
- consequence of that scope rejection: 11 `member[n]: owner missing from finite v2 manifest` and 11 `candidate[n]: candidate lies outside finite member set` errors;
- 11 `write_errors`: `candidate[n]: independently reviewed preimage binding missing`.

Although its structural counters show `pending=0`, the bundle has 11/11 pending candidate statuses; the invalid members/candidates are excluded before status counting. All eleven template reviews and the owner category review remain pending. The independent reviewer must decide the 17-path scope issue before final category approval/binding. No tests, code edits, production/test DB writes, signatures, or commit were performed. The clone was stopped after each read-only capture.

The packet's protected SHA-256 list is `protected-files.sha256`; it covers packet artifacts and relevant committed protocol, registry, review, and code files. The repository's only untracked entries before this memo were `.firecrawl/` and `tmp/`; they were left untouched.
