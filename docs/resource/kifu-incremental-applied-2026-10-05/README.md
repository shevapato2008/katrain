# 已实际写入的增量名称与来源页面

每个压缩 JSON 保存具体环境的已签 bundle、source registry、研究证据、真实 dry-run/apply/verify 回执；只收录两库已经提交并核对名称的批次，不把 pending 研究计为交付。新棋手批还包含 authoritative_pages 同步回执。

首批来源页面迁移另存 `player-pages-{TEST,PROD}.json.gz`：包括预览、提交后的前后值及重复预览的零变更结果。页面字段只追加已批准证据的正面来源、官方身份锚点和明确同人档案桥；URL 精确去重，已有手工元数据保留。

`kifu_players.authoritative_pages` 是 JSON 数组，每项含 `url`、`source_id`、`language`、`role`、`evidence_ids`。`role` 表示登记的来源类别，维基或专业资料不会被标成官方。后续棋手主页可按棋手 ID 使用这些页面及现有棋谱 FK，不需要再次找源；生平和名局介绍尚未开发。

统计网页是带时间的正式库快照；五语齐全指实体名称已独立批准并写库，完整覆盖指棋局双方棋手及赛事类型均具备五语名称。未关联实体的原文展示、中文首遍和未完成语言不计入这一覆盖率。

`kifu-event-literal-593-594-20261009.json.gz` 是 TEST/PROD 实际 593 owner 审定与 594 五语字面标题入库的有界归档。包含冻结选择与来源、122-owner 审核、610 名称及研究全文、两库原始与 owner 后捕获、独立根审、prepare/dry-run/apply/verify、两库各 12 项 HTTP 回执，以及 PROD 938 局严格资格增量统计。两份 173,025 关联行的 format-4 inventory 仅保留文件与快照 SHA-256 引用，不重复装入归档；原 SGF 不在此归档中复制。字面 raw title 资格与 64/85 正式赛事实体完成数分开统计。

`kifu-next16-595-20261009.json.gz` 是 TEST/PROD 实际 batch595 的有界归档（619,574 字节；SHA-256 `13ec2d09958e12f06f930ceefc62d3c77eba4c3e15fce2058110346c38398c67`）。两库各 16 个名称与 16 条研究证据已提交、读回并完成五语资格；各 16 条棋手资料 URL 已同步并验证，旧页面元数据保留；各 10 项实际 HTTP 样本通过。归档包含实际 v2 bundle/研究/registry、两库 16-owner scoped capture、执行审批和 baseline/dry-run/apply/verify、页面 plan/审批/preview/apply/verify、HTTP 回执、PROD 158 局有界统计、源选择与 76 个原始来源捕获字节及 helper review。两份 format-4 全库 inventory 只记文件与快照 SHA-256，不重复装入约 17.3 万行内容；含全库 inventory 的 root-reviewed-fresh 文件也只存哈希与审查摘要，原始 SGF 不复制。

归档来源清单：`selection20.json`、`source-only20.json`、`root-next16-source-review.json`、两库 `ENV-root-reviewed-fresh.json.gz` 的哈希与有界审查元数据来自主工作目录；实际执行文件与两库名称 receipt 只从 `bounded-version-v2/` 取。初次 66 字符 registry 版本在 TEST 插入前报 `VARCHAR(64)` 错误并回滚，旧 bundle 仅以失败原因记录，未作为实际 batch595 入档。查询耗时只是这两库 10 项样本观察，不代表全局性能保证。
