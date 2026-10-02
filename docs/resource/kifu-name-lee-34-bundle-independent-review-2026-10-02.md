# 李昌镐 ID 143：34 槽位 v2 包独立审核与克隆只读演练

审核者 `/root/lee_34_bundle_independent_sol`，调度模型 **`gpt-6-sol`、推理强度 `high`**；无法独立读取运行时模型标识。首轮发现缺项，暂缓签署；生产者修订后于 **`2026-10-02T12:21:28.356763Z`** 完成独立复核与实际签署。**最终结论：PASS，34 个精确关联与 11 条绑定姓名的有限包通过离线验证和隔离克隆只读 dry-run。** 没有 apply、undo、生产写入或克隆写入；此结论不是全库覆盖率或生产导入批准。

## 修订后最终载荷与验证

修订输入 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-34-current-prod/bundle-34-current-bound-unsigned-pending-review.json` 文件 SHA-256 `815566ad7a1cc10033e29fbd500b0a322a220c04ace059774b04a363bc928d68`，canonical SHA-256 `4abfde85df59c6871ced05650d72c738292f6af5818fecb1d2aa6ee80647124d`。生产者 `/root/lee_34_fresh_capture_luna` 绑定时间 `11:07:04Z`，身份范围冻结时间 `11:07:46Z`；本审核者签署在其后，未冒用生产者或既有五槽位审核签名。完整身份范围 `scope_sha256=1f4e29a2d0892c37153ea747f479fce46366b69a64ab10f509e1e0521f418e67`。保留原草案的 `identity_basis` 作为当时的未批准说明，最终决定由本轮 `review_conclusion` 与 `status=approved` 表示。所有 34 条链接共享同一个精确范围决定。

逐项复核结果：34 个链接与独立 58 项身份审阅中的 34 个 PASS 完全相同，24 HOLD 与原五项均不在包中。全部 34 个生产与隔离克隆 SGF UTF-8 哈希、具名关联对象哈希、完整期望上下文和目标 `NULL` FK 均对上；2,140 个原文槽位的范围哈希不变。33 条一致的专门赛程记录的行哈希、原文摘录与五份完整捕获文件的正文哈希对上。`98043/black` 的原始 CyberOro 棋谱和韩国棋院人物页均有准确原文摘录，分别在按 CP949、UTF-8 解码的哈希匹配捕获中出现；该项仍依原始全盘棋谱覆盖冲突赛程行。36 条共享来源核验包含 34 条赛程行（其中 `98043` 一行明确冲突）、原始棋谱及人物页；每个链接用同一来源集合及冻结范围哈希，没有把冲突赛程行称为一致证据。

十一条名称候选与受控来源已批准行逐字段吻合，来源行哈希与 11 个 `source_candidate_sha256` 均对上。绑定使用同一生产只读捕获文件 SHA-256 `0e9ee2e005c7101fba6d9bc230d11827ff8d19e869b7f98aebfe415d40ec6c15`；五个现存名称行的完整对象哈希及六个显式 `null` 与生产、克隆捕获一致。俄语 `Ли Чханхо` 的 `conflict_adjudication`、`excluded_candidates` 与原来源批准行相同，排除异写未丢失。研究哈希在固定 registry `2026-10-02.3` 下由离线 validator 重新核验。

已签包保存在受控目录 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-34-v2-reviewed/`：目录 `0700`，三个文件均 `0600`，生产者未签原件未改。`bundle-reviewed.json` 文件 SHA-256 **`8ff073ec596872671bf8b561deae2b71270f4e19fe16dc5738711689e9442a74`**，导入器 canonical bundle SHA-256 **`0ba47b3ddd92a2bde34ec6564b887b14509534a4ee8bb53530cf904a7a7cceca`**；已签 link-set SHA-256 `23e11c267ce4ec104cd1c0a5750179d5c3ddbb98c04bf5373b532c2377d34183`，候选数组 canonical SHA-256 `b45532023c2e73c7120177cd3bedc73f0efccddd654b9b98861bd3a78357ccc8`。`validation-report.json` 文件 SHA-256 `696faaefd44d8f4fd1c0e498f1308570ceca9a214cbecf0aca2b5d3edc2770fb`；`review-manifest.json` 文件 SHA-256 `1e268794381321767e9b837923dd2b6ee15e24a2867bab65f9b73862cd3f98e8`。

`scripts/kifu_name_batch.py validate` 对已签包、隔离克隆 v2 inventory、固定 registry 及受控研究 JSONL 返回退出码 **0**：`ready=true`、`write_ready=true`、11 approved、0 missing/pending/rejected、`errors=[]`、`write_errors=[]`。随后通过 SSH 隧道在本仓库调用 `dry_run_bundle`；连接前核实数据库名为 **`kifu_name_rehearsal_20261002`** 且 `default_transaction_read_only=on`，并以已签 canonical bundle SHA-256 为可信参数。dry-run 返回 `ready=true`、`write_ready=true`、34 个预期 `affected_albums`、`estimated_undo_rows=56`，无错误；它重新核对克隆完整 inventory、catalog、34 份 SGF、关联及 11 条名称前像。隧道已关闭。使用的是克隆 format-2 base inventory；生产没有选择表，本批只关联棋手黑白槽位，因此没有 `selected_event` 链接语义。后续若考虑正式库操作，仍须重新核对当时生产事务的全部前像与既有发布门槛。

## 首轮暂缓记录（修订前历史）

### 已核对的有限范围

