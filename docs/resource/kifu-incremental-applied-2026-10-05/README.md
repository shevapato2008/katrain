# 已实际写入的增量名称与来源页面

每个压缩 JSON 保存具体环境的已签 bundle、source registry、研究证据、真实 dry-run/apply/verify 回执；只收录两库已经提交并核对名称的批次，不把 pending 研究计为交付。新棋手批还包含 authoritative_pages 同步回执。

首批来源页面迁移另存 `player-pages-{TEST,PROD}.json.gz`：包括预览、提交后的前后值及重复预览的零变更结果。页面字段只追加已批准证据的正面来源、官方身份锚点和明确同人档案桥；URL 精确去重，已有手工元数据保留。

`kifu_players.authoritative_pages` 是 JSON 数组，每项含 `url`、`source_id`、`language`、`role`、`evidence_ids`。`role` 表示登记的来源类别，维基或专业资料不会被标成官方。后续棋手主页可按棋手 ID 使用这些页面及现有棋谱 FK，不需要再次找源；生平和名局介绍尚未开发。

统计网页是带时间的正式库快照；五语齐全指实体名称已独立批准并写库，完整覆盖指棋局双方棋手及赛事类型均具备五语名称。未关联实体的原文展示、中文首遍和未完成语言不计入这一覆盖率。

`kifu-event-literal-593-594-20261009.json.gz` 是 TEST/PROD 实际 593 owner 审定与 594 五语字面标题入库的有界归档。包含冻结选择与来源、122-owner 审核、610 名称及研究全文、两库原始与 owner 后捕获、独立根审、prepare/dry-run/apply/verify、两库各 12 项 HTTP 回执，以及 PROD 938 局严格资格增量统计。两份 173,025 关联行的 format-4 inventory 仅保留文件与快照 SHA-256 引用，不重复装入归档；原 SGF 不在此归档中复制。字面 raw title 资格与 64/85 正式赛事实体完成数分开统计。

`kifu-next16-595-20261009.json.gz` 是 TEST/PROD 实际 batch595 的有界归档（619,574 字节；SHA-256 `13ec2d09958e12f06f930ceefc62d3c77eba4c3e15fce2058110346c38398c67`）。两库各 16 个名称与 16 条研究证据已提交、读回并完成五语资格；各 16 条棋手资料 URL 已同步并验证，旧页面元数据保留；各 10 项实际 HTTP 样本通过。归档包含实际 v2 bundle/研究/registry、两库 16-owner scoped capture、执行审批和 baseline/dry-run/apply/verify、页面 plan/审批/preview/apply/verify、HTTP 回执、PROD 158 局有界统计、源选择与 76 个原始来源捕获字节及 helper review。两份 format-4 全库 inventory 只记文件与快照 SHA-256，不重复装入约 17.3 万行内容；含全库 inventory 的 root-reviewed-fresh 文件也只存哈希与审查摘要，原始 SGF 不复制。

归档来源清单：`selection20.json`、`source-only20.json`、`root-next16-source-review.json`、两库 `ENV-root-reviewed-fresh.json.gz` 的哈希与有界审查元数据来自主工作目录；实际执行文件与两库名称 receipt 只从 `bounded-version-v2/` 取。初次 66 字符 registry 版本在 TEST 插入前报 `VARCHAR(64)` 错误并回滚，旧 bundle 仅以失败原因记录，未作为实际 batch595 入档。查询耗时只是这两库 10 项样本观察，不代表全局性能保证。

`kifu-event-chinese-596-597-20261009.json.gz` 是 TEST/PROD 实际 batch596 owner 与 batch597 五语字面标题入库的有界归档（976,901 字节；SHA-256 `d6e5862a4380d55ecee8a787583a8aacddd3fa075560bc4dbe43b81beee39b7a`）。每库实际写入并核验 150 个 raw title owner、750 个名称和 750 条研究证据，两库各 12 项 HTTP 样本通过。含原始 C76/Han source-only、冻结选择与来源包、独立根审、两库 capture/prepare/dry-run/apply/verify、r6 native 构建回执、helper 源码与审核、校正后的 PROD 进度及只读校正审计。r6 恢复的较早 1,241 个中文混合标题 owner 与本批新 150 个 owner 分别计数；初次 597 bounded 诊断统计未作为最终进度收录。两份 173,025 关联行的 format-4 inventory 仅保留文件/快照 SHA-256 与尺寸引用，原 SGF 与全库目录不重复打包；字面标题不计为新增正式赛事实体 ID。

`../kifu-reader-zh-ko-r7-cloud-deployment-20261009.json.gz` 是 Task2 代码提交 `536718120c3c8630ba56b4d2a656f120e93152af` 的 TEST/PROD 实际读端发布归档（129,029 字节；SHA-256 `c71ede77d5a3565afe76648bcfd44961f2c183b66ba568cd607f84cf8a15886b`）。保存每环境 web 4 个、importer 6 个批准变更文件及补丁、native adapter 审核、最终 release tar/manifest 哈希引用、运行时文件和环境哈希、健康结果与两库各 12 项 HTTP 样本。TEST 保留旧 r5 镜像，通过 release 目录的 4 个持久只读源码 bind 提供 r7；容器重建或回滚后，须恢复四个 bind 并复核文件 SHA。TEST 失败的镜像构建不计发布成功。PROD 使用已验证的新 r7 镜像且无新增 bind。归档不含完整镜像、原始环境变量、模型或数据库主体；它与 596/597 名称入库归档分别记录。

`kifu-player-weng-598-and-reader-r8-20261009.json.gz` 保存两库实际 batch598、翁子瑜韩文名 `웡쯔위` 的来源与独立审批、名称 dry-run/apply/verify、各 13 项 HTTP 样本，以及每库新增的官方棋手名录与 u-go 本人页两条资料链接。归档 415,428 字节，SHA-256 `06449d74d1dc8c12b629b649595b495a7b81d8fd3041db9ceaf0d1d4e7452d1c`。同时记录 r8 三文件原生读端发布、旧 batch332 四位棋手的不可变创建证明与兼容修复审核、两库五位韩文读端样本；web 镜像保持不变，持久只读覆盖源码，其他容器与环境保持。r8 上的正式库实际统计为棋手 1,724/3,698、赛事类型 64/85、双棋手五语棋局 133,901/173,025、严格完整卡片 44,320/173,025。统计只重算翁子瑜的八盘增量并确认旧完成集合已恢复，其他棋局沿用实际597基线；全库 inventory 只存哈希引用，未复制原 SGF。此批未重启 RK3562。

`kifu-four-mandarin-599-20261009.json.gz` 封存两库实际 batch599：黄家胤、杨以伦、柯沛辰、王紫涵各补韩文名，共每库四个名称和四条研究证据，76盘物理棋谱保持；每库16项实际查询通过。归档 1,274,960 字节，SHA-256 `99fd5971c15803c9dfb3bf2d2677845b727c5da442daf69bdbe868ded6119806`。四位棋手所需七个来源URL已存在，原生只读预览确认链接归属；未新增链接、未执行可选页面证据合并。正式库棋手1,728/3,698、赛事类型64/85、双方棋手五语棋局133,965/173,025、严格完整卡片44,360/173,025（正式11,612，raw32,748）。统计重算76盘增量，其他沿用实际598，并核对全局完成集合；全库inventory只存哈希引用。初版误述普通话区域的候选在写入前被审核拒绝，实际入库仅使用已改正并独立批准的v2。未重启RK3562。
