# 李昌镐 ID 143：34 槽位 v2 包独立审核（暂缓）

审核者 `/root/lee_34_bundle_independent_sol`，调度模型 **`gpt-6-sol`、推理强度 `high`**；无法独立读取运行时模型标识。2026-10-02 本轮只读核对，不签名、不运行 dry-run、apply、undo，也不写正式库或隔离库。结论：**HOLD，待生产者修订未签包后重新独立审核**。

## 已核对的有限范围

受审未签文件为 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-34-current-prod/bundle-corrected-current-preimages-unsigned.json`，文件 SHA-256 `d6058561f8e8cc859bb5d784308efe887eda74729254146f2b7f7d11e4b06f13`，记录的 canonical bundle SHA-256 `215c28502d51ec0158c3f52723b8719db7a5fcdeb0ce9a8096c149e82be29af7`；它是未冻结草案，不是已审可导入包。其 `bundle_format=2`，34 条链接全为 `player:143` 的 `black`／`white` 槽位，11 个成员和候选为 `cn,de,en,es,fr,jp,ko,ru,tr,tw,ua`。`bundle_format=2` 对这些棋手槽位适用；本批没有 `selected_event` 链接。

34 个 `(album_id, side)` 与受控独立身份审阅 JSON（SHA-256 `0062e6c29ef0e12318de7e3c649f1b64ab9df5fee364035738519e477d1958b7`）的 33 个 `PASS` 加 `98043/black` 一个 `PASS_ORIGINAL_GAME_OVERRIDE` **集合完全相同**。24 个 `HOLD` 以及原五项 `40212/black`、`64489/black`、`83228/black`、`97368/white`、`98003/black` 均不在此包。2,140 个精确原文槽位的 CSV 重新计算得到 `raw_scope_sha256=43b19733404467dbe5300258627767d32ecd13138de7ac81d26a5a720acac9ec`，与包相同。五份 2010–2014 专门赛程页面的本地完整捕获字节 SHA-256 均与独立审阅记录一致；`98043` 原始 CyberOro 棋谱和韩国棋院人物页的捕获文件哈希也与审阅记录一致。`98043` 的赛程行有棋手颜色与胜者冲突，原始全盘棋谱是该项的裁定依据；不得把它改写成赛程一致。

现时只读生产捕获时间 `2026-10-02T10:30:31.761425Z`；隔离克隆完整 v2 inventory 时间 `10:26:16.351327Z`，逐项只读前像时间 `10:32:09.195312Z`。生产捕获摘要 SHA-256 `3e43dd57ef60b2764e097e85f43d3a3e45fa86e892c1060545b1fbd63c41ef01`；克隆 inventory 文件 SHA-256 `cf4f2a267885163d947cf668bcc5a83c8e6f9e4d474eec76329b8140bfe93595`。生产和克隆的 base inventory 内容哈希均为 `66b8946d908468c5f9c8f0dc8ef4b4ceddb76d840ef42f5cff5122fc5744b3a3`，生产 catalog 哈希为 `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`。两份捕获报告 34/34 个目标 FK 为 `NULL`，34/34 个关联对象哈希、期望上下文及生产／克隆 SGF UTF-8 哈希相符。审核者核对了捕获文件结构、目标计数和首项目标的具名关联对象哈希；**本轮未另行重捕获线上事务**。生产没有 selected-event 表，克隆有选择表但当前远端运行时不能生成 format-4 inventory；这个限制不改变本批 34 个棋手链接所需的 format-2 语义。

十一语已批准来源显示名为：`cn` 李昌镐；`tw,jp` 李昌鎬；`ko` 이창호；`en,de,es,fr,tr` Lee Chang-ho；`ru` Ли Чханхо；`ua` Лі Чхан Хо。现时生产和克隆前像摘要一致：五个现存 `cn,en,jp,ko,tw` 名称行，六个缺失 `de,es,fr,ru,tr,ua` 名称行。来源批准是旧的来源层决定；本轮没有签署这些名字与新 34 项载荷的绑定。

## 阻塞与生产者修订要求

1. **十一条名称尚未绑定。** 草案的每条 `name_preimage_sha256` 和 `preimage_binding` 均为 `null`，也没有当前批次的最终候选审核签名。由不同于本审核者的生产者用同一新鲜捕获逐语绑定五个现存行哈希和六个显式 `null`，记录真实 `actor_id`、模型、捕获时间／哈希、绑定时间及来源候选行哈希；冻结后再交本审核者独立批准。不得把旧五槽位包的最终绑定审核签名直接转移到本批。
2. **俄语候选丢失冲突决定。** 草案 `ru` 行仅保留 `Ли Чханхо` 显示和来源审核引用，却遗漏了已批准来源行中的 `conflict_adjudication` 与 `excluded_candidates`。须从受控 `source-reviewed-candidates.jsonl` 中的原批准俄语行原样保留这两项及其裁定／排除范围；`Ли Чхан Хо`、`Ли Чангхо` 不得静默消失或变成额外显示候选。
3. **`98043/black` 两项来源核验缺少必需原文摘录。** 其 `CyberOro original game SGF` 和 `Korean Baduk Association official player profile` 两个 `source_checks` 有真实 `body_sha256` 与 `identity_match`，但均缺 `body_excerpt`。当前 `_v2_scope` 对每条来源核验要求非空 `body_excerpt`；生产者须从已保存且哈希匹配的完整正文补上准确摘录，不可编造。其他 33 个赛程来源核验有摘录。
4. **冻结与签名仍为空。** 34 条 `identity_review.status=pending`，没有 `scope_frozen_at`、`scope_sha256` 或独立身份签名。生产者完成上面修订后固定精确载荷与哈希，保留原生产者历史和来源证据；本审核者再复核并签署。未签草案不应称作 validator-ready、dry-run-ready 或生产导入授权。

对现有未签包运行只读 `scripts/kifu_name_batch.py validate`（使用上述克隆 v2 inventory、固定 registry `2026-10-02.3` 与受控研究 JSONL）返回退出码 **1**：`ready=false`、`write_ready=false`，34 条链接均缺已批准身份审核，11 条候选均缺独立审核的前像绑定。候选不在有限已批准链接范围内的级联错误由身份审核未签引起。该报告未能检查签署后会暴露的俄语冲突字段和 `98043` 摘录问题，因此上列人工审核阻塞仍必须先修复。没有创建已签 bundle、没有 bundle 审核哈希或 clone dry-run 报告。