受审未签文件为 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-34-current-prod/bundle-corrected-current-preimages-unsigned.json`，文件 SHA-256 `d6058561f8e8cc859bb5d784308efe887eda74729254146f2b7f7d11e4b06f13`，记录的 canonical bundle SHA-256 `215c28502d51ec0158c3f52723b8719db7a5fcdeb0ce9a8096c149e82be29af7`；它是未冻结草案，不是已审可导入包。其 `bundle_format=2`，34 条链接全为 `player:143` 的 `black`／`white` 槽位，11 个成员和候选为 `cn,de,en,es,fr,jp,ko,ru,tr,tw,ua`。`bundle_format=2` 对这些棋手槽位适用；本批没有 `selected_event` 链接。

34 个 `(album_id, side)` 与受控独立身份审阅 JSON（SHA-256 `0062e6c29ef0e12318de7e3c649f1b64ab9df5fee364035738519e477d1958b7`）的 33 个 `PASS` 加 `98043/black` 一个 `PASS_ORIGINAL_GAME_OVERRIDE` **集合完全相同**。24 个 `HOLD` 以及原五项 `40212/black`、`64489/black`、`83228/black`、`97368/white`、`98003/black` 均不在此包。2,140 个精确原文槽位的 CSV 重新计算得到 `raw_scope_sha256=43b19733404467dbe5300258627767d32ecd13138de7ac81d26a5a720acac9ec`，与包相同。五份 2010–2014 专门赛程页面的本地完整捕获字节 SHA-256 均与独立审阅记录一致；`98043` 原始 CyberOro 棋谱和韩国棋院人物页的捕获文件哈希也与审阅记录一致。`98043` 的赛程行有棋手颜色与胜者冲突，原始全盘棋谱是该项的裁定依据；不得把它改写成赛程一致。

现时只读生产捕获时间 `2026-10-02T10:30:31.761425Z`；隔离克隆完整 v2 inventory 时间 `10:26:16.351327Z`，逐项只读前像时间 `10:32:09.195312Z`。生产捕获摘要 SHA-256 `3e43dd57ef60b2764e097e85f43d3a3e45fa86e892c1060545b1fbd63c41ef01`；克隆 inventory 文件 SHA-256 `cf4f2a267885163d947cf668bcc5a83c8e6f9e4d474eec76329b8140bfe93595`。生产和克隆的 base inventory 内容哈希均为 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`，生产 catalog 哈希为 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`。两份捕获报告 34/34 个目标 FK 为 `NULL`，34/34 个关联对象哈希、期望上下文及生产／克隆 SGF UTF-8 哈希相符。审核者核对了捕获文件结构、目标计数和首项目标的具名关联对象哈希；**本轮未另行重捕获线上事务**。生产没有 selected-event 表，克隆有选择表但当前远端运行时不能生成 format-4 inventory；这个限制不改变本批 34 个棋手链接所需的 format-2 语义。

十一语已批准来源显示名为：`cn` 李昌镐；`tw,jp` 李昌鎬；`ko` 이창호；`en,de,es,fr,tr` Lee Chang-ho；`ru` Ли Чханхо；`ua` Лі Чхан Хо。现时生产和克隆前像摘要一致：五个现存 `cn,en,jp,ko,tw` 名称行，六个缺失 `de,es,fr,ru,tr,ua` 名称行。来源批准是旧的来源层决定；本轮没有签署这些名字与新 34 项载荷的绑定。

### 阻塞与生产者修订要求

1. **十一条名称尚未绑定。** 草案的每条 `name_preimage_sha256` 和 `preimage_binding` 均为 `null`，也没有当前批次的最终候选审核签名。由不同于本审核者的生产者用同一新鲜捕获逐语绑定五个现存行哈希和六个显式 `null`，记录真实 `actor_id`、模型、捕获时间／哈希、绑定时间及来源候选行哈希；冻结后再交本审核者独立批准。不得把旧五槽位包的最终绑定审核签名直接转移到本批。
2. **俄语候选丢失冲突决定。** 草案 `ru` 行仅保留 `Ли Чханхо` 显示和来源审核引用，却遗漏了已批准来源行中的 `conflict_adjudication` 与 `excluded_candidates`。须从受控 `source-reviewed-candidates.jsonl` 中的原批准俄语行原样保留这两项及其裁定／排除范围；`Ли Чхан Хо`、`Ли Чангхо` 不得静默消失或变成额外显示候选。
3. **`98043/black` 两项来源核验缺少必需原文摘录。** 其 `CyberOro original game SGF` 和 `Korean Baduk Association official player profile` 两个 `source_checks` 有真实 `body_sha256` 与 `identity_match`，但均缺 `body_excerpt`。当前 `_v2_scope` 对每条来源核验要求非空 `body_excerpt`；生产者须从已保存且哈希匹配的完整正文补上准确摘录，不可编造。其他 33 个赛程来源核验有摘录。
4. **冻结与签名仍为空。** 34 条 `identity_review.status=pending`，没有 `scope_frozen_at`、`scope_sha256` 或独立身份签名。生产者完成上面修订后固定精确载荷与哈希，保留原生产者历史和来源证据；本审核者再复核并签署。未签草案不应称作 validator-ready、dry-run-ready 或生产导入授权。

首轮对未签包运行只读 `scripts/kifu_name_batch.py validate`（使用上述克隆 v2 inventory、固定 registry `2026-10-02.3` 与受控研究 JSONL）返回退出码 **1**：`ready=false`、`write_ready=false`，34 条链接均缺已批准身份审核，11 条候选均缺独立审核的前像绑定。候选不在有限已批准链接范围内的级联错误由身份审核未签引起。该报告未能检查签署后会暴露的俄语冲突字段和 `98043` 摘录问题，因此上列人工审核阻塞当时必须先修复。首轮没有创建已签 bundle、bundle 审核哈希或 clone dry-run 报告；修订后的结果见文首。
