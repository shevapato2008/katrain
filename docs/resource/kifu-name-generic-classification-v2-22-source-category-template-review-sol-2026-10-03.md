# classification-v2 22 格：独立来源、类别与模板签署

审核者 `/root/generic_v2_22_source_review_sol`；运行时标识 GPT-6，任务名中的 sol 不构成具体子型号认证。签署时间 `2026-10-02T22:55:24.479116+00:00`。对照 [Astra 阶段一协议](kifu-name-generic-three-event-protocol-decision-astra-2026-10-03.md) 和 [Sol 原 33 格审核](kifu-name-generic-three-event-11lang-independent-review-sol-2026-10-03.md)，独立审核 Luna 的 `generic-classification-v2-22-candidate-producer`。

**来源语义 22/22 PASS、类别 2/2 PASS、十一语 v2 模板 hash 11/11 PASS；最终候选签署 0/22，整包仍 HOLD，`ready=false/write_ready=false`。** 本次签署只覆盖精确通用说明、分类和旧冻结范围，不认证当前 owner 不存在，不批准数据库前像或身份关联。原 33 格稿的 30 PASS / 3 HOLD 结论保留；本包采用其修订文字。

| 语言 | 段位赛 | 个人赛 |
|---|---|---|
| cn | 段位赛 | 个人赛 |
| tw | 段位賽 | 個人賽 |
| jp | 段位戦 | 個人戦 |
| ko | 단위(段位) 관련 대회 | 개인전 |
| en | Dan-rank tournament | Individual tournament |
| de | Dan-Grad-Turnier | Einzelturnier |
| es | Torneo de grados dan | Torneo individual |
| fr | Tournoi de grades dan | Tournoi individuel |
| ru | Турнир по данам | Индивидуальный турнир |
| tr | Dan derecesi turnuvası | Bireysel turnuva |
| ua | Турнір за данами | Індивідуальний турнір |

两个原文均严格为 `raw_event / generic_event_description / generic / classification-v2`；每个 owner 有精确十一语 members/candidates。cn 是来源原文，tw 是繁体转换，jp/ko/en 及次六语均为编辑翻译，不声称本批 SGF 的当地官方赛事名。段位赛不推定升段制度、分组规则或全国系列；个人赛不补国家、年份、届次或全国身份。完整语言模板字典已冻结，hash 绑定包括未变的旧 placeholder/error 文本；本次新增语义批准限定于两个 generic 字符串。

独立从完整旧 inventory 重取精确出现行，逐项核对 producer 的全部 contexts、occurrence IDs/hash：段位赛 901 盘，日期 1982-03-23—2002-07-25；个人赛 638 盘，日期 1977-08-25—2002-09-19。全部来源 links 为 `19x19`，`event_id`、`duplicate_of_id`、round 均 NULL；两个值无 selected-event 额外成员。包内零 event owner、零 alias 提案、`album_links=[]`。这是 1,539 盘的旧冻结范围和 16,929 个理论语言槽上限，实际显示增益尚为零。

生产者 manifest 的 **15/15 文件字节数与 SHA-256 全部复算一致**；协议与旧独立审核副本和 docs 原件完全相同。22 条单项 pending 校验均通过精确文字/模板检查；整包 pending 校验报告完整复现。报告里的 `pending=0` 来自未通过 category owner 闸后的依赖计数；原候选实际 22/22 pending。没有运行 importer、连接任何数据库、操作 clone、修改应用代码或提交。

| 固定工件 | SHA-256 |
|---|---|
| producer manifest（字节） | `b031109af732deb53663e33901f7d76defe1da2823e1348c396773d3051d76fa` |
| producer bundle（字节） | `9ab9e55ef76d8b4d064a7706b131ce62829d35b9e800700a6ff0fbee891a2273` |
| producer bundle（规范 JSON） | `fd19b75b38308baeaf0b695f44f8b4ccac9600eceb5bd2894638990a561bd51a` |
| review manifest（字节） | `75174bda50e9f314324d1cd19ff70b38a44dff6d1d9952709f867958971a7513` |
| 22 来源语义签署 | `636657bf42c6c95033bc18c30e1be279a9a708ab1cfae726d113b0255abd8be4` |
| 两类别签署 | `9c9471774885dbc3829f090d08accd35e7f2625ac0fc53a56a69017ebeb470d1` |
| 十一语模板签署 | `38197a81b6da4d599b900cd76038f827f579dfd999d13abbf4ecc97ccf2a50f6` |

审查目录：`~/.local/share/kifu-name-audit/2026-10-03/generic-classification-v2-22-source-review-sol/`，0700；工件 0400。保留 source bundle、完整 raw scopes、producer manifest、协议及旧审核副本，并冻结 `source-decisions.signed.json`、`category-reviews.signed.json`、`template-reviews.signed.json`、`review-result.json` 与文件清单。producer 目录未改。

最终 binder 的精确阻塞：旧 inventory 是 `2026-10-02T22:10:26.244060Z` 的只读快照，记录 hash `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`；本次核对文件字节与快照范围，未从数据库重算当前库存。旧 catalog `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09` 的 capture 实际对应丁波 `raw_player`，不是两个 `raw_event` 的 owner/name 前像，不能证明它们当前可 create。

Binder 须在实际目标重新获取 inventory/catalog、两个精确 raw_event owner 及各十一语 name 前像，明确 create 或使用既有 ID；核对当前完整出现范围并重算相关 bundle hashes。随后由真实 actor 绑定 capture/source-candidate hash；**绑定先于独立最终 candidate review**。本次类别/模板语义签署可作为已审依赖，若目标 raw/category、模板或范围变化必须重新核对，不得批量移植为 22 个候选批准。实际最终审核须保留对应 reviewer/model 与时间，模板审核者须与 candidate reviewer 一致。全部 22 候选最终签署后再通过既有 validator 与 importer dry-run/apply 门槛；本备忘录不冒充当前写就绪或三组 33 格完成。
