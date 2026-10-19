# Hoensha archive-description-v1 绑定候选包（PENDING）

2026-10-03；生产者 `/root/hoensha_11_bundle_producer_luna`（运行时标识 GPT-6；无独立子型号认证）。按已冻结分类和模板审核重新生成十一语言 bundle 并绑定当前克隆前像。工作树提交 `5c78237104d11d259254212e44310bc47435a513`，其中 archive source validator 的接受规则提交 `23af794d` 为祖先。此文件仅记录候选/前像证据；11 个最终候选签名仍待独立审核，未导入。

## 冻结审批输入

- 分类审批 artifact SHA-256：`0d3ebc32f292630b9964a5d3998099894a90f4bef3935ea48d9553f3e2b64872`；manifest SHA-256：`0585403708f5fb87259f27b7b625d171f82e14b470ec5b1573b039dfdd255c95`。批准范围 hash：`d10c54be5c4e0bfe13f1f6fa9480549c0f29c2fa55ed36e222f45b114d820b44`，覆盖精确 595 个 CWI 源行：578 个直接 `Hoensha` 路径与 17 个经独立逐谱审核的 `ancient/Honinbo_Shuho` 路径。分类限定为历史来源说明，不建立赛事身份或棋局链接。
- 十一语模板审批 artifact SHA-256：`157101a54793ea32993fa6883be44ef41aba0b17a3fbc24cc9f14eeab7d89b8e`；manifest SHA-256：`d5a7a65c8749f17f62b616f8d2ec6db76737a92deb8709634b5f0477669816c5`。11/11 字符串与 `archive-description-v1` 精确模板和 hash 一致。

| 语种 | 精确模板文本 | 状态 |
|---|---|---|
| cn | 方圆社史料棋局 | 已批准模板；候选待独立签署 |
| tw | 方圓社史料棋局 | 已批准模板；候选待独立签署 |
| jp | 方円社の棋譜（史料） | 已批准模板；候选待独立签署 |
| ko | 호엔샤(方円社) 관련 옛 기보 | 已批准模板；候选待独立签署 |
| de | Historische Partie aus dem Hoensha-Archiv | 已批准模板；候选待独立签署 |
| es | Partida histórica del archivo de Hoensha | 已批准模板；候选待独立签署 |
| fr | Partie historique des archives de la Hoensha | 已批准模板；候选待独立签署 |
| ru | Историческая партия из архива Хоэнся | 已批准模板；候选待独立签署 |
| tr | Hoensha arşivinden tarihî go partisi | 已批准模板；候选待独立签署 |
| ua | Історична партія з архіву Хоенся | 已批准模板；候选待独立签署 |
| en | Hoensha archive game | 已批准模板；候选待独立签署 |

## 当前克隆前像绑定

在确认容器处于停止态后独占启动 `kifu-raw31-clone-20261003`，只读捕获后再次停止。数据库为 `kifu_raw31_clone_20261003`；inventory 查询和前像快照使用 `REPEATABLE READ READ ONLY`。捕获时间 `2026-10-03T00:53:46.295085+00:00` UTC，inventory snapshot `2026-10-03T00:53:36.444386Z`；inventory SHA-256 `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`，catalog SHA-256 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`。二者与已审冻结库存一致。approved-name snapshot 为 0 条，SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`。精确 `Hoensha game` raw_event owner 和 name 均不存在；11 个新 owner name 前像均为 null。克隆 name audit 表现为 3 个 `kifu_name_batches` / 230 个 `kifu_name_changes`（上一捕获为 2 / 69），但所需 inventory/catalog、目标 owner/name 前像及 approved-name snapshot 均按本次捕获重新绑定并固定在 packet 中。来源仍是昨晚正式库副本的克隆，不代表当前生产库。

Bundle `hoensha-595-archive-description-v1.approvals-bound.pending.json` SHA-256：`3287d0182eaa8e45613d08c466dc6188d75c8c5050a6152306f556f1f090dfea`。新的 `owner_set_sha256` 为 `ccbb7040324f8eb788e458a60f6141bd870b269d3a058e0d5293f53e1a2ca0c3`，`member_set_sha256` 为 `aedd2a10aa7af3d81e9c03e6cca8e1cee077f95195688d82c0e9a23cd7f89861`；`archive_scope_sha256` 与已审范围 hash 一致（`d10c54be5c4e0bfe13f1f6fa9480549c0f29c2fa55ed36e222f45b114d820b44`）。11 个候选均为 `review_status=pending`，并嵌入 root 的精确模板审核签名。每个候选都带由 `/root/hoensha_11_bundle_producer_luna` 在实际捕获后生成的 `preimage_binding`，capture SHA-256 `7080b406f66d6df7b62a386132cfd85403f85da4c968b25fd3300d0208e1bfa7`，name preimage 为 null。无候选审批签名。

## 实际 validator 结果

报告文件 `validator.pending.actual.json`：`ready=false`、`write_ready=false`、`write_errors=[]`。库存、catalog、来源正文、类别范围、11 语模板、owner/member 范围和前像 binding 均通过结构校验。只剩预期的最终批准门槛：

- 11 条 `candidate[n]: archive description candidate requires approval after category review`；
- `archive description owner requires all eleven approved language names: raw_event:@raw_hoensha_game_20261003`；
- `new raw category lacks corresponding approved display decision: raw_event:@raw_hoensha_game_20261003`。

validator 的 `pending` 计数仍显示 0，因为它只统计已通过候选校验的 decision；bundle 本身有 11/11 个 pending 状态。分类审核和模板审核原件、旧生产包、完整 595 occurrence 上下文、新库存/catalog/approved-name/preimage capture、clone-stop receipt、来源正文副本及校验报告均在受控 packet。受保护文件 SHA-256 索引为该目录的 `protected-files.sha256`。

未连接生产库或测试库；没有数据库写入、测试运行、代码修改或 commit。公开首轮候选记录仍保留原状；本文件记录其审批后重新绑定的版本。
