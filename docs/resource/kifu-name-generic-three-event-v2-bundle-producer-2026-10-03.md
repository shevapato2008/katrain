# 三个原始赛事说明：v2 草案与精确协议阻塞

2026-10-03；生产者 `/root/generic_event_bundle_producer`，运行时模型标识 GPT-6，未独立认证具体子型号。依据 [候选稿](kifu-name-generic-three-event-11lang-candidates-luna-2026-10-03.md)、[独立术语审核](kifu-name-generic-three-event-11lang-independent-review-sol-2026-10-03.md) 和 [冻结分流](kifu-name-high-volume-event-triage-2026-10-02.md)，保留三个精确原文：`段位赛` 901、`个人赛` 638、`Hoensha game` 595。共 2,134 个冻结槽、33 个候选字符串；全部新签署为 pending，0 批次批准、0 写入、0 实际显示增益。

受控目录 `/Users/fan/.local/share/kifu-name-audit/2026-10-03/generic-three-event-v2-bundle-producer/`（0700，文件0600）包含修正后 33 格、三个完整原文范围、个人赛 `bundle_format=2 / inventory_format=4` 待签阻塞草案、未改动 registry `.7`、四份保留网页正文副本和实际校验日志。没有启动容器、连接数据库、写测试或修改正式代码，没有提交。按当前工作范围，停止于明确的协议失配，语义协议决定后再重新制包。

## 精确修正与类别

原稿三个 HOLD 均采用独立审核提出的精确替代：段位赛 ko `단위(段位) 관련 대회`；Hoensha jp `方円社の棋譜（史料）`、ko `호엔샤(方円社) 관련 옛 기보`。替代文本尚未获得新工件独立签署，未把原稿 PASS 移植为包批准。个人赛 jp/ko/en 标为编辑翻译；Hoensha en 标为编辑扩写，均未冒称 SGF 原文或官方赛事名称。

`corrected-33-candidates.pending.json` 保留全部十一语；`three-raw-scopes.pending.json` 从复制的完整 inventory 重新计算范围，901/638/595 与冻结分流一致，所有目标 `event_id`、`duplicate_of_id` 均 NULL。中文两组保留 `generic_event_description`；Hoensha 的目标含义是历史组织/档案来源说明，记录为 `archive_source_description` 意向类别，同时明确当前 parser 实际返回 `unclassified_pending`。没有创建 event owner、赛事 ID、alias 或棋局身份关联，`album_links=[]`。

## 当前协议拒绝的精确文本

`generic` 仅接受 [固定 classification-v1 模板](../../katrain/web/kifu/name_candidates.py:60)，按字符串完全相等比较。个人赛十一格中八格通过单条 pending 校验，下列三格真实报 `classification display differs from versioned language template`。段位赛另外八格也与固定模板不同。

| 原文 | 语种 | 已审/修正候选 | 当前固定模板 |
|---|---|---|---|
| 个人赛 | en | Individual tournament | Individual Tournament |
| 个人赛 | ru | Индивидуальный турнир | Личный турнир |
| 个人赛 | ua | Індивідуальний турнір | Особистий турнір |
| 段位赛 | ko | 단위(段位) 관련 대회 | 단위 대회 |
| 段位赛 | en | Dan-rank tournament | Rank Tournament |
| 段位赛 | de | Dan-Grad-Turnier | Rangturnier |
| 段位赛 | es | Torneo de grados dan | Torneo de grados |
| 段位赛 | fr | Tournoi de grades dan | Tournoi de niveaux |
| 段位赛 | ru | Турнир по данам | Турнир разрядов |
| 段位赛 | tr | Dan derecesi turnuvası | Seviye turnuvası |
| 段位赛 | ua | Турнір за данами | Турнір розрядів |

Hoensha 十一格均没有 archive 描述模板；[generic 类别闸](../../katrain/web/kifu/name_candidates.py:499) 拒绝其当前 `unclassified_pending` 分类，而新 raw owner 的 [类别闸](../../katrain/web/kifu/name_candidates.py:661) 要求与保守 parser 完全一致。当前允许该分类使用的 conventional/generated/composed/transliterated 路径不能诚实代替描述性编辑翻译：conventional 要正面名称研究，generated 要完整负面检索及读音证据，composed 是本因坊专用组成协议。不能把 Hoensha 提升为赛事身份以绕过这些闸。

## 个人赛有限草案及实际失败

`individual-638-v2.bundle.pending-blocked.json` 只有一个新 raw_event ref、638 个精确原文出现、十一语 members/candidates 和零身份 links。规范 JSON SHA-256：`6a4ffa7be9e27ffe8ed7d3b73abdde53d7b9850e1b22631944baaecc601a0bb6`。

`individual-638-v2.validation.actual.json` 实际 `ready=false/write_ready=false`：新 raw owner 尚缺独立 category approval，产生后续 owner/member/candidate 依赖拒绝，十一格也尚无最终前像 binding。报告 `pending=0` 是计数器只计已通过结构校验的 decisions；原始 candidates **11/11 均 pending**。为看清模板根因，`individual-11-classification.validation.actual.json` 另调用现有公开单条校验函数，得到八格有效 pending、en/ru/ua 三格固定模板失配，没有伪造 category approval 或临时放宽校验。

可复用个人赛草案结构到段位赛：使用对应冻结 scope、新 raw_event ref、通用类别、零 links 和完整十一语；当前先解决表中精确模板差异。Hoensha 先决定最小档案描述类别/决策路径，再生产真实受支持的 v2 工件。独立签署还必须覆盖实际 category、版本模板及前像绑定；不能只对现稿补签来忽略协议拒绝。

## 旧快照、前像边界与来源

按本轮范围收敛，复制丁波生产者较早的克隆 inventory，**不是当前查询**：`2026-10-02T22:10:26.244060Z`，database identifier 为 `postgresql://postgres@127.0.0.1:55433/kifu_raw31_clone_20261003`；inventory SHA `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`，基础 album/source SHA `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`，旧 catalog SHA `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`。所有工件均把它标为 frozen/older。

丁波前像 capture 只捕获 raw_player，**不是本批 raw_event 前像查询**。另复制旧本因坊 clone-before receipt，其中 raw_event_value/name 均 0、catalog hash 与上述旧捕获一致，作为旧状态线索；不声称同一事务或当前克隆状态。草案 new ref 的 `name_preimage_sha256:null` 是新 owner 的协议要求，尚未形成可签的当前目标前像 binding。`preimage-limitations.json` 明确记录这些限制；语义决定后须重取目标库真实 owner/name 前像与 inventory/catalog，再由实际 binder 绑定、独立 reviewer 签署。

四份网页正文从此前 root 重取目录只读复制，并重新核对全部字节 SHA 与独立审核一致，捕获时间为 `2026-10-02T22:17:04Z` 附近；这是旧正文副本，未冒称本轮实时抓取。CWI 和日本棋院 archive 有 registry `.7` 记录；NDL 与 Kotobank 当前未登记，`registry-source-gaps.pending.json` 明确列出缺口，未虚构登记或 source_check。四页仅支持 Hoensha 历史来源语境；中文两组的直接原文依据来自冻结 inventory，韩日术语旁证仍是独立审核 memo 引用，本工件未补抓它们。`generic` 分类路径拒绝名称 research，因此草案 `evidence.empty.jsonl` 有意为空，来源正文与术语审核作为受控依赖保存，未包装成官方 localized name 研究。

`manifest.json` 固定全部受控输入/输出字节 hash；本轮没有 importer dry-run/apply。最终签署将改变包 hash，后续应重新生产及核对工件。
