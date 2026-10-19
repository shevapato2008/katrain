# 李昌镐 ID 143：34 个联赛槽位 v2 关联包预备

本备忘录记录未签、未冻结的有限关联包草案。草案由 `/root/lee_34_bundle_prep_luna`（记录模型 `gpt-6-luna`）于 2026-10-02 制作；没有自我批准、生产写入或克隆写入。它是额外批次，原先获签的五个槽位不在本批次中。

## 固定候选范围

独立审阅记录确认 58 个韩国围棋联赛候选中 **34 PASS、24 HOLD**：33 个 PASS 与 Go to Everyone! 完整赛程行吻合，另有 `98043/black` 以原始 CyberOro 全盘棋谱覆盖冲突赛程行。此处只使用以下 34 项；24 个 HOLD 未进入成员或链接集合：

`27182/white`, `27207/white`, `28261/white`, `29575/black`, `30702/white`, `34513/white`, `44125/black`, `50340/black`, `50488/white`, `70911/white`, `73619/white`, `74958/black`, `75033/white`, `83412/black`, `83561/white`, `84074/black`, `87568/black`, `87595/black`, `89846/white`, `90505/white`, `92389/white`, `93288/white`, `98013/black`, `98023/black`, `98039/black`, `98043/black`, `98050/black`, `98054/white`, `98065/white`, `98066/white`, `98098/white`, `98101/white`, `98122/black`, `98128/black`.

`raw_scope_sha256` 是对 2,140 个精确原文 `李昌镐` `(album_id, slot)` 项按整数 ID／槽位排序后计算的 SHA-256：`43b19733404467dbe5300258627767d32ecd13138de7ac81d26a5a720acac9ec`。它绑定完整原文范围；本批链接集只有 34 项，规范哈希为 `5cf4390fe67fbcf9e8a321904a01c38604a2604eabf0f0e6552ac47518a6426d`。原五槽位批次未被并入。

## 草案与输入快照

受控目录 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-34-v2-pending/` 权限为 `0700`，文件为 `0600`。`bundle-draft.json` SHA-256：`e10d80d8732069467cc87b0ec3534bf3e0a0632f05cae32dec30cc22d212abb3`。它含 34 条白／黑棋手关联、独立审阅来源行、完整期望上下文、11 个来源已审姓名候选的引用，且把身份审核和姓名前像绑定保持为 pending。完整来源哈希及每项 SGF 根和上下文证据在受控目录的 `manifest.json` 与 `slot-preimages-and-source-evidence.json` 中。

可用的旧冻结数据如下；这些值用于草案上下文，不代表已完成当前批次前像绑定：

| 输入 | 文件 SHA-256 | 内容哈希／说明 |
|---|---|---|
| 生产 v2 inventory | `518748084105398b4faeadc090d54f4a033b282a9402db20d2b0564fab465bd9` | 内部 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`；inventory format 2 |
| 克隆 v2 inventory | `a2f2bb7f73672958a6d6b742ea39d0545a666e2b94272e75ae168250c440872b` | 内部同上；基于 2026-10-01T18:11:45.460901Z 的快照 |
| 生产只读审阅捕获 | `8af0ea297e3c4e9b4e2da27487b484dbf171dc2d14a94b1267f56a0200ed7a64` | 完整 album/source/catalog/name 行，快照 `2026-10-02T05:08:51.65031+00:00`；SGF 正文只含先前五项 |
| catalog | — | 先前五项包记录的哈希 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09` |
| player 143 name preimages | `5e7ed4b44ea81707ce10384e31afc5219021cfd0a896157042b3575c438bb220` | 五个现存语种行与六个缺失行；需现时重捕获 |
| 精确槽位清单 | `5c36cdcedf3303310b05bf68b4ad3cc45c6e5368c76c1fbe373e3ab388844f11` | 2,140 个槽位 |
| 58 项独立审阅 JSON | `0062e6c29ef0e12318de7e3c649f1b64ab9df5fee364035738519e477d1958b7` | `gpt-6-sol`；34 PASS、24 HOLD |
| 来源协调 JSON | `0bb2b3f2059ca68f38ed15b2c89066425551b92cee2812036991bb1dcd9467e2` | producer reconciliation；不能替代独立身份签署 |
| source SGF hash CSV | `5ba5cbc90b0549db954122eb0a4d997f5a508c8e58550fb3ba53f8e392731496` | 源棋谱哈希，不是 34 项生产 `sgf_content` 哈希 |

链接的 `association_sha256` 与完整上下文从可用冻结 v2 inventory 派生。独立审阅 JSON 中的 `source_sgf.raw_sha256` 保存在私有侧车证据中，**没有**填入 `production_sgf_sha256`：对这 34 项尚无与同一现时生产事务绑定的 SGF 正文前像。不能把源文件哈希冒充为生产 SGF 前像。

十一语显示名与研究引用沿用既有独立来源批准行，并随受控副本保存来源 provenance 与 research。先前五槽位包对“绑定后的候选行”的批准不转移到本批；新生产前像绑定和本批独立复核仍待完成。

## 待完成的冻结与独立签署

可用生产捕获早于这次 34 项审阅，也早于当前可见的 selected-event inventory format 4 实现；可用克隆清单在五项隔离 apply/undo 演练之前。没有足够证据把旧文件称为当前生产／克隆状态。下一位生产者需在同一冻结周期内：

1. 以生产只读事务重新捕获完整 inventory、catalog、player 143 别名／canonical 唯一性、全部 11 语名称行前像，以及这 34 项各自的生产 SGF UTF-8 哈希和关联行。
2. 重新计算 2,140 项精确原名范围和 34／HOLD 分区；若范围、上下文或 SGF 与现有审阅输入不同，暂停并取得相应重审，不复制旧批准。
3. 在撤销后状态重新捕获克隆 inventory，并核实它与拟演练基线一致。
4. 如当前 selected-event 状态已纳入快照，使用 inventory format 4 捕获其选择与关联证明。**本批全是 player `black`／`white` 链接，因此 bundle format 2 仍合适；format 4 的链接语义只用于 `selected_event` 链接，本批不含此类链接。** 当前 validator 允许 format 2 bundle 搭配 format 4 inventory。
5. 用新前像重做候选绑定、重算 bundle/hash；由不同于生产者的独立审核者核验确切 34 项载荷、来源、生产／克隆前像，并签真实 `identity_review` 与 11 条绑定后姓名审核。此草案没有 freeze 时间、`scope_sha256` 或审阅签名，也不得用于 apply。

本次未运行导入器验证，因为 payload 明确保留空的生产 SGF 前像及 pending 状态，尚未达到可验证冻结包的条件。受控目录 `manifest.json` 登记了草案自身和全部输入来源文件的 SHA-256。
